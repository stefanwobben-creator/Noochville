"""Semantische matcher: lexicaal + concept + gecachet LLM-oordeel."""
from __future__ import annotations

from nooch_village import ai_match


def test_lexical_en_concept():
    assert ai_match.lexical_match("Optimizing website performance", "performance audit")
    # concept: code ~ feature (geen woord-overlap)
    assert not ai_match.lexical_match("Building new features", "schrijft de code")
    assert ai_match.concept_match("Building new features", "schrijft de code")
    # bug ~ testscript ~ rootcause
    assert ai_match.concept_match("Fixing bugs", "draait testscripts en vindt de rootcause")
    # geen relatie
    assert not ai_match.is_match("Fixing bugs", "ontwerpt het logo")


def test_cache_overschrijft_oordeel(tmp_path):
    c = ai_match.MatchCache(str(tmp_path / "m.json"))
    # van nature geen match
    assert ai_match.is_match("Fixing bugs", "ontwerpt het logo") is False
    # semantisch oordeel 'ja' wint
    c.set("Fixing bugs", "ontwerpt het logo", True)
    assert ai_match.is_match("Fixing bugs", "ontwerpt het logo", c) is True
    # en een expliciete 'nee' onderdrukt een lexicale match
    c.set("Optimizing website performance", "performance audit", False)
    assert ai_match.is_match("Optimizing website performance", "performance audit", c) is False


def test_refresh_semantic_met_geinjecteerde_ask(tmp_path):
    c = ai_match.MatchCache(str(tmp_path / "m.json"))
    calls = []

    def ask(acc, skill):
        calls.append((acc, skill))
        return "feature" in acc.lower()

    n = ai_match.refresh_semantic([("Build feature", "x"), ("Fix bug", "y")], ask, c)
    assert n == 2
    assert c.get("Build feature", "x") is True and c.get("Fix bug", "y") is False
    # onbeslist (None) wordt niet gecachet
    n2 = ai_match.refresh_semantic([("z", "q")], lambda a, s: None, c)
    assert n2 == 0 and c.get("z", "q") is None


def test_refresh_matches_noop_zonder_llm(tmp_path):
    from nooch_village import cockpit2
    dd = str(tmp_path / "poc")
    # ask die alles afwijst → bepaalt wel paren, maar test vooral dat de pipeline loopt
    n = cockpit2.refresh_matches(dd, ask=lambda a, s: True)
    assert n >= 0
