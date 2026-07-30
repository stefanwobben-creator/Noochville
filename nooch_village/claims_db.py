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
import logging
import os
import re
import time

log = logging.getLogger("village.claims")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "config", "claims_database.json")

# De runtime-overlay: curatie die op de server ontstaat (termen toevoegen/intrekken, werklijst-
# statussen) landt hier, NIET in de getrackte seed. Zo blijft config/claims_database.json schoon
# t.o.v. git (het ff-only-deploymodel blokkeert niet op runtime-writes) en blijft de seed de
# read-only bron die overal aanwezig is (CI, verse clone, verse install). Het bestand leeft onder
# de runtime-data_dir (dus test-geïsoleerd, net als llm_usage) en is een EXACTE delta — geen
# heuristische merge, want dat is op juridische termen te riskant.
OVERLAY_NAAM = "claims_runtime.json"

# "escaleren" is geen vierde kleur maar een weigering om te oordelen: de term heeft geen harde
# bron (categorie C in meta.toetsingskader), dus de tool beslist niet. Dat betekent ook dat hij
# NIET meetelt in de score — een score die daalt door iets waar de tool geen oordeel over heeft,
# liegt. De bevinding gaat altijd naar compliance.
ESCALEREN = "escaleren"
STOPLICHTEN = ("red", "orange", "green", ESCALEREN)


class ClaimsDbError(RuntimeError):
    """Ontbrekend of corrupt databestand. Fail-closed: liever niets dan verzonnen termen."""


def load_seed(path: str | None = None) -> dict:
    """Lees de getrackte seed (config/claims_database.json). Faalt bewust hard bij een ontbrekend
    of kapot bestand: een claimtoets zonder termen zou 'geen bevindingen' melden en dat is
    gevaarlijker dan een zichtbare fout."""
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


def load(path: str | None = None, data_dir: str | None = None) -> dict:
    """De EFFECTIEVE database: de seed, met de runtime-overlay eroverheen als `data_dir` gegeven is.

    Zonder `data_dir` (bv. in tests of losse tooling) krijg je de kale seed — ongewijzigd gedrag.
    De productie-lezers (cockpit, de claims_check-skill, de wekelijkse scan) geven altijd hun
    `data_dir` mee, zodat een runtime-toegevoegde term ook echt in de toets meekomt."""
    seed = load_seed(path)
    if not data_dir:
        return seed
    return _pas_overlay_toe(seed, _lees_overlay(data_dir))


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


def check_tekst(tekst: str, db: dict | None = None, data_dir: str | None = None) -> dict:
    """Toets een tekst tegen de database. Puur lokaal, geen netwerk.

    Geeft per gevonden term `{term, stoplicht, categorie, alternatief, waarom, gevonden}`
    plus de score en de tellingen terug. `data_dir` = de effectieve db (seed + runtime-overlay),
    zodat een runtime-toegevoegde term ook echt in de toets meekomt."""
    db = db if db is not None else load(data_dir=data_dir)
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


def _bouw_term(term: str, patroon: str, stoplicht: str, categorie: str,
               waarom: str = "", alternatief: str = "") -> dict:
    """Valideer en bouw één term-dict. Gedeeld door `add_term` (in-memory) en `overlay_add_term`
    (runtime-overlay); een onbruikbaar patroon komt zo op geen van beide paden de bron in."""
    if not term or not patroon:
        raise ValueError("term en patroon zijn verplicht")
    if stoplicht not in STOPLICHTEN:
        raise ValueError(f"stoplicht moet een van {STOPLICHTEN} zijn")
    try:
        re.compile(patroon, re.IGNORECASE)
    except re.error as e:
        raise ValueError(f"patroon compileert niet: {e}") from e
    return {"patroon": patroon, "term": term, "stoplicht": stoplicht,
            "categorie": categorie or "Algemeen",
            "waarom": waarom or "(toegevoegd door compliance, onderbouwing volgt)",
            "alternatief": alternatief or "(alternatief volgt)"}


