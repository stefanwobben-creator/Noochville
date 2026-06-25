"""Roloverleg (IDM): voorstellen op de agenda, Secretaris-check (Gate + -en-formulering), AI past
aan op reactie, consent → doorvoeren bij einde, schadelijk → blijft staan. Triage agendeert."""
from __future__ import annotations

from nooch_village.roloverleg import (
    Agenda, secretary_check, amend_with_reaction, apply_consented, _proposal_from_item)
from nooch_village.governance import Records
from nooch_village.models import Record, RoleDefinition, RecordType


def _records(tmp_path):
    r = Records(str(tmp_path / "gov.json"))
    r.put(Record(id="noochville", type=RecordType.CIRCLE, parent=None,
                 definition=RoleDefinition(purpose="Nooch", policies=[]), source="seed"))
    r.put(Record(id="scout", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="markt observeren",
                                           accountabilities=["Volgen van de markt"]), source="seed"))
    return r


def test_agenda_add_dedup_en_status(tmp_path):
    a = Agenda(str(tmp_path / "ag.json"))
    iid = a.add("scout", "amend_role", {"add_accountabilities": ["Bewaken van sociale media"]},
                "meer bereik", by="founder", title="Social media")
    iid2 = a.add("scout", "amend_role", {"add_accountabilities": ["Bewaken van sociale media"]},
                 "x", title="Social media")
    assert iid2 == iid                                       # dedup
    assert len(a.open()) == 1
    a.set_status(iid, "consented")
    assert a.get(iid)["status"] == "consented"
    # herladen vanaf schijf
    assert Agenda(str(tmp_path / "ag.json")).get(iid)["status"] == "consented"


def test_secretary_check_dubbel_en_en_vorm(tmp_path):
    recs = _records(tmp_path)
    # dubbele accountability (botst met scout's 'Volgen van de markt') + niet-en-vorm
    item = {"id": "x", "role_id": "librarian", "kind": "amend_role",
            "change": {"add_accountabilities": ["Volgen van de markt"]},
            "reason": "test", "by": "founder", "title": "t"}
    issues = secretary_check(item, recs)
    assert any(i["level"] == "blok" for i in issues)         # G2-duplicaat
    item2 = {"id": "y", "role_id": "scout", "kind": "amend_role",
             "change": {"add_accountabilities": ["sociale media bijhouden"]},
             "reason": "t", "by": "founder", "title": "t"}
    issues2 = secretary_check(item2, recs)
    assert any(i["level"] == "let op" for i in issues2)      # niet in -en-vorm


def test_amend_with_reaction_en_failclosed(tmp_path):
    item = {"id": "x", "role_id": "scout", "kind": "amend_role",
            "change": {"add_accountabilities": ["Bijhouden van social media"]},
            "reason": "t", "title": "t"}
    out = amend_with_reaction(item, "maak het breder",
                              llm_reason=lambda p: "Bewaken van alle online kanalen van Nooch")
    assert out["add_accountabilities"][0] == "Bewaken van alle online kanalen van Nooch"
    # geen reactie of geen LLM → ongemoeid
    assert amend_with_reaction(item, "", llm_reason=lambda p: "x")["add_accountabilities"][0] \
        == "Bijhouden van social media"
    assert amend_with_reaction(item, "breder", llm_reason=lambda p: None)["add_accountabilities"][0] \
        == "Bijhouden van social media"


def test_apply_consented_adopt_en_objected_blijft(tmp_path):
    recs = _records(tmp_path)
    a = Agenda(str(tmp_path / "ag.json"))
    ok_id = a.add("scout", "amend_role", {"add_accountabilities": ["Bewaken van sociale kanalen"]},
                  "bereik", title="Social")
    bad_id = a.add("librarian", "amend_role", {"add_accountabilities": ["Volgen van de markt"]},
                   "botst", title="Dubbel")              # botst met scout → Gate blokkeert
    a.set_status(ok_id, "consented")
    a.set_status(bad_id, "consented")
    res = apply_consented(a, recs)
    by_status = {r["status"] for r in res}
    assert "adopted" in by_status and "escalated" in by_status
    assert "Bewaken van sociale kanalen" in recs.get("scout").definition.accountabilities
    assert a.get(ok_id) is None                              # geadopteerd → van de agenda
    assert a.get(bad_id)["status"] == "objected"            # geblokkeerd → blijft staan


def test_triage_governance_agendeert_ipv_adopt(tmp_path):
    from nooch_village.human_inbox import HumanInbox
    from nooch_village.inbox_actions import decide_opportunity
    recs = _records(tmp_path)
    inbox = HumanInbox(str(tmp_path / "inbox.json"))
    iid = inbox.add_opportunity("Social media bijhouden", by="scout", wat="posts plaatsen")
    a = Agenda(str(tmp_path / "ag.json"))
    res = decide_opportunity(inbox, iid, "add", destination="governance",
                             owner="scout", records=recs, agenda=a)
    assert res["gov_status"] == "agendeerd"
    assert len(a.open()) == 1                                # op de agenda, niet doorgevoerd
    assert "Social media bijhouden" not in str(recs.get("scout").definition.accountabilities)


def test_cockpit_render_roloverleg(tmp_path):
    from nooch_village import cockpit
    recs = _records(tmp_path)
    item = {"id": "k1", "role_id": "scout", "kind": "amend_role",
            "change": {"add_accountabilities": ["Bewaken van sociale kanalen"]},
            "reason": "meer bereik", "by": "scout", "title": "Social media", "status": "open",
            "reactions": []}
    snap = {"purpose": "markt observeren", "accountabilities": ["Volgen van de markt"], "domains": []}
    page = cockpit.render_roloverleg(item, snap, [], "t")
    assert "Voorstel behandelen" in page and "Social media" in page
    assert "Volgen van de markt" in page                      # huidige rol
    assert "Bewaken van sociale kanalen" in page              # voorgestelde wijziging
    assert "Secretaris" in page
    for val in ("rov_react", "rov_consent", "rov_object"):
        assert f'value="{val}"' in page
    # overzicht
    ov = cockpit.render_roloverleg_overview([item], [item], ["scout", "librarian"], "t")
    assert "Roloverleg" in ov
    assert "/roloverleg?iid=k1" in ov and 'value="rov_end"' in ov and 'value="rov_add"' in ov
