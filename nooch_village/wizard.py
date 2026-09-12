"""Project-wizard — de geleide flow om één goed project op het bord te zetten (founder 20 jul).

De cockpit-kant van de Duolingo-achtige flow: de LLM helpt een ruw idee scherp te maken tot
een TOETSBARE uitkomst (die z'n eigen 'klaar wanneer' in zich draagt), en stelt een checklist
voor die per item tegen de skills van de rol wordt getoetst. Deze module is puur logica
(LLM-call + skill-check), zodat de cockpit-endpoints dun blijven en dit testbaar is.

Bewust in het cockpit synchroon (de mens wacht en verwacht dat de AI meedenkt — zoals spelvraag),
niet op de daemon. Fail-soft: valt de LLM weg, dan krijg je het ruwe idee / een leeg plan terug
i.p.v. een fout, en kan de mens alsnog handmatig verder.

De rolsuggesties ("wie kan dit oppakken", `roles_for`, endpoint /wizard/rollen) en het uitdelen
van stappen bij het aanmaken zijn op 12 september 2026 verwijderd, samen met de sectie in de wizard
(Stefan: "die stap kan ook weg"). Werk bij een andere rol neerleggen loopt via het werkoverleg en
de inbox (`route_werk`), niet via een nieuw project.

HET MODEL PRAAT ALLEEN VÓÓR HET OPSLAAN. `sharpen_outcome` zet een suggestie in het veld dat de
mens ziet; wat er bij het opslaan in dat veld staat is de titel, letterlijk. Er was hier een
`title_from` dat bij /wizard/create de formulering nog eens samenvatte, ongevraagd en onzichtbaar
tot het op het bord stond; die is op 12 september 2026 verwijderd (Stefan: "dat moet nooit mogen").
"""
from __future__ import annotations

import json
import logging
import re

from nooch_village.checklist_vorm import MAX_WOORDEN as _MAX_STAP_WOORDEN, zeef
from nooch_village.llm import reason
from nooch_village.projects import _BUSINESS_IMPACT, _EFFORT, _MISSIE_IMPACT

log = logging.getLogger("village.wizard")


# Werkwoorden die een project als een AFGERONDE uitkomst markeren (Holacracy: verleden tijd). Voor de
# deterministische selectie van goede voorbeelden van het eigen bord — géén LLM.
_ANKER_GOED = re.compile(
    r"\b(created|done|completed|organized|organised|granted|made|implemented|developed|written|"
    r"published|added|found|prepared|explored|submitted|sent|launched|built|integrated|mapped|"
    r"finalised|finalized|updated|designed|defined|selected|arranged|scheduled|set up|"
    r"gemaakt|geregeld|opgesteld|bijgewerkt|opgezet|verbeterd|afgerond|gerealiseerd|opgeleverd)\b",
    re.I)
_ANKER_SLECHT = re.compile(
    r"\b(exceed|can |will |should|to drive|to engage|organize |establish |plan for|guest in|"
    r"kan |kunnen|onderzoeken|uitzoeken|opzetten)\b", re.I)


def board_anchors(projects, n: int = 5) -> list[str]:
    """Kies (deterministisch, geen LLM) tot `n` GOED geformuleerde projecten van het eigen bord, als
    voorbeeld voor de sharpen-stap. Zo praat de wizard vanzelf in de taal, toon en het domein van dít
    team. Goed = kort, een voltooid-deelwoord-uitkomst, geen tegenwoordige tijd/activiteit/archief."""
    uit, seen = [], set()
    for p in projects or []:
        if p.get("archived"):
            continue
        s = ((p.get("scope") or p.get("label") or "") or "").strip()
        k = s.lower()
        if not s or len(s) > 72 or k in seen:
            continue
        if _ANKER_GOED.search(s) and not _ANKER_SLECHT.search(s):
            seen.add(k)
            uit.append(s)
            if len(uit) >= n:
                break
    return uit


def sharpen_outcome(ruw: str, *, anchors=None, reason_fn=reason) -> str:
    """Scherp een ruw idee aan tot ÉÉN uitkomst in de verleden tijd (Holacracy). `anchors` = goede
    voorbeelden van het eigen bord (zie board_anchors) zodat de wizard in de stem van het team praat.
    Fail-soft → het ruwe idee terug. Output in het Engels (het team stapt over op Engels)."""
    ruw = (ruw or "").strip()
    if not ruw:
        return ""
    voorbeelden = ""
    if anchors:
        voorbeelden = ("\n\nGOOD EXAMPLES FROM THIS TEAM'S OWN BOARD (match this style, tone and "
                       "language):\n" + "\n".join(f"- {a}" for a in anchors[:5]))
    out = reason_fn(
        "You sharpen a project description for a self-managing team (Holacracy). Turn the raw idea "
        "into ONE concrete outcome phrased in the PAST TENSE / done-state, so it is clear what "
        "'done' looks like (e.g. 'New website launched', not 'New website' and not 'Build a "
        "website'). Rules: exactly one outcome, plain everyday language, no jargon. Do NOT invent "
        "deadlines, metrics or scope the person did not give — a small project is fine. If the raw "
        "idea is ALREADY a clear past-tense outcome, return it essentially unchanged (only strip "
        "jargon). Keep the honest null-result allowed (e.g. 'A shortlist of 3 materials with sources "
        "was produced, or explicitly: none qualified'). Always answer in English."
        + voorbeelden +
        f"\n\nRAW IDEA: {ruw}\n\n"
        "OUTPUT: only the outcome sentence, no preamble or quotation marks.",
        max_tokens=140, call_site="wizard_sharpen")
    v = re.sub(r"\s+", " ", (out or "")).strip().strip('"“”‘’ ').strip()
    return v or ruw


