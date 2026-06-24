"""competitor_news-skill + ConcurrentScout-rol: pure parser, fail-closed run, en de
dedup/signaal/spanning-logica van de rol. Geen netwerk (HTTP en skill gemockt)."""
from __future__ import annotations
import logging
import types
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from nooch_village.skills_impl.competitor_news import CompetitorNewsSkill, _parse_feed
from nooch_village.roles import ConcurrentScout

_RSS = """<?xml version="1.0"?><rss><channel>
<item><title>Veja raises new funding round</title><link>http://a</link>
 <pubDate>Wed, 24 Jun 2026 10:00:00 GMT</pubDate></item>
<item><title>Veja oud bericht</title><link>http://old</link>
 <pubDate>Wed, 01 Jan 2020 10:00:00 GMT</pubDate></item>
</channel></rss>"""


# ── pure parser ───────────────────────────────────────────────────────────────

def test_parse_feed_filtert_op_venster_en_zet_merk():
    now = datetime(2026, 6, 24, 12, 0, tzinfo=timezone.utc)
    items = _parse_feed(_RSS, now=now, days=7, brand="Veja")
    assert len(items) == 1                       # oude bericht (2020) valt buiten 7 dagen
    assert items[0]["brand"] == "Veja"
    assert items[0]["link"] == "http://a"


# ── skill run ────────────────────────────────────────────────────────────────

def _resp(text):
    return SimpleNamespace(text=text, raise_for_status=lambda: None)


def test_run_schrijft_rapport_en_geeft_items(tmp_path):
    ctx = SimpleNamespace(data_dir=str(tmp_path), settings={"competitor_brands": "Veja"})
    with patch("requests.get", return_value=_resp(_RSS)):
        res = CompetitorNewsSkill().run({}, ctx)
    assert res["ok"] and res["total"] == 1
    assert res["brands"] == ["Veja"]
    import os
    assert os.path.exists(res["path"])


def test_run_fail_closed_als_alle_merken_falen(tmp_path):
    ctx = SimpleNamespace(data_dir=str(tmp_path), settings={"competitor_brands": "Veja, Moea"})
    def boom(*a, **k):
        raise RuntimeError("netwerk weg")
    with patch("requests.get", side_effect=boom):
        res = CompetitorNewsSkill().run({}, ctx)
    assert not res["ok"] and "faalden" in res["error"]


# ── rol: dedup + signalen + gebundelde missie-spanning ─────────────────────────

def _scout(skill_result, tmp_path):
    s = SimpleNamespace()
    s.id = "concurrent_scout"
    s.context = SimpleNamespace(data_dir=str(tmp_path), settings={})
    s.log = logging.getLogger("test.scout")
    s._busy = False
    s._events = []
    s._tensions = []
    s.bus = SimpleNamespace(publish=lambda e: s._events.append(e))
    s.use_skill = lambda cap, payload: skill_result
    s.sense_tension = lambda desc, kind="operational": s._tensions.append((desc, kind))
    for name in ("_on_pulse", "_is_mission_relevant", "_seen_path", "_load_seen", "_save_seen"):
        setattr(s, name, types.MethodType(getattr(ConcurrentScout, name), s))
    return s


_SKILL_OK = {
    "ok": True, "total": 2, "path": "/tmp/competitor_report_x.md",
    "items": [
        {"brand": "Veja", "title": "Veja launches B-Corp materials line",
         "link": "http://a", "date": "2026-06-24"},
        {"brand": "Moea", "title": "Moea opens flagship store", "link": "http://b",
         "date": "2026-06-24"},
    ],
}


def _signals(s):
    return [e for e in s._events if e.name == "competitor_signal"]


def test_eerste_run_signaleert_en_senst_missie_spanning(tmp_path):
    s = _scout(_SKILL_OK, tmp_path)
    s._on_pulse(None)
    assert len(_signals(s)) == 2                  # twee nieuwe berichten → twee signalen
    assert len(s._tensions) == 1                  # één gebundelde spanning (B-Corp = missie)
    done = [e for e in s._events if e.name == "competitor_pulse_completed"][0]
    assert done.data["new"] == 2 and done.data["mission_relevant"] == 1


def test_tweede_run_is_stil_door_dedup(tmp_path):
    s = _scout(_SKILL_OK, tmp_path)
    s._on_pulse(None)                             # eerste run: markeert links als gezien
    s._events.clear(); s._tensions.clear()
    s._on_pulse(None)                             # tweede run: niets nieuws
    assert _signals(s) == [] and s._tensions == []
    done = [e for e in s._events if e.name == "competitor_pulse_completed"][0]
    assert done.data["new"] == 0
