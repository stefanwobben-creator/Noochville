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

log = logging.getLogger("village.verslag")

# Per gespreksregel, zodat één rol-dump van 1500 tekens de invoer niet overheerst. Gemeten: met
# deze cap is de mediane invoer ~982 tokens, zonder cap ~1385 en de staart loopt naar 6846.
_REGEL_CAP = 600
_MAX_REGELS = 20            # de laatste 20; oudere regels zijn zelden nog het verhaal van de afloop

BEHAALD = "behaald"
NIET_BEHAALD = "niet behaald"
ONBEKEND = "onbekend"


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
        return ONBEKEND, "geen checklist om aan af te lezen"
    af = [i for i in items if i.get("done")]
    over = [i for i in items if not i.get("done") and not i.get("skipped")]
    if not over:
        return BEHAALD, f"alle {len(items)} checklist-items zijn afgevinkt of overgeslagen"
    if not af:
        return NIET_BEHAALD, f"geen van de {len(items)} checklist-items is afgevinkt"
    return ONBEKEND, f"{len(af)} van {len(items)} items af — te weinig om uit af te leiden"


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
    if (document or "").strip():
        uit.append("het bestaande einddocument")
    return uit


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
    if (document or "").strip():
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

    tekst = ""
    if reason is not None:
        try:
            tekst = (reason(f"{_PROMPT}\nVoorzet voor Result: {voorzet} ({reden}).\n\n"
                            f"--- MATERIAAL ---\n{mat}", call_site="verslag_assemblage") or "").strip()
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
    regels.append(f"## Result\n{voorzet} — {reden}.")
    regels.append("_Assembled without a language model: the facts below are listed as they were "
                  "recorded, not rewritten._")
    return "\n\n".join(regels)
