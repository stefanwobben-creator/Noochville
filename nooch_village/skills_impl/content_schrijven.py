from __future__ import annotations
from nooch_village.skills import Skill
from nooch_village.llm_keuze import skill_ladder

# Antwoordbudget voor een COMPLETE eerste draft (kop-opties + tekst). Stond op de default van 700
# tokens — dat is een alinea, geen draft; live kapte de tekst midden in een zin af.
_MAX_TOKENS = 2500
_ONGEVERIFIEERD = "unverified"


def _soorten() -> set[str]:
    """De publicatie-soorten zoals de claim-poort ze kent (één bron: publication_check)."""
    from nooch_village.publication_check import PublicationKind
    return {k.value for k in PublicationKind}


def _strikt(kind: str) -> bool:
    from nooch_village.publication_check import PublicationKind, STRICT_KINDS
    try:
        return PublicationKind(kind) in STRICT_KINDS
    except ValueError:
        return False


def _status_in_store(card: dict, notes) -> str:
    """De grondings-status zoals de KENNISBANK hem kent, niet zoals de payload hem opschrijft.

    Live (7 sep, cf46e6c447eb) schreef de planner cards met `status: "verified"` die in geen
    enkele store bestonden ("Gemaakt van 100% mycelium…"), en de prompt vertrouwde die status: een
    harde claim op een sales page zonder bewijs. Een status is een feit van de store; de payload
    mag hem noemen, maar hij wordt hier opnieuw gelezen. Zonder store (de losse aanroep in tests
    of een kale context) blijft de payload-status staan — er is dan niets om tegen te lezen."""
    if notes is None:
        return str(card.get("status") or _ONGEVERIFIEERD)
    try:
        note = notes.get(str(card.get("id") or ""))
    except Exception:                                    # noqa: BLE001 — kapotte store = niets bewezen
        note = None
    if note is None:
        return _ONGEVERIFIEERD
    st = getattr(note, "status", None)
    return str(getattr(st, "value", st) or _ONGEVERIFIEERD)


