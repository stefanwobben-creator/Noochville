"""De uitvoerlijst: welke checklist werkt de rol af?

De TITEL was de schakelaar. Alleen een lijst die letterlijk "Uitvoerplan" heette werd uitgevoerd, en
alleen daarop bood de cockpit een skill aan. Nina's "Acties uit overleg" en Lottes "What's needed"
kregen daardoor nooit een aanbod en werden nooit gedraaid, ook niet nadat hun rollen skills hadden.

Een kopje hoort geen schakelaar te zijn, dus de schakelaar kreeg een eigen veld (`uitvoer`), net als
`akkoord` in de scope ervoor. Deze tests leggen de vier keuzeregels vast, de klep die voorkomt dat de
rol zich met een overleglijstje gaat bemoeien, en de knop voor de projecten met meer dan één lijst.

Thread-vrij: geen inwoner-thread, geen echte LLM-call.
"""
from __future__ import annotations
import pytest
from types import SimpleNamespace

from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus
from nooch_village.skills import SkillRegistry, Skill
from nooch_village.projects import ProjectLedger, uitvoerlijst, PREP_CHECKLIST_TITLE

TODAY = "2026-09-05"


class _ResearchSkill(Skill):
    name = "openalex_evidence"
    description = "fake research skill (term → hits)"

    def run(self, payload, context):
        term = (payload or {}).get("term", "")
        return {"term": term, "total": 1,
                "hits": [{"title": f"Study on {term}", "year": 2021, "citations": 7, "topic": "footwear"}]}


@pytest.fixture
def ledger(tmp_path):
    return ProjectLedger(str(tmp_path / "projects.json"))


def _inhabitant(tmp_path, ledger, rid="harry_hemp"):
    reg = SkillRegistry()
    reg.register(_ResearchSkill())
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0"}, data_dir=str(tmp_path),
                          projects=ledger, records=None)
    rec = Record(id=rid, type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="waarheid", accountabilities=["research"],
                                           domains=[], skills=["openalex_evidence"]), source="sensed")
    return Inhabitant(rec, EventBus(name="test"), reg, ctx)


def _lijst(titel, items=(), **extra):
    """items: (tekst, skill|None)."""
    cl = {"id": titel[:8].lower().replace(" ", ""), "title": titel,
          "items": [{"id": f"i{n}", "text": t, "done": False, **({"skill": s} if s else {})}
                    for n, (t, s) in enumerate(items)]}
    cl.update(extra)
    return cl


# ── de vier keuzeregels ────────────────────────────────────────────────────────────────────────

def test_a_regel1_een_aangewezen_lijst_wint_altijd():
    p = {"checklists": [_lijst(PREP_CHECKLIST_TITLE, [("a", "openalex_evidence")]),
                        _lijst("Acties uit overleg", [("b", "openalex_evidence")], uitvoer=True)]}
    assert uitvoerlijst(p)["title"] == "Acties uit overleg"     # ook boven de Uitvoerplan-naam


def test_b_regel2_de_uitvoerplan_naam_blijft_werken():
    """Zonder deze regel zou elk bestaand project een migratie nodig hebben."""
    p = {"checklists": [_lijst("Notities"), _lijst(PREP_CHECKLIST_TITLE, [("a", "openalex_evidence")])]}
    assert uitvoerlijst(p)["title"] == PREP_CHECKLIST_TITLE


def test_c_regel3_een_enkele_lijst_met_werk_erin():
    """Dit is de regel die Nina en Lotte bedient zonder dat ze iets hernoemen."""
    p = {"checklists": [_lijst("Acties uit overleg", [("bel", None), ("zoek uit", "openalex_evidence")])]}
    assert uitvoerlijst(p)["title"] == "Acties uit overleg"


def test_d_regel3_de_klep_geen_skill_geen_bemoeienis():
    """DE KLEP. Zonder de skill-voorwaarde zou de rol Nina's overleglijstje gaan verzorgen, niets
    kunnen, en het project met een hulpvraag van ACTIEF trekken. De rol raakt een lijst pas aan als
    een mens er werk in heeft gelegd, en dat leggen gebeurt door een aanbod te accepteren."""
    p = {"checklists": [_lijst("Acties uit overleg", [("bel de fabriek", None), ("mail Wytse", None)])]}
    assert uitvoerlijst(p) is None


def test_e_regel4_meerdere_lijsten_zonder_aanwijzing_is_geen_gok():
    p = {"checklists": [_lijst("Functionaliteiten", [("a", "openalex_evidence")]),
                        _lijst("Acties uit overleg", [("b", "openalex_evidence")])]}
    assert uitvoerlijst(p) is None


@pytest.mark.parametrize("p", [None, {}, {"checklists": []}, {"checklists": None}])
def test_f_geen_lijsten_geen_uitvoerlijst(p):
    assert uitvoerlijst(p) is None
