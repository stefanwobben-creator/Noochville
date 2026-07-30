"""claims_modelpas.py — de recall-pas: claims vinden die geen enkele lijstterm raken.

De regex vangt bekende woorden. Wat hij per definitie niet vangt is de slim geformuleerde claim:
"onze zolen verdwijnen gewoon weer in de grond" staat in geen termenlijst en is toch een
afbreekbaarheidsclaim. Deze module laat één LLM-pas over de paginatekst lopen en levert ZINNEN op
die een milieuclaim over ons eigen product maken zónder een lijstterm te raken.

Dit is het spiegelbeeld van `claims_context`: die NEEMT valse positieven WEG van bestaande hits;
deze VOEGT kandidaten TOE die de regex miste. Ze mogen nooit door elkaar lopen — het ene filtert,
het andere vindt.

Vier regels:

1. **Afgesteld op recall.** Bij twijfel meldt het model de zin, en de bevinding gaat naar
   compliance. Een onterechte vlag kost een muisklik; een gemiste claim kost een boete.
2. **Gegrond in de records.** Het regelkader in de prompt wordt OPGEBOUWD uit de claims-database
   (`meta.toetsingskader`, `meta.regelgeving`, de categorieën, een greep uit de bestaande termen).
   Cureert compliance de database, dan verandert de prompt mee — geen tweede regelboek in code.
3. **Nooit rood, nooit gehallucineerd.** Rood is een wetsoordeel dat alleen uit de termen-database
   mag komen (`meta.toetsingskader.principe`); een modelvondst is een vermoeden. En het teruggegeven
   fragment moet LETTERLIJK in de paginatekst staan, anders valt de kandidaat af — dezelfde
   grondings-poort als `claim_evidence`.
4. **Fail-soft.** Geen LLM, geen antwoord, kapotte JSON → geen kandidaten, en het regex-pad is
   exact zoals het was. Deze pas mag de scan nooit slechter maken dan zonder LLM.
"""
from __future__ import annotations

import json
import logging
import re

from nooch_village.claims_db import ESCALEREN

log = logging.getLogger("village.claims.modelpas")

# Herkomst-stempel op elke modelvondst. De mens moet in één oogopslag zien dat hier geen lijstterm
# en geen wetsartikel achter zit, maar een model dat een vermoeden uitspreekt.
HERKOMST = "model"
HERKOMST_LABEL = "model-gevonden (geen lijstterm)"
BRON_LETTER = "M"                  # naast de bestaande A (EU-wet), B (ACM), C (interpretatie), D (beleid)

_MAX_TEKST = 6000                  # per pagina; genoeg voor de copy, begrensd in tokens
_MAX_KANDIDATEN = 12               # een pagina met meer dan dit is een herschrijf-opdracht, geen lijst
_MIN_FRAGMENT = 20                 # korter is te generiek om als vindplaats te dienen
_NIET_WOORD = re.compile(r"[^a-z0-9]+")


def _norm(tekst: str) -> str:
    return _NIET_WOORD.sub(" ", (tekst or "").lower()).strip()


def regelkader(db: dict, maximaal_termen: int = 14) -> str:
    """Het toetsingskader zoals de records het beschrijven, als prompt-context.

    Reference, don't copy: geen enkele regel staat hier als literal. De bestaande termen gaan mee als
    'deze woorden vangt de regex al' — de opdracht is juist om de ándere formuleringen te vinden."""
    meta = db.get("meta") or {}
    kader = meta.get("toetsingskader") or {}
    regels = meta.get("regelgeving") or {}
    termen = [str(t.get("term", "")) for t in (db.get("termen") or []) if t.get("term")]
    categorieen = sorted({str(t.get("categorie", "")) for t in (db.get("termen") or [])
                          if t.get("categorie")})
    delen = []
    if kader.get("principe"):
        delen.append(f"Toetsingsprincipe: {kader['principe']}")
    if regels:
        delen.append("Kader: " + " · ".join(str(v) for v in regels.values()))
    if categorieen:
        delen.append("Categorieën die compliance gebruikt: " + ", ".join(categorieen))
    if termen:
        delen.append("Deze woorden vangt de regex-scan AL (niet nog eens melden): "
                     + "; ".join(termen[:maximaal_termen]))
    return "\n".join(delen)


