"""Cross-path-memory voor means-gaps: een gat dat al in de inbox-historie staat (welke status
dan ook) wordt niet opnieuw gesensed. Dicht de 'resolve-dan-opnieuw'-lus waarin Harry elke
reflect nl_corpus_bron_onbruikbaar opnieuw publiceerde en de B-observer het telkens als ruis
her-evalueerde."""
from __future__ import annotations
import json
import logging
import types
from types import SimpleNamespace

from nooch_village.inhabitant import Inhabitant


def _stub(data_dir):
    s = SimpleNamespace(id="harry_hemp", log=logging.getLogger("t"))
    s.context = SimpleNamespace(data_dir=str(data_dir))
    s._events = []
    s.bus = SimpleNamespace(publish=lambda e: s._events.append(e))
    s._report_means_gap = types.MethodType(Inhabitant._report_means_gap, s)
    s._means_gap_already_known = types.MethodType(Inhabitant._means_gap_already_known, s)
    return s


def _write_inbox(data_dir, items):
    (data_dir / "human_inbox.json").write_text(json.dumps(items, ensure_ascii=False))


def test_geen_inbox_dan_wel_sensen(tmp_path):
    s = _stub(tmp_path)
    s._report_means_gap("nl_corpus_bron_onbruikbaar", "NL-corpus mist alledaagse woorden")
    sensed = [e for e in s._events if e.name == "means_gap_sensed"]
    assert len(sensed) == 1
    assert sensed[0].data["gap_key"] == "nl_corpus_bron_onbruikbaar"


def test_al_gemeld_pending_dan_stil(tmp_path):
    _write_inbox(tmp_path, {
        "abc": {"id": "abc", "type": "means_gap",
                "subject": "nl_corpus_bron_onbruikbaar", "status": "pending"}})
    s = _stub(tmp_path)
    s._report_means_gap("nl_corpus_bron_onbruikbaar", "x")
    assert [e for e in s._events if e.name == "means_gap_sensed"] == []


def test_al_resolved_dan_ook_stil(tmp_path):
    """De kern van de bug: een door de mens RESOLVED gat mag niet terugkomen."""
    _write_inbox(tmp_path, {
        "abc": {"id": "abc", "type": "means_gap",
                "subject": "nl_corpus_bron_onbruikbaar", "status": "resolved"}})
    s = _stub(tmp_path)
    s._report_means_gap("nl_corpus_bron_onbruikbaar", "x")
    assert [e for e in s._events if e.name == "means_gap_sensed"] == []


def test_ander_gap_wordt_niet_onderdrukt(tmp_path):
    """Een ander, nieuw gat blijft wél gesensed worden (geen overmatige onderdrukking)."""
    _write_inbox(tmp_path, {
        "abc": {"id": "abc", "type": "means_gap",
                "subject": "nl_corpus_bron_onbruikbaar", "status": "resolved"}})
    s = _stub(tmp_path)
    s._report_means_gap("pairs_sold_niet_meetbaar", "verkoop niet meetbaar in de puls")
    sensed = [e for e in s._events if e.name == "means_gap_sensed"]
    assert len(sensed) == 1 and sensed[0].data["gap_key"] == "pairs_sold_niet_meetbaar"
