"""Level 3 — Noochie's proactieve scope-nudge (optie 1: alleen wijzen). De matcher is fail-closed en
checkt de skill hard tegen het DNA; Noochie plaatst een nudge-comment + notificatie, gededupt per
(project, rol), en maakt zelf GEEN taken."""
from __future__ import annotations

from types import SimpleNamespace

from nooch_village.roles import Noochie
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus
from nooch_village.skills import SkillRegistry
from nooch_village.projects import ProjectLedger
from nooch_village.notifications import NotifStore
from nooch_village import scope_nudge


# ── matcher (puur, reason_fn geïnjecteerd) ─────────────────────────────────────

_ROSTER = [
    {"role_id": "harry_hemp", "name": "Scientist",
     "accountabilities": ["bewijs zoeken"], "skills": ["openalex_evidence", "epo_patents"]},
    {"role_id": "librarian", "name": "Librarian",
     "accountabilities": ["woordenschat"], "skills": ["curate"]},
]


def test_match_geldig_met_skill_in_dna():
    out = scope_nudge.match_project_to_role(
        "claim over barefoot-schoenen", _ROSTER,
        reason_fn=lambda p: '{"role_id": "harry_hemp", "skill": "openalex_evidence"}')
    assert out == {"role_id": "harry_hemp", "name": "Scientist", "skill": "openalex_evidence"}


def test_match_skill_buiten_dna_is_geen_match():
    # het model noemt een skill die NIET bij die rol hoort → machine-check verwerpt (geen verzonnen tool)
    out = scope_nudge.match_project_to_role(
        "iets", _ROSTER, reason_fn=lambda p: '{"role_id": "librarian", "skill": "openalex_evidence"}')
    assert out is None


def test_match_null_is_geen_match():
    out = scope_nudge.match_project_to_role(
        "iets", _ROSTER, reason_fn=lambda p: '{"role_id": null, "skill": null}')
    assert out is None


def test_match_lege_input_of_rol_zonder_skills():
    assert scope_nudge.match_project_to_role("", _ROSTER, reason_fn=lambda p: "{}") is None
    assert scope_nudge.match_project_to_role("x", [], reason_fn=lambda p: "{}") is None
    zonder_skill = [{"role_id": "x", "name": "X", "accountabilities": [], "skills": []}]
    assert scope_nudge.match_project_to_role("x", zonder_skill, reason_fn=lambda p: "{}") is None


def test_match_onparsbaar_faalt_closed():
    assert scope_nudge.match_project_to_role("x", _ROSTER, reason_fn=lambda p: "geen json") is None


# ── ProjectLedger-helpers ───────────────────────────────────────────────────────

def test_active_en_nudge_dedup(tmp_path):
    lg = ProjectLedger(str(tmp_path / "p.json"))
    pid = lg.create("owner_role", "Een project", "human")
    assert [p["id"] for p in lg.active()] == [pid]
    assert not lg.already_scope_nudged(pid, "harry_hemp")
    lg.mark_scope_nudge(pid, "harry_hemp")
    assert lg.already_scope_nudged(pid, "harry_hemp")
    lg.mark_scope_nudge(pid, "harry_hemp")                       # idempotent
    assert lg.get(pid)["scope_nudges"] == ["harry_hemp"]


# ── Noochie end-to-end (matcher gestubd) ────────────────────────────────────────

def _role(rid, skills, rtype=RecordType.ROLE, name=""):
    return Record(id=rid, type=rtype, parent="noochville",
                  definition=RoleDefinition(purpose="p", name=name, accountabilities=["a"],
                                            domains=[], skills=skills),
                  source="seed")


def _make_noochie(tmp_path, ledger, records):
    context = SimpleNamespace(settings={"reflect_interval_seconds": "0"}, data_dir=str(tmp_path),
                              projects=ledger, records=records, observations=None)
    record = _role("noochie", [])
    return Noochie(record, EventBus(name="test"), SkillRegistry(), context)


def test_noochie_nudgt_matchende_rol_en_dedupt(tmp_path, monkeypatch):
    lg = ProjectLedger(str(tmp_path / "p.json"))
    pid = lg.create("owner_role", "Barefoot-claim screenen", "human")
    records = SimpleNamespace(all=lambda: [
        _role("owner_role", ["curate"]),
        _role("harry_hemp", ["openalex_evidence"], name="Scientist"),
        _role("some_circle", ["x"], rtype=RecordType.CIRCLE),      # cirkel → uit de roster
        _role("noochie", []),                                      # Noochie zelf → uit de roster
    ])
    noochie = _make_noochie(tmp_path, lg, records)

    # de match is gestubd: het project matcht Scientist op openalex_evidence
    monkeypatch.setattr(scope_nudge, "match_project_to_role",
                        lambda text, roster, **k: {"role_id": "harry_hemp", "name": "Scientist",
                                                   "skill": "openalex_evidence"})

    noochie._nudge_scope_matches()
    log = lg.get(pid)["log"]
    assert any("@Scientist" in e.get("text", "") and "openalex_evidence" in e.get("text", "")
               for e in log)                                       # nudge-comment geplaatst
    assert lg.already_scope_nudged(pid, "harry_hemp")              # gemarkeerd
    notifs = NotifStore(str(tmp_path / "notifications.json")).for_targets([("role", "harry_hemp")])
    assert len(notifs) == 1                                        # notificatie aan de rol

    # tweede puls → geen dubbele nudge (dedup)
    n_before = len(lg.get(pid)["log"])
    noochie._nudge_scope_matches()
    assert len(lg.get(pid)["log"]) == n_before


def test_noochie_nudgt_de_eigenaar_niet(tmp_path, monkeypatch):
    # als de enige match de eigenaar zelf is, komt er geen nudge (een rol nudge je niet over eigen project)
    lg = ProjectLedger(str(tmp_path / "p.json"))
    pid = lg.create("harry_hemp", "Eigen onderzoek", "human")
    records = SimpleNamespace(all=lambda: [_role("harry_hemp", ["openalex_evidence"], name="Scientist")])
    noochie = _make_noochie(tmp_path, lg, records)

    seen = {}
    def fake_match(text, roster, **k):
        seen["ids"] = [r["role_id"] for r in roster]
        return None
    monkeypatch.setattr(scope_nudge, "match_project_to_role", fake_match)

    noochie._nudge_scope_matches()
    assert "harry_hemp" not in seen.get("ids", [])                 # eigenaar zit niet in de kandidaten
    assert not lg.get(pid)["log"]                                  # geen nudge
