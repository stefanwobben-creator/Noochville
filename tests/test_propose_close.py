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


# ── Inhabitant.propose_close publiceert het juiste event ─────────────────────

def test_propose_close_publiceert_event():
    from types import SimpleNamespace
    from nooch_village.inhabitant import Inhabitant
    from nooch_village.models import Record, RoleDefinition, RecordType
    from nooch_village.event_bus import EventBus
    from nooch_village.skills import SkillRegistry

    bus = EventBus(name="t")
    events = []
    bus.subscribe("resolution_proposed", lambda e: events.append(e.data))
    rec = Record(id="harry_hemp", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="test"), source="seed")
    inh = Inhabitant(rec, bus, SkillRegistry(),
                     SimpleNamespace(settings={"reflect_interval_seconds": "0"}))
    inh.propose_close("nl_corpus_coverage", "nu gedekt")
    assert events == [{"gap_key": "nl_corpus_coverage", "reason": "nu gedekt", "from": "harry_hemp"}]


def test_harry_puls_stelt_voor_nl_corpus_te_sluiten(tmp_path):
    """Na een puls stelt Harry voor de gedekte gaten te sluiten (hier nl_corpus_coverage)."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
    from test_harry_hemp import _make_harry

    harry, bus = _make_harry(tmp_path, ngram_result={"rows": [], "terms": {}})
    voorstellen = []
    bus.subscribe("resolution_proposed", lambda e: voorstellen.append(e.data["gap_key"]))

    harry._run_pulse(None)

    assert "nl_corpus_coverage" in voorstellen
