"""Test: elke geregistreerde skill declareert een concrete cost."""
from __future__ import annotations
import pytest
from nooch_village.village import Village

VALID_COSTS = {"free", "rate_limited", "credits"}


def test_all_registered_skills_have_concrete_cost():
    """Elke skill in de registry moet cost declareren — None is niet toegestaan."""
    v = Village(heartbeat_seconds=86400)
    missing = []
    invalid = []
    for name in v.registry.names():
        skill = v.registry.get(name)
        if skill.cost is None:
            missing.append(name)
        elif skill.cost not in VALID_COSTS:
            invalid.append(f"{name}: '{skill.cost}'")
    assert not missing, f"Skills zonder cost: {missing}"
    assert not invalid, f"Skills met onbekende cost-waarde: {invalid}"


def test_cost_values_are_valid_literals():
    """Smoke-test: importeer alle skills direct en check cost op class-niveau."""
    from nooch_village.skills_impl.plausible import PlausibleSkill
    from nooch_village.skills_impl.trends import TrendsSkill
    from nooch_village.skills_impl.field_note import FieldNoteSkill
    from nooch_village.skills_impl.bulletin_schrijven import BulletinSchrijvenSkill
    from nooch_village.skills_impl.budget import BudgetSkill
    from nooch_village.skills_impl.site_health import SiteHealthSkill
    from nooch_village.skills_impl.gsc import GscPerformanceSkill
    from nooch_village.skills_impl.gsc_report import GscReportSkill
    from nooch_village.skills_impl.ngram import NgramCultureSkill
    from nooch_village.skills_impl.openalex import OpenalexSkill
    from nooch_village.skills_impl.semantic_scholar import SemanticScholarSkill
    from nooch_village.skills_impl.openlibrary_search_inside import OpenlibrarySearchInsideSkill
    from nooch_village.skills_impl.library_skills import (
        LibraryListSkill, LibraryLookupSkill, KeywordReviewSkill,
    )
    skills = [
        PlausibleSkill, TrendsSkill, FieldNoteSkill, BulletinSchrijvenSkill,
        BudgetSkill, SiteHealthSkill, GscPerformanceSkill, GscReportSkill,
        NgramCultureSkill, OpenalexSkill, SemanticScholarSkill,
        OpenlibrarySearchInsideSkill, LibraryListSkill, LibraryLookupSkill,
        KeywordReviewSkill,
    ]
    for cls in skills:
        assert cls.cost in VALID_COSTS, (
            f"{cls.__name__}.cost = {cls.cost!r} — verwacht een van {VALID_COSTS}"
        )


def test_file_writing_skills_are_not_side_effect_free():
    """Skills die een bestand wegschrijven zijn niet side-effect-free."""
    from nooch_village.skills_impl.budget import BudgetSkill
    from nooch_village.skills_impl.field_note import FieldNoteSkill
    from nooch_village.skills_impl.bulletin_schrijven import BulletinSchrijvenSkill
    for cls in (BudgetSkill, FieldNoteSkill, BulletinSchrijvenSkill):
        assert cls.side_effect_free is False, (
            f"{cls.__name__}.side_effect_free moet False zijn (schrijft bestanden)"
        )


def test_base_skill_cost_default_is_none():
    """De Skill base-class heeft cost=None — subklassen moeten hem overschrijven."""
    from nooch_village.skills import Skill
    assert Skill.cost is None
