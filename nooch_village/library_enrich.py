"""Verrijk goedgekeurde bibliotheekwoorden met meetbare kans-signalen.

Twee bronnen, fail-closed per bron:
- KeywordsEverywhere: zoekvolume + concurrentie → kans-score (opportunity_score).
- Google Search Console: onze huidige stand voor exact die term (positie, klikken, impressies).

Schrijft via Library.set_evidence (merge), dus status/datum/rationale blijven ongemoeid. Bedoeld
als mens-gedraaid onderhoudscommando (`python -m nooch_village.village enrich_volumes`), niet als
autonome puls — capaciteit/credits blijven mens-gated.
"""
from __future__ import annotations
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
                   gsc: bool = True, sleep: float = 1.0, log=None) -> dict:
    """Verrijk alle approved-woorden. Retourneert {results, gsc_error}.

    only_missing=True slaat woorden over die al een volume hebben (idempotent, spaart credits).
    """
    from nooch_village.skills_impl.keywords_everywhere import (
        KeywordsEverywhereSkill, opportunity_score)
    country = (getattr(context, "settings", {}) or {}).get("ke_country", "").strip()

    gsc_by_query, gsc_error = ({}, None)
    if gsc:
        gsc_by_query, gsc_error = _gsc_index(context, log)

    ke = KeywordsEverywhereSkill()
    results = []
    approved = [w for w, e in (library.all() or {}).items()
                if isinstance(e, dict) and e.get("status") == "approved"]
    for w in approved:
        ev = (library.status(w) or {}).get("evidence") or {}
        updates: dict = {}

        if not (only_missing and ev.get("volume") is not None):
            res = ke.run({"kw": [w], "country": country}, context)
            if isinstance(res, dict) and "error" not in res and res.get("keywords"):
                kw = res["keywords"][0]
                vol = int(kw.get("vol", 0) or 0)
                comp = float(kw.get("competition", 0) or 0)
                updates.update(volume=vol, competition=comp,
                               opportunity=opportunity_score(vol, comp), ke_country=country)
            time.sleep(sleep)                               # beleefd tegen de API

        if gsc and gsc_error is None:
            g = gsc_by_query.get(w.strip().lower())
            if g:
                updates.update(gsc_seen=True, gsc_position=g.get("position"),
                               gsc_clicks=g.get("clicks"), gsc_impressions=g.get("impressions"))
            else:
                updates["gsc_seen"] = False                 # bekend: ranken (nog) niet voor deze term

        if updates and apply:
            library.set_evidence(w, updates)
        merged = {**ev, **updates}
        results.append({"word": w, **{k: merged.get(k) for k in (
            "volume", "competition", "opportunity",
            "gsc_seen", "gsc_position", "gsc_clicks", "gsc_impressions")}})
    return {"results": results, "gsc_error": gsc_error}
