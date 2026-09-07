"""SCOPE 4 — het uitvoerplan is een VOORSTEL, geen opdracht.

Een project naar ACTIEF slepen zegt "dit is aan de beurt". Het zegt niet "voer dit plan uit", want
dat plan bestond op dat moment nog niet: de rol maakt het pas ná de activatie. Sinds het
drie-stagiairs-besluit (5 sept 2026) hoort daar een mens tussen te staan.

Plannen is goedkoop en omkeerbaar; uitvoeren kost API-calls en schrijft naar de projectwall. De knip
ligt dus tussen die twee, niet bij het slepen.

Thread-vrij: geen enkele test start een inwoner-thread of doet een echte LLM-call.
"""
from __future__ import annotations
import pytest
from types import SimpleNamespace

from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus, Event
from nooch_village.skills import SkillRegistry, Skill
from nooch_village.projects import ProjectLedger, plan_wacht_op_akkoord
from nooch_village.village import Village

TODAY = "2026-09-05"
PLAN = ('{"deliverable":"dossier","items":['
        '{"text":"studies","skill":"openalex_evidence","payload":{"term":"barefoot"},"reason":""}]}')


class _ResearchSkill(Skill):
    name = "openalex_evidence"
    description = "fake research skill (term → hits)"

    def run(self, payload, context):
        term = (payload or {}).get("term", "")
        return {"term": term, "total": 1,
                "hits": [{"title": f"Study on {term}", "year": 2021, "citations": 7, "topic": "footwear"}]}


@pytest.fixture
def ledger(tmp_path):
    return ProjectLedger(str(tmp_path / "projects.json"))


def _inhabitant(tmp_path, ledger, rid="harry_hemp"):
    reg = SkillRegistry()
    reg.register(_ResearchSkill())
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0"}, data_dir=str(tmp_path),
                          projects=ledger, records=None)
    rec = Record(id=rid, type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="waarheid",
                                           accountabilities=["research studies by openalex, delivering evidence"],
                                           domains=[], skills=["openalex_evidence"]), source="sensed")
    return Inhabitant(rec, EventBus(name="test"), reg, ctx)


def _mock_plan(monkeypatch, plan=PLAN):
    import nooch_village.llm as llm
    monkeypatch.setattr(llm, "reason", lambda *a, **k: (plan, "mock") if k.get("return_tier") else plan)


def _cl(inh, ledger, pid):
    return inh._project_checklist(ledger.get(pid))


# ── a. plannen zet de vraag; uitvoeren wacht ───────────────────────────────────────────────────

def test_a_voorbereiding_levert_een_voorstel_geen_opdracht(tmp_path, ledger, monkeypatch):
    _mock_plan(monkeypatch)
    inh = _inhabitant(tmp_path, ledger)
    pid = ledger.create("harry_hemp", "onderzoek barefoot", "human", status="queued")
    ledger.start(pid)                                            # bord-drag naar ACTIEF
    inh.prepare_project(pid)
    cl = _cl(inh, ledger, pid)
    assert cl is not None and cl["akkoord"] is False             # het plan ligt er, als VOORSTEL
    assert plan_wacht_op_akkoord(ledger.get(pid)) is True


def test_b_zonder_akkoord_draait_er_niets(tmp_path, ledger, monkeypatch):
    _mock_plan(monkeypatch)
    inh = _inhabitant(tmp_path, ledger)
    pid = ledger.create("harry_hemp", "onderzoek barefoot", "human", status="queued")
    ledger.start(pid)
    inh._tend_projects(None)                                     # voorbereiden ÉN (niet) uitvoeren
    p = ledger.get(pid)
    assert _cl(inh, ledger, pid)["items"][0]["done"] is False     # geen skill gedraaid
    assert p.get("last_tended") != TODAY                          # niet 'vandaag afgehandeld'
    assert p["status"] != "done"


