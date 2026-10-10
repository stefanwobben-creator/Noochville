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
