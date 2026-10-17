"""Uitgaande mail, stap 1 (17 oktober 2026, besluit Stefan): `mail.verstuur` via de Workspace-relay,
STARTTLS zonder inlog, dry-run als standaard, faalt gesloten zonder config, een limiet per run, en een
auditregel per verzonden mail (aan, onderwerp, tijd — geen inhoud). Er gaat in deze tests nooit iets
echt de deur uit: de SMTP-klasse is een nep die alleen bijhoudt wat er gebeurde."""
from __future__ import annotations

import email
import json
import os
import smtplib
import sys

import pytest

from nooch_village import mail

CFG = {"MAIL_SMTP_HOST": "smtp-relay.gmail.com", "MAIL_SMTP_PORT": "587",
       "MAIL_FROM": "village@nooch.earth", "MAIL_FROM_NAME": "Village"}


class NepSMTP:
    """Doet alsof hij een SMTP-server is. `fout` = exceptie bij versturen; `tls=False` = geen STARTTLS."""
    gezien: list = []
    fout: Exception | None = None
    tls = True

    def __init__(self, host, poort, local_hostname=None, timeout=None):
        self.log = {"host": host, "poort": poort, "helo": local_hostname, "stappen": []}
        NepSMTP.gezien.append(self.log)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.log["stappen"].append("quit")

    def ehlo(self):
        self.log["stappen"].append("ehlo")

    def has_extn(self, naam):
        return naam == "starttls" and NepSMTP.tls

    def starttls(self, context=None):
        self.log["stappen"].append("starttls")
        self.log["tls_context"] = context

    def login(self, *a):                                  # mag NOOIT aangeroepen worden
        self.log["stappen"].append("login")

    def send_message(self, m):
        if NepSMTP.fout:
            raise NepSMTP.fout
        self.log["stappen"].append("send")
        self.log["bericht"] = m


@pytest.fixture(autouse=True)
def schoon(monkeypatch):
    for k in list(os.environ):
        if k.startswith("MAIL_"):
            monkeypatch.delenv(k)
    NepSMTP.gezien = []
    NepSMTP.fout = None
    NepSMTP.tls = True
    mail.nieuwe_run()
    yield


def _env(monkeypatch, **extra):
    for k, v in {**CFG, **extra}.items():
        monkeypatch.setenv(k, v)


def _audit(dd):
    pad = os.path.join(dd, "system_log.jsonl")
    if not os.path.exists(pad):
        return []
    return [json.loads(r) for r in open(pad, encoding="utf-8")]


# ── dry-run is de standaard ───────────────────────────────────────────────────────────────────

def test_zonder_verzend_gaat_er_niets_uit_en_staat_het_bericht_in_een_bestand(tmp_path, monkeypatch):
    _env(monkeypatch)
    uit = mail.verstuur("stefan@nooch.earth", "Week 42", "Hallo", "<p>Hallo</p>",
                        data_dir=str(tmp_path), smtp_cls=NepSMTP)
    assert uit["status"] == "dry-run" and uit["ingesteld"] is True
    assert NepSMTP.gezien == []                                               # geen verbinding
    m = email.message_from_bytes(open(uit["pad"], "rb").read())
    assert m["To"] == "stefan@nooch.earth" and m["Subject"] == "Week 42"
    assert m["From"] == "Village <village@nooch.earth>"
    assert os.path.dirname(uit["pad"]).endswith("mail_dryrun")
    assert _audit(str(tmp_path)) == []                                        # dry-run is geen verzending


def test_dry_run_werkt_ook_zonder_config(tmp_path):
    uit = mail.verstuur("stefan@nooch.earth", "Test", "x", data_dir=str(tmp_path), smtp_cls=NepSMTP)
    assert uit["status"] == "dry-run" and uit["ingesteld"] is False and NepSMTP.gezien == []


# ── echt verzenden ────────────────────────────────────────────────────────────────────────────

