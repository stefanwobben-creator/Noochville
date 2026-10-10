"""Metrics-fundament (10 oktober 2026): niveau + doel + oranje-drempel op de tegel, de set-keuze,
invoer vanuit het werkoverleg en de financiële begrippen op Nederlandse grondslag."""
from __future__ import annotations

import time

from nooch_village import cockpit2, definitions
from nooch_village.metrics import (GROEN, MAX_CRITICAL, ORANJE, ROOD, critical_te_veel,
                                   grens_fout, grens_status)
from nooch_village.views.metrics2 import render_metrics2_tab
from nooch_village.views.werkoverleg import _wo_metrics

C = "mother_earth__nooch"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def _kpi_tegel(dd, node=C, naam="Paren", richting="up", waarde=80.0):
    """Een handmatige KPI met één meting, als tegel op het dashboard van `node`."""
    st = cockpit2._Stores(dd)
    k = st.metrics.add_kpi(node, naam, "n", direction=richting)
    st.metrics.add_sample(k["id"], waarde)
    t = st.metrics.add_tile(node, f"kpi:{k['id']}", "value", "none", "getal")
    return k["id"], t["id"]


# ── de grens: puur ──────────────────────────────────────────────────────────

def test_grens_omhoog():
    assert grens_status(100, 100, 80, "up") == GROEN
    assert grens_status(90, 100, 80, "up") == ORANJE
    assert grens_status(79, 100, 80, "up") == ROOD


def test_grens_omlaag_draait_om():
    assert grens_status(2, 3, 5, "down") == GROEN
    assert grens_status(4, 3, 5, "down") == ORANJE
    assert grens_status(6, 3, 5, "down") == ROOD


def test_zonder_doel_of_richting_of_waarde_geen_status():
    assert grens_status(5, None, None, "up") == ""
    assert grens_status(5, 10, None, "") == ""          # of 5 goed is, hangt af van de richting
    assert grens_status(None, 10, 8, "up") == ""


def test_zonder_oranje_is_het_groen_of_rood():
    assert grens_status(9, 10, None, "up") == ROOD
    assert grens_status(10, 10, "", "up") == GROEN


def test_oranje_aan_de_verkeerde_kant_is_een_fout():
    assert grens_fout(100, 120, "up") and grens_fout(3, 1, "down")
    assert grens_fout(100, 80, "up") == "" and grens_fout(3, 5, "down") == ""


def test_meer_dan_drie_critical_is_te_veel():
    tiles = [{"niveau": "critical"}] * MAX_CRITICAL + [{"niveau": "smart"}]
    assert critical_te_veel(tiles) == 0
    assert critical_te_veel(tiles + [{"niveau": "critical"}]) == MAX_CRITICAL + 1


# ── op de tegel ─────────────────────────────────────────────────────────────

def _grens(dd, tid, node=C, **velden):
    form = {"node": [node], "tid": [tid], "next": ["/"],
            **{k: [str(v)] for k, v in velden.items()}}
    return cockpit2.dispatch(dd, "metrics2_grens", form, username="guest")[1]


def test_niveau_en_doel_worden_bewaard_en_getoond(tmp_path):
    dd = _dd(tmp_path)
    _mid, tid = _kpi_tegel(dd, waarde=90)
    assert "✓" in _grens(dd, tid, niveau="critical", target="100", oranje="80")
    st = cockpit2._Stores(dd)
    t = st.metrics.tiles_of(C)[0]
    assert (t["niveau"], t["target"], t["oranje"]) == ("critical", 100.0, 80.0)
    h = render_metrics2_tab(st, st.records.get(C), "t")
    assert "<span class='badge'>Critical</span>" in h
    assert "nu-status--wait'>Close to target</span> target 100 · amber from 80" in h


def test_oranje_aan_de_verkeerde_kant_wordt_geweigerd(tmp_path):
    dd = _dd(tmp_path)
    _mid, tid = _kpi_tegel(dd, richting="up")
    assert "✗" in _grens(dd, tid, niveau="", target="100", oranje="120")
    assert cockpit2._Stores(dd).metrics.tiles_of(C)[0]["target"] is None


def test_een_onbekend_niveau_wordt_geweigerd(tmp_path):
    dd = _dd(tmp_path)
    _mid, tid = _kpi_tegel(dd)
    assert "✗" in _grens(dd, tid, niveau="belangrijk")


