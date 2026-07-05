from __future__ import annotations
from abc import ABC, abstractmethod
import logging

log = logging.getLogger("village.skill")


class Skill(ABC):
    """Een echte vaardigheid. Inwoners krijgen skills geinjecteerd."""
    name: str = "abstract"
    needs_secret: bool = False
    description: str = ""

    required_env: tuple[str, ...] = ()
    """Env-/settings-sleutels die deze skill HARD nodig heeft. Ontbreekt er één, dan faalt
    de skill closed (geen verzonnen output). Het opstart-rapport leest dit zelfbeschrijvend
    uit, zodat je bij een run in één oogopslag ziet welke skills 'scherp staan'."""

    optional_env: tuple[str, ...] = ()
    """Env-/settings-sleutels die de skill VERBETEREN maar niet vereist zijn (hogere limiet,
    courtesy-mailto). Afwezig = de skill werkt nog, in beperkte modus."""

    cost: str | None = None
    """Puls-veiligheid en gemeten externe call-kost die de (toekomstige) puls-gate bewaakt.
    Verplicht voor elke concrete subklasse; None is niet toegestaan in productie.
      "free"         — veilig herhaald in de puls (lokale I/O, eigen API, geen quota)
      "rate_limited" — mag in de puls met backoff (onofficieel endpoint, throttling)
      "credits"      — gemeten/ongebonden kost, niet in de continue puls
    NB: kleine begrensde LLM-tokenkost wordt hier bewust niet gevlagd; daarom blijven
    field_note en bulletin_schrijven "free".
    """

    side_effect_free: bool = True
    """True = run() leest alleen en muteert geen state, intern noch extern.
    Schrijft de skill een bestand/record of doet hij een externe actie, dan False.
    """

    input_schema: str = ""
    """Beschrijving van de verwachte payload-sleutels (proza of pseudo-schema).
    Zie run()-docstring voor details.
    """

    output_schema: str = ""
    """Beschrijving van de teruggegeven dict-sleutels (proza of pseudo-schema).
    Zie run()-docstring voor details.
    """

    def available_metrics(self) -> list[str]:
        """De ruwe veldsleutels die deze skill oplevert (voor het catalogus-koppelscherm). Default
        leeg: een skill die géén meetbare velden declareert, levert niets te koppelen. Geen API-call."""
        return []

    @abstractmethod
    def run(self, payload: dict, context) -> dict:
        ...


class DataSourceSkill(Skill):
    """Een databron die de dag-puls generiek kan uitlezen: hij declareert zijn velden
    (`available_metrics`) én levert per veld een dagwaarde (`daily_values`). Zo hoeft de puls niets
    per bron/veld te hardcoden — hij itereert over de actieve DataSourceSkills en schrijft elk veld
    weg onder `<SOURCE>_<field>_day`.

    `SOURCE` = de catalogus-bron-id (= observation-`bron`), bewust los van `name` (de skill-id).
    """
    SOURCE: str = ""
    DEFAULT_FREQUENCY: str = "daily"

    def frequency(self, field: str) -> str:
        """Hoe vaak dit veld hoort te vullen ('daily' voor de huidige drie bronnen). De puls checkt
        per veld of er al een datapunt is voor de verwachte periode (idempotent + zelfherstellend),
        niet 'dagen sinds laatste ophaal'. Trage bronnen (Serpstat/Semantic Scholar) overschrijven dit
        later per veld; curator-override + koppeling aan de vers-drempel zijn een latere fase."""
        return self.DEFAULT_FREQUENCY

    def is_configured(self, context) -> bool:
        """Creds aanwezig? Generiek via `required_env` — geen per-bron hardcoding. Actief-maar-niet-
        geconfigureerd is een eigen zichtbare status (los van 'dood')."""
        import os
        return all((context.settings.get(k) or os.getenv(k)) for k in self.required_env)

    @abstractmethod
    def daily_values(self, context, datum: str) -> dict:
        """{field: value|None} voor de gedeclareerde velden op `datum` (fail-closed per veld: None bij
        ontbrekend/fout, geen mock). Sleutels ⊆ available_metrics()."""
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

    def all(self) -> list[Skill]:
        return list(self._skills.values())
