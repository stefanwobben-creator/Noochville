"""Linkbuilding in cockpit 2: toont doelwitten uit LinkTargets; pitchen/negeren verplaatst ze."""
from __future__ import annotations

import os

from nooch_village import cockpit2
from nooch_village.link_targets import LinkTargets


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def test_lege_linkbuilding(tmp_path):
    dd = _dd(tmp_path)
    html = cockpit2.render_linkbuilding(dd, csrf_token="t")
    assert "Linkbuilding" in html and "Nog geen doelwitten" in html


def test_toont_kandidaten_en_pitch_ignore(tmp_path):
    dd = _dd(tmp_path)
    store = LinkTargets(os.path.join(dd, "linkbuilding_targets.json"))
    store.add_candidate("https://gids.nl/beste-barefoot", "Beste barefoot gids", "SerpApi", "hoog")
    store.add_candidate("https://blog.nl/vegan", "Vegan blog", "SerpApi", "laag")
    html = cockpit2.render_linkbuilding(dd, csrf_token="t")
    assert "Beste barefoot gids" in html and "Vegan blog" in html
    assert "link_pursue" in html and "link_ignore" in html
    assert "2 te beoordelen" in html
    # hoog staat boven laag (prioriteit-sortering)
    assert html.index("Beste barefoot gids") < html.index("Vegan blog")
    # pitchen verplaatst naar 'pursued'
    cockpit2.dispatch(dd, "link_pursue",
                      {"link": ["https://gids.nl/beste-barefoot"], "next": ["/linkbuilding"]},
                      username="stefan")
    st = LinkTargets(os.path.join(dd, "linkbuilding_targets.json"))
    assert st.status("https://gids.nl/beste-barefoot") == "pursued"
    html2 = cockpit2.render_linkbuilding(dd, csrf_token="t")
    assert "Wordt gepitcht (1)" in html2


def test_gast_mag_niet_beslissen(tmp_path):
    dd = _dd(tmp_path)
    store = LinkTargets(os.path.join(dd, "linkbuilding_targets.json"))
    store.add_candidate("https://x.nl/a", "A", "s", "midden")
    cockpit2.dispatch(dd, "link_pursue", {"link": ["https://x.nl/a"], "next": ["/"]}, username="guest")
    assert LinkTargets(os.path.join(dd, "linkbuilding_targets.json")).status("https://x.nl/a") == "candidate"
