"""Tests voor de haal_pagina-skill. Geen netwerk: `haal` is geïnjecteerd."""
from __future__ import annotations

import pytest

from nooch_village import safe_fetch
from nooch_village.skills_impl.haal_pagina import HaalPaginaSkill, zoek_treffers

_PAGINA = {
    "url": "https://nooch.earth/pages/frequently_asked_questions",
    "status": 200,
    "titel": "FAQ — Nooch",
    "tekst": "FAQ — Nooch\n"
             "Waar zijn de schoenen van gemaakt?\n"
             "Onze materialen zijn natural en plantaardig.\n"
             "We gebruiken geen leer.\n"
             "Hoe zit het met verzending?\n"
             "We verzenden vanuit Portugal.\n",
}


def _vast(_url, **_kw):
    return dict(_PAGINA)


def test_zonder_term_geeft_de_tekst():
    uit = HaalPaginaSkill(haal=_vast).run({"url": _PAGINA["url"]})
    assert uit["ok"] is True
    assert uit["titel"] == "FAQ — Nooch"
    assert "natural" in uit["tekst"]
    assert uit["afgekapt"] is False


def test_max_tekens_kapt_af_en_zegt_dat():
    # 200 is de ondergrens van max_tekens, dus de pagina moet daar ruim overheen om af te kappen.
    lang = dict(_PAGINA, tekst="Lange lap tekst. " * 100)
    uit = HaalPaginaSkill(haal=lambda *_a, **_k: dict(lang)).run(
        {"url": _PAGINA["url"], "max_tekens": 200})
    assert uit["afgekapt"] is True
    assert len(uit["tekst"]) == 200
    assert uit["tekens_totaal"] > 200


def test_korte_pagina_wordt_niet_als_afgekapt_gemeld():
    uit = HaalPaginaSkill(haal=_vast).run({"url": _PAGINA["url"], "max_tekens": 200})
    assert uit["afgekapt"] is False
    assert uit["tekst"] == _PAGINA["tekst"]


def test_term_geeft_de_regel_met_context():
    uit = HaalPaginaSkill(haal=_vast).run({"url": _PAGINA["url"], "term": "natural"})
    assert uit["aantal_treffers"] == 1
    t = uit["treffers"][0]
    assert "natural" in t["regel"]
    # de kop erboven reist mee als context, zodat de mens de sectie herkent
    assert "Waar zijn de schoenen van gemaakt?" in t["voor"]
    assert "We gebruiken geen leer." in t["na"]


def test_term_is_hoofdletterongevoelig():
    uit = HaalPaginaSkill(haal=_vast).run({"url": _PAGINA["url"], "term": "NATURAL"})
    assert uit["aantal_treffers"] == 1


def test_term_niet_gevonden_is_no_data_geen_fout():
    """no_data ≠ nul: de pagina is opgehaald, de term staat er niet. Dat is een antwoord."""
    uit = HaalPaginaSkill(haal=_vast).run({"url": _PAGINA["url"], "term": "polyurethaan"})
    assert uit["ok"] is True
    assert uit["aantal_treffers"] == 0
    assert uit["no_data"] is True
    assert "polyurethaan" in uit["reason"]
    assert "error" not in uit


def test_url_verplicht():
    assert "error" in HaalPaginaSkill(haal=_vast).run({})
    assert "error" in HaalPaginaSkill(haal=_vast).run({"url": "   "})


def test_geweigerde_url_faalt_closed_en_is_niet_tijdelijk():
    def _weiger(_url, **_kw):
        raise safe_fetch.FetchGeweigerd("privé-adres")

    uit = HaalPaginaSkill(haal=_weiger).run({"url": "http://127.0.0.1/geheim"})
    assert "error" in uit and uit["tijdelijk"] is False
    assert "ok" not in uit


def test_tijdelijke_fout_wordt_als_tijdelijk_gemeld():
    def _429(_url, **_kw):
        raise safe_fetch.FetchMislukt("de pagina gaf HTTP 429", status=429)

    uit = HaalPaginaSkill(haal=_429).run({"url": _PAGINA["url"]})
    assert "error" in uit
    assert uit["tijdelijk"] is True
    assert uit["status"] == 429


def test_onverwachte_fout_wordt_gevangen():
    def _boem(_url, **_kw):
        raise ValueError("iets raars")

    uit = HaalPaginaSkill(haal=_boem).run({"url": _PAGINA["url"]})
    assert "error" in uit and "ValueError" in uit["error"]


def test_max_treffers_begrenst():
    veel = {"url": "https://x.test", "status": 200, "titel": "x",
            "tekst": "\n".join(f"regel {i} met natural erin" for i in range(50))}
    uit = HaalPaginaSkill(haal=lambda *_a, **_k: dict(veel)).run(
        {"url": "https://x.test", "term": "natural", "max_treffers": 3})
    assert uit["aantal_treffers"] == 3


def test_zoek_treffers_is_puur():
    tref = zoek_treffers("a\nb natural\nc", "natural", context_regels=1, max_treffers=5)
    assert len(tref) == 1
    assert tref[0]["voor"] == ["a"] and tref[0]["na"] == ["c"]
    assert tref[0]["regelnummer"] == 2


def test_skill_metadata_compleet():
    """De prep-LLM leest deze velden om een payload te vormen; ontbreken ze, dan gokt hij."""
    s = HaalPaginaSkill()
    assert s.name == "haal_pagina"
    assert s.side_effect_free is True
    assert "url" in s.required_payload
    assert s.input_schema and s.output_schema and s.description
