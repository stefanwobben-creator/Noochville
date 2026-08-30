"""Een bewaker die dezelfde faalmodus deelt als wat hij bewaakt, is geen bewaker.

ER WAS AL EEN PULS-WATCHDOG, en hij werkte: `Facilitator._run_pulse_watchdog` escaleert een rol die
op de vorige dag geen hartslag naliet. Maar hij wordt aangeroepen vanuit `tick()` — de hartslag
zelf. Toen de afslanking van 28 aug 2026 de facilitator slapend legde, viel de tick weg, en daarmee
de bewaker. Het dorp stond drie dagen stil zonder één signaal. Bij het herstel vuurde hij meteen
wél: hij was nooit stuk, hij kon alleen niet draaien.

WAAROP DEZE GRONDT, en waarop nadrukkelijk niet:
  WEL   `timekeeper_last_day.json` (een bestand, geen event) + logactiviteit
  NIET  `pulse_completed` / `last_pulse.json` / `pulse_history.jsonl` — die hangen alle drie aan
        `website_watcher`, en die kán slapen. Gemeten op 30 aug 2026: de bel luidde, er werden 659
        regels werk gedaan, en `last_pulse` bleef op 27 augustus staan.
"""
from __future__ import annotations

import json
from datetime import datetime

import pytest

from nooch_village import puls_wacht as pw

_ECHTE = pw.log_activiteit_vandaag        # vóór de autouse-stub hieronder


def _bel(tmp_path, dag: str):
    (tmp_path / "timekeeper_last_day.json").write_text(json.dumps({"last_day": dag}))


VANDAAG = datetime(2026, 8, 30, 9, 0)
VROEG = datetime(2026, 8, 30, 3, 0)


@pytest.fixture(autouse=True)
def _geen_journal(monkeypatch):
    """De log-check uit, tenzij een test hem expliciet zet.

    NIET met een verzonnen unit-naam: `journalctl -u <onbekend>` antwoordt exact hetzelfde als een
    unit die vandaag stil was, dus die truc maakte de uitkomst afhankelijk van of de machine
    systemd heeft. Lokaal (macOS) slaagde hij, in de CI (Ubuntu) niet — en dat verschil is precies
    de bug die `_unit_bestaat` nu afvangt."""
    monkeypatch.setattr(pw, "log_activiteit_vandaag", lambda unit=pw.UNIT: None)


def test_bel_van_vandaag_geluid_is_ok(tmp_path):
    _bel(tmp_path, "2026-08-30")
    uit = pw.controleer(str(tmp_path), {}, nu=VANDAAG)
    assert uit["ok"] and uit["redenen"] == []


def test_bel_van_vandaag_gemist_is_alarm(tmp_path):
    """Precies het geval van 28-30 augustus: de bel bleef op de 27e staan."""
    _bel(tmp_path, "2026-08-27")
    uit = pw.controleer(str(tmp_path), {}, nu=VANDAAG)
    assert not uit["ok"]
    assert "2026-08-27" in uit["redenen"][0]


def test_vóór_het_vuurmoment_is_stilte_normaal(tmp_path):
    """Om 03:00 is een ontbrekende bel van vandaag geen storing maar de normale toestand. Zonder dat
    onderscheid gaat de bewaker elke nacht af — en een bewaker die vals alarm geeft wordt genegeerd."""
    _bel(tmp_path, "2026-08-29")
    uit = pw.controleer(str(tmp_path), {}, nu=VROEG)
    assert uit["ok"] and uit["verwacht"] is False


def test_de_vuurtijd_en_tijdzone_komen_uit_de_config(tmp_path):
    _bel(tmp_path, "2026-08-29")
    laat = {"dag_begint_time": "23:00"}
    assert pw.controleer(str(tmp_path), laat, nu=VANDAAG)["ok"] is True
    vroeg = {"dag_begint_time": "01:00"}
    assert pw.controleer(str(tmp_path), vroeg, nu=VANDAAG)["ok"] is False


