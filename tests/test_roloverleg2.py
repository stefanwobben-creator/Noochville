"""Roloverleg in cockpit 2 — brok 1: modal-frame + agenda links."""
from __future__ import annotations

from nooch_village import cockpit2

C = "mother_earth__nooch"
RID = "mother_earth__nooch__website_developer"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def test_meeting_knop_op_cirkel(tmp_path):
    dd = _dd(tmp_path)
    node = cockpit2.render_node(cockpit2._Stores(dd), C, "overview", csrf_token="t")
    assert f"/roloverleg2?circle={C}" in node and "Governance meeting" in node
    # een rol heeft geen meeting-knop
    role = cockpit2.render_node(cockpit2._Stores(dd), RID, "overview", csrf_token="t")
    assert "roloverleg2" not in role


def test_agendapunt_bestaande_rol_en_nieuwe_rol(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "naam": ["Website Developer"], "next": ["/"]})
    cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "naam": ["Data Analist"], "next": ["/"]})
    items = cockpit2._Stores(dd).agenda.open()
    kinds = {it["kind"] for it in items}
    assert kinds == {"amend_role", "add_role"} and len(items) == 2
    frag = cockpit2.render_roloverleg2(cockpit2._Stores(dd), C, csrf_token="t", fragment=True)
    assert "Website Developer" in frag and "Data Analist" in frag and "Agenda" in frag


def test_editor_prefil_en_change_diff(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "naam": ["Website Developer"], "next": ["/"]})
    iid = cockpit2._Stores(dd).agenda.open()[0]["id"]
    frag = cockpit2.render_roloverleg2(cockpit2._Stores(dd), C, iid=iid, csrf_token="t", fragment=True)
    # editor prefilt de huidige rol
    assert "rov-editor" in frag and "Naam" in frag and "Building new features" in frag
    # naam wijzigen -> rename in change; accountability toevoegen -> add_accountabilities
    cockpit2.dispatch(dd, "rov2_set", {"iid": [iid], "field": ["name"], "value": ["Web Developer"], "next": ["/"]})
    cockpit2.dispatch(dd, "rov2_acc_add", {"iid": [iid], "text": ["Bewaken van performance"], "next": ["/"]})
    ch = cockpit2._Stores(dd).agenda.get(iid)["change"]
    assert ch.get("rename") == "Web Developer"
    assert "Bewaken van performance" in ch.get("add_accountabilities", [])
    # bestaande accountability verwijderen -> remove_accountabilities
    cockpit2.dispatch(dd, "rov2_acc_remove", {"iid": [iid], "idx": ["0"], "next": ["/"]})
    assert cockpit2._Stores(dd).agenda.get(iid)["change"].get("remove_accountabilities")


def test_editor_nieuwe_rol(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "naam": ["Data Analist"], "next": ["/"]})
    iid = cockpit2._Stores(dd).agenda.open()[0]["id"]
    cockpit2.dispatch(dd, "rov2_set", {"iid": [iid], "field": ["purpose"], "value": ["Inzicht uit data"], "next": ["/"]})
    cockpit2.dispatch(dd, "rov2_acc_add", {"iid": [iid], "text": ["Rapporteren van trends"], "next": ["/"]})
    ch = cockpit2._Stores(dd).agenda.get(iid)["change"]
    assert ch.get("purpose") == "Inzicht uit data" and "Rapporteren van trends" in ch.get("add_accountabilities", [])


def test_layout_toevoegen_boven_en_groene_knop(tmp_path):
    dd = _dd(tmp_path)
    # zonder agenda: knop bestaat maar is niet groen
    node0 = cockpit2.render_node(cockpit2._Stores(dd), C, "overview", csrf_token="t")
    assert "Governance meeting" in node0 and "btn ok js-modal" not in node0
    cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "naam": ["Website Developer"], "next": ["/"]})
    # met een lopend roloverleg: groen
    node1 = cockpit2.render_node(cockpit2._Stores(dd), C, "overview", csrf_token="t")
    assert "btn ok js-modal" in node1
    frag = cockpit2.render_roloverleg2(cockpit2._Stores(dd), C, csrf_token="t", fragment=True)
    assert "Welke spanning" not in frag                    # spanning-veld weg
    assert frag.find("rov-add") < frag.find("rov-list")    # toevoegen boven de lijst
    assert "rov-grid" in frag and "rov-foot" in frag and "Vergadering sluiten" in frag


def test_sluiten_voert_consented_door(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "naam": ["Website Developer"], "next": ["/"]})
    iid = cockpit2._Stores(dd).agenda.open()[0]["id"]
    cockpit2.dispatch(dd, "rov2_acc_add", {"iid": [iid], "text": ["Bewaken van performance"], "next": ["/"]})
    cockpit2._Stores(dd).agenda.set_status(iid, "consented")
    cockpit2.dispatch(dd, "rov2_end", {"circle": [C], "next": ["/node?id=" + C]})
    # doorgevoerd in de records + van de agenda af
    rec = cockpit2._Stores(dd).records.get(RID)
    assert "Bewaken van performance" in rec.definition.accountabilities
    assert cockpit2._Stores(dd).agenda.all() == []


