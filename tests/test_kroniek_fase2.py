"""De Kroniek fase 2: de brug (claim_evidence → bewijsregister) + de interpreteer-laag (per-onderwerp
synthese, fail-closed). Geen LLM, geen netwerk — puur de rollup-logica en de status-mapping."""
from __future__ import annotations

from types import SimpleNamespace

from nooch_village.evidence_ledger import EvidenceLedger, interpret
from nooch_village.skills_impl.claim_evidence import ClaimEvidenceSkill
from nooch_village.skills_impl.kroniek_interpret import KroniekInterpretSkill


def _led(tmp_path):
    return EvidenceLedger(str(tmp_path / "ev.jsonl"))


# ── brug: claim_evidence.evidence_records ─────────────────────────────────────

def test_evidence_records_mapt_de_vier_statussen():
    res = {"ok": True, "rows": [
        {"brand": "Veja", "claim": "biodegradable", "status": "bevestigd", "evidence": "ISO 14855", "source": "https://a"},
        {"brand": "MerkX", "claim": "afbreekbaar", "status": "onduidelijk", "evidence": "wij geloven", "source": "https://b"},
        {"brand": "MerkY", "claim": "afbreekbaar", "status": "leeg", "evidence": "", "source": ""},
        {"brand": "MerkZ", "claim": "afbreekbaar", "status": "fout", "evidence": "", "source": ""},
    ]}
    recs = ClaimEvidenceSkill().evidence_records(res, role_id="compliance")
    st = {r["query"]: r["status"] for r in recs}
    assert st["Veja — biodegradable"] == "bevestigd"
    assert st["MerkX — afbreekbaar"] == "leeg"        # onduidelijk → leeg: geen bevestigd bewijs (waarheidslat)
    assert st["MerkY — afbreekbaar"] == "leeg"
    assert st["MerkZ — afbreekbaar"] == "fout"
    assert all(r["skill"] == "claim_evidence" and r["role_id"] == "compliance" for r in recs)
    # de records zijn direct schrijfbaar naar de ledger (statuses passeren de fail-closed check)
    assert {r["status"] for r in recs} <= {"bevestigd", "leeg", "fout"}


def test_evidence_records_bij_lege_of_mislukte_uitkomst():
    assert ClaimEvidenceSkill().evidence_records({"ok": False}, role_id="x") == []
    assert ClaimEvidenceSkill().evidence_records({}, role_id="x") == []


# ── brug → register → interpret: end-to-end zonder inhabitant ──────────────────

def test_brug_en_interpret_samen(tmp_path):
    led = _led(tmp_path)
    result = {"ok": True, "rows": [
        {"brand": "Veja", "claim": "biodegradable", "status": "bevestigd", "evidence": "ISO 14855", "source": "https://veja"},
        {"brand": "MerkX", "claim": "biodegradable", "status": "onduidelijk", "evidence": "marketing", "source": "https://x"},
    ]}
    for rec in ClaimEvidenceSkill().evidence_records(result, role_id="compliance"):
        led.record(**rec)
    res = interpret(led, "biodegradable")
    assert len(res["bevestigd"]) == 1 and len(res["leeg"]) == 1
    assert "https://veja" in res["conclusie"]


# ── interpret: partitie, bronnen, fail-closed, laatste-stand ──────────────────

def test_interpret_partitioneert_en_noemt_bronnen(tmp_path):
    led = _led(tmp_path)
    led.record(role_id="c", skill="claim_evidence", query="Veja — biodegradable", source="https://a", status="bevestigd", result_ref="ISO 14855")
    led.record(role_id="c", skill="claim_evidence", query="MerkX — biodegradable", source="https://b", status="leeg")
    res = interpret(led, "biodegradable")
    assert len(res["bevestigd"]) == 1 and len(res["leeg"]) == 1 and len(res["fout"]) == 0
    assert "bevestigd bewijs" in res["conclusie"] and "https://a" in res["conclusie"]


def test_interpret_fail_closed_zonder_bevestigd(tmp_path):
    led = _led(tmp_path)
    led.record(role_id="c", skill="claim_evidence", query="MerkX — afbreekbaar", source="https://b", status="leeg")
    led.record(role_id="c", skill="claim_evidence", query="MerkY — afbreekbaar", source="", status="fout")
    res = interpret(led, "afbreekbaar")
    assert res["bevestigd"] == []
    assert res["conclusie"].startswith("GEEN bevestigd bewijs")


def test_interpret_neemt_laatste_stand_per_bron(tmp_path):
    led = _led(tmp_path)
    # zelfde (skill, query, bron): eerst fout, later bevestigd → een oudere fout telt niet meer
    led.record(role_id="c", skill="openalex", query="barefoot slijtage", source="openalex", status="fout", ts=100)
    led.record(role_id="c", skill="openalex", query="barefoot slijtage", source="openalex", status="bevestigd", result_ref="paper", ts=200)
    res = interpret(led, "barefoot")
    assert len(res["bevestigd"]) == 1 and len(res["fout"]) == 0


def test_interpret_leeg_onderwerp(tmp_path):
    assert interpret(_led(tmp_path), "  ")["conclusie"] == "geen onderwerp opgegeven"


# ── de skill ──────────────────────────────────────────────────────────────────

def test_kroniek_interpret_skill_leest_het_register(tmp_path):
    led = _led(tmp_path)
    led.record(role_id="c", skill="claim_evidence", query="Veja — biodegradable", source="https://a", status="bevestigd", result_ref="ISO")
    ctx = SimpleNamespace(evidence_ledger=led, data_dir=str(tmp_path))
    res = KroniekInterpretSkill().run({"onderwerp": "biodegradable"}, ctx)
    assert res["ok"] and len(res["bevestigd"]) == 1


def test_kroniek_interpret_skill_zonder_onderwerp(tmp_path):
    res = KroniekInterpretSkill().run({}, SimpleNamespace(data_dir=str(tmp_path)))
    assert res["ok"] is False


def test_kroniek_interpret_geregistreerd():
    from nooch_village.registry_factory import build_skill_registry
    assert build_skill_registry().get("kroniek_interpret") is not None
