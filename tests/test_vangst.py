"""Vangst — vangen scheiden van verwerken.

Vier beloften:
  1. vangen legt de zin vast en verder NIETS: geen bevinding, geen typering, geen kaart;
  2. het gevangen punt overleeft een herlaadbeurt en toont wie het inbracht;
  3. wie het inbracht reist mee, zodat het bij verwerken zíjn spanning wordt;
  4. verwerken hergebruikt de bestaande pijplijn: een spanning gaat door dezelfde haak die elke
     verse spanning typeert, en een project landt op het bord van de gekozen rol.
"""
from __future__ import annotations

import pytest

from nooch_village import cockpit2
from nooch_village.views.vangst import render_vangst

CIRCLE = "mother_earth__nooch"
ROL = "mother_earth__nooch__creator_of_shoes"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def _post(dd, action, **velden):
    return cockpit2.dispatch(dd, action, {k: [v] for k, v in velden.items()}, username="guest")


def _punten(dd):
    return cockpit2._Stores(dd).werk.punten(CIRCLE)


# ── 1. vangen schrijft alleen de zin ────────────────────────────────────────

def test_vangen_legt_vast_en_typeert_niets(tmp_path):
    dd = _dd(tmp_path)
    _post(dd, "vangst_add", circle=CIRCLE, punt="de leverancier belt nooit terug", next="/vangst")
    st = cockpit2._Stores(dd)
    punten = st.werk.punten(CIRCLE)
    assert [p["title"] for p in punten] == ["de leverancier belt nooit terug"]
    assert punten[0]["status"] == "open"
    assert punten[0].get("outcome") is None
    # Niets getypeerd, niets geschreven: geen enkele kaart bij wie dan ook.
    assert st.notif.all() == []


def test_lege_enter_is_geen_fout(tmp_path):
    dd = _dd(tmp_path)
    _nxt, msg = _post(dd, "vangst_add", circle=CIRCLE, punt="   ", next="/vangst")
    assert msg == ""
    assert _punten(dd) == []


def test_vangen_geeft_geen_banner(tmp_path):
    """Een bevestigingsbanner zou de aandacht (en op sommige schermen de focus) uit het veld halen;
    drie punten achter elkaar typen moet zonder onderbreking kunnen."""
    dd = _dd(tmp_path)
    _nxt, msg = _post(dd, "vangst_add", circle=CIRCLE, punt="een punt", next="/vangst")
    assert msg == ""


# ── 2. het punt blijft staan, en het scherm toont hem ───────────────────────

def test_drie_punten_blijven_staan_na_herladen(tmp_path):
    dd = _dd(tmp_path)
    for zin in ("eerste punt", "tweede punt", "derde punt"):
        _post(dd, "vangst_add", circle=CIRCLE, punt=zin, next="/vangst")
    # Verse stores = wat een herlaadbeurt ziet.
    html = render_vangst(cockpit2._Stores(dd), CIRCLE, csrf_token="t")
    for zin in ("eerste punt", "tweede punt", "derde punt"):
        assert zin in html
    # Het veld staat er nog, leeg, met de cursor erin — anders is de één-toets-flow weg.
    assert "autofocus" in html and "vangst_add" in html


