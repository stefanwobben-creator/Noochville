"""DeliverableStore: skill-resultaten overleven het project als gestructureerde records.

Store-unit (add/cap/delete-cascade + statusovergang-intact) en integratie via _execute_checklist
(record bij succes met VOLLEDIGE content, faalnote → geen record, store-fout → wall-note intact,
project_completed draagt deliverable_ids)."""
from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from nooch_village.deliverable_store import DeliverableStore
from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus
from nooch_village.skills import SkillRegistry, Skill
from nooch_village.projects import ProjectLedger, PREP_CHECKLIST_TITLE

TODAY = "2026-07-08"


class _ResearchSkill(Skill):
    name = "openalex_evidence"
    description = "fake research skill"

    def run(self, payload, context):
        term = (payload or {}).get("term", "")
        if term == "boom":
            raise RuntimeError("API kapot")
        return {"term": term, "total": 2, "hits": [{"title": f"Study on {term}", "year": 2021}]}


def _stores(tmp_path):
    return (ProjectLedger(str(tmp_path / "projects.json")),
            DeliverableStore(str(tmp_path / "deliverables.json")))


def _inh(tmp_path, ledger, dstore):
    reg = SkillRegistry()
    reg.register(_ResearchSkill())
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0"}, data_dir=str(tmp_path),
                          projects=ledger, deliverables=dstore, records=None)
    rec = Record(id="harry_hemp", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="w", accountabilities=["research"], domains=[],
                                           skills=["openalex_evidence"]), source="sensed")
    return Inhabitant(rec, EventBus(name="test"), reg, ctx)


def _prep(ledger, pid, items):
    cl = ledger.checklist_add(pid, title=PREP_CHECKLIST_TITLE)
    for text, skill, query, reason in items:
        ledger.check_add(pid, cl["id"], text, skill=skill, query=query, reason=reason)
    return cl


# ── store-unit ──────────────────────────────────────────────────────────────────

@pytest.mark.smoke
def test_add_bewaart_volledige_content_en_leest_terug(tmp_path):
    _, ds = _stores(tmp_path)
    content = {"total": 2, "hits": [{"title": "x"}]}
    rec = ds.add(project_id="p1", role="harry_hemp", skill="openalex_evidence", checklist_item="i1",
                 title="studies", content=content, summary="📎 studies", wall_note_id="w1")
    assert "content" not in rec and rec["wall_note_id"] == "w1" and rec["id"]   # content niet in de index
    assert ds.content_for(rec["id"]) == content                                 # wel in de sidecar
    assert ds.for_project("p1") == [rec] and ds.by_ids([rec["id"]]) == [rec]
    assert DeliverableStore(ds.path).content_for(rec["id"]) == content   # persistent (verse instance)


@pytest.mark.smoke
def test_cap_fail_loud_stand_in(tmp_path, caplog):
    _, ds = _stores(tmp_path)
    big = {"hits": [{"t": "x" * 200} for _ in range(50)]}      # ruim > 1000 bytes
    with caplog.at_level(logging.WARNING):
        rec = ds.add(project_id="p1", role="r", skill="s", checklist_item="i", title="t",
                     content=big, summary="📎", max_bytes=1000)
    sc = ds.content_for(rec["id"])                             # de stand-in is de SIDECAR-inhoud
    assert sc["_truncated"] is True and "preview" in sc
    assert sc["_cap"] == 1000 and sc["_bytes"] > 1000
    assert "content" not in rec                                # index-record blijft normaal
    assert "DELIVERABLE_CAP" in caplog.text                    # luide logregel, geen stille truncatie


@pytest.mark.smoke
def test_delete_cascade_alleen_eigen_project(tmp_path):
    import os
    _, ds = _stores(tmp_path)
    for ci in ("i", "j"):
        ds.add(project_id="p1", role="r", skill="s", checklist_item=ci, title="t", content={}, summary="a")
    ds.add(project_id="p2", role="r", skill="s", checklist_item="k", title="t", content={}, summary="c")
    p1_ids = [r["id"] for r in ds.for_project("p1")]
    assert all(os.path.exists(ds._sidecar_path(i)) for i in p1_ids)        # sidecars aangemaakt
    assert ds.delete_for_project("p1") == 2                    # count (index-records) teruggegeven
    assert ds.for_project("p1") == [] and len(ds.for_project("p2")) == 1   # alleen p1 weg
    assert all(not os.path.exists(ds._sidecar_path(i)) for i in p1_ids)    # sidecars mee-verwijderd


def test_statuswijziging_laat_records_staan_delete_ruimt_op(tmp_path):
    ledger, ds = _stores(tmp_path)
    pid = ledger.create("harry_hemp", "doel", "human")
    ds.add(project_id=pid, role="harry_hemp", skill="s", checklist_item="i", title="t", content={}, summary="a")
    ledger.complete(pid, "checklist voltooid (1/1)")
    ledger.archive(pid)
    ledger.unarchive(pid)
    assert len(ds.for_project(pid)) == 1                       # done/archief/heropening → records intact
    assert ds.delete_for_project(pid) == 1 and ds.for_project(pid) == []   # definitieve delete ruimt op










