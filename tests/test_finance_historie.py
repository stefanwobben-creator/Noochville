"""Finance PR 2a (10 oktober 2026): historie per maand — alleen toevoegen met `supersedes`, één bron
per maand (cutover), "no data" in plaats van nul, import/export (CSV en XLSX) met preview, rechten
met echte sessies, geen lekken, de lagen onder het raster."""
from __future__ import annotations

import http.client
import os
import threading
import urllib.parse
from http.server import HTTPServer

import pytest

from nooch_village import auth as _auth
from nooch_village import cockpit2, finance_config as fc, finance_pnl
from nooch_village import finance_historie as fh
from nooch_village.views import finance as fin
from nooch_village.views import overview
from nooch_village.views.tools import render_tools

from tests.test_finance_omzet import _omzet
from tests.test_finance_pr1 import FC, _boek, _dorp, _st

MERK_CENT = 7_781_234                            # €77,812.34 — een bedrag dat nergens anders mag opduiken
MERK_TXT = "77812.34"


def _opslaan(dd, cellen: dict, wie="fc@t.nl", note=""):
    form = {f"c|{k}|{m}": [v] for (m, k), v in cellen.items()}
    form["note"] = [note]
    return fin.verwerk_history_opslaan(_st(dd), form, door=wie)


def _rij(uit, key):
    return next(r for r in uit["rijen"] if r["key"] == key)


# ── alleen toevoegen ────────────────────────────────────────────────────────

def test_historie_heeft_alleen_toevoegen():
    for klasse in (fh.HistorieRegister, fh.ImportLog, fh.Instellingen):
        publiek = {n for n in dir(klasse) if not n.startswith("_")}
        assert not {n for n in publiek if any(w in n.lower() for w in ("update", "delete", "remove", "wijzig",
                                                                       "weg", "edit"))}, klasse


def test_wijziging_is_nieuwe_regel_met_supersedes(tmp_path):
    dd = _dorp(tmp_path)
    assert "✓ 1 new" in _opslaan(dd, {("2025-03", "brand"): "100,00"})
    assert "✓ 0 new, 1 changed" in _opslaan(dd, {("2025-03", "brand"): "150,50"}, note="Venema")
    reg = fh.HistorieRegister(dd)
    regels = reg.alle()
    assert len(regels) == 2
    oud, nieuw = sorted(regels, key=lambda r: r["created_at"])
    assert nieuw["supersedes"] == oud["id"] and oud["amount_cents"] == 10000
    assert reg.actueel()[("2025-03", "brand")]["amount_cents"] == 15050
    assert [r["amount_cents"] for r in reg.geschiedenis("2025-03", "brand")] == [15050, 10000]
    # ongewijzigd opslaan schrijft niets
    assert "✓ 0 new, 0 changed" in _opslaan(dd, {("2025-03", "brand"): "150.50"})
    assert len(reg.alle()) == 2


def test_leegmaken_opnieuw_invullen_en_de_hele_keten(tmp_path):
    """Besluit Stefan: leegmaken = een regel met `cleared` zonder bedrag die de vorige vervangt."""
    dd = _dorp(tmp_path)
    _opslaan(dd, {("2025-03", "brand"): "100"})
    assert "1 cleared" in _opslaan(dd, {("2025-03", "brand"): "", ("2025-04", "brand"): ""})
    reg = fh.HistorieRegister(dd)
    assert ("2025-03", "brand") not in reg.actueel()                      # actueel: no data
    leeg = reg.laatste()[("2025-03", "brand")]
    assert leeg["cleared"] is True and leeg["amount_cents"] is None
    assert len(reg.alle()) == 2                                           # 2025-04 was al leeg: niets
    assert "0 new, 0 changed, 0 cleared" in _opslaan(dd, {("2025-03", "brand"): ""})
    assert "1 new" in _opslaan(dd, {("2025-03", "brand"): "80"})          # opnieuw invullen
    keten = reg.geschiedenis("2025-03", "brand")
    assert [r.get("cleared", False) for r in keten] == [False, True, False]
    assert keten[0]["supersedes"] == keten[1]["id"] and keten[1]["supersedes"] == keten[2]["id"]
    assert reg.actueel()[("2025-03", "brand")]["amount_cents"] == 8000
    h = fin.render_history_cel(_st(dd), "fc@t.nl", "2025-03", "brand")
    assert h.count("no data (cleared)") == 1 and "€80.00" in h and "€100.00" in h


