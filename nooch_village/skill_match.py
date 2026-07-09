"""Cockpit-side skill-match: een stil skill-aanbod bij een mens-toegevoegd checklist-item.

Hergebruikt het `_plan_checklist`-recept (item-tekst tegen de DNA-skills van de owner-rol + hun
INPUT-vorm, met een machine-check tegen de harde DNA-lijst), maar voor een GEGEVEN item i.p.v. het
genereren van items. Draait in het cockpit-proces via de LLM-ladder (zoals _ai_reply).

Fail-closed: geen rol-DNA / geen skills / geen match / geen LLM-antwoord / niet-parsebaar / exceptie →
None per item (stil, geen foutmelding). GRENS: dit matcht alleen — het voert NIETS uit en roept nooit
skill.run() aan. Uitvoering blijft exclusief de daemon (Inhabitant._execute_checklist).

De functie accepteert een LIJST item-teksten (batch-klaar: één LLM-call voor N items). Vandaag roept de
cockpit 'm per item aan (er is geen bulk-toevoeg-UI); de vorm ligt klaar voor een latere batch-tak.
"""
from __future__ import annotations

import json
import re


def _extract_json(text):
    """Eerste JSON-object uit een LLM-antwoord, robuust tegen ```json-fences en omringend proza."""
    if not text:
        return None
    s = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", s, re.DOTALL | re.IGNORECASE)
    if fence:
        s = fence.group(1).strip()
    m = re.search(r"\{.*\}", s, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def _catalog(skills, registry) -> str:
    lines = []
    for name in skills:
        obj = registry.get(name) if registry else None
        desc = (getattr(obj, "description", "") or "").strip() if obj else ""
        insch = (getattr(obj, "input_schema", "") or "").strip() if obj else ""
        lines.append(f"- {name}: {desc[:160]}\n    input: " +
                     (insch or "(geen schema — leid af uit naam/omschrijving)"))
    return "\n".join(lines) or "(geen skills)"


def _payload_ok(skill_name: str, payload: dict, registry) -> bool:
    """Verplichte payload-velden (skill.required_payload) aanwezig? Onbekende skill / geen required →
    fail-soft True (identiek aan Inhabitant._missing_required)."""
    obj = registry.get(skill_name) if registry else None
    req = tuple(getattr(obj, "required_payload", ()) or ()) if obj is not None else ()
    pl = payload if isinstance(payload, dict) else {}
    return not [f for f in req if not pl.get(f)]


def plan_offers(owner_record, texts, registry, *, name: str = "") -> list:
    """Voor elk van `texts`: {skill, payload, payload_ok} als een DNA-skill het item kan oppakken, anders
    None. `owner_record` is het governance-Record van de owner-rol (met .definition.skills). None-record,
    geen skills of een lege lijst → alles None. Fail-closed op elke fout."""
    texts = list(texts or [])
    if owner_record is None or not texts:
        return [None] * len(texts)
    try:
        dna = owner_record.definition
        skills = list(getattr(dna, "skills", []) or [])
        if not skills:
            return [None] * len(texts)
        catalog = _catalog(skills, registry)
        accts = list(getattr(dna, "accountabilities", []) or [])
        genummerd = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(texts))
        prompt = (
            f"Je bent {name or 'een autonome rol'}. Jouw skills (de ENIGE tools die je hebt), met hun "
            f"INPUT-vorm:\n{catalog}\n\n"
            f"Jouw accountabilities: {accts or '(geen)'}\n\n"
            "Voor ELK van de volgende checklist-items: als één van jouw skills het item kan uitvoeren, "
            "geef de exacte skill-naam ÉN een 'payload'-object dat EXACT voldoet aan de 'input'-vorm van "
            "die skill (bv. een term-skill wil {\"term\": \"...\"}). Kan geen enkele skill het item "
            "uitvoeren, zet \"skill\": null, \"payload\": {}.\n"
            f"Items (in volgorde, 1..{len(texts)}):\n{genummerd}\n\n"
            "Antwoord UITSLUITEND met JSON, exact dit schema en exact zoveel entries als items, in "
            "dezelfde volgorde:\n{\"matches\": [{\"skill\": \"skillnaam of null\", \"payload\": {}}]}"
        )
        from nooch_village import llm
        raw = llm.reason(prompt, json_mode=True, max_tokens=900)
        data = _extract_json(raw)
        matches = data.get("matches") if isinstance(data, dict) else None
        if not isinstance(matches, list):
            return [None] * len(texts)
        out = []
        for i in range(len(texts)):
            m = matches[i] if i < len(matches) and isinstance(matches[i], dict) else {}
            sk = m.get("skill")
            if not sk or sk not in skills:                    # machine-check tegen de harde DNA-lijst
                out.append(None)
                continue
            pl = m.get("payload") if isinstance(m.get("payload"), dict) else {}
            out.append({"skill": sk, "payload": pl, "payload_ok": _payload_ok(sk, pl, registry)})
        return out
    except Exception:
        return [None] * len(texts)
