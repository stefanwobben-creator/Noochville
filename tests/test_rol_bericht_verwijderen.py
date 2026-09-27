"""Een bericht van een rol is van wie de rol bekleedt — voor het opruimen (26 september 2026).

DE REGEL DIE HIER OMDRAAIT. `ChannelStore._eigen` liet bewerken en verwijderen alleen toe bij
`author.type in ("human","person")` en `author.id == door`, met als onderbouwing: "een bericht van
een ROL is van niemand, ook niet van de mens die de rol vervult". Dat klopt als EIGENDOMSvraag maar
niet als OPRUIMvraag — de capaciteit-waarschuwingen die via `signaal.stuur` bij een rol landen waren
daardoor voor niemand weg te halen, ook niet voor degene die ze moest lezen.

GEMETEN OP PRODUCTIE, 374 berichten met een niet-menselijke auteur:

    52   van een rol die IEMAND bekleedt   → worden hiermee opruimbaar
    188  van een bestaande maar onbemande rol → blijven staan, en terecht: er is geen bekleder
    134  van een `author.id` die helemaal geen rol is ('claims-checker', 'zelf', 'dialoog', …)
         → die kan een rol-check per definitie niet raken

ALLEEN VERWIJDEREN, NIET BEWERKEN. Een rol mag je het zwijgen opleggen; je mag haar geen andere
woorden in de mond leggen. `verwijder` geeft een `rol_check` mee, `bewerk` niet.

DE KOPPELING MENS ↔ ROL IS NIET NIEUW: `is_role_filler`, dezelfde helper waar `_role_gate` op
draait. Geen tweede mechanisme ernaast.
"""
from __future__ import annotations

import inspect

from nooch_village import channels, cockpit2
from nooch_village.views import messages as mv
from nooch_village.views.messages import _bericht

ROL = "mother_earth__nooch__creator_of_shoes"
ANDERE_ROL = "mother_earth__nooch__compliance"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    ik = st.people.add("Rol Bekleder", "bekleder@test.nl")
    ander = st.people.add("Iemand Anders", "anders@test.nl")
    st.assign.assign(ROL, "person", ik.id)
    return dd, st, ik, ander


def _kanaal(st, a: str, b: str) -> str:
    return channels.dm_kanaal(a, b)


def _rolbericht(st, kanaal: str, rol: str, tekst: str = "capaciteit bijna op") -> str:
    """Precies wat `signaal.stuur` schrijft: author_type='role', author_id=<rol-id>."""
    e = st.channels.post(kanaal, tekst, author_type="role", author_id=rol)
    return e["id"]


def _wis(st, dd, kanaal, item, email):
    c = cockpit2._Ctx(st=st, g=lambda k, d="": {"kanaal": kanaal, "item": item}.get(k, d),
                      nxt="/messages", form={}, username=email, action="msg_remove", data_dir=dd)
    return cockpit2.ACTIONS["msg_remove"](c)


def _bewerk(st, dd, kanaal, item, tekst, email):
    velden = {"kanaal": kanaal, "item": item, "tekst": tekst}
    c = cockpit2._Ctx(st=st, g=lambda k, d="": velden.get(k, d), nxt="/messages",
                      form=velden, username=email, action="msg_edit", data_dir=dd)
    return cockpit2.ACTIONS["msg_edit"](c)


# ══ 1. Het bestaande gedrag, ongewijzigd ═════════════════════════════════════
def test_je_eigen_bericht_kun_je_nog_steeds_weghalen(tmp_path):
    dd, st, ik, ander = _dorp(tmp_path)
    k = _kanaal(st, ik.id, ander.id)
    e = st.channels.post(k, "van mijzelf", author_type="human", author_id=ik.id)
    _nxt, msg = _wis(st, dd, k, e["id"], ik.email)
    assert msg.startswith("🗑")
    assert st.channels.trail(k) == []


def test_je_eigen_bericht_kun_je_nog_steeds_bewerken(tmp_path):
    """DE HELFT DIE NIET VERANDERT. Alleen de rol-tak is nieuw."""
    dd, st, ik, ander = _dorp(tmp_path)
    k = _kanaal(st, ik.id, ander.id)
    e = st.channels.post(k, "van mijzelf", author_type="human", author_id=ik.id)
    _nxt, msg = _bewerk(st, dd, k, e["id"], "bijgesteld", ik.email)
    assert msg.startswith("✓")
    assert st.channels.trail(k)[0]["text"] == "bijgesteld"