def test_leeggemaakte_paren_en_net_sales(tmp_path):
    dd = _dorp(tmp_path)
    _opslaan(dd, {("2025-03", "net_sales"): "1000", ("2025-03", fh.PAREN): "10"})
    assert "1 changed" in _opslaan(dd, {("2025-03", "net_sales"): "1000", ("2025-03", fh.PAREN): ""})
    assert fh.HistorieRegister(dd).actueel()[("2025-03", "net_sales")]["pairs"] is None
    assert "1 cleared" in _opslaan(dd, {("2025-03", "net_sales"): "", ("2025-03", fh.PAREN): ""})


def test_pnl_toont_no_data_voor_een_leeggemaakte_maand(tmp_path):
    dd = _dorp(tmp_path)
    _opslaan(dd, {("2026-01", "brand"): "100", ("2026-02", "brand"): "200"})
    _opslaan(dd, {("2026-02", "brand"): ""})
    fh.Instellingen(dd).zet_history_until("2026-03", door="fc")
    h = fin.render_pnl(_st(dd), "fc@t.nl", van="2026-01", tot="2026-02")
    i = h.index("<td>Brand</td>")
    rij = h[i:h.index("</tr>", i)]
    assert "-€100.00" in rij and "no data" in rij and "€200.00" not in rij


@pytest.mark.parametrize("soort", ["csv", "xlsx"])
def test_export_en_import_van_een_leeggemaakte_cel(tmp_path, soort):
    dd = _dorp(tmp_path)
    _opslaan(dd, {("2025-01", "brand"): "100", ("2025-02", "brand"): "200"})
    _opslaan(dd, {("2025-01", "brand"): ""})
    reg = fh.HistorieRegister(dd)
    tab = fh.export_tabel(reg.actueel(), fc.laad(), fh.maanden_van("2025"))
    assert next(r for r in tab if r[0] == "brand")[2:4] == [None, 20000]   # leeg geëxporteerd
    blob = fh.export_csv(tab).encode() if soort == "csv" else fh.export_xlsx(tab)
    g = fh.lees_bestand(f"x.{soort}", blob, fc.laad())
    diff = fh.vergelijk(g["bedragen"], g["paren"], reg.laatste(), fc.laad(), leeg=g["leeg"], paren_leeg=g["paren_leeg"])
    assert (diff["nieuw"], diff["gewijzigd"], diff["geleegd"], diff["ongewijzigd"]) == (0, 0, 0, 1)
    assert len(reg.geschiedenis("2025-02", "brand")) == 1


def _import(dd, blob, **bevestig):
    st = _st(dd)
    soort, html = fin.verwerk_history_import(st, {"action": "finance_hist_import"},
                                             {"file": ("c.csv", blob)}, door="fc", csrf="t")
    iid = fh.ImportLog(dd).alle()[-1]["import_id"]
    msg = fin.verwerk_history_import(st, {"action": "finance_hist_import_bevestig", "import_id": iid, **bevestig},
                                     {}, door="fc", csrf="t")[1]
    return html, msg


def test_lege_cel_in_import_wordt_zonder_vinkje_overgeslagen(tmp_path):
    """Besluit Stefan: leegmaken via een import alleen met het vinkje "also clear"; standaard uit.
    De preview toont de cellen die geleegd ZOUDEN worden."""
    dd = _dorp(tmp_path)
    _opslaan(dd, {("2025-02", "brand"): "200", ("2025-02", "net_sales"): "900", ("2025-02", fh.PAREN): "9"})
    kop = ["line_key", "label", *fh.maanden_van("2025")]
    blob = fh.export_csv([kop, ["brand", "Brand"] + [None] * 12, ["net_sales_pairs", ""] + [None] * 12,
                          ["purchased_goods", ""] + [None, 5000] + [None] * 10]).encode()
    html, msg = _import(dd, blob)
    assert "2</strong> to clear" in html and "Also clear 2 cell(s)" in html and "no data (cleared)" in html
    assert "1 new" in msg and "0 cleared" in msg and "2 empty cell(s) in the file were skipped" in msg
    act = fh.HistorieRegister(dd).actueel()
    assert act[("2025-02", "brand")]["amount_cents"] == 20000                 # niet geleegd
    assert act[("2025-02", "net_sales")]["pairs"] == 9                        # paren ook niet
    assert act[("2025-02", "purchased_goods")]["amount_cents"] == 5000
    assert fh.ImportLog(dd).alle()[-1]["skipped_clears"] == 2


