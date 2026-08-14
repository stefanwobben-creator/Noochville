"""Van "is dit compliant?" naar een gegrond oordeel dat de founder kan bevestigen.

De drie claim-items die op 'Decisions for you' landden, waren LLM-geschreven escalaties zonder de
claim erin: *"De herziene claim en onderbouwing zijn klaar voor implementatie. Mag ik deze direct
live zetten?"* — zonder de tekst, zonder de clausule, zonder bewijs. Dat is precies de vraag die
een mens niet kan beantwoorden zonder zelf het werk over te doen.

Deze laag bouwt geen tweede pijplijn. Alles staat er al:

    claims_db.check_tekst        de termenlijst mét `bron` (A=EmpCo, B=ACM, C=interpretatie,
                                 D=Nooch-beleid) en `bron_detail` (recital/bijlage, letterlijk)
    claims_db `alternatief`      de voorgestelde vervangtekst, per term gecureerd
    claims_substantiatie         het bewijs uit de Kroniek: bevestigd / ambigu / ontbreekt
    claims_check.betekenis_van   de deterministische eerlijkheidsregels over wat de data NIET zegt

De enige toevoeging is het OORDEEL, en die is regel-gebaseerd:

    afwijzen           een rode term met een harde bron (A/B/D) en geen voorgestelde vervanging
    herformuleren      idem, mét de `alternatief` als voorgestelde nieuwe tekst
    compliant          ALLEEN met een bevestigd Kroniek-record én een clausule om het aan te hangen
    niet_te_beoordelen al het andere — dit is de eerlijke degradatie, geen zwak 'compliant'

**Geen oordeel zonder citaat.** `compliant` vereist bewijs én clausule; dat is de enige uitkomst
die een claim vrijgeeft, dus die drempel ligt het hoogst. Een lege scan (score 100, alle tellers 0)
is nooit een goedkeuring — dat is de bestaande lege-run-regel, hier hergebruikt in plaats van
nagebouwd. Bron C beslist de tool nooit zelf: dat staat zo in het toetsingskader van de database.

**De voorgestelde tekst is een VOORSTEL.** `alternatief` komt uit de database en is niet op deze
context getoetst; die waarschuwing staat al in `betekenis_van` en reist mee naar de kaart. De
founder bevestigt, past aan of verwerpt — het dorp zet niets live.
"""
from __future__ import annotations

import logging
import re

log = logging.getLogger("village.claim_oordeel")

COMPLIANT     = "compliant"
HERFORMULEREN = "herformuleren"
AFWIJZEN      = "afwijzen"
GEEN_OORDEEL  = "niet_te_beoordelen"

# Bronnen waarop de tool zelfstandig mag beslissen. C = interpretatie zonder harde bron; het
# toetsingskader van de database zegt letterlijk dat de tool die nooit beslist.
HARDE_BRONNEN = frozenset({"A", "B", "D"})

BRON_NAAM = {
    "A": "Richtlijn (EU) 2024/825 (EmpCo)",
    "B": "ACM Leidraad Duurzaamheidsclaims v2",
    "C": "interpretatie zonder harde bron",
    "D": "Nooch-beleid",
}

# Zinnen die een oordeel niet mag bevatten: ze suggereren een vrijgave die deze laag niet kan geven.
# Dezelfde familie guard als in claims_check — een te sterke string mét het gezag van compliance
# erachter is erger dan geen string.
_VERBODEN = re.compile(r"is compliant\b|is goedgekeurd|mag live|goedgekeurd door legal|"
                       r"juridisch akkoord|cleared for", re.I)


def _clausule(bevinding: dict) -> str:
    """De exacte regelgeving-clausule bij deze bevinding, of "" als hij er niet is."""
    bron = str(bevinding.get("bron") or "").strip().upper()
    detail = str(bevinding.get("bron_detail") or "").strip()
    if not bron or bron not in BRON_NAAM:
        return ""
    return f"{BRON_NAAM[bron]} — {detail}" if detail else BRON_NAAM[bron]


