"""EPIC-aardbol: metadata-parsing + 1u-cache, fail-closed zonder key/bij API-fout, de PNG-proxy met
input-validatie, en de widget (alleen op de anchor, met nette fallback, zonder inline styles).
Alle NASA-calls zijn gemockt — geen live requests."""
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
def _reset(monkeypatch):
    epic._meta_cache.update(ts=0.0, data=None)
    epic._png_cache.clear()
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
    assert out and out[:3] == b"\xff\xd8\xff"            # geldige JPEG terug (licht voor 22 frames)
    assert max(Image.open(BytesIO(out)).size) <= 512     # server-side geresized naar ~512px
    # onveilige input → None, geen call (voorkomt SSRF/path-traversal)
    assert epic.frame_bytes("../../etc/passwd", "2026-07-04") is None
    assert epic.frame_bytes("ok", "geen-datum") is None


def test_frame_bytes_pillow_fout_geeft_none(monkeypatch):
    # NASA geeft iets terug dat geen geldige afbeelding is → Pillow faalt → None (geen crash)
    monkeypatch.setattr(epic.requests, "get", lambda *a, **k: _FakeResp(content=b"geen-afbeelding"))
    assert epic.frame_bytes("epic_1b_20260704010000", "2026-07-04") is None


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return cockpit2._Stores(dd)


def test_widget_alleen_op_anchor(monkeypatch, tmp_path):
    monkeypatch.setattr(epic, "latest_frames", lambda: list(_FRAMES))
    st = _st(tmp_path)
    anchor = overview._overview_html(st, st.records.get("mother_earth"))
    assert "epic-earth" in anchor and "/epic/frame?image=" in anchor
    assert "2026-07-04 01:00:00 UTC" in anchor          # onderschrift met timestamp
    assert "Geen domein" not in anchor                  # geen placeholder-tekst onder de aardbol
    role = overview._overview_html(st, st.records.get("mother_earth__nooch__creator_of_shoes"))
    assert "epic-earth" not in role                     # niet op andere rollen/cirkels


def test_widget_fallback_zonder_frames(monkeypatch, tmp_path):
    monkeypatch.setattr(epic, "latest_frames", lambda: None)
    st = _st(tmp_path)
    html = overview._overview_html(st, st.records.get("mother_earth"))
    assert "niet beschikbaar" in html and "epic-frame" not in html   # nette fallback, geen kapotte pagina


def test_widget_geen_inline_style(monkeypatch):
    monkeypatch.setattr(epic, "latest_frames", lambda: list(_FRAMES))
    assert "style=" not in overview._epic_earth_html()   # UI-regel: geen inline styles
