"""Uitgaande mail (stap 1, 17 oktober 2026, besluit Stefan).

Eén functie, `verstuur(aan, onderwerp, tekst, html=None)`, via de SMTP-relay van Google Workspace
(`smtp-relay.gmail.com:587`, STARTTLS, GEEN inlog — de relay laat het server-IP toe). SPF en DKIM
van nooch.earth staan al op Google, dus er is geen DNS-wijziging nodig.

DRIE VANGNETTEN, en elk faalt gesloten:

1. **Dry-run is de standaard.** Zonder `verzend=True` gaat er niets de deur uit: het bericht wordt als
   `.eml` in `data/mail_dryrun/` gezet. Echt verzenden is altijd een expliciete keuze van de aanroeper.
2. **Geen configuratie = geen verzending.** Host en afzender komen uit `.env` (`MAIL_SMTP_HOST`,
   `MAIL_FROM`); ontbreekt er één, dan weigert `verzend=True`. Er is bewust geen standaard-host: een
   server die nog niet is ingericht hoort niets te versturen.
3. **Een limiet** (`MAIL_MAX_PER_RUN`, standaard 20). Een fout in een lus die per persoon mailt stopt
   dan na een handvol, niet na honderd. Elke poging telt, ook een dry-run. Geeft de aanroeper een
   eigen `MailRun` mee, dan telt die run; anders geldt een TIJDVENSTER: hooguit `MAIL_MAX_PER_RUN`
   per 60 minuten voor het hele proces (de cockpit en de daemon draaien weken, en een teller over
   die hele levensduur zou na twintig mails voorgoed dichtzitten).

Dry-run-bestanden ouder dan 14 dagen worden bij elke dry-run opgeruimd.

GEEN GEGEVENS IN EEN FOUT. Een SMTP-fout wordt gevangen; terug komt alleen de foutSOORT (en een SMTP-
code), nooit de melding zelf — die bevat bij smtplib vaak het adres of een stuk van het bericht.

Elke verzonden (en elke mislukte) mail komt als één regel in de bestaande audit-trail,
`system_log.jsonl`: aan, onderwerp, tijd. Geen inhoud, geen nieuwe store.

Een mail is een KENNISGEVING met een link terug (beveiligingsgrens van de human inbox): nooit een
approve-knop. Dat bewaakt deze module niet; dat is een regel voor wie de tekst opstelt.
"""
from __future__ import annotations

import json
import os
import re
import itertools
import smtplib
import ssl
import threading
import time
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

