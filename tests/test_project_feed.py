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


def test_ai_reply_prompt_bevat_accountabilities_en_triage_instructie(tmp_path):
    # de @mention-reply moet de rol laten TRIAGEREN tegen haar accountabilities/skills: past het, kan ik
    # het direct beantwoorden, of verwerk ik het via mijn inbox — die context + instructie horen erin.
    dd, rid, pid, codie = _setup(tmp_path)
    gezien = {}
    cockpit2._ai_reply(cockpit2._Stores(dd), pid,
                       ask=lambda prompt: gezien.setdefault("p", prompt) or "ok")
    p = gezien["p"]
    assert "Jouw accountabilities:" in p and "Jouw skills" in p
    assert "Triageer dit signaal" in p                  # de triage-instructie
    assert "Past het bij jouw rol" in p and "kan_direct" in p   # fit + direct-antwoord-toets


def test_role_capabilities_block_faalt_zacht_zonder_rol():
    # geen rol → lege string, nooit een exceptie (fail-soft)
    assert cockpit2._role_capabilities_block(None) == ""


def test_parse_triage():
    ok = ('{"fit": "ja", "welk_stuk": "", "kan_direct": true, '
          '"reactie": "Barefoot-schoenen verlagen de hakhoogte."}')
    t = cockpit2._parse_triage(ok)
    assert t["fit"] == "ja" and t["kan_direct"] is True and "Barefoot" in t["reactie"]
    # ongeldige fit → None (val terug op platte tekst)
    assert cockpit2._parse_triage('{"fit": "misschien", "reactie": "x"}') is None
    # lege reactie → None
    assert cockpit2._parse_triage('{"fit": "ja", "reactie": ""}') is None
    # geen JSON → None
    assert cockpit2._parse_triage("gewoon tekst") is None


def test_triage_fit_nee_wijst_kort_af_en_verwerkt_item(tmp_path):
    # past niet bij de rol → korte afwijzing op de wall; geen project; het inbox-item is verwerkt met reden.
    dd, rid, pid, codie = _setup(tmp_path)
    js = ('{"fit": "nee", "welk_stuk": "de juridische check", "kan_direct": false, '
          '"reactie": "Dit is niet mijn rol; de juridische check kan ik wel."}')
    assert cockpit2._ai_reply(cockpit2._Stores(dd), pid, ask=lambda p: js)
    st2 = cockpit2._Stores(dd)
    last = st2.projects.get(pid)["log"][-1]
    assert last["author"]["type"] == "persona" and "niet mijn rol" in last["text"]
    assert not [p for p in st2.projects._projects.values() if p.get("owner") == rid and p.get("id") != pid]
    n = [x for x in st2.notif.for_targets([("role", rid)]) if x.get("project_id") == pid]
    assert n and st2.notif.status_of(n[0]) == "verwerkt" and "past niet" in (n[0].get("outcome") or "")


def test_triage_direct_antwoord_op_de_wall(tmp_path):
    # kan direct uit kennis beantwoorden (geen skill) → antwoord staat op de wall, item verwerkt met reden.
    dd, rid, pid, codie = _setup(tmp_path)
    js = ('{"fit": "ja", "welk_stuk": "", "kan_direct": true, '
          '"reactie": "Kort antwoord: gebruik term X, die is stabiel."}')
    assert cockpit2._ai_reply(cockpit2._Stores(dd), pid, ask=lambda p: js)
    st2 = cockpit2._Stores(dd)
    last = st2.projects.get(pid)["log"][-1]
    assert "Kort antwoord" in last["text"]
    assert not [p for p in st2.projects._projects.values() if p.get("owner") == rid and p.get("id") != pid]
    n = [x for x in st2.notif.for_targets([("role", rid)]) if x.get("project_id") == pid]
    assert n and st2.notif.status_of(n[0]) == "verwerkt" and "direct beantwoord" in (n[0].get("outcome") or "")


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


