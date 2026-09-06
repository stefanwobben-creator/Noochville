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


# ── de knop ────────────────────────────────────────────────────────────────────────────────────

def test_g_aanwijzen_is_exclusief(tmp_path, ledger):
    """Twee vlaggen zou betekenen dat de volgorde in het bestand bepaalt welke lijst draait."""
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    a = ledger.checklist_add(pid, title="Functionaliteiten")
    b = ledger.checklist_add(pid, title="Acties uit overleg")
    assert ledger.set_checklist_uitvoer(pid, a["id"]) is True
    assert uitvoerlijst(ledger.get(pid))["id"] == a["id"]

    assert ledger.set_checklist_uitvoer(pid, b["id"]) is True    # van gedachten veranderd
    cls = {c["id"]: c for c in ledger.get(pid)["checklists"]}
    assert cls[b["id"]]["uitvoer"] is True and "uitvoer" not in cls[a["id"]]
    assert uitvoerlijst(ledger.get(pid))["id"] == b["id"]


def test_h_aanwijzen_van_iets_dat_niet_bestaat(tmp_path, ledger):
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    cl = ledger.checklist_add(pid, title="Lijst")
    assert ledger.set_checklist_uitvoer(pid, "bestaat-niet") is False
    assert ledger.set_checklist_uitvoer("geen-project", cl["id"]) is False


def test_i_aanwijzen_is_een_schrijfpad(tmp_path, ledger):
    """De concurrency-ratchet vangt dit ook, maar dan zonder uit te leggen waaróm: elk pad dat
    _save aanroept hoort onder dezelfde lock als de rest."""
    from nooch_village.projects import _WRITE_METHODS
    assert "set_checklist_uitvoer" in _WRITE_METHODS


# ── de rol en de lijst, end to end ─────────────────────────────────────────────────────────────

def test_j_de_rol_draait_een_hernoemde_lijst(tmp_path, ledger):
    """Nina's route: haar lijst heet anders, zij accepteert een aanbod, de rol pakt het op."""
    inh = _inhabitant(tmp_path, ledger)
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    cl = ledger.checklist_add(pid, title="Acties uit overleg")
    ledger.check_add(pid, cl["id"], "bel de fabriek")                 # mens-item, geen skill
    assert inh._project_checklist(ledger.get(pid)) is None            # nog geen werk voor de rol

    ledger.check_add(pid, cl["id"], "zoek de studies op",
                     skill="openalex_evidence", payload={"term": "barefoot"})
    assert inh._project_checklist(ledger.get(pid))["id"] == cl["id"]  # nu wel

    inh._execute_checklist(ledger.get(pid), TODAY)
    items = ledger.get(pid)["checklists"][0]["items"]
    assert items[1]["done"] is True                                   # het skill-item draaide
    assert items[0]["done"] is False                                  # het mens-item niet
    logtxt = " ".join(e["text"] for e in ledger.get(pid).get("log", []))
    assert "Study on barefoot" in logtxt


def test_k_geen_akkoord_poort_op_een_handgemaakte_lijst(tmp_path, ledger):
    """De twee routes naar uitvoering, allebei met een mens ervoor: óf het gegenereerde plan is
    goedgekeurd (`akkoord`), óf een mens accepteerde per item een aanbod. Een handgemaakte lijst
    draagt geen akkoord-vraag en hoort er ook geen te krijgen."""
    from nooch_village.projects import plan_wacht_op_akkoord
    inh = _inhabitant(tmp_path, ledger)
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    cl = ledger.checklist_add(pid, title="What's needed")
    ledger.check_add(pid, cl["id"], "zoek uit", skill="openalex_evidence", payload={"term": "x"})
    assert plan_wacht_op_akkoord(ledger.get(pid)) is False
    inh._execute_checklist(ledger.get(pid), TODAY)
    assert ledger.get(pid)["checklists"][0]["items"][0]["done"] is True


