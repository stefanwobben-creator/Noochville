"""De merk-stickers en het Giphy-zoekveld eronder.

TWEE DINGEN MOETEN HARD ZIJN, en ze zijn van een andere orde:

  1. DE SLEUTEL BLIJFT OP DE SERVER. `GIPHY_API_KEY` mag nergens in een pagina of in een
     JSON-antwoord terechtkomen. Alles wat de browser kan lezen kan iedereen lezen die de
     pagina opent;
  2. DE VASTE RIJ IS NIET AFHANKELIJK VAN GIPHY. Geen sleutel, geen netwerk of een stukke
     Giphy mag de stickerkiezer niet meenemen — het zoekveld valt stil, de rij blijft staan.
     Daarom is `zoek()` fail-soft en geeft de route 200 met een lege lijst in plaats van 5xx.

DE SCOPE WAS EEN GRENS EN IS ER GEEN MEER. Dit zocht eerst alleen in `@Nooch_Earth`; dat kanaal
bevat op productie één GIF, dus het zoekveld vond structureel niets. Sinds 22 september 2026 is
het publiek Giphy (founder-besluit) — zie sectie 5. De verdedigingen bij het DOWNLOADEN staan
daar los van en zijn allemaal blijven staan.
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


GOLDEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden",
                      "stickers_referentie.png")
#: Gemiddeld kleurverschil per pixel (0-255) dat een sticker mag afwijken van zijn bron.
#: Gekalibreerd op 22 september 2026: de negen goede liggen op 0,05-2,49; de kapotte ronde
#: (index 0 als 'doorzichtig') gaf 6,9 · 11,9 · 26,6 · 30,2 · 99,1 · 182,2 op zes van de negen.
#: Alles tussen 2,5 en 6,9 zou dus een nieuw soort afwijking zijn en hoort zich te melden.
MAX_AFWIJKING = 6.0


def test_de_stickers_zijn_nog_animaties():
    for naam in cockpit2.STICKERS:
        with Image.open(os.path.join(STATIC, naam)) as im:
            assert getattr(im, "n_frames", 1) > 1, f"{naam} is geen animatie meer"
            assert max(im.size) <= 240, f"{naam} is {im.size}"


def test_geen_sticker_ziet_er_anders_uit_dan_zijn_bron():
    """DE ENIGE TEST DIE DE ECHTE FOUT HAD GEVANGEN.

    De eerste optimalisatieronde haalde de bestandsgrootte wél en het beeld niet: index 0
    aanwijzen als 'doorzichtig' maakte van de globe een zwart vlak, van de peace-hand iets
    cyaans en van i-love-nooch onleesbare pap. Elke cap op bytes was daar groen op gebleven.

    EN DE TWEEDE POGING TOETSTE NIETS OP CI. Die vergeleek rechtstreeks met
    `claude/stickers_22sept/`, en die map staat niet in git: op de runner werd élk bestand
    overgeslagen. Hij viel om op zijn eigen ondergrens-assert (`gemeten >= 5`) — dat was de
    enige reden dat het opviel in plaats van stil groen te blijven.

    Vandaar een golden file: `tests/golden/stickers_referentie.png`, 30 kB, geschreven door
    `scripts/stickers_optimaliseren.py --apply` uit de BRONNEN. Geen hand-getypte lijst, en
    hij reist mee met de repo."""
    from PIL import ImageChops
    assert os.path.exists(GOLDEN), "golden file ontbreekt — draai scripts/stickers_optimaliseren.py --apply"
    with Image.open(GOLDEN) as ref:
        ref = ref.convert("RGB")
        t = ref.height
        assert ref.width == t * len(cockpit2.STICKERS), (
            f"referentie heeft {ref.width // t} tegels, er zijn {len(cockpit2.STICKERS)} stickers "
            "— draai scripts/stickers_optimaliseren.py --apply opnieuw")
        for i, naam in enumerate(cockpit2.STICKERS):
            verwacht = ref.crop((i * t, 0, (i + 1) * t, t))
            nu = _tegel(os.path.join(STATIC, naam), t)
            hist = ImageChops.difference(verwacht, nu).convert("L").histogram()
            afw = sum(w * n for w, n in enumerate(hist)) / (t * t)
            assert afw <= MAX_AFWIJKING, (
                f"{naam} wijkt {afw:.1f} af van zijn bron (max {MAX_AFWIJKING}) — het bestand is "
                "misschien klein genoeg, maar het ZIET er anders uit")


def _tegel(pad: str, grootte: int):
    """Zelfde duimnagel als `scripts/stickers_optimaliseren.tegel`. Bewust hier herhaald en niet
    geïmporteerd: een test die zijn meetlat uit de code haalt die hij toetst, meet niets."""
    with Image.open(pad) as im:
        im.seek(0)
        f = im.convert("RGBA")
        f.thumbnail((grootte, grootte), Image.LANCZOS)
    vel = Image.new("RGBA", (grootte, grootte), (255, 255, 255, 255))
    vel.paste(f, ((grootte - f.width) // 2, (grootte - f.height) // 2), f)
    return vel.convert("RGB")


def test_de_whitelist_laat_geen_pad_ontsnappen():
    """De statische route joint de naam op de map. De whitelist is wat dat veilig maakt, dus
    daar mag nooit iets met een schuine streep of puntjes in staan."""
    for naam in cockpit2.STICKERS:
        assert "/" not in naam and ".." not in naam and naam.endswith(".gif")


# ── 2. Wat een bruikbare treffer is ─────────────────────────────────────────────────────────
# DE EIGENAARSCHECK IS WEG (22 september 2026): hij bestond om alleen het merkkanaal door te
# laten, en dat is precies wat verviel. Zie sectie 5. Wat blijft is de check op het BEELD —
# die gaat niet over wie het maakte maar over of we er iets mee kunnen.
def test_een_treffer_zonder_bruikbaar_beeld_valt_af():
    assert giphy._treffer({"id": "4", "images": {}}) is None
    # http:// telt niet: een onbeveiligde bron op een https-pagina laadt toch niet.
    assert giphy._treffer({"id": "5", "images": {"original": {"url": "http://media/x.gif"}}}) is None
    # ... en een goede komt er wél door, ongeacht de uploader
    ok = giphy._treffer({"id": "6", "user": {"username": "wie_dan_ook"}, "title": "Donut",
                         "images": {"fixed_height_small": {"url": "https://media.giphy.com/x.gif"}}})
    assert ok["id"] == "6" and ok["naam"] == "Donut"


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
        {"id": "ok", "user": {"username": "wie_dan_ook"}, "title": "Walking donut",
         "images": {"fixed_height_small": {"url": "https://media.giphy.com/d.gif"}}},
        {"id": "weg", "user": {"username": "vreemde"}, "images": {}},   # geen bruikbaar beeld
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
        {"id": "ok", "images": {"fixed_height_small": {"url": "https://media.giphy.com/d.gif"}}}]}).encode()
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


# ── 5. De zoekscope is publiek Giphy geworden (22 september 2026) ───────────────────────────
# WAS: alleen het merkkanaal `Nooch_Earth`. Dat kanaal bevat op productie precies één GIF, dus
# het zoekveld vond voor bijna elke term niets — gemeten bij de deploy: "donut" 0, "shoe" 0,
# het hele kanaal 1. Founder-besluit: verbreden naar heel publiek Giphy, zoals een gewone
# GIF-kiezer. Wat NIET verandert zijn de downloadverdedigingen; die stonden er niet voor de
# merkscope maar tegen een adres dat de server gaat ophalen.
def test_een_term_buiten_het_merkkanaal_levert_nu_wel_iets_op(monkeypatch):
    """DE TEST DIE HET PROBLEEM VASTLEGT. Giphy geeft hier een treffer van een willekeurige
    uploader terug — precies het geval dat de oude eigenaarscheck wegfilterde en waardoor er
    voor "donut" niets te vinden was."""
    monkeypatch.setenv("GIPHY_API_KEY", "test")
    lichaam = json.dumps({"data": [
        {"id": "pub1", "user": {"username": "iemand_anders"}, "title": "Walking donut",
         "images": {"fixed_height_small": {"url": "https://media.giphy.com/d.gif"}}},
        {"id": "pub2", "title": "Donut zonder uploader",
         "images": {"fixed_height_small": {"url": "https://media.giphy.com/e.gif"}}},
    ]}).encode()
    monkeypatch.setattr(giphy.urllib.request, "urlopen", _nep(lichaam))
    hits = giphy.zoek("donut")
    assert [h["id"] for h in hits] == ["pub1", "pub2"], hits


def test_de_zoekterm_gaat_kaal_naar_giphy():
    """De `@Nooch_Earth`-prefix zat in de VRAAG en niet alleen in de filtering; blijft hij
    staan, dan zoekt Giphy nog steeds binnen dat kanaal en verandert er niets."""
    url = giphy._url("donut", "SLEUTEL", 8)
    assert "Nooch_Earth" not in url
    assert "q=donut" in url


def test_de_contentfilter_blijft_staan():
    """`rating=g` is de CONTENTfilter en staat los van de kanaalscope. Die verdwijnt niet mee."""
    assert "rating=g" in giphy._url("donut", "SLEUTEL", 8)


def test_haal_blijft_het_adres_zelf_opzoeken(monkeypatch):
    """HET ID-PAD BLIJFT. Dat bestond niet voor de merkscope maar omdat de client anders bepaalt
    welk adres deze server ophaalt. Alleen de eigenaarscheck erin verviel."""
    monkeypatch.setenv("GIPHY_API_KEY", "sleutel")
    lichaam = json.dumps({"data": {"id": "x1", "user": {"username": "vreemde"}, "title": "Iets",
                                   "images": {"original": {"url": "https://media.giphy.com/x.gif"}}}}).encode()
    monkeypatch.setattr(giphy.urllib.request, "urlopen", _nep(lichaam))
    t = giphy.haal("x1")
    assert t and t["url"] == "https://media.giphy.com/x.gif"


def test_de_downloadverdedigingen_zijn_ongemoeid(monkeypatch):
    """Vier dingen die niets met de merkscope te maken hebben en dus moesten blijven: alleen
    https, alleen `*.giphy.com`, een harde bovengrens die we ZELF tellen, en de magic bytes van
    een GIF. Hier alle vier in één test, zodat een latere opruiming ze niet los kan laten
    sneuvelen."""
    geprobeerd = []

    def nep_weigering(req, **k):
        geprobeerd.append(getattr(req, "full_url", req))
        raise AssertionError("dit adres had nooit opgehaald mogen worden")
    monkeypatch.setattr(giphy.urllib.request, "urlopen", nep_weigering)
    assert giphy.download("http://media.giphy.com/x.gif") is None      # geen https
    assert giphy.download("https://evil.example/x.gif") is None        # ander domein
    assert geprobeerd == [], geprobeerd

    class Antwoord:
        def __init__(self, data):
            self.data = data
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self, n=None): return self.data[:n] if n else self.data

    # te groot: we lezen cap+1 en weigeren zodra het er meer zijn dan de cap
    groot = b"GIF89a" + b"x" * 200
    monkeypatch.setattr(giphy.urllib.request, "urlopen", lambda *a, **k: Antwoord(groot))
    assert giphy.download("https://media.giphy.com/x.gif", cap=100) is None
    # geen GIF, ongeacht de naam
    monkeypatch.setattr(giphy.urllib.request, "urlopen", lambda *a, **k: Antwoord(b"<html>nope"))
    assert giphy.download("https://media.giphy.com/x.gif") is None
    # en een echte GIF komt er wél door
    monkeypatch.setattr(giphy.urllib.request, "urlopen", lambda *a, **k: Antwoord(b"GIF89a" + b"x" * 20))
    assert giphy.download("https://media.giphy.com/x.gif") == b"GIF89a" + b"x" * 20
