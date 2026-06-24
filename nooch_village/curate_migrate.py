"""Her-curatie van bestaande kaartjes door de curator.

Eenmalige migratie-laag: haal een bestaand (bijv. Nederlands, niet-atomair) kaartje
opnieuw door de curate-engine, zodat het Engels en atomair terugkomt, en vervang het
origineel. Geen nieuwe schrijfweg naast de curator — dit IS de curator, toegepast op
wat er al stond.

Fail-closed: levert de curator geen geldig kaartje op (LLM weg, onparseerbaar), dan
blijft het origineel staan. Er gaat nooit kennis verloren door een mislukte curatie.
"""
from __future__ import annotations
from datetime import date

from nooch_village.curate import curate
from nooch_village.ingest import ingest_insights


def recurate_card(notes, card_id: str, *, source_date: str | None = None,
                  reason_fn=None) -> dict:
    """Haal één bestaand kaartje opnieuw door de curator en vervang het.

    Alleen als de curator minstens één geldig (Engels, atomair, compleet) kaartje
    oplevert, verdwijnt het origineel. Anders blijft alles staan.
    Geeft {'card_id', 'replaced', 'new_ids', 'reason'}.
    """
    orig = notes.get(card_id)
    if orig is None:
        return {"card_id": card_id, "replaced": False, "new_ids": [],
                "reason": "niet gevonden"}
    sd = source_date or date.today().isoformat()
    existing = [n.id for n in notes.all() if n.id != card_id][:60]
    cards = curate(orig.claim, source=f"recurate:{card_id}", source_date=sd,
                   existing_ids=existing, reason_fn=reason_fn)
    if not cards:
        return {"card_id": card_id, "replaced": False, "new_ids": [],
                "reason": "curator leverde geen geldig kaartje (origineel behouden)"}
    notes.remove(card_id)
    res = ingest_insights(notes, cards)
    return {"card_id": card_id, "replaced": True, "new_ids": res["added"],
            "reason": f"{len(res['added'])} Engels atomair kaartje(s)"}


def recurate_cards(notes, card_ids, *, source_date: str | None = None,
                   reason_fn=None) -> list[dict]:
    """Her-cureer een lijst kaartjes, sequentieel (elk kaartje ziet de verse store)."""
    return [recurate_card(notes, cid, source_date=source_date, reason_fn=reason_fn)
            for cid in card_ids]
