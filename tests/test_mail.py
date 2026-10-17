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
    mail._VENSTER.clear()                                  # het standaardvenster is per proces
    yield
    mail._VENSTER.clear()


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
    """Een EXPLICIETE run (één weekmail-ronde) telt zichzelf, los van het tijdvenster."""
    _env(monkeypatch, MAIL_MAX_PER_RUN="3")
    run = mail.nieuwe_run()
    uit = [mail.verstuur(f"p{i}@nooch.earth", "Week 42", "x", verzend=True, data_dir=str(tmp_path),
                         run=run, smtp_cls=NepSMTP)["status"] for i in range(10)]
    assert uit == ["sent"] * 3 + ["refused"] * 7 and len(NepSMTP.gezien) == 3 and run.aantal == 3
    # een nieuwe run begint opnieuw te tellen
    assert mail.verstuur("p@nooch.earth", "T", "x", verzend=True, data_dir=str(tmp_path),
                         run=mail.nieuwe_run(), smtp_cls=NepSMTP)["status"] == "sent"


def test_ook_dry_runs_tellen_mee_voor_de_limiet(tmp_path, monkeypatch):
    _env(monkeypatch, MAIL_MAX_PER_RUN="2")
    s = [mail.verstuur("p@nooch.earth", "T", "x", data_dir=str(tmp_path))["status"] for _ in range(3)]
    assert s == ["dry-run", "dry-run", "refused"]


# ── het tijdvenster (17 oktober 2026) ────────────────────────────────────────────────────────

