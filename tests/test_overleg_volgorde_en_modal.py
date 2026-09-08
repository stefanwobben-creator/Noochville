"""Drie klachten van 8 september, alle drie dezelfde familie: het scherm liet iets anders zien
dan de mens aan het doen was.

1. **Een nieuw agendapunt landde onderaan.** `Agenda.add` doet `append`, dus wat je zojuist
   inbracht stond achter alles wat er al lag — én `render_roloverleg2` selecteert `items_open[0]`,
   dus de editor sprong naar het OUDSTE open punt.
2. **De agenda-stap toonde alle spanningen onder elkaar**, terwijl de puntenlijst links in het
   stappenmenu al staat. Wie meekeek in een scherm-deling moest meescrollen om te zien waarover
   het ging, in plaats van te kijken.
3. **"Group by → by person" wierp je het overleg uit.** De overlay onderschept alleen
   `a.js-modal[data-href]`; het projectbord bouwde gewone links naar de node-pagina.

Elke test hier is zo geschreven dat hij ROOD wordt als de betreffende regel eruit gaat — niet
alleen groen omdat er toevallig een string in de HTML staat.
"""
from __future__ import annotations

import ast
import pathlib
import re

from nooch_village import cockpit2
from nooch_village.views.projects import _projects_tab_html
from nooch_village.views.roloverleg import _rov_items
from nooch_village.views.vangst import actief_punt, render_vangst
from nooch_village.views.werkoverleg import render_werkoverleg

C = "mother_earth__nooch"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def _vang(dd, *zinnen):
    for z in zinnen:
        cockpit2.dispatch(dd, "vangst_add", {"circle": [C], "punt": [z], "next": ["/"]},
                          username="guest")


# ── 1. het nieuwste agendapunt staat bovenaan ───────────────────────────────

def test_nieuw_agendapunt_staat_bovenaan(tmp_path):
    dd = _dd(tmp_path)
    for naam in ("Website Developer", "Data Analist"):
        cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "naam": [naam], "next": ["/"]},
                          username="guest")
    st = cockpit2._Stores(dd)
    # De store houdt zijn invoervolgorde — dat is het feit, en dat mag niet veranderd zijn.
    assert [it["title"] for it in st.agenda.all()] == ["Website Developer", "Data Analist"]
    # Het SCHERM draait hem om.
    assert [it["title"] for it in _rov_items(st, C)] == ["Data Analist", "Website Developer"]


def test_editor_opent_het_punt_dat_je_net_inbracht(tmp_path):
    """De klacht achter de volgorde: `active = items_open[0]`. Met invoervolgorde is dat het
    oudste open punt, dus na het toevoegen keek je naar iets anders dan wat je net typte."""
    dd = _dd(tmp_path)
    for naam in ("Website Developer", "Data Analist"):
        cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "naam": [naam], "next": ["/"]},
                          username="guest")
    st = cockpit2._Stores(dd)
    nieuwste = [it for it in st.agenda.all() if it["title"] == "Data Analist"][0]
    frag = cockpit2.render_roloverleg2(st, C, csrf_token="t", fragment=True)
    # het gemarkeerde item in de lijst is het nieuwste
    m = re.search(r"class='rov-item on'><a[^>]*iid=([0-9a-f]+)", frag)
    assert m and m.group(1) == nieuwste["id"]
    # en het staat ook fysiek boven het oudere punt in de agendalijst
    titels = re.findall(r"<span class='rov-title'>([^<]*)", frag)
    assert titels == ["Data Analist", "Website Developer"]


# ── 2. spanning voor spanning ───────────────────────────────────────────────

def test_agenda_stap_toont_een_spanning_tegelijk(tmp_path):
    dd = _dd(tmp_path)
    _vang(dd, "de leverancier belt niet terug", "de FSC-verklaring verloopt", "monsters zijn zoek")
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    frag = render_werkoverleg(cockpit2._Stores(dd), C, "agenda", csrf_token="t", fragment=True)
    # één verwerk-blok rechts... (`wo-ocd` staat twee keer per punt: bewerken én verwerken,
    # dus de summary is de betrouwbare teller)
    assert frag.count("<summary>verwerken</summary>") == 1
    # ...maar alle drie de punten links in het menu, want dat is de navigatie
    assert frag.count("class='rov-title'") == 3
    assert "volgende spanning" in frag


