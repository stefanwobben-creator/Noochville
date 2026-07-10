"""PR 1 — data-semantiek van de metrics-kaart: complete-dagen-venster, headline = venster-aggregaat
volgens de aggregatieregel, ruwe tabel = exact de grafiek-dataset (ongecapt), delta alleen bij
'Vergelijk met vorige periode'."""
from __future__ import annotations

import datetime as dt
import time

from nooch_village import cockpit2
from nooch_village.metrics import window_range, filter_samples
from nooch_village.views.metrics import _agg, _data_table

C = "mother_earth__nooch"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def _today0(now: float) -> float:
    d = dt.datetime.fromtimestamp(now)
    return dt.datetime(d.year, d.month, d.day).timestamp()


# ── 3. venster = complete dagen (vandaag telt niet mee) ──────────────────────────────────────────
def test_window_sluit_vandaag_uit():
    now = time.time()
    today0 = _today0(now)
    start, end = window_range("7d", now)
    assert end == today0                       # einde = middernacht vandaag
    assert start == today0 - 7 * 86400         # begin = 7 volledige dagen terug
    # een meting van vandaag valt buiten het venster; die van gisteren erin
    samples = [{"at": today0 + 3600, "value": 99}, {"at": today0 - 86400, "value": 5}]
    assert [p[1] for p in filter_samples(samples, start, end)] == [5]


# ── 1/2. aggregatieregel bepaalt de headline ─────────────────────────────────────────────────────
def test_agg_regels():
    res = {"kind": "series", "points": [(1, 10, None), (2, 20, None), (3, 30, None)]}
    assert _agg(res, "som") == 60
    assert _agg(res, "gemiddelde") == 20
    assert _agg(res, "laatste_waarde") == 30
    assert _agg({"kind": "series", "points": []}, "som") is None   # geen data ≠ 0


def test_headline_is_som_aggregaat(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    k = st.metrics.add_kpi(C, "Sommetje", "n", aggregatie="som")
    now = time.time()
    for d, v in ((2, 11), (3, 22), (4, 33)):    # 3 complete dagen in het 7d-venster
        st.metrics.add_sample(k["id"], v, at=now - d * 86400)
    cockpit2.dispatch(dd, "tile_add", {"node": [C], "combo": [f"kpi:{k['id']}|value|none"],
                                       "form": ["trend"], "target": [""], "next": ["/"]}, username="guest")
    page = cockpit2.render_node(cockpit2._Stores(dd), C, "metrics", "t")
    assert "class='kpi-val'>66" in page         # 11+22+33 = som als kaart-headline, NIET de laatste 33
    assert "totaal 7d" in page                  # aggregatielabel bij de headline
    assert "class='linechart'" in page          # kaart toont het lijn-diagram met assen (geen sparkline)


# ── 5. ruwe-datatabel = exact de grafiek-dataset (ongecapt) ──────────────────────────────────────
def test_tabel_niet_afgekapt_en_gelijk_aan_grafiek():
    pts = [(float(i), float(i), f"2026-01-{i:02d}") for i in range(1, 20)]   # 19 punten > oude cap van 12
    res = {"kind": "series", "points": pts}
    html = _data_table(res, bron="test")
    assert html.count("<tr>") == 1 + len(pts)   # header + elke rij; geen afkapping op 12


# ── 4. delta alleen bij 'Vergelijk met vorige periode' ───────────────────────────────────────────
def test_delta_alleen_bij_compare(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    k = st.metrics.add_kpi(C, "Reeksje", "n", aggregatie="som")
    now = time.time()
    for d in (2, 3, 4):                          # huidige 7d-venster
        st.metrics.add_sample(k["id"], 10, at=now - d * 86400)
    for d in (9, 10):                           # de direct voorafgaande periode
        st.metrics.add_sample(k["id"], 5, at=now - d * 86400)
    cockpit2.dispatch(dd, "tile_add", {"node": [C], "combo": [f"kpi:{k['id']}|value|none"],
                                       "form": ["trend"], "target": [""], "next": ["/"]}, username="guest")
    off = cockpit2.render_node(cockpit2._Stores(dd), C, "metrics", "t")
    assert "class='delta" not in off            # geen delta-badge zonder de vergelijk-toggle
    on = cockpit2.render_node(cockpit2._Stores(dd), C, "metrics", "t", compare=True)
    assert "class='delta" in on and "vs vorige periode" in on   # aggregaat huidig vs. vorig venster


# ── PR 2 — last-standen pakken vandaag mee ('stand per nu'); som/gemiddelde niet ─────────────────
def test_laatste_waarde_pakt_vandaag_mee(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    k = st.metrics.add_kpi(C, "Voorraadstand", "paar", aggregatie="laatste_waarde")
    st.metrics.add_sample(k["id"], 7, at=time.time())          # vandaag gemeten stand
    cockpit2.dispatch(dd, "tile_add", {"node": [C], "combo": [f"kpi:{k['id']}|value|none"],
                                       "form": ["getal"], "target": [""], "next": ["/"]}, username="guest")
    page = cockpit2.render_node(cockpit2._Stores(dd), C, "metrics", "t")
    assert "stand per nu" in page               # last-stand pakt vandaag WÉL mee
    assert "class='kpi-val'>7" in page          # de vandaag gemeten stand is de headline


# ── PR 2 — periode-dropdown toont de actieve optie in de summary ─────────────────────────────────
def test_dropdown_toont_actieve_periode(tmp_path):
    from nooch_village.views import metrics
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    h = metrics._metrics_tab_html(st, st.records.get(C), csrf="t", win="28d")
    assert "class='cardmenu'" in h and "28 dagen <span class='caret'>" in h   # actieve optie in de summary
    assert "class='menuitem on'" in h                                         # actieve optie gemarkeerd
