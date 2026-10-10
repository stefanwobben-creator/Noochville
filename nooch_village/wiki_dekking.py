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
#: DE KOPNAMEN KOMEN UIT `wiki.VRAAGSECTIES` (een kopje per vraag, #697): het skelet, het zaad en
#: deze dekking lezen dezelfde namen. Het oude gedeelde kopje "Animal-derived & chemical status"
#: telt nergens voor: een feit eronder zegt niet welke van de twee vragen het beantwoordt.
VRAGEN: dict[str, tuple[tuple[str, str, tuple[str, ...], tuple[str, ...], str], ...]] = {
    "materiaal": (
        ("plastic", "Contains plastic?", ("pp",), wiki.kopnamen(wiki.PLASTIC), ""),
        ("biobased", "Biobased?", ("pp",), wiki.kopnamen(wiki.BIOBASED), ""),
        ("animal", "Animal-derived", ("vs",), wiki.kopnamen(wiki.DIERLIJK), ""),
        ("chem", "Dyes & chemicals", ("vs", "pp"), wiki.kopnamen(wiki.CHEMISCH), ""),
        ("co2", "CO2e per kg", ("pp",), (), "co2e_per_kg"),
        ("water", "Water per kg", ("pp",), (), "water_per_kg"),
        ("cert", "Certificate", ("vs", "pp"), wiki.kopnamen(wiki.CERTIFICERING), ""),
    ),
    "leverancier": (
        ("loc", "Location & contact", ("pp",), wiki.kopnamen(wiki.LOCATIE), ""),
        ("cert", "Company certification", ("vs", "pp"), wiki.kopnamen(wiki.BEDRIJFSCERT), ""),
        ("price", "Price per kg", ("pp",), (), "prijs_per_kg"),
        ("labor", "Labor & compliance", ("cfj",), wiki.kopnamen(wiki.ARBEID_COMPLIANCE), ""),
        ("own", "Ownership & health", ("pp",), wiki.kopnamen(wiki.EIGENDOM), ""),
    ),
}

# De vier celstatussen.
GECHECKT = "checked"        # een gegrond feit: nagekeken door een mens, geldig certificaat, citaat gevonden
ONGECHECKT = "unchecked"    # er staat een feit, maar de bron ontbreekt of de check is (nog) niet geldig
LEEG = "open"               # geen feit onder deze vraag
CONFLICT = "conflict"       # twee getallen spreken elkaar tegen, of een certificaat is verlopen
UITGESTELD = "deferred"     # nog geen antwoord, bewust uitgesteld tot een datum, met een eigenaar

#: Hoe zwaar een status weegt als een cel meerdere feiten heeft: een conflict mag nooit wegvallen
#: achter een ander, gecheckt feit.
_GEWICHT = {CONFLICT: 3, GECHECKT: 2, ONGECHECKT: 1, UITGESTELD: 0, LEEG: 0}

# ── Uitstel ("Deferred, to research later", 10 oktober 2026) ──────────────────
#: Waar een pagina haar uitgestelde vragen onthoudt: in haar eigen `meta`, naast de feiten — geen
#: tweede store. Per vraag: {tot (ISO "research by"), eigenaar (rol-id), door, op}.
#:
#: WAAROM: een lege vraag is niet hetzelfde als een vraag waarvan iemand zegt "die zoeken we uit vóór
#: datum X". Het eerste is een gat, het tweede een afspraak. Een afspraak met een datum telt mee voor
#: CN3 zolang de datum niet voorbij is; daarna valt hij terug op leeg en telt de pagina niet meer.
#: Deferred wordt NOOIT opgeteld bij gecheckt: het is een belofte, geen antwoord.
UITSTEL_SLEUTEL = "uitgesteld"


