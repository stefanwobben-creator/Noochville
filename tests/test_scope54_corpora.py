"""Scope 54 — de corpora leveren records met adres en strekking (skill-review batch A, 12-09-2026).

Wat hieronder vastligt, per patroon uit de review:

1. **Corpora leveren een adres.** openalex, semscholar, epo, google_patents en openlibrary zetten een
   `url` (en waar de bron hem heeft een `doi`) in elk record, zodat note en verslag een klikbare regel
   tonen; abstracts gaan tot 2000 tekens zodat `leesextract` er iets mee kan; elke skill geeft een
   `text` als leeswijzer.
2. **"Niets gevonden" heet niets gevonden.** epo leest een 404/"No results" als `no_data`; ngram is op
   topniveau fail-closed (alles stuk → `error`, niets in het corpus → `no_data`); openlibrary meldt nul
   treffers als `no_data`; onderzoeksvraag zegt `error` zonder model; haal_pagina meldt een lege pagina
   als `no_data` en niet als een geslaagde lezing met de URL als inhoud.
3. **Belofte = gedrag.** openlibrary_search_inside zoekt in de VOLTEKST (search/inside.json);
   zoekstrategie biedt alleen bronnen aan die de planner kan plannen.
4. **Eén wachtbudget per run** voor web_zoek en lead_beoordeling; safe_fetch laat alleen tekst door de
   HTML-stripper.

Alles zonder netwerk: urllib/requests gemockt, en getoetst op wat een mens merkt — de classificatie
(`Inhabitant._classify_result`), de note (`_deliverable_note`) en het verslag (`project_verslag`).
"""
from __future__ import annotations

import json
import urllib.error
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nooch_village import leesextract, project_verslag, safe_fetch
from nooch_village.event_bus import EventBus
from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RecordType, RoleDefinition
from nooch_village.skills import SkillRegistry


# ── gereedschap ──────────────────────────────────────────────────────────────

def _inw():
    rec = Record(id="rol", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="p", accountabilities=[], domains=[], skills=[]),
                 source="seed")
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0",
                                    "deliverable_conclusie_enabled": "0"}, rugzakken={})
    return Inhabitant(rec, EventBus(name="t"), SkillRegistry(), ctx)


class _Resp:
    """Nep-urllib-response als context manager."""
    def __init__(self, data):
        self._body = json.dumps(data).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _http(code, msg="", body=b""):
    import io
    return urllib.error.HTTPError(url="https://x", code=code, msg=msg, hdrs=None, fp=io.BytesIO(body))


LANG = " ".join(f"woord{i}" for i in range(200))          # ~1400 tekens: boven de leesextract-drempel


# ═══ 1. OpenAlex ═════════════════════════════════════════════════════════════

def _oa_work(i=1, n_words=200):
    return {"id": f"https://openalex.org/W{i}", "doi": f"https://doi.org/10.1/{i}",
            "title": f"Work {i}", "publication_year": 2020 + i, "cited_by_count": 100 - i,
            "abstract_inverted_index": {f"w{k}": [k] for k in range(n_words)},
            "primary_topic": {"display_name": "Footwear"},
            "authorships": [{"author": {"display_name": "A. Auteur"}}]}


def _oa_run(payload, works):
    from nooch_village.skills_impl.openalex import OpenalexSkill
    ctx = SimpleNamespace(settings={"OPENALEX_API_KEY": "sentinel"})
    with patch("urllib.request.urlopen", lambda req, timeout=None: _Resp({"results": works, "meta": {"count": len(works)}})), \
         patch("time.sleep"):
        return OpenalexSkill().run(payload, ctx)


def test_openalex_record_draagt_adres_doi_en_lang_abstract():
    uit = _oa_run({"term": "adhesives footwear", "limit": 2}, [_oa_work(1), _oa_work(2)])
    hit = uit["hits"][0]
    assert hit["url"] == "https://openalex.org/W1" and hit["doi"] == "https://doi.org/10.1/1"
    assert len(hit["abstract"]) > 600, "de cap van 400 hield leesextract buiten de deur"
    assert uit["text"].startswith("2 work(s) on OpenAlex for 'adhesives footwear' (exact phrase")
    assert "top cited: “Work 1”, 2021, 99 citations" in uit["text"]


def test_openalex_verslag_en_leesextract_lezen_het_record():
    uit = _oa_run({"term": "adhesives footwear", "limit": 1}, [_oa_work(1)])
    assert Inhabitant._classify_result(uit) == ("gelukt", ("list", "hits"))
    t = project_verslag.inhoud_tekst(uit)
    assert t.splitlines()[0].startswith("1 work(s) on OpenAlex")            # de text als leeswijzer
    assert "• Work 1 (https://openalex.org/W1) — w0 w1 w2" in t             # titel (adres) — strekking
    assert leesextract.te_lezen(uit, ("list", "hits")) == [(uit["hits"][0], "abstract")]
    note = _inw()._deliverable_note({"text": "x", "skill": "openalex_evidence"}, uit, ("list", "hits"))
    assert "url: https://openalex.org/W1" in note


