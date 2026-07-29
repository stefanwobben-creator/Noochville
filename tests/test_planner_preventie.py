"""Deel 3 — preventie: een mens-taak komt niet als AI-item in de klaar-telling.

De vorige PR ving de zombie ná het ontstaan (de park-klep). Dit voorkomt hem bij de bron: de planner
classificeert een item dat alleen een mens of externe partij kan doen als expliciete mens-taak, en
die telt niet mee in de klaar-telling. Zo kan een project zijn AI-deel gewoon afmaken in plaats van
eeuwig op 4/5 te blijven staan wachten op een fabrieksbezoek.

Grens die hier óók bewaakt wordt: niet-meetellen mag niet lezen als afgerond. Een openstaande
mens-taak reist mee tot in het einddocument, de review-melding en de badge (zie test_zombie_projecten
voor diezelfde garantie op overgeslagen items).
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from nooch_village.event_bus import EventBus
from nooch_village.inhabitant import Inhabitant, _skipped_tasks
from nooch_village.models import Record, RecordType, RoleDefinition
from nooch_village.projects import (ProjectLedger, checklist_progress, human_task_items,
                                    not_answered_note)
from nooch_village.skills import Skill, SkillRegistry

_PLAN = "nooch_village.llm.reason"


class _OkSkill(Skill):
    name = "claims_check"
    description = "fake skill"

    def run(self, payload, context):
        return {"ok": True}


def _inh(tmp_path, ledger):
    reg = SkillRegistry()
    reg.register(_OkSkill())
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0"}, data_dir=str(tmp_path),
                          projects=ledger, records=None)
    rec = Record(id="compliance", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="geen greenwashing", accountabilities=["claims"],
                                           domains=[], skills=["claims_check"]), source="sensed")
    return Inhabitant(rec, EventBus(name="test"), reg, ctx)


def _plan(items, deliverable="iets"):
    import json
    return json.dumps({"deliverable": deliverable, "accountability": "claims", "items": items})


def _cl(p):
    return next(c for c in p["checklists"] if c["title"] == Inhabitant._PREP_CHECKLIST_TITLE)


def _prepare(tmp_path, items):
    ledger = ProjectLedger(str(tmp_path / "projects.json"))
    pid = ledger.create("compliance", "QR-codes op alle schoenen", "human", status="future")
    inh = _inh(tmp_path, ledger)
    with patch(_PLAN, return_value=(_plan(items), "test-tier")):
        inh.prepare_project(pid)
    return ledger, pid


# ── de kern: mens-werk telt niet mee ───────────────────────────────────────────

def test_mens_taak_telt_niet_mee_in_de_klaar_telling(tmp_path):
    """DE test van deel 3: het project kan zijn AI-deel afmaken (1/1) terwijl de mens-taak open
    staat — in plaats van eeuwig op 1/2 te blijven hangen."""
    ledger, pid = _prepare(tmp_path, [
        {"text": "toets de claim", "skill": "claims_check", "payload": {}, "reason": ""},
        {"text": "plak de QR-sticker op de schoen", "skill": None, "payload": {},
         "reason": "fysiek werk", "kind": "human_external"},
    ])
    cl = _cl(ledger.get(pid))

    assert checklist_progress(cl) == (0, 1)              # de mens-taak zit NIET in de noemer
    mens = [it for it in cl["items"] if it.get("human_task")]
    assert len(mens) == 1 and mens[0]["text"].startswith("plak de QR")
    assert mens[0]["reason"]                              # de reden staat erbij


def test_missende_capaciteit_telt_wel_mee(tmp_path):
    """Alleen fysiek/menselijk werk valt buiten de telling. Een item waar software wél voor kan
    bestaan blijft gewoon meetellen — dat is een capaciteitsgat, geen mens-taak, en het hoort de
    klep te halen zodat het als gat geoogst kan worden."""
    ledger, pid = _prepare(tmp_path, [
        {"text": "toets de claim", "skill": "claims_check", "payload": {}, "reason": ""},
        {"text": "haal patentdata op", "skill": None, "payload": {}, "reason": "geen patent-skill",
         "kind": "missing_capability"},
    ])
    cl = _cl(ledger.get(pid))

    assert checklist_progress(cl) == (0, 2)
    assert not any(it.get("human_task") for it in cl["items"])


def test_zonder_classificatie_verandert_er_niets(tmp_path):
    """Fail-soft: geeft de LLM geen 'kind' terug (oud model, kapot antwoord), dan gedraagt het item
    zich exact als voorheen — meetellen en parkeren. Liever het bekende gedrag dan een gok."""
    ledger, pid = _prepare(tmp_path, [
        {"text": "iets onbekends", "skill": None, "payload": {}, "reason": "geen skill"},
    ])
    cl = _cl(ledger.get(pid))

    assert checklist_progress(cl) == (0, 1)
    assert not any(it.get("human_task") for it in cl["items"])


def test_de_rol_probeert_een_mens_taak_niet_uit_te_voeren(tmp_path):
    """En parkeert er ook niet op: het project maakt zijn AI-deel af en gaat naar review."""
    ledger, pid = _prepare(tmp_path, [
        {"text": "toets de claim", "skill": "claims_check", "payload": {}, "reason": ""},
        {"text": "bel de leverancier", "skill": None, "payload": {}, "reason": "telefoon",
         "kind": "human_external"},
    ])
    ledger.start(pid)
    inh = _inh(tmp_path, ledger)

    inh._execute_checklist(ledger.get(pid), "2026-07-29")

    p = ledger.get(pid)
    assert p["blocked_on"] == "review"                    # niet geparkeerd op de mens-taak
    assert checklist_progress(_cl(p)) == (1, 1)


# ── maar: niet meetellen mag niet lezen als afgerond ───────────────────────────

def test_open_mens_taak_reist_mee_naar_de_review(tmp_path):
    ledger, pid = _prepare(tmp_path, [
        {"text": "toets de claim", "skill": "claims_check", "payload": {}, "reason": ""},
        {"text": "bel de leverancier", "skill": None, "payload": {}, "reason": "telefoon",
         "kind": "human_external"},
    ])
    ledger.start(pid)
    _inh(tmp_path, ledger)._execute_checklist(ledger.get(pid), "2026-07-29")
    p = ledger.get(pid)

    melding = [e["text"] for e in p.get("log", []) if "klaar voor review" in e["text"]][-1]
    assert "bel de leverancier" in melding and "NIET beantwoord" in melding
    assert "bel de leverancier" in not_answered_note(p)
    assert [t for t, _r in _skipped_tasks(p)] == ["bel de leverancier"]   # ook in het einddocument
    assert len(human_task_items(p)) == 1


def test_afgevinkte_mens_taak_is_geen_voorbehoud_meer(tmp_path):
    """Heeft de mens 'm gedaan, dan hoeft het niet meer als openstaand gemeld te worden."""
    ledger, pid = _prepare(tmp_path, [
        {"text": "bel de leverancier", "skill": None, "payload": {}, "reason": "telefoon",
         "kind": "human_external"},
    ])
    cl = _cl(ledger.get(pid))
    ledger.check_toggle(pid, cl["id"], cl["items"][0]["id"])

    assert human_task_items(ledger.get(pid)) == []
    assert not_answered_note(ledger.get(pid)) == ""


