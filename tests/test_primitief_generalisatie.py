"""Primitief-generalisatie (optie C): prep-LLM krijgt input_schema's → payload per familie
(term / kw-lijst / brands-lijst); status-normalisatie over beide fail-conventies; note-opmaak per
archetype (lijst / tekst / metriek) met de eigen velden van elk record. Thread-vrij."""
from __future__ import annotations
import pytest
from types import SimpleNamespace

from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus
from nooch_village.skills import SkillRegistry, Skill
from nooch_village.projects import ProjectLedger

TODAY = "2026-07-08"


class _KwSkill(Skill):
    name = "keywords_everywhere"; description = "keyword-volumes"; input_schema = "kw: list[str] (keywords)"
    cost = "credits"
    def run(self, payload, context):
        self.last = payload
        return {"keywords": {"barefoot shoes": {"vol": 1000, "cpc": 0.5, "competition": 0.3}}}


class _BrandSkill(Skill):
    name = "competitor_discover"; description = "concurrenten"; input_schema = "brands: list[str], limit: int"
    cost = "credits"
    def run(self, payload, context):
        self.last = payload
        return {"ok": True, "candidates": [{"brand": "Vivobarefoot", "article": "launch", "link": "http://x"}]}


class _TermSkill(Skill):
    name = "openalex_evidence"; description = "studies"; input_schema = "term: str"
    cost = "rate_limited"
    def run(self, payload, context):
        self.last = payload
        return {"total": 2, "hits": [{"title": "Study on barefoot", "year": 2021, "citations": 7,
                                      "abstract": "biomechanics", "source": "openalex"}]}


def _inhabitant(tmp_path, ledger, skills, dna):
    reg = SkillRegistry()
    for s in skills:
        reg.register(s)
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0"}, data_dir=str(tmp_path),
                          projects=ledger, records=None)
    rec = Record(id="rol", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="p", accountabilities=["a by x, delivering y"],
                                           domains=[], skills=list(dna)), source="sensed")
    return Inhabitant(rec, EventBus(name="t"), reg, ctx)


@pytest.fixture
def ledger(tmp_path):
    return ProjectLedger(str(tmp_path / "projects.json"))


def _prep(ledger, pid, items):
    cl = ledger.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE)
    for text, skill, payload in items:
        ledger.check_add(pid, cl["id"], text, skill=skill, payload=payload)
    return cl


# a. prep-LLM krijgt de input_schema's mee (zodat hij de juiste payload-vorm kan genereren)
def test_a_prep_prompt_bevat_input_schemas(tmp_path, ledger, monkeypatch):
    import nooch_village.llm as llm
    seen = {}
    def fake_reason(prompt, **k):
        seen["prompt"] = prompt
        return ('{"deliverable":"d","items":[{"text":"volumes","skill":"keywords_everywhere",'
                '"payload":{"kw":["barefoot shoes"]},"reason":""}]}')
    monkeypatch.setattr(llm, "reason", fake_reason)
    inh = _inhabitant(tmp_path, ledger, [_KwSkill(), _TermSkill()], ["keywords_everywhere", "openalex_evidence"])
    pid = ledger.create("rol", "doel", "human", status="future")
    inh.prepare_project(pid)
    assert "kw: list[str]" in seen["prompt"] and "term: str" in seen["prompt"]   # schema's in de prompt
    it = inh._project_checklist(ledger.get(pid))["items"][0]
    assert it["payload"] == {"kw": ["barefoot shoes"]}                            # LLM-payload opgeslagen


# b. keywords_everywhere-item → skill krijgt {kw:[...]}, NIET {term}
def test_b_kw_payload_juist_doorgegeven(tmp_path, ledger):
    kw = _KwSkill()
    inh = _inhabitant(tmp_path, ledger, [kw], ["keywords_everywhere"])
    pid = ledger.create("rol", "doel", "human", status="queued")
    _prep(ledger, pid, [("volumes", "keywords_everywhere", {"kw": ["barefoot shoes"]})])
    inh._execute_checklist(ledger.get(pid), TODAY)
    assert kw.last == {"kw": ["barefoot shoes"]}                                  # geen {term}!
    assert inh._project_checklist(ledger.get(pid))["items"][0]["done"] is True    # afgevinkt


