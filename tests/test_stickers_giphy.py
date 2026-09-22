"""De merk-stickers en het Giphy-zoekveld eronder.

TWEE DINGEN MOETEN HARD ZIJN, en ze zijn van een andere orde:

  1. DE SLEUTEL BLIJFT OP DE SERVER. `GIPHY_API_KEY` mag nergens in een pagina of in een
     JSON-antwoord terechtkomen. Alles wat de browser kan lezen kan iedereen lezen die de
     pagina opent;
  2. DE VASTE RIJ IS NIET AFHANKELIJK VAN GIPHY. Geen sleutel, geen netwerk of een stukke
     Giphy mag de stickerkiezer niet meenemen — het zoekveld valt stil, de rij blijft staan.
     Daarom is `zoek()` fail-soft en geeft de route 200 met een lege lijst in plaats van 5xx.

EN ÉÉN DING DAT GEEN TEST MAAR EEN GRENS IS: de scope. We vragen scoped (`@Nooch_Earth` in de
zoekterm) én controleren het antwoord op `user.username`. Alleen vragen is niet genoeg — de
zoek-API bepaalt zelf wat hij relevant vindt, en één los GIF'je van een vreemde in de
stickerkiezer van een merk is precies wat je niet wil.
"""
from __future__ import annotations

import http.client
import json
import os
import threading
from http.server import HTTPServer

from PIL import Image

from nooch_village import auth as _auth
from nooch_village import cockpit2, giphy
from nooch_village.people import PeopleStore

EMAIL = "sticker@nooch.earth"
STATIC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "nooch_village", "static", "stickers")
CAP = 300 * 1024


# ── 1. De vaste rij ─────────────────────────────────────────────────────────────────────────
def test_er_staan_stickers_en_ze_worden_geserveerd():
    assert cockpit2.STICKERS, "geen stickers gevonden in static/stickers"
    for naam in cockpit2.STICKERS:
        assert cockpit2._STATIC_TYPES.get("stickers/" + naam) == "image/gif"


def test_geen_sticker_boven_de_cap():
    """DE AANLEIDING MET HET GETAL ERBIJ: de globe was 5,0 MB en de set 10 MB. Een rij boven een
    tekstvak die 10 MB ophaalt is geen kiezer maar een download. Deze grens is dezelfde als
    `scripts/stickers_optimaliseren.py` aanhoudt; hij hoort hier zodat een nieuwe sticker die
    er ongeoptimaliseerd in glipt zich meldt."""
    te_groot = [(n, os.path.getsize(os.path.join(STATIC, n)) // 1024)
                for n in cockpit2.STICKERS
                if os.path.getsize(os.path.join(STATIC, n)) > CAP]
    assert not te_groot, f"boven {CAP // 1024} kB: {te_groot} — draai scripts/stickers_optimaliseren.py"


def test_de_hele_rij_blijft_onder_twee_megabyte():
    totaal = sum(os.path.getsize(os.path.join(STATIC, n)) for n in cockpit2.STICKERS)
    assert totaal < 2 * 1024 * 1024, f"{totaal // 1024} kB voor de hele rij"


BRON = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "claude", "stickers_22sept")


def _alfa_minimum(pad: str) -> int:
    """De doorzichtigste pixel van het eerste frame. 0 = er is écht doorzichtigheid, 255 = dekkend."""
    with Image.open(pad) as im:
        im.seek(0)
        return im.convert("RGBA").getchannel("A").getextrema()[0]


def test_de_stickers_zijn_nog_animaties():
    for naam in cockpit2.STICKERS:
        with Image.open(os.path.join(STATIC, naam)) as im:
            assert getattr(im, "n_frames", 1) > 1, f"{naam} is geen animatie meer"
            assert max(im.size) <= 240, f"{naam} is {im.size}"


