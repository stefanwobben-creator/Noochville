"""Finance-formulieren begrijpelijk (UX-PR, 11 oktober 2026): elk veld een zichtbaar, gekoppeld
label en een hulptekst; de geposte veldnamen ongewijzigd; /finance/help met dezelfde rechten; een
fout houdt de invoer vast; de rekenhulp rekent in hele centen."""
from __future__ import annotations

import http.client
import json
import pathlib
import shutil
import subprocess
import threading
import urllib.parse
import uuid
from html.parser import HTMLParser
from http.server import HTTPServer

import pytest

from nooch_village import auth as _auth
from nooch_village import cockpit2, finance_uitleg as fu
from nooch_village.finance_register import KostenRegister
from nooch_village.views import finance as fin

from tests.test_finance_pr1 import _boek, _dorp, _st


class _Velden(HTMLParser):
    """Alle invoervelden (met hun naam, id, type, hidden) en alle label-for's van een stuk HTML."""

    def __init__(self):
        super().__init__()
        self.velden, self.labels = [], set()

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "label" and d.get("for"):
            self.labels.add(d["for"])
        if tag in ("input", "select", "textarea") and d.get("type") != "hidden":
            self.velden.append(d)


def _ontleed(html: str) -> _Velden:
    p = _Velden()
    p.feed(html)
    return p


def _formulieren(dd):
    """De HTML van elk Finance-formulier, zoals wie mag wijzigen hem ziet."""
    st = _st(dd)
    _boek(dd)
    kid = KostenRegister(dd).alle()[0]["id"]
    from tests.test_finance_omzet import _omzet
    from nooch_village.finance_omzet import OpbrengstRegister
    _omzet(dd)
    rid = OpbrengstRegister(dd).alle()[0]["id"]
    st.vaste_kosten.zet({"description": "Rent", "supplier": "", "amount_cents": 45000, "account_code": "",
                         "management_line": "", "van": "2026-01-01", "tot": "", "notitie": ""}, door="t")
    return {"costs": fin.render_costs(st, "fc@t.nl", "t", {}),
            "cost": fin.render_cost(st, "fc@t.nl", "t", kid),
            "recurring": fin.render_recurring(st, "fc@t.nl", "t"),
            "revenue": fin.render_revenue(st, "fc@t.nl", "t", {}),
            "revenue_line": fin.render_revenue_regel(st, "fc@t.nl", "t", rid),
            "history": fin.render_history(st, "fc@t.nl", "t", "2025"),
            "pnl": fin.render_pnl(st, "fc@t.nl")}


def test_elk_invoerveld_heeft_een_zichtbaar_gekoppeld_label(tmp_path):
    dd = _dorp(tmp_path)
    for scherm, html in _formulieren(dd).items():
        p = _ontleed(html[html.index("c2-main"):])                # niet de zoekbalk van de navigatie
        # Het historie-raster is een tabel: de regel staat links en de maand erboven (`c|regel|maand`).
        zonder = [v for v in p.velden if not str(v.get("name", "")).startswith("c|")
                  and (not v.get("id") or v["id"] not in p.labels)]
        assert zonder == [], (scherm, zonder)


def test_de_geposte_veldnamen_zijn_ongewijzigd(tmp_path):
    """Zelfde namen als vóór deze PR; alleen `doc_choice` is erbij, en die leest de server niet."""
    dd = _dorp(tmp_path)
    html = fin._kostformulier(_st(dd), __import__("nooch_village.finance_config", fromlist=["x"]).laad(),
                              "t", "finance_kost_add", "/finance/costs")
    namen = {v.get("name") for v in _ontleed(html).velden} - {None, ""}
    assert namen == {"entry_date", "period", "supplier", "description", "amount_excl", "vat", "account_code",
                     "management_line", "batch", "payment_status", "paid_date", "recurring_id", "note",
                     "file", "no_document_reason", "bevestig_dubbel", "doc_choice"}
    import inspect
    assert "doc_choice" not in inspect.getsource(fin.verwerk_kost)


