"""Dekking — welke vragen een materiaal- of leverancierpagina al beantwoordt (`/bom`, 10 oktober 2026).

Doel: per materiaal en per leverancier op de stuklijst zien wat er nog ontbreekt voor de Vegan
Society, het Product Passport en CFJ. De andere kant op van "From the BOM" op een wikipagina: daar
leest de pagina de stuklijst, hier leest de stuklijst de pagina's.

ALLEEN BEREKENEN, NIETS OPSLAAN. De wiki is de bron van waarheid. Er is geen dekkings-bestand en geen
formulier; verandert er een feit op een pagina, dan klopt de strook de volgende pageload vanzelf.

"UNKNOWN" IS NIET "NO". Een lege cel zegt: er staat nog geen feit onder deze vraag. Een feit
"contains no plastic" met een bron IS een antwoord, en kleurt dus net zo als "contains plastic".
Deze laag oordeelt niet over de inhoud, alleen over of er een gegrond antwoord staat.

WELK FEIT BIJ WELKE VRAAG. Twee manieren, allebei expliciet en in `VRAGEN` vastgelegd:
1. een GETAL-vraag (CO2e, water, prijs) leest de grootheid van een feit met waarde
   (`wiki.GROOTHEDEN`) — dezelfde regel als `bom_reken`, waar het kopje niet uitmaakt;
2. een TEKST-vraag leest het kopje waaronder het feit in de tekst staat (`{{fact:id}}` sinds #693),
   of, voor een feit dat nog geen plek heeft, zijn `For:`-regel (`sectie`). Alleen de kopnamen in
   `koppen` tellen; een feit onder een ander kopje beantwoordt geen vraag. Dat is bewust streng: een
   gok over welke vraag een alinea beantwoordt zou een groene cel opleveren die niemand heeft
   nagekeken.
"""
from __future__ import annotations

import re

from nooch_village import wiki

# ── De vragen ───────────────────────────────────────────────────────────────

#: De drie doelen waar de vragen voor bestaan. Sleutel → label op het scherm.
DOELEN: dict[str, str] = {"vs": "Vegan Society", "pp": "Product Passport", "cfj": "CFJ labor"}

#: DE ENE PLEK VOOR DE VRAGEN, per paginasoort: (sleutel, label, doelen, koppen, grootheid).
#: `koppen` = de kopnamen (hoofdletter-ongevoelig) waaronder een feit deze vraag beantwoordt;
#: `grootheid` = voor een getal-vraag de grootheid uit `wiki.GROOTHEDEN`, anders "".
#: De doelen komen uit het prototype van 10 oktober 2026 (arrays MQ en SQ).
#:
#: "Animal-derived & chemical status" STAAT HIER BEWUST NIET: dat ene kopje uit het zaad
#: (`wiki.DIERLIJK_CHEMISCH`) draagt twee vragen, en een feit eronder zegt niet welke van de twee
#: het beantwoordt. Gokken zou "animal-derived: answered" kunnen maken van een REACH-brief.
VRAGEN: dict[str, tuple[tuple[str, str, tuple[str, ...], tuple[str, ...], str], ...]] = {
    "materiaal": (
        ("plastic", "Contains plastic?", ("pp",), ("contains plastic", "plastic"), ""),
        ("biobased", "Biobased?", ("pp",), ("biobased", "biobased content"), ""),
        ("animal", "Animal-derived", ("vs",), ("animal-derived", "animal-derived status"), ""),
        ("chem", "Dyes & chemicals", ("vs", "pp"), ("dyes & chemicals", "dyes and chemicals"), ""),
        ("co2", "CO2e per kg", ("pp",), (), "co2e_per_kg"),
        ("water", "Water per kg", ("pp",), (), "water_per_kg"),
        ("cert", "Certificate", ("vs", "pp"), ("certificate", "certification", "certifications"), ""),
    ),
    "leverancier": (
        ("loc", "Location & contact", ("pp",), ("location & contact",), ""),
        ("cert", "Company certification", ("vs", "pp"), ("company certification",), ""),
        ("price", "Price per kg", ("pp",), (), "prijs_per_kg"),
        ("labor", "Labor & compliance", ("cfj",), ("labor & compliance",), ""),
        ("own", "Ownership & health", ("pp",), ("ownership & health",), ""),
    ),
}

