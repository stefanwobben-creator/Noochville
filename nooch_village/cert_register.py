"""Certificaten als extern bewijs — het register en de wachtlijst.

Waarom dit bestaat. De claim-pas kwam op NUL compliant uit, en terecht: elk 'bevestigd' record in
de Kroniek had als bron een eigen skill-run (`claims_check`, `escaleer`, `projectverzoek`). Een
claim onderbouwen met je eigen logboek is cirkelredenering, en die guard hoort te blijven staan.
Wat ontbrak is bewijs dat NIET uit onszelf komt.

Een certificaat is dat bewijs. Het draagt een feit dat iemand anders heeft vastgesteld, met een
uitgever, een datum en een vervaldatum. Daarom krijgt het een eigen herkomst:

    source = "external_certificate"

en alleen die herkomst (of een andere aantoonbaar externe bron) telt in de pas als onderbouwing.

Dit volgt de architectuurbeslissing in CLAUDE.md ("Certificaten in de village"): het gezag ligt bij
compliance, elk certificaat is één gestructureerd feit, `geldig_tot` is een HARD veld, en de
component-naar-cert-koppeling levert de founder — het dorp parseert en ontsluit, het weet niet wat
er intern in een schoen zit.

**Eerlijk degraderen.** Kan een veld niet gelezen worden, dan blijft het leeg en zegt het record
dat. Nooit een verzonnen vervaldatum en nooit een gereconstrueerd feit: een certificaat waarvan de
geldigheid geraden is, is geen bewijs maar een risico met een stempel erop.

**Een goedkeuring mag zijn bewijs niet overleven.** `geldig_tot` wordt bij ELKE toets opnieuw
vergeleken met vandaag; verloopt een certificaat, dan klapt de claim terug naar niet-onderbouwd.
Dat is een levende vergelijking, geen eenmalige stempel.
"""
from __future__ import annotations

import datetime
import logging
import os
import re

log = logging.getLogger("village.cert_register")

# De herkomst die telt. Bewust één vaste string: de pas vergelijkt hierop, en een tweede spelling
# ("extern_certificaat") zou stilletjes niet meetellen — dezelfde klasse als library/bibliotheek.
EXTERN = "external_certificate"

SKILL = "cert_evidence"

# Waar Stefan zijn certificaten neerlegt. Compliance-domein, naast de andere compliance-data.
MAP = "certificaten"

# De velden van één cert-record, uit de architectuurbeslissing in CLAUDE.md.
VELDEN = ("feit", "certificeert", "materiaal", "leverancier", "niveau", "instantie",
          "geldig_tot", "bron_pdf", "claims")

NIVEAUS = ("component", "eindproduct")

_DATUM = re.compile(r"(?:geldig\s*tot|valid\s*until|expiry|expires?|vervaldatum|valid\s*through)"
                    r"\D{0,20}(\d{4}-\d{2}-\d{2}|\d{2}[-/]\d{2}[-/]\d{4})", re.I)
_INSTANTIE = re.compile(r"(?:issued\s*by|uitgegeven\s*door|instantie|certifying\s*body|"
                        r"certification\s*body)\s*[:\-]?\s*(.{3,60})", re.I)
_LEVERANCIER = re.compile(r"(?:supplier|leverancier|manufacturer|producent)\s*[:\-]?\s*(.{3,60})", re.I)
_FEIT = re.compile(r"(?:feit|fact|claim|statement|certifies\s+that|verklaart\s+dat)\s*[:\-]?\s*"
                   r"(.{6,200})", re.I)
_MATERIAAL = re.compile(r"(?:materiaal|material)\s*[:\-]?\s*(.{2,60})", re.I)


def pad(data_dir: str) -> str:
    return os.path.join(data_dir, MAP)


def _datum(tekst: str) -> str:
    """De vervaldatum als ISO-datum, of "" als hij niet te lezen is. Nooit geraden."""
    m = _DATUM.search(tekst or "")
    if not m:
        return ""
    ruw = m.group(1)
    for vorm in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.datetime.strptime(ruw, vorm).strftime("%Y-%m-%d")
        except ValueError:
            continue
    log.warning("cert: vervaldatum %r niet te parsen — leeg gelaten", ruw)
    return ""


def _veld(pat: "re.Pattern[str]", tekst: str) -> str:
    m = pat.search(tekst or "")
    return " ".join(m.group(1).split())[:120] if m else ""


def lees_cert(tekst: str, *, bron_pdf: str = "") -> dict:
    """Lees één certificaat tot een gestructureerd feit. Ontbrekende velden blijven LEEG.

    Regel-gebaseerd, geen model: een geraden vervaldatum of een geherformuleerd feit zou
    confabulatie bij de bron zijn, en dat is erger dan een leeg veld. `ontbreekt` zegt precies wat
    er niet gelezen kon worden, zodat een mens het kan aanvullen in plaats van dat het wegvalt."""
    cert = {
        "feit":        _veld(_FEIT, tekst),
        "certificeert": _veld(_FEIT, tekst),
        "materiaal":   _veld(_MATERIAAL, tekst),
        "leverancier": _veld(_LEVERANCIER, tekst),
        "niveau":      "",
        "instantie":   _veld(_INSTANTIE, tekst),
        "geldig_tot":  _datum(tekst),
        "bron_pdf":    bron_pdf,
        "claims":      [],
    }
    for n in NIVEAUS:
        if re.search(rf"\b{n}\b", tekst or "", re.I):
            cert["niveau"] = n
            break
    cert["ontbreekt"] = [v for v in ("feit", "instantie", "geldig_tot") if not cert.get(v)]
    return cert