def add_term(db: dict, term: str, patroon: str, stoplicht: str, categorie: str,
             waarom: str = "", alternatief: str = "") -> dict:
    """Voeg een term toe aan een in-memory db (append-vriendelijk). Blijft bestaan voor tooling
    en tests; de productie-schrijfpaden lopen sinds de seed/overlay-splitsing via `overlay_add_term`."""
    nieuw = _bouw_term(term, patroon, stoplicht, categorie, waarom, alternatief)
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


# ── Runtime-overlay (data/claims_runtime.json) ──────────────────────────────────────────────────
# Exacte delta over de seed: toevoegen, intrekken en werklijst-status. Geen heuristische merge.

def _overlay_pad(data_dir: str) -> str:
    return os.path.join(data_dir, OVERLAY_NAAM)


def _leeg_overlay() -> dict:
    return {"toegevoegd": [], "ingetrokken": [], "werklijst": {}, "uitzonderingen": [],
            "meta_versie": ""}


def _lees_overlay(data_dir: str) -> dict:
    """De overlay-delta, of een lege delta als het bestand er (nog) niet is. Kapot bestand faalt
    luid — net als de seed: liever een zichtbare fout dan stil verkeerde compliance-data."""
    if not data_dir:
        return _leeg_overlay()
    p = _overlay_pad(data_dir)
    try:
        with open(p, encoding="utf-8") as f:
            ov = json.load(f)
    except FileNotFoundError:
        return _leeg_overlay()
    except (json.JSONDecodeError, OSError) as e:
        raise ClaimsDbError(f"claims-overlay onleesbaar: {e}") from e
    basis = _leeg_overlay()
    if isinstance(ov, dict):
        basis["toegevoegd"] = [t for t in (ov.get("toegevoegd") or []) if isinstance(t, dict)]
        basis["ingetrokken"] = [str(p) for p in (ov.get("ingetrokken") or [])]
        basis["werklijst"] = {str(k): str(v) for k, v in (ov.get("werklijst") or {}).items()}
        basis["uitzonderingen"] = [u for u in (ov.get("uitzonderingen") or []) if isinstance(u, dict)]
        basis["meta_versie"] = str(ov.get("meta_versie") or "")
    return basis


def _schrijf_overlay(data_dir: str, ov: dict) -> None:
    """Atomair (tmp + rename), zodat een half geschreven overlay nooit de bron wordt."""
    os.makedirs(data_dir, exist_ok=True)
    p = _overlay_pad(data_dir)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(ov, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, p)


def _term_key(t: dict) -> str:
    """Identiteit van een term = zijn patroon (de regex; functioneel uniek). Intrekken en dedup
    zijn zo een exacte string-match, geen fuzzy gok."""
    return (t.get("patroon") or "").strip()


def _pas_overlay_toe(seed: dict, ov: dict) -> dict:
    """De effectieve db = seed + delta, exact toegepast. Conflictregel (bewust, juridisch): als de
    seed (via een PR in git) een term draagt waarvan het patroon runtime is ingetrokken, WINT
    aanwezigheid — de term blijft staan — en het conflict wordt zichtbaar gelogd + in `_conflicten`
    gezet. Zo drukt een runtime-retractie nooit stil een in-git-gezette juridische term weg."""
    ingetrokken = set(ov.get("ingetrokken") or [])
    conflicten, termen, gezien = [], [], set()
    for t in seed.get("termen", []):
        k = _term_key(t)
        gezien.add(k)
        if k in ingetrokken:
            conflicten.append(t.get("term") or k)      # aanwezigheid wint: term blijft staan
        termen.append(t)
    for a in ov.get("toegevoegd") or []:
        k = _term_key(a)
        if not k or k in ingetrokken or k in gezien:    # runtime-ingetrokken of dubbel-met-seed → weg
            continue
        gezien.add(k)
        termen.append(a)
    status_over = ov.get("werklijst") or {}
    werklijst = [({**item, "status": status_over[str(item.get("nr"))]}
                  if str(item.get("nr")) in status_over else item)
                 for item in seed.get("werklijst", [])]
    meta = dict(seed.get("meta") or {})
    if ov.get("meta_versie"):
        meta["versie"] = ov["meta_versie"]
    eff = {**seed, "termen": termen, "werklijst": werklijst, "meta": meta,
           "uitzonderingen": list(ov.get("uitzonderingen") or [])}
    if conflicten:
        eff["_conflicten"] = conflicten
        for c in conflicten:
            log.warning("claims-overlay: runtime-retractie van in-git term '%s' genegeerd "
                        "(aanwezigheid wint) — trek 'm desgewenst via een PR op de seed in.", c)
    return eff