def test_c_na_akkoord_draait_het_wel(tmp_path, ledger, monkeypatch):
    _mock_plan(monkeypatch)
    inh = _inhabitant(tmp_path, ledger)
    pid = ledger.create("harry_hemp", "onderzoek barefoot", "human", status="queued")
    ledger.start(pid)
    inh.prepare_project(pid)
    clid = _cl(inh, ledger, pid)["id"]
    inh._execute_checklist(ledger.get(pid), TODAY)
    assert _cl(inh, ledger, pid)["items"][0]["done"] is False     # nog steeds niets

    assert ledger.plan_akkoord(pid, clid, door="stefan") is True  # de mens zegt ga maar doen
    inh._execute_checklist(ledger.get(pid), TODAY)
    it = _cl(inh, ledger, pid)["items"][0]
    assert it["done"] is True
    logtxt = " ".join(e["text"] for e in ledger.get(pid).get("log", []))
    assert "Study on barefoot" in logtxt                          # de deliverable-note staat op de wall


# ── b. fail-open: alleen een expliciete False blokkeert ────────────────────────────────────────

def test_d_handgemaakte_checklist_blijft_gewoon_draaien(tmp_path, ledger):
    """De deploy mag geen enkel bestaand project stilzetten. Een checklist zonder `akkoord`-sleutel
    is met de hand gemaakt of stamt van vóór deze regel: die doet wat hij altijd deed."""
    inh = _inhabitant(tmp_path, ledger)
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    cl = ledger.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE)   # geen akkoord-argument
    assert "akkoord" not in cl
    ledger.check_add(pid, cl["id"], "studies", skill="openalex_evidence", payload={"term": "barefoot"})
    inh._execute_checklist(ledger.get(pid), TODAY)
    assert _cl(inh, ledger, pid)["items"][0]["done"] is True


@pytest.mark.parametrize("waarde,wacht", [(False, True), (True, False), (None, False)])
def test_e_alleen_expliciet_false_blokkeert(waarde, wacht):
    cl = {"id": "x", "title": "Uitvoerplan", "items": []}
    if waarde is not None:
        cl["akkoord"] = waarde
    assert plan_wacht_op_akkoord(cl) is wacht                     # losse checklist
    assert plan_wacht_op_akkoord({"checklists": [cl]}) is wacht   # heel project
    assert plan_wacht_op_akkoord({"checklists": []}) is False     # project zonder plan


# ── c. de akkoord-knop zelf ────────────────────────────────────────────────────────────────────

def test_f_akkoord_is_eenmalig_en_noemt_de_naam(tmp_path, ledger):
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    cl = ledger.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE, akkoord=False)
    assert ledger.plan_akkoord(pid, cl["id"], door="stefan") is True
    cl2 = ledger.get(pid)["checklists"][0]
    assert cl2["akkoord"] is True and cl2["akkoord_door"] == "stefan"
    # tweede keer: er stond geen vraag meer open → False, en het blijft goedgekeurd
    assert ledger.plan_akkoord(pid, cl["id"], door="nina") is False
    assert ledger.get(pid)["checklists"][0]["akkoord_door"] == "stefan"


def test_g_akkoord_op_iets_wat_niet_wacht_doet_niets(tmp_path, ledger):
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    cl = ledger.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE)    # geen akkoord-vraag
    assert ledger.plan_akkoord(pid, cl["id"]) is False
    assert ledger.plan_akkoord(pid, "bestaat-niet") is False
    assert ledger.plan_akkoord("geen-project", cl["id"]) is False


def test_h_akkoord_raakt_de_review_vlag_niet(tmp_path, ledger):
    """Akkoord geven verandert geen enkel ITEM, dus de review-vlag (die over de inhoud van de
    checklist gaat) hoort te blijven staan. check_add/check_toggle wissen 'm wél — die veranderen wel."""
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    cl = ledger.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE, akkoord=False)
    ledger.mark_awaiting_review(pid)                              # zet de vlag langs het echte pad
    assert ledger.get(pid)["review_raised"] is True
    ledger.plan_akkoord(pid, cl["id"], door="stefan")
    assert ledger.get(pid).get("review_raised") is True
    ledger.check_add(pid, cl["id"], "iets nieuws")                # een ITEM-mutatie wist 'm wél
    assert ledger.get(pid).get("review_raised") is None


