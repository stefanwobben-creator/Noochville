"""KeywordsEverywhere-volume in de Librarian-beoordeling: boven de drempel auto-approve,
missie-risico's altijd mens-gated (escalate/reject). LLM gemockt op None (heuristiek-pad)."""
from __future__ import annotations
from types import SimpleNamespace
from unittest.mock import patch

from nooch_village.skills_impl.library_skills import KeywordReviewSkill


class _Lib:
    def __init__(self, data=None):
        self._d = data or {}
    def status(self, w):
        return self._d.get(w.lower())


def _ctx(settings=None, data=None):
    return SimpleNamespace(settings=settings or {}, library=_Lib(data), lexicon=None)


def _review(word, demand, ctx):
    # Geen netwerk: forceer het heuristiek-pad door de LLM uit te zetten.
    with patch("nooch_village.skills_impl.library_skills.reason", return_value=None):
        return KeywordReviewSkill().run({"word": word, "demand": demand}, ctx)


def test_hoog_volume_keurt_automatisch_goed():
    res = _review("trail running shoes", {"volume": 500}, _ctx())
    assert res["decision"] == "approve"
    assert res["basis"] == "volume"
    assert "500" in res["reason"]


def test_laag_volume_valt_terug_op_heuristiek():
    res = _review("trail running shoes", {"volume": 5}, _ctx())
    assert res["decision"] == "escalate"          # geen missie-kern, geen drempel → mens
    assert res["basis"] != "volume"


def test_risico_woord_blijft_mens_gated_ondanks_volume():
    res = _review("vegan sneakers", {"volume": 99999}, _ctx())
    assert res["decision"] == "escalate"          # 'vegan' is RISK → nooit auto-approve
    assert res["basis"] != "volume"


def test_verboden_claim_blijft_reject_ondanks_volume():
    res = _review("100% duurzaam", {"volume": 99999}, _ctx())
    assert res["decision"] == "reject"
    assert res["basis"] != "volume"


def test_drempel_is_instelbaar():
    ctx = _ctx(settings={"ke_auto_approve_volume": "1000"})
    res = _review("trail running shoes", {"volume": 500}, ctx)
    assert res["decision"] != "approve" or res["basis"] != "volume"   # 500 < 1000 → niet via volume


def test_drempel_nul_zet_auto_approve_uit():
    ctx = _ctx(settings={"ke_auto_approve_volume": "0"})
    res = _review("trail running shoes", {"volume": 99999}, ctx)
    assert res["basis"] != "volume"               # uit → volume keurt nooit goed


def test_gsc_impressies_tellen_niet_als_volume():
    # 'interest' (GSC-impressies) mag NIET als echt zoekvolume gelden voor auto-approve.
    res = _review("trail running shoes", {"interest": 99999}, _ctx())
    assert res["basis"] != "volume"
