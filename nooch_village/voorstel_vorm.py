"""De vaste vorm van een rol-voorstel — en de degradatie als het bewijs het niet draagt.

Dit is de veiligheidskritische kern van de onderzoekspas, en daarom staat hij er vóór er ook maar
één voorstel uitgaat. De hele week draaide om één les: een systeem dat iets niet kan onderbouwen
moet dat zéggen, niet iets plausibels produceren. Een rol die de founder een zelfverzekerde
aanbeveling voorlegt die nergens op rust is erger dan een rol die niets voorlegt — de founder kan de
eerste niet van een gegronde onderscheiden, en beslist er wel op.

Twee mechanismen, in deze volgorde:

  1. **De pre-check** — een "voorstel" dat alleen vragen bevat en geen concrete actie is geen
     voorstel maar een menu, en dat is precies de route die we vervangen. Het gaat terug voor nog
     een onderzoekspas. Een kale vraag mag alleen door als de rol zijn onderzoeksskills echt heeft
     uitgeput én de ontbrekende input extern is. Zelfde discipline als de payload-reparatie: eerst
     zelf proberen, pas escaleren met het concrete gebrek.

  2. **De degradatie** — zakt het voorstel op de gegrond-as van de missie-critic, dan gaat het NIET
     als aanbeveling uit. Het wordt omgezet naar de eerlijke variant: dit vond ik, dit kan ik niet
     onderbouwen, dit is de open vraag. De bevindingen blijven staan (die zijn echt); alleen de
     aanbeveling vervalt. Nooit een verzonnen aanbeveling, ook niet als hij plausibel klinkt.

De vorm zelf is vast zodat de founder in tien seconden kan beslissen. Vijf velden, en `nodig_van_jou`
is bewust optioneel: een voorstel dat altijd iets van de founder vraagt is weer een menu.
"""
from __future__ import annotations

import logging
import re

log = logging.getLogger("village.voorstel")

# De vaste vorm. Volgorde = leesvolgorde op /founder.
VELDEN = ("actie", "bewijs", "risico", "nodig_van_jou", "onzeker")

VELD_LABEL = {
    "actie": "Wat ik wil doen",
    "bewijs": "Waarom, met bewijs",
    "risico": "Risico of kosten",
    "nodig_van_jou": "Wat ik van je nodig heb",
    "onzeker": "Wat nog onzeker is",
}

SOORT_VOORSTEL = "voorstel"          # een concrete aanbeveling, gegrond
SOORT_BEVINDING = "bevinding"        # gedegradeerd: bevindingen zonder aanbeveling
SOORT_VRAAG = "vraag"                # onderzoeksskills uitgeput, ontbrekende input is extern

# Een "actie" die alleen uit vraagtekens en werkwoorden van niet-doen bestaat is geen actie.
_VRAAGWOORDEN = re.compile(
    r"\b(wil je|zullen we|moeten we|kun je|kunt u|wat vind je|graag je (input|mening|akkoord)|"
    r"laat (me|ons) weten|hoe wil je|welke kant|ter beoordeling|wat is jouw)\b", re.I)
# Minimale lengte van een actie-zin. Korter dan dit is geen concrete actie maar een kop.
MIN_ACTIE_CHARS = 25


def _tekst(v) -> str:
    if isinstance(v, (list, tuple)):
        return " ".join(str(x) for x in v)
    return str(v or "")


def bevat_concrete_actie(voorstel: dict) -> tuple[bool, str]:
    """Bevat dit voorstel een uitvoerbare actie, of alleen vragen?

    Geen smaakoordeel over kwaliteit — alleen: staat er iets dat gedáán kan worden. De founder mag
    een slecht voorstel afwijzen; hij hoort geen menu te krijgen dat als voorstel is verpakt."""
    actie = _tekst(voorstel.get("actie")).strip()
    if len(actie) < MIN_ACTIE_CHARS:
        return False, f"de actie is {len(actie)} tekens — dat is geen concrete actie"
    if actie.rstrip().endswith("?"):
        return False, "de actie is een vraag, geen voorstel"
    if _VRAAGWOORDEN.search(actie):
        treffer = _VRAAGWOORDEN.search(actie).group(0)
        return False, f"de actie vraagt om een beslissing ('{treffer}') in plaats van er een voor te stellen"
    return True, ""


