"""Wat er gebeurt op het moment dat een spanning ontstaat.

Eén call, één keer, bij het ontstaan — en alles daarna leest mee. Geen batch en geen vergadering:
wie de spanning later opent, leest de al-geschreven bevinding en het al-bepaalde type.

Dit is de haak die `NotifStore.add` aanroept. De store blijft dom; deze module weet van het model
en van de typering, en hij is fail-soft: gaat er iets mis, dan blijft de rauwe notificatie gewoon
staan. Een spanning die niet verrijkt kon worden is nog steeds een spanning.
"""
from __future__ import annotations

import logging

log = logging.getLogger("village.spanning")

# Verrijken kost een dure call. Alleen doen voor spanningen die een MENS gaat lezen; berichten
# tussen rollen onderling lopen via hun eigen borden en hebben deze tekst niet nodig.
def _is_mens_doel(target_id: str, records, assignments) -> bool:
    from nooch_village.assignments import door_mens_bemand
    try:
        return bool(door_mens_bemand(target_id, assignments, records))
    except Exception:                                    # noqa: BLE001
        return False


def maak_verrijker(records, assignments, data_dir: str = "", reason_fn=None):
    """Bouw de haak. Geeft een functie die één verse notificatie verrijkt."""
    from nooch_village import bevinding as bv, zelf_verwerking as zv

    def _verrijk(n: dict) -> dict:
        if str(n.get("target_type")) != "role":
            return {}
        if not _is_mens_doel(str(n.get("target_id") or ""), records, assignments):
            return {}
        rol = str(n.get("by") or "")
        # DE VOLLE TEKST, niet de preview. Dit las `snippet` — de afgekapte kopie — en herschreef
        # dus een spanning die al halverwege een zin ophield. De herschrijver kon nooit compleet
        # maken wat hem incompleet werd aangereikt.
        from nooch_village.notifications import volledig
        tekst = volledig(n)
        if not tekst.strip():
            return {}
        # SLAPENDE ROL: geen oordeel. Een spanning van een slapende rol wordt niet herschreven en
        # niet getypeerd — dat is de dure kant van het dorp, en die hoort stil te staan zodra een
        # rol slaapt. De spanning zelf blijft gewoon bestaan: slapen dempt het oordeel, het gooit
        # geen signaal weg.
        rec = records.get(rol) if (records is not None and rol) else None
        if rec is not None and getattr(rec, "slaapt", False):
            log.info("spanning van %s niet beoordeeld — die rol slaapt", rol)
            return {}
        b = bv.herschrijf(tekst, rol=rol, records=records, reason_fn=reason_fn)
        t = zv.verwerk(tekst, rol=rol, records=records, reason_fn=reason_fn,
                       voorstel=b.get("voorstel") or "", data_dir=data_dir)
        log.info("spanning van %s getypeerd als %s (bevinding %s)", rol or "?",
                 t.get("uitkomst"), "ok" if b.get("ok") else "geweigerd")
        return {"bevinding": b, "type": t.get("uitkomst"), "type_reden": t.get("reden")}

    return _verrijk
