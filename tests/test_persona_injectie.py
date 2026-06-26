"""Brok 3 — functionele persona-injectie: de toegewezen inwoner kleurt de LLM-prompt van de rol
(toon, niet capaciteit). work_one neemt de preamble mee; work_projects resolvet hem uit de store."""
from __future__ import annotations
import os
import tempfile

from nooch_village.projects import ProjectLedger
from nooch_village.governance import Records
from nooch_village.models import Record, RecordType, RoleDefinition
from nooch_village.personas import PersonaStore
from nooch_village.project_worker import work_one, work_projects, _persona_for


def test_work_one_zet_persona_vooraan():
    seen = {}
    def fake_llm(prompt):
        seen["p"] = prompt
        return "LEVER: klaar"
    res = work_one("doe iets", "trends", "vind woorden",
                   persona="Je bent Sam (INTJ). Droog en kort.", llm_reason=fake_llm)
    assert res["ok"] and res["outcome"] == "klaar"
    # de persona staat vóór de rol-instructie
    assert seen["p"].startswith("Je bent Sam (INTJ).")
    assert seen["p"].index("Sam") < seen["p"].index("Jouw purpose")


def test_work_one_zonder_persona_ongewijzigd():
    seen = {}
    work_one("x", "trends", "p", persona="", llm_reason=lambda pr: seen.update(p=pr) or "LEVER: ok")
    assert seen["p"].startswith("Je bent de rol 'trends'")    # geen lege preamble-ruis


def test_persona_for_resolved_uit_store():
    d = tempfile.mkdtemp()
    ps = PersonaStore(os.path.join(d, "personas.json"))
    sam = ps.add("Sam", mbti="INTJ", instructions="droog")
    recs = Records(os.path.join(d, "gov.json"))
    recs.put(Record(id="trends", type=RecordType.ROLE, parent=None,
                    definition=RoleDefinition(purpose="vind woorden"), persona_id=sam.id))
    pr = _persona_for(recs.get("trends"), ps)
    assert "Sam" in pr and "INTJ" in pr
    # geen koppeling → leeg
    recs.put(Record(id="kaal", type=RecordType.ROLE, parent=None,
                    definition=RoleDefinition(purpose="x")))
    assert _persona_for(recs.get("kaal"), ps) == ""


def test_work_projects_injecteert_gekoppelde_inwoner():
    d = tempfile.mkdtemp()
    ps = PersonaStore(os.path.join(d, "personas.json"))
    bo = ps.add("Bo", mbti="ENFP", instructions="speels en warm")
    recs = Records(os.path.join(d, "gov.json"))
    recs.put(Record(id="scout", type=RecordType.ROLE, parent=None,
                    definition=RoleDefinition(purpose="speur concurrenten"), persona_id=bo.id))
    led = ProjectLedger(os.path.join(d, "p.json"))
    pid = led.create("scout", "kijk naar concurrent X", "human", status="queued")
    seen = {}
    work_projects(led, recs, llm_reason=lambda pr: seen.update(p=pr) or "LEVER: gedaan",
                  personas=ps)
    assert "Bo" in seen["p"] and "speels en warm" in seen["p"]
    assert led.get(pid)["status"] == "running"               # werk opgepakt