def maak_uitstel(tot: str, eigenaar: str, door: str = "") -> dict | None:
    """{tot, eigenaar, door, op} of None. Datum en eigenaar zijn verplicht."""
    import time as _t
    tot = str(tot or "").strip()[:10]
    try:
        _t.strptime(tot, "%Y-%m-%d")
    except ValueError:
        return None
    eigenaar = " ".join(str(eigenaar or "").split())[:120]
    if not eigenaar:
        return None
    return {"tot": tot, "eigenaar": eigenaar, "door": str(door or "")[:64], "op": _t.time()}


def uitstel(pagina, k: str) -> dict | None:
    """Het uitstel van vraag `k` op deze pagina, opnieuw gevalideerd bij het lezen, of None."""
    u = ((getattr(pagina, "meta", None) or {}).get(UITSTEL_SLEUTEL) or {}).get(k)
    if not isinstance(u, dict):
        return None
    return u if maak_uitstel(u.get("tot"), u.get("eigenaar")) else None


def placeholders_van(soort: str, k: str) -> tuple[str, ...]:
    """De open-punt-regels die het zaad onder deze vraag zette ("Dye/chemical disclosure: not yet
    provided")."""
    v = next((x for x in vragen(soort) if x["k"] == k), None)
    if v is None or not v["koppen"]:
        return ()
    sectie = next((s for s in wiki.VRAAGSECTIES.get(soort, ()) if wiki.kopnamen(s) == v["koppen"]), None)
    return tuple(sectie[2]) if sectie else ()


# DE OPEN-PUNT-REGEL WORDT AFGELEID, NIET WEGGEHAALD (fix 11 oktober 2026). Tot dan haalde uitstellen
# de regel uit de TEKST, en terugdraaien zette hem niet terug: de pagina was na uitstellen en
# terugdraaien een andere pagina, en een verlopen datum bracht de regel ook niet terug. Nu blijft
# de tekst onaangeroerd en beslist de STAAT VAN HET VELD of de regel getoond (en geteld) wordt:
#   leeg (ook verlopen) → de regel staat er;
#   deferred            → de afspraak staat er ("deferred, research by …");
#   beantwoord          → niets (een "not yet provided" naast een antwoord is onwaar).
# Er hoeft dus nooit iets "teruggezet" te worden, en een tussentijdse bewerking van de pagina kan
# niet botsen met een opgeslagen regel.

def placeholder_vragen(soort: str) -> dict[str, str]:
    """{open-punt-regel: vraag-sleutel} voor een paginasoort."""
    return {p: v["k"] for v in vragen(soort) for p in placeholders_van(soort, v["k"])}


def soort_van(rij: dict) -> str:
    return "materiaal" if "onderdelen" in rij else "leverancier"


def verborgen_placeholders(rij: dict, soort: str = "") -> dict[str, dict]:
    """{open-punt-regel: cel} voor de regels die NIET getoond worden, omdat hun veld niet leeg is
    (deferred of beantwoord)."""
    soort = soort or soort_van(rij)
    return {p: rij["cellen"][k] for p, k in placeholder_vragen(soort).items()
            if rij["cellen"].get(k, {}).get("status", LEEG) != LEEG}


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
        import time as _t
        plek = next((k for k in koppen if _norm(k) in toegestaan), "")
        u = uitstel(pagina, vraag["k"])
        vandaag = ctx.get("vandaag") or _t.strftime("%Y-%m-%d")
        if u and u["tot"] >= vandaag:
            return {"status": UITGESTELD, "feiten": [], "kop": plek, "reden": "",
                    "tot": u["tot"], "eigenaar": u["eigenaar"]}
        if u:
            # VERLOPEN: terug naar leeg — de afspraak is niet nagekomen, de pagina telt niet meer.
            return {"status": LEEG, "feiten": [], "kop": plek, "verlopen": True, "tot": u["tot"],
                    "eigenaar": u["eigenaar"], "reden": f"deferred until {u['tot']} — expired"}
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


# ── Het dorp als geheel: CN3 "Substantiated pages" (10 oktober 2026) ─────────

