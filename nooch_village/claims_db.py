"""De claims-database: één bron van waarheid voor de EmpCo/ACM-claimtoets.

`config/claims_database.json` is curated content (geen runtime-state), en staat daarom
naast `strategy.json` in `config/` — versioneerd in git, niet in de gitignorede `data/`.

Iedereen leest vrij (`load()`); cureren is het exclusieve recht van de domein-eigenaar
(de compliance-rol). Deze module bezit het pad en de schrijf-logica, zodat de cockpit-route,
de dispatch-acties en de `claims_check`-skill nooit hun eigen pad of eigen parse-regels
hardcoden — reference, don't copy.
"""
from __future__ import annotations

import json
import os
import re
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "config", "claims_database.json")

# "escaleren" is geen vierde kleur maar een weigering om te oordelen: de term heeft geen harde
# bron (categorie C in meta.toetsingskader), dus de tool beslist niet. Dat betekent ook dat hij
# NIET meetelt in de score — een score die daalt door iets waar de tool geen oordeel over heeft,
# liegt. De bevinding gaat altijd naar compliance.
ESCALEREN = "escaleren"
STOPLICHTEN = ("red", "orange", "green", ESCALEREN)


class ClaimsDbError(RuntimeError):
    """Ontbrekend of corrupt databestand. Fail-closed: liever niets dan verzonnen termen."""


def load(path: str | None = None) -> dict:
    """Lees de database. Faalt bewust hard bij een ontbrekend of kapot bestand:
    een claimtoets zonder termen zou 'geen bevindingen' melden en dat is gevaarlijker
    dan een zichtbare fout."""
    p = path or DB_PATH
    try:
        with open(p, encoding="utf-8") as f:
            db = json.load(f)
    except FileNotFoundError as e:
        raise ClaimsDbError(f"claims-database ontbreekt: {p}") from e
    except (json.JSONDecodeError, OSError) as e:
        raise ClaimsDbError(f"claims-database onleesbaar: {e}") from e
    if not isinstance(db, dict) or not isinstance(db.get("termen"), list):
        raise ClaimsDbError("claims-database mist de sleutel 'termen'")
    return db


def save(db: dict, path: str | None = None) -> None:
    """Schrijf atomair (tmp + rename), zodat een half geschreven bestand nooit de bron wordt."""
    p = path or DB_PATH
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, p)


def bump_versie(db: dict) -> str:
    """Zet meta.versie op vandaag; bij een tweede wijziging op dezelfde dag telt een suffix op
    (2026-07-18, 2026-07-18.2, …) zodat elke mutatie zichtbaar is."""
    meta = db.setdefault("meta", {})
    vandaag = time.strftime("%Y-%m-%d")
    huidig = str(meta.get("versie", ""))
    if huidig == vandaag:
        nieuw = f"{vandaag}.2"
    elif huidig.startswith(vandaag + "."):
        try:
            nieuw = f"{vandaag}.{int(huidig.rsplit('.', 1)[1]) + 1}"
        except ValueError:
            nieuw = f"{vandaag}.2"
    else:
        nieuw = vandaag
    meta["versie"] = nieuw
    return nieuw


def compile_termen(db: dict) -> list[tuple[dict, "re.Pattern[str]"]]:
    """Compileer elk patroon case-insensitive. Een term met een kapot patroon wordt
    overgeslagen in plaats van de hele toets te laten klappen."""
    uit = []
    for t in db.get("termen", []):
        patroon = t.get("patroon") or ""
        if not patroon:
            continue
        try:
            uit.append((t, re.compile(patroon, re.IGNORECASE)))
        except re.error:
            continue
    return uit


def score(rood: int, oranje: int) -> int:
    """De scoreformule uit meta.scoring: max(0, 100 - 12*rood - 5*oranje).

    Escaleren-bevindingen ontbreken hier bewust: de tool heeft er geen oordeel over, dus mogen
    ze de score niet bewegen. Ze worden apart geteld en apart getoond."""
    return max(0, 100 - 12 * rood - 5 * oranje)


