"""Scope 56 — compliance zegt wat het vond en boekt 'niets gedaan' niet als resultaat.

Het patroon uit de skill-review van 12 september (batch C): "niets gedaan / kon niet" boekte als
resultaat, hulpvelden wonnen de inhoudsrace van de bevinding, het verslag kende de compliance-velden
niet, en twee Kroniek-lezers hadden twee waarheden. Deze tests toetsen wat de MENS merkt: de
classificatie (`Inhabitant._classify_result`), de wall-note (`_deliverable_note`), het verslag
(`project_verslag.inhoud_tekst`) en de plan-poort (`validate_payload`).
"""
from __future__ import annotations

import io
import json
import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nooch_village import claims_db
from nooch_village.inhabitant import Inhabitant as I
from nooch_village.project_verslag import inhoud_tekst

_PAD = (" Deze webpagina bevat verder algemene informatie over verzending, retourbeleid, "
        "klantenservice, maatvoering en de geschiedenis van het merk, puur als context. " * 2)


def _note(item_skill: str, result: dict) -> str:
    """De wall-note zoals de rol hem schrijft, zonder model (conclusiezin uit)."""
    inh = object.__new__(I)
    inh.context = SimpleNamespace(settings={"deliverable_conclusie_enabled": "0"}, rugzakken=None)
    inh.id = "compliance"
    status, archetype = I._classify_result(result)
    assert status == "gelukt", (status, result)
    return inh._deliverable_note({"text": "toets", "skill": item_skill}, result, archetype,
                                 source=item_skill)


# ══ claims_check ═════════════════════════════════════════════════════════════

def test_claims_check_lege_run_boekt_als_gemeld_leeg_met_de_lege_run_regel():
    from nooch_village.skills_impl.claims_check import ClaimsCheckSkill
    uit = ClaimsCheckSkill().run({"text": "Handgemaakt in Portugal, in kleine series."})
    assert I._classify_result(uit) == ("leeg", None)
    assert I._leeg_bron(uit) == "gemeld"                       # 📭 antwoord, geen kennisgat
    assert "GEEN goedkeuring" in uit["reason"]
    assert "toelichting" in uit and "betekenis" not in uit


def test_claims_check_de_rode_treffer_wint_van_de_disclaimers():
    """Gemeten in de review: 3 bevindingen (1 rood) en 4 betekenis-strings → de note toonde de
    disclaimers en verzweeg de rode treffer."""
    from nooch_village.skills_impl.claims_check import ClaimsCheckSkill
    uit = ClaimsCheckSkill().run({"text": "Onze zolen zijn plasticvrij en klimaatneutraal, "
                                          "100% recycled"})
    assert I._classify_result(uit) == ("gelukt", ("list", "bevindingen"))
    assert len(uit["toelichting"]) >= 3                        # de disclaimers zijn er nog wél
    note = _note("claims_check", uit)
    assert "klimaatneutraal" in note and "red" in note
    assert "VOORGESTELD alternatief" not in note.split("\n")[0:3][-1]
    assert uit["text"].startswith("3 findings: 1 red")


def test_claims_check_het_verslag_toont_stoplicht_bron_en_waarom():
    from nooch_village.skills_impl.claims_check import ClaimsCheckSkill
    uit = ClaimsCheckSkill().run({"text": "Onze 100% planet-safe sneakers."})
    tekst = inhoud_tekst(uit)
    regel = next(r for r in tekst.splitlines() if r.startswith("• planet-safe"))
    assert "red — source A" in regel and "found 'planet-safe'" in regel
    assert tekst.startswith(uit["text"])                       # de leeswijzer eerst


def test_claims_check_schrijft_zijn_eigen_kroniek_records():
    """Geen valse 'bevestigd, source=claims_check' meer uit de onderzoekspas-fallback: de skill
    beschrijft zelf zijn record — leeg bij niets, bevestigd mét result_ref bij treffers, en met een
    bron die in EIGEN_RUNS staat zodat hij nooit een claim op de site kan gronden."""
    from nooch_village.skills_impl.claims_check import ClaimsCheckSkill, KRONIEK_BRON
    from nooch_village.claims_substantiatie import EIGEN_RUNS
    s = ClaimsCheckSkill()
    leeg = s.evidence_records(s.run({"text": "Handgemaakt in Portugal."}), role_id="c")
    assert [r["status"] for r in leeg] == ["leeg"] and leeg[0]["source"] == KRONIEK_BRON
    vol = s.evidence_records(s.run({"text": "planet-safe sneakers"}), role_id="c")
    assert vol[0]["status"] == "bevestigd" and "planet-safe" in vol[0]["result_ref"]
    assert KRONIEK_BRON in EIGEN_RUNS
    assert s.evidence_records({"ok": False, "error": "x"}, role_id="c") == []


