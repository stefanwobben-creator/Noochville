"""SCOPE 0 — project_activated board-watch.

Een statuswijziging naar ACTIEF (meestal een bord-drag in het LOSSE cockpit-proces) moet binnen
seconden opgepakt worden i.p.v. pas bij de dag-puls (dag_begint). Cockpit en village delen alleen
projects.json; de village-poll (`Village._poll_board`) herleest dat bestand en vertaalt een verse
naar-'running'-overgang naar een in-memory project_activated-event.

19 SEPT 2026 — DE ONTVANGER IS WEG. `Inhabitant._on_project_activated` bereidde het project voor
en voerde het uit; die hele motor is met BLOK A verdwenen. Slepen naar ACTIEF is vanaf nu een
menselijke statuswijziging: het bord verandert, er gaat een event over de bus, en niemand pakt
het op. De detectie hieronder blijft getest, want het event voedt nog de board-watch zelf — en
er staat nu expliciet een test die bewijst dat een bord-drag geen AttributeError meer geeft.

Publisher = de village-board-watch, NIET ledger.start(): start() draait cross-proces in de
cockpit (geen bus, geen inwoners). Zie SCOPE-analyse.
"""
from __future__ import annotations
from types import SimpleNamespace

from nooch_village.inhabitant import Inhabitant
from nooch_village.village import Village
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus, Event
from nooch_village.skills import SkillRegistry, Skill
from nooch_village.projects import ProjectLedger, PREP_CHECKLIST_TITLE


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
    cl = ledger.checklist_add(pid, title=PREP_CHECKLIST_TITLE)
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










# f. een bord-drag naar ACTIEF loopt nergens meer op stuk
def test_f_bord_drag_naar_actief_crasht_niet(tmp_path):
    """Stefans eis bij het verwijderen van BLOK A: bewijs het, vertrouw niet op 'hij draait toch niet'.

    De rol heeft geen handler meer voor `project_activated`. Dit publiceert het event precies zoals
    de board-watch dat doet, laat de inwoner zijn inbox verwerken, en controleert dat er geen
    AttributeError op een verdwenen methode komt. Het project blijft staan waar het staat — dat IS
    het bedoelde gedrag: een mens doet het werk."""
    led = ProjectLedger(str(tmp_path / "p.json"))
    inh = _inhabitant(tmp_path, led)
    assert not inh.bus._subs.get("project_activated"), (
        "de rol hoort niet meer op project_activated te reageren")

    pid = led.create("harry_hemp", "blote-voeten schoenen", "human", status="future")
    led.start(pid)                                                # bord-drag → ACTIEF
    inh.bus.publish(Event("project_activated", {"pid": pid, "owner": "harry_hemp"}, "village"))
    while inh.inbox.pending() > 0:                                # eigen thread-werk afhandelen
        job = inh.inbox.take(timeout=0.05)
        if job and callable(job):
            job()
    assert led.get(pid)["status"] == "running"                    # staat er nog, onaangeroerd
    assert not led.get(pid).get("checklists")                     # en er is niets voorbereid


# g. prime: een project dat bij opstart AL running is, telt niet als nieuwe activatie
def test_g_prime_vuurt_niet_voor_bestaande_running(tmp_path):
    led = ProjectLedger(str(tmp_path / "p.json"))
    pid = led.create("harry_hemp", "doel", "human", status="future")
    led.start(pid)
    v, events = _watch(led)
    Village._prime_board_watch(v)                                # zaad met bestaande running
    assert Village._poll_board(v) == [] and events == []         # geen event voor pre-existing running
