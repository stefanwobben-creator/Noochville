"""Drie vervolgpunten op de DM-opruiming (22 september 2026).

1. DRIE KANALEN DIE ALLEMAAL DEZELFDE MENS ZIJN, samengevoegd tot één. Een overblijfsel van de
   inbox-migratie: die schreef de afzender weg zoals hij 'm aantrof — soms een id, soms een naam
   ("Stefan Wobben"), soms een e-mailadres. Voor de lezer waren het drie gesprekken met zichzelf.
2. EEN GESPREK BEGINNEN DAT NOG NIET BESTAAT. Een DM kon pas gevonden worden nadat er al een
   bericht in stond — wie het eerste wilde sturen had geen ingang. De OPLOSSING is op
   22 september 2026 vervangen: er kwam eerst een "＋ new conversation"-zoekblok bij, en dat is
   nu weer weg omdat `Direct` zelf iedereen toont. De belofte is dezelfde gebleven en de tests
   hieronder toetsen hem op de nieuwe plek; zie `tests/test_messages_direct_iedereen.py`.
3. "ROLES & SYSTEM" UIT DE LIJST. Verbergen, niet wissen: de kanalen blijven staan.
"""
from __future__ import annotations

import json
import os

from nooch_village import channels, cockpit2, dm_samenvoegen as D
from nooch_village.views.messages import _dm_groepen, _kanalen, render_messages

BRON_A, BRON_B = D.BRONNEN
DOEL = D.DOEL


def _dorp(tmp_path, kanalen: dict):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    with open(os.path.join(dd, "channels.json"), "w", encoding="utf-8") as fh:
        json.dump({"kanalen": kanalen, "namen": {}}, fh)
    return dd


def _b(bid, at, tekst, auteur):
    return {"id": bid, "kind": "comment", "at": float(at), "text": tekst,
            "author": {"type": "role", "id": auteur}}


def _echt():
    """De prod-vorm: 2 + 1 + 5, elk met een eigen spelling van dezelfde mens."""
    return {BRON_A: [_b("a1", 100, "Klaar: research", "Stefan Wobben"),
                     _b("a2", 400, "Klaar: capaciteit", "Stefan Wobben")],
            BRON_B: [_b("b1", 200, "Capaciteit ontbreekt", "stefan@nooch.earth")],
            DOEL: [_b("c1", 50, "research interesting facts", "dc5685eb2074"),
                   _b("c2", 300, "Testje", "dc5685eb2074"),
                   _b("c3", 500, "plan tuesday", "dc5685eb2074"),
                   _b("c4", 600, "Hi Logan", "dc5685eb2074"),
                   _b("c5", 700, "nog iets", "dc5685eb2074")]}


# ── 1. Samenvoegen ──────────────────────────────────────────────────────────
def test_de_droge_run_schrijft_niets(tmp_path):
    dd = _dorp(tmp_path, _echt())
    voor = D.sha256(f"{dd}/channels.json")
    v = D.voer_uit(dd, apply=False)
    assert v["verplaatst"] == 3 and v["doel_na"] == 8 and v["toegepast"] is False
    assert D.sha256(f"{dd}/channels.json") == voor


def test_samenvoegen_zet_op_tijd_en_verandert_geen_bericht(tmp_path):
    """DE KERN. De berichten worden VERPLAATST, niet herschreven — ook hun `author` niet, ook als
    die "Stefan Wobben" of een e-mailadres is. Dat is vastgelegde herkomst; "wie zei dit" mag een
    opruiming niet veranderen."""
    dd = _dorp(tmp_path, _echt())
    v = D.voer_uit(dd, apply=True)
    assert v["onverwacht"] == [], f"berichten gewijzigd: {v['onverwacht']}"
    kan = json.load(open(f"{dd}/channels.json"))["kanalen"]
    assert BRON_A not in kan and BRON_B not in kan
    t = kan[DOEL]
    assert [e["id"] for e in t] == ["c1", "a1", "b1", "c2", "a2", "c3", "c4", "c5"]
    assert [e["at"] for e in t] == sorted(e["at"] for e in t)
    # de auteurs staan er nog precies zoals ze stonden
    assert {e["author"]["id"] for e in t} == {"Stefan Wobben", "stefan@nooch.earth", "dc5685eb2074"}