def test_een_benchmark_tegel_krijgt_geen_status(tmp_path):
    """Bij `ref_kind=benchmark` is `target` een vergelijkwaarde, geen doel."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    k = st.metrics.add_kpi(C, "Bench", "n", direction="up")
    st.metrics.add_sample(k["id"], 1)
    st.metrics.add_tile(C, f"kpi:{k['id']}", "value", "none", "getal", target=100, ref_kind="benchmark")
    h = render_metrics2_tab(cockpit2._Stores(dd), st.records.get(C), "t", mset="all")
    assert "Off target" not in h


# ── de set-keuze ────────────────────────────────────────────────────────────

def test_standaard_critical_bovenaan_en_de_rest_uitklapbaar(tmp_path):
    dd = _dd(tmp_path)
    _m, crit = _kpi_tegel(dd, naam="Kritiek")
    _kpi_tegel(dd, naam="Overig")
    _grens(dd, crit, niveau="critical")
    st = cockpit2._Stores(dd)
    h = render_metrics2_tab(st, st.records.get(C), "t")
    assert ">Critical only</a>" in h and "class='cl-filter on'" in h
    assert "<details><summary>Other metrics (1)</summary>" in h
    kop = lambda naam: h.index(f"<span class='tile-t'>{naam}")
    assert kop("Kritiek") < h.index("Other metrics (1)") < kop("Overig")


def test_zonder_critical_staat_de_rest_open(tmp_path):
    dd = _dd(tmp_path)
    _kpi_tegel(dd)
    st = cockpit2._Stores(dd)
    h = render_metrics2_tab(st, st.records.get(C), "t")
    assert "No Critical Numbers set yet" in h and "<details open><summary>Other metrics (1)" in h


def test_all_toont_alles_zonder_klap(tmp_path):
    dd = _dd(tmp_path)
    _kpi_tegel(dd)
    st = cockpit2._Stores(dd)
    assert "Other metrics" not in render_metrics2_tab(st, st.records.get(C), "t", mset="all")


def test_waarschuwing_boven_drie_critical(tmp_path):
    dd = _dd(tmp_path)
    for i in range(MAX_CRITICAL + 1):
        _m, tid = _kpi_tegel(dd, naam=f"K{i}")
        _grens(dd, tid, niveau="critical")
    st = cockpit2._Stores(dd)
    h = render_metrics2_tab(st, st.records.get(C), "t")
    assert f"This circle has {MAX_CRITICAL + 1} Critical Numbers" in h
    # zacht: niets geblokkeerd, alle vier staan er
    assert all(f"K{i}" in h for i in range(MAX_CRITICAL + 1))


# ── invoer vanuit het werkoverleg ───────────────────────────────────────────

def test_werkoverleg_schrijft_hetzelfde_sample_met_wie_en_notitie(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    st.people.add("Stefan", "s@t.nl")
    pid = st.people.by_email("s@t.nl").id
    k = st.metrics.add_kpi(C, "Paren", "n")
    st = cockpit2._Stores(dd)
    h = _wo_metrics(st, st.records.get(C), "t")
    # dezelfde schrijfroute (m_sample), en na opslaan terug in het overleg
    rij = h[h.index("name='mid' value='" + k["id"]):]
    assert "value='m_sample'" in rij
    assert "name='next' value='/werkoverleg?circle=mother_earth__nooch&amp;step=metrics'" in h
    cockpit2.dispatch(dd, "m_sample", {"mid": [k["id"]], "value": ["12"], "notitie": ["  na de beurs "],
                                       "datum": ["2026-10-01"], "next": ["/"]}, username="guest")
    s = cockpit2._Stores(dd).metrics.get(k["id"])["samples"][-1]
    assert s["value"] == 12.0 and s["notitie"] == "na de beurs"
    assert time.strftime("%Y-%m-%d", time.localtime(s["at"])) == "2026-10-01"
    assert "door" not in s                                 # guest = niemand bekend
    # Ingelogd als Circle Lead (mag namens de kring noteren): het sample draagt wie het invoerde.
    cockpit2._Stores(dd).assign.assign(f"{C}__circle_lead", "person", pid)
    _n, msg = cockpit2.dispatch(dd, "m_sample", {"mid": [k["id"]], "value": ["13"], "next": ["/"]},
                                username="s@t.nl")
    assert "✓" in msg, msg
    assert cockpit2._Stores(dd).metrics.get(k["id"])["samples"][-1]["door"] == pid


def test_een_datum_in_de_toekomst_wordt_geweigerd(tmp_path):
    dd = _dd(tmp_path)
    k = cockpit2._Stores(dd).metrics.add_kpi(C, "Paren", "n")
    _nxt, msg = cockpit2.dispatch(dd, "m_sample", {"mid": [k["id"]], "value": ["1"],
                                                   "datum": ["2999-01-01"], "next": ["/"]},
                                  username="guest")
    assert "⛔" in msg and not cockpit2._Stores(dd).metrics.get(k["id"]).get("samples")


# ── financiële begrippen ────────────────────────────────────────────────────

def test_een_oude_nederlandse_naam_wordt_een_clarify_versie_zonder_dubbel(tmp_path):
    from nooch_village.definitions import DefinitionStore, hernoem_seed, seed_catalog
    st = DefinitionStore(str(tmp_path / "d.json"))
    oud = st.add("Brutomarge", owner="librarian", provenance="seed", source="finance", unit="%",
                 direction="up", cadence="maand", meettype="venster", window="30d",
                 definition="Brutowinst gedeeld door omzet.")
    assert hernoem_seed(st) >= 1
    cur = st.current(oud["id"])
    assert cur["name"] == "Gross margin" and cur["migration"] == "clarify" and cur["version"] == 2
    assert "Dutch GAAP (RJ)" in cur["definition"] and cur["standaard"] == "Dutch GAAP (RJ)"
    seed_catalog(st)
    assert sum(1 for d in st.all() if (st.current(d["id"]) or {}).get("name") == "Gross margin") == 1
    assert hernoem_seed(st) == 0                                           # idempotent


def test_financiele_definities_dragen_rj_als_grondslag():
    fin = [e for e in definitions._DEFINITION_SEED if e.get("source") == "finance"]
    namen = {e["name"] for e in fin}
    assert {"Revenue", "Gross margin", "Cash and cash equivalents", "Working capital"} <= namen
    for e in fin:
        if e["name"] in ("Revenue", "Gross margin", "Cash and cash equivalents", "Working capital"):
            assert e["definition"].count("Dutch GAAP (RJ)") == 1, e["name"]
    assert not any("GAAP" in str(v.get("standaard", "")) and "RJ" not in str(v.get("standaard", ""))
                   for v in definitions._GROUNDING.values())
