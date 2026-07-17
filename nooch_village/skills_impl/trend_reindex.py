"""trend_reindex — Sid's dagelijkse trend-re-index-skill.

De skill uit het raadsvoorstel "Trendsignalering met eerlijke re-indexering".
Wat hij doet, elke puls, uit zichzelf:

  1. Genereert TOT `trend_reindex_max_candidates` (default 5) nieuwe kandidaat-termen,
     verankerd aan het Nooch-domein en de bestaande watchlist (LLM-ladder, begrensd,
     fail-closed). Het is een PLAFOND, geen quotum: 0/2/3 mag, een lege dag mag.
  2. Haalt per term één Google-Trends-request op MET de ankerset erbij, zodat ze op
     dezelfde 0-100-schaal staan (term + 3 ankers = 4 termen, onder Google's max van 5).
  3. Her-indexeert op een basisjaar (jaargemiddeldes) i.p.v. op de laatste piek. Levert
     de multiplier t.o.v. de historische baseline, het onderscheid piek-versus-trend, en
     van-nul-emergentie (baseline ~0).
  4. Markeert een term pas als SIGNAAL als hij de baseline met een factor overschrijdt EN
     meerdere COMPLETE maanden aanhoudt (geen partiële blip).
  5. Houdt de best presterende op een append-only watchlist; laat de rest vallen.
  6. Gevolgde termen → append-only observatiereeks (data/trend_signals.jsonl). Opvallende
     bevindingen → fuzzy input voor de curate-poort (de Librarian schrijft, niet Sid).

Grenzen (hard, in code):
  - ALLEEN LEZEN naar buiten: haalt data op, publiceert/verstuurt/koopt niets, wijzigt
    geen website. De enige schrijf-acties zijn de eigen append-only bestanden.
  - GEEN levertiming-claims: zoekinteresse is geen verkoop en geen inkoopmoment. De
    synthese-prompt verbiedt die framing expliciet.
  - DAG-CAP + FAIL-CLOSED: hoogstens `max_candidates` termen en één begrensde LLM-call
    per puls; valt de LLM weg, dan her-indexeert hij alleen de bestaande watchlist en
    meldt dat de kandidaat-generatie eruit lag (geen verzonnen termen).

Pure helpers + injecteerbare `_fetch`/`reason_fn` (testbaar zonder netwerk of LLM).
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from collections import defaultdict

from nooch_village.skills import Skill
from nooch_village.skills_impl.trends import _drop_partial, _USER_AGENT

log = logging.getLogger(__name__)

_DEFAULT_ANCHORS = ["vegan shoes", "sustainable shoes", "plastic free shoes"]
_TIMEFRAME_DEFAULT = "today 5-y"
_WATCHLIST_FILE = "trend_watchlist.json"
_SIGNALS_FILE = "trend_signals.jsonl"

# Google Trends staat max 5 termen per request toe. Met 3 ankers past er 1 kandidaat +
# ankers in één request (4 ≤ 5), zodat kandidaat en ankers op dezelfde schaal staan.
_MAX_ANCHORS = 4


# ─────────────────────────────────────────────────────────────────────────────
# Pure re-index-helpers (geen netwerk, geen pandas nodig — werken op [(date, value)])
# ─────────────────────────────────────────────────────────────────────────────

def series_from_df(df, term: str):
    """DataFrame (pytrends interest_over_time) → [(date, float)] voor `term`, de lopende
    partiële week eraf. Fail-closed: geen kolom / geen complete week → [] (nooit een
    partiële rij terugleveren)."""
    if df is None or getattr(df, "empty", True) or term not in df:
        return []
    complete = _drop_partial(df)
    if complete is None or getattr(complete, "empty", True):
        return []
    out = []
    for idx, val in complete[term].items():
        d = idx.date() if hasattr(idx, "date") else idx
        try:
            out.append((d, float(val)))
        except (TypeError, ValueError):
            continue
    return out


def yearly_means(series) -> dict:
    """{jaar: gemiddelde} over alle datapunten van dat jaar."""
    buckets = defaultdict(list)
    for d, v in series:
        buckets[d.year].append(v)
    return {y: sum(vs) / len(vs) for y, vs in buckets.items() if vs}


def monthly_means(series) -> dict:
    """{(jaar, maand): gemiddelde}."""
    buckets = defaultdict(list)
    for d, v in series:
        buckets[(d.year, d.month)].append(v)
    return {ym: sum(vs) / len(vs) for ym, vs in buckets.items() if vs}


def complete_months(series) -> list:
    """Gesorteerde [(jaar, maand)] ZONDER de laatste (lopende, mogelijk onvolledige) maand.
    De maand van het laatste datapunt is per definitie nog niet af en telt niet mee in de
    'meerdere complete maanden aanhoudend'-toets."""
    months = sorted(monthly_means(series).keys())
    return months[:-1] if len(months) > 1 else []


def reindex_metrics(series, *, base_year=None, factor=2.0, min_months=3,
                    emergence_floor=1.0) -> dict | None:
    """Her-index één term-reeks op een basisjaar. Levert de eerlijke maten uit het
    raadsvoorstel. Fail-closed: te weinig data → None.

    baseline        = gemiddelde over het basisjaar (default: het vroegste jaar in de reeks).
    index_latest    = laatste-COMPLETE-maand-gemiddelde ÷ baseline (multiplier), of None bij
                      van-nul-emergentie (baseline ≤ emergence_floor → een deling zou ontploffen).
    peak            = hoogste weekwaarde in de hele reeks.
    recent_sustained= gemiddelde over de laatste `min_months` complete maanden.
    sustained       = houden ál die maanden ≥ factor × baseline aan? (de anti-blip-toets)
    signal_type     = 'emergence' | 'trend' | 'peak' | 'flat'
      emergence : baseline ≤ floor en recent duidelijk boven de floor (van-nul-opkomst)
      trend     : index_latest ≥ factor EN sustained (aanhoudend boven de drempel)
      peak      : ooit een piek ≥ factor × baseline, maar recent NIET aanhoudend (een blip)
      flat      : niets van dat alles
    is_signal       = signal_type in {'emergence', 'trend'}   (een blip is bewust géén signaal)
    """
    if len(series) < 8:                       # < ~2 maanden weekdata: te dun om te her-indexeren
        return None
    ym = yearly_means(series)
    if not ym:
        return None
    by = base_year if base_year in ym else min(ym)
    baseline = ym[by]
    peak = max(v for _, v in series)

    months = complete_months(series)
    recent = months[-min_months:] if len(months) >= min_months else months
    mm = monthly_means(series)
    recent_vals = [mm[m] for m in recent] if recent else []
    recent_sustained = (sum(recent_vals) / len(recent_vals)) if recent_vals else 0.0

    from_zero = baseline <= emergence_floor
    index_latest = None if from_zero else round(recent_sustained / baseline, 2)

    threshold = factor * baseline
    sustained = (
        len(recent) >= min_months
        and all(mm[m] >= threshold for m in recent)
    )
    ever_peak = peak >= threshold

    if from_zero and recent_sustained > emergence_floor:
        signal_type = "emergence"
    elif not from_zero and index_latest is not None and index_latest >= factor and sustained:
        signal_type = "trend"
    elif ever_peak:
        signal_type = "peak"
    else:
        signal_type = "flat"

    return {
        "base_year": by,
        "baseline": round(baseline, 3),
        "index_latest": index_latest,
        "peak": round(peak, 1),
        "recent_sustained": round(recent_sustained, 2),
        "recent_months": [f"{y}-{m:02d}" for (y, m) in recent],
        "sustained": sustained,
        "from_zero": from_zero,
        "signal_type": signal_type,
        "is_signal": signal_type in ("emergence", "trend"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Kandidaat-generatie (LLM-ladder, begrensd, fail-closed)
# ─────────────────────────────────────────────────────────────────────────────

def build_candidates_prompt(anchors, watchlist, mission: str, cap: int) -> str:
    """Vraag de LLM om TOT `cap` nieuwe Engelse zoektermen rond duurzame schoenen, die niet
    al in de ankerset of op de watchlist staan. Plafond, geen quotum: minder mag."""
    mission_line = f"Nooch's mission: {mission}\n" if mission else ""
    known = ", ".join(sorted(set(anchors) | set(watchlist))) or "(none)"
    return (
        "You scout emerging search terms for Nooch, a sustainable / vegan / plastic-free "
        "shoe brand. Propose NEW English Google-Trends search terms (2-4 words each) that a "
        "shopper interested in sustainable footwear might search, and that could reveal an "
        "emerging trend.\n"
        f"{mission_line}"
        f"ALREADY TRACKED (do NOT repeat, do NOT trivially reword): {known}\n\n"
        "HARD RULES:\n"
        f"- Return AT MOST {cap} terms. FEWER IS FINE. Quality over quantity; an empty list "
        "is acceptable if nothing new is worth watching.\n"
        "- Footwear/sustainability domain only. No brand names, no delivery/shipping terms, "
        "no purchase-intent phrasing.\n"
        "- Each term must be a plausible real search query, lowercase.\n\n"
        "Return ONLY a JSON array of strings, no prose, no code fences. Example: "
        '["minimalist shoes", "barefoot shoes"]'
    )


def parse_candidates(text: str | None, cap: int) -> list[str]:
    """LLM-output → schone, ontdubbelde lijst van hoogstens `cap` termen. Fail-closed: geen/
    onparseerbaar → []."""
    if not text:
        return []
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    start, end = cleaned.find("["), cleaned.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        data = json.loads(cleaned[start:end + 1])
    except (ValueError, TypeError):
        return []
    out, seen = [], set()
    for item in data:
        if not isinstance(item, str):
            continue
        t = item.strip().lower()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
        if len(out) >= cap:
            break
    return out


def generate_candidates(anchors, watchlist, *, mission="", cap=5, reason_fn=None) -> list[str]:
    """Genereer tot `cap` kandidaat-termen. Eén begrensde LLM-call (dag-cap). Fail-closed:
    geen LLM → [] (de caller her-indexeert dan alleen de watchlist)."""
    if cap <= 0:
        return []
    if reason_fn is None:
        import functools
        from nooch_village.llm import reason
        # max_tokens klein: een handvol korte termen — token-cap per puls.
        reason_fn = functools.partial(reason, call_site="skill_trend_reindex",
                                      max_tokens=200, json_mode=True)
    out = reason_fn(build_candidates_prompt(anchors, watchlist, mission, cap))
    known = {a.lower() for a in anchors} | {w.lower() for w in watchlist}
    return [t for t in parse_candidates(out, cap) if t not in known][:cap]


# ─────────────────────────────────────────────────────────────────────────────
# Curate-hand-off (de Librarian is de enige schrijfweg naar de NotesStore)
# ─────────────────────────────────────────────────────────────────────────────

def signal_to_fuzzy(term: str, m: dict) -> str:
    """Zet een gemarkeerd signaal om naar één regel ruwe curate-input. Bewust NEUTRAAL en
    zonder levertiming-framing: het is zoekinteresse, geen verkoop, geen inkoopmoment."""
    if m["signal_type"] == "emergence":
        body = (f"Search interest for '{term}' emerges from a near-zero baseline "
                f"(recent level {m['recent_sustained']} on Google Trends' 0-100 scale, "
                f"baseline year {m['base_year']}).")
    else:  # trend
        body = (f"Search interest for '{term}' sits at ~{m['index_latest']}x its "
                f"{m['base_year']} baseline and holds across the months "
                f"{', '.join(m['recent_months'])} (re-indexed, not a single-week peak).")
    return (f"INSIGHT (hypothesis): {body} GROUNDS: Google Trends, re-indexed on a base-year "
            f"average against the anchor set; search interest is a signal of attention, NOT "
            f"of sales or delivery timing.")


# ─────────────────────────────────────────────────────────────────────────────
# I/O helpers (append-only)
# ─────────────────────────────────────────────────────────────────────────────

def _load_watchlist(data_dir: str) -> list[dict]:
    path = os.path.join(data_dir, _WATCHLIST_FILE)
    try:
        return json.load(open(path)).get("terms", [])
    except Exception:
        return []


def _save_watchlist(data_dir: str, terms: list[dict]) -> None:
    path = os.path.join(data_dir, _WATCHLIST_FILE)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"terms": terms}, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _append_signal(data_dir: str, record: dict) -> None:
    """Append-only observatiereeks: één JSON-regel per gevolgde term per puls."""
    path = os.path.join(data_dir, _SIGNALS_FILE)
    with open(path, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# De skill
# ─────────────────────────────────────────────────────────────────────────────

class TrendReindexSkill(Skill):
    name = "trend_reindex"
    # rate_limited: pytrends is een onofficieel endpoint met throttling → in de puls met backoff.
    cost = "rate_limited"
    # Schrijft eigen append-only bestanden (watchlist + signals) → niet side-effect-free.
    side_effect_free = False
    description = (
        "Sid's dagelijkse trend-re-index: genereert tot 5 kandidaat-zoektermen, her-indexeert "
        "ze met de ankerset op een basisjaar (multiplier t.o.v. baseline, piek-versus-trend, "
        "van-nul-emergentie), markeert alleen aanhoudende signalen (factor + meerdere complete "
        "maanden), houdt de best presterende op een append-only watchlist en levert opvallende "
        "bevindingen als curate-input. Alleen lezen; geen levertiming-claims; fail-closed."
    )
    input_schema = (
        "payload optioneel: terms: list[str] (override i.p.v. LLM-generatie), "
        "keep: int (hoeveel op de watchlist houden, default 10)."
    )
    output_schema = (
        "{evaluated: [{term, ...reindex}], signals: [{term, ...}], watchlist: [term], "
        "candidates_source: 'llm'|'watchlist_only', fuzzy: str (curate-input), "
        "escalate: {reason}|None}"
    )

    # ── configuratie ──
    def _cfg(self, context):
        s = getattr(context, "settings", {}) or {}
        anchors = [a.strip() for a in
                   (s.get("trend_reindex_anchors") or ", ".join(_DEFAULT_ANCHORS)).split(",")
                   if a.strip()]
        return {
            "anchors": anchors[:_MAX_ANCHORS - 1] or _DEFAULT_ANCHORS,  # +1 kandidaat ≤ 5-term-cap
            "geo": (s.get("trend_reindex_geo") or "").strip(),          # leeg = worldwide
            "timeframe": (s.get("trend_reindex_timeframe") or _TIMEFRAME_DEFAULT).strip(),
            "hl": s.get("trend_reindex_hl", "en-US"),
            "base_year": _int_or_none(s.get("trend_reindex_base_year")),
            "max_candidates": int(s.get("trend_reindex_max_candidates", 5)),
            "factor": float(s.get("trend_reindex_factor", 2.0)),
            "min_months": int(s.get("trend_reindex_min_months", 3)),
            "emergence_floor": float(s.get("trend_reindex_emergence_floor", 1.0)),
            "keep": int(s.get("trend_reindex_keep", 10)),
        }

    def _make_fetch(self, cfg):
        """Bouw een pytrends-fetch [term + ankers] → df. Fail-closed: pytrends ontbreekt/init
        faalt → None (de skill escaleert dan)."""
        try:
            from pytrends.request import TrendReq
        except ImportError:
            return None
        try:
            pytrends = TrendReq(hl=cfg["hl"], tz=0, timeout=(10, 25),
                                requests_args={"headers": {"User-Agent": _USER_AGENT}})
        except Exception as exc:
            log.error("trend_reindex: pytrends-init faalde: %s", exc)
            return None

        def _fetch(terms):
            pytrends.build_payload(terms[:5], cat=0, timeframe=cfg["timeframe"],
                                   geo=cfg["geo"], gprop="")
            return pytrends.interest_over_time()
        return _fetch

    def run(self, payload: dict, context) -> dict:
        cfg = self._cfg(context)
        data_dir = getattr(context, "data_dir", "data")
        payload = payload or {}
        keep = int(payload.get("keep", cfg["keep"]))

        watchlist = _load_watchlist(data_dir)
        watch_terms = [w["term"] for w in watchlist]

        # 1) kandidaten: override, anders LLM-generatie (fail-closed → watchlist-only)
        escalate = None
        if payload.get("terms"):
            candidates = [t.strip().lower() for t in payload["terms"] if t.strip()][:cfg["max_candidates"]]
            source = "override"
        else:
            mission = getattr(getattr(context, "mission", None), "purpose", "") or ""
            candidates = generate_candidates(cfg["anchors"], watch_terms, mission=mission,
                                             cap=cfg["max_candidates"])
            source = "llm" if candidates else "watchlist_only"
            if not candidates and not watch_terms:
                escalate = {"reason": "LLM leverde geen kandidaten en de watchlist is leeg — "
                                      "geen termen om te her-indexeren."}

        # 2) fetch-poort. Geen pytrends → hard fail-closed + zichtbaar escaleren.
        fetch = payload.get("_fetch") or self._make_fetch(cfg)
        if fetch is None:
            return {"evaluated": [], "signals": [], "watchlist": watch_terms,
                    "candidates_source": source, "fuzzy": "",
                    "escalate": {"reason": "pytrends niet beschikbaar/initialiseerbaar — "
                                           "trend_reindex kan geen data ophalen (fail-closed)."}}

        # 3) her-indexeer elke term (kandidaten + bestaande watchlist), elk MET de ankerset
        to_eval, seen = [], set()
        for t in candidates + watch_terms:
            if t and t not in seen:
                seen.add(t)
                to_eval.append(t)

        evaluated, signals = [], []
        real = payload.get("_fetch") is None
        for term in to_eval:
            try:
                df = fetch([term] + cfg["anchors"])
            except Exception as exc:
                log.error("trend_reindex: fetch '%s' faalde: %s — term overgeslagen.", term, exc)
                continue
            series = series_from_df(df, term)
            m = reindex_metrics(series, base_year=cfg["base_year"], factor=cfg["factor"],
                                min_months=cfg["min_months"],
                                emergence_floor=cfg["emergence_floor"])
            if m is None:
                if real:
                    time.sleep(1.0)
                continue
            row = {"term": term, **m}
            evaluated.append(row)
            _append_signal(data_dir, {"term": term, "geo": cfg["geo"],
                                      "timeframe": cfg["timeframe"], **m})
            if m["is_signal"]:
                signals.append(row)
            if real:
                time.sleep(1.0)                         # beleefd tussen requests

        # 4) watchlist bijwerken: houd de best presterende (op multiplier / emergentie)
        merged = _merge_watchlist(watchlist, evaluated, keep)
        _save_watchlist(data_dir, merged)

        # 5) curate-hand-off voor de signalen (Librarian schrijft, niet Sid)
        fuzzy = "\n".join(signal_to_fuzzy(r["term"], r) for r in signals)

        return {
            "evaluated": evaluated,
            "signals": signals,
            "watchlist": [w["term"] for w in merged],
            "candidates_source": source,
            "fuzzy": fuzzy,
            "escalate": escalate,
        }


def _int_or_none(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _rank_key(row: dict) -> float:
    """Rangschik op sterkte: een aanhoudende trend op z'n multiplier; emergentie hoog (van nul);
    een blip laag."""
    st = row.get("signal_type")
    if st == "trend":
        return float(row.get("index_latest") or 0.0)
    if st == "emergence":
        return float(row.get("recent_sustained") or 0.0)
    return 0.0


def _merge_watchlist(existing: list[dict], evaluated: list[dict], keep: int) -> list[dict]:
    """Voeg de nieuw geëvalueerde termen samen met de bestaande watchlist en houd de `keep`
    best presterende. Append-only van geest: een term die eraf valt wordt niet 'verwijderd
    met verlies' — z'n observaties staan in trend_signals.jsonl. De watchlist is enkel het
    actieve venster."""
    by_term = {w["term"]: w for w in existing}
    for row in evaluated:
        by_term[row["term"]] = {"term": row["term"], "signal_type": row["signal_type"],
                                "index_latest": row.get("index_latest"),
                                "recent_sustained": row.get("recent_sustained")}
    ranked = sorted(by_term.values(), key=_rank_key, reverse=True)
    return ranked[:keep]
