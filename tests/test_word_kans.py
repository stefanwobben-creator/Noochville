"""Kans-score per zoekwoord: volume + concurrentie → opportunity, GSC-stand als snapshot,
verrijking achteraf via set_evidence, en de weekrapport-weergave."""
from __future__ import annotations
from types import SimpleNamespace

from nooch_village.skills_impl.keywords_everywhere import opportunity_score
from nooch_village.library import Library
from nooch_village.cockpit import _word_metrics
from nooch_village import library_enrich


def test_opportunity_score_weegt_concurrentie():
    assert opportunity_score(1000, 0.0) == 1000      # geen concurrentie → volledige kans
    assert opportunity_score(1000, 1.0) == 0         # max concurrentie → geen kans
    assert opportunity_score(1000, 0.25) == 750
    assert opportunity_score(1000, 2.0) == 0         # geklemd op [0,1]
    assert opportunity_score(None, 0.5) is None      # geen volume → geen score
    assert opportunity_score("x", 0.1) is None


def test_set_evidence_merget_zonder_status_of_datum(tmp_path):
    lib = Library(str(tmp_path / "library.json"))
    lib.curate("vegan sneakers", "approved", rationale="kern", evidence={"interest": 5},
               by="librarian")
    datum_voor = lib.status("vegan sneakers")["date"]
    lib.set_evidence("vegan sneakers", {"volume": 18000, "competition": 0.3, "opportunity": 12600})
    e = lib.status("vegan sneakers")
    assert e["status"] == "approved"                 # status ongemoeid
    assert e["date"] == datum_voor                   # datum ongemoeid
    assert e["evidence"]["interest"] == 5            # bestaande evidence behouden
    assert e["evidence"]["volume"] == 18000 and e["evidence"]["opportunity"] == 12600
    assert lib.set_evidence("onbekend woord", {"volume": 1}) is None


def test_word_metrics_toont_kerncijfers():
    html = _word_metrics({"volume": 18000, "competition": 0.3, "opportunity": 12600,
                          "gsc_seen": True, "gsc_position": 8.4, "gsc_clicks": 12})
    assert "vol 18000/mnd" in html
    assert "concurrentie 30%" in html
    assert "kans 12600" in html
    assert "positie 8.4" in html and "12 klikken" in html


def test_word_metrics_niet_rankend_en_leeg():
    assert "nog niet in Google" in _word_metrics({"volume": 500, "gsc_seen": False})
    assert "nog niet gemeten" in _word_metrics({})          # niks bekend → hint om te verrijken


class _FakeLib:
    def __init__(self, data):
        self._d = data
    def all(self):
        return self._d
    def status(self, w):
        return self._d.get(w)
    def set_evidence(self, w, updates):
        self._d[w]["evidence"] = {**self._d[w].get("evidence", {}), **updates}
        return self._d[w]


def test_enrich_library_verrijkt_volume_en_gsc(monkeypatch):
    data = {
        "vegan sneakers": {"status": "approved", "evidence": {}},
        "biobased":       {"status": "approved", "evidence": {"volume": 90}},  # heeft al volume
        "oud verboden":   {"status": "forbidden", "evidence": {}},
    }

    class FakeKE:
        def run(self, payload, context):
            return {"keywords": [{"vol": 18000, "competition": 0.3, "cpc": {"value": 1.2}}]}

    class FakeGSC:
        def run(self, payload, context):
            return {"rows": [{"query": "vegan sneakers", "position": 8.4,
                              "clicks": 12, "impressions": 300}]}

    monkeypatch.setattr(
        "nooch_village.skills_impl.keywords_everywhere.KeywordsEverywhereSkill", FakeKE)
    monkeypatch.setattr("nooch_village.skills_impl.gsc.GscPerformanceSkill", FakeGSC)

    lib = _FakeLib(data)
    ctx = SimpleNamespace(settings={"ke_country": ""})
    out = library_enrich.enrich_library(lib, ctx, sleep=0)

    assert out["gsc_error"] is None
    vs = data["vegan sneakers"]["evidence"]
    assert vs["volume"] == 18000 and vs["opportunity"] == opportunity_score(18000, 0.3)
    assert vs["gsc_seen"] is True and vs["gsc_position"] == 8.4 and vs["gsc_clicks"] == 12
    # biobased had al volume → KE overgeslagen, maar GSC-stand wel gezet (niet rankend)
    assert data["biobased"]["evidence"]["volume"] == 90
    assert data["biobased"]["evidence"]["gsc_seen"] is False
    # forbidden woord blijft buiten beschouwing
    assert "volume" not in data["oud verboden"]["evidence"]


def test_enrich_library_gsc_faalt_closed(monkeypatch):
    data = {"vegan sneakers": {"status": "approved", "evidence": {}}}

    class FakeKE:
        def run(self, p, c):
            return {"keywords": [{"vol": 100, "competition": 0.1}]}

    class FakeGSCErr:
        def run(self, p, c):
            return {"error": "GSC_SITE ontbreekt"}

    monkeypatch.setattr(
        "nooch_village.skills_impl.keywords_everywhere.KeywordsEverywhereSkill", FakeKE)
    monkeypatch.setattr("nooch_village.skills_impl.gsc.GscPerformanceSkill", FakeGSCErr)

    lib = _FakeLib(data)
    out = library_enrich.enrich_library(lib, SimpleNamespace(settings={"ke_country": ""}), sleep=0)
    assert "GSC" in (out["gsc_error"] or "")
    ev = data["vegan sneakers"]["evidence"]
    assert ev["volume"] == 100                      # KE wel
    assert "gsc_seen" not in ev                      # GSC niet gezet bij fout (fail-closed)
