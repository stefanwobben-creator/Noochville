"""Bij wie hoort dit? — de classificatiestap vóór de terugval op de Circle Lead.

Werk dat bij niemand terechtkan gaat naar de Circle Lead. Dat is eerlijk (iemand ziet het) maar
armzalig (die iemand moet alles zelf uitzoeken). Deze module doet ertussenin één ding: een
SUGGESTIE met GROND, zodat de lezer iets te accepteren of te weerspreken heeft in plaats van een
lege regel.

TWEE VRAGEN, en ze zijn niet hetzelfde:

    vorm   is dit een ACCOUNTABILITY (structureel, hoort in een rol), een PROJECT (meerdere
           stappen, een uitkomst) of een ACTIE (één handeling)? Af te leiden uit het werkwoord en
           de zinsvorm.
    rol    welke rol past op het ONDERWERP? Gematcht tegen de accountabilities van de rollen in de
           cirkel — niet tegen niets, en niet tegen de rolnaam alleen.

GEEN GROND, GEEN SUGGESTIE. Dit is de hele regel. Het model noemt een rol én citeert de
accountability waarop het matcht, en dat citaat wordt daarna DETERMINISTISCH geverifieerd tegen de
records. Klopt het citaat niet, dan vervalt de suggestie — een verzonnen routering is erger dan
geen routering, want ze ziet er precies zo uit als een goede.

Zelfde vorm als de grond-check in `bevinding`: het model mag het oordeel geven, wij controleren of
het ergens op slaat.

DE FAALMODUS IS BEWUST SAAI. Geen model, geen krediet, geen rol met deze accountability, of een
citaat dat niet klopt → geen suggestie, en het werk gaat gewoon naar de Circle Lead met de reden
erbij. De routering verandert nooit door deze module; hij annoteert alleen. Daarom mag hij ook
falen zonder dat er werk zoekraakt.

EIGENAARSCHAP. Deze classificatie is het werk van een SECRETARY-rol (`SECRETARY_ACCOUNTABILITY`).
Slaapt die rol of bestaat hij niet, dan is er geen suggestie — en dat is de veilige terugval, want
de Circle Lead krijgt het werk sowieso.
"""
from __future__ import annotations

import json
import logging
import re

log = logging.getLogger("village.triage")

CALL_SITE = "triage_rol"

#: De accountability die een rol tot eigenaar van deze classificatie maakt. Geen rol met deze
#: tekst = geen classificatie; de Circle Lead vangt het werk dan gewoon op.
#:
#: ENGELS, EN DAT IS EEN KEUZE. De vijf buren op deze rol komen uit de GlassFrog-import en zijn
#: Engels; deze accountability verschijnt straks GECITEERD naast die vijf op het scherm. Eén
#: Nederlandse regel ertussen leest als een fout, niet als een keuze. De matching is toch
#: taal-onafhankelijk — het citaat wordt letterlijk vergeleken, niet vertaald.
#:
#: Rol-DNA is een RECORD dat als geheel wordt gelezen: nieuwe regels nemen de taal van hun buren, en
#: een taalwissel is een bewuste hele-rol-pass. Zie docs/CONVENTIES.md.
SECRETARY_ACCOUNTABILITY = "Classifying orphaned and AI work, and proposing the owning role"

VORMEN = ("accountability", "project", "actie")

# Deterministische voorzet op de VORM. Het model mag hem overrulen, maar zonder model is dit beter
# dan niets: een structuurwoord wijst naar een accountability, een meervoudige uitkomst naar een
# project, en de rest is één handeling.
_STRUCTUUR = re.compile(r"\b(structureel|terugkerend|elke week|wekelijks|maandelijks|voortaan|"
                        r"altijd|standaard|beleid|verantwoordelijk\w*|eigenaar\w*)\b", re.I)
_PROJECT = re.compile(r"\b(overzicht|compleet|opzetten|inrichten|implementat\w+|pijplijn|"
                      r"jaarlijks|migratie|onderzoek\w*|analyse|plan\b)\b", re.I)


def vorm_voorzet(tekst: str) -> str:
    """Vorm zonder model. Gratis, en het antwoord waar we op terugvallen."""
    t = tekst or ""
    if _STRUCTUUR.search(t):
        return "accountability"
    if _PROJECT.search(t):
        return "project"
    return "actie"


def secretary_rol(records) -> str:
    """De WAKKERE rol die deze classificatie bezit, of "" als niemand hem draagt.

    Op de accountability en niet op de naam: wie het werk draagt staat in zijn DNA, niet in zijn
    titel. Drie rollen heten 'Secretary' op prod; alleen wie deze accountability heeft doet dit."""
    naald = SECRETARY_ACCOUNTABILITY.lower()[:40]
    try:
        for r in records.all():
            if getattr(r, "archived", False) or getattr(r, "slaapt", False):
                continue
            accs = list(getattr(getattr(r, "definition", None), "accountabilities", None) or [])
            if any(naald in str(a).lower() for a in accs):
                return r.id
    except Exception:                                        # noqa: BLE001
        pass
    return ""


def _kandidaten(records, cirkel: str = "") -> list[dict]:
    """De rollen waar dit werk heen KÁN, met hun accountabilities. Zonder accountabilities geen
    kandidaat: er valt dan niets te matchen, en matchen op een naam is raden."""
    from nooch_village import org
    uit = []
    try:
        alle = list(records.all())
    except Exception:                                        # noqa: BLE001
        return []
    for r in alle:
        if getattr(r, "archived", False) or getattr(r, "slaapt", False) or org.is_circle(r):
            continue
        accs = [str(a).strip() for a in
                (getattr(getattr(r, "definition", None), "accountabilities", None) or []) if str(a).strip()]
        if not accs:
            continue
        if cirkel and getattr(r, "parent", "") != cirkel:
            continue
        uit.append({"id": r.id, "accountabilities": accs})
    return uit


