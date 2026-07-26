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

# Het CONTRACT met de prompt is de Nederlandse marker "KAN NIET:" — die blijft letterlijk staan
# (i18n mini-2C: proza Engels, machine-tokens ongemoeid). De Engelse varianten staan er defensief
# naast: de prompt is nu Engels, dus een model kan afdwalen naar "CANNOT:". Zonder die tolerantie
# zou zo'n antwoord STIL als deliverable landen — een geblokkeerd project dat er afgerond uitziet.
# Alleen herkennen, nooit voorschrijven: de prompt vraagt onverkort om KAN NIET:.
_CANT = re.compile(r"(?:KAN\s*NIET|CAN\s*_?NOT|CANNOT)\s*:?\s*(.+)", re.IGNORECASE | re.DOTALL)
_CANT_START = ("KAN NIET", "CANNOT", "CAN NOT")


def _scope_text(scope) -> str:
    if isinstance(scope, dict):
        return " · ".join(f"{k}: {v}" for k, v in scope.items())
    return str(scope or "")


def work_one(scope, role_id: str, role_purpose: str, *, steer: str = "", persona: str = "",
             kennis: str = "", llm_reason=None) -> dict:
    """Laat de rol (met bestaande capaciteit, tekst-only, omkeerbaar) aan één project werken.
    `steer` = stuur-opmerkingen van de mens die de rol moet meenemen. `persona` = de preamble van
    de toegewezen inwoner (karakter; kleurt toon, niet capaciteit). `kennis` = het (al gerenderde,
    al gecapte) 'REEDS BEKEND'-blok uit de kennislaag (kennis_context.kennis_blok); leeg = geen
    injectie. Geeft {ok, outcome} of {ok: False, needs} als het nieuwe capaciteit/onomkeerbaarheid
    vraagt. Fail-closed zonder LLM."""
    if llm_reason is None:
        import functools
        from nooch_village.llm import reason as _reason
        llm_reason = functools.partial(_reason, call_site="project_work_one")
    prompt = (
        (persona.strip() + "\n\n" if persona and persona.strip() else "")
        + f"You are the role '{role_id}' in NoochVille (sustainable, vegan shoe brand Nooch.earth). "
        f"Your purpose: {role_purpose or '-'}.\n\n"
        f"Take on this project: {_scope_text(scope)}\n\n"
        + (kennis.strip() + "\n\n" if kennis and kennis.strip() else "")
        + (f"STEERING from the human (follow this explicitly): {steer}\n\n" if steer else "")
        + "Deliver what you can concretely do NOW with your own knowledge: a finished text outcome, a "
        "first draft, an analysis, or the concrete next step. Rules: text only (reversible), do not "
        "call external systems, do not publish/send/buy/delete anything, no new tools. Plain "
        "language, no jargon. Write in English.\n\n"
        "The two line markers below are Dutch ON PURPOSE — the system reads them literally. "
        "Reproduce the marker exactly as written; everything after it is English.\n\n"
        "Can you NOT do this with text alone (it needs a website change, an external tool, spending "
        "money, sending something, or a skill you do not have)? Then answer with:\n"
        "KAN NIET: <what is needed for that>\n\n"
        "Otherwise answer with:\n"
        "LEVER: <your concrete outcome or next step>")
    out = (llm_reason(prompt) or "").strip()
    if not out:
        return {"ok": False, "needs": None}
    m = _CANT.search(out)
    if m and out.upper().lstrip().startswith(_CANT_START):
        return {"ok": False, "needs": m.group(1).strip()[:200]}
    body = re.sub(r"^\s*(?:LEVER|DELIVER)\s*:?\s*", "", out, flags=re.IGNORECASE).strip()
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


def _raadpleeg_kennis(ledger, p: dict, owner: str, data_dir, bus) -> str:
    """Kennis-eerst: raadpleeg vóór het werken de kennislaag (kaartjes + inzichten + goedgekeurde
    signalen), meld het op de bus (kennis_geraadpleegd, ook bij 0/0/0) én — als er iets gevonden is —
    als één systeemregel in de projectfeed. Geeft het (gecapte) 'REEDS BEKEND'-promptblok, of "".
    Volledig fail-soft: zonder data_dir of bij elke fout gewoon geen injectie."""
    if data_dir is None:
        return ""
    try:
        from nooch_village.kennis_context import kennis_blok, kennis_voor, meld_raadpleging
        kennis = kennis_voor(data_dir, _scope_text(p.get("scope")))
        meld_raadpleging(bus, project_id=p.get("id", ""), rol=owner, kennis=kennis)
        blok = kennis_blok(kennis)
        if blok:
            try:                                       # feed-regel: zichtbaar op de projectkaart
                ledger.add_feed_entry(p["id"], "📚 raadpleegde de kennisbank: "
                                      + kennis["samenvatting"], kind="system",
                                      author_type="role", author_id=owner)
            except Exception:
                pass                                   # oude/kale ledger zonder feed → alleen log+event
        return blok
    except Exception:
        return ""


def work_projects(ledger, records=None, *, llm_reason=None, limit: int = 5,
                  agenda=None, formalize_threshold: int = 3, personas=None,
                  data_dir=None, bus=None) -> dict:
    """Loop de openstaande omkeerbare projecten langs en laat de eigenaar-rol eraan werken. Gewone
    projecten worden één keer opgepakt; experimenten elke puls opnieuw tot ze ≥ `formalize_threshold`
    keer zijn uitgevoerd. Is er een agenda meegegeven, dan worden rijpe experimenten daarna automatisch
    voorgedragen om te stollen tot accountability. `personas` (PersonaStore) kleurt de toon via de aan
    de rol gekoppelde inwoner. `data_dir` zet de kennis-eerst-raadpleging aan (kennislaag als
    promptcontext); `bus` maakt die raadpleging zichtbaar via kennis_geraadpleegd-events.
    Geeft {worked, blocked, skipped, formalized}."""
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
        kennis = _raadpleeg_kennis(ledger, p, owner, data_dir, bus)
        res = work_one(p.get("scope"), owner, purpose, steer=steer, persona=persona,
                       kennis=kennis, llm_reason=llm_reason)
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
