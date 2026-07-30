"""claims_substantiatie.py — de bewijs-vraag over een claim op de eigen site.

De regex-database zegt of een term MAG. Deze module stelt de tweede vraag die de EmpCo-richtlijn
stelt en die de tool tot nu toe niet stelde: is de claim ONDERBOUWD? Een milieuclaim over ons eigen
product is alleen groen als er een bevestigd record in de Kroniek (`EvidenceLedger`) tegenover staat.
Staat er niets, dan is het oranje "onderbouwing ontbreekt" — nooit stil groen.

Dit is dezelfde notie als de publicatie-gate van `content_check` (`publication_check.unverified_claims`:
een claim mag alleen mee als het kaartje `VERIFIED` is), maar met de opzoeklaag die een site-scan nodig
heeft: die heeft geen id-lijst van de auteur, alleen gevonden frases op een pagina.

Drie regels, en alle drie leunen ze naar VLAGGEN:

1. **Alleen `bevestigd` telt.** Exact de waarheidslat die `evidence_ledger.interpret()` al hanteert en
   die `claim_evidence` al inbakt: "claim gevonden, geen onderbouwing" is daar `leeg`, geen bewijs.
2. **Alleen ons eigen subject telt.** Een bevestigd B-Corp-record van een concurrent onderbouwt geen
   Nooch-claim. De eigen merknamen worden AFGELEID uit de scan-pagina's in de claims-database
   (reference, don't copy) — verhuist de site, dan verhuist deze toets mee.
3. **Fail-closed.** Geen register, onleesbaar register, of een halve match die een machine niet kan
   beslissen → geldt als niet-onderbouwd. Bij twijfel vlaggen; de mens veegt een onterechte vlag weg,
   een gemiste overtreding kost geld.

Zuivere logica, geen netwerk, geen LLM: de ledger gaat als argument mee zodat dit los te testen is.
"""
from __future__ import annotations

import logging
import re
import urllib.parse

log = logging.getLogger("village.claims.bewijs")

# De drie uitkomsten van de bewijs-vraag. `ambigu` is bewust geen vierde stoplicht maar een
# aantekening: hij gedraagt zich als `ontbreekt` (fail-closed) en levert daarnaast een capaciteitsgat
# op — de tool geeft toe dat hij het niet kon beslissen in plaats van te gokken.
ONDERBOUWD = "aanwezig"
ONTBREEKT = "ontbreekt"
AMBIGU = "ambigu"
NIET_VAN_TOEPASSING = "n.v.t."

# Rood is een verbod, geen bewijskwestie: 'wel onderbouwd' maakt een verboden generieke claim niet
# toelaatbaar. Bewijs kan een bevinding hier dus niet redden en de vraag wordt niet gesteld.
_BEWIJS_IRRELEVANT = ("red",)

_NIET_WOORD = re.compile(r"[^a-z0-9]+")
_MIN_TOKEN = 4                 # kortere tokens ('eco', 'bio') matchen te veel om iets te bewijzen


def _norm(tekst: str) -> str:
    """Kleine letters, alleen letters en cijfers, enkele spaties — zelfde normalisatie-idee als
    `claims_board.normaliseer`, zodat 'Plastic-Free' en 'plastic free' hetzelfde zijn."""
    return _NIET_WOORD.sub(" ", (tekst or "").lower()).strip()


def _tokens(tekst: str) -> set[str]:
    return {t for t in _norm(tekst).split() if len(t) >= _MIN_TOKEN}


def eigen_merken(db: dict) -> set[str]:
    """De merk-/domeinwoorden van ONS eigen huis, afgeleid uit `meta.scan_paginas`.

    De pagina's die we scannen zíjn onze site; daaruit volgt welk subject 'eigen' is. Zo staat de
    merknaam niet als literal in deze module (reference, don't copy) en volgt de toets automatisch
    als compliance de scan-lijst verhuist.

    Geen scan-pagina's → lege verzameling → niets kan onderbouwen. Dat is de fail-closed kant: liever
    alles oranje dan een concurrent-record dat onze claim groen praat."""
    merken: set[str] = set()
    for pagina in (db.get("meta") or {}).get("scan_paginas", []) or []:
        if not isinstance(pagina, dict):
            continue
        host = urllib.parse.urlparse(str(pagina.get("url") or "")).hostname or ""
        delen = [d for d in host.lower().split(".") if d and d != "www"]
        if delen:
            merken.add(delen[0])                     # nooch.earth → 'nooch'
    return merken