def test_lege_cel_in_import_wordt_met_vinkje_geleegd(tmp_path):
    dd = _dorp(tmp_path)
    _opslaan(dd, {("2025-02", "brand"): "200", ("2025-02", "net_sales"): "900", ("2025-02", fh.PAREN): "9"})
    kop = ["line_key", "label", *fh.maanden_van("2025")]
    blob = fh.export_csv([kop, ["brand", "Brand"] + [None] * 12, ["net_sales_pairs", ""] + [None] * 12]).encode()
    html, msg = _import(dd, blob, also_clear="1")
    assert "2 cleared" in msg
    reg = fh.HistorieRegister(dd)
    assert ("2025-02", "brand") not in reg.actueel()
    assert reg.actueel()[("2025-02", "net_sales")]["pairs"] is None and \
        reg.actueel()[("2025-02", "net_sales")]["amount_cents"] == 90000
    assert [r.get("cleared", False) for r in reg.geschiedenis("2025-02", "brand")] == [True, False]


def test_negatief_alleen_waar_de_regel_een_krediet_toestaat(tmp_path):
    dd = _dorp(tmp_path)
    assert "✗" in _opslaan(dd, {("2025-03", "brand"): "-5"})
    assert "✓" in _opslaan(dd, {("2025-03", "marketing_contribution_suppliers"): "-5"})


def test_paren_horen_bij_net_sales(tmp_path):
    dd = _dorp(tmp_path)
    assert "✗" in _opslaan(dd, {("2025-03", fh.PAREN): "10"})                 # paren zonder omzet
    assert "✓" in _opslaan(dd, {("2025-03", "net_sales"): "1000", ("2025-03", fh.PAREN): "10"})
    assert "✓ 0 new, 1 changed" in _opslaan(dd, {("2025-03", fh.PAREN): "12"})
    r = fh.HistorieRegister(dd).actueel()[("2025-03", "net_sales")]
    assert r["amount_cents"] == 100000 and r["pairs"] == 12


# ── bedragen exact ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("tekst,cent", [("1234,56", 123456), ("1234.56", 123456), ("1.234,56", 123456),
                                        ("1,234.56", 123456), ("€ 12", 1200), ("0,1", 10), ("-3,05", -305),
                                        ("1.234.567,89", 123456789), ("0.29", 29)])
def test_bedragen_naar_centen_exact(tekst, cent):
    assert fh.bedrag(tekst) == (cent, "")


def test_meer_dan_twee_decimalen_is_een_fout():
    assert fh.bedrag("1,234")[0] is None and fh.bedrag("abc")[0] is None


# ── cutover: één bron per maand ─────────────────────────────────────────────

def test_cutover_een_maand_nooit_uit_twee_bronnen(tmp_path):
    dd = _dorp(tmp_path)
    _opslaan(dd, {("2026-08", "purchased_goods"): "500", ("2026-08", "net_sales"): "2000",
                  ("2026-10", "purchased_goods"): "999"})                      # na de cutover: telt niet
    _boek(dd, amount_excl="100", period="2026-08")                            # vóór de cutover: telt niet
    _boek(dd, amount_excl="300", period="2026-10")
    _omzet(dd, period="2026-10", amount_excl="1000", pairs="")
    st = _st(dd)
    assert fh.Instellingen(dd).zet_history_until("2026-09", door="fc")[0]
    h = fin.render_pnl(st, "fc@t.nl")
    assert "2 register line(s)" not in h and "1 register line(s) fall in months up to the cutover" in h
    k, o, n = fh.kies_bronnen([("2026-08", "purchased_goods", 10000, "register"),
                               ("2026-10", "purchased_goods", 30000, "register")], [],
                              [("2026-08", "purchased_goods", 50000, "history"),
                               ("2026-10", "purchased_goods", 99900, "history")], [], "2026-09")
    assert sorted(k) == [("2026-08", "purchased_goods", 50000, "history"),
                         ("2026-10", "purchased_goods", 30000, "register")] and n == 1
    uit = finance_pnl.bereken(k, fc.laad(), opbrengsten=[("2026-08", "net_sales", 200000, "history"),
                                                         ("2026-10", "net_sales", 100000, "manual")],
                              historie_tot="2026-09")
    assert _rij(uit, "net_sales")["waarden"] == {"2026-08": 200000, "2026-10": 100000}
    assert uit["bron"] == {"2026-08": "history", "2026-10": "manual"}