def heeft_bewijs(voorstel: dict) -> bool:
    """Draagt het voorstel minstens één herleidbare bron? Lege lijst = niets om op te steunen."""
    return bool([b for b in (voorstel.get("bewijs") or []) if isinstance(b, dict) and b.get("bron")])


def degradeer(voorstel: dict, waarom: str) -> dict:
    """Zet een voorstel om naar de eerlijke variant: bevindingen zonder aanbeveling.

    DE regel van deze week, hier hard ingebakken. Wat er blijft staan is wat de skills werkelijk
    ophaalden — dat is echt en het hoort de founder te bereiken. Wat vervalt is de aanbeveling, want
    díe is wat de critic niet gedekt vond. De open vraag wordt expliciet gesteld in plaats van
    verstopt in een zelfverzekerde zin."""
    uit = dict(voorstel)
    oude_actie = _tekst(voorstel.get("actie")).strip()
    uit["soort"] = SOORT_BEVINDING
    uit["actie"] = ("Geen aanbeveling — het bewijs draagt er geen. Dit is wat ik vond; de "
                    "beslissing is aan jou.")
    uit["gedegradeerd_van"] = oude_actie[:400]
    uit["waarom_gedegradeerd"] = str(waarom or "")[:400]
    # De open vraag is niet "wat wil je" maar "wat ontbreekt er om dit wél te kunnen zeggen".
    bestaand = _tekst(voorstel.get("onzeker")).strip()
    ontbreekt = (f"Wat ontbreekt om dit te onderbouwen: {waarom}" if waarom else
                 "Wat ontbreekt om dit te onderbouwen is niet vastgesteld.")
    uit["onzeker"] = f"{ontbreekt}\n{bestaand}".strip()
    log.info("voorstel gedegradeerd naar bevinding: %s", str(waarom)[:120])
    return uit


def als_vraag(voorstel: dict, gebrek: str) -> dict:
    """De enige route waarlangs een kale vraag de founder mag bereiken.

    Alleen als de rol zijn onderzoeksskills heeft uitgeput ÉN de ontbrekende input extern is. Het
    concrete gebrek gaat mee — niet "ik heb je input nodig" maar "bron X gaf niets op query Y"."""
    uit = dict(voorstel)
    uit["soort"] = SOORT_VRAAG
    uit["nodig_van_jou"] = str(gebrek or "").strip()[:600]
    return uit


def keur(voorstel: dict) -> tuple[bool, str]:
    """De pre-check vóór de critic. (mag door, waarom niet).

    Draait vóór de dure toets, zoals de goedkope critic-assen vóór de LLM-as: een menu hoeft geen
    premium-call om afgewezen te worden."""
    soort = voorstel.get("soort") or SOORT_VOORSTEL
    if soort == SOORT_VRAAG:
        if not _tekst(voorstel.get("nodig_van_jou")).strip():
            return False, "een vraag zonder concreet gebrek is geen vraag maar een menu"
        return True, ""
    ok, waarom = bevat_concrete_actie(voorstel)
    if not ok:
        return False, waarom
    if soort == SOORT_VOORSTEL and not heeft_bewijs(voorstel):
        return False, "een voorstel zonder herleidbare bron is een mening"
    return True, ""


def render(voorstel: dict) -> str:
    """Het voorstel als platte tekst in de vaste vorm — voor de critic én voor de founder-kaart."""
    regels = []
    soort = voorstel.get("soort") or SOORT_VOORSTEL
    if soort == SOORT_BEVINDING:
        regels.append("⚠️ GEDEGRADEERD — het bewijs droeg de aanbeveling niet.")
    for veld in VELDEN:
        waarde = voorstel.get(veld)
        if veld == "bewijs":
            bronnen = [b for b in (waarde or []) if isinstance(b, dict)]
            if not bronnen:
                continue
            regels.append(f"## {VELD_LABEL[veld]}")
            for b in bronnen:
                ref = f" [kroniek:{b['kroniek']}]" if b.get("kroniek") else ""
                regels.append(f"- {b.get('bron', '?')}: {str(b.get('citaat', ''))[:300]}{ref}")
            continue
        tekst = _tekst(waarde).strip()
        if not tekst:
            continue                                 # leeg veld valt weg; 'nodig_van_jou' mag leeg
        regels.append(f"## {VELD_LABEL[veld]}\n{tekst}")
    return "\n\n".join(regels)
