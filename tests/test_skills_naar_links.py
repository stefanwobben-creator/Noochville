"""Taak 5 — opdrogen: DNA-skills naar koppelingen op accountabilities.

Voorbereiding, mens-gated: de founder draait zelf eerst de dry-run. Het commando raakt het
rol-DNA NOOIT aan — dat is een governance-ronde (remove_skills), geen bypass.
"""
from __future__ import annotations

from nooch_village import skills_naar_links
from nooch_village.ai_tasks import AITaskStore
from nooch_village.governance import Records
from nooch_village.models import Record, RecordType, RoleDefinition


def _recs(tmp_path):
    r = Records(str(tmp_path / "rec.json"))
    # De acceptatie-case: één middel (keywords_everywhere) in twee rol-DNA's.
    r.put(Record(id="librarian", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(
                     purpose="hoeder van de woordenschat",
                     accountabilities=["kandidaat-woorden beoordelen",
                                       "zoekvolume bij een woord zoeken"],
                     domains=["bibliotheek"],
                     skills=["keywords_everywhere", "keyword_review"])))
    r.put(Record(id="billy", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(
                     purpose="buzz volgen",
                     accountabilities=["zoekvolume van kernwoorden bijhouden"],
                     skills=["keywords_everywhere"])))
    return r


def _ai(tmp_path):
    return AITaskStore(str(tmp_path / "ai.json"))


# ── De dry-run ───────────────────────────────────────────────────────────────

def test_plan_stelt_per_rol_de_beste_belofte_voor(tmp_path):
    plan = skills_naar_links.plan(_recs(tmp_path).all(), _ai(tmp_path))
    ke = [r for r in plan if r["skill"] == "keywords_everywhere"]
    assert {r["role"] for r in ke} == {"librarian", "billy"}          # één middel, twee rollen
    for r in ke:
        assert r["status"] == "voorstel"
        assert "zoekvolume" in r["acc"]                                # de passende belofte
        assert r["acc_id"]


def test_beslisskill_bij_domeinhouder_is_gewoon_een_voorstel(tmp_path):
    plan = skills_naar_links.plan(_recs(tmp_path).all(), _ai(tmp_path))
    kr = next(r for r in plan if r["skill"] == "keyword_review")
    assert kr["role"] == "librarian" and kr["status"] == "voorstel"


def test_beslisskill_buiten_de_domeinhouder_wordt_niet_voorgesteld(tmp_path):
    recs = _recs(tmp_path)
    rec = recs.get("billy")
    rec.definition.skills.append("keyword_review")     # per ongeluk in het DNA
    recs.put(rec)
    plan = skills_naar_links.plan(recs.all(), _ai(tmp_path))
    r = next(x for x in plan if x["role"] == "billy" and x["skill"] == "keyword_review")
    assert r["status"] == "domeinpoort" and r["acc_id"] == ""


def test_geen_passende_belofte_raadt_niet(tmp_path):
    recs = Records(str(tmp_path / "r2.json"))
    recs.put(Record(id="rol_x", type=RecordType.ROLE, parent="w",
                    definition=RoleDefinition(purpose="p",
                                              accountabilities=["kantoorplanten water geven"],
                                              skills=["shopify_sales"])))
    r = skills_naar_links.plan(recs.all(), _ai(tmp_path))[0]
    assert r["status"] == "geen match" and r["acc_id"] == ""


def test_rapport_is_mensentaal(tmp_path):
    rap = skills_naar_links.rapport(
        skills_naar_links.plan(_recs(tmp_path).all(), _ai(tmp_path)), dry_run=True)
    assert "DROOGLOOP" in rap and "er is niets gewijzigd" in rap
    assert "librarian" in rap and "billy" in rap
    assert "keywords_everywhere" in rap
    assert "Het rol-DNA is NIET aangeraakt" in rap


# ── De echte run ─────────────────────────────────────────────────────────────

def test_run_legt_de_links_en_is_idempotent(tmp_path):
    recs, ai = _recs(tmp_path), _ai(tmp_path)
    gelegd = skills_naar_links.voer_uit(recs.all(), ai)
    assert len(gelegd) == 3                                   # 2× KE + 1× keyword_review

    # Eén middel, twee links — de dubbeling is opgelost zonder tweede implementatie.
    ke_links = [t for t in ai.all() if t.skill == "keywords_everywhere"]
    assert {t.role for t in ke_links} == {"librarian", "billy"}
    assert all(t.kind == "middel" and t.acc_id for t in ke_links)

    assert skills_naar_links.voer_uit(recs.all(), ai) == []    # idempotent
    assert len([t for t in ai.all() if t.skill == "keywords_everywhere"]) == 2

    # …en bij een tweede plan staat alles op 'al gekoppeld'.
    plan = skills_naar_links.plan(recs.all(), ai)
    assert {r["status"] for r in plan if r["skill"] == "keywords_everywhere"} == {"al gekoppeld"}


def test_run_raakt_het_rol_dna_nooit_aan(tmp_path):
    """Geen governance-bypass: opdrogen van het DNA loopt via remove_skills, niet via dit pad."""
    recs, ai = _recs(tmp_path), _ai(tmp_path)
    voor = {r.id: sorted(r.definition.skills) for r in recs.all()}
    skills_naar_links.voer_uit(recs.all(), ai)
    na = {r.id: sorted(r.definition.skills)
          for r in Records(str(tmp_path / "rec.json")).all()}
    assert voor == na


def test_run_logt_in_de_kroniek(tmp_path):
    from nooch_village.skill_links import SkillLinkKroniek
    recs, ai = _recs(tmp_path), _ai(tmp_path)
    kroniek = SkillLinkKroniek(str(tmp_path / "k.jsonl"))
    skills_naar_links.voer_uit(recs.all(), ai, kroniek=kroniek)
    rows = kroniek.all_records()
    assert len(rows) == 3
    assert all(r["action"] == "gelegd" and "opdrogen" in r["reden"] for r in rows)
