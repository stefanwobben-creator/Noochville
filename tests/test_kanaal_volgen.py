"""Kanalen zijn bewust: wat in JOUW lijst staat, en het kanaal van een doel (21 september 2026).

DE AANLEIDING, met het getal erbij. Messages toonde elk project met een gesprek als kanaal — op
productie 123 stuks, plus 42 DM's. Dat is geen lijst meer maar een muur: je scrolt langs honderden
namen op zoek naar één, en de cap van 25 ("25 of 159 · search for the rest") maakte dat zichtbaar
zonder het op te lossen. Besluit Stefan: een project is pas een kanaal als jij dat zegt.

Deze PR levert alleen de LAAG: `volg`/`ontvolg` op de mens en `goal:<id>` als kanaalsoort. Het
scherm dat erop staat komt in de volgende (geen half werk live).

DRIE KEUZES DIE DEZE TESTS VASTHOUDEN:

  1. "in mijn lijst" is een eigenschap van de MENS, niet van het kanaal — anders volgt iedereen
     hetzelfde en drijft het uiteen zodra er een tweede lezer bijkomt;
  2. ontvolgen raakt het GESPREK niet aan: er wordt niets verwijderd, alleen niet meer getoond;
  3. een doel-kanaal verwijst naar het DOEL-ID, niet naar de doelnaam.
"""
from __future__ import annotations

import json

from nooch_village import channels, cockpit2


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    een = st.people.add("Persoon Een", "een@t.nl")
    twee = st.people.add("Persoon Twee", "twee@t.nl")
    return dd, st, een, twee


# ── 1. Volgen is van de mens ─────────────────────────────────────────────────
def test_volgen_staat_bij_de_mens_en_niet_bij_het_kanaal(tmp_path):
    """DE KERNKEUZE. Twee mensen, één kanaal, twee verschillende lijsten."""
    dd, st, een, twee = _dorp(tmp_path)
    k = channels.project_kanaal("p1")
    assert st.people.volg(een.id, k) is True
    assert st.people.volgt(een.id, k) is True
    assert st.people.volgt(twee.id, k) is False, "de een volgen zette het voor iedereen aan"


def test_volgen_is_idempotent_en_verspringt_niet(tmp_path):
    """Het tijdstip van de EERSTE keer blijft staan. Zou elk bezoek het opnieuw zetten, dan is
    "sinds wanneer volg ik dit" een getal dat nooit iets betekent."""
    dd, st, een, _ = _dorp(tmp_path)
    k = channels.circle_kanaal("mother_earth")
    st.people.volg(een.id, k, at=1000.0)
    assert st.people.volg(een.id, k, at=2000.0) is False       # tweede keer verandert niets
    assert st.people.gevolgd(een.id)[k] == 1000.0


def test_ontvolgen_haalt_uit_de_lijst_en_niet_uit_de_data(tmp_path):
    """Een kanaal verdwijnt uit je LIJST, nooit uit de opslag. Het gesprek blijft compleet; je
    vindt het terug via zoeken, net als de eerste keer."""
    dd, st, een, _ = _dorp(tmp_path)
    k = channels.circle_kanaal("mother_earth")
    st.channels.post(k, "iets gezegds", author_type="human", author_id=een.id)
    st.people.volg(een.id, k)
    assert st.people.ontvolg(een.id, k) is True
    assert st.people.volgt(een.id, k) is False
    assert len(st.channels.trail(k)) == 1, "het gesprek is meegegaan met het ontvolgen"


def test_ontvolgen_van_iets_wat_je_niet_volgt_is_geen_fout(tmp_path):
    dd, st, een, _ = _dorp(tmp_path)
    assert st.people.ontvolg(een.id, "project:onbekend") is False
    assert st.people.volg("bestaat-niet", "project:p1") is False
    assert st.people.volg(een.id, "") is False


