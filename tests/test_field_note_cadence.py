"""Field Note: dagelijkse data blijft, dure LLM-proza is gepoort (standaard wekelijks)."""
from __future__ import annotations

import json
import os
import types

from nooch_village.skills_impl.field_note import FieldNoteSkill


def _ctx(tmp_path):
    dd = str(tmp_path)
    os.makedirs(dd, exist_ok=True)
    return types.SimpleNamespace(data_dir=dd, settings={})


_PLAUS = {"results": {"visitors": {"value": 120}}}


def test_prose_false_schrijft_data_maar_geen_note_of_kroniek(tmp_path):
    ctx = _ctx(tmp_path)
    res = FieldNoteSkill().run({"plausible": _PLAUS, "trends": {}, "prose": False}, ctx)
    # geen LLM-note geschreven
    assert res["path"] is None and res["prose"] is False
    mds = [f for f in os.listdir(os.path.join(str(tmp_path), "output")) if f.startswith("field_note_")]
    assert mds == []                                        # geen .md
    assert not os.path.exists(os.path.join(str(tmp_path), "evidence_ledger.jsonl"))   # geen Kroniek-regel
    # data WEL geschreven: last_pulse + raw json
    assert os.path.exists(os.path.join(str(tmp_path), "last_pulse.json"))
    raws = [f for f in os.listdir(os.path.join(str(tmp_path), "output")) if f.startswith("pulse_raw_")]
    assert len(raws) == 1
    assert json.load(open(os.path.join(str(tmp_path), "last_pulse.json")))["visitors"] == 120


def test_prose_default_true_backward_compat(tmp_path):
    # Zonder 'prose' in de payload = oude gedrag: volledige note (LLM-compose draait).
    ctx = _ctx(tmp_path)
    res = FieldNoteSkill().run({"plausible": _PLAUS, "trends": {}}, ctx)
    assert res.get("path") and res["path"].endswith(".md")
    assert os.path.exists(res["path"])
