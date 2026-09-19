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






def test_base_skill_cost_default_is_none():
    """De Skill base-class heeft cost=None — subklassen moeten hem overschrijven."""
    from nooch_village.skills import Skill
    assert Skill.cost is None
