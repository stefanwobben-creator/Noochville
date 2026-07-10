"""Definitie-id (def:<id>) als kanonieke operand-vorm in formules.

Dekt: pageviews÷visitors = 30÷22 op 09-07 via def:<id>; bestaande combo-operands blijven werken
(backward compat); onresolvebare/lege operand → WARNING + zichtbare hint; en dezelfde def-resolutie
in tegel en formule geeft dezelfde metric-id.
"""
from __future__ import annotations

from nooch_village import cockpit2
from nooch_village.views.metrics import (
    _formula_daily, _render_formula_tile, _def_obs_key, _obs_key_for_indicator,
)

C = "mother_earth__nooch"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def _def_id(st, veld):
    """De id van de geseede plausible-def voor dit veld (pageviews/visitors)."""
    for d in st.defs.all():
        c = st.defs.current(d["id"]) or {}
        if c.get("source") == "plausible" and c.get("veld") == veld:
            return d["id"]
    raise AssertionError(f"geen plausible-def voor {veld}")


def _by_day(rows):
    return {r["datum"]: r for r in rows}


# ── 1. pageviews ÷ visitors = 30 ÷ 22 op 09-07 via def:<id> ──────────────────────────

def test_pageviews_deelt_visitors_via_def_operand(tmp_path):
    dd = _dd(tmp_path); st = cockpit2._Stores(dd)
    pv, vis = _def_id(st, "pageviews"), _def_id(st, "visitors")
    st.observations.record_daily("plausible", "plausible_pageviews_day", 30, bron="plausible", datum="2026-07-09")
    st.observations.record_daily("plausible", "plausible_visitors_day", 22, bron="plausible", datum="2026-07-09")
    tile = {"f_a": f"def:{pv}", "f_b": f"def:{vis}", "f_op": "÷"}
    rows, issues = _formula_daily(cockpit2._Stores(dd), tile, None, None)
    assert issues == []
    day = _by_day(rows)["2026-07-09"]
    assert day["no_data"] is False
    assert day["value"] == round(30 / 22, 4)


# ── 2. bestaande combo-vormen blijven werken (backward compat) ───────────────────────

def test_combo_operand_pulse_visitors_blijft_resolven(tmp_path):
    dd = _dd(tmp_path); st = cockpit2._Stores(dd)
    pv = _def_id(st, "pageviews")
    st.observations.record_daily("plausible", "plausible_pageviews_day", 30, bron="plausible", datum="2026-07-09")
    st.observations.record_daily("plausible", "plausible_visitors_day", 22, bron="plausible", datum="2026-07-09")
    # gemengd: def:<id> (pageviews) ÷ oude combo (pulse_visitors|visitors|time)
    tile = {"f_a": f"def:{pv}", "f_b": "pulse_visitors|visitors|time", "f_op": "÷"}
    rows, issues = _formula_daily(cockpit2._Stores(dd), tile, None, None)
    assert issues == []
    assert _by_day(rows)["2026-07-09"]["value"] == round(30 / 22, 4)


def test_kpi_combo_operand_ongewijzigd(tmp_path):
    """Een kpi:<id>|value|none-operand blijft de bestaande route volgen (geen def:-tak)."""
    dd = _dd(tmp_path); st = cockpit2._Stores(dd)
    a = st.metrics.add_kpi(C, "A", "n")["id"]
    b = st.metrics.add_kpi(C, "B", "n")["id"]
    import time
    st.metrics.add_sample(a, 100, at=time.time()); st.metrics.add_sample(b, 10, at=time.time())
    tile = {"f_a": f"kpi:{a}|value|none", "f_b": f"kpi:{b}|value|none", "f_op": "÷"}
    rows, issues = _formula_daily(cockpit2._Stores(dd), tile, None, None)
    assert issues == [] and any(not r["no_data"] and r["value"] == 10.0 for r in rows)


# ── 3. fail-loud: onresolvebare / lege operand → WARNING + hint ──────────────────────

def test_onresolvebare_operand_warning_en_hint(tmp_path, caplog):
    dd = _dd(tmp_path); st = cockpit2._Stores(dd)
    vis = _def_id(st, "visitors")
    st.observations.record_daily("plausible", "plausible_visitors_day", 22, bron="plausible", datum="2026-07-09")
    tile = {"id": "t1", "node": C, "measure": "kapot", "aggregatie": "",
            "f_a": "def:bestaat-niet", "f_b": f"def:{vis}", "f_op": "÷"}
    with caplog.at_level("WARNING"):
        rows, issues = _formula_daily(cockpit2._Stores(dd), tile, None, None)
    assert any(i["operand"] == "A" and i["code"] == "unresolved" for i in issues)
    assert any("FORMULA_OPERAND_UNRESOLVED" in r.getMessage() for r in caplog.records)
    html = _render_formula_tile(cockpit2._Stores(dd), st.records.get(C), tile, csrf="t")
    assert "bron onbekend" in html                         # zichtbare hint, niet stil leeg


def test_lege_operand_warning_en_hint(tmp_path, caplog):
    """Def resolvet wél, maar de metric-id heeft geen rijen → FORMULA_OPERAND_EMPTY + hint."""
    dd = _dd(tmp_path); st = cockpit2._Stores(dd)
    pv, vis = _def_id(st, "pageviews"), _def_id(st, "visitors")
    st.observations.record_daily("plausible", "plausible_visitors_day", 22, bron="plausible", datum="2026-07-09")
    # pageviews-def bestaat, maar er staan GEEN plausible_pageviews_day-rijen
    tile = {"id": "t2", "node": C, "measure": "pv/vis", "aggregatie": "",
            "f_a": f"def:{pv}", "f_b": f"def:{vis}", "f_op": "÷"}
    with caplog.at_level("WARNING"):
        rows, issues = _formula_daily(cockpit2._Stores(dd), tile, None, None)
    assert any(i["operand"] == "A" and i["code"] == "empty" for i in issues)
    assert any("FORMULA_OPERAND_EMPTY" in r.getMessage() for r in caplog.records)
    html = _render_formula_tile(cockpit2._Stores(dd), st.records.get(C), tile, csrf="t")
    assert "bron levert geen data" in html


# ── 4. def-resolutie identiek in tegel en formule ───────────────────────────────────

def test_def_resolutie_identiek_aan_indicator_metric_id(tmp_path):
    dd = _dd(tmp_path); st = cockpit2._Stores(dd)
    pv, vis = _def_id(st, "pageviews"), _def_id(st, "visitors")
    assert _def_obs_key(st, pv) == ("plausible_pageviews_day", "plausible")
    assert _def_obs_key(st, vis) == ("plausible_visitors_day", "plausible")
    # exact dezelfde metric-id als een indicator/tegel op dezelfde bron+veld gebruikt
    assert _def_obs_key(st, pv) == _obs_key_for_indicator("plausible", "pageviews")
    assert _def_obs_key(st, vis) == _obs_key_for_indicator("plausible", "visitors")
