"""Twee dingen die een gesprek pas een gesprek maken: iemand KUNNEN aanspreken, en je eigen
woorden kunnen terugnemen.

1. DE MENSENLIJST STOND ACHTER EEN ZOEKTERM. `＋ new conversation` klapte open met een leeg
   veld eronder: wie de namen niet uit zijn hoofd kende zag een dood vak. Een lijst van vijf
   mensen verbergen achter een zoekveld is zoeken in plaats van kiezen. Zoeken FILTERT nu, het
   ontsluit niet meer.

2. EEN EIGEN BERICHT WAS DEFINITIEF. Er was alleen `msg_post`; een typefout bleef staan tot het
   einde der tijden. Nu `msg_edit` en `msg_remove`, met de auteur-poort IN DE STORE en niet in
   het scherm — een knop die er niet staat houdt een POST niet tegen. Dat is het verschil tussen
   deze tests en "de knop is er": de helft hieronder post namens iemand anders en eist dat er
   niets verandert.

WAT HIER BEWUST NIET STAAT: een "edited"-merkje. De project-wall bewerkt al jaren zonder, en
één van de twee achterkanten (`ProjectLedger.feed_edit`) kent het niet. Het merkje op één helft
zetten zou betekenen dat hetzelfde bericht wél of niet als bewerkt leest, afhankelijk van welk
soort kanaal het toevallig is.
"""
from __future__ import annotations

import os
import re
from html.parser import HTMLParser

from nooch_village import channels, cockpit2
from nooch_village.views.messages import render_messages

BASIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS = open(os.path.join(BASIS, "nooch_village", "static", "nooch.css"), encoding="utf-8").read()


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    ik = st.people.add("Ik Zelf", "ik@nooch.earth")
    ander = st.people.add("Ander Iemand", "ander@nooch.earth")
    return dd, cockpit2._Stores(dd), ik, ander


def _kanaal():
    return channels.circle_kanaal("mother_earth")


def _nieuw_dm_blok(html: str) -> str:
    """Alleen het `＋ new conversation`-uitklapblok."""
    m = re.search(r"<details class='qadd msg-nieuw-dm'.*?</details>", html, re.S)
    assert m, "geen new-conversation-blok"
    return m.group(0)


def _diepste_formulier(html: str) -> int:
    class Teller(HTMLParser):
        def __init__(self):
            super().__init__()
            self.diepte = self.max = 0

        def handle_starttag(self, tag, attrs):
            if tag == "form":
                self.diepte += 1
                self.max = max(self.max, self.diepte)

        def handle_endtag(self, tag):
            if tag == "form":
                self.diepte = max(0, self.diepte - 1)

    t = Teller()
    t.feed(html)
    return t.max


# ── 1. De mensenlijst staat er meteen ───────────────────────────────────────────────────────
def test_de_mensen_staan_er_zonder_dat_je_iets_typt(tmp_path):
    dd, st, ik, ander = _dorp(tmp_path)
    blok = _nieuw_dm_blok(render_messages(st, ik=ik.id, kanaal=_kanaal(), csrf_token="t"))
    assert "Ander Iemand" in blok
    assert channels.dm_kanaal(ik.id, ander.id) in blok


def test_het_blok_staat_open_zonder_zoekterm(tmp_path):
    """Een lijst die er is maar dicht zit, is voor wie 'm zoekt hetzelfde als geen lijst."""
    dd, st, ik, _a = _dorp(tmp_path)
    blok = _nieuw_dm_blok(render_messages(st, ik=ik.id, kanaal=_kanaal(), csrf_token="t"))
    assert blok.startswith("<details class='qadd msg-nieuw-dm' open>")