_PROMPT = (
    "Je bent compliance-assistent voor Nooch (duurzame veganistische schoenen). Hieronder staat de "
    "tekst van een pagina van onze EIGEN website.\n\n"
    "{kader}\n\n"
    "Een regex-scan op bekende termen is al gedraaid. Jouw taak is precies wat die scan NIET kan: "
    "vind ZINNEN die een MILIEUCLAIM of DUURZAAMHEIDSCLAIM maken over ons eigen product of merk, "
    "maar die geen van de hierboven genoemde woorden gebruiken. Denk aan omschrijvingen, metaforen, "
    "beelden, impliciete beloftes en cijfers zonder onderbouwing.\n\n"
    "Wat NIET melden: zinnen over een ander merk of de industrie in het algemeen, kritiek of "
    "ontmaskering, ontkenningen, citaten, definities, vragen, en zuiver feitelijke productinformatie "
    "(maat, kleur, levertijd, prijs).\n\n"
    "Stel je af op VOLLEDIGHEID, niet op zekerheid: twijfel je of een zin een claim is, MELD hem dan "
    "en zet \"zeker\": false. Een compliance-medewerker leest alles na; een gemiste claim ziet niemand.\n"
    "{negatieven}"
    "Antwoord UITSLUITEND met JSON, exact dit schema:\n"
    '{{"kandidaten":[{{"fragment":"een LETTERLIJK, aaneengesloten stuk uit de tekst hieronder",'
    '"waarom":"welke claim hier gemaakt wordt, kort","categorie":"een van de categorieën hierboven",'
    '"zeker":true of false}}]}}\n'
    "Het fragment moet woord-voor-woord in de tekst voorkomen. Verzin niets. Geen kandidaten? "
    'Antwoord {{"kandidaten":[]}}.\n\n'
    "PAGINATEKST:\n{tekst}"
)


def _negatieven_blok(negatieven) -> str:
    """Eerder door een mens weggewuifde vlaggen, als expliciete negatieven in de prompt.

    Dit is de gratis-labels-motor: elke whitelist-klik van compliance maakt de volgende pas beter,
    zonder dat iemand een prompt hoeft te herschrijven."""
    schoon = [str(n).strip() for n in (negatieven or []) if str(n).strip()][:8]
    if not schoon:
        return ""
    return ("Een mens heeft deze eerder beoordeeld als GEEN claim; meld ze niet opnieuw:\n"
            + "\n".join(f"- {n[:160]}" for n in schoon) + "\n")


def _extract(raw):
    if not raw:
        return None
    s = re.sub(r"```(?:json)?", "", str(raw)).strip()
    try:
        return json.loads(s[s.find("{"):s.rfind("}") + 1])
    except (ValueError, IndexError):
        return None


def _gegrond(fragment: str, tekst: str) -> bool:
    """Grondings-poort: het fragment moet (genormaliseerd) letterlijk in de tekst staan en niet
    triviaal kort zijn. Zo kan een model geen claim verzinnen die een taak wordt."""
    f = _norm(fragment)
    return len(f) >= _MIN_FRAGMENT and f in _norm(tekst)


def _al_gevlagd(fragment: str, bestaande: list[dict]) -> bool:
    """Raakt dit fragment een bevinding die de regex al vond? Dan is het dezelfde claim en hoeft
    hij niet twee keer op het bord."""
    f = _norm(fragment)
    for b in bestaande or []:
        for gevonden in (b.get("gevonden") or []):
            g = _norm(gevonden)
            if g and g in f:
                return True
    return False


