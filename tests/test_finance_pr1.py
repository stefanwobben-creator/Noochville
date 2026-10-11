"""Finance PR 1 (Costs), 10 oktober 2026: alleen toevoegen, borging, rechten, geen lekken, P&L."""
from __future__ import annotations

import ast
import http.client
import os
import threading
from http.server import HTTPServer

import pytest

from nooch_village import auth as _auth
from nooch_village import cockpit2, finance_config as fc, finance_pnl, zicht
from nooch_village.finance_register import KostenRegister, maak_kost, posten, totalen
from nooch_village.views import finance as fin

C = "mother_earth__nooch"
FC = "mother_earth__nooch__financial_controller"
BS = "mother_earth__nooch__strategic_lead_founder_steward"
PDF = b"%PDF-1.4 testfactuur"
MERK = "ZEBRA-FINANCE-7781"                      # een kostregel die nergens anders mag opduiken


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    for naam, mail, rol in (("Fien", "fc@t.nl", FC), ("Bas", "bs@t.nl", BS),
                            ("Lid", "lid@t.nl", "mother_earth__nooch__marketing_lead"),
                            ("Stefan", "stefan@nooch.earth", "mother_earth__nooch__shoe_developer")):
        st.people.add(naam, mail)
        st.assign.assign(rol, "person", st.people.by_email(mail).id)
    return dd


def _st(dd):
    return cockpit2._Stores(dd)


def _velden(**kw):
    v = {"action": "finance_kost_add", "entry_date": "2026-10-05", "supplier": "LTA", "description": "Strobel",
         "amount_excl": "100,00", "vat": "21", "management_line": "purchased_goods", "payment_status": "open"}
    v.update(kw)
    return v


def _boek(dd, blob=PDF, **kw):
    return fin.verwerk_kost(_st(dd), _velden(**kw), {"file": ("factuur.pdf", blob)} if blob else {},
                            username="fc@t.nl", door="fc")


# ── alleen toevoegen ────────────────────────────────────────────────────────

def test_het_register_heeft_geen_wijzig_of_verwijdermethode():
    """De klasse mag geen enkele schrijfweg hebben behalve toevoegen."""
    publiek = {n for n in dir(KostenRegister) if not n.startswith("_")}
    assert not {n for n in publiek if any(w in n.lower() for w in ("update", "delete", "remove", "wijzig",
                                                                    "weg", "zet", "set", "edit"))}
    bron = open(fin.__file__.replace("views/finance.py", "finance_register.py")).read()
    assert '"w"' not in bron.replace('"wb"', "")                      # het register wordt nooit herschreven


def test_een_correctie_is_tegenboeking_plus_nieuwe_regel_en_telt_netto(tmp_path):
    dd = _dorp(tmp_path)
    assert "✓" in _boek(dd)
    oud = KostenRegister(dd).alle()[0]
    msg = fin.verwerk_kost(_st(dd), _velden(action="finance_kost_correct", kid=oud["id"], amount_excl="80"),
                           {}, username="fc@t.nl", door="fc")
    assert "✓ corrected" in msg
    regels = KostenRegister(dd).alle()
    assert len(regels) == 3                                            # niets weg, twee erbij
    storno = [r for r in regels if r.get("corrects") == oud["id"]][0]
    assert storno["amount_excl_cents"] == -10000 and storno["vat_cents"] == -2100
    assert sum(r["amount_excl_cents"] for r in regels) == 8000          # netto de nieuwe waarde
    nieuw = [r for r in regels if r["id"] not in (oud["id"], storno["id"])][0]
    assert nieuw["attachment"] == oud["attachment"]                     # het document gaat mee


def test_negatief_alleen_op_marketing_bijdrage():
    cfg = fc.laad()
    basis = {"entry_date": "2026-10-05", "supplier": "X", "description": "y", "no_document_reason": "n"}
    assert maak_kost({**basis, "amount_excl": "-50", "management_line": "brand"}, cfg)[0] is None
    assert maak_kost({**basis, "amount_excl": "-50", "management_line": "marketing_contribution_suppliers"},
                     cfg)[0]["amount_excl_cents"] == -5000


def test_bedragen_in_centen_en_btw_telt_niet_mee(tmp_path):
    dd = _dorp(tmp_path)
    _boek(dd, amount_excl="0,10", vat="0,02")
    _boek(dd, blob=b"%PDF-1.4 tweede", amount_excl="0,20", vat="0,04")
    regels = KostenRegister(dd).alle()
    assert all(isinstance(r["amount_excl_cents"], int) for r in regels)
    assert totalen(regels, "management_line") == {"purchased_goods": 30}    # geen 0.30000000004, geen btw


