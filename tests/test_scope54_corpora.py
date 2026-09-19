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






