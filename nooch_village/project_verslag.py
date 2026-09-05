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
    deliverables wat de skills opleverden 197 van de 373 projecten heeft er, 652 in totaal

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
from nooch_village.projects import BEHAALD, NIET_BEHAALD, OVERGESLAGEN, heeft_seed_vorm

log = logging.getLogger("village.verslag")

# DE CAPS KNIPTEN FEITEN WEG. Een verslag zei "Paques niet bevestigd" terwijl de wall die
# communicatie wél toonde: de vermelding stond op positie 670 in een regel van 1296 tekens, en de
# cap stond op 600. Een tweede project verloor hem aan de regel-cap (23 regels → 20). Gemeten over
# alle 373 projecten: 3075 gespreksregels, 2696 in de prompt, 598 regels ingekort, 22 projecten die
# hele regels kwijtraakten.
#
# Verruimd naar 1500/50 op een meting, niet op gevoel. Mediaan en p90 van de totale invoer worden
# daarmee IDENTIEK aan volledig ongekapt (1556 / 3897 tokens) — de caps bijten alleen nog de
# uiterste staart, waar één project met 93 regels de kosten zou bepalen. Ter maat: de oude
# einddocument-synthese deed mediaan 4001 en p90 6519 in-tokens, dus dit blijft ruim goedkoper.
#
# Ze staan er nog wél: zonder cap loopt p99 naar 8698 en de max naar 11492 tokens, en dan bepaalt
# het langste gesprek van het dorp de prijs van elk verslag.
_REGEL_CAP = 1500
_MAX_REGELS = 50

# De sleutel is MECHANIEK en blijft Nederlands (hij wordt opgeslagen en vergeleken); het label is
# CONTENT en volgt de taal van het scherm. Dezelfde scheiding als `_IMPACT_LABEL` in views/projects.
# Zonder die scheiding lekte "onbekend (geen checklist om aan af te lezen)" letterlijk in een
# Engels verslag — gezien in de eerste echte assemblage op productie.
# Uit projects.py: één set sleutels voor het hele dorp. Hier stond een tweede spelling
# ("niet behaald" met een spatie) en die lekte als rauwe sleutel op het scherm.
ONBEKEND = "onbekend"

# TWEE TALEN, ÉÉN SLEUTEL. Scherm én verslag zijn nu Engels, passend bij de cockpit (i18n fase 1).
# De `taal`-parameter blijft bestaan: de sleutel is mechaniek en het label is content, en zodra er
# een taalinstelling komt hoeft alleen de aanroep te kiezen. Nu staat die keuze op één default —
# de infra bouwen we niet twee keer, maar we zetten hem ook niet nu al aan.
_VOORZET_LABEL = {
    "en": {BEHAALD: "achieved", NIET_BEHAALD: "not achieved",
           OVERGESLAGEN: "not recorded", ONBEKEND: "unclear"},
    "nl": {BEHAALD: "behaald", NIET_BEHAALD: "niet behaald",
           OVERGESLAGEN: "niet vastgelegd", ONBEKEND: "onduidelijk"},
}


def label_voor(voorzet: str, taal: str = "en") -> str:
    """Het label bij een voorzet-sleutel, in de taal van de lezer.

    Default Engels: dat is de schermtaal, en het scherm is de plek waar een ontbrekend label als
    rauwe sleutel zou opvallen. Onbekende sleutel → de sleutel zelf, zodat een nieuwe waarde
    zichtbaar wordt in plaats van stil als lege tekst te renderen."""
    return _VOORZET_LABEL.get(taal, _VOORZET_LABEL["en"]).get(voorzet, voorzet)


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


_DELIVERABLE_CAP = 1200          # per stuk; anders bepaalt één lange oplevering de hele invoer