# Bewijs mag niet uit onszelf komen. Een Kroniek-record met als bron een eigen skill-run
# ('claims_check', 'escaleer', 'projectverzoek', 'tegenspraak') zegt dat wíj iets gedraaid hebben,
# niet dat een externe bron de claim draagt. Gezien in de eerste prod-dry-run: drie claims kregen
# 'compliant' op precies zulke records. Een claim onderbouwen met je eigen logboek is de mooiste
# vorm van cirkelredenering die er is.
EIGEN_RUNS = frozenset({"claims_check", "claims_site_scan", "escaleer", "projectverzoek",
                        "tegenspraak", "kroniek_interpret", "onderzoekspas", "claim_evidence"})


def externe_records(bewijs: dict, *, vandaag: str = "") -> list[dict]:
    """De bewijs-records die NIET uit een eigen skill-run komen ÉN nog geldig zijn.

    De geldigheid wordt hier ELKE keer opnieuw vergeleken, niet ooit één keer gestempeld: een
    goedkeuring mag zijn bewijs niet overleven. Verloopt het certificaat, dan valt de claim vanzelf
    terug naar niet-onderbouwd — zonder dat iemand daar een taak voor hoeft te onthouden."""
    from nooch_village import cert_register as cr

    uit = []
    for r in bewijs.get("records") or []:
        bron = str(r.get("source") or r.get("bron") or "").strip().lower()
        if not bron or bron in EIGEN_RUNS:
            continue
        if bron == cr.EXTERN:
            cert = dict(r.get("meta") or {})
            if cr.verlopen(cert, vandaag=vandaag) is not False:
                log.info("claim-oordeel: certificaat %s verlopen of ongedateerd (geldig_tot=%r) — "
                         "telt niet meer als onderbouwing", r.get("id"), cert.get("geldig_tot"))
                continue
        uit.append(r)
    return uit


def _bewijs_id(bewijs: dict) -> str:
    for r in bewijs.get("records") or []:
        rid = str(r.get("id") or r.get("record_id") or "")
        if rid:
            return rid
    return ""


def _guard(tekst: str) -> str:
    """Weiger een formulering die een vrijgave suggereert. Geeft "" als hij schoon is."""
    m = _VERBODEN.search(tekst or "")
    return m.group(0) if m else ""


