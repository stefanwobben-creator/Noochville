"""Waar een signalering landt — de routering van `signaal.py`.

Dit bestand heette `test_fase10_notif_migratie.py` en toetste óók de eenmalige migratie van de 371
`NotifStore`-rijen. Die migratie is op 20 september 2026 op productie uitgevoerd (371 in, 371 uit,
0 kwijt) en haar code is met `NotifStore` meeverdwenen in B2. Wat blijft is de ROUTERING, en die
is permanent: élke melding in dit dorp loopt er langs, van een @-vermelding tot een puls-alarm.

De regel, in deze volgorde:

  1. doel is een PERSOON                            → die persoon
  2. doel is een ROL met precies één mens-vervuller → die mens (ook als de rol gearchiveerd is)
  3. doel is een ROL zonder mens-vervuller          → de Circle Lead van zijn cirkel
  3b. en heeft die er ook geen                      → de founder
  4. doel is een ROL met meerdere vervullers        → allemaal

Bij 4 is dubbel bezorgen beter dan niet bezorgen: dit is nieuw werk dat iemand moet oppakken.
"""
from __future__ import annotations

import tempfile

import pytest

from nooch_village import channels, cockpit2, signaal

ROL = "mother_earth__nooch__creator_of_shoes"
CIRKEL = "mother_earth__nooch"


@pytest.fixture()
def dorp():
    dd = tempfile.mkdtemp()
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    st.mens = st.people.add("Een Mens", "een@test.nl")
    st.tweede = st.people.add("Twee Mens", "twee@test.nl")
    st.founder = st.people.add("De Founder", "founder@test.nl")
    # DE BOOTSTRAP ZET AL VERVULLERS NEER. Zonder deze opschoning meet je de bootstrap in plaats
    # van de routering — dat kostte eerder een ronde.
    for rol in (ROL, signaal.TERUGVAL_ROL, f"{CIRKEL}__circle_lead"):
        rec = st.records.get(rol)
        for f in list(st.assign.fillers_of(rol, rec)) if rec else []:
            st.assign.unassign(rol, f.type, f.id)
    st.assign.assign(signaal.TERUGVAL_ROL, "person", st.founder.id)
    return st


# ── de vier takken ───────────────────────────────────────────────────────────

def test_een_persoon_is_zijn_eigen_adres(dorp):
    st = dorp
    assert signaal.ontvangers(st, "person", st.tweede.id) == ([st.tweede.id], signaal.NAAR_PERSOON)


def test_een_rol_met_een_vervuller_gaat_naar_die_mens(dorp):
    st = dorp
    st.assign.assign(ROL, "person", st.mens.id)
    assert signaal.ontvangers(st, "role", ROL) == ([st.mens.id], signaal.NAAR_VERVULLER)


def test_een_rol_zonder_mens_valt_terug_op_de_circle_lead(dorp):
    """De Circle Lead is de NABIJSTE mens, en het dorp gebruikt die regel al overal
    (`wiki.ontvanger`, `claims_board`). Hem hier overslaan liet een melding langs de
    dichtstbijzijnde mens schieten, regelrecht naar de founder."""
    st = dorp
    st.assign.assign(f"{CIRKEL}__circle_lead", "person", st.tweede.id)
    assert signaal.ontvangers(st, "role", ROL) == ([st.tweede.id], signaal.NAAR_LEAD)


def test_zonder_lead_valt_hij_terug_op_de_founder(dorp):
    st = dorp
    assert signaal.ontvangers(st, "role", ROL) == ([st.founder.id], signaal.NAAR_TERUGVAL)


def test_meerdere_vervullers_krijgen_het_allemaal(dorp):
    """Liever dubbel aankomen dan nergens: dit is werk dat iemand moet oppakken."""
    st = dorp
    st.assign.assign(ROL, "person", st.mens.id)
    st.assign.assign(ROL, "person", st.tweede.id)
    wie, reden = signaal.ontvangers(st, "role", ROL)
    assert sorted(wie) == sorted([st.mens.id, st.tweede.id]) and reden == signaal.MEERDERE
    assert len(signaal.stuur(st, "role", ROL, "nieuw werk", by="claims-checker")) == 2


