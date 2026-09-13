"""Het criteria-contract (scope 61, 13 september 2026) — de must/nice-lat die `_plan_checklist`
afspreekt blijft dezelfde lat door de hele keten heen, in plaats van drie keer los verzonnen
(`_plan_checklist` zelf, `ronde_twee.leads_uit`, `lead_beoordeling`). Zie
`structurele_prioriteit_informatievinden.md` voor het waarom: dat gat verklaarde zowel "instructie
vooraf gaat verloren" als "ik moet de hele update lezen en zoeken naar de conclusie".

`ronde_twee.py` en `lead_beoordeling.py` hebben allebei hun eigen testbestand, en
`projects.checklist_add`'s eigen sanitizing (capping, afkappen, leeg-blijft-leeg) staat in
test_projects.py. Wat hier vastligt is de twee plekken die daar niet doorheen komen:

1. `_plan_checklist` zelf: `must_criteria`/`nice_criteria` uit het modelantwoord worden
   genormaliseerd tot `data["criteria"]` — en `prepare_project` zet die in ÉÉN keer op de checklist.
2. `_herplan_na_strategie`: de lat van het OORSPRONKELIJKE plan wint over wat het smalle, tweede
   herplan-promptje er zelf nog bij verzint — anders drijven "wat het plan beloofde" en "waarop de
   herplande stappen toetsen" alsnog uiteen.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from nooch_village.event_bus import EventBus
from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RecordType, RoleDefinition
from nooch_village.projects import ProjectLedger
from nooch_village.skills import SkillRegistry


def _inhabitant(tmp_path, ledger=None, skills=()):
    """Zoals `test_opdracht_in_prep.py`'s helper: minimale ctx, geen rugzakken nodig (`_plan_checklist`
    valt terug op None via getattr)."""
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0"}, data_dir=str(tmp_path),
                          projects=ledger, records=None)
    rec = Record(id="harry_hemp", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="onderzoek", accountabilities=["research"],
                                           domains=[], skills=list(skills)),
                 source="seed")
    return Inhabitant(rec, EventBus(name="test"), SkillRegistry(), ctx)


def _fake_reason(antwoord: dict):
    """`_plan_checklist` vraagt altijd `return_tier=True` (zie test_primitief_generalisatie.py)."""
    def _f(prompt, **k):
        r = json.dumps(antwoord)
        return (r, "mock") if k.get("return_tier") else r
    return _f


# ── 1: _plan_checklist normaliseert must_criteria/nice_criteria ──────────────

def test_plan_checklist_normaliseert_must_en_nice_criteria(tmp_path, monkeypatch):
    import nooch_village.llm as llm
    antwoord = {"deliverable": "d", "accountability": "onderzoek",
                "must_criteria": ["plastic-free", "plastic-free", "  vegan  ", "x" * 200],
                "nice_criteria": ["EU-based"],
                "items": [{"text": "zoek", "skill": None, "reason": "geen skill nodig"}]}
    monkeypatch.setattr(llm, "reason", _fake_reason(antwoord))
    inh = _inhabitant(tmp_path)
    plan = inh._plan_checklist("Glue-free joining", description="plastic-free and vegan")
    assert plan is not None
    # ontdubbeld (case-insensitief), getrimd op witruimte, afgekapt op 80 tekens
    assert plan["criteria"]["must"] == ["plastic-free", "vegan", "x" * 80]
    assert plan["criteria"]["nice"] == ["EU-based"]


def test_plan_checklist_zonder_criteria_in_het_antwoord_laat_de_sleutel_weg(tmp_path, monkeypatch):
    """Een plan zonder heldere lat (bv. een zuivere oriëntatie-vraag) is prima: geen sleutel forceren."""
    import nooch_village.llm as llm
    antwoord = {"deliverable": "d", "accountability": "onderzoek",
                "items": [{"text": "zoek", "skill": None, "reason": "geen skill nodig"}]}
    monkeypatch.setattr(llm, "reason", _fake_reason(antwoord))
    inh = _inhabitant(tmp_path)
    plan = inh._plan_checklist("doel zonder duidelijke lat")
    assert plan is not None and "criteria" not in plan


def test_plan_checklist_capt_op_acht_criteria(tmp_path, monkeypatch):
    import nooch_village.llm as llm
    antwoord = {"deliverable": "d", "accountability": "a",
                "must_criteria": [f"c{i}" for i in range(12)],
                "items": [{"text": "zoek", "skill": None, "reason": "r"}]}
    monkeypatch.setattr(llm, "reason", _fake_reason(antwoord))
    inh = _inhabitant(tmp_path)
    plan = inh._plan_checklist("doel")
    assert len(plan["criteria"]["must"]) == 8


# ── 2: prepare_project zet die lat in ÉÉN keer op de checklist ───────────────

def test_prepare_project_zet_criteria_op_de_checklist(tmp_path, monkeypatch):
    import nooch_village.llm as llm
    antwoord = {"deliverable": "d", "accountability": "a", "must_criteria": ["plastic-free"],
                "items": [{"text": "zoek", "skill": None, "reason": "r"}]}
    monkeypatch.setattr(llm, "reason", _fake_reason(antwoord))
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    inh = _inhabitant(tmp_path, ledger)
    pid = ledger.create("harry_hemp", "Glue-free joining", "human", status="future")
    inh.prepare_project(pid)
    cl = inh._project_checklist(ledger.get(pid))
    assert cl["criteria"] == {"must": ["plastic-free"], "nice": []}


def test_prepare_project_zonder_lat_zet_geen_criteria_sleutel(tmp_path, monkeypatch):
    import nooch_village.llm as llm
    antwoord = {"deliverable": "d", "accountability": "a",
                "items": [{"text": "zoek", "skill": None, "reason": "r"}]}
    monkeypatch.setattr(llm, "reason", _fake_reason(antwoord))
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    inh = _inhabitant(tmp_path, ledger)
    pid = ledger.create("harry_hemp", "doel", "human", status="future")
    inh.prepare_project(pid)
    cl = inh._project_checklist(ledger.get(pid))
    assert "criteria" not in cl


# ── 3: _herplan_na_strategie — het oorspronkelijke plan wint ─────────────────

def _herplan_rol(tmp_path, ledger):
    return _inhabitant(tmp_path, ledger, skills=["zoekstrategie"])


def _resultaat():
    return {"ok": True, "stappen": [{"bron": "openalex_evidence", "term": "vegan shoes", "taal": "en"}]}


def test_herplan_neemt_de_bestaande_lat_over_niet_zijn_eigen_smalle_afleiding(tmp_path, monkeypatch):
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    inh = _herplan_rol(tmp_path, ledger)
    pid = ledger.create("harry_hemp", "Glue-free joining", "human", status="running")
    # het OORSPRONKELIJKE plan had al een lat, breder gemotiveerd dan dit smalle herplan-promptje
    ledger.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE,
                         criteria={"must": ["plastic-free"], "nice": ["EU-based"]})
    strategie_cl = ledger.checklist_add(pid, title="Strategie")
    ledger.check_add(pid, strategie_cl["id"], "bepaal de strategie", skill="zoekstrategie")
    item = ledger.get(pid)["checklists"][1]["items"][0]

    # het herplan-promptje verzint zelf een ANDERE lat — die moet verliezen van het origineel
    monkeypatch.setattr(Inhabitant, "_plan_checklist",
                        lambda self, goal, **kw: {
                            "items": [{"text": "x", "skill": "openalex_evidence", "payload": {"term": "t"}}],
                            "criteria": {"must": ["iets heel anders"], "nice": []}})
    inh._herplan_na_strategie(pid, item, _resultaat(), ledger)

    nieuw = ledger.get(pid)["checklists"][2]
    assert nieuw["criteria"] == {"must": ["plastic-free"], "nice": ["EU-based"]}   # het origineel wint


def test_herplan_valt_terug_op_zijn_eigen_lat_zonder_bestaand_plan(tmp_path, monkeypatch):
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    inh = _herplan_rol(tmp_path, ledger)
    pid = ledger.create("harry_hemp", "doel", "human", status="running")
    strategie_cl = ledger.checklist_add(pid, title="Strategie")            # GEEN criteria op deze lijst
    ledger.check_add(pid, strategie_cl["id"], "bepaal de strategie", skill="zoekstrategie")
    item = ledger.get(pid)["checklists"][0]["items"][0]

    monkeypatch.setattr(Inhabitant, "_plan_checklist",
                        lambda self, goal, **kw: {
                            "items": [{"text": "x", "skill": "openalex_evidence", "payload": {"term": "t"}}],
                            "criteria": {"must": ["eigen lat"], "nice": []}})
    inh._herplan_na_strategie(pid, item, _resultaat(), ledger)

    nieuw = ledger.get(pid)["checklists"][1]
    assert nieuw["criteria"] == {"must": ["eigen lat"], "nice": []}


def test_herplan_zonder_enige_lat_zet_geen_criteria(tmp_path, monkeypatch):
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    inh = _herplan_rol(tmp_path, ledger)
    pid = ledger.create("harry_hemp", "doel", "human", status="running")
    strategie_cl = ledger.checklist_add(pid, title="Strategie")
    ledger.check_add(pid, strategie_cl["id"], "bepaal de strategie", skill="zoekstrategie")
    item = ledger.get(pid)["checklists"][0]["items"][0]

    monkeypatch.setattr(Inhabitant, "_plan_checklist",
                        lambda self, goal, **kw: {
                            "items": [{"text": "x", "skill": "openalex_evidence", "payload": {"term": "t"}}]})
    inh._herplan_na_strategie(pid, item, _resultaat(), ledger)

    nieuw = ledger.get(pid)["checklists"][1]
    assert "criteria" not in nieuw
