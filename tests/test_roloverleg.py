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


def test_tension_validity_from_your_role():
    from nooch_village.roloverleg import tension_validity
    # rol stelt voor een ÁNDERE rol te wijzigen zonder baat voor de eigen rol → ongeldig
    cross = {"by": "analyst", "role_id": "scout", "benefit": ""}
    ok, why = tension_validity(cross)
    assert ok is False and "eigen rol" in why
    # mét baat → geldig (deterministisch, geen LLM)
    assert tension_validity({**cross, "benefit": "anders blijf ik op data wachten"})[0] is True
    # eigen rol → altijd geldig; Circle Lead/procesrol vrijgesteld
    assert tension_validity({"by": "scout", "role_id": "scout", "benefit": ""})[0] is True
    assert tension_validity({"by": "founder", "role_id": "scout", "benefit": ""})[0] is True
    # LLM mag een 'algemeen belang'-baat alsnog afkeuren
    ok2, _ = tension_validity({**cross, "benefit": "goed voor het dorp"},
                             llm_reason=lambda p: "NEE")
    assert ok2 is False


def test_rov_invalid_verwijdert_ongeldige_spanning_zonder_governance(tmp_path):
    from nooch_village import cockpit
    from nooch_village.roloverleg import Agenda
    data = tmp_path / "data"; data.mkdir()
    (data / "governance_records.json").write_text("{}", encoding="utf-8")
    ag = Agenda(str(data / "roloverleg_agenda.json"))
    iid = ag.add("scout", "amend_role", {"add_accountabilities": ["Bewaken van X"]},
                 "x", by="analyst", title="X")            # cross-rol, geen benefit → ongeldig
    res = cockpit._dispatch_action(str(data), "rov_invalid", iid, "", extra={})
    assert res["ok"] and res["rov"] == "invalid"
    assert Agenda(str(data / "roloverleg_agenda.json")).open() == []
    # een geldige spanning kan NIET zo verwijderd worden
    iid2 = ag.add("scout", "amend_role", {"add_accountabilities": ["Y-en"]}, "y", by="scout", title="Y")
    res2 = cockpit._dispatch_action(str(data), "rov_invalid", iid2, "", extra={})
    assert res2["ok"] is False


def test_build_change_from_fields_amend_diff():
    from nooch_village.roloverleg import build_change_from_fields
    item = {"kind": "amend_role", "role_id": "scout", "title": "scout", "change": {}}
    snap = {"purpose": "markt observeren", "accountabilities": ["Volgen van de markt", "Oud werk"],
            "domains": ["socials"]}
    # purpose gewijzigd, één accountability herschreven (Oud werk → Nieuw werk), domein verwijderd
    change, rid, title = build_change_from_fields(
        item, snap, naam="scout", purpose="de markt vóór zijn",
        accs=["Volgen van de markt", "Nieuw werk"], domeinen=[])
    assert rid == "scout"
    assert change["purpose"] == "de markt vóór zijn"
    assert change["add_accountabilities"] == ["Nieuw werk"]
    assert change["remove_accountabilities"] == ["Oud werk"]
    assert change["remove_domains"] == ["socials"]


def test_rov_edit_werkt_voorstel_bij(tmp_path):
    from nooch_village import cockpit
    from nooch_village.roloverleg import Agenda
    import json
    data = tmp_path / "data"; data.mkdir()
    recs = {"scout": {"id": "scout", "type": "role", "parent": "noochville", "version": 1,
                      "definition": {"purpose": "p", "accountabilities": ["A", "B"], "domains": []}}}
    (data / "governance_records.json").write_text(json.dumps(recs), encoding="utf-8")
    ag = Agenda(str(data / "roloverleg_agenda.json"))
    iid = ag.add("scout", "amend_role", {"add_accountabilities": ["C"]}, "x", by="scout", title="C")
    res = cockpit._dispatch_action(str(data), "rov_edit", iid, "", extra={
        "ed_naam": "scout", "ed_purpose": "nieuwe purpose",
        "ed_accs": "A\nB\nC-herschreven", "ed_domeinen": "nieuw domein"})
    assert res["ok"] and res["rov"] == "edited"
    it = Agenda(str(data / "roloverleg_agenda.json")).get(iid)
    assert it["change"]["add_accountabilities"] == ["C-herschreven"]      # C verwijderd, herschreven erbij
    assert it["change"]["purpose"] == "nieuwe purpose"
    assert it["change"]["add_domains"] == ["nieuw domein"]


