"""read_json: leest JSON fail-loud. 'Kan niet lezen' wordt nooit stil 'leeg'."""
from __future__ import annotations

import json
import os

import pytest

from nooch_village.util import read_json


def test_ontbrekend_bestand_geeft_default(tmp_path):
    p = str(tmp_path / "weg.json")
    assert read_json(p, {}) == {}
    assert read_json(p, [], expect=list) == []


def test_geldige_dict_wordt_gelezen(tmp_path):
    p = str(tmp_path / "d.json")
    open(p, "w").write(json.dumps({"a": 1}))
    assert read_json(p, {}) == {"a": 1}


def test_verkeerd_toplevel_type_raiset(tmp_path):
    # een lijst waar een dict verwacht wordt → luid, niet stil leeg
    p = str(tmp_path / "lijst.json")
    open(p, "w").write(json.dumps([1, 2, 3]))
    with pytest.raises(RuntimeError):
        read_json(p, {})                      # expect=dict (default)
    # met expect=list is dezelfde inhoud wél geldig
    assert read_json(p, [], expect=list) == [1, 2, 3]


def test_corrupte_json_raiset(tmp_path):
    p = str(tmp_path / "kapot.json")
    open(p, "w").write("{ niet: geldige json ]")
    with pytest.raises(RuntimeError):
        read_json(p, {})


def test_onleesbaar_bestand_raiset(tmp_path):
    # permissie-fout mag nooit stil 'leeg' worden (de bug die dit voorkomt)
    p = str(tmp_path / "geheim.json")
    open(p, "w").write(json.dumps({"a": 1}))
    os.chmod(p, 0o000)
    try:
        if os.access(p, os.R_OK):           # draait als root? dan is de permissie-test zinloos
            pytest.skip("proces kan altijd lezen (root) — permissie-pad niet testbaar")
        with pytest.raises(RuntimeError):
            read_json(p, {})
    finally:
        os.chmod(p, 0o644)                  # opruimen zodat tmp_path verwijderd kan worden


def test_expect_none_slaat_typecheck_over(tmp_path):
    p = str(tmp_path / "x.json")
    open(p, "w").write(json.dumps([1, 2]))
    assert read_json(p, None, expect=None) == [1, 2]
