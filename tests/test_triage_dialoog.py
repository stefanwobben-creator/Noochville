"""Holacracy-triage: vraag-aan-rol dialoog-lus (parkeren + gebundeld beantwoorden in de puls),
AI die governance-doelwit kiest (nieuw vs. uitbreiden) en een project Holacracy-formuleert,
plus de scroll-fix (rij-anchor) in de cockpit-render."""
from __future__ import annotations

from nooch_village.human_inbox import HumanInbox
from nooch_village.inbox_actions import (
    ask_role, answer_pending_questions, pick_governance_target, formulate_project)
from nooch_village.business_case import make_business_case


def _inbox(tmp_path):
    inbox = HumanInbox(str(tmp_path / "human_inbox.json"))
    iid = inbox.add_opportunity("Reviews op de productpagina", by="analyst", kind="project",
                                wat="Sterren en korte reviews tonen.",
                                waarom="sociaal bewijs",
                                business_case=make_business_case(effect=80, effort=2, confidence=0.7))
    return inbox, iid


def test_vraag_wordt_geparkeerd_geen_llm(tmp_path):
    inbox, iid = _inbox(tmp_path)
    res = ask_role(inbox, iid, "Ik snap dit voorstel niet, wat bedoel je precies?")
    assert res["ok"] and res["status"] == "waiting"
    item = inbox.get(iid)
    assert item["status"] == "pending"                       # item blijft open
    dlg = item["context"]["dialogue"]
    assert len(dlg) == 1 and dlg[0]["answered"] is False
    assert inbox.pending_questions()[0]["iid"] == iid


def test_lege_vraag_wordt_geweigerd(tmp_path):
    inbox, iid = _inbox(tmp_path)
    assert ask_role(inbox, iid, "   ")["ok"] is False


def test_gebundelde_beantwoording_vult_dialoog(tmp_path):
    inbox, iid = _inbox(tmp_path)
    ask_role(inbox, iid, "Wat bedoel je met sociaal bewijs?")
    iid2 = inbox.add_opportunity("Sokken van hennep", by="herman", wat="Hennep-sokken testen.")
    ask_role(inbox, iid2, "Is hennep wel bio-afbreekbaar?")

    def fake_llm(prompt):
        # twee vragen → twee antwoorden in het gevraagde formaat
        assert "VRAAG 1" in prompt and "VRAAG 2" in prompt
        return ("ANTWOORD 1: Sociaal bewijs betekent dat mensen eerder kopen als ze zien dat "
                "anderen blij zijn.\nANTWOORD 2: Pure hennep wel, maar let op het elastan.")

    res = answer_pending_questions(inbox, records=None, llm_reason=fake_llm)
    assert res["answered"] == 2 and res["pending"] == 0
    d1 = inbox.get(iid)["context"]["dialogue"][0]
    assert d1["answered"] and "Sociaal bewijs" in d1["a"]
    # tweede keer: niks meer open
    assert answer_pending_questions(inbox, llm_reason=fake_llm)["answered"] == 0


def test_beantwoording_fail_closed_zonder_llm(tmp_path):
    inbox, iid = _inbox(tmp_path)
    ask_role(inbox, iid, "Leg eens uit?")
    res = answer_pending_questions(inbox, llm_reason=lambda p: None)
    assert res["answered"] == 0 and res["pending"] == 1
    assert inbox.get(iid)["context"]["dialogue"][0]["answered"] is False


def test_pick_governance_target_kiest_bestaande_rol(tmp_path):
    out = pick_governance_target(["scout", "librarian", "analyst"],
                                 "Social media bijhouden", "posts plaatsen",
                                 llm_reason=lambda p: "scout")
    assert out == "scout"


def test_pick_governance_target_nieuw_en_fail_closed(tmp_path):
    assert pick_governance_target(["scout"], "iets", "iets",
                                  llm_reason=lambda p: "__new__") == "__new__"
    # onbekend antwoord → fail-closed naar __new__
    assert pick_governance_target(["scout"], "iets", "iets",
                                  llm_reason=lambda p: "bestaat_niet") == "__new__"
    # geen LLM-antwoord → __new__
    assert pick_governance_target(["scout"], "iets", "iets", llm_reason=lambda p: None) == "__new__"
    # lege roster → __new__
    assert pick_governance_target([], "iets", "iets", llm_reason=lambda p: "x") == "__new__"