def test_paid_date_alleen_bij_paid_en_zichtbaar_zonder_javascript(tmp_path):
    dd = _dorp(tmp_path)
    html = fin.render_costs(_st(dd), "fc@t.nl", "t", {})
    i = html.index("data-toon-als='payment_status=paid'")
    blok = html[i:html.index("</div></div>", i)]
    assert "name=\"paid_date\"" in blok and " hidden" not in html[i - 40:i]      # zonder JS gewoon zichtbaar


def test_hulpteksten_komen_uit_een_plek(tmp_path):
    dd = _dorp(tmp_path)
    schermen = _formulieren(dd)
    help_ = fin.render_help(_st(dd), "fc@t.nl")
    for naam in ("period", "vat", "management_line"):
        from nooch_village.web_base import _e
        assert _e(fu.KOSTEN[naam][2]) in schermen["costs"]
        assert fu.KOSTEN[naam][0] in help_
    assert fu.TERUGKEREND_KOP in schermen["recurring"] and fu.HISTORIE_KOP in schermen["history"]
    assert "Ask Venema" in help_ and "Which date is which" in help_


def test_lege_toestand_zegt_de_volgende_stap(tmp_path):
    dd = _dorp(tmp_path)
    st = _st(dd)
    assert fu.LEEG["costs"] in fin.render_costs(st, "fc@t.nl", "t", {})
    assert fu.LEEG["revenue"] in fin.render_revenue(st, "fc@t.nl", "t", {})
    assert fu.LEEG["recurring"] in fin.render_recurring(st, "fc@t.nl", "t")


def test_samenvatting_terugkerende_kosten():
    assert fu.samenvatting(45000, "2026-01-01") == "€450,00 per month, from 1 January 2026, ongoing."
    assert (fu.samenvatting(45000, "2026-01-01", "2026-12-31")
            == "€450,00 per month, from 1 January 2026, until 31 December 2026.")
    assert fu.samenvatting(None, "2026-01-01") == "" and fu.samenvatting(100, "") == ""


def test_rekenhulp_en_samenvatting_in_javascript():
    node = shutil.which("node")
    if not node:
        pytest.skip("node niet geïnstalleerd")
    test_js = pathlib.Path(__file__).resolve().parent / "js" / "finance_formulieren.test.js"
    uit = subprocess.run([node, str(test_js)], capture_output=True, text=True, timeout=60)
    assert uit.returncode == 0, f"JS-toetsen rood:\n{uit.stdout}\n{uit.stderr}"
    assert uit.stdout.count("  ok   ") >= 12, uit.stdout
    # DE JS-ZIN EN DE SERVER-ZIN ZIJN DEZELFDE (`finance_uitleg.samenvatting`).
    js = json.loads(next(r for r in uit.stdout.splitlines() if r.startswith("JSON "))[5:])
    assert js == [fu.samenvatting(45000, "2026-01-01", ""), fu.samenvatting(123456789, "2026-03-15", "2027-02-28"),
                  fu.samenvatting(5, "2026-12-31", ""), fu.samenvatting(None, "2026-01-01", "")]


def _server(dd):
    sessies = _auth.SessionStore()
    httpd = HTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, "T", sessions=sessies))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, sessies


def test_help_laadt_voor_finance_en_404_voor_de_rest(tmp_path):
    dd = _dorp(tmp_path)
    httpd, sessies = _server(dd)
    try:
        for wie, status in (("fc@t.nl", 200), ("bs@t.nl", 200), ("stefan@nooch.earth", 200), ("lid@t.nl", 404)):
            c = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=10)
            c.request("GET", "/finance/help", headers={"Cookie": f"nv_session={sessies.create(wie)}"})
            r = c.getresponse()
            body = r.read()
            assert r.status == status, wie
            assert (b"What goes where" in body) == (status == 200)
    finally:
        httpd.shutdown()


