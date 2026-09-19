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
from nooch_village.projects import ProjectLedger, PREP_CHECKLIST_TITLE

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


class _RefSkill(Skill):
    name = "ref_skill"; description = "verwijst naar iets"; input_schema = "ref: str"
    required_payload = ("ref",)
    def run(self, payload, context): return {}
    def validate_payload(self, payload, context) -> list:
        ref = (payload or {}).get("ref")
        return [] if ref in getattr(context, "known_refs", ()) else [f"ref '{ref}' bestaat niet"]


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
    cl = ledger.checklist_add(pid, title=PREP_CHECKLIST_TITLE)
    for text, skill, payload in items:
        ledger.check_add(pid, cl["id"], text, skill=skill, payload=payload)
    return cl








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


def test_payload_issues_grounds_references(tmp_path, ledger):
    inh = _inhabitant(tmp_path, ledger, [_RefSkill(), _KwSkill()], ["ref_skill", "keywords_everywhere"])
    inh.context.known_refs = ("bestaat",)
    assert inh._payload_issues("ref_skill", {"ref": "bestaat"}) == []                     # echte verwijzing → ok
    issues = inh._payload_issues("ref_skill", {"ref": "verzonnen"})
    assert issues and "verzonnen" in issues[0]                                            # spook → reden
    assert inh._payload_issues("keywords_everywhere", {"kw": ["x"]}) == []                # geen validate_payload → geen check