def test_rov_edit_hernoem_bestaande_rol(tmp_path):
    from nooch_village import cockpit
    from nooch_village.roloverleg import Agenda
    import json
    data = tmp_path / "data"; data.mkdir()
    recs = {"scout": {"id": "scout", "type": "role", "parent": "noochville", "version": 1,
                      "definition": {"purpose": "p", "accountabilities": ["A"], "domains": []}}}
    (data / "governance_records.json").write_text(json.dumps(recs), encoding="utf-8")
    ag = Agenda(str(data / "roloverleg_agenda.json"))
    iid = ag.add("scout", "amend_role", {"add_accountabilities": ["A"]}, "x", by="scout", title="scout")
    res = cockpit._dispatch_action(str(data), "rov_edit", iid, "", extra={
        "ed_naam": "Marktverkenner", "ed_purpose": "p", "ed_accs": "A", "ed_domeinen": ""})
    assert res["ok"]
    it = Agenda(str(data / "roloverleg_agenda.json")).get(iid)
    assert it["change"]["rename"] == "Marktverkenner" and it["title"] == "Marktverkenner"
    assert it["role_id"] == "scout"                                    # id blijft stabiel


def test_rename_doorgevoerd_in_adopt(tmp_path):
    from nooch_village.governance import proposal_from_dict, proposal_to_dict
    from nooch_village.models import Proposal, GovernanceChange, ChangeKind
    p = Proposal(proposer_role="founder",
                 change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id="scout",
                                         rename="Marktverkenner"),
                 tension="t", trigger_example="t", rationale="r")
    d = proposal_to_dict(p)
    assert d["change"]["rename"] == "Marktverkenner"
    assert proposal_from_dict(d).change.rename == "Marktverkenner"       # roundtrip


def test_rov_edit_nieuwe_rol_naam_bewerkbaar(tmp_path):
    from nooch_village import cockpit
    from nooch_village.roloverleg import Agenda
    data = tmp_path / "data"; data.mkdir()
    (data / "governance_records.json").write_text("{}", encoding="utf-8")
    ag = Agenda(str(data / "roloverleg_agenda.json"))
    iid = ag.add("oude_naam", "add_role",
                 {"purpose": "p", "add_accountabilities": ["x"], "new_role_parent": "noochville"},
                 "x", by="founder", title="Oude naam")
    res = cockpit._dispatch_action(str(data), "rov_edit", iid, "", extra={
        "ed_naam": "Copywriter", "ed_purpose": "laat de missie resoneren",
        "ed_accs": "Schrijven van copy", "ed_domeinen": ""})
    assert res["ok"]
    it = Agenda(str(data / "roloverleg_agenda.json")).get(iid)
    assert it["role_id"] == "copywriter" and it["title"] == "Copywriter"
    assert it["change"]["purpose"] == "laat de missie resoneren"
    assert it["change"]["add_accountabilities"] == ["Schrijven van copy"]


def test_render_roloverleg_met_string_roles():
    # Regressie: de live cockpit geeft `roles` als lijst STRINGS door; de render mag daar niet op
    # crashen (eerder: AttributeError op r.get in het groep-blok → lege respons).
    from nooch_village import cockpit
    it = {"id": "a", "role_id": "scout", "kind": "amend_role",
          "change": {"add_accountabilities": ["Bewaken van X"]}, "reason": "r", "by": "scout",
          "title": "Scout", "status": "open", "reactions": []}
    snap = {"purpose": "p", "name": "scout", "accountabilities": ["A"], "domains": []}
    page = cockpit.render_roloverleg(it, snap, [], "t", group_members=[it],
                                     roles=["scout", "librarian", "analyst"])
    assert "Beslis" in page and "Rol bewerken" in page and "librarian" in page


