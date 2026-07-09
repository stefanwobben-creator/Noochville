"""SCOPE — Owner/trekker: label dat klopt, dropdown die past.

De trekker mag alleen een filler van de owner-ROL zijn (skills/uitvoering komen van de owner-rol,
niet van de trekker). De owner-dropdown is gescoped op de cirkel van het project en sluit cirkels én
Holacracy-kernrollen uit. Een owner-wissel laat nooit een verweesde trekker staan.
"""
from __future__ import annotations
import re

from nooch_village import cockpit2
from nooch_village.views.projects import _owner_options, _trekker_options, _is_core_role

CIRCLE = "mother_earth__nooch"
WEBDEV = "mother_earth__nooch__website_developer"          # heeft bootstrap-person-fillers
MARKETING = "mother_earth__nooch__marketing_lead"
BRANDDES = "mother_earth__nooch__brand_visual_designer"
FACILITATOR = "mother_earth__nooch__facilitator"          # kernrol in dezelfde cirkel
# rollen ZONDER bootstrap-filler (in dezelfde cirkel, niet-core) — zo controleer ik de fillers zelf:
FACTORY = "mother_earth__nooch__factory_development_specialist"
INMATE = "mother_earth__nooch__inmate_in_residence"


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


def _opts(select_name, html):
    m = re.search(rf"<select name='{select_name}'>(.*?)</select>", html, re.DOTALL)
    return m.group(1) if m else ""


# a. trekker-dropdown toont alleen fillers van de owner-rol
def test_a_trekker_alleen_fillers_van_owner(tmp_path):
    dd, st = _st(tmp_path)
    codie = st.personas.add("Codie")
    buiten = st.personas.add("Buitenstaander")               # geen filler
    st.assign.assign(WEBDEV, "persona", codie.id)
    opts = _trekker_options(cockpit2._Stores(dd), WEBDEV)
    assert f"persona:{codie.id}" in opts                      # filler aanwezig
    assert f"persona:{buiten.id}" not in opts                # niet-filler afwezig
    assert "geen trekker" in opts


# b. owner zonder fillers → alleen "geen trekker"
def test_b_owner_zonder_fillers(tmp_path):
    dd, st = _st(tmp_path)
    st.personas.add("Losse AI")                              # bestaat, maar nergens toegewezen
    opts = _trekker_options(cockpit2._Stores(dd), FACTORY)   # rol zonder bootstrap-filler
    assert opts.count("<option") == 1 and "geen trekker" in opts


# c. proj_setowner → verweesde trekker wordt gereset; een trekker die de nieuwe rol wél bezet blijft
def test_c_setowner_reset_verweesde_trekker(tmp_path):
    dd, st = _st(tmp_path)
    codie = st.personas.add("Codie"); marky = st.personas.add("Marky")
    st.assign.assign(FACTORY, "persona", codie.id)           # FACTORY: enige filler = Codie
    st.assign.assign(INMATE, "persona", marky.id)            # INMATE: enige filler = Marky
    pid = st.projects.create(FACTORY, "Doel", "human", agent=codie.id)
    # verplaats naar INMATE: Codie bezet die rol niet → reset naar de enige filler (Marky)
    cockpit2.dispatch(dd, "proj_setowner", {"pid": [pid], "owner": [INMATE], "next": ["/"]}, username="guest")
    p = cockpit2._Stores(dd).projects.get(pid)
    assert p["owner"] == INMATE and p.get("agent") == marky.id and not p.get("person")

    # nu naar een rol die de HUIDIGE trekker (Marky) wél bezet — verplaats INMATE→INMATE-achtig:
    # geef FACTORY ook Marky als filler en verplaats terug → Marky bezet FACTORY → blijft staan
    st.assign.assign(FACTORY, "persona", marky.id)
    cockpit2.dispatch(dd, "proj_setowner", {"pid": [pid], "owner": [FACTORY], "next": ["/"]}, username="guest")
    p2 = cockpit2._Stores(dd).projects.get(pid)
    assert p2["owner"] == FACTORY and p2.get("agent") == marky.id    # bezet de rol → blijft staan


