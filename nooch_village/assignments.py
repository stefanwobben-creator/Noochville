"""Bezetting — wie vervult welke rol (GlassFrog 'Role Fillers').

Meervoudig én hybride: een rol kan door meerdere *fillers* vervuld worden, en een filler is een
mens (`person`) of een AI-inwoner (`persona`). Een mens kan meerdere rollen vervullen.

Dit is bewust een aparte laag náást de governance-records: een rol *bestaat* (geboren) via een
record; wie 'm *vervult* (bemenst) is operationeel en wijzigt vaak, zonder governance-wijziging.
`fillers_of` voegt legacy `Record.held_by` (mens) en `Record.persona_id` (AI) samen met de nieuwe
lijst, zodat bestaande data blijft werken.
"""
from __future__ import annotations
import json
import logging
import os
from dataclasses import dataclass

from nooch_village.util import atomic_write_json, read_json

log = logging.getLogger("village.assignments")

_VALID_TYPES = ("person", "persona")


@dataclass(frozen=True)
class Filler:
    """Een rolvervuller: een mens (person) of een AI-inwoner (persona). `focus` = optioneel
    waar deze vervuller zich binnen de rol op richt (GlassFrog 'Focus')."""
    type: str   # "person" | "persona"
    id: str
    focus: str = ""

    def as_dict(self) -> dict:
        return {"type": self.type, "id": self.id, "focus": self.focus}


class Assignments:
    """Store: role_id -> lijst fillers. data/assignments.json."""

    def __init__(self, path: str):
        self.path = path
        self._by_role: dict[str, list[dict]] = {k: list(v) for k, v in read_json(path, {}).items()}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        atomic_write_json(self.path, self._by_role)

    def assign(self, role_id: str, filler_type: str, filler_id: str, focus: str = "") -> bool:
        """Ken een filler toe aan een rol. Idempotent op (type, id); bestaat hij al, dan wordt
        de focus bijgewerkt (indien meegegeven)."""
        if filler_type not in _VALID_TYPES or not role_id or not filler_id:
            return False
        lst = self._by_role.setdefault(role_id, [])
        for r in lst:
            if r.get("type") == filler_type and r.get("id") == filler_id:
                if focus:
                    r["focus"] = focus
                self._save()
                return True
        lst.append({"type": filler_type, "id": filler_id, "focus": focus})
        self._save()
        return True

    def set_focus(self, role_id: str, filler_type: str, filler_id: str, focus: str) -> bool:
        for r in self._by_role.get(role_id, []):
            if r.get("type") == filler_type and r.get("id") == filler_id:
                r["focus"] = focus
                self._save()
                return True
        return False

    def unassign(self, role_id: str, filler_type: str, filler_id: str) -> bool:
        lst = self._by_role.get(role_id, [])
        for r in list(lst):
            if r.get("type") == filler_type and r.get("id") == filler_id:
                lst.remove(r)
                if not lst:
                    self._by_role.pop(role_id, None)
                self._save()
                return True
        return False

    def _stored(self, role_id: str) -> list[Filler]:
        return [Filler(r["type"], r["id"], r.get("focus", "")) for r in self._by_role.get(role_id, [])
                if r.get("type") in _VALID_TYPES and r.get("id")]

    def fillers_of(self, role_id: str, record=None) -> list[Filler]:
        """Alle fillers van een rol: de toegewezen lijst, aangevuld met legacy `held_by` (mens) en
        `persona_id` (AI) van het record (indien meegegeven). Dedup, volgorde stabiel."""
        out: list[Filler] = list(self._stored(role_id))
        seen = {(f.type, f.id) for f in out}
        if record is not None:
            held = getattr(record, "held_by", None)
            if held and ("person", held) not in seen:
                out.append(Filler("person", held)); seen.add(("person", held))
            pid = getattr(record, "persona_id", None)
            if pid and ("persona", pid) not in seen:
                out.append(Filler("persona", pid)); seen.add(("persona", pid))
        return out

    def roles_of(self, filler_type: str, filler_id: str) -> list[str]:
        """Alle rollen die deze filler vervult (alleen de toegewezen laag)."""
        return [rid for rid, lst in self._by_role.items()
                if any(r.get("type") == filler_type and r.get("id") == filler_id for r in lst)]

    def all(self) -> dict[str, list[dict]]:
        return {k: list(v) for k, v in self._by_role.items()}


# ── Bemensing: één definitie, één bron van waarheid ─────────────────────────────────────────

