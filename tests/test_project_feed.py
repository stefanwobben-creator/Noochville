"""Project-update-model: gestructureerde feed met auteur (mens/AI/rol) en soort (update/reactie)."""
from __future__ import annotations

import pytest

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
                                        "text": ["eerste versie staat klaar"], "next": ["/"]}, username="guest")
    cockpit2.dispatch(dd, "proj_feed", {"pid": [pid], "author": ["human:"],
                                        "text": ["mooi, ik publiceer"], "next": ["/"]}, username="guest")
    frag = cockpit2.render_project(cockpit2._Stores(dd), pid, csrf_token="t", fragment=True)
    # AI-update toont AI-naam + @rolnaam; menselijke reactie toont 'Jij' (geen update-badge meer)
    assert "Codie" in frag and "eerste versie staat klaar" in frag
    assert "frole" in frag and "Jij" in frag
    # composer = directe textarea + verborgen auteur 'human:' (een reactie is van jou)
    assert "comp-form" in frag and "value='human:'" in frag


def test_eigen_comment_wijzigen_verwijderen(tmp_path):
    dd, rid, pid, codie = _setup(tmp_path)
    cockpit2.dispatch(dd, "proj_feed", {"pid": [pid], "author": ["human:"], "text": ["mijn comment"], "next": ["/"]}, username="guest")
    cockpit2.dispatch(dd, "proj_feed", {"pid": [pid], "author": [f"persona:{codie.id}"],
                                        "text": ["AI update"], "next": ["/"]}, username="guest")
    frag = cockpit2.render_project(cockpit2._Stores(dd), pid, csrf_token="t", fragment=True)
    # eigen comment: edit/delete; AI-update: niet (dus precies 1 keer feed_remove)
    assert "Wijzigen" in frag and frag.count("feed_remove") == 1
    eid = cockpit2._Stores(dd).projects.get(pid)["log"][0]["id"]
    cockpit2.dispatch(dd, "feed_edit", {"pid": [pid], "item": [eid], "text": ["aangepast"], "next": ["/"]}, username="guest")
    assert cockpit2._Stores(dd).projects.get(pid)["log"][0]["text"] == "aangepast"
    cockpit2.dispatch(dd, "feed_remove", {"pid": [pid], "item": [eid], "next": ["/"]}, username="guest")
    assert len(cockpit2._Stores(dd).projects.get(pid)["log"]) == 1


def test_mention_maakt_notificatie_en_highlight(tmp_path):
    dd, rid, pid, codie = _setup(tmp_path)
    person = cockpit2._Stores(dd).people.all()[0]
    cockpit2.dispatch(dd, "proj_feed", {"pid": [pid], "author": ["human:"],
                                        "text": ["hoi @Website Developer kijk even"], "next": ["/"]}, username="guest")
    notes = cockpit2._Stores(dd).notif.all()
    assert len(notes) == 1 and notes[0]["target_type"] == "role" and notes[0]["target_id"] == rid
    # highlight in de bubble
    frag = cockpit2.render_project(cockpit2._Stores(dd), pid, csrf_token="t", fragment=True)
    assert "class='ment'>@Website Developer" in frag


def test_mention_autocomplete_data_in_modal(tmp_path):
    dd, rid, pid, codie = _setup(tmp_path)
    node = cockpit2.render_node(cockpit2._Stores(dd), rid, "projects", csrf_token="t")
    assert "__mentions=" in node and "mentionWire" in node and "Website Developer" in node


@pytest.mark.xfail(reason="notificatie-aggregatie op /person is deferred; de person-view heeft in "
                          "deze pass alleen de 'rollen'-tab, de rest is read-only placeholder", strict=False)
def test_persoonspagina_toont_notificatie(tmp_path):
    dd, rid, pid, codie = _setup(tmp_path)
    person = cockpit2._Stores(dd).people.all()[0]
    cockpit2._Stores(dd).assign.assign(rid, "person", person.id)
    cockpit2.dispatch(dd, "proj_feed", {"pid": [pid], "author": ["human:"],
                                        "text": ["@Website Developer to-do"], "next": ["/"]}, username="guest")
    page = cockpit2.render_person(cockpit2._Stores(dd), person.id)
    assert "🔔 Notificaties" in page and "1 nieuw" in page


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