def deliverable_blokken(deliverables, pid: str) -> list[str]:
    """De opgeleverde deliverables als tekstblokken. Fail-soft: geen store of een leesfout → leeg,
    want een verslag zonder deliverables is nog steeds een verslag.

    DEZE BRON KWAM VAN DE OUDE SYNTHESE. Die las hem al (652 deliverables over 197 projecten); hem
    niet overnemen zou betekenen dat het nieuwe pad mínder weet dan het oude, en dan is "de oude
    synthese vervangen" in werkelijkheid informatieverlies."""
    if deliverables is None or not pid:
        return []
    try:
        recs = deliverables.for_project(pid) or []
    except Exception as e:                                      # noqa: BLE001 - luid, niet stil
        log.warning("VERSLAG_DELIVERABLES_FAIL: niet te lezen voor %s: %s", pid, e)
        return []
    uit = []
    for r in recs:
        body = (r.get("summary") or "").strip()
        try:
            inhoud = deliverables.content_for(r["id"])
        except Exception:                                       # noqa: BLE001
            inhoud = None
        if inhoud:
            tekst = str(inhoud)
            body += "\n  " + (tekst[:_DELIVERABLE_CAP] + " …[ingekort]"
                              if len(tekst) > _DELIVERABLE_CAP else tekst)
        if body.strip():
            uit.append(body.strip())
    return uit


def bronnen_van(project: dict, document: str = "", deliverables: list | None = None) -> list[str]:
    """Welke bronnen dit verslag daadwerkelijk voedden. Alleen wat er ECHT is: een lege checklist
    is geen bron, en hem toch noemen maakt de provenance-telling een leugen.

    ENGELS, want deze lijst wordt op het SCHERM getoond ("assembled from 3 sources: …") en het
    scherm is Engels. Ze stonden even in het Nederlands mee met het verslag; toen dat terugging
    naar Engels bleven ze staan — zichtbaar als een halve zin in twee talen."""
    uit = []
    if (project.get("scope") or "").strip() or (project.get("done_when") or "").strip():
        uit.append("the project definition")
    items = _checklist_items(project)
    if items:
        af = sum(1 for i in items if i.get("done"))
        uit.append(f"the checklist ({af} of {len(items)} done)")
    regels = _gesprek(project)
    if regels:
        uit.append(f"the conversation ({len(regels)} lines)")
    if deliverables:
        uit.append(f"the delivered work ({len(deliverables)})")
    if _bruikbaar_document(document):
        uit.append("the existing end document")
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


def _materiaal(project: dict, document: str, deliverables: list | None = None) -> str:
    """Het ruwe materiaal, in de volgorde waarin een mens het zou lezen."""
    delen = [f"# {project.get('scope') or project.get('id')}"]
    dw = (project.get("done_when") or "").strip()
    if dw:
        delen.append(f"Desired outcome: {dw}")
    items = _checklist_items(project)
    if items:
        delen.append("\nChecklist:")
        for i in items:
            merk = "x" if i.get("done") else ("-" if i.get("skipped") else " ")
            delen.append(f"[{merk}] {i.get('text') or ''}")
    regels = _gesprek(project)
    if regels:
        delen.append("\nConversation:")
        delen.extend(regels)
    if deliverables:
        delen.append("\nDelivered work:")
        delen.extend(f"- {b}" for b in deliverables)
    if _bruikbaar_document(document):
        delen.append("\nExisting end document:\n" + document.strip())
    return "\n".join(delen)


_PROMPT = (
    "You are assembling a short project report for the founder, who will CONFIRM or correct it.\n\n"
    "WRITE IN ENGLISH, in markdown, at most ~250 words. The cockpit is in English and so is this "
    "report.\n\n"
    "GROUNDING RULE: everything you write must come literally from the material below. Do not "
    "invent results, numbers or conclusions. If something is not in there, say so.\n\n"
    "GOAL TYPE. Look first at what kind of project this is. For an ASSESSMENT project ('determine "
    "whether X is suitable', 'find out if Y is possible') the goal is ACHIEVED as soon as there is "
    "a grounded verdict — including a 'no'. A well-founded no is a successful investigation, not a "
    "failure. For a DELIVERY project ('produce X') the goal is achieved when the thing exists.\n\n"
    "Four headings, in this order, and nothing else:\n"
    "## Goal — the desired outcome, from the project definition. One or two sentences.\n"
    "## What happened — the story in running prose, derived from the checklist and the "
    "conversation. NO heading per task: weave the findings into one account. What was not "
    "investigated goes in a single closing sentence ('Not investigated: A, B') instead of a "
    "heading per task saying 'Status: not investigated'.\n"
    "## Result — whether the goal appears achieved, measured against the goal type above. The "
    "provisional verdict is given below; support it, or contradict it if the material says "
    "otherwise.\n"
    "## Learnings — what would go faster or better next time. Only if the material gives grounds "
    "for it; otherwise leave this heading out.\n"
)

