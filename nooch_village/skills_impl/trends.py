"""TrendsSkill — haalt Google Trends-data op per geo/locale.

Locale-model:
  Elke geo wordt gemapped op een taal (bijv. NL → nl, GB/US → en).
  Woorden per geo komen bij voorkeur uit het Lexicon voor die taal.
  Valt terug op keywords.txt + Library-goedkeuringen.

Output: `rows` (locale-bewust) + `keywords` (backward compat, eerste geo).
  Elke row: {term, locale, geo, interest_latest, direction, top_related, rising_related, tekst}
        of: {term, locale, geo, no_data: True, reason: str}      (bevraagd, geen data)
        of: {term, locale, geo, error: str}                       (de bron faalde: 429, netwerk)
  "geen data" is expliciet onderscheiden van een echte nul of interest=0, én van een fout.

Fail-closed per geo×term, en op topniveau (scope 55): álle rijen fout → `ok: False, error` (een
429-dag leest als ⚠️, niet als ✅); álle rijen leeg → `no_data: True`. De ladder in
evidence_ledger.SKILL_LADDERS valt bij een fout door naar `serpapi_trends` (zelfde payload).
"""
from __future__ import annotations
import os, json, time, random, logging, datetime
from nooch_village.skills import DataSourceSkill

log = logging.getLogger(__name__)

# Een realistische browser-User-Agent vermindert 429's: de pytrends-default-UA
# wordt sneller geblokkeerd door Google.
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# ── Stemming-paren (ratio A/B, geen gedeeld anker) ────────────────────────────────────────────────
# Google Trends' 0-100 is relatief aan de zwaarste term per request; naast een dominant anker comprimeert
# elke niche naar 0-1 (gemeten 2026-07-08, iteratie 1: docs/trends_sentiment_termset_meting_2026-07-08.md).
# Herontwerp: PAREN van tegengestelde stemming met vergelijkbare grootte. Per paar één request [A, B];
# ratio per datapunt = waarde_A / waarde_B uit dezelfde response — geen gedeeld anker, geen schaling.
#
# ORIËNTATIE (meetconstante — paren omdraaien breekt de reeks): A = zuinigheid/behoud-kant, B =
# toegeeflijkheid/nieuw-kant. Ratio A/B stijgt = versobering-stemming stijgt (socionomics). De paren komen
# uit config-sleutel `trends_pairs` — FAIL-CLOSED, GEEN default, GEEN partial parse: ontbrekend/leeg/één
# misvormd paar → luide error, bron levert niets.
_TIMEFRAME_DEFAULT = "today 5-y"        # weekly resolutie; de ratio gebruikt het recente (laatste) punt


def _parse_pairs(raw: str):
    """Parse `trends_pairs` ('A:B, A:B') → [(A, B), ...]. FAIL-CLOSED: None bij leeg, of bij één misvormd
    paar (geen ':' of lege A/B) — liever luid stuk dan stil half. Termen mogen spaties bevatten; whitespace
    rond termen en scheiders wordt getrimd."""
    raw = (raw or "").strip()
    if not raw:
        return None
    pairs = []
    for part in raw.split(","):
        part = part.strip()
        if part.count(":") != 1:                # geen of meerdere ':' → misvormd
            return None
        a, b = (x.strip() for x in part.split(":", 1))
        if not a or not b:
            return None
        pairs.append((a, b))
    return pairs or None


def _pair_field(a: str, b: str) -> str:
    """Veldsleutel per paar → metric `trends_ratio_<A>_<B>_day` (bijv. trends_ratio_second_hand_brand_new_day)."""
    return f"ratio_{_sanitize_field(a)}_{_sanitize_field(b)}"


