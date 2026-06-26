"""Cockpit UX brok 2: het lijst-pattern (_toptable) — top-N zichtbaar, rest achter een toggle."""
from __future__ import annotations

from nooch_village import cockpit

_TH = "<thead><tr><th>x</th></tr></thead>"


def test_toptable_toont_top_n_en_verbergt_rest():
    rows = [f"<tr><td>rij{i}</td></tr>" for i in range(7)]
    out = cockpit._toptable(_TH, rows, top=3)
    # eerste 3 staan in de zichtbare tabel
    assert "rij0" in out and "rij2" in out
    # de rest zit achter een toggle met een telling
    assert "<details" in out and "+4 van 7" in out
    assert "rij6" in out                                   # wel in de DOM (achter de toggle)


def test_toptable_geen_toggle_bij_weinig():
    rows = ["<tr><td>a</td></tr>", "<tr><td>b</td></tr>"]
    out = cockpit._toptable(_TH, rows, top=3)
    assert "<details" not in out                           # 2 rijen → geen toggle


def test_toptable_leeg():
    out = cockpit._toptable(_TH, [], empty="niks hier", cols=2)
    assert "niks hier" in out and "colspan=2" in out
