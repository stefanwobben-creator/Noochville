"""Woordenschat/kansen: rankt goedgekeurde woorden op de transparante kansrijkheid-score."""
from __future__ import annotations

import json
import os

from nooch_village import cockpit2
from nooch_village.views.woordenschat import kansrijkheid


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def test_score_formule():
    # volume 1000, competition 0.5, doelwit → 1000 * 1.0 / 0.5 = 2000
    e = {"function": "doelwit", "evidence": {"volume": 1000, "competition": 0.5}}
    assert kansrijkheid(e) == 2000.0
    # seed weegt lichter (fit 0.3)
    e2 = {"function": "volg", "evidence": {"volume": 1000, "competition": 0.5}}
    assert kansrijkheid(e2) == 600.0
    # ontbrekende velden fail-safe: geen volume → 0
    assert kansrijkheid({"function": "doelwit", "evidence": {}}) == 0.0


def test_scherm_rankt_op_kansrijkheid(tmp_path):
    dd = _dd(tmp_path)
    lib = {
        "earth shoes": {"status": "approved", "function": "doelwit",
                        "evidence": {"volume": 33100, "competition": 1.0, "position": 14}},
        "compostable shoes": {"status": "approved", "function": "doelwit",
                              "evidence": {"volume": 260, "competition": 1.0, "position": 11}},
        "verboden woord": {"status": "forbidden", "evidence": {"volume": 99999}},
    }
    with open(os.path.join(dd, "library.json"), "w") as f:
        json.dump(lib, f)
    html = cockpit2.render_woordenschat(dd)
    assert "Woordenschat" in html and "kansrijkheid = volume" in html
    assert "earth shoes" in html and "compostable shoes" in html
    assert "verboden woord" not in html                     # alleen approved
    # hoogste volume/score bovenaan
    assert html.index("earth shoes") < html.index("compostable shoes")