class ContentSchrijvenSkill(Skill):
    """Schrijft publieke website-content in Nooch-merkstem uit een cluster kennis-kaartjes.

    Eén LLM-call, fail-closed (geen LLM of geen materiaal → `error`, geen tekst). Geeft naast de
    tekst de gebruikte kaart-ids terug (`_claim_insight_ids`, run-administratie), zodat de
    claim-keuring (review_publication) ze per publicatie-soort kan toetsen. Schrijft zelf niets weg.

    SCOPE 57: de ids en `kind` stonden als inhoudssleutels in het resultaat en wonnen de wall van
    de draft zelf (een lijst telt zwaarder dan tekst); zonder LLM las het resultaat als 'gelukt'.
    Nu is de draft het enige inhoudsveld en is 'geen model' een fout.
    """
    name = "content_schrijven"
    cost = "free"  # kleine begrensde LLM-tokenkost wordt bewust niet gevlagd
    side_effect_free = True
    description = ("Write a first draft of public website copy in the Nooch brand voice from a set of "
                   "knowledge cards, per publication kind (blog | sales_page | passport). Only verified "
                   "cards become hard claims on a sales page or passport; the brand copy rules come "
                   "from context.copy_rules.")
    input_schema = ("cards: list of {id: str (a knowledge-base card id), claim: str, word?: str, "
                    "status?: str} (required — the material; a card's real status is read from the "
                    "knowledge base, a status written here is not trusted); "
                    "kind: str (optional — 'blog' (default) | 'sales_page' | 'passport'; strict claim "
                    "rules for the last two); audience?: str (the reader persona); "
                    "desired_outcome?: str (the emotion or action); locale?: str (default English)")
    required_payload = ("cards",)
    output_schema = ("text: str (the draft, headline options first) | error: str — fail-closed: "
                     "no model or no material is an error, never an empty success")

    def validate_payload(self, payload: dict, context) -> list:
        """Twee verwijzingen die een planner kan verzinnen: de publicatie-soort (enum) en de
        `verified`-status van een card. Een soort buiten de enum viel stil op de blog-regels; een
        verzonnen 'verified' werd een harde claim. Fail-soft zonder notes-store: dan is de status
        niet te toetsen en degradeert `run` hem bij het schrijven."""
        p = payload or {}
        redenen = []
        kind = str(p.get("kind") or "").strip()
        if kind and kind not in _soorten():
            redenen.append(f"'kind' must be one of {sorted(_soorten())}, not {kind!r}")
        cards = p.get("cards")
        if cards is not None and (not isinstance(cards, list)
                                  or not all(isinstance(c, dict) and str(c.get("claim") or "").strip()
                                             for c in cards)):
            redenen.append("'cards' must be a list of {id, claim} objects with a non-empty claim")
            return redenen
        notes = getattr(context, "notes", None) if context is not None else None
        if notes is not None and isinstance(cards, list):
            for c in cards:
                if str(c.get("status") or "").strip().lower() != "verified":
                    continue
                if _status_in_store(c, notes) != "verified":
                    redenen.append(f"card {str(c.get('id') or '?')!r} claims status 'verified' but the "
                                   f"knowledge base has no verified card with that id — a verified "
                                   f"status comes from the store, not from the plan")
        return redenen

    def run(self, payload: dict, context) -> dict:
        p = payload or {}
        cards = p.get("cards") or []
        if not isinstance(cards, list) or not cards:
            return {"error": "no material: 'cards' is required — a non-empty list of knowledge cards"}
        kind = str(p.get("kind") or "blog")
        if kind not in _soorten():
            return {"error": f"unknown publication kind {kind!r}; use one of {sorted(_soorten())}"}
        notes = getattr(context, "notes", None) if context is not None else None
        # De status wordt hier uit de store gelezen (of gedegradeerd): de prompt ziet nooit een
        # 'verified' die alleen in de payload bestond.
        materiaal = [{**c, "status": _status_in_store(c, notes)} for c in cards if isinstance(c, dict)]
        rules = getattr(context, "copy_rules", "") if context is not None else ""
        text = self._llm(materiaal, kind, str(p.get("audience") or ""),
                         str(p.get("desired_outcome") or ""), rules, p.get("locale"))
        if not text:
            return {"error": "no draft: the model gave no answer (fail-closed — nothing was written)"}
        return {
            "text": text,
            # Run-administratie (`_`-prefix): de claim-poort leest ze, de wall niet.
            "_claim_insight_ids": [c.get("id") for c in cards if isinstance(c, dict) and c.get("id")],
            "_kind": kind,
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
        claim_regel = (
            "This is marketing or sales content: use ONLY verified cards as hard claims; an "
            "unverified card may appear at most as an open direction or a question, never as fact."
            if _strikt(kind) else
            "This is a blog: you may write exploratively, but invent no facts beyond the material."
        )
        rules_block = (
            f"Follow these brand copy rules strictly as the basis for everything:\n{rules}\n\n"
            if rules else ""
        )
        prompt = (
            "You write a FIRST DRAFT of public content for Nooch.earth (sustainable, plant-based "
            "shoes: no plastic, no leather). A human rewrites it afterwards, so deliver a strong, "
            "complete draft, not a bare skeleton.\n\n"
            + rules_block
            + f"Reader (persona): {audience or 'not specified'}\n"
            + f"Desired outcome or emotion: {desired_outcome or 'not specified'}\n\n"
            + f"Publication kind: {kind}\n"
            + f"{claim_regel}\n\n"
            + f"Material (knowledge cards, grounding status in brackets):\n{material}\n\n"
            + "Turn this into one coherent piece for this one reader and the desired emotion. Base it "
            + "ONLY on the material below and above; invent no figures, sources or facts that are not "
            + "there — leave a gap open rather than fill it. Put a few headline options at the top "
            + "(the headline is ~80% of the success).\n"
            + instruction(locale)
        )
        out = reason(prompt, call_site="skill_content_schrijven", max_tokens=_MAX_TOKENS,
                     ladder=skill_ladder("skill_content_schrijven"))
        return out.strip() if out else None
