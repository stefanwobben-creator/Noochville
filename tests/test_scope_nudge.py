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

    # De match is gestubd: het project matcht Scientist op openalex_evidence. De stub geeft
    # (match, beantwoord) terug — `beantwoord` zegt of het MODEL sprak, en dat stuurt de vloer:
    # een oordeel mag onthouden worden, een storing nooit.
    monkeypatch.setattr(scope_nudge, "match_project_to_role",
                        lambda text, roster, **k: ({"role_id": "harry_hemp", "name": "Scientist",
                                                    "skill": "openalex_evidence"}, True))

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
        return (None, True)
    monkeypatch.setattr(scope_nudge, "match_project_to_role", fake_match)

    noochie._nudge_scope_matches()
    assert "harry_hemp" not in seen.get("ids", [])                 # eigenaar zit niet in de kandidaten
    assert not lg.get(pid)["log"]                                  # geen nudge


# ── De vloer: deterministisch waar het kan, het model voor de rest ───────────
#
# GEMETEN OP PROD, 29 aug 2026. `scope_nudge_match` was 3150 van de 8478 LLM-calls (37% van alles)
# en leverde 165 nudges op — 5,2%. De oorzaak zat niet in de roster (die is 7 rollen groot) maar in
# de LUS: elke puls opnieuw dezelfde vraag over elk actief project, terwijl er per dag maar 2% van
# die projecten verandert (7 van de 332 in 24 uur).
#
# Dit is de vorm van `kennis_dedup`: een deterministische vloer, en het model alleen voor wat de
# vloer niet kan uitsluiten.

def _teller(monkeypatch, uitkomst=(None, True)):
    """Telt de model-vragen en geeft een vaste uitkomst terug."""
    calls = []

    def _fn(text, roster, **k):
        calls.append([r["role_id"] for r in roster])
        return uitkomst
    monkeypatch.setattr(scope_nudge, "match_project_to_role", _fn)
    return calls


def test_dezelfde_invoer_wordt_niet_twee_keer_gevraagd(tmp_path, monkeypatch):
    """DE KERN. Hetzelfde project, dezelfde tekst, dezelfde rollen → hetzelfde antwoord."""
    lg = ProjectLedger(str(tmp_path / "p.json"))
    lg.create("owner_role", "Barefoot-claim screenen", "human")
    records = SimpleNamespace(all=lambda: [_role("owner_role", ["curate"]),
                                           _role("harry_hemp", ["openalex_evidence"])])
    noochie = _make_noochie(tmp_path, lg, records)
    calls = _teller(monkeypatch)
    noochie._nudge_scope_matches()
    noochie._nudge_scope_matches()
    noochie._nudge_scope_matches()
    assert len(calls) == 1, f"{len(calls)} model-vragen over ongewijzigde invoer"


def test_een_veranderd_project_wordt_opnieuw_gevraagd(tmp_path, monkeypatch):
    lg = ProjectLedger(str(tmp_path / "p.json"))
    pid = lg.create("owner_role", "Barefoot-claim screenen", "human")
    records = SimpleNamespace(all=lambda: [_role("owner_role", ["curate"]),
                                           _role("harry_hemp", ["openalex_evidence"])])
    noochie = _make_noochie(tmp_path, lg, records)
    calls = _teller(monkeypatch)
    noochie._nudge_scope_matches()
    lg.add_role_message(pid, "nieuwe informatie: het gaat toch om zolen")
    noochie._nudge_scope_matches()
    assert len(calls) == 2


def test_een_veranderde_ROL_wordt_opnieuw_gevraagd(tmp_path, monkeypatch):
    """Zonder dit zou een governance-wijziging pas landen als iemand toevallig het project aanraakt:
    een rol die er een skill bij krijgt kan alsnog de match zijn."""
    lg = ProjectLedger(str(tmp_path / "p.json"))
    lg.create("owner_role", "Barefoot-claim screenen", "human")
    skills = ["openalex_evidence"]
    records = SimpleNamespace(all=lambda: [_role("owner_role", ["curate"]),
                                           _role("harry_hemp", list(skills))])
    noochie = _make_noochie(tmp_path, lg, records)
    calls = _teller(monkeypatch)
    noochie._nudge_scope_matches()
    skills.append("epo_patents")                       # governance geeft er een skill bij
    noochie._nudge_scope_matches()
    assert len(calls) == 2


def test_zonder_model_wordt_er_niets_onthouden(tmp_path, monkeypatch):
    """FAIL-OPEN, en hier zit het gevaar. Een storing die als 'geen match' wordt vastgelegd, zet de
    nudge voor dit project stil tot iemand het aanraakt — precies de stille degradatie van het
    embedding-model. `beantwoord=False` mag dus nooit in de vloer terechtkomen."""
    lg = ProjectLedger(str(tmp_path / "p.json"))
    pid = lg.create("owner_role", "Barefoot-claim screenen", "human")
    records = SimpleNamespace(all=lambda: [_role("owner_role", ["curate"]),
                                           _role("harry_hemp", ["openalex_evidence"])])
    noochie = _make_noochie(tmp_path, lg, records)
    calls = _teller(monkeypatch, uitkomst=(None, False))          # model zweeg
    noochie._nudge_scope_matches()
    noochie._nudge_scope_matches()
    assert len(calls) == 2, "een storing werd als oordeel onthouden"
    assert not lg.scope_nudge_checked(pid)