def test_zonder_document_alleen_met_reden(tmp_path):
    dd = _dorp(tmp_path)
    assert "✗" in _boek(dd, blob=None)
    assert "✓" in _boek(dd, blob=None, no_document_reason="paper receipt lost")
    h = fin.render_costs(_st(dd), "fc@t.nl", "t", {})
    assert "missing document" in h and "paper receipt lost" in h


# ── borging ─────────────────────────────────────────────────────────────────

def test_hash_bij_upload_en_controle_bij_download(tmp_path):
    dd = _dorp(tmp_path)
    _boek(dd)
    reg = KostenRegister(dd)
    r = reg.alle()[0]
    assert r["attachment"]["sha256"] == __import__("hashlib").sha256(PDF).hexdigest()
    assert reg.lees_bijlage(r) == (PDF, "")
    with open(os.path.join(dd, r["attachment"]["path"]), "ab") as f:
        f.write(b"gemanipuleerd")
    blob, fout = reg.lees_bijlage(r)
    assert blob is None and "does not match its recorded hash" in fout


def test_alleen_echte_pdf_png_jpg_tot_10_mb(tmp_path):
    reg = KostenRegister(str(tmp_path))
    assert reg.bewaar_bijlage("x.exe", b"MZ")[0] is None
    assert reg.bewaar_bijlage("nep.pdf", b"<html>")[0] is None
    assert reg.bewaar_bijlage("groot.pdf", b"%PDF" + b"0" * (10 * 1024 * 1024))[0] is None
    assert reg.bewaar_bijlage("ok.png", b"\x89PNG....")[0]["mime"] == "image/png"


def test_dubbele_factuur_waarschuwt_en_vraagt_bevestiging(tmp_path):
    dd = _dorp(tmp_path)
    _boek(dd)
    msg = _boek(dd)
    assert msg.startswith("⚠") and "2026-10-05, LTA" in msg and len(KostenRegister(dd).alle()) == 1
    assert "✓" in _boek(dd, bevestig_dubbel="1")
    assert len(KostenRegister(dd).alle()) == 2


# ── rechten ─────────────────────────────────────────────────────────────────

def test_wie_mag_wat():
    st = type("S", (), {})()
    # zien: FC (fallback zolang het domein niet bestaat), Business strategy, Stefan; wijzigen: FC, Stefan
    groep = zicht.groepen()["finance"]
    assert groep["zien"]["personen"] == ["stefan@nooch.earth"] and BS in groep["zien"]["rollen"]
    assert BS not in groep["wijzigen"]["rollen"] and groep["fallback"]["Financial administration"] == FC
    assert st is not None


def test_echte_sessies_404_voor_wie_niet_mag(tmp_path):
    """Alle /finance-routes geven een 404 aan wie niet mag — ook de bijlage en de CSV."""
    dd = _dorp(tmp_path)
    _boek(dd, description=MERK)
    kid = KostenRegister(dd).alle()[0]["id"]
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

    routes = ("/finance/costs", f"/finance/costs/view?id={kid}", "/finance/recurring", "/finance/monthly",
              "/finance/pnl", "/finance/costs.csv", f"/finance/file?id={kid}", "/fixed-costs",
              "/finance/help")
    try:
        for pad in routes:
            status, body = get(pad, "lid@t.nl")
            assert status == 404 and MERK.encode() not in body and PDF not in body, pad
        for wie in ("fc@t.nl", "bs@t.nl", "stefan@nooch.earth"):
            assert get("/finance/costs", wie)[0] == 200, wie
        assert get(f"/finance/file?id={kid}", "bs@t.nl") == (200, PDF)
    finally:
        httpd.shutdown()
    # wie het downloadde, staat in het logboek
    assert "downloads.jsonl" in os.listdir(os.path.join(dd, "finance"))


def test_invoeren_alleen_fc_en_stefan(tmp_path):
    dd = _dorp(tmp_path)
    st = _st(dd)
    assert fin.mag_wijzigen(st, "fc@t.nl") and fin.mag_wijzigen(st, "stefan@nooch.earth")
    assert not fin.mag_wijzigen(st, "bs@t.nl") and not fin.mag_wijzigen(st, "lid@t.nl")
    assert "finance_kost_add" in fin.render_costs(st, "fc@t.nl", "t", {})
    assert "finance_kost_add" not in fin.render_costs(st, "bs@t.nl", "t", {})
    with pytest.raises(cockpit2.NietGevonden):
        cockpit2.dispatch(dd, "vaste_kosten_zet", {"omschrijving": ["Huur"], "bedrag": ["1"],
                                                   "van": ["2026-01-01"], "next": ["/"]}, username="bs@t.nl")