#: De zin die het zaad op een pagina zet zolang iets niet bekend is (`wiki.ARBEID_COMPLIANCE`, …).
#: Een pagina die er nog een draagt, is nog niet "met alles wat we weten" ingevuld (laag 2 van CN3).
PLACEHOLDERS = ("not yet provided", "not yet verified")


def voor_het_dorp(uitkomsten: list[dict], **ctx) -> dict:
    """De dekking over ALLE modellen samen: elk materiaal en elke leverancier één keer, ook als ze in
    twee modellen zitten. `uitkomsten` = `bom_reken.bereken` per model."""
    return dekking({"rijen": [r for u in uitkomsten for r in u.get("rijen", [])]}, **ctx)


def gestaafd(rij: dict, **ctx) -> bool:
    """Telt deze pagina mee voor CN3? Sinds de aanvulling "deferred" (10 oktober 2026) — alles:

    1. de pagina bestaat;
    2. ELK VELD is gecheckt, of deferred met een "research by"-datum die nog niet voorbij is;
    3. geen enkel feit op de pagina is ongecheckt of in conflict;
    4. bij een MATERIAAL: er is een leverancier gekoppeld.

    Dit vervangt de placeholder-toets van de vorige versie: "not yet provided" wordt niet meer
    getoond zodra een veld deferred is (`verborgen_placeholders`), en een veld dat leeg is zonder
    afspraak houdt de pagina hoe dan ook tegen.
    "Lege vragen mogen blijven staan" vervalt daarmee."""
    pagina = rij.get("pagina")
    if pagina is None:
        return False
    if "onderdelen" in rij and not rij.get("leverancier"):       # een materiaalrij zonder leverancier
        return False
    if any(c["status"] not in (GECHECKT, UITGESTELD) for c in rij["cellen"].values()):
        return False
    c = {"ledger": ctx.get("ledger"), "store": ctx.get("store"), "vandaag": ctx.get("vandaag", ""),
         "bestaat": ctx.get("bestaat")}
    return all(_feit_status(f, c) == GECHECKT for f in wiki.feiten(pagina))


def tekst_voor_lezers(pagina, vandaag: str = "") -> str:
    """De paginatekst voor wie hem BUITEN de pagina leest (zoeken, `/context`, de wiki-kaarten):
    de open-punt-regel van een deferred vraag (datum niet voorbij) wordt de afspraak, net als op de
    pagina. Leest alleen de pagina zelf (`meta`), geen stores — dus ook bruikbaar waar de dekking
    van /bom niet beschikbaar is. Een verlopen uitstel laat de regel staan: het veld is weer leeg."""
    import time as _t
    body = getattr(pagina, "body", "") or ""
    uit_meta = (getattr(pagina, "meta", None) or {}).get(UITSTEL_SLEUTEL) or {}
    if not uit_meta or not body:
        return body
    vandaag = vandaag or _t.strftime("%Y-%m-%d")
    per_regel = {**placeholder_vragen("materiaal"), **placeholder_vragen("leverancier")}
    regels = []
    for regel in body.split("\n"):
        r = regel.strip()
        k = per_regel.get(r[2:].strip()) if r[:2] in ("- ", "* ") else None
        u = uitstel(pagina, k) if k else None
        if u and u["tot"] >= vandaag:
            regel = f"- {r[2:].split(':')[0].strip()}: deferred, research by {u['tot']}"
        regels.append(regel)
    return "\n".join(regels)


def heeft_placeholder(rij: dict) -> bool:
    """Draagt de pagina nog een ZICHTBARE open-punt-regel? Een regel bij een deferred of beantwoord
    veld telt niet: die wordt ook niet getoond (`verborgen_placeholders`)."""
    weg = verborgen_placeholders(rij)
    for regel in (getattr(rij.get("pagina"), "body", "") or "").split("\n"):
        r = regel.strip()
        if r[:2] in ("- ", "* "):
            r = r[2:].strip()
        if any(p in r.lower() for p in PLACEHOLDERS) and r not in weg:
            return True
    return False


