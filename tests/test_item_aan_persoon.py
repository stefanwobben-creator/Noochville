"""Een checklist-item aan een persoon geven (besluit Stefan, 15 oktober 2026).

Eén optionele persoon per item (`persoon` op het item, geen nieuwe store), gekozen in het ✎-
formulier. Een toegewezen item staat op /acties en /today van die persoon en NIET bij anderen;
niet-toegewezen items volgen de gewone regel. Eén DM aan wie het krijgt — niet aan jezelf, niet aan
wie het eerder had — met projectnaam en itemtekst, en bij een nog niet gestart project dat het later
in de acties verschijnt. Geen LLM-call. Een verwijderde gebruiker valt terug naar niet-toegewezen.
"""
from __future__ import annotations

import pytest

from nooch_village import cockpit2
from nooch_village.views import acties as V

from tests.test_acties_checklist import ROL, _dorp, _plan, _teksten


@pytest.fixture
def dorp(tmp_path, monkeypatch):
    dd, st, ik, beer = _dorp(tmp_path)
    cees = st.people.add("Cees Drie", "cees@test.nl")
    pid = st.projects.create(ROL, "Permalinks", "human", status="running")
    clid = _plan(st, pid, [("GS1 masterdata uitzoeken", None), ("Shopify koppelen", None)])
    berichten = []
    monkeypatch.setattr(cockpit2, "_signaleer",
                        lambda st_, soort, doel, tekst, **kw: berichten.append((soort, doel, tekst)) or "m1")
    from nooch_village import llm

    def _nooit(*a, **k):
        raise AssertionError("toewijzen mag geen LLM aanroepen")
    monkeypatch.setattr(llm, "reason", _nooit)
    return dd, ik, beer, cees, pid, clid, berichten


def _item(dd, pid, n=0):
    p = cockpit2._Stores(dd).projects.get(pid)
    return p["checklists"][0]["items"][n]


def _geef(dd, pid, clid, item, persoon, wie="aap@test.nl", tekst=None):
    form = {"pid": [pid], "clid": [clid], "item": [item["id"]], "text": [tekst or item["text"]],
            "persoon": [persoon], "next": ["/"]}
    return cockpit2.dispatch(dd, "check_rename", form, username=wie)[1]


def test_toewijzen_herwijzen_en_ongedaan_maken(dorp):
    dd, ik, beer, cees, pid, clid, berichten = dorp
    it = _item(dd, pid)
    assert _geef(dd, pid, clid, it, beer.id) == "✎ item given to Beer Twee"
    assert _item(dd, pid)["persoon"] == beer.id
    assert _geef(dd, pid, clid, it, cees.id) == "✎ item given to Cees Drie"          # herwijzen
    assert _item(dd, pid)["persoon"] == cees.id
    assert _geef(dd, pid, clid, it, "") == "✎ item no longer assigned"              # ongedaan
    assert "persoon" not in _item(dd, pid)
    # opslaan zonder wijziging: geen schrijfactie, geen melding
    assert _geef(dd, pid, clid, it, "") == "· nothing changed"


def test_een_melding_alleen_aan_wie_het_krijgt(dorp):
    dd, ik, beer, cees, pid, clid, berichten = dorp
    it = _item(dd, pid)
    _geef(dd, pid, clid, it, beer.id)
    _geef(dd, pid, clid, it, beer.id)                         # nog eens opslaan: geen tweede DM
    _geef(dd, pid, clid, it, cees.id)                         # overnemen: Beer krijgt niets
    _geef(dd, pid, clid, it, "")                              # intrekken: niemand krijgt iets
    assert [(s, d) for s, d, _t in berichten] == [("person", beer.id), ("person", cees.id)]
    tekst = berichten[0][2]
    assert "Aap Een gave you an item on “Permalinks”: “GS1 masterdata uitzoeken”." == tekst


def test_geen_melding_als_je_het_aan_jezelf_geeft(dorp):
    dd, ik, beer, cees, pid, clid, berichten = dorp
    assert _geef(dd, pid, clid, _item(dd, pid), ik.id) == "✎ item given to Aap Een"
    assert berichten == []


def test_bij_een_project_dat_nog_niet_loopt_zegt_de_melding_dat(dorp):
    dd, ik, beer, cees, pid, clid, berichten = dorp
    st = cockpit2._Stores(dd)
    toek = st.projects.create(ROL, "Later", "human", status="future")
    cl2 = _plan(st, toek, [("Iets voor later", None)])
    _geef(dd, toek, cl2, _item(dd, toek), beer.id)
    assert berichten[-1][2].endswith("The project hasn't started yet; the item appears in your "
                                     "actions once it does.")
    # en het staat (nog) niet in Beers acties: zelfde bordregel als elk item
    assert "Iets voor later" not in _teksten(cockpit2._Stores(dd), beer)


