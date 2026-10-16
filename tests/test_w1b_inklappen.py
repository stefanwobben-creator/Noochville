"""Lege vragen inklappen (W1b, besluit Stefan 15 oktober 2026).

Een pagina van /bom ZONDER feiten: één regel ("No facts yet, N questions open: …") en de volledige
vragen (What counts, Defer) achter een `<details>` "Show the questions". Een pagina met minstens één
feit blijft exact zoals hij was. Een link naar `#vraag-<k>` opent het blok: zie
`tests/js/vraag_anker.test.js` (directe URL én klik op dezelfde pagina)."""
from __future__ import annotations

import pathlib
import shutil
import subprocess

import pytest

from nooch_village import cockpit2
from nooch_village.views.wiki import _vragen_sectie

from tests.test_w1_antwoorden import _feit, _pagina


def _sectie(dd, aid, csrf="t", bewerk=True):
    st = cockpit2._Stores(dd)
    return _vragen_sectie(st, st.att.get(aid), csrf, bewerk)


def test_zonder_feiten_een_regel_met_de_juiste_aantallen(tmp_path):
    dd, aid = _pagina(tmp_path, [])
    h = _sectie(dd, aid)
    assert ("<p class='muted'>No facts yet, 7 questions open: Contains plastic?, Biobased?, Animal-derived, "
            "Dyes &amp; chemicals, CO2e per kg, Water per kg, Certificate. To add facts: type <b>/</b> in the "
            "text and choose <b>Bulk Import Facts</b>.</p>") in h
    blok = h.split("<details class='box-details' id='vragen-blok'><summary>Show the questions</summary>", 1)[1]
    assert blok.count("<div class='wiki-inline' id='vraag-") == 7
    assert blok.count("What counts:") == 7
    assert blok.count("value='vraag_uitstel'") == 7                      # Defer blijft bereikbaar
    assert "id='vraag-overig'" not in h


def test_een_lezer_krijgt_geen_bulk_import_zin(tmp_path):
    dd, aid = _pagina(tmp_path, [])
    h = _sectie(dd, aid, csrf="", bewerk=False)
    regel = h.split("<p class='muted'>", 1)[1].split("</p>", 1)[0]
    assert regel.startswith("No facts yet, 7 questions open:") and "Bulk Import" not in regel


def test_een_uitgestelde_vraag_telt_niet_als_open(tmp_path):
    dd, aid = _pagina(tmp_path, [])
    form = {"aid": [aid], "soort": ["materiaal"], "k": ["co2"], "tot": ["2099-01-01"], "next": ["/"]}
    msg = cockpit2.dispatch(dd, "vraag_uitstel", form, username="guest")[1]
    assert not msg.startswith("✗"), msg
    h = _sectie(dd, aid)
    assert "No facts yet, 6 questions open:" in h and "CO2e per kg" not in h.split("</p>", 1)[0].split("open:", 1)[1]
    assert " 1 deferred." in h


def test_met_een_feit_blijft_alles_zoals_het_was(tmp_path):
    """Exact de opbouw van vóór het inklappen: intro, zeven open vraagblokken, Other facts, de ingang."""
    dd, aid = _pagina(tmp_path, [_feit("F1", "Weight 540 g/m2")])
    h = _sectie(dd, aid)
    assert "No facts yet" not in h and "id='vragen-blok'" not in h
    assert h.count("<details class='box-details'>") == 1 and "<summary>How this works</summary>" in h
    assert h.startswith("<div class='c2-sec' id='vragen'><h2>Questions and facts</h2><p class='muted'>What this page should answer")
    assert h.count("<div class='wiki-inline' id='vraag-") == 8            # 7 vragen + Other facts
    assert "To add facts: type <b>/</b>" in h


def test_het_anker_opent_het_blok_in_javascript():
    node = shutil.which("node")
    if not node:
        pytest.skip("node niet geïnstalleerd")
    t = pathlib.Path(__file__).resolve().parent / "js" / "vraag_anker.test.js"
    uit = subprocess.run([node, str(t)], capture_output=True, text=True, timeout=60)
    assert uit.returncode == 0, uit.stdout + uit.stderr
    assert uit.stdout.count("  ok   ") == 6, uit.stdout
