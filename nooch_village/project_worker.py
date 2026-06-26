"""Autonome project-uitvoering — de rol pakt z'n omkeerbare projecten zelf op.

Filosofie (docs/GOVERNANCE_FILOSOFIE.md): een rol mag vanuit zijn purpose vrij handelen aan een
experiment zolang het OMKEERBAAR is en geen domein van een ander schendt. Een accountability is
daarvoor NIET nodig (accountability = verwachting, geen toestemming).

Grenzen die hier hard bewaakt worden:
- Alleen `queued` projecten (die zijn door de omkeerbaarheidspoort als omkeerbaar gemarkeerd).
- De rol levert UITSLUITEND tekst (een deliverable / next action / analyse) met zijn BESTAANDE
  capaciteit (LLM-redenering). Geen externe write-API's, geen code, geen nieuwe skills, niets
  onomkeerbaars — dat blijft mens-gated (geboren-vs-bemenst).
- Vraagt het project tóch nieuwe capaciteit of een onomkeerbare handeling? Dan levert de rol niet,
  maar zegt 'KAN NIET' met wat er nodig is → het project wordt geblokkeerd voor jouw oordeel.
- De mens sluit projecten af (de rol markeert hooguit voortgang), zodat de onafhankelijke check blijft.
"""
from __future__ import annotations
import re

_CANT = re.compile(r"KAN\s*NIET\s*:?\s*(.+)", re.IGNORECASE | re.DOTALL)


def _scope_text(scope) -> str:
    if isinstance(scope, dict):
        return " · ".join(f"{k}: {v}" for k, v in scope.items())
    return str(scope or "")


def work_one(scope, role_id: str, role_purpose: str, *, steer: str = "", persona: str = "",
             llm_reason=None) -> dict:
    """Laat de rol (met bestaande capaciteit, tekst-only, omkeerbaar) aan één project werken.
    `steer` = stuur-opmerkingen van de mens die de rol moet meenemen. `persona` = de preamble van
    de toegewezen inwoner (karakter; kleurt toon, niet capaciteit). Geeft {ok, outcome} of
    {ok: False, needs} als het nieuwe capaciteit/onomkeerbaarheid vraagt. Fail-closed zonder LLM."""
    if llm_reason is None:
        from nooch_village.llm import reason as llm_reason
    prompt = (
        (persona.strip() + "\n\n" if persona and persona.strip() else "")
        + f"Je bent de rol '{role_id}' in NoochVille (duurzaam, vegan schoenenmerk Nooch.earth). "
        f"Jouw purpose: {role_purpose or '-'}.\n\n"
        f"Pak dit project op: {_scope_text(scope)}\n\n"
        + (f"STURING van de mens (volg dit nadrukkelijk): {steer}\n\n" if steer else "")
        + "Lever wat je NU concreet kunt met je eigen kennis: een afgeronde tekst-uitkomst, een eerste "
        "draft, een analyse, of de concrete eerstvolgende stap. Regels: alleen tekst (omkeerbaar), "
        "geen externe systemen aanroepen, niets publiceren/versturen/kopen/verwijderen, geen nieuwe "
        "tools. Gewone taal, geen jargon.\n\n"
        "Kun je dit NIET met tekst alleen (vereist een websitewijziging, een externe tool, geld "
        "uitgeven, iets versturen, of een vaardigheid die je niet hebt)? Antwoord dan met:\n"
        "KAN NIET: <wat is daarvoor nodig>\n\n"
        "Anders antwoord met:\n"
        "LEVER: <je concrete uitkomst of eerstvolgende stap>")
    out = (llm_reason(prompt) or "").strip()
    if not out:
        return {"ok": False, "needs": None}
    m = _CANT.search(out)
    if m and out.upper().lstrip().startswith("KAN NIET"):
        return {"ok": False, "needs": m.group(1).strip()[:200]}
    body = re.sub(r"^\s*LEVER\s*:?\s*", "", out, flags=re.IGNORECASE).strip()
    return {"ok": True, "outcome": body[:1500]} if body else {"ok": False, "needs": None}


def _persona_for(rec, personas) -> str:
    """De persona-preamble van de aan een rol gekoppelde inwoner (leeg = neutrale stem).
    Skills/capaciteit blijven van de rol; de inwoner kleurt alleen toon en aanpak."""
    if rec is None or personas is None:
        return ""
    pid = getattr(rec, "persona_id", None)
    if not pid:
        return ""
    from nooch_village.personas import persona_prompt
    return persona_prompt(personas.get(pid))


def _eligible(p, threshold: int) -> bool:
    """Wie pakt de rol op deze puls op? Gewone projecten één keer (idempotent via 'worked').
    Experimenten elke puls opnieuw, tot ze de stol-drempel halen — zo telt de herhaling mee."""
    if p.get("status") not in ("queued", "running"):
        return False
    if p.get("origin") == "experiment":
        return not p.get("formalized") and int(p.get("executions", 0)) < threshold
    return p.get("status") == "queued" and not p.get("worked")


def work_projects(ledger, records=None, *, llm_reason=None, limit: int = 5,
                  agenda=None, formalize_threshold: int = 3, personas=None) -> dict:
    """Loop de openstaande omkeerbare projecten langs en laat de eigenaar-rol eraan werken. Gewone
    projecten worden één keer opgepakt; experimenten elke puls opnieuw tot ze ≥ `formalize_threshold`
    keer zijn uitgevoerd. Is er een agenda meegegeven, dan worden rijpe experimenten daarna automatisch
    voorgedragen om te stollen tot accountability. `personas` (PersonaStore) kleurt de toon via de aan
    de rol gekoppelde inwoner. Geeft {worked, blocked, skipped, formalized}."""
    todo = [p for p in ledger.all() if _eligible(p, formalize_threshold)]
    worked = blocked = 0
    for p in todo[:limit]:
        owner = p.get("owner", "")
        purpose = ""
        persona = ""
        if records is not None:
            rec = records.get(owner)
            purpose = getattr(getattr(rec, "definition", None), "purpose", "") if rec else ""
            persona = _persona_for(rec, personas)
        steer = " · ".join(c.get("text", "") for c in p.get("comments", []) if c.get("text"))
        res = work_one(p.get("scope"), owner, purpose, steer=steer, persona=persona,
                       llm_reason=llm_reason)
        if res.get("ok"):
            ledger.record_progress(p["id"], res["outcome"])
            worked += 1
        elif res.get("needs"):
            # Vraagt nieuwe capaciteit/onomkeerbaarheid → blokkeren voor de mens (geboren-vs-bemenst).
            ledger.block(p["id"], f"capaciteit nodig: {res['needs']}")
            blocked += 1
    formalized = 0
    if agenda is not None:
        from nooch_village.roloverleg import formalize_ripe_experiments
        formalized = formalize_ripe_experiments(ledger, agenda, threshold=formalize_threshold)
    return {"worked": worked, "blocked": blocked, "skipped": max(0, len(todo) - limit),
            "formalized": formalized}
