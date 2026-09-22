"""De Overview-tab van een cirkel en van een rol op de nu-tokens.

EERST GEMETEN, want de klacht klopte maar niet op het punt dat hij noemde. Op een echte cockpit
(`/node?id=mother_earth__nooch&tab=overview`) staat de body al op `class="nu"`, laadt
`nooch-ui.css` mee, en is élk lettertype op dit scherm al Archivo — gecontroleerd met
`getComputedStyle`, niet met het oog. Wat er NIET mee was gegaan zijn de LIJNEN:

    ul.clean li    36×  border-bottom  #DDD4C0   (--border, de oude zandtint)
    .accrow         5×  border-bottom  #DDD4C0
    .c2-tabs        1×  border-bottom  #DDD4C0   (de streep onder de tabbalk)
    .manage-ico     6×  border-radius  9px       (--radius; nu heeft overal 0)

#DDD4C0 is warm zand; de nu-huisstijl tekent zijn subtiele lijnen op #E6E7E8 (`--nu-border-subtle`)
en kent geen radius. Op een scherm dat verder helemaal zwart-op-#FFFAFA is, zijn 42 zandkleurige
haarlijntjes precies wat "oude opmaak" betekent — en het is de dominante vorm op dit scherm, want
de DO/DON'T-lijsten van de strategie zijn niets anders dan die 36 regels.

`.rrole` GAAT MEE, hoewel hij op de Roles-tab staat en niet op Overview. Het is de derde van drie
klassen die exact hetzelfde betekenen (een scheidingslijn tussen twee regels) op exact hetzelfde
scherm. Twee ervan migreren en de derde laten staan, is de volgende persoon laten ontdekken dat
`/node` twee soorten haarlijn heeft.
"""
from __future__ import annotations

import os
import re

BASIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUD = open(os.path.join(BASIS, "nooch_village", "static", "nooch.css"), encoding="utf-8").read()
NU = open(os.path.join(BASIS, "nooch_village", "static", "nooch-ui.css"), encoding="utf-8").read()
STRAT = open(os.path.join(BASIS, "nooch_village", "views", "strategy.py"), encoding="utf-8").read()
OVERVIEW = open(os.path.join(BASIS, "nooch_village", "views", "overview.py"), encoding="utf-8").read()

from nooch_village.cockpit2_util import _CIRCLE_TABS, _ROLE_TABS

_ONT = lambda t: re.sub(r"/\*.*?\*/", " ", t, flags=re.S)


def _zonder_uitleg(bron: str) -> str:
    """Python-commentaar en docstrings eruit. Anders telt een test de UITLEG mee waarin staat
    dat iets weg is — en die uitleg hoort er juist te staan. Deze val sloeg in dit bestand
    meteen toe: de eerste versie van `test_de_onbereikbare_strategy_tak_is_weg` viel om op de
    comment die ik er zelf een regel eerder boven had gezet."""
    zonder = re.sub(r'"""..*?"""', " ", bron, flags=re.S)
    return re.sub(r"#[^\n]*", " ", zonder)


def _regels(css: str) -> dict:
    """selector → body, commentaar eruit. Twee dingen die deze week al een keer misgingen:
    zonder het strippen plakt de uitleg boven een regel aan de selector vast en matcht er
    niets, en een GEGROEPEERDE selector (`a, b, c {…}`) vind je niet terug op `b` als je de
    hele regel als sleutel neemt. Elke selector uit de groep krijgt dus zijn eigen ingang."""
    uit = {}
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", _ONT(css)):
        for deel in sel.split(","):
            uit.setdefault(" ".join(deel.split()), []).append(body)
    return {k: " ".join(v) for k, v in uit.items()}


#: De drie klassen die hetzelfde doen: één regel van de volgende scheiden.
_SCHEIDERS = ("ul.clean li", ".accrow", ".rrole")


# ── 1. De lijnen ────────────────────────────────────────────────────────────────────────────
def test_elke_scheidingslijn_op_dit_scherm_staat_op_de_nu_tint():
    nu = _regels(NU)
    for sel in _SCHEIDERS:
        regel = nu.get(f".nu {sel}", "")
        assert "var(--nu-border-subtle)" in regel, \
            f"{sel} tekent op /node nog een zandlijn en wordt niet overschreven"


