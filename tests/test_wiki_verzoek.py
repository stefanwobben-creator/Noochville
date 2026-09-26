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

def _dm_teksten_aan(st, persoon_id):
    """De DM-teksten die deze persoon heeft gekregen. Het ANTWOORD op een verzoek is sinds
    20 september 2026 een DM; het verzoek zelf staat nog in `NotifStore`, want dat draagt een
    beslissing (accepteren/weigeren/aanpassen) en een DM kan dat niet."""
    return [e.get("text") or "" for k in st.channels.kanalen_van(persoon_id)
            for e in st.channels.trail(k)]

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

    # Het voorstel is sinds B2 een DM bij de mens die de eigenaar-rol vervult: geen kaart met drie
    # knoppen, geen `pagina`-blok, geen `bevinding`. Wat overeind moet blijven is dat de ONTVANGER
    # klopt, dat de VOORGESTELDE TEKST meekomt (anders kan hij niets beoordelen), en dat er nog
    # niets is geschreven — een voorstel verandert uit zichzelf niets.
    st2 = cockpit2._Stores(dd)
    alice = next(p for p in st2.people.all() if p.name == "Alice")
    teksten = [e.get("text") or "" for k in st2.channels.kanalen_van(alice.id)
               for e in st2.channels.trail(k)]
    assert teksten
    bericht = teksten[-1]
    assert "hier ontbreekt de herkomst" in bericht              # de reden
    assert "Nieuwe tekst met herkomst." in bericht              # WAT er wordt voorgesteld
    assert a.id in bericht                                      # en waar het over gaat
    assert any(bob.id in k for k in st2.channels.kanalen_van(alice.id))   # van Bob
    assert st2.att.get(a.id).body == "Oude tekst."              # nog niets geschreven

# WAT HIER OOK WEG IS: `test_voorstel_slaat_de_dure_herschrijfhaak_over`. Die toetste dat een
# voorstel met een eigen `type` de LLM-verrijker van `spanning_ontstaat` oversloeg. Die haak hing
# aan `NotifStore.add` en is in B2 met pensioen gegaan — er valt niets meer over te slaan.

def test_voorstel_zonder_wijziging_of_zonder_reden_wordt_geweigerd(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    _persoon(st, "Bob", "bob@nooch.earth")
    a = st.att.add(OWNER, "note", title="p", body="zelfde tekst")
def test_pagina_toont_voorstelknop_aan_niet_eigenaar_en_editknop_aan_eigenaar(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    _persoon(st, "Alice", "alice@nooch.earth", OWNER)
    _persoon(st, "Bob", "bob@nooch.earth")
    # MET EEN DOMEIN, anders mág Bob gewoon bewerken en is er geen voorstelpad te tonen — zie
    # de domein-gate van 26 september. Het voorstelpad zelf is ongewijzigd.
    a = st.att.add(OWNER, "note", title="HyphaLite", body="tekst", domain="Materials")
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