def test_openalex_is_configured_volgt_de_sleutel_en_description_is_planner_engels():
    from nooch_village.skills_impl.openalex import OpenalexSkill
    s = OpenalexSkill()
    with patch.dict("os.environ", {}, clear=True):
        assert not s.is_configured(SimpleNamespace(settings={}))
    assert s.is_configured(SimpleNamespace(settings={"OPENALEX_API_KEY": "k"}))
    kop = s.description[:160]
    assert "OpenAlex" in kop and "English term" in kop
    assert "Academische" not in s.description and "optioneel" not in s.input_schema


# ═══ 2. Semantic Scholar ═════════════════════════════════════════════════════

def _s2_paper(i, cites=10):
    return {"paperId": f"P{i}", "title": f"Paper {i}", "year": 2019, "citationCount": cites,
            "abstract": LANG, "tldr": {"text": f"tldr {i}"},
            "externalIds": {"DOI": f"10.2/{i}"}, "url": f"https://www.semanticscholar.org/paper/P{i}"}


def _s2_skill():
    from nooch_village.skills_impl.semantic_scholar import SemanticScholarSkill
    return SemanticScholarSkill()


def test_semscholar_or_keten_wordt_per_clausule_gezocht_en_verenigd():
    gezien = []

    def fake(req, timeout=None):
        gezien.append(req.full_url)
        n = len(gezien)
        return _Resp({"total": 1, "data": [_s2_paper(n, cites=n), _s2_paper(0, cites=50)]})  # P0 in beide

    with patch("urllib.request.urlopen", fake), patch("time.sleep"):
        uit = _s2_skill().run({"term": "glue-free OR adhesive-free footwear", "limit": 5},
                              SimpleNamespace(settings={}))
    assert len(gezien) == 2
    assert "query=glue%20free" in gezien[0] and "query=adhesive%20free%20footwear" in gezien[1]
    assert uit["gezocht"] == ["glue free", "adhesive free footwear"]
    assert [h["title"] for h in uit["hits"]] == ["Paper 0", "Paper 2", "Paper 1"]     # dedup + citaties
    hit = uit["hits"][0]
    assert hit["url"] == "https://www.semanticscholar.org/paper/P0" and hit["doi"] == "10.2/0"
    assert len(hit["abstract"]) > 600
    assert uit["text"].startswith("2 paper(s) on Semantic Scholar for 'glue-free OR adhesive-free footwear'")
    assert "searched 2 clauses" in uit["text"] and "top cited: “Paper 0”, 2019, 50 citations" in uit["text"]


def test_semscholar_url_uit_paperid_als_de_bron_geen_url_geeft():
    p = _s2_paper(7)
    del p["url"]
    with patch("urllib.request.urlopen", lambda req, timeout=None: _Resp({"total": 1, "data": [p]})), \
         patch("time.sleep"):
        uit = _s2_skill().run({"term": "x"}, SimpleNamespace(settings={}))
    assert uit["hits"][0]["url"] == "https://www.semanticscholar.org/paper/P7"
    t = project_verslag.inhoud_tekst(uit)
    assert "• Paper 7 (https://www.semanticscholar.org/paper/P7) — woord0" in t


def test_semscholar_drie_uitkomsten():
    with patch("urllib.request.urlopen", lambda req, timeout=None: _Resp({"total": 0, "data": []})), \
         patch("time.sleep"):
        leeg = _s2_skill().run({"term": "a OR b"}, SimpleNamespace(settings={}))
    assert leeg["no_data"] is True and Inhabitant._classify_result(leeg)[0] == "leeg"

    def kapot(req, timeout=None):
        raise _http(503, "Service Unavailable")
    with patch("urllib.request.urlopen", kapot), patch("time.sleep"):
        fout = _s2_skill().run({"term": "a OR b"}, SimpleNamespace(settings={}))
    assert "error" in fout and "503" in fout["error"] and Inhabitant._classify_result(fout)[0] == "fout"


