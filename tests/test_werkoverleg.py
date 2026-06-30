"""Werkoverleg brok 1: store + modalframe (secretaris-gated) + hergebruik bestaande schermen."""
from __future__ import annotations

from nooch_village import cockpit2

C = "mother_earth__nooch"
RID = "mother_earth__nooch__website_developer"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def test_store_open_close(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    assert not st.werk.is_open(C)
    st.werk.open(C)
    assert cockpit2._Stores(dd).werk.is_open(C)
    cockpit2._Stores(dd).werk.close(C)
    assert not cockpit2._Stores(dd).werk.is_open(C)


def test_startscherm_secretaris_gate(tmp_path):
    dd = _dd(tmp_path)
    frag = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, csrf_token="t", fragment=True)
    assert "Werkoverleg" in frag and "Alleen de secretaris" in frag and "wo_open" in frag
    assert "wo-step" not in frag                      # nog niet gestart -> geen stappen


def test_knop_op_cirkel_en_niet_op_rol(tmp_path):
    dd = _dd(tmp_path)
    node = cockpit2.render_node(cockpit2._Stores(dd), C, "overview", csrf_token="t")
    assert "/werkoverleg?circle=" in node and "Tactical meeting" in node
    role = cockpit2.render_node(cockpit2._Stores(dd), RID, "overview", csrf_token="t")
    assert "Tactical meeting" not in role and "/werkoverleg?circle=" not in role


def test_open_toont_stappen_en_checkin_members(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]})
    frag = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "checkin", csrf_token="t", fragment=True)
    # vaste volgorde van 7 stappen
    for lbl in ("Check-in", "Checklist", "Metrics", "Projecten", "Agenda", "Check-out", "Sluiten"):
        assert lbl in frag
    assert "wo-step on" in frag and "Sluit overleg" in frag
    assert "Check-in" in frag                          # stap 1 = check-in (members-basis)


def test_stappen_hergebruiken_bestaande_schermen(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]})
    st = cockpit2._Stores(dd)
    cl = cockpit2.render_werkoverleg(st, C, "checklist", csrf_token="t", fragment=True)
    assert "Checklists" in cl and "+ Checklist-item" in cl          # echte checklist-scherm
    me = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "metrics", csrf_token="t", fragment=True)
    assert "+ KPI maken" in me and "Periode:" in me                 # echte metrics-scherm
    pr = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "projecten", csrf_token="t", fragment=True)
    assert "proj" in pr.lower()                                     # echte projecten-scherm


def _with_member(dd):
    st = cockpit2._Stores(dd)
    person = st.people.all()[0]
    st.assign.assign(RID, "person", person.id)
    return person


def test_checkin_presence(tmp_path):
    dd = _dd(tmp_path)
    p = _with_member(dd)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]})
    frag = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "checkin", csrf_token="t", fragment=True)
    assert "wo-mems" in frag and "wo_presence" in frag and p.name in frag
    # afwezig zetten -> verlof
    cockpit2.dispatch(dd, "wo_presence", {"circle": [C], "pid": [p.id], "present": ["0"], "next": ["/"]})
    assert cockpit2._Stores(dd).werk.is_present(C, p.id) is False
    frag2 = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "checkin", csrf_token="t", fragment=True)
    assert "op verlof" in frag2


def test_checklist_numerieke_waarde(tmp_path):
    dd = _dd(tmp_path)
    _with_member(dd)
    cockpit2.dispatch(dd, "cl_add", {"node": [C], "description": ["Facturen"], "cadence": ["week"],
                                     "doel": ["all"], "bestaand": ["1"], "next": ["/"]})
    cid = cockpit2._Stores(dd).checklists.for_node(C)[0]["id"]
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]})
    frag = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "checklist", csrf_token="t", fragment=True)
    assert "cl-check" in frag and "Rapporteren" in frag        # U5: V/X-knoppen + wie rapporteert
    assert "cl-num" not in frag                                # numeriek invoerveld vervallen
    # opslag-compat: een meegestuurde waarde wordt nog bewaard, ook al biedt de UI het veld niet meer
    cockpit2.dispatch(dd, "cl_report", {"cid": [cid], "ok": ["1"], "value": ["12"], "next": ["/"]})
    from nooch_village.checklists import ChecklistStore
    assert ChecklistStore.current_value(cockpit2._Stores(dd).checklists.get(cid)) == 12.0


def test_agenda_en_triage_project(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]})
    cockpit2.dispatch(dd, "wo_ag_add", {"circle": [C], "naam": ["Checkout hapert -SW"], "next": ["/"]})
    it = cockpit2._Stores(dd).werk.agenda(C)[0]
    assert it["title"] == "Checkout hapert" and it["by"] == "SW"
    # triage -> project toevoegen voor een rol
    cockpit2.dispatch(dd, "wo_ag_resolve", {"circle": [C], "iid": [it["id"]], "otype": ["project"],
                                            "owner": [RID], "detail": ["Checkout flow fixen"], "next": ["/"]})
    assert cockpit2._Stores(dd).werk.agenda_get(C, it["id"])["status"] == "done"
    projs = [p for p in cockpit2._Stores(dd).projects.all() if p.get("owner") == RID]
    assert any("Checkout flow fixen" in str(p.get("scope")) for p in projs)


