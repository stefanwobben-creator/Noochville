"""Geparkeerde founder-items: uit de wachtrij, maar géén oordeel.

De wachtrij liep vol met dingen waar de founder niets zinnigs over kón beslissen: compliance-
bevindingen over een site die wordt herbouwd, en rauwe radar-signalen die nog door geen enkele rol
zijn beoordeeld. Ze wegklikken als `verwerp` zou ze opruimen én de Founder Flow iets onwaars leren —
"de founder wees dit af" terwijl hij alleen zei "niet nu".

Daarom een aparte store, bewust NIET in `founder_labels.jsonl`:

  - een label is een OORDEEL en telt mee in de overeenstemming, de Wilson-poort en de drift;
  - een parkering is een AGENDA-besluit en telt nergens in mee.

Dat onderscheid moet structureel zijn, niet conventie. Zodra een parkering in de labelstroom zou
landen, is elke afgeleide meting stilletjes vervuild — en dat is precies de klasse fout die deze
codebase deze week op vier plekken heeft weggehaald.

Een parkering draagt een REDEN en een terugkeer-voorwaarde, want "later" zonder trigger is
weggooien met een vriendelijker woord.
"""
from __future__ import annotations

import json
import logging
import os
import time

log = logging.getLogger("village.founder_park")

BESTAND = "founder_park.jsonl"

# De redenen die we kennen, met hun terugkeer-voorwaarde. Een vrije tekst zou hier de
# terugkeer-voorwaarde optioneel maken, en dan is parkeren alsnog weggooien.
REDENEN = {
    "relaunch": "komt terug als de nieuwe site live is en compliance opnieuw scant",
    "rol_triage": "komt terug zodra de rol die de omkering krijgt dit signaal beoordeelt",
}


def pad(data_dir: str) -> str:
    return os.path.join(data_dir, BESTAND)


def park(data_dir: str, *, taak: str, items, reden: str, door: str = "founder") -> int:
    """Parkeer items van één taak. Geeft het aantal geparkeerde items terug.

    Idempotent op (taak, item): opnieuw parkeren voegt niets toe."""
    if reden not in REDENEN:
        log.warning("parkering GEWEIGERD: onbekende reden %r (bekend: %s)", reden, list(REDENEN))
        return 0
    al = {(r["taak"], r["item"]) for r in alle(data_dir) if not r.get("terug")}
    nieuw = [i for i in dict.fromkeys(items or []) if (taak, i) not in al]
    if not nieuw:
        return 0
    try:
        os.makedirs(data_dir, exist_ok=True)
        with open(pad(data_dir), "a", encoding="utf-8") as fh:
            for item in nieuw:
                fh.write(json.dumps({"taak": taak, "item": str(item), "reden": reden,
                                     "voorwaarde": REDENEN[reden], "door": door,
                                     "ts": time.time()}, ensure_ascii=False) + "\n")
    except OSError as e:
        log.warning("parkering niet vastgelegd: %s", e)
        return 0
    log.info("⏸ %d item(s) geparkeerd op '%s' — %s", len(nieuw), taak, REDENEN[reden])
    return len(nieuw)


def haal_terug(data_dir: str, *, taak: str, item: str, door: str = "founder") -> bool:
    """Zet één item terug in de wachtrij (append-only: een 'terug'-regel, niets wordt herschreven)."""
    try:
        with open(pad(data_dir), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"taak": taak, "item": str(item), "terug": True,
                                 "door": door, "ts": time.time()}, ensure_ascii=False) + "\n")
        return True
    except OSError as e:
        log.warning("terughalen niet vastgelegd: %s", e)
        return False


def alle(data_dir: str) -> list[dict]:
    uit = []
    try:
        with open(pad(data_dir), encoding="utf-8") as fh:
            for regel in fh:
                regel = regel.strip()
                if regel:
                    try:
                        uit.append(json.loads(regel))
                    except ValueError:
                        continue
    except FileNotFoundError:
        return []
    except OSError as e:
        log.warning("parkeringen onleesbaar: %s", e)
    return uit


def geparkeerd(data_dir: str, taak: str) -> set[str]:
    """De items die op dit moment geparkeerd staan (laatste regel per item wint)."""
    stand: dict[str, bool] = {}
    for r in sorted(alle(data_dir), key=lambda x: x.get("ts", 0)):
        if r.get("taak") == taak and r.get("item"):
            stand[r["item"]] = not r.get("terug")
    return {i for i, aan in stand.items() if aan}


def telling(data_dir: str) -> dict:
    """Per taak: hoeveel er geparkeerd staat, en waarom."""
    uit: dict = {}
    for r in alle(data_dir):
        if r.get("terug"):
            continue
        taak = r.get("taak", "?")
        if r["item"] in geparkeerd(data_dir, taak):
            uit.setdefault(taak, {}).setdefault(r.get("reden", "?"), 0)
            uit[taak][r["reden"]] += 1
    return uit