def test_andermans_mensbericht_blijft_verboden(tmp_path):
    dd, st, ik, ander = _dorp(tmp_path)
    k = _kanaal(st, ik.id, ander.id)
    e = st.channels.post(k, "van de ander", author_type="human", author_id=ander.id)
    _nxt, msg = _wis(st, dd, k, e["id"], ik.email)
    assert msg.startswith("✗")
    assert len(st.channels.trail(k)) == 1


# ══ 2. Een rol die je zelf bekleedt ══════════════════════════════════════════
def test_een_rolbericht_van_je_eigen_rol_mag_weg(tmp_path):
    """DE KERN. Dit is het geval dat eerder voor niemand weg te halen was."""
    dd, st, ik, ander = _dorp(tmp_path)
    k = _kanaal(st, ik.id, ander.id)
    item = _rolbericht(st, k, ROL)
    _nxt, msg = _wis(st, dd, k, item, ik.email)
    assert msg.startswith("🗑")
    assert st.channels.trail(k) == []


def test_het_werkt_in_elk_kanaal_niet_alleen_je_eigen_dm(tmp_path):
    """"in elk kanaal waar zo'n bericht verschijnt (niet beperkt tot je eigen DM)". Een
    rol-bericht landt via `signaal.stuur` in een DM, maar niets belooft dat dat zo blijft."""
    dd, st, ik, ander = _dorp(tmp_path)
    for k in (channels.circle_kanaal("mother_earth"),
              st.channels.maak_topic("Los kanaal", door=ik.id),
              _kanaal(st, ander.id, "compliance")):
        item = _rolbericht(st, k, ROL)
        _nxt, msg = _wis(cockpit2._Stores(dd), dd, k, item, ik.email)
        assert msg.startswith("🗑"), k
        assert cockpit2._Stores(dd).channels.trail(k) == [], k


def test_elke_rol_telt_niet_alleen_de_founder_rol(tmp_path):
    """"Dit geldt voor elke rol die iemand bekleedt, niet alleen de founder-rol.\""""
    dd, st, ik, ander = _dorp(tmp_path)
    st.assign.assign(ANDERE_ROL, "person", ik.id)
    k = _kanaal(st, ik.id, ander.id)
    item = _rolbericht(st, k, ANDERE_ROL)
    _nxt, msg = _wis(cockpit2._Stores(dd), dd, k, item, ik.email)
    assert msg.startswith("🗑")


def test_bewerken_van_een_rolbericht_blijft_verboden(tmp_path):
    """"Alleen verwijderen, niet bewerken." Anders staat er tekst onder de naam van een rol die
    de rol niet schreef — en dat is een ander soort fout dan een bericht te veel."""
    dd, st, ik, ander = _dorp(tmp_path)
    k = _kanaal(st, ik.id, ander.id)
    item = _rolbericht(st, k, ROL)
    _nxt, msg = _bewerk(st, dd, k, item, "iets anders", ik.email)
    assert msg.startswith("✗")
    assert st.channels.trail(k)[0]["text"] == "capaciteit bijna op"


# ══ 3. Een rol van iemand anders ═════════════════════════════════════════════
def test_een_rolbericht_van_andermans_rol_blijft_verboden(tmp_path):
    dd, st, ik, ander = _dorp(tmp_path)
    st.assign.assign(ANDERE_ROL, "person", ander.id)
    k = _kanaal(st, ik.id, ander.id)
    item = _rolbericht(st, k, ANDERE_ROL)
    _nxt, msg = _wis(cockpit2._Stores(dd), dd, k, item, ik.email)
    assert msg.startswith("✗")
    assert len(cockpit2._Stores(dd).channels.trail(k)) == 1


def test_een_onbemande_rol_is_van_niemand(tmp_path):
    """188 van de 374 rol-berichten op prod staan zo. Er is geen bekleder, dus er is niemand die
    hem mag weghalen — dat is de regel, niet een gat erin."""
    dd, st, ik, ander = _dorp(tmp_path)
    k = _kanaal(st, ik.id, ander.id)
    item = _rolbericht(st, k, ANDERE_ROL)
    for email in (ik.email, ander.email):
        _nxt, msg = _wis(cockpit2._Stores(dd), dd, k, item, email)
        assert msg.startswith("✗"), email
    assert len(cockpit2._Stores(dd).channels.trail(k)) == 1


