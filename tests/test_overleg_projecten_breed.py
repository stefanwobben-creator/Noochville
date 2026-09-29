"""De Projects-stap in het werkoverleg krijgt de volle breedte.

GEMETEN, NIET GESCHAT (22 september 2026, echte cockpit, venster 1500px):

    body max-width        1180px      ← de cap uit `web_base._CSS`
    .c2-wrap               884px      ← 1180 − 32 rechterpadding − 232 zijbalk
    .wo-mid                618px      ← 884 − 250 stappenmenu − 16 gap
    .pboard scrollWidth    669px      ← wat vier kolommen nodig hebben
    afgeknipt               51px      ← FUTURE viel er half af

en alle 36 kolommen stonden op exact 160px: hun `min-width`. Ze konden dus nergens heen — het
bord scrollde horizontaal binnen een kolom van 618px terwijl er rechts van de pagina 320px
leegstond.

DE OPLOSSING IS VERHUISD (29 september 2026). Hierboven stond de uitzondering: op de
Projects-stap legde het stappenmenu zich plat als een balk, om die 250px terug te winnen. Dat
werkte, maar je zág het springen bij elke stapwissel, en het duwde je op precies die ene stap
naar boven. De ruimte komt nu van elders: zolang het overleg LOOPT gaat de dorps-navigatie weg
(`body.wo-focus`), en dat levert 232px op — ruim meer dan het tekort van 51px.

Wat daarmee vervalt: de liggende menu-variant (`.wo-nav--rij`), de `nav_kaal`-kopie en de
per-stap-tak in `render_werkoverleg`. Wat blijft is deze meting, want die is nog steeds de
REDEN — alleen niet meer voor een uitzondering op één stap.

WAT ER NIET VERDWIJNT. Het stappenmenu en de vangbalk zijn geen sier: zonder menu kun je alleen
nog vooruit ("Next →") en nooit terug, en de vangbalk staat er bewust op ELKE stap (zie
`_wo_vangbar`) omdat "iets horen en opschrijven" niet mag wachten tot stap 5. Ze staan nu op elke
stap gewoon links, zoals overal.
"""
from __future__ import annotations

import os
import re

from nooch_village import cockpit2

BASIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS = open(os.path.join(BASIS, "nooch_village", "static", "nooch.css"), encoding="utf-8").read()

C = "mother_earth__nooch"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def _open(dd):
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")


def _stap(dd, step):
    return cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, step=step, csrf_token="t")


def _regels(css: str) -> dict:
    kaal = re.sub(r"/\*.*?\*/", " ", css, flags=re.S)
    return {s.strip(): b for s, b in re.findall(r"([^{}]+)\{([^{}]*)\}", kaal)}


# ── 1. De focus-modus ───────────────────────────────────────────────────────────────────────
def test_een_lopend_overleg_gebruikt_het_hele_scherm(tmp_path):
    dd = _dd(tmp_path)
    _open(dd)
    m = re.search(r"<body class=\"([^\"]*)\">", _stap(dd, "projecten"))
    assert m and set(m.group(1).split()) == {"wo-vol", "wo-focus"}


def test_elke_stap_krijgt_hem_nu(tmp_path):
    """DE UITZONDERING IS WEG. Hier stond het omgekeerde — "de andere stappen zetten hem niet" —
    en dat was precies het springen dat deze scope oplost."""
    dd = _dd(tmp_path)
    _open(dd)
    for step in ("checkin", "checklist", "metrics", "agenda", "checkout", "sluiten"):
        assert "wo-focus" in _stap(dd, step), step


def test_een_gesloten_overleg_houdt_de_navigatie(tmp_path):
    """MUTATIE-CONTROLE: zonder deze toets zou "altijd focus" er ook doorheen komen. Er loopt
    niets, dus er is geen reden om de rest van het dorp weg te halen."""
    dd = _dd(tmp_path)
    html = _stap(dd, "checkin")                     # niet geopend
    assert "wo-focus" not in html and "wo-vol" not in html
    assert "c2-side" in html, "de zijbalk hoort er juist te staan"


def test_de_projectenstap_houdt_zijn_raster(tmp_path):
    """Het menu blijft links staan, op élke stap — dat is wat de focus-modus mogelijk maakt."""
    dd = _dd(tmp_path)
    _open(dd)
    assert "wo-grid" in _stap(dd, "projecten")
    assert "wo-nav--rij" not in _stap(dd, "projecten"), "de liggende variant is terug"


def test_de_zijbalk_gaat_weg_en_de_marge_ook():
    """De klasse is niets zonder deze twee regels: `display:none` haalt de balk weg, maar de
    232px die elke zus-node ervoor reserveert blijft staan als je de marge vergeet."""
    r = _regels(CSS)
    assert "display:none" in r.get("body.wo-focus .c2-side", "")
    assert "margin-left:0" in r.get("body.wo-focus .c2-side ~ *:not(.c2-paneel)", "")


def test_de_cap_gaat_alleen_op_die_vlag_eraf():
    """`body{max-width:1180px}` staat in `web_base._CSS` en geldt voor de hele app. Deze ene
    regel zet hem uit, en alleen voor een pagina die er zelf om vraagt."""
    r = _regels(CSS)
    assert "max-width:none" in r.get("body.wo-vol", "")


