"""Finance PR 3 (11 oktober 2026): kostenimport uit Excel/CSV met een zip vol PDF's.

Preview schrijft niets in het register · alleen `importeren` · dubbel en niet-dubbel · valuta,
negatief, onbekende regel, ongeldige datum, ontbrekende PDF · cutover · betaald via · import_id ·
terugdraaien · leverancierstandaard · rechten · geen lekken.
"""
from __future__ import annotations

import io
import os
import zipfile

import pytest

from nooch_village import cockpit2
from nooch_village import finance_kosten_import as fki
from nooch_village.finance_historie import Instellingen
from nooch_village.finance_register import BANK, KostenRegister, filter_regels
from nooch_village.views import finance as fin

from tests.test_finance_pr1 import MERK, PDF, _boek, _dorp, _st

KOP = ["actie", "factuurdatum", "periode", "leverancier", "omschrijving", "valuta", "excl. btw", "btw",
       "managementregel", "opmerking / vraag", "bestand", "type", "betaald via", "status in Basecone",
       "boekstuknummer"]
LIMIET = 20 * 1024 * 1024


def _rij(**kw):
    basis = {"actie": "importeren", "factuurdatum": "2026-09-03", "periode": "", "leverancier": "LTA",
             "omschrijving": "Strobel", "valuta": "EUR", "excl. btw": "100,00", "btw": "21,00",
             "managementregel": "purchased_goods", "opmerking / vraag": "", "bestand": "a.pdf", "type": "factuur",
             "betaald via": "", "status in Basecone": "", "boekstuknummer": ""}
    basis.update(kw)
    return basis


def _csv(rijen, kop=KOP) -> bytes:
    regels = [";".join(kop)] + [";".join(str(r.get(k, "")) for k in kop) for r in rijen]
    return ("\n".join(regels) + "\n").encode("utf-8")


def _zip(bestanden: dict[str, bytes], map_: str = "Basecone export/") -> bytes:
    """Zoals Stefans zip: een map bovenaan, plus macOS-rommel die genegeerd moet worden."""
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for naam, blob in bestanden.items():
            z.writestr(map_ + naam, blob)
            z.writestr(f"__MACOSX/{map_}._{naam}", b"rommel")
        z.writestr(map_ + ".DS_Store", b"rommel")
    return b.getvalue()


def _pdf(n: int) -> bytes:
    return PDF + f" document {n}".encode()


def _preview(dd, rijen, bestanden=None, *, tabel=None, naam="voorstel.csv", wie="fc"):
    st = _st(dd)
    files = {"file": (naam, tabel if tabel is not None else _csv(rijen))}
    if bestanden is not None:
        files["zip"] = ("pdfs.zip", _zip(bestanden))
    return fin.verwerk_kosten_import(st, {"action": "finance_kosten_import"}, files, door=wie, csrf="t",
                                     limiet=LIMIET)


def _laatste_id(dd):
    return fki.KostenImportLog(dd).imports()[0]["import_id"]


def _bevestig(dd, iid=None, **extra):
    return fin.verwerk_kosten_import(_st(dd), {"action": "finance_kosten_import_bevestig",
                                               "import_id": iid or _laatste_id(dd), **extra},
                                     {}, door="fc", csrf="t", limiet=LIMIET)


def _oordeel(dd, rijen, bestanden=None):
    st = _st(dd)
    return fki.beoordeel("x.csv", _csv(rijen), _zip(bestanden or {}), register=KostenRegister(dd).alle(),
                         cfg=fin.fc.laad(), history_until=Instellingen(dd).history_until(),
                         standaarden=fki.LeveranciersStandaard(dd).standaarden(), import_id="t1")


def _status(o):
    return [x["status"] for x in o["rijen"]]


def _bestanden_register(dd) -> dict[str, bytes]:
    pad = os.path.join(dd, "finance")
    uit = {}
    for f in ("costs.jsonl",):
        p = os.path.join(pad, f)
        uit[f] = open(p, "rb").read() if os.path.exists(p) else b""
    att = os.path.join(pad, "attachments")
    uit["attachments"] = sorted(os.listdir(att)) if os.path.isdir(att) else []
    return uit


# ── preview schrijft niets ──────────────────────────────────────────────────

