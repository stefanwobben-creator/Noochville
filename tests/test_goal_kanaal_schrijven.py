"""Een doel-kanaal is een kanaal waar je in kunt schrijven.

DE BUG, en waarom hij twee keer terugkwam. `soort_van()` kent vijf soorten — project, circle, dm,
topic én GOAL — maar twee poorten in `cockpit2.py` schreven hun eigen lijstje van vier op:

    if channels.soort_van(kanaal) not in (channels.PROJECT, channels.CIRCLE,
                                          channels.DM, channels.TOPIC):
        return nxt, "✗ unknown channel"

Eén doel-kanaal per open doel staat sinds 21 september in de kanalenlijst, is te lezen
(`mag_kanaal_lezen` kent GOAL wél), en toont gewoon een schrijfbalk — `kan_antwoorden` gaat alleen
over DM's en zegt hier ja. Je typte dus een bericht in een kanaal dat je mag lezen, drukte op
Send, en kreeg "unknown channel" terug op een kanaal dat de lijst je zelf had aangeboden.

DAT HET TWEE KEER GEBEURDE IS HET PUNT. Het lijstje stond op twee plekken los van elkaar
uitgeschreven, en de tweede (`_eigen_bericht_poort`, bewerken en verwijderen) kopieerde op
22 september braaf de fout van de eerste. Dat is precies wat de `reference, don't copy`-regel uit
CLAUDE.md verbiedt: een feit dat op twee plekken leeft, drijft uiteen zonder dat iets zich meldt.
De lijst woont nu in `channels.SCHRIJFBAAR`, naast de constanten zelf — dan kan er geen derde
kopie ontstaan.
"""
from __future__ import annotations

import re

from nooch_village import channels, cockpit2

DOEL = "een_doel"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    ik = st.people.add("Doelschrijver Daan", "daan@nooch.earth")
    return dd, cockpit2._Stores(dd), ik.id


def _post(dd, kanaal, tekst, username="daan@nooch.earth"):
    return cockpit2.dispatch(dd, "msg_post",
                             {"kanaal": [kanaal], "tekst": [tekst], "next": ["/messages"]},
                             username=username)


# ── 1. Schrijven ────────────────────────────────────────────────────────────────────────────
def test_je_kunt_in_een_doel_kanaal_schrijven(tmp_path):
    dd, st, ik = _dorp(tmp_path)
    k = channels.goal_kanaal(DOEL)
    _nxt, msg = _post(dd, k, "dit gaat over het doel")
    assert not msg.startswith("✗"), msg
    assert [e["text"] for e in cockpit2._Stores(dd).channels.trail(k)] == ["dit gaat over het doel"]


def test_een_echt_onbekende_soort_wordt_nog_steeds_geweigerd(tmp_path):
    """MUTATIE-CONTROLE: de test hierboven zou ook slagen als de poort helemaal weg was. Dan is
    élke string een kanaal, en `post` maakt er een lege trail-sleutel van."""
    dd, st, ik = _dorp(tmp_path)
    _nxt, msg = _post(dd, "verzonnen:iets", "hallo")
    assert msg == "✗ unknown channel"
    assert cockpit2._Stores(dd).channels.trail("verzonnen:iets") == []


# ── 2. Bewerken en verwijderen ──────────────────────────────────────────────────────────────
def test_je_kunt_je_eigen_doel_bericht_bewerken_en_wissen(tmp_path):
    """De tweede poort. Zonder deze test dekt de fix maar de helft — en dat is precies hoe de
    bug zich vermenigvuldigde."""
    dd, st, ik = _dorp(tmp_path)
    k = channels.goal_kanaal(DOEL)
    _post(dd, k, "eerste poging")
    eid = cockpit2._Stores(dd).channels.trail(k)[-1]["id"]
    _nxt, msg = cockpit2.dispatch(dd, "msg_edit",
                                  {"kanaal": [k], "item": [eid], "tekst": ["tweede poging"],
                                   "next": ["/messages"]}, username="daan@nooch.earth")
    assert not msg.startswith("✗"), msg
    assert [e["text"] for e in cockpit2._Stores(dd).channels.trail(k)] == ["tweede poging"]
    cockpit2.dispatch(dd, "msg_remove", {"kanaal": [k], "item": [eid], "next": ["/messages"]},
                      username="daan@nooch.earth")
    assert cockpit2._Stores(dd).channels.trail(k) == []


def test_de_auteur_poort_geldt_ook_hier(tmp_path):
    """Een soort erbij mag geen poort openzetten die voor alle andere soorten dicht staat."""
    dd, st, ik = _dorp(tmp_path)
    cockpit2._Stores(dd).people.add("Andere Anouk", "anouk@nooch.earth")
    k = channels.goal_kanaal(DOEL)
    _post(dd, k, "mijn woorden")
    eid = cockpit2._Stores(dd).channels.trail(k)[-1]["id"]
    _nxt, msg = cockpit2.dispatch(dd, "msg_remove",
                                  {"kanaal": [k], "item": [eid], "next": ["/messages"]},
                                  username="anouk@nooch.earth")
    assert msg.startswith("✗")
    assert len(cockpit2._Stores(dd).channels.trail(k)) == 1


# ── 3. Eén lijst, niet drie ─────────────────────────────────────────────────────────────────
def test_de_lijst_woont_op_een_plek():
    """`reference, don't copy`. De twee poorten schreven hun eigen tuple; de tweede kopieerde de
    fout van de eerste. Een derde kopie hoort niet te kunnen ontstaan."""
    assert set(channels.SCHRIJFBAAR) == {channels.PROJECT, channels.CIRCLE,
                                         channels.DM, channels.TOPIC, channels.GOAL}


def test_geen_enkele_poort_schrijft_de_soorten_nog_zelf_uit():
    """Structureel, niet op naam: zoek elke plek in cockpit2.py die twee of meer kanaalsoort-
    constanten in één uitdrukking opsomt. Dat is per definitie een tweede lijst."""
    bron = open(cockpit2.__file__, encoding="utf-8").read()
    kaal = re.sub(r'"""..*?"""', " ", bron, flags=re.S)       # docstrings eruit
    kaal = re.sub(r"#[^\n]*", " ", kaal)                      # en comments
    opsommingen = re.findall(r"channels\.(?:PROJECT|CIRCLE|DM|TOPIC|GOAL)\s*,\s*"
                             r"channels\.(?:PROJECT|CIRCLE|DM|TOPIC|GOAL)", kaal)
    assert not opsommingen, f"{len(opsommingen)}× een eigen lijstje kanaalsoorten: {opsommingen}"
