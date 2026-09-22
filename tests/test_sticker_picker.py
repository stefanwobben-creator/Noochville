"""De stickerkiezer onder het schrijfveld: de eigen stickers, en zoeken in Giphy.

DRIE DINGEN MOETEN HARD ZIJN:

  1. DE VASTE RIJ IS NIET AFHANKELIJK VAN GIPHY. Acht formulieren die er al staan, één per
     sticker — dus ook zonder JavaScript en ook als Giphy eruit ligt. Alleen het vak eronder
     valt dan stil. Daarom staan de twee helften los, en niet in één lijst;
  2. ER REIST GEEN URL MEE. Bij het kiezen van een Giphy-treffer gaat alleen het ID naar de
     server; die zoekt het adres er zelf bij, toetst opnieuw of de eigenaar het merkkanaal is,
     en weigert elk adres buiten `*.giphy.com`. Zou de client de URL meesturen, dan bepaalt de
     client wat deze server ophaalt — elk intern adres, elk bestand achter de firewall;
  3. EEN GIPHY-STICKER KRIJGT DEZELFDE BEHANDELING als de eigen acht. Niet "ook een keer
     verkleinen", maar letterlijk dezelfde functie (`stickers.optimaliseer_bytes`), want twee
     paden geven binnen een maand twee formaten.

DE UITZONDERING VOOR `friday-dance.gif` IS VERVALLEN (22 september 2026). Hij stond één ronde
buiten de kiezer omdat zijn herkomst onbevestigd was; Stefan heeft bevestigd dat hij van Nooch
is. De filterlijst is daarmee wég en niet leeg: een lege lijst laat de vraag "wanneer vul ik
hier iets in?" openstaan, en die heeft geen antwoord meer.
"""
from __future__ import annotations

import io
import os

from PIL import Image

from nooch_village import channels, cockpit2, giphy, stickers
from nooch_village.views.messages import render_messages

CSRF = "TESTTOKEN"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    ik = st.people.add("Sticker Sam", "sam@nooch.earth")
    return dd, cockpit2._Stores(dd), ik.id


def _kanaal():
    return channels.circle_kanaal("mother_earth")


def _html(tmp_path):
    dd, st, ik = _dorp(tmp_path)
    return dd, st, ik, render_messages(st, ik=ik, kanaal=_kanaal(), csrf_token=CSRF)


# ── 1. De vaste rij ─────────────────────────────────────────────────────────────────────────
def test_alles_wat_er_ligt_staat_in_de_kiezer(tmp_path):
    """WAS: acht van de negen, met `friday-dance` eruit. Nu alle negen — en de kiezer telt wat
    er in de map ligt, zodat een nieuwe sticker er vanzelf bij komt."""
    _dd, _st, _ik, html = _html(tmp_path)
    assert cockpit2.STICKERS_PICKER == cockpit2.STICKERS
    assert html.count("value='sticker_post'") == len(cockpit2.STICKERS)
    assert "friday-dance" in html


def test_elke_sticker_is_een_eigen_formulier_dus_zonder_js(tmp_path):
    """De reden dat dit acht formulieren zijn en geen JS-lijst: zo werkt de rij ook als er geen
    JavaScript draait, en als Giphy eruit ligt."""
    _dd, _st, _ik, html = _html(tmp_path)
    blok = html.split("class='emoji-pop emo-st'")[1].split("</details>")[0]
    for naam in cockpit2.STICKERS_PICKER:
        assert f"value='{naam}'" in blok
        assert f"/static/stickers/{naam}" in blok


def _diepste_formulier(html: str) -> int:
    """De grootste nesting-diepte van <form> op de pagina. 1 = alle formulieren liggen naast
    elkaar, 2 = er zit er een IN een ander."""
    from html.parser import HTMLParser

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


def test_geen_formulier_in_een_formulier(tmp_path):
    """EEN <form> IN EEN <form> IS GEEN HTML: de browser gooit de binnenste weg en je klikt op
    een knop die niets doet. De kiezer draagt acht eigen formulieren en de paperclip ook, dus
    ze horen naast het schrijfformulier en niet erin.

    DE EERSTE VERSIE VAN DEZE TEST MAT HET VERKEERDE ELEMENT. Die knipte de pagina op
    `class='qadd-form'` en pakte stuk [1] — maar het BIJLAGE-formulier draagt diezelfde klasse,
    dus hij keek naar de paperclip en niet naar het schrijfveld. Hij bleef groen met de kiezer
    netjes ín het schrijfformulier gezet; een mutatie-controle liet dat zien. Nu geteld op de
    echte structuur, over de hele pagina, met een parser in plaats van met string-knippen."""
    _dd, _st, _ik, html = _html(tmp_path)
    assert _diepste_formulier(html) == 1


