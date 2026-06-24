"""competitor_news-skill + ConcurrentScout-rol: pure parser, fail-closed run, en de
dedup/signaal/spanning-logica van de rol. Geen netwerk (HTTP en skill gemockt)."""
from __future__ import annotations
import logging
import types
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from datetime import timedelta
from nooch_village.skills_impl.competitor_news import (
    CompetitorNewsSkill, _parse_all, _cascade_select)
from nooch_village.roles import ConcurrentScout

_RSS = """<?xml version="1.0"?><rss><channel>
<item><title>Veja raises new funding round</title><link>http://a</link>
 <pubDate>Wed, 24 Jun 2026 10:00:00 GMT</pubDate></item>
<item><title>Veja oud bericht</title><link>http://old</link>
 <pubDate>Wed, 01 Jan 2020 10:00:00 GMT</pubDate></item>
</channel></rss>"""


def _rss_one(days_ago: int, now: datetime) -> str:
    dt = (now - timedelta(days=days_ago)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    return (f'<?xml version="1.0"?><rss><channel><item><title>Veja nieuws</title>'
            f'<link>http://x</link><pubDate>{dt}</pubDate></item></channel></rss>')


# ── pure parser + cascade ──────────────────────────────────────────────────────

def test_parse_all_zet_merk_en_datum():
    now = datetime(2026, 6, 24, 12, 0, tzinfo=timezone.utc)
    items = _parse_all(_RSS, now=now, brand="Veja")
    assert len(items) == 2 and items[0]["brand"] == "Veja"


def test_cascade_kiest_kortste_venster_met_nieuws():
    now = datetime(2026, 6, 24, 12, 0, tzinfo=timezone.utc)
    items = _parse_all(_rss_one(50, now), now=now, brand="Veja")    # 50 dagen geleden
    sel, used = _cascade_select(items, now=now, windows=[30, 90, 365])
    assert used == 90 and len(sel) == 1            # buiten maand, binnen kwartaal


def test_cascade_leeg_als_niks_in_een_jaar():
    now = datetime(2026, 6, 24, 12, 0, tzinfo=timezone.utc)
    items = _parse_all(_rss_one(800, now), now=now, brand="Veja")   # >2 jaar geleden
    sel, used = _cascade_select(items, now=now, windows=[30, 90, 365])
    assert sel == [] and used == 365


def test_onleesbare_datum_wordt_hard_overgeslagen():
    now = datetime(2026, 6, 24, 12, 0, tzinfo=timezone.utc)
    bad = ('<?xml version="1.0"?><rss><channel><item><title>geen datum</title>'
           '<link>http://x</link><pubDate>onzin</pubDate></item></channel></rss>')
    assert _parse_all(bad, now=now, brand="Veja") == []      # geen 'now'-lek meer


def test_run_ontdubbelt_zelfde_link_over_merken():
    same = _rss_one(5, datetime.now(timezone.utc))           # zelfde link 'http://x'
    ctx = SimpleNamespace(data_dir="/tmp", settings={"competitor_brands": "Veja, Moea"})
    with patch("requests.get", return_value=_resp(same)):
        res = CompetitorNewsSkill().run({}, ctx)
    assert res["total"] == 1                                  # roundup telt maar één keer


def test_query_dwingt_footwear_context_af():
    seen = {}
    def grab(url, **k):
        seen["url"] = url
        return _resp(_RSS)
    ctx = SimpleNamespace(data_dir="/tmp", settings={"competitor_brands": "Moea"})
    with patch("requests.get", side_effect=grab):
        CompetitorNewsSkill().run({}, ctx)
    assert "footwear" in seen["url"] or "sneakers" in seen["url"]


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
    for name in ("_run_news", "_is_mission_relevant", "_seen_path", "_load_seen", "_save_seen"):
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
    s._run_news(["Veja", "Moea"])
    assert len(_signals(s)) == 2                  # twee nieuwe berichten → twee signalen
    assert len(s._tensions) == 1                  # één gebundelde spanning (B-Corp = missie)
    done = [e for e in s._events if e.name == "competitor_pulse_completed"][0]
    assert done.data["new"] == 2 and done.data["mission_relevant"] == 1


def test_tweede_run_is_stil_door_dedup(tmp_path):
    s = _scout(_SKILL_OK, tmp_path)
    s._run_news(["Veja", "Moea"])                 # eerste run: markeert links als gezien
    s._events.clear(); s._tensions.clear()
    s._run_news(["Veja", "Moea"])                 # tweede run: niets nieuws
    assert _signals(s) == [] and s._tensions == []
    done = [e for e in s._events if e.name == "competitor_pulse_completed"][0]
    assert done.data["new"] == 0
