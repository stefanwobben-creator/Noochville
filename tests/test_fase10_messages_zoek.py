"""Punt 1a — het zoek/filterveld boven de kanalenlijst van `/messages`.

Waarom dit er is, met een getal: op productie staan **442** niet-gearchiveerde projecten, en
`_kanalen` maakte van elk een kanaal in de lijst. Dat is geen lijst meer maar een muur. Twee
ingrepen: een zoekveld, en zonder zoekterm een cap op de projectgroep — op volgorde van het
laatste bericht, want alfabetisch afkappen is willekeurig en op recentheid afkappen laat zien waar
het gesprek loopt.

De tests zijn op GEDRAG geschreven en niet op de opmaak: ze bouwen een dorp met meer kanalen dan
de cap en kijken wat er in en uit de lijst valt.
"""
from __future__ import annotations

import re
import tempfile

import pytest

from nooch_village import channels, cockpit2
from nooch_village.views.messages import PROJECT_CAP, _kanalen, render_messages

OWNER = "mother_earth__nooch__creator_of_shoes"


@pytest.fixture()
def dorp():
    dd = tempfile.mkdtemp()
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    ik = st.people.add("Zoek Tester", "zoek@test.nl")
    # Ruim boven de cap, met oplopende tijd zodat "laatste bericht" een echte volgorde heeft.
    for i in range(PROJECT_CAP + 12):
        pid = st.projects.create(OWNER, f"Project {i:02d} mycelium" if i % 3 == 0
                                 else f"Project {i:02d} leer", "human", status="running")
        st.projects.add_feed_entry(pid, f"bericht {i}", kind="comment",
                                   author_type="human", author_id=ik.id)
    return st, ik.id


def _namen(html: str) -> list[str]:
    """De kanaalnamen uit de gerenderde lijst.

    LEEST `.msg-knaam` EN NIET DE HELE `<a>`. Sinds fase 11 (3b) bestaat de rij uit drie delen —
    naam, tijdstip, ongelezen-teller — dus de oude regex (`>([^<]+)</a>`) vond niets meer en gaf
    een lege lijst terug. De test op regel ~100 telt die lijst tegen een BOVENgrens en bleef dus
    groen omdat hij niets meer zag, niet omdat er niets mis was. Precies de stille meetfout waar
    `test_alle_vijf_de_bronnen_vallen_onder_de_regel` in de pijplijn-ratchet ook voor bestaat."""
    return re.findall(r"class='msg-knaam'>([^<]+)</span>", html)


def test_zonder_zoekterm_is_de_projectlijst_afgekapt(dorp):
    st, ik = dorp
    groepen, totaal = _kanalen(st, ik, "")
    assert totaal["Projects"] == PROJECT_CAP + 12          # ze bestaan allemaal
    assert len(groepen["Projects"]) == PROJECT_CAP         # maar je ziet er PROJECT_CAP
    assert totaal["Circles"] == len(groepen["Circles"])    # cirkels nooit afkappen


def test_de_afkapping_houdt_het_recentste_gesprek(dorp):
    """Alfabetisch afkappen zou willekeurig zijn. Het laatst besproken project hoort er sowieso in."""
    st, ik = dorp
    groepen, _ = _kanalen(st, ik, "")
    laatste = channels.project_kanaal(
        max(st.projects.all(), key=lambda p: (p.get("log") or [{}])[-1].get("at", 0))["id"])
    assert laatste in groepen["Projects"]


def test_zoeken_heft_de_cap_op_en_filtert_op_label(dorp):
    st, ik = dorp
    groepen, totaal = _kanalen(st, ik, "mycelium")
    gevonden = groepen["Projects"]
    assert len(gevonden) > 0
    assert all("mycelium" in _lbl(st, k, ik) for k in gevonden)
    # de cap geldt niet meer bij een zoekterm, en er valt echt iets af
    assert len(gevonden) < totaal["Projects"]


def _lbl(st, k, ik):
    from nooch_village.views.messages import _label
    return _label(st, k, ik).lower()


def test_zoeken_is_hoofdletter_en_spatie_ongevoelig(dorp):
    st, ik = dorp
    a, _ = _kanalen(st, ik, "MYCELIUM")
    b, _ = _kanalen(st, ik, "  mycelium  ")
    c, _ = _kanalen(st, ik, "mycelium")
    assert a["Projects"] == b["Projects"] == c["Projects"] != []


def test_de_voordeur_hangt_niet_van_de_zoekterm_af(dorp):
    """Welk kanaal er opengaat als je géén `k` meegeeft, mag niet veranderen door te zoeken —
    anders land je na een zoekopdracht ergens anders dan ervoor."""
    st, ik = dorp
    zonder = re.search(r"class='msg-kop'>([^<]*)<", render_messages(st, ik=ik, csrf_token="t"))
    met = re.search(r"class='msg-kop'>([^<]*)<",
                    render_messages(st, ik=ik, csrf_token="t", q="mycelium"))
    assert zonder and met and zonder.group(1) == met.group(1)


def test_het_scherm_zegt_hoeveel_er_verborgen_zijn(dorp):
    """Een stille cap is een leugen: je denkt dat dit alles is. Het aantal moet op het scherm."""
    st, ik = dorp
    html = render_messages(st, ik=ik, csrf_token="t")
    assert f"{PROJECT_CAP} of {PROJECT_CAP + 12}" in html
    assert "search for the rest" in html
    assert len(_namen(html)) <= PROJECT_CAP + 30           # niet alsnog alles gerenderd


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
