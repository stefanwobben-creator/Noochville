"""De inbox wordt DM — stap A: elke notificatie als bericht bij de mens die hem aangaat.

Dit vervangt het eerdere ontwerp met `role:<id>` en een `verwerking`-blok. Stefan trok die eis op
20 september in: *"alles wat tot dusver in de inbox is gekomen kon ik niet echt veel mee, dus dat
werkte sowieso niet, dus ook niet om te houden."* Er gaat dus géén state mee — en precies daarom
staat hieronder een test die dat vastlegt, want "we bewaren niets" is een besluit en geen
vergetelheid.

Twee dingen dragen het ontwerp en hebben elk hun eigen test:

1. **`target_type` routeert, niet `entry_id`.** Die twee verzamelingen raken elkaar nauwelijks: op
   prod zijn er 33 persoon-gerichte rijen waarvan er 3 een `entry_id` dragen, en 24 rijen mét
   `entry_id` waarvan er 21 rol-gericht zijn.
2. **Een rol met twee vervullers wordt NIET geraden.** Die rijen worden geparkeerd en gemeld.
"""
from __future__ import annotations

import tempfile

import pytest

from nooch_village import channels, cockpit2, notif_migratie as nm

LEVEND = "mother_earth__nooch__creator_of_shoes"
OPGEHEVEN = "librarian"


@pytest.fixture()
def dorp():
    dd = tempfile.mkdtemp()
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    st.mens = st.people.add("Een Mens", "een@test.nl")
    st.tweede = st.people.add("Twee Mens", "twee@test.nl")
    st.founder = st.people.add("De Founder", "founder@test.nl")
    # DE BOOTSTRAP ZET AL VERVULLERS NEER. Zonder deze opschoning heeft `creator_of_shoes` er twee
    # zodra de test er een bij zet, en dan meet je de bootstrap in plaats van de routering.
    for rol in (LEVEND, OPGEHEVEN, nm.TERUGVAL_ROL):
        rec = st.records.get(rol)
        for f in list(st.assign.fillers_of(rol, rec)) if rec else []:
            st.assign.unassign(rol, f.type, f.id)
    st.assign.assign(LEVEND, "person", st.mens.id)
    st.assign.assign(nm.TERUGVAL_ROL, "person", st.founder.id)
    return st


# ── routering ────────────────────────────────────────────────────────────────

def test_een_persoon_gericht_item_gaat_naar_die_persoon(dorp):
    st = dorp
    n = st.notif.add("person", st.tweede.id, "p1", snippet="voor jou", by="dialoog")
    ontvanger, reden = nm.ontvanger_van(st, n)
    assert ontvanger == st.tweede.id and reden == nm.NAAR_PERSOON


def test_een_rol_met_een_vervuller_gaat_naar_die_vervuller(dorp):
    st = dorp
    n = st.notif.add("role", LEVEND, "p1", snippet="iets", by="claims-checker")
    assert nm.ontvanger_van(st, n) == (st.mens.id, nm.NAAR_VERVULLER)


def test_een_rol_zonder_vervuller_valt_terug_op_de_founder(dorp):
    """Ook als de rol gearchiveerd is. Op prod dragen `noochville__circle_lead` (49 rijen) en
    `the_source` (36) nog wél een vervuller; dáár volgt de routering de vervulling. 85 berichten
    mogen niet van de volgorde van twee checks afhangen."""
    st = dorp
    n = st.notif.add("role", OPGEHEVEN, "p1", snippet="oud werk", by="harry_hemp")
    assert nm.ontvanger_van(st, n) == (st.founder.id, nm.NAAR_TERUGVAL)


def test_een_rol_met_twee_vervullers_wordt_niet_geraden(dorp):
    """Naar beiden is dubbel, naar de eerste is willekeur, naar de founder is een aanname. Parkeren."""
    st = dorp
    st.assign.assign(LEVEND, "person", st.tweede.id)          # nu twee mensen
    n = st.notif.add("role", LEVEND, "p1", snippet="iets", by="claims-checker")
    ontvanger, reden = nm.ontvanger_van(st, n)
    assert ontvanger == "" and reden == nm.MEERDERE
    r = nm.migreer(st.notif, st, apply=True)
    assert r["geparkeerd"] == 1 and r["geparkeerde_rollen"][f"role:{LEVEND}"] == 1
    assert r["klopt"] is True                                  # geparkeerd telt gewoon mee


def test_entry_id_speelt_geen_rol_in_de_routering(dorp):
    """De opdracht routeerde op `entry_id`; dat bleek een andere verzameling dan bedoeld."""
    st = dorp
    met = st.notif.add("role", LEVEND, "p1", entry_id="abc123", snippet="met", by="x")
    zonder = st.notif.add("role", LEVEND, "p1", snippet="zonder", by="x")
    assert nm.ontvanger_van(st, met)[0] == nm.ontvanger_van(st, zonder)[0] == st.mens.id


# ── het bericht ──────────────────────────────────────────────────────────────