def test_twee_berichten_op_dezelfde_seconde_blokkeren_de_samenvoeging(tmp_path):
    """DE POORT. Bij gelijke tijdstempels is de volgorde een gok, en dan hoort hier geen script te
    draaien maar een vraag aan een mens te komen."""
    k = _echt()
    k[BRON_A][0]["at"] = k[DOEL][0]["at"]
    dd = _dorp(tmp_path, k)
    v = D.voer_uit(dd, apply=True)
    assert v["blokkades"] and "dezelfde tijdstempel" in v["blokkades"][0]
    assert json.load(open(f"{dd}/channels.json"))["kanalen"].get(BRON_A), "toch samengevoegd"


def test_een_bericht_zonder_tijdstempel_blokkeert_ook(tmp_path):
    k = _echt()
    k[BRON_B][0].pop("at")
    dd = _dorp(tmp_path, k)
    v = D.voer_uit(dd, apply=True)
    assert any("zonder tijdstempel" in b for b in v["blokkades"])
    assert BRON_B in json.load(open(f"{dd}/channels.json"))["kanalen"]


def test_een_dubbel_bericht_id_blokkeert_ook(tmp_path):
    k = _echt()
    k[BRON_A][0]["id"] = "c1"
    dd = _dorp(tmp_path, k)
    assert any("dubbele bericht-id" in b for b in D.voer_uit(dd, apply=True)["blokkades"])


def test_twee_keer_draaien_doet_de_tweede_keer_niets(tmp_path):
    dd = _dorp(tmp_path, _echt())
    D.voer_uit(dd, apply=True)
    tussen = D.sha256(f"{dd}/channels.json")
    tweede = D.voer_uit(dd, apply=True)
    assert tweede["verplaatst"] == 0
    assert D.sha256(f"{dd}/channels.json") == tussen


# ── 2. Een gesprek beginnen ─────────────────────────────────────────────────
def test_je_kunt_iemand_vinden_die_nog_niets_gezegd_heeft(tmp_path):
    """HET GAT. `kanalen_van` leest `channels.json`, en daar staat niets tot iemand iets zegt. Wie
    het eerste bericht wilde sturen had dus geen ingang.

    HETZELFDE GAT, ANDERE OPLOSSING (22 september 2026). Eerst was het een zoekblok met
    `wie=bosbes`; nu staat Bob gewoon in Direct, zónder dat je iets typt. De test eist dus niet
    langer dat je hem kunt ZOEKEN maar dat hij er STAAT — dat is een sterkere eis, geen zwakkere."""
    import re
    dd = _dorp(tmp_path, {})
    st = cockpit2._Stores(dd)
    ik = st.people.add("Alice Aardbei", "alice@test.nl")
    bob = st.people.add("Bob Bosbes", "bob@test.nl")
    st2 = cockpit2._Stores(dd)
    assert st2.channels.kanalen_van(ik.id) == []              # er bestaat nog niets
    h = render_messages(st2, ik=ik.id, csrf_token="t")
    assert "Bob Bosbes" in h
    assert channels.dm_kanaal(ik.id, bob.id) in re.findall(r"k=(dm:[^'&]*)", h)


def test_de_bron_is_dezelfde_als_de_globale_zoek():
    """Een eigen personenlijst hier zou een tweede antwoord geven op "wie werkt hier"."""
    import inspect
    from nooch_village.views import messages
    # De aanroep verhuisde van `render_messages` (het zoekblok) naar `_dm_groepen` (de lijst
    # zelf). De belofte is ongewijzigd: één bron voor "wie werkt hier".
    bron = inspect.getsource(messages._dm_groepen)
    assert "from nooch_village.views.search import _people" in bron


def test_jezelf_staat_er_niet_bij(tmp_path):
    """Je eigen kanaal heet al "Yourself" zodra het bestaat; een lege rij met je eigen naam
    erbij maakt twee ingangen naar hetzelfde gesprek. Toetste eerst het zoekblok, nu de lijst."""
    dd = _dorp(tmp_path, {})
    st = cockpit2._Stores(dd)
    ik = st.people.add("Alice Aardbei", "alice@test.nl")
    direct, _rollen = _dm_groepen(cockpit2._Stores(dd), ik.id)
    assert channels.dm_kanaal(ik.id, ik.id) not in direct