def test_cutover_wint_van_net_sales_source_from():
    from nooch_village.finance_omzet import net_sales_per_maand
    opbr = [("2026-08", "net_sales", 1, "history"), ("2026-08", "net_sales", 2, "shopify"),
            ("2026-11", "net_sales", 3, "shopify"), ("2026-11", "net_sales", 4, "history")]
    assert net_sales_per_maand(opbr, "2026-06", historie_tot="2026-09") == (
        {"2026-08": 1, "2026-11": 3}, {"2026-08": "history", "2026-11": "shopify"})


def test_cutover_wijziging_staat_in_het_logboek(tmp_path):
    dd = _dorp(tmp_path)
    inst = fh.Instellingen(dd)
    assert inst.zet_history_until("2026-13", door="fc") == (False, "the cutover must be YYYY-MM, or empty for no history")
    inst.zet_history_until("2026-06", door="fc")
    inst.zet_history_until("2026-09", door="stefan")
    assert inst.history_until() == "2026-09"
    assert [(r["old"], r["new"], r["created_by"]) for r in inst.alle()] == [("", "2026-06", "fc"),
                                                                           ("2026-06", "2026-09", "stefan")]


def test_no_data_in_plaats_van_nul(tmp_path):
    dd = _dorp(tmp_path)
    _opslaan(dd, {("2026-01", "brand"): "100"})
    fh.Instellingen(dd).zet_history_until("2026-03", door="fc")
    h = fin.render_pnl(_st(dd), "fc@t.nl", van="2026-01", tot="2026-03")
    assert "no data" in h and ">history<" in h


# ── export/import ───────────────────────────────────────────────────────────

def _vul(dd):
    _opslaan(dd, {("2025-01", "net_sales"): "10000", ("2025-01", fh.PAREN): "100",
                  ("2025-01", "purchased_goods"): "4000,10", ("2025-02", "brand"): "0,29",
                  ("2025-03", "marketing_contribution_suppliers"): "-12,34",
                  ("2025-12", "other_income_grants"): "2500"})


@pytest.mark.parametrize("soort", ["csv", "xlsx"])
def test_export_en_terug_importeren_wijzigt_niets(tmp_path, soort):
    dd = _dorp(tmp_path)
    _vul(dd)
    tab = fh.export_tabel(fh.HistorieRegister(dd).actueel(), fc.laad(), fh.maanden_van("2025"))
    blob = fh.export_csv(tab).encode() if soort == "csv" else fh.export_xlsx(tab)
    gelezen = fh.lees_bestand(f"x.{soort}", blob, fc.laad())
    assert gelezen["fouten"] == []
    diff = fh.vergelijk(gelezen["bedragen"], gelezen["paren"], fh.HistorieRegister(dd).laatste(), fc.laad(),
                        leeg=gelezen["leeg"], paren_leeg=gelezen["paren_leeg"])
    assert (diff["nieuw"], diff["gewijzigd"], diff["ongewijzigd"]) == (0, 0, 5)              # net sales + paren = één regel


