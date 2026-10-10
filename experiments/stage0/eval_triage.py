#!/usr/bin/env python3
"""Stage 0 — meet of een klein lokaal model de menselijke keep/dismiss-beslissing reproduceert.

Ruis is de dure fout, dus het model draait als conservatief wegveeg-filter vóór de Gemini-ladder.
De vraag die telt is NIET accuracy, maar: **veegt het model bij hetzelfde weegvolume schoner weg
dan het lexicale filter dat we al hebben?**

Drie ontwerpkeuzes volgen daaruit:

1. **Het model scoort, het script beslist.** De prompt is neutraal ("rate 0-100 how worth keeping");
   het conservatisme zit puur in waar de dismiss-drempel ligt. Eén threshold-sweep vervangt het
   herschrijven van de prompt per run.
2. **De baseline dismisst ook.** `mission.strategie_relevantie` (de lexicale STRATEGIE_THEMAS-
   heuristiek) krijgt dezelfde dismiss-actie, en wordt vergeleken bij GELIJKE offload — niet bij
   gelijke drempel. Alleen dan meet je of het model iets toevoegt.
3. **Elke precision krijgt een Wilson-95%-CI.** Bij ~90 dismisses (20% van 450) is een punt-
   schatting van 90% niet scherp genoeg om als poort te dienen. Lees een run als richting.

Sinds 10 oktober 2026 schrijft elke run twee bestanden naast dit script (gitignored — ze bevatten
interne radartekst):

    rapport_<datum>.md   alle modellen naast elkaar, per feed, scorespreiding, holdout apart
    misses_<datum>.md    elke keep onder de drempel bij 20% wegvegen, plus 30 weggeveegde dismisses

En vier regels die je niet stilletjes moet omdraaien:

* **Holdout.** 100 rijen (vaste seed) blijven buiten het afstellen. De drempel wordt op de REST
  gekozen en daarna ongewijzigd op de holdout toegepast. De ids staan in `holdout_ids.txt`; die
  wordt bij een volgende run hergebruikt, zodat de holdout niet stilletjes verschuift.
* **EXCLUDE_FEEDS** (standaard `Projecten`, een interne feed) haalt rijen uit de HELE meting —
  ook uit `WITH_GEMINI=1`. Er gaat niets van een interne feed naar een externe API.
* **Met én zonder rationale.** Elke run draait ook zonder de regel "WHY IT WAS SURFACED", om te
  zien of het model alleen het eerdere oordeel napraat.
* **Modellen uit `ollama list`**, alleen die in het geheugen passen (zie `modellen()`).

Gebruik (op Stefans Mac, met de Ollama op localhost:11434):
    python3 experiments/stage0/eval_triage.py
    OLLAMA_MODELS=qwen2.5:3b python3 experiments/stage0/eval_triage.py      # één model
    NO_LLM=1 python3 experiments/stage0/eval_triage.py                       # alleen lexicaal
    WITH_GEMINI=1 python3 experiments/stage0/eval_triage.py                  # + Gemini-plafond

Scores worden gecachet in `scores_cache.jsonl` (gitignored, per model + exacte prompt): een tweede
run doet alleen wat nog niet gedaan is.

Eval-set: `evalset.jsonl` als die bestaat, anders `data/live_radar.json` — goedgekeurd=keep,
afgewezen=dismiss.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.request

_HIER = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HIER))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

# Reference, don't copy: de missietekst leeft op één gezaghebbende plek (mission.py) en wordt
# hier geïmporteerd, niet overgetypt. Verandert de missie, dan verandert deze prompt mee.
from nooch_village.mission import ANCHOR_PURPOSE, strategie_relevantie  # noqa: E402
# Het Wilson-interval leeft op één plek (nooch_village/stats.py) — dezelfde poort-statistiek die
# de Founder Flow gebruikt om een taak te promoveren. Reference, don't copy.
from nooch_village.stats import Z95 as Z, wilson  # noqa: E402,F401

_env = os.environ.get
EVALSET = _env("EVALSET", os.path.join(_HIER, "evalset.jsonl"))
RADAR = _env("RADAR", os.path.join(_REPO, "data", "live_radar.json"))
OLLAMA_BASE = _env("OLLAMA_BASE", "http://localhost:11434")
OFFLOAD_POINTS = [float(x) for x in _env("OFFLOADS", "0.10,0.20,0.30").split(",")]
#: Het werkpunt: hier wordt de drempel gekozen, de holdout gemeten en de misses-lijst gemaakt.
WERKPUNT = float(_env("WERKPUNT", "0.20"))
SEED = int(_env("SEED", "20261010"))
HOLDOUT_N = int(_env("HOLDOUT_N", "100"))
HOLDOUT_FILE = _env("HOLDOUT_FILE", os.path.join(_HIER, "holdout_ids.txt"))
CACHE_FILE = _env("CACHE_FILE", os.path.join(_HIER, "scores_cache.jsonl"))
EXCLUDE_FEEDS = [f.strip() for f in _env("EXCLUDE_FEEDS", "Projecten").split(",") if f.strip()]
STEEKPROEF_N = 30
#: Een model mag hoogstens zo groot zijn — en past daarnaast in het geheugen min deze marge.
MAX_MODEL_BYTES = 16 * 1024 ** 3
RAM_MARGE_BYTES = 4 * 1024 ** 3

# ── De prompt is bewust NEUTRAAL. Geen "when in doubt, keep" — dat duwde het model naar keep
# terwijl we offload eisen, en dat is tegen elkaar in optimaliseren. Het model rangschikt; de
# drempel maakt het conservatief. ──────────────────────────────────────────────────────────────
_TASK = (
    "A radar surfaces external signals (trends, competitors, materials, news) for this brand. "
    "A human then KEEPS the ones worth acting on and DISMISSES the rest. Many signals look "
    "topically related but are still not worth keeping.\n\n"
    "Rate how worth-keeping this signal is on a scale of 0 to 100, where 0 means certainly not "
    "worth keeping and 100 means certainly worth keeping. Use the full range; do not cluster "
    "your answers around one value.\n\n"
)


def prompt_for(row: dict, met_rationale: bool = True) -> str:
    """De prompt. `met_rationale=False` laat de regel weg waarom de radar het signaal opwierp — de
    toets of het model zelf oordeelt of alleen dat eerdere oordeel napraat."""
    waarom = f"WHY IT WAS SURFACED: {row['rationale']}\n" if met_rationale else ""
    return (
        f"{ANCHOR_PURPOSE}\n\n"
        f"{_TASK}"
        f"FEED: {row['feed']}\n"
        f"SIGNAL: {row['content']}\n"
        f"{waarom}\n"
        'Answer ONLY with JSON: {"score": <integer 0-100>}'
    )


# ── Eval-set laden ────────────────────────────────────────────────────────────────────────────
def row_id(row: dict) -> str:
    """Een stabiel id uit feed + content. De eval-set draagt geen radar-id (alleen feed, content,
    rationale, label), en hetzelfde signaal moet run na run hetzelfde id houden."""
    return hashlib.sha1(f"{row['feed']}\x00{row['content']}".encode("utf-8")).hexdigest()[:12]


def load_rows() -> list[dict]:
    """evalset.jsonl als die er is, anders afgeleid uit de live radar (goedgekeurd/afgewezen)."""
    if os.path.exists(EVALSET):
        rows = [json.loads(line) for line in open(EVALSET, encoding="utf-8") if line.strip()]
        print(f"eval-set: {EVALSET} ({len(rows)} items)")
    else:
        raw = json.load(open(RADAR, encoding="utf-8"))
        items = raw.get("items", raw)
        items = list(items.values()) if isinstance(items, dict) else items
        rows = [
            {"feed": it.get("feed", ""), "content": it.get("content", ""),
             "rationale": it.get("rationale", ""),
             "label": 1 if it.get("status") == "goedgekeurd" else 0}
            for it in items
            if it.get("status") in ("goedgekeurd", "afgewezen")
        ]
        print(f"eval-set: {EVALSET} bestaat niet → afgeleid uit {RADAR} ({len(rows)} items)")
    for r in rows:
        r["id"] = row_id(r)
    return rows


def splits(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """(afstellen, holdout). De holdout-ids komen uit `HOLDOUT_FILE` als die bestaat; anders wordt
    met een vaste seed getrokken en weggeschreven. Een id uit het bestand dat niet (meer) in de set
    zit, valt gewoon weg — de holdout wordt nooit stilletjes aangevuld."""
    if os.path.exists(HOLDOUT_FILE):
        ids = {l.strip() for l in open(HOLDOUT_FILE, encoding="utf-8") if l.strip()}
    else:
        alle = sorted(r["id"] for r in rows)
        ids = set(random.Random(SEED).sample(alle, min(HOLDOUT_N, len(alle))))
        with open(HOLDOUT_FILE, "w", encoding="utf-8") as f:
            f.write("".join(f"{i}\n" for i in sorted(ids)))
    return [r for r in rows if r["id"] not in ids], [r for r in rows if r["id"] in ids]


# ── Modellen ──────────────────────────────────────────────────────────────────────────────────
def ram_bytes() -> int:
    try:
        return int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True,
                                  text=True, check=True).stdout.strip())
    except Exception:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")


def modellen() -> tuple[list[tuple[str, int]], int, list[tuple[str, int]]]:
    """(passend, grens, te_groot) uit `ollama list` (de /api/tags van dezelfde Ollama).

    De grens is de kleinste van 16 GB en het RAM min 4 GB marge (het systeem en de cockpit draaien
    ernaast). `OLLAMA_MODELS=a,b` beperkt de keuze tot die modellen."""
    with urllib.request.urlopen(f"{OLLAMA_BASE}/api/tags", timeout=10) as r:
        tags = json.loads(r.read())["models"]
    grens = min(MAX_MODEL_BYTES, ram_bytes() - RAM_MARGE_BYTES)
    alle = sorted((m["name"], int(m.get("size", 0))) for m in tags)
    keuze = [m.strip() for m in _env("OLLAMA_MODELS", "").split(",") if m.strip()]
    if keuze:
        alle = [m for m in alle if m[0] in keuze]
    return [m for m in alle if m[1] < grens], grens, [m for m in alle if m[1] >= grens]


# ── Model-aanroep + cache ─────────────────────────────────────────────────────────────────────
def ask_ollama(prompt: str, model: str) -> str:
    body = json.dumps({
        "model": model, "prompt": prompt, "stream": False,
        "format": "json", "options": {"temperature": 0},
    }).encode()
    req = urllib.request.Request(f"{OLLAMA_BASE}/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["response"]


def parse_score(raw) -> float | None:
    """Haal een 0-100 keep-waardigheid uit het antwoord. None = onbruikbaar (telt als skipped)."""
    if raw is None:
        return None
    s = re.sub(r"```(?:json)?", "", str(raw))
    m = re.search(r'"(?:score|keep_worthiness|rating)"\s*:\s*"?(-?\d+(?:\.\d+)?)"?', s, re.I)
    if not m:
        m = re.search(r"(?<![\w.])(\d{1,3}(?:\.\d+)?)(?![\w.])", s)
    if not m:
        return None
    try:
        val = float(m.group(1))
    except ValueError:
        return None
    return min(100.0, max(0.0, val))


def gemini_score(prompt: str) -> float | None:
    from nooch_village.llm import reason
    return parse_score(reason(prompt, max_tokens=40, json_mode=True, call_site="stage0_eval"))


class Cache:
    """Scores per (model, exacte prompt). Een gewijzigde prompt is een nieuwe sleutel, dus een oude
    score kan nooit voor een nieuwe vraag doorgaan. Een None (fout) wordt niet bewaard."""

    def __init__(self, pad: str):
        self.pad, self.d = pad, {}
        if os.path.exists(pad):
            for line in open(pad, encoding="utf-8"):
                try:
                    e = json.loads(line)
                    self.d[e["k"]] = e["s"]
                except (ValueError, KeyError):
                    continue

    @staticmethod
    def sleutel(model: str, prompt: str) -> str:
        return f"{model}|{hashlib.sha1(prompt.encode('utf-8')).hexdigest()[:16]}"

    def get(self, model: str, prompt: str):
        return self.d.get(self.sleutel(model, prompt))

    def put(self, model: str, prompt: str, score) -> None:
        if score is None:
            return
        k = self.sleutel(model, prompt)
        self.d[k] = score
        with open(self.pad, "a", encoding="utf-8") as f:
            f.write(json.dumps({"k": k, "s": score}) + "\n")


def score_run(rows: list[dict], model: str, met_rationale: bool, cache: Cache,
              vraag=None) -> tuple[list[float | None], float, int]:
    """(scores, seconden, aantal echt gevraagd). `vraag` = de aanroep (Ollama of Gemini)."""
    vraag = vraag or (lambda p: parse_score(ask_ollama(p, model)))
    scores, t0, gevraagd = [], time.time(), 0
    for i, r in enumerate(rows, 1):
        p = prompt_for(r, met_rationale)
        s = cache.get(model, p)
        if s is None:
            try:
                s = vraag(p)
            except Exception as e:
                print(f"  [{model} {i}] fout: {e}")
                s = None
            gevraagd += 1
            cache.put(model, p, s)
        scores.append(s)
        if i % 50 == 0:
            print(f"  {model} {'met' if met_rationale else 'zonder'} rationale: {i}/{len(rows)}"
                  f"  ({time.time() - t0:.0f}s)")
    return scores, time.time() - t0, gevraagd


# ── Statistiek ────────────────────────────────────────────────────────────────────────────────
def dismiss_precision_at_k(scores: list[float], labels: list[int], k: int) -> tuple[float, int]:
    """Veeg de k laagst-scorende items weg; geef (verwacht aantal terecht weggeveegd, k).

    Belangrijk bij een grove scorer: de lexicale score is een integer 0-7, dus er zijn dikke
    gelijkspel-groepen. Welke items je binnen zo'n groep pakt is arbitrair, dus we rekenen de
    VERWACHTING over de groep uit (k_rest * dismisses / groepsgrootte) in plaats van een
    willekeurige ordening te laten meebeslissen. Voor een fijne scorer (0-100) is dit gelijk
    aan gewoon de onderste k nemen.
    """
    k = max(0, min(k, len(scores)))
    if k == 0:
        return (0.0, 0)
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    expected_tn, remaining, idx = 0.0, k, 0
    while remaining > 0 and idx < len(order):
        j = idx
        while j < len(order) and scores[order[j]] == scores[order[idx]]:
            j += 1
        group = order[idx:j]
        true_dismiss = sum(1 for i in group if labels[i] == 0)
        take = min(remaining, len(group))
        expected_tn += take * true_dismiss / len(group)
        remaining -= take
        idx = j
    return (expected_tn, k)


def at_offloads(scores: list[float], labels: list[int]) -> dict[float, dict]:
    """{offload: {k, prec, lo, hi, approx}} — dismiss-precision met Wilson-CI per offload-punt."""
    n, out = len(scores), {}
    for target in OFFLOAD_POINTS:
        k = int(round(target * n))
        tn, k = dismiss_precision_at_k(scores, labels, k)
        if k == 0:
            continue
        # Wilson eist hele successen; bij een gelijkspel-groep is `tn` een verwachting en dus
        # fractioneel. Dan ronden we voor het CI af en markeren dat met ~ — niet wegmoffelen.
        lo, hi = wilson(round(tn), k)
        out[target] = {"k": k, "prec": tn / k, "lo": lo, "hi": hi,
                       "approx": abs(tn - round(tn)) > 1e-9}
    return out


def drempel_voor(scores: list[float], target: float) -> float:
    """De score-drempel t (wegvegen = score < t) waarvan het aandeel weggeveegd het dichtst bij
    `target` ligt. Op de AFSTEL-set gekozen; de holdout krijgt hem ongewijzigd."""
    n = len(scores)
    kandidaten = sorted(set(scores)) + [max(scores) + 1]
    return min(kandidaten, key=lambda t: (abs(sum(1 for s in scores if s < t) - target * n), t))


def bij_drempel(scores: list[float], labels: list[int], t: float) -> dict:
    """Wat een vaste drempel doet: weggeveegd, precision + CI, en het aandeel keeps dat verloren gaat."""
    k = sum(1 for s in scores if s < t)
    tn = sum(1 for s, y in zip(scores, labels) if s < t and y == 0)
    keeps = sum(labels)
    lo, hi = wilson(tn, k) if k else (0.0, 0.0)
    return {"n": len(scores), "k": k, "offload": k / len(scores) if scores else 0.0,
            "prec": tn / k if k else None, "lo": lo, "hi": hi,
            "verloren": (k - tn) / keeps if keeps else 0.0, "verloren_n": k - tn}


def sweep_rijen(scores: list[float], labels: list[int]) -> list[tuple]:
    """Volledige drempel-curve: (drempel, offload, dismiss-precision, verloren kansen)."""
    n, keeps, uit, gezien = len(scores), sum(labels), [], set()
    for t in sorted(set(scores)):
        k = sum(1 for s in scores if s < t)
        if k == 0 or k in gezien:
            continue
        gezien.add(k)
        tn = sum(1 for s, y in zip(scores, labels) if s < t and y == 0)
        uit.append((t, k / n, tn / k, ((k - tn) / keeps) if keeps else 0.0))
    return uit


def kwantielen(xs: list[float]) -> str:
    s = sorted(xs)
    q = lambda p: s[min(len(s) - 1, int(p * len(s)))]
    return f"{q(0.1):.0f} / {q(0.5):.0f} / {q(0.9):.0f}"


def spearman(a: list[float], b: list[float]) -> float | None:
    """Rangcorrelatie met gemiddelde rangen bij gelijkspel. None bij te weinig of constante data."""
    if len(a) < 3:
        return None

    def rang(xs):
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        r, i = [0.0] * len(xs), 0
        while i < len(order):
            j = i
            while j < len(order) and xs[order[j]] == xs[order[i]]:
                j += 1
            for k in range(i, j):
                r[order[k]] = (i + j - 1) / 2
            i = j
        return r

    ra, rb = rang(a), rang(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra) ** 0.5
    vb = sum((y - mb) ** 2 for y in rb) ** 0.5
    return cov / (va * vb) if va and vb else None


# ── Markdown ──────────────────────────────────────────────────────────────────────────────────
def _pct(x) -> str:
    return "—" if x is None else f"{x * 100:.1f}%"


def _ci(d: dict) -> str:
    return f"{'~' if d.get('approx') else ''}[{d['lo'] * 100:.0f}–{d['hi'] * 100:.0f}]"


def _tabel(kop: list[str], rijen: list[list]) -> list[str]:
    return (["| " + " | ".join(kop) + " |", "|" + "|".join("---" for _ in kop) + "|"]
            + ["| " + " | ".join(str(c) for c in r) + " |" for r in rijen])


def _cel(x: str, n: int = 220) -> str:
    """Tekst in een tabelcel: één regel, geen pipes, ingekort."""
    t = " ".join(str(x or "").split()).replace("|", "/")
    return t if len(t) <= n else t[:n - 1] + "…"


class Run:
    """Eén scoring: een model (of de lexicale baseline) met of zonder rationale."""

    def __init__(self, naam: str, rows: list[dict], scores: list, seconden: float = 0.0,
                 gevraagd: int = 0, model: str = "", met_rationale: bool = True):
        self.naam, self.model, self.met_rationale = naam, model, met_rationale
        self.seconden, self.gevraagd = seconden, gevraagd
        self.alle = list(zip(rows, scores))
        self.skipped = sum(1 for _r, s in self.alle if s is None)

    def deel(self, ids: set | None) -> tuple[list[dict], list[float], list[int]]:
        paren = [(r, s) for r, s in self.alle if s is not None and (ids is None or r["id"] in ids)]
        return [r for r, _ in paren], [s for _, s in paren], [r["label"] for r, _ in paren]


def rapport(runs: list[Run], lex: Run, afstel: list[dict], holdout: list[dict], meta: dict) -> str:
    a_ids, h_ids = {r["id"] for r in afstel}, {r["id"] for r in holdout}
    L: list[str] = [f"# Stage 0 — triage-evaluatie, {meta['datum']}", ""]
    L += [f"- Eval-set: {meta['n_totaal']} rijen; uitgesloten feeds: "
          f"{', '.join(f'{f} ({n})' for f, n in meta['uitgesloten'].items()) or 'geen'} "
          f"→ {len(afstel) + len(holdout)} in de meting.",
          f"- Afstellen: {len(afstel)} rijen · holdout: {len(holdout)} rijen (seed {SEED}, ids in "
          f"`{os.path.basename(HOLDOUT_FILE)}`). De drempel wordt op de afstel-set gekozen bij "
          f"{WERKPUNT * 100:.0f}% wegvegen en ongewijzigd op de holdout toegepast.",
          f"- Modellen uit `ollama list` onder de grens van {meta['grens'] / 1024 ** 3:.1f} GB "
          f"(min(16 GB, RAM {meta['ram'] / 1024 ** 3:.0f} GB − 4 GB)): "
          f"{', '.join(f'{m} ({b / 1024 ** 3:.1f} GB)' for m, b in meta['modellen']) or 'geen'}"
          + (f"; te groot: {', '.join(m for m, _b in meta['te_groot'])}" if meta['te_groot'] else "")
          + ".",
          f"- Totale duur: {meta['duur'] / 60:.1f} min ({meta['gevraagd']} model-aanroepen, de rest "
          f"uit de cache).", ""]
    if meta.get("oude_logs"):
        L += ["## Eerdere runs", "", meta["oude_logs"], ""]

    # 1. Naast elkaar, op de afstel-set.
    L += ["## Alle runs naast elkaar (afstel-set)", "",
          "Dismiss-precision bij gelijke offload, met Wilson-95%-CI. Blind wegvegen haalt per "
          "definitie het aandeel echte dismisses: dat is de vloer.", ""]
    _r, _s, ys = lex.deel(a_ids)
    vloer = 1 - (sum(ys) / len(ys)) if ys else 0
    lp = at_offloads(*lex.deel(a_ids)[1:])
    kop = ["run", "N", "unieke scores", "p10/p50/p90"] + [f"@{p * 100:.0f}%" for p in OFFLOAD_POINTS] \
        + [f"Δ lexicaal @{WERKPUNT * 100:.0f}%", "duur"]
    rijen = []
    for run in [lex] + runs:
        _r, ss, ys = run.deel(a_ids)
        if not ss:
            rijen.append([run.naam, 0, "", "", *["—"] * len(OFFLOAD_POINTS), "", ""])
            continue
        mp = at_offloads(ss, ys)
        delta = ("" if run is lex or WERKPUNT not in mp or WERKPUNT not in lp
                 else f"{(mp[WERKPUNT]['prec'] - lp[WERKPUNT]['prec']) * 100:+.1f}pp")
        rijen.append([run.naam, len(ss) if not run.skipped else f"{len(ss)} ({run.skipped} skipped)",
                      len(set(ss)), kwantielen(ss),
                      *[f"{_pct(mp[p]['prec'])} {_ci(mp[p])}" if p in mp else "—" for p in OFFLOAD_POINTS],
                      delta, f"{run.seconden / 60:.1f} min" if run.seconden else ""])
    L += _tabel(kop, rijen) + ["", f"Vloer (blind wegvegen): {_pct(vloer)}.", ""]

    # 2. Holdout.
    L += ["## Holdout (apart, drempel van de afstel-set)", "",
          f"Per run de drempel die op de afstel-set {WERKPUNT * 100:.0f}% wegveegt, ongewijzigd op de "
          f"{len(holdout)} holdout-rijen.", ""]
    rijen = []
    for run in [lex] + runs:
        _r, sa, _ya = run.deel(a_ids)
        _r, sh, yh = run.deel(h_ids)
        if not sa or not sh:
            continue
        t = drempel_voor(sa, WERKPUNT)
        a, h = bij_drempel(sa, _ya, t), bij_drempel(sh, yh, t)
        rijen.append([run.naam, f"{t:g}", f"{_pct(a['offload'])} / {_pct(a['prec'])}",
                      f"{_pct(h['offload'])} ({h['k']})",
                      f"{_pct(h['prec'])} [{h['lo'] * 100:.0f}–{h['hi'] * 100:.0f}]",
                      f"{h['verloren_n']} ({_pct(h['verloren'])})"])
    L += _tabel(["run", "drempel (<)", "afstel: offload / precision", "holdout: weggeveegd",
                 "holdout: precision [CI]", "holdout: verloren keeps"], rijen) + [""]

    # 3. Met vs zonder rationale.
    paren = [(m, z) for m in runs for z in runs
             if m.model and m.model == z.model and m.met_rationale and not z.met_rationale]
    if paren:
        L += ["## Met en zonder rationale", "",
              "Praat het model alleen het eerdere oordeel na? Als de precision zonder de rationale-"
              "regel sterk zakt en de scores nauwelijks samenhangen, leunde het model op die regel.", ""]
        rijen = []
        for m, z in paren:
            _r, sm, ym = m.deel(a_ids)
            _r, sz, yz = z.deel(a_ids)
            pm, pz = at_offloads(sm, ym).get(WERKPUNT), at_offloads(sz, yz).get(WERKPUNT)
            gedeeld = {r["id"]: s for r, s in zip(*m.deel(a_ids)[:2])}
            zonder = {r["id"]: s for r, s in zip(*z.deel(a_ids)[:2])}
            ids = [i for i in gedeeld if i in zonder]
            rho = spearman([gedeeld[i] for i in ids], [zonder[i] for i in ids])
            rijen.append([m.model, _pct(pm["prec"]) if pm else "—", _pct(pz["prec"]) if pz else "—",
                          (f"{(pz['prec'] - pm['prec']) * 100:+.1f}pp" if pm and pz else "—"),
                          "—" if rho is None else f"{rho:.2f}"])
        L += _tabel(["model", f"met @{WERKPUNT * 100:.0f}%", f"zonder @{WERKPUNT * 100:.0f}%",
                     "verschil", "Spearman ρ (met vs zonder)"], rijen) + [""]

    # 4. Per feed.
    feeds = sorted({r["feed"] for r in afstel})
    L += ["## Per feed (afstel-set, bij de drempel van het werkpunt)", "",
          "Per feed: hoeveel er wordt weggeveegd, hoeveel daarvan terecht, en hoeveel keeps verloren "
          "gaan. Een feed waar de precision ver onder het gemiddelde ligt, is waar het model het "
          "oordeel van de mens het minst begrijpt.", ""]
    kop = ["feed", "N", "keeps"] + [run.naam for run in [lex] + runs]
    rijen = []
    for f in feeds:
        fr = [r for r in afstel if r["feed"] == f]
        rij = [f, len(fr), sum(r["label"] for r in fr)]
        fids = {r["id"] for r in fr}
        for run in [lex] + runs:
            _r, sa, _ya = run.deel(a_ids)
            if not sa:
                rij.append("—")
                continue
            t = drempel_voor(sa, WERKPUNT)
            _r, sf, yf = run.deel(fids)
            d = bij_drempel(sf, yf, t) if sf else None
            rij.append("—" if not d or not d["k"] else
                       f"{d['k']} weg · {_pct(d['prec'])} · {d['verloren_n']} keeps kwijt")
        rijen.append(rij)
    L += _tabel(kop, rijen) + [""]

    # 5. Scorespreiding.
    L += ["## Scorespreiding per run (afstel-set)", "",
          "Aantal keeps / dismisses per scoreband. Een model dat alles op één waarde zet, heeft "
          "voor een drempel niets te kiezen.", ""]
    banden = [(0, 10), (10, 20), (20, 30), (30, 40), (40, 50), (50, 60), (60, 70), (70, 80),
              (80, 90), (90, 101)]
    rijen = []
    for run in runs:
        _r, ss, ys = run.deel(a_ids)
        rij = [run.naam]
        for lo, hi in banden:
            k = sum(1 for s, y in zip(ss, ys) if lo <= s < hi and y == 1)
            d = sum(1 for s, y in zip(ss, ys) if lo <= s < hi and y == 0)
            rij.append(f"{k}/{d}" if k or d else "")
        rijen.append(rij)
    L += _tabel(["run"] + [f"{lo}–{min(hi, 100)}" for lo, hi in banden], rijen) + [""]

    # 6. De volledige tabellen per run (wat het script altijd al printte).
    L += ["## Per run: offload-tabel, verdict en drempel-sweep (afstel-set)", ""]
    for run in runs:
        _r, ss, ys = run.deel(a_ids)
        if not ss:
            continue
        mp = at_offloads(ss, ys)
        L += [f"### {run.naam}", ""]
        L += _tabel(["offload", "weggeveegd", "dismiss-precision", "95%-CI", "lexicaal", "verdict"],
                    [[f"{p * 100:.0f}%", mp[p]["k"], _pct(mp[p]["prec"]), _ci(mp[p]),
                      _pct(lp[p]["prec"]) if p in lp else "—",
                      ("—" if p not in lp else
                       ("model" if mp[p]["prec"] > lp[p]["prec"] else
                        "gelijk" if mp[p]["prec"] == lp[p]["prec"] else "lexicaal")
                       + f" ({(mp[p]['prec'] - lp[p]['prec']) * 100:+.1f}pp), vloer "
                       f"{(mp[p]['prec'] - vloer) * 100:+.1f}pp")]
                     for p in OFFLOAD_POINTS if p in mp])
        L += ["", "<details><summary>drempel-sweep</summary>", ""]
        L += _tabel(["drempel (<)", "offload", "dismiss-precision", "verloren kansen"],
                    [[f"{t:g}", _pct(o), _pct(p), _pct(v)] for t, o, p, v in sweep_rijen(ss, ys)])
        L += ["", "</details>", ""]
    L += ["Lees dit als RICHTING, niet als poort: bij deze N is een CI van ±8pp normaal. Promoveren "
          "pas als de ondergrens van het CI boven de lexicale bovengrens ligt.", ""]
    return "\n".join(L)


def misses(runs: list[Run], afstel: list[dict], holdout: list[dict], datum: str) -> str:
    """Per run: elke keep onder de werkpunt-drempel (afstel + holdout), en een steekproef van 30
    terecht of onterecht weggeveegde dismisses — om te lezen WAT het model wegveegt."""
    a_ids, h_ids = {r["id"] for r in afstel}, {r["id"] for r in holdout}
    L = [f"# Stage 0 — misses, {datum}", "",
         f"Drempel per run gekozen op de afstel-set bij {WERKPUNT * 100:.0f}% wegvegen. "
         "Interne radartekst: niet committen, niet delen buiten NoochVille.", ""]
    for run in runs:
        _r, sa, _ya = run.deel(a_ids)
        if not sa:
            continue
        t = drempel_voor(sa, WERKPUNT)
        rows, ss, _ys = run.deel(None)
        weg = [(r, s) for r, s in zip(rows, ss) if s < t]
        gemist = sorted([(r, s) for r, s in weg if r["label"] == 1], key=lambda x: x[1])
        dismissed = [(r, s) for r, s in weg if r["label"] == 0]
        steekproef = random.Random(SEED).sample(dismissed, min(STEEKPROEF_N, len(dismissed)))
        split = lambda r: "holdout" if r["id"] in h_ids else "afstel"
        L += [f"## {run.naam} — drempel < {t:g}", "",
              f"### Keeps die weggeveegd zouden worden ({len(gemist)})", ""]
        L += _tabel(["score", "feed", "set", "content", "rationale"],
                    [[f"{s:g}", r["feed"], split(r), _cel(r["content"]), _cel(r["rationale"], 160)]
                     for r, s in gemist]) if gemist else ["Geen."]
        L += ["", f"### Steekproef van weggeveegde dismisses ({len(steekproef)} van {len(dismissed)})", ""]
        L += _tabel(["score", "feed", "set", "content", "rationale"],
                    [[f"{s:g}", r["feed"], split(r), _cel(r["content"]), _cel(r["rationale"], 160)]
                     for r, s in sorted(steekproef, key=lambda x: x[1])]) if steekproef else ["Geen."]
        L += [""]
    return "\n".join(L)


# ── Main ──────────────────────────────────────────────────────────────────────────────────────
def main() -> None:
    t_start = time.time()
    datum = datetime.date.today().isoformat()
    alle = load_rows()
    uitgesloten = {f: sum(1 for r in alle if r["feed"] == f) for f in EXCLUDE_FEEDS}
    # EXCLUDE_FEEDS VÓÓR ALLES: een interne feed komt in geen enkele run, en dus ook nooit bij een
    # externe API (WITH_GEMINI). Daarom hier gefilterd en niet pas bij de Gemini-aanroep.
    rows = [r for r in alle if r["feed"] not in EXCLUDE_FEEDS]
    limit = int(_env("LIMIT", "0")) or len(rows)
    rows = rows[:limit]
    afstel, holdout = splits(rows)
    print(f"meting: {len(rows)} rijen (uitgesloten: {uitgesloten}) → afstel {len(afstel)}, "
          f"holdout {len(holdout)}")

    lex = Run("lexicaal (strategie_relevantie)", rows,
              [float(strategie_relevantie(f"{r['content']} {r['rationale']}")[0]) for r in rows])
    runs: list[Run] = []
    cache = Cache(CACHE_FILE)
    passend, grens, te_groot = ([], 0, []) if _env("NO_LLM") else modellen()
    gevraagd = 0
    for model, _b in passend:
        for met in (True, False):
            print(f"\n→ {model} {'met' if met else 'zonder'} rationale")
            scores, sec, n = score_run(rows, model, met, cache)
            gevraagd += n
            runs.append(Run(f"{model}{'' if met else ' · zonder rationale'}", rows, scores, sec, n,
                            model=model, met_rationale=met))
    if _env("WITH_GEMINI"):
        print("\n→ Gemini (ladder-plafond), met rationale")
        traag = float(_env("GEMINI_SLEEP", "1.0"))

        def via_gemini(p):
            time.sleep(traag)
            return gemini_score(p)
        scores, sec, n = score_run(rows, "gemini", True, cache, vraag=via_gemini)
        gevraagd += n
        runs.append(Run("Gemini (ladder-plafond)", rows, scores, sec, n))

    meta = {"datum": datum, "n_totaal": len(alle), "uitgesloten": uitgesloten, "grens": grens,
            "ram": ram_bytes(), "modellen": passend, "te_groot": te_groot,
            "duur": time.time() - t_start, "gevraagd": gevraagd,
            "oude_logs": _env("OUDE_LOGS", "")}
    pad_r = os.path.join(_HIER, f"rapport_{datum}.md")
    pad_m = os.path.join(_HIER, f"misses_{datum}.md")
    with open(pad_r, "w", encoding="utf-8") as f:
        f.write(rapport(runs, lex, afstel, holdout, meta))
    with open(pad_m, "w", encoding="utf-8") as f:
        f.write(misses(runs, afstel, holdout, datum))
    print(f"\nklaar in {meta['duur'] / 60:.1f} min → {pad_r}\n{' ' * 18}{pad_m}")


if __name__ == "__main__":
    main()
