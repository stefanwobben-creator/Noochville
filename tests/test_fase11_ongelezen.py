"""Fase 11, punt 3a — de ongelezen-indicator op de kanalenlijst van `/messages`.

Waarom dit er is, met een getal: op productie staan 442 niet-gearchiveerde kanalen. Zonder
ongelezen-aanduiding moet je ze alle 442 langslopen om te weten waar iets nieuws is. De zoekbalk
(fase 10, punt 1a) loste de andere helft op — vinden wat je zoekt — maar niet: zien waar iets is
zonder dat je weet dat je het zoekt.

EEN AANNAME IN DE SPEC KLOPTE NIET, en dat bepaalde het ontwerp. Punt 3a noemt dit "puur leeswerk
op al bestaande lees-tijdstippen". Die bestonden niet: `ChannelStore` draagt geen leesstatus, en de
oude `NotifStore` — die wél een `read`-vlag had — is in B2 opgeheven. De gezien-stand is daarom
nieuw, en hangt aan de MENS (`PeopleStore`) en niet aan het bericht: wanneer heb ÍK dit gelezen is
een eigenschap van de lezer. Zie de toelichting bij `PeopleStore.gezien`.

Ongelezen zelf wordt nooit opgeslagen. Het is een VERGELIJKING tussen twee tijdstippen, net als
`wiki.grond_status`: uitgerekend bij het lezen, zodat hij niet uit de pas kan lopen met de trail.

Vijf gedragingen, en drie ervan zijn de valkuilen waar zo'n indicator op stukgaat:
  1. een nieuw bericht van een ander maakt het kanaal ongelezen;
  2. je EIGEN bericht niet — anders is de teller meteen onbetrouwbaar, en een indicator die er één
     keer naast zit kijk je daarna niet meer aan;
  3. het kanaal openen zet hem uit, en het kanaal dat je NU opent staat nog wél in de lijst als
     ongelezen (anders zie je nooit wat je zojuist opende);
  4. de stand loopt nooit terug (twee tabbladen zetten elkaar niet op 'weer ongelezen');
  5. de indicator draagt een TELLING, niet alleen kleur — leesbaar in zwart-wit.
"""
from __future__ import annotations

import re
import tempfile

import pytest

from nooch_village import channels, cockpit2
from nooch_village.views.messages import render_messages

OWNER = "mother_earth__nooch__creator_of_shoes"


@pytest.fixture()
def dorp():
    dd = tempfile.mkdtemp()
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    ik = st.people.add("Lezer", "lezer@test.nl")
    ander = st.people.add("Schrijver", "schrijver@test.nl")
    kanaal = channels.dm_kanaal(ik.id, ander.id)
    return st, ik.id, ander.id, kanaal


def _rij(html: str, kanaal_label: str) -> str:
    """De <a>-regel van één kanaal, zodat we op de MODIFIER kunnen toetsen en niet op de hele pagina."""
    for m in re.finditer(r"<a class='(msg-kanaal[^']*)'[^>]*>(.*?)</a>", html, re.S):
        if kanaal_label in m.group(2):
            return m.group(1) + "|" + m.group(2)
    return ""


# ── 1. een bericht van een ander is ongelezen ───────────────────────────────

def test_een_bericht_van_een_ander_maakt_het_kanaal_ongelezen(dorp):
    st, ik, ander, kanaal = dorp
    st.channels.post(kanaal, "kijk hier eens naar", author_type="human", author_id=ander)
    # Een ANDER kanaal openen, zodat dit kanaal niet als 'nu geopend' wordt gemarkeerd.
    html = render_messages(cockpit2._Stores(st.dd), ik=ik, kanaal="")
    rij = _rij(html, "Schrijver")
    assert "msg-kanaal--nieuw" in rij, rij
    assert "msg-nieuw" in rij


def test_de_indicator_draagt_een_telling_en_niet_alleen_kleur(dorp):
    """Kleur-alleen is hier geen optie: het getal is wat een schermlezer voorleest en wat in
    zwart-wit overblijft. Zelfde regel als de bordkolommen uit fase 9."""
    st, ik, ander, kanaal = dorp
    for i in range(3):
        st.channels.post(kanaal, f"bericht {i}", author_type="human", author_id=ander)
    html = render_messages(cockpit2._Stores(st.dd), ik=ik, kanaal="")
    assert ">3</span>" in _rij(html, "Schrijver")


def test_boven_de_negen_kapt_hij_af_op_negen_plus(dorp):
    st, ik, ander, kanaal = dorp
    for i in range(14):
        st.channels.post(kanaal, f"bericht {i}", author_type="human", author_id=ander)
    html = render_messages(cockpit2._Stores(st.dd), ik=ik, kanaal="")
    assert ">9+</span>" in _rij(html, "Schrijver")


