"""De herstel-toets van de back-up (10 oktober 2026): hij moet een kapotte snapshot herkennen."""
from __future__ import annotations

import importlib.util
import os

from nooch_village import cockpit2

_PAD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts",
                    "backup_herstel_toets.py")
_spec = importlib.util.spec_from_file_location("backup_herstel_toets", _PAD)
toets_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(toets_mod)


def _data(tmp_path):
    dd = str(tmp_path / "data")
    cockpit2._bootstrap(dd)
    return dd


def test_een_gezonde_snapshot_is_te_herstellen(tmp_path):
    assert toets_mod.toets(_data(tmp_path)) == []


def test_een_half_geschreven_json_valt_op(tmp_path):
    dd = _data(tmp_path)
    open(os.path.join(dd, "people.json"), "w").write('{"half": ')
    fouten = toets_mod.toets(dd)
    assert any("people.json" in f and "geen geldige JSON" in f for f in fouten)


def test_alleen_de_laatste_jsonl_regel_mag_half_zijn(tmp_path):
    dd = _data(tmp_path)
    pad = os.path.join(dd, "log.jsonl")
    open(pad, "w").write('{"a": 1}\n{"b": ')                  # een append die net liep: geen fout
    assert toets_mod.toets(dd) == []
    open(pad, "w").write('{"a": 1}\nkapot\n{"c": 3}\n')        # middenin kapot: wel een fout
    assert any("log.jsonl" in f for f in toets_mod.toets(dd))


def test_een_lege_map_is_geen_back_up(tmp_path):
    leeg = tmp_path / "leeg"
    leeg.mkdir()
    assert toets_mod.toets(str(leeg))                          # geen records, geen mensen
    assert toets_mod.toets(str(tmp_path / "bestaat_niet")) == [f"geen map: {tmp_path / 'bestaat_niet'}"]


def test_finance_bijlagen_worden_tegen_hun_sha256_nagelopen(tmp_path):
    import hashlib
    import json
    dd = _data(tmp_path)
    os.makedirs(os.path.join(dd, "finance", "attachments", "2026"))
    blob = b"%PDF-1.4 factuur"
    rel = "finance/attachments/2026/a.pdf"
    open(os.path.join(dd, rel), "wb").write(blob)
    regel = {"id": "k1", "attachment": {"path": rel, "sha256": hashlib.sha256(blob).hexdigest()}}
    open(os.path.join(dd, "finance", "costs.jsonl"), "w").write(json.dumps(regel) + "\n")
    assert toets_mod.toets(dd) == []
    open(os.path.join(dd, rel), "ab").write(b"x")                     # beschadigd in de back-up
    assert any("sha256" in f for f in toets_mod.toets(dd))
    os.remove(os.path.join(dd, rel))
    assert any("ontbreekt" in f for f in toets_mod.toets(dd))
