"""Organization opent bij je eigen cirkel, en is het enige boom-concept (23 september 2026).

DE REDENERING, van Stefan en nagerekend op de echte org. Een cirkel IS een rol die rollen bevat
(harde regel 1), dus wat "mijn cirkel" toont is per definitie een deel van wat de organisatieboom
al toont. Twee nav-items voor hetzelfde ding is dan geen tweede perspectief maar redundantie.

WAT DE METING ERAAN TOEVOEGDE. Op prod toonde het Circle-paneel 15 rollen en het
Organization-paneel 13 (11 rollen + `mother_earth` + de cirkel zelf). Het verschil was exact
`circle_lead`, `circle_rep`, `facilitator` en `secretary`: `_tree_html.kids_of` laat kernrollen
bewust weg ("die zie je via de cirkel → Rollen"). Die vier gaan dus NIET verloren — ze staan op
`/node?id=<cirkel>&tab=roles` onder het kopje "Core roles", precies waar die comment naar wijst.
Gecontroleerd, niet aangenomen: zie `test_de_kernrollen_staan_op_de_roles_tab`.

WAT ER WEL ONTBRAK, en dat is de hele bouwopdracht: de boom klapte alleen open als je al op een
`/node`-pagina stond. `nooch.js` vult `hier` namelijk uitsluitend daar; vanaf Messages, Wiki of
Projects kwam de boom dicht en ongemarkeerd binnen. Dat was geen ontbrekende machinerie maar een
ontbrekende DEFAULT — `_tree_html` klapt ancestors al open (`org.breadcrumb`) en zet al `.here`
op de huidige node.

EN HET ECHTE DUPLICAAT ZAT ELDERS. Niet Circle-paneel ↔ boom, maar Circle-paneel ↔ Roles-tab:
allebei "de rollen van één cirkel + wie ze vervult". `_roles_html` deed het beter (via
`org.roles_of`/`org.subcircles_of`, met Core roles / Roles / Subcircles gesplitst) dan
`_paneel_circle`, dat rauw op `parent ==` filterde en subcirkels als gewone rijen tussen de rollen
zette. Van de twee is de mindere weg.
"""
from __future__ import annotations

import re

from nooch_village import cockpit2
from nooch_village.cockpit2 import _home_node
from nooch_village.cockpit2_util import _nav, overleg_items
from nooch_village.views.navpaneel import PANELEN, render_nav_paneel
from nooch_village.views.overview import _roles_html, _tree_html

OWNER = "mother_earth__nooch__creator_of_shoes"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    mens = st.people.add("Boom Tester", "boom@test.nl")
    st.assign.assign(OWNER, "person", mens.id)
    return dd, cockpit2._Stores(dd), mens.id


def _gemarkeerd(html: str) -> list[str]:
    """De node-ids die `.here` dragen. `cls` is "c here" voor een cirkel, " here" voor een rol."""
    return re.findall(r"<a class='[^']*\bhere\b[^']*' href='/node\?id=([^']+)'", html)


def _open_takken(html: str) -> int:
    return len(re.findall(r"<details class='tree-c' open>", html))


# ── b. De boom opent bij je eigen cirkel, waar je ook vandaan komt ───────────
def test_zonder_hier_landt_de_boom_op_je_eigen_cirkel(tmp_path):
    """DE BOUWOPDRACHT. `nooch.js` geeft `hier` alleen mee op `/node`; overal anders was hij leeg
    en kwam de boom dicht en ongemarkeerd binnen. De default maakt daar de eigen cirkel van."""
    dd, st, ik = _dorp(tmp_path)
    thuis = _home_node(st.records.all())
    assert thuis, "zonder thuiscirkel meet deze toets niets"

    html = render_nav_paneel(st, "org", ik)                  # geen `hier` — zoals vanaf /wiki
    assert _gemarkeerd(html) == [thuis], (
        f"de eigen cirkel is niet gemarkeerd; gemarkeerd: {_gemarkeerd(html)}")
    assert _open_takken(html) >= 1, "er staat geen tak open"


