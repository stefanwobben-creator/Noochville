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
    # de expliciete 'Vraag …'-knop is verwijderd: een rol nodig je nu uit via @mention in een reactie
    frag = cockpit2.render_project(cockpit2._Stores(dd), pid, csrf_token="t", fragment=True)
    assert "ai-ask-btn" not in frag and "Vraag Codie" not in frag
    # AI plaatst een reactie (LLM gestubd)
    ok = cockpit2._ai_reply(cockpit2._Stores(dd), pid, ask=lambda prompt: "Stap 1: meet de conversie.")
    assert ok
    last = cockpit2._Stores(dd).projects.get(pid)["log"][-1]
    assert last["author"] == {"type": "persona", "id": codie.id} and "Stap 1" in last["text"]


def test_ai_praat_mee_zonder_inwoner(tmp_path):
    dd, rid, pid, codie = _setup(tmp_path)
    pid2 = cockpit2._Stores(dd).projects.create("mother_earth__nooch__circle_lead", "X", "human")
    assert cockpit2._ai_reply(cockpit2._Stores(dd), pid2, ask=lambda p: "x") is False


def test_ai_reply_prompt_bevat_accountabilities_en_toetsinstructie(tmp_path):
    # de @mention-reply moet de rol laten TOETSEN aan haar accountabilities/skills en een concrete stap
    # voorstellen — dus die context + de toets-instructie horen in de prompt te staan.
    dd, rid, pid, codie = _setup(tmp_path)
    gezien = {}
    cockpit2._ai_reply(cockpit2._Stores(dd), pid,
                       ask=lambda prompt: gezien.setdefault("p", prompt) or "ok")
    p = gezien["p"]
    assert "Jouw accountabilities:" in p and "Jouw skills" in p
    assert "Toets de dialoog" in p                      # de relevantie-toets-instructie
    assert "zal ik" in p.lower()                        # het concrete-stap-voorstel


def test_role_capabilities_block_faalt_zacht_zonder_rol():
    # geen rol → lege string, nooit een exceptie (fail-soft)
    assert cockpit2._role_capabilities_block(None) == ""


def test_parse_reply_voorstel_json_en_fallback():
    from types import SimpleNamespace
    role = SimpleNamespace(id="r1", definition=SimpleNamespace(skills=["openalex_evidence"]))
    # geldig JSON-voorstel met een skill die in het DNA zit
    out = ('{"reactie": "Dat raakt mij. Zal ik het checken?", "voorstel": {"doen": true, '
           '"titel": "Onderzoek barefoot-claim", "skill": "openalex_evidence", "payload": {}}}')
    reactie, vst = cockpit2._parse_reply_voorstel(out, role)
    assert "Zal ik" in reactie and vst["titel"] == "Onderzoek barefoot-claim"
    assert vst["skill"] == "openalex_evidence" and vst["role_id"] == "r1"
    # skill buiten het DNA → genegeerd (geen verzonnen tool), voorstel blijft met skill None
    _, vst2 = cockpit2._parse_reply_voorstel(
        '{"reactie": "ok", "voorstel": {"doen": true, "titel": "X", "skill": "niet_bestaand"}}', role)
    assert vst2 and vst2["skill"] is None
    # doen=false → geen voorstel
    _, vst3 = cockpit2._parse_reply_voorstel(
        '{"reactie": "raakt me niet", "voorstel": {"doen": false, "titel": ""}}', role)
    assert vst3 is None
    # platte tekst (geen JSON) → tekst als reactie, geen voorstel (backward compat met oude stubs)
    reactie4, vst4 = cockpit2._parse_reply_voorstel("gewoon een reactie", role)
    assert reactie4 == "gewoon een reactie" and vst4 is None


def test_ai_reply_slaat_voorstel_op_de_entry(tmp_path):
    dd, rid, pid, codie = _setup(tmp_path)
    js = ('{"reactie": "Zal ik dit onderzoeken?", "voorstel": {"doen": true, '
          '"titel": "Onderzoek claim", "skill": null, "payload": {}}}')
    assert cockpit2._ai_reply(cockpit2._Stores(dd), pid, ask=lambda p: js)
    last = cockpit2._Stores(dd).projects.get(pid)["log"][-1]
    assert "Zal ik" in last["text"] and last.get("voorstel", {}).get("titel") == "Onderzoek claim"
    assert last["voorstel"]["role_id"] == rid


