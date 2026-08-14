"""Certificaten als extern bewijs, en de wachtlijst die eruit volgt.

De claim-pas kwam op nul compliant omdat elk 'bevestigd' record in de Kroniek een eigen skill-run
als bron had. Een certificaat is het bewijs dat wél van buiten komt — mits het als zodanig
herkenbaar is, en mits het nog geldt.

Deze tests bewaken drie dingen, en alle drie falen bewust naar de veilige kant:

  - een veld dat niet gelezen kan worden blijft LEEG (geen verzonnen vervaldatum, geen
    gereconstrueerd feit);
  - een cert zonder feit of zonder datum levert GEEN bewijsrecord;
  - een verlopen of ongedateerd cert draagt niets meer — de goedkeuring mag zijn bewijs niet
    overleven.
"""
from __future__ import annotations

from nooch_village import cert_register as cr


CERT = """CERTIFICATE OF ANALYSIS
Issued by: SGS Netherlands B.V.
Supplier: Recyclon Fibers GmbH
Material: rPET yarn, component level
Certifies that: the yarn contains 70% post-consumer recycled PET
Valid until: 2099-06-30
"""


# ── Lezen, en eerlijk leeg laten ────────────────────────────────────────────

def test_een_volledig_certificaat_wordt_gelezen():
    c = cr.lees_cert(CERT, bron_pdf="sgs-rpet.pdf")
    assert "70% post-consumer recycled PET" in c["feit"]
    assert c["instantie"].startswith("SGS")
    assert c["leverancier"].startswith("Recyclon")
    assert c["geldig_tot"] == "2099-06-30"
    assert c["niveau"] == "component"
    assert c["bron_pdf"] == "sgs-rpet.pdf"
    assert c["ontbreekt"] == []


def test_een_onleesbare_datum_wordt_niet_geraden():
    """Een geraden vervaldatum is geen bewijs maar een risico met een stempel erop."""
    c = cr.lees_cert("Certifies that: iets\nValid until: ergens in de zomer")
    assert c["geldig_tot"] == ""
    assert "geldig_tot" in c["ontbreekt"]


def test_ontbrekende_velden_staan_expliciet_in_ontbreekt():
    c = cr.lees_cert("Material: leer")
    assert set(c["ontbreekt"]) == {"feit", "instantie", "geldig_tot"}


# ── De geldigheid is een vergelijking, geen stempel ─────────────────────────

def test_verlopen_is_een_vergelijking_met_vandaag():
    assert cr.verlopen({"geldig_tot": "2020-01-01"}, vandaag="2026-08-15") is True
    assert cr.verlopen({"geldig_tot": "2099-01-01"}, vandaag="2026-08-15") is False


def test_zonder_datum_is_de_uitkomst_onbekend_niet_geldig():
    """None is nadrukkelijk niet False — anders leest 'geen datum' als 'nog geldig'."""
    assert cr.verlopen({"geldig_tot": ""}) is None


# ── Naar de Kroniek, met een herkomst die niet van onszelf is ───────────────

class _Ledger:
    def __init__(self):
        self.rows = []

    def record(self, **kw):
        row = dict(kw, id=f"K{len(self.rows)}")
        self.rows.append(row)
        return row

    def all_records(self):
        return list(self.rows)


def test_het_bewijsrecord_draagt_de_externe_herkomst():
    """Precies het punt: `external_certificate` is iets anders dan claims_check of escaleer."""
    led = _Ledger()
    r = cr.naar_evidence(cr.lees_cert(CERT, bron_pdf="sgs.pdf"), led)
    assert r["source"] == cr.EXTERN and r["status"] == "bevestigd"
    assert r["skill"] == "cert_evidence" and r["result_ref"] == "sgs.pdf"
    assert r["meta"]["geldig_tot"] == "2099-06-30"


def test_geen_feit_geen_record(caplog):
    led = _Ledger()
    with caplog.at_level("WARNING"):
        assert cr.naar_evidence({"geldig_tot": "2099-01-01", "feit": ""}, led) is None
    assert led.rows == [] and "geen leesbaar feit" in caplog.text