def test_de_lijst_overleeft_een_herstart(tmp_path):
    """Hij staat in `people.json` naast `gezien`, en reist mee zonder in de `Person`-dataclass te
    hoeven staan — `_to_person` filtert op de velden van die klasse."""
    dd, st, een, _ = _dorp(tmp_path)
    st.people.volg(een.id, "project:p1")
    opnieuw = cockpit2._Stores(dd)
    assert opnieuw.people.volgt(een.id, "project:p1") is True
    ruw = json.load(open(f"{dd}/people.json"))
    assert "gevolgd" in ruw[een.id]
    assert opnieuw.people.get(een.id).name == "Persoon Een"     # de dataclass blijft heel


def test_gezien_en_gevolgd_lopen_elkaar_niet_in_de_weg(tmp_path):
    """Twee sleutels op dezelfde mens, twee verschillende vragen: wanneer las ik dit, en wil ik
    het zien staan. Ze horen elkaar niet te overschrijven."""
    dd, st, een, _ = _dorp(tmp_path)
    k = channels.circle_kanaal("mother_earth")
    st.people.markeer_gezien(een.id, k, 500.0)
    st.people.volg(een.id, k, at=600.0)
    st.people.markeer_gezien(een.id, k, 700.0)
    assert st.people.gezien(een.id)[k] == 700.0
    assert st.people.gevolgd(een.id)[k] == 600.0


# ── 2. Het kanaal van een doel ───────────────────────────────────────────────
def test_een_doelkanaal_verwijst_naar_het_id_niet_naar_de_naam(tmp_path):
    """DE REDEN DAT DIT EEN EIGEN SOORT IS. `maak_topic("MITH")` was de goedkopere weg, en fout:
    de naam van een doel is een weergavestring die een mens verandert. Met `goal:<doel_id>` volgt
    het kanaal een hernoeming vanzelf."""
    dd, st, _, _ = _dorp(tmp_path)
    d = st.doelen.add("Rapport MITH", label="MITH")
    k = channels.goal_kanaal(d["id"])
    assert channels.soort_van(k) == channels.GOAL
    assert channels.doel_van(k) == d["id"]
    st.doelen.update(d["id"], label="MITH 2027")
    assert channels.doel_van(k) == d["id"], "het kanaal hing aan de naam"


def test_een_doelkanaal_is_een_gewoon_kanaal(tmp_path):
    """Geen tweede opslagmechanisme: dezelfde `post`/`trail` als een topic, in `channels.json`."""
    dd, st, een, _ = _dorp(tmp_path)
    d = st.doelen.add("Website live", label="Website")
    k = channels.goal_kanaal(d["id"])
    e = st.channels.post(k, "eerste woord hier", author_type="human", author_id=een.id)
    assert e is not None
    assert [x["text"] for x in st.channels.trail(k)] == ["eerste woord hier"]
    assert st.channels.laatste(k)["author"]["id"] == een.id
    ruw = json.load(open(f"{dd}/channels.json"))
    assert k in ruw["kanalen"], "een doelkanaal hoort in dezelfde opslag als een topic"


def test_een_doelkanaal_valt_niet_stil_zoals_een_dm_naar_een_rol(tmp_path):
    """`kan_antwoorden` laat alleen een DM naar een niet-bestaande persoon afketsen. Een doel is
    geen mens, dus hier mag gewoon geschreven worden — anders is het kanaal een dead letter."""
    from nooch_village.views.messages import kan_antwoorden
    dd, st, een, _ = _dorp(tmp_path)
    d = st.doelen.add("Supply chain", label="Supply chain")
    assert kan_antwoorden(st, channels.goal_kanaal(d["id"]), een.id) is True


def test_de_soorten_blijven_uit_elkaar_te_houden(tmp_path):
    """Vijf prefixen, vijf betekenissen. Een `goal:` mag nooit als project gelezen worden — dan
    gaat `post` de ledger in en verdwijnt het bericht."""
    ids = {channels.PROJECT: channels.project_kanaal("p"),
           channels.CIRCLE: channels.circle_kanaal("r"),
           channels.GOAL: channels.goal_kanaal("d"),
           channels.TOPIC: channels.topic_kanaal("t"),
           channels.DM: channels.dm_kanaal("a", "b")}
    for soort, kanaal in ids.items():
        assert channels.soort_van(kanaal) == soort
    assert len(set(ids.values())) == 5