def test_formulate_project_fail_closed(tmp_path):
    assert formulate_project("Reviews tonen", "wat", llm_reason=lambda p: None) == "Reviews tonen"
    out = formulate_project("Reviews tonen", "wat",
                            llm_reason=lambda p: "Reviews zichtbaar op elke productpagina")
    assert out == "Reviews zichtbaar op elke productpagina"


def test_klaar_geblokkeerd_zolang_vraag_open(tmp_path):
    """Veiligheid: je kunt niet afronden terwijl er nog een vraag openstaat (anders mis je
    het antwoord uit de volgende puls)."""
    from nooch_village.inbox_actions import decide_opportunity
    inbox, iid = _inbox(tmp_path)
    ask_role(inbox, iid, "Wat bedoel je?")
    res = decide_opportunity(inbox, iid, "done")
    assert res["ok"] is False and res["status"] == "blocked_question"
    assert inbox.get(iid)["status"] == "pending"             # nog open
    # antwoord komt binnen → dan mag afronden wel
    answer_pending_questions(inbox, llm_reason=lambda p: "ANTWOORD 1: Dit en dat.")
    res2 = decide_opportunity(inbox, iid, "done")
    assert res2["ok"] and res2["status"] == "done"
    assert inbox.get(iid)["status"] == "approved"            # nu weg uit de lijst


def test_project_wordt_concept_en_keuren_we_goed(tmp_path):
    """tac_project maakt een CONCEPT (draft) dat niet op het actieve bord staat; approve zet
    'm op queued (op het bord), discard gooit 'm weg."""
    from nooch_village.projects import ProjectLedger
    from nooch_village.inbox_actions import decide_opportunity
    inbox, iid = _inbox(tmp_path)
    projects = ProjectLedger(str(tmp_path / "projects.json"))
    res = decide_opportunity(inbox, iid, "add", destination="project", owner="scout",
                             scope_override="Reviews zichtbaar op elke productpagina",
                             project_status="draft", projects=projects)
    assert res["ok"] and res["draft"] is True
    d = projects.drafts()
    assert len(d) == 1 and d[0]["status"] == "draft" and d[0]["owner"] == "scout"
    assert projects.approve(d[0]["id"]) is True
    assert projects.get(d[0]["id"])["status"] == "queued"    # nu op het bord
    assert projects.drafts() == []
    # discard werkt alleen op drafts
    iid2 = projects.create("scout", "x", "human", status="draft")
    assert projects.discard(iid2) is True and projects.get(iid2) is None


def test_lopende_projecten_niet_in_backlog(tmp_path):
    """De backlog is een triage-wachtrij: lopende projecten staan er NIET in (anders blijft
    de lijst vollopen). Drafts ook niet."""
    import json
    from nooch_village import cockpit
    data = tmp_path / "data"
    data.mkdir()
    for f in ("governance_records.json", "human_inbox.json", "library.json"):
        (data / f).write_text("{}", encoding="utf-8")
    (data / "projects.json").write_text(json.dumps({
        "p1": {"id": "p1", "owner": "scout", "scope": "Lopend project", "status": "running",
               "business_case": make_business_case(effect=80, effort=2, confidence=0.7)},
        "p2": {"id": "p2", "owner": "harry", "scope": "Concept-project", "status": "draft",
               "business_case": make_business_case(effect=80, effort=2, confidence=0.7)},
    }), encoding="utf-8")
    snap = cockpit.gather(str(data))
    assert snap["backlog"] == []                             # geen projecten in de backlog
    assert len(snap["project_drafts"]) == 1
    page = cockpit.render_html(snap, csrf_token="t")
    assert "Concept-projecten" in page and "Concept-project" in page
    assert 'value="proj_approve"' in page and 'value="proj_discard"' in page


