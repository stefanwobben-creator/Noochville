"""Wat de founder ziet als een besluit hem écht bereikt.

Twee klachten die deze module wegneemt.

**"Een rol aan een rol."** De items droegen `by: "een rol"` en landden op een willekeurig doel. Wie
de spanning opwerpt was niet te zien, en welke van zijn eigen verantwoordelijkheden werd
aangesproken evenmin. Zonder dat tweede weet de founder niet wáárom iets bij hem ligt — en dat is
precies het verschil tussen een besluit nemen en een lijst afvinken.

**De afgekapte dump met Ja/Nee.** Een snippet van 160 tekens met een vraagteken erachter is geen
besluit maar een raadsel. Een kaart draagt daarom altijd zes dingen: wie het opwerpt, welke
accountability wordt geraakt, wat er gevonden is, wat er wordt voorgesteld, wat Ja en Nee
betekenen, en één regel bewijs.

**Geen match op de accountability = een signaal, geen leegte.** Raakt een item geen enkele
founder-verantwoordelijkheid, dan is dat zelf het antwoord: het ligt hier verkeerd. De kaart zegt
dat dan hardop in plaats van een leeg veld te tonen — een besluit dat aan geen enkele bevoegdheid
hangt, hoort terug naar de routering.
"""
from __future__ import annotations

import logging
import re

log = logging.getLogger("village.founder_kaart")

FOUNDER_ROL = "mother_earth__nooch__strategic_lead_founder_steward"

# Welke founder-accountability een onderwerp aanspreekt. De sleutels zijn de domeinen die de poort
# al onderscheidt; de waarden zijn zoekpatronen op de ECHTE accountability-tekst uit de records —
# niet de tekst zelf, want die leeft in governance en mag daar wijzigen zonder deze code te breken.
_DOMEIN_ACC = {
    "compliance": r"mission|values|principle",
    "merk":       r"story|mission|values",
    "strategie":  r"strategy|priorit",
    "geld":       r"fundraising|financial",
    "governance": r"strategy|priorit",
}

_PLACEHOLDER = {"een rol", "a role", "", "onbekend", "unknown", "system"}


def opwerper(notif: dict, projects=None, records=None) -> tuple[str, str]:
    """Wie werpt deze spanning op? → (rol_id, leesbare naam). Nooit "een rol".

    Valt terug op de eigenaar van het project waar het item aan hangt: dat is een gegeven, geen
    gok. Levert dat ook niets op, dan zegt de kaart dat expliciet — een onbekende afzender is een
    defect in de keten, geen cosmetisch probleem."""
    door = str(notif.get("by") or "").strip()
    if door.lower() not in _PLACEHOLDER:
        return door, _naam(records, door)
    pid = str(notif.get("project_id") or "")
    if pid and projects is not None:
        p = projects.get(pid)
        if p and p.get("owner"):
            return str(p["owner"]), _naam(records, str(p["owner"]))
    log.warning("founder-kaart: geen opwerper te bepalen voor item %s", notif.get("id"))
    return "", "onbekend — de afzender is onderweg verloren gegaan"


def _naam(records, rol_id: str) -> str:
    if not rol_id or records is None:
        return rol_id or "?"
    rec = records.get(rol_id)
    if rec is None:
        return rol_id
    return getattr(rec.definition, "name", "") or rol_id


def accountabilities(records, rol_id: str = FOUNDER_ROL) -> list[str]:
    rec = records.get(rol_id) if records is not None else None
    return list(getattr(getattr(rec, "definition", None), "accountabilities", None) or [])


def geraakte_accountability(domein: str, records, rol_id: str = FOUNDER_ROL) -> str:
    """Welke founder-verantwoordelijkheid spreekt dit aan? "" als geen enkele past."""
    pat = _DOMEIN_ACC.get(domein or "")
    if not pat:
        return ""
    for acc in accountabilities(records, rol_id):
        if re.search(pat, acc, re.I):
            return acc
    return ""


def eigen_accountability(rol_id: str, tekst: str, records) -> str:
    """Vanuit WELKE eigen verantwoordelijkheid werpt deze rol dit op?

    Dit staat op de kaart in plaats van een founder-label. De reden dat het bij de founder ligt
    hoort in de behoefte-regel ("ik heb jou nodig om X vrij te geven"), niet in een etiket op de
    rol van de ander — anders leest de kaart alsof de founder de spanning voelde."""
    from nooch_village.zelf_verwerking import eigen_domein
    return eigen_domein(tekst, rol_id, records) if rol_id else ""


def kaart(notif: dict, *, besluit=None, projects=None, records=None, voorstel: dict | None = None,
          bewijs: str = "") -> dict:
    """De volledige kaart. `besluit` is het poort-oordeel, `voorstel` het inhoudelijke voorstel."""
    poort = dict(notif.get("poort") or {}) if besluit is None else {
        "deur": getattr(besluit, "deur", ""), "reden": getattr(besluit, "reden", ""),
        "klasse": getattr(besluit, "klasse", ""), "sleutel": getattr(besluit, "sleutel", "")}
    domein = str(poort.get("klasse") or "").replace("-besluit", "")
    rol_id, rol_naam = opwerper(notif, projects, records)
    tekst = " ".join(str(notif.get("snippet") or "").split())
    v = dict(voorstel or {})
    # De accountability van de OPWERPER, niet die van de founder. Waarom het bij de founder ligt
    # staat in de behoefte-regel.
    eigen = eigen_accountability(rol_id, tekst, records)
    acc = geraakte_accountability(domein, records)

    if not acc:
        # Geen bevoegdheid geraakt = het ligt hier verkeerd. Dat hardop zeggen is het hele punt.
        log.info("founder-kaart: geen founder-accountability raakt domein %r — item %s ligt hier "
                 "mogelijk verkeerd", domein, notif.get("id"))

    return {
        "rol":            rol_naam,
        "rol_id":         rol_id,
        "vanuit":         eigen,
        "accountability": acc or ("geen founder-verantwoordelijkheid raakt dit — dit hoort "
                                  "waarschijnlijk terug naar de routering"),
        "hoort_hier":     bool(acc),
        "behoefte":       v.get("behoefte") or "",
        "gevonden":       v.get("gevonden") or tekst,
        "voorstel":       v.get("voorstel") or "",
        "ja":             v.get("ja") or "",
        "nee":            v.get("nee") or "",
        "bewijs":         bewijs or v.get("bewijs") or "",
        "domein":         domein,
    }


def render(k: dict) -> str:
    """De kaart als platte tekst — dezelfde volgorde als op het scherm, zodat CLI en UI hetzelfde
    verhaal vertellen."""
    kop = f"opgeworpen door : {k['rol']}"
    if k.get("vanuit"):
        kop += f", vanuit accountability “{k['vanuit'][:70]}”"
    regels = [kop]
    if k.get("behoefte"):
        # Waaróm het bij de founder ligt: als BEHOEFTE van de opwerpende rol, niet als etiket.
        regels.append(f"waarom bij jou   : {k['behoefte']}")
    regels.append(f"gevonden        : {k['gevonden'][:300]}")
    if k.get("voorstel"):
        regels.append(f"voorstel        : {k['voorstel']}")
    if k.get("ja"):
        regels.append(f"Ja betekent     : {k['ja']}")
    if k.get("nee"):
        regels.append(f"Nee betekent    : {k['nee']}")
    regels.append(f"bewijs          : {k['bewijs'] or '— geen bewijsregel meegeleverd'}")
    return "\n".join(regels)
