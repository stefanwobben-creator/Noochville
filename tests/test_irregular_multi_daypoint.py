"""Irregulaire bronnen mogen meerdere meetpunten per dag (cadans-bewuste record_daily-dedup).

Dekt: twee overleggen dezelfde dag → twee observaties; dezelfde snapshot twee keer → één (ook na
herstart); regulier (Plausible-achtig) ongewijzigd; fail-closed zonder event_id; en de tegel die
twee same-day-punten correct middelt.
"""
from __future__ import annotations

from nooch_village.observations import ObservationStore, record_werk_daily

_M = "werk_tevredenheid_day"   # irregulier (werkoverleg)
_D = "2026-07-10"


def _obs(tmp_path):
    return ObservationStore(str(tmp_path / "obs.jsonl"))


# ── irregulier: meerdere meetpunten per dag ─────────────────────────────────────────

def test_twee_overleggen_zelfde_dag_twee_observaties(tmp_path):
    obs = _obs(tmp_path)
    assert obs.record_daily("nooch", _M, 7, bron="werkoverleg", datum=_D, event_id="1000") is True
    assert obs.record_daily("nooch", _M, 9, bron="werkoverleg", datum=_D, event_id="2000") is True
    rows = obs.daily_series(_M, bron="werkoverleg")
    assert len(rows) == 2
    assert sorted(r["value"] for r in rows) == [7, 9]
    assert all((r.get("meta") or {}).get("event_id") in ("1000", "2000") for r in rows)


def test_zelfde_snapshot_twee_keer_een_observatie(tmp_path):
    obs = _obs(tmp_path)
    assert obs.record_daily("nooch", _M, 7, bron="werkoverleg", datum=_D, event_id="1000") is True
    assert obs.record_daily("nooch", _M, 7, bron="werkoverleg", datum=_D, event_id="1000") is False
    assert len(obs.daily_series(_M, bron="werkoverleg")) == 1


def test_idempotent_na_herstart(tmp_path):
    """Een verse store-instance herbouwt de dedup-index uit het bestand → herhaalde schrijf blijft one."""
    p = str(tmp_path / "obs.jsonl")
    ObservationStore(p).record_daily("nooch", _M, 7, bron="werkoverleg", datum=_D, event_id="1000")
    obs2 = ObservationStore(p)                    # verse instance leest het bestand opnieuw
    assert obs2.record_daily("nooch", _M, 7, bron="werkoverleg", datum=_D, event_id="1000") is False
    assert len(obs2.daily_series(_M, bron="werkoverleg")) == 1


# ── fail-closed: irregulier zonder event_id ─────────────────────────────────────────

def test_irregulier_zonder_event_id_geweigerd(tmp_path, caplog):
    obs = _obs(tmp_path)
    with caplog.at_level("WARNING"):
        assert obs.record_daily("nooch", _M, 7, bron="werkoverleg", datum=_D) is False
    assert obs.daily_series(_M, bron="werkoverleg") == []          # niet stil op dag-dedup teruggevallen
    assert any("event_id" in r.getMessage() for r in caplog.records)


# ── regulier (Plausible-achtig): gedrag ongewijzigd ─────────────────────────────────

def test_regulier_ongewijzigd_dag_dedup(tmp_path):
    obs = _obs(tmp_path)
    assert obs.record_daily("plausible", "plausible_visitors_day", 100, bron="plausible", datum=_D) is True
    # tweede schrijf zelfde dag → geweigerd (per-dag), event_id wordt genegeerd
    assert obs.record_daily("plausible", "plausible_visitors_day", 200, bron="plausible",
                            datum=_D, event_id="genegeerd") is False
    rows = obs.daily_series("plausible_visitors_day", bron="plausible")
    assert len(rows) == 1 and rows[0]["value"] == 100
    assert "event_id" not in (rows[0].get("meta") or {})          # regulier zet geen event_id in meta


# ── record_werk_daily: event_id uit de snapshot ─────────────────────────────────────

def test_record_werk_daily_twee_overleggen_zelfde_dag(tmp_path):
    obs = _obs(tmp_path)
    record_werk_daily(obs, "nooch", {"tevredenheid": 7, "duur_min": 30, "at": 2000, "started_at": 1000})
    record_werk_daily(obs, "nooch", {"tevredenheid": 9, "duur_min": 40, "at": 5000, "started_at": 4000})
    assert len(obs.daily_series(_M, bron="werkoverleg")) == 2       # twee overleggen (verschillende started_at)
    # zelfde snapshot nogmaals → idempotent
    record_werk_daily(obs, "nooch", {"tevredenheid": 7, "duur_min": 30, "at": 2000, "started_at": 1000})
    assert len(obs.daily_series(_M, bron="werkoverleg")) == 2


def test_record_werk_daily_fallback_op_ended_at(tmp_path):
    """Oude snapshot zonder started_at → event_id valt terug op 'at' (ended_at); nog steeds uniek."""
    obs = _obs(tmp_path)
    record_werk_daily(obs, "nooch", {"tevredenheid": 6, "at": 3000})   # geen started_at
    rows = obs.daily_series(_M, bron="werkoverleg")
    assert len(rows) == 1 and rows[0]["meta"]["event_id"] == "3000"


# ── tegel: twee same-day-punten → dag-gemiddelde ────────────────────────────────────

def test_tegel_middelt_two_same_day_points(tmp_path):
    from nooch_village.views.metrics import _daily_obs_series
    obs = _obs(tmp_path)
    obs.record_daily("nooch", _M, 6, bron="werkoverleg", datum=_D, event_id="1")
    obs.record_daily("nooch", _M, 8, bron="werkoverleg", datum=_D, event_id="2")

    class _St:
        pass
    st = _St(); st.observations = obs
    res = _daily_obs_series(st, "werk:nooch", "tevredenheid", cutoff=None, end=None)
    pts = res["points"]
    assert len(pts) == 1                 # één punt voor die dag
    assert pts[0][1] == 7.0              # gemiddelde van 6 en 8
