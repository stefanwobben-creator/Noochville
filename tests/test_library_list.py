"""Tests voor LibraryListSkill — vijf scenario's, geen threads."""
from __future__ import annotations
from types import SimpleNamespace
import pytest
from nooch_village.skills_impl.library_skills import LibraryListSkill
from nooch_village.library import Library


def _make_context(data: dict, tmp_path) -> SimpleNamespace:
    path = str(tmp_path / "library.json")
    lib = Library(path)
    lib._data = data
    return SimpleNamespace(library=lib)


def test_lege_library(tmp_path):
    ctx = _make_context({}, tmp_path)
    result = LibraryListSkill().run({}, ctx)
    assert result["terms"] == []
    assert result["count"] == 0


def test_default_filtert_alleen_approved_en_insight_statement(tmp_path):
    data = {
        "plastic-free":    {"status": "approved",           "rationale": ""},
        "vegan schoenen":  {"status": "escalated",          "rationale": ""},
        "nooches":         {"status": "forbidden",          "rationale": ""},
        "duurzaam leven":  {"status": "insight_statement",  "rationale": ""},
    }
    ctx = _make_context(data, tmp_path)
    result = LibraryListSkill().run({}, ctx)
    terms = {t["term"] for t in result["terms"]}
    assert "plastic-free" in terms
    assert "duurzaam leven" in terms
    assert "vegan schoenen" not in terms
    assert "nooches" not in terms
    assert result["count"] == 2


def test_expliciete_statuses_filter(tmp_path):
    data = {
        "noosh":          {"status": "forbidden",  "rationale": ""},
        "plastic-free":   {"status": "approved",   "rationale": ""},
        "earth shoes":    {"status": "forbidden",  "rationale": ""},
    }
    ctx = _make_context(data, tmp_path)
    result = LibraryListSkill().run({"statuses": ["forbidden"]}, ctx)
    terms = {t["term"] for t in result["terms"]}
    assert "noosh" in terms
    assert "earth shoes" in terms
    assert "plastic-free" not in terms
    assert result["count"] == 2


def test_locale_filter(tmp_path):
    data = {
        "plastic-free":     {"status": "approved", "rationale": "", "locale": "en"},
        "plasticvrij":      {"status": "approved", "rationale": "", "locale": "nl"},
        "duurzaam":         {"status": "approved", "rationale": ""},  # locale ontbreekt
    }
    ctx = _make_context(data, tmp_path)
    result = LibraryListSkill().run({"locale": "nl"}, ctx)
    terms = {t["term"] for t in result["terms"]}
    assert "plasticvrij" in terms
    assert "plastic-free" not in terms
    assert "duurzaam" not in terms
    assert result["count"] == 1


def test_ontbrekende_nieuwe_velden_geen_crash(tmp_path):
    data = {
        "plastic-free": {
            "status": "approved",
            "rationale": "missie-kern",
            "evidence": {"signal": "positive"},
            "by": "librarian",
            "date": "2026-06-13",
            # locale, concept_id, gemet_id ontbreken — vóór migratie
        }
    }
    ctx = _make_context(data, tmp_path)
    result = LibraryListSkill().run({}, ctx)
    assert result["count"] == 1
    term = result["terms"][0]
    assert term["term"] == "plastic-free"
    assert term["locale"] is None
    assert term["concept_id"] is None
    assert term["gemet_id"] is None


# --- Library.curate / link_concept / keywords_for_concept ---

def _lib(tmp_path) -> Library:
    return Library(str(tmp_path / "library.json"))


def test_curate_behoudt_concept_id(tmp_path):
    lib = _lib(tmp_path)
    lib.curate("plasticvrij", "approved", "missie-kern")
    lib.link_concept("plasticvrij", "plastic_free")
    lib.curate("plasticvrij", "forbidden", "toch niet")
    assert lib.status("plasticvrij")["concept_id"] == "plastic_free"


def test_link_concept_zet_concept_id(tmp_path):
    lib = _lib(tmp_path)
    lib.curate("plasticvrij", "approved")
    entry = lib.link_concept("plasticvrij", "plastic_free")
    assert entry["concept_id"] == "plastic_free"
    assert lib.status("plasticvrij")["concept_id"] == "plastic_free"


def test_link_concept_onbekend_woord_raist_key_error(tmp_path):
    lib = _lib(tmp_path)
    with pytest.raises(KeyError):
        lib.link_concept("onbekend", "plastic_free")


def test_keywords_for_concept(tmp_path):
    lib = _lib(tmp_path)
    lib.curate("plasticvrij", "approved")
    lib.curate("plastic-free", "approved")
    lib.curate("veganistisch", "approved")
    lib.link_concept("plasticvrij", "plastic_free")
    lib.link_concept("plastic-free", "plastic_free")
    result = lib.keywords_for_concept("plastic_free")
    assert set(result) == {"plasticvrij", "plastic-free"}
    assert "veganistisch" not in result
