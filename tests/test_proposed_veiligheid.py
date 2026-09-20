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


def _historisch_voorstel(led, owner, titel, **kw):
    """Een project met status `proposed` zoals het er op productie nog LIGT.

    Sinds 21 september 2026 kan zo'n project niet meer ONTSTAAN: de voorstel-lus is opgeheven
    (`proposed` staat niet meer in `START_STATUSSEN`). Maar de gearchiveerde voorstellen van
    daarvóór dragen de status nog, en juist dáárom blijft deze test staan: een restant in de data
    mag niet alsnog door een autonome lus worden opgepakt. Daarom hier niet via `create` maar
    rechtstreeks in de store, precies zoals zo'n oud record eruitziet."""
    pid = led.create(owner, titel, "role", status="future", **kw)
    led._projects[pid]["status"] = "proposed"
    led._save()
    return pid


def test_activate_pulse_raakt_een_voorstel_nooit_aan(tmp_path):
    """Ook niet met alle ruimte van de wereld, een bemenste eigenaar en een actieve cluster-root."""
    led = _led(tmp_path)
    root = led.create("harry", "cluster", "human", status="future")
    led.start(root)
    los = _historisch_voorstel(led, "harry", "voorstel (standalone)")
    lid = _historisch_voorstel(led, "harry", "voorstel als cluster-lid", parent=root)

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
    v = _historisch_voorstel(led, "niemand", "voorstel", parent=root)

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
    pid = _historisch_voorstel(ctx.projects, "harry", "voorstel")

    inh._tend_projects()

    p = ctx.projects.get(pid)
    assert p["status"] == "proposed"
    assert not p.get("checklists") and not p.get("progress")


def test_een_voorstel_kan_niet_meer_ONTSTAAN(tmp_path):
    """De keerzijde stond hier als "pas na menselijke acceptatie doet de puls mee", en die test
    hing aan `project_proposals.accept` — de helft van de lus die op 21 september 2026 is
    opgeheven omdat er geen scherm meer was waar een mens ja kon zeggen.

    Wat ervoor in de plaats komt is scherper: een voorstel kan niet meer ontstaan. `proposed` staat
    niet meer in `START_STATUSSEN`, dus de enige exemplaren die er zijn, zijn de gearchiveerde van
    vóór die datum — en de tests hierboven houden vast dat geen enkele lus die aanraakt."""
    from nooch_village.projects import START_STATUSSEN
    assert "proposed" not in START_STATUSSEN
    led = _led(tmp_path)
    try:
        led.create("harry", "voorstel", "role", status="proposed")
    except ValueError as e:
        assert "start-status" in str(e)
    else:
        raise AssertionError("een project mag niet meer als voorstel beginnen")
