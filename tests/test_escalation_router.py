"""Deel 4 — de escalatie-router: rollen laten samenwerken i.p.v. alles naar de mens te sturen.

De twee niet-onderhandelbare guards staan bovenaan:
  1. HOP-TELLER — A→B→A kan niet ontstaan; bij de limiet eindigt het bij de mens.
  2. ZICHTBAAR DOODLOPEN — loopt een doorverwezen item dood bij B, dan parkeert het daar zichtbaar
     via dezelfde klep, mét gat-record. Nooit stil sterven.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from nooch_village import gap_ledger
from nooch_village.escalation_router import kies_ontvanger, roster, trail_of
from nooch_village.event_bus import EventBus
from nooch_village.governance import Records
from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RecordType, RoleDefinition
from nooch_village.projects import ProjectLedger, PREP_CHECKLIST_TITLE
from nooch_village.skills import Skill, SkillRegistry


def _records(tmp_path):
    recs = Records(str(tmp_path / "gov.json"))
    recs.put(Record(id="harry", type=RecordType.ROLE, parent="dorp",
                    definition=RoleDefinition(purpose="wetenschappelijke onderbouwing",
                                              accountabilities=["onderzoek doen"])))
    recs.put(Record(id="website_dev", type=RecordType.ROLE, parent="dorp",
                    definition=RoleDefinition(purpose="de website bouwen en onderhouden",
                                              accountabilities=["pagina's bouwen"])))
    recs.put(Record(id="dorp", type=RecordType.CIRCLE, parent=None,
                    definition=RoleDefinition(purpose="de cirkel")))
    return recs


def _antwoord(role="NONE", kind="missing_capability", capability=""):
    def _fn(prompt, **kw):
        return json.dumps({"role": role, "kind": kind, "capability": capability})
    return _fn


def _project(ledger, owner="harry", tekst="bouw de QR-landingspagina", trail=None):
    pid = ledger.create(owner, "QR-codes op de schoenen", "human", status="running")
    ledger.start(pid)
    cl = ledger.checklist_add(pid, title=PREP_CHECKLIST_TITLE)
    ledger.check_add(pid, cl["id"], tekst, skill=None, reason="geen skill hiervoor")
    if trail:
        ledger.set_handoff_trail(pid, trail)
    return pid, cl["id"]


def _item(ledger, pid, clid):
    p = ledger.get(pid)
    cl = next(c for c in p["checklists"] if c["id"] == clid)
    return cl["items"][0]


# ── GUARD 1: de hop-teller ─────────────────────────────────────────────────────


# ── de beslisvolgorde ──────────────────────────────────────────────────────────


def test_roster_laat_cirkels_en_zichzelf_weg(tmp_path):
    recs = _records(tmp_path)
    ids = {k["id"] for k in roster(recs, exclude={"harry"})}
    assert ids == {"website_dev"}                            # geen 'dorp' (cirkel), geen 'harry'


def test_kies_ontvanger_is_fail_closed():
    kand = [{"id": "a"}, {"id": "b"}]
    assert kies_ontvanger(None, kand, [], "a") is None
    assert kies_ontvanger({"role": ""}, kand, [], "a") is None
    assert kies_ontvanger({"role": "none"}, kand, [], "a") is None
    assert kies_ontvanger({"role": "zzz"}, kand, [], "a") is None
    assert kies_ontvanger({"role": "a"}, kand, [], "a") is None          # zichzelf
    assert kies_ontvanger({"role": "b"}, kand, ["b"], "a") is None       # zag het al
    assert kies_ontvanger({"role": "b"}, kand, [], "a") == "b"


# ── hulpjes ────────────────────────────────────────────────────────────────────

class _Dummy(Skill):
    name = "niets"
    description = "doet niets"

    def run(self, payload, context):
        return {"ok": True}


def _inhabitant(tmp_path, ledger, recs, rol_id):
    reg = SkillRegistry()
    reg.register(_Dummy())
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0"}, data_dir=str(tmp_path),
                          projects=ledger, records=recs)
    rec = recs.get(rol_id)
    return Inhabitant(rec, EventBus(name="t"), reg, ctx)
