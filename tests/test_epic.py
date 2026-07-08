"""EPIC-aardbol: metadata-parsing + 1u-cache (in-memory + schijf), fail-closed zonder key/bij API-fout,
de thumbnail-proxy met input-validatie + JPEG-check, de schijf-cache die een herstart overleeft, en de
widget (alleen op de anchor, met nette fallback, zonder inline styles). Alle NASA-calls gemockt."""
from __future__ import annotations

import pytest

from nooch_village import epic, cockpit2
from nooch_village.views import overview

_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01" + b"\x00" * 40 + b"\xff\xd9"   # begint met JPEG-magic


class _FakeResp:
    def __init__(self, json_data=None, content=b"", ok=True):
        self._json, self.content, self._ok = json_data, content, ok

    def raise_for_status(self):
        if not self._ok:
            raise epic.requests.RequestException("boom")

    def json(self):
        if self._json is None:
            raise ValueError("geen json")
        return self._json


@pytest.fixture(autouse=True)
def _reset(monkeypatch, tmp_path):
    epic._meta_cache.update(ts=0.0, data=None)
    epic._frame_mem.clear()
    cdir = str(tmp_path / "epic_cache")                     # geïsoleerde schijf-cache per test
    monkeypatch.setattr(epic, "_CACHE_DIR", cdir)
    monkeypatch.setattr(epic, "_META_FILE", cdir + "/meta.json")
    monkeypatch.setattr(epic, "_FRAME_DIR", cdir + "/frames")
    monkeypatch.setenv("NASA_API_KEY", "TESTKEY")
    yield


_META_RAW = [
    {"image": "epic_1b_20260704000000", "date": "2026-07-04 00:00:00"},
    {"image": "epic_1b_20260704010000", "date": "2026-07-04 01:00:00"},
]
_FRAMES = [
    {"image": "epic_1b_20260704000000", "date": "2026-07-04", "caption": "2026-07-04 00:00:00"},
    {"image": "epic_1b_20260704010000", "date": "2026-07-04", "caption": "2026-07-04 01:00:00"},
]


def test_latest_frames_parst_en_cachet_1u(monkeypatch):
    calls = {"n": 0}
    def fake_get(*a, **k):
        calls["n"] += 1
        return _FakeResp(json_data=_META_RAW)
    monkeypatch.setattr(epic.requests, "get", fake_get)
    fr = epic.latest_frames()
    assert fr[-1]["image"] == "epic_1b_20260704010000"
    assert fr[-1]["date"] == "2026-07-04" and fr[-1]["caption"] == "2026-07-04 01:00:00"
    epic.latest_frames()                      # binnen TTL → geen tweede NASA-call
    assert calls["n"] == 1


def test_latest_frames_teruggesampled_naar_n(monkeypatch):
    big = [{"image": f"epic_1b_202607040{i:03d}0", "date": f"2026-07-04 0{i//60}:{i%60:02d}:00"}
           for i in range(20)]
    monkeypatch.setattr(epic.requests, "get", lambda *a, **k: _FakeResp(json_data=big))
    fr = epic.latest_frames()
    assert epic._N_FRAMES == 8 and len(fr) == 8            # 20 frames → teruggesampled naar 8 posities


def test_geen_key_geeft_none(monkeypatch):
    monkeypatch.setenv("NASA_API_KEY", "")
    monkeypatch.setattr(epic.requests, "get", lambda *a, **k: _FakeResp(json_data=_META_RAW))
    assert epic.latest_frames() is None


def test_api_fout_geeft_none(monkeypatch):
    monkeypatch.setattr(epic.requests, "get", lambda *a, **k: _FakeResp(ok=False))
    assert epic.latest_frames() is None


def test_frame_bytes_thumbnail_en_input_validatie(monkeypatch):
    seen = {}
    def fake_get(url, **k):
        seen["url"] = url
        return _FakeResp(content=_JPEG)
    monkeypatch.setattr(epic.requests, "get", fake_get)
    out = epic.frame_bytes("epic_1b_20260704010000", "2026-07-04")
    assert out == _JPEG and out[:3] == b"\xff\xd8\xff"     # thumbnail-JPEG direct doorgeserveerd (geen resize)
    assert "/thumbs/" in seen["url"] and seen["url"].endswith(".jpg")   # kleine thumbnail-bron
    assert epic.frame_bytes("../../etc/passwd", "2026-07-04") is None    # SSRF/path-traversal geweerd
    assert epic.frame_bytes("ok", "geen-datum") is None


def test_frame_bytes_geen_jpeg_geeft_none(monkeypatch):
    monkeypatch.setattr(epic.requests, "get", lambda *a, **k: _FakeResp(content=b"geen-afbeelding"))
    assert epic.frame_bytes("epic_1b_20260704010000", "2026-07-04") is None   # geen JPEG-magic → fail-closed


def test_schijf_cache_overleeft_herstart(monkeypatch):
    resp = _FakeResp(json_data=_META_RAW, content=_JPEG)
    monkeypatch.setattr(epic.requests, "get", lambda *a, **k: resp)
    epic.latest_frames()                                   # → meta.json op schijf
    assert epic.frame_bytes("epic_1b_20260704010000", "2026-07-04") == _JPEG   # → frames/*.jpg op schijf
    epic._meta_cache.update(ts=0.0, data=None)             # simuleer een herstart: in-memory leeg
    epic._frame_mem.clear()
    def boom(*a, **k):
        raise AssertionError("mag NASA niet bellen — moet uit de schijf-cache komen")
    monkeypatch.setattr(epic.requests, "get", boom)
    assert epic.latest_frames()[-1]["image"] == "epic_1b_20260704010000"       # uit meta.json
    assert epic.frame_bytes("epic_1b_20260704010000", "2026-07-04") == _JPEG    # uit frames/*.jpg


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return cockpit2._Stores(dd)


def test_widget_alleen_op_anchor(monkeypatch, tmp_path):
    monkeypatch.setattr(epic, "latest_frames", lambda: list(_FRAMES))
    st = _st(tmp_path)
    anchor = overview._overview_html(st, st.records.get("mother_earth"))
    assert "epic-earth" in anchor and "/epic/frame?image=" in anchor
    assert "2026-07-04 01:00:00 UTC" in anchor
    assert "Geen domein" not in anchor
    role = overview._overview_html(st, st.records.get("mother_earth__nooch__creator_of_shoes"))
    assert "epic-earth" not in role


def test_widget_fallback_zonder_frames(monkeypatch, tmp_path):
    monkeypatch.setattr(epic, "latest_frames", lambda: None)
    st = _st(tmp_path)
    html = overview._overview_html(st, st.records.get("mother_earth"))
    assert "niet beschikbaar" in html and "epic-frame" not in html


def test_widget_geen_inline_style(monkeypatch):
    monkeypatch.setattr(epic, "latest_frames", lambda: list(_FRAMES))
    assert "style=" not in overview._epic_earth_html()
