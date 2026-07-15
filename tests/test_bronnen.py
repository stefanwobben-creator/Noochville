"""Bronnen-aansluitscherm: toont elke DataSourceSkill met status + aan/uit; activeren zet sources.json."""
from __future__ import annotations

import os

from nooch_village import cockpit2


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def test_bronnen_toont_bronnen_met_status(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    html = cockpit2.render_bronnen(st, os.path.dirname(dd), csrf_token="t")
    assert "Bronnen aansluiten" in html
    # elke bron staat er, met een aan/uit-knop
    assert "source_activate" in html
    assert "Shopify" in html and "Plausible" in html
    # zonder sleutels (lege testomgeving) → 'sleutel nodig' voor bronnen die sleutels vragen
    assert "sleutel nodig" in html
    # keyless bron toont dat expliciet
    assert "Geen sleutel nodig" in html


def test_activeren_en_deactiveren_zet_status(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "source_activate", {"source": ["gsc"], "next": ["/bronnen"]}, username="stefan")
    assert cockpit2._Stores(dd).sources.active("gsc") is True
    cockpit2.dispatch(dd, "source_deactivate", {"source": ["gsc"], "next": ["/bronnen"]}, username="stefan")
    assert cockpit2._Stores(dd).sources.active("gsc") is False


def test_gast_mag_niet_activeren(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "source_activate", {"source": ["gsc"], "next": ["/bronnen"]}, username="guest")
    assert cockpit2._Stores(dd).sources.active("gsc") is False   # gast-actie genegeerd
