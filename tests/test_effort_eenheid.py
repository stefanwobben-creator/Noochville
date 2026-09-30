"""De eenheid van Effort wisselen verandert de weergave, niet de omvang.

De JS-toetsen staan in `tests/js/effort_eenheid.test.js` en laden het echte `nooch.js`; dit bestand
neemt ze mee in `pytest tests/` (zelfde doorgeefluik als `test_nooch_js_poller.py`, zonder node
slaat hij over). Daarnaast de server-kant: de render geeft de select zijn HUIDIGE eenheid mee, want
daarvandaan rekent de browser om — klopt die bij page-load niet, dan is de eerste wissel al fout.
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess

import pytest

from nooch_village import cockpit2
from nooch_village.views import projects as P

TEST_JS = pathlib.Path(__file__).resolve().parent / "js" / "effort_eenheid.test.js"
ROLE = "mother_earth__nooch__website_developer"


def test_de_omrekening_in_de_browser():
    node = shutil.which("node")
    if not node:
        pytest.skip("node niet geïnstalleerd — draai `node tests/js/effort_eenheid.test.js` met de hand")
    uit = subprocess.run([node, str(TEST_JS)], capture_output=True, text=True, timeout=60)
    assert uit.returncode == 0, f"JS-toetsen rood:\n{uit.stdout}\n{uit.stderr}"
    assert uit.stdout.count("  ok   ") >= 8, f"te weinig toetsen gedraaid:\n{uit.stdout}"


def _frag(tmp_path, number, unit):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    pid = cockpit2._Stores(dd).projects.create(ROLE, "T", "human")
    if number:
        cockpit2.dispatch(dd, "proj_seteffort",
                          {"pid": [pid], "number": [number], "unit": [unit], "next": ["/"]}, "guest")
    return P.render_project(cockpit2._Stores(dd), pid, csrf_token="TOK")


@pytest.mark.parametrize("number,unit,verwacht", [
    ("5", "dagen", "dagen"),      # 40 uur → toont 5 dagen
    ("3", "uren", "uren"),        # geen achtvoud → uren
    ("", "uren", "uren"),         # leeg → default uren
])
def test_de_select_kent_zijn_huidige_eenheid(tmp_path, number, unit, verwacht):
    frag = _frag(tmp_path, number, unit)
    assert f"name='unit' onchange='NV.effortEenheid(this)' data-unit='{verwacht}'" in frag
    assert f"value='{verwacht}' selected" in frag


def test_alleen_de_effort_select_rekent_om(tmp_path):
    """De andere rail-velden hebben geen "zelfde hoeveelheid, andere eenheid" en houden `_AUTOSAVE`."""
    frag = _frag(tmp_path, "5", "dagen")
    assert frag.count("NV.effortEenheid") == 1
    assert "name='number' value='5' min='0' step='any'" in frag   # step=1 zou 0,375 dag blokkeren


def test_een_fractie_dag_blijft_de_uren_die_het_waren(tmp_path):
    """Wat de browser na 3 uur → dagen verstuurt (0,375) landt weer als 3 uur."""
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    pid = cockpit2._Stores(dd).projects.create(ROLE, "T", "human")
    cockpit2.dispatch(dd, "proj_seteffort",
                      {"pid": [pid], "number": ["0.375"], "unit": ["dagen"], "next": ["/"]}, "guest")
    assert cockpit2._Stores(dd).projects.get(pid)["effort"] == {"hours": 3}
