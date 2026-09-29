"""Vier losse stukken (29 september 2026, avond).

Ze delen geen thema, wel een vorm: alle vier bouwen op mechaniek die er al stond.

  1. FOCUS-MODUS — zie `tests/test_overleg_projecten_breed.py`, waar de uitzondering die hij
     vervangt werd vastgelegd. Hier staat alleen wat de server ervan weet.
  2. EEN LINK IN EEN TABELCEL overleeft "bewerk als tekst" — de fix zit in `nooch.js`, dus de
     gedragstoets staat in `tests/js/poller.test.js`. Hier de server-kant: die deed het al goed,
     en dat hoort zo te blijven.
  3. HET BORD VERVERST voor wie meekijkt tijdens een overleg.
  4. `[[` KRIJGT TYPHULP: pagina's op titel, uit dezelfde lijst waar `wiki.resolve` tegen oplost.
"""
from __future__ import annotations

import json

from nooch_village import cockpit2, wiki
from nooch_village.views.search import pagina_hits

C = "mother_earth__nooch"
ROL = "mother_earth__nooch__website_developer"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


def _open(dd):
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")


# ══ 3. Het bord ververst voor de meekijkers ══════════════════════════════════
def test_het_bord_zit_in_een_poller_tijdens_het_overleg(tmp_path):
    dd, st = _dorp(tmp_path)
    _open(dd)
    st.projects.create(f"{C}__brand_visual_designer", "Een project", "human")
    html = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, step="projecten", csrf_token="t")
    assert "data-poll='/wo-bord-status?circle=" + C + "'" in html
    assert "data-poll-ms='6000'" in html
    # HET OMHULSEL BLIJFT STAAN: de poller vervangt de INHOUD van dit element, dus het bord zelf
    # hoort erbinnen te zitten en niet eromheen.
    binnen = html.split("data-poll=")[1].split(">", 1)[1]
    assert "pboard" in binnen.split("</div>")[0] or "pboard" in binnen[:4000]


def test_de_route_geeft_hetzelfde_bord_terug(tmp_path):
    from nooch_village.views.werkoverleg import _projects_tab_html
    dd, st = _dorp(tmp_path)
    _open(dd)
    st.projects.create(f"{C}__brand_visual_designer", "Een project", "human")
    st = cockpit2._Stores(dd)
    fragment = _projects_tab_html(st, st.records.get(C), "t", group="", add=False,
                                  nav=f"/werkoverleg?circle={C}&step=projecten")
    assert "Een project" in fragment and "pboard" in fragment


def test_zonder_lopend_overleg_geen_bord_en_geen_poller(tmp_path):
    """De route is niet bedoeld als publieke bord-API, en zonder overleg kijkt er ook niemand
    mee. `is_open` is dezelfde vraag die het scherm zelf stelt."""
    dd, st = _dorp(tmp_path)
    st.projects.create(f"{C}__brand_visual_designer", "Een project", "human")
    html = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, step="projecten", csrf_token="t")
    assert "wo-bord-status" not in html          # het overleg loopt niet: geen Projects-stap
    assert not cockpit2._Stores(dd).werk.is_open(C)


# ══ 4. `[[` krijgt typhulp ═══════════════════════════════════════════════════
def _paginas(st, *titels):
    for t in titels:
        st.att.add(ROL, "note", title=t, body="x")
    return cockpit2._Stores(st.dd) if hasattr(st, "dd") else st


def test_de_lijst_matcht_op_titel(tmp_path):
    dd, st = _dorp(tmp_path)
    for t in ("Outsole materials", "Hemp canvas", "Outsole suppliers"):
        st.att.add(ROL, "note", title=t, body="x")
    st = cockpit2._Stores(dd)
    labels = [h["label"] for h in pagina_hits(st, "outsole")]
    assert labels == ["Outsole materials", "Outsole suppliers"]