def test_claims_check_morfologische_variant_is_geen_andere_term():
    """'gerecycled' vs 'recycled' gaf een onterechte 'gaat over de term …, niet over de onderzochte
    claim' — fout, én hij maakte de toelichting langer."""
    from nooch_village.skills_impl.claims_check import betekenis_van
    basis = {"score": 95, "rood": 0, "oranje": 1, "groen": 0, "escaleren": 0}
    uit = betekenis_van({**basis, "bevindingen": [{"term": "gerecycled", "gevonden": ["recycled"]}]},
                        "Made with recycled materials")
    assert not any("niet over de onderzochte claim" in r for r in uit)
    uit = betekenis_van({**basis, "bevindingen": [{"term": "plasticvrij"}]},
                        "Together we are revolutionizing footwear")
    assert any("niet over de onderzochte claim" in r for r in uit)      # écht een andere term


def test_claims_check_description_is_engels_en_zegt_wat_leeg_betekent():
    from nooch_village.skills_impl.claims_check import ClaimsCheckSkill
    d = ClaimsCheckSkill.description
    assert "Checks text against" in d[:160] and "NOT an approval" in d
    assert "OR terms" in ClaimsCheckSkill.input_schema


# ══ claim_evidence ═══════════════════════════════════════════════════════════

def _ctx_ce():
    return SimpleNamespace(settings={"SERPAPI_API_KEY": "k"})


def _reason(a, o, c):
    payload = json.dumps({"claim_aanwezig": a, "onderbouwd": o, "citaat": c})
    return lambda prompt, **kw: payload


def test_claim_evidence_alle_merken_fout_blijft_open_met_reden():
    from nooch_village.skills_impl.claim_evidence import ClaimEvidenceSkill
    with patch("nooch_village.web_read.serpapi_search", lambda q, k, num=10: [{"link": "https://m.example"}]), \
         patch("nooch_village.web_read.fetch_text", return_value=""), \
         patch("nooch_village.llm.reason", _reason(True, True, "x")):
        res = ClaimEvidenceSkill().run({"brands": ["A", "B"], "claim": "afbreekbaar"}, _ctx_ce())
    assert I._classify_result(res) == ("fout", None)
    assert "no brand could be checked" in I._foutreden(res)
    # de mislukkingen zijn wél Kroniek-feiten (daarop leert de ladder)
    assert {r["status"] for r in ClaimEvidenceSkill().evidence_records(res, role_id="c")} == {"fout"}


def test_claim_evidence_alle_merken_leeg_is_gemeld_leeg():
    from nooch_village.skills_impl.claim_evidence import ClaimEvidenceSkill
    page = "Wij verkopen sneakers in vele kleuren. Gratis verzending." + _PAD
    with patch("nooch_village.web_read.serpapi_search", lambda q, k, num=10: [{"link": "https://m.example"}]), \
         patch("nooch_village.web_read.fetch_text", return_value=page), \
         patch("nooch_village.llm.reason", _reason(False, False, "")):
        res = ClaimEvidenceSkill().run({"brands": ["A"], "claim": "afbreekbaar"}, _ctx_ce())
    assert I._classify_result(res) == ("leeg", None) and I._leeg_bron(res) == "gemeld"
    assert "none of the 1 brand(s) makes the claim" in res["reason"]


def test_claim_evidence_string_brand_en_limit_cap():
    """`{"brands": "Veja"}` itereerde over de tekens: vier zoekopdrachten, vier credits."""
    from nooch_village.skills_impl.claim_evidence import ClaimEvidenceSkill, MAX_LIMIT
    queries, nums = [], []

    def zoek(q, k, num=10):
        queries.append(q); nums.append(num)
        return [{"link": f"https://veja.example/{i}"} for i in range(50)]
    page = "Onze zolen zijn gecertificeerd biodegradable volgens ISO 14855." + _PAD
    gelezen = []
    with patch("nooch_village.web_read.serpapi_search", zoek), \
         patch("nooch_village.web_read.fetch_text", side_effect=lambda u: gelezen.append(u) or page), \
         patch("nooch_village.llm.reason", _reason(True, False, "gecertificeerd biodegradable volgens ISO 14855")):
        res = ClaimEvidenceSkill().run({"brands": "Veja", "claim": "biodegradable", "limit": 40}, _ctx_ce())
    assert queries == ["Veja biodegradable"]
    assert len(gelezen) <= MAX_LIMIT                            # geen 40 pagina's
    assert res["rows"][0]["status"] == "onduidelijk"