# ── het a14e21e-geval: een plan dat volledig mens-werk is ──────────────────────

def test_volledig_mens_plan_gaat_meteen_naar_de_mens(tmp_path):
    """De twee prod-projecten die 0/5 op het bord stonden: elk item mens-werk. Dat is geen
    AI-project — het hoort meteen zichtbaar bij de mens te liggen, niet stil op het bord."""
    ledger, pid = _prepare(tmp_path, [
        {"text": "bezoek de fabriek", "skill": None, "payload": {}, "reason": "fysiek",
         "kind": "human_external"},
        {"text": "film het prototype", "skill": None, "payload": {}, "reason": "fysiek",
         "kind": "human_external"},
    ])
    p = ledger.get(pid)

    assert p["status"] == "blocked"
    assert "mens-project" in (p["blocked_on"] or "")
    assert any("volledig mens" in e["text"] or "mens- of extern werk" in e["text"]
               for e in p.get("log", []))
    assert checklist_progress(_cl(p)) == (0, 0)          # niets voor de rol te doen


def test_gemengd_plan_gaat_niet_naar_de_mens(tmp_path):
    """Grens: één uitvoerbaar item is genoeg om het een AI-project te laten blijven."""
    ledger, pid = _prepare(tmp_path, [
        {"text": "toets de claim", "skill": "claims_check", "payload": {}, "reason": ""},
        {"text": "bezoek de fabriek", "skill": None, "payload": {}, "reason": "fysiek",
         "kind": "human_external"},
    ])
    p = ledger.get(pid)

    assert p["status"] == "future" and p["blocked_on"] is None


def test_planprompt_vraagt_de_classificatie(tmp_path):
    """De classificatie moet ook echt gevraagd worden, anders komt hij nooit terug."""
    ledger = ProjectLedger(str(tmp_path / "projects.json"))
    pid = ledger.create("compliance", "doel", "human", status="future")
    with patch(_PLAN, return_value=(_plan([{"text": "x", "skill": None, "payload": {}}]),
                                    "t")) as m:
        _inh(tmp_path, ledger).prepare_project(pid)
    prompt = m.call_args[0][0]
    assert "human_external" in prompt and "missing_capability" in prompt
