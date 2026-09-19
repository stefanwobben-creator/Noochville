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
from nooch_village.projects import ProjectLedger, plan_wacht_op_akkoord, PREP_CHECKLIST_TITLE
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
    pid = ledger.create("harry_hemp", "doel", "human", status="running")
    cl = ledger.checklist_add(pid, title=PREP_CHECKLIST_TITLE, akkoord=False)
    assert ledger.plan_akkoord(pid, cl["id"], door="stefan") is True
    cl2 = ledger.get(pid)["checklists"][0]
    assert cl2["akkoord"] is True and cl2["akkoord_door"] == "stefan"
    # tweede keer: er stond geen vraag meer open → False, en het blijft goedgekeurd
    assert ledger.plan_akkoord(pid, cl["id"], door="nina") is False
    assert ledger.get(pid)["checklists"][0]["akkoord_door"] == "stefan"


def test_g_akkoord_op_iets_wat_niet_wacht_doet_niets(tmp_path, ledger):
    pid = ledger.create("harry_hemp", "doel", "human", status="running")
    cl = ledger.checklist_add(pid, title=PREP_CHECKLIST_TITLE)    # geen akkoord-vraag
    assert ledger.plan_akkoord(pid, cl["id"]) is False
    assert ledger.plan_akkoord(pid, "bestaat-niet") is False
    assert ledger.plan_akkoord("geen-project", cl["id"]) is False


def test_h_akkoord_raakt_de_review_vlag_niet(tmp_path, ledger):
    """Akkoord geven verandert geen enkel ITEM, dus de review-vlag (die over de inhoud van de
    checklist gaat) hoort te blijven staan. check_add/check_toggle wissen 'm wél — die veranderen wel."""
    pid = ledger.create("harry_hemp", "doel", "human", status="running")
    cl = ledger.checklist_add(pid, title=PREP_CHECKLIST_TITLE, akkoord=False)
    ledger.mark_awaiting_review(pid)                              # zet de vlag langs het echte pad
    assert ledger.get(pid)["review_raised"] is True
    ledger.plan_akkoord(pid, cl["id"], door="stefan")
    assert ledger.get(pid).get("review_raised") is True
    ledger.check_add(pid, cl["id"], "iets nieuws")                # een ITEM-mutatie wist 'm wél
    assert ledger.get(pid).get("review_raised") is None






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




def test_l_zonder_plan_verandert_er_niets_aan_de_watch(tmp_path):
    """Een project zonder uitvoerplan (of met een handgemaakte checklist) gedraagt zich als
    vanouds: één event bij de activatie, en niet meer."""
    led = ProjectLedger(str(tmp_path / "p.json"))
    pid = led.create("harry_hemp", "doel", "human")                           # slapend (future)
    v, events = _watch(led)
    Village._poll_board(v)
    led.start(pid)
    assert Village._poll_board(v) == [pid]
    assert events == [{"pid": pid, "owner": "harry_hemp"}]        # exact één
    events.clear()
    assert Village._poll_board(v) == [] and events == []


def test_m_herstart_vuurt_goedgekeurde_plannen_niet_opnieuw(tmp_path):
    led = ProjectLedger(str(tmp_path / "p.json"))
    pid = led.create("harry_hemp", "doel", "human", status="running")
    cl = led.checklist_add(pid, title=PREP_CHECKLIST_TITLE, akkoord=False)
    led.start(pid)
    led.plan_akkoord(pid, cl["id"], door="stefan")
    v, events = _watch(led)
    Village._prime_board_watch(v)                                 # daemon start op
    assert Village._poll_board(v) == [] and events == []          # oud akkoord = geen nieuw akkoord


