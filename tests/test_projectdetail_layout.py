"""Projectdetail-layout: bijlage in de composer-toolbar-rij (vóór Plaatsen) en de wall-scroll-container
met het scroll-naar-onderen-snippet. Puur render (geen gedragswijziging aan bijlage/composer)."""
from __future__ import annotations

from nooch_village import cockpit2


def _frag(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rid = "mother_earth__nooch__website_developer"
    pid = st.projects.create(rid, "X", "human")
    return cockpit2.render_project(cockpit2._Stores(dd), pid, csrf_token="t", fragment=True)


def test_bijlage_staat_voor_plaatsen_in_comp_row(tmp_path):
    frag = _frag(tmp_path)
    i_att, i_plaats = frag.find("comp-attach"), frag.find(">Plaatsen<")
    assert 0 < i_att < i_plaats                       # bijlage links op de toolbar-rij, Plaatsen daarna
    # het bijlage-gedrag (upload + link plakken) blijft ongewijzigd aanwezig
    assert "value='attach_file'" in frag and "value='attach_add'" in frag


def test_wall_scroll_container_en_snippet(tmp_path):
    frag = _frag(tmp_path)
    assert "class='wall-scroll'" in frag              # de scrollbare wall-container bestaat
    assert "w.scrollTop=w.scrollHeight" in frag       # zelf-meegedragen scroll-naar-onderen-snippet
