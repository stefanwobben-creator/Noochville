"""Brede Finance-tabellen op een telefoon (11 oktober 2026). Op 390px maakte de kostentabel de hele
pagina 747px breed: onder 760px is `.c2-wrap` een kolom met `align-items:flex-start`, en dan is
`.c2-main` zo breed als zijn inhoud. De Finance-frame rekt de kolom op (`c2-main--vol`) en een brede
tabel scrollt in zijn eigen `.c2-scroll`. Gemeten in Chrome op 390px: /finance/costs, /revenue
en /pnl 390px breed, tabbalk 358px; op 1300px verschuift er niets."""
from __future__ import annotations

import pathlib

from nooch_village.views import finance as fin

from tests.test_finance_omzet import _omzet
from tests.test_finance_pr1 import _boek, _dorp, _st

CSS = (pathlib.Path(__file__).resolve().parents[1] / "nooch_village" / "static" / "nooch.css").read_text()


def test_de_css_regels_bestaan_en_raken_alleen_de_modifier():
    assert "@media(max-width:760px){.c2-main--vol{align-self:stretch}}" in CSS
    assert ".c2-scroll{overflow-x:auto;max-width:100%}" in CSS
    assert ".rov-addgrid>*{min-width:0}" in CSS and ".qadd-form input[type=file]{max-width:100%}" in CSS
    # NIET `.c2-main` zelf: dat verschuift op 390px vrijwel alles op /projects en /wiki.
    assert "{.c2-main{align-self:stretch}}" not in CSS


def test_finance_tabellen_staan_in_een_scrollcontainer(tmp_path):
    dd = _dorp(tmp_path)
    _boek(dd, period="2026-10")
    _omzet(dd)
    st = _st(dd)
    for html in (fin.render_costs(st, "fc@t.nl", "t", {}), fin.render_revenue(st, "fc@t.nl", "t", {}),
                 fin.render_pnl(st, "fc@t.nl")):
        assert "class='c2-main c2-main--vol'" in html
        i = html.index("<table class='mtab'")
        assert "c2-scroll'>" in html[html.rindex("<div", 0, i):i]


def test_geen_scrollcontainer_om_een_lege_toestand(tmp_path):
    """`overflow` om een gewone alinea verandert het samenvallen van marges (14px verschil gemeten)."""
    html = fin.render_costs(_st(_dorp(tmp_path)), "fc@t.nl", "t", {})
    assert "c2-scroll" not in html
