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


def _wakkere_rollen(records, ai, skills_of) -> list[dict]:
    """De rollen die werk kunnen oppakken, met alles waarop je ze kunt herkennen.

    Slapend en gearchiveerd doen niet mee: die staan stil, en werk beloven aan een rol waar niemand
    zit is precies wat we bij de afslanking wilden voorkomen. Cirkels ook niet — die hebben geen
    handen (harde regel 7)."""
    from nooch_village import org
    uit = []
    for rec in sorted(records.all(), key=lambda r: _rolnaam(r).lower()):
        if org.is_circle(rec) or getattr(rec, "archived", False) or getattr(rec, "slaapt", False):
            continue
        d = getattr(rec, "definition", None)
        uit.append({"rol": rec.id, "naam": _rolnaam(rec),
                    "skills": sorted(skills_of(rec, ai) or set()),
                    "purpose": (getattr(d, "purpose", "") or "")[:160],
                    "accountabilities": list(getattr(d, "accountabilities", None) or [])[:5]})
    return uit


def _match_deterministisch(stappen: list[dict], rollen: list[dict]) -> list[dict]:
    """De gratis weg: een stap draagt al een skill, en die skill zit in de set van een rol.

    Dit is een OPZOEKING, geen gok — daarom staat hij vooraan en kost hij niets.

    EEN SKILL DIE IEDEREEN HEEFT ONDERSCHEIDT NIETS. Gezien op het echte scherm: de stap "escaleer
    onbevestigde claims naar compliance" stelde alle vijf de rollen-met-skills voor, want `escaleer`
    en `projectverzoek` zitten in elke skillset. Vijf suggesties waarvan er geen enkele iets zegt is
    erger dan geen suggestie — dan moet de lezer alsnog zelf kiezen, maar nu uit een lijst die
    zekerheid uitstraalt. Zo'n skill telt hier dus niet mee; blijft er niets over, dan valt de stap
    door naar de purpose-trede, waar wél een onderscheid te maken is."""
    # Pas vanaf TWEE kandidaten heeft 'iedereen heeft hem' betekenis: met één rol is elke skill
    # per definitie universeel, en dan zou deze regel de enige echte match wegfilteren. Een
    # testfixture met precies één skill-dragende rol wees dat aan.
    kandidaten = [r for r in rollen if r["skills"]]
    breed = (set.intersection(*(set(r["skills"]) for r in kandidaten))
             if len(kandidaten) >= 2 else set())
    nodig: dict[str, list[str]] = {}
    for it in stappen:
        sk, tekst = (it or {}).get("skill"), ((it or {}).get("tekst") or "").strip()
        if sk and tekst and str(sk) not in breed:
            nodig.setdefault(str(sk), []).append(tekst)
    if not nodig:
        return []
    uit = []
    for r in rollen:
        kan = set(r["skills"])
        gedekt = [t for sk, ts in nodig.items() if sk in kan for t in ts]
        if gedekt:
            uit.append({"rol": r["rol"], "naam": r["naam"], "stappen": gedekt,
                        "grond": "heeft de skill die deze stap vraagt"})
    return uit


