"""TimeKeeper (dagcyclus in Facilitator): dag_begint op een vast kloktijdstip (config), restart-bestendig."""
from __future__ import annotations
from datetime import datetime
from types import SimpleNamespace

from nooch_village.roles import _should_fire_daily, Facilitator


def test_vuurt_op_vast_tijdstip():
    assert _should_fire_daily(datetime(2026, 7, 5, 4, 31), None, 4, 32) is False   # vóór 04:32
    assert _should_fire_daily(datetime(2026, 7, 5, 4, 32), None, 4, 32) is True    # op 04:32
    assert _should_fire_daily(datetime(2026, 7, 5, 9, 0), None, 4, 32) is True     # na 04:32


def test_restart_vuurt_niet_dubbel_en_verschuift_niet():
    # al gevuurd vandaag (persistente last_day == vandaag) → restart vuurt niet opnieuw
    assert _should_fire_daily(datetime(2026, 7, 5, 9, 0), "2026-07-05", 4, 32) is False
    # server was down om 04:32; komt om 09:00 op met last_day=gisteren → vuurt de dag alsnog éénmaal (catch-up)
    assert _should_fire_daily(datetime(2026, 7, 5, 9, 0), "2026-07-04", 4, 32) is True
    # vóór het tijdstip na een restart → wacht netjes tot 04:32 (geen verschuiving)
    assert _should_fire_daily(datetime(2026, 7, 5, 3, 0), "2026-07-04", 4, 32) is False


def test_last_day_persisteert_over_restart(tmp_path):
    class _Stub:
        _last_day_path = Facilitator._last_day_path
        _load_last_day = Facilitator._load_last_day
        _save_last_day = Facilitator._save_last_day
    s = _Stub(); s.context = SimpleNamespace(data_dir=str(tmp_path))
    s._last_day = "2026-07-05"; s._save_last_day()
    s2 = _Stub(); s2.context = SimpleNamespace(data_dir=str(tmp_path))
    assert s2._load_last_day() == "2026-07-05"           # overleeft een 'restart' (nieuwe instantie)


def test_tijdstip_staat_centraal_in_settings():
    assert "dag_begint_time = 04:32" in open("config/settings.ini").read()
