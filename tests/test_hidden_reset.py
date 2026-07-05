"""Guard: het `hidden`-attribuut moet betrouwbaar werken. Een author `display:`-regel (bv.
.kc-radio{display:block}) overrulet anders `[hidden]`, waardoor categorie-filter/flip/kc-mode niet
werken. De reset `[hidden]{display:none!important}` staat in de basis-chrome en gaat op elke pagina mee."""
from __future__ import annotations

from nooch_village.web_base import _CSS
from nooch_village import cockpit2
from nooch_village.views import metrics


def test_hidden_reset_in_basis_chrome():
    assert "[hidden]{display:none!important}" in _CSS


def test_kpi_composer_ship_reset_en_verborgen_radios(tmp_path):
    dd = str(tmp_path / "poc"); cockpit2._bootstrap(dd); st = cockpit2._Stores(dd)
    h = metrics.render_kpi_composer(st, "mother_earth__nooch", "tok")
    assert "[hidden]{display:none!important}" in h        # reset gaat mee op /kpi_new
    assert "kc-metric" in h and "hidden>" in h            # radios dragen nog steeds hidden (JS toggelt dit)
