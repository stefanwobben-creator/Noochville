"""SCOPE 0 — project_activated board-watch.

Een statuswijziging naar ACTIEF (meestal een bord-drag in het LOSSE cockpit-proces) moet binnen
seconden opgepakt worden i.p.v. pas bij de dag-puls (dag_begint). Cockpit en village delen alleen
projects.json; de village-poll (`Village._poll_board`) herleest dat bestand en vertaalt een verse
naar-'running'-overgang naar een in-memory project_activated-event dat de eigenaar-rol oppakt
(`Inhabitant._on_project_activated`) en UITSLUITEND dat ene project uitvoert.

Publisher = de village-board-watch, NIET ledger.start(): start() draait cross-proces in de cockpit
(geen bus, geen inwoners) én zit ín _claim_run_complete (zou een react-lus geven). Zie SCOPE-analyse.
"""
from __future__ import annotations
from types import SimpleNamespace

from nooch_village.inhabitant import Inhabitant
from nooch_village.village import Village
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus, Event
from nooch_village.skills import SkillRegistry, Skill
from nooch_village.projects import ProjectLedger


class _ResearchSkill(Skill):
    name = "openalex_evidence"
    description = "fake research skill (term → hits)"

    def run(self, payload, context):
        term = (payload or {}).get("term", "")
        return {"term": term, "total": 1,
                "hits": [{"title": f"Study on {term}", "year": 2021, "citations": 7, "topic": "footwear"}]}


def _inhabitant(tmp_path, ledger, rid="harry_hemp"):
    reg = SkillRegistry()
    reg.register(_ResearchSkill())
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0"}, data_dir=str(tmp_path),
                          projects=ledger, records=None)
    rec = Record(id=rid, type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="waarheid",
                                           accountabilities=["research"], domains=[],
                                           skills=["openalex_evidence"]), source="sensed")
    return Inhabitant(rec, EventBus(name="test"), reg, ctx)


def _prep(ledger, pid, items):
    cl = ledger.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE)
    for text, skill, query in items:
        ledger.check_add(pid, cl["id"], text, skill=skill, query=query)
    return cl


def _watch(ledger):
    """Minimale village-stub die precies levert wat _poll_board/_prime_board_watch aanraken."""
    bus = EventBus(name="test")
    events: list[dict] = []
    bus.subscribe("project_activated", lambda e: events.append(e.data))
    v = SimpleNamespace(context=SimpleNamespace(projects=ledger), bus=bus, _activated_seen=set())
    return v, events


# a. board-watch detecteert een verse naar-'running'-overgang → project_activated met pid + owner
def test_a_board_watch_detecteert_activatie(tmp_path):
    led = ProjectLedger(str(tmp_path / "p.json"))
    pid = led.create("harry_hemp", "blote-voeten schoenen", "human", status="future")
    v, events = _watch(led)
    assert Village._poll_board(v) == [] and events == []          # nog niets actief
    led.start(pid)                                                # simuleer bord-drag → ACTIEF
    assert Village._poll_board(v) == [pid]
    assert events == [{"pid": pid, "owner": "harry_hemp"}]        # broadcast met owner-veld


# b. eigenaar-rol pakt ALLEEN het geactiveerde project op; owner-mismatch wordt genegeerd
def test_b_eigenaar_voert_alleen_dat_project_uit(tmp_path):
    led = ProjectLedger(str(tmp_path / "p.json"))
    inh = _inhabitant(tmp_path, led)
    pid = led.create("harry_hemp", "doel", "human", status="queued")
    _prep(led, pid, [("studies", "openalex_evidence", "barefoot")])
    ander = led.create("harry_hemp", "ander doel", "human", status="queued")
    _prep(led, ander, [("studies", "openalex_evidence", "vegan")])

    inh._on_project_activated(Event("project_activated", {"pid": pid, "owner": "harry_hemp"}, "board_watch"))
    assert inh._project_checklist(led.get(pid))["items"][0]["done"] is True      # dit project liep
    assert inh._project_checklist(led.get(ander))["items"][0]["done"] is False   # het andere niet

    # owner-mismatch: niet mijn project → geen uitvoering, geen crash
    vreemd = led.create("iemand_anders", "doel", "human", status="queued")
    _prep(led, vreemd, [("s", "openalex_evidence", "x")])
    inh._on_project_activated(Event("project_activated", {"pid": vreemd, "owner": "iemand_anders"}, "board_watch"))
    assert inh._project_checklist(led.get(vreemd))["items"][0]["done"] is False