# c. competitor_discover-item → skill krijgt {brands:[...]}
def test_c_brands_payload_juist_doorgegeven(tmp_path, ledger):
    br = _BrandSkill()
    inh = _inhabitant(tmp_path, ledger, [br], ["competitor_discover"])
    pid = ledger.create("rol", "doel", "human", status="queued")
    _prep(ledger, pid, [("concurrenten", "competitor_discover", {"brands": ["Nooch"], "limit": 4})])
    inh._execute_checklist(ledger.get(pid), TODAY)
    assert br.last == {"brands": ["Nooch"], "limit": 4}
    log = " ".join(e["text"] for e in ledger.get(pid).get("log", []))
    assert "Vivobarefoot" in log                                                 # note met echt resultaat


# d. status-normalisatie over BEIDE fail-conventies + succes-archetypes
def test_d_status_normalisatie():
    c = Inhabitant._classify_result
    assert c({"error": "x"})[0] == "fout"                       # {error}-conventie
    assert c({"ok": False, "error": "x"})[0] == "fout"          # {ok:False}-conventie
    assert c({"no_data": True})[0] == "leeg"
    assert c({"hits": []})[0] == "leeg"                         # lege lijst → leeg
    assert c({"total": 1, "hits": [{"title": "t"}]}) == ("gelukt", ("list", "hits"))
    assert c({"ok": True, "candidates": [{"brand": "b"}]}) == ("gelukt", ("list", "candidates"))
    assert c({"keywords": {"k": {"vol": 1}}}) == ("gelukt", ("dictlist", "keywords"))
    assert c({"vraag": "Wat is X?"}) == ("gelukt", ("text", "vraag"))
    assert c({"values": {"2026-07-01": 10}}) == ("gelukt", ("metric", "values"))


# e. note-opmaak per archetype: lijst met eigen velden / directe tekst / waarde-per-datum
def test_e_note_per_archetype(tmp_path, ledger):
    inh = _inhabitant(tmp_path, ledger, [], [])
    item = {"text": "x", "skill": "s"}
    lst = inh._deliverable_note(item, {"total": 1, "hits": [{"title": "Study", "citations": 7, "abstract": "bio"}]}, ("list", "hits"))
    assert "Study" in lst and "citations: 7" in lst and "abstract: bio" in lst   # record met EIGEN velden
    txt = inh._deliverable_note(item, {"vraag": "Wat is X?"}, ("text", "vraag"))
    assert txt.strip().endswith("Wat is X?")                                     # tekst direct
    met = inh._deliverable_note(item, {"values": {"2026-07-01": 10, "2026-07-02": 12}}, ("metric", "values"))
    assert "2026-07-01=10" in met and "2026-07-02=12" in met                     # waarde-per-datum
    dl = inh._deliverable_note(item, {"keywords": {"barefoot shoes": {"vol": 1000}}}, ("dictlist", "keywords"))
    assert "barefoot shoes" in dl and "vol: 1000" in dl


# f. skill zonder input_schema → fail-soft: catalogus toont fallback, geen crash
def test_f_geen_schema_fail_soft(tmp_path, ledger, monkeypatch):
    import nooch_village.llm as llm
    seen = {}
    class _NoSchema(Skill):
        name = "mystery"; description = "iets vaags"; cost = "free"
        def run(self, payload, context): return {"text": "ok"}
    monkeypatch.setattr(llm, "reason", lambda prompt, **k: seen.update(prompt=prompt) or
                        '{"deliverable":"d","items":[{"text":"t","skill":"mystery","payload":{},"reason":""}]}')
    inh = _inhabitant(tmp_path, ledger, [_NoSchema()], ["mystery"])
    pid = ledger.create("rol", "doel", "human", status="future")
    inh.prepare_project(pid)                                                      # mag niet crashen
    assert "geen schema" in seen["prompt"]                                        # fallback-tekst in catalogus
    assert inh._project_checklist(ledger.get(pid)) is not None
