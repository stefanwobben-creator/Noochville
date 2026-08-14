"""Een claim-oordeel is gegrond of het is een bevinding — een tussenvorm bestaat niet.

De drie claim-items die de founder te zien kreeg waren LLM-escalaties zonder de claim erin: "de
herziene claim is klaar voor implementatie, mag ik live?" — zonder tekst, zonder clausule, zonder
bewijs. Onbeantwoordbaar zonder het werk over te doen.

Deze tests leggen de grondingsregels vast, en vooral de KANT waarop ze falen: als het bewijs niet
reikt komt er een eerlijke bevinding uit, nooit een net-ogend 'compliant'. Dat is dezelfde regel
als de lege-run in claims_check (score 100 met nul tellers is geen goedkeuring) — daarom hergebruikt
deze laag die machinerie in plaats van hem na te bouwen.
"""
from __future__ import annotations

import pytest

from nooch_village import claim_oordeel as co
from nooch_village import claims_db


@pytest.fixture(scope="module")
def db():
    return claims_db.load_seed()


# ── De harde kant: een verbod beslist, en citeert ───────────────────────────

def test_een_verboden_term_levert_een_herformulering_met_clausule(db):
    o = co.oordeel_voor("Our shoes are eco-friendly.", db=db)
    assert o["oordeel"] == co.HERFORMULEREN
    assert "2024/825" in o["clausule"] and "Recital 9" in o["clausule"]
    assert o["nieuwe_tekst"]                       # de voorgestelde tekst staat er
    assert o["gegrond"] is True


def test_zonder_citeerbare_bron_geen_oordeel(db):
    """Geen oordeel zonder citaat — ook niet als de term rood is."""
    kaal = {"bevindingen": [{"term": "x", "stoplicht": "red", "bron": "", "bron_detail": "",
                             "waarom": "iets", "alternatief": "iets anders"}],
            "rood": 1, "oranje": 0, "groen": 0, "escaleren": 0, "score": 88}
    o = co.oordeel_voor("iets", db=kaal)
    assert o["oordeel"] == co.GEEN_OORDEEL and o["gegrond"] is False


def test_bron_c_wordt_nooit_door_de_tool_beslist():
    """Het toetsingskader van de database zegt het letterlijk: bij C beslist de mens."""
    esc = {"bevindingen": [{"term": "iets", "stoplicht": "escaleren", "bron": "C",
                            "bron_detail": "interpretatie"}],
           "rood": 0, "oranje": 0, "groen": 0, "escaleren": 1, "score": 100}
    o = co.oordeel_voor("iets", db=esc)
    assert o["oordeel"] == co.GEEN_OORDEEL and "beslist niet" in o["waarom"]


# ── De zachte kant: compliant vereist bewijs ÉN clausule ────────────────────

class _Ledger:
    def __init__(self, rijen):
        self._r = rijen

    def all(self):
        return list(self._r)


def _oranje(bewijs_onderbouwd: bool, monkeypatch):
    from nooch_village import claims_substantiatie as subst
    monkeypatch.setattr(subst, "_index", lambda ledger: [{"x": 1}])
    monkeypatch.setattr(subst, "bewijs_voor", lambda b, i, m: (
        # `source` is een EXTERNE bron, niet een eigen skill-run — anders telt het bewijs niet.
        {"onderbouwing": subst.ONDERBOUWD,
         "records": [{"id": "KRN-1", "source": "leverancierscertificaat"}],
         "reden": "1 bevestigd record — leverancierscertificaat"}
        if bewijs_onderbouwd else
        {"onderbouwing": subst.ONTBREEKT, "records": [], "reden": "geen bevestigd record"}))


def test_onderbouwd_bewijs_maakt_een_risico_term_compliant(db, monkeypatch):
    _oranje(True, monkeypatch)
    o = co.oordeel_voor("Made with recycled materials.", db=db, ledger=_Ledger([]), merken={"nooch"})
    assert o["oordeel"] == co.COMPLIANT
    assert o["bewijs_id"] == "KRN-1" and o["clausule"]
    assert o["gegrond"] is True


