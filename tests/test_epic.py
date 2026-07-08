"""EPIC-aardbol: metadata-parsing + 1u-cache (in-memory + schijf), fail-closed zonder key/bij API-fout,
de PNG→512px-resize-proxy met input-validatie, de schijf-cache die een herstart overleeft, en de widget
(met wachtindicator, nette fallback, zonder inline styles). Alle NASA-calls gemockt."""
from __future__ import annotations
from io import BytesIO

import pytest
from PIL import Image

from nooch_village import epic, cockpit2
from nooch_village.views import overview


def _fake_png(size: int = 1024, color=(0, 80, 180)) -> bytes:
    b = BytesIO()
    Image.new("RGB", (size, size), color).save(b, format="PNG")
    return b.getvalue()


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
    assert fr[-1]["image"] == "epic_1b_20260704010000" and fr[-1]["caption"] == "2026-07-04 01:00:00"
    epic.latest_frames()                      # binnen TTL → geen tweede NASA-call
    assert calls["n"] == 1


def test_latest_frames_teruggesampled_naar_n(monkeypatch):
    big = [{"image": f"epic_1b_2026070401{i:04d}", "date": f"2026-07-04 01:00:{i % 60:02d}"} for i in range(40)]
    monkeypatch.setattr(epic.requests, "get", lambda *a, **k: _FakeResp(json_data=big))
    fr = epic.latest_frames()
    assert epic._N_FRAMES == 24 and len(fr) == 24          # 40 frames → teruggesampled naar 24 posities


def test_geen_key_geeft_none(monkeypatch):
    monkeypatch.setenv("NASA_API_KEY", "")
    monkeypatch.setattr(epic.requests, "get", lambda *a, **k: _FakeResp(json_data=_META_RAW))
    assert epic.latest_frames() is None


def test_api_fout_geeft_none(monkeypatch):
    monkeypatch.setattr(epic.requests, "get", lambda *a, **k: _FakeResp(ok=False))
    assert epic.latest_frames() is None


def test_frame_bytes_resize_naar_512_en_input_validatie(monkeypatch):
    monkeypatch.setattr(epic.requests, "get", lambda *a, **k: _FakeResp(content=_fake_png(1024)))
    out = epic.frame_bytes("epic_1b_20260704010000", "2026-07-04")
    assert out and out[:3] == b"\xff\xd8\xff"               # geldige JPEG terug
    assert max(Image.open(BytesIO(out)).size) <= 512        # server-side geresized naar ~512px (scherp)
    assert epic.frame_bytes("../../etc/passwd", "2026-07-04") is None   # SSRF/path-traversal geweerd
    assert epic.frame_bytes("ok", "geen-datum") is None


def test_frame_bytes_pillow_fout_geeft_none(monkeypatch):
    monkeypatch.setattr(epic.requests, "get", lambda *a, **k: _FakeResp(content=b"geen-afbeelding"))
    assert epic.frame_bytes("epic_1b_20260704010000", "2026-07-04") is None   # geen afbeelding → None


def test_schijf_cache_overleeft_herstart(monkeypatch):
    resp = _FakeResp(json_data=_META_RAW, content=_fake_png(800))
    monkeypatch.setattr(epic.requests, "get", lambda *a, **k: resp)
    epic.latest_frames()                                   # → meta.json op schijf
    b1 = epic.frame_bytes("epic_1b_20260704010000", "2026-07-04")   # → frames/*.jpg op schijf
    assert b1
    epic._meta_cache.update(ts=0.0, data=None)             # simuleer een herstart: in-memory leeg
    epic._frame_mem.clear()
    def boom(*a, **k):
        raise AssertionError("mag NASA niet bellen — moet uit de schijf-cache komen")
    monkeypatch.setattr(epic.requests, "get", boom)
    assert epic.latest_frames()[-1]["image"] == "epic_1b_20260704010000"       # uit meta.json
    assert epic.frame_bytes("epic_1b_20260704010000", "2026-07-04") == b1       # uit frames/*.jpg


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return cockpit2._Stores(dd)


def test_widget_toont_loader_en_frames(monkeypatch, tmp_path):
    monkeypatch.setattr(epic, "latest_frames", lambda: list(_FRAMES))
    st = _st(tmp_path)
    anchor = overview._overview_html(st, st.records.get("mother_earth"))
    assert "epic-earth" in anchor and "/epic/frame?image=" in anchor
    assert "epic-loading" in anchor and "Mother Earth is loading" in anchor and "🌍" in anchor  # wachtindicator
    assert "2026-07-04 01:00:00 UTC" in anchor and "Geen domein" not in anchor
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