def test_er_is_een_weg_terug_naar_het_dorp(tmp_path):
    """MET DE NAVIGATIE WEG IS DIT ANDERS EEN DOODLOPENDE STRAAT. `wo_close` is Circle-Lead-werk,
    dus wie alleen meedoet kan er niet via "sluiten" uit — en hoeft dat ook niet: deze link
    navigeert alleen, het overleg loopt voor de anderen door."""
    dd = _dd(tmp_path)
    _open(dd)
    html = _stap(dd, "agenda")
    assert "back to the village" in html
    assert "wo_close" not in html.split("back to the village")[0][-400:]


def test_de_modalvorm_draagt_een_markering(tmp_path):
    """In de modal staat de navigatie op de pagina ERONDER, buiten dit fragment. De controller
    leest deze markering en zet dezelfde body-klasse; zonder markering zou hij op de URL moeten
    gokken en niet weten of het overleg open is."""
    dd = _dd(tmp_path)
    _open(dd)
    frag = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, step="agenda", csrf_token="t",
                                       fragment=True)
    assert "data-wo-focus" in frag and "<body" not in frag
    dicht = cockpit2.render_werkoverleg(cockpit2._Stores(dd), "mother_earth", step="checkin",
                                        csrf_token="t", fragment=True)
    assert "data-wo-focus" not in dicht


# ── 2. Wat er niet verdwijnt ────────────────────────────────────────────────────────────────
def test_het_stappenmenu_blijft_bereikbaar(tmp_path):
    """Zonder menu kun je alleen nog vooruit en nooit terug naar Metrics of Checklist."""
    dd = _dd(tmp_path)
    _open(dd)
    html = _stap(dd, "projecten")
    for step in ("checkin", "checklist", "metrics", "agenda", "checkout", "sluiten"):
        assert f"step={step}" in html, step


def test_het_stappenmenu_staat_op_elke_stap_links(tmp_path):
    """De liggende variant is weg; het menu staat overal in dezelfde kolom. Dat is de winst van
    de focus-modus: geen springende layout bij het wisselen van stap."""
    dd = _dd(tmp_path)
    _open(dd)
    r = _regels(CSS)
    assert "flex-direction:column" in r.get(".wo-nav", "")
    assert ".wo-nav--rij" not in r, "de liggende variant staat nog in de stylesheet"
    for step in ("projecten", "checklist"):
        assert "wo-nav wo-nav--rij" not in _stap(dd, step), step


def test_de_vangbalk_blijft_ook_op_deze_stap(tmp_path):
    """`_wo_vangbar` staat bewust op ELKE stap: wie tijdens het bord iets hoort moet het daar
    kunnen opschrijven, niet onthouden tot stap 5."""
    dd = _dd(tmp_path)
    _open(dd)
    html = _stap(dd, "projecten")
    assert "id='vang-tot'" in html and "id='vang-n'" in html


def test_het_bord_staat_er_echt(tmp_path):
    """Anders meet alles hierboven een lege stap: zonder projecten rendert `_projects_tab_html`
    "No projects yet." en is er helemaal geen bord om breed te maken."""
    dd = _dd(tmp_path)
    _open(dd)
    cockpit2._Stores(dd).projects.create(
        f"{C}__brand_visual_designer", "Een project op het bord", "human")
    assert "pboard" in _stap(dd, "projecten")


# ── 3. De schil ─────────────────────────────────────────────────────────────────────────────
def test_een_gewone_pagina_houdt_een_kale_body(tmp_path):
    """`_page` krijgt een body-klasse erbij; zonder argument mag er niets veranderen — elke
    andere view gaat hier doorheen."""
    from nooch_village.web_base import _page
    assert "<body><main>" in _page("Titel", "<p>x</p>")


def test_de_body_klasse_van_de_view_blijft_staan(tmp_path):
    """HIER STONDEN TWEE TOETSEN OP `_nu_body` (opgeheven 28 september 2026). Die functie zette
    `class="nu"` op de body en hing een tweede stylesheet achter de eerste; ze bewaakten dat hij
    een BESTAANDE klasse niet overschreef, en dat hij niet élke route raakte.

    Allebei die zorgen zijn verdwenen met het mechanisme: er is één stylesheet, elke pagina krijgt
    hem, en niemand schrijft meer in de body-tag. Wat blijft is de klasse die de VIEW zelf zet —
    `wo-vol` voor de brede projectenstap — en dat die er nog staat is precies wat deze toets
    overhoudt."""
    dd = _dd(tmp_path)
    _open(dd)
    html = _stap(dd, "projecten")
    assert "/static/nooch.css" in html
    m = re.search(r"<body class=\"([^\"]*)\">", html)
    assert m and set(m.group(1).split()) == {"wo-vol", "wo-focus"}


def test_de_fragmentvorm_krijgt_geen_body(tmp_path):
    """In de modal is er geen eigen pagina om een klasse op te zetten; dan mag hij ook niet
    doen alsof — zie het PR-bericht voor wat dat betekent."""
    dd = _dd(tmp_path)
    _open(dd)
    frag = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, step="projecten",
                                       csrf_token="t", fragment=True)
    assert "<body" not in frag