def test_het_blok_is_weer_dicht_te_klappen(tmp_path):
    """`.qadd[open]>summary{display:none}` verbergt de regel waarmee je een quick-add sluit —
    logisch voor iets dat je na gebruik dichtdoet, fout voor een lijst die standaard openstaat.
    Zonder deze uitzondering is "＋ new conversation" onzichtbaar én onklikbaar zodra de pagina
    laadt, en staat het veld er voorgoed."""
    kaal = re.sub(r"/\*.*?\*/", " ", CSS, flags=re.S)
    per = {s.strip(): b for s, b in re.findall(r"([^{}]+)\{([^{}]*)\}", kaal)}
    assert "display:none" in per.get(".qadd[open]>summary", ""), \
        "de familie-regel is weg — dan is de uitzondering hieronder zinloos geworden"
    assert "display:block" in per.get(".msg-nieuw-dm[open]>summary", "")


def test_zoeken_filtert_de_lijst_en_ontsluit_hem_niet(tmp_path):
    """MUTATIE-CONTROLE op de test hierboven: die zou ook slagen als het veld niets meer deed."""
    dd, st, ik, ander = _dorp(tmp_path)
    blok = _nieuw_dm_blok(render_messages(st, ik=ik.id, kanaal=_kanaal(),
                                          csrf_token="t", wie="Ander"))
    assert "Ander Iemand" in blok
    blok2 = _nieuw_dm_blok(render_messages(st, ik=ik.id, kanaal=_kanaal(),
                                           csrf_token="t", wie="Zoekterm Zonder Treffer"))
    assert "Ander Iemand" not in blok2
    assert "Nobody by that name." in blok2


def test_jezelf_staat_niet_in_de_lijst(tmp_path):
    """Je eigen kanaal heet 'Yourself' en staat al in de kanalenlijst."""
    dd, st, ik, _a = _dorp(tmp_path)
    blok = _nieuw_dm_blok(render_messages(st, ik=ik.id, kanaal=_kanaal(), csrf_token="t"))
    assert "Ander Iemand" in blok            # anders meet dit een lege lijst
    assert "Ik Zelf" not in blok


# ── 2. Bewerken en verwijderen: het scherm ──────────────────────────────────────────────────
def _post(dd, kanaal, tekst, username):
    return cockpit2.dispatch(dd, "msg_post",
                             {"kanaal": [kanaal], "tekst": [tekst],
                              "next": [f"/messages?k={kanaal}"]}, username=username)


def test_eigen_bericht_krijgt_bewerken_en_verwijderen(tmp_path):
    dd, st, ik, _a = _dorp(tmp_path)
    k = _kanaal()
    _post(dd, k, "mijn eigen zin", "ik@nooch.earth")
    st = cockpit2._Stores(dd)
    eid = st.channels.trail(k)[-1]["id"]
    html = render_messages(st, ik=ik.id, kanaal=k, csrf_token="t")
    assert f"data-bewerk='{eid}'" in html          # het inline bewerkformulier
    assert "value='msg_edit'" in html
    assert "value='msg_remove'" in html


def test_het_bericht_van_een_ander_krijgt_ze_niet(tmp_path):
    """MUTATIE-CONTROLE: de test hierboven zou ook slagen als élk bericht de knoppen kreeg."""
    dd, st, ik, ander = _dorp(tmp_path)
    k = _kanaal()
    _post(dd, k, "de zin van iemand anders", "ander@nooch.earth")
    _post(dd, k, "en mijn eigen zin", "ik@nooch.earth")
    st = cockpit2._Stores(dd)
    van_ander, van_mij = st.channels.trail(k)
    html = render_messages(st, ik=ik.id, kanaal=k, csrf_token="t")
    # BEIDE KANTEN IN ÉÉN RENDER, anders slaagt dit ook als er nergens een knop staat.
    assert f"data-bewerk='{van_mij['id']}'" in html
    assert f"data-bewerk='{van_ander['id']}'" not in html
    assert html.count("value='msg_edit'") == 1
    assert html.count("value='msg_remove'") == 1


