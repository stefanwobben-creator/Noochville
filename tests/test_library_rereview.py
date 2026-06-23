"""Tests voor her-review van geëscaleerde bibliotheek-termen. Thread-vrij, geen LLM."""
from __future__ import annotations

from types import SimpleNamespace

from nooch_village.library import Library
from nooch_village.lexicon import Lexicon
from nooch_village.seeds import _LEXICON_SEED
from nooch_village.library_rereview import rereview_escalated

_DEMAND = {"signal": "positive", "volume": 5000}


def _ctx(tmp_path):
    lex = Lexicon(str(tmp_path / "lexicon.json"))
    lex.seed(_LEXICON_SEED)
    return SimpleNamespace(lexicon=lex)


def _library(tmp_path):
    lib = Library(str(tmp_path / "library.json"))
    lib.curate("leather free shoes", "escalated", "leather is uitgesloten", evidence=_DEMAND)
    lib.curate("sustainable sneakers", "escalated", "geen signaal", evidence=_DEMAND)
    lib.curate("vegan shoes", "escalated", "verborgen conflict", evidence=_DEMAND)
    lib.curate("blue running shoes", "escalated", "off-mission", evidence=_DEMAND)
    lib.curate("duurzame sokken", "escalated", "geen vraag", evidence={"signal": "flat"})
    lib.curate("plastic shoes", "forbidden", "plastic", evidence={})   # niet escalated
    return lib


def test_leather_free_en_sustainable_worden_approved(tmp_path):
    lib = _library(tmp_path)
    res = rereview_escalated(lib, _ctx(tmp_path))
    assert "leather free shoes" in res["approved"]
    assert "sustainable sneakers" in res["approved"]
    assert lib.status("leather free shoes")["status"] == "approved"
    assert lib.status("sustainable sneakers")["status"] == "approved"


def test_vegan_en_off_mission_blijven_escalated(tmp_path):
    lib = _library(tmp_path)
    rereview_escalated(lib, _ctx(tmp_path))
    assert lib.status("vegan shoes")["status"] == "escalated"
    assert lib.status("blue running shoes")["status"] == "escalated"


def test_kern_zonder_vraag_blijft_escalated(tmp_path):
    lib = _library(tmp_path)
    rereview_escalated(lib, _ctx(tmp_path))
    assert lib.status("duurzame sokken")["status"] == "escalated"


def test_niet_escalated_termen_blijven_ongemoeid(tmp_path):
    lib = _library(tmp_path)
    rereview_escalated(lib, _ctx(tmp_path))
    assert lib.status("plastic shoes")["status"] == "forbidden"


def test_dry_run_schrijft_niets(tmp_path):
    lib = _library(tmp_path)
    res = rereview_escalated(lib, _ctx(tmp_path), apply=False)
    assert "leather free shoes" in res["approved"]            # wordt wel gerapporteerd
    assert lib.status("leather free shoes")["status"] == "escalated"   # maar niet geschreven


def test_telling_klopt(tmp_path):
    lib = _library(tmp_path)
    res = rereview_escalated(lib, _ctx(tmp_path))
    assert res["total"] == len(res["approved"]) + len(res["forbidden"]) + res["unchanged"]
    assert res["total"] == 5      # vijf escalated termen; de forbidden telt niet mee
