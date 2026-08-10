"""radar_nieuwheid.py — is de INHOUD van dit signaal nieuw voor het dorp?

Strikt gescheiden van `radar_clusters`. Dat is geen nettigheid maar de kern van het ontwerp:

    **Onderwerp-bekend is niet inhoud-bekend.**

Een cluster zegt "hier gaat het weer over mycelium". Dat is een uitspraak over het ONDERWERP. Als
je daarop zou filteren, verdwijnt het signaal "kweker X in Portugal levert vanaf Q3 op 40°C" achter
de vaststelling dat mycelium een bekend onderwerp is — precies het feit dat je wilde hebben. Daarom
draait deze check op de inhoud, per signaal, en altijd BINNEN het cluster: een nieuw feit in een
bekend onderwerp moet naar boven komen.

Hergebruikt `weten_we_dit_al` (de geheugen-eerst-skill): die doorzoekt kennisbank, kaarten-
bibliotheek, De Kroniek en projecten. Wat deze module toevoegt is de tweede vraag. De skill zegt
"raakt dit iets dat we hebben"; wij vragen daarna "en staat er iets in dit signaal dat in géén van
die treffers voorkomt". Dat verschil — een leverancier, een eigenschap, een getal — is de nieuwheid.

FAIL-SOFT EN RECALL-VEILIG, in die volgorde. Faalt de geheugencheck, dan geldt het signaal als
nieuw en blijft het zichtbaar. Nooit andersom: een signaal verbergen omdat het geheugen stuk was,
is precies het soort stille fout waar je maanden later achter komt. `gefaald` reist mee in de
uitslag zodat het scherm het kan zeggen.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import types

log = logging.getLogger("village.radar.nieuwheid")

CACHE_BESTAND = "radar_nieuwheid.json"

_TOKEN = re.compile(r"[\w\-]+")
_MIN_WOORD = 4
# Woorden die in bijna elk radar-signaal staan: die dragen geen nieuwheid, ook niet als ze
# toevallig in geen enkele treffer voorkomen.
_RUIS = {"deze", "voor", "over", "naar", "wordt", "worden", "heeft", "hebben", "kunnen",
         "zoals", "onder", "tussen", "andere", "nieuwe", "nieuw", "duurzame", "duurzaam",
         "materiaal", "materialen", "schoenen", "schoen", "productie", "bedrijf", "merk",
         "with", "from", "that", "this", "have", "will", "their", "which", "more", "than",
         "into", "about", "been", "they", "would", "could", "when", "what", "were", "also",
         "sustainable", "material", "materials", "shoes", "shoe", "footwear", "brand", "company"}


def _hash(tekst: str) -> str:
    return hashlib.sha1((tekst or "").encode("utf-8")).hexdigest()[:16]


def _kernwoorden(tekst: str) -> tuple[list[str], set[str]]:
    """De betekenisdragers van een signaal, plus welke daarvan een eigennaam lijken.

    Getallen tellen expliciet mee ongeacht lengte — '40°C', 'Q3', '2027' zijn juist het soort
    inhoud dat nieuw kan zijn terwijl het onderwerp bekend is.

    Eigennaam-heuristiek: een woord met een hoofdletter dat niet vooraan de tekst staat. Dat vangt
    leveranciers, merken en plaatsen ('Ecovative', 'Portugal') — precies de soort inhoud waar de
    regel over gaat. Deterministisch en zonder LLM; een gemiste eigennaam kost hooguit een plek in
    de rangschikking, geen zichtbaarheid."""
    uit: list[str] = []
    namen: set[str] = set()
    for n, w in enumerate(_TOKEN.findall(tekst or "")):
        low = w.lower()
        if any(ch.isdigit() for ch in low):
            uit.append(low)
        elif len(low) >= _MIN_WOORD and low not in _RUIS:
            uit.append(low)
            if n > 0 and w[:1].isupper():
                namen.add(low)
    return uit, namen


def _trefferteksten(uitslag: dict) -> str:
    """Alles wat het geheugen als treffer teruggaf, als één doorzoekbare tekst."""
    stukken: list[str] = []
    for i in uitslag.get("inzichten") or []:
        stukken += [str(i.get("titel") or ""), str(i.get("subject") or "")]
    for k in uitslag.get("kaarten") or []:
        stukken += [str(k.get("claim") or ""), str(k.get("bron") or "")]
    for p in uitslag.get("projecten") or []:
        stukken += [str(p.get("scope") or ""), str(p.get("antwoord") or "")]
    for bak in (uitslag.get("kroniek") or {}).values():
        for r in bak or []:
            stukken.append(str(r.get("query") or ""))
    for c in uitslag.get("context") or []:
        stukken += [str(c.get("titel") or ""), str(c.get("claim") or ""),
                    str(c.get("scope") or ""), str(c.get("query") or "")]
    return " ".join(stukken).lower()


def nieuwe_kernen(inhoud: str, uitslag: dict, *, maximaal: int = 6) -> list[str]:
    """De woorden uit dit signaal die in GEEN enkele geheugentreffer voorkomen.

    Dit is de operationalisering van "een leverancier, eigenschap of getal dat we nog niet hebben".
    Deterministisch en zonder LLM: substring-match tegen de trefferteksten, zodat 'mycelium' ook
    'myceliumleer' dekt. Leeg = het signaal voegt lexicaal niets toe aan wat we al hadden.

    De uitslag is GERANGSCHIKT, niet zomaar de eerste n woorden: getallen eerst, dan eigennamen,
    dan de rest. Dat is geen cosmetiek — een cap op leesvolgorde gooide precies de scherpste
    markers weg zodra ze achteraan in de zin stonden ('...in Portugal bij 40 graden'). Een getal
    of een leveranciersnaam zegt meer over nieuwe inhoud dan een werkwoord dat toevallig vooraan
    stond."""
    bekend = _trefferteksten(uitslag)
    woorden, namen = _kernwoorden(inhoud)
    gezien: list[str] = []
    for w in woorden:
        if w not in bekend and w not in gezien:
            gezien.append(w)
    cijfers = [w for w in gezien if any(ch.isdigit() for ch in w)]
    eigennamen = [w for w in gezien if w in namen and w not in cijfers]
    rest = [w for w in gezien if w not in cijfers and w not in eigennamen]
    return (cijfers + eigennamen + rest)[:maximaal]


def _context_voor(data_dir: str, context=None):
    """De skill leest via `context.data_dir`; een aanroeper zonder context krijgt een schil."""
    if context is not None and getattr(context, "data_dir", None):
        return context
    return types.SimpleNamespace(data_dir=data_dir)


def beoordeel_signaal(inhoud: str, *, data_dir: str, context=None, skill=None) -> dict:
    """Is de inhoud van dit signaal nieuw? Geeft {nieuw, reden, treffers, kernen, gefaald}.

    Drie uitkomsten, en de derde is de belangrijkste:
      - het geheugen kent dit onderwerp niet          → nieuw
      - het kent het onderwerp, maar niet deze kernen → nieuw (het feit in het bekende onderwerp)
      - het kent onderwerp én kernen                  → bekend, vouwt in het cluster

    Faalt de check, dan is de uitslag nieuw + `gefaald: True`. Recall-veilig: liever een signaal
    te veel op het scherm dan één dat stil verdween omdat een store kapot was."""
    inhoud = (inhoud or "").strip()
    if not inhoud:
        return {"nieuw": True, "reden": "empty signal — shown to be safe",
                "treffers": 0, "kernen": [], "gefaald": True}
    try:
        if skill is None:
            from nooch_village.skills_impl.weten_we_dit_al import WetenWeDitAlSkill
            skill = WetenWeDitAlSkill()
        uitslag = skill.run({"vraag": inhoud}, _context_voor(data_dir, context))
    except Exception as e:                           # noqa: BLE001 — nooit een signaal verliezen
        log.warning("geheugencheck faalde, signaal blijft staan: %s", e)
        return {"nieuw": True, "reden": f"memory check failed ({e}) — shown to be safe",
                "treffers": 0, "kernen": [], "gefaald": True}
    if not isinstance(uitslag, dict) or not uitslag.get("ok"):
        return {"nieuw": True, "reden": "memory check gave no answer — shown to be safe",
                "treffers": 0, "kernen": [], "gefaald": True}

    treffers = int(uitslag.get("treffers") or 0)
    if not uitslag.get("bekend"):
        return {"nieuw": True, "reden": "the village has nothing on this yet",
                "treffers": treffers, "kernen": [], "gefaald": False}
    kernen = nieuwe_kernen(inhoud, uitslag)
    if kernen:
        return {"nieuw": True,
                "reden": ("known topic, but these are new to us: " + ", ".join(kernen)),
                "treffers": treffers, "kernen": kernen, "gefaald": False}
    return {"nieuw": False, "reden": f"{treffers} existing entries already cover this",
            "treffers": treffers, "kernen": [], "gefaald": False}


# ── Cache: een oordeel per (signaal, inhoud) ─────────────────────────────────────────────────
# Zonder cache wisselt de nieuwheid van een signaal tussen twee page-loads zodra het geheugen
# groeit, en dat maakt de blinde meting onbetrouwbaar (de founder zou een ander scherm zien dan
# waarop de AI werd beoordeeld). De sleutel bevat de inhoud-hash, dus een gewijzigd signaal wordt
# opnieuw beoordeeld.

def _cache_pad(data_dir: str) -> str:
    return os.path.join(data_dir, CACHE_BESTAND)


def _lees_cache(data_dir: str) -> dict:
    try:
        with open(_cache_pad(data_dir), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _schrijf_cache(data_dir: str, cache: dict) -> None:
    try:
        os.makedirs(data_dir, exist_ok=True)
        tmp = _cache_pad(data_dir) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
        os.replace(tmp, _cache_pad(data_dir))
    except OSError as e:
        log.warning("nieuwheid-cache niet weggeschreven: %s", e)


def beoordeel_items(items: list[dict], *, data_dir: str, context=None, skill=None,
                    gebruik_cache: bool = True) -> dict[str, dict]:
    """Nieuwheid per signaal-id, met cache. Faalt nooit: elk item krijgt een uitslag."""
    cache = _lees_cache(data_dir) if gebruik_cache else {}
    uit: dict[str, dict] = {}
    veranderd = False
    for it in items:
        sid = it.get("id")
        if not sid:
            continue
        sleutel = f"{sid}:{_hash(str(it.get('content') or ''))}"
        if gebruik_cache and sleutel in cache:
            uit[sid] = cache[sleutel]
            continue
        oordeel = beoordeel_signaal(str(it.get("content") or ""), data_dir=data_dir,
                                    context=context, skill=skill)
        uit[sid] = oordeel
        # Een gefaalde check hoort NIET in de cache: die moet de volgende keer opnieuw draaien,
        # anders bevriest een tijdelijke storing het oordeel "nieuw" voor altijd.
        if gebruik_cache and not oordeel.get("gefaald"):
            cache[sleutel] = oordeel
            veranderd = True
    if veranderd:
        _schrijf_cache(data_dir, cache)
    return uit


def splits(clusters: list[dict], oordelen: dict[str, dict]) -> list[dict]:
    """Hang de nieuwheid aan elk cluster: welke leden komen individueel boven, welke vouwen in.

    Invouwen is zichtbaar en omkeerbaar — `ingevouwen` bevat de volledige signalen, niets wordt
    weggegooid. Het scherm klapt ze open; de teller blijft ze meetellen."""
    for c in clusters:
        nieuw, bekend = [], []
        for lid in c["leden"]:
            (nieuw if oordelen.get(lid["id"], {}).get("nieuw", True) else bekend).append(lid)
        c["nieuw"] = nieuw
        c["ingevouwen"] = bekend
    return clusters
