"""Terugkerende kosten — managementadministratie, Finance PR 1 (10 oktober 2026).

De opvolger van de vaste-kostenlijst uit CN2 (#702): dezelfde rol (de noemer van de runway, de som
van wat op een peildatum loopt), nu met de velden van het kostenregister zodat hij later in het
register opgaat: omschrijving, leverancier, bedrag per maand in CENTEN (excl. btw), Venema-rekening,
managementregel, van, tot (leeg = doorlopend), notitie.

WIJZIGEN MAG (besluit Stefan) — het is een plan, geen boeking — maar elke wijziging en verwijdering
komt als regel in `data/finance/recurring_log.jsonl` (wie, wanneer, oud → nieuw). Niets verdwijnt
stil.

De migratie van de oude lijst (`data/vaste_kosten.json`) staat in `migreer`: idempotent, dry-run als
standaard. Het oude veld `categorie` wordt de rekening (zo noemde CN2 het: "categorie als
rekeningnummer of categorienaam").
"""
from __future__ import annotations

import json
import os
import time
import uuid

from nooch_village.finance_register import MAP, centen
from nooch_village.util import JsonStore
from nooch_village.vaste_kosten import _datum, loopt_op


def maak_regel(omschrijving: str, bedrag, *, leverancier: str = "", account_code: str = "",
               management_line: str = "", van: str = "", tot: str = "", notitie: str = "",
               categorie: str = "") -> tuple[dict | None, str]:
    """(regel, "") of (None, reden). `bedrag` in EURO'S (komma of punt), opgeslagen in centen.
    `categorie` is de oude naam van `account_code` (CN2) en wordt daarheen gezet."""
    oms = " ".join((omschrijving or "").split())[:120]
    c = centen(bedrag)
    v, t = _datum(van), _datum(tot)
    if not oms:
        return None, "a description is required"
    if c is None or c < 0:
        return None, "the amount per month must be a number ≥ 0"
    if not v:
        return None, "a start date (YYYY-MM-DD) is required"
    if str(tot or "").strip() and not t:
        return None, "the end date must be YYYY-MM-DD, or empty for ongoing"
    if t and t < v:
        return None, "the end date is before the start date"
    account = " ".join((account_code or categorie or "").split())[:80]
    if management_line:
        from nooch_village import finance_config as fc
        if fc.regel(management_line) is None:
            return None, "unknown management line"
    return {"description": oms, "supplier": " ".join((leverancier or "").split())[:120],
            "amount_cents": c, "account_code": account, "management_line": management_line or "",
            "van": v, "tot": t, "notitie": " ".join((notitie or "").split())[:280]}, ""


class RecurringCostStore(JsonStore):
    """`{id: regel}` in `data/finance/recurring.json`, met een logboek ernaast. Zelfde naar buiten
    als de vaste-kostenlijst van #702 (`alle`, `totaal_op`, `zet`, `weg`), zodat de runway niets
    hoeft te weten van de verhuizing."""

    _STATE = "_d"
    _WRITE_METHODS = ("zet", "weg")

    def __init__(self, path: str):
        super().__init__(path)
        self.log_pad = os.path.join(os.path.dirname(path), "recurring_log.jsonl")

    def _log(self, actie: str, rid: str, oud, nieuw, door: str) -> None:
        os.makedirs(os.path.dirname(self.log_pad), exist_ok=True)
        with open(self.log_pad, "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": time.time(), "door": door, "actie": actie, "id": rid,
                                "oud": oud, "nieuw": nieuw}, ensure_ascii=False) + "\n")

    def alle(self) -> list[dict]:
        return sorted((dict(v, id=k) for k, v in self._d.items() if isinstance(v, dict)),
                      key=lambda r: (r.get("van", ""), r.get("description", "").lower()))

    def get(self, rid: str) -> dict | None:
        v = self._d.get(rid)
        return dict(v, id=rid) if isinstance(v, dict) else None

    def totaal_op(self, peildatum: str = "") -> float:
        """De vaste kosten per maand op de peildatum, in EURO'S (de runway rekent in euro's)."""
        return self.totaal_cents_op(peildatum) / 100

    def totaal_cents_op(self, peildatum: str = "") -> int:
        p = _datum(peildatum) or time.strftime("%Y-%m-%d")
        return sum(r["amount_cents"] for r in self.alle() if loopt_op(r, p))

    def zet(self, regel: dict, *, rid: str = "", door: str = "") -> str:
        nieuw_id = rid or uuid.uuid4().hex[:10]
        oud = self._d.get(nieuw_id)
        self._d[nieuw_id] = {**regel, "door": door, "op": time.time()}
        self._save()
        self._log("wijzig" if oud else "nieuw", nieuw_id, oud, self._d[nieuw_id], door)
        return nieuw_id

    def weg(self, rid: str, door: str = "") -> bool:
        if rid not in self._d:
            return False
        oud = self._d.pop(rid)
        self._save()
        self._log("weg", rid, oud, None, door)
        return True


def pad(data_dir: str) -> str:
    return os.path.join(data_dir, MAP, "recurring.json")


def migreer(data_dir: str, store: RecurringCostStore, *, apply: bool = False) -> list[dict]:
    """Zet de regels van de oude vaste-kostenlijst (`data/vaste_kosten.json`, #702) over naar
    `recurring`. IDEMPOTENT: een regel die al overgezet is (zelfde id) wordt overgeslagen. Dry-run
    tenzij `apply`. Het oude bestand blijft staan — niets verdwijnt."""
    oud_pad = os.path.join(data_dir, "vaste_kosten.json")
    if not os.path.exists(oud_pad):
        return []
    with open(oud_pad, encoding="utf-8") as f:
        oud = json.load(f)
    rapport = []
    for rid, r in sorted(oud.items()):
        if not isinstance(r, dict):
            continue
        if store.get(rid) is not None:
            rapport.append({"id": rid, "omschrijving": r.get("omschrijving", ""), "actie": "al over"})
            continue
        regel, fout = maak_regel(r.get("omschrijving", ""), r.get("bedrag"), van=r.get("van", ""),
                                 tot=r.get("tot", ""), notitie=r.get("notitie", ""),
                                 categorie=r.get("categorie", ""))
        if regel is None:
            rapport.append({"id": rid, "omschrijving": r.get("omschrijving", ""), "actie": f"fout: {fout}"})
            continue
        rapport.append({"id": rid, "omschrijving": regel["description"], "actie": "over"})
        if apply:
            store.zet(regel, rid=rid, door=r.get("door") or "migratie")
    return rapport
