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
        rollen = list(records.all())
    except Exception as e:                                   # noqa: BLE001
        # EEN AANROEPFOUT IS GEEN AFWEZIGHEID. Hier stond `except Exception: pass`, en die maakte
        # van élke fout een lege string — niet te onderscheiden van "geen enkele rol draagt deze
        # accountability". Op 4 sep 2026 gaf ik deze functie een LIJST waar hij de store verwacht;
        # `records.all()` bestond daar niet, de except slikte het, en de uitkomst las als "de
        # secretary slaapt". Ik heb dat als systeembevinding gerapporteerd voor ik het doorhad.
        #
        # De uitkomst blijft "" — de aanroeper hoort niet te klappen omdat de classificatie niet
        # lukt — maar hij is nu hoorbaar, en de melding noemt het type dat binnenkwam.
        log.warning("secretary_rol: records niet op te sommen (%s: %s) — behandeld als 'geen "
                    "secretary', maar dit is een AANROEPFOUT en geen lege org",
                    type(e).__name__, e)
        return ""
    for r in rollen:
        if getattr(r, "archived", False) or getattr(r, "slaapt", False):
            continue
        accs = list(getattr(getattr(r, "definition", None), "accountabilities", None) or [])
        if any(naald in str(a).lower() for a in accs):
            return r.id
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


# ── De meting ───────────────────────────────────────────────────────────────
#
# GROND STOPT FABRICATIE, NIET IRRELEVANTIE. Op prod bleek een ECHT citaat goedkoop: het model vond
# voor een lekkende koffiemachine netjes "Facilitating the Circle's regular Tactical Meetings" — waar
# en volstrekt naast de kwestie. De poort liet het door, terecht, want passendheid is oordeel.
#
# Dan is de vraag niet "hoe bouwen we een strengere poort" maar "hoe vaak stoort het". Daarom deze
# laag: per suggestie vastleggen wat de mens ermee deed. Geen UI erbij — de drie handelingen bestaan
# al; we noteren alleen welke het werd.

BESTAND = "triage_uitkomsten.jsonl"

#: Wat er met een suggestie kan gebeuren. Vier, want "geen suggestie" is geen uitkomst maar een
#: andere vraag, en die telt niet mee in de ratio.
UITKOMSTEN = ("geaccepteerd", "overschreven", "zelf", "anders")


def noteer_uitkomst(data_dir: str, n: dict, *, gekozen_rol: str = "", gekozen_persoon: str = "",
                    otype: str = "") -> str:
    """Leg vast wat er met een rolsuggestie gebeurde. Geeft de uitkomst terug, of "".

    Fail-soft en STIL mag hier: een meting die een handeling blokkeert is geen meting maar een
    obstakel. Draagt het item geen suggestie, dan is er niets te meten."""
    voorgesteld = str((n or {}).get("triage_rol") or "")
    if not voorgesteld:
        return ""
    if otype and otype != "action":
        uitkomst = "anders"
    elif gekozen_rol and gekozen_rol == voorgesteld:
        uitkomst = "geaccepteerd"
    elif gekozen_rol or gekozen_persoon:
        uitkomst = "overschreven"
    else:
        uitkomst = "zelf"
    try:
        import os
        import time
        pad = os.path.join(data_dir or ".", BESTAND)
        os.makedirs(os.path.dirname(pad) or ".", exist_ok=True)
        with open(pad, "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": time.time(), "nid": (n or {}).get("id", ""),
                                "voorgesteld": voorgesteld,
                                "gekozen": gekozen_rol or gekozen_persoon or "",
                                "otype": otype, "uitkomst": uitkomst,
                                "accountability": str((n or {}).get("triage_accountability") or "")[:200],
                                }, ensure_ascii=False) + "\n")
    except Exception as e:                                   # noqa: BLE001 — nooit een handeling breken
        log.warning("triage-meting niet vastgelegd: %s", e)
    return uitkomst


def acceptatie(data_dir: str) -> dict:
    """De ratio waar dit allemaal om draait: hoe vaak was de suggestie bruikbaar?

    `ratio` telt alleen de gevallen waarin de mens een ROL koos — accepteren of overschrijven. "Zelf
    houden" en "andere uitkomst" zeggen niets over de suggestie: dan ging het werk ergens anders
    heen om een reden die los staat van wie het zou moeten doen."""
    import os
    rijen = []
    try:
        with open(os.path.join(data_dir or ".", BESTAND), encoding="utf-8") as f:
            for r in f:
                try:
                    rijen.append(json.loads(r))
                except ValueError:
                    continue
    except FileNotFoundError:
        return {"n": 0, "ratio": None, **{u: 0 for u in UITKOMSTEN}}
    telling = {u: sum(1 for r in rijen if r.get("uitkomst") == u) for u in UITKOMSTEN}
    keuzes = telling["geaccepteerd"] + telling["overschreven"]
    return {"n": len(rijen), "ratio": (telling["geaccepteerd"] / keuzes) if keuzes else None,
            **telling}


# ── wie krijgt dit werk, als MENS? ────────────────────────────────────────────────────────────