def test_preview_schrijft_niets_in_het_register(tmp_path):
    dd = _dorp(tmp_path)
    _boek(dd)
    voor = _bestanden_register(dd)
    soort, html = _preview(dd, [_rij(), _rij(bestand="b.pdf", leverancier="Bunq")], {"a.pdf": _pdf(1), "b.pdf": _pdf(2)})
    assert soort == "html" and "Confirm import" in html
    assert _bestanden_register(dd) == voor                    # byte-identiek, geen bijlage erbij
    imp = fki.KostenImportLog(dd).imports()[0]
    assert imp["status"] == "previewed" and imp["zip"]["sha256"]   # wel geborgd: het bestand en de zip


def test_alleen_importeren_rijen_gaan_erin(tmp_path):
    dd = _dorp(tmp_path)
    rijen = [_rij(), _rij(actie="overslaan", bestand="", opmerking="privé"),
             _rij(actie="vraag", omschrijving="Laptop", managementregel="depreciation", bestand="")]
    soort, html = _preview(dd, rijen, {"a.pdf": _pdf(1)})
    assert "not imported" in html and "action: overslaan" in html and "action: vraag" in html
    assert _bevestig(dd)[1].startswith("✓ imported 1 line")
    regels = KostenRegister(dd).alle()
    assert [r["description"] for r in regels] == ["Strobel"]


# ── totalen en bedragen ─────────────────────────────────────────────────────

def test_totalen_centen_exact_en_decimale_komma_en_punt(tmp_path):
    dd = _dorp(tmp_path)
    o = _oordeel(dd, [_rij(**{"excl. btw": "1.234,56", "btw": "259,26"}),
                      _rij(bestand="b.pdf", leverancier="Bunq", **{"excl. btw": "0.10", "btw": "0.02"})],
                 {"a.pdf": _pdf(1), "b.pdf": _pdf(2)})
    assert o["totalen"] == {"EUR": {"aantal": 2, "excl": 123466, "btw": 25928}}


def test_excl_plus_btw_tegen_totaal_op_document(tmp_path):
    dd = _dorp(tmp_path)
    kop = KOP + ["totaal op document"]
    goed = _rij(**{"totaal op document": "121,00"})
    fout = _rij(bestand="b.pdf", leverancier="Bunq", **{"totaal op document": "121,01"})
    o = fki.beoordeel("x.csv", _csv([goed, fout], kop), _zip({"a.pdf": _pdf(1), "b.pdf": _pdf(2)}),
                      register=[], cfg=fin.fc.laad(), history_until="", standaarden={})
    assert _status(o) == [fki.NIEUW, fki.FOUT]
    assert "is not the total on the document" in o["rijen"][1]["redenen"][0]


def test_xlsx_met_echte_datums_en_getallen(tmp_path):
    import datetime
    from openpyxl import Workbook
    dd = _dorp(tmp_path)
    wb = Workbook()
    ws = wb.active
    ws.append(KOP)
    r = _rij()
    r.update({"factuurdatum": datetime.datetime(2026, 9, 3), "excl. btw": 100.1, "btw": 21.02})
    ws.append([r[k] for k in KOP])
    b = io.BytesIO()
    wb.save(b)
    soort, html = _preview(dd, None, {"a.pdf": _pdf(1)}, tabel=b.getvalue(), naam="voorstel.xlsx")
    assert soort == "html"
    _bevestig(dd)
    (regel,) = KostenRegister(dd).alle()
    assert (regel["entry_date"], regel["amount_excl_cents"], regel["vat_cents"]) == ("2026-09-03", 10010, 2102)


# ── dubbel en niet-dubbel ───────────────────────────────────────────────────

def test_een_pdf_onder_twee_regels_is_geen_dubbel_en_wordt_een_keer_bewaard(tmp_path):
    dd = _dorp(tmp_path)
    rijen = [_rij(), _rij(managementregel="transport_inbound", **{"excl. btw": "30,00", "btw": "6,30"})]
    o = _oordeel(dd, rijen, {"a.pdf": _pdf(1)})
    assert _status(o) == [fki.NIEUW, fki.NIEUW]
    _preview(dd, rijen, {"a.pdf": _pdf(1)})
    _bevestig(dd)
    regels = KostenRegister(dd).alle()
    assert len(regels) == 2 and regels[0]["attachment"] == regels[1]["attachment"]
    assert len(os.listdir(os.path.join(dd, "finance", "attachments", "2026"))) == 1


