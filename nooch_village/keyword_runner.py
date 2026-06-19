"""Adapter die KeywordsEverywhereSkill omzet naar de runner-signatuur van measure_batch."""
from __future__ import annotations
from typing import Callable


def make_keywords_runner(skill, context) -> Callable[[list[str], str, str], list[dict]]:
    """Geeft een runner terug met signatuur (candidates, country, data_source) -> list[dict].

    De runner roept skill.run aan met het correcte payload-formaat en geeft de
    per-keyword lijst terug zoals de skill die normaliseert (keyword/vol/cpc/competition/trend).
    Geen netwerk, geen API-key lookup hier — dat doet de skill via context.
    """
    def runner(candidates: list[str], country: str, data_source: str) -> list[dict]:
        result = skill.run(
            {"kw": candidates, "country": country, "data_source": data_source},
            context,
        )
        return result["keywords"]

    return runner