# De vier celstatussen.
GECHECKT = "checked"        # een gegrond feit: nagekeken door een mens, geldig certificaat, citaat gevonden
ONGECHECKT = "unchecked"    # er staat een feit, maar de bron ontbreekt of de check is (nog) niet geldig
LEEG = "open"               # geen feit onder deze vraag
CONFLICT = "conflict"       # twee getallen spreken elkaar tegen, of een certificaat is verlopen

#: Hoe zwaar een status weegt als een cel meerdere feiten heeft: een conflict mag nooit wegvallen
#: achter een ander, gecheckt feit.
_GEWICHT = {CONFLICT: 3, GECHECKT: 2, ONGECHECKT: 1, LEEG: 0}


def _norm(s: str) -> str:
    return " ".join((s or "").split()).lower()


def vragen(soort: str, doel: str = "") -> list[dict]:
    """De vragen voor een paginasoort, eventueel alleen die van één doel."""
    uit = []
    for k, label, doelen, koppen, grootheid in VRAGEN.get(soort, ()):
        if doel and doel not in doelen:
            continue
        uit.append({"k": k, "label": label, "doelen": doelen, "koppen": koppen,
                    "grootheid": grootheid})
    return uit


# ── Feit → kopje ────────────────────────────────────────────────────────────

_KOP_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def _koppen_en_feiten(body: str):
    """Loop één keer door de tekst: (kopjes in volgorde, {feit-id: omvattende kopjes})."""
    stapel: list[tuple[int, str]] = []
    alle: list[str] = []
    paden: dict[str, list[str]] = {}
    in_code = False
    for regel in (body or "").split("\n"):
        r = regel.strip()
        if r.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = _KOP_RE.match(r)
        if m:
            niveau = len(m.group(1))
            while stapel and stapel[-1][0] >= niveau:
                stapel.pop()
            stapel.append((niveau, m.group(2)))
            alle.append(m.group(2))
            continue
        f = wiki.FEIT_MARKER_RE.match(r)
        if f and f.group(1) not in paden:
            paden[f.group(1)] = [t for _n, t in stapel]
    return alle, paden


def kop_paden(body: str) -> dict[str, list[str]]:
    """{feit-id: [omvattende kopjes, buitenste eerst]} voor elk feit dat in de tekst staat.

    Een feit onder een subkopje telt ook voor het kopje erboven: "### Lab report" binnen
    "## Certification" gaat over certificering. Koppen in een codeblok tellen niet."""
    return _koppen_en_feiten(body)[1]


def _koppen_van(feit: dict, paden: dict[str, list[str]]) -> list[str]:
    """Waar dit feit staat: zijn kopjes in de tekst, of anders zijn `For:`-regel."""
    fid = wiki.feit_id(feit)
    if fid in paden:
        return paden[fid]
    return [feit["sectie"]] if feit.get("sectie") else []


# ── Eén cel ─────────────────────────────────────────────────────────────────

def _feit_status(feit: dict, ctx: dict) -> str:
    """De status van één feit. Een verlopen certificaat is een CONFLICT, geen "nog niet gecheckt":
    er wordt iets beweerd waar het bewijs van op is."""
    grond = feit.get("grond") or {}
    if grond.get("soort") == "cert":
        # De BRON los van wat een mens ervan zei: een verlopen certificaat wint ook van een
        # eerdere "I checked this" (zelfde volgorde als `wiki.grond_status`).
        if wiki._bron_status(feit, **ctx)["status"] == wiki.VERVALLEN:
            return CONFLICT
    return GECHECKT if wiki.grond_status(feit, **ctx)["status"] == wiki.GEGROND else ONGECHECKT


