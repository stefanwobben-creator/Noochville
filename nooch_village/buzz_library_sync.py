"""Library-koppeling voor community_listening (v2.1).

Sync research-approved Library-termen naar de effectieve queries van een platform, met
filter → exclude → cap → diff-log. Zo is de keten GSC → Librarian-triage → Library → Billy Buzz
→ ObservationStore rond: de Librarian-triage IS de poort voor wat er onderzocht wordt; hier komt
geen nieuwe goedkeurstap bij.

Grenzen:
- ALLOWLIST, geen blocklist: alleen wat via `_STATUS_MAP` op de Library-status 'approved' uitkomt
  passeert. Élke andere status — ook een toekomstige, nu onbekende — valt af. Zo laat de poort nooit
  stilletjes door wat we nog niet kenden.
- Fail-open op de handmatige queries: Library onleesbaar → BUZZ_LIBRARY_UNAVAILABLE, [] terug, de
  puls draait door op de handmatige queries.
- GEEN terugvloei van observaties naar de Library (anti-lus; bewuste keuze).
"""
from __future__ import annotations

import logging

from nooch_village.util import refuse

log = logging.getLogger("village.skill.buzz")

# 'research_approved' is in v2.1 de bestaande Library-status 'approved'. Deze indirectie houdt de
# toekomstige research/SEO-status-machine goedkoop: verandert die ooit, dan wisselt alleen deze map,
# niet de sync. De filter blijft een allowlist op de uitkomst van deze map.
_STATUS_MAP = {"research_approved": "approved"}


def _status_ok(entry: dict, wanted: str) -> bool:
    """Allowlist: alleen de status die `wanted` via _STATUS_MAP oplevert passeert."""
    return (entry or {}).get("status") == _STATUS_MAP.get(wanted, wanted)


def _locale_ok(entry: dict, locales: set) -> bool:
    """Locale-filter. null/onbekend PASSEERT (onbekend ≠ verkeerde locale); een expliciete andere
    locale valt af."""
    if not locales:
        return True
    loc = (entry or {}).get("locale") or ((entry or {}).get("evidence") or {}).get("locale")
    return True if not loc else (loc in locales)


def sync_library_terms(set_id: str, platform: str, link_cfg: dict, library, cache) -> list[str]:
    """Resolve de research-approved Library-termen voor deze set+platform (gefilterd, exclude eraf,
    gecapt, gededupt, alfabetisch), log de diff t.o.v. de vorige puls en geef de termen terug.
    Inactief/geen link → []. Library onleesbaar → BUZZ_LIBRARY_UNAVAILABLE + []."""
    if not link_cfg or not link_cfg.get("active"):
        return []
    flt = link_cfg.get("filter") or {}
    wanted_status = flt.get("status") or "research_approved"
    locales = {str(x).strip().lower() for x in (flt.get("locale") or []) if str(x).strip()}
    want_tags = {str(x).strip() for x in (flt.get("tags") or []) if str(x).strip()}
    exclude = {str(t).strip().lower() for t in (link_cfg.get("exclude") or []) if str(t).strip()}
    max_q = int(link_cfg.get("max_queries") or 0)

    if library is None:
        refuse("BUZZ_LIBRARY_UNAVAILABLE", "Library-store niet beschikbaar (None)",
               set=set_id, platform=platform)
        return []
    try:
        entries = library.all()
    except Exception as e:                                # fail-open op handmatige queries
        refuse("BUZZ_LIBRARY_UNAVAILABLE", str(e), set=set_id, platform=platform)
        return []

    cands: list[str] = []
    for word, e in (entries or {}).items():
        if not _status_ok(e, wanted_status):
            continue
        if not _locale_ok(e, locales):
            continue
        if want_tags and not (set((e or {}).get("tags") or []) & want_tags):
            continue
        w = str(word).strip()
        if not w or w.lower() in exclude:                # exclude wint van filter-match (mens-wint)
            continue
        cands.append(w.lower())                          # Library-keys zijn lowercase; expliciet
    cands = sorted(set(cands))                           # dedup + deterministisch alfabetisch

    if max_q and len(cands) > max_q:                     # deterministische afkap (alfabetisch)
        dropped = cands[max_q:]
        refuse("BUZZ_LIBRARY_CAP",
               f"{len(cands)} research-approved termen > max_queries {max_q}",
               set=set_id, platform=platform, dropped=len(dropped), terms=dropped)
        cands = cands[:max_q]

    # Diff-log t.o.v. de vorige puls (vorige stand in de cache, niet in de query-set).
    key = f"libsync:{set_id}:{platform}"
    prev = set(cache.sync_terms(key))
    added = sorted(set(cands) - prev)
    removed = sorted(prev - set(cands))
    if added or removed:
        parts = []
        if added:
            parts.append(f"+{len(added)} ({', '.join(added)})")
        if removed:
            parts.append(f"-{len(removed)} ({', '.join(removed)})")
        log.info("library-sync [%s/%s]: %s", set_id, platform, ", ".join(parts))
    cache.set_sync_terms(key, cands)
    return cands
