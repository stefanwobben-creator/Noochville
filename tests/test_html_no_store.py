"""HTML wordt nooit bewaard, statics juist wel (27 september 2026).

HET GAT. De cockpit stuurde op HTML géén enkele cache-header: geen `Cache-Control`, geen `ETag`,
geen `Last-Modified`. Een browser mag dan HEURISTISCH cachen, en bij terug/vooruit-navigatie
(bfcache) krijg je gegarandeerd de oude pagina terug.

WAT DAT KOSTTE, en waarom het erger is dan "een oude versie zien": het CSS-token `--w-smal-form`
staat in de INLINE `<style>` van de HTML, terwijl de klasse die hem gebruikt in de gecachte
`nooch.css` zit. Oude HTML + nieuwe CSS = `max-width:var(--w-smal-form)` verwijst naar niets, en
dan gooit CSS de héle declaratie weg: de kolom staat weer op volle breedte. Dat leest als "de
deploy is niet doorgekomen" terwijl de server allang het nieuwe serveert.

DEZE TOETS IS EEN RATCHET, en hij werkt op het HELE oppervlak en niet op één view: de routes
worden UIT DE BRON GELEZEN (`path == "/…"` in `cockpit2.py`) en stuk voor stuk echt opgevraagd
tegen een draaiende handler. Een nieuwe view komt er dus vanzelf bij — je kunt hem niet vergeten
toe te voegen, want niemand voegt hem toe.
"""
from __future__ import annotations

import http.client
import pathlib
import re
import tempfile
import threading
from http.server import ThreadingHTTPServer

import pytest

from nooch_village import auth as _auth
from nooch_village import cockpit2

BRON = (pathlib.Path(__file__).resolve().parents[1] / "nooch_village" / "cockpit2.py").read_text()

#: Routes die geen HTML-document zijn: downloads, fragmenten en binaire streams. Die vallen
#: buiten de regel, en ze staan hier met naam zodat "buiten de regel" een KEUZE is en geen
#: vergeetachtigheid.
GEEN_DOCUMENT = {
    "/bijlage", "/file", "/static",          # bestanden en assets
    "/giphy-zoek", "/md-preview",            # fragmenten voor een al geladen pagina
    # `/logout` VERNIETIGT DE SESSIE, en de fixture deelt er één over de hele module. Hem
    # meenemen betekende dat elke route NÁ hem alleen nog een 303 naar /login gaf — de sweep bleef
    # groen maar mat niets meer. Gevonden doordat deze toets alleen in de VOLLE run viel en los
    # slaagde; zijn redirect wordt hieronder apart getoetst.
    "/logout",
}


def _routes() -> list[str]:
    """Alle GET-routes, uit de bron. Dit is wat de ratchet automatisch laat meegroeien."""
    gevonden = sorted(set(re.findall(r'path == "(/[a-z0-9_-]*)"', BRON)))
    return [r for r in gevonden if r not in GEEN_DOCUMENT]


@pytest.fixture(scope="module")
def server():
    dd = tempfile.mkdtemp()
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    mens = st.people.add("Cache Tester", "cache@test.nl")
    st.people.set_password(mens.id, _auth.hash_password("geheim123"), must_change=False)
    st.people.backfill_must_change()
    for p in st.people.all():                      # must_change blokkeert anders elke pagina
        st.people.set_password(p.id, _auth.hash_password("geheim123"), must_change=False)

    import os
    sessions = _auth.SessionStore(os.path.join(dd, "sessions.json"))
    users = _auth.UserStore(os.path.join(dd, "people.json"))
    handler = cockpit2.make_handler(dd, "TOK", sessions, users)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    httpd.daemon_threads = True
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    # MET EEN SESSIE, want zonder redirect elke route naar /login en meet deze ratchet alleen nog
    # de 303 — niet de GERENDERDE HTML waar het om gaat. Dat was de eerste versie, en een mutatie
    # die `no-store` uit `_send` haalde bleef daardoor grotendeels groen.
    token = sessions.create("cache@test.nl")
    yield httpd.server_address, f"{_auth.SESSION_COOKIE}={token}"
    httpd.shutdown()


def _haal(server, pad: str, *, ingelogd: bool = True):
    adres, cookie = server
    c = http.client.HTTPConnection(*adres, timeout=10)
    c.request("GET", pad, headers={"Cookie": cookie} if ingelogd else {})
    r = c.getresponse()
    r.read()
    c.close()
    return r.status, {k.lower(): v for k, v in r.getheaders()}


# ══ De regel, over het hele oppervlak ════════════════════════════════════════
def test_er_zijn_routes_gevonden():
    """Zou de bron-scan stukgaan, dan slagen alle toetsen hieronder op nul routes."""
    r = _routes()
    assert len(r) >= 30, r