def _last_complete_week(today: datetime.date) -> datetime.date:
    """De laatste COMPLETE Google-Trends-week vóór `today`. Trends' weekly-reeks markeert de lopende week
    als isPartial (onvolledig); die is dus altijd de voorlaatste. Trends-weken starten op ZONDAG. Deze
    datum labelt de observatie = de week die de waarde werkelijk beschrijft (deterministisch uit today,
    zodat de due-check en de write dezelfde sleutel gebruiken → idempotent, geen dag-refetch)."""
    days_since_sunday = (today.weekday() + 1) % 7          # ma=0..zo=6 → zondag=0
    this_week_sunday = today - datetime.timedelta(days=days_since_sunday)
    return this_week_sunday - datetime.timedelta(days=7)   # vorige (laatste complete) week


def _drop_partial(df):
    """Verwijder de lopende, onvolledige week (isPartial=True) vóór het laatste punt gekozen wordt.
    FAIL-CLOSED: ontbreekt de isPartial-kolom onverwacht → None (behandel als 'geen betrouwbare complete
    week'; nooit terugvallen op een partiële rij)."""
    if "isPartial" not in df:
        return None
    return df[~df["isPartial"].astype(bool)]


def _sanitize_field(term: str) -> str:
    """Term → veilige observatie-veldsleutel (trends_<veld>_day)."""
    return "".join(c if c.isalnum() else "_" for c in term.strip().lower()).strip("_") or "term"


def rotate_window(items: list, cursor: int, size: int) -> tuple[list, int]:
    """Round-robin venster van maximaal `size` items vanaf `cursor`.

    Geeft (venster, volgende_cursor). Zo bevraagt elke puls maar een paar termen en
    rolt over meerdere pulsen door de hele set — dat begrenst de request-burst die
    Google Trends 429't, ongeacht hoe groot de woordenlijst wordt.

    Leeg → ([], 0). size <= 0 of size >= aantal → alle items (cursor terug naar 0).
    """
    n = len(items)
    if n == 0:
        return [], 0
    if size <= 0 or size >= n:
        return list(items), 0
    start = cursor % n
    window = [items[(start + i) % n] for i in range(size)]
    return window, (start + size) % n


def payload_terms(payload: dict) -> list[str]:
    """De gevraagde termen uit een Trends-payload: `keywords` (lijst of komma-string) óf `term`
    (één string). Eén lezer voor google_trends én serpapi_trends, zodat de ladder dezelfde payload
    aan beide treden kan geven. Leeg → [] (de aanroeper kiest dan zijn eigen zaad)."""
    payload = payload or {}
    raw = payload.get("keywords")
    if isinstance(raw, str):
        raw = [t for t in raw.replace(";", ",").split(",")]
    terms = [str(t).strip() for t in (raw or []) if str(t).strip()]
    term = str(payload.get("term") or "").strip()
    if not terms and term:
        terms = [term]
    return list(dict.fromkeys(terms))


def row_tekst(row: dict) -> str:
    """Eén leesbare zin per term ("interest 62 (stijgend); top: barefoot shoes women, …; rising:
    …") — de strekking voor note en verslag. Zonder dit veld toonde het verslag alleen "• term"."""
    delen = [f"interest {row.get('interest_latest')} ({row.get('direction', '?')})"]
    top = [r.get("query") for r in (row.get("top_related") or []) if isinstance(r, dict) and r.get("query")]
    if top:
        delen.append("top: " + ", ".join(top[:5]))
    rising = [f"{r.get('query')}{' (breakout)' if r.get('breakout') else ''}"
              for r in (row.get("rising_related") or []) if isinstance(r, dict) and r.get("query")]
    if rising:
        delen.append("rising: " + ", ".join(rising[:5]))
    return "; ".join(delen)


