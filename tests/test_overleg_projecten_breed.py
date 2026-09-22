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

WAT DEZE STAP APART MAAKT. De andere zes stappen zijn één kolom tekst of één formulier; die
willen geen 1200px. Alleen dit bord zet vier kolommen naast elkaar, en alleen hier kost het
stappenmenu links dus écht iets. Daarom een uitzondering op ÉÉN stap en geen nieuwe breedte
voor het hele overleg.

WAT ER NIET VERDWIJNT. Het stappenmenu en de vangbalk zijn geen sier: zonder menu kun je alleen
nog vooruit ("Next →") en nooit terug, en de vangbalk staat er bewust op ELKE stap (zie
`_wo_vangbar`) omdat "iets horen en opschrijven" niet mag wachten tot stap 5. Ze verhuizen dus
naar boven in plaats van te verdwijnen — de linkerkolom, horizontaal.
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


# ── 1. De stap zelf ─────────────────────────────────────────────────────────────────────────
def test_de_projectenstap_zet_de_breedte_vlag(tmp_path):
    dd = _dd(tmp_path)
    _open(dd)
    assert "<body class=\"wo-vol\">" in _stap(dd, "projecten")


def test_de_andere_stappen_zetten_hem_niet(tmp_path):
    """MUTATIE-CONTROLE: de test hierboven zou ook slagen als élke stap breed werd."""
    dd = _dd(tmp_path)
    _open(dd)
    for step in ("checkin", "checklist", "metrics", "agenda", "checkout", "sluiten"):
        assert "wo-vol" not in _stap(dd, step), step


def test_de_projectenstap_heeft_geen_wo_grid(tmp_path):
    """Het raster reserveert 250px voor de linkerkolom. Blijft het staan, dan is de body-cap
    weghalen maar de helft van de winst."""
    dd = _dd(tmp_path)
    _open(dd)
    assert "wo-grid" not in _stap(dd, "projecten")
    assert "wo-grid" in _stap(dd, "checklist")


def test_de_cap_gaat_alleen_op_die_vlag_eraf():
    """`body{max-width:1180px}` staat in `web_base._CSS` en geldt voor de hele app. Deze ene
    regel zet hem uit, en alleen voor een pagina die er zelf om vraagt."""
    r = _regels(CSS)
    assert "max-width:none" in r.get("body.wo-vol", "")


# ── 2. Wat er niet verdwijnt ────────────────────────────────────────────────────────────────
def test_het_stappenmenu_blijft_bereikbaar(tmp_path):
    """Zonder menu kun je alleen nog vooruit en nooit terug naar Metrics of Checklist."""
    dd = _dd(tmp_path)
    _open(dd)
    html = _stap(dd, "projecten")
    for step in ("checkin", "checklist", "metrics", "agenda", "checkout", "sluiten"):
        assert f"step={step}" in html, step


def test_het_stappenmenu_staat_horizontaal(tmp_path):
    """Boven het bord in plaats van ernaast: een verticaal menu naast een bord van vier kolommen
    is precies de 250px die deze stap niet heeft."""
    dd = _dd(tmp_path)
    _open(dd)
    assert "wo-nav wo-nav--rij" in _stap(dd, "projecten")
    assert "wo-nav wo-nav--rij" not in _stap(dd, "checklist")
    r = _regels(CSS)
    assert "flex-direction:row" in r.get(".wo-nav--rij", "")
    assert "flex-direction:column" in r.get(".wo-nav", ""), \
        "de familie-regel is weg — dan doet de modifier niets meer"


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


def test_de_nu_laag_overleeft_een_body_klasse(tmp_path):
    """`_nu_body` verving letterlijk `<body>`. Staat er een klasse in, dan matchte die regel
    niet meer en verloor het hele scherm zijn nu-opmaak — en dat zie je aan het font, niet aan
    een fout."""
    dd = _dd(tmp_path)
    _open(dd)
    html = cockpit2._nu_body("/werkoverleg", _stap(dd, "projecten"))
    assert "nooch-ui.css" in html
    m = re.search(r"<body class=\"([^\"]*)\">", html)
    assert m, "geen body-klasse gevonden"
    assert set(m.group(1).split()) == {"nu", "wo-vol"}


def test_een_route_buiten_de_nu_lijst_krijgt_de_klasse_niet():
    """MUTATIE-CONTROLE op de regel hierboven: hij mag niet ELKE pagina nu maken."""
    kaal = "<body class=\"wo-vol\"><main>x</main></body>"
    assert cockpit2._nu_body("/claims", kaal) == kaal


def test_de_fragmentvorm_krijgt_geen_body(tmp_path):
    """In de modal is er geen eigen pagina om een klasse op te zetten; dan mag hij ook niet
    doen alsof — zie het PR-bericht voor wat dat betekent."""
    dd = _dd(tmp_path)
    _open(dd)
    frag = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, step="projecten",
                                       csrf_token="t", fragment=True)
    assert "<body" not in frag