def bemensing(role_id: str, assignments, records=None,
              *, alleen_mensen: bool = False) -> tuple[bool | None, str]:
    """(ja / nee / ONBEKEND, reden) — zit er iemand in deze rol? `None` = niet vast te stellen.

    DE DERDE WAARDE IS DE HELE POINTE. Hiervoor gaven `bemand` en `door_mens_bemand` een kale
    `False` terug zodra de store niet te lezen was. Het commentaar boven de `except` zei al
    "een kapotte store ≠ onbemand-oordeel" — en de regel eronder deed precies dat: hij gaf het
    onbemand-oordeel. `claims_board` hing daar een BERICHT aan ("[rol X onbemand]" naar de Circle
    Lead), dus een leesfout van één seconde werd een bewering over de organisatie die daarna in
    de stapel van de founder bleef staan. Dat is dezelfde vorm als de 37 kopieën die op 14
    augustus met de hand zijn weggeveegd, alleen met een andere oorzaak.

    "Ik weet het niet" is een antwoord dat een aanroeper kan wegen; `False` is dat niet. Elke
    aanroeper kiest daarom zelf zijn faalrichting, en moet die opschrijven (`bij_twijfel` op
    `bemand`/`door_mens_bemand` is verplicht). Hier is geen goede default: bij `claims_board`
    moet twijfel zwijgen, bij `escalation_router` moet twijfel géén kandidaat opleveren, en dat
    zijn tegengestelde richtingen op dezelfde vraag.

    `alleen_mensen=True` beperkt tot type "person". Een PERSONA telt dan niet mee: die is een
    stem, geen paar handen (zie `governance.wordt_opgepakt`).

    Deze functie is DE plek waar de bemensingsvraag beantwoord wordt. Hij leest beide lagen (de
    assignments-store én het legacy `record.persona_id`-veld); dat is geen besluiteloosheid maar
    een vangnet ná de migratie (`migrate_persona_bindings`): de data is uitgelijnd, en mocht er
    ooit tóch een legacy-binding opduiken, dan ziet precies deze ene functie 'm — niet elke
    aanroeper apart, want dát was de val."""
    if not role_id:
        return None, "geen rol opgegeven"
    if assignments is None:
        return None, "geen assignments-store"
    rec = None
    if records is not None:
        try:
            rec = records.get(role_id)
        except Exception as e:                           # noqa: BLE001 — kapotte store ≠ oordeel
            log.warning("bemensing(%s): records niet leesbaar (%s: %s)", role_id, type(e).__name__, e)
            return None, f"records niet leesbaar ({type(e).__name__})"
    try:
        fillers = list(assignments.fillers_of(role_id, record=rec))
    except Exception as e:                               # noqa: BLE001
        log.warning("bemensing(%s): assignments niet leesbaar (%s: %s)", role_id, type(e).__name__, e)
        return None, f"assignments niet leesbaar ({type(e).__name__})"
    if alleen_mensen:
        mensen = [f for f in fillers if f.type == "person"]
        if mensen:
            return True, f"{len(mensen)} mens(en) in de rol"
        return False, ("wel vervuld, maar niet door een mens" if fillers else "niemand in de rol")
    if fillers:
        return True, f"{len(fillers)} vervuller(s)"
    return False, "niemand in de rol"


def bemand(role_id: str, assignments, records=None, *, bij_twijfel: bool) -> bool:
    """Is deze rol bemand — door een MENS of door een PERSONA? Zie `bemensing`.

    `bij_twijfel` is VERPLICHT en heeft bewust geen default: het is de enige plek waar de
    aanroeper zegt wat een onleesbare store betekent voor zíjn beslissing. Een default zou die
    keuze weer onzichtbaar maken, en onzichtbaar is precies hoe de kale `False` hier drie jaar
    kon blijven staan."""
    ja, _reden = bemensing(role_id, assignments, records)
    return bij_twijfel if ja is None else ja


def door_mens_bemand(role_id: str, assignments, records=None, *, bij_twijfel: bool) -> bool:
    """Vervult een MENS deze rol? Voor de paar plekken waar dat écht de vraag is (een mens-inbox
    heeft een mens nodig). Onderscheiden van `bemand`, want die twee zijn niet hetzelfde en het
    door elkaar halen is precies wat misging. `bij_twijfel`: zie `bemand`."""
    ja, _reden = bemensing(role_id, assignments, records, alleen_mensen=True)
    return bij_twijfel if ja is None else ja


def migrate_persona_bindings(records, assignments) -> int:
    """Legacy `record.persona_id` → de assignments-store. Geeft het aantal verplaatste bindingen.

    DE keuze tegen de twee-lagen-divergentie: de assignments-store wordt de bron van waarheid, en
    `fillers_of(rol)` zónder `record=` klopt daarna. De legacy velden blijven op het record staan
    (andere code leest ze nog, bv. de WIP-limiet), maar ze zijn geen tweede waarheid meer — ze zijn
    een kopie die meeloopt.

    Idempotent: een binding die er al staat wordt niet gedupliceerd. Fail-soft per record."""
    verplaatst = 0
    try:
        alle = records.all()
    except Exception:                                    # noqa: BLE001
        return 0
    for rec in alle:
        pid = getattr(rec, "persona_id", None)
        if not pid:
            continue
        try:
            if any(f.type == "persona" and f.id == pid
                   for f in assignments.fillers_of(rec.id)):
                continue                                 # al in de store
            assignments.assign(rec.id, "persona", pid)
            verplaatst += 1
        except Exception:                                # noqa: BLE001 — één kapot record blokkeert niet
            continue
    return verplaatst