# De vier koppen die de prompt vraagt, met de bijna-treffers die een model ervan maakt. "Lernings"
# is geen verzinsel: dat stond letterlijk in een document op productie. Een kop is een VAST LABEL —
# als hij uit modeltekst komt, is hij een typefout wachtend om te gebeuren, en dan vindt
# `met_result` de Result-sectie niet meer en valt het modeloordeel stil weg.
_KOP_NORMALISATIE = {
    "goal": "Goal", "doel": "Goal", "project goal": "Goal", "projectdoel": "Goal",
    "what happened": "What happened", "wat er gebeurde": "What happened",
    "what happend": "What happened", "whathappened": "What happened",
    "result": "Result", "resultaat": "Result", "results": "Result", "outcome": "Result",
    "learnings": "Learnings", "lernings": "Learnings", "leringen": "Learnings",
    "learning": "Learnings", "lessons learned": "Learnings", "lessons": "Learnings",
}


def normaliseer_koppen(md: str) -> str:
    """Zet de sectiekoppen op hun vaste label. Een kop die het model net anders spelt ("Lernings")
    breekt de zoekfunctie in `met_result` — dan verdwijnt het modeloordeel zonder foutmelding.

    Alleen KOPPEN worden geraakt, en alleen als ze herkend worden; een kop die we niet kennen laten
    we staan zoals hij is. Liever een onbekende kop zichtbaar dan stilletjes hernoemd naar iets wat
    het model niet bedoelde."""
    uit = []
    for regel in (md or "").splitlines():
        s2 = regel.strip()
        if s2.startswith("#"):
            hekjes = len(s2) - len(s2.lstrip("#"))
            tekst = s2.lstrip("#").strip().strip("*").strip()
            vast = _KOP_NORMALISATIE.get(tekst.casefold())
            if vast:
                uit.append("#" * hekjes + " " + vast)
                continue
        uit.append(regel)
    return "\n".join(uit)


def stel_samen(project: dict, document: str = "", *, reason=None,
               deliverables: list | None = None) -> Concept | None:
    """Stel het conceptverslag samen. `reason` is de LLM-functie (injectie, geen import in dit pad).

    ZONDER MODEL GEEN PROZA, MAAR WEL EEN VERSLAG. De feiten liggen er al; een model schrijft ze
    alleen leesbaar op. Valt het weg, dan komt er een gestructureerde variant uit dezelfde bronnen
    — geen verzonnen tekst, en zichtbaar soberder. Fail-closed betekent hier: niets bedenken, niet
    niets leveren.

    Geeft None als er werkelijk niets is om uit samen te stellen; dan hoort er geen verslag te zijn
    en zegt de kaart dat gewoon."""
    bronnen = bronnen_van(project, document, deliverables)
    if not bronnen:
        return None
    voorzet, reden = voorzet_result(project)
    mat = _materiaal(project, document, deliverables)

    # ALLEEN DE DEFINITIE IS NIETS OM OVER TE SCHRIJVEN. Dan kan een model niets doen behalve de
    # titel omschrijven en de gaten opvullen — en dat is precies hoe "an existing final document
    # titled 'Klaar wanneer'" ontstond. Gemeten: zo'n project houdt ~5 tokens materiaal over.
    # De gestructureerde variant zegt hetzelfde, eerlijker, en kost niets.
    genoeg = len(bronnen) > 1
    tekst = ""
    if reason is not None and genoeg:
        try:
            tekst = (reason(f"{_PROMPT}\nProvisional Result: {label_voor(voorzet)} ({reden}).\n\n"
                            f"--- MATERIAL ---\n{mat}", call_site="verslag_assemblage") or "").strip()
            # DE FENCE ERAF VÓÓR OPSLAG. Het model wikkelt zijn antwoord in ```markdown — gezien in
            # de eerste echte assemblage, en hetzelfde artefact als in 46 van de 307 bestaande
            # documenten. Op het scherm valt het niet op (`_md_doc` stript hem), maar bij bevestigen
            # wordt deze tekst het OPGESLAGEN document, en dan bestendigt hij precies de
            # opslag-rommel die we los aan het opruimen zijn. Zelfde helper als de essentie-ladder.
            # De fence eraf én de koppen op hun vaste label — in die volgorde, want een gefencete
            # tekst heeft nog geen leesbare koppen.
            tekst = normaliseer_koppen(ontfence(tekst)).strip()
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
    regels.append(f"## {KOP_RESULTAAT}\n{label_voor(voorzet).capitalize()} — {reden}.")
    regels.append("_Assembled without a language model: the facts above are listed as they "
                  "were recorded, not rewritten._")
    return "\n\n".join(regels)


