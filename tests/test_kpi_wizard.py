"""Scope 5 — KPI-wizard: modus-toggle + categorie-eerst + ⓘ-tooltips + grijs-bij-geen-data,
plaats (context vs losstaand), vorm-op-aard, en de formule-modus (opslag + verplichte aggregatie)."""
from __future__ import annotations

from nooch_village import cockpit2

C = "mother_earth__nooch"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def test_wizard_indicators_categorie_en_heeft_data(tmp_path):
    from nooch_village.views.metrics import _wizard_indicators
    st = cockpit2._Stores(_dd(tmp_path))
    inds = {i["name"]: i for i in _wizard_indicators(st, st.records.get(C))}
    # bron-liveness whitelist
    assert inds["Bezoekers (Plausible)"]["has_data"] is True        # plausible = live
    assert inds["Voorraadwaarde"]["has_data"] is False              # erp = nog geen data
    # categorie-backfill (source→categorie)
    assert inds["Bezoekers (Plausible)"]["categorie"] == "Website"
    assert inds["Voorraadwaarde"]["categorie"] == "Supply chain"


def test_composer_structuur_en_geen_inline_style(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    h = cockpit2.render_kpi_composer(st, C, csrf_token="t")
    assert "kc-mode-btn" in h and "Formule maken" in h             # modus-toggle
    assert "kc-cat" in h and "kc-metric" in h                      # categorie-chips + metric-lijst
    assert "title=" in h and "nog geen data" in h                  # ⓘ-tooltips + grijs
    assert "f_agg" in h and "f_op" in h                            # formule-modus met aggregatie
    assert "data-aard='reeks'" in h                                # vorm gefilterd op aard
    assert "name='node' value='mother_earth__nooch'" in h          # plaats context-afgeleid (vast)
    assert "style='display:none'" not in h                         # geen inline styles meer


def test_composer_losstaand_geeft_plaats_keuze(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    h = cockpit2.render_kpi_composer(st, "", csrf_token="t")        # geen node → losstaande start
    assert "<select name='node'>" in h and "Losstaande start" in h


def test_formule_verplichte_aggregatie(tmp_path):
    dd = _dd(tmp_path)
    _, msg = cockpit2.dispatch(dd, "tile_add", {
        "node": [C], "mode": ["formule"], "f_a": ["pulse_visitors|visitors|time"], "f_op": ["÷"],
        "f_b": ["shopify|pairs_sold|none"], "f_name": ["Conversie"], "f_agg": [""], "next": ["/"]},
        username="guest")
    assert "aggregatie" in msg.lower()                              # zonder aggregatie → geweigerd
    assert not [t for t in cockpit2._Stores(dd).metrics.tiles_of(C) if t.get("form") == "formule"]


def test_formule_opslag_en_placeholder_render(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "tile_add", {
        "node": [C], "mode": ["formule"], "f_a": ["pulse_visitors|visitors|time"], "f_op": ["÷"],
        "f_b": ["shopify|pairs_sold|none"], "f_name": ["Conversie"], "f_agg": ["gemiddelde"], "next": ["/"]},
        username="guest")
    t = [x for x in cockpit2._Stores(dd).metrics.tiles_of(C) if x.get("form") == "formule"][0]
    assert t["measure"] == "Conversie" and t["f_op"] == "÷" and t["aggregatie"] == "gemiddelde"
    assert t["f_a"] == "pulse_visitors|visitors|time" and t["f_b"] == "shopify|pairs_sold|none"
    page = cockpit2.render_node(cockpit2._Stores(dd), C, "metrics", csrf_token="t")
    # de formule-tegel wordt nu fail-closed doorgerekend; zonder dagdata → eerlijk 'geen data'
    assert "Conversie" in page and "berekening volgt" not in page
