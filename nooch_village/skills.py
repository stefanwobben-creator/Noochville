from __future__ import annotations
from abc import ABC, abstractmethod
import logging

log = logging.getLogger("village.skill")


class Skill(ABC):
    """Een echte vaardigheid. Inwoners krijgen skills geinjecteerd."""
    name: str = "abstract"
    needs_secret: bool = False
    description: str = ""

    @abstractmethod
    def run(self, payload: dict, context) -> dict:
        ...


class SkillRegistry:
    def __init__(self):
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill
        log.info("skill geregistreerd: %s", skill.name)

    def get(self, name: str):
        return self._skills.get(name)

    def names(self) -> list[str]:
        return list(self._skills)
