"""Finance PR 1b (10 oktober 2026): handmatige omzet en subsidie — alleen toevoegen, terugwerkende
kracht, rechten met echte sessies, geen lekken, het P&L op een bekende set, de bronregel, borging,
en de Finance-kaart onder Tools."""
from __future__ import annotations

import http.client
import threading
from http.server import HTTPServer

from nooch_village import auth as _auth
from nooch_village import cockpit2, finance_config as fc, finance_pnl, zicht
from nooch_village.finance_omzet import (OpbrengstRegister, maak_opbrengst, net_sales_per_maand,
                                         paren_per_maand, posten as opbrengst_posten)
from nooch_village.finance_register import KostenRegister, posten
from nooch_village.views import finance as fin
from nooch_village.views import overview
from nooch_village.views.tools import render_tools

from tests.test_finance_pr1 import FC, PDF, _boek, _dorp, _st

MERK = "OKAPI-OMZET-4410"                       # een opbrengstregel die nergens anders mag opduiken


def _velden(**kw):
    v = {"action": "finance_omzet_add", "entry_date": "2026-10-05", "period": "2026-10",
         "revenue_line": "net_sales", "description": "Batch 4 deliveries", "amount_excl": "1000,00",
         "vat": "210", "batch": "Batch 4", "pairs": "10"}
    v.update(kw)
    return v


def _omzet(dd, blob=None, wie="fc@t.nl", **kw):
    return fin.verwerk_omzet(_st(dd), _velden(**kw), {"file": ("beschikking.pdf", blob)} if blob else {},
                             username=wie, door=wie)


def _rij(uit, key):
    return next(r for r in uit["rijen"] if r["key"] == key)


# ── alleen toevoegen ────────────────────────────────────────────────────────

def test_het_opbrengstregister_heeft_alleen_toevoegen():
    publiek = {n for n in dir(OpbrengstRegister) if not n.startswith("_")}
    assert not {n for n in publiek if any(w in n.lower() for w in ("update", "delete", "remove", "wijzig",
                                                                    "weg", "zet", "set", "edit"))}


def test_correctie_draait_bedrag_en_paren_om(tmp_path):
    dd = _dorp(tmp_path)
    assert "✓" in _omzet(dd)
    oud = OpbrengstRegister(dd).alle()[0]
    msg = fin.verwerk_omzet(_st(dd), _velden(action="finance_omzet_correct", kid=oud["id"],
                                             amount_excl="800", pairs="8"), {}, username="fc@t.nl", door="fc")
    assert "✓ corrected" in msg
    regels = OpbrengstRegister(dd).alle()
    assert len(regels) == 3
    storno = [r for r in regels if r.get("corrects") == oud["id"]][0]
    assert storno["amount_excl_cents"] == -100000 and storno["pairs"] == -10
    assert sum(r["amount_excl_cents"] for r in regels) == 80000
    assert paren_per_maand(regels) == {"2026-10": 8}


def test_terugwerkende_kracht_raakt_alleen_die_maand(tmp_path):
    dd = _dorp(tmp_path)
    _omzet(dd, period="2026-09", amount_excl="500")
    voor = finance_pnl.bereken([], fc.laad(), opbrengsten=opbrengst_posten(OpbrengstRegister(dd).alle()))
    _omzet(dd, entry_date="2026-10-09", period="2026-03", amount_excl="200")    # achteraf ingevoerd
    na = finance_pnl.bereken([], fc.laad(), opbrengsten=opbrengst_posten(OpbrengstRegister(dd).alle()))
    assert _rij(voor, "net_sales")["waarden"] == {"2026-09": 50000}
    assert _rij(na, "net_sales")["waarden"] == {"2026-03": 20000, "2026-09": 50000}


# ── validatie ───────────────────────────────────────────────────────────────

def test_negatief_en_paren_alleen_op_net_sales():
    cfg = fc.laad()
    basis = {"entry_date": "2026-10-01", "period": "2026-10", "description": "x"}
    assert maak_opbrengst({**basis, "revenue_line": "net_sales", "amount_excl": "-10"}, cfg)[0] is None
    assert maak_opbrengst({**basis, "revenue_line": "net_sales", "amount_excl": "-10", "note": "return"},
                          cfg)[0] is not None
    assert maak_opbrengst({**basis, "revenue_line": "other_income_grants", "amount_excl": "-10",
                           "note": "x"}, cfg)[0] is None
    assert maak_opbrengst({**basis, "revenue_line": "other_income_grants", "amount_excl": "10",
                           "pairs": "3"}, cfg)[0] is None