# ── het menselijke sluitstuk ──────────────────────────────────────────────────────────────────
# Eén tabel voor beide: de voorzet en het menselijke oordeel spreken dezelfde taal.
_RESULT_LABEL = _VOORZET_LABEL["en"]   # het verslag volgt de cockpit-taal

# DE KOPNAMEN OP ÉÉN PLEK. Het verslag is Nederlands, dus de koppen ook — en `modeloordeel` en
# `met_result` zoeken ernaar. Stonden ze los, dan zou een prompt-wijziging ("Result" → "Resultaat")
# de zoekfunctie stil laten missen, en dan valt het modeloordeel weg zonder foutmelding. De Engelse
# namen blijven herkend voor documenten van vóór deze wijziging.
KOP_RESULTAAT = "Result"
KOP_LERINGEN = "Learnings"
# Beide talen blijven HERKEND, ook al schrijven we er nog maar één. Op productie staan documenten
# en een wachtend concept met Nederlandse koppen uit de dag dat het verslag Nederlands was; die
# moeten leesbaar blijven. Herkennen is goedkoop, een onleesbaar verslag niet.
_RESULTAAT_KOPPEN = {KOP_RESULTAAT.casefold(), "resultaat"}
_LERINGEN_KOPPEN = {KOP_LERINGEN.casefold(), "leringen"}


def _kopblok(tekst: str, koppen: set) -> str:
    """De tekst onder één van deze koppen, tot de volgende kop. "" als hij er niet is."""
    regels = (tekst or "").splitlines()
    for i, r in enumerate(regels):
        if r.strip().lower().lstrip("#").strip() in koppen:
            rest = []
            for volgende in regels[i + 1:]:
                if volgende.strip().startswith("#"):
                    break
                rest.append(volgende)
            return " ".join(x.strip() for x in rest if x.strip()).strip()
    return ""


def voorstel_toelichting(concept_tekst: str) -> str:
    """De Resultaat-alinea als VOORSTEL voor het toelichtingsveld.

    DE ANTI-HUISWERK-BELOFTE. Een leeg veld met "Why (one line)" laat de mens het werk doen dat de
    assembler net al deed: de analyse staat al in de wall en in het concept. Voorinvullen maakt van
    de vraag een AANVULLING in plaats van een opstel — en wie het niet eens is, overschrijft het.

    Het label ("Behaald.", "Niet behaald.") gaat eraf: dat staat al in de radio-keuze ernaast, en
    een toelichting die begint met het antwoord op de vraag ernaast leest als een echo."""
    t = _kopblok(concept_tekst, _RESULTAAT_KOPPEN)
    for lab in list(_VOORZET_LABEL["nl"].values()) + list(_VOORZET_LABEL["en"].values()):
        for vorm in (f"**{lab.capitalize()}.**", f"**{lab}.**", f"{lab.capitalize()}.", f"{lab}."):
            if t.lower().startswith(vorm.lower()):
                t = t[len(vorm):].strip()
                break
    return t[:600]


def voorstel_learnings(concept_tekst: str) -> str:
    """De Leringen-alinea als voorstel, of "" als het model er geen zag.

    LEEG IS EEN GELDIG VOORSTEL. De prompt zegt expliciet: alleen een Leringen-kop als het
    materiaal er aanleiding voor geeft. Een verzonnen lering is erger dan geen — dit veld is
    orggeheugen, geen invuloefening."""
    return _kopblok(concept_tekst, _LERINGEN_KOPPEN)[:600]