def test_meerdere_rollen_per_voorstel(tmp_path):
    from nooch_village import cockpit
    from nooch_village.roloverleg import Agenda
    data = tmp_path / "data"; data.mkdir()
    (data / "governance_records.json").write_text("{}", encoding="utf-8")
    ag = Agenda(str(data / "roloverleg_agenda.json"))
    iid = ag.add("scout", "amend_role", {"add_accountabilities": ["X"]}, "spanning",
                 by="scout", title="Scout")
    gid = ag.group_of(iid)
    # bestaande rol toevoegen aan het voorstel
    r1 = cockpit._dispatch_action(str(data), "rov_group_add", "", "", extra={
        "group": gid, "g_owner": "librarian"})
    # nieuwe rol toevoegen aan het voorstel
    r2 = cockpit._dispatch_action(str(data), "rov_group_add", "", "", extra={
        "group": gid, "g_owner": "__new__", "g_naam": "Copywriter"})
    assert r1["ok"] and r2["ok"]
    ag2 = Agenda(str(data / "roloverleg_agenda.json"))
    members = ag2.members_of_group(gid)
    assert len(members) == 3
    assert {m["role_id"] for m in members} == {"scout", "librarian", "copywriter"}
    assert all((m.get("group") or m["id"]) == gid for m in members)
    # hele voorstel in één keer aannemen
    res = cockpit._dispatch_action(str(data), "rov_group_consent", "", "", extra={"group": gid})
    assert res["ok"] and res["n"] == 3
    ag3 = Agenda(str(data / "roloverleg_agenda.json"))
    assert all(m["status"] == "consented" for m in ag3.members_of_group(gid))


def test_rol_verwijderen_voorstel(tmp_path):
    from nooch_village import cockpit
    from nooch_village.roloverleg import Agenda, _proposal_from_item
    from nooch_village.models import ChangeKind
    import json
    data = tmp_path / "data"; data.mkdir()
    recs = {"noochville": {"id": "noochville", "type": "circle", "parent": None, "version": 1,
                           "definition": {"purpose": "p"}, "members": ["scout"]},
            "scout": {"id": "scout", "type": "role", "parent": "noochville", "version": 1,
                      "definition": {"purpose": "p", "accountabilities": [], "domains": []}}}
    (data / "governance_records.json").write_text(json.dumps(recs), encoding="utf-8")
    ag = Agenda(str(data / "roloverleg_agenda.json"))
    iid = ag.add("scout", "amend_role", {"add_accountabilities": ["X"]}, "weg ermee",
                 by="founder", title="Scout")
    # omzetten naar verwijder-voorstel
    res = cockpit._dispatch_action(str(data), "rov_remove", iid, "", extra={})
    assert res["ok"] and res["rov"] == "to_remove"
    it = Agenda(str(data / "roloverleg_agenda.json")).get(iid)
    assert it["kind"] == "remove_role"
    # _proposal_from_item bouwt nu een echte REMOVE_ROLE (niet langer amend)
    assert _proposal_from_item(it).change.kind == ChangeKind.REMOVE_ROLE
    # terugdraaien kan
    cockpit._dispatch_action(str(data), "rov_keep_role", iid, "", extra={})
    assert Agenda(str(data / "roloverleg_agenda.json")).get(iid)["kind"] == "amend_role"
    # een NIEUWE-rol-voorstel verwijderen = gewoon van de agenda
    iid2 = ag.add("nieuw", "add_role", {"purpose": "p", "add_accountabilities": ["Y"],
                  "new_role_parent": "noochville"}, "x", by="founder", title="Nieuw")
    r2 = cockpit._dispatch_action(str(data), "rov_remove", iid2, "", extra={})
    assert r2["rov"] == "removed_draft"
    assert Agenda(str(data / "roloverleg_agenda.json")).get(iid2) is None


def test_evaluate_objection_proces():
    from nooch_village.roloverleg import evaluate_objection
    # alle 'left' → geldig bezwaar
    geldig = evaluate_objection({"q1": "left", "q2": "left", "q3": "left", "q4": "left"},
                                harm="mijn rol kan haar doel niet meer uitdrukken")
    assert geldig["valid"] is True and geldig["harm"].startswith("mijn rol")
    assert [s["label"] for s in geldig["steps"]] == ["Schade", "Door dit voorstel",
                                                     "Zeker, niet speculatief", "Beperkt jouw rol"]
    # q1 rechts (alleen 'onnodig') → geen geldig bezwaar
    assert evaluate_objection({"q1": "right", "q2": "left", "q3": "left", "q4": "left"})["valid"] is False
    # anticiperen (q3 rechts) + veilig om te proberen (q3b rechts) → ongeldig; q3b komt in de stappen
    r = evaluate_objection({"q1": "left", "q2": "left", "q3": "right", "q3b": "right", "q4": "left"})
    assert r["valid"] is False and any(s["label"] == "Niet veilig om te proberen" for s in r["steps"])
    # anticiperen + aanzienlijke schade vóór bijsturen (q3b links) → wél geldig
    assert evaluate_objection({"q1": "left", "q2": "left", "q3": "right", "q3b": "left",
                               "q4": "left"})["valid"] is True
    # niets beantwoord → ongeldig
    assert evaluate_objection({})["valid"] is False