def test_mention_to_task_maakt_project_voor_de_rol(tmp_path):
    dd, rid, pid, codie = _setup(tmp_path)
    st = cockpit2._Stores(dd)
    st.projects.add_feed_entry(pid, "Zal ik dit oppakken?", kind="comment", author_type="persona",
                               author_id=codie.id,
                               voorstel={"titel": "Onderzoek barefoot-claim", "skill": None,
                                         "payload": {}, "role_id": rid})
    eid = st.projects.get(pid)["log"][-1]["id"]
    cockpit2.dispatch(dd, "mention_to_task", {"pid": [pid], "item": [eid], "next": ["/"]}, username="guest")
    st2 = cockpit2._Stores(dd)
    # 1) nieuw project owned door de rol, met de voorgestelde titel als scope
    nieuw = [p for p in st2.projects._projects.values()
             if p.get("owner") == rid and p.get("id") != pid and p.get("scope") == "Onderzoek barefoot-claim"]
    assert len(nieuw) == 1
    cls = nieuw[0].get("checklists") or []
    assert cls and cls[0]["items"][0]["text"] == "Onderzoek barefoot-claim"
    # 2) trail op het bron-project + het voorstel is weg (geen dubbele taak bij tweede klik)
    src = st2.projects.get(pid)
    assert any(e.get("kind") == "system" and "taak gemaakt" in e.get("text", "") for e in src["log"])
    pe = next(e for e in src["log"] if e["id"] == eid)
    assert "voorstel" not in pe                                   # de persona-entry heeft geen voorstel meer
    # tweede klik doet niets meer (voorstel weg)
    _, msg = cockpit2.dispatch(dd, "mention_to_task", {"pid": [pid], "item": [eid], "next": ["/"]}, username="guest")
    assert "geen voorstel" in msg


def test_create_task_from_voorstel_maakt_project_met_skill(tmp_path):
    dd, rid, pid, codie = _setup(tmp_path)
    st = cockpit2._Stores(dd)
    vst = {"titel": "Onderzoek claim", "skill": "openalex_evidence", "payload": {}, "role_id": rid}
    new_pid = cockpit2._create_task_from_voorstel(st, st.records.get(rid), vst)
    assert new_pid
    p = cockpit2._Stores(dd).projects.get(new_pid)
    assert p["owner"] == rid and p["scope"] == "Onderzoek claim"
    item = p["checklists"][0]["items"][0]
    assert item["text"] == "Onderzoek claim" and item.get("skill") == "openalex_evidence"


def test_ai_reply_autotask_binnen_scope_maakt_zelf_taak(tmp_path, monkeypatch):
    # experiment aan: een stap die op een EIGEN skill (in het DNA) draait, is binnen scope → de rol maakt
    # 'm zelf aan, geen knop. 'Binnen scope' is hard: de skill zit echt in het DNA.
    monkeypatch.setenv("mention_autotask", "1")
    dd, rid, pid, codie = _setup(tmp_path)
    st = cockpit2._Stores(dd)
    r = st.records.get(rid); r.definition.skills = ["openalex_evidence"]; st.records.put(r)
    js = ('{"reactie": "Dat raakt mij, ik pak het op.", "voorstel": {"doen": true, '
          '"titel": "Onderzoek barefoot-claim", "skill": "openalex_evidence", "payload": {}}}')
    assert cockpit2._ai_reply(cockpit2._Stores(dd), pid, ask=lambda p: js)
    st2 = cockpit2._Stores(dd)
    nieuw = [p for p in st2.projects._projects.values() if p.get("owner") == rid and p.get("id") != pid
             and p.get("scope") == "Onderzoek barefoot-claim"]
    assert len(nieuw) == 1                                        # de rol maakte binnen scope zelf een project
    pcomment = [e for e in st2.projects.get(pid)["log"] if e.get("author", {}).get("type") == "persona"][-1]
    assert "voorstel" not in pcomment                            # zelf gedaan → geen knop meer