def test_scherm_toont_wie_het_inbracht(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    st.werk.backlog_add(CIRCLE, "punt van iemand", by="Stefan Wobben", by_id="p1")
    html = render_vangst(cockpit2._Stores(dd), CIRCLE, csrf_token="t")
    assert "Stefan Wobben" in html


# ── 3. de inbrenger reist mee ───────────────────────────────────────────────

def test_inbrenger_wordt_de_afzender_van_de_spanning(tmp_path, monkeypatch):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    it = st.werk.backlog_add(CIRCLE, "hier klopt iets niet aan de levertijden",
                             by="Stefan Wobben", by_id="p-stefan")
    _post(dd, "vangst_verwerk", circle=CIRCLE, iid=it["id"], otype="spanning", rol=ROL,
          next="/vangst")
    items = cockpit2._Stores(dd).notif.all()
    assert len(items) == 1
    assert items[0]["by"] == "p-stefan"                 # niet 'werkoverleg', niet leeg
    assert items[0]["snippet"] == "hier klopt iets niet aan de levertijden"


# ── 4. verwerken hergebruikt wat er al staat ────────────────────────────────

def test_spanning_gaat_ongetypeerd_de_bestaande_haak_in(tmp_path, monkeypatch):
    """De kaart mag hier NIET al een type dragen: dan zou `NotifStore.add` de haak overslaan en
    zou de vangst zijn eigen typering doen in plaats van de bestaande.

    En de haak moet ECHT gezet worden op de store die de actie gebruikt. `_bootstrap` zet hem op een
    `_Stores` die daarna wordt weggegooid, en elke request bouwt een verse — dus zonder deze regel
    draait de bevinding-schrijver in het web-pad nergens."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    it = st.werk.backlog_add(CIRCLE, "een punt om te verwerken", by_id="p1")
    gezien = {}

    def _nep_verrijker(records, assignments, data_dir="", reason_fn=None):
        def _fn(n):
            gezien.update(n)
            return {"type": "naar_rol",
                    "bevinding": {"ok": True, "spanning": "x", "voorstel": "y"}}
        return _fn

    monkeypatch.setattr("nooch_village.spanning_ontstaat.maak_verrijker", _nep_verrijker)
    _post(dd, "vangst_verwerk", circle=CIRCLE, iid=it["id"], otype="spanning", rol=ROL,
          next="/vangst")
    assert gezien.get("snippet") == "een punt om te verwerken"      # de haak is echt gedraaid
    assert not gezien.get("type")                                   # ongetypeerd de haak in
    item = cockpit2._Stores(dd).notif.all()[0]
    assert item["type"] == "naar_rol"                               # de haak typeerde hem
    assert item["bevinding"]["ok"] is True


def test_punt_wordt_project_op_het_bord_van_een_rol(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    it = st.werk.backlog_add(CIRCLE, "zool-leverancier vergelijken", by_id="p1")
    _nxt, msg = _post(dd, "vangst_verwerk", circle=CIRCLE, iid=it["id"], otype="project",
                      owner=ROL, tekst="zool-leverancier vergelijken", next="/vangst")
    assert msg.startswith("✓ project")
    st2 = cockpit2._Stores(dd)
    assert [p for p in st2.projects.all() if p.get("owner") == ROL
            and "zool-leverancier" in str(p.get("scope"))]
    # En het punt staat als verwerkt in de lijst — de ruwe tekst blijft staan.
    punt = st2.werk.punt_get(CIRCLE, it["id"])
    assert punt["status"] == "done" and punt["outcome"]["type"] == "project"
    assert "zool-leverancier vergelijken" in punt["title"]


def test_een_verwerkt_punt_wordt_niet_twee_keer_verwerkt(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    it = st.werk.backlog_add(CIRCLE, "dubbel verwerken", by_id="p1")
    _post(dd, "vangst_verwerk", circle=CIRCLE, iid=it["id"], otype="project", owner=ROL,
          tekst="dubbel verwerken", next="/vangst")
    _nxt, msg = _post(dd, "vangst_verwerk", circle=CIRCLE, iid=it["id"], otype="project",
                      owner=ROL, tekst="dubbel verwerken", next="/vangst")
    assert msg == "✗ already processed"
    assert len([p for p in cockpit2._Stores(dd).projects.all()
                if "dubbel verwerken" in str(p.get("scope"))]) == 1


def test_een_cirkel_kan_geen_project_dragen(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    it = st.werk.backlog_add(CIRCLE, "punt", by_id="p1")
    _nxt, msg = _post(dd, "vangst_verwerk", circle=CIRCLE, iid=it["id"], otype="project",
                      owner=CIRCLE, tekst="punt", next="/vangst")
    assert "circle cannot hold a project" in msg


def test_punt_van_de_agenda_blijft_zichtbaar_in_de_vangst(tmp_path):
    """Een overleg openen verplaatst de backlog naar de agenda. Zou de vangst alleen de backlog
    tonen, dan zou vastgelegd werk stil verdwijnen."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    st.werk.backlog_add(CIRCLE, "gisteren gevangen", by_id="p1")
    st.werk.open(CIRCLE)
    punten = cockpit2._Stores(dd).werk.punten(CIRCLE)
    assert [p["title"] for p in punten] == ["gisteren gevangen"]
    assert punten[0]["bron"] == "agenda"
    assert "gisteren gevangen" in render_vangst(cockpit2._Stores(dd), CIRCLE, csrf_token="t")


def test_geen_cirkel_geen_vangst(tmp_path):
    dd = _dd(tmp_path)
    html = render_vangst(cockpit2._Stores(dd), ROL, csrf_token="t")
    assert "Capture belongs to a circle" in html


def test_de_flow_stuurt_de_actienaam_mee(tmp_path):
    """De actienaam staat op de submit-KNOP, en `new FormData(form)` neemt knopwaarden niet mee.

    Zonder een expliciete `set('action', …)` komt de POST als naamloze actie binnen, en die doet de
    dispatch stil niets — 200, en weg. Precies dat gebeurde in de eerste meting op het scherm: drie
    punten getypt, nul aangekomen, geen enkele foutmelding."""
    dd = _dd(tmp_path)
    html = render_vangst(cockpit2._Stores(dd), CIRCLE, csrf_token="t")
    assert "d.set('action','vangst_add')" in html
    # En het veld dat de flow draagt moet er zijn, met de lijst die ververst wordt.
    assert "id='vang-form'" in html and "id='vang-lijst'" in html and "data-frag=" in html


def test_fragment_toont_dezelfde_rijen_als_de_pagina(tmp_path):
    """Eén bron voor de rijen: de live-verversing mag geen tweede vorm van hetzelfde zijn."""
    from nooch_village.views.vangst import render_vangst_frag
    dd = _dd(tmp_path)
    cockpit2._Stores(dd).werk.backlog_add(CIRCLE, "een gevangen punt", by="Iemand", by_id="p1")
    frag = render_vangst_frag(cockpit2._Stores(dd), CIRCLE, csrf_token="t")
    assert "een gevangen punt" in frag and "data-open='1'" in frag
    assert frag in render_vangst(cockpit2._Stores(dd), CIRCLE, csrf_token="t")
