"""De curate-engine: fuzzy input → goedgevormde, atomaire, Engelse insight-kaartjes.

Dit is het hart van de Librarian-curator. Eén kwaliteitspoort voor de kennislaag: alles wat
erin komt is Engels, atomair (één claim per kaartje), compleet (claim/source/grounds), en waar
mogelijk gekoppeld aan bestaande kaartjes. De LLM herschrijft/vertaalt/splitst; een
deterministische validator bewaakt de structuur (fail-closed).

Pure helpers + een orkestratie-functie met injecteerbare reason, zodat alles testbaar is
zonder netwerk.
"""
from __future__ import annotations
import json
import re

from nooch_village.llm import reason

_VALID_EVIDENCE = {"measured", "reported", "claimed", "certified", "peer_reviewed"}


def build_curate_prompt(fuzzy: str, existing_ids: list[str] | None = None) -> str:
    """Bouw de curatie-prompt. Harde regels: Engels-only, atomair, JSON-output."""
    ids = ", ".join(existing_ids or []) or "(none)"
    return (
        "You are the Librarian of Nooch.earth, curator of the knowledge base, a Zettelkasten of "
        "atomic insight cards. Turn the rough input into one or more well-formed cards.\n\n"
        "HARD RULES:\n"
        "- ENGLISH ONLY. Translate any non-English input; even Dutch phenomena are reported in English.\n"
        "- ATOMIC: exactly one claim per card. Split multi-claim input into separate cards.\n"
        "- Every card needs solid grounds (the evidence or reasoning behind the claim).\n\n"
        f"Rough input (may be fuzzy or non-English):\n\"\"\"{fuzzy}\"\"\"\n\n"
        f"Existing card ids you MAY link to (only if genuinely related): {ids}\n\n"
        "Return ONLY a JSON array, no prose, no code fences. Each object:\n"
        '{"id": "<short_english_snake_case_slug>", "claim": "<one atomic claim in English>", '
        '"grounds": "<evidence or reasoning in English>", '
        '"evidence_type": "measured|reported|claimed|certified|peer_reviewed or null", '
        '"concept_id": "<lexicon concept id or null>", "tags": ["..."], '
        '"links_to": ["<existing id>", ...]}'
    )


def parse_cards(text: str | None) -> list[dict]:
    """Haal de JSON-array met kaartjes uit de LLM-output. Fail-closed: geen/onparseerbaar → []."""
    if not text:
        return []
    # strip eventuele code-fences
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    start, end = cleaned.find("["), cleaned.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        data = json.loads(cleaned[start:end + 1])
    except (ValueError, TypeError):
        return []
    return [d for d in data if isinstance(d, dict)]


def validate_card(d: dict) -> bool:
    """Deterministische compleetheids-poort: id (slug), claim en grounds moeten gevuld zijn."""
    def filled(k):
        return isinstance(d.get(k), str) and d[k].strip() != ""
    if not (filled("id") and filled("claim") and filled("grounds")):
        return False
    return re.fullmatch(r"[a-z0-9_]+", d["id"].strip()) is not None


def finalize_card(d: dict, source: str, source_date: str) -> dict:
    """Vul de vaste velden in (source/source_date/status) en normaliseer evidence_type.
    status = supported als er grounds zijn (validator garandeert dat), anders unresolved."""
    ev = d.get("evidence_type")
    ev = ev if ev in _VALID_EVIDENCE else None
    return {
        "id":            d["id"].strip(),
        "claim":         d["claim"].strip(),
        "grounds":       d["grounds"].strip(),
        "source":        source,
        "source_date":   source_date,
        "status":        "supported",
        "evidence_type": ev,
        "concept_id":    d.get("concept_id") or None,
        "tags":          [t for t in (d.get("tags") or []) if isinstance(t, str)],
        "links_to":      [x for x in (d.get("links_to") or []) if isinstance(x, str)],
    }


def curate(fuzzy: str, *, source: str, source_date: str,
           existing_ids: list[str] | None = None, reason_fn=None) -> list[dict]:
    """Fuzzy input → lijst goedgevormde kaart-dicts (Engels, atomair, compleet).

    Roept de LLM aan (reason_fn, default llm.reason), parseert, valideert en finaliseert.
    Fail-closed op elke stap: geen LLM/onparseerbaar/ongeldig → die kaartjes vervallen.
    """
    import functools
    rf = reason_fn or functools.partial(reason, call_site="curate_cards")
    out = rf(build_curate_prompt(fuzzy, existing_ids))
    cards = parse_cards(out)
    return [finalize_card(d, source, source_date) for d in cards if validate_card(d)]
