"""Wiki brok 2 — "ik vind dat pagina X moet zeggen Y".

Bewerken is van de eigenaar; wie dat niet is doet een VOORSTEL. Dat loopt langs het bestaande
verzoekmechanisme (een `naar_rol`-item met accepteren / aanpassen / weigeren) — geen nieuw scherm en
geen tweede beslis-logica. Eén ding is hier concreter dan bij een gewoon verzoek: de tekst ÍS het
voorstel, dus accepteren schrijft hem als nieuwe versie in plaats van er een project van te maken.

Deze tests bewaken vooral de twee plekken waar het stil mis kan gaan:
  - een AI-vervulde eigenaar-rol leest de mens-inbox nooit → het verzoek gaat naar de Circle Lead,
  - het antwoord aan de vrager gaat naar de PERSOON, niet naar een 'rol' met een persoon-id erin.
"""
from __future__ import annotations

import pytest

from nooch_village import cockpit2, wiki
from nooch_village.views.inbox import render_verwerk
from nooch_village.views.wiki import render_pagina

OWNER = "mother_earth__nooch__creator_of_shoes"
CIRCLE = "mother_earth__nooch"
LEAD = "mother_earth__nooch__circle_lead"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def _ontmens(st, rol):
    """Haal de mens-vervullers van een rol af. Een verse bootstrap zet de founder al op een paar
    rollen; voor 'deze rol is AI-vervuld/onbemand' moet dat er eerst af."""
    for f in list(st.assign.fillers_of(rol, record=st.records.get(rol))):
        if f.type == "person":
            st.assign.unassign(rol, "person", f.id)


def _persoon(st, naam, mail, rol=None):
    p = st.people.add(naam, mail)
    if rol:
        st.assign.assign(rol, "person", p.id)
    return p


def _laatste(st, target_id):
    items = [n for n in st.notif.all() if n.get("target_id") == target_id]
    return items[-1] if items else None


# ── routering: waar landt het verzoek? ──────────────────────────────────────

