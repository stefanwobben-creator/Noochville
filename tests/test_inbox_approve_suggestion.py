"""Test dat 'inbox approve' een suggestion-item afhandelt (was een stille no-op-bug)."""
from __future__ import annotations

import nooch_village.inbox.__main__ as inbox_cli
from nooch_village.human_inbox import HumanInbox


def test_approve_suggestion_sluit_het_item(tmp_path, monkeypatch, capsys):
    inbox = HumanInbox(str(tmp_path / "inbox.json"))
    iid = inbox.add_suggestion("nl_corpus_bron_onbruikbaar", "alternatieve bron evalueren")

    # CLI laadt zijn eigen inbox-instantie; wijs die naar onze temp-inbox.
    monkeypatch.setattr(inbox_cli, "_inbox_only", lambda: inbox)

    inbox_cli.main(["approve", iid, "akkoord"])

    item = inbox.get(iid)
    assert item["status"] == "approved"             # niet langer stil blijven hangen
    assert "geaccepteerd" in capsys.readouterr().out.lower()


def test_approve_onbekend_type_valt_in_vangnet(tmp_path, monkeypatch, capsys):
    """Een type zonder eigen branch sluit nu via het vangnet i.p.v. stil te doen."""
    inbox = HumanInbox(str(tmp_path / "inbox.json"))
    iid = inbox.add_suggestion("x", "y")
    # forceer een onbekend type
    inbox._items[iid]["type"] = "iets_nieuws"
    inbox._save()
    monkeypatch.setattr(inbox_cli, "_inbox_only", lambda: inbox)

    inbox_cli.main(["approve", iid])

    assert inbox.get(iid)["status"] == "approved"
