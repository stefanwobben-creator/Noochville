"""google_patents — het alternatieve pad van de skill-ladder (keyless). Parse los getest op een vaste
sample (geen netwerk); run fail-closed bij fout en geldig no_data bij leeg."""
from __future__ import annotations

from nooch_village.skills_impl.google_patents import GooglePatentsSkill

SAMPLE = {"results": {"total_num_results": 2, "cluster": [{"result": [
    {"patent": {"title": "Biodegradable sole", "publication_number": "US123A1",
                "publication_date": "2024-01-01", "snippet": "A shoe with a compostable sole.",
                "assignee": "ACME", "inventor": ["A. Jones"]}},
    {"patent": {"title": "Compostable shoe", "publication_number": "EP999A1",
                "priority_date": "2023-05-05"}},
]}]}}


def test_parse_sample():
    total, pats = GooglePatentsSkill._parse(SAMPLE)
    assert total == 2 and len(pats) == 2
    assert pats[0]["title"] == "Biodegradable sole" and pats[0]["assignee"] == ["ACME"]
    assert pats[0]["inventors"] == ["A. Jones"] and "compostable" in pats[0]["abstract"]
    assert pats[1]["publication_date"] == "2023-05-05"                 # valt terug op priority_date


def test_run_ok_zonder_netwerk():
    sk = GooglePatentsSkill()
    sk._fetch = lambda term, limit, _get=None: SAMPLE                  # bypass HTTP
    out = sk.run({"term": "biodegradable sole"}, None)
    assert out["total"] == 2 and len(out["patents"]) == 2 and "error" not in out


def test_run_leeg_is_no_data():
    sk = GooglePatentsSkill()
    sk._fetch = lambda term, limit, _get=None: {"results": {"total_num_results": 0, "cluster": []}}
    out = sk.run({"term": "onvindbaar"}, None)
    assert out.get("no_data") and out["patents"] == []


def test_run_faalt_closed():
    sk = GooglePatentsSkill()
    def boom(term, limit, _get=None):
        raise RuntimeError("HTTP 403")
    sk._fetch = boom
    out = sk.run({"term": "x"}, None)
    assert "error" in out and out["patents"] == []                    # geen crash, gat + error


def test_geen_term():
    assert "error" in GooglePatentsSkill().run({}, None)


def test_geregistreerd_in_factory():
    from nooch_village.registry_factory import build_skill_registry
    assert "google_patents" in build_skill_registry().names()