class Klok:
    def __init__(self, t=1_800_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


def test_zonder_eigen_run_hooguit_de_limiet_per_uur(tmp_path, monkeypatch):
    """Na 3 mails dicht; binnen het uur blijft hij dicht; een (gesimuleerd) uur later weer open."""
    _env(monkeypatch, MAIL_MAX_PER_RUN="3")
    klok = Klok()
    monkeypatch.setattr(mail, "_nu", klok)

    def stuur():
        return mail.verstuur("p@nooch.earth", "T", "x", verzend=True, data_dir=str(tmp_path),
                             smtp_cls=NepSMTP)

    assert [stuur()["status"] for _ in range(3)] == ["sent"] * 3
    dicht = stuur()
    assert dicht["status"] == "refused" and "per 60 minutes" in dicht["reden"]
    klok.t += 3599                                                            # nét binnen het uur
    assert stuur()["status"] == "refused"
    klok.t += 2                                                               # ruim een uur na de eerste
    assert stuur()["status"] == "sent"
    assert len(NepSMTP.gezien) == 4


def test_het_venster_glijdt_mee(tmp_path, monkeypatch):
    _env(monkeypatch, MAIL_MAX_PER_RUN="2")
    klok = Klok()
    monkeypatch.setattr(mail, "_nu", klok)
    st = lambda: mail.verstuur("p@nooch.earth", "T", "x", data_dir=str(tmp_path))["status"]   # noqa: E731
    assert st() == "dry-run"                       # t = 0
    klok.t += 1800
    assert st() == "dry-run"                       # t = 30 min
    assert st() == "refused"
    klok.t += 1801                                 # t = 60 min + 1 s: de eerste valt eruit, de tweede niet
    assert st() == "dry-run" and st() == "refused"


def test_een_expliciete_run_negeert_een_vol_venster(tmp_path, monkeypatch):
    _env(monkeypatch, MAIL_MAX_PER_RUN="1")
    assert mail.verstuur("p@nooch.earth", "T", "x", data_dir=str(tmp_path))["status"] == "dry-run"
    assert mail.verstuur("p@nooch.earth", "T", "x", data_dir=str(tmp_path))["status"] == "refused"
    run = mail.nieuwe_run(limiet=2)
    assert [mail.verstuur("p@nooch.earth", "T", "x", data_dir=str(tmp_path), run=run)["status"]
            for _ in range(3)] == ["dry-run", "dry-run", "refused"]


# ── dry-runs opruimen ─────────────────────────────────────────────────────────────────────────

def test_dry_runs_ouder_dan_14_dagen_gaan_weg_bij_de_volgende_dry_run(tmp_path, monkeypatch):
    _env(monkeypatch)
    klok = Klok()
    monkeypatch.setattr(mail, "_nu", klok)
    map_ = tmp_path / "mail_dryrun"
    map_.mkdir()
    dag = 86400
    bestanden = {"oud.eml": 15 * dag, "net-te-oud.eml": 14 * dag + 60, "jong.eml": 13 * dag + 12 * 3600,
                 "oud-maar-geen-eml.txt": 30 * dag}
    for naam, leeftijd in bestanden.items():
        (map_ / naam).write_text("x")
        os.utime(map_ / naam, (klok.t - leeftijd, klok.t - leeftijd))
    uit = mail.verstuur("p@nooch.earth", "T", "x", data_dir=str(tmp_path))
    over = sorted(os.listdir(map_))
    assert "oud.eml" not in over and "net-te-oud.eml" not in over
    assert "jong.eml" in over and "oud-maar-geen-eml.txt" in over
    assert os.path.basename(uit["pad"]) in over                              # de nieuwe staat er wel


def test_opruimen_breekt_een_dry_run_nooit(tmp_path, monkeypatch):
    _env(monkeypatch)
    monkeypatch.setattr(mail.os, "scandir", lambda p: (_ for _ in ()).throw(PermissionError("nee")))
    assert mail.verstuur("p@nooch.earth", "T", "x", data_dir=str(tmp_path))["status"] == "dry-run"


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


# ── alleen IPv4, en TLS op de hostnaam (17 oktober 2026) ─────────────────────────────────────
# Aanleiding: de server verbond via IPv6 met de relay; Google kende alleen het IPv4-adres en
# weigerde met 550. Geen echt netwerk in deze tests: getaddrinfo, create_connection en TLS zijn nep.

import socket  # noqa: E402


def test_de_standaard_verbinding_is_de_ipv4_klasse():
    assert mail.verstuur.__kwdefaults__["smtp_cls"] is mail._SMTPv4
    assert issubclass(mail._SMTPv4, smtplib.SMTP)


def test_a_de_verbinding_vraagt_alleen_ipv4_adressen(monkeypatch):
    gevraagd, verbonden = [], []

    def nep_getaddrinfo(host, port, family=0, type=0, *a, **k):
        gevraagd.append((host, port, family, type))
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.10", port))]

    monkeypatch.setattr(mail.socket, "getaddrinfo", nep_getaddrinfo)
    monkeypatch.setattr(mail.socket, "create_connection",
                        lambda adres, timeout=None, bron=None: verbonden.append(adres) or "SOCK")
    s = mail._SMTPv4(local_hostname="test")                                        # zonder host: maakt nog geen verbinding
    assert s._get_socket("smtp-relay.gmail.com", 587, 30) == "SOCK"
    assert gevraagd == [("smtp-relay.gmail.com", 587, socket.AF_INET, socket.SOCK_STREAM)]
    assert verbonden == [("192.0.2.10", 587)]


def test_a_volgende_ipv4_adres_als_het_eerste_faalt_en_nooit_ipv6(monkeypatch):
    monkeypatch.setattr(mail.socket, "getaddrinfo", lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.1", 587)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.2", 587))])
    pogingen = []

    def nep(adres, timeout=None, bron=None):
        pogingen.append(adres)
        if adres[0] == "192.0.2.1":
            raise OSError("onbereikbaar")
        return "SOCK"

    monkeypatch.setattr(mail.socket, "create_connection", nep)
    assert mail._SMTPv4(local_hostname="test")._get_socket("smtp-relay.gmail.com", 587, 30) == "SOCK"
    assert pogingen == [("192.0.2.1", 587), ("192.0.2.2", 587)]
    monkeypatch.setattr(mail.socket, "getaddrinfo", lambda *a, **k: [])
    with pytest.raises(OSError):
        mail._SMTPv4(local_hostname="test")._get_socket("smtp-relay.gmail.com", 587, 30)


