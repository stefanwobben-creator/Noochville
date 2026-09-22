"""Direct toont iedereen, niet alleen wie je al eens geschreven hebt.

WAT ER MIS WAS. `_dm_groepen` gaf `st.channels.kanalen_van(ik)` terug: de DM-kanalen die
BESTAAN. Een kanaal bestaat pas zodra iemand er iets in zegt, dus een collega met wie je nooit
eerder sprak stond niet in Direct. Je zag een lijst van gesprekken waar een lijst van mensen
hoorde te staan — en om iemand te bereiken moest je eerst door een apart zoekblok.

DAT ZOEKBLOK IS WEG. "＋ new conversation" bestond alleen omdat Direct incompleet was; zodra
Direct iedereen toont is het een tweede ingang naar dezelfde handeling. Twee plekken om iemand
te kiezen betekent dat "waar kies ik iemand" twee antwoorden heeft.

DRIE DINGEN DIE MOETEN KLOPPEN:

  1. iedereen staat erin, ook zonder gesprek, en jezelf niet dubbel;
  2. wie je wél al sprak staat BOVENAAN, op volgorde van het laatste bericht. Dat was hij
     overigens nog niet: `kanalen_van` sorteert op kanaal-id (`dm:<a>|<b>`), en dat is de
     alfabetische volgorde van twee hex-id's — willekeurig dus. Deze verandering maakt de
     sortering waar die er al leek te zijn;
  3. klikken op zo'n nog-lege rij levert een werkend gesprek op: een leeg kanaal met een
     schrijfbalk, niet een 404 of een dood scherm. Daar was al niets voor nodig — deze test legt
     vast dat dat zo blijft, want de hele opzet leunt erop.
"""
from __future__ import annotations

import re

from nooch_village import channels, cockpit2
from nooch_village.views.messages import _dm_groepen, render_messages


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    ik = st.people.add("Ik Zelf", "ik@nooch.earth")
    oud = st.people.add("Oud Gesprek", "oud@nooch.earth")
    nieuw = st.people.add("Nooit Gesproken", "nooit@nooch.earth")
    return dd, cockpit2._Stores(dd), ik, oud, nieuw


def _direct_rijen(html: str) -> list[str]:
    """De kanaal-id's onder de kop Direct, op volgorde."""
    na = html.split(">Direct<", 1)
    assert len(na) == 2, "geen Direct-groep op het scherm"
    staart = na[1].split("msg-groep", 1)[0]
    return re.findall(r"href='/messages\?k=([^'&]+)", staart)


# ── 1. Iedereen staat erin ──────────────────────────────────────────────────────────────────
def test_iemand_zonder_gesprek_staat_ook_in_direct(tmp_path):
    dd, st, ik, oud, nieuw = _dorp(tmp_path)
    dms, _rollen = _dm_groepen(st, ik.id)
    assert channels.dm_kanaal(ik.id, nieuw.id) in dms


def test_jezelf_staat_er_niet_bij(tmp_path):
    """Een notitie aan jezelf blijft bestaan als het kanaal er al is, maar een lege rij met je
    eigen naam erin is geen gesprek dat je wilt beginnen."""
    dd, st, ik, oud, nieuw = _dorp(tmp_path)
    dms, _rollen = _dm_groepen(st, ik.id)
    assert dms, "lege lijst — dan meet deze test niets"
    assert channels.dm_kanaal(ik.id, ik.id) not in dms


def test_iedereen_staat_er_precies_een_keer(tmp_path):
    """MUTATIE-CONTROLE: aanvullen mag geen dubbele rij opleveren voor wie je al sprak."""
    dd, st, ik, oud, nieuw = _dorp(tmp_path)
    st.channels.post(channels.dm_kanaal(ik.id, oud.id), "hallo",
                     author_type="human", author_id=ik.id)
    st2 = cockpit2._Stores(dd)
    dms, _rollen = _dm_groepen(st2, ik.id)
    assert len(dms) == len(set(dms))
    # Precies één rij per ANDER mens in het dorp (de bootstrap zaait er zelf ook een paar).
    anderen = {p.id for p in st2.people.all() if p.id != ik.id}
    assert dms == sorted(dms, key=dms.index)                       # volgorde ongemoeid
    assert {channels.dm_kanaal(ik.id, p) for p in anderen} == set(dms)


def test_een_rol_afzender_blijft_uit_direct(tmp_path):
    """De splitsing die `_dm_groepen` maakt blijft staan: 37 rol- en systeemafzenders horen niet
    tussen je echte gesprekken. Aanvullen met mensen mag die scheiding niet opheffen."""
    dd, st, ik, oud, nieuw = _dorp(tmp_path)
    rol_kanaal = channels.dm_kanaal(ik.id, "compliance")
    st.channels.post(rol_kanaal, "van een rol", author_type="role", author_id="compliance")
    dms, rollen = _dm_groepen(cockpit2._Stores(dd), ik.id)
    assert rol_kanaal in rollen and rol_kanaal not in dms


