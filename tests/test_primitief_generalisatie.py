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
    cost = "credits"; required_payload = ("kw",); last = None
    def run(self, payload, context):
        self.last = payload
        return {"keywords": {"barefoot shoes": {"vol": 1000, "cpc": 0.5, "competition": 0.3}}}


class _BrandSkill(Skill):
    name = "competitor_discover"; description = "concurrenten"; input_schema = "brands: list[str], limit: int"
    cost = "credits"; required_payload = ("brands",); last = None
    def run(self, payload, context):
        self.last = payload
        return {"ok": True, "candidates": [{"brand": "Vivobarefoot", "article": "launch", "link": "http://x"}]}


class _TermSkill(Skill):
    name = "openalex_evidence"; description = "studies"; input_schema = "term: str"
    cost = "rate_limited"; required_payload = ("term",); last = None
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
        r = ('{"deliverable":"d","items":[{"text":"volumes","skill":"keywords_everywhere",'
             '"payload":{"kw":["barefoot shoes"]},"reason":""}]}')
        return (r, "mock") if k.get("return_tier") else r
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
    def _fr(prompt, **k):
        seen["prompt"] = prompt
        r = '{"deliverable":"d","items":[{"text":"t","skill":"mystery","payload":{},"reason":""}]}'
        return (r, "mock") if k.get("return_tier") else r
    monkeypatch.setattr(llm, "reason", _fr)
    inh = _inhabitant(tmp_path, ledger, [_NoSchema()], ["mystery"])
    pid = ledger.create("rol", "doel", "human", status="future")
    inh.prepare_project(pid)                                                      # mag niet crashen
    assert "geen schema" in seen["prompt"]                                        # fallback-tekst in catalogus
    assert inh._project_checklist(ledger.get(pid)) is not None


# ── Plan-parse robuust over alle tredes (PR na #133: mistral gaf onparsebare output) ────────────
def test_extract_json_robuust_fences_en_proza():
    ex = Inhabitant._extract_json
    assert ex('{"items":[1]}') == {"items": [1]}                     # d. kale JSON (Gemini) blijft werken
    assert ex('```json\n{"items":[2]}\n```') == {"items": [2]}       # a. markdown-fences ```json …```
    assert ex('```\n{"items":[3]}\n```') == {"items": [3]}           # a. fences zonder taal-tag
    assert ex('Hier is het plan:\n{"items":[4]}\nKlaar.') == {"items": [4]}   # b. leidend/volgend proza
    assert ex('geen json') is None and ex('') is None               # onparsebaar → None


def test_prep_met_markdown_fences_parset(tmp_path, ledger, monkeypatch):
    """mistral-stijl: JSON in ```json-fences → _extract_json strippt ze → prep slaagt (het geval van Billy)."""
    import nooch_village.llm as llm
    fenced = ('```json\n{"deliverable":"d","items":[{"text":"studies","skill":"openalex_evidence",'
              '"payload":{"term":"barefoot shoes"},"reason":""}]}\n```')
    monkeypatch.setattr(llm, "reason",
                        lambda *a, **k: (fenced, "mistral:mistral-small") if k.get("return_tier") else fenced)
    inh = _inhabitant(tmp_path, ledger, [_TermSkill()], ["openalex_evidence"])
    pid = ledger.create("rol", "doel", "human", status="future")
    inh.prepare_project(pid)
    cl = inh._project_checklist(ledger.get(pid))
    assert cl and cl["items"][0]["skill"] == "openalex_evidence"
    assert cl["items"][0]["payload"] == {"term": "barefoot shoes"}


def test_prep_onparsebaar_retry_dan_niet_parsebaar_gelogd(tmp_path, ledger, monkeypatch, caplog):
    """Onparsebare output → één gerichte retry; daarna None + de log zegt 'NIET PARSEBAAR' mét rauwe output."""
    import logging
    import nooch_village.llm as llm
    calls = {"n": 0}
    def _fr(prompt, **k):
        calls["n"] += 1
        r = "sorry, ik kan dit niet als JSON geven"
        return (r, "mistral:x") if k.get("return_tier") else r
    monkeypatch.setattr(llm, "reason", _fr)
    inh = _inhabitant(tmp_path, ledger, [_TermSkill()], ["openalex_evidence"])
    pid = ledger.create("rol", "doel", "human", status="future")
    with caplog.at_level(logging.WARNING):
        inh.prepare_project(pid)
    assert inh._project_checklist(ledger.get(pid)) is None           # geen checklist
    assert calls["n"] == 2                                            # eerste poging + één gerichte retry
    msgs = " ".join(r.getMessage() for r in caplog.records)
    assert "NIET PARSEBAAR" in msgs and "sorry" in msgs              # onderscheid + rauwe output in de log


def test_prep_geen_antwoord_onderscheiden_van_niet_parsebaar(tmp_path, ledger, monkeypatch, caplog):
    import logging
    import nooch_village.llm as llm
    monkeypatch.setattr(llm, "reason", lambda *a, **k: (None, None) if k.get("return_tier") else None)
    inh = _inhabitant(tmp_path, ledger, [_TermSkill()], ["openalex_evidence"])
    pid = ledger.create("rol", "doel", "human", status="future")
    with caplog.at_level(logging.WARNING):
        inh.prepare_project(pid)
    msgs = " ".join(r.getMessage() for r in caplog.records)
    assert "geen antwoord" in msgs and "PARSEBAAR" not in msgs       # 'geen antwoord' ≠ 'niet parsebaar'


