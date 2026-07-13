"""EPO OPS patent-skill (XML-interface): OAuth-token (cache/fail-closed), OPS-XML-parse, lijst-archetype,
fail-soft (0 patenten / 403). Geen netwerk (fetch/post geïnjecteerd), geen credential-waarden in de test."""
from __future__ import annotations
import pytest
from types import SimpleNamespace
from unittest.mock import patch

from nooch_village.skills_impl.epo_patents import EpoPatentsSkill
from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus
from nooch_village.skills import SkillRegistry


def _ctx(**kw):
    s = {"EPO_CONSUMER_KEY": "k", "EPO_CONSUMER_SECRET": "s"}
    s.update(kw)
    return SimpleNamespace(settings=s)


def _inh():
    rec = Record(id="rol", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="p", accountabilities=[], domains=[], skills=[]), source="seed")
    return Inhabitant(rec, EventBus(name="t"), SkillRegistry(), SimpleNamespace(settings={"reflect_interval_seconds": "0"}))


# Realistische OPS-search/biblio-XML (namespaces zoals de officiële structuur).
_OPS_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<ops:world-patent-data xmlns:ops="http://ops.epo.org" xmlns="http://www.epo.org/exchange">
  <ops:biblio-search total-result-count="42">
    <ops:search-result>
      <exchange-documents>
        <exchange-document country="US" doc-number="1234567" kind="A1" family-id="99">
          <bibliographic-data>
            <publication-reference>
              <document-id document-id-type="docdb">
                <country>US</country><doc-number>1234567</doc-number><kind>A1</kind><date>20200101</date>
              </document-id>
            </publication-reference>
            <invention-title lang="de">Barfussschuh</invention-title>
            <invention-title lang="en">Barefoot shoe</invention-title>
            <parties>
              <applicants>
                <applicant data-format="docdb"><applicant-name><name>VIVOBAREFOOT LTD</name></applicant-name></applicant>
                <applicant data-format="epodoc"><applicant-name><name>Vivobarefoot [GB]</name></applicant-name></applicant>
              </applicants>
              <inventors>
                <inventor data-format="docdb"><inventor-name><name>SMITH JOHN</name></inventor-name></inventor>
              </inventors>
            </parties>
          </bibliographic-data>
          <abstract lang="en"><p>A shoe that mimics barefoot walking.</p></abstract>
        </exchange-document>
      </exchange-documents>
    </ops:search-result>
  </ops:biblio-search>
</ops:world-patent-data>"""

_OPS_XML_EMPTY = b"""<?xml version="1.0"?>
<ops:world-patent-data xmlns:ops="http://ops.epo.org">
  <ops:biblio-search total-result-count="0"><ops:search-result/></ops:biblio-search>