def test_een_auteur_die_helemaal_geen_rol_is(tmp_path):
    """134 van de 374 op prod: 'claims-checker', 'zelf', 'dialoog'. Een rol-check kan die per
    definitie niet raken, en fail-closed betekent hier: niemand mag."""
    dd, st, ik, ander = _dorp(tmp_path)
    k = _kanaal(st, ik.id, ander.id)
    item = _rolbericht(st, k, "claims-checker")
    _nxt, msg = _wis(st, dd, k, item, ik.email)
    assert msg.startswith("✗")


def test_je_eigen_person_id_als_rol_id_telt_niet(tmp_path):
    """OOK 11 KEER OP PROD: `author.type='role'` met een PERSON-id erin. Dat is een datafout, geen
    rol — en `is_role_filler` op een person-id vindt niets. Fail-closed, en bewust niet stilzwijgend
    opgerekt tot "het lijkt op jou, dus het mag"."""
    dd, st, ik, ander = _dorp(tmp_path)
    k = _kanaal(st, ik.id, ander.id)
    item = _rolbericht(st, k, ik.id)
    _nxt, msg = _wis(st, dd, k, item, ik.email)
    assert msg.startswith("✗")


# ══ 4. De bezetting wisselt ══════════════════════════════════════════════════
def test_de_nieuwe_bezetter_mag_het_en_de_oude_niet_meer(tmp_path):
    """HET RECHT HANGT AAN DE ROL, NIET AAN DE PERSOON. Zou het bij het aanmaken worden
    vastgelegd, dan houdt een vertrokken mens zijn knop en krijgt zijn opvolger hem nooit."""
    dd, st, ik, ander = _dorp(tmp_path)
    k = _kanaal(st, ik.id, ander.id)
    item = _rolbericht(st, k, ROL)

    # vóór de wissel: de ander mag niet
    _nxt, msg = _wis(cockpit2._Stores(dd), dd, k, item, ander.email)
    assert msg.startswith("✗"), "de niet-bekleder mocht al"

    st.assign.unassign(ROL, "person", ik.id)
    st.assign.assign(ROL, "person", ander.id)

    # ná de wissel: de oude bekleder mag niet meer
    _nxt, msg = _wis(cockpit2._Stores(dd), dd, k, item, ik.email)
    assert msg.startswith("✗"), "de oude bekleder mag het nog"
    assert len(cockpit2._Stores(dd).channels.trail(k)) == 1

    # en de nieuwe wel
    _nxt, msg = _wis(cockpit2._Stores(dd), dd, k, item, ander.email)
    assert msg.startswith("🗑")
    assert cockpit2._Stores(dd).channels.trail(k) == []


def test_twee_bekleders_mogen_allebei(tmp_path):
    """`signaal.stuur` stuurt bij meerdere vervullers naar ALLEMAAL ("een dubbel bericht is hier
    minder erg dan een bericht dat niemand krijgt"). Dan hoort opruimen ook bij allemaal te
    liggen."""
    dd, st, ik, ander = _dorp(tmp_path)
    st.assign.assign(ROL, "person", ander.id)
    k = _kanaal(st, ik.id, ander.id)
    for email in (ik.email, ander.email):
        item = _rolbericht(st, k, ROL)
        _nxt, msg = _wis(cockpit2._Stores(dd), dd, k, item, email)
        assert msg.startswith("🗑"), email


# ══ 5. Scherm en actie stellen dezelfde vraag ════════════════════════════════
def _html(st, e, k, ik):
    return _bericht(st, e, kanaal=k, csrf_token="t", ik=ik)


def test_de_knop_staat_bij_een_rolbericht_van_je_eigen_rol(tmp_path):
    dd, st, ik, ander = _dorp(tmp_path)
    k = _kanaal(st, ik.id, ander.id)
    e = st.channels.post(k, "capaciteit bijna op", author_type="role", author_id=ROL)
    h = _html(st, e, k, ik.id)
    assert "value='msg_remove'" in h


def test_maar_de_bewerk_knop_niet(tmp_path):
    """Zou Edit er staan, dan is hij bovendien dood: `bewerk` krijgt geen `rol_check`."""
    dd, st, ik, ander = _dorp(tmp_path)
    k = _kanaal(st, ik.id, ander.id)
    e = st.channels.post(k, "capaciteit bijna op", author_type="role", author_id=ROL)
    h = _html(st, e, k, ik.id)
    assert "inline-edit" not in h and "editor-inline" not in h, h[:400]
    assert "<textarea" not in h


def test_bij_je_eigen_bericht_staan_ze_allebei(tmp_path):
    dd, st, ik, ander = _dorp(tmp_path)
    k = _kanaal(st, ik.id, ander.id)
    e = st.channels.post(k, "van mijzelf", author_type="human", author_id=ik.id)
    h = _html(st, e, k, ik.id)
    assert "value='msg_remove'" in h and "editor-inline" in h


