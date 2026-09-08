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
    assert "Connect sources" in html
    # elke bron staat er, met een aan/uit-knop
    assert "source_activate" in html
    assert "Shopify" in html and "Plausible" in html
    # zonder sleutels (lege testomgeving) → 'sleutel nodig' voor bronnen die sleutels vragen
    assert "key needed" in html
    # keyless bron toont dat expliciet
    assert "No key needed" in html


def test_activeren_en_deactiveren_zet_status(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "source_activate", {"source": ["gsc"], "next": ["/bronnen"]}, username="guest")
    assert cockpit2._Stores(dd).sources.active("gsc") is True
    cockpit2.dispatch(dd, "source_deactivate", {"source": ["gsc"], "next": ["/bronnen"]}, username="guest")
    assert cockpit2._Stores(dd).sources.active("gsc") is False


def test_een_onbekende_gebruiker_mag_geen_bron_aanzetten(tmp_path):
    """DEZE TEST STOND OMGEKEERD, en hij hield daarmee de bug op zijn plek.

    Hij heette `test_gast_mag_niet_activeren` en eiste dat `username="guest"` werd genegeerd,
    terwijl `username="stefan"` — een string die geen enkel account is — een externe bron mocht
    aanzetten. De handler deed letterlijk `if not src or c.username in (None, "guest")`, dus:
    weigert de guest (auth UIT, per definitie alles mag) en laat élke ingelogde naam door, ook
    een die nergens bestaat.

    Een bron aanzetten laat het HELE dorp bij elke pulse een externe API aanroepen met de sleutels
    van de organisatie. Dat is org-breed, dus de poort is nu `_anchor_gate`, dezelfde als bij
    persona-beheer. "Mens-gated" in de oude comment betekende "een mens en geen agent", niet
    "een ingelogde gebruiker" — elke cockpit-actie is per definitie mens-geïnitieerd."""
    dd = _dd(tmp_path)
    _nxt, msg = cockpit2.dispatch(dd, "source_activate",
                                  {"source": ["gsc"], "next": ["/bronnen"]},
                                  username="niemand@nergens.nl")
    assert "No access" in msg
    assert cockpit2._Stores(dd).sources.active("gsc") is False