def test_zichtbaar_bij_de_juiste_persoon_en_niet_bij_anderen(dorp):
    dd, ik, beer, cees, pid, clid, berichten = dorp
    _geef(dd, pid, clid, _item(dd, pid), beer.id)
    st = cockpit2._Stores(dd)
    # Beer vervult de rol van dit project niet, maar het item is aan hem gegeven
    assert _teksten(st, beer) == ["GS1 masterdata uitzoeken"]
    # Aap (rolvervuller) ziet het gegeven item niet meer, het andere wel
    assert _teksten(st, ik) == ["Shopify koppelen"]
    assert _teksten(st, cees) == []
    # /today rekent met dezelfde lijst
    from nooch_village.views.today import render_today
    assert "<b>1 checklist item need a human</b>" in render_today(st, ik=beer.id)
    assert "checklist item" not in render_today(st, ik=cees.id)


def test_een_verwijderde_gebruiker_valt_terug(dorp):
    dd, ik, beer, cees, pid, clid, berichten = dorp
    _geef(dd, pid, clid, _item(dd, pid), cees.id)
    st = cockpit2._Stores(dd)
    st.people._items.pop(cees.id)
    st.people._save()
    st = cockpit2._Stores(dd)
    assert sorted(_teksten(st, ik)) == ["GS1 masterdata uitzoeken", "Shopify koppelen"]  # gewone regel
    html = cockpit2.render_project(st, pid, csrf_token="t")
    assert "Cees Drie" not in html                                   # geen label, geen fout


def test_alleen_bestaande_gebruikers_en_alleen_wie_mag_bewerken(dorp):
    dd, ik, beer, cees, pid, clid, berichten = dorp
    it = _item(dd, pid)
    assert _geef(dd, pid, clid, it, "bestaat-niet").startswith("✗ pick someone")
    assert "persoon" not in _item(dd, pid)
    # Beer vervult de eigenaar-rol niet: hij mag niet toewijzen (zelfde poort als bewerken)
    msg = _geef(dd, pid, clid, it, beer.id, wie="beer@test.nl")
    assert "persoon" not in _item(dd, pid) and not msg.startswith("✎")


def test_label_op_het_item_en_de_keuzelijst_in_het_bewerkformulier(dorp):
    dd, ik, beer, cees, pid, clid, berichten = dorp
    _geef(dd, pid, clid, _item(dd, pid), beer.id)
    html = cockpit2.render_project(cockpit2._Stores(dd), pid, csrf_token="t")
    assert "<span class='chip muted' title='Assigned to Beer Twee'>Beer Twee</span>" in html
    # de keuze zit in het ✎-paneel: een <details>/<summary> (toetsenbord: Tab + Enter) met een
    # gewone <select> erin (toetsenbord: pijltjes)
    paneel = html.split("<details class='fedit ck-bewerk'>", 1)[1].split("</details>", 1)[0]
    assert "<summary class='flink' title='edit item'>✎</summary>" in paneel
    assert "<select name='persoon' aria-label='Assigned to'><option value=''>Nobody</option>" in paneel
    assert f"<option value='{beer.id}' selected>Beer Twee</option>" in paneel
    # geen nieuwe klassen: alleen `chip muted` en de bestaande `ck-`-klassen
    assert "ck-persoon" not in html and "assignee" not in html


def test_de_melding_landt_echt_als_dm_bij_de_ontvanger(tmp_path):
    """Zonder nep-`_signaleer`: de bestaande DM-weg (`signaal.stuur`) zet het bericht in een kanaal
    van de ontvanger, en nergens een actie erbij (dat zou `route_werk` doen: dubbel werk)."""
    dd, st, ik, beer = _dorp(tmp_path)
    pid = st.projects.create(ROL, "Permalinks", "human", status="running")
    clid = _plan(st, pid, [("GS1 masterdata uitzoeken", None)])
    _geef(dd, pid, clid, _item(dd, pid), beer.id)
    st = cockpit2._Stores(dd)
    teksten = [e.get("text") or e.get("tekst") or "" for k in st.channels.kanalen_van(beer.id)
               for e in st.channels.trail(k)]
    assert sum("“GS1 masterdata uitzoeken”" in t for t in teksten) == 1
    assert st.acties.voor(beer.id) == []
