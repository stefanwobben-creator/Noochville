"""PoC-datamodel: people, assignments (multi-fill, hybride), attachments, org-boom, importer."""
from __future__ import annotations

from nooch_village.people import PeopleStore
from nooch_village.assignments import Assignments
from nooch_village.attachments import AttachmentStore
from nooch_village import org
from nooch_village.models import Record, RecordType, RoleDefinition
from nooch_village.glassfrog_import import import_org, nooch_poc_org
from nooch_village.governance import Records


# ── people ──
def test_people_dedup_en_lookup(tmp_path):
    ps = PeopleStore(str(tmp_path / "people.json"))
    a = ps.add("Lotte Mulder")
    b = ps.add("lotte mulder")                      # zelfde naam (case-insensitief) → zelfde mens
    assert a.id == b.id
    assert ps.by_name("Lotte Mulder").id == a.id
    ps.update(a.id, email="lotte@nooch.earth")
    assert PeopleStore(str(tmp_path / "people.json")).get(a.id).email == "lotte@nooch.earth"


# ── assignments ──
def test_assignments_multifill_en_hybride(tmp_path):
    asg = Assignments(str(tmp_path / "assign.json"))
    asg.assign("website_developer", "person", "p_stefan")
    asg.assign("website_developer", "person", "p_dan")
    asg.assign("website_developer", "person", "p_dan")     # idempotent
    fillers = asg.fillers_of("website_developer")
    assert len(fillers) == 2
    # hybride: ook een AI-inwoner kan een rol vervullen
    asg.assign("scout", "persona", "persona_noochie")
    assert asg.fillers_of("scout")[0].type == "persona"
    # een mens vervult meerdere rollen
    asg.assign("marketing_lead", "person", "p_stefan")
    assert set(asg.roles_of("person", "p_stefan")) == {"website_developer", "marketing_lead"}


def test_fillers_of_voegt_legacy_samen(tmp_path):
    asg = Assignments(str(tmp_path / "assign.json"))
    asg.assign("r1", "person", "p_new")
    rec = Record(id="r1", type=RecordType.ROLE, parent="c1",
                 definition=RoleDefinition(purpose="x"), held_by="p_legacy", persona_id="persona_x")
    types = {(f.type, f.id) for f in asg.fillers_of("r1", record=rec)}
    assert ("person", "p_new") in types and ("person", "p_legacy") in types
    assert ("persona", "persona_x") in types


# ── attachments ──
def test_attachments_generiek(tmp_path):
    st = AttachmentStore(str(tmp_path / "att.json"))
    n = st.add("scout", "note", title="Veja", body="lanceert nieuwe sneaker")
    st.add("scout", "metric", title="vegan sneakers", meta={"value": "210", "unit": "zoekvolume"})
    assert st.add("scout", "onzin") is None             # ongeldige soort
    assert len(st.list("scout")) == 2
    assert len(st.list("scout", "note")) == 1
    assert st.counts("scout")["metric"] == 1
    st.update(n.id, body="geüpdatet")
    assert st.get(n.id).body == "geüpdatet"
    assert st.remove(n.id) and st.counts("scout")["note"] == 0


# ── org-boom ──
def _rec(rid, typ, parent):
    return Record(id=rid, type=typ, parent=parent, definition=RoleDefinition(purpose=""))


def test_org_boom_nesting():
    recs = [
        _rec("me", RecordType.CIRCLE, None),
        _rec("me__shareholder", RecordType.ROLE, "me"),
        _rec("me__nooch", RecordType.CIRCLE, "me"),
        _rec("me__nooch__website", RecordType.ROLE, "me__nooch"),
        _rec("me__nooch__marketing", RecordType.ROLE, "me__nooch"),
    ]
    assert [r.id for r in org.roots(recs)] == ["me"]
    assert {r.id for r in org.subcircles_of(recs, "me")} == {"me__nooch"}
    assert {r.id for r in org.roles_of(recs, "me")} == {"me__shareholder"}
    assert {r.id for r in org.roles_of(recs, "me__nooch")} == {"me__nooch__website", "me__nooch__marketing"}
    assert len(org.descendants(recs, "me")) == 4
    assert org.breadcrumb(recs, "me__nooch__website") == ["me", "me__nooch", "me__nooch__website"]


# ── importer: de echte Nooch-structuur ──
def test_import_nooch_org(tmp_path):
    recs = Records(str(tmp_path / "governance_records.json"))
    ppl = PeopleStore(str(tmp_path / "people.json"))
    asg = Assignments(str(tmp_path / "assign.json"))
    summary = import_org(nooch_poc_org(), recs, ppl, asg)

    assert summary["circles"] == 2 and summary["roles"] == 20
    # 6 mensen: Lotte, Stefan, Nina, Matthijs, Wytse, Dan
    assert summary["people"] == 6
    # nesting: Mother Earth is wortel, Nooch hangt eronder
    me = recs.get("mother_earth")
    nooch = recs.get("mother_earth__nooch")
    assert me is not None and me.parent is None and me.type == RecordType.CIRCLE
    assert nooch is not None and nooch.parent == "mother_earth" and nooch.type == RecordType.CIRCLE
    # subcirkel zit in members van de wortel
    assert "mother_earth__nooch" in me.members
    # Website Developer heeft twee mensen (Stefan + Dan) en domein nooch.earth
    wd = recs.get("mother_earth__nooch__website_developer")
    assert wd is not None and wd.definition.domains == ["Nooch.earth"]
    assert len(asg.fillers_of(wd.id)) == 2
    # Lotte vervult meerdere rollen
    lotte = ppl.by_name("Lotte Mulder")
    assert len(asg.roles_of("person", lotte.id)) >= 4