def test_import_csv_komma_scheiding_punt_decimaal_label_en_fouten(tmp_path):
    dd = _dorp(tmp_path)
    csv_ = ("line_key,label,2024-01,2024-02,2024-13\n"
            ",Purchased goods,\"1,234.56\",10.5,\n"
            "net_sales,,500,,\n"
            "net_sales_pairs,,5,,\n"
            "bestaat_niet,Nope,1,,\n").encode()
    g = fh.lees_bestand("a.csv", csv_, fc.laad())
    assert g["bedragen"][("2024-01", "purchased_goods")] == 123456
    assert g["bedragen"][("2024-02", "purchased_goods")] == 1050
    assert g["paren"] == {"2024-01": 5}
    assert any("2024-13" in f for f in g["fouten"]) and any("unknown line" in f for f in g["fouten"])


def test_import_flow_preview_bevestig_en_fouten_blokkeren(tmp_path):
    dd = _dorp(tmp_path)
    st = _st(dd)
    goed = "line_key;label;2025-01\nbrand;Brand;12,34\n".encode()
    soort, html = fin.verwerk_history_import(st, {"action": "finance_hist_import", "next": "/finance/history"},
                                             {"file": ("a.csv", goed)}, door="fc", csrf="t")
    assert soort == "html" and "1</strong> new" in html and fh.HistorieRegister(dd).alle() == []
    imp = fh.ImportLog(dd).alle()[-1]
    assert imp["status"] == "previewed" and len(imp["attachment"]["sha256"]) == 64
    assert os.path.isfile(os.path.join(dd, imp["attachment"]["path"]))
    soort, msg = fin.verwerk_history_import(st, {"action": "finance_hist_import_bevestig",
                                                 "import_id": imp["import_id"]}, {}, door="fc", csrf="t")
    assert "✓ imported: 1 new" in msg
    r = fh.HistorieRegister(dd).actueel()[("2025-01", "brand")]
    assert r["amount_cents"] == 1234 and r["source"] == f"import:{imp['import_id']}"
    assert fh.ImportLog(dd).status(imp["import_id"])["status"] == "applied"
    # twee keer bevestigen kan niet
    assert "✗" in fin.verwerk_history_import(st, {"action": "finance_hist_import_bevestig",
                                                  "import_id": imp["import_id"]}, {}, door="fc", csrf="t")[1]
    # met een fout: niets, tenzij "ook de geldige rijen"
    fout = "line_key;label;2025-02\nbrand;;7\nonzin;;1\n".encode()
    fin.verwerk_history_import(st, {"action": "finance_hist_import"}, {"file": ("b.csv", fout)}, door="fc", csrf="t")
    iid = fh.ImportLog(dd).alle()[-1]["import_id"]
    assert "✗ nothing imported" in fin.verwerk_history_import(
        st, {"action": "finance_hist_import_bevestig", "import_id": iid}, {}, door="fc", csrf="t")[1]
    assert "✓" in fin.verwerk_history_import(
        st, {"action": "finance_hist_import_bevestig", "import_id": iid, "valid_rows": "1"}, {},
        door="fc", csrf="t")[1]
    assert fh.HistorieRegister(dd).actueel()[("2025-02", "brand")]["amount_cents"] == 700


def test_importbestand_alleen_csv_of_echte_xlsx(tmp_path):
    dd = _dorp(tmp_path)
    log = fh.ImportLog(dd)
    assert log.bewaar("a.pdf", b"%PDF", door="x")[0] is None
    assert log.bewaar("a.xlsx", b"geen zip", door="x")[0] is None


# ── de lagen onder het raster ───────────────────────────────────────────────

def test_lagen_onder_het_raster_kloppen(tmp_path):
    dd = _dorp(tmp_path)
    _opslaan(dd, {("2025-05", "net_sales"): "1000", ("2025-05", "purchased_goods"): "300",
                  ("2025-05", "other_housing_it"): "100", ("2025-05", "other_income_grants"): "50"})
    h = fin.render_history(_st(dd), "fc@t.nl", "t", "2025")
    controle = h[h.index("Check: layers"):]
    assert "€700.00" in controle                                          # CM1 = 1000 − 300
    assert "€650.00" in controle                                          # EBITDA = 700 + 50 − 100
    assert controle.count("no data") >= 11                                # de andere maanden
    assert "finance_hist_opslaan" in h and "finance_hist_opslaan" not in fin.render_history(_st(dd), "bs@t.nl", "t", "2025")


