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
    assert any("already has a similar accountability" in i["msg"] for i in issues)


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






