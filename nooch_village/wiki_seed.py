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

from nooch_village import artefacts
from nooch_village import cert_register, wiki

BRON_STUKLIJST = "bill of materials of the Nooch shoe (founder input)"


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
        regels = [f"From the {BRON_STUKLIJST}.", "", "## Used in"]
        for c in sorted(delen, key=lambda x: x.naam):
            regels.append(f"- {c.naam}")
        open_punten = []
        for c in sorted(delen, key=lambda x: x.naam):
            if c.naam in onzeker.get(sleutel, set()):
                open_punten.append(f"- {c.naam}: material not yet certain — noted in the bill of "
                                   f"materials as “{c.realisatie}”")
            if c.alternatieven:
                open_punten.append(f"- {c.naam}: alternative under consideration — "
                                   + ", ".join(c.alternatieven))
            elif c.opmerking:
                open_punten.append(f"- {c.naam}: {c.opmerking}")
        # CO2 & WATER: de plek, geen getal (1 oktober 2026). De stuklijst kent geen milieucijfers,
        # dus hier staat alleen WAAR ze horen en in welke vorm. De zin beweert bewust niet dat het
        # getal ontbreekt: die tekst blijft staan als de eigenaar het feit toevoegt, en zou dan
        # liegen. Of het er is, toont het BOM-scherm — afgeleid bij het lezen.
        #
        # DE KOPPEN ZIJN ENGELS (1 oktober 2026), dezelfde termen als `wiki.SJABLONEN`: wat de app
        # als vaste vorm aanlevert is systeemoutput, en die is Engels. Zie docs/CONVENTIES.md.
        regels += ["", "## CO2 & Water",
                   "As a fact with a value (CO2e per kg, water per kg), grounded in the supplier "
                   "TDS or another source. The BOM screen calculates with these values."]
        if open_punten:
            regels += ["", "## Open items", *open_punten]
        regels += ["", "What this material demonstrably is or is not belongs on this page as a "
                   "fact, grounded in a certificate or a Chronicle record."]
        uit.append({"titel": materiaal, "body": "\n".join(regels), "feiten": []})
    return uit


# ── claim-pagina's ──────────────────────────────────────────────────────────

