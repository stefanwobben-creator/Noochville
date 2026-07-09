"""Geheugen-laag fase 1: bestaande deliverables als context in de prep-prompt.

Pure-functie (gather_deliverable_context): bron/filter/score/begrenzing/exclude/fail-closed.
Injectie (_plan_checklist): config-schakelaar + sectie alleen bij niet-leeg blok.
"""
from __future__ import annotations
from types import SimpleNamespace
from unittest.mock import patch

from nooch_village.deliverable_context import gather_deliverable_context
from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus
from nooch_village.skills import SkillRegistry
from nooch_village.projects import ProjectLedger


def _ledger(projects):
    """Minimale ledger-stub: alleen by_status, zoals de helper 'm aanroept."""
    return SimpleNamespace(by_status=lambda s: [p for p in projects if p.get("status") == s])


def _proj(pid, owner, scope, keyword, log, status="done"):
    return {"id": pid, "owner": owner, "scope": scope, "keyword": keyword, "status": status, "log": log}


def _note(text, who="rol", at=1):
    return {"who": who, "text": text, "at": at}


# 1. Done-project met relevante 📎-note → in het blok, met bron-prefix
def test_1_relevante_deliverable_opgenomen(tmp_path):
    p = _proj("p1", "harry_hemp", "Onderzoek naar barefoot shoes", "barefoot shoes",
              [_note("📎 studie — via openalex_evidence: barefoot loopschoenen verbeteren de voethouding")])
    blok = gather_deliverable_context(_ledger([p]), "barefoot loopschoenen onderzoek",
                                      max_notes=5, max_chars=2000)
    assert "[harry_hemp/Onderzoek naar barefoot shoes]" in blok
    assert "barefoot loopschoenen" in blok


# 2. Faalnote (⚠️) en mens-comment → nooit opgenomen
def test_2_faalnote_en_mens_uitgesloten(tmp_path):
    p = _proj("p1", "o", "barefoot shoes", "barefoot",
              [_note("⚠️ 'x' via epo_patents niet gelukt (leeg): barefoot loopschoenen"),
               _note("barefoot loopschoenen is belangrijk", who="mens")])
    assert gather_deliverable_context(_ledger([p]), "barefoot loopschoenen", max_notes=5, max_chars=2000) == ""


# 3. Niet-done project → nooit opgenomen
def test_3_niet_done_uitgesloten(tmp_path):
    p = _proj("p1", "o", "barefoot shoes", "barefoot",
              [_note("📎 barefoot loopschoenen studie")], status="future")
    assert gather_deliverable_context(_ledger([p]), "barefoot loopschoenen", max_notes=5, max_chars=2000) == ""


# 4. Score 0 (geen overlap) → niet opgenomen; volledig leeg → ""
def test_4_geen_overlap_leeg(tmp_path):
    p = _proj("p1", "o", "iets heel anders", "",
              [_note("📎 quantum fysica en supergeleiders resultaten")])
    assert gather_deliverable_context(_ledger([p]), "barefoot loopschoenen onderzoek",
                                      max_notes=5, max_chars=2000) == ""


# 5. max_notes en max_chars worden gerespecteerd (afkap zichtbaar)
def test_5_begrenzingen(tmp_path):
    ps = [_proj(f"p{i}", "o", "barefoot shoes", "barefoot",
               [_note(f"📎 studie {i} barefoot loopschoenen resultaat", at=i)]) for i in range(3)]
    een = gather_deliverable_context(_ledger(ps), "barefoot loopschoenen", max_notes=1, max_chars=2000)
    assert len(een.splitlines()) == 1                       # max_notes hard
    kort = gather_deliverable_context(_ledger(ps), "barefoot loopschoenen", max_notes=5, max_chars=40)
    assert kort and len(kort) <= 40                         # max_chars hard, zichtbaar afgekapt


# 6. Eigen project uitgesloten (geen zelf-referentie)
def test_6_eigen_project_uitgesloten(tmp_path):
    p = _proj("zelf", "o", "barefoot shoes", "barefoot", [_note("📎 barefoot loopschoenen studie")])
    assert gather_deliverable_context(_ledger([p]), "barefoot loopschoenen",
                                      max_notes=5, max_chars=2000, exclude_pid="zelf") == ""


# 8. Interne exception (corrupt log-entry) → fail-closed, blok leeg
def test_8_failclosed_corrupt_entry(tmp_path):
    p = _proj("p1", "o", "barefoot", "barefoot", [None])     # None.get(...) → AttributeError intern
    assert gather_deliverable_context(_ledger([p]), "barefoot", max_notes=5, max_chars=2000) == ""


# ── Injectie in _plan_checklist ───────────────────────────────────────────────
def _inhabitant(tmp_path, ledger, **settings):
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0", **settings},
                          data_dir=str(tmp_path), projects=ledger, records=None)
    rec = Record(id="harry_hemp", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="x", accountabilities=["research"], domains=[], skills=[]),
                 source="sensed")
    return Inhabitant(rec, EventBus(name="test"), SkillRegistry(), ctx)


def _seed_done(ledger, owner, scope, keyword, note_text):
    pid = ledger.create(owner, scope, "human", status="queued", keyword=keyword)
    ledger.add_role_message(pid, note_text)
    ledger.get(pid)["status"] = "done"
    ledger._save()
    return pid


def _capture_prompt(inh, goal, **kw):
    cap = {}
    def fake_reason(prompt, **k):
        cap["prompt"] = prompt
        return (None, "mock") if k.get("return_tier") else None
    with patch("nooch_village.llm.reason", side_effect=fake_reason):
        inh._plan_checklist(goal, **kw)
    return cap.get("prompt", "")


def test_injectie_met_context_toont_sectie(tmp_path):
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    _seed_done(ledger, "harry_hemp", "Onderzoek naar barefoot shoes", "barefoot",
               "📎 studie — via openalex_evidence: barefoot loopschoenen bevindingen")
    inh = _inhabitant(tmp_path, ledger)                     # enabled default "1"
    prompt = _capture_prompt(inh, "barefoot loopschoenen onderzoek", keyword="barefoot", exclude_pid="ander")
    assert "Eerder afgerond onderzoek in het dorp" in prompt
    assert "barefoot loopschoenen bevindingen" in prompt


# 4b + 7. Leeg blok → geen sectie; enabled=0 → geen sectie (prompt zonder geheugen-kop)
def test_7_uitgeschakeld_geen_sectie(tmp_path):
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    _seed_done(ledger, "harry_hemp", "Onderzoek naar barefoot shoes", "barefoot",
               "📎 barefoot loopschoenen bevindingen")     # relevante bron aanwezig...
    inh = _inhabitant(tmp_path, ledger, deliverable_context_enabled="0")   # ...maar uit
    prompt = _capture_prompt(inh, "barefoot loopschoenen onderzoek", keyword="barefoot", exclude_pid="ander")
    assert "Eerder afgerond onderzoek" not in prompt        # geen sectie


def test_4b_leeg_blok_geen_sectie(tmp_path):
    ledger = ProjectLedger(str(tmp_path / "p.json"))        # geen done-projecten → leeg blok
    inh = _inhabitant(tmp_path, ledger)
    prompt = _capture_prompt(inh, "barefoot onderzoek", keyword="barefoot", exclude_pid="ander")
    assert "Eerder afgerond onderzoek" not in prompt        # leeg blok → sectie volledig weggelaten