def test_een_fout_toont_het_formulier_met_wat_er_stond_en_slaat_niets_op(tmp_path):
    dd = _dorp(tmp_path)
    httpd, sessies = _server(dd)
    try:
        b = uuid.uuid4().hex
        fc = sessies.create('fc@t.nl')                        # CSRF per sessie (17 oktober 2026)
        velden = {"csrf": _auth.csrf_voor("T", fc), "action": "finance_kost_add", "next": "/finance/costs", "entry_date": "2026-10-05",
                  "supplier": "OKAPI-LEVERANCIER", "description": "Strobel", "amount_excl": "100,00",
                  "payment_status": "open", "no_document_reason": "test"}       # geen account, geen regel
        body = b"".join(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
                        for k, v in velden.items()) + f"--{b}--\r\n".encode()
        c = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=10)
        c.request("POST", "/action", body, {"Cookie": f"nv_session={fc}",
                                            "Content-Type": f"multipart/form-data; boundary={b}"})
        r = c.getresponse()
        html = r.read().decode()
        assert r.status == 200 and "OKAPI-LEVERANCIER" in html                   # de invoer staat er nog
        i = html.index("id='fk-management_line'")
        assert "⚠ ✗ pick a management line" in html[i:i + 4000]                 # bij het veld
        assert KostenRegister(dd).alle() == []
        # terugkerende kost: zelfde, via de gewone (niet-multipart) route
        form = urllib.parse.urlencode({"csrf": _auth.csrf_voor("T", fc), "action": "vaste_kosten_zet", "next": "/finance/recurring",
                                       "omschrijving": "OKAPI-HUUR", "bedrag": "450", "van": "2026-02-01",
                                       "tot": "2026-01-01"})
        c = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=10)
        c.request("POST", "/action", form, {"Cookie": f"nv_session={fc}",
                                             "Content-Type": "application/x-www-form-urlencoded"})
        r = c.getresponse()
        html = r.read().decode()
        assert r.status == 200 and "OKAPI-HUUR" in html and "end date is before the start date" in html
        assert _st(dd).vaste_kosten.alle() == []
    finally:
        httpd.shutdown()


def test_de_hulptekst_klopt_met_het_gedrag():
    """De vier vragen uit de instructie (sectie 9): wat de tekst zegt, doet het systeem ook."""
    from nooch_village import finance_config as fc
    from nooch_village.finance_register import maak_kost
    cfg = fc.laad()
    basis = {"entry_date": "2026-10-05", "supplier": "X", "description": "Y", "amount_excl": "100",
             "no_document_reason": "t"}
    # a. zonder account en regel: geweigerd; een account uit de lijst stelt een regel voor, een vrij
    #    getypte naam niet.
    assert maak_kost(basis, cfg)[0] is None
    assert maak_kost({**basis, "account_code": cfg["accounts"][0]["naam_nl"]}, cfg)[0] is not None
    assert maak_kost({**basis, "account_code": "Telefoon"}, cfg)[0] is None
    assert "Required, unless you picked an account from the list" in fu.KOSTEN["management_line"][2]
    assert "not in the list proposes nothing" in fu.KOSTEN["account_code"][2]
    # b. de runway telt de maandbedragen van alles wat vandaag loopt: "monthly share" klopt.
    from nooch_village.finance_recurring import RecurringCostStore
    import tempfile, os
    rc = RecurringCostStore(os.path.join(tempfile.mkdtemp(), "recurring.json"))
    rc.zet({"description": "Insurance", "supplier": "", "amount_cents": 10000, "account_code": "",
            "management_line": "", "van": "2026-01-01", "tot": "", "notitie": ""}, door="t")
    assert rc.totaal_cents_op("2026-06-15") == 10000
    assert "divided by 12" in fu.TERUGKEREND["bedrag"][2] and "divided by 3" in fu.TERUGKEREND["bedrag"][2]
    # c. een creditnota kan niet als losse negatieve regel (behalve op de marketingbijdrage): via Correct.
    assert maak_kost({**basis, "management_line": "brand", "amount_excl": "-50"}, cfg)[0] is None
    vat = " ".join(next(a for k, _t, a in fu.HELP if k == "vat"))
    assert "use Correct" in vat and "cannot yet be entered as a line of its own" in vat
    # d. niet-aftrekbare btw: geen fiscale regel, wel de verwijzing.
    assert "Ask Venema before entering such a cost." in vat