def test_toekomstige_periode_waarschuwt_maar_slaat_op(tmp_path):
    dd = _dorp(tmp_path)
    msg = _omzet(dd, period="2099-01")
    assert "✓" in msg and "future" in msg and len(OpbrengstRegister(dd).alle()) == 1


# ── borging van bijlagen ────────────────────────────────────────────────────

def test_bijlage_hash_type_en_dubbel_over_beide_registers(tmp_path):
    dd = _dorp(tmp_path)
    assert "✗" in _omzet(dd, blob=b"geen pdf", revenue_line="other_income_grants", pairs="")
    _boek(dd)                                                        # dezelfde PDF als kostfactuur
    msg = _omzet(dd, blob=PDF, revenue_line="other_income_grants", pairs="")
    assert "already in the register" in msg and OpbrengstRegister(dd).alle() == []
    assert "✓" in fin.verwerk_omzet(_st(dd), _velden(revenue_line="other_income_grants", pairs="",
                                                     bevestig_dubbel="1"),
                                    {"file": ("b.pdf", PDF)}, username="fc@t.nl", door="fc")
    reg = OpbrengstRegister(dd)
    r = reg.alle()[0]
    assert reg.lees_bijlage(r)[0] == PDF and len(r["attachment"]["sha256"]) == 64


# ── rechten met echte sessies, geen lekken ──────────────────────────────────

def test_echte_sessies_404_en_invoer_alleen_wie_mag_wijzigen(tmp_path):
    dd = _dorp(tmp_path)
    _omzet(dd, blob=PDF, description=MERK, revenue_line="other_income_grants", pairs="")
    rid = OpbrengstRegister(dd).alle()[0]["id"]
    sessies = _auth.SessionStore()
    httpd = HTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, "T", sessions=sessies))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    poort = httpd.server_address[1]

    def get(pad, wie):
        conn = http.client.HTTPConnection("127.0.0.1", poort, timeout=10)
        conn.request("GET", pad, headers={"Cookie": f"nv_session={sessies.create(wie)}"})
        r = conn.getresponse()
        body = r.read()
        conn.close()
        return r.status, body

    routes = ("/finance/revenue", f"/finance/revenue/view?id={rid}", "/finance/revenue.csv",
              f"/finance/file?reg=revenue&id={rid}", "/finance/pnl", "/finance/costs")
    try:
        for pad in routes:
            status, body = get(pad, "lid@t.nl")
            assert status == 404 and MERK.encode() not in body and PDF not in body, pad
        for wie in ("fc@t.nl", "bs@t.nl", "stefan@nooch.earth"):
            status, body = get("/finance/revenue", wie)
            assert status == 200 and MERK.encode() in body, wie
        assert get(f"/finance/file?reg=revenue&id={rid}", "bs@t.nl") == (200, PDF)
        assert MERK.encode() in get("/finance/revenue.csv", "fc@t.nl")[1]
        assert b"/finance/revenue" in get("/finance/costs", "fc@t.nl")[1]          # tab-link
        assert b"/finance/revenue" in get("/finance/pnl", "fc@t.nl")[1]
    finally:
        httpd.shutdown()
    st = _st(dd)
    assert "finance_omzet_add" in fin.render_revenue(st, "fc@t.nl", "t", {})
    assert "finance_omzet_add" not in fin.render_revenue(st, "bs@t.nl", "t", {})


def test_een_opbrengstregel_duikt_nergens_anders_op(tmp_path):
    dd = _dorp(tmp_path)
    _omzet(dd, description=MERK)
    st = _st(dd)
    from nooch_village import noochie_memo
    from nooch_village.views.search import render_search_fragment
    assert MERK not in render_search_fragment(st, MERK)
    beeld, rapport = noochie_memo.verzamel(dd)
    assert MERK not in str(beeld) + str(rapport)


# ── het P&L op een bekende set ──────────────────────────────────────────────

def _bekend():
    kosten = [("2026-10", "purchased_goods", 30000, "register"), ("2026-10", "other_housing_it", 10000, "register")]
    opbr = [("2026-10", "net_sales", 100000, "manual"), ("2026-10", "other_income_grants", 5000, "manual")]
    return finance_pnl.bereken(kosten, fc.laad(), opbrengsten=opbr, paren={"2026-10": 10})