def test_semscholar_backoff_herhaalt_5xx_en_timeout_precies_een_keer():
    s = _s2_skill()
    slaap = []
    calls = {"n": 0}

    def eerst_500(req, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise _http(500, "Internal Server Error")
        return _Resp({"data": []})

    with patch("urllib.request.urlopen", eerst_500):
        assert s._fetch_with_backoff("https://x", {}, _sleep=slaap.append) == {"data": []}
    assert calls["n"] == 2 and slaap == [2.0]

    calls["n"] = 0

    def eerst_timeout(req, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.URLError("timed out")
        return _Resp({"data": [1]})

    with patch("urllib.request.urlopen", eerst_timeout):
        assert s._fetch_with_backoff("https://x", {}, _sleep=lambda *_: None) == {"data": [1]}

    def altijd_500(req, timeout=None):
        raise _http(502, "Bad Gateway")
    with patch("urllib.request.urlopen", altijd_500):
        uit = s._fetch_with_backoff("https://x", {}, _sleep=lambda *_: None)
    assert isinstance(uit, str) and "502" in uit                              # één herhaling, dan fout

    def vierhonderd(req, timeout=None):
        calls["n"] += 1
        raise _http(404, "Not Found")
    calls["n"] = 0
    with patch("urllib.request.urlopen", vierhonderd):
        uit = s._fetch_with_backoff("https://x", {}, _sleep=lambda *_: None)
    assert "404" in uit and calls["n"] == 1                                    # geen herhaling op 4xx


def test_semscholar_429_backoff_blijft_zoals_hij_was():
    s = _s2_skill()
    slaap = []

    def altijd_429(req, timeout=None):
        raise _http(429, "Too Many Requests")
    with patch("urllib.request.urlopen", altijd_429):
        uit = s._fetch_with_backoff("https://x", {}, _sleep=slaap.append)
    assert "429" in uit and len(slaap) == 3                                    # 4 pogingen, 3 pauzes


def test_semscholar_metadata_engels():
    s = _s2_skill()
    assert "Semantic Scholar" in s.description[:160] and "English" in s.description[:160]
    assert "required" in s.input_schema and "zoekterm" not in s.input_schema


# ═══ 3. EPO OPS ══════════════════════════════════════════════════════════════

_OPS_XML = b"""<?xml version="1.0"?>
<ops:world-patent-data xmlns:ops="http://ops.epo.org" xmlns="http://www.epo.org/exchange">
  <ops:biblio-search total-result-count="3"><ops:search-result><exchange-documents>
    <exchange-document country="EP" doc-number="777" kind="A1">
      <bibliographic-data>
        <publication-reference><document-id document-id-type="docdb">
          <country>EP</country><doc-number>777</doc-number><kind>A1</kind><date>20210101</date>
        </document-id></publication-reference>
        <invention-title lang="en">Glue-free shoe</invention-title>
      </bibliographic-data>
      <abstract lang="en"><p>%s</p></abstract>
    </exchange-document>
  </exchange-documents></ops:search-result></ops:biblio-search>
</ops:world-patent-data>""" % LANG.encode()


def _epo(get):
    from nooch_village.skills_impl.epo_patents import EpoPatentsSkill
    sk = EpoPatentsSkill()
    sk._get_token = lambda ctx: "tok"
    sk._default_get = get
    return sk


def test_epo_404_en_no_results_lezen_als_no_data_niet_als_fout():
    def vierhonderdvier(url, token):
        raise _http(404, "Not Found", b"<fault><message>No results found</message></fault>")
    uit = _epo(vierhonderdvier).run({"term": "zzxq sole"}, SimpleNamespace(settings={}))
    assert uit["no_data"] is True and "error" not in uit
    assert uit["gezocht"] == 'ta="zzxq sole"' and "searched: ta=" in uit["reason"]
    assert Inhabitant._classify_result(uit)[0] == "leeg"

    def fault(url, token):
        raise RuntimeError("OPS fault SERVER.EntityNotFound: No results found")
    assert _epo(fault).run({"term": "x"}, SimpleNamespace(settings={})).get("no_data") is True


def test_epo_echte_fout_blijft_fout():
    def vijfhonderd(url, token):
        raise _http(503, "Service Unavailable")
    uit = _epo(vijfhonderd).run({"term": "x"}, SimpleNamespace(settings={}))
    assert "error" in uit and "503" in uit["error"] and Inhabitant._classify_result(uit)[0] == "fout"


def test_epo_record_met_espacenet_link_lang_abstract_en_text():
    with patch("time.sleep"):
        uit = _epo(lambda url, token: _OPS_XML).run({"term": "shoe sole"}, SimpleNamespace(settings={}))
    p = uit["patents"][0]
    assert p["url"] == "https://worldwide.espacenet.com/patent/search?q=pn%3DEP777A1"
    assert len(p["abstract"]) > 600
    assert uit["gezocht"] == 'ta="shoe sole"'
    assert uit["text"] == ("3 patent(s) via EPO OPS for 'shoe sole' (searched: ta=\"shoe sole\"); "
                           "first: “Glue-free shoe” (EP777A1, 20210101).")
    t = project_verslag.inhoud_tekst(uit)
    assert "• Glue-free shoe (https://worldwide.espacenet.com/patent/search?q=pn%3DEP777A1) — woord0" in t
    assert leesextract.te_lezen(uit, ("list", "patents")) == [(p, "abstract")]


def test_epo_or_keten_mengt_leeg_en_treffers_en_faalt_bij_storing_zonder_treffers():
    gezien = []

    def half(url, token):
        gezien.append(url)
        if len(gezien) == 1:
            raise _http(404, "Not Found")
        return _OPS_XML
    with patch("time.sleep"):
        uit = _epo(half).run({"term": "zzxq OR shoe sole"}, SimpleNamespace(settings={}))
    assert len(gezien) == 2 and len(uit["patents"]) == 1 and "error" not in uit
    assert uit["gezocht"] == 'ta="zzxq" | ta="shoe sole"'

    def stuk_en_leeg(url, token):
        gezien.append(url)
        raise _http(500 if len(gezien) % 2 else 404, "x")
    gezien.clear()
    with patch("time.sleep"):
        uit = _epo(stuk_en_leeg).run({"term": "a OR b"}, SimpleNamespace(settings={}))
    assert "error" in uit and uit["patents"] == []           # niets gevonden én iets stuk: geen 'leeg'


def test_epo_input_schema_zegt_hoe_or_werkt():
    from nooch_village.skills_impl.epo_patents import EpoPatentsSkill
    s = EpoPatentsSkill()
    assert "' OR '" in s.input_schema and "separately" in s.input_schema
    assert "EPO Open Patent Services" in s.description[:160]


# ═══ 4. Google Patents ═══════════════════════════════════════════════════════

def test_google_patents_record_met_link_en_text():
    from nooch_village.skills_impl.google_patents import GooglePatentsSkill
    sk = GooglePatentsSkill()
    sk._fetch = lambda term, limit, _get=None: {"results": {"total_num_results": 1, "cluster": [{"result": [
        {"patent": {"title": "Compostable sole", "publication_number": "US123A1",
                    "publication_date": "2024-01-01", "snippet": LANG}}]}]}}
    uit = sk.run({"term": "compostable sole"}, None)
    p = uit["patents"][0]
    assert p["url"] == "https://patents.google.com/patent/US123A1" and len(p["abstract"]) > 600
    assert uit["text"] == ("1 patent(s) on Google Patents for 'compostable sole'; first: "
                           "“Compostable sole” (US123A1, 2024-01-01).")
    assert "• Compostable sole (https://patents.google.com/patent/US123A1) — woord0" in project_verslag.inhoud_tekst(uit)


# ═══ 5. Open Library — voltekst ══════════════════════════════════════════════

_OL_HIT = {"edition": {"key": "/books/OL1M", "title": "Born to Run",
                       "authors": [{"name": "Christopher McDougall"}], "publish_year": [2009]},
           "ia": "borntorun00mcdo",
           "highlight": {"text": ["the {{{barefoot}}} runners of the Copper Canyon",
                                  "running {{{barefoot}}} on the trail"]}}


def _ol_skill():
    from nooch_village.skills_impl.openlibrary_search_inside import OpenlibrarySearchInsideSkill
    return OpenlibrarySearchInsideSkill()


class _Get:
    """Nep-requests.get: een reeks uitkomsten (dict = JSON-body, int = status, Exception = raise)."""
    def __init__(self, *uitkomsten):
        self.uitkomsten, self.gezien = list(uitkomsten), []

    def __call__(self, url, params=None, headers=None, timeout=None):
        self.gezien.append({"url": url, "params": params, "timeout": timeout})
        u = self.uitkomsten.pop(0)
        if isinstance(u, Exception):
            raise u
        status, body = (u, {}) if isinstance(u, int) else (200, u)
        return SimpleNamespace(status_code=status, reason="", text=json.dumps(body), json=lambda: body)


def test_openlibrary_bevraagt_het_search_inside_endpoint_en_parset_de_treffers():
    get = _Get({"hits": {"total": 2, "hits": [_OL_HIT, {"edition": {"key": "/books/OL2M", "title": "B"},
                                                          "highlight": {"text": ["x {{{barefoot}}} y"]}}]}})
    with patch("requests.get", get), patch("time.sleep"):
        uit = _ol_skill().run({"term": "barefoot", "limit": 5}, None)
    assert get.gezien[0]["url"] == "https://openlibrary.org/search/inside.json"
    assert get.gezien[0]["params"] == {"q": "barefoot", "limit": 5} and get.gezien[0]["timeout"] == 20
    assert uit["total"] == 2 and len(uit["hits"]) == 2 and "error" not in uit
    h = uit["hits"][0]
    assert h["title"] == "Born to Run" and h["url"] == "https://archive.org/details/borntorun00mcdo"
    assert h["tekst"] == "the barefoot runners of the Copper Canyon … running barefoot on the trail"
    assert h["authors"] == ["Christopher McDougall"] and h["year"] == 2009
    assert uit["hits"][1]["url"] == "https://openlibrary.org/books/OL2M"       # geen ia → de editie
    assert uit["text"].startswith("2 book(s) with 'barefoot' in their full text")
    assert "• Born to Run (https://archive.org/details/borntorun00mcdo) — the barefoot runners" in \
        project_verslag.inhoud_tekst(uit)
    assert Inhabitant._classify_result(uit) == ("gelukt", ("list", "hits"))


@pytest.mark.parametrize("data", [
    {}, {"hits": None}, {"hits": []}, {"hits": {"hits": "geen lijst"}},
    {"hits": {"total": "veel", "hits": [None, 3, {"edition": "x", "highlight": {"text": "geen lijst"}}]}},
    {"hits": {"hits": [{"edition": {"title": "T", "authors": "niet een lijst", "publish_year": "onbekend"},
                        "highlight": None}]}},
    {"hits": {"hits": [{"edition": {"title": "T", "publish_date": "March 2011"}, "ia": ["eerste", "tweede"],
                        "highlight": {"text": ["x"]}}]}},
])
def test_openlibrary_parse_is_defensief(data):
    from nooch_village.skills_impl.openlibrary_search_inside import parse_hits
    total, records = parse_hits(data)
    assert isinstance(total, int) and isinstance(records, list)
    for r in records:
        assert set(r) == {"source", "title", "url", "tekst", "authors", "year"}
        assert isinstance(r["authors"], list) and (r["year"] is None or isinstance(r["year"], int))
        assert isinstance(r["url"], str) and "[" not in r["url"]
    if records and data["hits"]["hits"][0].get("ia") == ["eerste", "tweede"]:
        assert records[0]["url"] == "https://archive.org/details/eerste" and records[0]["year"] == 2011


def test_openlibrary_nul_treffers_is_no_data_en_storing_is_error():
    with patch("requests.get", _Get({"hits": {"total": 0, "hits": []}})), patch("time.sleep"):
        leeg = _ol_skill().run({"term": "zzxq"}, None)
    assert leeg["no_data"] is True and "zzxq" in leeg["reason"]
    assert Inhabitant._classify_result(leeg)[0] == "leeg"                     # gemeld, geen kennisgat

    import requests
    get = _Get(requests.exceptions.Timeout("t"), requests.exceptions.ConnectionError("c"))
    with patch("requests.get", get), patch("time.sleep"):
        fout = _ol_skill().run({"term": "x"}, None)
    assert "error" in fout and "niet bereikbaar" in fout["error"] and len(get.gezien) == 2   # één herhaling
    assert Inhabitant._classify_result(fout)[0] == "fout"


def test_openlibrary_herhaalt_een_keer_na_timeout_of_5xx():
    import requests
    ok = {"hits": {"total": 1, "hits": [_OL_HIT]}}
    get = _Get(requests.exceptions.Timeout("t"), ok)
    with patch("requests.get", get), patch("time.sleep"):
        assert _ol_skill().run({"term": "barefoot"}, None)["total"] == 1
    get = _Get(503, ok)
    with patch("requests.get", get), patch("time.sleep"):
        assert _ol_skill().run({"term": "barefoot"}, None)["total"] == 1 and len(get.gezien) == 2
    get = _Get(404)
    with patch("requests.get", get), patch("time.sleep"):
        uit = _ol_skill().run({"term": "barefoot"}, None)
    assert "error" in uit and "404" in uit["error"] and len(get.gezien) == 1


def test_openlibrary_belofte_is_overal_dezelfde():
    from nooch_village import skill_labels
    from nooch_village.skills_impl.zoekstrategie import BRONNEN
    s = _ol_skill()
    assert "Full-text search inside" in s.description[:160]
    assert "inside scanned books" in BRONNEN["openlibrary_search_inside"]
    assert "full text" in skill_labels.LABELS["openlibrary_search_inside"].lower()
    from nooch_village.skills_impl import openlibrary_search_inside as mod
    assert mod._ENDPOINT == "https://openlibrary.org/search/inside.json"       # de voltekst, niet de catalogus


# ═══ 6. Ngram — topniveau fail-closed, strekking per rij ═════════════════════

def _ng():
    from nooch_village.skills_impl.ngram import NgramCultureSkill
    return NgramCultureSkill()


def _reeks(stijgend=True):
    """40 jaar (1980-2019). Stijgend: exponentieel, de recente helling ligt ruim boven de 5%-drempel.
    Dalend: dertig jaar plateau en dan tien jaar 10% per jaar omlaag (de piek ligt dus in 1980)."""
    if stijgend:
        return [1e-7 * 1.2 ** i for i in range(40)]
    return [1.2e-4] * 30 + [1.2e-4 * 0.9 ** (i + 1) for i in range(10)]


def test_ngram_alles_stuk_is_error_niets_gevonden_is_no_data():
    def stuk(*a, **k):
        raise urllib.error.URLError("timed out")
    with patch("nooch_village.skills_impl.ngram._fetch_ngram", stuk), patch("nooch_village.skills_impl.ngram.time.sleep"):
        fout = _ng().run({"terms": ["vegan", "leather"]}, None)
    assert "error" in fout and "2 van 2" in fout["error"] and "timed out" in fout["error"]
    assert all(r.get("error") and not r.get("no_data") for r in fout["rows"])   # rows blijven voor de Wachter
    assert Inhabitant._classify_result(fout)[0] == "fout"

    with patch("nooch_village.skills_impl.ngram._fetch_ngram", return_value=[]), \
         patch("nooch_village.skills_impl.ngram.time.sleep"):
        leeg = _ng().run({"terms": ["zzxq"]}, None)
    assert leeg["no_data"] is True and "corpus" in leeg["reason"] and len(leeg["rows"]) == 1
    assert Inhabitant._classify_result(leeg)[0] == "leeg"


def test_ngram_mix_is_gelukt_met_strekking_per_rij_en_text():
    raw = [{"ngram": "vegan (All)", "timeseries": _reeks(True)},
           {"ngram": "vegan", "timeseries": [0.0] * 40},                   # de losse variant telt niet
           {"ngram": "leather (All)", "timeseries": _reeks(False)}]
    with patch("nooch_village.skills_impl.ngram._fetch_ngram", return_value=raw), \
         patch("nooch_village.skills_impl.ngram.time.sleep"):
        uit = _ng().run({"terms": ["vegan", "leather", "zzxq"], "locale": "en", "year_start": 1980}, None)
    assert "error" not in uit and not uit.get("no_data")
    assert Inhabitant._classify_result(uit) == ("gelukt", ("list", "rows"))
    rij = {r["term"]: r for r in uit["rows"]}
    assert rij["vegan"]["signal"]["direction"] == "stijgend"
    assert rij["vegan"]["tekst"] == "rising over 2010–2019; last 1.2e-04, peak 1.2e-04 in 2019"
    assert rij["leather"]["tekst"] == "falling over 2010–2019; last 4.2e-05, peak 1.2e-04 in 1980"
    assert rij["zzxq"]["no_data"] is True
    assert uit["text"] == ("2 of 3 term(s) found in Google Books Ngram (corpus 26, 1980–%d): "
                           "rising — vegan; falling — leather; not in corpus — zzxq." % uit["year_end"])
    t = project_verslag.inhoud_tekst(uit)
    assert t.splitlines()[0].startswith("2 of 3 term(s) found")
    assert "• vegan — rising over 2010–2019" in t                            # de richting haalt het verslag


def test_ngram_stuurt_case_insensitive_mee_en_neemt_locale_of_corpus_uit_de_payload():
    gezien = []

    def fake(req, timeout=None):
        gezien.append(req.full_url)
        return _Resp([])
    with patch("urllib.request.urlopen", fake), patch("nooch_village.skills_impl.ngram.time.sleep"):
        _ng().run({"terms": ["barefoot"], "locale": "nl"}, None)             # geen indicatorwoord, tóch NL
        _ng().run({"terms": ["schoenen"], "corpus": 26}, None)               # corpus wint van de detectie
        _ng().run({"terms": ["schoenen"]}, None)                             # zonder aanwijzing: detectie
    assert "case_insensitive=true" in gezien[0]
    assert "corpus=10" in gezien[0] and "corpus=26" in gezien[1] and "corpus=10" in gezien[2]


def test_ngram_metadata_zegt_taal_en_lengte():
    s = _ng()
    assert "locale" in s.input_schema and "5 words" in s.input_schema
    assert "Google Books Ngram" in s.description[:160]


# ═══ 7. web_zoek en lead_beoordeling — één wachtbudget per run ═══════════════

def _budget_recorder(monkeypatch, tekst="pagina " * 100):
    gezien = []

    def haal(url, *, budget=None, **kw):
        gezien.append(budget)
        return {"url": url, "status": 200, "titel": "t", "tekst": tekst}
    monkeypatch.setattr(safe_fetch, "haal_tekst_geduldig", haal)
    return gezien


def test_web_zoek_leest_alle_paginas_met_een_wachtbudget_per_run(monkeypatch):
    from nooch_village.skills_impl.web_zoek import WebZoekSkill, _WACHTBUDGET_S
    gezien = _budget_recorder(monkeypatch)
    treffers = [{"title": f"T{i}", "link": f"https://s{i}.example/", "snippet": "s"} for i in range(3)]
    s = WebZoekSkill(zoek=lambda term, key, num=10, gl="", hl="": treffers)
    ctx = SimpleNamespace(settings={"SERPAPI_API_KEY": "k"})
    uit = s.run({"term": "t"}, ctx)
    assert uit["gelezen"] == 3
    assert len(gezien) == 3 and all(isinstance(b, safe_fetch.Wachtbudget) for b in gezien)
    assert len({id(b) for b in gezien}) == 1 and gezien[0].over == _WACHTBUDGET_S    # één budget, gedeeld
    uit2 = s.run({"term": "t"}, ctx)
    assert id(gezien[-1]) != id(gezien[0])                                          # per run een nieuw


def test_lead_beoordeling_leest_met_wachtbudget(monkeypatch):
    from nooch_village.skills_impl.lead_beoordeling import LeadBeoordelingSkill
    gezien = _budget_recorder(monkeypatch)
    s = LeadBeoordelingSkill(zoek=None, reason_fn=lambda *a, **k: json.dumps(
        {"what_is_this": "a shop", "criteria": [], "fit": "low", "why": "w", "next_step": "discard", "quote": ""}))
    uit = s.run({"naam": "x", "url": "https://x.example/"}, SimpleNamespace(settings={}))
    assert uit["ok"] is True and len(gezien) == 1 and isinstance(gezien[0], safe_fetch.Wachtbudget)


def test_lead_beoordeling_eerste_record_draagt_naam_en_adres_voor_het_verslag():
    from nooch_village.skills_impl.lead_beoordeling import LeadBeoordelingSkill
    s = LeadBeoordelingSkill(zoek=None, haal=lambda url: {"url": url, "titel": "Kiilto", "tekst": "Kiilto makes glue. " * 20},
                             reason_fn=lambda *a, **k: json.dumps(
                                 {"what_is_this": "Finnish adhesive maker (manufacturer)",
                                  "criteria": [{"criterion": "plastic-free", "verdict": "yes",
                                                "quote": "Kiilto makes glue."}],
                                  "fit": "medium", "why": "w", "next_step": "read_more",
                                  "quote": "Kiilto makes glue."}))
    uit = s.run({"naam": "Kiilto", "url": "https://kiilto.com/"}, SimpleNamespace(settings={}))
    eerste = uit["beoordeling"][0]
    assert eerste["naam"] == "Kiilto" and eerste["url"] == "https://kiilto.com/"
    t = project_verslag.inhoud_tekst(uit)
    assert "• Kiilto (https://kiilto.com/) — Finnish adhesive maker (manufacturer)" in t
    assert "• plastic-free — yes — “Kiilto makes glue.”" in t


# ═══ 8. haal_pagina en safe_fetch ════════════════════════════════════════════

_FAQ = {"url": "https://nooch.earth/pages/faq", "status": 200, "titel": "FAQ — Nooch",
        "tekst": "FAQ — Nooch\nWaar zijn de schoenen van gemaakt?\nOnze materialen zijn natural en "
                 "plantaardig.\nWe gebruiken geen leer.\n"}


def test_haal_pagina_lege_pagina_is_no_data_niet_gelukt_met_de_url_als_inhoud():
    from nooch_village.skills_impl.haal_pagina import HaalPaginaSkill
    leeg = dict(_FAQ, tekst="   ")
    uit = HaalPaginaSkill(haal=lambda *_a, **_k: dict(leeg)).run({"url": _FAQ["url"]})
    assert uit["no_data"] is True and "leesbare tekst" in uit["reason"] and "error" not in uit
    assert Inhabitant._classify_result(uit)[0] == "leeg"
    uit = HaalPaginaSkill(haal=lambda *_a, **_k: dict(leeg)).run({"url": _FAQ["url"], "term": "natural"})
    assert uit["no_data"] is True                                              # ook mét term


def test_haal_pagina_treffers_dragen_titel_url_en_fragment_en_er_is_een_text():
    from nooch_village.skills_impl.haal_pagina import HaalPaginaSkill
    uit = HaalPaginaSkill(haal=lambda *_a, **_k: dict(_FAQ)).run({"url": _FAQ["url"], "term": "natural"})
    t = uit["treffers"][0]
    assert t["titel"] == "FAQ — Nooch" and t["url"] == _FAQ["url"]
    assert t["fragment"] == ("FAQ — Nooch · Waar zijn de schoenen van gemaakt? · Onze materialen zijn "
                             "natural en plantaardig. · We gebruiken geen leer.")
    assert uit["text"] == ("FAQ — Nooch (nooch.earth): 1 line(s) with 'natural'; first: “Onze materialen "
                           "zijn natural en plantaardig.”.")
    assert Inhabitant._classify_result(uit) == ("gelukt", ("list", "treffers"))
    verslag = project_verslag.inhoud_tekst(uit)
    assert verslag.splitlines()[0].startswith("FAQ — Nooch (nooch.earth): 1 line(s)")
    assert "• FAQ — Nooch (https://nooch.earth/pages/faq) — FAQ — Nooch · Waar zijn de schoenen" in verslag
    note = _inw()._deliverable_note({"text": "faq", "skill": "haal_pagina"}, uit, ("list", "treffers"))
    assert "titel: FAQ — Nooch" in note and "regel: Onze materialen zijn natural" in note


def test_safe_fetch_laat_alleen_tekst_door_de_stripper():
    with pytest.raises(safe_fetch.FetchMislukt) as e:
        safe_fetch.haal_tekst("https://nooch.earth/x.pdf", _fetch=lambda u: (200, "%PDF-1.4 binaire ruis", "application/pdf"))
    assert "application/pdf" in str(e.value) and e.value.status == 200
    assert not safe_fetch.is_tijdelijk(e.value)                                 # geen retry op een PDF
    ok = safe_fetch.haal_tekst("https://nooch.earth/", _fetch=lambda u: (200, "<title>T</title><p>tekst</p>",
                                                                          "text/html; charset=utf-8"))
    assert ok["titel"] == "T" and "tekst" in ok["tekst"]
    assert safe_fetch.haal_tekst("https://nooch.earth/", _fetch=lambda u: (200, "<p>x</p>"))["tekst"]  # zonder type: door
    assert safe_fetch.haal_tekst("https://nooch.earth/", _fetch=lambda u: (200, "plat", "text/plain"))["tekst"] == "plat"


def test_haal_pagina_meldt_een_pdf_als_permanente_fout():
    from nooch_village.skills_impl.haal_pagina import HaalPaginaSkill
    def pdf(url, **_k):
        return safe_fetch.haal_tekst(url, _fetch=lambda u: (200, "%PDF", "application/pdf"))
    uit = HaalPaginaSkill(haal=pdf).run({"url": "https://nooch.earth/gids.pdf"})
    assert "error" in uit and uit["tijdelijk"] is False and "application/pdf" in uit["error"]


# ═══ 9. zoekstrategie — alleen plannbare bronnen ═════════════════════════════

def test_zoekstrategie_biedt_alleen_bronnen_aan_die_in_een_rugzak_zitten():
    from nooch_village.skills_impl.zoekstrategie import BRONNEN
    with open("config/rugzakken.json", encoding="utf-8") as f:
        rz = json.load(f)
    plannbaar = {s for k, v in rz.items() if isinstance(v, dict) for s in (v.get("skills") or [])}
    assert set(BRONNEN) <= plannbaar, sorted(set(BRONNEN) - plannbaar)
    assert "google_patents" not in BRONNEN and "semscholar_tldr" not in BRONNEN
    assert "Semantic Scholar" in BRONNEN["openalex_evidence"] and "Google Patents" in BRONNEN["epo_patents"]


# ═══ 10. onderzoeksvraag en ruis_check — classificatie ═══════════════════════

def test_onderzoeksvraag_drie_uitkomsten_classificeren_verschillend():
    from nooch_village.skills_impl.onderzoeksvraag import OnderzoeksvraagSkill
    def _run(antwoord):
        with patch("nooch_village.llm.reason", return_value=antwoord):
            return OnderzoeksvraagSkill().run({"word": "barefoot shoes", "claim": "rising"}, None)
    assert Inhabitant._classify_result(_run(None))[0] == "fout"
    assert Inhabitant._classify_result(_run('{"question": null}'))[0] == "leeg"
    goed = _run('{"question": "Which biomechanical benefits drive the uptake of barefoot shoes?"}')
    assert Inhabitant._classify_result(goed) == ("gelukt", ("text", "vraag"))
    assert project_verslag.inhoud_tekst(goed) == "Which biomechanical benefits drive the uptake of barefoot shoes?"


def test_ruis_check_accepteert_een_getal_met_decimaal_of_exponent():
    from nooch_village.skills_impl.ruis_check import RuisCheckSkill
    s = RuisCheckSkill()
    assert s.run({"query": "q", "aantal": "5000.0"}, None)["status"] == "bruikbaar"
    assert s.run({"query": "q", "aantal": "5e3"}, None)["aantal"] == 5000
    assert s.run({"query": "q", "aantal": 5001.7}, None)["status"] == "te_breed"
    assert "error" in s.run({"query": "q", "aantal": "veel"}, None)