def test_geen_vervaldatum_geen_record(caplog):
    led = _Ledger()
    with caplog.at_level("WARNING"):
        assert cr.naar_evidence({"feit": "iets", "geldig_tot": ""}, led) is None
    assert led.rows == []


# ── De wachtlijst ───────────────────────────────────────────────────────────

def _met_cert(claims, geldig_tot="2099-01-01"):
    led = _Ledger()
    cert = cr.lees_cert(CERT, bron_pdf="sgs.pdf")
    cert["claims"] = list(claims)
    cert["geldig_tot"] = geldig_tot
    cr.naar_evidence(cert, led)
    return led


def test_een_gedekte_claim_is_onderbouwd():
    led = _met_cert(["Recycled, recycled"])
    rij = cr.wachtlijst(["Recycled, recycled"], led, vandaag="2026-08-15")[0]
    assert rij["status"] == "onderbouwd" and "SGS" in rij["reden"]


def test_een_ongedekte_claim_is_pending_met_een_opdracht():
    led = _met_cert(["iets anders"])
    rij = cr.wachtlijst(["compensated"], led, vandaag="2026-08-15")[0]
    assert rij["status"] == "pending"
    assert "haal een certificaat op" in cr.opdracht(rij)


def test_een_verlopen_cert_maakt_de_claim_weer_pending():
    led = _met_cert(["Recycled, recycled"], geldig_tot="2020-01-01")
    rij = cr.wachtlijst(["Recycled, recycled"], led, vandaag="2026-08-15")[0]
    assert rij["status"] == "pending" and "verlopen" in rij["reden"]
    assert "vernieuw het certificaat" in cr.opdracht(rij)


def test_de_koppeling_claim_cert_wordt_niet_geraden():
    """Welk onderdeel welk materiaal bevat weet alleen de founder (CLAUDE.md). Een machine die dat
    raadt, koppelt vroeg of laat een cert aan een claim die het niet draagt."""
    cert = {"claims": ["70% gerecycled PET in de zool"]}
    assert cr.draagt(cert, "70% gerecycled PET in de zool") is True
    assert cr.draagt(cert, "gerecycled") is False          # bijna is niet genoeg


# ── De skill ────────────────────────────────────────────────────────────────

class _Ctx:
    def __init__(self, led, data_dir=""):
        self.evidence = led
        self.data_dir = data_dir


def test_de_skill_schrijft_het_record_en_meldt_wat_ontbreekt():
    from nooch_village.skills_impl.cert_evidence import CertEvidenceSkill
    led = _Ledger()
    uit = CertEvidenceSkill().run({"text": CERT, "claims": ["Recycled, recycled"]}, _Ctx(led))
    assert uit["geschreven"] and uit["record_id"]
    assert led.rows[0]["source"] == cr.EXTERN


def test_de_skill_weigert_een_cert_zonder_datum():
    from nooch_village.skills_impl.cert_evidence import CertEvidenceSkill
    led = _Ledger()
    uit = CertEvidenceSkill().run({"text": "Certifies that: iets zonder datum"}, _Ctx(led))
    assert not uit["geschreven"] and "geldig_tot" in uit["reason"]


def test_de_skill_meldt_een_cert_zonder_claim_koppeling():
    from nooch_village.skills_impl.cert_evidence import CertEvidenceSkill
    uit = CertEvidenceSkill().run({"text": CERT}, _Ctx(_Ledger()))
    assert any("geen claims gekoppeld" in r for r in uit.get("let_op") or [])


def test_een_onleesbaar_bestand_is_een_fout_geen_leegte():
    """Fail-closed en luid: 'kon niet openen' is iets anders dan 'geen bewijs'."""
    from nooch_village.skills_impl.cert_evidence import CertEvidenceSkill
    uit = CertEvidenceSkill().run({"bestand": "bestaat-niet.txt"}, _Ctx(_Ledger(), "/tmp/xyz"))
    assert "error" in uit and "niet te lezen" in uit["error"]
