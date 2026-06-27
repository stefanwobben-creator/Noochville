"""Autonome AI op accountability (cockpit 2): genest, geselecteerd uit het rugzakje, met cadeau-match."""
from __future__ import annotations

from nooch_village.ai_tasks import AITaskStore
from nooch_village import cockpit2


def test_store_add_for_acc_role(tmp_path):
    st = AITaskStore(str(tmp_path / "ai.json"))
    t = st.add("role_x", 0, "persona_1", "schrijft de code")
    assert t is not None
    assert [x.id for x in st.for_acc("role_x", 0)] == [t.id]
    assert st.for_acc("role_x", 1) == []
    assert len(st.for_role("role_x")) == 1
    assert st.remove(t.id) and st.for_role("role_x") == []
    st.add("role_x", 2, "persona_1", "x")
    assert len(AITaskStore(str(tmp_path / "ai.json")).all()) == 1


def test_persona_rugzak(tmp_path):
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


def test_ai_genest_onder_accountability(tmp_path):
    dd, st = _st(tmp_path)
    codie = st.personas.add("Codie", skills=["schrijft de code"])
    role = "mother_earth__nooch__website_developer"
    cockpit2.dispatch(dd, "aitask_add", {"role": [role], "acc": ["0"],
                                         "pick": [f"{codie.id}::schrijft de code"], "next": ["/"]})
    page = cockpit2.render_node(cockpit2._Stores(dd), role, "overview", csrf_token="t")
    # subtiele AI-marker op de accountability + één gebundeld overzicht (niet dubbel)
    assert "ai-on" in page and "AI in deze rol" in page
    assert "Codie" in page and "schrijft de code" in page
    assert "acc-sub" not in page                  # geen herhaalde chip per regel meer
    assert "Autonome AI-taken" not in page


def test_cadeau_icoon_bij_match(tmp_path):
    dd, st = _st(tmp_path)
    # skill 'performance' matcht 'Optimzing website performance'
    st.personas.add("Codie", skills=["performance tuning"])
    role = "mother_earth__nooch__website_developer"
    page = cockpit2.render_node(cockpit2._Stores(dd), role, "overview", csrf_token="t")
    assert "ai-gift" in page and "🎁" in page


def test_geen_cadeau_en_geen_plusai_zonder_match(tmp_path):
    dd, st = _st(tmp_path)
    st.personas.add("Codie", skills=["iets totaal anders xyz"])
    role = "mother_earth__nooch__website_developer"
    page = cockpit2.render_node(cockpit2._Stores(dd), role, "overview", csrf_token="t")
    # geen discovery-affordance als er niets past, en de oude '+ AI' bestaat niet meer
    assert "🎁" not in page and "+ AI" not in page


def test_modal_selecteert_uit_rugzak_geen_vrije_tekst(tmp_path):
    dd, st = _st(tmp_path)
    codie = st.personas.add("Codie", skills=["schrijft de code"])
    role = "mother_earth__nooch__website_developer"
    frag = cockpit2.render_aitask(cockpit2._Stores(dd), role, 0, csrf_token="t", fragment=True)
    assert "<!doctype" not in frag.lower()
    assert "selecteert" in frag and f"{codie.id}::schrijft de code" in frag
    assert "Rugzak van een AI uitbreiden" in frag


def test_persona_skill_add_via_dispatch(tmp_path):
    dd, st = _st(tmp_path)
    codie = st.personas.add("Codie")
    cockpit2.dispatch(dd, "persona_skill_add", {"agent": [codie.id], "skill": ["schrijft de code"], "next": ["/"]})
    assert cockpit2._Stores(dd).personas.get(codie.id).skills == ["schrijft de code"]
