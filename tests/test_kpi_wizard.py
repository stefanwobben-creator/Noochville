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


def test_wizard_een_regel_per_metric_werk_geconsolideerd(tmp_path):
    """Deelopdracht 3: werk staat één keer per metric (geconsolideerde def), niet als 3 dim-combos."""
    from nooch_village.views.metrics import _wizard_indicators
    st = cockpit2._Stores(_dd(tmp_path))
    inds = _wizard_indicators(st, st.records.get(C))
    namen = [i["name"] for i in inds]
    assert namen.count("Tevredenheid werkoverleg") == 1                  # één keer
    tev = next(i for i in inds if i["name"] == "Tevredenheid werkoverleg")
    assert tev["value"] == f"werk:{C}|tevredenheid|over_tijd" and tev["aard"] == "reeks"
    assert not any("|gemiddeld" in i["value"] or "|totaal" in i["value"] for i in inds)   # geen dim-combos
    assert next(i["value"] for i in inds if i["name"] == "Bezoekers (Plausible)") == "pulse_visitors|visitors|time"


def test_composer_categorie_eerst_lege_staat_en_placeholder(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    h = cockpit2.render_kpi_composer(st, C, csrf_token="t")
    assert "kc-empty" in h and "kc-picked" in h                          # lege-staat + picked-blok
    assert "Kies eerst een categorie" in h and "chip outline" in h       # categorie-prompt + aard-tag
    assert "Standaard weergave" in h and "<select name='form'>" in h     # stap 3 = vorm-keuze (Tufte-tabel)


def test_wizard_werk_tegel_maakt_en_rendert(tmp_path):
    """Een via de wizard gekozen werk-metric (over_tijd-value) maakt een tegel die rendert."""
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "tile_add", {"node": [C], "combo": [f"werk:{C}|tevredenheid|over_tijd"],
                      "form": ["trend"], "ref_kind": [""], "target": [""], "mode": ["indicator"],
                      "next": ["/"]}, "guest")
    tiles = [t for t in cockpit2._Stores(dd).metrics.tiles_of(C) if t.get("measure") == "tevredenheid"]
    assert tiles and tiles[0]["dim"] == "over_tijd"
    page = cockpit2.render_node(cockpit2._Stores(dd), C, "metrics", csrf_token="t")
    assert "Tevredenheid" in page or "tevredenheid" in page


def test_stap3_vormkeuze_tufte_beslistabel(tmp_path):
    """Deelopdracht 4: stap 3 is de vorm-keuze (Tufte-tabel), geen placeholder + geen data-aard-brug meer."""
    st = cockpit2._Stores(_dd(tmp_path))
    h = cockpit2.render_kpi_composer(st, C, csrf_token="t")
    assert "name='form'" in h and "kc-tufte" in h                       # vorm-select + tufte-microcopy
    for key in ("'reeks|0'", "'reeks|1'", "'moment|0'", "'categorie|0'"):
        assert key in h                                                  # de beslistabel per aard × referentie
    for vorm in ("trend", "staaf", "bullet", "gestapeld", "horizontaal"):
        assert vorm in h                                                 # alle vormen kiesbaar
    assert "AARD_FORM" not in h                                          # de brug uit deelopdracht 3 is weg (één plek)


def test_nieuwe_svg_renderers_en_geen_data(tmp_path):
    from nooch_village.views.metrics import _bar_chart_svg, _stacked_bar_svg, _hbar_svg
    pts = [(1000.0, 3), (1086400.0, 5)]; rows = [("NL", 40), ("BE", 12)]
    assert "barchart" in _bar_chart_svg(pts) and "stackbar" in _stacked_bar_svg(rows) and "hbar" in _hbar_svg(rows)
    assert "style=" not in _bar_chart_svg(pts) + _stacked_bar_svg(rows) + _hbar_svg(rows)   # SVG-attributen, geen inline
    for r in (_bar_chart_svg([]), _stacked_bar_svg([]), _hbar_svg([])):
        assert "geen data in deze periode" in r                         # zelfde geen-data als het lijndiagram


def test_staaf_tegel_rendert_end_to_end(tmp_path):
    import time, datetime
    dd = _dd(tmp_path); st = cockpit2._Stores(dd); base = time.time() - 2 * 86400
    today = datetime.date.today()
    for i, v in enumerate([40, 55, 48]):                 # recente datum+ts → binnen het 7d-standaardvenster
        d = (today - datetime.timedelta(days=2 - i)).isoformat()   # dynamisch (niet hardcoded, geen datum-rollover)
        st.observations.record_daily("website_watcher", "plausible_visitors_day", v, bron="plausible",
                                     datum=d, ts=base + i * 86400)
    cockpit2.dispatch(dd, "tile_add", {"node": [C], "combo": ["pulse_visitors|visitors|time"],
                      "form": ["staaf"], "ref_kind": [""], "target": [""], "mode": ["indicator"],
                      "next": ["/"]}, "guest")
    tile = [t for t in cockpit2._Stores(dd).metrics.tiles_of(C) if t.get("form") == "staaf"][0]
    assert tile["form"] == "staaf"                                       # de gekozen vorm is opgeslagen (één plek)
    page = cockpit2.render_node(cockpit2._Stores(dd), C, "metrics", csrf_token="t")
    assert "barchart" in page                                           # de staaf-renderer draait op de tegel


def test_categorie_chips_gebruiken_design_componenten(tmp_path):
    """Scope 2: de categorie-chips zijn .chip-opt-pills in een .chip-wrap (flex-wrap), niet de oude
    niet-wrappende .cl-bar-tekst. De actieve categorie krijgt .on (→ .chip-opt.on)."""
    st = cockpit2._Stores(_dd(tmp_path))
    h = cockpit2.render_kpi_composer(st, C, csrf_token="t")
    assert "class='chip-wrap kc-cats'" in h                 # wrap-rij: chips breken af binnen de kaart
    assert "class='chip-opt kc-cat'" in h                   # interactieve pill (design-systeem-component)
    assert "cl-bar kc-cats" not in h                        # oude niet-wrappende opmaak weg
    assert "classList.toggle('on'" in h                     # JS zet .on op de actieve categorie
