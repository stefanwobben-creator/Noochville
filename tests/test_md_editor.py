"""De gedeelde opmaak-editor (md_editor): rendert, is zelfvoorzienend op een pagina zonder _modal_html,
wrapSel wordt nooit dubbel gedefinieerd (guarded), en een geconverteerd veld toont markdown veilig."""
from __future__ import annotations

from nooch_village import cockpit2
from nooch_village.cockpit2_util import md_editor
from nooch_village.views.projects import _modal_html
from nooch_village.views.backlog import render_backlog_tab, _item_beheer

CIRCLE = "mother_earth__nooch"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def test_md_editor_rendert_en_escapet_value():
    h = md_editor("body", "**hoi** <script>", rows=5)
    assert "class='editor'" in h and "class='editor-tb'" in h
    assert "<textarea name='body' rows='5'" in h
    assert "if(!window.wrapSel)" in h                          # zelfvoorzienend + guarded
    voor_ta = h.split("</textarea>")[0]
    assert "&lt;script&gt;" in voor_ta and "<script>" not in voor_ta   # value ge-escaped in de textarea
    assert md_editor("x", help=True).count("md-help") == 1 and "md-help" not in md_editor("x")


def test_editor_werkt_op_pagina_zonder_modal_html(tmp_path):
    """De backlog-tab laadt _modal_html NIET; toch werkt de editor er (wrapSel reist mee)."""
    st = cockpit2._Stores(_dd(tmp_path))
    rec = st.records.get(CIRCLE)
    tab = render_backlog_tab(st, rec, csrf="t", username="x@y.nl")
    assert "class='editor'" in tab and "if(!window.wrapSel)" in tab
    # de modal definieert wrapSel nu WÉL (guarded): een <script> in een fragment draait niet bij
    # innerHTML, dus zonder deze definitie deden de WYSIWYG-knoppen in de modal niets.
    assert "window.wrapSel=" in _modal_html() and "if(!window.wrapSel)" in _modal_html()


def test_wrapsel_nooit_dubbel_gedefinieerd():
    # elke md_editor-instantie is guarded → op een pagina met N editors nooit een runtime-herdefinitie
    two = md_editor("a") + md_editor("b")
    # ELKE definitie zit achter de guard; geen kale definitie
    assert "window.wrapSel=function" not in two.replace("if(!window.wrapSel){window.wrapSel=function", "")


def test_geconverteerd_veld_toont_markdown_veilig(tmp_path):
    """Backlog-beschrijving ging van _e (plat) naar _md (opmaak): markdown wordt gerenderd en HTML blijft
    ge-escaped (geen rauwe opmaaktekens, geen onveilige HTML)."""
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "backlog_add",
                      {"titel": ["T"], "beschrijving": ["**vet** en <script>x</script>"],
                       "type": ["taak"], "domein": ["algemeen"], "next": ["/"]}, "guest")
    st = cockpit2._Stores(dd)
    it = st.backlog.all()[0]
    html = _item_beheer(st.records.get(CIRCLE), it, "t")
    assert "<strong>vet</strong>" in html and "**vet**" not in html     # markdown gerenderd
    assert "&lt;script&gt;" in html and "<script>x" not in html          # HTML ge-escaped (veilig)