def test_zonder_schrijfrecht_geen_kiezer(tmp_path):
    """Zelfde poort als het antwoordveld. Staat er geen veld, dan ook geen stickers."""
    dd, st, ik = _dorp(tmp_path)
    html = render_messages(st, ik="", kanaal=_kanaal(), csrf_token=CSRF)
    assert "sticker_post" not in html


# ── 2. Plaatsen ─────────────────────────────────────────────────────────────────────────────
def test_een_eigen_sticker_wordt_niet_gekopieerd(tmp_path):
    """DE ACHT STAAN IN HET PAKKET. Ze per bericht naar data/ schrijven zou dezelfde 100 kB bij
    elke high-five nog een keer opleveren; de bijlage verwijst dus naar `stickers/<naam>`."""
    dd, st, ik = _dorp(tmp_path)
    naam = cockpit2.STICKERS_PICKER[0]
    _nxt, msg = cockpit2.dispatch(dd, "sticker_post",
                                  {"kanaal": [_kanaal()], "naam": [naam]},
                                  username="sam@nooch.earth")
    assert "sticker" in msg
    trail = cockpit2._Stores(dd).channels.trail(_kanaal())
    b = trail[-1]["bijlagen"][0]
    assert b["stored"] == "stickers/" + naam
    assert not os.path.exists(os.path.join(dd, "kanaalbijlagen"))


def test_een_naam_die_niet_in_de_kiezer_staat_wordt_geweigerd(tmp_path):
    """DE POORT BLIJFT, OOK NU ER NIETS MEER IS TERUGGETROKKEN. Een POST hoort niet te kunnen
    kiezen wat het scherm niet aanbiedt — dat is hier een bestand dat er niet is, en het zou
    morgen weer een teruggetrokken sticker kunnen zijn."""
    dd, st, ik = _dorp(tmp_path)
    for naam in ("bestaat-niet.gif", "../nooch.css", ""):
        _nxt, msg = cockpit2.dispatch(dd, "sticker_post",
                                      {"kanaal": [_kanaal()], "naam": [naam]},
                                      username="sam@nooch.earth")
        assert msg.startswith("✗"), naam
    assert cockpit2._Stores(dd).channels.trail(_kanaal()) == []


def test_de_kiezer_heeft_precies_dezelfde_poort_als_het_antwoordveld(tmp_path):
    """DE REGEL IS "dezelfde poort als het antwoordveld", dus dat is wat hier wordt gemeten:
    voor dezelfde kanalen dezelfde uitkomst als `msg_post`, niet een eigen strengere of
    soepelere lijst.

    Inclusief het geval dat je misschien anders zou verwachten: een cirkelkanaal van een
    cirkel die niet bestaat mag bij ALLEBEI. Dat is bestaand gedrag van de gesprekslaag en
    geen gat dat de stickerkiezer introduceert — zou ik het hier dichtzetten, dan zaten de
    twee poorten uit elkaar en was "dezelfde poort" alleen nog een zin in een docstring."""
    dd, st, ik = _dorp(tmp_path)
    vreemde_dm = channels.dm_kanaal(
        st.people.add("A", "a@n.nl").id, st.people.add("B", "b@n.nl").id)
    for kanaal in (vreemde_dm, "onzin:kanaal", "circle:bestaat_niet"):
        _n, bericht = cockpit2.dispatch(dd, "msg_post", {"kanaal": [kanaal], "tekst": ["x"]},
                                        username="sam@nooch.earth")
        _n, sticker = cockpit2.dispatch(dd, "sticker_post",
                                        {"kanaal": [kanaal],
                                         "naam": [cockpit2.STICKERS_PICKER[0]]},
                                        username="sam@nooch.earth")
        assert bericht.startswith("✗") == sticker.startswith("✗"), (
            f"{kanaal}: bericht={bericht!r} sticker={sticker!r}")


def test_je_blijft_na_het_plaatsen_in_het_gesprek(tmp_path):
    """GEVONDEN DOOR TE KLIKKEN. De eerste versie stuurde je na een sticker naar het
    projectenbord: het formulier droeg geen `next`, `dispatch` zet die dan op "/", en de
    `or`-terugval eronder ging daardoor nooit aan — "/" is waar. De test dekte het PLAATSEN
    wel en de bestemming niet."""
    dd, st, ik = _dorp(tmp_path)
    nxt, _msg = cockpit2.dispatch(dd, "sticker_post",
                                  {"kanaal": [_kanaal()], "naam": [cockpit2.STICKERS_PICKER[0]]},
                                  username="sam@nooch.earth")
    assert nxt.startswith("/messages") and "mother_earth" in nxt
    # En met een expliciete `next` die ergens anders heen wijst: ook dan het gesprek in.
    nxt2, _ = cockpit2.dispatch(dd, "sticker_post",
                                {"kanaal": [_kanaal()], "next": ["/projects"],
                                 "naam": [cockpit2.STICKERS_PICKER[0]]},
                                username="sam@nooch.earth")
    assert nxt2.startswith("/messages")