def test_focusmodus_render_een_kaart_met_stappen(tmp_path):
    """Focusmodus toont één spanning en de stapsgewijze keuzes (Duolingo-stijl), met een
    duidelijke weg terug naar het overzicht."""
    from nooch_village import cockpit
    x = {"iid": "k1", "title": "Reviews op de PDP", "by": "analyst",
         "wat": "Sterren tonen.", "waarom": "sociaal bewijs",
         "business_case": make_business_case(effect=80, effort=2, confidence=0.7),
         "value": 28.0, "dialogue": []}
    page = cockpit.render_triage(x, 1, 3, ["scout", "analyst"], "t")
    assert "Reviews op de PDP" in page and "Hoe pak je dit op?" in page
    assert "← overzicht" in page                                    # terug naar de lijst
    for val in ("tac_project", "tac_info_give", "tac_info_ask", "gov_proposal",
                "tension_done", "vision_drop"):
        assert f'value="{val}"' in page
    # uitkomst toevoegen → blijf op de kaart; afronden/vraag → terug naar overzicht
    assert "/triage?iid=k1" in page and 'value="/triage"' in page
    assert "<option value=\"scout\">" in page                       # rol-keuze


def test_focusmodus_overzicht_lijst_alle_spanningen(tmp_path):
    """Het overzicht toont álle openstaande spanningen als klikbare lijst (geen gedwongen
    volgorde), met een 'wacht op antwoord'-badge waar een vraag openstaat."""
    from nooch_village import cockpit
    queue = [
        {"iid": "k1", "title": "Reviews op de PDP", "by": "analyst", "value": 28.0,
         "business_case": make_business_case(effect=80, effort=2, confidence=0.7),
         "awaiting": False},
        {"iid": "k2", "title": "Sokken van hennep", "by": "herman", "value": 12.0,
         "business_case": None, "awaiting": True},
    ]
    page = cockpit.render_triage_overview(queue, "t")
    assert "2 openstaande spanning" in page
    assert "Reviews op de PDP" in page and "Sokken van hennep" in page
    assert "/triage?iid=k1" in page and "/triage?iid=k2" in page    # elk klikbaar
    assert "wacht op antwoord" in page                              # badge op k2
    assert "ArrowDown" in page and "ArrowUp" in page                # toetsenbord-navigatie


def test_focusmodus_overzicht_leeg_is_klaar(tmp_path):
    from nooch_village import cockpit
    assert "Alles verwerkt" in cockpit.render_triage_overview([], "t")
    assert "Alles verwerkt" in cockpit.render_triage(None, 0, 0, [], "t")


def test_focus_kaart_holacracy_knoppen_en_dialoog(tmp_path):
    """De focusmodus toont de Holacracy-knoppen en, bij een onbeantwoorde vraag, 'wachten op
    antwoord' met de dialoog. (De kansen-backlog is uit het dashboard; verwerken gaat via focus.)"""
    from nooch_village import cockpit
    data = tmp_path / "data"
    data.mkdir()
    for f in ("governance_records.json", "projects.json", "library.json"):
        (data / f).write_text("{}", encoding="utf-8")
    inbox = HumanInbox(str(data / "human_inbox.json"))
    iid = inbox.add_opportunity("Reviews op de productpagina", by="analyst",
                                wat="Sterren tonen.", waarom="sociaal bewijs",
                                business_case=make_business_case(effect=80, effort=2, confidence=0.7))
    inbox.add_question(iid, "Wat bedoel je hiermee?", by_role="analyst")

    snap = cockpit.gather(str(data))
    # backlog is niet meer in het dashboard gerenderd
    assert "Kansen-backlog" not in cockpit.render_html(snap, csrf_token="t")
    x = next(b for b in snap["backlog"] if b.get("iid") == iid)
    page = cockpit.render_triage(x, 1, 1, ["analyst"], "t")
    for val in ("tac_project", "tac_info_give", "tac_info_ask",
                "gov_proposal", "tension_done", "vision_drop"):
        assert f'value="{val}"' in page
    assert "⚙️ Tactical" in page and "🏛️ Governance" in page
    assert "wachten op antwoord" in page and "Wat bedoel je hiermee?" in page
    assert "Wat bedoel je hiermee?" in page                   # de geparkeerde vraag