def test_m2_herstart_pakt_een_wachtend_plan_niet_stiekem_op(tmp_path):
    """Het spiegelbeeld: een plan dat vóór de herstart nog wachtte, hoort ná de herstart nog steeds
    te wachten. Een daemon-herstart is geen akkoord."""
    led = ProjectLedger(str(tmp_path / "p.json"))
    pid = led.create("harry_hemp", "doel", "human", status="running")
    led.checklist_add(pid, title=PREP_CHECKLIST_TITLE, akkoord=False)
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
    pid = led.create("harry_hemp", "doel", "human", status="running")
    cl = led.checklist_add(pid, title=PREP_CHECKLIST_TITLE, akkoord=False)
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
    pid = led.create("harry_hemp", "doel", "human", status="running")
    cl = led.checklist_add(pid, title=PREP_CHECKLIST_TITLE, akkoord=False)
    led.check_add(pid, cl["id"], "studies", skill="openalex_evidence")
    html = _checklists_html(led.get(pid), "", pid, "/projects", False)   # rw=False
    assert "waiting for your go-ahead" in html and "plan_akkoord" not in html


# ── g. de balk zegt wat er gaat gebeuren ───────────────────────────────────────────────────────

def _plan_met_alle_soorten(ledger, pid):
    """Het echte geval van 6 september: twee skill-items, één mens-taak, één zonder skill."""
    cl = ledger.checklist_add(pid, title=PREP_CHECKLIST_TITLE, akkoord=False)
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
    pid = ledger.create("harry_hemp", "doel", "human", status="running")
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
    pid = ledger.create("harry_hemp", "doel", "human", status="running")
    cl = ledger.checklist_add(pid, title=PREP_CHECKLIST_TITLE, akkoord=False)
    ledger.check_add(pid, cl["id"], "bel de fabriek", human_task=True, reason="telefoon")
    html = _checklists_html(ledger.get(pid), "csrf", pid, "/projects", True)
    assert "plan_akkoord" not in html
    assert "1 for you (hands-on)" in html


def test_s_na_akkoord_blijft_staan_wat_van_jou_is(tmp_path, ledger):
    """Als de rol klaar is wil je weten wat er nog op jouw bord ligt. Dezelfde samenvatting, maar
    de gedraaide items tellen niet meer mee."""
    from nooch_village.views.checklists import _checklists_html
    pid = ledger.create("harry_hemp", "doel", "human", status="running")
    cl = _plan_met_alle_soorten(ledger, pid)
    ledger.plan_akkoord(pid, cl["id"], door="stefan")
    for it in ledger.get(pid)["checklists"][0]["items"][:2]:
        ledger.check_toggle(pid, cl["id"], it["id"])       # de rol heeft ze gedraaid

    html = _checklists_html(ledger.get(pid), "csrf", pid, "/projects", True)
    assert "approved by stefan" in html
    assert "the role runs" not in html                      # niets meer te draaien
    assert "1 for you (hands-on)" in html and "1 nobody can run yet" in html


# ── Geen bericht over een scherm waar je zelf staat ─────────────────────────────────────────────

def _inw_met_ledger(tmp_path):
    from types import SimpleNamespace
    from nooch_village.event_bus import EventBus
    from nooch_village.inhabitant import Inhabitant
    from nooch_village.models import Record, RoleDefinition, RecordType
    from nooch_village.projects import ProjectLedger
    from nooch_village.skills import SkillRegistry
    led = ProjectLedger(str(tmp_path / "p.json"))
    rec = Record(id="the_source", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="p", skills=["escaleer"]), source="seed")
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0"}, data_dir=str(tmp_path),
                          projects=led, rugzakken={})
    return Inhabitant(rec, EventBus(name="test"), SkillRegistry(), ctx), led


def _plan_klaar(inw, led, monkeypatch, *, net_gevraagd):
    """Bereid één project voor en geef terug welke berichten er naar een rol gingen."""
    from nooch_village.inhabitant import Inhabitant
    monkeypatch.setattr(Inhabitant, "_plan_checklist",
                        lambda self, goal, **kw: {"items": [
                            {"text": "zoek iets op", "skill": "escaleer", "payload": {}}]})
    gestuurd = []
    monkeypatch.setattr(Inhabitant, "_notify_rol",
                        lambda self, rol, pid, tekst: gestuurd.append(tekst))
    pid = led.create("the_source", "een doel", "human", status="running")
    inw.prepare_project(pid, net_gevraagd=net_gevraagd)
    return gestuurd






