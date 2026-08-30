"""De hartslag hangt aan niemand.

WAT ER GEBEURDE. De afslanking van 28 augustus 2026 legde `facilitator` slapend. Dat is een normaal
governance-besluit over een rol — behalve dat die rol toevallig ook de dagbel luidde. Het dorp
pulseerde drie dagen niet: geen Field Note, geen metrics, geen curatie. Er faalde niets, er werd
niets gelogd, `_should_fire_daily` stond gewoon op True. Er tikte alleen niets meer.

De fout was niet het besluit maar de KOPPELING: een klok die in een deelnemer woont, kan door een
besluit over die deelnemer worden uitgezet. Over een rol mag het dorp beslissen; over zijn hartslag
niet.

DEZE RATCHET BEWAAKT DRIE DINGEN:

  1. De cadans-events komen uit `dagcyclus.py` en nergens anders. Een rol die er weer één publiceert
     zet de koppeling stilzwijgend terug.
  2. De klok is geen rol: geen record, geen CLASS_MAP-entry, geen `Inhabitant`-basis.
  3. Uitval van de puls is HOORBAAR. `pulse_completed` blijft rolwerk — dat mag, want het ís werk —
     maar als het uitblijft moet dat een melding zijn met een naam, geen lege regel.

Punt 3 is de tweede helft van dezelfde les: loskoppelen wat infrastructuur is, en zichtbaar maken
wat terecht aan een rol hangt. Wat je niet kunt loskoppelen, moet je kunnen horen.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1] / "nooch_village"

# De bel en zijn familie. Wie deze publiceert, bepaalt of het dorp leeft.
CADANS = ("dag_begint", "dag_eindigt", "maand_begint", "kwartaal_begint")

# Alleen hier hoort de cadans thuis. Eentje erbij is een besluit, geen bijvangst.
#
# De twee andere zijn het tegenovergestelde van de bug: `village.once()` (de cron-ingang) en de
# groei-demo trappen met de HAND een puls af of sluiten de dag, met bron "cron"/"demo". Dat is een
# mens die belt, niet een rol die toevallig de klok draagt — en het moet blijven werken op een uur
# dat de cadans niet vuurt. De scherpe eigenschap staat in `test_geen_enkele_rol_luidt_de_bel`.
TOEGESTAAN = {"dagcyclus.py", "village.py", "demos/growth.py"}


def _publiceert(event: str) -> set[str]:
    """Bestanden die dit event op de bus zetten."""
    patroon = re.compile(r'Event\(\s*"' + event + r'"')
    uit = set()
    for f in sorted(ROOT.rglob("*.py")):
        if patroon.search(f.read_text(encoding="utf-8")):
            uit.add(str(f.relative_to(ROOT)))
    return uit


def test_alleen_de_klok_luidt_de_bel():
    for event in CADANS:
        bronnen = _publiceert(event)
        erbij = bronnen - TOEGESTAAN
        assert erbij == set(), (
            f"'{event}' wordt gepubliceerd vanuit {sorted(erbij)}. De dagcadans is infrastructuur: "
            "hangt hij aan een rol, dan zet een governance-besluit over die rol de hartslag uit — "
            "precies wat op 28 aug 2026 drie dagen stilte opleverde. Zie nooch_village/dagcyclus.py.")


def test_de_klok_is_geen_rol():
    from nooch_village.dagcyclus import Dagcyclus
    from nooch_village.village import CLASS_MAP
    assert "dagcyclus" not in CLASS_MAP and "klok" not in CLASS_MAP
    assert Dagcyclus.__bases__ == (object,)          # geen Inhabitant, dus geen record en geen slaap


def test_de_village_start_en_stopt_de_klok():
    """Gedrag naast de telling: de klok hoort bij het dorp zelf, niet bij de wortelcirkel."""
    import inspect

    from nooch_village.village import Village
    assert "self.dagcyclus.start()" in inspect.getsource(Village.start)
    assert "self.dagcyclus.stop()" in inspect.getsource(Village.stop)


def test_de_bel_luidt_pas_als_er_geluisterd_wordt():
    """Volgorde-detail met tanden: `root.start()` zet de luisteraars aan. Belt de klok daarvóór, dan
    valt de eerste ring in een leeg dorp — en die komt pas de volgende kalenderdag terug."""
    import inspect

    bron = inspect.getsource(__import__("nooch_village.village", fromlist=["Village"]).Village.start)
    assert bron.index("self.root.start()") < bron.index("self.dagcyclus.start()")


def test_een_uitgebleven_puls_is_geen_lege_regel():
    """`pulse_completed` komt van een rol en kan dus wegvallen. Dat mag — maar niet in stilte: het
    printte 'Field Note: None | tension=None', en dat leest als een lege dag."""
    import inspect

    from nooch_village import village
    bron = inspect.getsource(village._run_single_pulse)
    assert "Geen groei-puls afgerond" in bron
    assert "_PULS_ROLLEN" in bron and "reconciler.live" in bron   # mét de naam van wie stilviel


def test_geen_enkele_rol_luidt_de_bel():
    """Scherper dan de bestandslijst: geen enkele klasse die een inwoner IS mag de cadans publiceren.
    Dat is de eigenschap die brak — het bestand waarin hij stond was toeval."""
    import inspect

    from nooch_village import roles
    from nooch_village.inhabitant import Inhabitant
    for naam, obj in vars(roles).items():
        if not (inspect.isclass(obj) and issubclass(obj, Inhabitant)):
            continue
        bron = inspect.getsource(obj)
        for event in CADANS:
            assert f'Event("{event}"' not in bron, f"{naam} publiceert '{event}'"


def test_de_facilitator_mag_weer_slapen():
    """De belofte die hierbij hoort: nu de bel losstaat, is de facilitator weer gewoon een
    governance-rol. Slaapt hij, dan verdwijnt er geen infrastructuur meer met hem."""
    from nooch_village.afslank_afhankelijkheden import rol_afhankelijkheden
    afh = rol_afhankelijkheden("facilitator")
    events = {e.get("event") for e in (afh.get("events") or [])}
    assert not (events & set(CADANS)), (
        f"de facilitator draagt de cadans nog: {sorted(events & set(CADANS))}")
