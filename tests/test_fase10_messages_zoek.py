"""Het zoek/filterveld boven de kanalenlijst van `/messages`, en wat die lijst toont.

WAAROM DIT ER IS, MET EEN GETAL: op productie staan 442 niet-gearchiveerde projecten, en `_kanalen`
maakte van elk mét gesprek een kanaal in de lijst — 123 stuks. Dat is geen lijst maar een muur.
Punt 1a (20 september 2026) zette er een zoekveld en een CAP van 25 op: de 25 meest recente, met
"search for the rest" eronder.

DE CAP IS OP 21 SEPTEMBER VERVANGEN, niet verhoogd. Een cap laat je nog steeds langs namen scrollen
die je niet zocht; hij maakte het probleem zichtbaar zonder het op te lossen. Nu zijn kanalen
BEWUST: Projects toont alleen wat JIJ volgt, en volgen doe je door een kanaal te openen of op te
zoeken. `PROJECT_CAP` bestaat niet meer.

Wat onveranderd bleef en hier nog steeds getoetst wordt: het zoekveld is een GET-formulier (geen
JS-filter), zoeken is hoofdletter- en spatie-ongevoelig, de voordeur hangt niet van de zoekterm af,
en een leeg kanaal toont geen tijdstip.

De tests zijn op GEDRAG geschreven en niet op de opmaak.
"""
from __future__ import annotations

import re
import tempfile

import pytest

from nooch_village import channels, cockpit2
from nooch_village.views.messages import _kanalen, render_messages

OWNER = "mother_earth__nooch__creator_of_shoes"


@pytest.fixture()
def dorp():
    dd = tempfile.mkdtemp()
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    ik = st.people.add("Zoek Tester", "zoek@test.nl")
    # Veel meer projecten dan iemand wil zien, met oplopende tijd zodat "laatste bericht" een echte
    # volgorde heeft. Eén op de drie heet "mycelium" — dat is waar de zoektests op mikken.
    for i in range(37):
        pid = st.projects.create(OWNER, f"Project {i:02d} mycelium" if i % 3 == 0
                                 else f"Project {i:02d} leer", "human", status="running")
        st.projects.add_feed_entry(pid, f"bericht {i}", kind="comment",
                                   author_type="human", author_id=ik.id)
    # En drie die deze mens heeft toegevoegd. Dat is wat zijn lijst hoort te tonen — de andere 34
    # bestaan wel, maar niet voor hem tot hij ze opzoekt.
    gevolgd = [channels.project_kanaal(p["id"]) for p in st.projects.all()[:3]]
    for k in gevolgd:
        st.people.volg(ik.id, k)
    return st, ik.id


def _namen(html: str) -> list[str]:
    """De kanaalnamen uit de gerenderde lijst.

    LEEST `.msg-knaam` EN NIET DE HELE `<a>`. Sinds fase 11 (3b) bestaat de rij uit drie delen —
    naam, tijdstip, ongelezen-teller — dus de oude regex (`>([^<]+)</a>`) vond niets meer en gaf
    een lege lijst terug. De test op regel ~100 telt die lijst tegen een BOVENgrens en bleef dus
    groen omdat hij niets meer zag, niet omdat er niets mis was. Precies de stille meetfout waar
    `test_alle_vijf_de_bronnen_vallen_onder_de_regel` in de pijplijn-ratchet ook voor bestaat."""
    return re.findall(r"class='msg-knaam'>([^<]+)</span>", html)


def test_zonder_zoekterm_zie_je_alleen_wat_je_volgt(dorp):
    """DE VERVANGING VAN DE CAP. Niet "de 25 recentste van 37" maar "de 3 die van jou zijn".
    Het verschil is dat het tweede een keuze is en het eerste een afkapping."""
    st, ik = dorp
    groepen, totaal, gevolgd = _kanalen(st, ik, "")
    assert totaal["Projects"] == 37                        # ze bestaan allemaal
    assert len(groepen["Projects"]) == 3                   # je ziet wat je toevoegde
    assert set(groepen["Projects"]) == gevolgd
    assert len(groepen["General"]) == 1                    # het dorpskanaal staat er altijd


def test_de_eigen_lijst_staat_op_volgorde_van_het_laatste_bericht(dorp):
    """Alfabetisch sorteren zou willekeurig zijn; op recentheid laat zien waar het gesprek loopt.
    Dat argument overleeft het wegvallen van de cap ongewijzigd — het ging nooit over afkappen
    maar over volgorde."""
    st, ik = dorp
    groepen, _t, _g = _kanalen(st, ik, "")
    op_tijd = sorted(groepen["Projects"],
                     key=lambda k: -(st.channels.laatste(k) or {}).get("at", 0))
    assert groepen["Projects"] == op_tijd


def test_zoeken_ziet_ook_wat_je_niet_volgt(dorp):
    """DE ENIGE MANIER WAAROP DEZE WIJZIGING IETS KAPOT ZOU MAKEN: een project dat je nog niet hebt
    toegevoegd onvindbaar maken. Mét zoekterm komt het hele veld terug, niet alleen je eigen lijst."""
    st, ik = dorp
    groepen, totaal, gevolgd = _kanalen(st, ik, "mycelium")
    gevonden = groepen["Projects"]
    assert len(gevonden) > len(gevolgd), "zoeken toont niet meer dan je eigen lijst"
    assert all("mycelium" in _lbl(st, k, ik) for k in gevonden)
    assert len(gevonden) < totaal["Projects"]              # en er valt echt iets af
    assert any(k not in gevolgd for k in gevonden)         # inclusief niet-gevolgde


