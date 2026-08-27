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
    assert "Tactical meeting" in frag and "Only the secretary" in frag and "wo_open" in frag
    assert "wo-step" not in frag                      # nog niet gestart -> geen stappen


def test_knop_op_cirkel_en_niet_op_rol(tmp_path):
    dd = _dd(tmp_path)
    node = cockpit2.render_node(cockpit2._Stores(dd), C, "overview", csrf_token="t")
    assert "/werkoverleg?circle=" in node and "Tactical meeting" in node
    role = cockpit2.render_node(cockpit2._Stores(dd), RID, "overview", csrf_token="t")
    assert "Tactical meeting" not in role and "/werkoverleg?circle=" not in role


def test_open_toont_stappen_en_checkin_members(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    frag = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "checkin", csrf_token="t", fragment=True)
    # vaste volgorde van 7 stappen
    for lbl in ("Check-in", "Checklist", "Metrics", "Projects", "Agenda", "Check-out", "Close"):
        assert lbl in frag
    assert "wo-step on" in frag and "Next" in frag            # per-stap actie, geen onderbalk
    assert "Sluit overleg" not in frag and "rov-foot" not in frag  # afronden alleen op stap 7
    assert "wo-grid" in frag and "id='wo-video'" not in frag      # 2 kolommen; video verhuisde naar de call bar
    assert "Check-in" in frag                          # stap 1 = check-in (members-basis)


def test_stappen_hergebruiken_bestaande_schermen(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    st = cockpit2._Stores(dd)
    cl = cockpit2.render_werkoverleg(st, C, "checklist", csrf_token="t", fragment=True)
    assert "Checklists" in cl and "+ Checklist item" in cl          # echte checklist-scherm
    me = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "metrics", csrf_token="t", fragment=True)
    assert "+ Create KPI" in me and "Period:" in me                 # echte metrics-scherm
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
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    frag = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "checkin", csrf_token="t", fragment=True)
    assert "wo-mems" in frag and "wo_presence" in frag and p.name in frag
    # afwezig zetten -> verlof
    cockpit2.dispatch(dd, "wo_presence", {"circle": [C], "pid": [p.id], "present": ["0"], "next": ["/"]}, username="guest")
    assert cockpit2._Stores(dd).werk.is_present(C, p.id) is False
    frag2 = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "checkin", csrf_token="t", fragment=True)
    assert "on leave" in frag2


def test_checklist_numerieke_waarde(tmp_path):
    dd = _dd(tmp_path)
    _with_member(dd)
    cockpit2.dispatch(dd, "cl_add", {"node": [C], "description": ["Facturen"], "cadence": ["week"],
                                     "doel": ["all"], "bestaand": ["1"], "next": ["/"]}, username="guest")
    cid = cockpit2._Stores(dd).checklists.for_node(C)[0]["id"]
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    frag = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "checklist", csrf_token="t", fragment=True)
    assert "cl-check" in frag and "Reporting" in frag        # U5: V/X-knoppen + wie rapporteert
    assert "cl-num" not in frag                                # numeriek invoerveld vervallen
    # opslag-compat: een meegestuurde waarde wordt nog bewaard, ook al biedt de UI het veld niet meer
    cockpit2.dispatch(dd, "cl_report", {"cid": [cid], "ok": ["1"], "value": ["12"], "next": ["/"]}, username="guest")
    from nooch_village.checklists import ChecklistStore
    assert ChecklistStore.current_value(cockpit2._Stores(dd).checklists.get(cid)) == 12.0


def _punt(dd, label: str) -> str:
    """Vang één punt via de GEDEELDE vangkant en geef zijn id."""
    cockpit2.dispatch(dd, "vangst_add", {"circle": [C], "punt": [label], "next": ["/"]},
                      username="guest")
    return [p for p in cockpit2._Stores(dd).werk.punten(C) if p["title"] == label][0]["id"]


def _uitkomst(dd, iid: str, **velden):
    vorm = {"circle": [C], "iid": [iid], "next": ["/"]}
    vorm.update({k: [v] for k, v in velden.items()})
    return cockpit2.dispatch(dd, "vangst_uitkomst", vorm, username="guest")


def _rolnaam(dd, rid: str) -> str:
    return cockpit2._name(cockpit2._Stores(dd).records.get(rid))