def test_de_tweede_helft_van_een_gesplitst_document_later_is_geen_dubbel(tmp_path):
    """De PDF staat al in het register onder één regel; dezelfde PDF met een ander bedrag op een
    andere regel is de andere helft van hetzelfde document, geen dubbel."""
    dd = _dorp(tmp_path)
    _preview(dd, [_rij()], {"a.pdf": _pdf(1)})
    _bevestig(dd)
    o = _oordeel(dd, [_rij(managementregel="transport_inbound", **{"excl. btw": "30,00", "btw": "6,30"})],
                 {"a.pdf": _pdf(1)})
    assert _status(o) == [fki.NIEUW]


def test_echte_dubbelen_worden_geweigerd(tmp_path):
    dd = _dorp(tmp_path)
    _preview(dd, [_rij()], {"a.pdf": _pdf(1)})
    _bevestig(dd)
    # dezelfde PDF, hetzelfde bedrag, dezelfde regel (andere leverancierspelling)
    o = _oordeel(dd, [_rij(leverancier="L.T.A.")], {"a.pdf": _pdf(1)})
    assert _status(o) == [fki.DUBBEL]
    # zelfde leverancier, datum, totaal en regel — met een ander bestand
    o = _oordeel(dd, [_rij(bestand="c.pdf")], {"c.pdf": _pdf(3)})
    assert _status(o) == [fki.DUBBEL]
    # twee keer dezelfde rij in één bestand
    o = _oordeel(dd, [_rij(bestand="d.pdf", leverancier="X"), _rij(bestand="d.pdf", leverancier="X")],
                 {"d.pdf": _pdf(4)})
    assert _status(o) == [fki.NIEUW, fki.DUBBEL]


# ── fouten en waarschuwingen ────────────────────────────────────────────────

@pytest.mark.parametrize("rij, stuk", [
    (_rij(valuta="USD"), "only EUR"),
    (_rij(**{"excl. btw": "-12,00"}), "negative amounts"),
    (_rij(managementregel="koffie"), "unknown management line"),
    (_rij(managementregel=""), "pick a management line"),
    (_rij(factuurdatum="31-02-2026"), "invalid invoice date"),
    (_rij(bestand="weg.pdf"), "is not in the zip"),
    (_rij(bestand=""), "no file, and no reason"),
    (_rij(actie="misschien"), "unknown action"),
    (_rij(**{"betaald via": "de buurman"}), "unknown 'paid via'"),
    (_rij(**{"excl. btw": "1,234"}), "more than two decimals"),
])
def test_een_foute_rij_met_reden(tmp_path, rij, stuk):
    o = _oordeel(_dorp(tmp_path), [rij], {"a.pdf": _pdf(1)})
    assert _status(o) == [fki.FOUT] and stuk in "; ".join(o["rijen"][0]["redenen"])


def test_een_nep_pdf_in_de_zip_is_een_fout(tmp_path):
    o = _oordeel(_dorp(tmp_path), [_rij()], {"a.pdf": b"geen pdf"})
    assert _status(o) == [fki.FOUT] and "not a real .pdf" in o["rijen"][0]["redenen"][0]


def test_twee_gelijke_namen_in_de_zip_is_een_fout(tmp_path):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("2025/a.pdf", _pdf(1))
        z.writestr("2026/a.pdf", _pdf(2))
    o = fki.beoordeel("x.csv", _csv([_rij()]), b.getvalue(), register=[], cfg=fin.fc.laad(),
                      history_until="", standaarden={})
    assert "two files named 'a.pdf'" in o["rijen"][0]["redenen"][0]


def test_een_foute_rij_blokkeert_tenzij_de_geldige_rijen_mogen(tmp_path):
    dd = _dorp(tmp_path)
    _preview(dd, [_rij(), _rij(bestand="b.pdf", valuta="GBP")], {"a.pdf": _pdf(1), "b.pdf": _pdf(2)})
    iid = _laatste_id(dd)
    assert _bevestig(dd, iid)[1].startswith("✗ nothing imported")
    assert KostenRegister(dd).alle() == []
    assert _bevestig(dd, iid, valid_rows="1")[1].startswith("✓ imported 1 line")
    assert _bevestig(dd, iid, valid_rows="1")[1].startswith("✗ this import does not exist or was already handled")