</ops:world-patent-data>"""


# ── a. auth ─────────────────────────────────────────────────────────────────────
def test_a_token_uit_creds_en_cache():
    sk = EpoPatentsSkill()
    posts = []
    def _post(url, data, headers):
        posts.append(headers); return {"access_token": "TOK", "expires_in": 1200}
    assert sk._get_token(_ctx(), _post=_post) == "TOK"
    assert posts[0]["Authorization"].startswith("Basic ")
    def _boom(*a):
        raise AssertionError("cache miste — geen tweede token-call verwacht")
    assert sk._get_token(_ctx(), _post=_boom) == "TOK"


def test_a_ontbrekende_creds_failclosed():
    sk = EpoPatentsSkill()
    ctx = SimpleNamespace(settings={})
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(RuntimeError, match="ontbreekt"):
            sk._get_token(ctx, _post=lambda *a: {"access_token": "x"})
        r = sk.run({"term": "x"}, ctx)
    assert r.get("error") and r["patents"] == []


def test_a_secret_key_alias_geaccepteerd():
    sk = EpoPatentsSkill()
    ctx = SimpleNamespace(settings={"EPO_CONSUMER_KEY": "k", "EPO_CONSUMER_SECRET_KEY": "s"})
    assert sk.is_configured(ctx)
    assert sk._get_token(ctx, _post=lambda *a: {"access_token": "T", "expires_in": 10}) == "T"


# ── b/c. XML-parse → velden correct uit de OPS-XML ──────────────────────────────
def test_c_xml_parse_velden():
    total, patents = EpoPatentsSkill._parse_patents(_OPS_XML)
    assert total == 42 and len(patents) == 1
    p = patents[0]
    assert p["title"] == "Barefoot shoe"                            # en-titel geprefereerd
    assert p["publication_number"] == "US1234567A1"
    assert p["publication_date"] == "20200101"
    assert "barefoot walking" in p["abstract"]
    assert p["applicants"] == ["Vivobarefoot [GB]"]                 # epodoc-voorkeur (leesbare naam)
    assert p["inventors"] == ["SMITH JOHN"]                         # geen epodoc → terugval op alle formats


def test_b_search_en_run(monkeypatch):
    sk = EpoPatentsSkill()
    seen = {}
    monkeypatch.setattr(sk, "_get_token", lambda ctx: "tok")
    def _fake_get(url, token):
        seen["url"] = url
        return _OPS_XML
    monkeypatch.setattr(sk, "_default_get", _fake_get)
    # _search bouwt de URL (q + Range) en parset de XML
    r = sk.run({"term": "barefoot shoes", "limit": 5}, _ctx())
    assert 'q=ti%3D%22barefoot%20shoes%22' in seen["url"] and "Range=1-5" in seen["url"]   # titel-frase-CQL
    assert r["total"] == 42 and len(r["patents"]) == 1 and r["patents"][0]["title"] == "Barefoot shoe"


# ── d. lijst-archetype → note-formatter toont eigen velden per patent ────────────
def test_d_archetype_en_note():
    result = {"total": 1, "patents": [{"title": "Barefoot shoe", "publication_number": "US1A1",
                                       "publication_date": "20200101", "applicants": ["Vivo"]}]}
    assert Inhabitant._classify_result(result) == ("gelukt", ("list", "patents"))
    note = _inh()._deliverable_note({"text": "patenten", "skill": "epo_patents"}, result, ("list", "patents"))
    assert "Barefoot shoe" in note and "publication_date: 20200101" in note and "Vivo" in note


# ── e. fail-soft: 0 patenten (echte observatie) / 403 → gat + error ──────────────
def test_e_lege_set_nul_patenten(monkeypatch):
    sk = EpoPatentsSkill()
    monkeypatch.setattr(sk, "_get_token", lambda ctx: "tok")
    monkeypatch.setattr(sk, "_default_get", staticmethod(lambda url, token: _OPS_XML_EMPTY))
    r = sk.run({"term": "zzxq"}, _ctx())
    assert r["total"] == 0 and r["patents"] == [] and r.get("no_data")
    assert Inhabitant._classify_result(r)[0] == "leeg"


def test_e_search_403_gat_error(monkeypatch):
    sk = EpoPatentsSkill()
    monkeypatch.setattr(sk, "_get_token", lambda ctx: "tok")
    def _boom(*a):
        raise RuntimeError("HTTP 403 fair-use")
    monkeypatch.setattr(sk, "_search", _boom)
    r = sk.run({"term": "x"}, _ctx())
    assert r.get("error") and "403" in r["error"] and r["patents"] == []
    assert Inhabitant._classify_result(r)[0] == "fout"


# ── f. capability zichtbaar + metadata ──────────────────────────────────────────
def test_f_available_metrics_en_metadata():
    sk = EpoPatentsSkill()
    assert sk.available_metrics() == ["patents"]
    assert sk.cost == "rate_limited" and "term" in sk.input_schema and "patents" in sk.output_schema


# ── g. query-normalisatie: complexe boolean-string → kernfrase (CQL breekt anders → 404) ──────────
def test_g_normalize_term():
    n = EpoPatentsSkill._normalize_term
    assert n("barefoot shoes biodegradable sole OR barefoot shoes compostable sole") \
        == "barefoot shoes biodegradable sole"                      # eerste OR-clausule
    got = n('"ISO 4649" AND ("PHA" OR "polyhydroxyalkanoate")')
    assert all(x not in got for x in ('"', "(", ")", " OR ", " AND "))   # operators/quotes/haakjes weg
    assert "ISO 4649" in got and "PHA" in got
    assert n("barefoot shoes") == "barefoot shoes"                  # simpel blijft simpel
    assert n('"only quotes"') == "only quotes"                      # leeg-na-normalisatie-fallback


# ── h. CQL-vorm: ≤2 woorden = exacte titel-frase; ≥3 woorden = ti any (frase 404't anders) ─────────
def test_h_lange_query_gebruikt_ti_any(monkeypatch):
    sk = EpoPatentsSkill()
    seen = {}
    monkeypatch.setattr(sk, "_get_token", lambda ctx: "tok")
    monkeypatch.setattr(sk, "_default_get",
                        lambda url, token: (seen.__setitem__("url", url), _OPS_XML)[1])
    sk.run({"term": '"barefoot shoes" biodegradable sole OR compostable', "limit": 3}, _ctx())
    assert "ti%20any%20" in seen["url"] and "ti%3D%22" not in seen["url"]   # ti any "…", geen exacte frase
