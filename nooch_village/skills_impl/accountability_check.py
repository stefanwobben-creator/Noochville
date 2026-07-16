"""accountability_check — dorpsbrede check op de accountabilities van alle rollen.

Twee dingen tegelijk, want ze hangen samen met het pull-systeem (rollen matchen woorden/kansen op hun
eigen verantwoordelijkheden, dus die moeten schoon zijn):
  1. DUBBELINGEN: welke accountabilities overlappen tussen rollen (twee rollen die hetzelfde claimen).
  2. FORMULERING: welke zijn zwak geformuleerd (vaag, meerdere dingen in één), met een herformulering.

Pure helpers + een injecteerbare reason_fn (testbaar zonder netwerk); fail-closed zonder LLM → lege
check, nooit een verzonnen bevinding. Schrijft niets aan de governance: het is een leescheck/advies.
"""
from __future__ import annotations

import json
import re


def build_check_prompt(roles: list[dict], mission: str = "") -> str:
    """roles: [{"role": <naam>, "accountabilities": [<str>, ...]}]."""
    lines = []
    for r in roles:
        for a in (r.get("accountabilities") or []):
            lines.append(f"- [{r.get('role', '?')}] {a}")
    body = "\n".join(lines)
    m = f"Missie-context: {mission}\n\n" if mission else ""
    return (
        "Je bent governance-facilitator van een GlassFrog-organisatie. Hieronder alle accountabilities "
        "(verantwoordelijkheden) per rol.\n\n"
        f"{m}"
        "Doe twee checks:\n"
        "1. DUBBELINGEN: welke accountabilities overlappen of zijn (bijna) identiek tussen rollen? "
        "Elke overlap is een governance-spanning: twee rollen die hetzelfde claimen. Noem alleen echte "
        "overlap, geen toevallige woordgelijkenis.\n"
        "2. FORMULERING: welke accountabilities zijn zwak (vaag, meerdere dingen in één, geen duidelijke "
        "actie of uitkomst)? Geef per zwakke een scherpere herformulering.\n\n"
        f"Accountabilities:\n{body}\n\n"
        "Antwoord met UITSLUITEND een JSON-object, geen proza, geen code-fences:\n"
        '{"duplicates": [{"accountability": "<korte omschrijving>", "roles": ["rolA", "rolB"], '
        '"advies": "<welke rol houdt het, of hoe splitsen>"}], '
        '"weak": [{"role": "<rol>", "accountability": "<huidige tekst>", '
        '"herformulering": "<scherper>", "waarom": "<kort>"}]}'
    )


def parse_check(text: str | None) -> dict:
    """Haal het JSON-object uit de LLM-output. Fail-closed: geen/onparseerbaar → lege check."""
    if not text:
        return {"duplicates": [], "weak": []}
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    s, e = cleaned.find("{"), cleaned.rfind("}")
    if s == -1 or e == -1 or e < s:
        return {"duplicates": [], "weak": []}
    try:
        d = json.loads(cleaned[s:e + 1])
    except (ValueError, TypeError):
        return {"duplicates": [], "weak": []}
    if not isinstance(d, dict):
        return {"duplicates": [], "weak": []}
    return {"duplicates": list(d.get("duplicates") or []), "weak": list(d.get("weak") or [])}


def check_accountabilities(roles: list[dict], reason_fn, mission: str = "") -> dict:
    """Draai de check. `roles`: [{role, accountabilities}]. `reason_fn`: prompt -> tekst (of None).
    Fail-closed: geen rollen met accountabilities of geen LLM → lege, eerlijke uitkomst."""
    roles = [r for r in roles if (r.get("accountabilities"))]
    if not roles:
        return {"ok": True, "n_roles": 0, "duplicates": [], "weak": []}
    try:
        out = reason_fn(build_check_prompt(roles, mission))
    except Exception:
        out = None
    return {"ok": True, "n_roles": len(roles), **parse_check(out)}