def test_doorzichtigheid_blijft_waar_hij_er_was():
    """De eerste optimalisatieronde haalde de bestandsgrootte wél en het BEELD niet: index 0
    aanwijzen als 'doorzichtig' maakte van de globe een zwart vlak en van de peace-hand iets
    cyaans. Een cap op bytes alleen zou dat groen hebben gelaten.

    GEMETEN OP HET BEELD, NIET OP EEN VLAGGETJE. `info["transparency"]` zegt alleen dat er een
    index is aangewezen; twee van de negen originelen hebben die vlag terwijl geen enkele pixel
    doorzichtig is (friday-dance, walking-sneakers), en die vlag laat Pillow dan terecht vallen.
    Wat telt is of de pixels die doorzichtig wáren dat nog zijn."""
    gemeten = 0
    for naam in cockpit2.STICKERS:
        bron = os.path.join(BRON, naam)
        if not os.path.exists(bron) or _alfa_minimum(bron) != 0:
            continue                                   # origineel was dekkend: niets te bewaren
        gemeten += 1
        assert _alfa_minimum(os.path.join(STATIC, naam)) == 0, \
            f"{naam} heeft zijn doorzichtige achtergrond verloren"
    assert gemeten >= 5, f"maar {gemeten} stickers met doorzichtigheid — zegt deze test nog iets?"


def test_de_whitelist_laat_geen_pad_ontsnappen():
    """De statische route joint de naam op de map. De whitelist is wat dat veilig maakt, dus
    daar mag nooit iets met een schuine streep of puntjes in staan."""
    for naam in cockpit2.STICKERS:
        assert "/" not in naam and ".." not in naam and naam.endswith(".gif")


# ── 2. De scope: alleen het merkkanaal ──────────────────────────────────────────────────────
def test_de_vraag_is_gescoped_op_het_merkkanaal():
    url = giphy._url("donut", "SLEUTEL", 8)
    assert "%40Nooch_Earth+donut" in url or "%40Nooch_Earth%20donut" in url


def test_een_treffer_van_iemand_anders_valt_af():
    beeld = {"fixed_height_small": {"url": "https://media.giphy.com/x.gif"}}
    assert giphy._treffer({"id": "1", "user": {"username": giphy.GIPHY_USER},
                           "images": beeld, "title": "Donut"})["id"] == "1"
    assert giphy._treffer({"id": "2", "user": {"username": "vreemde"}, "images": beeld}) is None
    assert giphy._treffer({"id": "3", "images": beeld}) is None          # helemaal geen eigenaar


def test_een_treffer_zonder_bruikbaar_beeld_valt_af():
    assert giphy._treffer({"id": "4", "user": {"username": giphy.GIPHY_USER}, "images": {}}) is None
    # http:// telt niet: een onbeveiligde bron op een https-pagina laadt toch niet.
    assert giphy._treffer({"id": "5", "user": {"username": giphy.GIPHY_USER},
                           "images": {"original": {"url": "http://media/x.gif"}}}) is None


# ── 3. Fail-soft ────────────────────────────────────────────────────────────────────────────
def test_zonder_sleutel_valt_het_zoekveld_stil(monkeypatch):
    monkeypatch.delenv("GIPHY_API_KEY", raising=False)
    assert giphy.zoek("donut") == []


def test_een_stukke_giphy_geeft_een_lege_lijst(monkeypatch):
    monkeypatch.setenv("GIPHY_API_KEY", "test")

    def kapot(*a, **k):
        raise OSError("geen netwerk")
    monkeypatch.setattr(giphy.urllib.request, "urlopen", kapot)
    assert giphy.zoek("donut") == []


def test_onzin_van_giphy_geeft_een_lege_lijst(monkeypatch):
    """Niet alleen een netwerkfout: een 200 met iets anders erin mag ook niets omver halen."""
    monkeypatch.setenv("GIPHY_API_KEY", "test")
    for lichaam in (b"geen json", b'{"data": "geen lijst"}', b"{}", b"[]"):
        monkeypatch.setattr(giphy.urllib.request, "urlopen", _nep(lichaam))
        assert giphy.zoek("donut") == []