def test_het_formulier_draagt_de_terugweg(tmp_path):
    _dd, _st, _ik, html = _html(tmp_path)
    blok = html.split("class='emoji-pop emo-st'")[1].split("</details>")[0]
    assert blok.count("name='next'") == len(cockpit2.STICKERS_PICKER)


# ── 3. Giphy: alleen een id, en dezelfde verkleining ────────────────────────────────────────
def _gif_bytes(zijde=400, frames=12) -> bytes:
    fr = []
    for i in range(frames):
        im = Image.new("RGB", (zijde, zijde), (i * 20 % 255, 80, 200 - i * 10 % 200))
        fr.append(im.convert("P", palette=Image.ADAPTIVE, colors=256))
    b = io.BytesIO()
    fr[0].save(b, format="GIF", save_all=True, append_images=fr[1:], duration=80, loop=0)
    return b.getvalue()


def test_de_giphy_knop_stuurt_een_id_en_geen_url(tmp_path, monkeypatch):
    """Het formulier dat de JS bouwt draagt `gif`, niet `url`. Getoetst op de bron van dat
    formulier, want hij bestaat alleen in de browser."""
    js = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "nooch_village", "static", "nooch.js"), encoding="utf-8").read()
    blok = js.split("function giphyZoek")[1].split("function stickers")[0]
    assert "name='gif'" in blok
    assert "name='url'" not in blok and 'name="url"' not in blok
    assert "giphy_post" in blok


def test_een_gekozen_giphy_sticker_wordt_verkleind_en_bewaard(tmp_path, monkeypatch):
    dd, st, ik = _dorp(tmp_path)
    ruw = _gif_bytes()
    monkeypatch.setattr(giphy, "haal", lambda gid, **k: {
        "id": gid, "url": "https://media.giphy.com/media/x/giphy.gif", "naam": "Walking Donut"})
    monkeypatch.setattr(giphy, "download", lambda url, **k: ruw)
    _nxt, msg = cockpit2.dispatch(dd, "giphy_post",
                                  {"kanaal": [_kanaal()], "gif": ["abc123"]},
                                  username="sam@nooch.earth")
    assert msg.startswith("🏷"), msg
    b = cockpit2._Stores(dd).channels.trail(_kanaal())[-1]["bijlagen"][0]
    pad = os.path.join(dd, b["stored"])
    assert os.path.exists(pad) and b["stored"].startswith("kanaalbijlagen/")
    assert b["size"] < len(ruw), "niet verkleind"
    with Image.open(pad) as im:
        assert max(im.size) <= 240, f"niet naar stickerformaat gebracht: {im.size}"


def test_dezelfde_verkleining_als_de_eigen_rij(tmp_path, monkeypatch):
    """NIET 'ook een keer verkleinen' MAAR DEZELFDE FUNCTIE. Als deze twee uit elkaar lopen,
    ziet een Giphy-sticker er na één wijziging anders uit dan de acht ernaast."""
    dd, st, ik = _dorp(tmp_path)
    ruw = _gif_bytes()
    gezien = {}
    echt = stickers.optimaliseer_bytes
    monkeypatch.setattr(stickers, "optimaliseer_bytes",
                        lambda data, **k: gezien.setdefault("uit", echt(data, **k)))
    monkeypatch.setattr(giphy, "haal", lambda gid, **k: {
        "id": gid, "url": "https://media.giphy.com/x.gif", "naam": "x"})
    monkeypatch.setattr(giphy, "download", lambda url, **k: ruw)
    cockpit2.dispatch(dd, "giphy_post", {"kanaal": [_kanaal()], "gif": ["a"]},
                      username="sam@nooch.earth")
    assert gezien.get("uit"), "optimaliseer_bytes is niet aangeroepen"


def test_giphy_uit_plaatst_niets_en_zegt_waarom(tmp_path, monkeypatch):
    dd, st, ik = _dorp(tmp_path)
    monkeypatch.setattr(giphy, "haal", lambda gid, **k: None)
    _nxt, msg = cockpit2.dispatch(dd, "giphy_post", {"kanaal": [_kanaal()], "gif": ["a"]},
                                  username="sam@nooch.earth")
    assert msg.startswith("✗") and "Nooch" in msg
    assert cockpit2._Stores(dd).channels.trail(_kanaal()) == []


