"""Zaad voor de eerste wiki-pagina's — uit wat er al ligt, niets erbij verzonnen.

Twee soorten, allebei uit een bestaande bron:

| pagina        | bron                                   | eigenaar               |
|---------------|----------------------------------------|------------------------|
| materiaal     | `data_bom.NOOCH_SCHOEN_BOM` (stuklijst)| de rol die de schoen maakt |
| claim         | `config/claims_database.json` werklijst| compliance             |

**Wat dit NIET doet.** Er wordt geen duurzaamheidsproza geschreven en geen feit geconstrueerd dat
de bron niet geeft. Een materiaal-pagina zegt in welke onderdelen het materiaal zit en welke keuzes
nog openstaan; méér weet de stuklijst niet. Een claim-pagina krijgt alleen een FEIT als er een
geldig certificaat tegenover staat — staat dat er niet, dan zegt de pagina dat, en dat is precies
de wachtlijst die `cert_register` al bijhoudt. Een pagina vol ongegronde feiten zou het hele punt
van deze laag omkeren.

**Fail-closed.** Bestaat de eigenaar-rol niet in dit dorp (de compliance-rol leeft bijvoorbeeld niet
in elke dataset), dan wordt die hélft overgeslagen mét reden — er wordt nooit een pagina op een
willekeurige andere rol gezet. **Idempotent:** een pagina met dezelfde titel bij dezelfde eigenaar
wordt overgeslagen, nooit overschreven; wat de eigenaar sinds het zaaien heeft aangepast blijft
staan.
"""
from __future__ import annotations

import json
import os

from nooch_village import cert_register, wiki

BRON_STUKLIJST = "stuklijst van de Nooch-schoen (founder-input)"


# ── materiaal-pagina's ──────────────────────────────────────────────────────

def _materiaalnaam(ruw: str) -> tuple[str, bool]:
    """(naam, onzeker). Een '(?)' achter een materiaal is een aantekening over ZEKERHEID, geen deel
    van de naam — 'BIOREL (?)' en 'BIOREL' zijn hetzelfde materiaal, waarvan er één nog gecheckt
    moet worden. Zonder deze splitsing krijg je twee pagina's voor één materiaal."""
    naam = " ".join((ruw or "").split())
    if naam.endswith("(?)"):
        return naam[:-3].strip(), True
    return naam, False


def materiaal_paginas(bom_tekst: str) -> list[dict]:
    """Eén pagina per materiaal uit de stuklijst: waar het in zit, en wat er nog open staat.

    De parse komt uit `compositie.ontleed_bom` — dezelfde als de belofte-graaf gebruikt, zodat er
    geen tweede lezing van dezelfde stuklijst ontstaat.

    Groeperen gebeurt hoofdletter-ongevoelig: 'Cotton thread' en 'Cotton Thread' zijn één materiaal.
    Dat is geen interpretatie maar noodzaak — twee pagina's met dezelfde titel lossen in de wiki
    bewust NIET op als link, dus die zouden allebei onbereikbaar zijn."""
    from nooch_village.compositie import ontleed_bom

    per_materiaal: dict[str, list] = {}
    spelling: dict[str, str] = {}
    onzeker: dict[str, set] = {}
    for c in ontleed_bom(bom_tekst, bron=BRON_STUKLIJST):
        naam, twijfel = _materiaalnaam(c.realisatie)
        if not naam:
            continue
        sleutel = naam.lower()
        per_materiaal.setdefault(sleutel, []).append(c)
        spelling.setdefault(sleutel, naam)
        if twijfel:
            onzeker.setdefault(sleutel, set()).add(c.naam)

    uit = []
    for sleutel, delen in sorted(per_materiaal.items()):
        materiaal = spelling[sleutel]
        regels = [f"Uit de {BRON_STUKLIJST}.", "", "## Gebruikt in"]
        for c in sorted(delen, key=lambda x: x.naam):
            regels.append(f"- {c.naam}")
        open_punten = []
        for c in sorted(delen, key=lambda x: x.naam):
            if c.naam in onzeker.get(sleutel, set()):
                open_punten.append(f"- {c.naam}: materiaal nog onzeker — in de stuklijst genoteerd "
                                   f"als “{c.realisatie}”")
            if c.alternatieven:
                open_punten.append(f"- {c.naam}: alternatief in beeld — "
                                   + ", ".join(c.alternatieven))
            elif c.opmerking:
                open_punten.append(f"- {c.naam}: {c.opmerking}")
        if open_punten:
            regels += ["", "## Nog open", *open_punten]
        regels += ["", "Wat dit materiaal aantoonbaar wél of niet is, hoort als feit op deze "
                   "pagina te staan, met een certificaat of Kroniek-record als grond."]
        uit.append({"titel": materiaal, "body": "\n".join(regels), "feiten": []})
    return uit