def extra_kandidaten(tekst: str, db: dict, bestaande: list[dict], *, reason_fn=None,
                     pagina: str = "", url: str = "", negatieven=None) -> dict:
    """De extra pas over één pagina.

    Geeft `{gedraaid, reden, kandidaten, onzeker, verworpen}`:
      `gedraaid`  — heeft de LLM-pas daadwerkelijk een antwoord gegeven? (False = fail-soft, het
                    regex-pad blijft zoals het was, en de caller mag dit als capaciteitsgat oogsten)
      `kandidaten` — bevindingen in exact het regex-formaat, met `herkomst=model`
      `onzeker`    — de kandidaten die het model zelf niet kon classificeren (ze zitten óók in
                     `kandidaten`; ze worden dus gevlagd, en apart geteld voor de gat-oogst)
      `verworpen`  — fragmenten die de grondings-poort of de dedupe niet haalden (transparantie)
    """
    leeg = {"gedraaid": False, "reden": "", "kandidaten": [], "onzeker": [], "verworpen": []}
    if not (tekst or "").strip():
        return {**leeg, "reden": "geen paginatekst"}
    if reason_fn is None:
        from nooch_village.llm import reason as reason_fn           # laat import: geen key = None
    prompt = _PROMPT.format(kader=regelkader(db), negatieven=_negatieven_blok(negatieven),
                            tekst=(tekst or "")[:_MAX_TEKST])
    try:
        raw = reason_fn(prompt, max_tokens=1200, json_mode=True, call_site="claims_modelpas")
    except Exception as e:                           # noqa: BLE001 — de pas mag de scan nooit breken
        log.info("modelpas faalde (%s) — regex-pad ongewijzigd", e)
        return {**leeg, "reden": f"LLM-fout: {e}"}
    data = _extract(raw)
    if not isinstance(data, dict) or not isinstance(data.get("kandidaten"), list):
        return {**leeg, "reden": "geen bruikbaar LLM-antwoord (fail-soft: regex-pad ongewijzigd)"}

    kandidaten, onzeker, verworpen = [], [], []
    for rij in data["kandidaten"][:_MAX_KANDIDATEN]:
        if not isinstance(rij, dict):
            continue
        fragment = str(rij.get("fragment") or "").strip()
        if not _gegrond(fragment, tekst):
            verworpen.append({"fragment": fragment[:160], "reden": "niet letterlijk in de tekst"})
            continue
        if _al_gevlagd(fragment, bestaande):
            verworpen.append({"fragment": fragment[:160], "reden": "regex vond deze claim al"})
            continue
        bevinding = _als_bevinding(rij, fragment, pagina, url)
        kandidaten.append(bevinding)
        if not rij.get("zeker", True):
            onzeker.append(bevinding)
    log.info("modelpas %s: %d kandidaat(en), %d verworpen", pagina or url, len(kandidaten),
             len(verworpen))
    return {"gedraaid": True, "reden": "", "kandidaten": kandidaten, "onzeker": onzeker,
            "verworpen": verworpen}


def _als_bevinding(rij: dict, fragment: str, pagina: str, url: str) -> dict:
    """Een modelvondst in het formaat van een regex-bevinding, zodat de dedupe, de rol-routing en de
    taakopmaak van `claims_board` ongewijzigd blijven werken.

    `stoplicht` is hier voorlopig oranje; `weeg_bewijs` beslist na de bewijs-toets definitief."""
    zeker = bool(rij.get("zeker", True))
    waarom = str(rij.get("waarom") or "").strip() or "het model ziet hier een milieuclaim"
    return {
        "term": fragment[:120],
        "gevonden": [fragment[:300]],
        "stoplicht": "orange",
        "categorie": str(rij.get("categorie") or "").strip() or "Generiek",
        "waarom": (f"{HERKOMST_LABEL}: {waarom}"
                   + ("" if zeker else " — het model kon dit zelf niet met zekerheid classificeren")),
        "alternatief": ("Laat compliance de formulering beoordelen; noem het concrete, aantoonbare "
                        "voordeel in plaats van de belofte."),
        "bron": BRON_LETTER,
        "bron_detail": ("model-gevonden kandidaat, geen wetsartikel en geen lijstterm — vermoeden "
                        "dat een mens toetst"),
        "hardheid": "vermoeden",
        "herkomst": HERKOMST,
        "model_zeker": zeker,
        "pagina": pagina,
        "url": url,
    }


def weeg_bewijs(kandidaten: list[dict]) -> None:
    """Bepaal het definitieve stoplicht van een modelvondst ná de bewijs-toets.

    Geen onderbouwing → ORANJE: een claim zonder bewijs is een echt EmpCo-risico, hij telt mee in de
    score en hij vuurt de terugkoppeling. Wél onderbouwing → ESCALEREN: het bewijs staat er, maar de
    tool heeft geen wettelijke bron voor déze formulering, dus compliance beslist. Nooit rood.

    Waarom niet alles escaleren: escaleren beweegt de score niet en vuurt de heads-up niet — dat maakt
    een onderbouwing-loze claim maximaal stil, en dat is precies tegen recall-eerst."""
    from nooch_village.claims_substantiatie import ONDERBOUWD
    for b in kandidaten:
        if b.get("herkomst") != HERKOMST:
            continue
        b["stoplicht"] = ESCALEREN if b.get("onderbouwing") == ONDERBOUWD else "orange"
