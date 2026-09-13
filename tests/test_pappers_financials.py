"""Tests voor PappersFinancialsSkill. Geen netwerk: requests.get is gemockt."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nooch_village.skills_impl.pappers_financials import (
    PappersFinancialsSkill, _haal_omzetreeks, _trend, _get,
)


def _ctx(key="test-sentinel-key"):
    return SimpleNamespace(settings=({"PAPPERS_API_KEY": key} if key else {}))


class _FakeResp:
    def __init__(self, data, status_code=200, text=""):
        self._data = data
        self.status_code = status_code
        self.text = text or str(data)[:200]

    def json(self):
        return self._data


_VEJA_ZOEK = {"resultats": [
    {"nom_entreprise": "VEJA", "siren": "482711220"},
    {"nom_entreprise": "VEJA STORE PARIS", "siren": "999888777"},
]}

_VEJA_ENTREPRISE = {
    "nom_entreprise": "VEJA",
    "finances": [
        {"annee": "2021", "chiffre_affaires": 100_000_000},
        {"annee": "2022", "chiffre_affaires": 130_000_000},
        {"annee": "2023", "chiffre_affaires": 140_000_000},
        {"annee": "2024", "chiffre_affaires": 101_000_000},
    ],
}


# ── pure functies ─────────────────────────────────────────────────────────────

def test_haal_omzetreeks_herkent_de_hoofdvorm():
    jaren, ontbreekt = _haal_omzetreeks(_VEJA_ENTREPRISE)
    assert ontbreekt == []
    assert jaren[0] == {"jaar": "2021", "omzet": 100_000_000.0}
    assert jaren[-1] == {"jaar": "2024", "omzet": 101_000_000.0}


def test_haal_omzetreeks_faalt_zichtbaar_bij_onbekend_schema():
    jaren, ontbreekt = _haal_omzetreeks({"iets_anders": [1, 2, 3]})
    assert jaren == []
    assert ontbreekt and "iets_anders" in ontbreekt[0]


def test_haal_omzetreeks_faalt_zichtbaar_bij_reeks_zonder_herkend_veld():
    jaren, ontbreekt = _haal_omzetreeks({"finances": [{"onbekend_veld": 1}]})
    assert jaren == []
    assert ontbreekt and "onbekend_veld" in ontbreekt[0]


def test_trend_piek_en_jaar_op_jaar():
    jaren, _ = _haal_omzetreeks(_VEJA_ENTREPRISE)
    t = _trend(jaren)
    assert t["piek_jaar"] == "2023"
    assert t["sinds_piek_pct"] < 0                  # daling t.o.v. de piek
    assert t["jaar_op_jaar_pct"] < 0


def test_trend_met_één_jaar_is_leeg():
    assert _trend([{"jaar": "2024", "omzet": 100}]) == {}


# ── run() ──────────────────────────────────────────────────────────────────────

def test_zonder_key_faalt_closed():
    with pytest.raises(RuntimeError, match="PAPPERS_API_KEY"):
        PappersFinancialsSkill().run({"bedrijf": "Veja"}, _ctx(key=""))


def test_zonder_bedrijf_of_siren_geeft_foutmelding():
    uit = PappersFinancialsSkill().run({}, _ctx())
    assert "error" in uit


def test_happy_path_zoekt_en_haalt_financien_op():
    def _fake_get(url, params=None, timeout=None):
        if "recherche" in url:
            return _FakeResp(_VEJA_ZOEK)
        return _FakeResp(_VEJA_ENTREPRISE)

    with patch("nooch_village.skills_impl.pappers_financials.requests.get", _fake_get):
        uit = PappersFinancialsSkill().run({"bedrijf": "Veja"}, _ctx())

    assert uit["ok"] is True
    assert uit["siren"] == "482711220"
    assert uit["bedrijf"] == "VEJA"
    assert len(uit["jaren"]) == 4
    assert uit["trend"]["piek_jaar"] == "2023"
    assert uit["kandidaten"] == [{"naam": "VEJA STORE PARIS", "siren": "999888777"}]
    assert "VEJA" in uit["text"] and "2023" in uit["text"]


def test_direct_siren_slaat_zoeken_over():
    calls = []

    def _fake_get(url, params=None, timeout=None):
        calls.append(url)
        return _FakeResp(_VEJA_ENTREPRISE)

    with patch("nooch_village.skills_impl.pappers_financials.requests.get", _fake_get):
        uit = PappersFinancialsSkill().run({"siren": "482711220"}, _ctx())

    assert uit["ok"] is True
    assert "kandidaten" not in uit
    assert all("recherche" not in c for c in calls)


def test_geen_resultaat_is_no_data():
    with patch("nooch_village.skills_impl.pappers_financials.requests.get",
               lambda *a, **k: _FakeResp({"resultats": []})):
        uit = PappersFinancialsSkill().run({"bedrijf": "Onbestaand BV"}, _ctx())
    assert uit["no_data"] is True
    assert "Onbestaand BV" in uit["reason"]


def test_gevonden_maar_geen_jaarrekening_is_no_data():
    def _fake_get(url, params=None, timeout=None):
        if "recherche" in url:
            return _FakeResp(_VEJA_ZOEK)
        return _FakeResp({"nom_entreprise": "VEJA", "finances": []})

    with patch("nooch_village.skills_impl.pappers_financials.requests.get", _fake_get):
        uit = PappersFinancialsSkill().run({"bedrijf": "Veja"}, _ctx())
    assert uit["no_data"] is True
    assert "no filed annual accounts" in uit["reason"]


def test_onherkend_schema_geeft_zichtbare_fout_geen_stille_lege_reeks():
    def _fake_get(url, params=None, timeout=None):
        if "recherche" in url:
            return _FakeResp(_VEJA_ZOEK)
        return _FakeResp({"nom_entreprise": "VEJA", "iets_nieuws": []})

    with patch("nooch_village.skills_impl.pappers_financials.requests.get", _fake_get):
        uit = PappersFinancialsSkill().run({"bedrijf": "Veja"}, _ctx())
    assert "error" in uit
    assert "documentation" in uit["error"]


def test_http_fout_wordt_gemaskeerd_en_url_lekt_niet():
    def _fake_get(url, params=None, timeout=None):
        return _FakeResp({"message": "invalid api_token"}, status_code=403,
                          text="invalid api_token=SECRET1234567890")
    with patch("nooch_village.skills_impl.pappers_financials.requests.get", _fake_get):
        uit = PappersFinancialsSkill().run({"bedrijf": "Veja"}, _ctx())
    assert "error" in uit
    assert "SECRET1234567890" not in uit["error"]


def test_429_gevolgd_door_200_levert_alsnog_data_via_get():
    calls = {"n": 0}

    def _fake_get(url, params=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakeResp({}, status_code=429, text="rate limited")
        return _FakeResp(_VEJA_ZOEK)

    with patch("nooch_village.skills_impl.pappers_financials.requests.get", _fake_get), \
         patch("nooch_village.skills_impl.pappers_financials.time.sleep"):
        data = _get("https://api.pappers.fr/v2/recherche", {"api_token": "k", "q": "Veja"})
    assert calls["n"] == 2
    assert data == _VEJA_ZOEK


def test_permanente_4xx_stopt_direct_zonder_retries():
    calls = {"n": 0}

    def _fake_get(url, params=None, timeout=None):
        calls["n"] += 1
        return _FakeResp({}, status_code=403, text="forbidden")

    with patch("nooch_village.skills_impl.pappers_financials.requests.get", _fake_get), \
         patch("nooch_village.skills_impl.pappers_financials.time.sleep"):
        with pytest.raises(RuntimeError):
            _get("https://api.pappers.fr/v2/recherche", {"api_token": "k"})
    assert calls["n"] == 1                     # geen retries op een permanente fout


def test_skill_metadata_compleet():
    s = PappersFinancialsSkill()
    assert s.name == "pappers_financials"
    assert s.required_env == ("PAPPERS_API_KEY",)
    assert s.side_effect_free is True
    assert s.required_payload == (("bedrijf", "siren"),)
    assert s.input_schema and s.output_schema and s.description