# ── geen lekken ─────────────────────────────────────────────────────────────

#: De enige modules die het register (of `data/finance/`) mogen kennen.
_TOEGESTAAN = {"finance_register.py", "finance_recurring.py", "finance_pnl.py", "finance_config.py",
               "finance_omzet.py", "finance_historie.py", "views/finance.py", "cockpit2.py", "cli.py"}


def test_guard_niemand_anders_leest_finance():
    """Finance-data komt NOOIT in LLM-context, memo's, radar of zoekindexen. Deze toets faalt zodra
    een andere module het register importeert of naar data/finance/ verwijst."""
    root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nooch_village")
    fout = []
    for dirpath, _d, files in os.walk(root):
        for f in files:
            if not f.endswith(".py"):
                continue
            pad = os.path.join(dirpath, f)
            rel = os.path.relpath(pad, root)
            if rel in _TOEGESTAAN:
                continue
            boom = ast.parse(open(pad, encoding="utf-8").read())
            for n in ast.walk(boom):
                mods = []
                if isinstance(n, ast.Import):
                    mods = [a.name for a in n.names]
                elif isinstance(n, ast.ImportFrom):
                    mods = [n.module or ""] + [f"{n.module}.{a.name}" for a in n.names]
                if any("finance_register" in m or "finance_omzet" in m or "finance_historie" in m or "views.finance" in m
                       or m.endswith("views.finance") for m in mods):
                    fout.append(f"{rel}: importeert finance")
                # `history.jsonl` exact (of als padstuk): `pulse_history.jsonl` e.d. zijn geen finance.
                if isinstance(n, ast.Constant) and isinstance(n.value, str) and (any(
                        b in n.value for b in ("costs.jsonl", "revenue.jsonl", "history_imports.jsonl",
                                               "history_settings.jsonl"))
                        or n.value == "history.jsonl" or n.value.endswith("/history.jsonl")):
                    fout.append(f"{rel}: verwijst naar een finance-register")
    assert fout == []


def test_een_kostregel_duikt_nergens_anders_op(tmp_path):
    dd = _dorp(tmp_path)
    _boek(dd, description=MERK, supplier=MERK)
    st = _st(dd)
    from nooch_village import artefacts, noochie_memo
    from nooch_village.views.search import render_search_fragment
    assert MERK not in render_search_fragment(st, MERK)
    for rol in (FC, BS):
        assert MERK not in artefacts.render_context_markdown(artefacts.serialize_context(rol, st.records, st.att))
    beeld, rapport = noochie_memo.verzamel(dd)
    assert MERK not in str(beeld) + str(rapport)
    radar = getattr(st, "radar", None)
    assert MERK not in str(getattr(radar, "_data", ""))


# ── recurring + migratie ────────────────────────────────────────────────────

def test_migratie_is_idempotent_en_de_runway_blijft_gelijk(tmp_path):
    import json
    from nooch_village import finance_recurring
    from nooch_village.views.metrics import runway
    dd = _dorp(tmp_path)
    with open(os.path.join(dd, "vaste_kosten.json"), "w") as f:
        json.dump({"a1": {"omschrijving": "Huur", "bedrag": 1200.5, "categorie": "Huisvestingskosten",
                          "van": "2026-01-01", "tot": "", "notitie": ""}}, f)
    st = _st(dd)
    droog = finance_recurring.migreer(dd, st.vaste_kosten)
    assert [r["actie"] for r in droog] == ["over"] and st.vaste_kosten.alle() == []
    finance_recurring.migreer(dd, st.vaste_kosten, apply=True)
    st = _st(dd)
    r = st.vaste_kosten.get("a1")
    assert (r["amount_cents"], r["account_code"]) == (120050, "Huisvestingskosten")
    assert runway(st)["vaste_kosten"] == 1200.5
    assert [x["actie"] for x in finance_recurring.migreer(dd, st.vaste_kosten, apply=True)] == ["al over"]


def test_recurring_wijzigen_staat_in_het_logboek(tmp_path):
    dd = _dorp(tmp_path)
    form = {"omschrijving": ["Huur"], "bedrag": ["1000"], "van": ["2026-01-01"], "next": ["/"]}
    cockpit2.dispatch(dd, "vaste_kosten_zet", form, username="fc@t.nl")
    rid = _st(dd).vaste_kosten.alle()[0]["id"]
    cockpit2.dispatch(dd, "vaste_kosten_zet", dict(form, rid=[rid], bedrag=["1100"]), username="fc@t.nl")
    cockpit2.dispatch(dd, "vaste_kosten_weg", {"rid": [rid], "next": ["/"]}, username="fc@t.nl")
    log = open(os.path.join(dd, "finance", "recurring_log.jsonl")).read().splitlines()
    assert [__import__("json").loads(r)["actie"] for r in log] == ["nieuw", "wijzig", "weg"]


