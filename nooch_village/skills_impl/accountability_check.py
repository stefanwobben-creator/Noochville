"""accountability_check — dorpsbrede check op de accountabilities van alle rollen.

Twee dingen tegelijk, want ze hangen samen met het pull-systeem (rollen matchen woorden/kansen op hun
eigen verantwoordelijkheden, dus die moeten schoon zijn):
  1. DUBBELINGEN: welke accountabilities overlappen tussen rollen (twee rollen die hetzelfde claimen).
  2. FORMULERING: welke zijn zwak geformuleerd (vaag, meerdere dingen in één), met een herformulering.

Pure helpers + een injecteerbare reason_fn (testbaar zonder netwerk). Schrijft niets aan de
governance: het is een leescheck/advies.

Fail-closed, en sinds scope 56 ook ONDERSCHEIDBAAR: "het model gaf niets" en "het model vond niets"
waren tot dan dezelfde uitkomst (`ok: True, duplicates: [], weak: []`), en het scherm zei dan
"No duplicates found." terwijl de check niet had gedraaid (skill-review 12-09-2026). Nu is een
storing `ok: False` + `reden`, en draagt elke uitkomst `at` en `n_roles`, zodat de Circle Lead ziet
wanneer de check liep en over hoeveel rollen.
"""
from __future__ import annotations

import json
import re
import time

# Het antwoord is één JSON-object over álle rollen (~30 in productie, elk met meerdere
# accountabilities en per zwakke een herformulering). De default van `llm.reason` (700 tokens)
# kapte dat af; een afgekapt JSON parst niet en las als "0 aandachtspunten".
MAX_TOKENS = 3000


def build_check_prompt(roles: list[dict], mission: str = "") -> str:
    """roles: [{"role": <naam>, "accountabilities": [<str>, ...]}]."""
    lines = []
    for r in roles:
        for a in (r.get("accountabilities") or []):
            lines.append(f"- [{r.get('role', '?')}] {a}")
    body = "\n".join(lines)
    m = f"Mission context: {mission}\n\n" if mission else ""
    return (
        "You are the governance facilitator of a GlassFrog organisation. Below are all "
        "accountabilities per role.\n\n"
        f"{m}"
        "Do two checks, using only the accountabilities listed below:\n"
        "1. DUBBELINGEN (duplicates): which accountabilities overlap or are (nearly) identical between "
        "roles? Every overlap is a governance tension: two roles claiming the same work. Name only real "
        "overlap, not coincidental word similarity.\n"
        "2. FORMULERING (wording): which accountabilities are weak (vague, several things in one, no "
        "clear action or outcome)? Give a sharper rewording for each weak one.\n\n"
        f"Accountabilities:\n{body}\n\n"
        "Answer with ONLY a JSON object, no prose, no code fences:\n"
        '{"duplicates": [{"accountability": "<short description>", "roles": ["roleA", "roleB"], '
        '"advies": "<which role keeps it, or how to split>"}], '
        '"weak": [{"role": "<role>", "accountability": "<current text>", '
        '"herformulering": "<sharper>", "waarom": "<short>"}]}'
    )


def parse_check(text: str | None) -> dict | None:
    """Haal het JSON-object uit de LLM-output. None = geen of onparseerbaar antwoord — en dat is
    iets anders dan een lege check (`{"duplicates": [], "weak": []}`): het eerste is een storing,
    het tweede een oordeel."""
    if not text:
        return None
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    s, e = cleaned.find("{"), cleaned.rfind("}")
    if s == -1 or e == -1 or e < s:
        return None
    try:
        d = json.loads(cleaned[s:e + 1])
    except (ValueError, TypeError):
        return None
    if not isinstance(d, dict):
        return None
    return {"duplicates": list(d.get("duplicates") or []), "weak": list(d.get("weak") or [])}


def check_accountabilities(roles: list[dict], reason_fn, mission: str = "") -> dict:
    """Draai de check. `roles`: [{role, accountabilities}]. `reason_fn`: prompt -> tekst (of None).

    Drie uitkomsten: geen rollen met accountabilities → `ok: True`, leeg (er valt niets te checken);
    het model antwoordt niet of onleesbaar → `ok: False` + `reden` (de check kon niet draaien);
    anders het oordeel. `at` = wanneer, `n_roles` = over hoeveel rollen."""
    roles = [r for r in roles if (r.get("accountabilities"))]
    basis = {"at": time.time(), "n_roles": len(roles)}
    if not roles:
        return {"ok": True, **basis, "duplicates": [], "weak": [],
                "reden": "geen rollen met accountabilities — niets te checken"}
    try:
        out = reason_fn(build_check_prompt(roles, mission))
    except Exception as e:                                   # noqa: BLE001 — storing, geen oordeel
        return {"ok": False, **basis, "duplicates": [], "weak": [],
                "reden": f"het model gaf een fout ({type(e).__name__}) — de check kon niet draaien"}
    geparsed = parse_check(out)
    if geparsed is None:
        reden = ("het model gaf geen antwoord — de check kon niet draaien (geen sleutel, quota "
                 "of storing)" if not out else
                 f"het antwoord van het model was niet leesbaar als JSON ({len(str(out))} tekens) — "
                 f"de check kon niet draaien")
        return {"ok": False, **basis, "duplicates": [], "weak": [], "reden": reden}
    return {"ok": True, **basis, **geparsed}
