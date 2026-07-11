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
from nooch_village.projects import ProjectLedger

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
    cl = ledger.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE)
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


# ── integratie via _execute_checklist ───────────────────────────────────────────

@pytest.mark.smoke
def test_execute_schrijft_record_met_volledige_content_en_wall_link(tmp_path):
    ledger, ds = _stores(tmp_path)
    inh = _inh(tmp_path, ledger, ds)
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    _prep(ledger, pid, [("studies", "openalex_evidence", "barefoot", "")])
    inh._execute_checklist(ledger.get(pid), TODAY)
    recs = ds.for_project(pid)
    assert len(recs) == 1
    r = recs[0]
    assert r["skill"] == "openalex_evidence"
    assert ds.content_for(r["id"])["hits"][0]["title"] == "Study on barefoot"   # VOLLEDIGE output in sidecar
    assert r["summary"].startswith("📎")
    assert r["wall_note_id"] in [e.get("id") for e in ledger.get(pid).get("log", [])]   # link klopt
    item = inh._project_checklist(ledger.get(pid))["items"][0]
    assert r["checklist_item"] == item["id"] and r["title"] == "studies"   # adresseerbaar id + leesbare tekst


def test_checklist_item_zonder_id_valt_terug_op_positie(tmp_path, caplog):
    ledger, ds = _stores(tmp_path)
    inh = _inh(tmp_path, ledger, ds)
    with caplog.at_level(logging.WARNING):
        inh._store_deliverable({"id": "p9"}, {"text": "geen-id-item"}, 3, "s",
                               {"x": 1}, "📎 geen-id-item", "w1")     # item zonder 'id'
    rec = ds.for_project("p9")[0]
    assert rec["checklist_item"] == "pos:3" and rec["title"] == "geen-id-item"   # positie-adres
    assert "zonder id" in caplog.text                                # luid gemeld


def test_faalnote_geen_record(tmp_path):
    ledger, ds = _stores(tmp_path)
    inh = _inh(tmp_path, ledger, ds)
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    _prep(ledger, pid, [("boom-item", "openalex_evidence", "boom", "")])
    inh._execute_checklist(ledger.get(pid), TODAY)
    assert ds.for_project(pid) == []                          # faal → geen record
    assert any("niet gelukt" in e["text"] for e in ledger.get(pid).get("log", []))   # wel ⚠️ wall-note


def test_store_fout_laat_wall_note_intact(tmp_path):
    ledger, ds = _stores(tmp_path)
    inh = _inh(tmp_path, ledger, ds)
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    _prep(ledger, pid, [("studies", "openalex_evidence", "barefoot", "")])
    def _boom(**k):
        raise RuntimeError("store kapot")
    ds.add = _boom                                            # store-write faalt
    inh._execute_checklist(ledger.get(pid), TODAY)           # mag NIET crashen (additief)
    p = ledger.get(pid)
    assert inh._project_checklist(p)["items"][0]["done"] is True         # item toch afgevinkt
    assert any(e.get("text", "").startswith("📎") for e in p.get("log", []))   # wall-note staat er


def test_project_completed_draagt_deliverable_ids(tmp_path):
    # Review-gate: uitvoer schrijft de deliverable + zet WACHT; project_completed (mét deliverable_ids)
    # komt pas bij mens-DONE via de board-watch (village._poll_board), niet autonoom.
    from types import SimpleNamespace as _NS
    from nooch_village.village import Village
    ledger, ds = _stores(tmp_path)
    inh = _inh(tmp_path, ledger, ds)
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    _prep(ledger, pid, [("studies", "openalex_evidence", "barefoot", "")])
    inh._claim_run_complete(pid)                            # → deliverable geschreven, project in WACHT
    did = ds.for_project(pid)[0]["id"]
    assert ledger.get(pid)["status"] == "blocked" and ledger.get(pid)["blocked_on"] == "review"
    # mens kent Done toe → board-watch vuurt project_completed met de deliverable_ids
    ledger.complete(pid, "checklist voltooid (1/1) — goedgekeurd na review")
    events = []
    bus = inh.bus; bus.subscribe("project_completed", lambda e: events.append(e.data))
    stub = _NS(context=_NS(projects=ledger, deliverables=ds, _autonomous_done=set()), bus=bus,
               _activated_seen=set(), _completed_seen=set())
    Village._poll_board(stub)
    assert events and events[0]["deliverable_ids"] == [did] and events[0]["route"] == "review"
