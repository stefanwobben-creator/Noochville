"""Een rol moet te bemensen zijn vanaf de rol, en een mislukte toewijzing moet dat zeggen.

Twee klachten, één regel eronder. Stefan maakte de rol `compliance` aan, stond op de rolpagina,
zag onder ROLE FILLERS 'Not filled yet.' en geen enkele knop — en concludeerde dat de rol niet te
bemensen was. De enige ingang naar het vervullers-scherm was een icoon van 26 px op de Roles-tab
van de OUDERCIRKEL. Het scherm zelf werkte; het was alleen niet te vinden vanaf de plek waar je
staat als je aan een rol denkt.

En kwam je er wél, dan viel de toewijzing stil door als de keuzelijst op '— pick person —' bleef
staan: `msg` bleef leeg, de redirect droeg geen melding, en de mens zag exact hetzelfde scherm
terug. Zelfde patroon als bij `_act_role_unassign`, die "✓ removed" meldde ook als er niets was
verwijderd. Dat is de fout die deze sessie steeds terugkomt: een actie mag zijn uitkomst niet
impliciet laten aflezen, en mag nooit beweren wat hij niet heeft gedaan.
"""
from __future__ import annotations

from nooch_village import cockpit2

ROL = "mother_earth__nooch__website_developer"
LEEG = "mother_earth__nooch__factory_development_specialist"   # onbemand in de fixture
CIRKEL = "mother_earth__nooch"


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return cockpit2._Stores(dd)


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


# ── De ingang staat waar je hem zoekt ────────────────────────────────────────────────────────

def test_rolpagina_heeft_beheer_ingang(tmp_path):
    st = _st(tmp_path)
    page = cockpit2.render_node(st, LEEG, "overview", csrf_token="t")
    assert "Role Fillers" in page and "Not filled yet." in page
    # Zelfde control, zelfde URL, zelfde modal-mechaniek als de rij op de cirkelpagina.
    assert f"/rolefillers?role={LEEG}" in page
    assert "manage-ico js-modal" in page and "data-href" in page


def test_rolpagina_zonder_token_geen_beheer(tmp_path):
    """Pariteit met `_role_row`: geen csrf-token = geen beheer-affordance."""
    st = _st(tmp_path)
    page = cockpit2.render_node(st, LEEG, "overview")
    assert "Role Fillers" in page                      # het blok blijft leesbaar
    assert "/rolefillers?role=" not in page and "manage-ico" not in page


def test_cirkelpagina_houdt_zijn_icoon(tmp_path):
    """De extractie naar één helper mag de bestaande ingang niet stilletjes weghalen."""
    st = _st(tmp_path)
    page = cockpit2.render_node(st, CIRKEL, "roles", csrf_token="t")
    assert "manage-ico js-modal" in page
    assert f"/rolefillers?role={LEEG}" in page


def test_cirkel_overview_krijgt_geen_vervullersblok(tmp_path):
    """Een cirkel wordt niet bemenst; het blok hoort daar niet te verschijnen."""
    st = _st(tmp_path)
    page = cockpit2.render_node(st, CIRKEL, "overview", csrf_token="t")
    assert "Role Fillers" not in page


# ── De uitkomst wordt gemeld, ook als hij nee is ─────────────────────────────────────────────

def test_toewijzen_zonder_keuze_zegt_nee(tmp_path):
    dd = _dd(tmp_path)
    _, msg = cockpit2.dispatch(dd, "role_assign",
                               {"role": [LEEG], "filler": [""], "next": ["/"]}, username="guest")
    assert msg, "een lege melding is precies de stilte die dit moest oplossen"
    assert cockpit2.is_weigering(msg), f"moet als weigering (ok=0) reizen, kreeg: {msg!r}"
    assert cockpit2._Stores(dd).assign.fillers_of(LEEG) == []


def test_toewijzen_met_persoon_meldt_succes(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    lotte = st.people.by_name("Lotte Mulder")
    _, msg = cockpit2.dispatch(dd, "role_assign",
                               {"role": [LEEG], "filler": [f"person:{lotte.id}"], "next": ["/"]},
                               username="guest")
    assert not cockpit2.is_weigering(msg) and msg.startswith("✓")
    assert any(f.id == lotte.id for f in cockpit2._Stores(dd).assign.fillers_of(LEEG))


def test_verwijderen_van_niet_vervuller_zegt_nee(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    lotte = st.people.by_name("Lotte Mulder")
    _, msg = cockpit2.dispatch(dd, "role_unassign",
                               {"role": [LEEG], "filler": [f"person:{lotte.id}"], "next": ["/"]},
                               username="guest")
    assert cockpit2.is_weigering(msg), f"niets verwijderd, dus geen '✓ removed'; kreeg: {msg!r}"


def test_verwijderen_van_echte_vervuller_meldt_succes(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    stefan = st.people.by_name("Stefan Wobben")
    cockpit2.dispatch(dd, "role_assign",
                      {"role": [LEEG], "filler": [f"person:{stefan.id}"], "next": ["/"]},
                      username="guest")
    _, msg = cockpit2.dispatch(dd, "role_unassign",
                               {"role": [LEEG], "filler": [f"person:{stefan.id}"], "next": ["/"]},
                               username="guest")
    assert msg.startswith("✓") and not cockpit2.is_weigering(msg)
    assert cockpit2._Stores(dd).assign.fillers_of(LEEG) == []


def test_bemensde_rol_houdt_de_ingang(tmp_path):
    """Ook een gevulde rol moet te beheren zijn — anders kun je niemand meer toevoegen."""
    st = _st(tmp_path)
    page = cockpit2.render_node(st, ROL, "overview", csrf_token="t")
    assert "Stefan Wobben" in page and f"/rolefillers?role={ROL}" in page
