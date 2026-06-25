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


def test_secretary_check_dubbel_in_dezelfde_rol(tmp_path):
    """De Secretaris ziet ook een accountability die de rol AL (vergelijkbaar) heeft —
    Gate's G2 slaat de eigen rol over, dus die check zit hier."""
    recs = _records(tmp_path)               # scout heeft 'Volgen van de markt'
    item = {"id": "x", "role_id": "scout", "kind": "amend_role",
            "change": {"add_accountabilities": ["Volgen van de markt en trends"]},
            "reason": "t", "by": "founder", "title": "t"}
    issues = secretary_check(item, recs)
    assert any("heeft al een vergelijkbare accountability" in i["msg"] for i in issues)


def test_amend_with_reaction_hele_rol_diff_en_failclosed():
    item = {"id": "x", "role_id": "scout", "kind": "amend_role",
            "change": {"add_accountabilities": ["Bijhouden van social media"]},
            "reason": "t", "title": "t"}
    snap = {"purpose": "markt observeren", "accountabilities": ["Volgen van de markt"], "domains": []}
    rev = ("PURPOSE: markt observeren\nACCOUNTABILITIES:\n"
           "- Bewaken van alle online kanalen\n- Analyseren van trends\nDOMEIN: -")
    out = amend_with_reaction(item, "maak het breder, haal 'volgen van de markt' weg",
                              role_snapshot=snap, llm_reason=lambda p: rev)
    # desired vervangt de hele set: nieuwe accountabilities erbij, de oude eruit (echte diff)
    assert "Bewaken van alle online kanalen" in out["add_accountabilities"]
    assert "Volgen van de markt" in out["remove_accountabilities"]
    # geen reactie / geen LLM → ongemoeid
    assert amend_with_reaction(item, "", llm_reason=lambda p: "x") == item["change"]
    assert amend_with_reaction(item, "breder", role_snapshot=snap, llm_reason=lambda p: None) \
        == item["change"]


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


def test_suggest_accountabilities():
    from nooch_village.inbox_actions import suggest_accountabilities
    out = suggest_accountabilities("Copywriter", "Schrijven van copy", llm_reason=lambda p:
                                   "Schrijven van blogcopy\n- Bewaken van de tone of voice\n3) Redigeren van teksten")
    assert out == ["Schrijven van blogcopy", "Bewaken van de tone of voice", "Redigeren van teksten"]
    assert suggest_accountabilities("x", "y", llm_reason=lambda p: None) == []


def test_rov_add_nieuwe_rol_met_alle_velden(tmp_path):
    from nooch_village import cockpit
    from nooch_village.roloverleg import Agenda
    data = tmp_path / "data"; data.mkdir()
    (data / "governance_records.json").write_text("{}", encoding="utf-8")
    res = cockpit._dispatch_action(str(data), "rov_add", "", "we hebben copy nodig", extra={
        "owner": "__new__", "rolnaam": "Copywriter",
        "purpose": "Het laten resoneren van de missie in woorden",
        "domein": "de blog", "accs": "Schrijven van blogcopy\nBewaken van de tone of voice"})
    assert res["ok"] and res["rov"] == "added"
    it = Agenda(str(data / "roloverleg_agenda.json")).open()[0]
    assert it["kind"] == "add_role" and it["change"]["purpose"].startswith("Het laten")
    assert it["change"]["add_accountabilities"] == ["Schrijven van blogcopy", "Bewaken van de tone of voice"]
    assert it["change"]["add_domains"] == ["de blog"]


def test_voorstel_draagt_spanning_en_voorbeeld(tmp_path):
    from nooch_village import cockpit
    from nooch_village.roloverleg import Agenda
    data = tmp_path / "data"; data.mkdir()
    (data / "governance_records.json").write_text("{}", encoding="utf-8")
    cockpit._dispatch_action(str(data), "rov_add", "", "social blijft liggen", extra={
        "owner": "scout", "accs": "Bewaken van sociale kanalen",
        "voorbeeld": "vorige maand 3 weken stil op TikTok"})
    it = Agenda(str(data / "roloverleg_agenda.json")).open()[0]
    assert it["reason"] == "social blijft liggen"
    assert it["example"] == "vorige maand 3 weken stil op TikTok"
    page = cockpit.render_roloverleg(it, {"purpose": "p", "accountabilities": [], "domains": []}, [], "t")
    assert "Lost deze spanning op" in page and "Concreet voorbeeld" in page
    assert "3 weken stil op TikTok" in page


def test_roloverleg_diff_huidig_vs_na(tmp_path):
    from nooch_village import cockpit
    item = {"id": "k1", "role_id": "scout", "kind": "amend_role",
            "change": {"add_accountabilities": ["Bewaken van sociale kanalen"]},
            "reason": "bereik", "by": "scout", "title": "Social", "status": "open", "reactions": []}
    snap = {"purpose": "markt observeren", "accountabilities": ["Volgen van de markt"], "domains": []}
    page = cockpit.render_roloverleg(item, snap, [], "t")
    assert "Huidige rol" in page and "Na dit voorstel" in page
    assert "Volgen van de markt" in page and "✚ Bewaken van sociale kanalen" in page


def test_rov_to_project_maakt_experiment_en_haalt_van_agenda(tmp_path):
    from nooch_village import cockpit
    from nooch_village.roloverleg import Agenda
    from nooch_village.projects import ProjectLedger
    data = tmp_path / "data"; data.mkdir()
    (data / "governance_records.json").write_text("{}", encoding="utf-8")
    ag = Agenda(str(data / "roloverleg_agenda.json"))
    iid = ag.add("scout", "amend_role", {"add_accountabilities": ["Bewaken van sociale kanalen"]},
                 "bereik", title="Social")
    res = cockpit._dispatch_action(str(data), "rov_to_project", iid, "", extra={})
    assert res["ok"] and res["rov"] == "to_project"
    assert Agenda(str(data / "roloverleg_agenda.json")).open() == []   # van de agenda af (van schijf)
    ps = ProjectLedger(str(data / "projects.json")).all()
    assert len(ps) == 1 and ps[0]["owner"] == "scout" and ps[0]["status"] == "queued"
    assert "Bewaken van sociale kanalen" in str(ps[0]["scope"])


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