def _bump_overlay_versie(ov: dict) -> str:
    """Zet meta_versie op vandaag; tweede wijziging op dezelfde dag krijgt een suffix (.2, .3, …)."""
    vandaag = time.strftime("%Y-%m-%d")
    huidig = str(ov.get("meta_versie") or "")
    if huidig == vandaag:
        nieuw = f"{vandaag}.2"
    elif huidig.startswith(vandaag + "."):
        try:
            nieuw = f"{vandaag}.{int(huidig.rsplit('.', 1)[1]) + 1}"
        except ValueError:
            nieuw = f"{vandaag}.2"
    else:
        nieuw = vandaag
    ov["meta_versie"] = nieuw
    return nieuw


def overlay_add_term(data_dir: str, term: str, patroon: str, stoplicht: str, categorie: str,
                     waarom: str = "", alternatief: str = "") -> tuple[dict, str]:
    """Voeg een term toe via de runtime-overlay (seed blijft ongemoeid). Een eerder ingetrokken
    patroon wordt bij toevoegen weer teruggezet. Geeft (nieuwe term, versie)."""
    nieuw = _bouw_term(term, patroon, stoplicht, categorie, waarom, alternatief)
    ov = _lees_overlay(data_dir)
    ov["ingetrokken"] = [p for p in ov["ingetrokken"] if p != patroon]
    ov["toegevoegd"] = [t for t in ov["toegevoegd"] if _term_key(t) != patroon] + [nieuw]
    versie = _bump_overlay_versie(ov)
    _schrijf_overlay(data_dir, ov)
    return nieuw, versie


def overlay_retract(data_dir: str, patroon: str) -> str:
    """Trek een term in via de overlay. Een runtime-toegevoegde term verdwijnt schoon; een
    seed-term blijft staan (aanwezigheid wint, zie `_pas_overlay_toe`) — het patroon wordt wel
    onthouden zodat het conflict zichtbaar blijft. Geeft de versie."""
    patroon = (patroon or "").strip()
    if not patroon:
        raise ValueError("patroon is verplicht om in te trekken")
    ov = _lees_overlay(data_dir)
    ov["toegevoegd"] = [t for t in ov["toegevoegd"] if _term_key(t) != patroon]
    if patroon not in ov["ingetrokken"]:
        ov["ingetrokken"].append(patroon)
    versie = _bump_overlay_versie(ov)
    _schrijf_overlay(data_dir, ov)
    return versie


# ── Uitzonderingen: de over-vlag die een mens heeft weggewuifd ──────────────────────────────────
# Een uitzondering VERWIJDERT nooit een bevinding. Hij zegt alleen: maak hier geen taak van, en toon
# hem apart met de naam van wie dat besloot. Zo blijft een verkeerd oordeel terugvindbaar in plaats
# van stil te verdwijnen — dezelfde regel als de 'in context, geen claim'-groep van de checker.

_FRAGMENT_NIET_WOORD = re.compile(r"[^a-z0-9]+")
_MIN_UITZONDERING = 12             # korter fragment zou halve site wegfilteren


def _norm_fragment(tekst: str) -> str:
    return _FRAGMENT_NIET_WOORD.sub(" ", (tekst or "").lower()).strip()