# `test_geen_treffer_zegt_dat_ook` STOND HIER. Hij toetste de melding "Nobody by that name" in
# het zoekblok. Er is geen zoekveld meer om niets te vinden: Direct toont iedereen, en "iedereen"
# is nooit leeg zolang je zelf bestaat. De test is dus niet afgezwakt maar zonder onderwerp.


def test_zonder_schrijfsessie_geen_schrijfbalk(tmp_path):
    """Heette `test_zonder_schrijfsessie_geen_ingang` en toetste dat het zoekblok wegbleef.
    Dat blok is er niet meer; de belofte eronder wél: zonder schrijfsessie geen schrijfveld."""
    dd = _dorp(tmp_path, {})
    st = cockpit2._Stores(dd)
    ik = st.people.add("Alice Aardbei", "alice@test.nl")
    bob = st.people.add("Bob Bosbes", "bob@test.nl")
    k = channels.dm_kanaal(ik.id, bob.id)
    h = render_messages(cockpit2._Stores(dd), ik=ik.id, kanaal=k, csrf_token="")
    assert "id='msg-tekst'" not in h and "value='msg_post'" not in h


# ── 3. Verbergen, niet wissen ───────────────────────────────────────────────
def test_de_rolgroep_staat_niet_meer_in_de_lijst(tmp_path):
    dd = _dorp(tmp_path, {})
    st = cockpit2._Stores(dd)
    ik = st.people.add("Alice Aardbei", "alice@test.nl")
    st.channels.post(channels.dm_kanaal(ik.id, "compliance"), "scan af", author_id="compliance")
    st2 = cockpit2._Stores(dd)
    groepen, _t, _g = _kanalen(st2, ik.id, "")
    assert "Roles & system" not in groepen
    # "Goals" stond hier tot 26 september 2026; de automatische koppeling doel → kanaal is
    # opgeheven, zie `tests/test_messages_kanaal_verwijderen.py`.
    assert list(groepen) == ["General", "Channels", "Projects", "Direct"]
    assert "Roles" not in render_messages(st2, ik=ik.id, csrf_token="t")


def test_maar_het_gesprek_staat_er_nog(tmp_path):
    """VERBERGEN, NIET WISSEN — zelfde discipline als eerder in dit traject. De kanalen, hun
    berichten en hun bijlagen blijven staan, en wie een link heeft komt er nog gewoon in."""
    from nooch_village.views.messages import mag_kanaal_lezen
    dd = _dorp(tmp_path, {})
    st = cockpit2._Stores(dd)
    ik = st.people.add("Alice Aardbei", "alice@test.nl")
    k = channels.dm_kanaal(ik.id, "compliance")
    st.channels.post(k, "scan af", author_id="compliance")
    st2 = cockpit2._Stores(dd)
    assert len(st2.channels.trail(k)) == 1
    assert mag_kanaal_lezen(st2, k, ik.id) is True
    assert "scan af" in render_messages(st2, ik=ik.id, kanaal=k, csrf_token="t")


def test_de_splitsing_blijft_bestaan(tmp_path):
    """`_dm_groepen` blijft ze afsplitsen — dat is wat ze uit Direct houdt. Alleen de tweede lijst
    wordt niet meer getoond."""
    dd = _dorp(tmp_path, {})
    st = cockpit2._Stores(dd)
    ik = st.people.add("Alice Aardbei", "alice@test.nl")
    st.channels.post(channels.dm_kanaal(ik.id, "compliance"), "x", author_id="compliance")
    direct, rollen = _dm_groepen(cockpit2._Stores(dd), ik.id)
    # `direct` is niet meer leeg — hij bevat sinds 22 september elke MENS in het dorp. Waar het
    # om gaat is dat de rol-afzender er niet tussen staat, en dat is wat hier wordt getoetst.
    assert len(rollen) == 1
    assert channels.dm_kanaal(ik.id, "compliance") not in direct
