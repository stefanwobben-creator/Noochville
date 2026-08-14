"""Notificaties intrekken die een inmiddels gefixte bug heeft uitgezonden.

Het geval. `claims_board` stuurde een kopie naar de Circle Lead met "[rol X onbemand]" zodra een
rol onbemand leek. `bemand()` keek toen naar het verkeerde (type "person", assignments zonder
`record=`), dus élke AI-bemande rol las als onbemand. Dat is gefixt in #271. Maar de 37 kopieën
die de bug al had uitgestuurd bleven staan, en die stonden nog steeds in de founder-inbox als
werk — terwijl compliance en copywriter gewoon bemand zijn en doorgewerkt hebben.

Ze routeren zou verlopen werk op een bemand bureau injecteren. Ze horen ingetrokken, met een
uitkomst die zegt waarom, zodat het spoor blijft: verwerkt + gearchiveerd, dezelfde route als de
135 vastgelopen-project-notificaties eerder.

Twee guards, want een veeg die te veel pakt is erger dan de rommel:

  - alleen items van vóór de fix (een nieuw item met deze tekst zou een REGRESSIE zijn en moet
    zichtbaar blijven, niet meegeveegd worden);
  - alleen als de genoemde rol NU aantoonbaar bemand is — dat is precies de bewering die de bug
    verkeerd deed, dus die toetsen we opnieuw in plaats van hem te geloven.

Idempotent: gearchiveerde items worden overgeslagen.
"""
from __future__ import annotations

import logging
import re

log = logging.getLogger("village.notif_opruiming")

# De fix (#271, "een AI-rol leest zijn inbox nooit, dus werk hoort op zijn bord") is gemerged op
# 11 aug 2026. Alles van daarvóór met deze tekst is een emissie van de bug.
FIX_TS = 1786492800.0          # 2026-08-11 00:00 UTC
FIX_REF = "#271"

_ONBEMAND = re.compile(r"\[rol ([a-z0-9_]+) onbemand\]", re.I)


def _rol_id(kort: str, records) -> str:
    """De notificatie draagt het laatste segment ('compliance', 'copywriter'). Zoek het record."""
    if records is None:
        return ""
    if records.get(kort) is not None:
        return kort
    for rec in records.all():
        if rec.id.split("__")[-1] == kort:
            return rec.id
    return ""


def stale_onbemand(notif, records, assignments, *, fix_ts: float = FIX_TS) -> list[dict]:
    """De items die de bug heeft uitgezonden en die inmiddels aantoonbaar onwaar zijn."""
    from nooch_village.assignments import bemand

    uit = []
    for n in notif.all():
        if n.get("archived"):
            continue
        m = _ONBEMAND.search(str(n.get("snippet") or ""))
        if not m:
            continue
        if float(n.get("at") or 0) >= fix_ts:
            # Ná de fix: dan is dit géén grafsteen maar een regressie. Zichtbaar laten.
            log.warning("opruiming: '[rol %s onbemand]'-item van NA %s — mogelijke regressie, "
                        "niet opgeruimd (%s)", m.group(1), FIX_REF, n.get("id"))
            continue
        rol = _rol_id(m.group(1), records)
        if not rol or not bemand(rol, assignments, records):
            continue                                   # rol is écht onbemand → geen grafsteen
        uit.append(n)
    return uit


def archiveer_stale_onbemand(notif, records, assignments, *, fix_ts: float = FIX_TS,
                             dry_run: bool = False) -> dict:
    """Trek de emissies van de gefixte bug in. Geeft een telling terug; logt wat hij deed."""
    kandidaten = stale_onbemand(notif, records, assignments, fix_ts=fix_ts)
    if not kandidaten:
        return {"gevonden": 0, "gearchiveerd": 0}
    if dry_run:
        return {"gevonden": len(kandidaten), "gearchiveerd": 0}
    n = 0
    for item in kandidaten:
        iid = item.get("id")
        notif.mark_item_processed(
            iid, outcome=f"ingetrokken: emissie van een gefixte bug ({FIX_REF}) — de rol was al bemand",
            by="opruiming")
        if notif.archive_item(iid):
            n += 1
    log.info("opruiming: %d/%d '[rol X onbemand]'-notificatie(s) ingetrokken (%s)",
             n, len(kandidaten), FIX_REF)
    return {"gevonden": len(kandidaten), "gearchiveerd": n}
