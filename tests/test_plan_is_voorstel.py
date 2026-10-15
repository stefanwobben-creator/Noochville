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
    # akkoord direct in de data: de knop ("go ahead") en `ledger.plan_akkoord` zijn weg (15 okt 2026),
    # maar oude checklists dragen `akkoord: true` nog, en de daemon moet die blijven negeren
    led._projects[pid]["checklists"][0]["akkoord"] = True
    led._save()
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