# ── d. de mens hoort het te weten ──────────────────────────────────────────────────────────────

def test_i_plan_klaar_meldt_zich_bij_de_eigenaar_rol(tmp_path, ledger, monkeypatch):
    from nooch_village.notifications import NotifStore
    _mock_plan(monkeypatch)
    inh = _inhabitant(tmp_path, ledger)
    pid = ledger.create("harry_hemp", "onderzoek barefoot", "human", status="queued")
    ledger.start(pid)
    inh.prepare_project(pid)
    n = NotifStore(str(tmp_path / "notifications.json")).for_targets([("role", "harry_hemp")])
    assert len(n) == 1
    tekst = n[0].get("tekst") or n[0]["snippet"]
    assert "Execution plan" in tekst and "go ahead" in tekst       # wat er ligt, en wat jij moet doen


def test_j_volledig_mens_plan_vraagt_geen_akkoord(tmp_path, ledger, monkeypatch):
    """Een plan dat de rol tóch niet kan draaien wordt geblokkeerd en bij de mens gelegd. Dáár een
    'ga maar doen'-knop bij zetten is een lege belofte: er is niets om te draaien."""
    from nooch_village.notifications import NotifStore
    from nooch_village.human_inbox import FOUNDER_ROLE_ID
    _mock_plan(monkeypatch, '{"deliverable":"d","items":[{"text":"bel de fabriek","skill":null,'
                            '"kind":"human_external","reason":""}]}')
    inh = _inhabitant(tmp_path, ledger)
    pid = ledger.create("harry_hemp", "bel de fabriek", "human", status="queued")
    ledger.start(pid)
    inh.prepare_project(pid)
    assert ledger.get(pid)["status"] == "blocked"
    store = NotifStore(str(tmp_path / "notifications.json"))
    assert len(store.for_targets([("role", FOUNDER_ROLE_ID)])) == 1        # de mens-project-melding
    eigen = [n for n in store.for_targets([("role", "harry_hemp")])
             if "go ahead" in (n.get("tekst") or n.get("snippet") or "")]
    assert eigen == []                                                     # géén akkoord-vraag


# ── e. de akkoord-brug in de board-watch ───────────────────────────────────────────────────────

def _watch(ledger):
    """Minimale village-stub met precies wat _poll_board/_prime_board_watch aanraken. Bewust
    ONVERANDERD t.o.v. test_project_activated: scope 4 voegt geen tweede seen-set toe, maar
    verandert wat er in de bestaande staat."""
    bus = EventBus(name="test")
    events: list[dict] = []
    bus.subscribe("project_activated", lambda e: events.append(e.data))
    v = SimpleNamespace(context=SimpleNamespace(projects=ledger), bus=bus,
                        _activated_seen=set(), _completed_seen=set())
    return v, events


def test_k_de_hele_route_over_de_board_watch(tmp_path, ledger, monkeypatch):
    """De echte volgorde. Drag naar ACTIEF → event (er is nog geen plan, dus niets wacht) → de rol
    maakt het plan → het project valt uit de watch zolang het wacht → akkoord → event → uitvoeren.

    Akkoord geven is geen statuswijziging; zonder deze brug klik je 'go ahead' en gebeurt er tot
    04:32 de volgende ochtend niets."""
    _mock_plan(monkeypatch)
    inh = _inhabitant(tmp_path, ledger)
    pid = ledger.create("harry_hemp", "onderzoek barefoot", "human", status="queued")
    v, events = _watch(ledger)
    Village._prime_board_watch(v)

    ledger.start(pid)                                             # bord-drag naar ACTIEF
    assert Village._poll_board(v) == [pid]                        # aan de beurt: er wacht nog niets
    events.clear()

    inh.prepare_project(pid)                                      # de rol maakt het uitvoerplan
    clid = _cl(inh, ledger, pid)["id"]
    assert Village._poll_board(v) == [] and events == []          # wacht op akkoord → stil
    assert Village._poll_board(v) == [] and events == []          # en blijft stil

    ledger.plan_akkoord(pid, clid, door="stefan")                 # de mens zegt ga maar doen
    assert Village._poll_board(v) == [pid]                        # opnieuw aan de beurt
    assert events == [{"pid": pid, "owner": "harry_hemp"}]
    events.clear()
    assert Village._poll_board(v) == [] and events == []          # precies één keer


