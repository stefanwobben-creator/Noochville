"""De Kroniek — ladder ingehaakt in de skill-executor (_use_skill_with_ladder). Een skill mét ladder
(epo_patents → google_patents) rerouteert bij een dode route, logt in het bewijsregister en escaleert
als láátste tree; een skill zónder ladder draait ongewijzigd."""
from __future__ import annotations

import json
import os
import types

from nooch_village.inhabitant import Inhabitant
from nooch_village.evidence_ledger import EvidenceLedger


def _fake_inhabitant(tmp_path, results):
    """Minimale fake: use_skill zoekt het resultaat per skill-naam op in `results`."""
    calls = []
    def use_skill(name, payload):
        calls.append(name)
        return results[name]
    self = types.SimpleNamespace(
        id="harry_hemp",
        context=types.SimpleNamespace(data_dir=str(tmp_path)),
        use_skill=use_skill,
    )
    self._calls = calls
    return self


def test_skill_zonder_ladder_ongewijzigd(tmp_path):
    self = _fake_inhabitant(tmp_path, {"openalex_evidence": {"hits": [1]}})
    out = Inhabitant._use_skill_with_ladder(self, "openalex_evidence", {"term": "x"})
    assert out == {"hits": [1]} and self._calls == ["openalex_evidence"]
    assert not os.path.exists(os.path.join(str(tmp_path), "evidence_ledger.jsonl"))   # geen ladder → geen log


def test_epo_faalt_google_bevestigt(tmp_path):
    self = _fake_inhabitant(tmp_path, {
        "epo_patents":    {"error": "EPO OPS: HTTP 500", "patents": []},
        "google_patents": {"total": 1, "patents": [{"title": "Biodegradable sole"}]},
    })
    out = Inhabitant._use_skill_with_ladder(self, "epo_patents", {"term": "PHA sole"})
    assert out == {"total": 1, "patents": [{"title": "Biodegradable sole"}]}          # google's resultaat
    assert self._calls == ["epo_patents", "google_patents"]                           # dode route → alt-pad
    recs = EvidenceLedger(os.path.join(str(tmp_path), "evidence_ledger.jsonl")).all_records()
    assert [r["status"] for r in recs] == ["fout", "bevestigd"]                        # beide onthouden
    assert [r["source"] for r in recs] == ["epo_patents", "google_patents"]


def test_beide_bronnen_falen_escaleert_naar_human_inbox(tmp_path):
    self = _fake_inhabitant(tmp_path, {
        "epo_patents":    {"error": "down", "patents": []},
        "google_patents": {"error": "HTTP 403", "patents": []},
    })
    out = Inhabitant._use_skill_with_ladder(self, "epo_patents", {"term": "x"})
    assert "error" in out                                                             # geen crash, gat teruggegeven
    inbox = json.load(open(os.path.join(str(tmp_path), "human_inbox.json")))
    subjects = [it.get("subject") for it in inbox.values()]
    assert "skill_ladder:epo_patents" in subjects                                     # láátste tree: mens gewekt
    recs = EvidenceLedger(os.path.join(str(tmp_path), "evidence_ledger.jsonl")).all_records()
    assert [r["status"] for r in recs] == ["fout", "fout"]