# c. geactiveerd zonder checklist → project_needs_preparation, geen valse done
def test_c_geen_checklist_signaal_geen_uitvoering(tmp_path):
    led = ProjectLedger(str(tmp_path / "p.json"))
    inh = _inhabitant(tmp_path, led)
    signals = []
    inh.bus.subscribe("project_needs_preparation", lambda e: signals.append(e.data))
    pid = led.create("harry_hemp", "doel", "human", status="queued")   # geen _prep → geen checklist
    inh._on_project_activated(Event("project_activated", {"pid": pid, "owner": "harry_hemp"}, "board_watch"))
    p = led.get(pid)
    assert p["status"] != "done" and p.get("outcome") != "stub:done"
    assert signals and signals[0]["project_id"] == pid


# d. tweede activatie zelfde dag → idempotent (geen dubbele notes) + board-watch dedupliceert
def test_d_tweede_activatie_idempotent(tmp_path):
    led = ProjectLedger(str(tmp_path / "p.json"))
    inh = _inhabitant(tmp_path, led)
    pid = led.create("harry_hemp", "doel", "human", status="queued")
    _prep(led, pid, [("studies", "openalex_evidence", "barefoot")])
    ev = Event("project_activated", {"pid": pid, "owner": "harry_hemp"}, "board_watch")
    inh._on_project_activated(ev)
    n1 = len(led.get(pid).get("log", []))
    inh._on_project_activated(ev)                                # tweede activatie, zelfde dag
    assert len(led.get(pid).get("log", [])) == n1               # geen dubbele deliverable-notes

    # board-watch zelf vuurt niet twee keer voor dezelfde lopende activatie
    v, events = _watch(led)
    Village._poll_board(v)                                       # pid is al 'running' → 1e keer gezien
    first = list(events)
    Village._poll_board(v)                                       # zelfde running-set → geen nieuw event
    assert events == first


# e. eigenaar zonder live inwoner (mens-rol) → event verdwijnt, geen crash
def test_e_mens_rol_geen_crash(tmp_path):
    led = ProjectLedger(str(tmp_path / "p.json"))
    pid = led.create("founder", "mens-project", "human", status="future")   # mens-bemande rol
    v, events = _watch(led)                                                  # geen inwoner geabonneerd
    led.start(pid)
    assert Village._poll_board(v) == [pid]                       # publiceert netjes...
    assert events == [{"pid": pid, "owner": "founder"}]          # ...en niets crasht (geen subscriber)

    # en een echte inwoner met een ANDER id negeert het stil (owner-mismatch)
    inh = _inhabitant(tmp_path, led, rid="harry_hemp")
    inh._on_project_activated(Event("project_activated", {"pid": pid, "owner": "founder"}, "board_watch"))


# f. wiring: het project_activated-event is echt gekoppeld; bestaande 'running' vuurt niet bij opstart
def test_f_wiring_en_prime(tmp_path):
    led = ProjectLedger(str(tmp_path / "p.json"))
    inh = _inhabitant(tmp_path, led)
    assert inh.bus._subs.get("project_activated"), "react() moet project_activated koppelen"

    # _prime_board_watch: een project dat bij opstart AL running is, telt niet als nieuwe activatie
    pid = led.create("harry_hemp", "doel", "human", status="future")
    led.start(pid)
    v, events = _watch(led)
    Village._prime_board_watch(v)                                # zaad met bestaande running
    assert Village._poll_board(v) == [] and events == []         # geen event voor pre-existing running
