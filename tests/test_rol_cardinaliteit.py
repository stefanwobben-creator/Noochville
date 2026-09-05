"""De cardinaliteitswet: hoeveel vervullers een rol heeft, bepaalt wie het project krijgt.

Een project stond standaard onbemand zodra je het aan een rol hing — ook als die rol gewoon vervuld
was. Dat is een stille nul: het scherm zegt "niemand", terwijl de eigenaar eenduidig is.

DE DEFINITIE VAN "VERVULLER" IS DE HELE WET. `mens_vervullers` telt alleen mensen, en onder díe
definitie heeft 14 van de 29 rollen op productie "geen vervuller" — terwijl 11 daarvan gewoon
AI-vervuld zijn. Gemeten scheelt dat **135 tegen 9** projecten die de auto-toewijs-tak raken. Een
vervuller is dus een mens ÓF een persona, en `st.assign.fillers_of` is de bron die beide kent.
"""
from __future__ import annotations

from nooch_village import cockpit2

ROLE = "mother_earth__nooch__website_developer"
CIRCLE = "mother_earth__nooch"


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


def _vul(st, rol, *personen):
    """Zet precies deze mensen op de rol; haal bestaande vervullers eraf."""
    # Argumentvolgorde is (role_id, filler_type, filler_id) — omgedraaid raden kostte een run.
    rec = st.records.get(rol)
    for f in list(st.assign.fillers_of(rol, record=rec)):
        st.assign.unassign(rol, f.type, f.id)
    for pid in personen:
        assert st.assign.assign(rol, "person", pid), pid


def _personen(st, n=2):
    return [p.id for p in st.people.all()[:n]]


# ── de drie takken van de wet ────────────────────────────────────────────────
def test_nul_vervullers_mag_onbemand(tmp_path):
    """HET ENIGE GEVAL WAARIN ONBEMAND EERLIJK IS: er is werkelijk niemand om het aan te geven.
    Deze tak blijft in de code voor rollen die later leeglopen, ook al is hij op Nooch zeldzaam
    (3 van de 29 rollen)."""
    dd, st = _st(tmp_path)
    _vul(st, ROLE)
    n, soort, wie = cockpit2.vervulling(cockpit2._Stores(dd), ROLE)
    assert (n, soort, wie) == (0, "", "")
    cockpit2.dispatch(dd, "proj_add", {"owner": [ROLE], "scope": ["Kaal"], "trekker": [""],
                                       "done_when": ["af"], "next": ["/"]}, username="guest")
    p = cockpit2._Stores(dd).projects.all()[0]
    assert not p.get("person") and not p.get("agent")


def test_een_vervuller_wijst_automatisch_toe(tmp_path):
    """Onbemand laten is hier een STILLE NUL: de eigenaar is eenduidig, en hem niet invullen
    suggereert dat er iets te kiezen valt. Gemeten: 135 van de 140 onbemande projecten op
    productie vallen in deze tak."""
    dd, st = _st(tmp_path)
    (mens,) = _personen(st, 1)
    _vul(st, ROLE, mens)
    _, msg = cockpit2.dispatch(dd, "proj_add", {"owner": [ROLE], "scope": ["Eén"], "trekker": [""],
                                                "done_when": ["af"], "next": ["/"]},
                               username="guest")
    assert not cockpit2.is_weigering(msg), msg
    p = cockpit2._Stores(dd).projects.all()[0]
    assert p["person"] == mens and not p.get("agent")


def test_twee_vervullers_dwingen_een_keuze_af(tmp_path):
    """Een stille gok tussen twee mensen is erger dan geen keuze, want niemand ziet dat er gegokt
    is. De weigering draagt een ✗ zodat `is_weigering` hem herkent en de client hem nooit als
    succes rendert."""
    dd, st = _st(tmp_path)
    a, b = _personen(st, 2)
    _vul(st, ROLE, a, b)
    _, msg = cockpit2.dispatch(dd, "proj_add", {"owner": [ROLE], "scope": ["Twee"], "trekker": [""],
                                                "done_when": ["af"], "next": ["/"]},
                               username="guest")
    assert cockpit2.is_weigering(msg), msg
    assert "pick an owner" in msg
    assert cockpit2._Stores(dd).projects.all() == []        # niet stil op het bord beland


def test_een_expliciete_keuze_wint_altijd(tmp_path):
    """De wet vult een GAT, hij overrulet geen mens — ook niet bij twee vervullers."""
    dd, st = _st(tmp_path)
    a, b = _personen(st, 2)
    _vul(st, ROLE, a, b)
    _, msg = cockpit2.dispatch(dd, "proj_add", {"owner": [ROLE], "scope": ["Gekozen"],
                                                "trekker": [f"person:{b}"], "done_when": ["af"],
                                                "next": ["/"]}, username="guest")
    assert not cockpit2.is_weigering(msg), msg
    assert cockpit2._Stores(dd).projects.all()[0]["person"] == b


