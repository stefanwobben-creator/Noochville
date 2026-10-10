"""CN1 "Batch 4 sold" (10 oktober 2026): telling op besteldatum, drie toestanden, startdatum in de UI."""
from __future__ import annotations

import time

import pytest

from nooch_village import batch_cn, cockpit2, critical_numbers
from nooch_village.metrics import maak_lijn
from nooch_village.views.metrics2 import render_metrics2_tab

C = "mother_earth__nooch"
SALES = "mother_earth__nooch__sales"


def _tile(van="2026-11-15", tot="2026-12-31", doel=500):
    return {"target": doel, "lijn": maak_lijn(van, tot)}


def _reeks(*dagen):
    return [{"datum": d, "value": v} for d, v in dagen]


# ── de stand: puur ──────────────────────────────────────────────────────────

def test_voor_de_startdatum_niet_gestart_en_geen_getal():
    s = batch_cn.stand(_reeks(("2026-11-01", 20)), _tile(), vandaag="2026-11-10")
    assert s == {"toestand": "not started", "paren": None, "sluitdatum": ""}


def test_open_telt_vanaf_de_startdatum_op_besteldatum():
    s = batch_cn.stand(_reeks(("2026-11-14", 99), ("2026-11-15", 30), ("2026-11-20", 12)),
                       _tile(), vandaag="2026-11-21")
    assert s == {"toestand": "open", "paren": 42.0, "sluitdatum": ""}  # 11-14 telt niet mee


def test_gesloten_bij_500_en_de_eindstand_blijft_staan():
    s = batch_cn.stand(_reeks(("2026-11-15", 300), ("2026-11-20", 250), ("2026-11-25", 80)),
                       _tile(), vandaag="2026-12-01")
    assert s == {"toestand": "closed", "paren": 550.0, "sluitdatum": "2026-11-20"}


def test_gesloten_na_de_deadline_zonder_het_doel():
    s = batch_cn.stand(_reeks(("2026-11-15", 120)), _tile(), vandaag="2027-01-05")
    assert s == {"toestand": "closed", "paren": 120.0, "sluitdatum": "2026-12-31"}


def test_open_zonder_shopify_data_is_geen_nul():
    s = batch_cn.stand([], _tile(), vandaag="2026-11-20")
    assert s["toestand"] == "open" and s["paren"] is None


# ── op de tegel ─────────────────────────────────────────────────────────────

def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    for naam, mail, rol in (("Sanne", "sales@t.nl", SALES),
                            ("Lid", "lid@t.nl", "mother_earth__nooch__marketing_lead")):
        st.people.add(naam, mail)
        st.assign.assign(rol, "person", st.people.by_email(mail).id)
    critical_numbers.zaai(st.metrics, critical_numbers.laad(), apply=True)
    return dd


def _cn1(st):
    return next(t for t in st.metrics.tiles_of(C) if t.get("cn") == "cn1_batch4")


def _h(dd):
    st = cockpit2._Stores(dd)
    h = render_metrics2_tab(st, st.records.get(C), "t", mset="all")
    return h[h.index("cn1_batch4") if "cn1_batch4" in h else 0:]


def _verzet(dd, van, tot="2026-12-31"):
    st = cockpit2._Stores(dd)
    st.metrics.set_tile_extra(C, _cn1(st)["id"], lijn=maak_lijn(van, tot))


def _verkoop(dd, *dagen):
    obs = cockpit2._Stores(dd).observations
    for d, v in dagen:
        obs.record_daily("shopify", "shopify_pairs_sold_day", v, bron="shopify", datum=d)


def test_het_zaad_heeft_cn1_als_critical_met_500_en_startdatum():
    cfg = critical_numbers.laad()
    n = next(x for x in cfg["nummers"] if x["sleutel"] == "cn1_batch4")
    assert (n["niveau"], n["target"], n["lijn"]["van"], n["lijn"]["tot"]) == \
           ("critical", 500, "2026-11-15", "2026-12-31")
    assert sum(1 for x in cfg["nummers"] if x.get("niveau") == "critical") <= 3


def test_not_started_toont_geen_status(tmp_path):
    dd = _dd(tmp_path)
    vandaag = time.strftime("%Y-%m-%d")
    _verzet(dd, "2099-01-01", "2099-12-31")
    st = cockpit2._Stores(dd)
    h = render_metrics2_tab(st, st.records.get(C), "t", mset="all")
    blok = h[h.index("Not started"):][:400]
    assert "the batch opens 2099-01-01" in blok and "nu-status" not in blok
    assert vandaag < "2099-01-01"


def test_open_met_lijn_en_status(tmp_path):
    dd = _dd(tmp_path)
    van = time.strftime("%Y-%m-%d", time.localtime(time.time() - 10 * 86400))
    tot = time.strftime("%Y-%m-%d", time.localtime(time.time() + 30 * 86400))
    _verzet(dd, van, tot)
    _verkoop(dd, (van, 200))                                    # ver boven de lijn na 10 van 40 dagen
    st = cockpit2._Stores(dd)
    h = render_metrics2_tab(st, st.records.get(C), "t", mset="all")
    assert f"Open since {van}" in h and "On target</span> line today" in h


def test_gesloten_toont_de_eindstand_zonder_rood(tmp_path):
    dd = _dd(tmp_path)
    _verzet(dd, "2026-01-01", "2026-02-01")
    _verkoop(dd, ("2026-01-10", 90))
    st = cockpit2._Stores(dd)
    h = render_metrics2_tab(st, st.records.get(C), "t", mset="all")
    blok = h[h.index("Closed 2026-02-01"):][:300]
    assert "final count 90 of 500" in blok and "Off target" not in blok


# ── de startdatum in de UI ──────────────────────────────────────────────────

def test_sales_verzet_de_startdatum_en_het_zaad_houdt_hem_vast(tmp_path):
    dd = _dd(tmp_path)
    tid = _cn1(cockpit2._Stores(dd))["id"]
    form = {"node": [C], "tid": [tid], "datum": ["2026-11-20"], "next": ["/"]}
    with pytest.raises(cockpit2.Forbidden):
        cockpit2.dispatch(dd, "cn_startdatum_zet", form, username="lid@t.nl")
    assert "✓" in cockpit2.dispatch(dd, "cn_startdatum_zet", form, username="sales@t.nl")[1]
    assert _cn1(cockpit2._Stores(dd))["lijn"]["van"] == "2026-11-20"
    te_laat = dict(form, datum=["2027-01-10"])
    assert "✗" in cockpit2.dispatch(dd, "cn_startdatum_zet", te_laat, username="sales@t.nl")[1]
    st = cockpit2._Stores(dd)
    critical_numbers.zaai(st.metrics, critical_numbers.laad(), apply=True)
    assert _cn1(cockpit2._Stores(dd))["lijn"]["van"] == "2026-11-20"          # niet teruggezet