def test_b_tls_controleert_het_certificaat_op_de_hostnaam_niet_op_het_ip(monkeypatch):
    """`connect()` met de HOSTNAAM; de socket is nep. `starttls()` moet die hostnaam als
    `server_hostname` aan het TLS-context geven."""
    class NepSock:
        def makefile(self, *a, **k):
            import io
            return io.BytesIO(b"220 smtp-relay.gmail.com ESMTP ready\r\n")

        def sendall(self, *a):
            pass

        def close(self):
            pass

    class NepContext:
        gezien = None

        def wrap_socket(self, sock, server_hostname=None):
            NepContext.gezien = server_hostname
            return sock

    monkeypatch.setattr(mail._SMTPv4, "_get_socket", lambda self, h, p, t: NepSock())
    s = mail._SMTPv4(local_hostname="test")
    code, _ = s.connect("smtp-relay.gmail.com", 587)
    assert code == 220 and s._host == "smtp-relay.gmail.com"
    s.esmtp_features = {"starttls": ""}
    s.does_esmtp = True
    s.ehlo_resp = b"smtp-relay.gmail.com"                     # alsof EHLO al gebeurd is
    monkeypatch.setattr(s, "docmd", lambda *a, **k: (220, b"go ahead"))
    s.starttls(context=NepContext())
    assert NepContext.gezien == "smtp-relay.gmail.com"


def test_b_verstuur_geeft_de_hostnaam_door_niet_een_ip(tmp_path, monkeypatch):
    _env(monkeypatch)
    mail.verstuur("stefan@nooch.earth", "T", "x", verzend=True, data_dir=str(tmp_path), smtp_cls=NepSMTP)
    assert NepSMTP.gezien[0]["host"] == "smtp-relay.gmail.com"
    assert NepSMTP.gezien[0]["tls_context"].check_hostname


def test_c_een_weigering_met_550_komt_als_code_in_de_log_en_niet_als_tekst(tmp_path, monkeypatch):
    _env(monkeypatch)
    NepSMTP.fout = smtplib.SMTPSenderRefused(
        550, b"5.7.1 Invalid credentials for relay [2a01:4f8:c010:8974::1]. The IP address you've "
             b"registered doesn't match", "village@nooch.earth")
    uit = mail.verstuur("stefan@nooch.earth", "Village mail test", "Hallo geheim", verzend=True,
                        data_dir=str(tmp_path), smtp_cls=NepSMTP)
    assert uit == {"status": "failed", "reden": "SMTPSenderRefused 550"}
    (regel,) = _audit(str(tmp_path))
    assert regel["event"] == "mail_failed"
    assert regel["fout"] == "SMTPSenderRefused" and regel["smtp_code"] == 550
    assert set(regel) == {"event", "by", "aan", "onderwerp", "at", "reden", "fout", "smtp_code"}
    tekst = json.dumps(regel)
    for verboden in ("Invalid credentials", "2a01", "registered", "geheim", "village@nooch.earth"):
        assert verboden not in tekst


def test_c_een_fout_zonder_smtp_code_logt_klasse_en_geen_code(tmp_path, monkeypatch):
    _env(monkeypatch)
    NepSMTP.fout = OSError("Network is unreachable: 2a01:4f8:c010:8974::1")
    mail.verstuur("stefan@nooch.earth", "T", "x", verzend=True, data_dir=str(tmp_path), smtp_cls=NepSMTP)
    (regel,) = _audit(str(tmp_path))
    assert regel["fout"] == "OSError" and regel["smtp_code"] is None and "2a01" not in json.dumps(regel)


def test_geen_netwerk_bij_een_dry_run_ook_niet_voor_de_eigen_hostnaam(tmp_path, monkeypatch):
    """Zonder domein vroeg `make_msgid` de eigen hostnaam op via DNS (seconden, en netwerk in een
    test). Een dry-run — met of zonder config — mag geen enkele netwerkfunctie aanroepen."""
    def geen_netwerk(*a, **k):
        raise AssertionError("netwerk aangeroepen")
    for naam in ("getfqdn", "gethostname", "gethostbyaddr", "getaddrinfo", "create_connection"):
        monkeypatch.setattr(mail.socket, naam, geen_netwerk)
    assert mail.verstuur("p@nooch.earth", "T", "x", data_dir=str(tmp_path))["status"] == "dry-run"
    _env(monkeypatch)
    assert mail.verstuur("p@nooch.earth", "T", "x", data_dir=str(tmp_path))["status"] == "dry-run"