def test_agenda_stap_deelt_de_vang_en_verwerk_van_vangst(tmp_path):
    """De agenda-stap rendert DEZELFDE component als /vangst — geen tweede triage-scherm."""
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    iid = _punt(dd, "Checkout hapert")
    frag = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "agenda", csrf_token="t",
                                       fragment=True, iid=iid)
    assert "Punten behandelen" in frag
    assert "vang-form" in frag and "vang-lijst" in frag       # de gedeelde vangkant
    assert "Uitkomsten van het overleg" in frag              # de gedeelde verwerkkant
    assert "Checkout hapert" in frag
    # De oude triage is weg: geen 'Process tension'-paneel en geen wo_ag_*-actie meer.
    assert "wo_ag_" not in frag


def test_drie_uitkomsten_onder_een_spanning_naar_verschillende_rollen(tmp_path):
    """Waar het oude scherm faalde: het dwong één uitkomst per spanning af."""
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    iid = _punt(dd, "De FSC-verklaring verloopt in november")
    rol = _rolnaam(dd, RID)
    for otype, tekst in (("actie", "Leverancier bellen"),
                         ("project", "Certificering vernieuwen"),
                         ("governance", "Wie bewaakt certificaten?")):
        _nxt, msg = _uitkomst(dd, iid, otype=otype, rol=rol, tekst=tekst)
        assert msg.startswith("✓"), (otype, msg)
    punt = cockpit2._Stores(dd).werk.punt_get(C, iid)
    assert [u["type"] for u in punt["uitkomsten"]] == ["actie", "project", "governance"]
    # en ze doen elk hun echte werk
    projs = cockpit2._Stores(dd).projects.all()
    assert any("Certificering vernieuwen" in str(p.get("scope")) for p in projs)
    assert cockpit2._Stores(dd).agenda.open()                 # roloverleg-punt staat er


def test_een_uitkomst_draagt_rol_persoon_en_kroniek_herkomst(tmp_path):
    dd = _dd(tmp_path)
    p = _with_member(dd)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    iid = _punt(dd, "Iets")
    _uitkomst(dd, iid, otype="actie", rol=_rolnaam(dd, RID), tekst="Lotte bellen", persoon=p.id)
    u = cockpit2._Stores(dd).werk.punt_get(C, iid)["uitkomsten"][0]
    assert u["rol"] == RID and u["persoon"] == p.id
    assert "staat" not in u                       # de staat-keuze is uit de flow
    # HERKOMST: een echt Kroniek-record, geen rolnaam
    assert u["kroniek"]
    kr = [r for r in cockpit2._Stores(dd).evidence.all_records() if r["id"] == u["kroniek"]]
    assert kr and kr[0]["skill"] == "werkoverleg" and kr[0]["status"] == "bevestigd"


