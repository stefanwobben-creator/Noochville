"""project_completed-event bij autonome afronding + opname in Noochies dagbulletin.

Publicatie-kant (Inhabitant._claim_run_complete): exact één event bij DONE, geen bij onvolledig,
geen tweede bij een tweede passage (idempotentie rust op de status==running-guard).
Bulletin-kant (Noochie): de afrondingsregel '<owner> rondde af: <scope>' (scope uit de ledger),
en fail-closed als het project niet meer in de ledger staat.
"""
from __future__ import annotations
from types import SimpleNamespace
from unittest.mock import patch

from nooch_village.inhabitant import Inhabitant
from nooch_village.roles import Noochie
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus, Event
from nooch_village.skills import SkillRegistry, Skill
from nooch_village.projects import ProjectLedger
from nooch_village.skills_impl.bulletin_schrijven import BulletinSchrijvenSkill

_MOCK_BULLETIN = ("# Dorpsbulletin\n## Wat ik vandaag zag\nx\n## Wie was actief\nx\n"
                  "## Wat ik signaleer\nx\n## Tot morgen\nx")


class _ResearchSkill(Skill):
    name = "openalex_evidence"
    description = "fake research skill"

    def run(self, payload, context):
        term = (payload or {}).get("term", "")
        return {"term": term, "total": 1,
                "hits": [{"title": f"Study on {term}", "year": 2021, "citations": 7, "topic": "footwear"}]}


def _inhabitant(tmp_path, ledger):
    reg = SkillRegistry()
    reg.register(_ResearchSkill())
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0"}, data_dir=str(tmp_path),
                          projects=ledger, records=None)
    rec = Record(id="harry_hemp", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="x", accountabilities=["research"], domains=[],
                                           skills=["openalex_evidence"]), source="sensed")
    return Inhabitant(rec, EventBus(name="test"), reg, ctx)


def _prep(ledger, pid, items):
    cl = ledger.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE)
    for text, skill, query in items:
        ledger.check_add(pid, cl["id"], text, skill=skill, query=query)
    return cl


def _capture(inh):
    got = []
    inh.bus.subscribe("project_completed", lambda e: got.append(e.data))
    return got


# 1. Autonoom DONE → exact één project_completed met project_id/owner/outcome
def test_1_autonome_done_publiceert_event(tmp_path):
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    inh = _inhabitant(tmp_path, ledger)
    got = _capture(inh)
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    _prep(ledger, pid, [("studie", "openalex_evidence", "barefoot")])
    inh._claim_run_complete(pid)
    assert ledger.get(pid)["status"] == "done"
    assert len(got) == 1
    e = got[0]
    assert e["project_id"] == pid and e["owner"] == "harry_hemp" and e["outcome"]
    assert "pid" not in e                                   # sleutel heet project_id, NIET pid


# 2. Onvolledige checklist (blijft ACTIEF) → geen event
def test_2_onvolledig_geen_event(tmp_path):
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    inh = _inhabitant(tmp_path, ledger)
    got = _capture(inh)
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    _prep(ledger, pid, [("studie", "openalex_evidence", "x"), ("mens-taak", None, "")])  # no-skill blijft open
    inh._claim_run_complete(pid)
    assert ledger.get(pid)["status"] != "done"
    assert got == []


# 3. Tweede passage op al-done project → geen tweede event (status-guard, niet last_tended)
def test_3_tweede_passage_geen_tweede_event(tmp_path):
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    inh = _inhabitant(tmp_path, ledger)
    got = _capture(inh)
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    _prep(ledger, pid, [("studie", "openalex_evidence", "x")])
    inh._claim_run_complete(pid)
    assert len(got) == 1
    # forceer dat de guard op status==running rust en niet op de last_tended-datum:
    ledger.get(pid)["last_tended"] = ""
    ledger._save()
    inh._claim_run_complete(pid)                            # al done → guard blokkeert
    assert len(got) == 1 and ledger.get(pid)["status"] == "done"


# ── Bulletin-kant (Noochie) ───────────────────────────────────────────────────
def _make_noochie(tmp_path, ledger):
    reg = SkillRegistry()
    reg.register(BulletinSchrijvenSkill())
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0"}, data_dir=str(tmp_path),
                          records=None, projects=ledger)
    rec = Record(id="noochie", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="x", skills=["bulletin_schrijven"]), source="seed")
    return Noochie(rec, EventBus(name="test"), reg, ctx)


# 4. Bulletin bevat de afrondingsregel met de scope-tekst (scope uit de ledger)
def test_4_bulletin_bevat_afrondingsregel(tmp_path):
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    pid = ledger.create("harry_hemp", "Onderzoek naar barefoot shoes", "human", status="future")
    noochie = _make_noochie(tmp_path, ledger)
    noochie._events_today = [{"name": "project_completed", "by": "harry_hemp", "note": "", "project_id": pid}]
    with patch("nooch_village.llm.reason", return_value=_MOCK_BULLETIN) as mock:
        noochie._on_dag_eindigt(Event("dag_eindigt", {}, "test"))
    prompt = mock.call_args[0][0]
    assert "rondde af: Onderzoek naar barefoot shoes" in prompt   # owner (records=None → id) + scope uit ledger


# 5. project_completed voor een onvindbaar project → regel overgeslagen, geen exception
def test_5_onvindbaar_project_regel_overgeslagen(tmp_path):
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    noochie = _make_noochie(tmp_path, ledger)
    noochie._events_today = [{"name": "project_completed", "by": "harry_hemp", "note": "", "project_id": "bestaat-niet"}]
    with patch("nooch_village.llm.reason", return_value=_MOCK_BULLETIN) as mock:
        noochie._on_dag_eindigt(Event("dag_eindigt", {}, "test"))   # geen crash
    prompt = mock.call_args[0][0]
    assert "rondde af" not in prompt                       # onvindbaar → regel overgeslagen (fail-closed)