# ── rechten met echte sessies, geen lekken, Tools ───────────────────────────

def test_echte_sessies_404_en_bewerken_alleen_wie_mag(tmp_path):
    dd = _dorp(tmp_path)
    _opslaan(dd, {("2025-01", "brand"): MERK_TXT})
    sessies = _auth.SessionStore()
    httpd = HTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, "T", sessions=sessies))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    poort = httpd.server_address[1]

    def req(methode, pad, wie, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", poort, timeout=10)
        tok = sessies.create(wie)
        kop = {"Cookie": f"nv_session={tok}"}
        if body is not None:
            kop["Content-Type"] = "application/x-www-form-urlencoded"
            body = body.replace("csrf=T", "csrf=" + _auth.csrf_voor("T", tok))   # CSRF per sessie
        conn.request(methode, pad, body=body, headers=kop)
        r = conn.getresponse()
        data = r.read()
        conn.close()
        return r.status, data

    routes = ("/finance/history?jaar=2025", "/finance/history/cell?period=2025-01&line=brand",
              "/finance/history.csv?jaar=2025", "/finance/history.xlsx?jaar=2025")
    try:
        for pad in routes:
            status, body = req("GET", pad, "lid@t.nl")
            assert status == 404 and MERK_TXT.encode() not in body and b"77812" not in body, pad
        for wie in ("fc@t.nl", "bs@t.nl", "stefan@nooch.earth"):
            status, body = req("GET", "/finance/history?jaar=2025", wie)
            assert status == 200 and MERK_TXT.encode() in body, wie
        assert b"77812,34" in req("GET", "/finance/history.csv?jaar=2025", "bs@t.nl")[1]
        assert req("GET", "/finance/history.xlsx?jaar=2025", "fc@t.nl")[1].startswith(b"PK")
        for wie in ("lid@t.nl", "bs@t.nl"):                                   # zien ≠ wijzigen
            for actie in ({"action": "finance_hist_opslaan", "c|brand|2025-02": "1"},
                          {"action": "finance_hist_cutover", "history_until": "2025-12"}):
                body = urllib.parse.urlencode({"csrf": "T", "next": "/", **actie})
                assert req("POST", "/action", wie, body)[0] == 404, (wie, actie)
        body = urllib.parse.urlencode({"csrf": "T", "next": "/finance/history", "action": "finance_hist_cutover",
                                       "history_until": "2025-12"})
        assert req("POST", "/action", "stefan@nooch.earth", body)[0] in (302, 303)
    finally:
        httpd.shutdown()
    assert fh.Instellingen(dd).history_until() == "2025-12"
    assert ("2025-02", "brand") not in fh.HistorieRegister(dd).actueel()


def test_historie_duikt_nergens_anders_op(tmp_path):
    dd = _dorp(tmp_path)
    _opslaan(dd, {("2025-01", "brand"): MERK_TXT}, note="OKAPI-HIST-1")
    st = _st(dd)
    from nooch_village import artefacts, noochie_memo
    from nooch_village.views.search import render_search_fragment
    assert "OKAPI-HIST-1" not in render_search_fragment(st, "OKAPI-HIST-1")
    ctx = artefacts.render_context_markdown(artefacts.serialize_context(FC, st.records, st.att))
    assert MERK_TXT not in ctx and "OKAPI-HIST-1" not in ctx
    beeld, rapport = noochie_memo.verzamel(dd)
    assert "OKAPI-HIST-1" not in str(beeld) + str(rapport) and MERK_TXT not in str(beeld) + str(rapport)


def test_historie_kaart_onder_tools_alleen_voor_finance(tmp_path):
    dd = _dorp(tmp_path)
    st = _st(dd)
    rec = st.records.get(FC)
    rec.definition.domains = list(rec.definition.domains or []) + ["Financial administration"]
    st.records.all = lambda _orig=st.records.all: [rec if r.id == FC else r for r in _orig()]
    assert "/finance/history" in render_tools(st, username="fc@t.nl")
    assert "/finance/history" not in render_tools(st, username="lid@t.nl")
    assert "/finance/history" not in overview._role_tools_html(rec)