def cijfers(dek: dict, **ctx) -> dict:
    """Alle getallen van CN3 uit één dekking — berekend, nooit opgeslagen.

    Laag 1 · koppeling: materialen met een leverancier.
    Laag 2 · pagina: materialen + leveranciers met een pagina zonder placeholder-zin.
    Laag 3 · dekking: de vraagcellen per status.
    Critical Number: aandeel gestaafde pagina's. Smart Number: het aantal lege cellen."""
    mats, levs = dek["materialen"], dek["leveranciers"]
    rijen = mats + levs
    cellen = [c for r in rijen for c in r["cellen"].values()]
    n_gestaafd = sum(1 for r in rijen if gestaafd(r, **ctx))
    return {
        "materialen": len(mats),
        "met_leverancier": sum(1 for m in mats if m.get("leverancier")),
        "paginas_totaal": len(rijen),
        "paginas_bestaan": sum(1 for r in rijen if r.get("pagina") is not None),
        "paginas_zonder_placeholder": sum(1 for r in rijen if r.get("pagina") is not None
                                          and not heeft_placeholder(r)),
        "gestaafd": n_gestaafd,
        "gestaafd_pct": round(100 * n_gestaafd / len(rijen), 1) if rijen else None,
        "cellen_checked": sum(1 for c in cellen if c["status"] == GECHECKT),
        "cellen_unchecked": sum(1 for c in cellen if c["status"] == ONGECHECKT),
        "cellen_open": sum(1 for c in cellen if c["status"] == LEEG),
        "cellen_conflict": sum(1 for c in cellen if c["status"] == CONFLICT),
        # Deferred staat APART, nooit bij gecheckt: een belofte met een datum is geen antwoord.
        "cellen_deferred": sum(1 for c in cellen if c["status"] == UITGESTELD),
        "cellen_deferred_verlopen": sum(1 for c in cellen if c.get("verlopen")),
    }


def open_vragen(dek: dict) -> list[dict]:
    """Elke vraagcel die nog niet gecheckt is, als rij: {soort, naam, pagina, vraag, status, kop}.
    Conflicten eerst, dan ongecheckt, dan leeg — de volgorde waarin ze aandacht vragen."""
    volgorde = {CONFLICT: 0, ONGECHECKT: 1, LEEG: 2, UITGESTELD: 3}
    uit = []
    for soort, sleutel in (("materiaal", "materialen"), ("leverancier", "leveranciers")):
        labels = {v["k"]: v["label"] for v in vragen(soort)}
        for r in dek[sleutel]:
            for k, c in r["cellen"].items():
                if c["status"] != GECHECKT:
                    uit.append({"soort": soort, "naam": r["naam"], "pagina": r.get("pagina"),
                                "k": k, "vraag": labels[k], "status": c["status"],
                                "kop": c.get("kop", ""), "reden": c.get("reden", ""),
                                "tot": c.get("tot", ""), "eigenaar": c.get("eigenaar", ""),
                                "verlopen": bool(c.get("verlopen"))})
    # Deferred sorteert op "research by" (de vroegste afspraak bovenaan), de rest op naam.
    return sorted(uit, key=lambda x: (volgorde[x["status"]], x["tot"] if x["status"] == UITGESTELD else "",
                                      x["soort"], x["naam"].lower()))


def uit_stores(att, leveranciers, materialen, *, ledger=None, bestaat=None) -> tuple[dict, dict]:
    """(dekking over alle modellen, ctx) uit de stores die /bom ook leest. Op modelniveau: een
    kleurvariant verandert welke materialen het dorp heeft niet."""
    from nooch_village import bom_reken
    from nooch_village.data_bom import MODELLEN
    pags = wiki.paginas(att)
    uitk = [bom_reken.bereken(MODELLEN[m]["master"], pags, leveranciers.alle(),
                              afwijkingen=materialen.afwijkingen(m, "")) for m in MODELLEN]
    ctx = {"ledger": ledger, "store": att, "bestaat": bestaat}
    return voor_het_dorp(uitk, **ctx), ctx