def test_waarschuwingen_worden_wel_geimporteerd(tmp_path):
    dd = _dorp(tmp_path)
    kop = KOP + ["zekerheid"]
    rijen = [_rij(type="herinnering"), _rij(bestand="b.pdf", leverancier="B", **{"opmerking / vraag": "klopt dit?"}),
             _rij(bestand="c.pdf", leverancier="C", zekerheid="laag")]
    o = fki.beoordeel("x.csv", _csv(rijen, kop), _zip({"a.pdf": _pdf(1), "b.pdf": _pdf(2), "c.pdf": _pdf(3)}),
                      register=[], cfg=fin.fc.laad(), history_until="", standaarden={})
    assert _status(o) == [fki.WAARSCHUWING] * 3
    w = [x["waarschuwingen"][0] for x in o["rijen"]]
    assert "reminder" in w[0] and "question" in w[1] and "low" in w[2]
    assert o["totalen"]["EUR"]["aantal"] == 3


def test_ontbrekende_kolom_is_een_bestandsfout(tmp_path):
    dd = _dorp(tmp_path)
    o = fki.beoordeel("x.csv", _csv([_rij()], [k for k in KOP if k != "managementregel"]), b"",
                      register=[], cfg=fin.fc.laad(), history_until="", standaarden={})
    assert o["rijen"] == [] and "managementregel" in o["fouten"][0]


# ── cutover ─────────────────────────────────────────────────────────────────

def test_zonder_cutover_tellen_alle_rijen(tmp_path):
    dd = _dorp(tmp_path)
    soort, html = _preview(dd, [_rij(factuurdatum="2025-03-01")], {"a.pdf": _pdf(1)})
    assert "No cutover set: all 1 rows count in the P&amp;L." in html


def test_met_cutover_aantal_en_som_ervoor(tmp_path):
    dd = _dorp(tmp_path)
    Instellingen(dd).zet_history_until("2025-12", door="t")
    rijen = [_rij(factuurdatum="2025-03-01"), _rij(bestand="b.pdf", leverancier="B", factuurdatum="2026-01-05")]
    o = _oordeel(dd, rijen, {"a.pdf": _pdf(1), "b.pdf": _pdf(2)})
    assert o["cutover"] == {"tot": "2025-12", "aantal": 2, "voor_aantal": 1, "voor_excl": 10000}
    assert _status(o) == [fki.WAARSCHUWING, fki.NIEUW]
    soort, html = _preview(dd, rijen, {"a.pdf": _pdf(1), "b.pdf": _pdf(2)})
    assert "<strong>1</strong> of the 2 rows to import fall on or before it" in html


# ── betaald via, import_id, notitie ─────────────────────────────────────────

def test_betaald_via_staat_op_paid_telt_mee_en_is_zichtbaar(tmp_path):
    dd = _dorp(tmp_path)
    _preview(dd, [_rij(**{"betaald via": "Current account (director)"}),
                  _rij(bestand="b.pdf", leverancier="B")], {"a.pdf": _pdf(1), "b.pdf": _pdf(2)})
    _bevestig(dd)
    rc, bank = sorted(KostenRegister(dd).alle(), key=lambda r: r["supplier"], reverse=True)
    assert (rc["paid_via"], rc["payment_status"], rc["paid_date"]) == ("rc_directie", "paid", "")
    assert (bank["paid_via"], bank["payment_status"]) == ("", "open")
    # het P&L telt beide: `posten` is wat het P&L leest, en daar staat betaald via niet in
    from nooch_village.finance_register import posten
    assert sorted(posten(KostenRegister(dd).alle())) == [("2026-09", "purchased_goods", 10000, "register")] * 2
    # detailscherm, CSV en filter
    st = _st(dd)
    assert "Current account (director)" in fin.render_cost(st, "fc@t.nl", "t", rc["id"])
    assert "Nooch bank account" in fin.render_cost(st, "fc@t.nl", "t", bank["id"])
    csv = fin.csv_export(KostenRegister(dd).alle())
    assert csv.splitlines()[0].endswith(";paid_via;import_id") and ";rc_directie;" in csv
    alle = KostenRegister(dd).alle()
    assert [r["id"] for r in filter_regels(alle, betaald_via="rc_directie")] == [rc["id"]]
    assert [r["id"] for r in filter_regels(alle, betaald_via=BANK)] == [bank["id"]]
    assert "ff-betaald-via" in fin.render_costs(st, "fc@t.nl", "t", {})


