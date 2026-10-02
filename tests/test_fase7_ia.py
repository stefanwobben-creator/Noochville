"""Fase 7: de schermindeling van prototype v15 op de live cockpit.

Structuur, geen stijl — de vormgeving komt in fase 9 in één keer over alle herbouwde schermen.
Wat hier vastligt is de INDELING, en vooral de dingen die er bij een volgende beurt zo weer
insluipen:

1. de navigatie staat op ÉÉN plek (was: topbar + footer + rechterrail);
2. Projects is de landing, niet een tab die je moet vinden;
3. policies/notes/tools zijn één Wiki-oppervlak met een filter, en de OUDE links blijven werken;
4. Keep-in-wiki schrijft een feit mét herkomst, en niet zomaar op elke pagina;
5. de zoek-sneltoets kaapt geen invoervelden.
"""
from __future__ import annotations

from nooch_village import cockpit2, wiki
from nooch_village.cockpit2_util import _CIRCLE_TABS, _ROLE_TABS, _nav

OWNER = "mother_earth__nooch__creator_of_shoes"
CIRKEL = "mother_earth__nooch"


def _stores(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


# ── 1. één navigatie ─────────────────────────────────────────────────────────
def test_de_zijbalk_bevat_navigatie_zoek_en_de_boom():
    """`c2-org` STOND HIER. De boom werd met elke pagina meegerenderd in de zijbalk; sinds
    21 september is hij een nav-paneel dat je ophaalt als je erop klikt. Hij hoort nog steeds bij
    de rest van de navigatie — wat deze test bewaakt — maar als knop, niet als meegerenderd blok."""
    h = _nav()
    for stuk in ("c2-side", "c2-search", "c2-subnav"):
        assert stuk in h, stuk
    assert "data-nav-paneel='org'" in h and "Organization" in h


def test_de_organisatieboom_staat_links_en_niet_meer_rechts(tmp_path):
    """Hij zat in de `c2-rail` die `_send` rechts injecteerde. Twee plekken navigatie is één te
    veel; sinds fase 7 hoort hij bij de rest, links.

    SINDS 21 SEPTEMBER IS DAT EEN PANEEL en niet meer een injectie in de zijbalk — hij wordt
    opgehaald als je op Organization klikt. De bewering is onveranderd: links, één plek, en niet
    meer via de rechter rail."""
    from nooch_village.views.navpaneel import PANELEN
    src = open("nooch_village/cockpit2.py", encoding="utf-8").read()
    assert "org" in PANELEN
    assert "c2-rail" not in src.split("def _send")[1].split("def _send_bytes")[0]


# ── 2. Projects is de landing ────────────────────────────────────────────────
def test_slash_stuurt_naar_projects():
    src = open("nooch_village/cockpit2.py", encoding="utf-8").read()
    blok = src.split('if path in ("/", "/index.html"):')[1][:400]
    assert '"/projects"' in blok


def test_het_bord_is_niet_gedupliceerd():
    """`/projects` hergebruikt `_projects_tab_html` letterlijk. Een tweede bord zou na één
    wijziging uit de pas lopen — dezelfde regel als bij de doelen."""
    from nooch_village.views.projects import render_projects_screen
    import inspect
    assert "_projects_tab_html" in inspect.getsource(render_projects_screen)


def test_projects_blijft_ook_een_tab():
    """Op de cirkel en de rol is het bord de GEFILTERDE weergave van die node. De eigen route is
    de ongefilterde voordeur; allebei nodig."""
    assert "projects" in _CIRCLE_TABS and "projects" in _ROLE_TABS


# ── 3. één Wiki-oppervlak ────────────────────────────────────────────────────
def test_drie_tabs_zijn_er_een_geworden():
    for weg in ("policies", "notes", "tools"):
        assert weg not in _CIRCLE_TABS and weg not in _ROLE_TABS
    assert "wiki" in _CIRCLE_TABS and "wiki" in _ROLE_TABS


def test_de_wiki_tab_filtert_op_soort(tmp_path):
    """TOOLS ZIJN HIER WEG (27 september 2026): ze hebben een eigen ingang (`/tools`) en de
    voorwaarde was dat ze dan ook écht uit de wiki-tab verdwijnen — anders zijn het twee plekken.
    Wat deze toets bewaakt is het FILTEREN zelf, en dat is onveranderd; alleen op de twee soorten
    die hier nog wonen."""
    dd, st = _stores(tmp_path)
    st.att.add(OWNER, "note", title="Selco", body="leverancier")
    st.att.add(OWNER, "policy", title="Beleidje", body="mits")
    alles = cockpit2.render_node(st, OWNER, "wiki", csrf_token="t", username="guest")
    assert "Selco" in alles and "Beleidje" in alles
    alleen_note = cockpit2.render_node(st, OWNER, "wiki", csrf_token="t", username="guest",
                                       kind_flt="note")
    assert "Selco" in alleen_note and "Beleidje" not in alleen_note


def test_oude_links_blijven_werken_en_filteren_voor(tmp_path):
    """Een bookmark op ?tab=tools hoort niet op een lege pagina uit te komen.

    HIJ LANDDE OP WIKI MET TOOLS VOORGEFILTERD; sinds 27 september staan tools op `/tools`. De
    belofte blijft dezelfde — geen lege pagina — maar nu met een verwijzing naar waar ze wél
    staan, want een tool die stil verdwijnt laat niemand merken dat hij verhuisd is."""
    dd, st = _stores(tmp_path)
    st.att.add(OWNER, "note", title="Selco")
    st.att.add(OWNER, "tool", title="Copy checker", url="https://x")
    html = cockpit2.render_node(st, OWNER, "tools", csrf_token="t", username="guest")
    assert "Copy checker" not in html, "de tool staat nog op de rol"
    assert "/tools" in html, "er staat geen verwijzing naar waar hij nu woont"
    from nooch_village.views.tools import render_tools
    assert "Copy checker" in render_tools(st, csrf_token="t", username="guest")


def test_de_wiki_index_toont_het_hele_dorp(tmp_path):
    """Hiervóór vond je een pagina alleen via de rol die hem toevallig bezat."""
    from nooch_village.views.wiki import render_wiki_index
    dd, st = _stores(tmp_path)
    st.att.add(OWNER, "note", title="Selco")
    st.att.add(CIRKEL, "policy", title="Stance", domain="Governance")
    html = render_wiki_index(st)
    # ER STOND HIER OOK `"Governance" in html`, en dat mat de oude weergave: de kolom toonde de
    # RUWE domeinnaam. Sinds 23 september toont hij het BAKJE uit `domeinen.BAKJES`, en een
    # domein dat niet in de classificatietabel staat valt in Overig — precies zoals bedoeld.
    # Wat deze toets bedoelt is dat de index het hele dorp laat zien, ongeacht wie wat bezit,
    # en dat meten de twee titels.
    assert "Selco" in html and "Stance" in html
    assert "Overig" in html, "een onbekend domein hoort zichtbaar in Overig te landen"


# ── 4. Keep-in-wiki: weggehaald (2 oktober 2026) ─────────────────────────────
def test_keep_in_wiki_bestaat_niet_meer(tmp_path):
    """Een bericht in een projectgesprek is een update, geen feit (besluit Stefan, 2 oktober 2026).
    Kennis gaat naar de wiki via het bevestigde rapport (`rapport_naar_wiki`). Niet alleen de knop
    is weg maar ook de actie: een schrijfpad zonder ingang is een achterdeur."""
    dd, st = _stores(tmp_path)
    pagina = st.att.add(OWNER, wiki.PAGINA_KIND, title="Selco (supplier)")
    pid = st.projects.create(OWNER, "Batch 4", "human", status="running")
    e = st.projects.add_feed_entry(pid, "Selco levert in 3 weken.", kind="comment",
                                   author_type="human", author_id="")
    from nooch_village.views import projects as P
    assert "Keep in wiki" not in P.render_project(cockpit2._Stores(dd), pid, csrf_token="TOK")
    cockpit2.dispatch(dd, "keep_in_wiki", {"aid": [pagina.id], "pid": [pid], "item": [e["id"]],
                                           "next": ["/"]}, username="guest")
    assert wiki.feiten(cockpit2._Stores(dd).att.get(pagina.id)) == []


# ── 5. de zoek-sneltoets ─────────────────────────────────────────────────────
def test_de_sneltoets_kaapt_geen_invoerveld():
    """`/` moet in een formulier gewoon een schuine streep blijven. Zonder deze check is de
    sneltoets een bug die je pas merkt als iemand een pad typt."""
    h = _nav()
    assert "tikt" in h and "isContentEditable" in h        # niet kapen terwijl je typt
    assert "metaKey" in h and "ctrlKey" in h             # Cmd+K én Ctrl+K