def test_verzenden_via_de_relay_met_starttls_en_zonder_inlog(tmp_path, monkeypatch):
    _env(monkeypatch)
    uit = mail.verstuur("stefan@nooch.earth", "Week 42", "Hallo", "<p>Hallo</p>",
                        verzend=True, data_dir=str(tmp_path), smtp_cls=NepSMTP)
    assert uit["status"] == "sent"
    (log,) = NepSMTP.gezien
    assert (log["host"], log["poort"], log["helo"]) == ("smtp-relay.gmail.com", 587, "village.nooch.earth")
    assert log["stappen"] == ["ehlo", "starttls", "ehlo", "send", "quit"]      # geen "login"
    assert log["tls_context"] is not None and log["tls_context"].check_hostname
    m = log["bericht"]
    assert m["From"] == "Village <village@nooch.earth>" and m["To"] == "stefan@nooch.earth"
    assert m.get_body(("plain",)).get_content().strip() == "Hallo"
    assert m.get_body(("html",)).get_content().strip() == "<p>Hallo</p>"
    assert m["Message-ID"].endswith("@nooch.earth>")


def test_zonder_starttls_wordt_er_niet_verzonden(tmp_path, monkeypatch):
    _env(monkeypatch)
    NepSMTP.tls = False
    uit = mail.verstuur("stefan@nooch.earth", "Test", "geheim", verzend=True,
                        data_dir=str(tmp_path), smtp_cls=NepSMTP)
    assert uit["status"] == "failed" and "send" not in NepSMTP.gezien[0]["stappen"]


@pytest.mark.parametrize("ontbreekt", ["MAIL_SMTP_HOST", "MAIL_FROM"])
def test_zonder_config_weigert_echt_verzenden(tmp_path, monkeypatch, ontbreekt):
    _env(monkeypatch)
    monkeypatch.delenv(ontbreekt)
    uit = mail.verstuur("stefan@nooch.earth", "Test", "x", verzend=True, data_dir=str(tmp_path),
                        smtp_cls=NepSMTP)
    assert uit["status"] == "refused" and "not configured" in uit["reden"]
    assert NepSMTP.gezien == [] and _audit(str(tmp_path)) == []


def test_een_ongeldige_afzender_telt_als_niet_ingesteld(tmp_path, monkeypatch):
    _env(monkeypatch, MAIL_FROM="geen adres")
    assert mail.verstuur("stefan@nooch.earth", "T", "x", verzend=True, data_dir=str(tmp_path),
                         smtp_cls=NepSMTP)["status"] == "refused"


@pytest.mark.parametrize("fout", [
    smtplib.SMTPRecipientsRefused({"stefan@nooch.earth": (550, b"5.1.1 stefan@nooch.earth unknown")}),
    smtplib.SMTPDataError(554, b"rejected: text 'Hallo geheim' contains stefan@nooch.earth"),
    smtplib.SMTPServerDisconnected("Connection unexpectedly closed: stefan@nooch.earth"),
    OSError("Network is unreachable"),
])
def test_een_fout_geeft_alleen_de_soort_terug_nooit_gegevens(tmp_path, monkeypatch, fout):
    _env(monkeypatch)
    NepSMTP.fout = fout
    uit = mail.verstuur("stefan@nooch.earth", "Week 42", "Hallo geheim", verzend=True,
                        data_dir=str(tmp_path), smtp_cls=NepSMTP)
    assert uit["status"] == "failed"
    tekst = json.dumps(uit) + json.dumps(_audit(str(tmp_path)))
    assert "geheim" not in tekst and "unknown" not in tekst and "unexpectedly" not in tekst
    assert "stefan@nooch.earth" not in uit["reden"]
    assert uit["reden"].startswith(type(fout).__name__)
    (regel,) = _audit(str(tmp_path))
    assert regel["event"] == "mail_failed" and regel["reden"] == uit["reden"]


# ── registratie ───────────────────────────────────────────────────────────────────────────────

def test_elke_verzonden_mail_staat_in_de_audit_trail_zonder_inhoud(tmp_path, monkeypatch):
    _env(monkeypatch)
    mail.verstuur("stefan@nooch.earth", "Week 42", "Persoonlijke acties: X, Y", "<p>X</p>",
                  verzend=True, data_dir=str(tmp_path), smtp_cls=NepSMTP)
    (regel,) = _audit(str(tmp_path))
    assert set(regel) == {"event", "by", "aan", "onderwerp", "at"}
    assert (regel["event"], regel["aan"], regel["onderwerp"]) == ("mail_sent", "stefan@nooch.earth", "Week 42")
    assert "Persoonlijke" not in json.dumps(regel)


