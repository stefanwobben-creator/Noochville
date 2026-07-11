"""community_listening — grounded ophaal-skill die gebruikerservaringen over een onderwerp
verzamelt als gestructureerde observaties.

Geen oordeel, geen sentiment, geen insights: zelfde patroon als news en de concurrentiemonitor.
De skill dispatcht per ACTIEF platform van de zoek-set naar een fetcher (registry:
`buzz_fetchers.FETCHERS`), ontdubbelt centraal op permalink en schrijft observatie-rijen weg.
Het dorp voeden (samenvatting, spanning) doet Billy Buzz (de ConcurrentScout-rol), niet deze skill.

v2-bronnen: YouTube-comments (key) + Bluesky-posts (keyless). Reddit blijft bestaan maar staat
inactief (datacenter-IP-blok; wacht op script-app OAuth). Fail-closed: elke stille early-return
krijgt een BUZZ_*-refuse-code — niets faalt zonder logregel.
"""
from __future__ import annotations

import logging
import os
import time

from nooch_village.skills import Skill
from nooch_village.util import refuse

log = logging.getLogger("village.skill.buzz")


def _refuse(code: str, reason: str, **ctx) -> dict:
    """Log de weigering (stabiele code) én geef een fail-dict terug, zodat élk early-return-pad
    zowel een logregel als een leesbare uitkomst heeft."""
    refuse(code, reason, **ctx)
    return {"ok": False, "refuse": code, "error": reason, **ctx}


class CommunityListeningSkill(Skill):
    name = "community_listening"
    cost = "rate_limited"          # publieke endpoints, beleefde 1 req/s + backoff
    side_effect_free = False       # schrijft observatie-rijen
    required_env = ()              # geen HARDE key: Bluesky is keyless (YouTube is optioneel)
    optional_env = ("YOUTUBE_API_KEY",)   # verbetert: zonder key slaat alleen YouTube over
    description = ("Verzamelt gebruikerservaringen (YouTube-comments + Bluesky-posts, Reddit inactief) "
                  "over een onderwerp als gestructureerde observaties. Grounded, geen oordeel/sentiment. "
                  "Fail-closed, per-platform 6u-cache, quota-guard op YouTube.")
    input_schema = ("query_set_id: str (verplicht — verwijst naar een set in buzz_query_sets.json). "
                    "optioneel: time_window: str (default '7d', alleen Reddit)")
    required_payload = ("query_set_id",)
    output_schema = ("ok: bool, count/new: int (nieuwe rijen totaal), counts: {platform: int|'inactief'}, "
                     "summary: str, query_set_id: str | refuse-dict met code BUZZ_*")

    # ── injectie-punten (met fallback op data_dir, zoals competitor_news) ─────────
    def _query_sets(self, context):
        qs = getattr(context, "buzz_query_sets", None)
        if qs is not None:
            return qs
        from nooch_village.buzz_query_sets import BuzzQuerySets
        return BuzzQuerySets(os.path.join(getattr(context, "data_dir", "."), "buzz_query_sets.json"))

    def _obs_store(self, context):
        st = getattr(context, "buzz_observations", None)
        if st is not None:
            return st
        from nooch_village.buzz_observations import BuzzObservationStore
        return BuzzObservationStore(
            os.path.join(getattr(context, "data_dir", "."), "buzz_observations.jsonl"))

    def _cache(self, context):
        from nooch_village.buzz_observations import BuzzCache
        return BuzzCache(os.path.join(getattr(context, "data_dir", "."), "buzz_cache.json"))

    # ── run ─────────────────────────────────────────────────────────────────────
    def run(self, payload: dict, context=None) -> dict:
        set_id = (payload.get("query_set_id") or "").strip()
        if not set_id:
            return _refuse("BUZZ_NO_SET", "geen query_set_id opgegeven")
        qset = self._query_sets(context).get(set_id)
        if qset is None:
            return _refuse("BUZZ_NO_SET", "zoek-set bestaat niet", query_set_id=set_id)
        if not qset.get("active"):
            return _refuse("BUZZ_SET_INACTIVE", "zoek-set staat op inactive", query_set_id=set_id)
        platforms = qset.get("platforms") or {}
        if not platforms:
            return _refuse("BUZZ_EMPTY_SET", "zoek-set heeft geen platforms", query_set_id=set_id)

        from nooch_village.skills_impl.buzz_fetchers import FETCHERS
        from nooch_village.buzz_query_sets import PLATFORM_ORDER

        store = self._obs_store(context)
        cache = self._cache(context)
        opts = {"now": time.time(), "time_window": payload.get("time_window") or "7d"}

        counts: dict = {}
        summary: list[str] = []
        total_new = 0
        first_refuse = None
        # Bekende platforms eerst (stabiele volgorde), daarna eventueel onbekende uit de set.
        ordered = [p for p in PLATFORM_ORDER if p in platforms] + \
                  [p for p in platforms if p not in PLATFORM_ORDER]
        for platform in ordered:
            cfg = platforms.get(platform) or {}
            if not cfg.get("active"):
                counts[platform] = "inactief"
                summary.append(f"{platform}: inactief")
                continue
            fetcher = FETCHERS.get(platform)
            if fetcher is None:
                counts[platform] = "onbekend"
                summary.append(f"{platform}: onbekende fetcher")
                refuse("BUZZ_UNKNOWN_PLATFORM", "geen fetcher voor platform", platform=platform)
                continue
            res = fetcher.fetch(set_id, cfg, context, cache, opts)
            new = 0
            for row in res.get("rows", []):
                if store.record_observation(row):
                    new += 1
            total_new += new
            counts[platform] = new
            label = f"{platform}: {new} nieuw"
            if res.get("short"):                    # YouTube: comments overgeslagen wegens te kort
                label += f", {res['short']} te kort"
            if res.get("refuse"):
                label += f" [{res['refuse']}]"
                first_refuse = first_refuse or res["refuse"]
            summary.append(label)

        summary_str = " / ".join(summary)
        log.info("🎧 community_listening '%s': %s", set_id, summary_str)
        out = {"ok": True, "count": total_new, "new": total_new, "counts": counts,
               "summary": summary_str, "query_set_id": set_id}
        if first_refuse:
            out["refuse"] = first_refuse       # informatief; de puls slaagde (fail-loud per platform)
        return out