def test_verwacht_maar_nog_niet_gefactureerd(tmp_path):
    dd = _dorp(tmp_path)
    cockpit2.dispatch(dd, "vaste_kosten_zet", {"omschrijving": ["Huur"], "bedrag": ["1000"],
                                               "van": ["2026-01-01"], "next": ["/"]}, username="fc@t.nl")
    rid = _st(dd).vaste_kosten.alle()[0]["id"]
    _boek(dd, recurring_id=rid, period="2026-09", amount_excl="1000")
    open_ = fin.verwacht_niet_gefactureerd(_st(dd), ["2026-08", "2026-09", "2026-10"])
    assert [x["maand"] for x in open_] == ["2026-08", "2026-10"]


# ── CSV ─────────────────────────────────────────────────────────────────────

def test_csv_puntkomma_decimale_komma_en_rekening(tmp_path):
    dd = _dorp(tmp_path)
    _boek(dd, amount_excl="1234,56", vat="259,26", account_code="Kostprijs van de omzet")
    csv = fin.csv_export(KostenRegister(dd).alle())
    kop, rij = csv.strip().split("\r\n")
    assert kop.split(";") == list(fin.CSV_KOLOMMEN)
    velden = rij.split(";")
    assert velden[5] == "Kostprijs van de omzet" and velden[8] == "1234,56" and velden[9] == "259,26"


# ── P&L ─────────────────────────────────────────────────────────────────────

def _bekende_posten(bron="register"):
    return [("2026-10", "purchased_goods", 10000, bron), ("2026-10", "transport_inbound", 2000, bron),
            ("2026-10", "outbound_freight", 500, bron), ("2026-10", "brand", 1000, bron),
            ("2026-10", "marketing_contribution_suppliers", -300, bron), ("2026-10", "other_housing_it", 400, bron),
            ("2026-10", "depreciation", 100, bron), ("2026-10", "psp_transaction_cost", 50, bron),
            ("2026-10", "tax", 0, bron),
            # een correctie die zichzelf opheft
            ("2026-10", "brand", 700, bron), ("2026-10", "brand", -700, bron)]


def _rij(uit, key):
    return next(r for r in uit["rijen"] if r["key"] == key)


def test_pnl_groepen_lagen_en_krediet_zonder_omzet():
    uit = finance_pnl.bereken(_bekende_posten(), fc.laad())
    assert uit["kosten_alleen"]
    assert _rij(uit, "cost_of_sales")["waarden"]["2026-10"] == -12000
    assert _rij(uit, "marketing_contribution_suppliers")["waarden"]["2026-10"] == 300    # krediet
    assert _rij(uit, "selling")["waarden"]["2026-10"] == -700                          # 1000 − 300, correctie op
    assert _rij(uit, "cm1")["waarden"]["2026-10"] == -12000
    assert _rij(uit, "cm3")["waarden"]["2026-10"] == -13200
    assert _rij(uit, "ebt")["waarden"]["2026-10"] == -13750
    assert "costs only" in _rij(uit, "cm1")["label"] and _rij(uit, "cm1")["pct"] is None


def test_pnl_met_omzet_marges_en_percentages():
    uit = finance_pnl.bereken(_bekende_posten(), fc.laad(), omzet={"2026-10": 50000})
    assert not uit["kosten_alleen"]
    assert _rij(uit, "cm1")["waarden"]["2026-10"] == 38000
    assert abs(_rij(uit, "cm1")["pct"]["2026-10"] - 0.76) < 1e-9
    assert _rij(uit, "net")["waarden"]["2026-10"] == 50000 - 13750


def test_pnl_bron_maakt_niet_uit():
    a = finance_pnl.bereken(_bekende_posten("register"), fc.laad())
    b = finance_pnl.bereken(_bekende_posten("history"), fc.laad())
    assert a == b


def test_de_pnl_pagina_toont_kosten_negatief_en_wacht_op_omzet(tmp_path):
    dd = _dorp(tmp_path)
    _boek(dd, amount_excl="100", period="2026-10")
    h = fin.render_pnl(_st(dd), "fc@t.nl")
    assert "No revenue in this selection yet" in h and "-€100.00" in h and "costs only" in h
    assert posten(KostenRegister(dd).alle()) == [("2026-10", "purchased_goods", 10000, "register")]