_OORDEEL_TEKST = {
    "red": "red — forbidden, never use",
    "orange": "orange — risk, only with the evidence named",
    "green": "green — safe for Nooch",
    "escaleren": "escalate — no hard source; compliance judges, not the tool",
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
        regels = [f"**Verdict:** {_OORDEEL_TEKST.get(oordeel, oordeel or 'unknown')}."]
        if rij.get("herformulering"):
            regels.append(f"**Rewording:** {rij['herformulering']}")
        if rij.get("status"):
            regels.append(f"**Status:** {rij['status']}")
        regels.append(f"**Source of the verdict:** Nooch claims database{' v' + versie if versie else ''} "
                      f"(maintained by compliance).")

        feiten = []
        status = cert_register.status_voor(claim, certs, vandaag=vandaag)
        if status["status"] == "onderbouwd" and (status.get("cert") or {}).get("_record_id"):
            feiten.append(wiki.maak_feit(f"Substantiated: {claim}", soort="cert",
                                         ref=str(status["cert"]["_record_id"])))
        else:
            # Geen certificaat = geen feit. De pagina zégt dat er iets ontbreekt in plaats van een
            # ongegronde bewering te dragen; dit is dezelfde wachtlijst als in cert_register.
            # De LABELS zijn hier Engels; `reden` en `opdracht` komen uit `cert_register` en zijn
            # daar nog Nederlands (taalschuld buiten dit bestand, zie de scan van 2 oktober 2026).
            regels.append(f"**Not yet substantiated:** {status['reden']}.")
            regels.append(f"**What is needed:** {cert_register.opdracht(status)}")
        uit.append({"titel": claim[:200], "body": "\n".join(regels),
                    "feiten": [f for f in feiten if f]})
    return uit


# ── leverancier-pagina's ─────────────────────────────────────────────────────

BRON_CERTREGISTER = "certificates registered in the Chronicle"


def leverancier_paginas(ledger, *, vandaag: str = "") -> list[dict]:
    """Eén pagina per leverancier uit de certificaten in de Kroniek: welk materiaal, en welk feit
    daarover gegrond is.

    De bron is dezelfde `cert_register.certs_uit_kroniek` als de claim-pagina's gebruiken — geen
    tweede lezing van het certificatenregister. Een cert zonder leverancier-naam levert geen
    pagina: er is dan niets om de pagina op te noemen, en een pagina "Onbekend" zou latere certs
    zonder naam stilzwijgend bij elkaar vegen.

    Groeperen gebeurt hoofdletter- en spatie-ongevoelig, dezelfde reden als bij `materiaal_paginas`:
    twee pagina's met dezelfde titel lossen als [[link]] bewust niet op, dus die zouden allebei
    onbereikbaar zijn.

    **Een verlopen (of ongedateerd) certificaat levert geen feit.** Zelfde principe als bij claims:
    een goedkeuring mag zijn bewijs niet overleven. De pagina zelf blijft gewoon bestaan — de
    leverancier is nog steeds een leverancier — met een open punt dat zegt wat er moet gebeuren."""
    certs = cert_register.certs_uit_kroniek(ledger) if ledger is not None else []

    per_leverancier: dict[str, list] = {}
    spelling: dict[str, str] = {}
    for c in certs:
        naam = " ".join(str(c.get("leverancier") or "").split())
        if not naam:
            continue
        sleutel = naam.lower()
        per_leverancier.setdefault(sleutel, []).append(c)
        spelling.setdefault(sleutel, naam)

    uit = []
    for sleutel, cs in sorted(per_leverancier.items()):
        leverancier = spelling[sleutel]
        materialen = sorted({" ".join(str(c.get("materiaal") or "").split())
                             for c in cs if c.get("materiaal")})
        regels = [f"Supplier from the {BRON_CERTREGISTER}."]
        if materialen:
            regels += ["", "## Material"]
            regels += [f"- {m}" for m in materialen]

        feiten = []
        open_punten = []
        for c in sorted(cs, key=lambda x: str(x.get("feit") or "")):
            feit_tekst = str(c.get("feit") or "").strip()
            if not feit_tekst:
                continue
            verval = cert_register.verlopen(c, vandaag=vandaag)
            if verval or verval is None:
                reden = "expired" if verval else "has no readable expiry date"
                open_punten.append(f"- {feit_tekst}: certificate {reden} — renew the certificate "
                                   f"with {leverancier} before this fact is grounded again")
            elif c.get("_record_id"):
                feiten.append(wiki.maak_feit(feit_tekst, soort="cert", ref=str(c["_record_id"])))

        # PRIJSAFSPRAAK HOORT HIER en niet op de materiaalpagina: twee leveranciers van hetzelfde
        # materiaal kunnen verschillend prijzen. Zelfde regel als bij CO2 & water: de plek, geen
        # bewering over of het getal er al is.
        regels += ["", "## Price agreement",
                   "As a fact with a value (cost price per kg), grounded in the quote or the "
                   "contract. The BOM screen calculates with this value."]
        if open_punten:
            regels += ["", "## Open items", *open_punten]
        uit.append({"titel": leverancier, "body": "\n".join(regels),
                    "feiten": [f for f in feiten if f]})
    return uit


# ── zaaien ──────────────────────────────────────────────────────────────────

def _bestaat(store, eigenaar: str, titel: str) -> bool:
    """Staat deze pagina er al, óf is hij er met opzet niet meer?

    TWEE VRAGEN, één antwoord, en de tweede is nieuw (27 september 2026). De archief-check dekte
    archiveren; een HARD verwijderd artefact laat geen rij achter, dus zag deze functie een lege
    plek en zaaide `zaai()` gewoon opnieuw. `is_gewist_bij` leest het changelog: was de laatste
    actie op (eigenaar, titel) een verwijdering, dan hoort hier niets terug te groeien.

    ALLEEN DE SEEDER WORDT TEGENGEHOUDEN. Een mens die via `artefact_add` bewust een pagina met
    die titel maakt, komt hier niet langs — en zijn `add` maakt de plek daarna vanzelf weer
    levend, want `is_gewist` kijkt naar de LÁÁTSTE actie."""
    doel = artefacts.norm_titel(titel)
    if any(artefacts.norm_titel(a.title) == doel
           for a in store.list(eigenaar, wiki.PAGINA_KIND, include_archived=True)):
        return True
    return artefacts.is_gewist_bij(store, eigenaar, titel)


def zaai(store, records, *, paginas: list[dict], eigenaar: str, soort: str,
         apply: bool = False, actor_id: str = "") -> list[dict]:
    """Zet één set pagina's bij één eigenaar. Geeft een rapportregel per pagina.

    `apply=False` (default) schrijft niets — dan is dit een dry-run die precies laat zien wat er
    zou gebeuren. Zonder de eigenaar-rol gebeurt er niets: fail-closed, met de reden erbij.

    GEARCHIVEERD IS OOK GEEN EIGENAAR. De poort stond op `records.get(eigenaar) is None`, en een
    archief-record bestaat nog gewoon — dus die check zei ja voor een rol die uit het dorp weg is,
    en de pagina's waren aangemaakt op een plek die niemand opent. Stil op de verkeerde plek is
    erger dan zichtbaar overgeslagen."""
    if records is not None:
        rec = records.get(eigenaar)
        reden = ""
        if rec is None:
            reden = f"rol '{eigenaar}' bestaat niet in dit dorp"
        elif getattr(rec, "archived", False):
            reden = f"rol '{eigenaar}' is gearchiveerd — pagina's daar ziet niemand"
        if reden:
            return [{"soort": soort, "eigenaar": eigenaar, "titel": "—",
                     "actie": "overgeslagen", "reden": reden}]
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
               eigenaar_leverancier: str = "", apply: bool = False, actor_id: str = "",
               vandaag: str = "") -> list[dict]:
    """Alle sets in één keer. De helft (of het derde) waarvan de eigenaar-rol ontbreekt, wordt
    overgeslagen — de rest gaat gewoon door.

    `eigenaar_leverancier` is optioneel; zonder waarde wordt die stap helemaal overgeslagen (geen
    rapportregel) — niet elk dorp heeft de leverancier-pagina's al ingericht, en dat is geen fout."""
    from nooch_village.data_bom import NOOCH_SCHOEN_BOM

    rapport = zaai(store, records, paginas=materiaal_paginas(NOOCH_SCHOEN_BOM),
                   eigenaar=eigenaar_materiaal, soort="materiaal", apply=apply, actor_id=actor_id)
    if eigenaar_leverancier:
        rapport += zaai(store, records, paginas=leverancier_paginas(ledger, vandaag=vandaag),
                        eigenaar=eigenaar_leverancier, soort="leverancier", apply=apply,
                        actor_id=actor_id)
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