def test_agenda_initialen_en_geen_kindlabel(tmp_path):
    dd = _dd(tmp_path)
    # initialen komen uit de tekst: '-SW' achteraan
    cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "naam": ["Website Developer -SW"], "next": ["/"]})
    it = cockpit2._Stores(dd).agenda.open()[0]
    assert it["title"] == "Website Developer" and it.get("by") == "SW"
    frag = cockpit2.render_roloverleg2(cockpit2._Stores(dd), C, csrf_token="t", fragment=True)
    assert "door SW" in frag and ">SW<" in frag                  # initialen-avatar
    assert "rov-kind" not in frag and "chip muted'>open" not in frag   # geen kind-label/open-chip
    assert "list='rov-roles'" in frag and "<datalist" in frag    # smart-search
    assert "name='by'" not in frag                               # los initialen-veld weg


def test_secretaris_inline_en_consent(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "naam": ["Website Developer"], "next": ["/"]})
    iid = cockpit2._Stores(dd).agenda.open()[0]["id"]
    cockpit2.dispatch(dd, "rov2_acc_add", {"iid": [iid], "text": ["Snel reageren op tickets"], "next": ["/"]})
    frag = cockpit2.render_roloverleg2(cockpit2._Stores(dd), C, iid=iid, csrf_token="t", fragment=True)
    assert "sec-issue" in frag and "-en-vorm" in frag            # feedback bij de accountability
    assert "rov2_consent" in frag                                # consent kan (alleen advies)


def test_consent_geblokkeerd_zonder_purpose(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "naam": ["Data Analist"], "next": ["/"]})
    iid = cockpit2._Stores(dd).agenda.open()[0]["id"]
    frag = cockpit2.render_roloverleg2(cockpit2._Stores(dd), C, iid=iid, csrf_token="t", fragment=True)
    assert "disabled>Neem voorstel aan" in frag and "rov2_consent" not in frag
    # consent-actie weigert ook serverside
    cockpit2.dispatch(dd, "rov2_consent", {"iid": [iid], "circle": [C], "next": ["/"]})
    assert cockpit2._Stores(dd).agenda.get(iid)["status"] == "open"


def test_consent_en_auto_volgend(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "naam": ["Website Developer"], "next": ["/"]})
    cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "naam": ["Financial Controller"], "next": ["/"]})
    first = cockpit2._Stores(dd).agenda.open()[0]["id"]
    cockpit2.dispatch(dd, "rov2_consent", {"iid": [first], "circle": [C], "next": ["/"]})
    assert cockpit2._Stores(dd).agenda.get(first)["status"] == "consented"
    # zonder iid auto-selecteert de render het volgende OPEN punt
    frag = cockpit2.render_roloverleg2(cockpit2._Stores(dd), C, csrf_token="t", fragment=True)
    assert "Financial Controller" in frag and "rov-editor" in frag


def test_ai_assistent_footer_en_chatvenster(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "naam": ["Website Developer"], "next": ["/"]})
    iid = cockpit2._Stores(dd).agenda.open()[0]["id"]
    # AI-knop staat rechts in de footer (geen inline kladblok meer in de editor)
    frag = cockpit2.render_roloverleg2(cockpit2._Stores(dd), C, iid=iid, csrf_token="t", fragment=True)
    assert "rovchat-toggle" in frag and "AI-assistent" in frag and "chat=1" in frag
    assert "kbblok" not in frag                              # geen ingeklapt kladblok in de editor
    # chat=1 -> chatvenster met de twee modi (eerst vragen waar je hulp bij wilt)
    win = cockpit2.render_roloverleg2(cockpit2._Stores(dd), C, iid=iid, csrf_token="t", fragment=True, chat=True)
    assert "rovchat" in win and "Waar kan ik mee helpen?" in win
    assert "Spanning verhelderen" in win and "Accountability formuleren" in win


def test_ai_helper_mode_bewust(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "naam": ["Website Developer"], "next": ["/"]})
    iid = cockpit2._Stores(dd).agenda.open()[0]["id"]
    item = cockpit2._Stores(dd).agenda.get(iid)
    # spanning-modus stelt vragen; accountability-modus formuleert (-en-vorm)
    p_span = cockpit2._rov_ai_kladblok(cockpit2._Stores(dd), item, mode="spanning", ask=lambda p: p)
    p_acc = cockpit2._rov_ai_kladblok(cockpit2._Stores(dd), item, mode="accountability", ask=lambda p: p)
    assert "verhelderen" in p_span and "scherpe vragen" in p_span
    assert "accountability te formuleren" in p_acc and "-en-vorm" in p_acc


