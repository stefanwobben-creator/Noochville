"""CN2 Runway (10 oktober 2026): vaste kosten, cash, het quotiënt, en wie het mag zien en wijzigen."""
from __future__ import annotations

import pytest

from nooch_village import cockpit2, critical_numbers, zicht
from nooch_village.vaste_kosten import maak_regel
from nooch_village.views.metrics import _sources_for, runway
from nooch_village.views.metrics2 import render_metrics2_tab
from nooch_village.views.vaste_kosten import render_vaste_kosten
from nooch_village.views.werkoverleg import _wo_metrics

C = "mother_earth__nooch"
FC = "mother_earth__nooch__financial_controller"
BS = "mother_earth__nooch__strategic_lead_founder_steward"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    for naam, mail, rol in (("Fien", "fc@t.nl", FC), ("Bas", "bs@t.nl", BS),
                            ("Anker", "anker@t.nl", "mother_earth__circle_lead"),
                            ("Lid", "lid@t.nl", "mother_earth__nooch__marketing_lead")):
        st.people.add(naam, mail)
        st.assign.assign(rol, "person", st.people.by_email(mail).id)
    critical_numbers.zaai(st.metrics, critical_numbers.laad(), apply=True)
    return dd


def _st(dd):
    return cockpit2._Stores(dd)


# ── vaste kosten ────────────────────────────────────────────────────────────

def test_een_regel_wordt_gevalideerd():
    assert maak_regel("Huur", "1200,50", van="2026-01-01")[0]["bedrag"] == 1200.5
    assert maak_regel("", "10", van="2026-01-01")[0] is None
    assert maak_regel("Huur", "veel", van="2026-01-01")[0] is None
    assert maak_regel("Huur", "10", van="")[0] is None
    assert maak_regel("Huur", "10", van="2026-05-01", tot="2026-04-01")[0] is None


def test_het_totaal_telt_alleen_wat_op_de_peildatum_loopt(tmp_path):
    st = _st(_dorp(tmp_path))
    for oms, b, van, tot in (("Huur", 1000, "2026-01-01", ""), ("Oude lease", 300, "2025-01-01", "2026-06-30"),
                             ("Nieuw abonnement", 50, "2026-11-01", "")):
        st.vaste_kosten.zet(maak_regel(oms, b, van=van, tot=tot)[0])
    assert st.vaste_kosten.totaal_op("2026-10-10") == 1000
    assert st.vaste_kosten.totaal_op("2026-06-30") == 1300                # einddatum telt nog mee
    assert st.vaste_kosten.totaal_op("2026-11-01") == 1050


# ── runway ──────────────────────────────────────────────────────────────────

def test_runway_is_cash_gedeeld_door_vaste_kosten_en_nooit_door_nul(tmp_path):
    dd = _dorp(tmp_path)
    st = _st(dd)
    assert runway(st)["maanden"] is None                                  # geen cash, geen kosten
    cash = st.metrics.by_cn("cn2_cash")
    st.metrics.add_sample(cash["id"], 24000)
    assert runway(_st(dd))["maanden"] is None                             # kosten 0 → geen runway
    st = _st(dd)
    st.vaste_kosten.zet(maak_regel("Huur", 3000, van="2026-01-01")[0])
    assert runway(_st(dd)) == {"cash": 24000.0, "vaste_kosten": 3000.0, "maanden": 8.0}


@pytest.mark.parametrize("cash,woord", [(39000, "On target"), (24000, "Close to target"),
                                        (15000, "Off target")])
def test_de_grens_6_en_12_maanden(tmp_path, cash, woord):
    dd = _dorp(tmp_path)
    st = _st(dd)
    st.vaste_kosten.zet(maak_regel("Huur", 3000, van="2026-01-01")[0])
    st.metrics.add_sample(st.metrics.by_cn("cn2_cash")["id"], cash)
    st = _st(dd)
    h = render_metrics2_tab(st, st.records.get(C), "t", mset="critical")
    deel = h[h.index("Runway (months)"):] if "Runway (months)" in h else h
    assert f">{woord}</span> target 12 · amber from 6" in deel


# ── zicht ───────────────────────────────────────────────────────────────────

def test_wie_mag_zien_en_wijzigen(tmp_path):
    st = _st(_dorp(tmp_path))
    rechten = {u: (zicht.mag(st, u, "finance"), zicht.mag(st, u, "finance", "wijzigen"))
               for u in ("fc@t.nl", "bs@t.nl", "anker@t.nl", "lid@t.nl", "onbekend@t.nl", None, "guest")}
    assert rechten == {"fc@t.nl": (True, True), "bs@t.nl": (True, False), "anker@t.nl": (True, True),
                       "lid@t.nl": (False, False), "onbekend@t.nl": (False, False),
                       None: (False, False), "guest": (True, True)}
    assert not zicht.mag(st, "fc@t.nl", "bestaat_niet")                   # onbekende groep: dicht