@pytest.mark.parametrize("pad", _routes())
def test_elke_html_respons_stuurt_no_store(server, pad):
    """DE REGEL ZELF, niet de routelijst: alles wat een DOCUMENT teruggeeft — HTML of een
    redirect — draagt `no-store`.

    Een route die zonder queryparameter 404't (`/context` wil een `id`) levert `text/plain` en is
    geen document; die valt er dus buiten. Dat is geen uitzondering maar dezelfde regel, precies
    gelezen."""
    status, h = _haal(server, pad)
    soort = (h.get("content-type") or "")
    if not (soort.startswith("text/html") or status in (301, 302, 303, 307, 308)):
        pytest.skip(f"{pad} → {status} {soort or 'geen content-type'} (geen document)")
    assert h.get("cache-control") == "no-store", (pad, status, h.get("cache-control"))


def test_de_sweep_raakt_echt_gerenderde_paginas(server):
    """DE TOETS OP DE TOETS. Zou de sessie niet pakken, dan meet de sweep hierboven alleen
    redirects naar /login — en dan is de ratchet een lege huls die groen blijft terwijl
    `_send` de header niet meer zet. Precies dat gebeurde in de eerste versie hiervan."""
    html = [p for p in _routes()
            if _haal(server, p)[1].get("content-type", "").startswith("text/html")]
    assert len(html) >= 10, f"maar {len(html)} van de {len(_routes())} leverden HTML: {html}"


def test_ook_de_redirect_naar_login(server):
    """Elke schrijfactie eindigt in een 303, en een gecachte redirect stuurt je morgen naar het
    adres van gisteren — inclusief de `?msg=` van een handeling die je niet net deed."""
    status, h = _haal(server, "/acties", ingelogd=False)
    assert status == 303
    assert h.get("cache-control") == "no-store"


def test_ook_de_uitlog_redirect(server):
    """Apart, want hij zit niet in de sweep (zie `GEEN_DOCUMENT`) — en juist een uitlog-redirect
    wil je nooit uit de cache terugkrijgen."""
    status, h = _haal(server, "/logout")
    assert status in (302, 303)
    assert h.get("cache-control") == "no-store"


def test_de_loginpagina_zelf_ook(server):
    status, h = _haal(server, "/login", ingelogd=False)
    assert status == 200 and h["content-type"].startswith("text/html")
    assert h.get("cache-control") == "no-store"


# ══ Statics blijven juist wél cachebaar ══════════════════════════════════════
def test_een_static_houdt_zijn_lange_cache(server):
    """DE ANDERE HELFT VAN DE REGEL. `nooch.css` draagt een inhoud-hash in zijn URL, dus nieuwe
    inhoud = nieuwe URL = verse download. `no-store` daarop zou elke pagina zijn stylesheet
    opnieuw laten halen, voor niets."""
    status, h = _haal(server, "/static/nooch.css")
    if status == 303:                                   # statics zitten achter login
        pytest.skip("statics zijn hier achter auth; de header is getoetst op de bron hieronder")
    assert "max-age" in (h.get("cache-control") or ""), h.get("cache-control")
    assert "no-store" not in (h.get("cache-control") or "")


def test_de_static_route_zet_geen_no_store():
    """Bron-kant van dezelfde regel, zodat hij ook geldt als statics achter auth blijven."""
    stuk = BRON.split("def _send_bytes(")[1].split("def ")[0]
    assert 'f"public, max-age={cache_secs}"' in stuk
    assert "no-store" not in stuk


# ══ De vorm zelf ═════════════════════════════════════════════════════════════
def test_er_is_maar_een_plek_die_html_stuurt():
    """DE REDEN DAT ÉÉN REGEL VOLSTAAT. Zou er een tweede HTML-uitgang bijkomen, dan zegt deze
    toets dat — en dan moet die de header ook zetten."""
    assert BRON.count('send_header("Content-Type", "text/html') == 1


def test_die_plek_zet_de_header():
    stuk = BRON.split("def _send(")[1].split("def _schrijf(")[0]
    assert 'send_header("Cache-Control", "no-store")' in stuk


def test_de_redirect_helper_ook():
    stuk = BRON.split("def _redirect_to(")[1].split("def ")[0]
    assert 'send_header("Cache-Control", "no-store")' in stuk


def test_de_uitzonderingen_staan_met_naam():
    """"Buiten de regel" hoort een keuze te zijn, geen vergeetachtigheid: elke uitzondering staat
    in `GEEN_DOCUMENT` en is dus op te zoeken."""
    alle = set(re.findall(r'path == "(/[a-z0-9_-]*)"', BRON))
    assert GEEN_DOCUMENT <= alle | {"/static"}, GEEN_DOCUMENT - alle