def test_mens_vervulde_eigenaar_krijgt_het_zelf(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    _persoon(st, "Alice", "alice@nooch.earth", OWNER)
    ontv = wiki.ontvanger(OWNER, cockpit2._Stores(st.dd).records,
                          cockpit2._Stores(st.dd).assign)
    assert ontv["rol"] == OWNER and ontv["reden"] == ""


def test_ai_vervulde_eigenaar_routeert_naar_circle_lead(tmp_path):
    # De bekende dead letter: een AI-rol leest de NotifStore nooit. Dan is 'netjes bezorgen bij de
    # eigenaar' hetzelfde als weggooien.
    st = cockpit2._Stores(_dd(tmp_path))
    _ontmens(st, OWNER)
    st.assign.assign(OWNER, "persona", "ai_wendy")
    st2 = cockpit2._Stores(st.dd)
    ontv = wiki.ontvanger(OWNER, st2.records, st2.assign)
    assert ontv["rol"] == LEAD and "no human filler" in ontv["reden"]


def test_onbemande_eigenaar_routeert_ook_naar_circle_lead(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    _ontmens(st, OWNER)
    st2 = cockpit2._Stores(st.dd)
    ontv = wiki.ontvanger(OWNER, st2.records, st2.assign)
    assert ontv["rol"] == LEAD


# ── de voorstel-route ───────────────────────────────────────────────────────

def test_voorstel_landt_als_naar_rol_item_met_de_tekst(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    _persoon(st, "Alice", "alice@nooch.earth", OWNER)          # eigenaar (mens)
    bob = _persoon(st, "Bob", "bob@nooch.earth")               # vraagt iets
    a = st.att.add(OWNER, "note", title="HyphaLite", body="Oude tekst.")

    nxt, msg = cockpit2.dispatch(dd, "pagina_voorstel",
        {"aid": [a.id], "waarom": ["hier ontbreekt de herkomst"],
         "voorstel": ["Nieuwe tekst met herkomst."], "next": ["/"]},
        username="bob@nooch.earth")
    assert "proposal sent" in msg

    n = _laatste(cockpit2._Stores(dd), OWNER)
    assert n["type"] == "naar_rol"                              # bestaande drie-knoppen-kaart
    assert n["by"] == bob.id
    assert n["pagina"]["aid"] == a.id
    assert n["pagina"]["body"] == "Nieuwe tekst met herkomst."
    assert n["pagina"]["was"] == "Oude tekst."                  # het verschil blijft leesbaar
    assert "herkomst" in n["bevinding"]["spanning"]
    assert cockpit2._Stores(dd).att.get(a.id).body == "Oude tekst."   # nog niets geschreven


def test_voorstel_slaat_de_dure_herschrijfhaak_over(tmp_path):
    # Het type staat er bij het ONTSTAAN al op; dan hoeft de verrijker (LLM) niet te draaien.
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    geraakt = []
    st.notif.set_verrijker(lambda n: geraakt.append(n) or {"type": "founder"})
    a = st.att.add(OWNER, "note", title="p", body="oud")
    snippet, extra = wiki.voorstel_velden(a, voorstel="nieuw", waarom="omdat",
                                          van_naam="Bob", van_id="b1")
    n = st.notif.add("role", OWNER, "", by="b1", snippet=snippet, extra=extra)
    assert geraakt == [] and n["type"] == "naar_rol"
    # een item zónder eigen type gaat er wél langs (de haak blijft gewoon werken)
    st.notif.add("role", OWNER, "", by="b1", snippet="rauwe spanning")
    assert len(geraakt) == 1


def test_voorstel_zonder_wijziging_of_zonder_reden_wordt_geweigerd(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    _persoon(st, "Bob", "bob@nooch.earth")
    a = st.att.add(OWNER, "note", title="p", body="zelfde tekst")

    _, msg1 = cockpit2.dispatch(dd, "pagina_voorstel",
        {"aid": [a.id], "waarom": ["iets"], "voorstel": ["zelfde tekst"], "next": ["/"]},
        username="bob@nooch.earth")
    assert "already there" in msg1
    _, msg2 = cockpit2.dispatch(dd, "pagina_voorstel",
        {"aid": [a.id], "waarom": ["  "], "voorstel": ["andere tekst"], "next": ["/"]},
        username="bob@nooch.earth")
    assert "one line" in msg2
    assert [n for n in cockpit2._Stores(dd).notif.all() if n.get("pagina")] == []


# ── beslissen: accepteren schrijft, de rest niet ────────────────────────────

def _voorstel(dd, aid, *, door="bob@nooch.earth", tekst="Nieuwe tekst."):
    cockpit2.dispatch(dd, "pagina_voorstel",
                      {"aid": [aid], "waarom": ["kan beter"], "voorstel": [tekst], "next": ["/"]},
                      username=door)
    st = cockpit2._Stores(dd)
    return [n for n in st.notif.all() if n.get("pagina")][-1]


def test_accepteren_schrijft_een_nieuwe_versie_met_de_vrager_erin(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    alice = _persoon(st, "Alice", "alice@nooch.earth", OWNER)
    _persoon(st, "Bob", "bob@nooch.earth")
    a = st.att.add(OWNER, "note", title="HyphaLite", body="Oude tekst.")
    n = _voorstel(dd, a.id)

    nxt, msg = cockpit2.dispatch(dd, "verzoek_besluit",
        {"nid": [n["id"]], "keuze": ["accepteer"], "next": ["/"]},
        username="alice@nooch.earth")
    assert "new version" in msg
    vers = cockpit2._Stores(dd).att.get(a.id)
    assert vers.body == "Nieuwe tekst."
    assert vers.versions[-1]["change_note"] == "voorstel van Bob aangenomen"
    assert vers.versions[-1]["actor_id"] == alice.id           # wie tekende, staat in de historie
    # het item is verwerkt én uit de wachtrij; er is GEEN project van gemaakt
    beslist = next(x for x in cockpit2._Stores(dd).notif.all() if x["id"] == n["id"])
    assert beslist.get("processed") and beslist.get("archived")
    assert cockpit2._Stores(dd).projects.all() == [] or all(
        p.get("origin") != "projectverzoek" for p in cockpit2._Stores(dd).projects.all())


def test_circle_lead_mag_beslissen_over_een_ai_pagina(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    _ontmens(st, OWNER)
    st.assign.assign(OWNER, "persona", "ai_wendy")             # eigenaar is AI
    _ontmens(st, LEAD)
    _persoon(st, "Lead", "lead@nooch.earth", LEAD)
    _persoon(st, "Bob", "bob@nooch.earth")
    a = st.att.add(OWNER, "note", title="HyphaLite", body="oud")
    n = _voorstel(dd, a.id)
    assert n["target_id"] == LEAD                              # niet in de dode brievenbus

    _, msg = cockpit2.dispatch(dd, "verzoek_besluit",
        {"nid": [n["id"]], "keuze": ["accepteer"], "next": ["/"]}, username="lead@nooch.earth")
    assert "new version" in msg
    assert cockpit2._Stores(dd).att.get(a.id).body == "Nieuwe tekst."


def test_weigeren_schrijft_niets_en_antwoordt_de_persoon(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    _persoon(st, "Alice", "alice@nooch.earth", OWNER)
    bob = _persoon(st, "Bob", "bob@nooch.earth")
    a = st.att.add(OWNER, "note", title="p", body="oud")
    n = _voorstel(dd, a.id)

    _, msg = cockpit2.dispatch(dd, "verzoek_besluit",
        {"nid": [n["id"]], "keuze": ["weiger"], "tekst": ["dit klopt feitelijk niet"], "next": ["/"]},
        username="alice@nooch.earth")
    assert "geweigerd" in msg
    assert cockpit2._Stores(dd).att.get(a.id).body == "oud"
    # het antwoord gaat naar de PERSOON Bob — een 'rol' met zijn persoon-id zou nergens aankomen
    terug = [x for x in cockpit2._Stores(dd).notif.all()
             if x.get("target_type") == "person" and x.get("target_id") == bob.id]
    assert terug and "geweigerd" in terug[-1]["snippet"]


def test_aanpassen_stuurt_herformulering_terug_zonder_te_schrijven(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    _persoon(st, "Alice", "alice@nooch.earth", OWNER)
    bob = _persoon(st, "Bob", "bob@nooch.earth")
    a = st.att.add(OWNER, "note", title="p", body="oud")
    n = _voorstel(dd, a.id)

    cockpit2.dispatch(dd, "verzoek_besluit",
        {"nid": [n["id"]], "keuze": ["aanpassen"], "tekst": ["noem ook de leverancier"], "next": ["/"]},
        username="alice@nooch.earth")
    assert cockpit2._Stores(dd).att.get(a.id).body == "oud"
    terug = [x for x in cockpit2._Stores(dd).notif.all()
             if x.get("target_type") == "person" and x.get("target_id") == bob.id]
    assert terug and "herformulering" in terug[-1]["snippet"]


def test_wie_de_rol_niet_vervult_kan_niet_beslissen(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    _persoon(st, "Alice", "alice@nooch.earth", OWNER)
    _persoon(st, "Bob", "bob@nooch.earth")
    a = st.att.add(OWNER, "note", title="p", body="oud")
    n = _voorstel(dd, a.id)
    _, msg = cockpit2.dispatch(dd, "verzoek_besluit",
        {"nid": [n["id"]], "keuze": ["accepteer"], "next": ["/"]}, username="bob@nooch.earth")
    assert "No access" in msg
    assert cockpit2._Stores(dd).att.get(a.id).body == "oud"


def test_verwijderde_pagina_faalt_netjes(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    _persoon(st, "Alice", "alice@nooch.earth", OWNER)
    _persoon(st, "Bob", "bob@nooch.earth")
    a = st.att.add(OWNER, "note", title="p", body="oud")
    n = _voorstel(dd, a.id)
    cockpit2._Stores(dd).att.remove(a.id)
    _, msg = cockpit2.dispatch(dd, "verzoek_besluit",
        {"nid": [n["id"]], "keuze": ["accepteer"], "next": ["/"]}, username="alice@nooch.earth")
    assert "bestaat niet meer" in msg


# ── scherm ──────────────────────────────────────────────────────────────────

def test_pagina_toont_voorstelknop_aan_niet_eigenaar_en_editknop_aan_eigenaar(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    _persoon(st, "Alice", "alice@nooch.earth", OWNER)
    _persoon(st, "Bob", "bob@nooch.earth")
    a = st.att.add(OWNER, "note", title="HyphaLite", body="tekst")
    st2 = cockpit2._Stores(st.dd)

    bezoeker = render_pagina(st2, a.id, csrf_token="tok", username="bob@nooch.earth")
    assert "pagina_voorstel" in bezoeker and "Suggest a change" in bezoeker
    assert "Goes to" in bezoeker and "Alice" not in bezoeker.split("Goes to")[0][-200:]
    assert "artefact_edit" not in bezoeker

    eigenaar = render_pagina(st2, a.id, csrf_token="tok", username="alice@nooch.earth")
    assert "artefact_edit" in eigenaar and "pagina_voorstel" not in eigenaar


def test_pagina_zonder_schrijfsessie_toont_geen_voorstelknop(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    _persoon(st, "Bob", "bob@nooch.earth")
    a = st.att.add(OWNER, "note", title="p", body="tekst")
    html = render_pagina(cockpit2._Stores(st.dd), a.id, csrf_token="", username="bob@nooch.earth")
    assert "pagina_voorstel" not in html


def test_inbox_toont_het_voorstel_en_zegt_wat_accepteren_doet(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    _persoon(st, "Alice", "alice@nooch.earth", OWNER)
    _persoon(st, "Bob", "bob@nooch.earth")
    a = st.att.add(OWNER, "note", title="HyphaLite", body="Oude tekst.")
    n = _voorstel(dd, a.id)

    html = render_verwerk(cockpit2._Stores(dd), n, csrf_token="tok")
    assert "Proposal for page" in html and "HyphaLite" in html
    assert "Nieuwe tekst." in html and "Oude tekst." in html        # het verschil is leesbaar
    assert f"/pagina?id={a.id}" in html
    assert "new version of the page" in html                       # niet: 'project op je bord'
    for knop in ("accepteer", "aanpassen", "weiger"):               # de bestaande drie knoppen
        assert f"value='{knop}'" in html


def test_inbox_toont_geen_tegenstrijdige_project_zin_bij_een_pagina(tmp_path):
    # De generieke kaart zegt "dan verschijnt het als project op je bord". Bij een pagina klopt dat
    # niet, en twee tegengestelde zinnen op één scherm is erger dan één zin te weinig.
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    _persoon(st, "Alice", "alice@nooch.earth", OWNER)
    bob = _persoon(st, "Bob Reader", "bob@nooch.earth")
    a = st.att.add(OWNER, "note", title="HyphaLite", body="Oude tekst.")
    n = _voorstel(dd, a.id)

    html = render_verwerk(cockpit2._Stores(dd), n, csrf_token="tok")
    assert "als project op je bord" not in html
    assert "Bob Reader" in html and bob.id not in html      # naam, geen kaal persoon-id
