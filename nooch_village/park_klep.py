"""De parkeer-klep: wanneer keert een geparkeerd project terug in de stroom?

`_tend_projects` pakt alleen `queued` en `running` op. Een project dat naar `blocked` ging werd
daarna nooit meer bekeken — en omdat `reset_item_fails` bij het parkeren de tellers op nul zet,
lázen de items daarna als "kan gewoon vooruit" terwijl het project stil bleef staan. Vier projecten
stonden zo tot vijftien dagen te wachten op niets.

De verleiding is om alles wat er runnable uitziet weer los te laten. Dat is precies de thrash-loop:
draaien, falen, parkeren, weer los, opnieuw falen. Daarom leest deze klep de **vastgelegde
park-reden** (`ProjectLedger.park`, #287) en niet de item-state:

  human   → terug zodra het mens-item is afgevinkt of overgeslagen;
  payload → terug zodra de payload hersteld is (`payload_ok` niet meer False);
  fails   → BLIJFT staan. Een bron die drie keer faalde gaat het bij poging vier ook niet doen;
            daar is een mens of een andere route voor nodig. Automatisch loslaten zou hier alleen
            het logboek vullen.

Een project zonder vastgelegde reden (geparkeerd vóór #287) blijft staan: zonder reden is elke
heropening een gok, en dat is de fout die we net hebben weggehaald.
"""
from __future__ import annotations

import logging

log = logging.getLogger("village.parkklep")


def _items_van(project: dict) -> dict:
    return {it["id"]: it
            for cl in (project.get("checklists") or [])
            for it in (cl.get("items") or []) if it.get("id")}


def opgelost(project: dict, park: dict) -> tuple[bool, str]:
    """Is de vastgelegde blokkade weg? → (ja/nee, in mensentaal waarom).

    Beoordeelt ALLEEN de items die bij het parkeren zijn vastgelegd. Nieuwe items die er sindsdien
    bij kwamen tellen niet mee: dit is de vraag "is de reden van toen verdwenen?", niet "valt er nu
    iets te doen?" — anders opent een toegevoegd item een project dat nog steeds op zijn oude
    blokkade wacht."""
    if not park:
        return False, "geen vastgelegde park-reden (geparkeerd vóór de klep) — laat staan"
    if park.get("reden") == "fails" or any(i.get("reden") == "fails" for i in park.get("items") or []):
        return False, "park-reden 'fails': een bron die faalde heeft ingrijpen nodig, geen herkansing"
    huidig = _items_van(project)
    open_nog = []
    for i in (park.get("items") or []):
        it = huidig.get(i.get("id"))
        if it is None:                                   # item verwijderd → blokkade bestaat niet meer
            continue
        if it.get("done") or it.get("skipped"):
            continue
        if i.get("reden") == "payload" and it.get("payload_ok") is not False:
            continue                                     # payload hersteld
        open_nog.append(str(it.get("text") or "")[:60])
    if open_nog:
        return False, f"{len(open_nog)} van de vastgelegde blokkades staat nog open: {open_nog[0]}"
    return True, "alle vastgelegde blokkades zijn opgelost"


def heropen(ledger, project: dict) -> str | None:
    """Zet dit project terug in de stroom als zijn vastgelegde blokkade weg is.

    Geeft de reden terug als er iets gebeurde, anders None. Fail-soft: een kapotte park-reden mag
    geen puls breken."""
    pid = project.get("id")
    if not pid or project.get("status") != "blocked":
        return None
    try:
        park = ledger.park_reden(pid)
        klaar, waarom = opgelost(project, park)
    except Exception as e:                               # noqa: BLE001
        log.warning("park-klep overgeslagen voor %s: %s", pid, e)
        return None
    if not klaar:
        return None
    if not ledger.unblock(pid):
        return None
    log.info("▶️ project '%s' terug in de stroom: %s", pid, waarom)
    return waarom