def _match_model(stappen: list[dict], rollen: list[dict], *, reason_fn=None,
                 ladder: str | None = None) -> list[dict]:
    """De tweede weg, ALLEEN als de eerste leeg is: één begrensd rondje over de roster.

    Waarom een model hier verantwoord is: de kandidatenlijst is klein en gesloten (de wakkere rollen,
    op prod een stuk of twintig), het antwoord wordt machinaal teruggecontroleerd tegen die lijst, en
    de fout is goedkoop — een verkeerde suggestie kost een klik. Dat is een andere afweging dan
    `escalation_mens`, waar een misser via het spoor blijft plakken.

    Fail-OPEN: geen model, onbruikbaar antwoord of een verzonnen rol → een lege lijst, en het scherm
    zegt 'wijs zelf toe'. Nooit een gok die als gronding leest."""
    if not stappen or not rollen:
        return []
    if reason_fn is None:
        reason_fn = reason
    lijst = "\n".join(
        f"- {r['rol']} ({r['naam']}): purpose={r['purpose'] or '(geen)'}; "
        f"accountabilities={'; '.join(r['accountabilities']) or '(geen)'}; "
        f"skills={', '.join(r['skills']) or '(geen)'}" for r in rollen)
    genummerd = "\n".join(f"{i + 1}. {(it.get('tekst') or '').strip()}"
                          for i, it in enumerate(stappen))
    prompt = (
        "Je verdeelt stappen over rollen in een zelfsturende organisatie (Holacracy).\n\n"
        f"STAPPEN:\n{genummerd}\n\n"
        f"ROLLEN (id, naam, purpose, accountabilities, skills):\n{lijst}\n\n"
        "Wijs elke stap toe aan de rol wiens PURPOSE of ACCOUNTABILITY hem dekt. Oordeel over "
        "eigenaarschap, niet over gereedschap: een rol die dit werk bezit maar de tool nog niet "
        "heeft, is nog steeds de juiste. Past er voor een stap geen enkele rol duidelijk, laat die "
        "stap dan weg — liever niets dan een gok.\n"
        'Antwoord UITSLUITEND met JSON: {"toewijzingen":[{"stap":<nummer>,"rol":"<rol-id>"}]}')
    try:
        raw = reason_fn(prompt, json_mode=True, max_tokens=500, call_site="rol_match",
                        ladder=ladder)
    except Exception as e:                               # noqa: BLE001 — nooit het scherm breken
        log.warning("rol-match via model faalde: %s", e)
        return []
    data = _extract(raw)
    rijen = (data or {}).get("toewijzingen")
    if not isinstance(rijen, list):
        return []
    geldig = {r["rol"]: r for r in rollen}
    per_rol: dict[str, list[str]] = {}
    for rij in rijen:
        if not isinstance(rij, dict):
            continue
        rol = str(rij.get("rol") or "").strip()
        if rol not in geldig:                            # verzonnen of uitgesloten rol → weg
            continue
        try:
            i = int(rij.get("stap")) - 1
        except (TypeError, ValueError):
            continue
        if 0 <= i < len(stappen):
            tekst = (stappen[i].get("tekst") or "").strip()
            if tekst:
                per_rol.setdefault(rol, []).append(tekst)
    return [{"rol": rol, "naam": geldig[rol]["naam"], "stappen": ts,
             "grond": "purpose of accountability dekt dit"}
            for rol, ts in per_rol.items()]


def roles_for(items: list, *, records, ai, skills_of, reason_fn=None,
              ladder: str | None = None) -> list[dict]:
    """Welke WAKKERE rollen kunnen een stuk van dit werk oppakken?

    TWEE TREDES, en de volgorde is de hele truc:

      1. DETERMINISTISCH (gratis): draagt een stap al een skill, dan zoeken we op wélke rol die
         skill heeft. Een opzoeking, geen gok.
      2. ALLEEN OP LEEG: één begrensd modelrondje over de roster (purpose + accountabilities +
         skills). Niet bij elke keer — alleen als de gratis weg niets vond.

    WAAROM DIE TWEEDE TREDE ER MOEST KOMEN, gemeten op prod 29 aug 2026. Op het doel "technische
    specs van alle materialen" zei dit scherm "geen rol heeft een passende skill", terwijl Scientist,
    Library en Copywriter voor de hand liggen. De oorzaak was NIET dat de match te letterlijk was —
    er werd helemaal geen tekst vergeleken. De planner had aan alle vijf de stappen `skill=null`
    gehangen (de wizard stond open voor Copywriter, en geen van diens vier skills dekt dit), dus
    `nodig` was leeg en de functie viel er meteen uit. Er viel niets te matchen.

    Daaronder ligt een tweede feit dat de eerste trede structureel dun maakt: van de 23 wakkere
    rollen hebben er VIJF een skill (Scientist 12, Library 10, Trends & Competition 7, Compliance 6,
    Copywriter 4). De andere achttien — Creator of Shoes, Website Developer, Community and Email —
    hebben er nul. Een skill-match kan die per definitie nooit voorstellen, hoe goed hij ook is.
    Betere skill-tagging maakt trede 1 sterker, maar niet volledig: purpose en accountability zijn
    de enige grond die ook een skill-loze rol heeft.

    Fail-open: geen model → een lege lijst, en het scherm zegt 'wijs zelf toe'.

    Geeft per rol: rol, naam, welke stappen, en de GROND (waaróm deze rol)."""
    stappen = [it for it in (items or []) if isinstance(it, dict) and (it.get("tekst") or "").strip()]
    if not stappen:
        return []
    rollen = _wakkere_rollen(records, ai, skills_of)
    gevonden = _match_deterministisch(stappen, rollen)
    if gevonden:
        return gevonden
    return _match_model(stappen, rollen, reason_fn=reason_fn, ladder=ladder)


