"""Hefboom 1 — de bedrading van de pull-scheduler: `available_role_ids` en `run_board_pulse`.

De beslislogica zelf (WIP, master-switch, fallback, prioriteit) staat in test_board_loop.py; hier
toetsen we alleen de bedrading eromheen: wie telt als bemenst-en-beschikbaar, en of de beweging
zichtbaar wordt gemaakt (feed, jsonl, bus-event).
"""
from __future__ import annotations

import json
import os

from nooch_village.assignments import Assignments
from nooch_village.board_loop import available_role_ids, run_board_pulse
from nooch_village.config import Context
from nooch_village.governance import Records
from nooch_village.models import Record, RecordType, RoleDefinition
from nooch_village.projects import ProjectLedger


def _ctx(tmp_path):
    dd = str(tmp_path)
    ctx = Context(settings={}, data_dir=dd)
    ctx.projects = ProjectLedger(os.path.join(dd, "projects.json"))
    recs = Records(os.path.join(dd, "governance_records.json"))
    recs.put(Record(id="dorp", type=RecordType.CIRCLE, parent=None,
                    definition=RoleDefinition(purpose="de cirkel")))
    recs.put(Record(id="harry", type=RecordType.ROLE, parent="dorp",
                    definition=RoleDefinition(purpose="wetenschap"), persona_id="p1"))
    recs.put(Record(id="ronnie", type=RecordType.ROLE, parent="dorp",
                    definition=RoleDefinition(purpose="niemand vervult mij")))
    ctx.records = recs
    return ctx, recs, dd


class _Bus:
    def __init__(self):
        self.events = []

    def publish(self, e):
        self.events.append(e)


def test_available_alleen_bemenste_levende_rollen(tmp_path):
    ctx, recs, dd = _ctx(tmp_path)
    # harry is AI-bemand (persona_id), ronnie heeft geen enkele vervuller, dorp is een cirkel.
    assert available_role_ids(recs, dd) == ["harry"]
    # een mens-vervulling telt óók als bemenst (anders escaleert guardrail 3 een mensrol als 'onbemand')
    Assignments(os.path.join(dd, "assignments.json")).assign("ronnie", "person", "stefan")
    assert available_role_ids(recs, dd) == ["harry", "ronnie"]
    # een onbemande (geboren maar niet geïmplementeerde) rol valt af, ook mét vervuller
    assert available_role_ids(recs, dd, unmanned={"ronnie"}) == ["harry"]


def test_available_is_fail_closed_zonder_records(tmp_path):
    assert available_role_ids(None, str(tmp_path)) == []


def test_run_board_pulse_maakt_de_beweging_zichtbaar(tmp_path):
    ctx, recs, dd = _ctx(tmp_path)
    led = ctx.projects
    root = led.create("harry", "het cluster", "human", status="future")
    led.start(root)
    lid = led.create("harry", "een cluster-lid", "human", status="future", parent=root)
    bus = _Bus()

    res = run_board_pulse(ctx, records=recs, bus=bus, wip={"board": 3, "roles": {}})

    assert res["activated"] == [lid] and led.get(lid)["status"] == "running"
    assert res["available_roles"] == ["harry"]
    # 1) zichtbaar op de kaart zelf
    teksten = [e["text"] for e in led.get(lid).get("log", [])]
    assert any("board pulse: activated" in t for t in teksten)
    # 2) zichtbaar in de eigen historie
    rows = [json.loads(r) for r in open(os.path.join(dd, "board_pulse.jsonl"))]
    assert rows[-1]["counts"] == {"activated": 1, "resumed": 0, "escalated": 0}
    # 3) zichtbaar op de bus (→ system_log)
    assert [e.name for e in bus.events] == ["board_pulse_completed"]


def test_run_board_pulse_logt_ook_een_lege_puls(tmp_path):
    """Stilte is een waarneming: een puls die niets beweegt schrijft óók een regel, zodat Stefan
    het verschil ziet tussen 'niets te doen' en 'de puls draait niet'."""
    ctx, recs, dd = _ctx(tmp_path)
    ctx.projects.create("harry", "standalone, mens-gestuurd", "human", status="future")

    res = run_board_pulse(ctx, records=recs, wip={"board": 3, "roles": {}})

    assert res["activated"] == [] and res["resumed"] == [] and res["escalated"] == []
    rows = [json.loads(r) for r in open(os.path.join(dd, "board_pulse.jsonl"))]
    assert len(rows) == 1 and rows[0]["counts"]["activated"] == 0


def test_run_board_pulse_laat_standalone_projecten_met_rust(tmp_path):
    """Harde grens: een project zonder ouder is mens-gestuurd. Hoeveel WIP-ruimte er ook is."""
    ctx, recs, dd = _ctx(tmp_path)
    led = ctx.projects
    los = led.create("harry", "standalone toekomst", "human", status="future")

    run_board_pulse(ctx, records=recs, wip={"board": 10, "roles": {}})

    assert led.get(los)["status"] == "future"


def test_run_board_pulse_is_herhaalbaar(tmp_path):
    """Deterministisch en WIP-gated: een tweede puls verandert niets meer en dupliceert geen feed."""
    ctx, recs, dd = _ctx(tmp_path)
    led = ctx.projects
    root = led.create("harry", "cluster", "human", status="future")
    led.start(root)
    lid = led.create("harry", "lid", "human", status="future", parent=root)

    run_board_pulse(ctx, records=recs, wip={"board": 3, "roles": {}})
    tweede = run_board_pulse(ctx, records=recs, wip={"board": 3, "roles": {}})

    assert tweede["activated"] == [] and led.get(lid)["status"] == "running"
    assert sum(1 for e in led.get(lid).get("log", []) if "board pulse" in e["text"]) == 1


def test_run_board_pulse_zonder_grootboek_faalt_zacht(tmp_path):
    ctx = Context(settings={}, data_dir=str(tmp_path))
    res = run_board_pulse(ctx)
    assert res["activated"] == [] and res["skipped"]


def test_dag_begint_trekt_de_bord_puls(tmp_path):
    """De bedrading zelf: de daemon-cadans (dag_begint) draait de bord-puls, zonder tweede timer.
    We publiceren het event rechtstreeks op de bus van een sandbox-dorp; de dorpsthreads draaien niet,
    dus alleen de directe infra-subscriber (Village._on_board_pulse) doet hier werk."""
    from nooch_village.event_bus import Event
    from nooch_village.village import Village

    sandbox = str(tmp_path / "dorp")
    v = Village(heartbeat_seconds=86400, data_dir=sandbox)
    led = v.context.projects
    owner = "librarian"
    v.records.set_persona(owner, "p-test")            # bemens één seed-rol → hij telt als beschikbaar
    root = led.create(owner, "cluster", "human", status="future")
    led.start(root)
    lid = led.create(owner, "lid", "human", status="future", parent=root)

    v.bus.publish(Event("dag_begint", {"label": "test"}, "test"))

    assert led.get(lid)["status"] == "running"
    assert os.path.exists(os.path.join(sandbox, "board_pulse.jsonl"))