def test_chat_start_en_kladblok(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "naam": ["Website Developer"], "next": ["/"]})
    iid = cockpit2._Stores(dd).agenda.open()[0]["id"]
    cockpit2.dispatch(dd, "rov2_chat_start", {"iid": [iid], "mode": ["spanning"], "next": ["/"]})
    assert cockpit2._Stores(dd).agenda.get(iid).get("chatmode") == "spanning"
    # jouw bericht wordt opgeslagen (AI faalt closed zonder key)
    cockpit2.dispatch(dd, "rov2_kladblok", {"iid": [iid], "text": ["even sparren"], "next": ["/"]})
    kb = cockpit2._Stores(dd).agenda.get(iid).get("kladblok")
    assert kb and kb[-1]["who"] == "jij" and kb[-1]["text"] == "even sparren"
    # reset -> terug naar de keuze
    cockpit2.dispatch(dd, "rov2_chat_start", {"iid": [iid], "mode": ["reset"], "next": ["/"]})
    assert cockpit2._Stores(dd).agenda.get(iid).get("chatmode") == ""


def test_accountability_dubbel_check(tmp_path):
    dd = _dd(tmp_path)
    # een bestaande accountability bij een ándere rol vinden we terug
    st = cockpit2._Stores(dd)
    existing = ""
    for r in st.records.all():
        if r.definition.accountabilities:
            existing = r.definition.accountabilities[0]; break
    hits = cockpit2._rov_dupes(st, existing)
    assert hits and hits[0][1] == existing
    # in accountability-modus plaatst de assistent een ⚠-check bij een dubbele formulering
    cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "naam": ["Data Analist"], "next": ["/"]})
    iid = cockpit2._Stores(dd).agenda.open()[0]["id"]
    cockpit2.dispatch(dd, "rov2_chat_start", {"iid": [iid], "mode": ["accountability"], "next": ["/"]})
    cockpit2.dispatch(dd, "rov2_kladblok", {"iid": [iid], "text": [existing], "next": ["/"]})
    kb = cockpit2._Stores(dd).agenda.get(iid).get("kladblok")
    assert any(m.get("who") == "note" for m in kb)


def test_rol_verwijderen_via_overleg(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "naam": ["Website Developer"], "next": ["/"]})
    iid = cockpit2._Stores(dd).agenda.open()[0]["id"]
    f = cockpit2.render_roloverleg2(cockpit2._Stores(dd), C, iid=iid, csrf_token="t", fragment=True)
    assert "rov-delrole" in f and "Rol verwijderen" in f
    # maak er een verwijder-voorstel van
    cockpit2.dispatch(dd, "rov2_setkind", {"iid": [iid], "kind": ["remove_role"], "next": ["/"]})
    f2 = cockpit2.render_roloverleg2(cockpit2._Stores(dd), C, iid=iid, csrf_token="t", fragment=True)
    assert "wordt <b>verwijderd</b>" in f2 and "terug naar wijzigen" in f2 and "Neem voorstel aan" in f2
    # consent + sluiten -> rol gearchiveerd (verweesd werk = advies, geen blok)
    cockpit2.dispatch(dd, "rov2_consent", {"iid": [iid], "circle": [C], "next": ["/"]})
    cockpit2.dispatch(dd, "rov2_end", {"circle": [C], "next": ["/"]})
    rec = cockpit2._Stores(dd).records.get(RID)
    assert rec is None or rec.archived


def test_secretaris_gate_en_bevestiging_bij_sluiten(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "naam": ["Website Developer"], "next": ["/"]})
    frag = cockpit2.render_roloverleg2(cockpit2._Stores(dd), C, csrf_token="t", fragment=True)
    assert "Alleen de secretaris opent en sluit" in frag        # secretaris-gate (notitie)
    assert "data-confirm=" in frag and "rov2_end" in frag        # bevestiging bij sluiten
    assert "geen aangenomen voorstellen" in frag                 # 0 consented -> melding
    # met een aangenomen voorstel telt de bevestiging mee
    iid = cockpit2._Stores(dd).agenda.open()[0]["id"]
    cockpit2.dispatch(dd, "rov2_acc_add", {"iid": [iid], "text": ["Bewaken van iets"], "next": ["/"]})
    cockpit2.dispatch(dd, "rov2_consent", {"iid": [iid], "circle": [C], "next": ["/"]})
    f2 = cockpit2.render_roloverleg2(cockpit2._Stores(dd), C, csrf_token="t", fragment=True)
    assert "1 aangenomen voorstel(len) worden doorgevoerd" in f2


