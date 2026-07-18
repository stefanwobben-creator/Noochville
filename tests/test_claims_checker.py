"""Claims-checker: één bron van waarheid, de lokale toets en de compliance-poort.

De rode draad van deze suite: de termenlijst leeft ALLEEN in config/claims_database.json.
Wie hem naar de HTML of naar Python-code terugkopieert, laat een test vallen.
"""
from __future__ import annotations

import json
import os
import re

import pytest

from nooch_village import claims_db
from nooch_village.skills_impl.claims_check import ClaimsCheckSkill

HTML_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "nooch_village", "static", "claims_checker.html")


# ── De bron zelf ────────────────────────────────────────────────────────────

def test_database_laadt_en_alle_patronen_compileren():
    db = claims_db.load()
    assert len(db["termen"]) >= 56
    for t in db["termen"]:
        re.compile(t["patroon"], re.IGNORECASE)          # faalt luid bij een kapot patroon
        assert t["stoplicht"] in claims_db.STOPLICHTEN
        assert t["term"] and t["categorie"]


def test_werklijst_en_landen_compleet():
    db = claims_db.load()
    assert len(db["werklijst"]) >= 20
    for w in db["werklijst"]:
        assert {"nr", "claim", "oordeel", "herformulering", "status"} <= set(w)
        assert w["status"] in claims_db.werk_statussen(db)
    for code in ("NL", "DE", "BE"):
        land = db["landen"][code]
        assert land["punten"] and land["note_rood"] and land["note_oranje"]


def test_ontbrekende_database_faalt_closed(tmp_path):
    with pytest.raises(claims_db.ClaimsDbError):
        claims_db.load(str(tmp_path / "bestaat-niet.json"))


def test_corrupte_database_faalt_closed(tmp_path):
    p = tmp_path / "kapot.json"
    p.write_text("{niet: json", encoding="utf-8")
    with pytest.raises(claims_db.ClaimsDbError):
        claims_db.load(str(p))


# ── De toets ────────────────────────────────────────────────────────────────

def test_check_tekst_vindt_verboden_claims_en_scoort():
    uitslag = claims_db.check_tekst("Onze 100% planet-safe sneakers zijn biologisch afbreekbaar.")
    termen = {b["term"] for b in uitslag["bevindingen"]}
    assert any("planet-safe" in t for t in termen)
    assert any("afbreekbaar" in t for t in termen)
    assert uitslag["rood"] >= 2
    assert uitslag["score"] == claims_db.score(uitslag["rood"], uitslag["oranje"])
    assert uitslag["score"] < 100


def test_schone_tekst_houdt_volle_score():
    uitslag = claims_db.check_tekst("Handgemaakt in Portugal, in kleine series.")
    assert uitslag["bevindingen"] == []
    assert uitslag["score"] == 100


def test_score_volgt_de_formule_uit_meta():
    db = claims_db.load()
    formule = db["meta"]["scoring"]
    assert "12" in formule and "5" in formule            # de code mag niet uit de pas lopen
    assert claims_db.score(2, 3) == 100 - 24 - 15
    assert claims_db.score(20, 0) == 0                   # nooit negatief


# ── De skill ────────────────────────────────────────────────────────────────

def test_skill_toetst_tekst():
    uit = ClaimsCheckSkill().run({"text": "Duurzaam en klimaatneutraal geproduceerd."})
    assert uit["ok"] is True
    assert uit["rood"] >= 2
    assert uit["versie"]


def test_skill_accepteert_termenlijst():
    uit = ClaimsCheckSkill().run({"terms": ["zero waste", "vegan"]})
    assert uit["ok"] is True
    stoplichten = {b["stoplicht"] for b in uit["bevindingen"]}
    assert "red" in stoplichten and "green" in stoplichten


def test_skill_zonder_payload_faalt_netjes():
    assert ClaimsCheckSkill().run({})["ok"] is False


def test_skill_staat_in_de_registry():
    from nooch_village.registry_factory import build_skill_registry
    reg = build_skill_registry()
    assert reg.get("claims_check") is not None


