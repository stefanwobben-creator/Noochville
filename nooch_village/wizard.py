"""Project-wizard — de geleide flow om één goed project op het bord te zetten (founder 20 jul).

De cockpit-kant van de Duolingo-achtige flow: de LLM helpt een ruw idee scherp te maken tot
een TOETSBARE uitkomst (die z'n eigen 'klaar wanneer' in zich draagt), en stelt een checklist
voor die per item tegen de skills van de rol wordt getoetst. Deze module is puur logica
(LLM-call + skill-check), zodat de cockpit-endpoints dun blijven en dit testbaar is.

Bewust in het cockpit synchroon (de mens wacht en verwacht dat de AI meedenkt — zoals spelvraag),
niet op de daemon. Fail-soft: valt de LLM weg, dan krijg je het ruwe idee / een leeg plan terug
i.p.v. een fout, en kan de mens alsnog handmatig verder.
"""
from __future__ import annotations

import json
import re

from nooch_village.llm import reason


def sharpen_outcome(ruw: str, *, reason_fn=reason) -> str:
    """Zet een ruw idee om in één concrete, toetsbare uitkomst. Fail-soft → het ruwe idee terug."""
    ruw = (ruw or "").strip()
    if not ruw:
        return ""
    out = reason_fn(
        "Je helpt een projectomschrijving scherp te maken voor een zelfsturend team. Zet dit "
        "ruwe idee om in ÉÉN concrete, TOETSBARE uitkomst. Een uitkomst is geen onderwerp maar "
        "een resultaat waaraan je ziet dat het klaar is, met een meetbaar 'klaar' erin — inclusief "
        "de eerlijke nul-uitkomst (bv. 'er ligt een overzicht van 3 materialen met bron, óf "
        "expliciet: geen enkel materiaal voldoet').\n\n"
        f"RUW IDEE: {ruw}\n\n"
        "OUTPUT: alleen de uitkomst-zin in het Nederlands, geen inleiding of aanhalingstekens.",
        max_tokens=140, call_site="wizard_sharpen")
    v = re.sub(r"\s+", " ", (out or "")).strip().strip('"“”‘’ ').strip()
    return v or ruw


def _catalog_block(catalog: list[dict]) -> str:
    lines = []
    for c in catalog or []:
        lines.append(f"- {c['name']}: {(c.get('description') or '')[:120]}\n    input: "
                     + (c.get("input") or "(geen schema — leid af uit naam)"))
    return "\n".join(lines) or "(geen skills)"


def plan_items(goal: str, catalog: list[dict], *, reason_fn=reason,
               required_of=None, max_items: int = 5) -> list[dict]:
    """Stel een checklist voor bij `goal`, elk item met een skill uit `catalog` (of null = mens-taak)
    en een payload in de vorm van het input_schema. `catalog` = [{name, description, input}] van de
    skills die de ROL heeft. `required_of(skill)` → verplichte payload-velden (voor de uitvoerbaarheid).

    Geeft [{tekst, skill, payload, ok, reden}]. ok = een skill van de rol dekt het item én de
    verplichte payload-velden zijn ingevuld; anders ok=False (mens-taak of payload onvolledig).
    Fail-soft: [] bij een onbruikbaar LLM-antwoord."""
    goal = (goal or "").strip()
    if not goal:
        return []
    eigen = {c["name"] for c in (catalog or [])}
    prompt = (
        "Je breekt een projectdoel op in 2 tot 5 concrete stappen voor een zelfsturende rol.\n\n"
        f"DOEL (de uitkomst):\n\"{goal}\"\n\n"
        f"De skills van deze rol (de ENIGE tools), met hun input-vorm:\n{_catalog_block(catalog)}\n\n"
        "Voor ELK item: als één van deze skills het kan uitvoeren, geef de exacte skill-naam ÉN een "
        "'payload'-object dat voldoet aan de 'input'-vorm van die skill. Kan geen enkele skill het, "
        "zet skill=null en payload={} (dan wordt het een menselijke taak). Elk item begint met een "
        "werkwoord en is één stap.\n"
        "Antwoord UITSLUITEND met JSON:\n"
        '{"items":[{"tekst":"...","skill":"skillnaam of null","payload":{}}]}')
    raw = reason_fn(prompt, max_tokens=900, json_mode=True, call_site="wizard_plan")
    data = _extract(raw)
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        return []
    uit: list[dict] = []
    for it in data["items"][:max_items]:
        if not isinstance(it, dict):
            continue
        tekst = str(it.get("tekst") or "").strip()
        if not tekst:
            continue
        skill = it.get("skill")
        skill = skill if (skill and skill in eigen) else None       # alleen skills die de rol écht heeft
        payload = it.get("payload") if isinstance(it.get("payload"), dict) else {}
        ok, reden = True, ""
        if not skill:
            ok, reden = False, "geen skill — menselijke taak"
        elif required_of is not None:
            mist = [f for f in (required_of(skill) or ()) if not payload.get(f)]
            if mist:
                ok, reden = False, f"payload onvolledig: {', '.join(mist)} ontbreekt"
        uit.append({"tekst": tekst[:200], "skill": skill, "payload": payload,
                    "ok": ok, "reden": reden})
    return uit


def _extract(raw):
    if not raw:
        return None
    s = re.sub(r"```(?:json)?", "", str(raw)).strip()
    try:
        return json.loads(s[s.find("{"):s.rfind("}") + 1])
    except (ValueError, IndexError):
        return None