def test_claim_evidence_het_verslag_leest_merk_url_oordeel_en_citaat():
    from nooch_village.skills_impl.claim_evidence import ClaimEvidenceSkill
    page = "Onze zolen zijn gecertificeerd biodegradable volgens ISO 14855, labresultaat bijgevoegd." + _PAD
    with patch("nooch_village.web_read.serpapi_search", lambda q, k, num=10: [{"link": "https://veja.example/duurzaam"}]), \
         patch("nooch_village.web_read.fetch_text", return_value=page), \
         patch("nooch_village.llm.reason", _reason(True, True, "gecertificeerd biodegradable volgens ISO 14855")):
        res = ClaimEvidenceSkill().run({"brands": ["Veja"], "claim": "biodegradable"}, _ctx_ce())
    regel = [r for r in inhoud_tekst(res).splitlines() if r.startswith("• Veja")][0]
    assert "https://veja.example/duurzaam" in regel and "confirmed" in regel
    assert "ISO 14855" in regel
    assert res["text"].startswith("'biodegradable' checked for 1 brand(s)")
    row = res["rows"][0]
    assert row["url"] == row["source"] and row["citaat"] == row["evidence"]   # additief


# ══ cert_evidence ════════════════════════════════════════════════════════════

CERT = """CERTIFICATE OF ANALYSIS
Issued by: SGS Netherlands B.V.
Supplier: Recyclon Fibers GmbH
Material: rPET yarn, component level
Certifies that: the yarn contains 70% post-consumer recycled PET
Valid until: 2099-06-30
"""