# ── Payload-validatie tegen required_payload (fail-fast bij prepare, niet fail-silent bij uitvoering) ──
def _mock_plan(monkeypatch, plan_json):
    import nooch_village.llm as llm
    monkeypatch.setattr(llm, "reason",
                        lambda *a, **k: (plan_json, "mock") if k.get("return_tier") else plan_json)


def test_missing_required_helper(tmp_path, ledger):
    inh = _inhabitant(tmp_path, ledger, [_BrandSkill(), _KwSkill()], ["competitor_discover", "keywords_everywhere"])
    assert inh._missing_required("competitor_discover", {"limit": 20}) == ["brands"]     # verplicht ontbreekt
    assert inh._missing_required("competitor_discover", {"brands": ["x"]}) == []         # compleet
    assert inh._missing_required("competitor_discover", {"brands": []}) == ["brands"]    # leeg = ontbrekend
    assert inh._missing_required("onbekende_skill", {}) == []                            # onbekend → fail-soft


def test_a_volledige_payload_uitvoerbaar(tmp_path, ledger, monkeypatch):
    _mock_plan(monkeypatch, '{"deliverable":"d","items":[{"text":"volumes","skill":"keywords_everywhere",'
                            '"payload":{"kw":["barefoot shoes"]},"reason":""}]}')
    inh = _inhabitant(tmp_path, ledger, [_KwSkill()], ["keywords_everywhere"])
    pid = ledger.create("rol", "doel", "human", status="future"); inh.prepare_project(pid)
    it = inh._project_checklist(ledger.get(pid))["items"][0]
    assert it.get("payload_ok") is not False and it["skill"] == "keywords_everywhere"   # valide, uitvoerbaar


def test_b_competitor_zonder_brands_gemarkeerd_en_niet_uitgevoerd(tmp_path, ledger, monkeypatch):
    br = _BrandSkill()
    _mock_plan(monkeypatch, '{"deliverable":"d","items":[{"text":"concurrenten","skill":"competitor_discover",'
                            '"payload":{"limit":20},"reason":""}]}')
    inh = _inhabitant(tmp_path, ledger, [br], ["competitor_discover"])
    pid = ledger.create("rol", "doel", "human", status="future"); inh.prepare_project(pid)
    it = inh._project_checklist(ledger.get(pid))["items"][0]
    assert it["payload_ok"] is False and "brands" in it["reason"]         # gemarkeerd + reden
    ledger.start(pid); inh._execute_checklist(ledger.get(pid), TODAY)     # uitvoering slaat het over
    assert br.last is None                                                # skill NIET aangeroepen
    assert inh._project_checklist(ledger.get(pid))["items"][0]["done"] is False   # blijft open


def test_c_keywords_zonder_kw_gemarkeerd(tmp_path, ledger, monkeypatch):
    _mock_plan(monkeypatch, '{"deliverable":"d","items":[{"text":"volumes","skill":"keywords_everywhere",'
                            '"payload":{"country":"global"},"reason":""}]}')
    inh = _inhabitant(tmp_path, ledger, [_KwSkill()], ["keywords_everywhere"])
    pid = ledger.create("rol", "doel", "human", status="future"); inh.prepare_project(pid)
    it = inh._project_checklist(ledger.get(pid))["items"][0]
    assert it["payload_ok"] is False and "kw" in it["reason"]


def test_d_optioneel_veld_ontbreekt_valide(tmp_path, ledger, monkeypatch):
    # brands aanwezig, limit (optioneel) ontbreekt → valide
    _mock_plan(monkeypatch, '{"deliverable":"d","items":[{"text":"concurrenten","skill":"competitor_discover",'
                            '"payload":{"brands":["Nooch"]},"reason":""}]}')
    inh = _inhabitant(tmp_path, ledger, [_BrandSkill()], ["competitor_discover"])
    pid = ledger.create("rol", "doel", "human", status="future"); inh.prepare_project(pid)
    it = inh._project_checklist(ledger.get(pid))["items"][0]
    assert it.get("payload_ok") is not False                              # optioneel veld mag ontbreken


def test_e_skill_zonder_required_payload_failsoft(tmp_path, ledger, monkeypatch):
    class _NoReq(Skill):
        name = "mystery"; description = "geen required_payload"; cost = "free"
        def run(self, payload, context): return {"text": "ok"}
    _mock_plan(monkeypatch, '{"deliverable":"d","items":[{"text":"t","skill":"mystery","payload":{},"reason":""}]}')
    inh = _inhabitant(tmp_path, ledger, [_NoReq()], ["mystery"])
    pid = ledger.create("rol", "doel", "human", status="future"); inh.prepare_project(pid)   # mag niet crashen
    it = inh._project_checklist(ledger.get(pid))["items"][0]
    assert it.get("payload_ok") is not False                              # geen validatie mogelijk → uitvoerbaar