# De drie assen zoals het project ze opslaat. Één bron: `projects._EFFORT` c.s. — een tweede lijst
# hier zou na één wijziging uit de pas lopen, en dan raadt de wizard iets wat het project weigert.
_ASSEN = {"tijd": _EFFORT, "missie": _MISSIE_IMPACT, "business": _BUSINESS_IMPACT}


def guess_impact(idee: str, *, rol: str = "", reason_fn=reason) -> dict:
    """Een GOK voor moeite en impact — bedoeld om in één tik bij te stellen, niet om te geloven.

    Fail-soft en fail-CLOSED per as: alles wat niet in de toegestane waarden zit valt weg in plaats
    van als 'onbekend' te worden opgeslagen. Een verzonnen as is erger dan een lege: hij stuurt
    later de prioritering.

    Geeft {} terug als er niets bruikbaars uitkomt — dan blijven de chips gewoon leeg."""
    idee = (idee or "").strip()
    if not idee:
        return {}
    out = reason_fn(
        "You estimate effort and impact for one project in a small mission-driven shoe company "
        "(Nooch: sustainable footwear, organic growth, no advertising). Answer with JSON only.\n"
        "Fields:\n"
        '  "tijd":     one of "1u" (about an hour), "1d" (a day), "2d", "1w" (a week or more)\n'
        '  "missie":   one of "versterkt", "neutraal", "verzwakt" — does this strengthen the '
        "mission (durability, transparency, less harm)?\n"
        '  "business": one of "hoog", "medium", "laag" — commercial weight\n'
        '  "waarom":   ONE short sentence, plain language, why you guessed this\n'
        "Be honest: most small projects are 'neutraal' and 'medium'. Do not inflate.\n\n'"
        f"PROJECT: {idee[:400]}\n"
        + (f"ROLE: {rol}\n" if rol else "")
        + '\nOUTPUT: only JSON, e.g. {"tijd":"1d","missie":"neutraal","business":"medium",'
          '"waarom":"..."}',
        json_mode=True, max_tokens=200, call_site="wizard_impact")
    data = _extract(out) or {}
    if not isinstance(data, dict):
        return {}
    uit = {}
    for as_, toegestaan in _ASSEN.items():
        v = str(data.get(as_) or "").strip()
        if v in toegestaan:
            uit[as_] = v
    waarom = re.sub(r"\s+", " ", str(data.get("waarom") or "")).strip()
    if waarom:
        uit["waarom"] = waarom[:160]
    return uit


def _catalog_block(catalog: list[dict]) -> str:
    lines = []
    for c in catalog or []:
        lines.append(f"- {c['name']}: {(c.get('description') or '')[:120]}\n    input: "
                     + (c.get("input") or "(geen schema — leid af uit naam)"))
    return "\n".join(lines) or "(geen skills)"