def test_zonder_bewijs_wordt_het_geen_compliant(db, monkeypatch):
    """De kant waarop dit moet falen: liever een herformulering dan een zwak vinkje."""
    _oranje(False, monkeypatch)
    o = co.oordeel_voor("Made with recycled materials.", db=db, ledger=_Ledger([]), merken={"nooch"})
    assert o["oordeel"] != co.COMPLIANT
    assert "ontbreekt" in o["waarom"] or "geen bevestigd" in o["waarom"]


def test_geen_gevlagde_term_is_geen_goedkeuring(db):
    """De regel die het vaakst verkeerd gaat: niets gevonden ≠ compliant."""
    o = co.oordeel_voor("Sneakers made in Portugal.", db=db)
    assert o["oordeel"] == co.GEEN_OORDEEL
    assert "geen goedkeuring" in o["waarom"]


def test_een_lege_run_levert_nooit_een_oordeel(db):
    o = co.oordeel_voor("", db=db)
    assert o["oordeel"] == co.GEEN_OORDEEL and o["gegrond"] is False


# ── De kaart: tekst, clausule en herkomst staan erop ────────────────────────

def test_de_kaart_draagt_de_tekst_de_clausule_en_het_spoor(db):
    k = co.kaart(co.oordeel_voor("Our shoes are eco-friendly.", db=db))
    assert k["claim"] == "Our shoes are eco-friendly."          # waar beslist hij over
    assert k["nieuwe_tekst"]                                     # wat hij kan goedkeuren
    assert any("clausule" in r for r in k["spoor"])              # waarop het rust
    assert k["door"] == "compliance (claims-pas)"                # is dit via compliance gegaan


def test_de_kaart_draagt_de_waarschuwing_over_de_voorgestelde_tekst(db):
    """`alternatief` komt uit de database en is niet op deze context getoetst. Die waarschuwing
    staat al in betekenis_van en moet meereizen — anders leest een voorstel als een vrijgave."""
    k = co.kaart(co.oordeel_voor("Our shoes are eco-friendly.", db=db))
    assert any("VOORGESTELD alternatief" in r for r in k["spoor"])


def test_een_formulering_die_vrijgave_suggereert_degradeert(caplog):
    """De guard van claims_check, op onze eigen uitvoer. Niet stilletjes poetsen: degraderen."""
    vals = {"claim": "x", "oordeel": co.COMPLIANT, "waarom": "deze claim is goedgekeurd door legal",
            "gegrond": True, "clausule": "iets", "bewijs_id": "KRN-9"}
    with caplog.at_level("WARNING"):
        k = co.kaart(vals)
    assert k["oordeel"] == co.GEEN_OORDEEL and k["gegrond"] is False
    assert any("gedegradeerd" in r for r in k["spoor"])
    assert "verboden formulering" in caplog.text


def test_high_stakes_kent_geen_zwakke_uitkomst(db):
    """Elke uitkomst is óf gegrond met een clausule, óf expliciet geen oordeel. Er is geen derde."""
    for claim in ("Our shoes are eco-friendly.", "Made with recycled materials.",
                  "Sneakers made in Portugal.", ""):
        o = co.oordeel_voor(claim, db=db)
        assert (o["gegrond"] and o["clausule"]) or o["oordeel"] == co.GEEN_OORDEEL


def test_een_taakomschrijving_is_geen_claim():
    """Wat de eerste prod-dry-run echt blootlegde. "Locate the Plant Based Treaty-logo …" kreeg een
    oordeel mét clausule, want 'Plant Based' staat er letterlijk in. De bevinding was terecht; de
    TEKST was geen claim. De poort zit dus op de invoer, niet op het oordeel — een veto op de
    bevinding zou correcte oordelen wegduwen (`_raakt` is bewust ruim)."""
    assert co.claims_uit("🙋 compliance: 'Locate the Plant Based Treaty-logo on the footer'") == []
    assert co.claims_uit("Recognize that verifying the statistic is already running") == []


def test_een_claim_scan_levert_wel_claims():
    uit = co.claims_uit('🟠 Claim-scan: 2 model-gevonden claim(s) — "Created with love and '
                        'conscience" (product), "This choice conserves water" (faq)')
    assert "Created with love and conscience" in uit
    assert "This choice conserves water" in uit


