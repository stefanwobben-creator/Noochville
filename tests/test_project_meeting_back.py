"""Projectdetail geopend vanuit het werkoverleg: terug-CTA (boven+onder) + niet-sluitbaar."""
from __future__ import annotations

from nooch_village import cockpit2


def _setup(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rid = "mother_earth__nooch__website_developer"
    pid = st.projects.create(rid, "Checkout", "human")
    return dd, pid


def test_normaal_geen_terug_cta(tmp_path):
    dd, pid = _setup(tmp_path)
    frag = cockpit2.render_project(cockpit2._Stores(dd), pid, csrf_token="t", fragment=True)
    assert "terug naar werkoverleg" not in frag and "data-noclose" not in frag


def test_vanuit_werkoverleg_terug_cta_en_noclose(tmp_path):
    dd, pid = _setup(tmp_path)
    back = "/werkoverleg?circle=mother_earth__nooch&step=projecten"
    frag = cockpit2.render_project(cockpit2._Stores(dd), pid, csrf_token="t", back=back, fragment=True)
    assert frag.count("← terug naar werkoverleg") == 2          # boven én onder
    assert "data-noclose='1'" in frag and "step=projecten" in frag
