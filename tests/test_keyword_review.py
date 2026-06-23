"""Tests voor de Librarian keyword-review-heuristiek. Thread-vrij, geen LLM, geen netwerk."""
from __future__ import annotations

from types import SimpleNamespace

from nooch_village.lexicon import Lexicon
from nooch_village.seeds import _LEXICON_SEED
from nooch_village.skills_impl.library_skills import KeywordReviewSkill

_DEMAND = {"signal": "positive", "source": "keywords_everywhere", "volume": 5000}


def _ctx(tmp_path, seed=True):
    lex = Lexicon(str(tmp_path / "lexicon.json"))
    if seed:
        lex.seed(_LEXICON_SEED)
    return SimpleNamespace(lexicon=lex)


def _decide(word, ctx, demand=_DEMAND):
    return KeywordReviewSkill()._heuristic(word, demand, ctx)[0]


# ── Bug 1: Engelse missiewoorden worden nu herkend ────────────────────────────

def test_sustainable_wordt_goedgekeurd_met_vraag(tmp_path):
    assert _decide("sustainable sneakers", _ctx(tmp_path)) == "approve"


def test_sustainable_zonder_lexicon_valt_terug_en_escaleert(tmp_path):
    """Zonder Lexicon kent de baseline 'sustainable' niet → escalate. Bewijst dat het
    Lexicon de Engelse herkenning levert."""
    assert _decide("sustainable sneakers", _ctx(tmp_path, seed=False)) == "escalate"


def test_nederlandse_kern_blijft_werken(tmp_path):
    assert _decide("duurzame schoenen", _ctx(tmp_path)) == "approve"


# ── Bug 2: leather free / leervrij is missie-positief, geen leer-risico ────────

def test_leather_free_wordt_goedgekeurd(tmp_path):
    assert _decide("leather free shoes", _ctx(tmp_path)) == "approve"


def test_leervrij_wordt_goedgekeurd(tmp_path):
    assert _decide("leervrije schoenen", _ctx(tmp_path)) == "approve"


def test_echt_leer_escaleert_nog_steeds(tmp_path):
    assert _decide("leather shoes", _ctx(tmp_path)) == "escalate"


# ── Regressie + behouden standpunten ──────────────────────────────────────────

def test_plastic_free_blijft_werken_ondanks_koppelteken(tmp_path):
    """Lexicon heeft 'plastic-free' (koppelteken); de zoekterm gebruikt een spatie."""
    assert _decide("plastic free shoes", _ctx(tmp_path)) == "approve"


def test_vegan_blijft_escaleren_standpunt_behouden(tmp_path):
    assert _decide("vegan shoes", _ctx(tmp_path)) == "escalate"


def test_off_mission_escaleert(tmp_path):
    assert _decide("blue running shoes", _ctx(tmp_path)) == "escalate"


def test_kern_zonder_vraag_escaleert(tmp_path):
    geen_vraag = {"signal": "flat"}
    assert KeywordReviewSkill()._heuristic("sustainable shoes", geen_vraag, _ctx(tmp_path))[0] == "escalate"


# ── Wiring: run() geeft context door aan de heuristiek ────────────────────────

def test_run_geeft_context_door(tmp_path):
    ctx = _ctx(tmp_path)
    ctx.library = SimpleNamespace(status=lambda w: None)   # niets bekend → heuristiek beslist
    out = KeywordReviewSkill().run({"word": "sustainable sneakers", "demand": _DEMAND}, ctx)
    assert out["decision"] == "approve"
    assert out["basis"] == "heuristic"