# ── een vervuller is een mens ÓF een persona ─────────────────────────────────
def test_een_ai_vervulde_rol_telt_als_vervuld(tmp_path):
    """Dit is waar de hele meting op draaide: onder de mens-alleen-definitie zou deze rol "leeg"
    heten en het project onbemand blijven, terwijl er gewoon een eigenaar is."""
    dd, st = _st(tmp_path)
    _vul(st, ROLE)
    # De bootstrap heeft geen persona's; een synthetische id volstaat, want de wet gaat over het
    # AANTAL en de SOORT vervullers, niet over het bestaan van de persona erachter.
    pid_persona = "harry_hemp_persona"
    assert st.assign.assign(ROLE, "persona", pid_persona)
    st2 = cockpit2._Stores(dd)
    n, soort, wie = cockpit2.vervulling(st2, ROLE)
    assert (n, soort, wie) == (1, "persona", pid_persona)
    assert cockpit2.mens_vervullers(st2, ROLE) == []      # de mens-telling zegt hier "geen"
    cockpit2.dispatch(dd, "proj_add", {"owner": [ROLE], "scope": ["AI"], "trekker": [""],
                                       "done_when": ["af"], "next": ["/"]}, username="guest")
    p = cockpit2._Stores(dd).projects.all()[0]
    assert p["agent"] == pid_persona and not p.get("person")


# ── één wet, meerdere consumenten ────────────────────────────────────────────
def test_de_owner_wissel_leest_dezelfde_wet(tmp_path):
    """`_resync_trekker` had zijn eigen kopie van "precies één filler → daarheen". Twee plekken die
    hetzelfde beslissen lopen uiteen zodra er één verandert."""
    dd, st = _st(tmp_path)
    a, b = _personen(st, 2)
    ROLE2 = "mother_earth__nooch__brand_visual_designer"
    _vul(st, ROLE, a)
    _vul(st, ROLE2, b)
    cockpit2.dispatch(dd, "proj_add", {"owner": [ROLE], "scope": ["Verhuist"], "trekker": [""],
                                       "done_when": ["af"], "next": ["/"]}, username="guest")
    pid = cockpit2._Stores(dd).projects.all()[0]["id"]
    assert cockpit2._Stores(dd).projects.get(pid)["person"] == a
    cockpit2.dispatch(dd, "proj_setowner", {"pid": [pid], "owner": [ROLE2], "next": ["/"]},
                      username="guest")
    assert cockpit2._Stores(dd).projects.get(pid)["person"] == b


def test_bij_meerdere_vervullers_blijft_de_wissel_leeg_en_weigert_niet(tmp_path):
    """Een owner-wissel is een NA-correctie, geen intake: de mens staat daar niet voor een
    formulier, dus daar is leeg het juiste antwoord in plaats van een weigering."""
    dd, st = _st(tmp_path)
    # DRIE mensen: `a` mag GEEN vervuller van ROLE2 zijn, anders is de trekker niet verweesd en
    # laat `_resync_trekker` hem terecht staan — dan toetst deze test niets.
    a, b, cc = _personen(st, 3)
    ROLE2 = "mother_earth__nooch__brand_visual_designer"
    _vul(st, ROLE, a)
    _vul(st, ROLE2, b, cc)
    cockpit2.dispatch(dd, "proj_add", {"owner": [ROLE], "scope": ["Verhuist"], "trekker": [""],
                                       "done_when": ["af"], "next": ["/"]}, username="guest")
    pid = cockpit2._Stores(dd).projects.all()[0]["id"]
    _, msg = cockpit2.dispatch(dd, "proj_setowner", {"pid": [pid], "owner": [ROLE2], "next": ["/"]},
                               username="guest")
    assert not cockpit2.is_weigering(msg), msg
    p = cockpit2._Stores(dd).projects.get(pid)
    assert not p.get("person") and not p.get("agent")


def test_individuele_actie_valt_buiten_de_wet(tmp_path):
    """Een Individueel Initiatief hangt niet aan een rol, dus er valt geen cardinaliteit te lezen."""
    dd, st = _st(tmp_path)
    n, soort, wie = cockpit2.vervulling(cockpit2._Stores(dd), f"{cockpit2._II_PREFIX}{CIRCLE}")
    assert (n, soort, wie) == (0, "", "")


def test_onbekende_rol_geeft_nul_en_valt_niet_om(tmp_path):
    dd, st = _st(tmp_path)
    assert cockpit2.vervulling(cockpit2._Stores(dd), "bestaat_niet") == (0, "", "")
    assert cockpit2.vervulling(cockpit2._Stores(dd), "") == (0, "", "")