def test_download_weigert_alles_buiten_giphy(monkeypatch):
    """De URL komt uit `haal()` en niet uit de browser, en tóch ligt hij tegen een lijst: een
    adres dat de server gaat ophalen hoort getoetst te worden op wat het IS, niet op waar het
    vandaan kwam.

    DE EERSTE VERSIE BEWEES NIETS. Die riep `download` gewoon aan en keek of er None uitkwam —
    maar op een machine zonder netwerk komt er óók None uit als de hostcontrole helemaal weg
    is. Hij bleef groen met die controle uitgeschakeld. Nu wordt geteld of `urlopen` überhaupt
    is aangeroepen: een geweigerd adres hoort de deur niet uit te gaan."""
    geprobeerd = []

    def nep(req, **k):
        geprobeerd.append(getattr(req, "full_url", req))
        raise AssertionError("dit adres had nooit opgehaald mogen worden")
    monkeypatch.setattr(giphy.urllib.request, "urlopen", nep)
    for slecht in ("https://evil.example/x.gif",                  # ander domein
                   "http://media.giphy.com/x.gif",                # geen https
                   "https://media.giphy.com.evil.test/x.gif",     # lijkt erop, is het niet
                   "https://127.0.0.1/x.gif",                     # intern adres
                   ""):
        assert giphy.download(slecht) is None, slecht
    assert geprobeerd == [], f"server ging tóch op pad naar {geprobeerd}"


def test_download_haalt_een_echte_giphy_url_wel_op(monkeypatch):
    """Mutatie-controle op de test hierboven: die zou ook slagen als `download` nooit iets
    ophaalde."""
    gif = _gif_bytes(zijde=40, frames=2)

    class Antwoord:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self, n=None): return gif
    monkeypatch.setattr(giphy.urllib.request, "urlopen", lambda *a, **k: Antwoord())
    assert giphy.download("https://media3.giphy.com/media/x/giphy.gif") == gif


def test_haal_stuurt_alleen_alfanumerieke_ids(monkeypatch):
    """Het id belandt in een URL. Een id met een `&` of een `/` erin zou er parameters bij
    kunnen plakken."""
    monkeypatch.setenv("GIPHY_API_KEY", "sleutel")
    gezien = {}

    def nep(req, **k):
        gezien["url"] = req.full_url
        raise OSError("stop hier")
    monkeypatch.setattr(giphy.urllib.request, "urlopen", nep)
    giphy.haal("abc/../123&api_key=anders")
    # Alles wat geen letter of cijfer is valt weg, dus de schuine strepen, de punten en de `&`.
    # Wat overblijft is één pad-segment en precies één `api_key`: die van ons.
    assert gezien["url"] == "https://api.giphy.com/v1/gifs/abc123apikeyanders?api_key=sleutel"
    assert gezien["url"].count("api_key=") == 1


# ── 4. Serveren ─────────────────────────────────────────────────────────────────────────────
def test_een_eigen_sticker_wordt_uit_het_pakket_geserveerd(tmp_path):
    """`stored` wijst naar `stickers/<naam>` en niet naar data/. De route moet dat weten, en
    op LIDMAATSCHAP toetsen — niet op een pad-join, want dan is er iets te ontsnappen."""
    dd, st, ik = _dorp(tmp_path)
    naam = cockpit2.STICKERS_PICKER[0]
    cockpit2.dispatch(dd, "sticker_post", {"kanaal": [_kanaal()], "naam": [naam]},
                      username="sam@nooch.earth")
    st2 = cockpit2._Stores(dd)
    b = st2.channels.trail(_kanaal())[-1]["bijlagen"][0]
    from nooch_village.views.messages import _bijlagen_html
    html = _bijlagen_html(st2.channels.trail(_kanaal())[-1], _kanaal())
    assert f"id={b['id']}" in html and "msg-bijlage--beeld" in html
    # En hij staat als STICKER in de draad: kleiner, zonder kader. Het onderscheid komt uit de
    # meta en niet uit een gok op het pad — een Giphy-sticker ligt in dezelfde map als een foto.
    assert b.get("soort") == "sticker"
    assert "msg-bijlage--sticker" in html


def test_een_gewone_afbeelding_wordt_geen_sticker(tmp_path):
    """Mutatie-controle: de regel hierboven zou ook slagen als élke afbeelding als sticker
    rendert, en dan krijgt een gedeelde foto ineens 160px en geen kader."""
    from nooch_village.views.messages import _bijlagen_html
    entry = {"id": "e1", "bijlagen": [{"id": "b1", "name": "foto.png", "stored": "x/foto.png",
                                       "size": 10, "mime": "image/png"}]}
    html = _bijlagen_html(entry, _kanaal())
    assert "msg-bijlage--beeld" in html and "msg-bijlage--sticker" not in html
