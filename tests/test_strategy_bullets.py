"""Simpele strategie-bullets onder de gewone kop 'Strategie' (bv. de Mother-Earth-principes):
titel bold, uitleg gewoon (markdown). De placeholder-secties verschijnen alleen bij een RIJKE
strategie (zoals Nooch), niet bij een bullets-only entry."""
from __future__ import annotations

from nooch_village import cockpit2
from nooch_village.views.strategy import _strategy_tab_html


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return cockpit2._Stores(dd)


def test_strategie_bullets_onder_kop_strategie(tmp_path):
    st = _st(tmp_path)
    st.strategies.set("mother_earth", {"strategy": [
        "**Recycle Everything:** Close all loops; zero waste.",
        "**Adapt or Exit:** Evolve with changes or fail.",
    ]})
    html = _strategy_tab_html(st, st.records.get("mother_earth"), with_purpose_chain=False)
    assert "<h3>Strategie</h3>" in html
    assert "<strong>Recycle Everything:</strong> Close all loops" in html   # titel bold, uitleg gewoon
    assert "Adapt or Exit" in html
    # geen eigen sub-koppen (Principles/Beliefs) en geen placeholders bij een bullets-only entry
    assert "Principles" not in html and "<h3>Beliefs</h3>" not in html
    assert "Words that require evidence" not in html and "Current focus" not in html


def test_rijke_strategie_houdt_placeholders(tmp_path):
    st = _st(tmp_path)
    st.strategies.set("mother_earth", {"mission": "een missie-zin"})   # rijk veld → placeholders terug
    html = _strategy_tab_html(st, st.records.get("mother_earth"), with_purpose_chain=False)
    assert "Words that require evidence" in html and "Current focus" in html
