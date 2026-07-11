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


def _capture(inh, name="project_completed"):
    got = []
    inh.bus.subscribe(name, lambda e: got.append(e.data))
    return got


# 1. Checklist af → WACHT (review), NIET done: geen project_completed, wel awaiting_review + note
def test_1_checklist_af_wacht_op_review(tmp_path):
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    inh = _inhabitant(tmp_path, ledger)
    done_evt = _capture(inh, "project_completed")
    review_evt = _capture(inh, "project_awaiting_review")
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    _prep(ledger, pid, [("studie", "openalex_evidence", "barefoot")])
    inh._claim_run_complete(pid)
    p = ledger.get(pid)
    assert p["status"] == "blocked" and p["blocked_on"] == "review"   # WACHT-kolom
    assert p.get("review_raised") is True and p.get("outcome") in (None, "")   # outcome pas bij Done
    assert done_evt == []                                              # GEEN autonome project_completed
    assert len(review_evt) == 1 and review_evt[0]["project_id"] == pid
    assert any(e.get("text", "").startswith("✅ Checklist voltooid") for e in p.get("log", []))


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


# 3. Wacht → actief terugslepen (review afgewezen): geen re-event, geen re-block, geen outcome-wis
def test_3_terugsleep_herblokkeert_niet_zonder_mutatie(tmp_path):
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    inh = _inhabitant(tmp_path, ledger)
    review_evt = _capture(inh, "project_awaiting_review")
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    _prep(ledger, pid, [("studie", "openalex_evidence", "x")])
    inh._claim_run_complete(pid)                            # → wacht, review_raised gezet
    assert len(review_evt) == 1 and ledger.get(pid)["review_raised"] is True
    # mens sleept wacht→actief (review afgewezen); forceer een verse dag zodat _execute_checklist echt draait
    ledger.start(pid)                                       # blocked → running, blocked_on gewist
    ledger.get(pid)["last_tended"] = ""; ledger._save()
    inh._claim_run_complete(pid)
    p = ledger.get(pid)
    assert len(review_evt) == 1                             # geen tweede awaiting_review
    assert p["status"] == "running" and p.get("outcome") in (None, "")   # blijft actief, geen outcome
    # pas een checklist-mutatie (uitvinken) wist de vlag → volgende all-done mag opnieuw reviewen
    cl = inh._project_checklist(p)
    ledger.check_toggle(pid, cl["id"], cl["items"][0]["id"])   # uitvinken → review_raised gewist
    assert ledger.get(pid).get("review_raised") in (None, False)


# 3b. Mens sleept wacht→done → board-watch vuurt project_completed MÉT deliverable_ids (#10-fix)
def test_3b_mens_done_via_board_watch(tmp_path):
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
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
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    ledger.start(pid)                                       # actief (running), blocked_on leeg
    ledger.complete(pid, "handmatig afgerond")             # mens sleept Actief→Done (geen review-marker)
    bus = EventBus(name="test"); got = []
    bus.subscribe("project_completed", lambda e: got.append(e.data))
    stub = SimpleNamespace(context=SimpleNamespace(projects=ledger, deliverables=None, _autonomous_done=set()),
                           bus=bus, _activated_seen=set(), _completed_seen=set())
    Village._poll_board(stub)
    assert len(got) == 1 and got[0]["project_id"] == pid
    assert got[0]["route"] == "direct" and got[0]["deliverable_ids"] == []   # geen gate, geen deliverables


# 3c. DONE→ACTIEF (reopen) met volle checklist → GEEN vals project_completed (bekende bug, nu opgelost)
def test_3c_reopen_geen_vals_completed(tmp_path):
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    inh = _inhabitant(tmp_path, ledger)
    done_evt = _capture(inh, "project_completed")
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    _prep(ledger, pid, [("studie", "openalex_evidence", "x")])
    inh._claim_run_complete(pid)                            # → WACHT, review_raised gezet
    ledger.complete(pid, "checklist voltooid (1/1) — goedgekeurd na review")   # mens: Done
    ledger.reopen(pid)                                      # DONE→ACTIEF: outcome gewist, checklist nog vol
    ledger.get(pid)["last_tended"] = ""; ledger._save()    # forceer dat de puls echt draait
    inh._claim_run_complete(pid)                            # de dagpuls
    p = ledger.get(pid)
    assert p["status"] == "running"                        # blijft ACTIEF, geen re-complete
    assert done_evt == []                                  # GEEN vals project_completed (bug opgelost)


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


# 6. Bulletin bevat de 'wacht op review'-regel (naast 'rondde af'), scope uit de ledger
def test_6_bulletin_toont_wacht_op_review(tmp_path):
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    pid = ledger.create("harry_hemp", "Onderzoek naar barefoot shoes", "human", status="future")
    noochie = _make_noochie(tmp_path, ledger)
    noochie._events_today = [{"name": "project_awaiting_review", "by": "harry_hemp",
                              "note": "", "project_id": pid}]
    with patch("nooch_village.llm.reason", return_value=_MOCK_BULLETIN) as mock:
        noochie._on_dag_eindigt(Event("dag_eindigt", {}, "test"))
    prompt = mock.call_args[0][0]
    assert "wacht op review: Onderzoek naar barefoot shoes" in prompt