def test_een_uitkomst_is_bewerkbaar_en_verwijderbaar(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    iid = _punt(dd, "Iets")
    _uitkomst(dd, iid, otype="info", rol=_rolnaam(dd, RID), tekst="eerste tekst")
    uid = cockpit2._Stores(dd).werk.punt_get(C, iid)["uitkomsten"][0]["id"]
    cockpit2.dispatch(dd, "vangst_uitkomst_edit",
                      {"circle": [C], "iid": [iid], "uid": [uid], "tekst": ["bijgesteld"],
                       "persoon": [""], "next": ["/"]}, username="guest")
    u = cockpit2._Stores(dd).werk.punt_get(C, iid)["uitkomsten"][0]
    assert u["tekst"] == "bijgesteld"
    cockpit2.dispatch(dd, "vangst_uitkomst_weg",
                      {"circle": [C], "iid": [iid], "uid": [uid], "next": ["/"]}, username="guest")
    assert cockpit2._Stores(dd).werk.punt_get(C, iid)["uitkomsten"] == []


def test_een_actie_zonder_lopend_project_wordt_geen_zwart_gat(tmp_path):
    """Een actie hangt aan een lopend project van die rol. Heeft de rol er geen, dan wordt het een
    project — anders verdwijnt de actie in het niets."""
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    iid = _punt(dd, "Login doorsturen")
    _nxt, msg = _uitkomst(dd, iid, otype="actie", rol=_rolnaam(dd, RID), tekst="Cosh login sturen")
    assert msg.startswith("✓")
    st = cockpit2._Stores(dd)
    items = [t for p in st.projects.all() for cl in p.get("checklists", []) for t in cl.get("items", [])]
    scopes = [str(p.get("scope")) for p in st.projects.all()]
    assert any("Cosh login" in t.get("text", "") for t in items) or \
           any("Cosh login" in sc for sc in scopes)


def test_transparantie_checklist_op_breedste_cirkel(tmp_path):
    # Fase 2: de transparantie-POLICY is uit definition.policies gehaald (was eerder een note);
    # de operationele cadans blijft als checklist-item op de breedste cirkel.
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    root = cockpit2.org.roots(st.records.all())[0]
    assert cockpit2._TRANSP_POLICY not in root.definition.policies      # geen string-policy meer
    assert any(i["description"] == cockpit2._TRANSP_CHECK for i in st.checklists.for_node(root.id))


def test_een_governance_punt_belandt_op_de_roloverleg_agenda(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    iid = _punt(dd, "Nieuwe rol nodig")
    _uitkomst(dd, iid, otype="governance", rol=_rolnaam(dd, RID),
              tekst="kans: groei; nodig: een SEO-rol")
    assert cockpit2._Stores(dd).agenda.open()
    u = cockpit2._Stores(dd).werk.punt_get(C, iid)["uitkomsten"][0]
    assert u["type"] == "governance"


def test_checkout_en_samenvatting(tmp_path):
    dd = _dd(tmp_path)
    p = _with_member(dd)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    cockpit2.dispatch(dd, "wo_checkout", {"circle": [C], "pid": [p.id], "ok": ["1"], "next": ["/"]},
                      username="guest")
    assert cockpit2._Stores(dd).werk.checkout(C)[p.id] is True
    frag = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "sluiten", csrf_token="t", fragment=True)
    assert "Summary" in frag and "Check-out" in frag and "1 yes · 0 no" in frag
    assert "Average satisfaction" not in frag                 # de schaal is weg
    assert "Close meeting" in frag and "Next" not in frag     # stap 7 = centrale sluit-actie


def test_de_checkout_is_ja_nee_zoals_de_check_in(tmp_path):
    """Geen schaal en geen gemiddelde meer: dezelfde twee knoppen als bij de check-in."""
    dd = _dd(tmp_path)
    _with_member(dd)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    frag = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "checkout", csrf_token="t",
                                       fragment=True)
    assert "cl-check ok" in frag and "cl-check no" in frag    # zelfde knoppen als de check-in
    assert "wo-scale" not in frag and "wo-avg" not in frag    # schaal én gemiddelde weg
    assert "Did this meeting give you what you needed?" in frag
    assert "name='ok'" in frag and "name='score'" not in frag


def test_een_oud_cijfer_wordt_niet_vertaald_naar_ja(tmp_path):
    """Een 7 uit een archief is geen 'ja'. Er is geen grens die dat eerlijk vertaalt, dus toont
    het scherm hem niet als ghost — en de oude waarde blijft staan zoals hij is opgeschreven."""
    dd = _dd(tmp_path)
    p = _with_member(dd)
    st = cockpit2._Stores(dd)
    st.werk.open(C)
    st.werk._m[C].setdefault("checkout", {})[p.id] = 7        # record van vóór de wijziging
    st.werk._save()
    cockpit2.dispatch(dd, "wo_close", {"circle": [C], "next": ["/"]}, username="guest")
    assert cockpit2._Stores(dd).werk.prev_checkout(C).get(p.id) == 7   # ongewijzigd bewaard
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    frag = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "checkout", csrf_token="t",
                                       fragment=True)
    assert "last time" not in frag                            # geen ghost, ook geen legenda


def test_checkout_toont_het_vorige_antwoord(tmp_path):
    dd = _dd(tmp_path)
    p = _with_member(dd)
    # overleg 1: ja, sluiten -> wordt 'vorige keer'
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    cockpit2.dispatch(dd, "wo_checkout", {"circle": [C], "pid": [p.id], "ok": ["1"], "next": ["/"]},
                      username="guest")
    cockpit2.dispatch(dd, "wo_close", {"circle": [C], "next": ["/"]}, username="guest")
    assert cockpit2._Stores(dd).werk.prev_checkout(C).get(p.id) is True
    # overleg 2: nog niets ingevuld -> het ja verschijnt als ghost (class prev)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    frag = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "checkout", csrf_token="t", fragment=True)
    assert "cl-check ok prev" in frag and "last time" in frag