def _cel(vraag: dict, pagina, koppen: list[str], paden: dict, ctx: dict) -> dict:
    """{status, feiten, kop, reden} voor één vraag op één pagina.

    `kop` is het kopje waar het scherm naartoe springt: waar het antwoord staat, of — bij een lege
    cel — het kopje op de pagina waar het hoort. Leeg als de pagina zo'n kopje (nog) niet heeft."""
    if pagina is None:
        return {"status": LEEG, "feiten": [], "kop": "", "reden": "no page"}
    toegestaan = {_norm(k) for k in vraag["koppen"]}
    treffers: list[tuple[dict, str]] = []          # (feit, het kopje waar hij onder stond)
    for f in wiki.feiten(pagina):
        if vraag["grootheid"]:
            w = wiki.waarde(f)
            if w and w["grootheid"] == vraag["grootheid"]:
                treffers.append((f, ""))
            continue
        kop = next((k for k in _koppen_van(f, paden) if _norm(k) in toegestaan), None)
        if kop is not None:
            treffers.append((f, kop))
    if not treffers:
        plek = next((k for k in koppen if _norm(k) in toegestaan), "")
        return {"status": LEEG, "feiten": [], "kop": plek, "reden": "no fact for this question"}
    statussen = [_feit_status(f, ctx) for f, _k in treffers]
    reden = ""
    if vraag["grootheid"]:
        getallen = {wiki.waarde(f)["getal"] for f, _k in treffers}
        if len(getallen) > 1:
            # Twee waarden voor dezelfde grootheid: welke het is, is een besluit van de eigenaar.
            # `bom_reken` telt hem dan ook niet mee.
            statussen.append(CONFLICT)
            reden = "more than one value on the page"
    status = max(statussen, key=_GEWICHT.__getitem__)
    if status == CONFLICT and not reden:
        reden = "a certificate has expired"
    return {"status": status, "feiten": [wiki.feit_id(f) for f, _k in treffers],
            "kop": next((k for _f, k in treffers if k), ""), "reden": reden}


def _rij(soort: str, naam: str, pagina, ctx: dict, **extra) -> dict:
    koppen, paden = _koppen_en_feiten(getattr(pagina, "body", "")) if pagina is not None else ([], {})
    return {"naam": naam, "pagina": pagina, **extra,
            "cellen": {v["k"]: _cel(v, pagina, koppen, paden, ctx) for v in vragen(soort)}}


# ── De hele strook ──────────────────────────────────────────────────────────

def dekking(bom: dict, *, ledger=None, store=None, vandaag: str = "", bestaat=None) -> dict:
    """{"materialen": [...], "leveranciers": [...]} voor één stuklijst.

    `bom` is de uitkomst van `bom_reken.bereken`: die heeft per rij de materiaal- en
    leverancierpagina al opgezocht (op BOM-naam, zie `wiki.resolve_bom`), dus hier wordt niets
    opnieuw gekoppeld. Elk materiaal en elke leverancier komt één keer voor, in stuklijstvolgorde.

    Een rij zonder pagina krijgt `pagina=None` en alleen lege cellen — geen fout: de pagina moet nog
    geschreven worden, en dat is precies wat de strook laat zien."""
    ctx = {"ledger": ledger, "store": store, "vandaag": vandaag, "bestaat": bestaat}
    mats: dict[str, dict] = {}
    levs: dict[str, dict] = {}
    for r in bom.get("rijen", []):
        mk = _norm(r["materiaal"])
        if mk and mk not in mats:
            mats[mk] = {"naam": r["materiaal"], "pagina": r.get("mat"),
                        "leverancier": r.get("supplier") or "", "onderdelen": []}
        if mk:
            mats[mk]["onderdelen"].append(r["part"])
        lk = _norm(r.get("supplier") or "")
        if lk:
            if lk not in levs:
                levs[lk] = {"naam": r["supplier"], "pagina": r.get("lev"), "materialen": []}
            if r["materiaal"] not in levs[lk]["materialen"]:
                levs[lk]["materialen"].append(r["materiaal"])
    return {
        "materialen": [_rij("materiaal", m["naam"], m["pagina"], ctx, leverancier=m["leverancier"],
                            onderdelen=m["onderdelen"]) for m in mats.values()],
        "leveranciers": [_rij("leverancier", l["naam"], l["pagina"], ctx,
                              materialen=l["materialen"]) for l in levs.values()],
    }


def volledig(rij: dict, soort: str, doel: str) -> bool:
    """Volledig voor dit doel = elke vraag met dit doel is gecheckt."""
    return all(rij["cellen"][v["k"]]["status"] == GECHECKT for v in vragen(soort, doel))


def rollup(dek: dict) -> dict:
    """{doel: {"materialen": (n, m), "leveranciers": (n, m)}} — hoeveel rijen volledig zijn.

    Alleen de paginasoorten die vragen voor dat doel hebben: CFJ vraagt niets aan een materiaal, en
    "0 van 14 materialen volledig voor CFJ" zou een gat suggereren dat er niet is."""
    uit: dict[str, dict] = {}
    for doel in DOELEN:
        per: dict[str, tuple[int, int]] = {}
        for soort, sleutel in (("materiaal", "materialen"), ("leverancier", "leveranciers")):
            if not vragen(soort, doel):
                continue
            rijen = dek[sleutel]
            per[sleutel] = (sum(1 for r in rijen if volledig(r, soort, doel)), len(rijen))
        uit[doel] = per
    return uit
