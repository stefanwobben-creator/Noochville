"""Tests voor de site_watch-skill. Geen netwerk: `haal` is geïnjecteerd."""
from __future__ import annotations

from nooch_village import safe_fetch
from nooch_village.skills_impl.site_watch import SiteWatchSkill, vergelijk

_URL = "https://concurrent.example/prijzen"


class _Ctx:
    def __init__(self, data_dir):
        self.data_dir = str(data_dir)


def _pagina(tekst: str):
    return lambda *_a, **_k: {"url": _URL, "status": 200, "titel": "Prijzen", "tekst": tekst}


def test_eerste_keer_is_no_data_en_legt_basislijn_vast(tmp_path):
    uit = SiteWatchSkill(haal=_pagina("Schoen A: 90 euro\nSchoen B: 120 euro\n")).run(
        {"url": _URL}, _Ctx(tmp_path))
    assert uit["ok"] is True
    assert uit["eerste_keer"] is True
    assert uit["no_data"] is True
    assert "baseline" in uit["reason"]
    assert "error" not in uit


def test_tweede_keer_zonder_wijziging_is_no_data(tmp_path):
    skill = SiteWatchSkill(haal=_pagina("Schoen A: 90 euro\n"))
    ctx = _Ctx(tmp_path)
    skill.run({"url": _URL}, ctx)                            # basislijn
    uit = skill.run({"url": _URL}, ctx)                       # zelfde tekst nogmaals

    assert uit["ok"] is True
    assert uit["no_data"] is True
    assert "no change" in uit["reason"]
    assert uit["eerste_keer"] is False


def test_gewijzigde_pagina_meldt_toegevoegd_en_verwijderd(tmp_path):
    skill = SiteWatchSkill(haal=_pagina("Schoen A: 90 euro\nSchoen B: 120 euro\n"))
    ctx = _Ctx(tmp_path)
    skill.run({"url": _URL}, ctx)                            # basislijn

    skill._haal = _pagina("Schoen A: 75 euro\nSchoen B: 120 euro\nSchoen C: 150 euro\n")
    uit = skill.run({"url": _URL, "label": "Concurrent prijzen"}, ctx)

    assert uit["ok"] is True
    assert "no_data" not in uit
    assert uit["aantal_verwijderd"] == 1 and "Schoen A: 90 euro" in uit["verwijderd"]
    assert uit["aantal_toegevoegd"] == 2
    assert "Schoen A: 75 euro" in uit["toegevoegd"] and "Schoen C: 150 euro" in uit["toegevoegd"]
    assert "Concurrent prijzen" in uit["text"]


def test_derde_keer_vergelijkt_met_de_tweede_niet_met_de_eerste(tmp_path):
    """De basislijn schuift elke check op: een opgeloste wijziging blijft niet eeuwig meetellen."""
    skill = SiteWatchSkill(haal=_pagina("v1\n"))
    ctx = _Ctx(tmp_path)
    skill.run({"url": _URL}, ctx)                            # basislijn v1

    skill._haal = _pagina("v2\n")
    eerste_diff = skill.run({"url": _URL}, ctx)
    assert eerste_diff["toegevoegd"] == ["v2"] and eerste_diff["verwijderd"] == ["v1"]

    # Terug naar v1: t.o.v. v2 (de nieuwe basislijn) is dat weer een verschil, niet 'geen wijziging'.
    skill._haal = _pagina("v1\n")
    tweede_diff = skill.run({"url": _URL}, ctx)
    assert tweede_diff["toegevoegd"] == ["v1"] and tweede_diff["verwijderd"] == ["v2"]


def test_whitespace_only_verschil_telt_niet_als_wijziging(tmp_path):
    skill = SiteWatchSkill(haal=_pagina("Schoen A: 90 euro\n"))
    ctx = _Ctx(tmp_path)
    skill.run({"url": _URL}, ctx)

    skill._haal = _pagina("  Schoen A: 90 euro  \n\n")
    uit = skill.run({"url": _URL}, ctx)
    assert uit["no_data"] is True and "no change" in uit["reason"]


def test_geen_leesbare_tekst_is_no_data_zonder_data_dir_te_raken():
    uit = SiteWatchSkill(haal=_pagina("   \n  ")).run({"url": _URL}, None)
    assert uit["no_data"] is True
    assert "error" not in uit


def test_geen_data_dir_geeft_expliciete_fout(tmp_path):
    class _GeenDataDir:
        pass
    uit = SiteWatchSkill(haal=_pagina("iets")).run({"url": _URL}, _GeenDataDir())
    assert "error" in uit and "data_dir" in uit["error"]


def test_label_valt_terug_op_domein(tmp_path):
    skill = SiteWatchSkill(haal=_pagina("a\n"))
    ctx = _Ctx(tmp_path)
    skill.run({"url": _URL}, ctx)
    skill._haal = _pagina("b\n")
    uit = skill.run({"url": _URL}, ctx)
    assert uit["label"] == "concurrent.example"


def test_geweigerde_url_faalt_closed_en_is_niet_tijdelijk(tmp_path):
    def _weiger(_url, **_kw):
        raise safe_fetch.FetchGeweigerd("privé-adres")
    uit = SiteWatchSkill(haal=_weiger).run({"url": "http://127.0.0.1/geheim"}, _Ctx(tmp_path))
    assert "error" in uit and uit["tijdelijk"] is False
    assert "ok" not in uit


def test_tijdelijke_fout_wordt_als_tijdelijk_gemeld(tmp_path):
    def _429(_url, **_kw):
        raise safe_fetch.FetchMislukt("HTTP 429", status=429)
    uit = SiteWatchSkill(haal=_429).run({"url": _URL}, _Ctx(tmp_path))
    assert uit["tijdelijk"] is True and uit["status"] == 429


def test_url_verplicht():
    assert "error" in SiteWatchSkill(haal=_pagina("x")).run({}, None)


def test_validate_payload_weigert_placeholder():
    reden = SiteWatchSkill().validate_payload(
        {"url": "PLACEHOLDER — invullen met de URL uit stap 1"}, None)
    assert reden and "geen adres" in reden[0]


def test_validate_payload_accepteert_echte_url():
    assert SiteWatchSkill().validate_payload({"url": _URL}, None) == []


def test_vergelijk_is_puur_en_negeert_volgorde_niet_woordenlijst():
    toegevoegd, verwijderd = vergelijk("a\nb\nc", "a\nc\nd")
    assert toegevoegd == ["d"]
    assert verwijderd == ["b"]


def test_skill_metadata_compleet():
    s = SiteWatchSkill()
    assert s.name == "site_watch"
    assert s.side_effect_free is False          # schrijft data/site_watch/<hash>.json
    assert not s.required_env                   # geen sleutel nodig
    assert "url" in s.required_payload
    assert s.input_schema and s.output_schema and s.description