def oordeel_voor(claim: str, *, db, ledger=None, merken=None) -> dict:
    """Het gegronde oordeel over één claim.

    Geeft: {claim, oordeel, clausule, bewijs_id, bewijs_reden, nieuwe_tekst, waarom, betekenis,
            bevindingen, gegrond}. `gegrond=False` betekent: dit is een bevinding, geen oordeel."""
    from nooch_village import claims_substantiatie as subst
    from nooch_village.skills_impl import claims_check

    claim = (claim or "").strip()
    uit = {"claim": claim, "oordeel": GEEN_OORDEEL, "clausule": "", "bewijs_id": "",
           "bewijs_reden": "", "nieuwe_tekst": "", "waarom": "", "betekenis": [],
           "bevindingen": [], "gegrond": False}
    if not claim:
        uit["waarom"] = "lege claim — niets te beoordelen"
        return uit

    uitslag = db if isinstance(db, dict) and "bevindingen" in db else None
    if uitslag is None:
        from nooch_village import claims_db
        uitslag = claims_db.check_tekst(claim, db)
    bevindingen = list(uitslag.get("bevindingen") or [])
    uit["bevindingen"] = bevindingen
    uit["betekenis"] = claims_check.betekenis_van(uitslag, claim)

    # GEEN relevantie-veto op `_raakt`. Overwogen na de eerste prod-dry-run en verworpen: die helper
    # is bewust RUIM ("bij twijfel géén melding"), want als waarschuwing kost een valse treffer
    # hooguit een overbodige voetnoot. Als veto keert die kostenverhouding om — 'gerecycled' (NL)
    # deelt geen woord met "recycled materials" (EN) en zou een correct oordeel wegduwen.
    #
    # Wat er in die dry-run echt misging zat bij de INVOER: er werden taak-omschrijvingen als claim
    # aangeboden ("Locate the Plant Based Treaty-logo …"). Een term die daar letterlijk in staat is
    # een terechte bevinding over die tekst; de tekst was alleen geen claim. Daarom bewaakt
    # `claims_uit` de invoer, en blijven de betekenis-regels hier staan als voetnoot op de kaart.

    index, mrk = [], set(merken or ())
    if ledger is not None:
        try:
            index = subst._index(ledger)
        except Exception as e:                        # noqa: BLE001 — geen bewijs ≠ compliant
            log.warning("claim-oordeel: Kroniek onleesbaar (%s) — geen bewijs beschikbaar", e)

    # 1. Een harde rode bevinding beslist. Geen bewijs kan een verbod opheffen: een verbod is geen
    #    bewijskwestie (dezelfde regel als in claims_substantiatie.pas_toe).
    for b in bevindingen:
        if str(b.get("stoplicht") or "") != "red":
            continue
        bron = str(b.get("bron") or "").upper()
        if bron not in HARDE_BRONNEN:
            continue
        clausule = _clausule(b)
        alternatief = str(b.get("alternatief") or "").strip()
        uit["clausule"] = clausule
        uit["waarom"] = (f"de term “{b.get('term')}” is verboden: {b.get('waarom') or '—'}")
        if alternatief:
            uit["oordeel"] = HERFORMULEREN
            uit["nieuwe_tekst"] = alternatief
        else:
            uit["oordeel"] = AFWIJZEN
        uit["gegrond"] = bool(clausule)
        if not clausule:
            uit["oordeel"] = GEEN_OORDEEL
            uit["waarom"] += " — maar de bron is niet te citeren, dus dit blijft een bevinding"
        return uit

    # 2. Oranje: hier telt bewijs wél. Onderbouwd → compliant, anders herformuleren of eerlijk niets.
    for b in bevindingen:
        if str(b.get("stoplicht") or "") != "orange":
            continue
        bewijs = subst.bewijs_voor(b, index, mrk) if index else {
            "onderbouwing": subst.ONTBREEKT, "records": [],
            "reden": "de Kroniek is niet geraadpleegd"}
        extern = externe_records(bewijs)
        uit["clausule"] = _clausule(b)
        uit["bewijs_reden"] = str(bewijs.get("reden") or "")
        uit["bewijs_id"] = _bewijs_id({"records": extern})
        if extern and bewijs.get("onderbouwing") == subst.ONDERBOUWD and uit["clausule"]:
            uit["oordeel"] = COMPLIANT
            uit["waarom"] = (f"de risico-term “{b.get('term')}” is toegestaan mits onderbouwd, en er "
                             f"ligt een bevestigd Kroniek-record")
            uit["gegrond"] = True
            return uit
        alternatief = str(b.get("alternatief") or "").strip()
        uit["nieuwe_tekst"] = alternatief
        ontbreekt = uit["bewijs_reden"] or "geen bevestigd record"
        if bewijs.get("onderbouwing") == subst.ONDERBOUWD and not extern:
            ontbreekt = (f"alleen records uit onze eigen skill-runs ({uit['bewijs_reden']}) — dat "
                         f"zegt dat wij iets draaiden, niet dat een externe bron de claim draagt")
        uit["waarom"] = (f"de risico-term “{b.get('term')}” mag alleen mét bewijs, en dat ontbreekt: "
                         f"{ontbreekt}")
        # Zelfde regel als in de rode tak: zonder citeerbare clausule is dit een bevinding, geen
        # oordeel. Anders zou een 'herformuleren' zonder wetsgrond als besluit op de kaart landen.
        uit["gegrond"] = bool(uit["clausule"])
        uit["oordeel"] = (HERFORMULEREN if (alternatief and uit["clausule"]) else GEEN_OORDEEL)
        return uit

    # 3. Escaleren (bron C) en alles wat overblijft: eerlijk geen oordeel. Een claim zonder gevlagde
    #    term is NIET compliant — dat is precies wat de betekenis-regels zeggen.
    esc = [b for b in bevindingen if str(b.get("stoplicht") or "") == "escaleren"]
    if esc:
        uit["clausule"] = _clausule(esc[0])
        uit["waarom"] = ("de database markeert dit als 'escaleren': geen harde bron, dus de tool "
                         "beslist niet — een mens beoordeelt")
        return uit
    uit["waarom"] = ("geen gevlagde term gevonden; dat is geen goedkeuring. Deze toets kijkt alleen "
                     "naar de termenlijst en zegt niets over de inhoud van de claim")
    return uit