def test_de_body_telt_hier_niet_mee(tmp_path):
    """HET VERSCHIL MET DE ZOEKBALK. `_pages` doorzoekt ook de tekst en de feiten — goed als je
    nog niet weet hoe iets heet. Een link-picker beantwoordt "hoe heet die pagina exact", en een
    treffer op een woord middenin de tekst is daar ruis."""
    dd, st = _dorp(tmp_path)
    st.att.add(ROL, "note", title="Hemp canvas", body="Deze pagina noemt outsole heel vaak.")
    st = cockpit2._Stores(dd)
    assert pagina_hits(st, "outsole") == []


def test_een_dubbele_titel_levert_zijn_id(tmp_path):
    """`wiki.resolve` lost een dubbele titel BEWUST niet op (een gok kan naar de verkeerde pagina
    wijzen). Dan is het id de enige vorm die nog werkt — en dus wat de picker aanbiedt."""
    dd, st = _dorp(tmp_path)
    a = st.att.add(ROL, "note", title="Outsole", body="x")
    b = st.att.add(ROL, "note", title="Outsole", body="y")
    st = cockpit2._Stores(dd)
    labels = [h["label"] for h in pagina_hits(st, "outsole")]
    assert sorted(labels) == sorted([a.id, b.id])
    pags = wiki.verwijsbaar(st.att)
    assert wiki.resolve(labels[0], pags) is not None
    assert wiki.resolve("Outsole", pags) is None, "de titel loste toch op"


def test_alles_wat_de_picker_aanbiedt_lost_ook_echt_op(tmp_path):
    """DE ENIGE EIS DIE ERTOE DOET. Een picker die iets aanbiedt wat `resolve` daarna niet vindt,
    is erger dan geen picker: je denkt dat je gelinkt hebt."""
    dd, st = _dorp(tmp_path)
    for t in ("Outsole materials", "Hemp canvas"):
        st.att.add(ROL, "note", title=t, body="x")
    st.att.add(ROL, "policy", title="Outsole policy", body="x")
    st = cockpit2._Stores(dd)
    pags = wiki.verwijsbaar(st.att)
    for h in pagina_hits(st, "o"):
        assert wiki.resolve(h["label"], pags) is not None, h


def test_lege_zoekterm_geeft_de_eerste_paginas(tmp_path):
    """Je hebt dan net `[[` getypt. Een lege lijst ziet eruit als kapot."""
    dd, st = _dorp(tmp_path)
    for t in ("Aaa", "Bbb"):
        st.att.add(ROL, "note", title=t, body="x")
    st = cockpit2._Stores(dd)
    # Het dorp start met een eigen pagina (de Decision coach-tool), dus niet "precies deze twee":
    # wat telt is dat een lege term een GEVULDE lijst geeft, op alfabet.
    labels = [h["label"] for h in pagina_hits(st, "")]
    assert labels[:2] == ["Aaa", "Bbb"] and len(labels) >= 2


def test_de_route_geeft_json(tmp_path):
    dd, st = _dorp(tmp_path)
    st.att.add(ROL, "note", title="Outsole materials", body="x")
    st = cockpit2._Stores(dd)
    hits = pagina_hits(st, "outsole")
    assert json.dumps({"hits": hits})          # serialiseerbaar, zoals de route hem verstuurt
    assert hits[0]["kind"] == "note" and hits[0]["titel"] == "Outsole materials"


def test_het_bewerkveld_en_het_voorstelveld_dragen_de_haak(tmp_path):
    """De typhulp hangt aan `#wiki-body` (het contenteditable bewerkveld) en aan elk veld met
    `data-wikilink` — het voorstelformulier, want dat wordt straks de tekst van de pagina."""
    from nooch_village.views.wiki import _voorstel_form, render_pagina
    dd, st = _dorp(tmp_path)
    mens = st.people.add("Beheerder", "b@t.nl")
    st.assign.assign(ROL, "person", mens.id)
    a = st.att.add(ROL, "note", title="Outsole materials", body="x")
    st = cockpit2._Stores(dd)
    assert "id='wiki-body'" in render_pagina(st, a.id, csrf_token="TOK", username="b@t.nl")
    assert "data-wikilink" in _voorstel_form(st, st.att.get(a.id), "TOK")
