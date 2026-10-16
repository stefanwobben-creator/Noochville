"""Rijen op het projectenbord (16 oktober 2026, besluit Stefan): alleen een gebruiker met een
people-record krijgt een eigen rij. Een onbekende `person` (zoals een login-e-mailadres) en elke
`agent` vallen onder "No owner"; de kaart toont dan ook geen initialen. De data blijft staan."""
from __future__ import annotations

import re

from nooch_village import cockpit2

ROL = "mother_earth__nooch__website_developer"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    mens = st.people.add("Ada Lovelace", "ada@nooch.earth")
    sid = st.personas.add("Sid the Science Kid")
    pj = st.projects
    pj.create(ROL, "Van Ada", "human", person=mens.id)
    pj.create(ROL, "Van een e-mailadres", "human", person="ada@nooch.earth")
    pj.create(ROL, "Van Sid", "human", agent=sid.id)
    pj.create(ROL, "Van niemand", "human")
    return dd, mens


def _kaart(page, titel):
    return page.split(f"title='{titel}'", 1)[1].split("class='card pcard", 1)[0]


def test_alleen_een_gebruiker_krijgt_een_rij(tmp_path):
    dd, _mens = _dorp(tmp_path)
    page = cockpit2.render_node(cockpit2._Stores(dd), ROL, "projects", csrf_token="t")
    rijen = re.findall(r"<div class='swim-h'>([^<]*)</div>", page)
    assert rijen == ["Ada Lovelace (1)", "No owner (3)"]
    assert "ada@nooch.earth" not in "".join(rijen) and "(AI)" not in "".join(rijen)


def test_de_kaart_volgt_dezelfde_regel(tmp_path):
    dd, _mens = _dorp(tmp_path)
    page = cockpit2.render_node(cockpit2._Stores(dd), ROL, "projects", csrf_token="t")
    assert "<span class='av' title='Ada Lovelace' aria-label='Ada Lovelace'>AL</span>" in _kaart(page, "Van Ada")
    for titel in ("Van een e-mailadres", "Van Sid", "Van niemand"):
        k = _kaart(page, titel)
        assert "<span class='muted'>no owner</span>" in k and "class='av" not in k, titel


def test_de_data_blijft_staan(tmp_path):
    dd, _mens = _dorp(tmp_path)
    st = cockpit2._Stores(dd)
    cockpit2.render_node(st, ROL, "projects", csrf_token="t")
    per = {p["scope"]: p for p in cockpit2._Stores(dd).projects.all()}
    assert per["Van een e-mailadres"]["person"] == "ada@nooch.earth"
    assert per["Van Sid"]["agent"]


def test_elke_agent_valt_onder_no_owner_ook_naast_een_gebruiker(tmp_path):
    """Komt op prod niet voor (16 oktober 2026: 0 projecten met beide), maar de regel is "elke agent"."""
    dd, mens = _dorp(tmp_path)
    st = cockpit2._Stores(dd)
    sid = next(p for p in st.projects.all() if p["scope"] == "Van Sid")
    sid["person"] = mens.id
    st.projects._save()
    page = cockpit2.render_node(cockpit2._Stores(dd), ROL, "projects", csrf_token="t")
    assert re.findall(r"<div class='swim-h'>([^<]*)</div>", page) == ["Ada Lovelace (1)", "No owner (3)"]