def test_een_geen_match_MAG_onthouden_worden(tmp_path, monkeypatch):
    """Het model sprak; 'geen match' is een geldig oordeel over deze invoer."""
    lg = ProjectLedger(str(tmp_path / "p.json"))
    pid = lg.create("owner_role", "Barefoot-claim screenen", "human")
    records = SimpleNamespace(all=lambda: [_role("owner_role", ["curate"]),
                                           _role("harry_hemp", ["openalex_evidence"])])
    noochie = _make_noochie(tmp_path, lg, records)
    _teller(monkeypatch, uitkomst=(None, True))
    noochie._nudge_scope_matches()
    assert lg.scope_nudge_checked(pid)


def test_de_vloer_bumpt_updated_at_niet(tmp_path, monkeypatch):
    """Machine-onderhoud versiont niet — zou de vloer `updated_at` bumpen, dan ziet de lus zichzelf
    eeuwig als 'veranderd' en is de vloer meteen weer weg. Zelfde regel als de wiki-broncheck."""
    lg = ProjectLedger(str(tmp_path / "p.json"))
    pid = lg.create("owner_role", "Barefoot-claim screenen", "human")
    voor = lg.get(pid)["updated_at"]
    lg.mark_scope_nudge_checked(pid, "abc123")
    assert lg.get(pid)["updated_at"] == voor


def test_een_al_genudgede_rol_valt_vóór_de_call_af(tmp_path, monkeypatch):
    """POORT 1: deze check stond ACHTER het model. Een rol die dit project al kreeg, kan er niets
    meer opleveren — dus hoort hij niet in de vraag, en blijft er niemand over, dan is de vraag zelf
    overbodig."""
    lg = ProjectLedger(str(tmp_path / "p.json"))
    pid = lg.create("owner_role", "Barefoot-claim screenen", "human")
    lg.mark_scope_nudge(pid, "harry_hemp")
    records = SimpleNamespace(all=lambda: [_role("owner_role", ["curate"]),
                                           _role("harry_hemp", ["openalex_evidence"])])
    noochie = _make_noochie(tmp_path, lg, records)
    calls = _teller(monkeypatch)
    noochie._nudge_scope_matches()
    assert calls == [], "het model werd gebeld terwijl er geen kandidaat meer was"


def test_de_dedup_garantie_blijft_staan(tmp_path, monkeypatch):
    """De check verhuisde naar vóór de call; de garantie mag niet verhuizen. Een rol krijgt nooit een
    tweede nudge voor hetzelfde project — nu doordat hij niet eens in de vraag zit, en doordat de
    machine-check in `match_project_to_role` alleen rollen uit de meegegeven lijst accepteert."""
    lg = ProjectLedger(str(tmp_path / "p.json"))
    pid = lg.create("owner_role", "Barefoot-claim screenen", "human")
    records = SimpleNamespace(all=lambda: [_role("owner_role", ["curate"]),
                                           _role("harry_hemp", ["openalex_evidence"], name="Scientist"),
                                           _role("compliance", ["claims_check"], name="Compliance")])
    noochie = _make_noochie(tmp_path, lg, records)
    monkeypatch.setattr(scope_nudge, "match_project_to_role",
                        lambda text, roster, **k: ({"role_id": "harry_hemp", "name": "Scientist",
                                                    "skill": "openalex_evidence"}, True))
    noochie._nudge_scope_matches()
    lg.add_role_message(pid, "iets veranderts")        # vloer open, dus hij vraagt opnieuw
    noochie._nudge_scope_matches()
    assert lg.get(pid)["scope_nudges"] == ["harry_hemp"]
    nudges = [e for e in lg.get(pid)["log"] if "@Scientist" in (e.get("text") or "")]
    assert len(nudges) == 1


def test_de_vingerafdruk_dekt_de_hele_invoer():
    """Wat het antwoord bepaalt, hoort in de sleutel: de tekst én de kandidaten met hun skills en
    accountabilities. Een sleutel die iets weglaat, geeft een verouderd antwoord terug."""
    r = [{"role_id": "a", "name": "A", "skills": ["s"], "accountabilities": ["x"]}]
    v = scope_nudge.invoer_vinger("tekst", r)
    assert v == scope_nudge.invoer_vinger("tekst", r)                       # stabiel
    assert v != scope_nudge.invoer_vinger("andere tekst", r)                # tekst telt
    assert v != scope_nudge.invoer_vinger("tekst", [{**r[0], "skills": ["t"]}])
    assert v != scope_nudge.invoer_vinger("tekst", [{**r[0], "accountabilities": ["y"]}])
    assert v != scope_nudge.invoer_vinger("tekst", r + [{"role_id": "b", "name": "B",
                                                         "skills": ["u"], "accountabilities": []}])
