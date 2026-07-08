"""Meetcatalogus-contract (machine-leesbaar) + healthcheck.

De mensen-leesbare kaart staat in docs/meetcatalogus.md; dit is het afdwingbare contract:
welke metric-families verwacht zijn, per bron, met cadans en actief/inactief-status.

De healthcheck signaleert twee dingen en zwijgt bij bewust-inactieve bronnen:
1. ONGECATALOGISEERDE reeks: een reeks in de store die geen enkele catalogus-family matcht
   → "er is iets nieuws verschenen dat we niet kennen".
2. NIET-VULLEND: een gecatalogiseerde ACTIEVE family die te lang geen nieuwe SCHRIJF kreeg
   (N pulsen: N=2 daily, N=1 weekly). Bewust op schrijf-recency (ts), niet op het datum-label —
   dat verschilt per bron (OpenAlex R−30, Trends complete-week, GSC lag) en zou anders vals alarm geven.
Een family zonder data → GEEN alarm (known-future / nog niet gevuld). Inactieve bron → NOOIT alarm.
"""
from __future__ import annotations
import collections
import fnmatch
import time

# (pattern, bron, cadans, status). cadans ∈ daily|weekly|monthly|irregular. status ∈ active|inactive.
# pattern ondersteunt fnmatch-wildcards (*): dimensie-families als '<base>::*', dynamische als '<prefix>_*_day'.
CATALOG = [
    ("plausible_visitors_day",            "plausible",          "daily",     "active"),
    ("plausible_pageviews_day",           "plausible",          "daily",     "active"),
    ("plausible_visit_duration_day",      "plausible",          "daily",     "active"),
    ("plausible_bounce_rate_day",         "plausible",          "daily",     "active"),
    ("plausible_visitors_day::*",         "plausible",          "daily",     "active"),   # per land
    ("plausible_pageviews_day::*",        "plausible",          "daily",     "active"),
    ("plausible_visit_duration_day::*",   "plausible",          "daily",     "active"),
    ("plausible_bounce_rate_day::*",      "plausible",          "daily",     "active"),
    ("plausible_page_visitors_day::*",    "plausible",          "daily",     "active"),   # scope 2 page_path
    ("visitors_via_*",                    "plausible",          "daily",     "active"),
    ("gsc_impressions_day",               "gsc",                "daily",     "active"),
    ("gsc_clicks_day",                    "gsc",                "daily",     "active"),
    ("gsc_ctr_day",                       "gsc",                "daily",     "active"),
    ("gsc_position_day",                  "gsc",                "daily",     "active"),
    ("gsc_*_day::*",                      "gsc",                "daily",     "active"),   # per keyword
    ("openalex_works_90d::*",             "openalex",           "weekly",    "active"),
    ("trends_ratio_*_day",                "trends",             "weekly",    "active"),   # incl. scope 3 slow÷fast
    ("keywordseverywhere_*_day",          "keywordseverywhere", "weekly",    "active"),
    ("alphavantage_*_day",                "alphavantage",       "daily",     "active"),
    ("werk_duur_day",                     "werkoverleg",        "irregular", "active"),   # per overleg → geen N-check
    ("werk_tevredenheid_day",             "werkoverleg",        "irregular", "active"),
    ("gdelt_*_day",                       "gdelt_tone",         "daily",     "inactive"),
    ("shopify_*_day",                     "shopify",            "daily",     "inactive"),
    ("semanticscholar_*_day",             "semanticscholar",    "monthly",   "inactive"),
]

# Schrijf-recency-marge (seconden) waarbinnen een actieve family een nieuwe schrijf hoort te hebben.
# N pulsen + puls-timing-marge. 'irregular' heeft geen vaste cadans → geen recency-check.
_TS_THRESH = {"daily": 2 * 86400 + 43200, "weekly": 8 * 86400, "monthly": 35 * 86400}


def _in_catalog(metric: str, bron: str) -> bool:
    return any(bron == pb and fnmatch.fnmatch(metric, pat) for (pat, pb, _c, _s) in CATALOG)


def healthcheck(obs, now_ts: float | None = None, catalog=CATALOG) -> list[dict]:
    """Geef de lijst signalen (leeg = gezond). `obs` = ObservationStore (of een lijst rijen); `now_ts`
    injecteerbaar voor tests."""
    now_ts = time.time() if now_ts is None else now_ts
    rows = obs._read_all() if hasattr(obs, "_read_all") else list(obs)
    max_ts: dict[tuple[str, str], float] = collections.defaultdict(float)
    for r in rows:
        k = (r.get("bron"), r.get("metric"))
        try:
            ts = float(r.get("ts") or 0)
        except (TypeError, ValueError):
            ts = 0.0
        if ts > max_ts[k]:
            max_ts[k] = ts
    signals: list[dict] = []
    # 1) ongecatalogiseerde reeks
    for (bron, metric) in max_ts:
        if not _in_catalog(metric, bron):
            signals.append({"type": "ongecatalogiseerd", "bron": bron, "metric": metric})
    # 2) niet-vullend: actieve family met data waarvan de laatste SCHRIJF te oud is
    for (pat, pb, cadans, status) in catalog:
        if status != "active" or cadans not in _TS_THRESH:
            continue                                       # inactief of irregular → geen recency-alarm
        tss = [ts for (bron, metric), ts in max_ts.items() if bron == pb and fnmatch.fnmatch(metric, pat)]
        if not tss:
            continue                                       # geen data → geen vals alarm (known-future)
        age = now_ts - max(tss)
        if age > _TS_THRESH[cadans]:
            signals.append({"type": "niet-vullend", "bron": pb, "family": pat,
                            "laatste_schrijf_dagen": round(age / 86400, 1)})
    return signals