def test_een_expliciete_hier_wint_van_de_default(tmp_path):
    """De default mag nooit overschrijven waar je ECHT staat. Sta je op een rolpagina, dan hoort
    die rol gemarkeerd te zijn, niet je cirkel."""
    dd, st, ik = _dorp(tmp_path)
    html = render_nav_paneel(st, "org", ik, hier=OWNER)
    assert _gemarkeerd(html) == [OWNER]
    assert _home_node(st.records.all()) not in _gemarkeerd(html)


def test_de_default_komt_uit_dezelfde_bron_als_de_rest(tmp_path):
    """`_home_node` voedt ook de twee overleg-knoppen, `/projects` en `/vangst`. Een eigen
    "welke cirkel is van mij"-regel hier zou een tweede antwoord op dezelfde vraag geven — de val
    die `_paneel_circle` juist had."""
    import inspect

    from nooch_village.views import navpaneel
    bron = inspect.getsource(navpaneel.render_nav_paneel)
    assert "_home_node" in bron, "de default gebruikt niet de gedeelde bron"


def test_een_boom_zonder_thuiscirkel_valt_niet_om(tmp_path):
    """Fail-soft: geen records = geen default, en dan nog steeds een boom (leeg) in plaats van
    een uitzondering in een fragment dat in een openstaande pagina wordt gezet."""
    dd = str(tmp_path / "leeg")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    # ER STOND HIER `st.records.archive(...)`, en die methode bestaat niet — `Records` kent
    # `all/get/put/set_holder/set_persona/root`. Archiveren gaat via het record zelf.
    for r in st.records.all():
        r.archived = True
        st.records.put(r)
    assert _home_node(st.records.all()) == "", "er is nog een thuiscirkel; de toets meet niets"
    html = render_nav_paneel(st, "org", "")
    assert "Organization" in html
    assert _gemarkeerd(html) == []


# ── c. Circle bestaat niet meer ──────────────────────────────────────────────
def test_circle_is_geen_paneel_en_geen_knop_meer(tmp_path):
    """Besluit Stefan, 23 september 2026: helemaal weg, ook niet als kale link. Twee klikken naar
    de eigen cirkel via de gemarkeerde node in de boom is goed genoeg."""
    dd, st, ik = _dorp(tmp_path)
    assert "ci" not in PANELEN
    assert render_nav_paneel(st, "ci", ik) == ""             # fail-closed, geen half scherm
    h = _nav()
    assert "data-nav-paneel='ci'" not in h
    assert ">Circle<" not in h


def test_de_placeholder_van_de_circle_knop_is_weg():
    """`_SIDE_CIRCLE` was de plek die `_send` per verzoek invulde. Blijft hij staan, dan staat er
    een HTML-comment in elke pagina die nooit meer vervangen wordt.

    OP DE NAAM EN OP DE UITVOER, niet via een import: de eerste versie van deze toets importeerde
    `_SIDE_CIRCLE` om te bewijzen dat hij weg was, en dat kan per definitie niet."""
    from nooch_village import cockpit2_util
    assert not hasattr(cockpit2_util, "_SIDE_CIRCLE")
    assert "<!--c2-circle-->" not in _nav()


def test_de_overleg_knoppen_houden_hun_cirkel(tmp_path):
    """`_home_node` gaat NIET weg met de knop: hij voedt ook Werkoverleg en Roloverleg. Dit is de
    toets die zou vallen als "Circle weg" te breed werd opgevat."""
    dd, st, ik = _dorp(tmp_path)
    cid = _home_node(st.records.all())
    knoppen = overleg_items(cid)
    assert f"/werkoverleg?circle={cid}" in knoppen
    assert f"/roloverleg2?circle={cid}" in knoppen


