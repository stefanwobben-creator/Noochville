"""Tests voor het roterend Trends-venster + User-Agent. Geen netwerk, thread-vrij."""
from __future__ import annotations

import json
import os
from types import SimpleNamespace

from nooch_village.skills_impl.trends import rotate_window, TrendsSkill, _USER_AGENT


# ── rotate_window (puur) ──────────────────────────────────────────────────────

def test_venster_neemt_eerste_n_en_schuift_cursor_op():
    items = ["a", "b", "c", "d", "e"]
    window, nxt = rotate_window(items, 0, 3)
    assert window == ["a", "b", "c"]
    assert nxt == 3


def test_venster_wrapt_rond():
    items = ["a", "b", "c", "d", "e"]
    window, nxt = rotate_window(items, 3, 3)      # vanaf index 3: d, e, a
    assert window == ["d", "e", "a"]
    assert nxt == 1


def test_volledige_dekking_over_pulsen():
    items = ["a", "b", "c", "d", "e"]
    seen, cursor = [], 0
    for _ in range(2):                            # 2 pulsen × 3 = 6 >= 5 termen
        window, cursor = rotate_window(items, cursor, 3)
        seen += window
    assert set(items) <= set(seen)                # alles minstens één keer gezien


def test_size_groter_dan_lijst_geeft_alles():
    window, nxt = rotate_window(["a", "b"], 0, 5)
    assert window == ["a", "b"]
    assert nxt == 0


def test_lege_lijst():
    assert rotate_window([], 7, 3) == ([], 0)


# ── _select_window (cursor-persistentie) ──────────────────────────────────────

def _ctx(tmp_path, size=3):
    return SimpleNamespace(
        data_dir=str(tmp_path),
        settings={"trends_keywords_per_pulse": str(size)},
    )


def test_select_window_bewaart_en_schuift_cursor(tmp_path):
    skill = TrendsSkill()
    ctx = _ctx(tmp_path, size=2)
    kws = ["a", "b", "c", "d"]
    first = skill._select_window(kws, ctx)
    second = skill._select_window(kws, ctx)       # tweede puls leest opgeslagen cursor
    assert first == ["a", "b"]
    assert second == ["c", "d"]
    cursor = json.load(open(os.path.join(str(tmp_path), "trends_cursor.json")))["cursor"]
    assert cursor == 0                            # na 4 van 4 weer rond


def test_select_window_corrupte_cursor_valt_terug_op_nul(tmp_path):
    p = os.path.join(str(tmp_path), "trends_cursor.json")
    open(p, "w").write("rommel{")
    skill = TrendsSkill()
    window = skill._select_window(["a", "b", "c"], _ctx(tmp_path, size=2))
    assert window == ["a", "b"]                   # cursor 0 als fallback


# ── User-Agent ────────────────────────────────────────────────────────────────

def test_user_agent_is_browser_achtig():
    assert "Mozilla/5.0" in _USER_AGENT and "Chrome" in _USER_AGENT
