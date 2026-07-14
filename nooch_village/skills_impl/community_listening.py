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
import re
import time

from nooch_village.skills import Skill
from nooch_village.util import refuse

log = logging.getLogger("village.skill.buzz")


def _refuse(code: str, reason: str, **ctx) -> dict:
    """Log de weigering (stabiele code) én geef een fail-dict terug, zodat élk early-return-pad
    zowel een logregel als een leesbare uitkomst heeft."""
    refuse(code, reason, **ctx)
    return {"ok": False, "refuse": code, "error": reason, **ctx}


def _dedup_ci(items) -> list[str]:
    """Case-insensitive, gestripte dedup met behoud van volgorde (handmatige queries eerst)."""
    seen, out = set(), []
    for it in items:
        s = str(it).strip()
        k = s.lower()
        if s and k not in seen:
            seen.add(k)
            out.append(s)
    return out


def _slugify(text: str) -> str:
    """Deterministische, korte slug voor de discovery-set-id (`discover:<slug>`). Geen tijd/random,
    zodat dezelfde focus dezelfde tag krijgt en observaties per project herkenbaar geclusterd blijven."""
    s = re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")
    return s[:40]


class CommunityListeningSkill(Skill):
    name = "community_listening"
    cost = "rate_limited"          # publieke endpoints, beleefde 1 req/s + backoff
    side_effect_free = False       # schrijft observatie-rijen
    required_env = ()              # geen HARDE key: Bluesky is keyless (YouTube is optioneel)
    optional_env = ("YOUTUBE_API_KEY",)   # verbetert: zonder key slaat alleen YouTube over
    description = ("Verzamelt gebruikerservaringen (YouTube-comments + Bluesky-posts, Reddit inactief) "
                  "over een onderwerp als gestructureerde observaties. Grounded, geen oordeel/sentiment. "
                  "Twee modi: MONITOR (vaste set uit de config, historische reeks) of DISCOVERY "
                  "(projectscope, vrije termen buiten de Library om). Fail-closed, 6u-cache, quota-guard.")
    input_schema = (
        "Precies één van twee modi. "
        "MONITOR: query_set_id: str — verwijst naar een BESTAANDE set in buzz_query_sets.json "
        "(vaste, mens-gecureerde termen; bouwt een historische reeks op). Verzin hier NOOIT een id. "
        "DISCOVERY (voor een project met eigen scope): laat query_set_id weg en geef "
        "queries: [str] — vrije zoektermen die je AFLEIDT uit het projectdoel (mogen buiten de "
        "Library om gaan; eenmalige verkenning, geen reeks); optioneel focus: str (kort onderwerp-label "
        "voor de tag). optioneel (beide modi): time_window: str (default '7d', alleen Reddit)")
    required_payload = ()   # voorwaardelijk: óf query_set_id óf queries — validate_payload bewaakt dit
    output_schema = ("ok: bool, count/new: int (nieuwe rijen totaal), counts: {platform: int|'inactief'}, "
                     "summary: str, query_set_id: str (in discovery-modus een 'discover:<slug>'-tag) "
                     "| refuse-dict met code BUZZ_*")

    def validate_payload(self, payload, context) -> list:
        """Grondings-poort voor beide modi. MONITOR: de query_set_id MOET naar een bestaande set
        verwijzen — een planner mag er geen verzinnen (anders een 'uitvoerbaar' item dat live sterft met
        BUZZ_NO_SET). DISCOVERY: inline queries hebben geen verwijzing en zijn dus per definitie gegrond.
        Ontbreken beide → het item is niet uitvoerbaar (geen scope). Fail-soft als de store onleesbaar is."""
        payload = payload or {}
        set_id = (payload.get("query_set_id") or "").strip()
        queries = [q for q in (payload.get("queries") or []) if str(q).strip()]
        if set_id:
            try:
                exists = self._query_sets(context).get(set_id) is not None
            except Exception:
                return []                            # store onleesbaar → niet blokkeren
            return [] if exists else [f"query-set '{set_id}' bestaat niet"]
        if queries:
            return []                                # discovery-modus: inline termen, niets te gronden
        return ["geef een bestaande query_set_id (monitor) of discovery-queries op"]

    def _discovery_set(self, focus, queries) -> tuple[str, dict]:
        """Bouw een EFEMERE zoek-set uit inline queries (project-/discovery-modus). Niet opgeslagen in de
        config (blijft data, geen code): YouTube + Bluesky actief, Reddit inactief, en BEWUST géén
        library_link — zo gaan discovery-termen buiten de Library om (verkenning, niet de vaste reeks).
        De id krijgt het `discover:`-voorvoegsel zodat observaties per project herkenbaar en gescheiden
        van de monitor-reeks blijven."""
        label = (str(focus).strip() if focus else "") or (queries[0] if queries else "discovery")
        slug = _slugify(label) or "adhoc"
        q = _dedup_ci(queries)
        set_id = f"discover:{slug}"
        return set_id, {
            "id": set_id, "label": label[:120], "active": True,
            "platforms": {
                "youtube": {"active": True, "channel_ids": [], "queries": q},
                "bluesky": {"active": True, "queries": q},
                "reddit": {"active": False, "subreddits": [], "queries": q},
            },
        }

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

    def _merge_library(self, set_id: str, platform: str, cfg: dict, library, cache) -> dict:
        """v2.1: als dit platform een actief library_link heeft, sync de research-approved Library-
        termen en merge ze (case-insensitive) met de handmatige queries. De fetcher weet niets van de
        Library — hij krijgt gewoon een cfg-kopie met meer queries. Geen link/geen termen → cfg ongewijzigd.
        Fail-open: bij BUZZ_LIBRARY_UNAVAILABLE komen er geen termen bij en draaien de handmatige queries door."""
        link = cfg.get("library_link")
        if not link or not link.get("active"):
            return cfg
        from nooch_village.buzz_library_sync import sync_library_terms
        lib_terms = sync_library_terms(set_id, platform, link, library, cache)
        if not lib_terms:
            return cfg
        return {**cfg, "queries": _dedup_ci(list(cfg.get("queries") or []) + lib_terms)}

    # ── run ─────────────────────────────────────────────────────────────────────
    def run(self, payload: dict, context=None) -> dict:
        payload = payload or {}
        set_id = (payload.get("query_set_id") or "").strip()
        queries = [str(q).strip() for q in (payload.get("queries") or []) if str(q).strip()]

        if set_id:
            # MONITOR-modus: vaste, mens-gecureerde set uit de config (historische reeks).
            qset = self._query_sets(context).get(set_id)
            if qset is None:
                return _refuse("BUZZ_NO_SET", "zoek-set bestaat niet", query_set_id=set_id)
            if not qset.get("active"):
                return _refuse("BUZZ_SET_INACTIVE", "zoek-set staat op inactive", query_set_id=set_id)
        elif queries:
            # DISCOVERY-modus: efemere projectscope uit inline queries (buiten de Library om).
            set_id, qset = self._discovery_set(payload.get("focus"), queries)
        else:
            return _refuse("BUZZ_NO_SET", "geef een bestaande query_set_id of discovery-queries op")

        platforms = qset.get("platforms") or {}
        if not platforms:
            return _refuse("BUZZ_EMPTY_SET", "zoek-set heeft geen platforms", query_set_id=set_id)

        from nooch_village.skills_impl.buzz_fetchers import FETCHERS
        from nooch_village.buzz_query_sets import PLATFORM_ORDER

        store = self._obs_store(context)
        cache = self._cache(context)
        library = getattr(context, "library", None)
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
            eff_cfg = self._merge_library(set_id, platform, cfg, library, cache)
            res = fetcher.fetch(set_id, eff_cfg, context, cache, opts)
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
