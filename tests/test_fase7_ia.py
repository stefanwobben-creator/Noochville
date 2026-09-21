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
    dd, st = _stores(tmp_path)
    st.att.add(OWNER, "note", title="Selco", body="leverancier")
    st.att.add(OWNER, "tool", title="Copy checker", url="https://x")
    alles = cockpit2.render_node(st, OWNER, "wiki", csrf_token="t", username="guest")
    assert "Selco" in alles and "Copy checker" in alles
    alleen_note = cockpit2.render_node(st, OWNER, "wiki", csrf_token="t", username="guest",
                                       kind_flt="note")
    assert "Selco" in alleen_note and "Copy checker" not in alleen_note


def test_oude_links_blijven_werken_en_filteren_voor(tmp_path):
    """Een bookmark op ?tab=tools hoort niet op een lege pagina uit te komen. Hij landt op Wiki,
    met tools al voorgefilterd — preciezer dan alleen doorsturen."""
    dd, st = _stores(tmp_path)
    st.att.add(OWNER, "note", title="Selco")
    st.att.add(OWNER, "tool", title="Copy checker", url="https://x")
    html = cockpit2.render_node(st, OWNER, "tools", csrf_token="t", username="guest")
    assert "Copy checker" in html and "Selco" not in html


def test_de_wiki_index_toont_het_hele_dorp(tmp_path):
    """Hiervóór vond je een pagina alleen via de rol die hem toevallig bezat."""
    from nooch_village.views.wiki import render_wiki_index
    dd, st = _stores(tmp_path)
    st.att.add(OWNER, "note", title="Selco")
    st.att.add(CIRKEL, "policy", title="Stance", domain="Governance")
    html = render_wiki_index(st)
    assert "Selco" in html and "Stance" in html and "Governance" in html


# ── 4. Keep-in-wiki ──────────────────────────────────────────────────────────
def _project_met_bericht(st, dd):
    pid = st.projects.create(OWNER, "Batch 4", "human", status="running")
    st.projects.add_feed_entry(pid, "Selco levert in 3 weken.", kind="comment",
                               author_type="human", author_id="")
    return pid


def test_keep_in_wiki_schrijft_een_feit_met_herkomst(tmp_path):
    dd, st = _stores(tmp_path)
    pagina = st.att.add(OWNER, wiki.PAGINA_KIND, title="Selco (supplier)")
    pid = _project_met_bericht(st, dd)
    eid = st.projects.get(pid)["log"][0]["id"]
    _, msg = cockpit2.dispatch(dd, "keep_in_wiki",
                               {"aid": [pagina.id], "pid": [pid], "item": [eid], "next": ["/"]},
                               username="guest")
    assert "kept on" in msg
    feiten = wiki.feiten(cockpit2._Stores(dd).att.get(pagina.id))
    assert len(feiten) == 1
    assert "3 weken" in feiten[0]["tekst"]
    # De herkomst IS het punt: zonder bron is het een bewering.
    assert feiten[0]["grond"]["soort"] == "bron" and feiten[0]["grond"]["ref"] == pid
    assert "Batch 4" in feiten[0]["grond"]["citaat"]


def test_een_feit_uit_een_gesprek_is_herkomst_en_geen_bewijs(tmp_path):
    """`soort="bron"` leest als `ongecontroleerd`, niet als `gegrond`. Een uitspraak in een
    projectgesprek is precies dat."""
    dd, st = _stores(tmp_path)
    pagina = st.att.add(OWNER, wiki.PAGINA_KIND, title="Selco (supplier)")
    pid = _project_met_bericht(st, dd)
    eid = st.projects.get(pid)["log"][0]["id"]
    cockpit2.dispatch(dd, "keep_in_wiki",
                      {"aid": [pagina.id], "pid": [pid], "item": [eid], "next": ["/"]},
                      username="guest")
    st2 = cockpit2._Stores(dd)
    status = wiki.grond_status(wiki.feiten(st2.att.get(pagina.id))[0])
    assert status != wiki.GEGROND


def test_keep_in_wiki_weigert_fail_closed(tmp_path):
    dd, st = _stores(tmp_path)
    pagina = st.att.add(OWNER, wiki.PAGINA_KIND, title="Selco (supplier)")
    pid = _project_met_bericht(st, dd)
    eid = st.projects.get(pid)["log"][0]["id"]
    for velden, waarom in (
            ({"aid": ["bestaat-niet"], "pid": [pid], "item": [eid]}, "page not found"),
            ({"aid": [pagina.id], "pid": ["xxx"], "item": [eid]}, "project not found"),
            ({"aid": [pagina.id], "pid": [pid], "item": ["xxx"]}, "message not found")):
        _, msg = cockpit2.dispatch(dd, "keep_in_wiki", {**{k: v for k, v in velden.items()},
                                                        "next": ["/"]}, username="guest")
        assert waarom in msg, (velden, msg)
    assert wiki.feiten(cockpit2._Stores(dd).att.get(pagina.id)) == []


# ── 5. de zoek-sneltoets ─────────────────────────────────────────────────────
def test_de_sneltoets_kaapt_geen_invoerveld():
    """`/` moet in een formulier gewoon een schuine streep blijven. Zonder deze check is de
    sneltoets een bug die je pas merkt als iemand een pad typt."""
    h = _nav()
    assert "tikt" in h and "isContentEditable" in h        # niet kapen terwijl je typt
    assert "metaKey" in h and "ctrlKey" in h             # Cmd+K én Ctrl+K
