"""Scope 50b (12 september 2026) — de zoekterm past bij de bron.

Het lijmvrij-onderzoek zocht met één term per bron, in de verkeerde vorm: OpenAlex kreeg de hele
vraag als EXACTE frase (nul), EPO kreeg koppeltekens in een titel-index (nul), web_zoek las vijf van
acht treffers en concludeerde over acht, en alles ging in één taal. Wat hieronder vastligt:

1. OpenAlex: tot drie woorden een frase op citaties (de 8-juli-fix blijft); langer een
   relevantiezoek op losse woorden, en de uitkomst zegt welke van de twee het was;
2. EPO: koppeltekens en schuine strepen worden spaties vóór de CQL;
3. web_zoek leest standaard ALLE treffers (tot het plafond), tenzij `lees` anders zegt;
4. de planner en de strategie vragen om drie woordenschatten (vak, koper, markt) en om korte
   corpus-frases; de herplanning geeft de taal door in de payload.
"""
from __future__ import annotations

import json
import urllib.parse
from types import SimpleNamespace
from unittest.mock import patch

from nooch_village.skills_impl import openalex as oa
from nooch_village.skills_impl.epo_patents import EpoPatentsSkill
from nooch_village.skills_impl.web_zoek import WebZoekSkill


# ── 1: OpenAlex ──────────────────────────────────────────────────────────────

class _Resp:
    def __init__(self, data):
        self._b = json.dumps(data).encode()

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _werk():
    return {"id": "W1", "title": "Adhesives in the footwear industry", "publication_year": 2020,
            "cited_by_count": 12, "abstract_inverted_index": {"glue": [0]}, "primary_topic": {},
            "authorships": []}


def _run(term):
    gezien = []

    def fake_urlopen(req, timeout=None):
        gezien.append(req.full_url)
        return _Resp({"results": [_werk()], "meta": {"count": 1}})
    with patch("urllib.request.urlopen", fake_urlopen), patch("time.sleep"):
        uit = oa.OpenalexSkill().run({"term": term, "limit": 5},
                                     SimpleNamespace(settings={"OPENALEX_API_KEY": "sentinel"}))
    return gezien, uit


def test_korte_term_blijft_een_frase_op_citaties():
    urls, uit = _run("adhesives footwear")
    assert "search=%22adhesives%20footwear%22" in urls[0] and "sort=cited_by_count:desc" in urls[0]
    assert uit["zoekwijze"] == "frase"


def test_lange_term_wordt_een_relevantiezoek_op_losse_woorden():
    """De hele vraag als frase staat in geen enkel abstract; als losse woorden op relevantie wél."""
    urls, uit = _run("glue-free bio-based joining footwear")
    q = urllib.parse.quote("glue-free bio-based joining footwear")
    assert f"search={q}&" in urls[0] and "%22" not in urls[0]
    assert "sort=" not in urls[0]                              # geen citatie-sort: dan winnen de klassiekers
    assert uit["zoekwijze"] == "relevantie" and uit["hits"][0]["title"].startswith("Adhesives")


def test_zoekwijze_grens_ligt_op_drie_woorden():
    assert oa._zoekwijze("a b c") == "frase" and oa._zoekwijze("a b c d") == "relevantie"
    assert oa._zoekwijze("") == "frase"


def test_or_keten_met_een_lange_clause_meldt_relevantie():
    urls, uit = _run("adhesives footwear OR sustainable bio-based adhesive bonding")
    assert "%22adhesives%20footwear%22" in urls[0] and "%22" not in urls[1]
    assert uit["zoekwijze"] == "relevantie"


def test_no_data_draagt_de_zoekwijze_ook():
    def fake_urlopen(req, timeout=None):
        return _Resp({"results": [], "meta": {"count": 0}})
    with patch("urllib.request.urlopen", fake_urlopen), patch("time.sleep"):
        uit = oa.OpenalexSkill().run({"term": "one two three four"},
                                     SimpleNamespace(settings={"OPENALEX_API_KEY": "s"}))
    assert uit["no_data"] is True and uit["zoekwijze"] == "relevantie"


# ── 2: EPO ───────────────────────────────────────────────────────────────────

def test_epo_koppeltekens_worden_spaties_voor_de_cql():
    assert EpoPatentsSkill._normalize_term("glue-free bio-based joining") == "glue free bio based joining"
    assert EpoPatentsSkill._normalize_term("sole/upper bonding") == "sole upper bonding"
    assert EpoPatentsSkill._normalize_term('"shoe sole" AND (adhesive OR glue)') == "shoe sole adhesive"