def test_pnl_marges_percentages_en_subsidie_onder_cm3():
    uit = _bekend()
    assert _rij(uit, "net_sales")["waarden"]["2026-10"] == 100000
    assert _rij(uit, "cm1")["waarden"]["2026-10"] == 70000
    assert abs(_rij(uit, "cm1")["pct"]["2026-10"] - 0.70) < 1e-9
    assert _rij(uit, "cm3")["waarden"]["2026-10"] == 70000                  # subsidie NIET in CM3
    assert _rij(uit, "ebitda")["waarden"]["2026-10"] == 70000 + 5000 - 10000
    keys = [r["key"] for r in uit["rijen"]]
    assert keys.index("cm3") < keys.index("other_income_grants") < keys.index("ebitda")
    assert uit["bron"] == {"2026-10": "manual"} and uit["paren"] == {"2026-10": 10}


def test_from_layer_is_een_instelling():
    cfg = fc.laad()
    for r in cfg["revenue_lines"]:
        if r["key"] == "other_income_grants":
            r["from_layer"] = "ebit"
    uit = finance_pnl.bereken([("2026-10", "other_housing_it", 10000, "register")], cfg,
                              opbrengsten=[("2026-10", "net_sales", 100000, "manual"),
                                           ("2026-10", "other_income_grants", 5000, "manual")])
    assert _rij(uit, "ebitda")["waarden"]["2026-10"] == 90000
    assert _rij(uit, "ebit")["waarden"]["2026-10"] == 95000


def test_bronregel_een_maand_nooit_uit_twee_bronnen():
    opbr = [("2026-09", "net_sales", 100, "manual"), ("2026-09", "net_sales", 999, "shopify"),
            ("2026-11", "net_sales", 200, "manual"), ("2026-11", "net_sales", 300, "shopify")]
    assert net_sales_per_maand(opbr, "") == ({"2026-09": 100, "2026-11": 200},
                                             {"2026-09": "manual", "2026-11": "manual"})
    assert net_sales_per_maand(opbr, "2026-10") == ({"2026-09": 100, "2026-11": 300},
                                                    {"2026-09": "manual", "2026-11": "shopify"})


def test_pnl_pagina_per_paar_en_streepje_zonder_paren(tmp_path):
    dd = _dorp(tmp_path)
    _omzet(dd, period="2026-09", amount_excl="1000", pairs="10")
    _omzet(dd, period="2026-10", amount_excl="500", pairs="")
    st = _st(dd)
    h = fin.render_pnl(st, "fc@t.nl")
    assert "Source of net sales" in h and "<td class='num muted'>manual</td>" in h and "€1,000.00" in h
    pp = fin.render_pnl(st, "fc@t.nl", per="paar")
    i = pp.index("<strong>Net sales</strong>")
    rij = pp[i:pp.index("</tr>", i)]
    # september 1000/10 per paar; oktober zonder paren en het totaal: een streepje, geen getal
    assert rij.count("€100.00") == 1 and rij.count("—") == 2 and "€150.00" not in rij
    assert posten(KostenRegister(dd).alle()) == []


# ── de Finance-kaart onder Tools ────────────────────────────────────────────

def test_domein_naam_gelijk_aan_zicht():
    assert [d.lower() for d in zicht.groepen()["finance"]["domeinen"]] == ["financial administration"]
    assert "financial administration" in overview._DOMAIN_TOOLS


def test_finance_kaart_alleen_voor_de_finance_groep(tmp_path):
    dd = _dorp(tmp_path)
    st = _st(dd)
    rec = st.records.get(FC)
    rec.definition.domains = list(rec.definition.domains or []) + ["Financial administration"]
    assert "/finance/costs" in overview._role_tools_html(rec, st, "fc@t.nl")
    assert "/finance/costs" not in overview._role_tools_html(rec, st, "lid@t.nl")
    assert "/finance/costs" not in overview._role_tools_html(rec)            # fail-closed
    st.records.all = lambda _orig=st.records.all: [rec if r.id == FC else r for r in _orig()]
    assert "/finance/costs" in render_tools(st, username="bs@t.nl")
    assert "/finance/costs" not in render_tools(st, username="lid@t.nl")
