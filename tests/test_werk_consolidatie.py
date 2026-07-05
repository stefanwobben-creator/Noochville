"""Deelopdracht 1: consolidatie werk-metric-definities. Elke werk-metric is één def met de scope-3-
velden aard+aggregatie + een werk_measure-koppeling naar de combo. Idempotent; bestaande tegels
(werk:<circle>|measure|dim) blijven ongemoeid resolven."""
from __future__ import annotations

from nooch_village import cockpit2
from nooch_village.definitions import migrate_definitions, _WERK_CONSOLIDATIE
from nooch_village.metric_schema import DIM_AGGREGATIE, normalize


def _defs_by_name(st):
    return {(st.defs.current(d["id"]) or {}).get("name"): (st.defs.current(d["id"]) or {})
            for d in st.defs.all()}


def test_werk_defs_krijgen_aard_aggregatie_en_koppeling(tmp_path):
    dd = str(tmp_path / "poc"); cockpit2._bootstrap(dd); st = cockpit2._Stores(dd)  # bootstrap draait migrate
    byname = _defs_by_name(st)
    for name, (measure, aard, agg) in _WERK_CONSOLIDATIE.items():
        c = byname[name]
        assert c["werk_measure"] == measure, name
        assert c["aard"] == aard, name              # bewuste correctie moment→reeks
        assert c["aggregatie"] == agg, name          # scores middelen, tellingen sommeren


def test_migratie_is_idempotent(tmp_path):
    dd = str(tmp_path / "poc"); cockpit2._bootstrap(dd); st = cockpit2._Stores(dd)
    assert migrate_definitions(st.defs) == 0          # bootstrap deed 'm al → tweede run 0 wijzigingen


def test_niet_werk_defs_onaangeroerd(tmp_path):
    dd = str(tmp_path / "poc"); cockpit2._bootstrap(dd); st = cockpit2._Stores(dd)
    bez = _defs_by_name(st)["Bezoekers (Plausible)"]
    assert bez["werk_measure"] == ""                  # geen werk-metric → geen koppeling
    assert bez["aard"] == "reeks"                      # z'n eigen aard blijft


def test_dim_aggregatie_map_en_schema():
    assert DIM_AGGREGATIE == {"gemiddeld": "gemiddelde", "totaal": "som"}   # over_tijd = reeks, geen agg
    assert normalize(name="X", werk_measure="duur")["werk_measure"] == "duur"  # schema behoudt het veld


def test_bestaande_werk_tegel_blijft_resolven(tmp_path):
    # oude sleutel werk:<circle>|measure|dim moet ongewijzigd blijven werken (non-destructief)
    from nooch_village.views.metrics import _fetch
    dd = str(tmp_path / "poc"); cockpit2._bootstrap(dd); st = cockpit2._Stores(dd)
    C = "mother_earth__nooch"
    res = _fetch(st, f"werk:{C}", "tevredenheid", "gemiddeld", None, None)
    assert res["kind"] in ("number", "series")        # resolvet zonder te breken
