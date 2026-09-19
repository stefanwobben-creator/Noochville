"""DE veiligheidsgarantie van hefboom 2: een project met status `proposed` komt NOOIT vanzelf in
beweging. Ruis is duur, dus de mens is de poort — en die poort mag niet per ongeluk openvallen
doordat een andere lus zijn statusfilter verbreedt.

Deze test bevroor die grens op drie autonome lussen. Twee bestaan sinds 19 september 2026 niet
meer: `project_worker._eligible` (de module is weg) en de voorbereid-en-voer-uit-helft van
`Inhabitant._tend_projects` (BLOK A). Wat overblijft is `board_loop.activate_pulse`, en dat is
nu de ENIGE lus die een project uit zichzelf in beweging kan brengen — reden te meer om hem
hier vast te houden. Verbreedt iemand dat statusfilter, dan valt hier een test om.

`_tend_projects` blijft wél getest, maar op wat hij nog doet: hij mag een voorstel niet
heropenen. Dat is de parkeer-klep, en die kijkt naar `blocked`, niet naar `proposed`.
"""
from __future__ import annotations

import os

from nooch_village.board_loop import activate_pulse
from nooch_village.event_bus import EventBus
from nooch_village.config import Context
from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RecordType, RoleDefinition
from nooch_village.projects import ProjectLedger
from nooch_village.skills import SkillRegistry


def _led(tmp_path):
    return ProjectLedger(os.path.join(str(tmp_path), "projects.json"))


def test_activate_pulse_raakt_een_voorstel_nooit_aan(tmp_path):
    """Ook niet met alle ruimte van de wereld, een bemenste eigenaar en een actieve cluster-root."""
    led = _led(tmp_path)
    root = led.create("harry", "cluster", "human", status="future")
    led.start(root)
    los = led.create("harry", "voorstel (standalone)", "role", status="proposed")
    lid = led.create("harry", "voorstel als cluster-lid", "role", status="proposed", parent=root)

    res = activate_pulse(led, ["harry"], wip={"board": 99, "roles": {}})

    assert res == {"activated": [], "resumed": [], "escalated": []}
    assert led.get(los)["status"] == "proposed"
    assert led.get(lid)["status"] == "proposed"


def test_activate_pulse_escaleert_een_voorstel_niet_bij_onbemande_rol(tmp_path):
    """Guardrail 3 (onbemande eigenaar → naar de mens) mag een voorstel evenmin verplaatsen: het
    ligt al bij de mens. Anders zou een voorstel als 'blocked' op het bord verschijnen."""
    led = _led(tmp_path)
    root = led.create("harry", "cluster", "human", status="future")
    led.start(root)
    v = led.create("niemand", "voorstel", "role", status="proposed", parent=root)

    res = activate_pulse(led, ["harry"], wip={"board": 99, "roles": {}})

    assert res["escalated"] == [] and led.get(v)["status"] == "proposed"




def test_tend_projects_heropent_een_voorstel_niet(tmp_path):
    """Inhabitant: een voorstel blijft een voorstel. De parkeer-klep kijkt naar `blocked`;
    `proposed` komt daar niet in voor, dus er gebeurt niets."""
    dd = str(tmp_path)
    ctx = Context(settings={}, data_dir=dd)
    ctx.projects = _led(tmp_path)
    rec = Record(id="harry", type=RecordType.ROLE, parent=None,
                 definition=RoleDefinition(purpose="wetenschap"))
    inh = Inhabitant(rec, EventBus(name="t"), SkillRegistry(), ctx)
    pid = ctx.projects.create("harry", "voorstel", "role", status="proposed")

    inh._tend_projects()

    p = ctx.projects.get(pid)
    assert p["status"] == "proposed"
    assert not p.get("checklists") and not p.get("progress")


def test_pas_na_menselijke_acceptatie_doet_de_puls_mee(tmp_path):
    """De keerzijde van de garantie: is de mens akkoord, dan gaat het voorstel de normale flow in.
    Als root-project blijft activeren mens-werk (de puls raakt root-projecten bewust niet aan)."""
    from nooch_village.project_proposals import accept
    led = _led(tmp_path)
    pid = led.create("harry", "voorstel", "role", status="proposed")

    assert accept(led, str(tmp_path), pid, person="stefan") is True
    assert led.get(pid)["status"] == "future" and led.get(pid)["person"] == "stefan"
    # standalone root → de puls laat het met rust; de mens zet het zelf op actief
    assert activate_pulse(led, ["harry"], wip={"board": 99, "roles": {}})["activated"] == []
