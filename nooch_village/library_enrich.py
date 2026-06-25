"""Verrijk goedgekeurde bibliotheekwoorden met meetbare kans-signalen.

Twee bronnen, fail-closed per bron:
- KeywordsEverywhere: zoekvolume + concurrentie → kans-score (opportunity_score).
- Google Search Console: onze huidige stand voor exact die term (positie, klikken, impressies).

Schrijft via Library.set_evidence (merge), dus status/datum/rationale blijven ongemoeid. Bedoeld
als mens-gedraaid onderhoudscommando (`python -m nooch_village.village enrich_volumes`), niet als
autonome puls — capaciteit/credits blijven mens-gated.
"""
from __future__ import annotations
import os
import time


def _gsc_index(context, log) -> tuple[dict, str | None]:
    """Eén GSC-call: alle rankende queries, geïndexeerd op kleine-letter term. (index, error)."""
    try:
        from nooch_village.skills_impl.gsc import GscPerformanceSkill
        res = GscPerformanceSkill().run({}, context)
    except Exception as e:                                   # pragma: no cover - infra
        return {}, str(e)
    if not isinstance(res, dict) or "error" in res:
        return {}, (res.get("error") if isinstance(res, dict) else str(res))
    return {(r.get("query") or "").strip().lower(): r for r in res.get("rows", [])}, None


def enrich_library(library, context, *, apply: bool = True, only_missing: bool = True,
                   gsc: bool = True, seeds_trends: bool = True,
                   sleep: float = 1.0, log=None) -> dict:
    """Verrijk alle approved-woorden. Retourneert {results, gsc_error}.

    only_missing=True slaat woorden over die al een volume hebben (idempotent, spaart credits).
    Doelwit-woorden krijgen volume/concurrentie/kans + GSC-stand; volg-woorden (seeds) krijgen
    daarnaast de meerjarige trend-toestand (5-jaars Google Trends → opkomend/stabiel/...).
    """
    from nooch_village.skills_impl.keywords_everywhere import (
        KeywordsEverywhereSkill, opportunity_score, trend_change_pct)
    from nooch_village.library import classify_function
    from nooch_village.trend_analysis import trend_state, recent_surge
    from nooch_village.seed_surge_store import SeedSurges
    surges = SeedSurges(os.path.join(
        (getattr(context, "data_dir", None) or "data"), "seed_surges.json"))
    country = (getattr(context, "settings", {}) or {}).get("ke_country", "").strip()

    gsc_by_query, gsc_error = ({}, None)
    if gsc:
        gsc_by_query, gsc_error = _gsc_index(context, log)

    trends_skill = None
    if seeds_trends:
        try:
            from nooch_village.skills_impl.serpapi_trends import SerpapiTrendsSkill
            trends_skill = SerpapiTrendsSkill()
        except Exception:
            trends_skill = None

    ke = KeywordsEverywhereSkill()
    results = []
    approved = [w for w, e in (library.all() or {}).items()
                if isinstance(e, dict) and e.get("status") == "approved"]
    for w in approved:
        entry = library.status(w) or {}
        ev = entry.get("evidence") or {}
        fn = entry.get("function") if entry.get("function") in ("volg", "doelwit") \
            else classify_function(w, ev)
        updates: dict = {}

        if not (only_missing and ev.get("volume") is not None):
            res = ke.run({"kw": [w], "country": country}, context)
            if isinstance(res, dict) and "error" not in res and res.get("keywords"):
                kw = res["keywords"][0]
                vol = int(kw.get("vol", 0) or 0)
                comp = float(kw.get("competition", 0) or 0)
                updates.update(volume=vol, competition=comp, ke_country=country)
                tp = trend_change_pct(kw.get("trend"))
                if tp is not None:
                    updates["trend_pct"] = tp               # 12-mnd trend voor volg-woorden
            time.sleep(sleep)                               # beleefd tegen de API

        if gsc and gsc_error is None:
            g = gsc_by_query.get(w.strip().lower())
            if g:
                updates.update(gsc_seen=True, gsc_position=g.get("position"),
                               gsc_clicks=g.get("clicks"), gsc_impressions=g.get("impressions"))
            else:
                updates["gsc_seen"] = False                 # bekend: ranken (nog) niet voor deze term

        # Kans = volume × resterende organische ruimte (uit onze GSC-positie), pas ná de GSC-stand.
        merged_now = {**ev, **updates}
        vol = merged_now.get("volume")
        if vol is not None:
            updates["opportunity"] = opportunity_score(
                vol, position=merged_now.get("gsc_position"), ranks=merged_now.get("gsc_seen"))

        # Volg-woorden (seeds): meerjarige trend-toestand uit 5-jaars Google Trends.
        if fn == "volg" and trends_skill is not None and \
                not (only_missing and ev.get("trend_series")):
            series = trends_skill.series(w, context, timeframe="today 5-y")
            st = trend_state(series)
            if st is not None:
                updates["trend_state"] = st
                updates["trend_series"] = series          # bewaar de curve voor de sparkline
                surge = recent_surge(series)
                updates["recent_surge"] = surge
                if surge:                                 # spanning: laat Harry het onderzoeken
                    surges.add(w, locale=(library.status(w) or {}).get("locale") or "")
            time.sleep(sleep)

        if updates and apply:
            library.set_evidence(w, updates)
        merged = {**ev, **updates}
        results.append({"word": w, "function": fn, **{k: merged.get(k) for k in (
            "volume", "competition", "opportunity", "trend_state",
            "gsc_seen", "gsc_position", "gsc_clicks", "gsc_impressions")}})
    return {"results": results, "gsc_error": gsc_error}