def test_noochie_hulp_context_opener(tmp_path):
    dd = _dd(tmp_path)
    # render_noochie met schermcontext (de spanning) opent met 'Heb je hulp nodig bij ...'
    frag = cockpit2.render_noochie(cockpit2._Stores(dd), csrf="t", screen_ctx="Checkout hapert")
    assert "Do you need help with Checkout hapert?" in frag


def test_projecten_stap_geen_losse_add(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    frag = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "projecten", csrf_token="t", fragment=True)
    # in het overleg geen enkel project-add-pad (werk komt via de triage binnen)
    assert "qadd-top" not in frag and "add project" not in frag and "/project/nieuw" not in frag
    # op de gewone tab blijft toevoegen wel bestaan — sinds 21 jul via de wizard-modal
    # (de inline qadd-uitklap is dáár door vervangen), zie views/projects.py
    tab = cockpit2.render_node(cockpit2._Stores(dd), C, "projects", csrf_token="t")
    assert "/project/nieuw" in tab and "add project" in tab


def test_sluiten(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    cockpit2.dispatch(dd, "wo_close", {"circle": [C], "next": ["/"]}, username="guest")
    assert not cockpit2._Stores(dd).werk.is_open(C)


def test_de_agenda_stap_gooit_je_niet_het_overleg_uit(tmp_path):
    """De gedeelde component werkte, maar nam je mee naar zijn eigen huis: na elke uitkomst stond
    je op /vangst in plaats van in het overleg."""
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    iid = _punt(dd, "Iets")
    frag = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "agenda", csrf_token="t",
                                       fragment=True, iid=iid)
    assert "/werkoverleg?circle=" in frag
    assert "value='/vangst?circle=" not in frag        # geen terug-URL naar het vangscherm


def test_een_punt_toevoegen_kan_op_elke_stap(tmp_path):
    """Wie tijdens de check-in iets hoort moet het daar kunnen opschrijven. Stond het veld alleen
    op stap 5, dan was de handeling in de praktijk 'onthouden tot stap 5'."""
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    for stap in ("checkin", "checklist", "metrics", "projecten", "agenda", "checkout", "sluiten"):
        frag = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, stap, csrf_token="t",
                                           fragment=True)
        assert "vang-form" in frag, stap
        assert "Punten behandelen" in frag, stap
        # en hij komt terug op de stap waar je stond, niet op de agenda-stap
        assert f"value='/werkoverleg?circle={C}&amp;step={stap}'" in frag, stap


def test_de_puntenlijst_blijft_onder_de_agenda_stap(tmp_path):
    """Vangen is overal; behandelen is stap 5. Anders staat dezelfde lijst zeven keer op het
    scherm en is 'de agenda-stap' geen stap meer."""
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    _punt(dd, "Checkout hapert")
    ag = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "agenda", csrf_token="t",
                                     fragment=True)
    ci = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "checkin", csrf_token="t",
                                     fragment=True)
    doos = "<div class='rdr-tool' id='vang-lijst'>"      # de lijst zelf, niet de scriptregel
    assert doos in ag and "Checkout hapert" in ag
    assert doos not in ci and "Checkout hapert" not in ci


def test_de_teller_is_de_terugkoppeling_buiten_de_agenda_stap(tmp_path):
    """Op de andere zes stappen zie je de lijst niet. Dan moet het getal laten zien dat je punt
    geland is — anders typ je in het duister."""
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    leeg = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "checkin", csrf_token="t",
                                       fragment=True)
    assert "<span id='vang-tot'>0 onderwerpen</span>, <span id='vang-n'>0</span> te doen" in leeg
    _punt(dd, "Eén punt")
    een = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "checkin", csrf_token="t",
                                      fragment=True)
    assert "<span id='vang-tot'>1 onderwerp</span>, <span id='vang-n'>1</span> te doen" in een


def test_de_vangwachtrij_reist_mee_naar_elke_stap(tmp_path):
    """Zonder de wachtrij vervangt het scherm zich na elk punt en verdwijnt het punt dat je al aan
    het typen was. De balk vraagt de GEDEELDE mechaniek aan met attributen; er reist geen kopie
    van het script mee."""
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    for stap in ("checkin", "agenda"):
        frag = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, stap, csrf_token="t",
                                           fragment=True)
        assert "data-qa-frag=" in frag and "data-qa-input" in frag, stap
        assert "<script" not in frag, stap           # geen kopie van de mechaniek per scherm