def test_het_bewerkveld_nest_geen_formulieren(tmp_path):
    """Een <form> in een <form> gooit de browser weg — dan is de knop er wel en doet hij niets.
    Dat ging in #556 al een keer mis in dezelfde balk."""
    dd, st, ik, _a = _dorp(tmp_path)
    k = _kanaal()
    _post(dd, k, "mijn eigen zin", "ik@nooch.earth")
    html = render_messages(cockpit2._Stores(dd), ik=ik.id, kanaal=k, csrf_token="t")
    assert _diepste_formulier(html) == 1


def test_het_bewerkveld_heeft_een_label(tmp_path):
    """Geen zichtbaar label (het staat op de plek van de tekst), maar wel een hoorbaar."""
    dd, st, ik, _a = _dorp(tmp_path)
    k = _kanaal()
    _post(dd, k, "mijn eigen zin", "ik@nooch.earth")
    st = cockpit2._Stores(dd)
    eid = st.channels.trail(k)[-1]["id"]
    html = render_messages(st, ik=ik.id, kanaal=k, csrf_token="t")
    assert f"<label class='sr' for='msg-edit-{eid}'>" in html
    assert f"id='msg-edit-{eid}'" in html


def test_het_bewerkveld_hergebruikt_de_bestaande_veldopmaak(tmp_path):
    """Geen nieuwe familie: het veld hangt in een `.qadd-form`, en die regel bestaat al —
    inclusief zijn nu-tegenhanger. Anders is dit het enige tekstvak in het dorp met een
    eigen rand."""
    dd, st, ik, _a = _dorp(tmp_path)
    k = _kanaal()
    _post(dd, k, "mijn eigen zin", "ik@nooch.earth")
    html = render_messages(cockpit2._Stores(dd), ik=ik.id, kanaal=k, csrf_token="t")
    assert "class='qadd-form msg-bewerk'" in html
    assert ".qadd-form textarea{" in CSS.replace("\n", "")


# ── 3. Bewerken en verwijderen: de poort ────────────────────────────────────────────────────
def _teksten(dd, k):
    return [e.get("text") for e in cockpit2._Stores(dd).channels.trail(k)]


def test_je_bewerkt_je_eigen_bericht(tmp_path):
    dd, st, ik, _a = _dorp(tmp_path)
    k = _kanaal()
    _post(dd, k, "eerste poging", "ik@nooch.earth")
    eid = cockpit2._Stores(dd).channels.trail(k)[-1]["id"]
    cockpit2.dispatch(dd, "msg_edit", {"kanaal": [k], "item": [eid], "tekst": ["tweede poging"],
                                       "next": ["/messages"]}, username="ik@nooch.earth")
    assert _teksten(dd, k) == ["tweede poging"]


def test_een_ander_bewerkt_jouw_bericht_niet(tmp_path):
    """DE POORT ZIT IN DE STORE, niet in het scherm. Dit is een POST zoals iemand hem met de
    hand kan sturen: de knop staat er niet, en dat mag niet het enige zijn dat hem tegenhoudt."""
    dd, st, ik, _a = _dorp(tmp_path)
    k = _kanaal()
    _post(dd, k, "mijn woorden", "ik@nooch.earth")
    eid = cockpit2._Stores(dd).channels.trail(k)[-1]["id"]
    _nxt, msg = cockpit2.dispatch(dd, "msg_edit",
                                  {"kanaal": [k], "item": [eid], "tekst": ["gestolen woorden"],
                                   "next": ["/messages"]}, username="ander@nooch.earth")
    assert _teksten(dd, k) == ["mijn woorden"]
    assert msg.startswith("✗")


def test_je_verwijdert_je_eigen_bericht(tmp_path):
    dd, st, ik, _a = _dorp(tmp_path)
    k = _kanaal()
    _post(dd, k, "weg hiermee", "ik@nooch.earth")
    eid = cockpit2._Stores(dd).channels.trail(k)[-1]["id"]
    cockpit2.dispatch(dd, "msg_remove", {"kanaal": [k], "item": [eid], "next": ["/messages"]},
                      username="ik@nooch.earth")
    assert _teksten(dd, k) == []


