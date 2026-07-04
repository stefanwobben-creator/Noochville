"""Scope 6 — dashboard: centrale periode-picker (start,end), Actueel-liveness, compare (reeks-lijn +
moment-delta), uitklap met bron-kolom, en de ⓘ-flip (voor-/achterkant)."""
from __future__ import annotations
import time

from nooch_village import cockpit2
from nooch_village.views.metrics import _metrics_tab_html
from nooch_village.metrics import window_range

C = "mother_earth__nooch"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def test_window_range():
    now = 1_800_000_000.0
    s, e = window_range("gisteren", now)
    assert s is not None and e is not None and s < e
    assert window_range("actueel", now)[0] is None            # alles → laatste waarde
    s, e = window_range("aangepast", now, "2026-07-01", "2026-07-03")
    assert s is not None and e is not None and s < e


def test_periode_picker_en_actueel_liveness(tmp_path):
    dd = _dd(tmp_path); st = cockpit2._Stores(dd); rec = st.records.get(C)
    h = _metrics_tab_html(st, rec, csrf="t", win="7d")
    assert all(p in h for p in ("Vandaag", "Gisteren", "Actueel", "7 dagen", "28 dagen",
                                "Kwartaal", "Jaar", "Aangepast"))
    assert "muted' title='alleen beschikbaar bij een live-capabele bron'>Actueel" in h  # grijs zonder live-bron
    st.metrics.add_tile(C, "pulse_visitors", "visitors", "time", "verdeling")
    h2 = _metrics_tab_html(cockpit2._Stores(dd), rec, csrf="t", win="7d")
    assert "mw=actueel" in h2                                  # met live-bron → klikbaar


def test_compare_reeks_tweede_lijn(tmp_path):
    dd = _dd(tmp_path); st = cockpit2._Stores(dd); now = time.time()
    for i, v in enumerate([40, 55, 48]):                       # huidige 7d-venster
        st.observations.record_daily("ww", "visitors_day", v, bron="plausible", datum=f"cur{i}", ts=now - i * 86400 - 3600)
    for i, v in enumerate([30, 35, 33]):                       # vorige 7d-venster
        st.observations.record_daily("ww", "visitors_day", v, bron="plausible", datum=f"prev{i}", ts=now - (8 + i) * 86400)
    st.metrics.add_tile(C, "pulse_visitors", "visitors", "time", "verdeling")
    h = _metrics_tab_html(cockpit2._Stores(dd), st.records.get(C), csrf="t", win="7d", compare=True)
    assert h.count("<polyline") >= 2                          # huidige + vorige periode als twee lijnen


def test_compare_moment_delta(tmp_path):
    dd = _dd(tmp_path); st = cockpit2._Stores(dd); now = time.time()
    st.werk._m.setdefault(C, {})["log"] = [
        {"at": now - 1 * 86400, "tevredenheid": 8.0},         # huidige 7d
        {"at": now - 9 * 86400, "tevredenheid": 6.0},         # vorige 7d
    ]
    st.werk._save()
    st.metrics.add_tile(C, f"werk:{C}", "tevredenheid", "gemiddeld", "getal")
    h = _metrics_tab_html(cockpit2._Stores(dd), st.records.get(C), csrf="t", win="7d", compare=True)
    assert "vs vorige periode" in h                           # delta-badge naast het getal


def test_uitklap_ruwe_data_met_bron(tmp_path):
    dd = _dd(tmp_path); st = cockpit2._Stores(dd); now = time.time()
    st.observations.record_daily("ww", "visitors_day", 40, bron="plausible", datum="a", ts=now - 1 * 86400)
    st.observations.record_daily("ww", "visitors_day", 55, bron="plausible", datum="b", ts=now - 2 * 86400)
    st.metrics.add_tile(C, "pulse_visitors", "visitors", "time", "verdeling")
    h = _metrics_tab_html(cockpit2._Stores(dd), st.records.get(C), csrf="t", win="7d")
    assert "ruwe data" in h and "<th>bron</th>" in h


def test_flip_voor_en_achterkant(tmp_path):
    dd = _dd(tmp_path); st = cockpit2._Stores(dd)
    st.metrics.add_tile(C, "pulse_visitors", "visitors", "time", "verdeling")
    h = _metrics_tab_html(cockpit2._Stores(dd), st.records.get(C), csrf="t", win="7d")
    assert "js-flip" in h and "tile-front" in h and "tile-back" in h and "js-flipback" in h
    assert "style='display" not in h                          # geen inline styles