def finish_rows(rows: list, legacy: dict, geos: list, first_geo: str, *, timeframe: str = "",
                source: str = "") -> dict:
    """De topniveau-uitkomst uit de rijen (scope 55), gedeeld door google_trends en serpapi_trends:
    álle rijen fout → `ok: False, error` (de bron faalde, item blijft open); álle rijen leeg →
    `no_data: True` (bevraagd, niets); anders de rijen met een `text` erboven. Een mix van data en
    fouten is gelukt, mét de fouten in de `text`."""
    from nooch_village.sleutelmasker import masker
    out = {"rows": rows, "keywords": legacy, "geos": geos, "geo": first_geo}
    if source:
        out["source"] = source
    fout = [r for r in rows if r.get("error")]
    leeg = [r for r in rows if r.get("no_data") and not r.get("error")]
    goed = [r for r in rows if not r.get("error") and not r.get("no_data")]
    if rows and len(fout) == len(rows):
        redenen = sorted({masker(r["error"])[:120] for r in fout})
        out["ok"] = False
        out["error"] = (f"all {len(rows)} lookup(s) failed: " + " | ".join(redenen[:3]))
        return out
    if not goed:
        out["no_data"] = True
        out["reason"] = (f"no interest data for {', '.join(dict.fromkeys(r.get('term', '') for r in rows))}"
                         f" (geo {', '.join(g or 'worldwide' for g in geos)}"
                         + (f", {timeframe}" if timeframe else "") + ")") if rows else "no terms to look up"
        return out
    kop = "; ".join(f"{r['term']} {r.get('interest_latest')} ({r.get('direction')})" for r in goed[:5])
    out["text"] = (f"{len(goed)} of {len(rows)} term(s) with Google Trends data"
                   + (f" ({timeframe})" if timeframe else "") + f": {kop}"
                   + (f"; {len(leeg)} without data" if leeg else "")
                   + (f"; {len(fout)} failed" if fout else ""))
    return out


# Geo-code → taal (uitbreidbaar)
_GEO_LOCALE: dict[str, str] = {
    "NL": "nl",
    "BE": "nl",
    "GB": "en",
    "US": "en",
    "AU": "en",
    "CA": "en",
    "IE": "en",
    "": "en",      # lege string = worldwide discovery → EN (Engelse discovery-koers)
}


def _geo_to_locale(geo: str) -> str:
    return _GEO_LOCALE.get(geo.upper(), "en")


def _normalize_rising_value(raw):
    """rising-value is een int (stijgingspercentage) of de string 'Breakout'.
    Breakout = >5000% of vanuit nul; we behouden het signaal als hoge sentinel
    en markeren het apart, zodat het sterkste discovery-signaal niet wegvalt."""
    if isinstance(raw, str) and raw.strip().lower() == "breakout":
        return 10000, True
    try:
        return int(raw), False
    except (TypeError, ValueError):
        return 0, False


def _keywords_for_locale(locale: str, context) -> list[str]:
    """Woorden voor een locale: Lexicon-taalvak heeft prioriteit, dan keywords.txt + Library.
    Bevestigde concurrenten (context.competitors) komen er als extra zaad bij, zodat de
    Trends-run hun gerelateerde zoektermen ophaalt en die via de Librarian-pijp lopen."""
    lexicon = getattr(context, "lexicon", None)
    base: list[str] = []
    if lexicon:
        base = list(lexicon.words_for_lang(locale, status_filter="approved"))

    if not base:
        # Fallback: keywords.txt + Library (taal-onbewust)
        path = os.path.join(os.path.dirname(context.data_dir), "config", "keywords.txt")
        kws: list[str] = []
        if os.path.exists(path):
            kws = [l.strip() for l in open(path) if l.strip() and not l.startswith("#")]
        lib = getattr(context, "library", None)
        if lib:
            kws.extend(w for w, e in lib.all().items()
                       if e.get("status") == "approved" and w not in kws)
        base = kws or ["duurzame sneakers", "vegan schoenen", "plastic free shoes"]

    comp = getattr(context, "competitors", None)
    if comp is not None:
        for c in comp.confirmed():
            if c not in base:
                base.append(c)
    return base


