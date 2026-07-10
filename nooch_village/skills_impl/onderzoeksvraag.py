from __future__ import annotations
import re
from nooch_village.skills import Skill


class OnderzoeksvraagSkill(Skill):
    """Leidt uit een bevestigde trend-kaart één onderzoekbare 'waaróm'-vraag af.

    Zelfde patroon als verband_voorstel: één LLM-call, één regel terug, fail-closed.
    Produceert geen kennis en doet geen externe research; levert alleen de vraag die
    de scientist daarna met zijn bestaande grounding-skills kan onderzoeken.
    """
    name = "onderzoeksvraag"
    cost = "free"  # kleine begrensde LLM-tokenkost wordt bewust niet gevlagd
    side_effect_free = True
    description = "Leidt uit een bevestigde trend-kaart één onderzoeksvraag af naar de waaróm erachter."
    input_schema = "payload['kaart'] = {'word': str, 'claim': str} — de trend-kaart."
    required_payload = ("kaart",)
    output_schema = "{'vraag': str|None} — één onderzoekbare vraag, of None (fail-closed)."

    def run(self, payload: dict, context) -> dict:
        kaart = payload.get("kaart", {})
        return {"vraag": self._llm(kaart, payload.get("locale"))}

    def _llm(self, kaart: dict, locale: str | None = None) -> str | None:
        from nooch_village.llm import reason
        from nooch_village.language import instruction
        word = kaart.get("word", "")
        claim = kaart.get("claim", "")
        prompt = (
            "Een zoekterm over duurzame schoenen komt herhaaldelijk op als stijgende "
            "trend. Wij willen de waaróm eronder begrijpen door er wetenschappelijke "
            "literatuur bij te zoeken. Formuleer EEN concrete, onderzoekbare vraag die "
            "de oorzaak of het mechanisme achter deze trend raakt (bijvoorbeeld de "
            "voordelen, de drijfveren, of het bewijs). Geen ja/nee-vraag, geen "
            "marketing, geen meervoudige vraag.\n\n"
            f"TREND-TERM: {word}\n"
            f"WAT WE WETEN: {claim}\n\n"
            "Antwoord op EXACT één regel:\n"
            "VRAAG: <één onderzoekbare vraag>\n"
            "Kun je geen zinvolle vraag vormen, antwoord dan: VRAAG: geen\n"
            + instruction(locale)
        )
        out = reason(prompt, call_site="skill_onderzoeksvraag")
        if not out:
            return None
        m = re.search(r"VRAAG:\s*(.+)", out, re.IGNORECASE)
        if not m:
            return None
        vraag = m.group(1).strip()
        if not vraag or vraag.lower().startswith("geen"):
            return None
        return vraag
