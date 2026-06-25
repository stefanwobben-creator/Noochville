"""Mens-poort voor kansen: een door een rol gesensde kans landt als beslissing in de inbox en
wordt PAS een project als de mens 'm goedkeurt. Negeren sluit 'm. Niets wordt autonoom gequeued."""
from __future__ import annotations

from nooch_village.human_inbox import HumanInbox
from nooch_village.projects import ProjectLedger
from nooch_village.inbox_actions import decide_opportunity
from nooch_village.business_case import make_business_case


def _setup(tmp_path):
    inbox = HumanInbox(str(tmp_path / "human_inbox.json"))
    projects = ProjectLedger(str(tmp_path / "projects.json"))
    iid = inbox.add_opportunity("Reviews oogsten op de PDP", by="analyst", kind="project",
                                wat="We tonen reviews op de productpagina.",
                                waarom="sociaal bewijs → conversie",
                                business_case=make_business_case(effect=80, effort=2, confidence=0.7))
    return inbox, projects, iid


def test_kans_in_inbox_pending(tmp_path):
    inbox, _projects, iid = _setup(tmp_path)
    item = inbox.get(iid)
    assert item["type"] == "opportunity" and item["status"] == "pending"
    # dedup op titel
    iid2 = inbox.add_opportunity("Reviews oogsten op de PDP")
    assert iid2 == iid


def test_add_maakt_project_houdt_item_open(tmp_path):
    inbox, projects, iid = _setup(tmp_path)
    res = decide_opportunity(inbox, iid, "add", destination="project",
                             owner="website_watcher", projects=projects)
    assert res["ok"] and res["status"] == "added" and res["owner"] == "website_watcher"
    ps = projects.all()
    assert len(ps) == 1 and ps[0]["owner"] == "website_watcher"
    assert inbox.get(iid)["status"] == "pending"           # item BLIJFT open


def test_meerdere_uitkomsten_op_een_kans(tmp_path):
    from nooch_village.notes_store import NotesStore
    inbox, projects, iid = _setup(tmp_path)
    notes = NotesStore(str(tmp_path / "notes.json"))
    # twee projecten (verschillende rollen) + een kennis-kaart, dan afronden
    decide_opportunity(inbox, iid, "add", destination="project", owner="scout", projects=projects)
    decide_opportunity(inbox, iid, "add", destination="project", owner="librarian", projects=projects)
    decide_opportunity(inbox, iid, "add", destination="knowledge", notes=notes)
    assert len(projects.all()) == 2 and len(notes.all()) == 1
    assert inbox.get(iid)["status"] == "pending"           # nog open
    decide_opportunity(inbox, iid, "done")
    assert inbox.get(iid)["status"] == "approved"          # nu gesloten


def test_reject_onthoudt_constraint(tmp_path):
    from nooch_village.constraints import Constraints
    inbox, projects, iid = _setup(tmp_path)
    cons = Constraints(str(tmp_path / "constraints.json"))
    res = decide_opportunity(inbox, iid, "reject", reason="we bieden geen kinderschoenen",
                             remember_constraint=True, constraints=cons)
    assert res["ok"] and res["status"] == "rejected" and res["constraint_learned"]
    assert "geen kinderschoenen" in cons.texts()[0]
    assert projects.all() == []


def test_approve_naar_governance_nieuwe_rol(tmp_path):
    from nooch_village.governance import Records
    from nooch_village.models import Record, RoleDefinition, RecordType
    inbox, projects, iid = _setup(tmp_path)
    recs = Records(str(tmp_path / "gov.json"))
    recs.put(Record(id="noochville", type=RecordType.CIRCLE, parent=None,
                    definition=RoleDefinition(purpose="Nooch", policies=[]), source="seed"))
    res = decide_opportunity(inbox, iid, "add", destination="governance",
                             owner="__new__", records=recs)
    assert res["ok"] and res["destination"] == "governance"
    assert res["gov_status"] == "adopted"
    # er is een nieuw (onbemand) rol-record bijgekomen
    assert any(r.id != "noochville" for r in recs.all())


def test_approve_naar_governance_rol_uitbreiden(tmp_path):
    from nooch_village.governance import Records
    from nooch_village.models import Record, RoleDefinition, RecordType
    inbox, projects, iid = _setup(tmp_path)
    recs = Records(str(tmp_path / "gov.json"))
    recs.put(Record(id="noochville", type=RecordType.CIRCLE, parent=None,
                    definition=RoleDefinition(purpose="Nooch", policies=[]), source="seed"))
    recs.put(Record(id="scout", type=RecordType.ROLE, parent="noochville",
                    definition=RoleDefinition(purpose="markt observeren", accountabilities=[]),
                    source="seed"))
    res = decide_opportunity(inbox, iid, "add", destination="governance",
                             owner="scout", records=recs)
    assert res["ok"] and res["gov_status"] in ("adopted", "escalated")


def test_na_afronden_geen_actie_meer(tmp_path):
    inbox, projects, iid = _setup(tmp_path)
    decide_opportunity(inbox, iid, "done")
    again = decide_opportunity(inbox, iid, "add", destination="project", projects=projects)
    assert again["ok"] is False                            # gesloten item: geen actie meer
