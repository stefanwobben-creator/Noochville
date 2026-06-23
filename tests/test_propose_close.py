"""Tests voor 'ik dek dit nu, voorstel tot sluiten' (rol stelt voor, mens bevestigt). Thread-vrij."""
from __future__ import annotations

from nooch_village.human_inbox import HumanInbox


def _inbox(tmp_path):
    return HumanInbox(str(tmp_path / "inbox.json"))


def test_find_by_gap(tmp_path):
    inbox = _inbox(tmp_path)
    iid = inbox.add_suggestion("nl_corpus_coverage", "NL-dekking")
    assert inbox.find_by_gap("nl_corpus_coverage") == iid
    assert inbox.find_by_gap("bestaat_niet") is None


def test_propose_resolution_zet_voorstel_status_blijft_pending(tmp_path):
    inbox = _inbox(tmp_path)
    iid = inbox.add_suggestion("ngram_2019_cutoff", "cutoff")
    assert inbox.propose_resolution(iid, "harry_hemp", "ik dek dit nu via voortzetting") is True
    item = inbox.get(iid)
    assert item["status"] == "pending"                      # nog niet gesloten
    assert item["proposed_resolution"]["by"] == "harry_hemp"


def test_confirm_resolution_sluit_het_item(tmp_path):
    inbox = _inbox(tmp_path)
    iid = inbox.add_suggestion("ngram_2019_cutoff", "cutoff")
    inbox.propose_resolution(iid, "harry_hemp", "gedekt via OpenAlex-voortzetting")
    assert inbox.confirm_resolution(iid, by_human="Stefan") is True
    item = inbox.get(iid)
    assert item["status"] == "approved"
    assert item["resolution"]["confirmed_by"] == "Stefan"
    assert item["resolution"]["proposed_by"] == "harry_hemp"


def test_confirm_zonder_voorstel_faalt(tmp_path):
    """De mens kan niets bevestigen wat geen rol heeft voorgesteld (geen lege approvals)."""
    inbox = _inbox(tmp_path)
    iid = inbox.add_suggestion("x", "y")
    assert inbox.confirm_resolution(iid) is False
    assert inbox.get(iid)["status"] == "pending"


def test_rol_sluit_niet_zelf(tmp_path):
    """propose_resolution sluit NOOIT zelf — alleen de mens-bevestiging doet dat."""
    inbox = _inbox(tmp_path)
    iid = inbox.add_suggestion("g", "d")
    inbox.propose_resolution(iid, "harry_hemp", "klaar")
    assert inbox.get(iid)["status"] == "pending"            # geen dichtgeklapte lus
