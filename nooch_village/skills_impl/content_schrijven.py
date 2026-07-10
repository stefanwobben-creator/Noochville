from __future__ import annotations
from nooch_village.skills import Skill


class ContentSchrijvenSkill(Skill):
    """Schrijft publieke website-content in Nooch-merkstem uit een cluster kennis-kaartjes.

    Eén LLM-call, fail-closed (geen LLM of geen materiaal → geen tekst). Geeft naast de
    tekst de gebruikte kaart-ids terug, zodat de claim-keuring (review_publication) ze
    per publicatie-soort kan toetsen. Schrijft zelf niets weg.
    """
    name = "content_schrijven"
    cost = "free"  # kleine begrensde LLM-tokenkost wordt bewust niet gevlagd
    side_effect_free = True
    description = "Schrijft publieke website-content in Nooch-merkstem uit een cluster kennis-kaartjes, per publicatie-soort."
    input_schema = ("payload: {'cards': [{'id','word','claim','status'}], "
                    "'kind': 'blog|sales_page|passport', 'audience'?: str, "
                    "'desired_outcome'?: str, 'locale'?: str}. De copyregels komen uit "
                    "context.copy_rules.")
    output_schema = "{'text': str|None, 'claim_insight_ids': [str], 'kind': str} — fail-closed: text=None zonder LLM of materiaal"

    def run(self, payload: dict, context) -> dict:
        cards = payload.get("cards", [])
        kind = payload.get("kind", "blog")
        rules = getattr(context, "copy_rules", "") if context is not None else ""
        text = self._llm(cards, kind, payload.get("audience", ""),
                         payload.get("desired_outcome", ""), rules, payload.get("locale"))
        return {
            "text": text,
            "claim_insight_ids": [c.get("id") for c in cards if c.get("id")],
            "kind": kind,
        }

    def _llm(self, cards: list[dict], kind: str, audience: str,
             desired_outcome: str, rules: str, locale: str | None = None) -> str | None:
        from nooch_village.llm import reason
        from nooch_village.language import instruction
        if not cards:
            return None
        material = "\n".join(
            f"- ({c.get('status', '?')}) {c.get('claim', '')}" for c in cards
        )
        strict = kind in ("sales_page", "passport")
        claim_regel = (
            "Dit is marketing/sales-content: gebruik UITSLUITEND geverifieerde (verified) "
            "kaartjes als harde claim; onbewezen kaartjes mogen hooguit als open richting "
            "of vraag, nooit als feit."
            if strict else
            "Dit is een blog: je mag verkennend schrijven, maar verzin geen feiten buiten "
            "het materiaal."
        )
        rules_block = (
            f"Volg deze merk-copyregels strikt als basis voor alles:\n{rules}\n\n"
            if rules else ""
        )
        prompt = (
            "Je schrijft een EERSTE DRAFT van publieke content voor Nooch.earth. Een mens "
            "herschrijft 'm daarna, dus lever een sterke, complete draft, geen kaal raamwerk.\n\n"
            + rules_block
            + f"Lezer (persona): {audience or 'niet gespecificeerd'}\n"
            + f"Gewenste uitkomst/emotie: {desired_outcome or 'niet gespecificeerd'}\n\n"
            + f"Publicatie-soort: {kind}\n"
            + f"{claim_regel}\n\n"
            + f"Materiaal (kennis-kaartjes, met grounding-status tussen haakjes):\n{material}\n\n"
            + "Maak hier één samenhangend stuk van, gericht op deze ene lezer en de gewenste "
            + "emotie. Baseer je ALLEEN op het materiaal; verzin geen cijfers, bronnen of "
            + "feiten die er niet staan. Geef bovenaan een paar kop-opties (de kop is ~80% "
            + "van het succes).\n"
            + instruction(locale)
        )
        out = reason(prompt, call_site="skill_content_schrijven")
        return out.strip() if out else None