def _mini_pdf(regels: list[str]) -> bytes:
    """Een minimale PDF met één tekstpagina (ongecomprimeerd), zodat pypdf de tekstlaag vindt."""
    def esc(s):
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    inhoud = "BT /F1 12 Tf 40 750 Td 14 TL " + " ".join(f"({esc(r)}) Tj T*" for r in regels) + " ET"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> "
        "/Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(inhoud.encode('latin-1'))} >>\nstream\n{inhoud}\nendstream",
    ]
    uit = io.BytesIO()
    uit.write(b"%PDF-1.4\n")
    offsets = []
    for n, o in enumerate(objs, 1):
        offsets.append(uit.tell())
        uit.write(f"{n} 0 obj\n{o}\nendobj\n".encode("latin-1"))
    xref = uit.tell()
    uit.write(f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode())
    for off in offsets:
        uit.write(f"{off:010d} 00000 n \n".encode())
    uit.write(f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return uit.getvalue()


def _certmap(tmp_path):
    from nooch_village import cert_register as cr
    os.makedirs(cr.pad(str(tmp_path)), exist_ok=True)
    return cr.pad(str(tmp_path))


def test_cert_evidence_schrijft_in_de_daemon_context_wel_een_record(tmp_path):
    """De productie-`Context` heeft geen `evidence`-attribuut; tot scope 56 schreef de skill daar
    NOOIT een record ("✘ geen ledger beschikbaar"). Nu resolvet hij de Kroniek zoals de site-scan."""
    from nooch_village.config import Context
    from nooch_village.skills_impl.cert_evidence import CertEvidenceSkill
    ctx = Context(data_dir=str(tmp_path), settings={})
    assert not hasattr(ctx, "evidence")
    uit = CertEvidenceSkill().run({"text": CERT, "claims": ["Recycled, recycled"]}, ctx)
    assert uit["ok"] and uit["geschreven"] and uit["record_id"]
    rijen = [json.loads(r) for r in open(tmp_path / "evidence_ledger.jsonl", encoding="utf-8")]
    assert rijen[0]["source"] == "external_certificate" and rijen[0]["id"] == uit["record_id"]
    assert I._classify_result(uit)[0] == "gelukt"
    assert "SGS" in uit["text"] and "2099-06-30" in uit["text"]


def test_cert_evidence_leest_een_pdf_met_tekstlaag(tmp_path):
    from nooch_village.skills_impl.cert_evidence import CertEvidenceSkill
    (tmp_path / "certificaten" / "sgs.pdf").parent.mkdir(exist_ok=True)
    (tmp_path / "certificaten" / "sgs.pdf").write_bytes(_mini_pdf(CERT.strip().splitlines()))
    ctx = SimpleNamespace(data_dir=str(tmp_path), settings={})
    uit = CertEvidenceSkill().run({"bestand": "sgs.pdf"}, ctx)
    assert uit["ok"] and uit["cert"]["ontbreekt"] == []
    assert uit["cert"]["geldig_tot"] == "2099-06-30" and uit["cert"]["instantie"].startswith("SGS")
    assert uit["cert"]["bron_pdf"] == "sgs.pdf"


def test_cert_evidence_een_scan_zonder_tekstlaag_is_een_fout(tmp_path):
    from pypdf import PdfWriter
    from nooch_village.skills_impl.cert_evidence import CertEvidenceSkill
    map_ = _certmap(tmp_path)
    w = PdfWriter()
    w.add_blank_page(width=200, height=200)
    with open(os.path.join(map_, "scan.pdf"), "wb") as fh:
        w.write(fh)
    uit = CertEvidenceSkill().run({"bestand": "scan.pdf"}, SimpleNamespace(data_dir=str(tmp_path)))
    assert I._classify_result(uit) == ("fout", None) and "tekstlaag" in uit["error"]


def test_cert_evidence_niet_geschreven_is_niet_gelukt(tmp_path):
    from nooch_village.skills_impl.cert_evidence import CertEvidenceSkill
    ctx = SimpleNamespace(data_dir=str(tmp_path))
    uit = CertEvidenceSkill().run({"text": "Material: leer"}, ctx)          # feit + datum ontbreken
    assert I._classify_result(uit) == ("fout", None)
    assert "feit" in uit["error"] and not uit["geschreven"]
    assert not os.path.exists(tmp_path / "evidence_ledger.jsonl")
    zonder = CertEvidenceSkill().run({"text": CERT}, None)                  # geen Kroniek te vinden
    assert zonder["ok"] is False and "Kroniek" in zonder["error"]


def test_cert_evidence_een_verlopen_certificaat_wordt_als_zodanig_gemeld(tmp_path):
    from nooch_village.skills_impl.cert_evidence import CertEvidenceSkill
    ctx = SimpleNamespace(data_dir=str(tmp_path))
    uit = CertEvidenceSkill().run({"text": CERT.replace("2099-06-30", "2020-01-01"),
                                   "claims": ["recycled"]}, ctx)
    assert uit["ok"] and uit["verlopen"] is True
    assert any("verlopen (2020-01-01)" in r for r in uit["let_op"])
    assert "EXPIRED" in uit["text"]
    assert "EXPIRED" in _note("cert_evidence", uit)


def test_cert_evidence_validate_payload_vangt_een_verzonnen_bestand(tmp_path):
    from nooch_village.skills_impl.cert_evidence import CertEvidenceSkill
    map_ = _certmap(tmp_path)
    open(os.path.join(map_, "echt.txt"), "w", encoding="utf-8").write(CERT)
    ctx = SimpleNamespace(data_dir=str(tmp_path))
    s = CertEvidenceSkill()
    assert s.validate_payload({"bestand": "echt.txt"}, ctx) == []
    assert any("bestaat niet" in r for r in s.validate_payload({"bestand": "spook.pdf"}, ctx))
    assert s.validate_payload({"bestand": "spook.pdf"}, None) == []        # zonder data_dir: fail-soft
    assert s.validate_payload({}, None)


# ══ claims_substantiatie / claim_oordeel — één bewijslezer ═══════════════════

def _bev(term="plasticvrij / plastic-free", gevonden=("plastic-free",), stoplicht="orange"):
    return {"term": term, "gevonden": list(gevonden), "stoplicht": stoplicht, "categorie": "x",
            "waarom": "vraagt bewijs", "alternatief": "", "pagina": "home", "url": "https://nooch.earth/"}


def test_eigen_run_records_gronden_op_de_site_geen_claim_meer(tmp_path):
    """De site-scan las een record `source=claims_check, status=bevestigd` (zoals de onderzoekspas
    er bij élke run een schreef) als bewijs — de groene claim viel weg."""
    from nooch_village import claims_substantiatie as subst
    from nooch_village.evidence_ledger import EvidenceLedger
    led = EvidenceLedger(str(tmp_path / "evidence_ledger.jsonl"))
    for bron in ("claims_check", "claims_db", "escaleer"):
        led.record(role_id="compliance", skill=bron, query="nooch — plastic-free", source=bron,
                   status="bevestigd", result_ref="plastic-free (orange)")
    b = _bev(stoplicht="green", term="plasticvrij", gevonden=["plastic-free"])
    subst.pas_toe([b], ledger=led, db=claims_db.load())
    assert b["onderbouwing"] == subst.ONTBREEKT and b["stoplicht"] == "orange"
    assert "eigen skill-run" in b["onderbouwing_reden"]


def test_een_verlopen_certificaat_grondt_op_de_site_geen_claim_meer(tmp_path):
    from nooch_village import cert_register as cr, claims_substantiatie as subst
    from nooch_village.evidence_ledger import EvidenceLedger
    led = EvidenceLedger(str(tmp_path / "evidence_ledger.jsonl"))
    for tot in ("2020-01-01", ""):
        led.record(role_id="compliance", skill=cr.SKILL, query="nooch plastic-free upper", source=cr.EXTERN,
                   status="bevestigd", result_ref="sgs.pdf",
                   meta={"geldig_tot": tot, "feit": "nooch plastic-free upper", "subject": "nooch"})
    b = _bev()
    subst.pas_toe([b], ledger=led, db=claims_db.load())
    assert b["onderbouwing"] == subst.ONTBREEKT
    assert "verlopen of ongedateerd" in b["onderbouwing_reden"]
    geldig = EvidenceLedger(str(tmp_path / "geldig.jsonl"))
    geldig.record(role_id="compliance", skill=cr.SKILL, query="nooch plastic-free upper", source=cr.EXTERN,
                  status="bevestigd", result_ref="sgs.pdf",
                  meta={"geldig_tot": "2099-01-01", "feit": "nooch plastic-free upper", "subject": "nooch"})
    b2 = _bev()
    subst.pas_toe([b2], ledger=geldig, db=claims_db.load())
    assert b2["onderbouwing"] == subst.ONDERBOUWD               # een geldig cert draagt wél


def test_claim_oordeel_verwijst_naar_dezelfde_filter():
    from nooch_village import claim_oordeel as co, claims_substantiatie as subst
    assert co.EIGEN_RUNS is subst.EIGEN_RUNS
    bewijs = {"records": [{"id": "K1", "source": "claims_check"},
                          {"id": "K2", "source": "leverancierscertificaat"}]}
    assert [r["id"] for r in co.externe_records(bewijs)] == ["K2"]
    assert [r["id"] for r in subst.externe_records(bewijs["records"])] == ["K2"]


# ══ claims_site_scan ═════════════════════════════════════════════════════════

_PAGINA = """<html><head><title>Nooch</title></head><body>
<p>Our shoes are plastic-free and vegan.</p></body></html>"""


def _scan_ctx(tmp_path, monkeypatch):
    from nooch_village.projects import ProjectLedger
    kopie = tmp_path / "claims_database.json"
    kopie.write_text(json.dumps(claims_db.load(), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(claims_db, "DB_PATH", str(kopie))
    return SimpleNamespace(data_dir=str(tmp_path), settings={}, records=None,
                           projects=ProjectLedger(str(tmp_path / "projects.json")), evidence_ledger=None)


def test_site_scan_skipped_leest_als_gemeld_niet_als_kennisgat(tmp_path, monkeypatch):
    """Het merendeel van de 45 'lege' scan-items uit de review: de week was al gedaan, en dat las
    als 🕳 kennisgat omdat de skipped-vorm alleen `ok`/`reden` droeg."""
    from nooch_village.skills_impl.claims_site_scan import ClaimsSiteScanSkill
    ctx = _scan_ctx(tmp_path, monkeypatch)
    ClaimsSiteScanSkill().run({"_fetch": lambda u: (200, _PAGINA), "_sleep": lambda s: None,
                               "modelpas": False}, ctx)
    tweede = ClaimsSiteScanSkill().run({"_fetch": lambda u: (200, _PAGINA), "_sleep": lambda s: None,
                                        "modelpas": False}, ctx)
    assert tweede["skipped"] is True and tweede["reden"]          # de pulslaag leest dit nog
    assert I._classify_result(tweede) == ("leeg", None)
    assert I._leeg_bron(tweede) == "gemeld"
    assert "this week's scan: 5 of 5 page(s) covered" in tweede["reason"]


def test_site_scan_deelrun_zonder_bevinding_is_gemeld_leeg_met_dekking(tmp_path, monkeypatch):
    """Een deelrun met één 429 en 0 nieuwe bevindingen boekte als 'gelukt' met de paginalabels
    als "2 results" — de administratieve lijsten wonnen de inhoudsrace."""
    from nooch_village import safe_fetch
    from nooch_village.skills_impl.claims_site_scan import ClaimsSiteScanSkill
    ctx = _scan_ctx(tmp_path, monkeypatch)
    schoon = "<html><body><p>Handmade in Portugal.</p></body></html>"

    def fetch(url):
        if "mission" in url:
            raise safe_fetch.FetchMislukt("de pagina gaf HTTP 429", status=429)
        return (200, schoon)
    uit = ClaimsSiteScanSkill().run({"_fetch": fetch, "_sleep": lambda s: None, "modelpas": False}, ctx)
    assert uit["ok"] and uit["volledig"] is False
    assert I._classify_result(uit) == ("leeg", None) and I._leeg_bron(uit) == "gemeld"
    assert "4 of 5 covered this week" in uit["reason"] and "1 page(s) not fetched (mission)" in uit["reason"]
    assert set(uit["_scan"]) >= {"gedekt", "fouten", "statussen", "gewhitelist", "gaten"}
    assert "gedekt" not in uit and "fouten" not in uit             # niet meer op topniveau


def test_site_scan_met_bevinding_toont_de_bevinding_niet_de_paginalabels(tmp_path, monkeypatch):
    from nooch_village.skills_impl.claims_site_scan import ClaimsSiteScanSkill
    ctx = _scan_ctx(tmp_path, monkeypatch)
    pagina = "<html><body><p>Onze schoenen zijn volstrekt gifvrij en biologisch afbreekbaar.</p></body></html>"
    uit = ClaimsSiteScanSkill().run({"_fetch": lambda u: (200, pagina), "_sleep": lambda s: None,
                                     "modelpas": False}, ctx)
    assert uit["nieuw"] >= 1
    assert I._classify_result(uit) == ("gelukt", ("list", "aangemaakt"))
    rec = uit["aangemaakt"][0]
    assert rec["url"].startswith("https://nooch.earth") and rec["oordeel"].startswith(rec["stoplicht"])
    assert "on page" in rec["citaat"]
    verslag = inhoud_tekst(uit)
    assert "https://nooch.earth" in verslag and "red" in verslag
    assert "new finding(s)" in uit["text"]


def test_site_scan_escalatie_blijft_een_fout(tmp_path, monkeypatch):
    from nooch_village import safe_fetch
    from nooch_village.skills_impl.claims_site_scan import ClaimsSiteScanSkill
    ctx = _scan_ctx(tmp_path, monkeypatch)

    def kapot(url):
        raise safe_fetch.FetchMislukt("de pagina gaf HTTP 503", status=503)
    uit = ClaimsSiteScanSkill().run({"_fetch": kapot, "_sleep": lambda s: None, "modelpas": False}, ctx)
    assert uit["ok"] is False and I._classify_result(uit)[0] == "fout"
    assert "geen enkele pagina" in I._foutreden(uit)


# ══ regulation_watch ═════════════════════════════════════════════════════════

def _rw_ctx(tmp_path, bronnen):
    import sys
    from nooch_village.projects import ProjectLedger
    sys.path.insert(0, os.path.dirname(__file__))
    from test_claims_v3 import _records_dubbel
    return SimpleNamespace(data_dir=str(tmp_path), settings={"regulation_sources": bronnen},
                           projects=ProjectLedger(str(tmp_path / "p.json")), records=_records_dubbel())


def _fetch_half(url):
    from nooch_village import safe_fetch
    if "acm" in url:
        raise safe_fetch.FetchMislukt("timeout")
    return (200, b"<html><body>wettekst</body></html>", "text/html")


def test_regulation_watch_een_mislukte_meting_krijgt_de_volgende_puls_een_nieuwe_kans(tmp_path):
    from nooch_village.skills_impl import regulation_watch as rw
    ctx = _rw_ctx(tmp_path, "A | EU | https://eur-lex.europa.eu/x\nB | ACM | https://www.acm.nl/y\n")
    eerste = rw.RegulationWatchSkill().run({"_maand": "2026-06", "_fetch": _fetch_half}, ctx)
    assert eerste["ok"] and eerste["gemeten"] == 1
    assert "bron niet gemeten — ACM" in eerste["headsup"] and "poging 1/5" in eerste["headsup"]
    assert I._classify_result(eerste) == ("leeg", None)          # niets gewijzigd = antwoord
    tweede = rw.RegulationWatchSkill().run({"_maand": "2026-06", "_fetch": _fetch_half}, ctx)
    assert tweede["skipped"] is False                            # ACM opnieuw, EU niet nog eens
    assert tweede["fouten"] and tweede["headsup"] is None        # tussendoor stil (alleen het log)
    assert "twee maanden" not in str(tweede.get("escalate"))
    rijen = rw.lees_log(str(tmp_path))
    assert sum(1 for r in rijen if "eur-lex" in r["url"]) == 1  # de geslaagde bron niet herhaald


def test_regulation_watch_geeft_op_na_max_pogingen_en_zegt_dat(tmp_path):
    from nooch_village.skills_impl import regulation_watch as rw
    ctx = _rw_ctx(tmp_path, "A | EU | https://eur-lex.europa.eu/x\nB | ACM | https://www.acm.nl/y\n")
    laatste = None
    for _ in range(rw.MAX_POGINGEN_PER_MAAND):
        laatste = rw.RegulationWatchSkill().run({"_maand": "2026-06", "_fetch": _fetch_half}, ctx)
    assert f"opgegeven na {rw.MAX_POGINGEN_PER_MAAND} pogingen" in laatste["headsup"]
    daarna = rw.RegulationWatchSkill().run({"_maand": "2026-06", "_fetch": _fetch_half}, ctx)
    assert daarna["skipped"] is True and daarna["no_data"] is True
    assert "opgegeven" in daarna["reason"] and "ACM" in daarna["reason"]
    assert rw.maand_gedaan(rw.lees_log(str(tmp_path)), "2026-06", rw.parse_bronnen(ctx.settings))
    assert rw.MAX_POGINGEN_PER_MAAND == 5


def test_regulation_watch_maand_gedaan_telt_alleen_geslaagde_metingen():
    from nooch_village.skills_impl import regulation_watch as rw
    fout = [{"soort": "meting", "maand": "2026-06", "url": "u", "status": "fout"}]
    assert rw.maand_gedaan(fout, "2026-06") is False
    assert rw.maand_gedaan(fout + [{"soort": "meting", "maand": "2026-06", "url": "u", "status": "ok"}],
                           "2026-06") is True


def test_regulation_watch_beide_mijlpalen_komen_naast_elkaar(tmp_path, monkeypatch):
    """De dedupe op `sleutel.split("|")[0]` liet de NL-omzettingsmijlpaal nooit ontstaan zolang de
    EmpCo-handhavingstaak open stond — beide deelden de basis 'mijlpaal'."""
    from nooch_village.skills_impl import regulation_watch as rw
    monkeypatch.setattr(rw, "HANDHAVING_MAAND", "2000-01")
    ctx = _rw_ctx(tmp_path, "A | NL-omzetting EmpCo (Stb. 2026) | https://www.acm.nl/wet\n")
    fetch = lambda url: (200, b"<html><body>x</body></html>", "text/html")   # noqa: E731
    uit = rw.RegulationWatchSkill().run({"_maand": "2026-06", "_fetch": fetch}, ctx)
    titels = [t["titel"] for t in uit["aangemaakt"]]
    assert any("EmpCo-handhaving" in t for t in titels) and any("NL-wettekst" in t for t in titels)
    weer = rw.RegulationWatchSkill().run({"_maand": "2026-06", "force": True, "_fetch": fetch}, ctx)
    assert weer["aangemaakt"] == []                                # en niet nog een keer


# ══ content_check ════════════════════════════════════════════════════════════

def _cc_ctx(tmp_path=None, rules="REGELS"):
    from nooch_village.notes_store import NotesStore
    from nooch_village.insight import Insight, GroundingStatus, EvidenceType
    store = None
    if tmp_path is not None:
        store = NotesStore(str(tmp_path / "notes.json"))
        if store.get("v") is None:                                  # één store per test, hergebruikt
            store.add(Insight(id="v", claim="c", source="t", status=GroundingStatus.VERIFIED, grounds="g",
                              warrant="w", rebuttal="r", evidence_type=EvidenceType.PEER_REVIEWED))
    return SimpleNamespace(notes=store, copy_rules=rules, data_dir=None)


def test_content_check_rode_empco_term_wordt_ook_in_een_blog_gestopt(tmp_path):
    from nooch_village.skills_impl.content_check import ContentCheckSkill
    with patch("nooch_village.llm.reason", return_value='{"compliant": true, "issues": []}'):
        uit = ContentCheckSkill().run({"text": "Onze duurzame sneaker.", "kind": "blog"}, _cc_ctx(tmp_path))
    assert uit["gate_ok"] is False and any("duurzaam" in w for w in uit["forbidden_words"])
    assert I._classify_result(uit) == ("gelukt", ("list", "bevindingen"))
    regel = inhoud_tekst(uit).splitlines()[1]
    assert "red — blocked — source A+B" in regel and "found 'duurzame'" in regel


def test_content_check_verboden_woord_valt_ook_zonder_store(tmp_path):
    from nooch_village.skills_impl.content_check import ContentCheckSkill
    with patch("nooch_village.llm.reason", return_value='{"compliant": true, "issues": []}'):
        uit = ContentCheckSkill().run({"text": "Gemaakt van plastic.", "kind": "sales_page"}, _cc_ctx(None))
    assert uit["forbidden_words"] == ["plastic"] and uit["gate_ok"] is False
    assert uit["ok"] is True and uit["niet_getoetst"] == []


def test_content_check_niets_gevonden_maar_laag_niet_gedraaid_is_niet_getoetst(tmp_path):
    from nooch_village.skills_impl.content_check import ContentCheckSkill
    with patch("nooch_village.llm.reason", return_value=None):
        geen_model = ContentCheckSkill().run({"text": "Een schone tekst."}, _cc_ctx(tmp_path))
    assert geen_model["ok"] is False and "no model" in geen_model["error"]
    geen_regels = ContentCheckSkill().run({"text": "Een schone tekst."}, _cc_ctx(tmp_path, rules=""))
    assert geen_regels["ok"] is False and "no copy_rules" in geen_regels["error"]
    with patch("nooch_village.llm.reason", return_value='{"compliant": true, "issues": []}'):
        geen_store = ContentCheckSkill().run({"text": "Een schone tekst.", "kind": "sales_page",
                                              "claim_insight_ids": ["v"]}, _cc_ctx(None))
    assert geen_store["ok"] is False and "no notes store" in geen_store["error"]
    for uit in (geen_model, geen_regels, geen_store):
        assert I._classify_result(uit)[0] == "fout" and "niet getoetst" in I._foutreden(uit)


def test_content_check_schoon_met_alle_lagen_is_gemeld_leeg_en_ok_is_geen_suggestie(tmp_path):
    from nooch_village.skills_impl.content_check import ContentCheckSkill
    for antwoord in ("OK.", '{"compliant": true, "issues": []}'):
        with patch("nooch_village.llm.reason", return_value=antwoord):
            uit = ContentCheckSkill().run({"text": "Een schone tekst.", "kind": "sales_page",
                                           "claim_insight_ids": ["v"]}, _cc_ctx(tmp_path))
        assert uit["suggestions"] is None
        assert uit["no_data"] is True and I._leeg_bron(uit) == "gemeld"
        assert "claim card(s)" in uit["reason"] and "copy rules" in uit["reason"]


def test_content_check_onbekende_kind_sneuvelt_bij_plannen_en_bij_draaien():
    from nooch_village.skills_impl.content_check import ContentCheckSkill
    s = ContentCheckSkill()
    assert s.required_payload == ("text",)
    assert any("blog, sales_page, passport" in r for r in s.validate_payload({"text": "x", "kind": "landing"}, None))
    uit = s.run({"text": "x", "kind": "landing"}, _cc_ctx(None))
    assert uit["ok"] is False and "sales_page" in uit["error"]
    assert "'blog' | 'sales_page' | 'passport'" in s.input_schema
    assert s.description.startswith("Final check of a public text")


def test_content_check_prompt_is_engels_met_json_en_ladder(tmp_path):
    from nooch_village.skills_impl.content_check import ContentCheckSkill, _PROMPT
    assert "only on the rules and the text below" in _PROMPT and '"compliant"' in _PROMPT
    gezien = {}

    def vang(prompt, **kw):
        gezien.update(kw)
        return '{"compliant": false, "issues": ["Too long"]}'
    with patch("nooch_village.llm.reason", vang):
        uit = ContentCheckSkill().run({"text": "T.", "ladder": "premium"}, _cc_ctx(tmp_path))
    assert gezien["json_mode"] is True and gezien["ladder"] == "premium" and gezien["max_tokens"] >= 500
    assert uit["suggestions"] == "Too long"
    assert uit["bevindingen"][-1] == {"term": "copy rules", "oordeel": "advice", "citaat": "Too long"}


def test_find_forbidden_words_gebruikt_de_database_met_de_literals_als_vangnet(monkeypatch):
    from nooch_village import publication_check as pc
    assert pc.find_forbidden_words("Onze planet-safe plastic zool", pc.FORBIDDEN_IN_SALES) == [
        "plastic", "planet-safe / planet-friendly / planet-loving"]
    monkeypatch.setattr(claims_db, "DB_PATH", "/nergens/claims.json")
    assert pc.find_forbidden_words("Onze planet-safe plastic zool", pc.FORBIDDEN_IN_SALES) == ["plastic"]
    rapport = pc.review_publication("Onze plastic zool", [], pc.PublicationKind.SALES_PAGE, None)
    assert rapport.database_ok is False and rapport.forbidden_words == ["plastic"]


# ══ accountability_check ═════════════════════════════════════════════════════

def test_accountability_check_storing_is_geen_oordeel(tmp_path):
    from nooch_village import cockpit2
    from nooch_village.skills_impl.accountability_check import check_accountabilities
    rollen = [{"role": "A", "accountabilities": ["x doen"]}]
    res = check_accountabilities(rollen, reason_fn=lambda p: None)
    assert res["ok"] is False and "geen antwoord" in res["reden"]
    assert res["n_roles"] == 1 and res["at"] > 0
    afgekapt = check_accountabilities(rollen, reason_fn=lambda p: '{"duplicates": [{"acc')
    assert afgekapt["ok"] is False and "niet leesbaar" in afgekapt["reden"]
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    with open(os.path.join(dd, "accountability_check.json"), "w", encoding="utf-8") as f:
        json.dump(res, f)
    html = cockpit2.render_accountabilities(st, dd, csrf_token="t")
    assert "The check could not run" in html and "No duplicates found" not in html
    assert "Last run:" in html and "1 roles checked" in html


def test_accountability_check_actie_geeft_capaciteit_en_zegt_storing(tmp_path, monkeypatch):
    from nooch_village import cockpit2, llm
    from nooch_village.skills_impl.accountability_check import MAX_TOKENS
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    gezien = {}

    def vang(prompt, **kw):
        gezien.update(kw)
        return None
    monkeypatch.setattr(llm, "reason", vang)
    _, msg = cockpit2.dispatch(dd, "acc_check", {"next": ["/accountabilities"]}, "guest")
    assert gezien["max_tokens"] == MAX_TOKENS == 3000 and gezien["json_mode"] is True
    assert "kon niet draaien" in msg
    opgeslagen = json.load(open(os.path.join(dd, "accountability_check.json"), encoding="utf-8"))
    assert opgeslagen["ok"] is False and "at" in opgeslagen and "n_roles" in opgeslagen
    monkeypatch.setattr(llm, "reason", lambda p, **kw: '{"duplicates": [], "weak": []}')
    _, msg = cockpit2.dispatch(dd, "acc_check", {"next": ["/accountabilities"]}, "guest")
    assert msg.startswith("check klaar: 0 aandachtspunt(en) over")