# ── invoer en limiet ──────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("aan", ["", "geen-adres", "a@b", "a@b.nl, c@d.nl", "a@b.nl\nBcc: x@y.nl",
                                 "Stefan <stefan@nooch.earth>", "a b@c.nl", "a@b.nl;c@d.nl"])
def test_alleen_een_enkel_kaal_adres(tmp_path, monkeypatch, aan):
    _env(monkeypatch)
    uit = mail.verstuur(aan, "T", "x", verzend=True, data_dir=str(tmp_path), smtp_cls=NepSMTP)
    assert uit == {"status": "refused", "reden": "invalid address"} and NepSMTP.gezien == []


def test_een_regeleinde_in_het_onderwerp_kan_geen_header_toevoegen(tmp_path, monkeypatch):
    _env(monkeypatch)
    mail.verstuur("stefan@nooch.earth", "Hallo\r\nBcc: x@y.nl", "x", verzend=True,
                  data_dir=str(tmp_path), smtp_cls=NepSMTP)
    m = NepSMTP.gezien[0]["bericht"]
    assert m["Bcc"] is None and m["Subject"] == "Hallo Bcc: x@y.nl"


def test_de_limiet_per_run_stopt_een_lus(tmp_path, monkeypatch):
    _env(monkeypatch, MAIL_MAX_PER_RUN="3")
    run = mail.nieuwe_run()
    uit = [mail.verstuur(f"p{i}@nooch.earth", "Week 42", "x", verzend=True, data_dir=str(tmp_path),
                         smtp_cls=NepSMTP)["status"] for i in range(10)]
    assert uit == ["sent"] * 3 + ["refused"] * 7 and len(NepSMTP.gezien) == 3 and run.aantal == 3
    # een nieuwe run begint opnieuw te tellen
    mail.nieuwe_run()
    assert mail.verstuur("p@nooch.earth", "T", "x", verzend=True, data_dir=str(tmp_path),
                         smtp_cls=NepSMTP)["status"] == "sent"


def test_ook_dry_runs_tellen_mee_voor_de_limiet(tmp_path, monkeypatch):
    _env(monkeypatch, MAIL_MAX_PER_RUN="2")
    mail.nieuwe_run()
    s = [mail.verstuur("p@nooch.earth", "T", "x", data_dir=str(tmp_path))["status"] for _ in range(3)]
    assert s == ["dry-run", "dry-run", "refused"]


# ── het commando ──────────────────────────────────────────────────────────────────────────────

def _cli(monkeypatch, tmp_path, *argv):
    from nooch_village import cli, config
    echt = config.load_context

    def _ctx(_base):
        c = echt(_base)
        c.data_dir = str(tmp_path)
        return c
    monkeypatch.setattr(config, "load_context", _ctx)
    monkeypatch.setattr(mail.smtplib, "SMTP", NepSMTP)
    monkeypatch.setattr(mail.verstuur, "__kwdefaults__", {**mail.verstuur.__kwdefaults__, "smtp_cls": NepSMTP})
    monkeypatch.setattr(sys, "argv", ["village", "mail_test", *argv])
    with pytest.raises(SystemExit) as e:
        cli.main()
    return e.value.code


def test_mail_test_toont_in_dry_run_wat_er_zou_gaan(tmp_path, monkeypatch, capsys):
    _env(monkeypatch)
    assert _cli(monkeypatch, tmp_path) == 0
    uit = capsys.readouterr().out
    assert "DRY-RUN" in uit and "stefan@nooch.earth" in uit and "smtp-relay.gmail.com" in uit
    assert "configured" in uit and NepSMTP.gezien == []
    assert os.listdir(os.path.join(tmp_path, "mail_dryrun"))


def test_mail_test_send_stuurt_een_testmail_naar_stefan(tmp_path, monkeypatch, capsys):
    _env(monkeypatch)
    assert _cli(monkeypatch, tmp_path, "--send") == 0
    (log,) = NepSMTP.gezien
    assert log["bericht"]["To"] == "stefan@nooch.earth" and "login" not in log["stappen"]
    assert "status=sent" in capsys.readouterr().out


def test_mail_test_send_zonder_config_faalt_gesloten(tmp_path, monkeypatch, capsys):
    assert _cli(monkeypatch, tmp_path, "--send") == 1
    assert NepSMTP.gezien == [] and "NOT configured" in capsys.readouterr().out