def test_skill_is_puur_lokaal():
    """Geen netwerk-import in de skill: de toets mag nooit buiten de deur praten."""
    with open(os.path.join(os.path.dirname(HTML_PATH), "..", "skills_impl", "claims_check.py"),
              encoding="utf-8") as f:
        bron = f.read()
    assert "requests" not in bron and "urllib" not in bron


# ── Muteren (compliance-domein) ─────────────────────────────────────────────

def _kopie(tmp_path) -> str:
    p = tmp_path / "claims_database.json"
    p.write_text(json.dumps(claims_db.load(), ensure_ascii=False), encoding="utf-8")
    return str(p)


def test_term_toevoegen_en_versie_bumpen(tmp_path):
    pad = _kopie(tmp_path)
    db = claims_db.load(pad)
    voor = len(db["termen"])
    claims_db.add_term(db, term="gifvrij / toxin-free", patroon="gifvrij|toxin.?free",
                       stoplicht="red", categorie="Materiaal")
    nieuwe_versie = claims_db.bump_versie(db)
    claims_db.save(db, pad)

    herladen = claims_db.load(pad)                        # overleeft een 'herstart'
    assert len(herladen["termen"]) == voor + 1
    assert herladen["meta"]["versie"] == nieuwe_versie
    assert claims_db.check_tekst("volledig gifvrij", herladen)["rood"] >= 1


def test_kapot_patroon_komt_de_bron_niet_in():
    db = claims_db.load()
    with pytest.raises(ValueError):
        claims_db.add_term(db, term="x", patroon="[onafgesloten", stoplicht="red", categorie="x")
    with pytest.raises(ValueError):
        claims_db.add_term(db, term="x", patroon="ok", stoplicht="paars", categorie="x")


def test_werkstatus_wijzigen(tmp_path):
    pad = _kopie(tmp_path)
    db = claims_db.load(pad)
    claims_db.set_werk_status(db, 1, "live")
    claims_db.save(db, pad)
    assert claims_db.load(pad)["werklijst"][0]["status"] == "live"
    with pytest.raises(ValueError):
        claims_db.set_werk_status(db, 1, "verzonnen-status")
    with pytest.raises(ValueError):
        claims_db.set_werk_status(db, 999, "live")


def test_bump_versie_telt_door_binnen_een_dag():
    db = {"meta": {"versie": ""}}
    eerste = claims_db.bump_versie(db)
    tweede = claims_db.bump_versie(db)
    derde = claims_db.bump_versie(db)
    assert eerste != tweede != derde
    assert tweede.endswith(".2") and derde.endswith(".3")


# ── De poort ────────────────────────────────────────────────────────────────

def test_dispatch_weigert_onbekende_gebruiker(tmp_path):
    from nooch_village import cockpit2
    dd = str(tmp_path)
    for actie, form in (("claims_term_add", {"term": ["x"], "patroon": ["x"], "stoplicht": ["red"]}),
                        ("claims_work_status", {"nr": ["1"], "status": ["live"]})):
        _, msg = cockpit2.dispatch(dd, actie, {**form, "next": ["/claims"]}, "niemand@nergens.nl")
        assert "Geen toegang" in msg


def test_dispatch_schrijft_naar_de_bron_en_logt(tmp_path, monkeypatch):
    """De acceptatietest van taak 3: de mutatie staat in de JSON (niet in de browser) en
    komt in de audit-trail terecht."""
    from nooch_village import cockpit2
    pad = _kopie(tmp_path)
    monkeypatch.setattr(claims_db, "DB_PATH", pad)
    dd = str(tmp_path / "data")
    os.makedirs(dd, exist_ok=True)

    _, msg = cockpit2.dispatch(dd, "claims_term_add",
                               {"term": ["gifvrij"], "patroon": ["gifvrij"], "stoplicht": ["red"],
                                "categorie": ["Materiaal"], "next": ["/claims"]}, "guest")
    assert msg.startswith("✓")
    _, msg = cockpit2.dispatch(dd, "claims_work_status",
                               {"nr": ["3"], "status": ["live"], "next": ["/claims"]}, "guest")
    assert msg.startswith("✓")

    db = claims_db.load(pad)                                     # overleeft een herstart
    assert any(t["term"] == "gifvrij" for t in db["termen"])
    assert [w for w in db["werklijst"] if w["nr"] == 3][0]["status"] == "live"

    log = [json.loads(r) for r in open(os.path.join(dd, "system_log.jsonl"), encoding="utf-8")]
    assert {e["event"] for e in log} == {"claims_term_added", "claims_work_status"}