def domein_eigenaar(st, domein: str) -> dict:
    """De wakkere rol die dit DOMEIN houdt → {rol, grond}. `rol` is "" als er geen eigenaar is.

    Een domein is een VERKLARING ("deze rol bezit dit onderwerp"), geen gevolgtrekking uit tekst.
    Daarom staat hij vóór de secretary-classificatie: die matcht accountability-tekst via een model
    en is dus tekstgestuurd — subtieler dan een vaste rol-id, maar even broos.
    `radar_beoordeling.rol_voor` noteerde het al: "domein-match zou sterker zijn … zodra rollen ze
    krijgen". Dit is die zodra.

    DRIE UITKOMSTEN, EN TWEE ERVAN ZIJN NIET HETZELFDE:

      geen domein geconfigureerd  → STILLE terugval. Niets mis: de config zegt niets over
                                    eigenaarschap, en de secretary neemt het over.
      domein houdt niemand        → LUIDE logregel. Dit is een CONFIG-FOUT (typefout, of het
                                    governance-akte is nooit gezet). Zonder die regel routeert de
                                    radar stil voor altijd naar de founder: een signaal dat bestaat
                                    maar niet gelezen wordt.
      twee rollen houden het      → LUIDE logregel plus terugval. Twee eigenaren van één domein is
                                    een governance-fout; ertussen kiezen zou die fout verbergen
                                    achter een gok.

    `grond` reist mee, zodat een droge run leesbaar is zonder de code ernaast te leggen."""
    domein = (domein or "").strip()
    if not domein:
        return {"rol": "", "grond": "geen eigenaar_domein geconfigureerd"}
    naald = domein.lower()
    houders = []
    try:
        for r in st.records.all():
            if getattr(r, "archived", False) or getattr(r, "slaapt", False):
                continue
            doms = list(getattr(getattr(r, "definition", None), "domains", None) or [])
            if any(naald == str(d).strip().lower() for d in doms):
                houders.append(r.id)
    except Exception:                                        # noqa: BLE001
        log.warning("domein-eigenaar zoeken faalde voor %r", domein, exc_info=True)
        return {"rol": "", "grond": f"domein {domein!r} niet op te zoeken"}

    if len(houders) == 1:
        return {"rol": houders[0], "grond": f"houdt het domein {domein!r}"}
    if len(houders) > 1:
        log.warning("GOVERNANCE-FOUT: domein %r wordt gehouden door %d rollen (%s) — geen "
                    "eigenaar aangewezen, terugval op de classificatie",
                    domein, len(houders), ", ".join(houders))
        return {"rol": "", "grond": f"meerdere rollen houden {domein!r}"}
    log.warning("CONFIG-FOUT: domein %r is geconfigureerd maar wordt door GEEN enkele wakkere rol "
                "gehouden — typefout, of het governance-akte is nooit gezet. Tot dat klopt "
                "routeert dit naar de Circle Lead of de founder.", domein)
    return {"rol": "", "grond": f"domein {domein!r} wordt door niemand gehouden"}


def menselijke_eigenaar(st, tekst: str, *, reason_fn=None, domein: str = "") -> dict:
    """De rol die dit werk hoort te dragen ÉN door een mens vervuld wordt.

    ÉÉN LOOKUP, TWEE GEBRUIKEN: de memo-ontvanger en de landing van het project dat eruit volgt.
    Zou de memo naar de ene rol gaan en het project naar de andere, dan kan "één persoon oordeelt
    én bezit" alleen per toeval kloppen — en breekt het stil zodra de org verschuift.

    Geen vaste rol-id. `classificeer` matcht de tekst tegen de ACTUELE accountabilities, dus een
    andere vervuller én een verplaatste eigenaar-rol worden allebei gevolgd.

    DRIE FAIL-OPENS, want dit mag nooit stil wegvallen:
      geen gegronde match      → Circle Lead van de cirkel
      rol zonder MENS          → Circle Lead. Let op: een AI-vervulde rol is hier net zo goed
                                 onbruikbaar als een lege — een persona leest de NotifStore nooit,
                                 dus een bericht daarheen is een dead letter (zie CLAUDE.md).
                                 `bestemming()` hopt hier NIET, want die vraagt of de rol kan
                                 UITVOEREN, en dat kan een persona; wij vragen of er iemand LEEST.
      ook de lead onbemand     → de founder-rol, het laatste adres dat altijd bestaat

    Geeft {rol, mens, waarom, via} — `via` vertelt hoe hij daar kwam, zodat een droge run leesbaar
    is zonder de code ernaast te leggen."""
    from nooch_village.cockpit2 import mens_vervullers, _circle_lead_van   # noqa: PLC0415
    from nooch_village.human_inbox import FOUNDER_ROLE_ID                  # noqa: PLC0415

    # DOMEIN EERST: een verklaring gaat vóór een gevolgtrekking. Houdt niemand het domein (of is er
    # geen geconfigureerd), dan neemt de secretary het over — `domein_eigenaar` heeft het verschil
    # tussen "niets geconfigureerd" en "config-fout" dan al geLOGD.
    dom = domein_eigenaar(st, domein)
    if dom["rol"]:
        rol, waarom = dom["rol"], dom["grond"]
    else:
        uitslag = classificeer(tekst, st.records, reason_fn=reason_fn)
        rol = uitslag.get("rol") or ""
        waarom = uitslag.get("grond") or ""
        if domein:
            waarom = f"{dom['grond']}; {waarom}"

    def _mens(r):
        return (mens_vervullers(st, r) or [None])[0] if r else None

    if rol and _mens(rol):
        return {"rol": rol, "mens": _mens(rol), "waarom": waarom, "via": ""}

    reden = ("geen gegronde match" if not rol
             else f"{rol} heeft geen menselijke vervuller")
    lead = _circle_lead_van(st, rol) if rol else ""
    if lead and _mens(lead):
        return {"rol": lead, "mens": _mens(lead), "waarom": waarom, "via": reden}

    return {"rol": FOUNDER_ROLE_ID, "mens": _mens(FOUNDER_ROLE_ID), "waarom": waarom,
            "via": f"{reden}; ook de Circle Lead is onbemand"}
