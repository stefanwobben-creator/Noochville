"""Geen enkele client-fetch naar /action mag de uitkomst negeren.

DE KLASSE (3–4 sep 2026). Eerst de drawer (#425): een kale fetch, dus een 403 na een herstart zag
er precies zo uit als succes. Toen de projecten-Done (#429): er stónd een `resp.ok`-poort, maar die
mat het TRANSPORT — een weigering reist als melding op een 303, fetch volgt die, de status is 200 en
het scherm meldde "✓ moved" terwijl de server nee zei.

Deze test sluit de klasse. Hij telt, en het plafond is nul: elke `fetch('/action')` moet zowel de
status als de server-markering (`ok=0`) lezen. Zou er één bij komen zonder, dan groeit de telling en
faalt dit — dezelfde vorm als de inline-style-ratchet.
"""
from __future__ import annotations

import pathlib
import re

_PADEN = sorted(pathlib.Path("nooch_village/views").glob("*.py")) + [
    pathlib.Path("nooch_village/cockpit2.py")]

#: Hoe ver na de fetch we naar de afhandeling kijken. Ruim genoeg voor een then-keten.
_VENSTER = 900


def _action_fetches():
    """(bestand, regel, staart) voor elke client-fetch naar /action."""
    for p in _PADEN:
        s = p.read_text(encoding="utf-8")
        for m in re.finditer(r"fetch\(\s*'/action'", s):
            yield p.name, s[:m.start()].count("\n") + 1, s[m.start():m.start() + _VENSTER]


def test_elke_action_fetch_leest_de_status():
    blind = [f"{n}:{r}" for n, r, staart in _action_fetches() if ".ok" not in staart]
    assert blind == [], f"fetch zonder statuscontrole: {blind}"


def test_elke_action_fetch_leest_de_server_markering():
    """`resp.ok` alleen is niet genoeg — dat was #429. De uitkomst staat in `ok=0`, server-side
    gezet door `_redirect`, want de client mag niet op een emoji sniffen."""
    zonder = [f"{n}:{r}" for n, r, staart in _action_fetches()
              if "ok')!=='0'" not in staart and "ok')==='0'" not in staart
              and "eigering(" not in staart.lower()]
    assert zonder == [], f"fetch zonder weiger-markering: {zonder}"


def test_de_klasse_is_niet_leeg():
    """Een ratchet die niets telt bewaakt niets — dit is de validatie van het meetinstrument."""
    assert len(list(_action_fetches())) >= 5


def test_ook_de_slapende_oppervlakken_zijn_gedekt():
    """`noochie` slaapt en de callbar staat sinds 11 aug uit de app-shell. Ze zijn tóch gedekt:
    een scherm dat wakker wordt, hoort de bug niet mee terug te brengen."""
    namen = {n for n, _r, _s in _action_fetches()}
    assert {"noochie.py", "callbar.py"} <= namen
