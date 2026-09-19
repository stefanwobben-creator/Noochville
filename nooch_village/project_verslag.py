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

from nooch_village.projects import BEHAALD, NIET_BEHAALD, OVERGESLAGEN

log = logging.getLogger("village.verslag")

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