def test_menu_markeert_hetzelfde_punt_als_het_scherm_toont(tmp_path):
    """Twee plekken die zelf bepalen wat 'actief' is, wijzen vroeg of laat naar verschillende
    punten. Daarom lezen ze allebei `actief_punt`."""
    dd = _dd(tmp_path)
    _vang(dd, "punt een", "punt twee")
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    st = cockpit2._Stores(dd)
    verwacht = actief_punt(st.werk.punten(C))
    frag = render_werkoverleg(st, C, "agenda", csrf_token="t", fragment=True)
    m = re.search(r"class='rov-item on'><a[^>]*open=([0-9a-f]+)", frag)
    assert m and m.group(1) == verwacht
    # het geopende blok hoort bij datzelfde punt (het afgetikt-formulier draagt de iid)
    assert f"name='iid' value='{verwacht}'" in frag


def test_gekozen_punt_wint_van_het_eerste_open_punt(tmp_path):
    dd = _dd(tmp_path)
    _vang(dd, "punt een", "punt twee")
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    st = cockpit2._Stores(dd)
    punten = st.werk.punten(C)
    ander = [p for p in punten if p["id"] != actief_punt(punten)][0]
    frag = render_werkoverleg(st, C, "agenda", csrf_token="t", fragment=True, iid=ander["id"])
    assert ander["title"] in frag and frag.count("<summary>verwerken</summary>") == 1
    assert f"name='iid' value='{ander['id']}'" in frag


def test_vangscherm_blijft_de_volle_lijst(tmp_path):
    """`/vangst` is een ander gebaar: daar scan en vang je, en er is geen tweede lijst die de
    navigatie doet. De enkel-modus hoort dus niet te lekken."""
    dd = _dd(tmp_path)
    _vang(dd, "punt een", "punt twee", "punt drie")
    html = render_vangst(cockpit2._Stores(dd), C, csrf_token="t")
    assert html.count("<summary>verwerken</summary>") == 3
    assert "volgende spanning" not in html


# ── 3. het projectbord blijft in het overleg ────────────────────────────────

def test_groepeerknoppen_blijven_in_de_modal(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    frag = render_werkoverleg(cockpit2._Stores(dd), C, "projecten", csrf_token="t", fragment=True)
    assert "vbtn js-modal" in frag
    assert f"/werkoverleg?circle={C}&amp;step=projecten&amp;group=persoon" in frag
    # geen enkele weg terug naar de volle pagina: dát is wat het overleg dichtklapte
    assert f"/node?id={C}&tab=projects" not in frag


def test_buiten_het_overleg_verandert_er_niets(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    html = _projects_tab_html(st, st.records.get(C), "t")
    assert f"<a class='vbtn' href='/node?id={C}&amp;tab=projects&amp;group=persoon'>" in html
    assert "vbtn js-modal" not in html


def test_gekozen_groepering_blijft_staan(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    frag = render_werkoverleg(cockpit2._Stores(dd), C, "projecten", csrf_token="t",
                              fragment=True, group="persoon")
    assert "class='vbtn js-modal on'" in frag
    assert frag.index("group=persoon") > 0


def test_route_geeft_group_door():
    """De view kan het onthouden, maar alleen als de route de parameter doorgeeft. Dit is een
    structurele check op de aanroep — een string-grep zou groen blijven als iemand `group`
    doorgeeft in een comment of in een andere aanroep."""
    bron = pathlib.Path(cockpit2.__file__).read_text(encoding="utf-8")
    boom = ast.parse(bron)
    aanroepen = [n for n in ast.walk(boom)
                 if isinstance(n, ast.Call)
                 and getattr(n.func, "id", getattr(n.func, "attr", "")) == "render_werkoverleg"]
    assert aanroepen, "de route roept render_werkoverleg niet meer aan"
    assert any("group" in [k.arg for k in c.keywords] for c in aanroepen)