def _varianten(bevinding: dict) -> list[str]:
    """Waar we op matchen: de letterlijk gevonden frases én de varianten uit het term-veld.

    Het term-veld noteert varianten met een schuine streep ('milieuvriendelijk / eco-friendly');
    elk deel is een zelfstandige zoeksleutel."""
    uit: list[str] = []
    for gevonden in bevinding.get("gevonden") or []:
        g = _norm(gevonden)
        if g:
            uit.append(g)
    for deel in re.split(r"[/,]", str(bevinding.get("term") or "")):
        d = _norm(deel)
        if d:
            uit.append(d)
    return list(dict.fromkeys(uit))


def _index(ledger) -> list[dict]:
    """De Kroniek als platte, genormaliseerde zoeklijst. Eén keer per scan opgebouwd.

    Fail-closed: een onleesbaar register geeft een lege index, en een lege index betekent dat niets
    onderbouwd is — nooit dat alles in orde is."""
    try:
        rijen = ledger.all_records() if ledger is not None else []
    except Exception as e:                           # noqa: BLE001 — bewijs ophalen mag nooit fataal zijn
        log.warning("bewijsregister onleesbaar (%s) — alles geldt als niet-onderbouwd", e)
        return []
    index = []
    for r in rijen:
        if not isinstance(r, dict):
            continue
        meta = r.get("meta") if isinstance(r.get("meta"), dict) else {}
        onderwerp = " ".join(str(x) for x in (r.get("query", ""), meta.get("claim", "")))
        subject = " ".join(str(x) for x in (r.get("query", ""), r.get("source", ""),
                                           meta.get("subject", "")))
        index.append({"record": r, "status": r.get("status", ""),
                      "onderwerp": _norm(onderwerp), "onderwerp_tokens": _tokens(onderwerp),
                      "subject": _norm(subject)})
    return index


def _van_ons(rij: dict, merken: set[str]) -> bool:
    return any(m in rij["subject"] for m in merken)


def _match(varianten: list[str], rij: dict) -> str | None:
    """Hoe goed dekt dit record de claim? `vol`, `deel` of None.

    Bewust op HELE tokens en niet op substring: 'plasticvrij' zit letterlijk in 'plasticvrije
    verpakking', en dan zou bewijs over de vérpakking een claim over de zóól onderbouwen. Dat is
    precies de stille fout die recall-eerst niet mag maken.

    `deel` is de morfologische of gedeeltelijke bijna-match (plasticvrij ↔ plasticvrije, of één van
    twee woorden). Die geldt NIET als bewijs — hij wordt `ambigu`: een mens moet ernaar kijken."""
    tokens = rij["onderwerp_tokens"]
    kandidaten = [t for t in (_tokens(v) for v in varianten) if t]
    for vt in kandidaten:
        if vt <= tokens:
            return "vol"
    for vt in kandidaten:
        if vt & tokens:
            return "deel"                                # sommige woorden kloppen, niet alle
        if any(q.startswith(t) or t.startswith(q) for t in vt for q in tokens):
            return "deel"                                # zelfde stam, andere buiging
    return None


def bewijs_voor(bevinding: dict, index: list[dict], merken: set[str]) -> dict:
    """De bewijs-vraag voor één bevinding: `{onderbouwing, reden, records}`.

    Volle match op ons eigen subject met status `bevestigd` → onderbouwd. Een halve match (het
    subject klopt, de claim maar gedeeltelijk) → `ambigu`: dat is geen bewijs, maar wél een signaal
    dat een mens ernaar moet kijken. Al het andere → ontbreekt."""
    varianten = _varianten(bevinding)
    if not varianten:
        return {"onderbouwing": ONTBREEKT, "records": [],
                "reden": "geen concrete claim-frase om bewijs bij te zoeken"}

    volledig, gedeeltelijk = [], []
    for rij in index:
        if not _van_ons(rij, merken):
            continue                                 # bewijs over een ánder merk zegt niets over ons
        if rij["status"] != "bevestigd":
            continue                                 # leeg/fout is onderzocht-en-niets, geen bewijs
        dekking = _match(varianten, rij)
        if dekking == "vol":
            volledig.append(rij["record"])
        elif dekking == "deel":
            gedeeltelijk.append(rij["record"])

    if volledig:
        bronnen = sorted({str(r.get("source") or "") for r in volledig if r.get("source")})
        citaat = next((str(r.get("result_ref")) for r in volledig if r.get("result_ref")), "")
        reden = f"{len(volledig)} bevestigd record" + ("s" if len(volledig) > 1 else "")
        if bronnen:
            reden += " — " + ", ".join(bronnen[:2])
        if citaat:
            reden += f" · “{citaat[:160]}”"
        return {"onderbouwing": ONDERBOUWD, "records": volledig, "reden": reden}
    if gedeeltelijk:
        return {"onderbouwing": AMBIGU, "records": gedeeltelijk,
                "reden": (f"{len(gedeeltelijk)} bevestigd record raakt deze claim gedeeltelijk — "
                          f"een machine kan niet vaststellen of het dezelfde claim onderbouwt")}
    return {"onderbouwing": ONTBREEKT, "records": [],
            "reden": "geen bevestigd record in de Kroniek voor deze claim op onze eigen site"}


