"""Rugzakken — cirkelbrede capaciteit, gegroepeerd naar de soort vraag die hij beantwoordt.

Een skill is een gedeeld middel. Tot nu toe kwam hij bij een rol via het rol-DNA: per rol een lijst,
door governance gezet. Dat model koppelt GEREEDSCHAP aan MANDAAT, en dat zijn twee verschillende
dingen. Wie ergens over gaat is governance; welk gereedschap er in de schuur ligt is dat niet.

Een rugzak draait dat om. Het middel hoort bij de CIRKEL, elke rol mag erbij, en wat een rol
onderscheidt is niet zijn gereedschap maar zijn domein. Die scheiding staat al hard in de code:
`Inhabitant._domein_weigering` weigert een beslis-skill voor een rol zonder dat domein, absoluut en
zonder policy-omweg. Dit bestand raakt die poort niet aan en kan hem niet omzeilen: rugzakken
verruimen alleen de set die de poort daarna nog beoordeelt.

WAAROM GEGROEPEERD. De planner krijgt de catalogus in zijn prompt. Vijftig middelen achter elkaar is
twee problemen tegelijk: de prompt wordt lang, en het model kiest slechter naarmate de lijst langer
is. Gegroepeerd ziet het eerst welke SOORT vraag dit is ("wat gebeurt er buiten", "mag dit") en
kiest het daarbinnen.

WAT EEN RUGZAK NIET IS. Hij is geen puls. `Inhabitant.capabilities()` (wat een rol uit eigen
beweging op de dagpuls draait) blijft bewust op het DNA staan. Anders zou elke rol die de
claims-scan KAN pakken hem ook elke dag GAAN draaien, en dat is precies de fout waar
`_run_pulse_skills` in zijn eigen commentaar voor waarschuwt: "de Copywriter hóórt geen claims-scan
te draaien". Bereikbaar zijn en op eigen initiatief draaien zijn twee verschillende dingen.

Fail-soft in beide richtingen: geen bestand → lege dict → het dorp gedraagt zich als voorheen (het
DNA is de vloer, een rugzak neemt nooit iets af). Een skill in een rugzak die niet in de registry
staat wordt bij het bouwen van de catalogus gewoon overgeslagen, zoals elke andere onbekende naam.
"""
from __future__ import annotations

import json
import logging
import os

log = logging.getLogger("village.rugzak")

BESTAND = "rugzakken.json"


def laad(base_dir: str) -> dict:
    """Lees `config/rugzakken.json`. Ontbreekt of stuk → lege dict (fail-soft, luid gelogd).

    Sleutels die met '_' beginnen zijn commentaar in het bestand zelf en worden overgeslagen, net
    als bij `strategy.json` — zo kan de uitleg naast de data staan in plaats van in een los document
    dat ernaast verjaart.
    """
    pad = os.path.join(base_dir, "config", BESTAND)
    if not os.path.exists(pad):
        return {}
    try:
        with open(pad, encoding="utf-8") as f:
            rauw = json.load(f)
    except Exception as exc:                            # noqa: BLE001 — stuk bestand mag niets breken
        log.warning("rugzakken: %s onleesbaar (%s) — verder zonder rugzakken", pad, exc)
        return {}
    if not isinstance(rauw, dict):
        log.warning("rugzakken: %s is geen object — verder zonder rugzakken", pad)
        return {}
    uit = {}
    for naam, blok in rauw.items():
        if naam.startswith("_"):
            continue
        if not isinstance(blok, dict):
            log.warning("rugzakken: '%s' is geen object — overgeslagen", naam)
            continue
        skills = [s for s in (blok.get("skills") or []) if isinstance(s, str) and s.strip()]
        uit[naam] = {"stagiair": str(blok.get("stagiair") or ""),
                     "wat": str(blok.get("wat") or ""),
                     "skills": skills}
    return uit


def alle_skills(rugzakken) -> set[str]:
    """Elk middel dat in enige rugzak zit. Dit is wat een rol EXTRA mag pakken boven zijn DNA."""
    uit: set[str] = set()
    for blok in (rugzakken or {}).values():
        uit.update((blok or {}).get("skills") or ())
    return uit


def rugzak_van(rugzakken, skill: str) -> str:
    """In welke rugzak zit dit middel? Leeg = in geen enkele (dan komt hij uit het DNA)."""
    for naam, blok in (rugzakken or {}).items():
        if skill in ((blok or {}).get("skills") or ()):
            return naam
    return ""


def catalogus(rugzakken, namen, registry) -> str:
    """De skill-catalogus voor de planner-prompt, gegroepeerd per rugzak.

    `namen` = de skills die deze rol daadwerkelijk mag voeren (DNA ∪ koppelingen ∪ rugzakken); we
    tonen dus nooit iets dat de poort daarna zou weigeren wegens 'niet van jou'. Een middel dat in
    geen rugzak zit (typisch een DNA-grant of een periodieke skill van deze rol) komt onderaan onder
    'eigen gereedschap' — het moet kiesbaar blijven, ook zonder groep.

    Geeft platte tekst terug, klaar om in de prompt te plakken. Leeg → "(no skills)", zodat de
    aanroeper geen lege sectie hoeft af te vangen.
    """
    beschikbaar = set(namen or ())
    if not beschikbaar:
        return "(no skills)"

    def _regel(naam: str) -> str:
        obj = registry.get(naam) if registry is not None else None
        desc = (getattr(obj, "description", "") or "").strip() if obj else ""
        insch = (getattr(obj, "input_schema", "") or "").strip() if obj else ""
        return (f"- {naam}: {desc[:160]}\n    input: " +
                (insch or "(no schema — infer it from the name/description)"))

    regels: list[str] = []
    gezien: set[str] = set()
    for naam, blok in (rugzakken or {}).items():
        hier = [s for s in ((blok or {}).get("skills") or ()) if s in beschikbaar]
        if not hier:
            continue
        kop = (blok or {}).get("wat") or naam
        regels.append(f"\n[{naam}] {kop}")
        regels.extend(_regel(s) for s in hier)
        gezien.update(hier)

    rest = sorted(beschikbaar - gezien)
    if rest:
        regels.append("\n[eigen gereedschap] van deze rol zelf")
        regels.extend(_regel(s) for s in rest)

    return "\n".join(regels).strip() or "(no skills)"