# ── claim-pagina's ──────────────────────────────────────────────────────────

_OORDEEL_TEKST = {
    "red": "rood — verboden, nooit gebruiken",
    "orange": "oranje — risico, alleen met genoemd bewijs",
    "green": "groen — veilig voor Nooch",
    "escaleren": "escaleren — geen harde bron; compliance beoordeelt, de tool niet",
}


def claims_db(pad: str | None = None) -> dict:
    """De claims-database (curated content in `config/`). Fail-closed via `claims_db.load_seed`:
    liever een zichtbare fout dan een zaad zonder claims."""
    from nooch_village import claims_db as cdb
    return cdb.load_seed(pad)


def claim_paginas(db: dict, ledger=None, *, vandaag: str = "") -> list[dict]:
    """Eén pagina per claim uit de werklijst: het oordeel, de herformulering en de onderbouwing.

    De onderbouwing is geen mening maar een vergelijking: `cert_register` zegt of er een geldig
    certificaat tegenover staat. Zo ja → één feit met dat certificaat als grond. Zo nee → géén
    feit, maar een regel die zegt wat er ontbreekt."""
    meta = db.get("meta") or {}
    versie = str(meta.get("versie") or "")
    certs = cert_register.certs_uit_kroniek(ledger) if ledger is not None else []

    uit = []
    for rij in db.get("werklijst") or []:
        claim = " ".join(str(rij.get("claim") or "").split())
        if not claim:
            continue
        oordeel = str(rij.get("oordeel") or "")
        regels = [f"**Oordeel:** {_OORDEEL_TEKST.get(oordeel, oordeel or 'onbekend')}."]
        if rij.get("herformulering"):
            regels.append(f"**Herformulering:** {rij['herformulering']}")
        if rij.get("status"):
            regels.append(f"**Status:** {rij['status']}")
        regels.append(f"**Bron van het oordeel:** Nooch claims-database{' v' + versie if versie else ''} "
                      f"(beheer: compliance).")

        feiten = []
        status = cert_register.status_voor(claim, certs, vandaag=vandaag)
        if status["status"] == "onderbouwd" and (status.get("cert") or {}).get("_record_id"):
            feiten.append(wiki.maak_feit(f"Onderbouwd: {claim}", soort="cert",
                                         ref=str(status["cert"]["_record_id"])))
        else:
            # Geen certificaat = geen feit. De pagina zégt dat er iets ontbreekt in plaats van een
            # ongegronde bewering te dragen; dit is dezelfde wachtlijst als in cert_register.
            regels.append(f"**Nog niet onderbouwd:** {status['reden']}.")
            regels.append(f"**Wat er nodig is:** {cert_register.opdracht(status)}")
        uit.append({"titel": claim[:200], "body": "\n".join(regels),
                    "feiten": [f for f in feiten if f]})
    return uit


# ── zaaien ──────────────────────────────────────────────────────────────────