def test_triage_actie_los_en_aan_project(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]})
    # losse actie
    cockpit2.dispatch(dd, "wo_ag_add", {"circle": [C], "naam": ["Meeting plannen met Lotte"], "next": ["/"]})
    iid = cockpit2._Stores(dd).werk.agenda(C)[0]["id"]
    cockpit2.dispatch(dd, "wo_ag_resolve", {"circle": [C], "iid": [iid], "otype": ["action"],
                                            "detail": ["Lotte bellen"], "pid_link": [""], "next": ["/"]})
    it = cockpit2._Stores(dd).werk.agenda_get(C, iid)
    assert it["status"] == "done" and it["outcome"]["type"] == "action"
    # actie gekoppeld aan een project -> checklist-item op dat project
    pid = cockpit2._Stores(dd).projects.create(RID, "Website", "human")
    cockpit2.dispatch(dd, "wo_ag_add", {"circle": [C], "naam": ["Login doorsturen"], "next": ["/"]})
    iid2 = [i["id"] for i in cockpit2._Stores(dd).werk.agenda(C) if i["status"] != "done"][0]
    cockpit2.dispatch(dd, "wo_ag_resolve", {"circle": [C], "iid": [iid2], "otype": ["action"],
                                            "detail": ["Cosh login sturen"], "pid_link": [pid], "next": ["/"]})
    p = cockpit2._Stores(dd).projects.get(pid)
    items = [t for cl in p.get("checklists", []) for t in cl.get("items", [])]
    assert any("Cosh login" in t.get("text", "") for t in items)


def test_triage_geen_need_veld_en_info_richting(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]})
    cockpit2.dispatch(dd, "wo_ag_add", {"circle": [C], "naam": ["Iets"], "next": ["/"]})
    iid = cockpit2._Stores(dd).werk.agenda(C)[0]["id"]
    frag = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "agenda", csrf_token="t", fragment=True, iid=iid)
    assert "Wat heb je nodig" not in frag                     # need-veld is weg
    assert "wo-spanning" in frag and "Spanning" in frag       # spanning als eigen blok
    # info met richting (delen/nodig); detail krijgt richting + doelgroep
    cockpit2.dispatch(dd, "wo_ag_resolve", {"circle": [C], "iid": [iid], "otype": ["info"],
                                            "dir": ["delen"], "detail": ["losdoc"], "next": ["/"]})
    oc = cockpit2._Stores(dd).werk.agenda_get(C, iid)["outcome"]
    assert oc["type"] == "info" and oc["detail"].startswith("delen (iedereen):")


def test_transparantie_policy_op_breedste_cirkel(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    root = cockpit2.org.roots(st.records.all())[0]
    assert cockpit2._TRANSP_POLICY in root.definition.policies
    assert any(i["description"] == cockpit2._TRANSP_CHECK for i in st.checklists.for_node(root.id))


def test_triage_roloverleg_punt(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]})
    cockpit2.dispatch(dd, "wo_ag_add", {"circle": [C], "naam": ["Nieuwe rol nodig"], "next": ["/"]})
    iid = cockpit2._Stores(dd).werk.agenda(C)[0]["id"]
    cockpit2.dispatch(dd, "wo_ag_resolve", {"circle": [C], "iid": [iid], "otype": ["roloverleg"],
                                            "detail": ["kans: groei; nodig: een SEO-rol"], "next": ["/"]})
    # belandt op de roloverleg-agenda
    assert cockpit2._Stores(dd).agenda.open()
    assert cockpit2._Stores(dd).werk.agenda_get(C, iid)["outcome"]["type"] == "roloverleg"


def test_checkout_en_samenvatting(tmp_path):
    dd = _dd(tmp_path)
    p = _with_member(dd)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]})
    cockpit2.dispatch(dd, "wo_checkout", {"circle": [C], "pid": [p.id], "score": ["8"], "next": ["/"]})
    assert cockpit2._Stores(dd).werk.checkout(C)[p.id] == 8
    frag = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "sluiten", csrf_token="t", fragment=True)
    assert "Samenvatting" in frag and "Gemiddelde tevredenheid" in frag and "8" in frag


def test_checkout_toont_vorige_score(tmp_path):
    dd = _dd(tmp_path)
    p = _with_member(dd)
    # overleg 1: score 7, sluiten -> wordt 'vorige keer'
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]})
    cockpit2.dispatch(dd, "wo_checkout", {"circle": [C], "pid": [p.id], "score": ["7"], "next": ["/"]})
    cockpit2.dispatch(dd, "wo_close", {"circle": [C], "next": ["/"]})
    assert cockpit2._Stores(dd).werk.prev_checkout(C).get(p.id) == 7
    # overleg 2: nog niet gescoord -> de 7 verschijnt als ghost (class prev)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]})
    frag = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "checkout", csrf_token="t", fragment=True)
    assert "wo-sc prev" in frag and "vorige keer" in frag


def test_noochie_hulp_context_opener(tmp_path):
    dd = _dd(tmp_path)
    # render_noochie met schermcontext (de spanning) opent met 'Heb je hulp nodig bij ...'
    frag = cockpit2.render_noochie(cockpit2._Stores(dd), csrf="t", screen_ctx="Checkout hapert")
    assert "Heb je hulp nodig bij Checkout hapert?" in frag


def test_projecten_stap_geen_losse_add(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]})
    frag = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "projecten", csrf_token="t", fragment=True)
    # in het overleg geen losse project-add (loopt via de triage)
    assert "qadd-top" not in frag and "+ project toevoegen" not in frag
    # op de gewone tab blijft toevoegen wel bestaan
    tab = cockpit2.render_node(cockpit2._Stores(dd), C, "projects", csrf_token="t")
    assert "qadd-top" in tab


def test_sluiten(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]})
    cockpit2.dispatch(dd, "wo_close", {"circle": [C], "next": ["/"]})
    assert not cockpit2._Stores(dd).werk.is_open(C)