def modeloordeel_kort(concept_tekst: str) -> str:
    """Alleen het OORDEEL uit de Result-sectie, voor de signaalregel.

    `modeloordeel` geeft de hele alinea; die hoort in het rapport en niet in een balk van één regel
    — daar leest hij als een tweede samenvatting naast de eerste. Gezien in de render: "Draft
    concluded **Achieved.** The STCB grant was successfully submitted, approved, and funded."

    Neemt de eerste zin, strip de markdown-nadruk (die als sterretjes zou renderen omdat de
    signaalregel geëscapete tekst is, geen markdown) en kap op een woordgrens."""
    t = modeloordeel(concept_tekst)
    if not t:
        return ""
    t = t.replace("**", "").replace("__", "").strip()
    for punt in (". ", "! ", "? "):
        i = t.find(punt)
        if 0 < i <= 60:
            return t[:i]
    t = t.split(".")[0] if len(t.split(".")[0]) <= 60 else t
    if len(t) > 60:
        ruimte = t.rfind(" ", 0, 60)
        t = (t[:ruimte] if ruimte > 0 else t[:60]) + "…"
    return t.strip()


def modeloordeel(concept_tekst: str) -> str:
    """De Result-alinea die het MODEL schreef, uit het concept.

    Nodig omdat de twee signalen naast elkaar horen: het modeloordeel als voorstel en de
    checklist-staat als kruischeck. Botsen ze — zoals bij het barefoot-project, waar de checklist
    "af" zei en het gesprek "nog niet" — dan is dat iets om naar te kijken, niet iets om te
    verstoppen achter één samengevoegd cijfer.

    Geen kopje gevonden → "", en dan toont het scherm alleen de kruischeck. Liever niets dan een
    willekeurige alinea die zich voordoet als een oordeel."""
    return _kopblok(concept_tekst, _RESULTAAT_KOPPEN)[:400]


def result_blok(oordeel: str, toelichting: str = "", learnings: str = "") -> str:
    """Het definitieve Result-kopje, zoals het in het bevestigde document komt.

    DIT VERVANGT het Result van het model: de mens heeft het laatste woord. Het modeloordeel was
    een voorstel en heeft zijn werk gedaan zodra iemand erop reageert."""
    delen = [f"## {KOP_RESULTAAT}\n**{_RESULT_LABEL.get(oordeel, oordeel).capitalize()}.**"
             + (f" {toelichting.strip()}" if (toelichting or "").strip() else "")]
    if (learnings or "").strip():
        delen.append(f"## {KOP_LERINGEN}\n{learnings.strip()}")
    return "\n\n".join(delen)


def met_result(concept_tekst: str, oordeel: str, toelichting: str = "",
               learnings: str = "") -> str:
    """Zet het menselijke Result in de plaats van dat van het model, met behoud van de rest.

    GEEN INFORMATIEVERLIES: Goal en What happened blijven staan zoals ze waren; alleen het
    voorstel-Result maakt plaats voor het oordeel. Was er geen Result-kop (bijvoorbeeld in de
    modelloze variant), dan komt het blok er gewoon onder."""
    regels = (concept_tekst or "").splitlines()
    uit, i, geknipt = [], 0, False
    while i < len(regels):
        r = regels[i]
        if not geknipt and r.strip().lower().lstrip("#").strip() in (_RESULTAAT_KOPPEN | _LERINGEN_KOPPEN):
            geknipt = True
            i += 1
            while i < len(regels) and not regels[i].strip().startswith("#"):
                i += 1
            continue
        if geknipt and r.strip().lower().lstrip("#").strip() in _LERINGEN_KOPPEN:
            i += 1
            while i < len(regels) and not regels[i].strip().startswith("#"):
                i += 1
            continue
        uit.append(r)
        i += 1
    kop = "\n".join(uit).rstrip()
    return (kop + "\n\n" + result_blok(oordeel, toelichting, learnings)).strip()