def test_een_ander_verwijdert_jouw_bericht_niet(tmp_path):
    dd, st, ik, _a = _dorp(tmp_path)
    k = _kanaal()
    _post(dd, k, "blijft staan", "ik@nooch.earth")
    eid = cockpit2._Stores(dd).channels.trail(k)[-1]["id"]
    _nxt, msg = cockpit2.dispatch(dd, "msg_remove",
                                  {"kanaal": [k], "item": [eid], "next": ["/messages"]},
                                  username="ander@nooch.earth")
    assert _teksten(dd, k) == ["blijft staan"]
    assert msg.startswith("✗")


def test_een_lege_bewerking_doet_niets(tmp_path):
    """Fail-closed, net als `post`: een leeg bericht bestaat niet, dus een bewerking naar leeg
    is geen verwijdering maar een fout."""
    dd, st, ik, _a = _dorp(tmp_path)
    k = _kanaal()
    _post(dd, k, "blijft zoals het is", "ik@nooch.earth")
    eid = cockpit2._Stores(dd).channels.trail(k)[-1]["id"]
    cockpit2.dispatch(dd, "msg_edit", {"kanaal": [k], "item": [eid], "tekst": ["   "],
                                       "next": ["/messages"]}, username="ik@nooch.earth")
    assert _teksten(dd, k) == ["blijft zoals het is"]


def test_een_bericht_van_een_rol_is_van_niemand(tmp_path):
    """Een rol schrijft ook in kanalen. Die berichten horen bij geen mens, dus er is niemand
    die ze mag bewerken — ook niet de mens die de rol vervult."""
    dd, st, ik, _a = _dorp(tmp_path)
    k = _kanaal()
    st.channels.post(k, "namens de rol", author_type="role", author_id=ik.id)
    eid = cockpit2._Stores(dd).channels.trail(k)[-1]["id"]
    cockpit2.dispatch(dd, "msg_edit", {"kanaal": [k], "item": [eid], "tekst": ["gekaapt"],
                                       "next": ["/messages"]}, username="ik@nooch.earth")
    assert _teksten(dd, k) == ["namens de rol"]


# ── 4. Allebei de achterkanten ──────────────────────────────────────────────────────────────
def test_het_werkt_ook_in_een_projectkanaal(tmp_path):
    """Een projectkanaal woont in `project["log"]` via de ledger, niet in channels.json. Zonder
    deze test dekt alles hierboven maar één van de twee opslagplekken — en dan staan de knoppen
    op een projectkanaal wel op het scherm en doen ze niets."""
    dd, st, ik, _a = _dorp(tmp_path)
    pid = st.projects.create("mother_earth", "Een project met een gesprek", "human")
    k = channels.project_kanaal(pid)
    _post(dd, k, "eerste poging", "ik@nooch.earth")
    eid = cockpit2._Stores(dd).channels.trail(k)[-1]["id"]
    cockpit2.dispatch(dd, "msg_edit", {"kanaal": [k], "item": [eid], "tekst": ["tweede poging"],
                                       "next": ["/messages"]}, username="ik@nooch.earth")
    assert "tweede poging" in _teksten(dd, k)
    cockpit2.dispatch(dd, "msg_remove", {"kanaal": [k], "item": [eid], "next": ["/messages"]},
                      username="ik@nooch.earth")
    assert "tweede poging" not in _teksten(dd, k)


def test_de_twee_nieuwe_schrijfacties_staan_onder_het_slot():
    """`JsonStore._WRITE_METHODS` is de lijst die de schrijf-lock zet. Een schrijfmethode die
    er niet in staat schrijft zonder lock — precies het gat dat de JsonStore-fase dichtte."""
    assert "bewerk" in channels.ChannelStore._WRITE_METHODS
    assert "verwijder" in channels.ChannelStore._WRITE_METHODS