def test_import_id_en_herkomst_in_de_notitie(tmp_path):
    dd = _dorp(tmp_path)
    _preview(dd, [_rij(**{"status in Basecone": "Verwerkt", "boekstuknummer": "INK-2026-041",
                          "opmerking / vraag": "contract 2026"})], {"a.pdf": _pdf(1)})
    iid = _laatste_id(dd)
    _bevestig(dd)
    (r,) = KostenRegister(dd).alle()
    assert r["import_id"] == iid and r["created_by"] == "fc"
    assert r["note"] == f"import:{iid} · Basecone: Verwerkt · Venema: INK-2026-041 · contract 2026"
    assert fki.KostenImportLog(dd).status(iid)["status"] == "applied"


def test_een_correctie_houdt_betaald_via_maar_niet_het_import_id(tmp_path):
    dd = _dorp(tmp_path)
    _preview(dd, [_rij(**{"betaald via": "rc_directie"})], {"a.pdf": _pdf(1)})
    _bevestig(dd)
    (r,) = KostenRegister(dd).alle()
    velden = {"action": "finance_kost_correct", "kid": r["id"], "entry_date": "2026-09-03", "supplier": "LTA",
              "description": "Strobel", "amount_excl": "90,00", "vat": "18,90", "management_line": "purchased_goods",
              "payment_status": "paid"}
    assert fin.verwerk_kost(_st(dd), velden, {}, username="fc@t.nl", door="fc").startswith("✓")
    nieuw = [x for x in KostenRegister(dd).alle() if not x.get("corrects") and x["id"] != r["id"]][0]
    assert nieuw["paid_via"] == "rc_directie" and nieuw["import_id"] == ""


# ── terugdraaien ────────────────────────────────────────────────────────────

def test_terugdraaien_annuleert_alleen_deze_import_en_laat_correcties_staan(tmp_path):
    dd = _dorp(tmp_path)
    _boek(dd, supplier="Handmatig")                           # niet uit een import
    _preview(dd, [_rij(), _rij(bestand="b.pdf", leverancier="B")], {"a.pdf": _pdf(1), "b.pdf": _pdf(2)})
    iid = _laatste_id(dd)
    _bevestig(dd)
    reg = KostenRegister(dd)
    a, b = [r for r in reg.alle() if r.get("import_id") == iid]
    reg.correctie(b["id"], {**{k: v for k, v in b.items() if k not in ("id", "created_at", "created_by")},
                            "amount_excl_cents": 5000, "import_id": ""}, door="fc")
    st = _st(dd)
    assert fin.verwerk_kosten_import_terug(st, {"import_id": iid}, door="fc").startswith("✗ tick the box")
    uit = fin.verwerk_kosten_import_terug(st, {"import_id": iid, "bevestig": "1"}, door="fc")
    assert "1 line(s) cancelled, 1 corrected line(s) left" in uit
    alle = reg.alle()
    storno = [r for r in alle if r.get("corrects") == a["id"]]
    assert len(storno) == 1 and storno[0]["note"] == f"Cancelled: import {iid} undone"
    assert sum(r["amount_excl_cents"] for r in alle if r["supplier"] == "Handmatig") == 10000
    assert sum(r["amount_excl_cents"] for r in alle if r["supplier"] == "B") == 5000   # de correctie blijft
    assert fki.KostenImportLog(dd).status(iid)["status"] == "undone"
    assert fin.verwerk_kosten_import_terug(st, {"import_id": iid, "bevestig": "1"}, door="fc").startswith("✗")


def test_na_terugdraaien_mag_dezelfde_import_opnieuw(tmp_path):
    dd = _dorp(tmp_path)
    _preview(dd, [_rij()], {"a.pdf": _pdf(1)})
    iid = _laatste_id(dd)
    _bevestig(dd)
    fin.verwerk_kosten_import_terug(_st(dd), {"import_id": iid, "bevestig": "1"}, door="fc")
    o = _oordeel(dd, [_rij()], {"a.pdf": _pdf(1)})
    assert _status(o) == [fki.NIEUW]


# ── leverancierstandaard ────────────────────────────────────────────────────