_PROMPT = """Je bepaalt bij WIE een stuk werk hoort, en in welke VORM.

HET WERK:
{tekst}

DE ROLLEN DIE HET KUNNEN DRAGEN, met hun accountabilities:
{rollen}

Twee vragen.

1. "vorm" — precies één van: accountability, project, actie.
     accountability = het is structureel en hoort permanent bij een rol
     project        = meerdere stappen met één uitkomst
     actie          = één handeling

2. "rol" — welke rol hierboven past op het ONDERWERP van dit werk? Kies alleen als je het kunt
   staven, en citeer dan LETTERLIJK de accountability waarop je matcht in "accountability".
   Past er geen enkele, geef dan "rol": "" en "accountability": "". Dat is een geldig antwoord en
   beter dan een gok: een verzonnen routering ziet er precies zo uit als een goede.

Het citaat wordt gecontroleerd tegen de records. Verzin het niet en vat het niet samen — kopieer.

Antwoord ALLEEN met JSON:
{{"vorm": "...", "rol": "...", "accountability": "...", "waarom": "één korte zin"}}"""


def _citaat_klopt(citaat: str, accs: list[str]) -> str:
    """Staat dit citaat ECHT bij deze rol? Geeft de echte accountability terug, of "".

    Ruim in spelling, streng in inhoud: hoofdletters en spaties mogen verschillen, de woorden niet.
    Een samenvatting die 'er ongeveer op lijkt' is geen grond."""
    kaal = " ".join((citaat or "").lower().split())
    if len(kaal) < 12:
        return ""
    for a in accs:
        echt = " ".join(str(a).lower().split())
        if kaal in echt or echt in kaal:
            return a
    return ""


def classificeer(tekst: str, records, *, cirkel: str = "", reason_fn=None, ladder: str = "") -> dict:
    """Geeft {vorm, rol, accountability, waarom, grond}. `rol` is "" als er geen GEGRONDE match is.

    `grond` zegt waaróm er (g)een suggestie is — die zin gaat mee naar het scherm, want een lege
    band laat de lezer raden of we niets vonden of niet gekeken hebben."""
    leeg = {"vorm": vorm_voorzet(tekst), "rol": "", "accountability": "", "waarom": "",
            "grond": "geen classificatie gedraaid"}
    if not (tekst or "").strip():
        return {**leeg, "grond": "geen tekst om te classificeren"}
    eigenaar = secretary_rol(records)
    if not eigenaar:
        # De faalmodus die Stefan expliciet wilde: geen Secretary wakker → geen suggestie, en het
        # werk gaat gewoon naar de Circle Lead.
        return {**leeg, "grond": "geen wakkere rol met de classificatie-accountability"}
    kandidaten = _kandidaten(records, cirkel)
    if not kandidaten:
        return {**leeg, "grond": "geen rollen met accountabilities om tegen te matchen"}

    if reason_fn is None:
        from nooch_village.llm import reason as reason_fn                # noqa: PLC0415
    if not ladder:
        try:
            from nooch_village.llm import met_dorpsstaart
            ladder = met_dorpsstaart("mistral:mistral-small-latest")
        except Exception:                                    # noqa: BLE001
            ladder = ""
    rollen_blok = "\n".join(
        f"- {k['id']}\n" + "\n".join(f"    · {a}" for a in k["accountabilities"][:6])
        for k in kandidaten[:20])
    try:
        rauw = reason_fn(_PROMPT.format(tekst=(tekst or "")[:900], rollen=rollen_blok),
                         json_mode=True, max_tokens=400, call_site=CALL_SITE,
                         **({"ladder": ladder} if ladder else {}))
    except Exception as e:                                   # noqa: BLE001 — nooit blokkeren
        log.warning("triage: classificatie faalde (%s)", e)
        return {**leeg, "grond": f"classificatie faalde: {e}"[:120]}
    if not rauw:
        return {**leeg, "grond": "geen antwoord van het model"}
    m = re.search(r"\{.*\}", str(rauw), re.DOTALL)
    try:
        data = json.loads(m.group(0)) if m else {}
    except ValueError:
        data = {}

    vorm = str(data.get("vorm") or "").strip().lower()
    if vorm not in VORMEN:
        vorm = vorm_voorzet(tekst)
    rol = str(data.get("rol") or "").strip()
    citaat = str(data.get("accountability") or "").strip()
    waarom = str(data.get("waarom") or "").strip()[:200]

    kandidaat = next((k for k in kandidaten if k["id"] == rol), None)
    if kandidaat is None:
        return {"vorm": vorm, "rol": "", "accountability": "", "waarom": waarom,
                "grond": "het model noemde een rol die niet in de lijst staat"}
    echt = _citaat_klopt(citaat, kandidaat["accountabilities"])
    if not echt:
        # GEEN GROND, GEEN SUGGESTIE. Het model mag het oordeel geven; wij controleren of het
        # ergens op slaat. Een citaat dat niet in de records staat is een verzinsel, en dat is
        # gevaarlijker dan zwijgen omdat het er precies zo uitziet als een goede match.
        log.info("triage: citaat niet terug te vinden bij %s — suggestie vervalt", rol)
        return {"vorm": vorm, "rol": "", "accountability": "", "waarom": waarom,
                "grond": "de geciteerde accountability staat niet bij die rol"}
    return {"vorm": vorm, "rol": rol, "accountability": echt, "waarom": waarom,
            "grond": f"gematcht door {eigenaar}"}