def pas_toe(bevindingen: list[dict], *, ledger, db: dict) -> list[dict]:
    """Zet de bewijs-velden op elke bevinding en verhoog een ONDERBOUWDE-loze groene claim naar oranje.

    Wat er verandert per stoplicht:
      `red`        → onveranderd; een verbod is geen bewijskwestie.
      `orange`     → blijft oranje. Mét bewijs vertelt de taak nu wáár dat bewijs staat; zónder bewijs
                     staat de reden erbij. Bewust géén verlaging naar groen: dat zou recall inruilen.
      `green`      → zonder bewijs ORANJE ("onderbouwing ontbreekt") en dus niet langer weggegooid.
      `escaleren`  → blijft escaleren (de tool heeft hier geen oordeel; `claims_db` verbiedt dat zo'n
                     bevinding de score beweegt), mét de bewijs-aantekening.

    Geeft de bevindingen terug waarvoor het bewijs `ambigu` was — grondstof voor de gat-oogst.
    """
    index = _index(ledger)
    merken = eigen_merken(db or {})
    if not merken:
        log.warning("geen scan-pagina's in de claims-database — geen eigen merk af te leiden; "
                    "elke claim geldt daarmee als niet-onderbouwd")
    ambigu: list[dict] = []
    for b in bevindingen:
        if b.get("stoplicht") in _BEWIJS_IRRELEVANT:
            b["onderbouwing"] = NIET_VAN_TOEPASSING
            b["onderbouwing_reden"] = "verboden claim — bewijs maakt hem niet toelaatbaar"
            continue
        uitslag = bewijs_voor(b, index, merken)
        b["onderbouwing"] = uitslag["onderbouwing"]
        b["onderbouwing_reden"] = uitslag["reden"]
        b["onderbouwing_records"] = [str(r.get("id") or "") for r in uitslag["records"]]
        if uitslag["onderbouwing"] == AMBIGU:
            ambigu.append(b)
        if uitslag["onderbouwing"] != ONDERBOUWD and b.get("stoplicht") == "green":
            b["stoplicht"] = "orange"                # de gedragsverandering: geen stil groen meer
            b["onderbouwing_verhoogd"] = True
    return ambigu


# ── Bewijs vastleggen (het schrijfpad) ──────────────────────────────────────────────────────────────
# Zonder dit pad kan een oranje bevinding nooit meer sluiten en leert de mens de tool te negeren.
# Eén Kroniek-record per vastgelegde onderbouwing: append-only, met bron én letterlijk citaat, zodat
# een latere lezer kan controleren waaróm iets als onderbouwd geldt. Compliance-gated in de dispatch.

SKILL = "claims_substantiatie"


def leg_bewijs_vast(ledger, *, claim: str, bron: str, citaat: str, merk: str,
                    door: str = "compliance") -> dict:
    """Schrijf één bevestigd bewijsrecord voor een eigen claim. Geeft het record terug.

    De query krijgt de vorm `<merk> — <claim>`, dezelfde sleutel-vorm die `claim_evidence` gebruikt
    (`evidence_records`), zodat handmatig en machinaal vastgelegd bewijs door één opzoeklaag gevonden
    worden. `door` gaat mee als rol-id: wie het bewijs vaststelde is onderdeel van het bewijs."""
    claim, bron, citaat = (claim or "").strip(), (bron or "").strip(), (citaat or "").strip()
    if not claim:
        raise ValueError("claim is verplicht")
    if not bron:
        raise ValueError("bron (URL of vindplaats) is verplicht")
    if len(citaat) < 20:
        raise ValueError("citaat is verplicht en moet letterlijk zijn (minimaal 20 tekens)")
    merk = (merk or "").strip() or "eigen site"
    return ledger.record(role_id=door, skill=SKILL, query=f"{merk} — {claim}",
                         source=bron, status="bevestigd", result_ref=citaat[:500],
                         meta={"claim": claim, "subject": merk, "vastgelegd_door": door})


def vastgelegd(ledger, limiet: int = 10) -> list[dict]:
    """De laatst vastgelegde onderbouwingen (nieuwste eerst) — zodat het scherm kan tonen hoe vol het
    register ís. Een leeg register is de eerlijkste verklaring voor een muur van oranje."""
    try:
        rijen = [r for r in ledger.all_records() if r.get("skill") == SKILL]
    except Exception:                                # noqa: BLE001 — weergave mag nooit breken
        return []
    return sorted(rijen, key=lambda r: r.get("ts", 0), reverse=True)[:limiet]
