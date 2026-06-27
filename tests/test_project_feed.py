"""Project-update-model: gestructureerde feed met auteur (mens/AI/rol) en soort (update/reactie)."""
from __future__ import annotations

from nooch_village import cockpit2


def _setup(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rid = "mother_earth__nooch__website_developer"
    codie = st.personas.add("Codie")
    st.assign.assign(rid, "persona", codie.id)
    pid = st.projects.create(rid, "Checkout flow", "human")
    return dd, rid, pid, codie


def test_add_feed_entry_model(tmp_path):
    dd, rid, pid, codie = _setup(tmp_path)
    st = cockpit2._Stores(dd)
    e = st.projects.add_feed_entry(pid, "versie klaar", kind="update",
                                   author_type="persona", author_id=codie.id)
    assert e["kind"] == "update" and e["author"] == {"type": "persona", "id": codie.id}
    assert e["id"] and e["at"]
    # ongeldige waarden vallen terug
    e2 = st.projects.add_feed_entry(pid, "x", kind="zomaar", author_type="alien")
    assert e2["kind"] == "comment" and e2["author"]["type"] == "human"
    assert st.projects.add_feed_entry(pid, "   ") is None    # lege tekst


def test_feed_render_auteur_en_soort(tmp_path):
    dd, rid, pid, codie = _setup(tmp_path)
    cockpit2.dispatch(dd, "proj_feed", {"pid": [pid], "author": [f"persona:{codie.id}"],
                                        "text": ["eerste versie staat klaar"], "next": ["/"]})
    cockpit2.dispatch(dd, "proj_feed", {"pid": [pid], "author": ["human:"],
                                        "text": ["mooi, ik publiceer"], "next": ["/"]})
    frag = cockpit2.render_project(cockpit2._Stores(dd), pid, csrf_token="t", fragment=True)
    # AI-update toont AI-naam + @rolnaam; menselijke reactie toont 'Jij' (geen update-badge meer)
    assert "Codie" in frag and "eerste versie staat klaar" in frag
    assert "frole" in frag and "Jij" in frag
    # composer = directe textarea + verborgen auteur 'human:' (een reactie is van jou)
    assert "comp-form" in frag and "value='human:'" in frag


def test_ai_praat_mee_op_verzoek(tmp_path):
    dd, rid, pid, codie = _setup(tmp_path)
    # knop zichtbaar omdat de eigenaar-rol een AI-inwoner heeft
    frag = cockpit2.render_project(cockpit2._Stores(dd), pid, csrf_token="t", fragment=True)
    assert "ai-ask-btn" in frag and "Vraag Codie" in frag
    # AI plaatst een reactie (LLM gestubd)
    ok = cockpit2._ai_reply(cockpit2._Stores(dd), pid, ask=lambda prompt: "Stap 1: meet de conversie.")
    assert ok
    last = cockpit2._Stores(dd).projects.get(pid)["log"][-1]
    assert last["author"] == {"type": "persona", "id": codie.id} and "Stap 1" in last["text"]


def test_ai_praat_mee_zonder_inwoner(tmp_path):
    dd, rid, pid, codie = _setup(tmp_path)
    pid2 = cockpit2._Stores(dd).projects.create("mother_earth__nooch__circle_lead", "X", "human")
    assert cockpit2._ai_reply(cockpit2._Stores(dd), pid2, ask=lambda p: "x") is False


def test_oude_log_entries_blijven_leesbaar(tmp_path):
    dd, rid, pid, codie = _setup(tmp_path)
    st = cockpit2._Stores(dd)
    # oud schema rechtstreeks injecteren
    p = st.projects.get(pid)
    p.setdefault("log", []).append({"who": "rol", "text": "oude update", "at": 1.0})
    p["log"].append({"who": "mens", "text": "oude reactie", "at": 2.0})
    st.projects._save()
    frag = cockpit2.render_project(cockpit2._Stores(dd), pid, csrf_token="t", fragment=True)
    assert "oude update" in frag and "oude reactie" in frag      # oud schema blijft leesbaar


def test_human_reactie_zet_worked_false(tmp_path):
    dd, rid, pid, codie = _setup(tmp_path)
    st = cockpit2._Stores(dd)
    st.projects.add_feed_entry(pid, "klaar", kind="update", author_type="persona", author_id=codie.id)
    st.projects.add_feed_entry(pid, "graag aanpassen", kind="comment", author_type="human")
    assert cockpit2._Stores(dd).projects.get(pid).get("worked") is False
