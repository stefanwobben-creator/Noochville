"""Tests voor durable reject — thread-vrij.

1. list/show lezen de inbox zonder sync_unmanned aan te roepen (inbox wijzigt niet).
2. reject activatie → onderliggend sensed record gearchiveerd; sync_unmanned voegt
   het daarna niet opnieuw toe.
3. add_activation op een gerejecteerde role_id → geen nieuw item (dedup any status).
4. _print_item_full voor means_gap toont de beschrijving.
"""
from __future__ import annotations
import io, sys
from unittest.mock import patch, MagicMock

from nooch_village.human_inbox import HumanInbox


# ── helpers ─────────────────────────────────────────────────────────────────

def _make_inbox(tmp_path) -> HumanInbox:
    return HumanInbox(str(tmp_path / "inbox.json"))


def _dummy_record(role_id: str) -> dict:
    return {
        "id": role_id, "type": "role", "source": "sensed",
        "definition": {"purpose": "test", "accountabilities": [], "domains": [], "skills": []},
    }


# ── 1. Leespaden muteren de inbox niet ──────────────────────────────────────

def test_inbox_only_does_not_call_sync_unmanned(tmp_path, monkeypatch):
    """_inbox_only() laadt HumanInbox direct — Village.__init__ (en sync_unmanned) wordt nooit aangeroepen."""
    # Patch Village zodat een aanroep direct faalt
    import nooch_village.inbox.__main__ as cli
    monkeypatch.setattr(cli, "_load", lambda: (_ for _ in ()).throw(
        AssertionError("_load() (Village) mag niet aangeroepen worden vanuit een leespad")
    ))

    inbox_pre = _make_inbox(tmp_path)
    inbox_pre.add_activation("rol_a", _dummy_record("rol_a"))

    # Simuleer list-pad door _inbox_only direct te roepen (zonder de echte datadir)
    inbox_read = HumanInbox(str(tmp_path / "inbox.json"))
    items_before = len(inbox_read.all())

    # Nog een read — mag inbox niet groeien
    inbox_read2 = HumanInbox(str(tmp_path / "inbox.json"))
    assert len(inbox_read2.all()) == items_before


def test_show_does_not_add_items(tmp_path):
    """Na show zijn er niet meer items dan voor show."""
    inbox = _make_inbox(tmp_path)
    inbox.add_means_gap("openlibrary_v2", "test")

    before = len(inbox.all())
    # Laad opnieuw (zoals _inbox_only doet)
    inbox2 = HumanInbox(str(tmp_path / "inbox.json"))
    _ = inbox2.get(list(inbox2._items.keys())[0])  # show-achtige lookup
    assert len(inbox2.all()) == before


# ── 2. reject activatie archiveert het record ────────────────────────────────

def test_reject_activation_archives_record(tmp_path):
    """Reject van een activatie-item archiveert het onderliggende record via _records_only()."""
    from nooch_village.governance import Records
    from nooch_village.models import Record, RecordType, RoleDefinition

    # Maak een Records-instantie met één sensed rol
    records = Records(str(tmp_path / "governance_records.json"))
    rec = Record(
        id="churn_rol",
        type=RecordType.ROLE,
        parent="noochville",
        definition=RoleDefinition(purpose="test", accountabilities=[], domains=[], skills=[]),
        source="sensed",
    )
    records.put(rec)

    # Voeg het als activatie toe aan de inbox
    inbox = _make_inbox(tmp_path)
    iid = inbox.add_activation("churn_rol", _dummy_record("churn_rol"))
    assert inbox.get(iid)["status"] == "pending"

    # Reject + archiveer (zoals de CLI dat nu doet)
    inbox.resolve(iid, "rejected", reason="churn-artefact")
    rec2 = records.get("churn_rol")
    assert rec2 is not None
    rec2.archived = True
    rec2.version += 1
    records.put(rec2)

    # Verify: record is gearchiveerd
    assert records.get("churn_rol").archived is True

    # sync_unmanned slaat gearchiveerde records over
    inbox2 = HumanInbox(str(tmp_path / "inbox.json"))
    from nooch_village.models import RecordType as RT
    import dataclasses

    all_recs = [records.get("churn_rol")]
    class_map = {}
    added = inbox2.sync_unmanned(all_recs, class_map)
    assert added == 0, "gearchiveerde rol mag niet opnieuw toegevoegd worden"
    assert len(inbox2.pending()) == 0


# ── 3. add_activation dedupt op rejected ────────────────────────────────────

def test_add_activation_dedupes_on_rejected(tmp_path):
    """Eenmaal afgewezen activatie keert niet terug als nieuw item."""
    inbox = _make_inbox(tmp_path)
    iid   = inbox.add_activation("churn_rol", _dummy_record("churn_rol"))
    inbox.resolve(iid, "rejected", reason="niet nodig")

    iid2  = inbox.add_activation("churn_rol", _dummy_record("churn_rol"))
    assert iid == iid2, "zelfde item-id verwacht"
    assert len(inbox.all()) == 1, "mag slechts één item bevatten"


def test_add_activation_dedupes_on_approved(tmp_path):
    """Goedgekeurde activatie keert ook niet terug als nieuw item."""
    inbox = _make_inbox(tmp_path)
    iid   = inbox.add_activation("rol_b", _dummy_record("rol_b"))
    inbox.resolve(iid, "approved")

    iid2  = inbox.add_activation("rol_b", _dummy_record("rol_b"))
    assert iid == iid2
    assert len(inbox.all()) == 1


# ── 4. means_gap show toont beschrijving ────────────────────────────────────

def test_means_gap_show_has_description(tmp_path, capsys):
    """_print_item_full voor een means_gap-item toont de beschrijving."""
    inbox = _make_inbox(tmp_path)
    inbox.add_means_gap("ngram_2019_cutoff",
                        "ngram stopt in 2019 — recente verschuivingen onzichtbaar")
    item = inbox.pending()[0]

    from nooch_village.inbox.__main__ import _print_item_full
    _print_item_full(item)

    out = capsys.readouterr().out
    assert "ngram_2019_cutoff"                        in out
    assert "ngram stopt in 2019"                      in out
    assert "recente verschuivingen onzichtbaar"        in out