# ── 2. je eigen woorden zijn niet nieuw voor jou ────────────────────────────

def test_je_eigen_bericht_telt_niet_als_ongelezen(dorp):
    """DE VALKUIL DIE DE INDICATOR ONBETROUWBAAR MAAKT. Je typt iets, gaat terug naar de lijst, en
    ziet je eigen zin als 'nieuw' staan. Eén keer is genoeg om er niet meer op te vertrouwen."""
    st, ik, ander, kanaal = dorp
    st.channels.post(kanaal, "ik zeg zelf iets", author_type="human", author_id=ik)
    html = render_messages(cockpit2._Stores(st.dd), ik=ik, kanaal="")
    assert "msg-kanaal--nieuw" not in _rij(html, "Schrijver")


# ── 3. openen is lezen ──────────────────────────────────────────────────────

def test_het_kanaal_openen_zet_de_indicator_uit(dorp):
    st, ik, ander, kanaal = dorp
    st.channels.post(kanaal, "iets nieuws", author_type="human", author_id=ander)
    # Openen…
    render_messages(cockpit2._Stores(st.dd), ik=ik, kanaal=kanaal)
    # …en daarna terugkomen: weg.
    html = render_messages(cockpit2._Stores(st.dd), ik=ik, kanaal="")
    assert "msg-kanaal--nieuw" not in _rij(html, "Schrijver")


def test_het_kanaal_dat_je_nu_opent_staat_nog_wel_als_ongelezen_in_de_lijst(dorp):
    """Anders zie je nooit wát je zojuist opende: de rij die je aanklikte zou in dezelfde
    pageload al schoon zijn. Daarom telt de weergave vóór het markeren."""
    st, ik, ander, kanaal = dorp
    st.channels.post(kanaal, "iets nieuws", author_type="human", author_id=ander)
    html = render_messages(cockpit2._Stores(st.dd), ik=ik, kanaal=kanaal)
    assert "msg-kanaal--nieuw" in _rij(html, "Schrijver")


def test_een_nieuw_bericht_na_het_lezen_telt_weer(dorp):
    st, ik, ander, kanaal = dorp
    st.channels.post(kanaal, "eerste", author_type="human", author_id=ander)
    render_messages(cockpit2._Stores(st.dd), ik=ik, kanaal=kanaal)     # gelezen
    st.channels.post(kanaal, "tweede", author_type="human", author_id=ander)
    html = render_messages(cockpit2._Stores(st.dd), ik=ik, kanaal="")
    rij = _rij(html, "Schrijver")
    assert "msg-kanaal--nieuw" in rij and ">1</span>" in rij, rij


# ── 4. de stand loopt nooit terug ───────────────────────────────────────────

def test_de_gezien_stand_loopt_nooit_terug(dorp):
    """Twee tabbladen: het ene staat op een ouder bericht. Zou de oudere stand winnen, dan zet het
    ene tabblad het andere terug op 'ongelezen' — en dan flikkert de indicator zonder reden."""
    st, ik, _ander, kanaal = dorp
    st.people.markeer_gezien(ik, kanaal, 1000.0)
    st.people.markeer_gezien(ik, kanaal, 500.0)
    assert st.people.gezien(ik)[kanaal] == 1000.0


def test_de_gezien_stand_overleeft_het_herlezen_van_de_store(dorp):
    """Hij hangt aan de mens en niet aan het bericht, dus hij moet het bestand overleven — en
    `Person` mag er niet door breken, want `_to_person` filtert op de dataclass-velden."""
    st, ik, _ander, kanaal = dorp
    st.people.markeer_gezien(ik, kanaal, 42.0)
    vers = cockpit2._Stores(st.dd)
    assert vers.people.gezien(ik)[kanaal] == 42.0
    assert vers.people.get(ik).name == "Lezer"


# ── 5. een gast heeft geen gezien-stand ─────────────────────────────────────

def test_zonder_ingelogde_mens_is_er_geen_indicator(dorp):
    """Fail-soft: zonder `ik` valt er niets te vergelijken. Geen indicator is het juiste antwoord —
    een gast zou anders alles als ongelezen zien en dat zegt hem niets."""
    st, _ik, ander, kanaal = dorp
    st.channels.post(kanaal, "iets", author_type="human", author_id=ander)
    html = render_messages(cockpit2._Stores(st.dd), ik="", kanaal="")
    assert "msg-kanaal--nieuw" not in html
