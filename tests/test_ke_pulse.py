"""KeywordsEverywhere draait mee in de GSC-puls: nieuwe high_potential-queries worden
gemeten (capped, fail-closed) en doorgestuurd met echt zoekvolume in de demand."""
from __future__ import annotations
import logging
import types
from types import SimpleNamespace

from nooch_village.roles import TrendsWorker

# De echte TrendsWorker-methodes die elkaar via self aanroepen, op de stub gebonden.
_BOUND = ("_measure_volumes", "_propose_from_gsc", "_ke_pulse_max", "_ke_country")


class _Lib:
    def __init__(self, data=None):
        self._d = data or {}
    def status(self, w):
        return self._d.get(w.lower())


def _stub(use_skill_return, *, settings=None, lib=None, has_ke=True):
    s = SimpleNamespace()
    s.id = "trends"
    s.dna = SimpleNamespace(skills=(["keywords_everywhere"] if has_ke else []))
    s.context = SimpleNamespace(settings=settings or {}, library=lib or _Lib())
    s.log = logging.getLogger("test.trends")
    s._published = []
    s.bus = SimpleNamespace(publish=lambda e: s._published.append(e))
    s._captured = {}
    def _use(cap, payload):
        s._captured["cap"] = cap
        s._captured["payload"] = payload
        return use_skill_return
    s.use_skill = _use
    for name in _BOUND:
        setattr(s, name, types.MethodType(getattr(TrendsWorker, name), s))
    return s


def test_measure_volumes_capt_en_geeft_volume_terug():
    ret = {"keywords": [{"keyword": "a", "vol": 300}, {"keyword": "b", "vol": 0}]}
    s = _stub(ret, settings={"ke_pulse_max": "2"})
    vols = s._measure_volumes(["a", "b", "c"])
    assert vols == {"a": 300, "b": 0}
    assert s._captured["payload"]["kw"] == ["a", "b"]      # cap 2 toegepast
    assert s._captured["cap"] == "keywords_everywhere"


def test_measure_volumes_fail_closed_zonder_key():
    s = _stub({"error": "KEYWORDS_EVERYWHERE_API_KEY ontbreekt"})
    assert TrendsWorker._measure_volumes(s, ["a"]) == {}    # geen volume, geen crash


def test_measure_volumes_overslaan_zonder_dna_grant():
    s = _stub({"keywords": [{"keyword": "a", "vol": 9}]}, has_ke=False)
    assert TrendsWorker._measure_volumes(s, ["a"]) == {}
    assert s._captured == {}                                # use_skill niet aangeroepen


def test_propose_from_gsc_meet_alleen_nieuwe_en_hangt_volume_eraan():
    lib = _Lib({"bekend": {"status": "escalated"}})         # al in bibliotheek → niet opnieuw
    ret = {"keywords": [{"keyword": "nieuw kw", "vol": 420}]}
    s = _stub(ret, lib=lib)
    result = {"rows": [
        {"query": "bekend",   "bucket": "high_potential", "impressions": 50, "position": 12, "clicks": 1},
        {"query": "nieuw kw", "bucket": "high_potential", "impressions": 80, "position": 15, "clicks": 2},
        {"query": "laag",     "bucket": "low_ranking",     "impressions": 5,  "position": 40, "clicks": 0},
    ]}
    TrendsWorker._propose_from_gsc(s, result)
    # alleen 'nieuw kw' gemeten (bekend overgeslagen, low_ranking telt niet)
    assert s._captured["payload"]["kw"] == ["nieuw kw"]
    # precies één keyword_proposed, met het echte volume in de demand
    assert len(s._published) == 1
    ev = s._published[0]
    assert ev.data["word"] == "nieuw kw"
    assert ev.data["demand"]["volume"] == 420
