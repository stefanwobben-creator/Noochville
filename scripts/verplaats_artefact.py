"""Verplaats een artefact (note | policy | tool) naar een andere rol of cirkel.

Waarom dit bestaat: `AttachmentStore.update()` kan de `anchor` bewust niet wijzigen, en
archiveren-plus-opnieuw-aanmaken kost je de id én de versiehistorie (de NNN-teller telt de
gearchiveerde id gewoon mee, dus POSITIONSTAT-001 wordt POSITIONSTAT-002). Een organisatie
verandert echter van vorm: een policy die eerst bij één rol hoorde, blijkt daarna voor de hele
cirkel te gelden. Dit script laat het artefact die verhuizing volgen zonder identiteit te
verliezen.

Fail-closed: het doel moet het domein van de policy in `definition.domains` hebben staan. Dat is
dezelfde eis die de cockpit server-side stelt bij het aanmaken (cockpit2, `owner_domains`). Zonder
die check zou een policy na de verhuizing bij een eigenaar hangen die dat domein niet bezit, en
dan is de governance-keten stuk.

Gebruik:
    ./venv/bin/python scripts/verplaats_artefact.py TONEOFVOICE-001 mother_earth__nooch
    ./venv/bin/python scripts/verplaats_artefact.py TONEOFVOICE-001 mother_earth__nooch --doen

Zonder `--doen` is het een droogloop: hij vertelt wat er zou gebeuren en raakt niets aan.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from nooch_village import artefacts                       # noqa: E402
from nooch_village.governance import Records              # noqa: E402
from nooch_village.util import atomic_write_json, file_lock, read_json  # noqa: E402

_DATA = os.path.join(os.path.dirname(__file__), "..", "data")


class VerplaatsFout(Exception):
    """Het artefact mag niet verhuizen. De boodschap is voor de mens aan de terminal."""


def controleer(artefact: dict, doel_id: str, records) -> str:
    """Mag dit artefact naar dit doel? Retourneert de naam van het doel, of gooit VerplaatsFout."""
    doel = records.get(doel_id)
    if doel is None:
        raise VerplaatsFout(f"Doel '{doel_id}' bestaat niet in de governance-records.")
    if artefact.get("anchor") == doel_id:
        raise VerplaatsFout(f"Artefact hangt al bij '{doel_id}'. Niets te doen.")
    if artefact.get("kind") == "policy":
        domein = (artefact.get("domain") or "").strip()
        domeinen = list(getattr(doel.definition, "domains", None) or [])
        if not domein:
            raise VerplaatsFout("Policy zonder domein kan niet verhuizen: een policy is "
                                "domein-gescopeerd. Zet eerst een domein.")
        if domein not in domeinen:
            raise VerplaatsFout(
                f"Doel '{doel_id}' heeft het domein '{domein}' niet. "
                f"Aanwezig: {domeinen or 'geen'}. Voeg het domein eerst toe via een "
                f"governance-ronde; dat is bewust geen scriptbare stap.")
    return getattr(doel.definition, "name", "") or doel_id


def verplaats(pad: str, artefact_id: str, doel_id: str, records, *,
              actor_id: str = "", governance_ref: str = "", doen: bool = False) -> dict:
    """Herschrijf de anchor. Legt een versie-entry vast zodat de verhuizing in de historie staat,
    en schrijft een changelog-regel zodat de 'gewijzigd sinds laatst gezien'-stip klopt voor de
    nieuwe erfketen."""
    with file_lock(pad):
        items = read_json(pad, {})
        a = items.get(artefact_id)
        if a is None:
            raise VerplaatsFout(f"Artefact '{artefact_id}' bestaat niet.")
        doelnaam = controleer(a, doel_id, records)
        van = a.get("anchor", "")
        if not doen:
            return {"artefact_id": artefact_id, "van": van, "naar": doel_id,
                    "doelnaam": doelnaam, "toegepast": False}
        a["anchor"] = doel_id
        a["updated_at"] = time.time()
        versies = a.setdefault("versions", [])
        nr = (versies[-1]["version_nr"] + 1) if versies else 1
        versies.append({
            "version_nr": nr, "ts": time.time(), "actor_id": actor_id, "actor_type": "human",
            "body_snapshot": a.get("body", ""),
            "change_note": f"verplaatst van {van} naar {doel_id}",
            "governance_ref": governance_ref,
        })
        atomic_write_json(pad, items)

    # Changelog buiten het slot: log_change pakt zijn eigen slot op zijn eigen pad.
    artefacts.log_change(os.path.dirname(pad), action="edit",
                         artefact=type("A", (), {"id": artefact_id, "anchor": doel_id,
                                                 "kind": a.get("kind", ""),
                                                 "inherit": bool(a.get("inherit"))})(),
                         records=records, actor_id=actor_id, actor_type="person",
                         governance_ref=governance_ref)
    return {"artefact_id": artefact_id, "van": van, "naar": doel_id, "doelnaam": doelnaam,
            "toegepast": True}


def main() -> int:
    p = argparse.ArgumentParser(description="Verplaats een artefact naar een andere rol/cirkel.")
    p.add_argument("artefact_id", help="bv. TONEOFVOICE-001")
    p.add_argument("doel", help="record-id van de nieuwe eigenaar, bv. mother_earth__nooch")
    p.add_argument("--doen", action="store_true", help="daadwerkelijk schrijven (default: droogloop)")
    p.add_argument("--actor", default="", help="wie verplaatst (e-mail/persoon-id)")
    p.add_argument("--ref", default="", help="governance_ref: het besluit dat dit toestaat")
    p.add_argument("--data", default=_DATA, help="data-map (default: ./data)")
    args = p.parse_args()

    records = Records(os.path.join(args.data, "governance_records.json"))
    try:
        uit = verplaats(os.path.join(args.data, "attachments.json"), args.artefact_id, args.doel,
                        records, actor_id=args.actor, governance_ref=args.ref, doen=args.doen)
    except VerplaatsFout as e:
        print(f"Geweigerd: {e}")
        return 1
    kop = "Verplaatst" if uit["toegepast"] else "Droogloop (niets gewijzigd)"
    print(f"{kop}: {uit['artefact_id']}\n  van : {uit['van']}\n  naar: {uit['naar']} "
          f"({uit['doelnaam']})")
    if not uit["toegepast"]:
        print("\nVoeg --doen toe om het echt te schrijven.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
