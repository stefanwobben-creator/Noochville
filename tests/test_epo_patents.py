"""EPO OPS patent-skill: OAuth-token (cache/fail-closed), search+biblio-parsing, lijst-archetype-output,
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


_SEARCH_JSON = {"ops:world-patent-data": {"ops:biblio-search": {
    "@total-result-count": "42",
    "ops:search-result": {"ops:publication-reference": [
        {"document-id": {"@document-id-type": "docdb",
                         "country": {"$": "US"}, "doc-number": {"$": "1234567"}, "kind": {"$": "A1"}}}]}}}}

_BIBLIO_JSON = {"ops:world-patent-data": {"exchange-documents": {"exchange-document": {
    "bibliographic-data": {
        "invention-title": [{"@lang": "de", "$": "Barfussschuh"}, {"@lang": "en", "$": "Barefoot shoe"}],
        "publication-reference": {"document-id": {"@document-id-type": "docdb", "country": {"$": "US"},
                                  "doc-number": {"$": "1234567"}, "kind": {"$": "A1"}, "date": {"$": "20200101"}}},
        "parties": {"applicants": {"applicant": {"applicant-name": {"name": {"$": "Vivobarefoot Ltd"}}}}}},
    "abstract": [{"@lang": "en", "p": {"$": "A shoe that mimics barefoot walking."}}]}}}}


# ── a. auth ─────────────────────────────────────────────────────────────────────
def test_a_token_uit_creds_en_cache():
    sk = EpoPatentsSkill()
    posts = []
    def _post(url, data, headers):
        posts.append(headers); return {"access_token": "TOK", "expires_in": 1200}
    assert sk._get_token(_ctx(), _post=_post) == "TOK"
    assert posts[0]["Authorization"].startswith("Basic ")           # Basic-auth met key:secret
    def _boom(*a):
        raise AssertionError("cache miste — mag geen tweede token-call doen")
    assert sk._get_token(_ctx(), _post=_boom) == "TOK"              # gecachet


def test_a_ontbrekende_creds_failclosed():
    sk = EpoPatentsSkill()
    ctx = SimpleNamespace(settings={})
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(RuntimeError, match="ontbreekt"):
            sk._get_token(ctx, _post=lambda *a: {"access_token": "x"})
        r = sk.run({"term": "x"}, ctx)
    assert r.get("error") and r["patents"] == []                    # geen kale call, geen crash


def test_a_secret_key_alias_geaccepteerd():
    sk = EpoPatentsSkill()
    ctx = SimpleNamespace(settings={"EPO_CONSUMER_KEY": "k", "EPO_CONSUMER_SECRET_KEY": "s"})
    assert sk.is_configured(ctx)                                    # .env-naam EPO_CONSUMER_SECRET_KEY werkt
    assert sk._get_token(ctx, _post=lambda *a: {"access_token": "T", "expires_in": 10}) == "T"


# ── b. query → lijst met verwachte velden ───────────────────────────────────────
def test_b_search_parst_refs():
    total, refs = EpoPatentsSkill()._search("tok", 'ti="x"', 5, _get=lambda u: _SEARCH_JSON)
    assert total == 42 and refs == ["US.1234567.A1"]


def test_b_biblio_parst_velden():
    rec = EpoPatentsSkill()._biblio("tok", "US.1234567.A1", _get=lambda u: _BIBLIO_JSON)
    assert rec["title"] == "Barefoot shoe"                          # en-titel geprefereerd
    assert rec["publication_number"] == "US1234567A1"
    assert rec["publication_date"] == "20200101"
    assert "barefoot walking" in rec["abstract"]
    assert rec["applicants"] == ["Vivobarefoot Ltd"]


def test_b_run_levert_lijst(monkeypatch):
    sk = EpoPatentsSkill()
    seen = {}
    monkeypatch.setattr(sk, "_get_token", lambda ctx: "tok")
    monkeypatch.setattr(sk, "_search", lambda tok, cql, limit: seen.update(cql=cql) or (2, ["US.1.A1", "US.2.A1"]))
    monkeypatch.setattr(sk, "_biblio", lambda tok, ref: {"title": f"Patent {ref}", "publication_number": ref,
                                                         "publication_date": "20200101"})
    r = sk.run({"term": "barefoot shoes"}, _ctx())
    assert seen["cql"] == 'ti="barefoot shoes"'                     # zoekt op titel-frase
    assert r["total"] == 2 and len(r["patents"]) == 2 and r["patents"][0]["title"] == "Patent US.1.A1"


# ── c. lijst-archetype → note-formatter toont eigen velden per patent ────────────
def test_c_archetype_en_note():
    result = {"total": 1, "patents": [{"title": "Barefoot shoe", "publication_number": "US1A1",
                                       "publication_date": "20200101", "applicants": ["Vivo"]}]}
    assert Inhabitant._classify_result(result) == ("gelukt", ("list", "patents"))
    note = _inh()._deliverable_note({"text": "patenten", "skill": "epo_patents"}, result, ("list", "patents"))
    assert "Barefoot shoe" in note and "publication_date: 20200101" in note and "Vivo" in note


# ── d. fail-soft: 0 patenten (echte observatie) / 403 → gat + error ──────────────
def test_d_lege_set_nul_patenten(monkeypatch):
    sk = EpoPatentsSkill()
    monkeypatch.setattr(sk, "_get_token", lambda ctx: "tok")
    monkeypatch.setattr(sk, "_search", lambda *a: (0, []))
    r = sk.run({"term": "zzxq"}, _ctx())
    assert r["total"] == 0 and r["patents"] == [] and r.get("no_data")
    assert Inhabitant._classify_result(r)[0] == "leeg"             # → item blijft open, geen fout


def test_d_search_403_gat_error(monkeypatch):
    sk = EpoPatentsSkill()
    monkeypatch.setattr(sk, "_get_token", lambda ctx: "tok")
    def _boom(*a):
        raise RuntimeError("HTTP 403 fair-use")
    monkeypatch.setattr(sk, "_search", _boom)
    r = sk.run({"term": "x"}, _ctx())
    assert r.get("error") and "403" in r["error"] and r["patents"] == []
    assert Inhabitant._classify_result(r)[0] == "fout"


# ── e. capability zichtbaar + cost/schema gedeclareerd ──────────────────────────
def test_e_available_metrics_en_metadata():
    sk = EpoPatentsSkill()
    assert sk.available_metrics() == ["patents"]
    assert sk.cost == "rate_limited" and "term" in sk.input_schema and "patents" in sk.output_schema