def _lbl(st, k, ik):
    from nooch_village.views.messages import _label
    return _label(st, k, ik).lower()


def test_zoeken_is_hoofdletter_en_spatie_ongevoelig(dorp):
    st, ik = dorp
    a, _ta, _ga = _kanalen(st, ik, "MYCELIUM")
    b, _tb, _gb = _kanalen(st, ik, "  mycelium  ")
    c, _tc, _gc = _kanalen(st, ik, "mycelium")
    assert a["Projects"] == b["Projects"] == c["Projects"] != []


def test_de_voordeur_hangt_niet_van_de_zoekterm_af(dorp):
    """Welk kanaal er opengaat als je géén `k` meegeeft, mag niet veranderen door te zoeken —
    anders land je na een zoekopdracht ergens anders dan ervoor."""
    st, ik = dorp
    zonder = re.search(r"class='msg-kop'>([^<]*)<", render_messages(st, ik=ik, csrf_token="t"))
    met = re.search(r"class='msg-kop'>([^<]*)<",
                    render_messages(st, ik=ik, csrf_token="t", q="mycelium"))
    assert zonder and met and zonder.group(1) == met.group(1)


def test_het_scherm_zegt_hoeveel_je_volgt_van_hoeveel(dorp):
    """Een stille lijst is een leugen: je denkt dat dit alles is. Het aantal moet op het scherm —
    en de tekst erbij is veranderd van "search for the rest" (dat klinkt als afgekapt) naar
    "search to add more" (dat zegt wat je moet doen)."""
    st, ik = dorp
    html = render_messages(st, ik=ik, csrf_token="t")
    assert "3 of 37" in html
    assert "search to add more" in html
    assert "search for the rest" not in html
    assert len(_namen(html)) < 37, "de hele muur staat alsnog op het scherm"


def test_geen_treffer_zegt_dat_ook(dorp):
    st, ik = dorp
    html = render_messages(st, ik=ik, csrf_token="t", q="zoiets-bestaat-niet")
    assert "No channel matches that" in html


# ── Fase 11, laag 1+2: de kanaalrij, de rail en de drill-down ────────────────────────────────

def test_de_kanaalrij_draagt_naam_en_tijdstip(dorp):
    """3b: naam, wanneer, en hoeveel nieuw — in die volgorde. Zonder tijdstip moet je een kanaal
    openen om te weten of er deze week nog iets gebeurd is, en dat is precies de vraag die een
    lijst hoort te beantwoorden."""
    st, ik = dorp
    html = render_messages(st, ik=ik)
    assert "msg-knaam" in html and "msg-tijd" in html
    assert _namen(html), "de namen moeten leesbaar blijven in de rij"
    # Het tijdstip hoort bij een kanaal waarin iets GEZEGD is. General is leeg en toont er geen —
    # dat is de regel hieronder, en de reden dat deze test een gevolgd project nodig heeft.


def test_een_kanaal_zonder_gesprek_toont_geen_tijdstip():
    """GEEN DATA IS GEEN NUL. Een leeg kanaal heeft geen laatste bericht; "01/01/70" ziet eruit
    als data terwijl het een bug is."""
    from nooch_village.views.messages import _kort_tijd
    assert _kort_tijd(0) == ""
    assert _kort_tijd(1_700_000_000.0)                      # een echt tijdstip levert wél tekst


def test_messages_klapt_de_zijbalk_in_tot_een_rail(dorp):
    """Drie kolommen (navigatie, kanalen, gesprek) passen alleen als de eerste krimpt. Het WOORD
    blijft in de DOM — een rail die alleen monogrammen rendert laat een schermlezer 'PR' horen."""
    st, ik = dorp
    html = render_messages(st, ik=ik)
    assert "c2-side--rail" in html
    assert "c2-mono" in html and "c2-lbl" in html
    assert "Projects" in html


def test_de_mobiele_lijst_stand_markeert_niets_als_gelezen(dorp):
    """DE VAL VAN DRILL-DOWN. "Het openen is het lezen" klopt alleen als je het gesprek ZIET; in
    de lijst-stand is de draad juist verborgen. Zou hij tóch markeren, dan is het ongelezen-merk
    weg van een kanaal dat niemand las."""
    st, ik = dorp
    k = channels.project_kanaal(st.projects.all()[0]["id"])
    st.channels.post(k, "iets nieuws", author_type="person", author_id="iemand_anders")
    render_messages(st, ik=ik, kanaal=k, lijst=True)
    assert not st.people.gezien(ik).get(k)
    render_messages(st, ik=ik, kanaal=k)
    assert st.people.gezien(ik).get(k)


def test_de_drill_down_stand_staat_in_de_markup(dorp):
    """Eén rendering, twee standen: `data-mob` zegt welk niveau een telefoon toont. Desktop ziet
    beide panelen — daarom mag hier niets verdwijnen uit de DOM."""
    st, ik = dorp
    lijst = render_messages(st, ik=ik, lijst=True)
    draad = render_messages(st, ik=ik)
    assert "data-mob='lijst'" in lijst and "data-mob='draad'" in draad
    for html in (lijst, draad):
        assert "msg-lijst" in html and "msg-draad" in html   # beide panelen blijven staan
    assert "msg-terug" in draad                              # en de weg terug staat er
