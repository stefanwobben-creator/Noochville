"""`ongelezen(st, ik)` los uit `render_messages` (17 oktober 2026).

Eén regel voor "wat is er nieuw voor deze mens": het Messages-scherm, `/today` en straks de weekmail
gebruiken hem. GEEN GEDRAGSVERANDERING voor het scherm — bewezen met de oude lus, hier letterlijk als
referentie, en met de getoonde teller. `ongelezen` geeft nooit berichttekst terug."""
from __future__ import annotations

import json
import os
import re

import pytest

from nooch_village import channels, cockpit2
from nooch_village.views import messages as M


def _oud(st, ik, kanalen):
    """De lus zoals hij tot 17 oktober 2026 in `render_messages` stond, ongewijzigd."""
    ongelezen: dict = {}
    if ik:
        gz = st.people.gezien(ik)
        for k in kanalen:
            sinds = float(gz.get(k) or 0)
            n = 0
            for e in st.channels.trail(k, limit=M._ONGELEZEN_CAP):
                if float(e.get("at") or 0) <= sinds:
                    continue
                if (e.get("author") or {}).get("id") == ik:
                    continue
                n += 1
            if n:
                ongelezen[k] = n
    return ongelezen


@pytest.fixture
def dorp(tmp_path, monkeypatch):
    klok = {"t": 1_790_000_000.0}
    monkeypatch.setattr(channels.time, "time", lambda: klok["t"]) if hasattr(channels, "time") else None
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    ada = st.people.add("Ada Lovelace", "ada@x.nl")
    bo = st.people.add("Bo Bakker", "bo@x.nl")
    cy = st.people.add("Cy Chen", "cy@x.nl")
    dm_bo, dm_cy = channels.dm_kanaal(ada.id, bo.id), channels.dm_kanaal(ada.id, cy.id)
    for i in range(3):
        klok["t"] += 60
        st.channels.post(dm_bo, f"GEHEIM-oud-{i}", author_id=bo.id)
    st.people.markeer_gezien(ada.id, dm_bo, klok["t"] - 30)                 # alleen het 3e is nieuw
    klok["t"] += 60
    st.channels.post(dm_bo, "GEHEIM-eigen", author_id=ada.id)                # eigen telt niet
    klok["t"] += 60
    st.channels.post(dm_bo, "@Ada GEHEIM-vermelding", author_id=bo.id,
                     herkomst={"project": "p1", "entry": "e1"})
    for i in range(60):                                                      # boven de cap van 50
        klok["t"] += 1
        st.channels.post(dm_cy, f"GEHEIM-veel-{i}", author_id=cy.id)
    klok["t"] += 1
    return dd, ada, bo, cy, dm_bo, dm_cy


def test_de_telling_is_exact_de_oude_lus(dorp):
    dd, ada, bo, cy, dm_bo, dm_cy = dorp
    st = cockpit2._Stores(dd)
    groepen, _t, _g = M._kanalen(st, ada.id, "")
    kanalen = [k for rij in groepen.values() for k in rij]
    nieuw = M.ongelezen_per_kanaal(st, ada.id, kanalen)
    assert nieuw == _oud(st, ada.id, kanalen)
    assert nieuw[dm_bo] == 2 and nieuw[dm_cy] == M._ONGELEZEN_CAP                # cap blijft 50
    for wie in (bo.id, cy.id, ""):                                           # ook voor anderen en zonder ik
        g, _t, _g = M._kanalen(st, wie, "")
        kn = [k for rij in g.values() for k in rij]
        assert M.ongelezen_per_kanaal(st, wie, kn) == _oud(st, wie, kn)


def test_het_scherm_toont_dezelfde_tellers(dorp):
    dd, ada, _bo, _cy, dm_bo, dm_cy = dorp
    html = M.render_messages(cockpit2._Stores(dd), ik=ada.id, csrf_token="t")
    tellers = dict(re.findall(r"href='/messages\?k=([^'&]+)[^']*'>(?:(?!</a>).)*?"
                              r"<span class='msg-nieuw'>([^<]+)</span>", html))
    assert tellers == {dm_bo: "2", dm_cy: "9+"}


def test_ongelezen_geeft_vorm_zonder_tekst(dorp):
    dd, ada, bo, cy, dm_bo, dm_cy = dorp
    rijen = M.ongelezen(cockpit2._Stores(dd), ada.id)
    assert [r["kanaal"] for r in rijen] == [dm_cy, dm_bo]                    # nieuwste eerst
    per = {r["kanaal"]: r for r in rijen}
    assert set(per[dm_bo]) == {"kanaal", "soort", "aantal", "vermeldingen", "laatste_at", "van"}
    assert per[dm_bo]["aantal"] == 2 and per[dm_bo]["vermeldingen"] == 1 and per[dm_bo]["van"] == [bo.id]
    assert per[dm_cy]["aantal"] == 50 and per[dm_cy]["vermeldingen"] == 0
    assert per[dm_bo]["soort"] == channels.soort_van(dm_bo)
    assert "GEHEIM" not in json.dumps(rijen)                                 # nooit berichttekst


def test_ongelezen_is_puur(dorp):
    dd, ada, *_ = dorp
    pad = os.path.join(dd, "people.json")
    voor = open(pad, "rb").read()
    M.ongelezen(cockpit2._Stores(dd), ada.id)
    M.ongelezen_per_kanaal(cockpit2._Stores(dd), ada.id, [])
    assert open(pad, "rb").read() == voor                                    # niets als gelezen gemarkeerd
    assert M.ongelezen(cockpit2._Stores(dd), "") == []


def test_na_openen_is_het_gelezen_en_een_signaal_is_geen_vermelding(dorp):
    dd, ada, bo, _cy, dm_bo, _dm_cy = dorp
    st = cockpit2._Stores(dd)
    st.channels.post(dm_bo, "GEHEIM-signaal", author_id=bo.id, herkomst={"project": "p1"})
    assert {r["kanaal"]: r["vermeldingen"] for r in M.ongelezen(cockpit2._Stores(dd), ada.id)}[dm_bo] == 1
    M.render_messages(cockpit2._Stores(dd), ik=ada.id, kanaal=dm_bo, csrf_token="t")   # openen = gezien
    assert dm_bo not in {r["kanaal"] for r in M.ongelezen(cockpit2._Stores(dd), ada.id)}
