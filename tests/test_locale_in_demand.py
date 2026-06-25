"""Debt-fix: GSC- en Trends-proposers geven de locale mee in de keyword_proposed-demand,
zodat Harry niet meer met locale='' grondt. Stubs; geen netwerk."""
from __future__ import annotations
import logging
import types
from types import SimpleNamespace

from nooch_village.roles import TrendsWorker, WebsiteWatcherWorker


class _Lib:
    def status(self, w):
        return None


def _published(events):
    return [e for e in events if e.name == "keyword_proposed"]


def test_gsc_proposer_geeft_locale_mee():
    s = SimpleNamespace(id="trends", log=logging.getLogger("t"),
                        context=SimpleNamespace(library=_Lib()),
                        dna=SimpleNamespace(skills=[]))   # geen KE → _measure_volumes = {}
    s._events = []
    s.bus = SimpleNamespace(publish=lambda e: s._events.append(e))
    s._propose_from_gsc = types.MethodType(TrendsWorker._propose_from_gsc, s)
    result = {"rows": [{"query": "duurzame sneakers dames", "bucket": "high_potential",
                        "impressions": 40, "position": 14, "clicks": 2, "locale": "nl"}]}
    s._propose_from_gsc(result)
    ev = _published(s._events)
    assert ev and ev[0].data["demand"]["locale"] == "nl"


def test_trends_proposer_geeft_locale_mee():
    s = SimpleNamespace(id="website_watcher", log=logging.getLogger("t"),
                        context=SimpleNamespace(library=_Lib(), strategy={}))
    s._events = []
    s.bus = SimpleNamespace(publish=lambda e: s._events.append(e))
    s._propose_related = types.MethodType(WebsiteWatcherWorker._propose_related, s)
    trends = {"geo": "NL", "keywords": {
        "sustainable": {"top_related": [{"query": "vegan sneakers", "value": 60}]}}}
    s._propose_related(trends)
    ev = _published(s._events)
    assert ev and ev[0].data["demand"]["locale"] == "nl"