def plan_items(goal: str, catalog: list[dict], *, reason_fn=reason,
               required_of=None, max_items: int = 5, kennis: str = "",
               ladder: str | None = None, data_dir: str = "") -> list[dict]:
    """Stel een checklist voor bij `goal`, elk item met een skill uit `catalog` (of null = mens-taak)
    en een payload in de vorm van het input_schema. `catalog` = [{name, description, input}] van de
    skills die de ROL heeft. `required_of(skill)` → verplichte payload-velden (voor de uitvoerbaarheid).

    Geeft [{tekst, skill, payload, ok, reden}]. ok = een skill van de rol dekt het item én de
    verplichte payload-velden zijn ingevuld; anders ok=False (mens-taak of payload onvolledig).
    `ladder`: de modelkeuze voor deze call (None = de dorpsladder). Bepalen WELK werk er gebeurt is
    dezelfde beslissing als `plan_checklist` in de daemon, dus hetzelfde beleid — de aanroeper haalt
    hem op bij `llm_keuze.llm_voorkeur`, want die kent de persona en het budget; hier weten we dat niet.

    Fail-soft: [] bij een onbruikbaar LLM-antwoord."""
    goal = (goal or "").strip()
    if not goal:
        return []
    eigen = {c["name"] for c in (catalog or [])}
    # Geheugen-eerst: het (al gerenderde, gecapte) 'wat weten we al'-blok komt vóór de skills, met
    # de instructie om voort te bouwen i.p.v. opnieuw te verzamelen. Leeg → geen sectie.
    kennis_section = (kennis.strip() + "\n\n") if kennis and kennis.strip() else ""
    # DE PROMPT IS ENGELS SINDS 06-09-2026 (tweede ronde na #466). Dit is de prompt die de
    # checklist-items schrijft, dus hij bepaalt de taal van het meest gelezen stuk tekst in het hele
    # dorp: de stappen op de projectkaart. Hij stond nog volledig in het Nederlands, en dat was bij
    # het eerste echte gebruik meteen zichtbaar — Engelse kop, Nederlandse stappen eronder.
    #
    # De JSON-SLEUTELS blijven Nederlands ("tekst"). Dat is een parse-token dat `_normaliseer` en de
    # callers lezen; die gaan pas mee als het geheel omgaat (2E), en een half omgezet paar valt stil
    # zonder foutmelding. Zie tests/test_i18n_prompt_grens.py voor die afspraak.
    prompt = (
        "You break a project goal down into 2 to 5 concrete steps for a self-managing role.\n\n"
        f"GOAL (the outcome):\n\"{goal}\"\n\n"
        f"{kennis_section}"
        f"This role's skills (the ONLY tools available), with their input shape:\n"
        f"{_catalog_block(catalog)}\n\n"
        + ("MEMORY FIRST: knowledge or earlier research is already listed above. BUILD ON IT: do not "
           "repeat research that exists and do not gather again what is already there. Start with a "
           "SYNTHESIS step (read and combine what we already know) and only then plan the part that "
           "is genuinely missing.\n"
           # DE HERKOMST VAN DAT BLOK MOET ERBIJ. Het is EXTERN onderzoek — patenten, papers,
           # radar-signalen — en géén inventaris van wat Nooch gebruikt. Zonder deze zin las het
           # model 'PHA, PBAT, algae-based' onder het kopje 'wat we al weten' en schreef het terug
           # als ONZE materialen, inclusief 'recycled' — een claim die wij niet zomaar mogen maken.
           "IMPORTANT: that block is EXTERNAL RESEARCH (patents, papers, market signals), NOT a list "
           "of materials or suppliers we use. Never write that a material from that block is ours, "
           "and do not carry material names out of it into the steps.\n"
           if kennis_section else "")
        + "For EACH item: if one of these skills can carry it out, give the exact skill name AND a "
        "'payload' object matching that skill's 'input' shape. If no skill can do it, set skill=null "
        "and payload={} (it then becomes a human task).\n"
        # Dezelfde zoekregel als in de daemon-planner (scope 50b): de wizard is de andere weg naar
        # het bord, en de zoektermen die hier ontstaan draaien straks precies zo.
        "SEARCH TERMS, when the goal asks to find, research or compare something: plan the "
        "open-web search (web_zoek) in THREE vocabularies, one step each — the trade vocabulary of "
        "the field, the buyer's words, and the language of the market where this is made or sold "
        "(set 'taal' and 'land' in the payload). A corpus source (openalex_evidence, epo_patents) "
        "gets a SHORT technical phrase of 2 to 3 words, never the whole question. Search terms "
        "follow the corpus or the market, not the English rule below.\n"
        "RESEARCH FRAME: for an assessment ('should we', 'is there potential') plan the evidence "
        "that answers it (market size and growth, demand over time, the competitive field, what "
        "customers say, science where relevant); internal figures only when the goal is about "
        "something we already do. Never plan a step that synthesizes or reports on the other steps: "
        "the final document is assembled automatically.\n"
        # VORM, expliciet en met een voorbeeld: de gemeten suggesties waren 25-40 woorden lang.
        f"SHAPE OF A STEP: starts with a verb, is ONE action, and is at most {_MAX_STAP_WOORDEN} "
        "words. No explanation, no parenthetical lists. "
        "Good: 'ask three suppliers for technical specs'. "
        "Bad: 'Synthesise the existing insights and confirmed findings in order to structure our "
        "current knowledge of plant-based soles'.\n"
        "Write every step in ENGLISH, whatever language the goal above is written in.\n"
        "Answer with JSON ONLY:\n"
        '{"items":[{"tekst":"...","skill":"skill name or null","payload":{}}]}')
    raw = reason_fn(prompt, max_tokens=900, json_mode=True, call_site="wizard_plan",
                    ladder=ladder)
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
    # DE POORT ONDER DE PROMPT. De prompt vraagt om korte stappen zonder claims; deze zeef
    # garandeert het. Een prompt is een verzoek, een poort is een garantie — en het model schreef
    # gemeten stappen van 25-40 woorden met 'recycled polymers' erin.
    goed, weg = zeef(uit, data_dir=data_dir)
    if weg:
        log.info("wizard-plan: %d van de %d voorgestelde stappen geweigerd op vorm/claim",
                 len(weg), len(uit))
    return goed


def _extract(raw):
    if not raw:
        return None
    s = re.sub(r"```(?:json)?", "", str(raw)).strip()
    try:
        return json.loads(s[s.find("{"):s.rfind("}") + 1])
    except (ValueError, IndexError):
        return None