def test_er_gaat_geen_verwerkingsstate_mee(dorp):
    """Een besluit, geen vergetelheid: Stefan trok de eis in omdat de inbox niet werkte."""
    st = dorp
    n = st.notif.add("role", LEVEND, "p1", snippet="iets", by="claims-checker")
    st.notif.mark_item_processed(n["id"], outcome="afgehandeld")
    nm.migreer(st.notif, st, apply=True)
    kanaal = channels.dm_kanaal("claims-checker", st.mens.id)
    e = st.channels.trail(kanaal)[0]
    assert "verwerking" not in e
    assert set(e) == {"id", "kind", "author", "text", "at"}


def test_id_en_tijdstip_komen_uit_de_notificatie(dorp):
    """Twee keuzes die uit het vorige ontwerp overeind blijven: `at` van de klok nemen zet drie
    maanden gesprek op de dag van de migratie, en het id maakt de migratie idempotent."""
    st = dorp
    n = st.notif.add("role", LEVEND, "p1", snippet="iets", by="x")
    nm.migreer(st.notif, st, apply=True)
    e = st.channels.trail(channels.dm_kanaal("x", st.mens.id))[0]
    assert e["id"] == n["id"] and e["at"] == n["at"]


def test_de_migratie_is_idempotent_en_verantwoordt_alles(dorp):
    st = dorp
    for i in range(3):
        st.notif.add("role", LEVEND, "p1", snippet=f"item {i}", by="claims-checker")
    st.notif.add("person", st.tweede.id, "p1", snippet="voor jou", by="dialoog")
    eerste = nm.migreer(st.notif, st, apply=True)
    tweede = nm.migreer(st.notif, st, apply=True)
    assert eerste["geschreven"] == 4 and tweede["geschreven"] == 0
    assert tweede["bestond_al"] == 4
    assert eerste["klopt"] and tweede["klopt"]


def test_droogloop_schrijft_niets(dorp):
    st = dorp
    st.notif.add("role", LEVEND, "p1", snippet="iets", by="x")
    r = nm.migreer(st.notif, st, apply=False)
    assert r["geschreven"] == 1 and "klopt" not in r
    assert "droogloop" in nm.rapport_tekst(r)
    assert st.channels.bestaande() == []


def test_notifstore_blijft_intact(dorp):
    """Stap A van twee: schrijven. Verwijderen is stap B."""
    st = dorp
    st.notif.add("role", LEVEND, "p1", snippet="iets", by="x")
    nm.migreer(st.notif, st, apply=True)
    assert len(st.notif.all()) == 1


# ── het antwoordveld ─────────────────────────────────────────────────────────

def test_geen_antwoordveld_als_de_tegenpartij_geen_persoon_is(dorp):
    """Antwoorden aan `compliance` is een dead letter: een rol leest geen berichten."""
    from nooch_village.views.messages import kan_antwoorden, render_messages
    st = dorp
    st.notif.add("role", LEVEND, "p1", snippet="iets", by="claims-checker")
    nm.migreer(st.notif, st, apply=True)
    dood = channels.dm_kanaal("claims-checker", st.mens.id)
    levend = channels.dm_kanaal(st.mens.id, st.tweede.id)
    assert kan_antwoorden(st, dood, st.mens.id) is False
    assert kan_antwoorden(st, levend, st.mens.id) is True
    html = render_messages(st, ik=st.mens.id, kanaal=dood, csrf_token="t")
    assert "No reply box" in html and "value='msg_post'" not in html


def test_de_poort_staat_ook_server_side(dorp):
    """Het ontbrekende invoerveld is geen poort. Een handmatige POST hoort ook te stuiten."""
    st = dorp
    st.notif.add("role", LEVEND, "p1", snippet="iets", by="claims-checker")
    nm.migreer(st.notif, st, apply=True)
    dood = channels.dm_kanaal("claims-checker", st.mens.id)
    velden = {"kanaal": dood, "tekst": "hallo?"}
    _nxt, msg = cockpit2.ACTIONS["msg_post"](cockpit2._Ctx(
        st=st, g=lambda k, d="": velden.get(k, d), nxt="/messages", form=velden,
        username=st.mens.email, action="msg_post", data_dir=""))
    assert msg.startswith("✗") and "nobody reads" in msg


def test_het_kanaal_heet_naar_de_bron_en_niet_direct(dorp):
    """Twintig kanalen die allemaal "direct" heten is geen lijst."""
    from nooch_village.views.messages import _label
    st = dorp
    kanaal = channels.dm_kanaal("claims-checker", st.mens.id)
    assert _label(st, kanaal, st.mens.id) == "claims-checker"


def test_een_kanaal_met_jezelf_heet_yourself_en_mag_antwoorden(dorp):
    """Op prod bestaat er één: notificaties waarvan de afzender dezelfde mens is als de vervuller
    van de doelrol — jij die je eigen rol aanspreekt. Zonder aparte regel heet dat "direct", net
    als elk ander naamloos kanaal, en heeft het geen invoerveld terwijl het je eigen notitieblok is."""
    from nooch_village.views.messages import _label, kan_antwoorden
    st = dorp
    eigen = channels.dm_kanaal(st.mens.id, st.mens.id)
    assert _label(st, eigen, st.mens.id) == "Yourself"
    assert kan_antwoorden(st, eigen, st.mens.id) is True