def kaart(oordeel: dict) -> dict:
    """Wat er op de voorstel-kaart moet staan, in de volgorde waarin de founder het leest.

    De twee schermklachten zijn hier het ontwerp: de TEKST waarover hij beslist staat er (en bij
    herformuleren de voorgestelde nieuwe tekst inline), en de HERKOMST staat er (dat compliance de
    pas draaide, met clausule en bewijs-spoor). Zonder die twee is het een blind vinkje."""
    o = dict(oordeel or {})
    spoor = []
    if o.get("clausule"):
        spoor.append(f"clausule: {o['clausule']}")
    if o.get("bewijs_id"):
        spoor.append(f"Kroniek-record: {o['bewijs_id']}")
    if o.get("bewijs_reden"):
        spoor.append(f"bewijs: {o['bewijs_reden']}")
    for regel in o.get("betekenis") or []:
        spoor.append(f"let op: {regel}")
    tekst = " ".join([str(o.get("waarom") or ""), str(o.get("nieuwe_tekst") or "")])
    fout = _guard(tekst)
    if fout:
        # De guard van claims_check, hier op onze eigen uitvoer. Een oordeel dat een vrijgave
        # suggereert die deze laag niet kan geven, degradeert — het wordt niet stilletjes gepoetst.
        log.warning("claim-oordeel: verboden formulering %r — gedegradeerd naar bevinding", fout)
        o["oordeel"] = GEEN_OORDEEL
        o["gegrond"] = False
        spoor.append(f"gedegradeerd: de formulering bevatte “{fout}”, wat een vrijgave suggereert")
    return {"claim": o.get("claim", ""), "oordeel": o.get("oordeel", GEEN_OORDEEL),
            "nieuwe_tekst": o.get("nieuwe_tekst", ""), "waarom": o.get("waarom", ""),
            "gegrond": bool(o.get("gegrond")), "spoor": spoor,
            "door": "compliance (claims-pas)"}


# Waar een claim vandaan MAG komen. Een claim is een publieke uitspraak op onze site, geen zin uit
# een taakomschrijving. Zonder deze poort belandt "Locate the exact literal quote of …" als claim in
# een compliance-oordeel, en dan beoordeelt de pas onze eigen takenlijst.
_CLAIM_MARKERS = re.compile(r"Claim-scan|Onderbouw:|Beoordeel:|Vervang:|claim[- ]?tekst", re.I)
_TAAK_MARKERS = re.compile(r"^(locate|extract|record|check|flag|recognize|verify|onderzoek|"
                           r"controleer)\b", re.I)


def claims_uit(scope: str) -> list[str]:
    """De claim-teksten in deze project-scope, of niets als het geen claim-bron is."""
    if not _CLAIM_MARKERS.search(scope or ""):
        return []
    uit = []
    m = re.search(r"(?:Onderbouw|Beoordeel|Vervang):\s*(.+?)\s+—", scope)
    if m:
        uit.append(m.group(1))
    uit += re.findall(r"[\u201c\"']([^\u201d\"']{12,160})[\u201d\"']", scope)
    return [c.strip(" '\"") for c in uit
            if c.strip() and not _TAAK_MARKERS.search(c.strip())]


def dry_run(claims: list[str], *, data_dir: str) -> list[dict]:
    """Draai de pas over een lijst claims zonder iets te muteren."""
    import os
    from nooch_village import claims_db, claims_substantiatie
    from nooch_village.evidence_ledger import EvidenceLedger

    db = claims_db.load(data_dir=data_dir)
    ledger = EvidenceLedger(os.path.join(data_dir, "evidence_ledger.jsonl"))
    merken = claims_substantiatie.eigen_merken(db)
    uit = []
    for c in claims:
        o = oordeel_voor(c, db=db, ledger=ledger, merken=merken)
        uit.append({"oordeel": o, "kaart": kaart(o)})
    return uit
