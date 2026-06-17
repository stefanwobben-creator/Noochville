"""Wachter: elke skill die een governance-record toekent, moet bestaan in de
SkillRegistry. Een record dat een niet-bestaande skill toekent (spook-skill
of typefout) maakt deze test rood."""
from __future__ import annotations
from nooch_village.village import Village


def test_toegekende_skills_bestaan_in_registry():
    v = Village(heartbeat_seconds=0)
    registry = v.registry
    spook = []
    for record in v.records.all():
        for skill in record.definition.skills:
            if registry.get(skill) is None:
                spook.append(f"{record.id}:{skill}")
    assert not spook, (
        "Records kennen skills toe die niet in de registry bestaan: "
        + ", ".join(spook)
    )
