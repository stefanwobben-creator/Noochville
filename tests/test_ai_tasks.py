"""Autonome AI-taken per accountability (cockpit 2)."""
from __future__ import annotations

from nooch_village.ai_tasks import AITaskStore
from nooch_village import cockpit2


def test_store_add_for_acc_role(tmp_path):
    st = AITaskStore(str(tmp_path / "ai.json"))
    t = st.add("role_x", 0, "persona_1", "stelt conceptteksten op")
    assert t is not None
    assert [x.id for x in st.for_acc("role_x", 0)] == [t.id]
    assert st.for_acc("role_x", 1) == []
    assert len(st.for_role("role_x")) == 1
    assert st.remove(t.id) and st.for_role("role_x") == []
    # herladen vanaf schijf
    st.add("role_x", 2, "persona_1", "x")
    assert len(AITaskStore(str(tmp_path / "ai.json")).all()) == 1


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


def test_accountability_toont_ai_markering_en_groep(tmp_path):
    dd, st = _st(tmp_path)
    noochie = st.personas.add("Noochie")
    role = "mother_earth__nooch__inmate_in_residence"
    cockpit2.dispatch(dd, "aitask_add", {"role": [role], "acc": ["0"], "agent": [noochie.id],
                                         "wat": ["genereert ideeën"], "next": ["/"]})
    page = cockpit2.render_node(cockpit2._Stores(dd), role, "overview", csrf_token="t")
    assert "aichip" in page and "Noochie" in page and "genereert ideeën" in page
    assert "Autonome AI-taken (1)" in page           # gegroepeerde weergave op de rol
    assert "+ AI" in page                             # markeer-link op accountabilities zonder taak


def test_circle_aggregeert_autonome_ai_taken(tmp_path):
    dd, st = _st(tmp_path)
    noochie = st.personas.add("Noochie")
    role = "mother_earth__nooch__website_developer"
    cockpit2.dispatch(dd, "aitask_add", {"role": [role], "acc": ["0"], "agent": [noochie.id],
                                         "wat": ["schrijft code-concept"], "next": ["/"]})
    page = cockpit2.render_node(cockpit2._Stores(dd), "mother_earth__nooch", "overview", csrf_token="t")
    assert "Autonome AI-taken (1)" in page and "Website Developer" in page and "schrijft code-concept" in page


def test_aitask_modal_fragment(tmp_path):
    dd, st = _st(tmp_path)
    st.personas.add("Noochie")
    role = "mother_earth__nooch__inmate_in_residence"
    frag = cockpit2.render_aitask(cockpit2._Stores(dd), role, 0, csrf_token="t", fragment=True)
    assert "<!doctype" not in frag.lower()
    assert "Autonome AI-taak" in frag and "aitask_add" in frag and "zelfstandig" in frag