def roles_for_tekst(tekst: str, *, records, ai, skills_of, reason_fn=None,
                    ladder: str | None = None) -> list[dict]:
    """Dezelfde matcher, maar op één stuk TEKST in plaats van een plan.

    Bestaat zodat 'bij wie hoort deze spanning?' geen tweede matcher wordt: een spanning is hier
    gewoon een plan van één stap zonder skill, en valt dus meteen door naar de purpose-trede."""
    return roles_for([{"tekst": (tekst or "").strip(), "skill": None}],
                     records=records, ai=ai, skills_of=skills_of, reason_fn=reason_fn,
                     ladder=ladder)


def _rolnaam(rec) -> str:
    d = getattr(rec, "definition", None)
    return (getattr(d, "name", None) or getattr(rec, "id", "") or "").strip() or getattr(rec, "id", "")


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


def title_from(dod: str, *, reason_fn=reason) -> str:
    """Leid een korte, outcome-gerichte titel (max ~8 woorden) af uit de uitgebreide DoD.
    Fail-soft: valt de LLM weg, dan het eerste zinsdeel, ingekort."""
    dod = (dod or "").strip()
    if not dod:
        return ""
    out = reason_fn(
        "Vat deze project-uitkomst samen in een KORTE titel van maximaal 8 woorden. "
        "Outcome-gericht en concreet, geen werkwoord-opdracht, geen punt aan het eind, geen "
        "aanhalingstekens.\n\n"
        f"UITKOMST: {dod}\n\nOUTPUT: alleen de titel.",
        max_tokens=30, call_site="wizard_title")
    t = re.sub(r"\s+", " ", (out or "")).strip().strip('"“”‘’. ').strip()
    if not t:
        t = re.split(r"[.,:;]", dod)[0].strip()
    return (t or dod)[:80]


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
    prompt = (
        "Je breekt een projectdoel op in 2 tot 5 concrete stappen voor een zelfsturende rol.\n\n"
        f"DOEL (de uitkomst):\n\"{goal}\"\n\n"
        f"{kennis_section}"
        f"De skills van deze rol (de ENIGE tools), met hun input-vorm:\n{_catalog_block(catalog)}\n\n"
        + ("GEHEUGEN-EERST: er staat hierboven al kennis of eerder onderzoek. Bouw daarop VOORT: "
           "herhaal geen bestaand onderzoek en verzamel niet opnieuw wat er al ligt. Begin bij een "
           "SYNTHESE-stap (lees en combineer wat we al weten) en plan daarna alleen het écht "
           "ontbrekende stuk.\n"
           # DE HERKOMST VAN DAT BLOK MOET ERBIJ. Het is EXTERN onderzoek — patenten, papers,
           # radar-signalen — en géén inventaris van wat Nooch gebruikt. Zonder deze zin las het
           # model 'PHA, PBAT, algae-based' onder het kopje 'wat we al weten' en schreef het terug
           # als ONZE materialen, inclusief 'recycled' — een claim die wij niet zomaar mogen maken.
           "LET OP: dat blok is EXTERN ONDERZOEK (patenten, papers, marktsignalen), GEEN lijst van "
           "materialen of leveranciers die wij gebruiken. Schrijf nooit dat een materiaal uit dat "
           "blok van ons is, en neem er geen materiaalnamen uit over in de stappen.\n"
           if kennis_section else "")
        + "Voor ELK item: als één van deze skills het kan uitvoeren, geef de exacte skill-naam ÉN een "
        "'payload'-object dat voldoet aan de 'input'-vorm van die skill. Kan geen enkele skill het, "
        "zet skill=null en payload={} (dan wordt het een menselijke taak).\n"
        # VORM, expliciet en met een voorbeeld: de gemeten suggesties waren 25-40 woorden lang.
        f"VORM VAN EEN STAP: begint met een werkwoord, is ÉÉN handeling, en is hoogstens "
        f"{_MAX_STAP_WOORDEN} woorden. Geen toelichting, geen opsomming tussen haakjes. "
        "Goed: 'vraag drie leveranciers om technische specs'. "
        "Fout: 'Synthetiseer de bestaande inzichten en bevestigde bevindingen om de huidige "
        "kennis over plantaardige zolen te structureren'.\n"
        "Antwoord UITSLUITEND met JSON:\n"
        '{"items":[{"tekst":"...","skill":"skillnaam of null","payload":{}}]}')
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