# ── 2. De volgorde ──────────────────────────────────────────────────────────────────────────
def test_gesprekken_staan_boven_de_nog_lege_rijen(tmp_path):
    dd, st, ik, oud, nieuw = _dorp(tmp_path)
    st.channels.post(channels.dm_kanaal(ik.id, oud.id), "hallo",
                     author_type="human", author_id=ik.id)
    st2 = cockpit2._Stores(dd)
    dms, _rollen = _dm_groepen(st2, ik.id)
    assert dms[0] == channels.dm_kanaal(ik.id, oud.id)
    # en alles daarna is leeg — niet alleen de laatste rij
    for k in dms[1:]:
        assert st2.channels.trail(k) == [], k


def test_gesprekken_staan_op_volgorde_van_het_laatste_bericht(tmp_path):
    """`kanalen_van` sorteert op kanaal-id — de alfabetische volgorde van twee hex-id's, dus
    willekeurig. Twee gesprekken waarvan het jongste onderaan stond, is precies wat een
    gesprekkenlijst niet moet doen."""
    dd, st, ik, oud, nieuw = _dorp(tmp_path)
    k_oud = channels.dm_kanaal(ik.id, oud.id)
    k_nieuw = channels.dm_kanaal(ik.id, nieuw.id)
    st.channels.post(k_oud, "eerst", author_type="human", author_id=ik.id)
    st.channels.post(k_nieuw, "later", author_type="human", author_id=ik.id)
    dms, _rollen = _dm_groepen(cockpit2._Stores(dd), ik.id)
    assert dms[:2] == [k_nieuw, k_oud]


# ── 3. Klikken op een lege rij ──────────────────────────────────────────────────────────────
def test_een_lege_dm_toont_een_gesprek_met_een_schrijfbalk(tmp_path):
    """Hier leunt de hele opzet op: een rij zonder berichten moet een werkend, leeg gesprek
    openen. Er was hier niets voor nodig — deze test zorgt dat dat zo blijft."""
    dd, st, ik, oud, nieuw = _dorp(tmp_path)
    k = channels.dm_kanaal(ik.id, nieuw.id)
    html = render_messages(st, ik=ik.id, kanaal=k, csrf_token="t")
    assert "Nothing said here yet." in html
    assert "id='msg-tekst'" in html and "value='msg_post'" in html
    assert "Nooit Gesproken" in html                 # het gesprek heet naar de ander


def test_de_rij_staat_ook_echt_op_het_scherm(tmp_path):
    """De twee tests hierboven toetsen de FUNCTIE; deze het scherm."""
    dd, st, ik, oud, nieuw = _dorp(tmp_path)
    html = render_messages(st, ik=ik.id, kanaal=channels.circle_kanaal("mother_earth"),
                           csrf_token="t")
    assert channels.dm_kanaal(ik.id, nieuw.id) in _direct_rijen(html)


# ── 4. Het zoekblok is weg ──────────────────────────────────────────────────────────────────
def test_er_is_geen_tweede_ingang_meer_om_iemand_te_kiezen(tmp_path):
    """"＋ new conversation" bestond omdat Direct incompleet was. Nu is Direct de plek."""
    dd, st, ik, oud, nieuw = _dorp(tmp_path)
    html = render_messages(st, ik=ik.id, kanaal=channels.circle_kanaal("mother_earth"),
                           csrf_token="t")
    assert "new conversation" not in html
    assert "msg-nieuw-dm" not in html
    assert "Who do you want to write to?" not in html


def test_de_css_van_dat_blok_gaat_mee(tmp_path):
    """Dode CSS liegt op drie manieren tegelijk (zie `test_dode_css`): hij telt mee in elke
    meting, suggereert dat er een scherm is dat hem gebruikt, en wordt bij elke stijlronde
    meegesleept."""
    import os
    basis = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    css = open(os.path.join(basis, "nooch_village", "static", "nooch.css"), encoding="utf-8").read()
    kaal = re.sub(r"/\*.*?\*/", " ", css, flags=re.S)
    assert "msg-nieuw-dm" not in kaal


def test_de_wie_parameter_is_nergens_meer(tmp_path):
    """Hij droeg de zoekterm van dat blok. Een parameter die de route nog doorgeeft aan een
    functie die hem niet meer kent, is de volgende verwarring."""
    import os
    basis = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for pad in ("nooch_village/views/messages.py", "nooch_village/cockpit2.py"):
        bron = open(os.path.join(basis, pad), encoding="utf-8").read()
        kaal = re.sub(r'""".*?"""', " ", bron, flags=re.S)
        kaal = re.sub(r"#[^\n]*", " ", kaal)
        assert 'wie=' not in kaal and '"wie"' not in kaal, pad
