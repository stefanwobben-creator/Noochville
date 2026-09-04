"""Het projectverslag dat zichzelf samenstelt — bij afsluiting, uit wat er al ligt.

HOLACRACY-ZUIVER, EN DAAROM WEINIG VELDEN. Een project ís een gewenst resultaat, dus de
projectdefinitie is het doel — er is geen apart Goal-veld en dat hoeft er ook niet te komen.
Gemeten in de wizard: één invoer (`uitkomst`) wordt zowel `scope` (de korte titel) als
`done_when` (de volledige uitkomst). Wat er gebeurde staat in de checklist en het gesprek. Wat het
opleverde is het enige menselijke momentje, en dat komt in een latere PR.

WAT DEZE MODULE WEL DOET: bij het afsluiten één keer een CONCEPT samenstellen uit het materiaal
dat er al is, met een provisionele voorzet voor het resultaat. Wat hij NIET doet: iets afdwingen.
Er is geen poort. Mislukt de assemblage, dan is het project gewoon afgesloten en staat er geen
verslag — luidruchtig gelogd, niet stil.

DE VIER BRONNEN, en waarom precies deze:

    definitie    scope + done_when      het doel; bij 21% van de afgesloten projecten op productie
                                        is `done_when` leeg en is de titel het hele doel
    checklist    items + wat afgevinkt   het logboek van wat er gebeurde (gem. 3,6 items, 3,3 af)
    gesprek      log-regels met tekst    waar rollen en mensen verslag deden
    document     het bestaande einddoc   de rijkste bron; 57 van 57 afgesloten projecten heeft er een

Het bestaande document is een BRON en geen slachtoffer: het concept wacht naast het document
(`ProjectDocStore.write_concept`) en vervangt het pas als een mens bevestigt. Deze store houdt geen
versies, dus meteen overschrijven zou de werkoutput onherroepelijk wissen.

TWEE LOGFORMATEN. Het gesprek bestaat op productie uit een oud formaat (`{who, text}`, 2311 regels,
vaak hele rol-dumps van meer dan 1000 tekens) en een nieuw (`{kind, author, text}`, 715 regels).
`_gesprek` leest beide en kapt lange regels af — anders bepaalt één dump de helft van de invoer.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from nooch_village.project_essentie import ontfence
from nooch_village.projects import heeft_seed_vorm

log = logging.getLogger("village.verslag")

# Per gespreksregel, zodat één rol-dump van 1500 tekens de invoer niet overheerst. Gemeten: met
# deze cap is de mediane invoer ~982 tokens, zonder cap ~1385 en de staart loopt naar 6846.
_REGEL_CAP = 600
_MAX_REGELS = 20            # de laatste 20; oudere regels zijn zelden nog het verhaal van de afloop

# De sleutel is MECHANIEK en blijft Nederlands (hij wordt opgeslagen en vergeleken); het label is
# CONTENT en volgt de taal van het scherm. Dezelfde scheiding als `_IMPACT_LABEL` in views/projects.
# Zonder die scheiding lekte "onbekend (geen checklist om aan af te lezen)" letterlijk in een
# Engels verslag — gezien in de eerste echte assemblage op productie.
BEHAALD = "behaald"
NIET_BEHAALD = "niet behaald"
ONBEKEND = "onbekend"

_VOORZET_LABEL = {BEHAALD: "achieved", NIET_BEHAALD: "not achieved", ONBEKEND: "unclear"}


def label_voor(voorzet: str) -> str:
    """Het Engelse label bij een voorzet-sleutel. Onbekende sleutel → de sleutel zelf, zodat een
    nieuwe waarde zichtbaar wordt in plaats van stil als lege tekst te renderen."""
    return _VOORZET_LABEL.get(voorzet, voorzet)


@dataclass(frozen=True)
class Concept:
    """Een samengesteld conceptverslag: tekst plus waar hij vandaan komt.

    `bronnen` is geen decoratie. Een verslag dat een mens moet bevestigen, moet laten zien waaruit
    het is samengesteld — anders bevestigt hij een tekst en niet een afleiding."""
    tekst: str
    bronnen: list[str] = field(default_factory=list)
    voorzet: str = ONBEKEND
    voorzet_reden: str = ""


def _checklist_items(project: dict) -> list[dict]:
    return [i for c in (project.get("checklists") or []) for i in (c.get("items") or [])
            if isinstance(i, dict)]


def _gesprek(project: dict) -> list[str]:
    """De gesprekregels, beide formaten, nieuwste laatst, elk afgekapt."""
    uit: list[str] = []
    for e in (project.get("log") or []):
        if not isinstance(e, dict):
            continue
        t = (e.get("text") or "").strip()
        if not t:
            continue
        wie = e.get("who")
        if not wie:
            a = e.get("author")
            wie = (a.get("type") if isinstance(a, dict) else None) or "onbekend"
        kort = t[:_REGEL_CAP] + (" …[ingekort]" if len(t) > _REGEL_CAP else "")
        uit.append(f"{wie}: {kort}")
    return uit[-_MAX_REGELS:]


def voorzet_result(project: dict) -> tuple[str, str]:
    """De PROVISIONELE voorzet voor "doel behaald?" — deterministisch, geen model.

    Checklist helemaal af → waarschijnlijk behaald. Niets afgevinkt terwijl er wel items zijn →
    waarschijnlijk niet. Alles daartussen, of geen checklist → onbekend, en dan zegt het verslag
    dat eerlijk in plaats van te gokken.

    DIT IS EEN VOORZET, GEEN OORDEEL. Een "nee" moet net zo makkelijk kunnen als een "ja"; een
    project dat stil als done wordt weggezet terwijl het resultaat er niet kwam is precies de
    stille mislukking die we vermijden. De mens bevestigt of corrigeert (volgende PR)."""
    items = _checklist_items(project)
    if not items:
        return ONBEKEND, "there is no checklist to read progress from"
    af = [i for i in items if i.get("done")]
    over = [i for i in items if not i.get("done") and not i.get("skipped")]
    if not over:
        return BEHAALD, f"all {len(items)} checklist items are ticked or skipped"
    if not af:
        return NIET_BEHAALD, f"none of the {len(items)} checklist items is ticked"
    return ONBEKEND, f"{len(af)} of {len(items)} items done — too little to conclude from"


def bronnen_van(project: dict, document: str = "") -> list[str]:
    """Welke bronnen dit verslag daadwerkelijk voedden. Alleen wat er ECHT is: een lege checklist
    is geen bron, en hem toch noemen maakt de provenance-telling een leugen."""
    uit = []
    if (project.get("scope") or "").strip() or (project.get("done_when") or "").strip():
        uit.append("de projectdefinitie")
    items = _checklist_items(project)
    if items:
        af = sum(1 for i in items if i.get("done"))
        uit.append(f"de checklist ({af} van {len(items)} af)")
    regels = _gesprek(project)
    if regels:
        uit.append(f"het gesprek ({len(regels)} regels)")
    if _bruikbaar_document(document):
        uit.append("het bestaande einddocument")
    return uit


def _bruikbaar_document(document: str) -> bool:
    """Telt dit document als bron?

    NEE ALS HET DE SEED IS. Bij 31% van de afgesloten projecten op productie is het "document"
    niets dan de geseede opdracht. Dat als vierde bron meetellen maakt de provenance-telling
    onwaar, en het als materiaal aanbieden zet het model op een dwaalspoor: in de eerste echte
    assemblage schreef het "an existing final document titled 'Klaar wanneer'" — het las de
    seed-kop als een documenttitel. De opdracht komt al binnen via `done_when`; twee keer
    aanbieden voegt niets toe en verzint iets."""
    return bool((document or "").strip()) and not heeft_seed_vorm(document)


def _materiaal(project: dict, document: str) -> str:
    """Het ruwe materiaal, in de volgorde waarin een mens het zou lezen."""
    delen = [f"# {project.get('scope') or project.get('id')}"]
    dw = (project.get("done_when") or "").strip()
    if dw:
        delen.append(f"Gewenst resultaat: {dw}")
    items = _checklist_items(project)
    if items:
        delen.append("\nChecklist:")
        for i in items:
            merk = "x" if i.get("done") else ("-" if i.get("skipped") else " ")
            delen.append(f"[{merk}] {i.get('text') or ''}")
    regels = _gesprek(project)
    if regels:
        delen.append("\nGesprek:")
        delen.extend(regels)
    if _bruikbaar_document(document):
        delen.append("\nBestaand einddocument:\n" + document.strip())
    return "\n".join(delen)


_PROMPT = (
    "Je stelt een kort projectverslag samen voor een mens die het gaat BEVESTIGEN of corrigeren.\n"
    "Schrijf in het Engels, in markdown, maximaal ~250 woorden.\n\n"
    "GRONDINGSREGEL: alles wat je schrijft moet letterlijk uit het materiaal hieronder komen. "
    "Verzin geen resultaten, getallen of conclusies. Staat er iets niet in, schrijf dan dat het "
    "er niet in staat.\n\n"
    "Drie kopjes, in deze volgorde:\n"
    "## Goal — het gewenste resultaat, uit de projectdefinitie. Eén of twee zinnen.\n"
    "## What happened — wat er gebeurde, afgeleid uit de checklist en het gesprek. Feiten, geen "
    "interpretatie.\n"
    "## Result — of het doel behaald lijkt. De voorzet staat hieronder; onderbouw hem uit het "
    "materiaal of spreek hem tegen als het materiaal iets anders zegt. Een 'niet behaald' is een "
    "even goede uitkomst als een 'behaald' — schrijf het gewoon op.\n"
)


def stel_samen(project: dict, document: str = "", *, reason=None) -> Concept | None:
    """Stel het conceptverslag samen. `reason` is de LLM-functie (injectie, geen import in dit pad).

    ZONDER MODEL GEEN PROZA, MAAR WEL EEN VERSLAG. De feiten liggen er al; een model schrijft ze
    alleen leesbaar op. Valt het weg, dan komt er een gestructureerde variant uit dezelfde bronnen
    — geen verzonnen tekst, en zichtbaar soberder. Fail-closed betekent hier: niets bedenken, niet
    niets leveren.

    Geeft None als er werkelijk niets is om uit samen te stellen; dan hoort er geen verslag te zijn
    en zegt de kaart dat gewoon."""
    bronnen = bronnen_van(project, document)
    if not bronnen:
        return None
    voorzet, reden = voorzet_result(project)
    mat = _materiaal(project, document)

    # ALLEEN DE DEFINITIE IS NIETS OM OVER TE SCHRIJVEN. Dan kan een model niets doen behalve de
    # titel omschrijven en de gaten opvullen — en dat is precies hoe "an existing final document
    # titled 'Klaar wanneer'" ontstond. Gemeten: zo'n project houdt ~5 tokens materiaal over.
    # De gestructureerde variant zegt hetzelfde, eerlijker, en kost niets.
    genoeg = len(bronnen) > 1
    tekst = ""
    if reason is not None and genoeg:
        try:
            tekst = (reason(f"{_PROMPT}\nProvisional Result: {label_voor(voorzet)} ({reden}).\n\n"
                            f"--- MATERIAAL ---\n{mat}", call_site="verslag_assemblage") or "").strip()
            # DE FENCE ERAF VÓÓR OPSLAG. Het model wikkelt zijn antwoord in ```markdown — gezien in
            # de eerste echte assemblage, en hetzelfde artefact als in 46 van de 307 bestaande
            # documenten. Op het scherm valt het niet op (`_md_doc` stript hem), maar bij bevestigen
            # wordt deze tekst het OPGESLAGEN document, en dan bestendigt hij precies de
            # opslag-rommel die we los aan het opruimen zijn. Zelfde helper als de essentie-ladder.
            tekst = ontfence(tekst).strip()
        except Exception as e:                                  # noqa: BLE001 - luid, niet stil
            log.warning("VERSLAG_LLM_FAIL: assemblage voor %s mislukt (%s) — "
                        "terugval op de gestructureerde variant", project.get("id"), e)
    if not tekst:
        tekst = _zonder_model(project, document, voorzet, reden)
    return Concept(tekst=tekst, bronnen=bronnen, voorzet=voorzet, voorzet_reden=reden)


def _zonder_model(project: dict, document: str, voorzet: str, reden: str) -> str:
    """De terugval: dezelfde drie kopjes, maar met het ruwe materiaal in plaats van proza.

    Bewust herkenbaar soberder. Wie dit leest moet kunnen zien dat er geen model aan te pas kwam,
    anders leest een kale opsomming als een geschreven verslag."""
    dw = (project.get("done_when") or "").strip()
    regels = [f"## Goal\n{dw or (project.get('scope') or '')}"]
    items = _checklist_items(project)
    if items:
        gedaan = [f"- {i.get('text') or ''}" for i in items if i.get("done")]
        open_ = [f"- {i.get('text') or ''}" for i in items
                 if not i.get("done") and not i.get("skipped")]
        stuk = ["## What happened"]
        if gedaan:
            stuk.append("Done:\n" + "\n".join(gedaan))
        if open_:
            stuk.append("Still open:\n" + "\n".join(open_))
        regels.append("\n\n".join(stuk))
    else:
        regels.append("## What happened\nNo checklist was kept for this project.")
    regels.append(f"## Result\n{label_voor(voorzet)} — {reden}.")
    regels.append("_Assembled without a language model: the facts below are listed as they were "
                  "recorded, not rewritten._")
    return "\n\n".join(regels)