def test_l_zonder_plan_verandert_er_niets_aan_de_watch(tmp_path):
    """Een project zonder uitvoerplan (of met een handgemaakte checklist) gedraagt zich als
    vanouds: één event bij de activatie, en niet meer."""
    led = ProjectLedger(str(tmp_path / "p.json"))
    pid = led.create("harry_hemp", "doel", "human", status="queued")
    v, events = _watch(led)
    Village._poll_board(v)
    led.start(pid)
    assert Village._poll_board(v) == [pid]
    assert events == [{"pid": pid, "owner": "harry_hemp"}]        # exact één
    events.clear()
    assert Village._poll_board(v) == [] and events == []


def test_m_herstart_vuurt_goedgekeurde_plannen_niet_opnieuw(tmp_path):
    led = ProjectLedger(str(tmp_path / "p.json"))
    pid = led.create("harry_hemp", "doel", "human", status="queued")
    cl = led.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE, akkoord=False)
    led.start(pid)
    led.plan_akkoord(pid, cl["id"], door="stefan")
    v, events = _watch(led)
    Village._prime_board_watch(v)                                 # daemon start op
    assert Village._poll_board(v) == [] and events == []          # oud akkoord = geen nieuw akkoord


def test_m2_herstart_pakt_een_wachtend_plan_niet_stiekem_op(tmp_path):
    """Het spiegelbeeld: een plan dat vóór de herstart nog wachtte, hoort ná de herstart nog steeds
    te wachten. Een daemon-herstart is geen akkoord."""
    led = ProjectLedger(str(tmp_path / "p.json"))
    pid = led.create("harry_hemp", "doel", "human", status="queued")
    led.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE, akkoord=False)
    led.start(pid)
    v, events = _watch(led)
    Village._prime_board_watch(v)
    assert Village._poll_board(v) == [] and events == []


# ── f. de knop bestaat, is gated, en staat op het scherm ───────────────────────────────────────

def test_n_cockpit_actie_is_geregistreerd_en_gelabeld():
    import inspect
    from nooch_village import cockpit2
    assert cockpit2.ACTIONS["plan_akkoord"] is cockpit2._act_plan_akkoord
    src = inspect.getsource(cockpit2._act_plan_akkoord)
    assert "# AUTHZ:" in src                                      # CLAUDE.md: elke actie labelt zijn poort
    assert "_role_gate" in src                                    # en gebruikt 'm ook echt


def test_o_wachtend_plan_toont_de_knop(tmp_path):
    from nooch_village.views.checklists import _checklists_html
    led = ProjectLedger(str(tmp_path / "p.json"))
    pid = led.create("harry_hemp", "doel", "human", status="queued")
    cl = led.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE, akkoord=False)
    led.check_add(pid, cl["id"], "studies", skill="openalex_evidence")

    html = _checklists_html(led.get(pid), "csrf", pid, "/projects", True)
    assert "plan_akkoord" in html and "go ahead" in html
    # De balk zegt óók WAT er gaat draaien: dat is de vraag die de knop stelt.
    assert "the role runs 1" in html and "openalex_evidence" in html

    led.plan_akkoord(pid, cl["id"], door="stefan")
    html2 = _checklists_html(led.get(pid), "csrf", pid, "/projects", True)
    assert "plan_akkoord" not in html2                             # knop weg zodra het gezegd is
    # DRIE TOESTANDEN sinds 06-09-2026, niet twee. Direct na akkoord is de rol nog BEZIG: de
    # bordpuls is nog niet langsgeweest en het item staat open. "approved by" op dat moment tonen
    # leest als 'klaar', en dat was precies de verwarring — je zag niet dat er nog iets liep.
    assert "the role is working" in html2 and "1 to go" in html2
    assert "data-bezig" in html2

    led.check_toggle(pid, cl["id"], led.get(pid)["checklists"][0]["items"][0]["id"])
    html3 = _checklists_html(led.get(pid), "csrf", pid, "/projects", True)
    assert "approved by stefan" in html3                           # klaar: nu pas, en wél wie