def uitzonderingen(db: dict) -> list[dict]:
    """De vastgelegde uitzonderingen uit de effectieve database (leeg zonder overlay)."""
    return [u for u in (db.get("uitzonderingen") or []) if isinstance(u, dict)]


def is_uitgezonderd(bevinding: dict, db: dict) -> dict | None:
    """Heeft een mens deze bevinding op deze pagina eerder weggewuifd? Geeft de uitzondering terug.

    Match op fragment-insluiting in beide richtingen (de scan vindt soms de hele zin, soms de frase)
    en op pagina: een uitzondering geldt per vindplaats, niet sitebreed — dezelfde claim op een
    andere pagina is een nieuwe beslissing. Een uitzondering zonder pagina geldt overal (bewuste
    ontsnapping voor een sitewide element als een footer)."""
    kandidaten = [_norm_fragment(g) for g in (bevinding.get("gevonden") or [])]
    kandidaten += [_norm_fragment(bevinding.get("term", ""))]
    kandidaten = [k for k in kandidaten if k]
    pagina = _norm_fragment(bevinding.get("pagina", ""))
    for u in uitzonderingen(db):
        frag = _norm_fragment(u.get("fragment", ""))
        if len(frag) < _MIN_UITZONDERING:
            continue
        upagina = _norm_fragment(u.get("pagina", ""))
        if upagina and pagina and upagina != pagina:
            continue
        if any(frag in k or k in frag for k in kandidaten):
            return u
    return None


def overlay_uitzondering(data_dir: str, fragment: str, pagina: str = "", waarom: str = "",
                         door: str = "") -> tuple[dict, str]:
    """Leg een uitzondering vast via de overlay. Geeft (uitzondering, versie).

    Het fragment moet lang genoeg zijn om één vindplaats aan te wijzen: een uitzondering op 'eco'
    zou de halve site blind maken, en dat is precies de fout die deze tool moet uitsluiten."""
    fragment = (fragment or "").strip()
    if len(_norm_fragment(fragment)) < _MIN_UITZONDERING:
        raise ValueError(f"fragment is te kort of te generiek (minimaal {_MIN_UITZONDERING} tekens "
                         f"aan letters/cijfers) — een uitzondering moet één vindplaats aanwijzen")
    nieuw = {"fragment": fragment[:300], "pagina": (pagina or "").strip()[:80],
             "waarom": (waarom or "").strip()[:200], "door": door or "?", "at": time.time()}
    ov = _lees_overlay(data_dir)
    ov["uitzonderingen"] = [u for u in ov["uitzonderingen"]
                            if _norm_fragment(u.get("fragment", "")) != _norm_fragment(fragment)
                            or (u.get("pagina") or "") != nieuw["pagina"]] + [nieuw]
    versie = _bump_overlay_versie(ov)
    _schrijf_overlay(data_dir, ov)
    return nieuw, versie


def overlay_set_status(data_dir: str, nr: int, status: str, seed_path: str | None = None,
                       machine: bool = False) -> str:
    """Zet een werklijst-status via de overlay (de seed blijft ongemoeid). Valideert de status en
    het bestaan van het item tegen de seed. `machine=True` (de wekelijkse auto-scan) laat ook de
    AUTO_STATUSSEN toe — die dragen hun herkomst in de naam en zijn geen mens-keuze. Geeft de versie."""
    seed = load_seed(seed_path)
    toegestaan = set(werk_statussen(seed)) | (set(AUTO_STATUSSEN) if machine else set())
    if status not in toegestaan:
        raise ValueError(f"onbekende status '{status}'")
    if not any(int(item.get("nr", -1)) == int(nr) for item in seed.get("werklijst", [])):
        raise ValueError(f"werklijst-item {nr} bestaat niet")
    ov = _lees_overlay(data_dir)
    ov["werklijst"][str(int(nr))] = status
    versie = _bump_overlay_versie(ov)
    _schrijf_overlay(data_dir, ov)
    return versie
