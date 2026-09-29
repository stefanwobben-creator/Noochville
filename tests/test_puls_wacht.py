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


def _dm_teksten(st_of_dd, rol_of_persoon=None):
    """Alle DM-teksten in een dorp, of die van één rol/persoon.

    Sinds B2 (20 sept 2026) landt een melding als DM bij de mens in plaats van als rij in
    `NotifStore`. De routering — wie het krijgt — is ongewijzigd; alleen de plek is verhuisd."""
    from nooch_village import channels, signaal
    st = st_of_dd
    if isinstance(st_of_dd, str):
        st = signaal._MiniStores(st_of_dd)
    if rol_of_persoon is None:
        return [e.get("text") or "" for k in st.channels.bestaande()
                if channels.soort_van(k) == channels.DM for e in st.channels.trail(k)]
    wie, _ = signaal.ontvangers(st, "role", rol_of_persoon)
    if not wie:
        wie = [rol_of_persoon]
    return [e.get("text") or "" for p in wie for k in st.channels.kanalen_van(p)
            for e in st.channels.trail(k)]

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
    # EEN DORP IS NODIG OM TE KUNNEN BEZORGEN. `NotifStore.add` schreef vroeger een rij ongeacht
    # of de doelrol bestond; een DM moet een MENS vinden, en daarvoor zijn records en assignments
    # nodig. Dat is een echte consequentie van B2 en staat als bevinding in het nachtlog: draait
    # het alarm in een dorp waar de records onleesbaar zijn, dan blijven alleen het alarmbestand
    # en stdout over. Die twee zijn hier ook getoetst, en dat is precies waarom het er drie zijn.
    from nooch_village import cockpit2
    cockpit2._bootstrap(str(tmp_path))
    _bel(tmp_path, "2026-08-27")
    uit = pw.controleer(str(tmp_path), {}, nu=VANDAAG)
    pw.alarm(str(tmp_path), uit)
    assert (tmp_path / pw.ALARM_LOG).exists()                       # 1. plat bestand
    assert "PULS-ALARM" in (tmp_path / pw.ALARM_LOG).read_text()
    items = _dm_teksten(str(tmp_path))                              # 2. een DM bij de founder
    assert items and any("PULS-ALARM" in t for t in items)
    assert "PULS-ALARM" in capsys.readouterr().out                  # 3. stdout → cron/systemd