def test_l_het_plan_wint_van_een_los_lijstje(tmp_path, ledger):
    """Een project met zowel een gegenereerd plan als een eigen lijstje: de rol werkt het plan af,
    en de akkoord-poort blijft dus staan."""
    inh = _inhabitant(tmp_path, ledger)
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    eigen = ledger.checklist_add(pid, title="Acties uit overleg")
    ledger.check_add(pid, eigen["id"], "zoek uit", skill="openalex_evidence", payload={"term": "x"})
    plan = ledger.checklist_add(pid, title=PREP_CHECKLIST_TITLE, akkoord=False)
    ledger.check_add(pid, plan["id"], "andere zoekopdracht",
                     skill="openalex_evidence", payload={"term": "y"})

    assert inh._project_checklist(ledger.get(pid))["id"] == plan["id"]
    inh._execute_checklist(ledger.get(pid), TODAY)
    cls = {c["id"]: c for c in ledger.get(pid)["checklists"]}
    assert cls[plan["id"]]["items"][0]["done"] is False               # wacht op akkoord
    assert cls[eigen["id"]]["items"][0]["done"] is False              # en dit is niet zijn lijst


# ── de UI ──────────────────────────────────────────────────────────────────────────────────────

def _html(ledger, pid, rw=True):
    from nooch_village.views.checklists import _checklists_html
    return _checklists_html(ledger.get(pid), "csrf" if rw else "", pid, "/projects", rw)


def test_m_bij_een_lijst_geen_ruis(tmp_path, ledger):
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    cl = ledger.checklist_add(pid, title="Acties uit overleg")
    ledger.check_add(pid, cl["id"], "zoek uit", skill="openalex_evidence")
    html = _html(ledger, pid)
    assert "the role works this list" not in html                     # niets te kiezen, niets te melden
    assert "checklist_uitvoer" not in html


def test_n_de_stille_valkuil_wordt_zichtbaar(tmp_path, ledger):
    """Zonder deze melding accepteer je een aanbod op de verkeerde lijst en gebeurt er nooit iets,
    zonder enig spoor. Dit raakt vandaag drie projecten."""
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    plan = ledger.checklist_add(pid, title=PREP_CHECKLIST_TITLE)
    ledger.check_add(pid, plan["id"], "a", skill="openalex_evidence")
    eigen = ledger.checklist_add(pid, title="Acties uit overleg")
    ledger.check_add(pid, eigen["id"], "b", skill="openalex_evidence")

    html = _html(ledger, pid)
    assert "the role works this list" in html                         # op het plan
    assert "the role doesn't work this list" in html                  # op het eigen lijstje
    assert "checklist_uitvoer" in html                                # met de knop erbij

    ledger.set_checklist_uitvoer(pid, eigen["id"])                    # één klik
    html2 = _html(ledger, pid)
    # De melding wisselt van lijst mee: het plan ligt nu stil, en dát hoor je te zien. Anders
    # verdwijnt een uitvoerplan geruisloos uit beeld omdat je een ander lijstje aanwees.
    assert html2.count("the role works this list") == 1
    assert html2.count("the role doesn't work this list") == 1
    assert html2.index("the role doesn't work this list") < html2.index("the role works this list")


def test_o_een_lijst_zonder_skill_items_krijgt_geen_knop(tmp_path, ledger):
    """De knop hoort alleen te staan waar hij iets oplost: een lijst met werk dat blijft liggen."""
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    plan = ledger.checklist_add(pid, title=PREP_CHECKLIST_TITLE)
    ledger.check_add(pid, plan["id"], "a", skill="openalex_evidence")
    notities = ledger.checklist_add(pid, title="Notities")
    ledger.check_add(pid, notities["id"], "denk hier nog over na")
    html = _html(ledger, pid)
    assert "the role works this list" in html
    assert "the role doesn't work this list" not in html
    assert "checklist_uitvoer" not in html


def test_p_leesmodus_toont_de_stand_zonder_knop(tmp_path, ledger):
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    plan = ledger.checklist_add(pid, title=PREP_CHECKLIST_TITLE)
    ledger.check_add(pid, plan["id"], "a", skill="openalex_evidence")
    eigen = ledger.checklist_add(pid, title="Acties uit overleg")
    ledger.check_add(pid, eigen["id"], "b", skill="openalex_evidence")
    html = _html(ledger, pid, rw=False)
    assert "the role doesn't work this list" in html and "checklist_uitvoer" not in html


def test_q_cockpit_actie_is_geregistreerd_en_gelabeld():
    import inspect
    from nooch_village import cockpit2
    assert cockpit2.ACTIONS["checklist_uitvoer"] is cockpit2._act_checklist_uitvoer
    src = inspect.getsource(cockpit2._act_checklist_uitvoer)
    assert "# AUTHZ:" in src and "_role_gate" in src