def test_triage_binnen_scope_verwerkt_zelf_via_inbox(tmp_path, monkeypatch):
    # experiment aan + een skill die ECHT in het DNA zit (machine-check via _dna_skill_for) → de rol maakt
    # er zelf een project van EN markeert het inbox-item verwerkt met de uitkomst (historie). Eén flow.
    monkeypatch.setenv("mention_autotask", "1")
    monkeypatch.setattr(cockpit2, "_dna_skill_for",
                        lambda st, role, ask: {"skill": "openalex_evidence", "payload": {}, "payload_ok": True})
    dd, rid, pid, codie = _setup(tmp_path)
    st = cockpit2._Stores(dd)
    r = st.records.get(rid); r.definition.skills = ["openalex_evidence"]; st.records.put(r)
    js = ('{"fit": "ja", "welk_stuk": "", "kan_direct": false, '
          '"reactie": "Ik verwerk dit via mijn inbox."}')
    assert cockpit2._ai_reply(cockpit2._Stores(dd), pid, ask=lambda p: js)
    st2 = cockpit2._Stores(dd)
    nieuw = [p for p in st2.projects._projects.values() if p.get("owner") == rid and p.get("id") != pid]
    assert len(nieuw) == 1                                        # binnen scope → zelf een project gemaakt
    assert nieuw[0]["checklists"][0]["items"][0].get("skill") == "openalex_evidence"
    n = [x for x in st2.notif.for_targets([("role", rid)]) if x.get("project_id") == pid]
    assert n and st2.notif.status_of(n[0]) == "verwerkt" and "als project" in (n[0].get("outcome") or "")


def test_triage_buiten_scope_blijft_nieuw_in_inbox(tmp_path, monkeypatch):
    # experiment aan, maar geen eigen skill matcht (buiten scope) → geen auto-project; het inbox-item blijft
    # 'nieuw' voor de mens om via de vijf-uitkomsten te verwerken.
    monkeypatch.setenv("mention_autotask", "1")
    monkeypatch.setattr(cockpit2, "_dna_skill_for", lambda st, role, ask: None)
    dd, rid, pid, codie = _setup(tmp_path)
    js = ('{"fit": "deels", "welk_stuk": "de meting", "kan_direct": false, '
          '"reactie": "Ik verwerk dit via mijn inbox."}')
    assert cockpit2._ai_reply(cockpit2._Stores(dd), pid, ask=lambda p: js)
    st2 = cockpit2._Stores(dd)
    assert not [p for p in st2.projects._projects.values() if p.get("owner") == rid and p.get("id") != pid]
    n = [x for x in st2.notif.for_targets([("role", rid)]) if x.get("project_id") == pid]
    assert n and st2.notif.status_of(n[0]) == "nieuw"            # wacht op de mens


def test_triage_zonder_experiment_blijft_nieuw(tmp_path, monkeypatch):
    # experiment UIT (default): ook binnen scope maakt de rol niet automatisch een project; het item blijft
    # 'nieuw' in de inbox (veilige default, alles via de mens).
    monkeypatch.setattr(cockpit2, "_dna_skill_for",
                        lambda st, role, ask: {"skill": "openalex_evidence", "payload": {}, "payload_ok": True})
    dd, rid, pid, codie = _setup(tmp_path)
    js = ('{"fit": "ja", "welk_stuk": "", "kan_direct": false, "reactie": "Ik verwerk dit via mijn inbox."}')
    assert cockpit2._ai_reply(cockpit2._Stores(dd), pid, ask=lambda p: js)
    st2 = cockpit2._Stores(dd)
    assert not [p for p in st2.projects._projects.values() if p.get("owner") == rid and p.get("id") != pid]
    n = [x for x in st2.notif.for_targets([("role", rid)]) if x.get("project_id") == pid]
    assert n and st2.notif.status_of(n[0]) == "nieuw"


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