def test_dispatch_weigert_onzin_zonder_te_schrijven(tmp_path, monkeypatch):
    from nooch_village import cockpit2
    pad = _kopie(tmp_path)
    monkeypatch.setattr(claims_db, "DB_PATH", pad)
    voor = open(pad, encoding="utf-8").read()
    _, msg = cockpit2.dispatch(str(tmp_path), "claims_term_add",
                               {"term": ["x"], "patroon": ["[kapot"], "stoplicht": ["red"],
                                "next": ["/claims"]}, "guest")
    assert msg.startswith("⛔")
    assert open(pad, encoding="utf-8").read() == voor      # bron ongemoeid


def test_gate_is_dezelfde_voor_knop_en_mutatie(tmp_path):
    """De leespoort van de UI mag nooit ruimer zijn dan de schrijfpoort."""
    from nooch_village import cockpit2
    st = cockpit2._Stores(str(tmp_path))
    assert cockpit2._claims_gate_open(st, "niemand@nergens.nl") is False
    assert cockpit2._claims_gate_open(st, "guest") is True     # auth uit = alles mag


# ── Eén bron van waarheid ───────────────────────────────────────────────────

def test_html_bevat_geen_gekopieerde_database():
    """De acceptatietest van taak 1: geen termenlijst, werklijst of landenregel in de HTML."""
    with open(HTML_PATH, encoding="utf-8") as f:
        html = f.read()
    assert 'fetch("/claims/db.json"' in html
    db = claims_db.load()
    for t in db["termen"][:15]:
        assert t["patroon"] not in html, f"patroon van '{t['term']}' staat gekopieerd in de HTML"
    for w in db["werklijst"][:5]:
        assert w["herformulering"] not in html
    for punt in db["landen"]["NL"]["punten"]:
        assert punt not in html
    assert "ADMIN_CODE" not in html            # client-side 'beveiliging' is vervangen door de sessie


# ── Governance: het claims-database-domein voor compliance ──────────────────

def test_compliance_claims_voorstel_passeert_de_gate(tmp_path):
    """De compliance-rol bestaat al (geboren via governance); dit is een AMEND die hem het
    domein over de eigen claims geeft. Uniek domein → G1 en G2 klagen niet."""
    from nooch_village.governance import Gate, Records
    from nooch_village.seeds import seed_records, migrate_records
    from nooch_village.models import ChangeKind, Record, RoleDefinition, RecordType
    from nooch_village.role_proposals import build_compliance_claims_proposal

    records = Records(str(tmp_path / "gov.json"))
    seed_records(records)
    migrate_records(records)
    records.put(Record(
        id="compliance", type=RecordType.ROLE, parent="noochville",
        definition=RoleDefinition(purpose="claims bewaken",
                                  accountabilities=["claims van externe merken verifiëren"],
                                  domains=["claim-verification"], skills=["claim_evidence"]),
        source="sensed",
    ))
    p = build_compliance_claims_proposal()
    assert p.change.kind == ChangeKind.AMEND_ROLE
    assert p.change.add_domains == ["claims-database"]
    assert p.change.add_skills == ["claims_check"]
    passed, gate, reason = Gate().check(p, records)
    assert passed, f"verwacht aangenomen, maar {gate}: {reason}"


def test_compliance_claims_voorstel_draagt_herhalingsbewijs():
    """G0-discipline: een structurele wijziging onderbouwt de herhaling, niet één incident."""
    from nooch_village.role_proposals import build_compliance_claims_proposal
    p = build_compliance_claims_proposal()
    assert any(w in p.trigger_example.lower() for w in ("terugkerend", "structureel", "meermaals"))
    assert p.rationale and p.tension