def test_p_leesmodus_toont_de_stand_zonder_knop(tmp_path):
    from nooch_village.views.checklists import _checklists_html
    led = ProjectLedger(str(tmp_path / "p.json"))
    pid = led.create("harry_hemp", "doel", "human", status="queued")
    cl = led.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE, akkoord=False)
    led.check_add(pid, cl["id"], "studies", skill="openalex_evidence")
    html = _checklists_html(led.get(pid), "", pid, "/projects", False)   # rw=False
    assert "waiting for your go-ahead" in html and "plan_akkoord" not in html


# ── g. de balk zegt wat er gaat gebeuren ───────────────────────────────────────────────────────

def _plan_met_alle_soorten(ledger, pid):
    """Het echte geval van 6 september: twee skill-items, één mens-taak, één zonder skill."""
    cl = ledger.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE, akkoord=False)
    ledger.check_add(pid, cl["id"], "check of de site leeft", skill="site_health",
                     payload={"url": "https://village.nooch.earth"})
    ledger.check_add(pid, cl["id"], "haal de pagina op", skill="haal_pagina",
                     payload={"url": "https://village.nooch.earth", "term": "viewport"})
    ledger.check_add(pid, cl["id"], "test met de hand op een telefoon", human_task=True,
                     reason="fysieke interactie met een toestel")
    ledger.check_add(pid, cl["id"], "draai Lighthouse", reason="geen skill beschikbaar")
    return cl


def test_q_de_balk_vertelt_wat_de_knop_doet(tmp_path, ledger):
    """De klacht van 6 september: 'als ik akkoord zeg kan ik niet makkelijk zien wat de AI dan
    uitvoert'. Die informatie stond verspreid over vier items met elk een eigen labeltje. Nu staat
    het antwoord op de plek waar de vraag gesteld wordt."""
    from nooch_village.views.checklists import _checklists_html
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    _plan_met_alle_soorten(ledger, pid)
    html = _checklists_html(ledger.get(pid), "csrf", pid, "/projects", True)

    assert "the role runs 2" in html                       # niet 4, en niet 3
    assert "site_health" in html and "haal_pagina" in html  # mét de namen, niet alleen een getal
    assert "1 for you (hands-on)" in html                   # de mens-taak
    assert "1 nobody can run yet" in html                   # het item zonder skill


def test_r_geen_knop_als_er_niets_te_draaien_valt(tmp_path, ledger):
    """'go ahead' op een plan dat de rol niet kan draaien is een lege belofte. Dan geen knop, wel
    de reden — anders klik je en gebeurt er niets, zonder uitleg."""
    from nooch_village.views.checklists import _checklists_html
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    cl = ledger.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE, akkoord=False)
    ledger.check_add(pid, cl["id"], "bel de fabriek", human_task=True, reason="telefoon")
    html = _checklists_html(ledger.get(pid), "csrf", pid, "/projects", True)
    assert "plan_akkoord" not in html
    assert "1 for you (hands-on)" in html


def test_s_na_akkoord_blijft_staan_wat_van_jou_is(tmp_path, ledger):
    """Als de rol klaar is wil je weten wat er nog op jouw bord ligt. Dezelfde samenvatting, maar
    de gedraaide items tellen niet meer mee."""
    from nooch_village.views.checklists import _checklists_html
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    cl = _plan_met_alle_soorten(ledger, pid)
    ledger.plan_akkoord(pid, cl["id"], door="stefan")
    for it in ledger.get(pid)["checklists"][0]["items"][:2]:
        ledger.check_toggle(pid, cl["id"], it["id"])       # de rol heeft ze gedraaid

    html = _checklists_html(ledger.get(pid), "csrf", pid, "/projects", True)
    assert "approved by stefan" in html
    assert "the role runs" not in html                      # niets meer te draaien
    assert "1 for you (hands-on)" in html and "1 nobody can run yet" in html