def test_geen_knop_bij_een_rol_die_je_niet_bekleedt(tmp_path):
    dd, st, ik, ander = _dorp(tmp_path)
    k = _kanaal(st, ik.id, ander.id)
    e = st.channels.post(k, "van een andere rol", author_type="role", author_id=ANDERE_ROL)
    assert "value='msg_remove'" not in _html(st, e, k, ik.id)


def test_een_rolbericht_blijft_links_staan(tmp_path):
    """MAG IK DIT WEGHALEN ≠ IS DIT VAN MIJ. Het blijft andermans naam boven de tekst, dus het
    hoort niet als jouw bericht rechts in beeld te springen."""
    dd, st, ik, ander = _dorp(tmp_path)
    k = _kanaal(st, ik.id, ander.id)
    e = st.channels.post(k, "capaciteit bijna op", author_type="role", author_id=ROL)
    h = _html(st, e, k, ik.id)
    assert "msg-item--ik" not in h
    assert "msg-av" in h, "de avatarkolom hoort er te staan, zoals bij elk bericht van een ander"


def test_de_view_bouwt_de_poort_niet_na(tmp_path):
    """`reference, don't copy`. Dit is het verschil dat bij #610 pas live opviel: de server werd
    ruimer en de knop niet."""
    bron = inspect.getsource(mv)
    assert "mag_bericht_verwijderen" in bron
    assert "is_role_filler" not in bron, "de view stelt de rol-vraag zelf opnieuw"


def test_de_poort_hergebruikt_de_bestaande_mens_rol_koppeling():
    """"Zoek zelf uit hoe de bestaande koppeling mens ↔ rol al ergens wordt vastgesteld en
    hergebruik dat." Dat is `is_role_filler`, waar `_role_gate` ook op draait."""
    bron = inspect.getsource(cockpit2.mag_bericht_verwijderen)
    assert "is_role_filler(" in bron
    assert "fillers_of(" not in bron, "er wordt een tweede mechanisme naast gebouwd"


# ══ 6. De diepe poort ════════════════════════════════════════════════════════
def test_een_nagespeelde_post_loopt_op_de_store_stuk(tmp_path):
    """Een knop die niet gerenderd wordt houdt geen POST tegen. De store moet het zelf weigeren,
    ook als iemand het formulier naspeelt."""
    dd, st, ik, ander = _dorp(tmp_path)
    k = _kanaal(st, ik.id, ander.id)
    item = _rolbericht(st, k, ANDERE_ROL)
    assert st.channels.verwijder(k, item, door=ik.id) is False
    assert st.channels.verwijder(k, item, door=ik.id, rol_check=lambda _r: False) is False
    assert len(st.channels.trail(k)) == 1


def test_zonder_rol_check_verandert_er_niets(tmp_path):
    """DE DEFAULT IS HET OUDE GEDRAG. Elke aanroeper die geen `rol_check` meegeeft — `bewerk`
    voorop — houdt de mens-eigen regel."""
    dd, st, ik, ander = _dorp(tmp_path)
    k = _kanaal(st, ik.id, ander.id)
    item = _rolbericht(st, k, ROL)
    assert st.channels.verwijder(k, item, door=ik.id) is False
    assert len(st.channels.trail(k)) == 1


def test_het_predikaat_staat_op_een_plek():
    """`_eigen` en het scherm stellen dezelfde vraag; twee kopieën is hoe de goal-kanaal-bug zich
    vermenigvuldigde."""
    bron = inspect.getsource(channels)
    assert bron.count("def mag_wissen(") == 1
    eigen = inspect.getsource(channels.ChannelStore._eigen)
    assert "mag_wissen(" in eigen
    assert '"human"' not in eigen, "de auteurstypen staan hier weer apart uitgeschreven"


def test_een_kapotte_rol_check_sluit_de_deur(tmp_path):
    """Fail-closed: een poort die openvalt bij een exception is geen poort."""
    def ontploft(_rid):
        raise RuntimeError("assignments stuk")
    e = {"id": "x", "author": {"type": "role", "id": ROL}}
    assert channels.mag_wissen(e, "iemand", ontploft) is False


def test_een_lege_door_mag_niets():
    e = {"id": "x", "author": {"type": "human", "id": "a"}}
    assert channels.mag_wissen(e, "", lambda _r: True) is False
