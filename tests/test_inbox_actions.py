"""Gedeelde inbox-acties: één gevalideerd pad voor CLI én cockpit.

Keyword-beslissing sluit het item én cureert in de bibliotheek; defer en confirm zijn
pure bookkeeping. Geen Village, geen netwerk."""
from __future__ import annotations
import pytest

from nooch_village.human_inbox import HumanInbox
from nooch_village.notes_store import NotesStore
from nooch_village.projects import ProjectLedger
from nooch_village.governance import Records
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.inbox_actions import (
    decide_keyword, defer_item, confirm_item, add_reference, route_to_project, mark_done,
    route_to_governance)


class _StubLibrary:
    def __init__(self):
        self.calls = []
    def curate(self, word, status, rationale="", evidence=None, by="Librarian"):
        self.calls.append({"word": word, "status": status, "by": by})
        return {"word": word, "status": status}


def _inbox_with_keyword(tmp_path, word="vegan sneakers"):
    hi = HumanInbox(str(tmp_path / "inbox.json"))
    iid = hi.add_keyword_escalation(word, reason="impliceert plastic",
                                    demand={"signal": "rising", "locale": "en"})
    return hi, iid


def test_approve_keyword_cureert_approved(tmp_path):
    hi, iid = _inbox_with_keyword(tmp_path)
    lib = _StubLibrary()
    res = decide_keyword(hi, lib, iid, "approve", reason="ok")
    assert res["ok"] and res["status"] == "approved"
    assert hi.get(iid)["status"] == "approved"
    assert lib.calls == [{"word": "vegan sneakers", "status": "approved", "by": "human"}]


def test_reject_keyword_cureert_forbidden(tmp_path):
    hi, iid = _inbox_with_keyword(tmp_path)
    lib = _StubLibrary()
    res = decide_keyword(hi, lib, iid, "reject", reason="greenwashing")
    assert res["ok"] and res["status"] == "forbidden"
    assert hi.get(iid)["status"] == "rejected"
    assert lib.calls[0]["status"] == "forbidden"


def test_decide_keyword_weigert_niet_pending(tmp_path):
    hi, iid = _inbox_with_keyword(tmp_path)
    lib = _StubLibrary()
    decide_keyword(hi, lib, iid, "approve")
    res = decide_keyword(hi, lib, iid, "reject")     # al beslist
    assert not res["ok"]
    assert len(lib.calls) == 1                        # tweede besluit raakt de bibliotheek niet


def test_decide_keyword_weigert_ander_type(tmp_path):
    hi = HumanInbox(str(tmp_path / "inbox.json"))
    iid = hi.add_means_gap("gap_x", "iets")
    lib = _StubLibrary()
    res = decide_keyword(hi, lib, iid, "approve")
    assert not res["ok"] and "geen keyword" in res["error"]
    assert lib.calls == []


def test_defer_item(tmp_path):
    hi, iid = _inbox_with_keyword(tmp_path)
    res = defer_item(hi, iid, reason="later")
    assert res["ok"]
    assert hi.get(iid)["status"] == "deferred"


def test_confirm_item_zonder_voorstel_faalt(tmp_path):
    hi, iid = _inbox_with_keyword(tmp_path)
    res = confirm_item(hi, iid)
    assert not res["ok"]


def test_confirm_item_met_voorstel(tmp_path):
    hi = HumanInbox(str(tmp_path / "inbox.json"))
    iid = hi.add_means_gap("gap_x", "iets")
    hi.propose_resolution(iid, by="harry_hemp", reason="ik dek dit nu")
    res = confirm_item(hi, iid)
    assert res["ok"]
    assert hi.get(iid)["status"] == "approved"


# ── Add Reference (capture info → kennis-kaart) ───────────────────────────────

def test_add_reference_schrijft_kaart_zonder_te_sluiten(tmp_path):
    """Een rail produceert een uitkomst maar sluit de spanning niet (multi-uitkomst)."""
    notes = NotesStore(str(tmp_path / "notes.json"))
    res = add_reference(notes, claim="Most vegan sneakers contain plastic.",
                        grounds="Material analysis from the nooch.earth article.")
    assert res["ok"]
    card = notes.get(res["card_id"])
    assert card is not None and "plastic" in card.claim
    assert card.grounds                                  # contract: grounds gevuld