def test_diff_weergave_verwijderd_en_nieuw(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "naam": ["Website Developer"], "next": ["/"]})
    iid = cockpit2._Stores(dd).agenda.open()[0]["id"]
    rec = cockpit2._Stores(dd).records.get(RID)
    bestaand = rec.definition.accountabilities[0]
    # bestaande accountability verwijderen -> doorgestreept (is-del), niet weg
    cockpit2.dispatch(dd, "rov2_acc_remove", {"iid": [iid], "text": [bestaand], "next": ["/"]})
    # nieuwe accountability toevoegen -> als 'nieuw' gemarkeerd (is-new)
    cockpit2.dispatch(dd, "rov2_acc_add", {"iid": [iid], "text": ["Bewaken van performance"], "next": ["/"]})
    frag = cockpit2.render_roloverleg2(cockpit2._Stores(dd), C, iid=iid, csrf_token="t", fragment=True)
    assert "is-del" in frag and "<s>" in frag and "herstel" in frag    # verwijderd = doorgestreept + herstel
    assert "is-new" in frag and "chip green'>nieuw" in frag             # toegevoegd = nieuw
    # herstel zet 'm terug
    cockpit2.dispatch(dd, "rov2_acc_add", {"iid": [iid], "text": [bestaand], "next": ["/"]})
    ch = cockpit2._Stores(dd).agenda.get(iid)["change"]
    assert bestaand not in ch.get("remove_accountabilities", [])


def test_voorstel_meerdere_rollen(tmp_path):
    dd = _dd(tmp_path)
    # rol splitsen: bestaande rol wijzigen + tegelijk een nieuwe rol in HETZELFDE voorstel
    cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "naam": ["Website Developer"], "next": ["/"]})
    iid = cockpit2._Stores(dd).agenda.open()[0]["id"]
    gid = cockpit2._Stores(dd).agenda.group_of(iid)
    cockpit2.dispatch(dd, "rov2_add_to_group", {"circle": [C], "group": [gid], "naam": ["Data Analist"], "next": ["/"]})
    # twee leden in dezelfde groep, maar één rij in de agenda
    members = cockpit2._Stores(dd).agenda.members_of_group(gid)
    assert len(members) == 2
    frag = cockpit2.render_roloverleg2(cockpit2._Stores(dd), C, iid=iid, csrf_token="t", fragment=True)
    assert "Website Developer" in frag and "Data Analist" in frag      # beide blokken zichtbaar
    assert "rov-more" in frag                                          # '+1' in de agenda-rij
    assert frag.count("class='rovm") >= 2                              # twee wijziging-blokken
    # 'toevoegen aan voorstel' met bestaande/nieuwe rol
    assert "Toevoegen aan voorstel" in frag and "rov2_add_to_group" in frag


def test_groep_consent_en_verwijderen(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "naam": ["Website Developer"], "next": ["/"]})
    iid = cockpit2._Stores(dd).agenda.open()[0]["id"]
    gid = cockpit2._Stores(dd).agenda.group_of(iid)
    cockpit2.dispatch(dd, "rov2_acc_add", {"iid": [iid], "text": ["Bewaken van iets"], "next": ["/"]})
    cockpit2.dispatch(dd, "rov2_add_to_group", {"circle": [C], "group": [gid], "naam": ["Data Analist"], "next": ["/"]})
    new_iid = [m["id"] for m in cockpit2._Stores(dd).agenda.members_of_group(gid) if m["id"] != iid][0]
    cockpit2.dispatch(dd, "rov2_acc_add", {"iid": [new_iid], "text": ["Rapporteren van trends"], "next": ["/"]})
    cockpit2.dispatch(dd, "rov2_set", {"iid": [new_iid], "field": ["purpose"], "value": ["Inzicht"], "next": ["/"]})
    # consent op één lid zet het HELE voorstel op consented
    cockpit2.dispatch(dd, "rov2_consent", {"iid": [iid], "circle": [C], "next": ["/"]})
    assert all(m["status"] == "consented" for m in cockpit2._Stores(dd).agenda.members_of_group(gid))
    # heel voorstel verwijderen
    cockpit2.dispatch(dd, "rov2_remove_group", {"iid": [iid], "circle": [C], "next": ["/"]})
    assert cockpit2._Stores(dd).agenda.all() == []


def test_select_en_verwijderen(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "naam": ["Website Developer"], "next": ["/"]})
    iid = cockpit2._Stores(dd).agenda.open()[0]["id"]
    sel = cockpit2.render_roloverleg2(cockpit2._Stores(dd), C, iid=iid, csrf_token="t", fragment=True)
    assert "rov-item on" in sel and "Toevoegen aan voorstel" in sel
    cockpit2.dispatch(dd, "rov2_remove", {"iid": [iid], "circle": [C], "next": ["/"]})
    assert cockpit2._Stores(dd).agenda.open() == []