def test_rov_object_proces_zet_status(tmp_path):
    from nooch_village import cockpit
    from nooch_village.roloverleg import Agenda
    data = tmp_path / "data"; data.mkdir()
    (data / "governance_records.json").write_text("{}", encoding="utf-8")
    ag = Agenda(str(data / "roloverleg_agenda.json"))
    iid = ag.add("scout", "amend_role", {"add_accountabilities": ["Bewaken van X"]}, "x",
                 by="scout", title="X")
    # niets beantwoord → geweigerd
    assert cockpit._dispatch_action(str(data), "rov_object", iid, "", extra={})["ok"] is False
    # geen geldig bezwaar (q1 rechts) → terug naar open
    res = cockpit._dispatch_action(str(data), "rov_object", iid, "", extra={
        "q1": "right", "q2": "left", "q3": "left", "q4": "left"})
    assert res["rov"] == "obj_invalid"
    assert Agenda(str(data / "roloverleg_agenda.json")).get(iid)["status"] == "open"
    # geldig bezwaar (alles links) → voorstel gaat van de agenda
    res2 = cockpit._dispatch_action(str(data), "rov_object", iid, "", extra={
        "q1": "left", "q2": "left", "q3": "left", "q4": "left", "harm": "beperkt mijn rol"})
    assert res2["rov"] == "obj_valid"
    assert Agenda(str(data / "roloverleg_agenda.json")).get(iid) is None      # weg van de agenda


def test_auto_stollen_na_3x(tmp_path):
    from nooch_village.projects import ProjectLedger
    from nooch_village.roloverleg import Agenda, formalize_ripe_experiments
    led = ProjectLedger(str(tmp_path / "projects.json"))
    pid = led.create("scout", "Bewaken van sociale kanalen", "human", origin="experiment")
    ag = Agenda(str(tmp_path / "ag.json"))
    led.record_progress(pid, "ronde 1"); led.record_progress(pid, "ronde 2")
    assert formalize_ripe_experiments(led, ag) == 0          # nog maar 2x → niet rijp
    led.record_progress(pid, "ronde 3")
    assert led.get(pid)["executions"] == 3
    assert formalize_ripe_experiments(led, ag) == 1          # 3x → stolt
    it = ag.open()[0]
    assert it["role_id"] == "scout" and it["kind"] == "amend_role"
    assert it["change"]["add_accountabilities"] == ["Bewaken van sociale kanalen"]
    assert led.get(pid)["formalized"] is True
    assert formalize_ripe_experiments(led, ag) == 0          # dedup: niet nog eens


def test_work_projects_experiment_herwerkt_tot_drempel(tmp_path):
    from nooch_village.projects import ProjectLedger
    from nooch_village.roloverleg import Agenda
    from nooch_village.project_worker import work_projects
    led = ProjectLedger(str(tmp_path / "projects.json"))
    pid = led.create("scout", "Volgen van trends", "human", origin="experiment")
    ag = Agenda(str(tmp_path / "ag.json"))
    out = None
    for _ in range(4):                                        # vier pulsen
        out = work_projects(led, llm_reason=lambda p: "LEVER: gedaan", agenda=ag)
    assert led.get(pid)["executions"] == 3                   # gestopt op de drempel
    assert ag.open() and ag.open()[0]["change"]["add_accountabilities"] == ["Volgen van trends"]


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
    # overzicht: open item zichtbaar + 'zelf toevoegen' altijd
    ov = cockpit.render_roloverleg_overview([item], [item], ["scout", "librarian"], "t")
    assert "Roloverleg" in ov
    assert "/roloverleg?iid=k1" in ov and 'value="rov_add"' in ov
    # de 'Einde roloverleg'-knop verschijnt zodra er een AANGENOMEN (consented) voorstel is —
    # ook als er geen open items meer zijn (de bug: anders bleef het hangen).
    consented = {**item, "status": "consented"}
    ov2 = cockpit.render_roloverleg_overview([], [consented], ["scout"], "t")
    assert 'value="rov_end"' in ov2 and "Aangenomen" in ov2 and "/roloverleg?iid=k1" in ov2
