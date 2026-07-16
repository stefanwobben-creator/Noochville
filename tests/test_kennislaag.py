"""Inzichten-scherm (kennislaag): toont de Librarian's inzicht-kaarten uit notes.json."""
from __future__ import annotations

import os

from nooch_village import cockpit2
from nooch_village.notes_store import NotesStore
from nooch_village.insight import Insight


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def test_lege_kennislaag_toont_uitleg(tmp_path):
    dd = _dd(tmp_path)
    html = cockpit2.render_kennislaag(dd)
    assert "Inzichten" in html and "Nog geen inzichten" in html


def test_kennislaag_toont_kaarten(tmp_path):
    dd = _dd(tmp_path)
    store = NotesStore(os.path.join(dd, "notes.json"))
    store.add(Insight(id="i1", word="microplastics", claim="Sterk relevant; bronnen tonen milieu-impact.",
                      source="harry_hemp", grounding_count=3))
    store.add(Insight(id="i2", word="biobased", claim="Matig relevant in verpakkingscontext.",
                      source="harry_hemp", grounding_count=1))
    html = cockpit2.render_kennislaag(dd)
    assert "microplastics" in html and "biobased" in html
    assert "milieu-impact" in html
    assert "2 kaart" in html
    # meest-gegronde kaart staat bovenaan
    assert html.index("microplastics") < html.index("biobased")
