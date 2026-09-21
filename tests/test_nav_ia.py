"""De navigatie is ÉÉN plek: de zijbalk (fase 7, 19 september 2026, prototype v15).

Daarvoor stond ze op drie: een topbar met logo+zoek, een footer met drie meta-links en een
organisatieboom in de rechterrail. Deze test bevriest het nieuwe contract — de inhoud én de
single-source-regel (geen view hardcodeert de nav inline)."""
from __future__ import annotations

import glob
import re

from nooch_village.cockpit2_util import _footer, _nav


def test_de_zijbalk_draagt_de_hele_navigatie():
    """Logo, zoek, begroeting, de nav-items en de plek voor de organisatieboom — alles in één
    aside. Dat is het punt: drie plekken navigatie liepen uiteen."""
    h = _nav()
    assert "c2-side" in h and "c2-logo" in h and "class='c2-search'" in h and "c2-greet" in h
    # De boom staat hier als KNOP (paneel), niet meer als meegerenderd blok — zie
    # `test_nav_accordeon.py::test_de_organisatieboom_is_een_paneel_geworden`.
    assert "data-nav-paneel='org'" in h
    for href, label in (("/projects", "Projects"), ("/wiki", "Wiki"), ("/admin", "Admin")):
        assert href in h and label in h


def test_messages_staat_er_pas_in_sinds_er_data_achter_zit():
    """In fase 7 stond Messages er bewust NIET in: het prototype zegt zelf dat dat scherm nog niet
    bestaat, en een nav-item dat naar niets wijst is erger dan een ontbrekend nav-item. Sinds fase
    8 is de channel-laag er, dus staat hij er wel."""
    h = _nav()
    assert "Messages" in h and "/messages" in h


def test_de_inbox_staat_er_niet_meer_in_geen_van_beide_vormen():
    """DEZE TEST BEWAAKTE EEN DODE KNOP. Hij eiste `ibxToggle()` in de zijbalk — een functie die
    nergens in de repo gedefinieerd is — op gezag van een docstring die naar `render_inbox_chrome`
    verwees, dat evenmin bestaat. Er is ook nooit een route `/inbox` geweest: hij staat niet in
    `do_GET` en dus niet in de route-tabel van `docs/ARCHITECTUUR.md`. De knop gaf een JS-fout en
    verder niets.

    Wat hij nu bewaakt is het omgekeerde: geen knop, geen link, en geen aanroep van een functie die
    er niet is. Messages dekt de functie (besluit Stefan, 21 september 2026)."""
    h = _nav()
    assert "Inbox" not in h
    assert "ibxToggle" not in h
    assert "/inbox" not in h


def test_de_footer_draagt_geen_navigatie_meer():
    """Goals en Metrics zijn tabs op de cirkel geworden, Admin staat in de zijbalk. Wat overblijft
    is de build-info."""
    f = _footer()
    assert "build" in f
    assert "/metrics2" not in f and "/admin" not in f and "/goals" not in f


def test_context_label_wordt_niet_meer_getoond():
    """De breadcrumb is uit de header gehaald; `context` blijft alleen in de signatuur voor compat,
    zodat de ~18 aanroepen niet hoefden te wijzigen. Geen enkele waarde lekt nog naar de HTML."""
    assert "projectdetail" not in _nav("projectdetail")
    assert _nav("patterns") == _nav("projectdetail") == _nav()


def test_geen_view_hardcodeert_de_nav_nog_inline():
    # single-source: geen enkele view mag de oude inline nav-balk nog dragen.
    oud = re.compile(r"<div class='bar'>cockpit 2 · GlassFrog \(PoC\) · build \{_BUILD\}")
    overtreders = [f for f in glob.glob("nooch_village/views/*.py")
                   if oud.search(open(f).read())]
    assert not overtreders, f"nav nog inline in: {overtreders}"