def test_een_lid_ziet_runway_en_cash_nergens(tmp_path):
    dd = _dorp(tmp_path)
    lid, fc = zicht.voor(_st(dd), "lid@t.nl"), zicht.voor(_st(dd), "fc@t.nl")
    rec = lid.records.get(C)
    h_lid = render_metrics2_tab(lid, rec, "t", mset="all")
    h_fc = render_metrics2_tab(fc, rec, "t", mset="all")
    for woord in ("Runway (months)", "Cash and cash equivalents", "Fixed costs per month"):
        assert woord not in h_lid, woord
        assert woord in h_fc, woord
    assert "Substantiated pages" in h_lid                                 # de rest blijft open
    assert not any(s["id"] == "runway" for s in _sources_for(lid, rec))
    cash = lid.metrics._m.by_cn("cn2_cash")["id"]
    assert lid.metrics.get(cash) is None and fc.metrics.get(cash) is not None


def test_in_het_werkoverleg_alleen_voor_wie_mag(tmp_path):
    dd = _dorp(tmp_path)
    for wie, ziet in (("lid@t.nl", False), ("bs@t.nl", True), ("fc@t.nl", True)):
        st = zicht.voor(_st(dd), wie)
        assert ("Cash and cash equivalents" in _wo_metrics(st, st.records.get(C), "t")) is ziet, wie


def test_cash_invoeren_alleen_fc_en_anker(tmp_path):
    dd = _dorp(tmp_path)
    mid = _st(dd).metrics.by_cn("cn2_cash")["id"]
    for wie, mag in (("lid@t.nl", False), ("bs@t.nl", False), ("fc@t.nl", True), ("anker@t.nl", True)):
        _n, msg = cockpit2.dispatch(dd, "m_sample", {"mid": [mid], "value": ["1000"], "next": ["/"]},
                                    username=wie)
        assert ("✓" in msg) is mag, (wie, msg)
    s = _st(dd).metrics.get(mid)["samples"]
    assert len(s) == 2 and s[0]["door"] == _st(dd).people.by_email("fc@t.nl").id


def test_vaste_kosten_wijzigen_alleen_fc_en_anker(tmp_path):
    dd = _dorp(tmp_path)
    form = {"omschrijving": ["Huur"], "bedrag": ["1000"], "van": ["2026-01-01"], "next": ["/fixed-costs"]}
    for wie in ("lid@t.nl", "bs@t.nl"):
        with pytest.raises(cockpit2.Forbidden):
            cockpit2.dispatch(dd, "vaste_kosten_zet", form, username=wie)
    assert "✓" in cockpit2.dispatch(dd, "vaste_kosten_zet", form, username="fc@t.nl")[1]
    assert _st(dd).vaste_kosten.totaal_op("2026-10-10") == 1000


def test_de_pagina_vaste_kosten_per_rol(tmp_path):
    dd = _dorp(tmp_path)
    _st(dd).vaste_kosten.zet(maak_regel("Huur", 1234, van="2026-01-01")[0])
    lid = render_vaste_kosten(_st(dd), "lid@t.nl", "t")
    assert "1,234" not in lid and "Only the Financial Controller" in lid
    bs = render_vaste_kosten(_st(dd), "bs@t.nl", "t")
    assert "€1,234.00" in bs and "vaste_kosten_zet" not in bs
    assert "vaste_kosten_zet" in render_vaste_kosten(_st(dd), "fc@t.nl", "t")


def test_het_zaad_maakt_cash_runway_en_vaste_kosten(tmp_path):
    st = _st(_dorp(tmp_path))
    tiles = {t["cn"]: t for t in st.metrics.tiles_of(C) if t.get("cn")}
    r = tiles["cn2_runway"]
    assert (r["niveau"], r["target"], r["oranje"], r["zicht"]) == ("critical", 12.0, 6.0, "finance")
    cash = st.metrics.by_cn("cn2_cash")
    assert cash["zicht"] == "finance" and tiles["cn2_cash"]["source"] == f"kpi:{cash['id']}"
    assert tiles["cn2_fixed_costs"]["zicht"] == "finance"
    assert sum(1 for t in tiles.values() if t.get("niveau") == "critical") <= 3


# ── de routes gebruiken de kijker-versie ────────────────────────────────────

def test_de_routes_schermen_af_voor_een_lid(tmp_path):
    """De echte handler: een ingelogd lid ziet de runway op geen enkele metrics-route, de FC wel."""
    import http.client
    import threading
    from http.server import HTTPServer
    from nooch_village import auth as _auth

    dd = _dorp(tmp_path)
    mid = _st(dd).metrics.by_cn("cn2_cash")["id"]
    _st(dd).metrics.add_sample(mid, 4321)
    sessies = _auth.SessionStore()
    httpd = HTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, "T", sessions=sessies))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    poort = httpd.server_address[1]

    def get(pad, wie):
        conn = http.client.HTTPConnection("127.0.0.1", poort, timeout=10)
        conn.request("GET", pad, headers={"Cookie": f"nv_session={sessies.create(wie)}"})
        r = conn.getresponse()
        body = r.read().decode("utf-8", "replace")
        conn.close()
        return body

    try:
        for pad in (f"/node?id={C}&tab=metrics&mset=all", f"/metrics2?node={C}&mset=all",
                    f"/werkoverleg?circle={C}&step=metrics"):
            assert "Runway (months)" not in get(pad, "lid@t.nl"), pad
        assert "Runway (months)" in get(f"/node?id={C}&tab=metrics&mset=all", "fc@t.nl")
        assert "4321" not in get(f"/metric_export?mid={mid}", "lid@t.nl")
        assert "4321" in get(f"/metric_export?mid={mid}", "fc@t.nl")
    finally:
        httpd.shutdown()
