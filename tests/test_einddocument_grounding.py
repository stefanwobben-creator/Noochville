"""Fabricage-rem op het einddocument: de synthese mag geen ongegronde data (getallen/tabellen)
produceren voor taken zonder deliverable. Dekt de twee helpers + de end-to-end vangst (LLM gemockt)."""
from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import patch

import nooch_village.inhabitant as inh
from nooch_village.inhabitant import _ungrounded_tasks, _fabrication_suspects, synthesize_einddocument


# ── _ungrounded_tasks ─────────────────────────────────────────────────────────

def test_ungrounded_tasks_zijn_de_taken_zonder_deliverable():
    project = {"checklists": [{"items": [
        {"id": "a", "text": "Identificeer merken"},
        {"id": "b", "text": "Prijsanalyse"},
        {"id": "c", "text": "Taak zonder id", },
    ]}]}
    deliverables = [{"checklist_item": "a"}]           # alleen taak a heeft een deliverable
    ug = _ungrounded_tasks(project, deliverables)
    assert "Prijsanalyse" in ug and "Taak zonder id" in ug
    assert "Identificeer merken" not in ug             # a is gegrond


# ── _fabrication_suspects ─────────────────────────────────────────────────────

def test_suspects_flagt_tabel_onder_ongegronde_taak():
    doc = ("## Identificeer merken\nVeja, Xero\n\n"
           "## Prijsanalyse\n| Merk | Prijs |\n| --- | --- |\n| Veja | €120 |\n")
    assert _fabrication_suspects(doc, ["Prijsanalyse"]) == ["Prijsanalyse"]


def test_suspects_schoon_bij_niet_onderzocht():
    doc = "## Prijsanalyse\nNiet onderzocht — geen gegrond resultaat.\n"
    assert _fabrication_suspects(doc, ["Prijsanalyse"]) == []


def test_suspects_negeert_data_onder_gegronde_taak():
    doc = "## Identificeer merken\n| Merk | Land |\n| --- | --- |\n| Veja | FR |\n"
    assert _fabrication_suspects(doc, ["Prijsanalyse"]) == []   # tabel hoort bij een NIET-ongegronde taak


# ── mocks voor de end-to-end ──────────────────────────────────────────────────

class _DocStore:
    def __init__(self): self.docs = {}
    def read(self, pid): return self.docs.get(pid)
    def write(self, pid, text): self.docs[pid] = text


class _DelivStore:
    def __init__(self, recs, contents): self.recs, self.contents = recs, contents
    def for_project(self, pid): return self.recs
    def content_for(self, rid): return self.contents.get(rid)


class _Projects:
    def __init__(self): self.msgs = []
    def add_role_message(self, pid, msg): self.msgs.append(msg)


def test_synthese_geeft_ongegronde_taken_mee_en_vangt_fabricage(caplog):
    project = {"id": "p1", "scope": "prijsanalyse barefoot", "comments": [],
               "checklists": [{"id": "c1", "items": [
                   {"id": "a", "text": "Identificeer merken"},
                   {"id": "b", "text": "Prijsanalyse van merken"}]}]}
    dstore = _DelivStore([{"id": "d1", "checklist_item": "a", "summary": "merken gevonden"}],
                         {"d1": "Veja, Xero"})
    docstore, projects, captured = _DocStore(), _Projects(), {}

    def fake_reason(prompt, **kw):
        captured["prompt"] = prompt
        # de LLM fabriceert een prijstabel onder de ongegronde taak
        return ("## Identificeer merken\nVeja, Xero\n\n"
                "## Prijsanalyse van merken\n| Merk | Prijs |\n| --- | --- |\n| Veja | €120 |\n\n"
                "## Conclusie\nx\n\n## Aanbevelingen\n- y")

    with caplog.at_level(logging.WARNING), patch("nooch_village.llm.reason", fake_reason):
        ok = synthesize_einddocument(
            project_docs=docstore, deliverables=dstore, projects=projects, personas=None,
            record=SimpleNamespace(persona_id=None), settings={}, project=project,
            force_final=True, log=logging.getLogger("test.einddoc"))

    assert ok is True
    # 1) de ongegronde taak is expliciet aan de synthese meegegeven met de harde regel
    assert "TAKEN ZONDER GEGROND RESULTAAT" in captured["prompt"]
    assert "Prijsanalyse van merken" in captured["prompt"]
    assert "HARDE GRONDINGS-REGEL" in captured["prompt"]
    # 2) de fabricage-vangst sloeg aan: luide log + zichtbare wall-waarschuwing
    assert "DOC_FABRICATION_SUSPECT" in caplog.text
    assert any("ONGEGRONDE data" in m for m in projects.msgs)


def test_synthese_geen_valse_alarm_bij_schoon_document():
    project = {"id": "p2", "scope": "merken", "comments": [],
               "checklists": [{"id": "c1", "items": [
                   {"id": "a", "text": "Identificeer merken"},
                   {"id": "b", "text": "Prijsanalyse van merken"}]}]}
    dstore = _DelivStore([{"id": "d1", "checklist_item": "a", "summary": "merken"}], {"d1": "Veja"})
    docstore, projects = _DocStore(), _Projects()

    def fake_reason(prompt, **kw):
        # de LLM gehoorzaamt: ongegronde taak → 'niet onderzocht', geen verzonnen tabel
        return ("## Identificeer merken\nVeja\n\n"
                "## Prijsanalyse van merken\nNiet onderzocht — geen gegrond resultaat.\n\n"
                "## Conclusie\nx\n\n## Aanbevelingen\n- y")

    with patch("nooch_village.llm.reason", fake_reason):
        ok = synthesize_einddocument(
            project_docs=docstore, deliverables=dstore, projects=projects, personas=None,
            record=SimpleNamespace(persona_id=None), settings={}, project=project,
            force_final=False, log=logging.getLogger("test.einddoc2"))

    assert ok is True
    assert not any("ONGEGRONDE data" in m for m in projects.msgs)   # schoon → geen waarschuwing
