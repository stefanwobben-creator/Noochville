"""De AITaskStore, en de bewaking dat de AUTONOME laag van het scherm weg blijft.

Tot scope 39 kon je op de rolpagina een AI aan een accountability hangen die hem "zelfstandig
uitvoert": een 🎁 als er een passende skill was, een 🤖 als er een gekoppeld was, en een blok
"AI in this role" eronder. Gemeten op 10 september: `kind="autonoom"` werd in de hele codebase
NERGENS buiten `views/overview.py` gelezen. Geen daemon, geen puls, geen planner deed er ooit iets
mee. Het scherm beloofde uitvoering die niet bestond — dezelfde fout als een skill die "gelukt"
meldt zonder iets te doen, één laag hoger.

Wat een rol kan uitvoeren komt uit zijn DNA plus de rugzakken (`skillset.py`), standaard
beschikbaar voor élke rol. Hulp aanbieden doen de stagiairs langs de bestaande verzoek-route.

De STORE blijft: `kind="middel"` (het dorpsmiddel aan een belofte) is wél bedraad, via
`skill_links` naar `gap_classifier` en naar het stoplicht in het roloverleg.
"""
from __future__ import annotations

from nooch_village.ai_tasks import AITaskStore, KIND_MIDDEL
from nooch_village import acc_ids, cockpit2

ROLE = "mother_earth__nooch__website_developer"


def test_store_add_for_acc_role(tmp_path):
    st = AITaskStore(str(tmp_path / "ai.json"))
    t = st.add("role_x", "acc_a", "persona_1", "schrijft de code")
    assert t is not None
    assert [x.id for x in st.for_acc("role_x", "acc_a")] == [t.id]
    assert st.for_acc("role_x", "acc_b") == []
    assert len(st.for_role("role_x")) == 1
    assert st.remove(t.id) and st.for_role("role_x") == []
    st.add("role_x", "acc_c", "persona_1", "x")
    assert len(AITaskStore(str(tmp_path / "ai.json")).all()) == 1


def test_persona_backpack(tmp_path):
    from nooch_village.personas import PersonaStore
    ps = PersonaStore(str(tmp_path / "p.json"))
    p = ps.add("Codie", skills=["schrijft de code"])
    assert p.skills == ["schrijft de code"]
    ps.add_skill(p.id, "draait testscripts")
    ps.add_skill(p.id, "schrijft de code")              # idempotent
    assert ps.get(p.id).skills == ["schrijft de code", "draait testscripts"]
    ps.remove_skill(p.id, "schrijft de code")
    assert ps.get(p.id).skills == ["draait testscripts"]


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


# ── de autonome laag is van het scherm ───────────────────────────────────────

def test_rolpagina_belooft_geen_autonome_uitvoering_meer(tmp_path):
    """Ook mét een perfect passende persona-skill verschijnt er geen 🎁 en geen AI-blok."""
    dd, st = _st(tmp_path)
    st.personas.add("Codie", skills=["performance tuning"])   # matchte eerder op 'performance'
    page = cockpit2.render_node(cockpit2._Stores(dd), ROLE, "overview", csrf_token="t")
    assert "🎁" not in page and "ai-gift" not in page
    assert "AI in this role" not in page
    assert "does autonomously" not in page


def test_een_bestaande_autonome_rij_wekt_het_scherm_niet(tmp_path):
    """De oude rijen blijven in de store staan (bewust; weggooien is een apart besluit). Ze mogen
    het scherm niet terug tot leven wekken — anders lekt de verwijderde belofte via de data."""
    dd, st = _st(tmp_path)
    codie = st.personas.add("Codie", skills=["schrijft de code"])
    aid = acc_ids.acc_id_at(st.records.get(ROLE).definition, 0)
    st.ai.add(ROLE, aid, codie.id, "schrijft de code")        # legacy autonome koppeling
    page = cockpit2.render_node(cockpit2._Stores(dd), ROLE, "overview", csrf_token="t")
    assert "AI in this role" not in page
    assert "🤖" not in page


def test_de_verwijderde_acties_bestaan_niet_meer(tmp_path):
    """Poort-tests toetsen gedrag ACHTER een actie; deze toetst dat de actie zelf weg is. Zonder
    dit kan een tak stil terugkeren zonder dat iets rood wordt."""
    for actie in ("aitask_add", "aitask_remove", "persona_skill_add"):
        assert actie not in cockpit2.ACTIONS, actie


# ── wat er voor in de plaats kwam: de middelen-modal ─────────────────────────

def test_middelen_modal_toont_alleen_middelen(tmp_path):
    dd, st = _st(tmp_path)
    st.personas.add("Codie", skills=["schrijft de code"])
    _st2 = cockpit2._Stores(dd)
    aid = acc_ids.acc_id_at(_st2.records.get(ROLE).definition, 0)
    frag = cockpit2.render_middelen(_st2, ROLE, aid, csrf_token="t", fragment=True)
    assert "<!doctype" not in frag.lower()
    assert "Village resources on this commitment" in frag
    # geen rugzak-select en geen backpack-uitbreider meer
    assert "backpack" not in frag.lower()
    assert "::schrijft de code" not in frag
    # wél de picker voor dorpsmiddelen
    assert "skilllink_add" in frag


def test_middelen_modal_laat_een_gelegd_middel_losmaken(tmp_path):
    dd, st = _st(tmp_path)
    aid = acc_ids.acc_id_at(st.records.get(ROLE).definition, 0)
    t = st.ai.add_link(ROLE, aid, "site_health")
    assert t.kind == KIND_MIDDEL
    frag = cockpit2.render_middelen(cockpit2._Stores(dd), ROLE, aid, csrf_token="t", fragment=True)
    assert "middel_remove" in frag and t.id in frag


def test_de_ingang_naar_de_modal_staat_op_de_belofte(tmp_path):
    """Zonder ingang is de picker onbereikbaar en kun je een gelegd middel nergens losmaken."""
    dd, st = _st(tmp_path)
    page = cockpit2.render_node(cockpit2._Stores(dd), ROLE, "overview", csrf_token="t")
    assert "/middelen?role=" in page
    # leesweergave (auth uit, geen csrf): geen beheerknop
    kaal = cockpit2.render_node(cockpit2._Stores(dd), ROLE, "overview", csrf_token="")
    assert "/middelen?role=" not in kaal