def test_het_alarm_valt_niet_om_op_een_kapotte_store(tmp_path, capsys, monkeypatch):
    """Het schreeuwen zelf mag nooit stuk gaan aan een van zijn kanalen."""
    monkeypatch.setattr("nooch_village.channels.ChannelStore.post",
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


# ── De wekelijkse uitgangen ─────────────────────────────────────────────────────────────────
#
# HET GAT DAT DEZE CHECK VEROORZAAKTE. De bewaker hierboven kijkt of de dagelijkse TIK afging,
# niet naar wat er ÍN die tik gebeurde. Een gezonde tik met een stilzwijgend overgeslagen weekmemo
# ziet er voor hem identiek uit aan een gezonde week — en zo had Stefan na twee weken nog nooit een
# weekmemo gezien: nul berichten in zijn DM-kanaal, ooit.
#
# WAT DIT NIET DOET: elke lege week een "niets te melden" sturen. Dat is de ruis die de send-gate
# in `weekmemo.ronde` juist vermijdt, en die gate blijft zoals hij is. Alleen ECHTE stilte alarmeert.
import os as _os
import time as _time


def _leg_vast(dd, bestand, dagen_geleden):
    """Doe alsof een wekelijkse uitgang zoveel dagen geleden zijn ronde vastlegde."""
    with open(_os.path.join(dd, bestand), "w", encoding="utf-8") as f:
        json.dump({"laatste_periode": "2026-W39",
                   "laatste_at": _time.time() - dagen_geleden * 86400,
                   "laatste_aantal": 0}, f)


def _namen():
    return [naam for naam, _b in pw._weekuitgangen()]


def test_de_twee_wekelijkse_uitgangen_worden_allebei_bewaakt():
    from nooch_village import noochie_memo, weekmemo
    bestanden = dict(pw._weekuitgangen())
    assert bestanden["weekmemo"] == weekmemo.STATE
    assert bestanden["noochie-memo"] == noochie_memo.STATE


def test_twee_stille_uitgangen_geven_twee_eigen_regels(tmp_path):
    """PER UITGANG APART. "Er is iets stil" is geen melding waar je iets mee kunt; uit het alarm
    moet blijken WELKE van de twee is vastgelopen."""
    dd = str(tmp_path)
    for _naam, bestand in pw._weekuitgangen():
        _leg_vast(dd, bestand, 30)
    uit = pw.controleer_week(dd)
    assert uit["ok"] is False and len(uit["redenen"]) == 2
    for naam in _namen():
        assert any(r.startswith(naam + ":") for r in uit["redenen"]), naam


def test_een_stille_uitgang_verraadt_de_andere_niet(tmp_path):
    """De helft die loopt hoort niet in het alarm te staan — anders zoek je in de verkeerde."""
    dd = str(tmp_path)
    namen = dict(pw._weekuitgangen())
    _leg_vast(dd, namen["weekmemo"], 30)
    _leg_vast(dd, namen["noochie-memo"], 2)
    uit = pw.controleer_week(dd)
    assert uit["ok"] is False and len(uit["redenen"]) == 1
    assert uit["redenen"][0].startswith("weekmemo:")
    assert "noochie-memo" not in uit["redenen"][0]


def test_een_recente_lege_ronde_is_geen_stilte(tmp_path):
    """DE KERN VAN DEZE CHECK. Een week zonder nieuwe signalen levert geen bericht op en is tóch
    een geslaagde ronde: hij LEGDE iets vast. Zou dat alarmeren, dan is het alarm de wekelijkse
    ruis geworden die we juist niet wilden."""
    dd = str(tmp_path)
    for _naam, bestand in pw._weekuitgangen():
        _leg_vast(dd, bestand, 3)                       # 3 dagen geleden, aantal 0
    uit = pw.controleer_week(dd)
    assert uit["ok"] is True and uit["redenen"] == []


def test_nog_nooit_gedraaid_is_ook_stilte(tmp_path):
    """Precies het geval dat dit veroorzaakte: gewired, nooit iets vastgelegd, en niets in het dorp
    dat het zei."""
    uit = pw.controleer_week(str(tmp_path))
    assert uit["ok"] is False and len(uit["redenen"]) == 2
    assert all("nog nooit" in r for r in uit["redenen"]), uit["redenen"]


def test_de_drempel_ligt_ruimer_dan_de_cyclus(tmp_path):
    """Een week die een dag uitloopt is geen storing. Een bewaker die daarop afgaat, leert men
    negeren — en dan mist hij de keer dat het wél mis is."""
    dd = str(tmp_path)
    assert pw.STILTE_DAGEN > 7
    for _naam, bestand in pw._weekuitgangen():
        _leg_vast(dd, bestand, 8)
    assert pw.controleer_week(dd)["ok"] is True
    for _naam, bestand in pw._weekuitgangen():
        _leg_vast(dd, bestand, pw.STILTE_DAGEN + 1)
    assert pw.controleer_week(dd)["ok"] is False


def test_de_dagelijkse_check_blijft_over_de_dagbel_gaan(tmp_path):
    """TWEE KLOKKEN, TWEE UITSLAGEN. Zou de stilte in `controleer` zitten, dan komt een stille
    weekmemo elke ochtend langs als PULS-alarm — met een tekst die over de dagbel gaat."""
    dd = str(tmp_path)
    (tmp_path / "timekeeper_last_day.json").write_text(
        json.dumps({"last_day": datetime.now().date().isoformat()}), encoding="utf-8")
    uit = pw.controleer(dd, {})                          # géén memo-bestanden in deze map
    assert uit["ok"] is True, uit["redenen"]
    assert "stiltes" not in uit


def test_het_stiltealarm_landt_bij_de_founder_met_een_eigen_kop(tmp_path):
    dd = str(tmp_path)
    uit = pw.controleer_week(dd)
    pw.alarm(dd, uit, kop="🤫 STILTE-ALARM")
    regels = open(_os.path.join(dd, pw.ALARM_LOG), encoding="utf-8").read()
    assert "STILTE-ALARM" in regels and "weekmemo" in regels and "noochie-memo" in regels
    assert "PULS-ALARM" not in regels


def test_de_cli_alarmeert_op_allebei():
    import pathlib
    cli = (pathlib.Path(__file__).resolve().parents[1] / "nooch_village" / "cli.py").read_text()
    blok = cli.split('elif mode == "puls_wacht":')[1].split("elif mode ==")[0]
    assert "controleer_week" in blok
    assert 'kop="🤫 STILTE-ALARM"' in blok
    assert blok.count("alarm(ctx.data_dir") == 2, "de twee alarmen delen één melding"
