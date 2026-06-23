"""Tests voor de zelf-overbodigheid-beslisser (pioniers-reflectie, R1). Puur, thread-vrij."""
from __future__ import annotations

from nooch_village.redundancy import accountability_covered, is_redundant


def test_covered_bij_genoeg_overlap():
    assert accountability_covered(
        "monitor visitor traffic weekly",
        ["monitor visitor traffic on the site"]) is True


def test_niet_covered_bij_te_weinig_overlap():
    # geen gedeelde inhoud
    assert accountability_covered(
        "monitor visitor traffic", ["write the daily bulletin"]) is False
    # slechts één gedeeld token (monitor) — onder de drempel
    assert accountability_covered(
        "monitor visitor traffic", ["monitor the budget"]) is False


def test_lege_of_triviale_accountability_dekt_nooit():
    assert accountability_covered("", ["monitor visitor traffic"]) is False
    assert accountability_covered("de en op", ["monitor visitor traffic"]) is False


def test_redundant_als_alles_gedekt():
    my = ["monitor visitor traffic weekly", "report findings to the founder"]
    others = {
        "watcher": ["monitor visitor traffic on the site"],
        "scribe":  ["report findings and write summaries for the founder"],
    }
    red, coverers = is_redundant(my, others)
    assert red is True
    assert coverers == ["scribe", "watcher"]   # gesorteerd


def test_niet_redundant_als_een_accountability_ongedekt():
    my = ["monitor visitor traffic", "ground keywords in academic literature"]
    others = {"watcher": ["monitor visitor traffic on the site"]}
    red, coverers = is_redundant(my, others)
    assert red is False
    assert coverers == []


def test_geen_accountabilities_niet_redundant():
    assert is_redundant([], {"x": ["anything at all here"]}) == (False, [])
