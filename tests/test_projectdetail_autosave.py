"""Projectdetails-zijbalk: auto-opslaan (onchange/onblur, geen knop) + trekker-ververs bij rol-wissel.

De vier controls (rol/trekker/missie/business/effort) slaan op bij selectie/blur; de modal vangt de
submit via wire() → reopen (fragment-re-render) + toast, met een .catch voor het foutpad. De server-side
reset (_resync_trekker) + de re-render ververst de trekker-opties na een rol-wissel. Een afgewezen waarde
slaat niet op → bij re-render springt de oude waarde terug.
"""
from __future__ import annotations

from nooch_village import cockpit2
from nooch_village.views import projects as P

WEBDEV = "mother_earth__nooch__website_developer"
FACTORY = "mother_earth__nooch__factory_development_specialist"
INMATE = "mother_earth__nooch__inmate_in_residence"


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


def _rw(dd, pid):
    return P.render_project(cockpit2._Stores(dd), pid, csrf_token="TOK")


def test_autosave_bedrading_geen_knoppen(tmp_path):
    dd, st = _st(tmp_path)
    pid = st.projects.create(WEBDEV, "T", "human")
    frag = _rw(dd, pid)
    assert "requestSubmit" in frag                              # de auto-submit-handler
    for act in ("proj_setowner", "proj_settrekker", "proj_setimpact", "proj_seteffort"):
        assert f"name='action' value='{act}'" in frag          # actie zit nu in een verborgen input
        assert f"value='{act}'>opslaan" not in frag            # geen opslaan-knop meer op deze forms
    assert "name='owner' onchange=" in frag and "name='trekker' onchange=" in frag
    assert "name='value' onchange=" in frag                    # impact-dropdown auto-opslaan
    assert "name='unit' onchange=" in frag and "onblur=" in frag   # effort: toggle onchange, getal onblur


def test_foutpad_catch_in_wire(tmp_path):
    # geen stille mislukking: wire() heeft een .catch met een 'niet opgeslagen'-toast (+ reopen = revert)
    modal = P._modal_html()
    assert ".catch(function()" in modal and "niet opgeslagen" in modal


def test_rolwissel_ververst_trekker_opties_en_invalideert(tmp_path):
    dd, st = _st(tmp_path)
    codie = st.personas.add("Codie")
    marky = st.personas.add("Marky")
    st.assign.assign(FACTORY, "persona", codie.id)             # FACTORY: enige filler Codie
    st.assign.assign(INMATE, "persona", marky.id)              # INMATE: enige filler Marky
    pid = st.projects.create(FACTORY, "Doel", "human", agent=codie.id)
    assert f"persona:{codie.id}" in _rw(dd, pid)               # vóór: trekker-opties tonen Codie
    # wissel naar INMATE: Codie is daar geen filler → server reset naar Marky (enige filler)
    cockpit2.dispatch(dd, "proj_setowner", {"pid": [pid], "owner": [INMATE], "next": ["/"]}, username="guest")
    assert cockpit2._Stores(dd).projects.get(pid).get("agent") == marky.id   # verweesde trekker gereset
    frag = _rw(dd, pid)
    assert f"persona:{marky.id}" in frag and f"persona:{codie.id}" not in frag   # opties ververst


def test_server_reject_bewaart_oude_waarde_in_render(tmp_path):
    dd, st = _st(tmp_path)
    pid = st.projects.create(WEBDEV, "T", "human", missie_impact="versterkt")
    # afgewezen waarde slaat NIET op → de re-render toont nog de oude (revert)
    _, msg = cockpit2.dispatch(dd, "proj_setimpact",
                               {"pid": [pid], "kind": ["missie"], "value": ["banaan"], "next": ["/"]}, "guest")
    assert "ongeldig" in msg.lower()
    assert cockpit2._Stores(dd).projects.get(pid)["missie_impact"] == "versterkt"
    assert "value='versterkt' selected" in _rw(dd, pid)