def test_add_reference_weigert_zonder_grounds(tmp_path):
    notes = NotesStore(str(tmp_path / "notes.json"))
    res = add_reference(notes, claim="Een claim zonder bewijs.", grounds="")
    assert not res["ok"]
    assert notes.all() == []                             # niks geschreven (fail-closed)


# ── Add Project (uitkomst voor een rol) ───────────────────────────────────────

def test_route_to_project_maakt_project_zonder_te_sluiten(tmp_path):
    projects = ProjectLedger(str(tmp_path / "projects.json"))
    res = route_to_project(projects, owner="the_source",
                           scope="Onderzoek KB-datasets als NL-bron")
    assert res["ok"]
    proj = projects.get(res["pid"])
    assert proj["owner"] == "the_source" and "KB-datasets" in proj["scope"]


def test_route_to_project_vereist_owner_en_scope(tmp_path):
    projects = ProjectLedger(str(tmp_path / "projects.json"))
    res = route_to_project(projects, owner="", scope="iets")
    assert not res["ok"]
    assert projects.all() == []


# ── Bring to Governance (rol een skill geven) ─────────────────────────────────

def _records_with_role(tmp_path, role_id="trends"):
    recs = Records(str(tmp_path / "gov.json"))
    recs.put(Record(id="noochville", type=RecordType.CIRCLE, parent=None,
                    definition=RoleDefinition(purpose="anchor"), source="seed"))
    recs.put(Record(id=role_id, type=RecordType.ROLE, parent="noochville",
                    definition=RoleDefinition(purpose="iets", skills=["a"]), source="seed"))
    return recs


def test_route_to_governance_grant_skill_adopted(tmp_path):
    recs = _records_with_role(tmp_path, "trends")
    res = route_to_governance(recs, "trends", "serpapi_trends",
                              rationale="serpapi-bron bestaat en wordt aangeroepen")
    assert res["ok"] and res["status"] == "adopted"
    assert "serpapi_trends" in recs.get("trends").definition.skills


def test_route_to_governance_onbekende_rol_invalid(tmp_path):
    recs = _records_with_role(tmp_path, "trends")
    res = route_to_governance(recs, "bestaat_niet", "x",
                              rationale="lange genoege reden hier")
    assert not res["ok"] and res["status"] == "invalid"


def test_route_to_governance_korte_rationale_invalid(tmp_path):
    recs = _records_with_role(tmp_path, "trends")
    res = route_to_governance(recs, "trends", "x", rationale="kort")
    assert not res["ok"] and res["status"] == "invalid"
    assert "x" not in recs.get("trends").definition.skills      # niks toegevoegd


def test_een_spanning_meerdere_uitkomsten_dan_sluiten(tmp_path):
    """De kern-les: één spanning → meerdere uitkomsten, daarna bewust sluiten.
    Project + reference produceren, spanning blijft pending; mark_done sluit hem."""
    projects = ProjectLedger(str(tmp_path / "projects.json"))
    notes = NotesStore(str(tmp_path / "notes.json"))
    hi = HumanInbox(str(tmp_path / "inbox.json"))
    iid = hi.add_means_gap("nl_corpus", "NL-bron onbruikbaar")

    route_to_project(projects, owner="the_source", scope="Onderzoek KB-datasets")
    add_reference(notes, claim="The Dutch ngram corpus lacks core mission words.",
                  grounds="Coverage check found 9 missing strong-signal words.")
    assert hi.get(iid)["status"] == "pending"            # nog open na twee uitkomsten

    mark_done(hi, iid, reason="project + reference vastgelegd; accountability dekt no-data")
    assert hi.get(iid)["status"] == "withdrawn"          # nu bewust gesloten
    assert len(projects.all()) == 1 and len(notes.all()) == 1
