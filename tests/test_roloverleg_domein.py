"""Een domein toevoegen via het overleg, en dan sluiten (28 september 2026).

DE MELDING: "domein toevoegen werkt niet, verwijderen wel. Na de poging staat de rol nog op No
domain, en de agenda is volledig leeg — geen open, consented of objected item."

WAT ER AAN DE HAND WAS, twee dingen tegelijk, allebei uitgevoerd en niet geredeneerd:

1. SLUITEN GOOIDE ALLES WEG. `_act_rov2_end` haalde élk resterend agendapunt van de agenda, met
   als reden dat de "Governance meeting"-knop anders groen blijft hangen. Die knop bestaat niet:
   `overleg_items` geeft het roloverleg een gewone link en alleen het WERKoverleg een live-staat.
   Wie dus een domein toevoegde en daarna op de opvallendste groene knop drukte — "Close meeting"
   staat in de vaste voet, "Adopt proposal" bij het voorstel — zag zijn werk verdwijnen zonder
   spoor. Dat verklaart de lege agenda precies, en waarom "verwijderen wel werkte": dat was een
   ronde die wél tot consent kwam.
2. DE ACCOUNTABILITY-EIS BLOKKEERDE IETS ANDERS DAN ZICHZELF. `_rov_hard` keek naar de STAND van
   de rol ("a role needs at least one accountability") en niet naar de WIJZIGING. Een rol met nul
   accountabilities was daardoor helemaal niet meer te amenderen — ook niet om er een DOMEIN aan
   te hangen, met een foutmelding die over iets anders gaat dan wat je voorstelt.

Deze toets rijdt de hele keten door de echte dispatch-takken: toevoegen → consent → sluiten, en de
variant die de melding beschrijft: toevoegen → meteen sluiten.
"""
from __future__ import annotations

import dataclasses
import inspect
import re

from nooch_village import cockpit2

CIRKEL = "mother_earth__nooch"
MET_ACCS = "mother_earth__nooch__community_and_email"
ZONDER_ACCS = "mother_earth__nooch__copywriter"


def _dorp(tmp_path):
    """De cirkel, een Circle Lead, en een rol ZONDER accountabilities — zoals ze voorkomen."""
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    lead = st.people.add("Lead", "lead@test.nl")
    st.assign.assign(f"{CIRKEL}__circle_lead", "person", lead.id)
    basis = st.records.get(MET_ACCS)
    st.records.put(dataclasses.replace(
        basis, id=ZONDER_ACCS,
        definition=dataclasses.replace(basis.definition, name="Copywriter",
                                       domains=[], accountabilities=[])))
    c = st.records.get(CIRKEL)
    c.members = list(c.members) + [ZONDER_ACCS]
    st.records.put(c)
    return dd, cockpit2._Stores(dd)


def _doe(st, dd, actie, **velden):
    velden = {"csrf": "T", "circle": CIRKEL, **velden}
    ctx = cockpit2._Ctx(st=st, g=lambda k, d="": velden.get(k, d), nxt="/roloverleg2",
                        form=velden, username="lead@test.nl", action=actie, data_dir=dd)
    return cockpit2.ACTIONS[actie](ctx)[1]


def _punt(st, titel):
    return next(i for i in st.agenda.all() if i["title"] == titel)


# ══ 1. De keten die de melding beschrijft ════════════════════════════════════
def test_domein_toevoegen_consent_sluiten(tmp_path):
    """DE TOETS DIE ERTOE DOET: de hele weg, via de echte takken, met de records als uitkomst."""
    dd, st = _dorp(tmp_path)
    _doe(st, dd, "rov2_add", naam="Community and Email")
    iid = _punt(st, "Community and Email")["id"]
    _doe(st, dd, "rov2_dom_add", iid=iid, text="Tone of voice")
    assert st.agenda.get(iid)["change"]["add_domains"] == ["Tone of voice"]
    assert "✓" in _doe(st, dd, "rov2_consent", iid=iid)
    _doe(st, dd, "rov2_end")
    assert cockpit2._Stores(dd).records.get(MET_ACCS).definition.domains == ["Tone of voice"]


def test_toevoegen_op_een_rol_zonder_accountabilities(tmp_path):
    """HET TWEEDE HALF VAN DE BUG. De rol bestaat al zonder accountabilities; een voorstel dat
    daar niets aan verandert, hoort niet op die stand te stranden."""
    dd, st = _dorp(tmp_path)
    _doe(st, dd, "rov2_add", naam="Copywriter")
    iid = _punt(st, "Copywriter")["id"]
    _doe(st, dd, "rov2_dom_add", iid=iid, text="Tone of voice")
    assert "✓" in _doe(st, dd, "rov2_consent", iid=iid), "consent werd geblokkeerd"
    _doe(st, dd, "rov2_end")
    assert cockpit2._Stores(dd).records.get(ZONDER_ACCS).definition.domains == ["Tone of voice"]