# c2. owner-wissel naar een rol zonder fillers → trekker leeg (nooit verweesd)
def test_c2_setowner_geen_fillers_wist_trekker(tmp_path):
    dd, st = _st(tmp_path)
    codie = st.personas.add("Codie")
    st.assign.assign(FACTORY, "persona", codie.id)
    pid = st.projects.create(FACTORY, "Doel", "human", agent=codie.id)
    # INMATE heeft geen filler → trekker moet leeg (niet verweesd)
    cockpit2.dispatch(dd, "proj_setowner", {"pid": [pid], "owner": [INMATE], "next": ["/"]}, username="guest")
    p = cockpit2._Stores(dd).projects.get(pid)
    assert p["owner"] == INMATE and not p.get("agent") and not p.get("person")


# d. owner-dropdown toont alleen rollen uit de cirkel van het bord
def test_d_owner_dropdown_gescoped_op_cirkel(tmp_path):
    dd, st = _st(tmp_path)
    opts = _owner_options(cockpit2._Stores(dd), sel_owner=WEBDEV, circle=CIRCLE)
    assert f"value='{WEBDEV}'" in opts and f"value='{MARKETING}'" in opts   # eigen cirkel
    assert "value='harry_hemp'" not in opts                                 # andere cirkel (noochville)
    assert "value='website_watcher'" not in opts                            # andere cirkel


# e. cirkels blijven uitgesloten; dangling-owner-optie blijft
def test_e_cirkels_uit_dangling_blijft(tmp_path):
    dd, st = _st(tmp_path)
    opts = _owner_options(cockpit2._Stores(dd), sel_owner=WEBDEV, circle=CIRCLE)
    assert f"value='{CIRCLE}'" not in opts and "value='mother_earth'" not in opts   # geen cirkels
    # dangling owner (bestaat niet meer) → expliciete ⚠-optie, geselecteerd
    dangling = _owner_options(cockpit2._Stores(dd), sel_owner="rol_weg_xyz", circle=None)
    assert "rol_weg_xyz" in dangling and "bestaat niet meer" in dangling and "selected" in dangling


# f. kernrol (facilitator) niet in de dropdown
def test_f_kernrol_niet_in_dropdown(tmp_path):
    dd, st = _st(tmp_path)
    opts = _owner_options(cockpit2._Stores(dd), circle=CIRCLE)
    assert FACILITATOR not in opts
    assert f"{CIRCLE}__secretary" not in opts and f"{CIRCLE}__circle_lead" not in opts
    assert _is_core_role(FACILITATOR) and _is_core_role("facilitator")
    assert not _is_core_role(WEBDEV) and not _is_core_role(MARKETING)


# g. verweesde trekker (bestaand project) → geen crash bij render, reset bij de volgende owner-wissel
def test_g_verweesde_trekker_geen_crash_dan_reset(tmp_path):
    dd, st = _st(tmp_path)
    codie = st.personas.add("Codie")                         # NIET toegewezen aan FACTORY → verweesd
    pid = st.projects.create(FACTORY, "Doel", "human", agent=codie.id)
    # geen crash in beide modi; read-only toont de (verweesde) trekker-naam nog
    ro = cockpit2.render_project(cockpit2._Stores(dd), pid, csrf_token="", fragment=True)
    assert "Codie" in ro                                     # read-only weergave toont de naam
    rw = cockpit2.render_project(cockpit2._Stores(dd), pid, csrf_token="t", fragment=True)
    assert f"persona:{codie.id}" not in _opts("trekker", rw) # rw-dropdown: geen ongeldige (verweesde) optie
    # reset bij de volgende owner-wissel: naar een rol met precies één filler
    marky = st.personas.add("Marky"); st.assign.assign(INMATE, "persona", marky.id)
    cockpit2.dispatch(dd, "proj_setowner", {"pid": [pid], "owner": [INMATE], "next": ["/"]}, username="guest")
    p = cockpit2._Stores(dd).projects.get(pid)
    assert p.get("agent") == marky.id                        # verweesde Codie is opgeruimd