def test_nooit_geluid_is_ook_alarm(tmp_path):
    uit = pw.controleer(str(tmp_path), {}, nu=VANDAAG)
    assert not uit["ok"] and "nooit" in uit["redenen"][0]


# ── Waarop hij NIET grondt ─────────────────────────────────────────────────

def test_hij_kijkt_niet_naar_pulse_completed_of_last_pulse():
    """DE KERN. Die drie hangen aan `website_watcher`, en die kan slapen — dan zou de bewaker een
    storing melden die er niet is, of zwijgen omdat zijn eigen bron mee wegviel."""
    import inspect
    bron = inspect.getsource(pw)
    for verboden in ("pulse_completed", "last_pulse", "pulse_history"):
        assert verboden not in bron.split('"""', 2)[2], verboden


def test_geen_journalctl_is_geen_storing(tmp_path, monkeypatch):
    """None is geen 'nee': op een machine zonder journal weten we het niet, en dan hoort de bewaker
    daarover te zwijgen in plaats van iets te melden dat hij niet kan zien."""
    _bel(tmp_path, "2026-08-30")
    monkeypatch.setattr(pw, "log_activiteit_vandaag", lambda unit=pw.UNIT: None)
    uit = pw.controleer(str(tmp_path), {}, nu=VANDAAG)
    assert uit["ok"] and uit["activiteit"] is None


def test_een_stille_daemon_is_wel_alarm(tmp_path, monkeypatch):
    _bel(tmp_path, "2026-08-30")
    monkeypatch.setattr(pw, "log_activiteit_vandaag", lambda unit=pw.UNIT: False)
    uit = pw.controleer(str(tmp_path), {}, nu=VANDAAG)
    assert not uit["ok"] and "niets gelogd" in uit["redenen"][0]


# ── Fail-loud: drie kanalen ────────────────────────────────────────────────

def test_het_alarm_gaat_naar_drie_kanalen(tmp_path, capsys):
    """Als er één stilvalt is dat precies het geval waarvoor dit bestaat."""
    from nooch_village.notifications import NotifStore
    _bel(tmp_path, "2026-08-27")
    uit = pw.controleer(str(tmp_path), {}, nu=VANDAAG)
    pw.alarm(str(tmp_path), uit)
    assert (tmp_path / pw.ALARM_LOG).exists()                       # 1. plat bestand
    assert "PULS-ALARM" in (tmp_path / pw.ALARM_LOG).read_text()
    items = NotifStore(str(tmp_path / "notifications.json")).all()  # 2. founder-inbox
    assert items and "PULS-ALARM" in (items[0].get("tekst") or "")
    assert "PULS-ALARM" in capsys.readouterr().out                  # 3. stdout → cron/systemd


def test_het_alarm_valt_niet_om_op_een_kapotte_store(tmp_path, capsys, monkeypatch):
    """Het schreeuwen zelf mag nooit stuk gaan aan een van zijn kanalen."""
    monkeypatch.setattr("nooch_village.notifications.NotifStore.add",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("stuk")))
    pw.alarm(str(tmp_path), {"redenen": ["iets"]})
    assert "PULS-ALARM" in capsys.readouterr().out


def test_een_onbekende_unit_is_geen_stilte(monkeypatch):
    """DOOR DE CI GEVONDEN. `journalctl -u <onbekend>` antwoordt '-- No entries --' — exact hetzelfde
    als een unit die vandaag stil was. Zonder de bestaat-check leest een tikfout in de unit-naam als
    'de daemon ligt stil', en dan huilt de bewaker elke ochtend wolf om zijn eigen configuratie.

    Lokaal (macOS, géén journalctl) slaagde de oude test; in de CI (Ubuntu, wél journalctl) niet.
    Dat verschil wás de bug. `_ECHTE` is de functie zoals hij vóór de fixture-stub bestond."""
    monkeypatch.setattr(pw, "_unit_bestaat", lambda unit: False)
    assert _ECHTE("bestaat-niet") is None