def test_verwijderen_blijft_werken(tmp_path):
    """De kant die het al deed, als tegenproef: deze stap repareert de ene zonder de andere te
    breken."""
    dd, st = _dorp(tmp_path)
    rec = st.records.get(MET_ACCS)
    rec.definition.domains = ["Tone of voice"]
    st.records.put(rec)
    st = cockpit2._Stores(dd)
    _doe(st, dd, "rov2_add", naam="Community and Email")
    iid = _punt(st, "Community and Email")["id"]
    _doe(st, dd, "rov2_dom_remove", iid=iid, text="Tone of voice")
    _doe(st, dd, "rov2_consent", iid=iid)
    _doe(st, dd, "rov2_end")
    assert cockpit2._Stores(dd).records.get(MET_ACCS).definition.domains == []


# ══ 2. Sluiten gooit niets weg ═══════════════════════════════════════════════
def test_sluiten_zonder_consent_laat_het_voorstel_staan(tmp_path):
    """DE MELDING, LETTERLIJK: domein toevoegen en dan op de groene knop in de voet drukken. Er
    wordt niets geschreven — dat klopt, er is niets aangenomen — maar het voorstel hoort er nog te
    liggen, mét de bewerkingen erin."""
    dd, st = _dorp(tmp_path)
    _doe(st, dd, "rov2_add", naam="Community and Email")
    iid = _punt(st, "Community and Email")["id"]
    _doe(st, dd, "rov2_dom_add", iid=iid, text="Tone of voice")
    melding = _doe(st, dd, "rov2_end")

    verse = cockpit2._Stores(dd)
    assert verse.records.get(MET_ACCS).definition.domains == [], "niets aangenomen, niets geschreven"
    over = verse.agenda.get(iid)
    assert over is not None, "het voorstel is van de agenda verdwenen"
    assert over["change"]["add_domains"] == ["Tone of voice"], "de bewerking is weg"
    assert over in verse.agenda.open(), "het komt het volgende overleg niet terug"
    assert "blijven op de agenda" in melding


def test_en_het_volgende_overleg_kan_hem_alsnog_aannemen(tmp_path):
    """De keten tot het eind: wat blijft staan, moet ook echt weer op te pakken zijn."""
    dd, st = _dorp(tmp_path)
    _doe(st, dd, "rov2_add", naam="Community and Email")
    iid = _punt(st, "Community and Email")["id"]
    _doe(st, dd, "rov2_dom_add", iid=iid, text="Tone of voice")
    _doe(st, dd, "rov2_end")

    st2 = cockpit2._Stores(dd)
    _doe(st2, dd, "rov2_consent", iid=iid)
    _doe(st2, dd, "rov2_end")
    assert cockpit2._Stores(dd).records.get(MET_ACCS).definition.domains == ["Tone of voice"]


def test_een_geblokkeerd_voorstel_wordt_zichtbaar_geweigerd(tmp_path):
    """`apply_consented` belooft: "gate blokkeert → blijft staan als schadelijk met reden". De
    overleg-variant sloeg zo'n punt stil over en liet hem op `consented` staan; het sluiten haalde
    hem daarna weg. Twee stappen verder was er geen voorstel meer en geen reden."""
    dd, st = _dorp(tmp_path)
    _doe(st, dd, "rov2_add", naam="Community and Email")
    iid = _punt(st, "Community and Email")["id"]
    _doe(st, dd, "rov2_consent", iid=iid)
    # Pas ná consent onbruikbaar maken: alle accountabilities eruit. Dat is precies het geval dat
    # `_rov_hard` wél hoort te blokkeren — het voorstel maakt de rol leeg.
    for a in list(st.records.get(MET_ACCS).definition.accountabilities):
        _doe(st, dd, "rov2_acc_remove", iid=iid, text=a)
    _doe(st, dd, "rov2_end")

    verse = cockpit2._Stores(dd)
    over = verse.agenda.get(iid)
    assert over is not None and over["status"] == "objected"
    assert over in verse.agenda.open(), "een geweigerd punt hoort terug te komen"