def test_leverancierstandaard_wordt_aangeboden_bewaard_en_alleen_genoemd(tmp_path):
    dd = _dorp(tmp_path)
    _preview(dd, [_rij()], {"a.pdf": _pdf(1)})
    _bevestig(dd)
    st = _st(dd)
    html = fin.render_kosten_import(st, "fc@t.nl", "t")
    assert "Save supplier defaults (1)" in html and "LTA|purchased_goods" in html
    assert fin.verwerk_leverancier_standaard(st, ["LTA|purchased_goods"], door="fc") == "✓ 1 supplier default(s) saved"
    assert open(os.path.join(dd, "finance", "supplier_defaults.jsonl")).read().count("\n") == 1
    assert "Save supplier defaults" not in fin.render_kosten_import(_st(dd), "fc@t.nl", "t")
    # genoemd, niet gekozen: een rij zonder regel blijft een fout, met de standaard in de reden
    o = _oordeel(dd, [_rij(bestand="b.pdf", managementregel="", factuurdatum="2026-09-04")], {"b.pdf": _pdf(2)})
    assert _status(o) == [fki.FOUT] and "the default for this supplier is Purchased goods" in o["rijen"][0]["redenen"][0]
    # en in het handmatige formulier ook
    velden = {"action": "finance_kost_add", "entry_date": "2026-09-05", "supplier": "lta", "description": "x",
              "amount_excl": "1", "vat": "0", "management_line": "", "payment_status": "open",
              "no_document_reason": "test"}
    assert "the default for lta is Purchased goods" in fin.verwerk_kost(_st(dd), velden, {}, username="fc@t.nl", door="fc")
    assert not (os.path.exists(os.path.join(os.path.dirname(fin.fc._PAD), "supplier_defaults.jsonl")))


# ── grenzen: grootte, rechten, geen lekken ──────────────────────────────────

def test_een_te_groot_bestand_geeft_de_vaste_melding_en_bewaart_niets(tmp_path):
    dd = _dorp(tmp_path)
    groot = b"PK" + b"0" * (LIMIET + 1)
    for files in ({"file": ("v.csv", _csv([_rij()])), "zip": ("p.zip", groot)},
                  {"file": ("v.xlsx", groot)}):
        soort, msg = fin.verwerk_kosten_import(_st(dd), {"action": "finance_kosten_import"}, files,
                                               door="fc", csrf="t", limiet=LIMIET)
        assert (soort, msg) == ("msg", "✗ File too large (limit 20 MB). Split the import by year.")
    assert fki.KostenImportLog(dd).imports() == []
    assert not os.path.isdir(os.path.join(dd, "finance", "imports"))


def test_rechten_fc_en_stefan_wel_anderen_404(tmp_path):
    import http.client
    import threading
    from http.server import HTTPServer
    from nooch_village import auth as _auth
    dd = _dorp(tmp_path)
    sessies = _auth.SessionStore()
    httpd = HTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, "T", sessions=sessies))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        for wie, verwacht in (("fc@t.nl", 200), ("stefan@nooch.earth", 200), ("bs@t.nl", 404), ("lid@t.nl", 404)):
            c = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=10)
            c.request("GET", "/finance/costs/import", headers={"Cookie": f"nv_session={sessies.create(wie)}"})
            r = c.getresponse()
            body = r.read().decode()
            assert r.status == verwacht, wie
            if verwacht == 404:
                assert "Import" not in body
    finally:
        httpd.shutdown()
    st = _st(dd)
    assert "/finance/costs/import" in fin.render_costs(st, "fc@t.nl", "t", {})
    assert "/finance/costs/import" not in fin.render_costs(st, "bs@t.nl", "t", {})
    for actie in ("finance_kosten_import_terug", "finance_leverancier_standaard"):
        with pytest.raises(cockpit2.NietGevonden):
            cockpit2.dispatch(dd, actie, {"import_id": ["x"], "bevestig": ["1"], "next": ["/"]}, username="bs@t.nl")


def test_een_geimporteerde_regel_duikt_nergens_anders_op(tmp_path):
    dd = _dorp(tmp_path)
    _preview(dd, [_rij(leverancier=MERK, omschrijving=MERK)], {"a.pdf": _pdf(1)})
    _bevestig(dd)
    st = _st(dd)
    from nooch_village import artefacts, noochie_memo
    from nooch_village.views.search import render_search_fragment
    from tests.test_finance_pr1 import BS, FC
    assert MERK not in render_search_fragment(st, MERK)
    for rol in (FC, BS):
        assert MERK not in artefacts.render_context_markdown(artefacts.serialize_context(rol, st.records, st.att))
    beeld, rapport = noochie_memo.verzamel(dd)
    assert MERK not in str(beeld) + str(rapport)
    # de geborgde bestanden staan buiten de webroot en buiten git
    for imp in fki.KostenImportLog(dd).imports():
        for b in (imp["attachment"], imp["zip"]):
            assert b["path"].startswith(os.path.join("finance", "imports"))
