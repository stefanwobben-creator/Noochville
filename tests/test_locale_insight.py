"""Inbox-fix (bezoekersdata per locale): website_watcher duidt de Plausible country-breakdown
per puls (locale_insight). Stub; geen netwerk."""
from __future__ import annotations
import logging
import types
from types import SimpleNamespace

from nooch_village.roles import WebsiteWatcherWorker


def _stub():
    s = SimpleNamespace(id="website_watcher", log=logging.getLogger("t"))
    s._events = []
    s.bus = SimpleNamespace(publish=lambda e: s._events.append(e))
    s._surface_locale = types.MethodType(WebsiteWatcherWorker._surface_locale, s)
    return s


def test_surface_locale_publiceert_inzicht():
    s = _stub()
    plausible = {"countries": [{"country": "NL", "visitors": 40}, {"country": "BE", "visitors": 12}]}
    s._surface_locale(plausible)
    ev = [e for e in s._events if e.name == "locale_insight"]
    assert ev and ev[0].data["countries"][0]["locale"] == "NL"
    assert ev[0].data["countries"][0]["visitors"] == 40


def test_surface_locale_stil_zonder_data():
    s = _stub()
    s._surface_locale({"countries": []})
    s._surface_locale({"error": "x"})
    assert [e for e in s._events if e.name == "locale_insight"] == []