def test_sluiten_haalt_wel_weg_wat_het_schreef(tmp_path):
    """De andere kant van dezelfde regel: een aangenomen voorstel is klaar en hoort niet als
    eeuwig agendapunt te blijven liggen."""
    dd, st = _dorp(tmp_path)
    _doe(st, dd, "rov2_add", naam="Community and Email")
    iid = _punt(st, "Community and Email")["id"]
    _doe(st, dd, "rov2_dom_add", iid=iid, text="Tone of voice")
    _doe(st, dd, "rov2_consent", iid=iid)
    _doe(st, dd, "rov2_end")
    assert cockpit2._Stores(dd).agenda.get(iid) is None


def test_de_reden_om_weg_te_gooien_bestond_niet():
    """De rechtvaardiging in de code ("anders blijft de knop groen hangen") beschreef een
    schermeffect dat er niet is. Vastgelegd, zodat hij niet als vanzelfsprekend terugkomt."""
    from nooch_village.cockpit2_util import overleg_items
    h = overleg_items(CIRKEL, werk_open=True)
    rol_knop = h.split("/roloverleg2")[1]
    assert "c2-overleg--live" not in rol_knop, "het roloverleg heeft nu wél een live-staat"
    kaal = re.sub(r'"""(?:.|\n)*?"""', "", inspect.getsource(overleg_items))
    assert "agenda" not in kaal, "de knop leest nu tóch de agenda"


# ══ 3. De accountability-eis raakt alleen wat hij bedoelt ════════════════════
def _hard(st, iid):
    from nooch_village.views.roloverleg import _rov_hard
    return _rov_hard(st, st.agenda.get(iid))


def test_een_nieuwe_rol_moet_nog_steeds_een_accountability_hebben(tmp_path):
    """Die eis blijft: een rol hoort niet leeg geboren te worden."""
    dd, st = _dorp(tmp_path)
    _doe(st, dd, "rov2_add", naam="Gloednieuwe rol")
    iid = _punt(st, "Gloednieuwe rol")["id"]
    assert _hard(st, iid), "een lege nieuwe rol mag gewoon door"
    assert "⛔" in _doe(st, dd, "rov2_consent", iid=iid)


def test_de_laatste_accountability_weghalen_blijft_geblokkeerd(tmp_path):
    """De tegenproef op de versoepeling: een voorstel dat de rol léég maakt, wordt wél gestopt."""
    dd, st = _dorp(tmp_path)
    _doe(st, dd, "rov2_add", naam="Community and Email")
    iid = _punt(st, "Community and Email")["id"]
    for a in list(st.records.get(MET_ACCS).definition.accountabilities):
        _doe(st, dd, "rov2_acc_remove", iid=iid, text=a)
    assert _hard(st, iid)


def test_een_domein_op_een_lege_rol_wordt_niet_geblokkeerd(tmp_path):
    """En de versoepeling zelf: het voorstel verslechtert niets, dus de stand van de rol houdt het
    niet tegen."""
    dd, st = _dorp(tmp_path)
    _doe(st, dd, "rov2_add", naam="Copywriter")
    iid = _punt(st, "Copywriter")["id"]
    _doe(st, dd, "rov2_dom_add", iid=iid, text="Tone of voice")
    assert _hard(st, iid) == []


# ══ 4. Twee groene knoppen zijn er één te veel ═══════════════════════════════
def test_aannemen_is_de_hoofdactie_en_sluiten_niet(tmp_path):
    """Waar de klik verkeerd landde. "Close meeting" stond als `btn ok` in de vaste voet en was
    daarmee de opvallendste groene knop op het scherm, terwijl "Adopt proposal" de handeling is
    waar het overleg om draait. Zelfde meting als bij "Move page" naast "Edit page"."""
    from nooch_village.views.roloverleg import render_roloverleg2
    dd, st = _dorp(tmp_path)
    _doe(st, dd, "rov2_add", naam="Community and Email")
    h = render_roloverleg2(st, CIRKEL, csrf_token="TOK")
    sluit = h.split("value='rov2_end'")[0]
    assert "btn ghost" in sluit.rsplit("<button", 1)[1], "sluiten is nog een primaire knop"
    neem = h.split("value='rov2_consent'")[0]
    assert "btn ok" in neem.rsplit("<button", 1)[1], "aannemen is niet meer de hoofdactie"


def test_de_bevestiging_zegt_wat_er_met_de_rest_gebeurt(tmp_path):
    """Het deel dat je niet verwachtte, was het deel dat niet genoemd werd."""
    from nooch_village.views.roloverleg import render_roloverleg2
    dd, st = _dorp(tmp_path)
    _doe(st, dd, "rov2_add", naam="Community and Email")
    h = render_roloverleg2(st, CIRKEL, csrf_token="TOK")
    bevestiging = h.split("data-confirm='")[1].split("'")[0]
    assert "stay on the agenda" in bevestiging
    assert "nothing will be written" in bevestiging