def test_de_basislaag_tekent_ze_nog_wel_in_zand():
    """MUTATIE-CONTROLE: de test hierboven zou ook slagen als iemand de basisregels had
    weggehaald. Dan is er geen lijn meer in plaats van een andere lijn — en dan meet de
    bovenstaande test een scherm zonder scheidingen."""
    oud = _regels(OUD)
    for sel in _SCHEIDERS:
        assert "var(--border)" in oud.get(sel, ""), f"{sel} zet in de basislaag geen lijn meer"


def test_de_streep_onder_de_tabbalk_gaat_mee():
    """`.nu .c2-tabs a` bestond al (de tabs zelf), de CONTAINER niet — en die tekent de lijn
    waar de hele balk op staat."""
    assert "var(--nu-border-subtle)" in _regels(NU).get(".nu .c2-tabs", "")


def test_het_beheer_icoon_heeft_geen_ronde_hoek_meer():
    """`.nu .manage-ico` zette wel de kleur maar niet de radius; de 9px bleef staan op een
    scherm waar verder niets rond is."""
    assert re.search(r"\.nu \.manage-ico[^{]*\{[^}]*border-radius:\s*0", _ONT(NU))
    assert "border-radius:var(--radius)" in _ONT(OUD).replace(" ", "").replace("\n", ""), \
        "de basisregel zet geen radius meer — dan overschrijft de nu-regel niets"


# ── 2. De zandlijn die nooit iemand zag ─────────────────────────────────────────────────────
#
# BIJVANGST, en de reden dat hij in deze PR zit: `_purpose_chain` tekende zijn linkerlijn met
# `style='...border-left:2px solid var(--border)'` — een inline style (tegen de UI-regel uit
# CLAUDE.md) én de oude zandtint. Bij het vervangen door een klasse bleek dat niemand die lijn
# ooit te zien krijgt: de functie had één aanroeper, en die gaf `with_purpose_chain=False`.
# `True` kon alleen uit `render_node`'s `elif tab == "strategy"` komen, en die tak is
# onbereikbaar — `"strategy"` staat niet in `_CIRCLE_TABS`/`_ROLE_TABS`, dus de regel
# `if tab not in tabs: tab = "overview"` erboven vangt hem altijd af.
def test_de_onbereikbare_strategy_tak_is_weg():
    """`tests/test_cockpit2.py` legt al vast dat de KNOP uit de tabbalk weg is; de tak erachter
    bleef staan. Een vlag door een functie heen duwen die maar één stand kent, is een keuze die
    niemand meer maakt."""
    assert "strategy" not in _CIRCLE_TABS and "strategy" not in _ROLE_TABS
    assert 'tab == "strategy"' not in _zonder_uitleg(OVERVIEW)
    assert "_purpose_chain" not in _zonder_uitleg(STRAT)
    assert "with_purpose_chain" not in _zonder_uitleg(STRAT)
    assert "with_purpose_chain" not in _zonder_uitleg(OVERVIEW)


def test_de_inline_style_teller_van_strategy_is_gedaald():
    """De ratchet in `test_ui_no_inline_style` mag alleen omlaag. Twee inline styles minder,
    want ze zaten allebei in de verwijderde keten."""
    from tests.test_ui_no_inline_style import _STYLE_WHITELIST
    assert _STYLE_WHITELIST["views/strategy.py"] == STRAT.count("style='")
    assert _STYLE_WHITELIST["views/strategy.py"] < 14, "plafond niet verlaagd"


# ── 3. De scope ─────────────────────────────────────────────────────────────────────────────
def test_alles_wat_erbij_komt_blijft_binnen_de_nu_scope():
    """Eén regel zonder `.nu` ervoor raakt élk scherm, ook de geparkeerde. Dit staat al in
    `test_fase10_huisstijl`; hier als herhaling omdat deze PR vijf regels toevoegt."""
    regels = [r.split("{")[0].strip() for r in _ONT(NU).split("}") if "{" in r]
    buiten = [r for r in regels if r and not r.startswith(".nu") and not r.startswith("@")]
    assert not buiten, f"regels buiten de scope: {buiten}"
