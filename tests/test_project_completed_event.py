"""Review-gate: checklist af → 'wacht' (review), Done pas bij mens-toekenning + bulletin.

Uitvoer-kant (Inhabitant._execute_checklist): checklist volledig af → status 'blocked' met
blocked_on='review' (de WACHT-kolom) + wall-note + project_awaiting_review, GEEN autonome
project_completed. Een verse all-done-overgang vuurt één keer; na terugsleep herblokkeert de
review_raised-vlag niet (tot een checklist-mutatie).
DONE-kant (village._poll_board): mens sleept wacht→done in het cockpit-proces → complete() laat
blocked_on=='review' staan als marker → de board-watch vuurt project_completed (met deliverable_ids)
op de daemon-bus (#10-fix).
Bulletin-kant (Noochie): '<owner> rondde af: <scope>' (Done) én '<owner> wacht op review: <scope>'.
"""
from __future__ import annotations
from types import SimpleNamespace
from unittest.mock import patch

from nooch_village.inhabitant import Inhabitant
from nooch_village.roles import Noochie
from nooch_village.village import Village
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus, Event
from nooch_village.skills import SkillRegistry, Skill
from nooch_village.projects import ProjectLedger, PREP_CHECKLIST_TITLE

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
    cl = ledger.checklist_add(pid, title=PREP_CHECKLIST_TITLE)
    for text, skill, query in items:
        ledger.check_add(pid, cl["id"], text, skill=skill, query=query)
    return cl


def _capture(inh, name="project_completed"):
    got = []
    inh.bus.subscribe(name, lambda e: got.append(e.data))
    return got








# 3b. Mens sleept wacht→done → board-watch vuurt project_completed MÉT deliverable_ids (#10-fix)
def test_3b_mens_done_via_board_watch(tmp_path):
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    pid = ledger.create("harry_hemp", "doel", "human", status="running")
    ledger.start(pid)                                       # → running
    ledger.mark_awaiting_review(pid)                        # checklist af → wacht (blocked_on=review)
    ledger.complete(pid, "checklist voltooid (1/1) — goedgekeurd na review")   # mens kent Done toe
    # board-watch stub (village._poll_board) met verse _completed_seen → detecteert de review-done
    bus = EventBus(name="test"); got = []
    bus.subscribe("project_completed", lambda e: got.append(e.data))
    stub = SimpleNamespace(context=SimpleNamespace(projects=ledger, deliverables=None),
                           bus=bus, _activated_seen=set(), _completed_seen=set())
    Village._poll_board(stub)
    assert len(got) == 1 and got[0]["project_id"] == pid and got[0]["owner"] == "harry_hemp"
    assert got[0]["route"] == "review"                     # via de gate (blocked_on=="review")
    assert got[0]["outcome"].endswith("goedgekeurd na review") and got[0]["deliverable_ids"] == []
    Village._poll_board(stub)                               # tweede poll → geen dubbel event
    assert len(got) == 1


# 3d. Direct Actief→Done (mens sleept zonder de gate) → één project_completed, route="direct", geen deliverables
def test_3d_direct_actief_done(tmp_path):
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    pid = ledger.create("harry_hemp", "doel", "human", status="running")
    ledger.start(pid)                                       # actief (running), blocked_on leeg
    ledger.complete(pid, "handmatig afgerond")             # mens sleept Actief→Done (geen review-marker)
    bus = EventBus(name="test"); got = []
    bus.subscribe("project_completed", lambda e: got.append(e.data))
    stub = SimpleNamespace(context=SimpleNamespace(projects=ledger, deliverables=None, _autonomous_done=set()),
                           bus=bus, _activated_seen=set(), _completed_seen=set())
    Village._poll_board(stub)
    assert len(got) == 1 and got[0]["project_id"] == pid
    assert got[0]["route"] == "direct" and got[0]["deliverable_ids"] == []   # geen gate, geen deliverables