def test_het_paneel_circle_bestaat_niet_meer():
    """Niet "staat er nog maar wordt niet aangeroepen": weg. Anders dan bij Messages en Projects
    is er hier geen reden hem te bewaren — zijn inhoud bestaat elders, en beter."""
    from nooch_village.views import navpaneel
    assert not hasattr(navpaneel, "_paneel_circle")


# ── Wat er NIET verloren mag gaan ────────────────────────────────────────────
def test_de_kernrollen_staan_op_de_roles_tab(tmp_path):
    """DE CORRECTIE DIE DIT BESLUIT MOGELIJK MAAKTE. Het Circle-paneel was de enige NAV-plek met
    de vier governancerollen, want `_tree_html` laat ze bewust weg. Maar ze zijn niet weg: de
    Roles-tab van de cirkel toont ze onder "Core roles" — precies waar de comment in de boom naar
    verwijst. Valt deze toets, dan heeft het weghalen van Circle wél informatie gekost."""
    dd, st, ik = _dorp(tmp_path)
    cirkel = st.records.get(_home_node(st.records.all()))
    tab = _roles_html(st, cirkel, "TOK")
    kern = [r.id for r in st.records.all()
            if r.id.endswith(("__facilitator", "__secretary", "__circle_lead", "__circle_rep"))
            and not r.archived and getattr(r, "parent", None) == cirkel.id]
    assert kern, "dit dorp heeft geen kernrollen; de toets meet dan niets"
    for rid in kern:
        assert f"/node?id={rid}" in tab, f"{rid} staat niet op de Roles-tab"
    assert "Core roles" in tab


def test_de_boom_laat_de_kernrollen_nog_steeds_weg(tmp_path):
    """Bewust ongewijzigd (besluit: punt a vervalt). Staat dit er ooit anders, dan is dat een
    keuze en geen ongeluk — deze toets maakt hem zichtbaar."""
    dd, st, ik = _dorp(tmp_path)
    cirkel = st.records.get(_home_node(st.records.all()))
    boom = _tree_html(st, cirkel.id)
    kern = [r.id for r in st.records.all()
            if r.id.endswith(("__facilitator", "__secretary", "__circle_lead", "__circle_rep"))
            and not r.archived and getattr(r, "parent", None) == cirkel.id]
    assert kern
    for rid in kern:
        assert f"/node?id={rid}" not in boom


# ── Opruiming die met dit besluit meekomt ────────────────────────────────────
def test_er_zijn_geen_dode_tree_imports_meer():
    """`site_audit` en `skills` importeerden `_tree_html` en returnden op de volgende regel zonder
    hem te gebruiken — restanten van de rechterrail die in fase 10 verdween. Een import die niets
    doet, leest als "hier staat een boom"."""
    import pathlib
    wortel = pathlib.Path(__file__).resolve().parents[1] / "nooch_village" / "views"
    for naam in ("site_audit.py", "skills.py"):
        bron = (wortel / naam).read_text()
        assert "_tree_html" not in bron, f"{naam} importeert de boom nog"


def test_de_ongebruikte_crumb_berekening_is_weg():
    """`render_node` rekende een breadcrumb uit die nergens in de uitvoer terechtkwam: het
    kruimelpad zelf was al weg, de berekening bleef staan.

    OP DE AANROEP, niet op het woord. De eerste versie zocht "crumb" in de bron en viel over een
    COMMENT die uitlegt dat de breadcrumb weg is — dan toetst hij de uitleg in plaats van de
    code, een val die in dit project vaker is toegeslagen. `org.breadcrumb` blijft elders gewoon
    in gebruik (de persoonspagina en `_tree_html`); het gaat om déze aanroeper."""
    import inspect

    from nooch_village.views import overview
    bron = inspect.getsource(overview.render_node)
    assert "org.breadcrumb" not in bron, "render_node rekent nog steeds een kruimelpad uit"