def _bestaat(store, eigenaar: str, titel: str) -> bool:
    doel = " ".join((titel or "").split()).lower()
    return any(" ".join((a.title or "").split()).lower() == doel
               for a in store.list(eigenaar, wiki.PAGINA_KIND, include_archived=True))


def zaai(store, records, *, paginas: list[dict], eigenaar: str, soort: str,
         apply: bool = False, actor_id: str = "") -> list[dict]:
    """Zet één set pagina's bij één eigenaar. Geeft een rapportregel per pagina.

    `apply=False` (default) schrijft niets — dan is dit een dry-run die precies laat zien wat er
    zou gebeuren. Zonder de eigenaar-rol gebeurt er niets: fail-closed, met de reden erbij."""
    if records is not None and records.get(eigenaar) is None:
        return [{"soort": soort, "eigenaar": eigenaar, "titel": "—", "actie": "overgeslagen",
                 "reden": f"rol '{eigenaar}' bestaat niet in dit dorp"}]
    rapport = []
    for p in paginas:
        if _bestaat(store, eigenaar, p["titel"]):
            rapport.append({"soort": soort, "eigenaar": eigenaar, "titel": p["titel"],
                            "actie": "bestaat al", "reden": "niet overschreven"})
            continue
        if not apply:
            rapport.append({"soort": soort, "eigenaar": eigenaar, "titel": p["titel"],
                            "actie": "zou aanmaken", "reden": f"{len(p.get('feiten') or [])} feit(en)"})
            continue
        a = store.add(eigenaar, wiki.PAGINA_KIND, title=p["titel"], body=p["body"],
                      meta={"feiten": p.get("feiten") or []},
                      actor_id=actor_id, actor_type="person",
                      governance_ref=f"role:{eigenaar}", change_note="zaad uit bestaande bron")
        rapport.append({"soort": soort, "eigenaar": eigenaar, "titel": p["titel"],
                        "actie": "aangemaakt" if a else "mislukt",
                        "reden": (a.id if a else "store weigerde")})
    return rapport


def zaai_alles(store, records, ledger=None, *, eigenaar_materiaal: str, eigenaar_claims: str,
               apply: bool = False, actor_id: str = "", vandaag: str = "") -> list[dict]:
    """Beide sets in één keer. De helft waarvan de eigenaar-rol ontbreekt, wordt overgeslagen —
    de andere helft gaat gewoon door."""
    from nooch_village.data_bom import NOOCH_SCHOEN_BOM

    rapport = zaai(store, records, paginas=materiaal_paginas(NOOCH_SCHOEN_BOM),
                   eigenaar=eigenaar_materiaal, soort="materiaal", apply=apply, actor_id=actor_id)
    try:
        db = claims_db()
    except Exception as e:                      # noqa: BLE001 — nette regel i.p.v. een halve run
        rapport.append({"soort": "claim", "eigenaar": eigenaar_claims, "titel": "—",
                        "actie": "overgeslagen", "reden": f"claims-database onleesbaar: {e}"})
        return rapport
    rapport += zaai(store, records, paginas=claim_paginas(db, ledger, vandaag=vandaag),
                    eigenaar=eigenaar_claims, soort="claim", apply=apply, actor_id=actor_id)
    return rapport


def rapport_tekst(rapport: list[dict]) -> str:
    """Het rapport als tabel voor de CLI — altijd tonen vóór er iets geschreven wordt."""
    if not rapport:
        return "(niets te zaaien)"
    breed = max(len(r["titel"]) for r in rapport)
    regels = [f"{'soort':<10} {'actie':<14} {'pagina':<{breed}}  reden"]
    for r in rapport:
        regels.append(f"{r['soort']:<10} {r['actie']:<14} {r['titel']:<{breed}}  {r['reden']}")
    tel: dict[str, int] = {}
    for r in rapport:
        tel[r["actie"]] = tel.get(r["actie"], 0) + 1
    regels.append("")
    regels.append(" · ".join(f"{k}: {v}" for k, v in sorted(tel.items())))
    return "\n".join(regels)