def verlopen(cert: dict, *, vandaag: str = "") -> bool | None:
    """Is dit certificaat verlopen? True/False, of None als de datum onbekend is.

    None is nadrukkelijk niet False: een certificaat zonder leesbare vervaldatum is geen geldig
    certificaat, want niemand kan zeggen tot wanneer het draagt."""
    tot = str(cert.get("geldig_tot") or "").strip()
    if not tot:
        return None
    nu = vandaag or datetime.date.today().isoformat()
    return tot < nu


def draagt(cert: dict, claim: str) -> bool:
    """Dekt dit certificaat deze claim? Alleen als de claim expliciet in `claims` staat.

    Bewust geen fuzzy match: welk Nooch-onderdeel welk materiaal bevat weet alleen de founder (zie
    CLAUDE.md). Een machine die dat raadt, koppelt vroeg of laat een cert aan een claim die het niet
    draagt — en dat is precies de fout die een certificaat hoort te voorkomen."""
    doel = " ".join((claim or "").lower().split())
    return any(doel == " ".join(str(c).lower().split()) for c in cert.get("claims") or [])


def naar_evidence(cert: dict, ledger, *, rol: str = "compliance") -> dict | None:
    """Schrijf het cert als extern bewijsrecord in de Kroniek. None als het niet mag.

    Weigert een cert zonder feit of zonder geldigheidsdatum: dan is er niets te dragen, of niet te
    zeggen tot wanneer. Fail-closed, want dit record is precies het ding dat later een 'compliant'
    rechtvaardigt."""
    if not str(cert.get("feit") or "").strip():
        log.warning("cert: geen leesbaar feit — geen bewijsrecord geschreven (%s)",
                    cert.get("bron_pdf") or "?")
        return None
    if verlopen(cert) is None:
        log.warning("cert: geen leesbare vervaldatum — geen bewijsrecord geschreven (%s)",
                    cert.get("bron_pdf") or "?")
        return None
    return ledger.record(
        role_id=rol, skill=SKILL, query=str(cert.get("feit"))[:200], source=EXTERN,
        status="bevestigd", result_ref=str(cert.get("bron_pdf") or "")[:200],
        meta={k: cert.get(k) for k in VELDEN})


# ── De wachtlijst ───────────────────────────────────────────────────────────

def certs_uit_kroniek(ledger) -> list[dict]:
    """De cert-records in de Kroniek, met hun meta terug als cert-dict."""
    uit = []
    for r in ledger.all_records():
        if r.get("source") != EXTERN or r.get("status") != "bevestigd":
            continue
        meta = dict(r.get("meta") or {})
        meta.setdefault("feit", r.get("query") or "")
        meta["_record_id"] = r.get("id")
        uit.append(meta)
    return uit


def status_voor(claim: str, certs: list[dict], *, vandaag: str = "") -> dict:
    """Onderbouwd of pending, en waarom. Dit is de levende check: `geldig_tot` wordt hier elke keer
    opnieuw vergeleken, zodat een goedkeuring zijn bewijs niet kan overleven."""
    kandidaten = [c for c in certs if draagt(c, claim)]
    if not kandidaten:
        return {"claim": claim, "status": "pending", "reden": "geen certificaat dekt deze claim",
                "cert": None}
    geldig = [c for c in kandidaten if verlopen(c, vandaag=vandaag) is False]
    if geldig:
        c = geldig[0]
        return {"claim": claim, "status": "onderbouwd",
                "reden": (f"{c.get('instantie') or 'certificaat'} — geldig tot "
                          f"{c.get('geldig_tot')}"),
                "cert": c}
    c = kandidaten[0]
    tot = c.get("geldig_tot") or "onbekend"
    return {"claim": claim, "status": "pending",
            "reden": f"het certificaat dekt deze claim maar is verlopen of ongedateerd ({tot})",
            "cert": c}


def wachtlijst(claims: list[str], ledger, *, vandaag: str = "") -> list[dict]:
    """Per claim: onderbouwd of pending. De pending-lijst is de opdracht aan de mens."""
    certs = certs_uit_kroniek(ledger)
    return [status_voor(c, certs, vandaag=vandaag) for c in claims]


def opdracht(rij: dict) -> str:
    """De pending-regel als concrete mens-taak, niet als statusmelding."""
    claim = rij.get("claim") or "?"
    cert = rij.get("cert") or {}
    lev = cert.get("leverancier") or "de leverancier"
    if cert:
        return (f"vernieuw het certificaat voor de claim “{claim}” bij {lev} — "
                f"{rij.get('reden')}")
    return (f"haal een certificaat op dat de claim “{claim}” draagt (uitgever, feit, vervaldatum) "
            f"en leg het in data/{MAP}/")