def test_ai_reply_autotask_buiten_scope_blijft_knop(tmp_path, monkeypatch):
    # experiment aan, maar de voorgestelde skill zit NIET in het DNA → buiten scope → geen auto, het
    # voorstel blijft staan zodat de mens via de knop beslist.
    monkeypatch.setenv("mention_autotask", "1")
    dd, rid, pid, codie = _setup(tmp_path)
    js = ('{"reactie": "Zal ik dit oppakken?", "voorstel": {"doen": true, '
          '"titel": "Iets buiten scope", "skill": "niet_van_mij", "payload": {}}}')
    assert cockpit2._ai_reply(cockpit2._Stores(dd), pid, ask=lambda p: js)
    st2 = cockpit2._Stores(dd)
    assert not [p for p in st2.projects._projects.values() if p.get("owner") == rid and p.get("id") != pid]
    last = st2.projects.get(pid)["log"][-1]
    assert last.get("voorstel", {}).get("titel") == "Iets buiten scope" and last["voorstel"]["skill"] is None


def test_ai_reply_zonder_experiment_altijd_knop(tmp_path):
    # experiment UIT (default): ook een binnen-scope-voorstel blijft via de knop lopen (veilige default).
    dd, rid, pid, codie = _setup(tmp_path)
    st = cockpit2._Stores(dd)
    r = st.records.get(rid); r.definition.skills = ["openalex_evidence"]; st.records.put(r)
    js = ('{"reactie": "Ik kan dit.", "voorstel": {"doen": true, "titel": "T", '
          '"skill": "openalex_evidence", "payload": {}}}')
    assert cockpit2._ai_reply(cockpit2._Stores(dd), pid, ask=lambda p: js)
    st2 = cockpit2._Stores(dd)
    assert not [p for p in st2.projects._projects.values() if p.get("owner") == rid and p.get("id") != pid]
    assert st2.projects.get(pid)["log"][-1]["voorstel"]["skill"] == "openalex_evidence"   # blijft: knop


def test_mention_op_persona_naam_raakt_de_rol(tmp_path):
    # @Codie (persona-naam) moet exact hetzelfde doel raken als @Website Developer (rolnaam): de rol.
    dd, rid, pid, codie = _setup(tmp_path)
    from nooch_village.views.feed import _mentionables, _mentions_in
    js, by_name = _mentionables(cockpit2._Stores(dd))
    assert {"l": "Codie"} in js                          # persona-naam in de autofill-lijst
    ment = _mentions_in("hoi @Codie kijk even", by_name)
    assert ment and ment[0][0] == "role" and ment[0][1] == rid


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


def test_add_role_message_krijgt_id(tmp_path):
    dd, rid, pid, codie = _setup(tmp_path)
    st = cockpit2._Stores(dd)
    nid = st.projects.add_role_message(pid, "deliverable klaar")
    assert nid and len(nid) == 10                                    # id-patroon van add_feed_entry
    entry = cockpit2._Stores(dd).projects.get(pid)["log"][-1]
    assert entry["id"] == nid and entry["who"] == "rol" and entry["text"] == "deliverable klaar"
    assert cockpit2._Stores(dd).projects.get(pid)["progress"] == "deliverable klaar"   # bestaand gedrag
    assert st.projects.add_role_message(pid, "   ") is None          # lege tekst → None (was False, blijft falsy)


def test_oude_role_note_zonder_id_blijft_geldig(tmp_path):
    dd, rid, pid, codie = _setup(tmp_path)
    st = cockpit2._Stores(dd)
    p = st.projects.get(pid)
    p.setdefault("log", []).append({"who": "rol", "text": "oude deliverable", "at": 1.0})  # geen id (pre-fix)
    st.projects._save()
    frag = cockpit2.render_project(cockpit2._Stores(dd), pid, csrf_token="t", fragment=True)
    assert "oude deliverable" in frag                                # geen migratie nodig; rendert prima


def test_human_reactie_zet_worked_false(tmp_path):
    dd, rid, pid, codie = _setup(tmp_path)
    st = cockpit2._Stores(dd)
    st.projects.add_feed_entry(pid, "klaar", kind="update", author_type="persona", author_id=codie.id)
    st.projects.add_feed_entry(pid, "graag aanpassen", kind="comment", author_type="human")
    assert cockpit2._Stores(dd).projects.get(pid).get("worked") is False