def test_een_goed_antwoord_komt_er_wel_door(monkeypatch):
    """Mutatie-controle op de drie tests hierboven: die zouden ook slagen als `zoek` altijd
    leeg teruggaf."""
    monkeypatch.setenv("GIPHY_API_KEY", "test")
    lichaam = json.dumps({"data": [
        {"id": "ok", "user": {"username": giphy.GIPHY_USER}, "title": "Walking donut",
         "images": {"fixed_height_small": {"url": "https://media.giphy.com/d.gif"}}},
        {"id": "weg", "user": {"username": "vreemde"},
         "images": {"fixed_height_small": {"url": "https://media.giphy.com/v.gif"}}},
    ]}).encode()
    monkeypatch.setattr(giphy.urllib.request, "urlopen", _nep(lichaam))
    hits = giphy.zoek("donut")
    assert [h["id"] for h in hits] == ["ok"]
    assert hits[0]["naam"] == "Walking donut"


class _nep:
    """Minimale stand-in voor `urlopen` als contextmanager."""

    def __init__(self, lichaam: bytes):
        self.lichaam = lichaam

    def __call__(self, *a, **k):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self.lichaam


# ── 4. De route ─────────────────────────────────────────────────────────────────────────────
def _server(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    ps = PeopleStore(os.path.join(dd, "people.json"))
    p = ps.add("Sticker Sam", EMAIL)
    ps.set_password(p.id, _auth.hash_password("geheim1234"), must_change=False)
    sessions = _auth.SessionStore()
    tok = sessions.create(EMAIL)
    httpd = HTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, "TESTTOKEN", sessions=sessions))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1], tok


def _get(port, pad, cookie=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request("GET", pad, headers=({"Cookie": f"nv_session={cookie}"} if cookie else {}))
    r = conn.getresponse()
    body = r.read()
    ctype = r.getheader("Content-Type") or ""
    conn.close()
    return r.status, ctype, body


def test_de_route_geeft_200_met_een_lege_lijst_als_giphy_uit_staat(tmp_path, monkeypatch):
    """GEEN 5XX. Een stickerkiezer die rood wordt omdat een dienst van derden hapert is erger
    dan een zoekveld dat niets vindt."""
    monkeypatch.delenv("GIPHY_API_KEY", raising=False)
    httpd, port, tok = _server(tmp_path)
    try:
        status, ctype, body = _get(port, "/giphy-zoek?q=donut", cookie=tok)
        assert status == 200 and ctype.startswith("application/json")
        assert json.loads(body)["hits"] == []
    finally:
        httpd.shutdown()


def test_de_sleutel_komt_niet_mee_naar_buiten(tmp_path, monkeypatch):
    monkeypatch.setenv("GIPHY_API_KEY", "GEHEIME-SLEUTEL-XYZ")
    lichaam = json.dumps({"data": [
        {"id": "ok", "user": {"username": giphy.GIPHY_USER},
         "images": {"fixed_height_small": {"url": "https://media.giphy.com/d.gif"}}}]}).encode()
    monkeypatch.setattr(giphy.urllib.request, "urlopen", _nep(lichaam))
    httpd, port, tok = _server(tmp_path)
    try:
        _s, _c, body = _get(port, "/giphy-zoek?q=donut", cookie=tok)
        assert b"GEHEIME-SLEUTEL-XYZ" not in body
        assert json.loads(body)["hits"][0]["url"] == "https://media.giphy.com/d.gif"
    finally:
        httpd.shutdown()


def test_de_route_zit_achter_de_login(tmp_path):
    httpd, port, _tok = _server(tmp_path)
    try:
        status, _c, _b = _get(port, "/giphy-zoek?q=donut")
        assert status in (302, 303, 403), status
    finally:
        httpd.shutdown()


def test_een_sticker_wordt_echt_geserveerd(tmp_path):
    httpd, port, tok = _server(tmp_path)
    try:
        naam = cockpit2.STICKERS[0]
        status, ctype, body = _get(port, "/static/stickers/" + naam, cookie=tok)
        assert status == 200 and ctype == "image/gif"
        assert body[:6] in (b"GIF87a", b"GIF89a")
        assert len(body) == os.path.getsize(os.path.join(STATIC, naam))
    finally:
        httpd.shutdown()


def test_een_bestand_buiten_de_map_wordt_niet_geserveerd(tmp_path):
    httpd, port, tok = _server(tmp_path)
    try:
        for pad in ("/static/stickers/../nooch.css", "/static/stickers/geenbestand.gif"):
            status, _c, _b = _get(port, pad, cookie=tok)
            assert status == 404, pad
    finally:
        httpd.shutdown()