def _read_keywords(context) -> list[str]:
    """Backward compat: geeft keywords voor de standaard geo terug."""
    return _keywords_for_locale(
        _geo_to_locale(context.settings.get("trends_geo", "NL")), context)


class TrendsSkill(DataSourceSkill):
    name = "google_trends"
    SOURCE = "trends"
    # Flux-bron: relatieve interesse is een niveau op een moment (geen cumulatieve stand) → de tegel
    # toont de waarde/lijn zelf. Weekly: Trends-data is niet dagvers genoeg voor daily.
    kind = "flux"
    DEFAULT_FREQUENCY = "weekly"
    cost = "rate_limited"
    description = (
        "Google Trends interest over time per geo/locale, plus related queries. THE SOURCE FOR "
        "'is this a trend or a hype': it reaches back years, where `keywords_everywhere` stops at "
        "twelve months. A month says nothing and twelve months only shows the season — ask for "
        "24 or 36 months before calling anything a trend. Set `timeframe` (Google's own syntax: "
        "'today 12-m', 'today 5-y', 'all'); default is 'today 12-m', which is the SHORTEST "
        "defensible window. Looks up the terms you pass (`keywords` or `term`). Fail-closed per "
        "geo×term; falls back to SerpApi when Google blocks."
    )
    input_schema = ("keywords: list[str] (the terms to look up; `term`: str is accepted as alias for one "
                    "term) · geos: list[str] (optional, country codes like 'NL', 'US'; '' = worldwide; "
                    "default settings.trends_geo) · timeframe: str (optional, Google syntax, default "
                    "'today 12-m') · hl: str (optional, interface language, default 'nl-NL')")
    # Of-of: de planlaag geeft een term-skill `{term}` (zoektermen.OPEN_WEB), de demo's geven
    # `keywords`. Tot scope 55 negeerde run() `term` en draaide het roterende Lexicon-venster —
    # het item onderzocht dan iets anders dan de planner vroeg, als 'gelukt'.
    required_payload = (("keywords", "term"),)
    output_schema = ("rows: list[{term, locale, geo, interest_latest, direction, top_related, "
                     "rising_related, tekst}], keywords: {term: …} (first geo), text: str "
                     "| no_data: True, reason | ok: False, error")

    def available_metrics(self, context=None) -> list[str]:
        """DYNAMISCHE velden: één ratio-veld per stemming-paar uit `trends_pairs`. Zonder context, of bij een
        ongeldige/lege config → leeg (de paren staan in de config, niet vast in de klasse)."""
        pairs = _parse_pairs((getattr(context, "settings", {}) or {}).get("trends_pairs", "")) if context else None
        return [_pair_field(a, b) for a, b in pairs] if pairs else []

    def is_configured(self, context) -> bool:
        """Keyless (pytrends). 'Geconfigureerd' = de pytrends-dependency is importeerbaar. Een pytrends
        die wél importeert maar bij de CALL breekt (Google wijzigt z'n endpoint) valt fail-closed naar
        None per term → verschijnt als 'dood', niet als crash of 'niet geconfigureerd'."""
        try:
            import pytrends.request  # noqa: F401
            return True
        except Exception:
            return False

    def expected_datum(self, today):
        """Datumlabel + due-sleutel = de laatste COMPLETE Trends-week (niet de pulsdatum, niet de lopende
        partiële week). Zie _last_complete_week."""
        return _last_complete_week(today).isoformat()

    def daily_values(self, context, datum: str, *, _fetch=None) -> dict:
        """Stemming-ratio per paar uit `trends_pairs`: per paar één request [A, B]; ratio = waarde_A /
        waarde_B van de laatste COMPLETE week (float, ONGESCHAALD, niet naar int afronden). Oriëntatie A =
        zuinigheid/behoud, B = toegeeflijkheid/nieuw (meetconstante; paren omdraaien breekt de reeks).
        Veld/metric = trends_ratio_<A>_<B>_day.

        COMPLETE WEEK: de lopende week is in Trends isPartial=True (onvolledig). Die wordt weggefilterd
        (_drop_partial) vóór het laatste punt gekozen wordt; de ratio komt van de laatste complete week.
        Het datumlabel van de observatie is die complete week (via expected_datum), niet de pulsdatum —
        essentieel voor latere lead/lag-analyse.

        Fail-closed:
          - `trends_pairs` ontbreekt/leeg/één misvormd paar → ERROR-log, bron levert niets (geen default,
            geen partial parse).
          - geen enkele complete (niet-partiële) week / isPartial-kolom afwezig → gat + ERROR (nooit
            terugvallen op een partiële rij).
          - NUL-GUARD op de noemer: B == 0 of afwezig op de laatste complete week → dat punt NIET schrijven
            + ERROR (scope 0 mat 100% niet-nul voor alle B; een 0 daar is een verdachte response).
          - A == 0 bij geldige B → ratio 0 wegschrijven (echte observatie).
          - mislukte/lege request → gat (None) + ERROR (geen interpolatie).
        `_fetch(payload, timeframe, geo) -> df` injecteerbaar (geen netwerk in tests)."""
        settings = getattr(context, "settings", {}) or {}
        pairs = _parse_pairs(settings.get("trends_pairs", ""))
        if pairs is None:
            log.error("Trends stemming-paren: config 'trends_pairs' ontbreekt, is leeg of bevat een misvormd "
                      "paar (verwacht 'A:B, A:B') — bron levert niets (fail-closed, geen partial parse).")
            return {}
        out = {_pair_field(a, b): None for a, b in pairs}
        geo = (settings.get("trends_geo") or "").strip()          # leeg = worldwide (zoals de scope-0-meting)
        timeframe = (settings.get("trends_timeframe") or _TIMEFRAME_DEFAULT).strip()
        hl = settings.get("trends_hl", "en-US")
        real = _fetch is None
        if real:
            try:
                from pytrends.request import TrendReq
            except ImportError:
                return out                                        # dependency ontbreekt → alles None
            try:
                pytrends = TrendReq(hl=hl, tz=0, timeout=(10, 25),
                                    requests_args={"headers": {"User-Agent": _USER_AGENT}})
            except Exception as exc:
                log.error("Trends init faalde: %s — bron levert niets.", exc)
                return out

            def _fetch(payload, tf, g):
                pytrends.build_payload(payload, cat=0, timeframe=tf, geo=g, gprop="")
                return pytrends.interest_over_time()
        for a, b in pairs:
            field = _pair_field(a, b)
            try:
                df = _fetch([a, b], timeframe, geo)
            except Exception as exc:
                log.error("Trends paar '%s÷%s' request faalde: %s — gat.", a, b, exc)
                continue
            if df is None or getattr(df, "empty", True) or a not in df or b not in df:
                log.error("Trends paar '%s÷%s': lege/incomplete respons — gat.", a, b)
                continue
            complete = _drop_partial(df)                          # lopende partiële week weg → laatste COMPLETE week
            if complete is None or getattr(complete, "empty", True):
                log.error("Trends paar '%s÷%s': geen complete (niet-partiële) week in de respons — gat "
                          "(nooit terugvallen op een partiële rij).", a, b)
                continue
            b_recent = complete[b].tolist()[-1]
            if not b_recent:                                      # noemer 0/afwezig → verdacht (scope 0: 100% niet-nul)
                log.error("Trends paar '%s÷%s': noemer B=%r op de laatste complete week — punt geskipt "
                          "(verdachte respons).", a, b, b_recent)
                continue
            out[field] = round(complete[a].tolist()[-1] / b_recent, 4)  # laatste COMPLETE week; float, ongeschaald
            if real:
                time.sleep(1.0)                                   # beleefd tussen paar-requests
        return out

    def backfill_pairs(self, context, obs, pairs, *, _fetch=None):
        """Eenmalige 5-jaars backfill van de ratio-reeks per stemming-paar. Voor elk paar de VOLLEDIGE
        interest_over_time-reeks (today 5-y); de partiële laatste week weg (_drop_partial); per COMPLETE week
        ratio = A/B → `trends_ratio_<A>_<B>_day`, datum = de weekgrens (df-index, zondag), meta backfill:true.
        Noemer 0/afwezig → die week overgeslagen (geen deel-door-nul, geen interpolatie). Idempotent: een
        reeds live geschreven week (zelfde datum) blijft staan (record_daily dedupt). `_fetch` injecteerbaar."""
        settings = getattr(context, "settings", {}) or {}
        geo = (settings.get("trends_geo") or "").strip()
        timeframe = (settings.get("trends_timeframe") or _TIMEFRAME_DEFAULT).strip()
        hl = settings.get("trends_hl", "en-US")
        real = _fetch is None
        if real:
            try:
                from pytrends.request import TrendReq
            except ImportError:
                return []
            try:
                pytrends = TrendReq(hl=hl, tz=0, timeout=(10, 25),
                                    requests_args={"headers": {"User-Agent": _USER_AGENT}})
            except Exception as exc:
                log.error("Trends init faalde (backfill): %s", exc)
                return []

            def _fetch(payload, tf, g):
                pytrends.build_payload(payload, cat=0, timeframe=tf, geo=g, gprop="")
                return pytrends.interest_over_time()
        written = []
        for a, b in pairs:
            metric = f"trends_{_pair_field(a, b)}_day"
            try:
                df = _fetch([a, b], timeframe, geo)
            except Exception as exc:
                log.error("Trends backfill paar '%s÷%s' faalde: %s", a, b, exc)
                continue
            if df is None or getattr(df, "empty", True) or a not in df or b not in df:
                log.error("Trends backfill '%s÷%s': lege/incomplete respons", a, b)
                continue
            complete = _drop_partial(df)
            if complete is None or getattr(complete, "empty", True):
                continue
            for idx, row in complete.iterrows():
                bv = row[b]
                if not bv:
                    continue                                      # noemer 0/afwezig → week overslaan
                datum = idx.date().isoformat() if hasattr(idx, "date") else str(idx)
                if obs.record_daily("trends", metric, round(row[a] / bv, 4), bron="trends", datum=datum,
                                    meta={"backfill": True}):
                    written.append(("trends", _pair_field(a, b), datum))
            if real:
                time.sleep(1.0)
        return written

    def _select_window(self, keywords: list[str], context) -> list[str]:
        """Beperk tot een roterend venster (default 3) en bewaar de cursor, zodat de
        request-burst begrensd blijft en de set over meerdere pulsen toch rondkomt."""
        size = int(context.settings.get("trends_keywords_per_pulse", "3"))
        path = os.path.join(context.data_dir, "trends_cursor.json")
        try:
            cursor = int(json.load(open(path)).get("cursor", 0))
        except Exception:
            cursor = 0
        window, nxt = rotate_window(keywords, cursor, size)
        try:
            with open(path, "w") as f:
                json.dump({"cursor": nxt}, f)
        except Exception:
            pass
        return window

    def _fetch(self, pytrends, keyword, geo, timeframe="today 12-m", max_retries=4, base_delay=8):
        """Exponentiele backoff bij 429."""
        retries = 0
        while retries < max_retries:
            try:
                pytrends.build_payload([keyword], cat=0,
                                       timeframe=timeframe, geo=geo, gprop="")
                return pytrends.interest_over_time(), pytrends.related_queries()
            except Exception as e:
                if "429" in str(e):
                    delay = min(base_delay * (2 ** retries) + random.uniform(1, 3), 90)
                    time.sleep(delay)
                    retries += 1
                else:
                    raise
        raise RuntimeError(f"max retries voor '{keyword}' (geo={geo})")

    def run(self, payload: dict, context) -> dict:
        payload = payload or {}
        try:
            from pytrends.request import TrendReq
        except ImportError:
            return {"ok": False, "error": "pytrends niet geinstalleerd (pip install pytrends)",
                    "keywords": {}, "rows": []}

        # Welke geo's worden bevraagd?
        geos_raw = payload.get("geos") or [context.settings.get("trends_geo", "NL")]
        if isinstance(geos_raw, str):
            geos_raw = [geos_raw]
        geos: list[str] = list(dict.fromkeys(geos_raw))  # dedup, volgorde behouden
        timeframe = payload.get("timeframe", "today 12-m")
        hl        = payload.get("hl", "nl-NL")
        gevraagd  = payload_terms(payload)               # keywords óf term; leeg = het roterende venster

        pytrends = TrendReq(hl=hl, tz=60, timeout=(10, 25),
                            requests_args={"headers": {"User-Agent": _USER_AGENT}})

        rows: list[dict]  = []
        legacy: dict      = {}           # eerste geo → keywords-dict (backward compat)
        first_geo         = geos[0] if geos else ""

        for geo in geos:
            locale   = _geo_to_locale(geo)
            if gevraagd:
                keywords = gevraagd                     # expliciet meegegeven: respecteer volledig
            else:
                keywords = self._select_window(_keywords_for_locale(locale, context), context)

            for kw in keywords:
                try:
                    interest_df, related = self._fetch(pytrends, kw, geo, timeframe=timeframe)

                    if interest_df is not None and not interest_df.empty and kw in interest_df:
                        series  = interest_df[kw].tolist()
                        latest  = int(series[-1])
                        prev    = int(series[-2]) if len(series) > 1 else latest
                        direction = (
                            "stijgend" if latest > prev else
                            "dalend"   if latest < prev else
                            "vlak"
                        )
                        top_related: list = []
                        if kw in related and related[kw].get("top") is not None:
                            top_related = (related[kw]["top"][["query", "value"]]
                                           .head(5).to_dict("records"))
                        rising_related: list = []
                        if kw in related and related[kw].get("rising") is not None:
                            for rec in related[kw]["rising"][["query", "value"]].head(5).to_dict("records"):
                                val, is_breakout = _normalize_rising_value(rec.get("value"))
                                rising_related.append({
                                    "query": rec.get("query"),
                                    "value": val,
                                    "breakout": is_breakout,
                                })
                        row = {
                            "term":            kw,
                            "locale":          locale,
                            "geo":             geo,
                            "interest_latest": latest,
                            "direction":       direction,
                            "top_related":     top_related,
                            "rising_related":  rising_related,
                        }
                        row["tekst"] = row_tekst(row)
                        if geo == first_geo:
                            legacy[kw] = {
                                "interest_latest": latest,
                                "direction":       direction,
                                "top_related":     top_related,
                                "rising_related":  rising_related,
                            }
                    else:
                        row = {
                            "term":    kw,
                            "locale":  locale,
                            "geo":     geo,
                            "no_data": True,
                            "reason":  "geen data voor deze geo",
                        }
                        if geo == first_geo:
                            legacy[kw] = {"no_data": True}
                    rows.append(row)

                except Exception as e:
                    # Een fout (429, netwerk) is GEEN 'geen data': de rij zegt `error`, zodat de
                    # topniveau-uitkomst hieronder een geblokkeerde dag als fout kan melden.
                    row = {
                        "term":    kw,
                        "locale":  locale,
                        "geo":     geo,
                        "error":   str(e),
                    }
                    rows.append(row)
                    if geo == first_geo:
                        legacy[kw] = {"error": str(e)}

                time.sleep(1)   # vriendelijk voor Google

        return finish_rows(rows, legacy, geos, first_geo, timeframe=timeframe)