#: Eén adres, zonder naam, komma, puntkomma of witruimte (dus ook geen header-injectie).
_ADRES_RE = re.compile(r"^[^@\s<>,;\"']+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
_STANDAARD_LIMIET = 20
_ONDERWERP_MAX = 200
_DRYRUN_MAP = "mail_dryrun"


class MailRun:
    """Telt de pogingen van één run (één commando, één daemon-taak). Boven `limiet` weigert hij."""

    def __init__(self, limiet: int | None = None):
        self.limiet = limiet if limiet is not None else _limiet_uit_env()
        self.aantal = 0


def nieuwe_run(limiet: int | None = None) -> MailRun:
    """Een run met een verse teller, om expliciet mee te geven (`verstuur(..., run=...)`): één
    weekmail-ronde, één overlegverslag. Zonder `run` geldt het tijdvenster hieronder."""
    return MailRun(limiet)


#: HET STANDAARDVENSTER (17 oktober 2026, besluit Stefan): wie geen eigen run meegeeft, valt onder
#: hooguit `MAIL_MAX_PER_RUN` pogingen per `VENSTER_SECONDEN`, glijdend, voor het hele proces.
VENSTER_SECONDEN = 3600
_VENSTER: list[float] = []
_VENSTER_SLOT = threading.Lock()                 # de cockpit is meerdradig


def _nu() -> float:
    return time.time()


def _venster_toelaten() -> tuple[bool, int]:
    """(mag het, limiet). Telt de poging mee als hij mag."""
    limiet = _limiet_uit_env()
    nu = _nu()
    with _VENSTER_SLOT:
        _VENSTER[:] = [t for t in _VENSTER if nu - t < VENSTER_SECONDEN]
        if len(_VENSTER) >= limiet:
            return False, limiet
        _VENSTER.append(nu)
        return True, limiet


_VOLGNR = itertools.count(1)                      # unieke bestandsnaam binnen dezelfde seconde

#: Dry-run-bestanden ouder dan dit gaan weg bij de volgende dry-run.
DRYRUN_BEWAAR_DAGEN = 14


def _ruim_dryruns_op(map_: str) -> int:
    """Haal `.eml`-bestanden ouder dan `DRYRUN_BEWAAR_DAGEN` weg. Goedkoop (één `scandir`) en
    fail-soft: opruimen mag een dry-run nooit breken. Geeft het aantal weggehaalde bestanden."""
    grens = _nu() - DRYRUN_BEWAAR_DAGEN * 86400
    weg = 0
    try:
        for e in os.scandir(map_):
            if e.is_file() and e.name.endswith(".eml") and e.stat().st_mtime < grens:
                try:
                    os.remove(e.path)
                    weg += 1
                except OSError:
                    pass
    except OSError:
        pass
    return weg


def _limiet_uit_env() -> int:
    try:
        n = int(os.environ.get("MAIL_MAX_PER_RUN", _STANDAARD_LIMIET))
    except ValueError:
        return _STANDAARD_LIMIET
    return max(0, n)


def instellingen() -> dict:
    """De mailconfiguratie uit de omgeving (`.env` via `config.load_context`). `ok` is alleen waar
    als host én afzender er zijn."""
    host = os.environ.get("MAIL_SMTP_HOST", "").strip()
    afzender = os.environ.get("MAIL_FROM", "").strip()
    try:
        poort = int(os.environ.get("MAIL_SMTP_PORT", "587"))
    except ValueError:
        poort = 0
    return {"host": host, "poort": poort, "afzender": afzender,
            "naam": os.environ.get("MAIL_FROM_NAME", "Village").strip() or "Village",
            "ok": bool(host and afzender and _ADRES_RE.match(afzender) and poort)}


def _bericht(aan: str, onderwerp: str, tekst: str, html: str | None, cfg: dict) -> EmailMessage:
    m = EmailMessage()
    m["From"] = formataddr((cfg["naam"], cfg["afzender"] or "village@localhost"))
    m["To"] = aan
    m["Subject"] = onderwerp
    m["Date"] = formatdate(localtime=True)
    m["Message-ID"] = make_msgid(domain=(cfg["afzender"].split("@")[-1] if cfg["afzender"] else None))
    m.set_content(tekst or "")
    if html:
        m.add_alternative(html, subtype="html")
    return m


def _audit(data_dir: str, event: str, aan: str, onderwerp: str, **extra) -> None:
    """Eén regel in de bestaande audit-trail. Fail-soft: een log mag een verzending niet breken."""
    try:
        with open(os.path.join(data_dir, "system_log.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"event": event, "by": "village", "aan": aan, "onderwerp": onderwerp,
                                "at": time.time(), **extra}, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _data_dir(data_dir: str | None) -> str:
    if data_dir:
        return data_dir
    from nooch_village.config import load_context
    from nooch_village.village import BASE_DIR
    return load_context(BASE_DIR).data_dir


def verstuur(aan: str, onderwerp: str, tekst: str, html: str | None = None, *,
             verzend: bool = False, data_dir: str | None = None, run: MailRun | None = None,
             smtp_cls=smtplib.SMTP) -> dict:
    """Verstuur één mail, of — standaard — schrijf hem als dry-run weg.

    Geeft `{"status": ..., ...}` terug, nooit een exceptie:
      - `dry-run` → `pad` naar het `.eml`-bestand;
      - `sent`    → `message_id`;
      - `refused` → `reden` (ongeldig adres/onderwerp, limiet, niet ingesteld);
      - `failed`  → `reden` = alleen de foutsoort (en SMTP-code), nooit de melding.
    Statussen, redenen en audit-events zijn Engels: systeemoutput (docs/CONVENTIES.md).
    """
    aan = (aan or "").strip()
    onderwerp = " ".join((onderwerp or "").split())[:_ONDERWERP_MAX]
    if not _ADRES_RE.match(aan):
        return {"status": "refused", "reden": "invalid address"}
    if not onderwerp:
        return {"status": "refused", "reden": "no subject"}
    if run is None:
        mag, limiet = _venster_toelaten()
        if not mag:
            return {"status": "refused",
                    "reden": f"limit of {limiet} mails per {VENSTER_SECONDEN // 60} minutes reached"}
    else:
        if run.aantal >= run.limiet:
            return {"status": "refused", "reden": f"limit of {run.limiet} mails per run reached"}
        run.aantal += 1

    cfg = instellingen()
    dd = _data_dir(data_dir)
    bericht = _bericht(aan, onderwerp, tekst, html, cfg)

    if not verzend:
        map_ = os.path.join(dd, _DRYRUN_MAP)
        os.makedirs(map_, exist_ok=True)
        _ruim_dryruns_op(map_)
        naam = (time.strftime("%Y%m%d-%H%M%S") + f"-{next(_VOLGNR):04d}-"
                + re.sub(r"[^a-z0-9]+", "-", aan.lower())[:40])
        pad = os.path.join(map_, naam + ".eml")
        with open(pad, "wb") as f:
            f.write(bytes(bericht))
        return {"status": "dry-run", "pad": pad, "ingesteld": cfg["ok"]}

    if not cfg["ok"]:
        return {"status": "refused", "reden": "mail is not configured (set MAIL_SMTP_HOST and MAIL_FROM in .env)"}
    try:
        with smtp_cls(cfg["host"], cfg["poort"], local_hostname="village.nooch.earth", timeout=30) as s:
            s.ehlo()
            if not s.has_extn("starttls"):
                raise smtplib.SMTPNotSupportedError("STARTTLS")
            s.starttls(context=ssl.create_default_context())
            s.ehlo()
            s.send_message(bericht)
    except Exception as e:                                  # noqa: BLE001 — nooit een traceback met gegevens
        reden = type(e).__name__
        if isinstance(e, smtplib.SMTPResponseException):
            reden += f" {e.smtp_code}"
        elif isinstance(e, smtplib.SMTPRecipientsRefused):
            reden += " " + ",".join(str(v[0]) for v in e.recipients.values())
        _audit(dd, "mail_failed", aan, onderwerp, reden=reden)
        return {"status": "failed", "reden": reden}
    _audit(dd, "mail_sent", aan, onderwerp)
    return {"status": "sent", "message_id": bericht["Message-ID"]}