def test_epo_zoekt_de_losse_woorden_in_de_titel():
    gezien = []

    def _get(url):
        gezien.append(url)
        return b"<r/>"
    with patch.object(EpoPatentsSkill, "_parse_patents", staticmethod(lambda x: (0, []))):
        EpoPatentsSkill()._search("tok", "glue-free bio-based joining", 5, _get=_get)
    assert urllib.parse.quote('ti any "glue free bio based joining"') in gezien[0]


# ── 3: web_zoek leest alles ──────────────────────────────────────────────────

CTX = SimpleNamespace(settings={"SERPAPI_API_KEY": "k"})


def _skill(n):
    treffers = [{"title": f"T{i}", "link": f"https://x{i}.example/p", "snippet": "s"} for i in range(n)]

    def _zoek(term, key, *, num=10, gl="", hl=""):
        return treffers[:num]
    return WebZoekSkill(zoek=_zoek, haal=lambda url: {"url": url, "tekst": "pagina " * 50})


def test_default_leest_alle_treffers():
    uit = _skill(8).run({"term": "bio based hot melt"}, CTX)
    assert uit["aantal_treffers"] == 8 and uit["gelezen"] == 8 and uit["volledig_gelezen"] is True


def test_boven_het_leesplafond_blijft_de_dekking_eerlijk():
    uit = _skill(20).run({"term": "t", "aantal": 15}, CTX)
    assert uit["aantal_treffers"] == 15 and uit["gelezen"] == 10 and uit["volledig_gelezen"] is False
    assert "COVERAGE IS INCOMPLETE" in uit["text"]


def test_lees_nul_is_nog_steeds_alleen_de_lijst():
    uit = _skill(8).run({"term": "t", "lees": 0}, CTX)
    assert uit["gelezen"] == 0 and uit["aantal_treffers"] == 8


# ── 4: de prompts vragen om drie woordenschatten ─────────────────────────────

def test_planner_vraagt_drie_woordenschatten_en_korte_corpusfrases(tmp_path, monkeypatch):
    import nooch_village.llm as llm
    from nooch_village.event_bus import EventBus
    from nooch_village.inhabitant import Inhabitant
    from nooch_village.models import Record, RecordType, RoleDefinition
    from nooch_village.skills import SkillRegistry
    gezien = {}

    def _model(prompt, **k):
        gezien["p"] = prompt
        antwoord = '{"deliverable":"x","items":[{"text":"t","skill":null,"payload":{},"reason":"r"}]}'
        return (antwoord, "mock") if k.get("return_tier") else antwoord
    monkeypatch.setattr(llm, "reason", _model)
    rec = Record(id="r", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="t", skills=["web_zoek"]), source="seed")
    ctx = SimpleNamespace(settings={"deliverable_context_enabled": "0"}, rugzakken={},
                          data_dir=str(tmp_path), projects=None, records=None)
    Inhabitant(rec, EventBus(name="t"), SkillRegistry(), ctx)._plan_checklist("Find bio-based glues")
    p = gezien["p"]
    assert "THREE vocabularies" in p and "the language of the market" in p
    assert "SHORT technical phrase of 2 to 3 words" in p
    assert "Search terms follow the corpus or the market" in p


def test_zoekstrategie_vraagt_drie_woordenschatten(monkeypatch):
    from nooch_village.skills_impl.zoekstrategie import ZoekstrategieSkill
    import nooch_village.llm as llm
    gezien = {}

    def _model(prompt, **k):
        gezien["p"] = prompt
        return json.dumps({"strategie": "s", "stappen": [{"bron": "web_zoek", "term": "bio glue", "taal": "en"}],
                           "bij_nul_treffers": "n"})
    monkeypatch.setattr(llm, "reason", _model)
    uit = ZoekstrategieSkill().run({"vraag": "v"}, SimpleNamespace(settings={}, data_dir=None))
    assert uit["ok"] is True
    assert "THREE VOCABULARIES" in gezien["p"] and "the language of the market" in gezien["p"]
    assert "SHORT technical phrase of 2 to 3 words" in gezien["p"]


def test_herplanning_geeft_de_taal_door_in_de_payload():
    import inspect
    from nooch_village.inhabitant import Inhabitant
    bron = inspect.getsource(Inhabitant._herplan_na_strategie)
    assert "'taal'" in bron and "'land'" in bron
