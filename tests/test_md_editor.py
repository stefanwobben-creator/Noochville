"""De gedeelde opmaak-editor (md_editor): rendert, is zelfvoorzienend op een pagina zonder _modal_html,
wrapSel wordt nooit dubbel gedefinieerd (guarded), en een geconverteerd veld toont markdown veilig."""
from __future__ import annotations

from nooch_village import cockpit2
from nooch_village.cockpit2_util import md_editor, _md
from nooch_village.views.projects import _modal_html
from nooch_village.views.rapport import render_projectrapport

CIRCLE = "mother_earth__nooch"
ROLE = "mother_earth__nooch__website_developer"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def test_md_editor_rendert_en_escapet_value():
    h = md_editor("body", "**hoi** <script>", rows=5)
    assert "class='editor'" in h and "class='editor-tb'" in h
    assert "<textarea name='body' rows='5'" in h
    assert "if(!window.wrapSel)" in h                          # zelfvoorzienend + guarded
    assert "title='Bold'" in h and "title='Heading'" in h      # toolbar-knoppen aanwezig
    assert "title='Link'" not in h and "🔗" not in h           # link-knop bewust weg (renderer blijft)
    voor_ta = h.split("</textarea>")[0]
    assert "&lt;script&gt;" in voor_ta and "<script>" not in voor_ta   # value ge-escaped in de textarea
    assert md_editor("x", help=True).count("md-help") == 1 and "md-help" not in md_editor("x")


def test_editor_werkt_op_pagina_zonder_modal_html(tmp_path):
    """Het rapport-scherm laadt _modal_html NIET; toch werkt de editor er (wrapSel reist mee).
    (Tot 11 september 2026 was het backlog-scherm hier het voertuig; dat is verwijderd.)"""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    pid = st.projects.create(ROLE, "Eén document", "human", status="queued", done_when="af")
    st.projects.start(pid)
    tab = render_projectrapport(cockpit2._Stores(dd), pid, csrf_token="t")
    assert "class='editor'" in tab and "if(!window.wrapSel)" in tab
    assert "wrapSel=function" not in tab.replace("if(!window.wrapSel){window.wrapSel=function", "")
    # de modal definieert wrapSel nu WÉL (guarded): een <script> in een fragment draait niet bij
    # innerHTML, dus zonder deze definitie deden de WYSIWYG-knoppen in de modal niets.
    assert "window.wrapSel=" in _modal_html() and "if(!window.wrapSel)" in _modal_html()


def test_wrapsel_nooit_dubbel_gedefinieerd():
    # elke md_editor-instantie is guarded → op een pagina met N editors nooit een runtime-herdefinitie
    two = md_editor("a") + md_editor("b")
    # ELKE definitie zit achter de guard; geen kale definitie
    assert "window.wrapSel=function" not in two.replace("if(!window.wrapSel){window.wrapSel=function", "")


def test_geconverteerd_veld_toont_markdown_veilig():
    """Een veld dat van _e (plat) naar _md (opmaak) gaat: markdown wordt gerenderd en HTML blijft
    ge-escaped (geen rauwe opmaaktekens, geen onveilige HTML). Dit is de eigenschap van `_md` zelf;
    het backlog-scherm dat hem eerst droeg is weg."""
    html = _md("**vet** en <script>x</script>")
    assert "<strong>vet</strong>" in html and "**vet**" not in html     # markdown gerenderd
    assert "&lt;script&gt;" in html and "<script>x" not in html          # HTML ge-escaped (veilig)