def check_tekst(tekst: str, db: dict | None = None) -> dict:
    """Toets een tekst tegen de database. Puur lokaal, geen netwerk.

    Geeft per gevonden term `{term, stoplicht, categorie, alternatief, waarom, gevonden}`
    plus de score en de tellingen terug."""
    db = db if db is not None else load()
    bevindingen = []
    for t, rx in compile_termen(db):
        gevonden = rx.findall(tekst or "")
        if not gevonden:
            continue
        # findall geeft tuples bij groepen; de volledige match halen we via finditer
        matches = sorted({m.group(0).strip() for m in rx.finditer(tekst or "") if m.group(0).strip()})
        bevindingen.append({
            "term": t.get("term", ""),
            "stoplicht": t.get("stoplicht", ""),
            "categorie": t.get("categorie", ""),
            "waarom": t.get("waarom", ""),
            "alternatief": t.get("alternatief", ""),
            "gevonden": matches,
            # Herkomst van het oordeel: bron-letter + de letterlijke onderbouwing uit de
            # database. Zo kan de lezer zien of hier de wet spreekt of een interpretatie.
            "bron": t.get("bron", ""),
            "bron_detail": t.get("bron_detail", ""),
            "hardheid": t.get("hardheid", ""),
            "stoplicht_advies": t.get("stoplicht_advies", ""),
        })
    rood = sum(1 for b in bevindingen if b["stoplicht"] == "red")
    oranje = sum(1 for b in bevindingen if b["stoplicht"] == "orange")
    groen = sum(1 for b in bevindingen if b["stoplicht"] == "green")
    escaleren = sum(1 for b in bevindingen if b["stoplicht"] == ESCALEREN)
    return {
        "bevindingen": bevindingen,
        "rood": rood, "oranje": oranje, "groen": groen, "escaleren": escaleren,
        "score": score(rood, oranje),
        "versie": (db.get("meta") or {}).get("versie", ""),
    }


def add_term(db: dict, term: str, patroon: str, stoplicht: str, categorie: str,
             waarom: str = "", alternatief: str = "") -> dict:
    """Voeg een term toe (append-vriendelijk: bestaande termen blijven ongemoeid).
    Valideert het patroon; een onbruikbaar patroon komt de bron niet in."""
    if not term or not patroon:
        raise ValueError("term en patroon zijn verplicht")
    if stoplicht not in STOPLICHTEN:
        raise ValueError(f"stoplicht moet een van {STOPLICHTEN} zijn")
    try:
        re.compile(patroon, re.IGNORECASE)
    except re.error as e:
        raise ValueError(f"patroon compileert niet: {e}") from e
    nieuw = {"patroon": patroon, "term": term, "stoplicht": stoplicht,
             "categorie": categorie or "Algemeen",
             "waarom": waarom or "(toegevoegd door compliance, onderbouwing volgt)",
             "alternatief": alternatief or "(alternatief volgt)"}
    db.setdefault("termen", []).append(nieuw)
    return nieuw


# Statussen die de scan zélf mag zetten. Ze dragen hun herkomst in de naam, zodat mens- en
# machine-oordeel nooit verward raken: wie "opgelost (auto-geverifieerd)" leest, weet dat een
# byte-vergelijking dat vaststelde en geen mens.
AUTO_OPGELOST = "opgelost (auto-geverifieerd)"
AUTO_REGRESSIE = "open (regressie)"
NIET_VERIFIEERBAAR = "niet auto-verifieerbaar"
AUTO_STATUSSEN = (AUTO_OPGELOST, AUTO_REGRESSIE, NIET_VERIFIEERBAAR)


def is_auto(status: str) -> bool:
    return str(status or "").startswith(("opgelost (auto", "open (regressie", "niet auto"))


def werk_statussen(db: dict) -> list[str]:
    """De toegestane werklijst-statussen, uit meta — niet uit een literal in code of HTML."""
    return list((db.get("meta") or {}).get("werklijst_statussen") or ["open"])


def set_werk_status(db: dict, nr: int, status: str) -> dict:
    """Zet de status van een werklijst-item. Geeft het gewijzigde item terug."""
    if status not in werk_statussen(db):
        raise ValueError(f"onbekende status '{status}'")
    for item in db.get("werklijst", []):
        if int(item.get("nr", -1)) == int(nr):
            item["status"] = status
            return item
    raise ValueError(f"werklijst-item {nr} bestaat niet")
