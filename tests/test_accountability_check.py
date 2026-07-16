"""Accountability-check: pure helpers (fail-closed) + het scherm + de dispatch-actie."""
from __future__ import annotations

import json
import os

from nooch_village import cockpit2
from nooch_village.skills_impl.accountability_check import (
    build_check_prompt, parse_check, check_accountabilities,
)

_ROLES = [
    {"role": "Website Watcher", "accountabilities": ["site monitoren", "bezoekersdata duiden"]},
    {"role": "Trends", "accountabilities": ["GSC-queries ophalen", "site monitoren"]},
]

_FAKE = json.dumps({
    "duplicates": [{"accountability": "site monitoren", "roles": ["Website Watcher", "Trends"],
                    "advies": "houd bij Website Watcher"}],
    "weak": [{"role": "Trends", "accountability": "GSC-queries ophalen",
              "herformulering": "wekelijks de top-GSC-queries ophalen en aan Library aanleveren",
              "waarom": "geen uitkomst benoemd"}],
})


def test_prompt_bevat_alle_accountabilities():
    p = build_check_prompt(_ROLES, mission="test")
    assert "site monitoren" in p and "GSC-queries ophalen" in p
    assert "Website Watcher" in p and "Trends" in p
    assert "DUBBELINGEN" in p and "FORMULERING" in p


def test_parse_faalt_closed_op_rommel():
    assert parse_check(None) == {"duplicates": [], "weak": []}
    assert parse_check("geen json hier") == {"duplicates": [], "weak": []}
    got = parse_check("```json\n" + _FAKE + "\n```")
    assert len(got["duplicates"]) == 1 and len(got["weak"]) == 1


def test_check_gebruikt_reason_fn():
    res = check_accountabilities(_ROLES, reason_fn=lambda p: _FAKE)
    assert res["ok"] and res["n_roles"] == 2
    assert res["duplicates"][0]["accountability"] == "site monitoren"
    # geen LLM (reason_fn gooit) → fail-closed lege check, geen crash
    res2 = check_accountabilities(_ROLES, reason_fn=lambda p: (_ for _ in ()).throw(RuntimeError()))
    assert res2["duplicates"] == [] and res2["weak"] == []


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def test_scherm_en_actie(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    html = cockpit2.render_accountabilities(st, dd, csrf_token="t")
    assert "Accountability-check" in html and "acc_check" in html
    assert "Alle accountabilities per rol" in html
    # schrijf een nep-resultaat en render opnieuw → toont bevindingen
    with open(os.path.join(dd, "accountability_check.json"), "w") as f:
        f.write(_FAKE)
    html2 = cockpit2.render_accountabilities(st, dd, csrf_token="t")
    assert "Dubbelingen (1)" in html2 and "Formulering (1)" in html2
    assert "site monitoren" in html2