def test_bewijs_uit_onze_eigen_skill_runs_telt_niet(db, monkeypatch):
    """Gezien in de prod-dry-run: drie claims kregen 'compliant' op Kroniek-records waarvan de bron
    'claims_check' of 'escaleer' was. Dat zegt dat wíj iets draaiden, niet dat een externe bron de
    claim draagt — een claim onderbouwen met je eigen logboek is cirkelredenering."""
    from nooch_village import claims_substantiatie as subst
    monkeypatch.setattr(subst, "_index", lambda ledger: [{"x": 1}])
    monkeypatch.setattr(subst, "bewijs_voor", lambda b, i, m: {
        "onderbouwing": subst.ONDERBOUWD, "records": [{"id": "K1", "source": "claims_check"}],
        "reden": "1 bevestigd record — claims_check"})
    o = co.oordeel_voor("Made with recycled materials.", db=db, ledger=_Ledger([]), merken={"nooch"})
    assert o["oordeel"] != co.COMPLIANT
    assert "eigen skill-runs" in o["waarom"]


def test_herformuleren_zonder_clausule_is_geen_oordeel(db, monkeypatch):
    """Zelfde regel als in de rode tak. Anders landt een herformulering zonder wetsgrond als
    besluit op de kaart."""
    kaal = {"bevindingen": [{"term": "x", "stoplicht": "orange", "bron": "", "bron_detail": "",
                             "alternatief": "iets anders", "waarom": "iets"}],
            "rood": 0, "oranje": 1, "groen": 0, "escaleren": 0, "score": 95}
    o = co.oordeel_voor("iets", db=kaal)
    assert o["oordeel"] == co.GEEN_OORDEEL and o["gegrond"] is False


# ── Anti-drift: een goedkeuring mag zijn bewijs niet overleven ──────────────

def _cert_bewijs(geldig_tot):
    from nooch_village import cert_register as cr
    from nooch_village import claims_substantiatie as subst
    return {"onderbouwing": subst.ONDERBOUWD,
            "records": [{"id": "K9", "source": cr.EXTERN,
                         "meta": {"geldig_tot": geldig_tot, "feit": "70% gerecycled PET"}}],
            "reden": "1 bevestigd certificaat"}


def test_een_geldig_certificaat_draagt_wel(db, monkeypatch):
    from nooch_village import claims_substantiatie as subst
    monkeypatch.setattr(subst, "_index", lambda ledger: [{"x": 1}])
    monkeypatch.setattr(subst, "bewijs_voor", lambda b, i, m: _cert_bewijs("2099-01-01"))
    o = co.oordeel_voor("Made with recycled materials.", db=db, ledger=_Ledger([]), merken={"n"})
    assert o["oordeel"] == co.COMPLIANT and o["bewijs_id"] == "K9"


def test_een_verlopen_certificaat_klapt_de_claim_terug(db, monkeypatch, caplog):
    """Een levende vergelijking, geen eenmalige stempel — anders overleeft de goedkeuring het bewijs."""
    from nooch_village import claims_substantiatie as subst
    monkeypatch.setattr(subst, "_index", lambda ledger: [{"x": 1}])
    monkeypatch.setattr(subst, "bewijs_voor", lambda b, i, m: _cert_bewijs("2020-01-01"))
    with caplog.at_level("INFO"):
        o = co.oordeel_voor("Made with recycled materials.", db=db, ledger=_Ledger([]), merken={"n"})
    assert o["oordeel"] != co.COMPLIANT
    assert "verlopen" in caplog.text


def test_een_certificaat_zonder_datum_draagt_niet(db, monkeypatch):
    """Onbekend ≠ geldig: niemand kan zeggen tot wanneer het draagt."""
    from nooch_village import claims_substantiatie as subst
    monkeypatch.setattr(subst, "_index", lambda ledger: [{"x": 1}])
    monkeypatch.setattr(subst, "bewijs_voor", lambda b, i, m: _cert_bewijs(""))
    o = co.oordeel_voor("Made with recycled materials.", db=db, ledger=_Ledger([]), merken={"n"})
    assert o["oordeel"] != co.COMPLIANT