# ── de vangnetten ────────────────────────────────────────────────────────────

def test_een_onbekende_ontvanger_verdwijnt_niet(dorp):
    """Een gast die via "+ tension" iets noteert heeft geen persoon-id. Onder de eerste versie
    verdween dat punt spoorloos. Een genoteerde spanning die nergens aankomt is het ergste wat deze
    laag kan doen: de schrijver denkt dat hij iets heeft vastgelegd."""
    st = dorp
    for doel_type, doel_id in (("person", ""), ("person", "bestaat-niet"), ("role", "")):
        wie, reden = signaal.ontvangers(st, doel_type, doel_id)
        assert wie == [st.founder.id] and reden == signaal.NAAR_TERUGVAL, (doel_type, doel_id)
    assert signaal.stuur(st, "person", "", "een los punt", by="zelf")


def test_de_terugval_begeeft_het_niet_bij_meer_dan_een_vervuller(dorp):
    """Een vangnet dat faalt omdát er meer mensen beschikbaar zijn, is geen vangnet. De eerste
    versie gaf "" zodra de founder-rol twee vervullers had — zonder fout, zonder log."""
    st = dorp
    st.assign.assign(signaal.TERUGVAL_ROL, "person", st.tweede.id)
    assert len(signaal.mensen_van(st, signaal.TERUGVAL_ROL)) == 2
    terug = signaal.terugval(st)
    assert terug and signaal.terugval(st) == terug        # en altijd dezelfde


def test_een_lege_tekst_levert_geen_bericht(dorp):
    st = dorp
    st.assign.assign(ROL, "person", st.mens.id)
    assert signaal.stuur(st, "role", ROL, "   ", by="x") == []


# ── het bericht zelf ─────────────────────────────────────────────────────────

def test_het_kanaal_draagt_de_afzender_ook_als_dat_geen_mens_is(dorp):
    """Bij 333 van de 338 gemigreerde meldingen was de afzender een rol- of systeemnaam. Die blijft
    zichtbaar, zodat de bron van een signaal niet wegvalt."""
    st = dorp
    st.assign.assign(ROL, "person", st.mens.id)
    kanalen = signaal.stuur(st, "role", ROL, "iets", by="claims-checker")
    assert kanalen == [channels.dm_kanaal("claims-checker", st.mens.id)]
    e = st.channels.trail(kanalen[0])[-1]
    assert e["author"]["id"] == "claims-checker" and e["text"] == "iets"


def test_geen_antwoordveld_als_de_tegenpartij_geen_persoon_is(dorp):
    """Antwoorden aan `claims-checker` is een dead letter: een rol leest geen berichten."""
    from nooch_village.views.messages import kan_antwoorden
    st = dorp
    dood = channels.dm_kanaal("claims-checker", st.mens.id)
    levend = channels.dm_kanaal(st.mens.id, st.tweede.id)
    eigen = channels.dm_kanaal(st.mens.id, st.mens.id)
    assert kan_antwoorden(st, dood, st.mens.id) is False
    assert kan_antwoorden(st, levend, st.mens.id) is True
    assert kan_antwoorden(st, eigen, st.mens.id) is True      # je eigen notitieblok mag wel


def test_de_poort_staat_ook_server_side(dorp):
    """Het ontbrekende invoerveld is geen poort. Een handmatige POST hoort ook te stuiten."""
    st = dorp
    dood = channels.dm_kanaal("claims-checker", st.mens.id)
    velden = {"kanaal": dood, "tekst": "hallo?"}
    _nxt, msg = cockpit2.ACTIONS["msg_post"](cockpit2._Ctx(
        st=st, g=lambda k, d="": velden.get(k, d), nxt="/messages", form=velden,
        username=st.mens.email, action="msg_post", data_dir=""))
    assert msg.startswith("✗") and "nobody reads" in msg
