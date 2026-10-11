"""De gedeelde chrome — SINDS B1 (11 oktober 2026) weer één zijbalk, zonder header.

B1 VOLGT HET PROTOTYPE V2 (`claude/prototype_v2_vormgeving_live.html`): merk, een zoekknop ("Search
or jump to", toets `/`), de twee meetings, de hoofditems, Admin en Organization, en onderaan de
gebruiker. De header die hieronder beschreven staat (september 2026) is vervallen; de tests die hem
vastlegden zijn omgezet naar de nieuwe vorm. Wat bleef: de paneel-knoppen, de hamburger, de
initialen met de volle naam.

WAT ER TOEN VERANDERDE (historie):

WAT ER VERANDERT. `_nav()` rendert alles in één `<aside class='c2-side'>`: logo, zoekbalk,
begroeting, navigatie-items, en onderaan de twee overleg-pillen. Het prototype splitst dat:

  * een STICKY HEADER bovenaan met het logo links, het globale zoekveld in het midden en
    rechts een avatar met initialen die naar je eigen persoonspagina wijst — in plaats van de
    tekstuele "Hoi Stefan";
  * de zijbalk houdt alléén navigatie, en de twee overleg-pillen verhuizen van ONDERAAN naar
    BOVENAAN: dat is de snelle ingang naar een lopend overleg.

DRIE DINGEN DIE NIET IN HET PROTOTYPE ZITTEN en die wél moeten blijven werken, want het is een
statische mockup: de paneel-knoppen (Projects/Circle/Organization openen een uitklap via
`data-nav-paneel` en zijn dus een `<button>`, geen link), de mobiele hamburger (`navToggle()`
klapt de zijbalk in en uit), en de live-zoek (`_GS_LIVE_JS` hangt aan `#gs-input`/`#gs-drop`).
Die drie staan hieronder als aparte tests, niet als aanname.

Dit raakt gedeelde chrome die ~40 views aanroepen. Geen enkele view verandert; alleen `_nav()`
en de CSS eromheen.
"""
from __future__ import annotations

import os
import re

from nooch_village.cockpit2_util import (_nav, _SIDE_ITEMS,
                                         _SIDE_OVERLEG, _initials)

BASIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS = open(os.path.join(BASIS, "nooch_village", "static", "nooch.css"), encoding="utf-8").read()
NU = open(os.path.join(BASIS, "nooch_village", "static", "nooch.css"), encoding="utf-8").read()


def _regels(css: str, met_media: bool = False):
    kaal = re.sub(r"/\*.*?\*/", " ", css, flags=re.S)
    if not met_media:
        kaal = re.sub(r"@media[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", " ", kaal)
    return {re.sub(r"\s+", " ", s.strip()): b
            for sel, b in re.findall(r"([^{}]+)\{([^{}]*)\}", kaal) for s in sel.split(",")}


def _tussen(html: str, start: str, eind: str) -> str:
    return html.split(start, 1)[1].split(eind, 1)[0]


# ── 1. De splitsing ─────────────────────────────────────────────────────────────────────────
def test_merk_zoekknop_en_gebruiker_staan_in_de_zijbalk():
    html = _nav()
    zij = _tussen(html, "<aside class='c2-side'>", "</aside>")
    for stuk in ("c2-logo", "id='c2-zoek'", "c2-subnav", "c2-av"):
        assert stuk in zij, stuk
    # de volgorde van het prototype: merk, zoeken, meetings, navigatie, gebruiker onderaan
    assert zij.index("c2-logo") < zij.index("id='c2-zoek'") < zij.index(_SIDE_OVERLEG) \
        < zij.index("href='/projects'") < zij.index("c2-av")

def test_de_zoekknop_is_zonder_js_een_link_naar_de_zoekpagina():
    """Voorwaarde Stefan (B1): zonder JS linkt de zoekknop naar /search, en daar staat een veld."""
    from nooch_village.views.search import render_search
    html = _nav()
    knop = _tussen(html, "id='c2-zoek'", "</a>")
    assert "href='/search'" in knop and "aria-haspopup='dialog'" in knop
    assert "name='q'" in render_search(None, "")

def test_er_is_geen_header_meer():
    html = _nav()
    assert "<header" not in html and "c2-header" not in html

def test_de_overleg_pillen_staan_bovenaan():
    """Ze stonden ONDER de nav-items, achter een scheiding. Nu erboven: dat is de snelle ingang
    naar een lopend overleg."""
    html = _nav()
    zij = _tussen(html, "<aside class='c2-side'>", "</aside>")
    eerste_item = min(zij.index(h) for h, _l, _p in _SIDE_ITEMS)
    assert zij.index(_SIDE_OVERLEG) < eerste_item


# ── 2. De avatar ────────────────────────────────────────────────────────────────────────────
def test_de_begroeting_is_een_avatar_geworden():
    html = _nav()
    assert "Hoi" not in html
    assert "c2-greet" not in html
    assert "id='c2-av'" in html


def test_de_avatar_krijgt_de_initialen_en_de_volledige_naam(tmp_path):
    """Voor- én achternaam ("SW"), met de volle naam in title en aria-label en dezelfde link
    naar /person?id=… die de begroeting had."""
    from nooch_village import auth as _auth
    from nooch_village import cockpit2
    import http.client
    import threading
    from http.server import HTTPServer
    from nooch_village.people import PeopleStore

    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    ps = PeopleStore(os.path.join(dd, "people.json"))
    # EEN NAAM DIE NIET AL IN DE SEED STAAT. `people.add` ontdubbelt op NAAM, dus "Stefan
    # Wobben" toevoegen levert de bestaande seed-persoon terug — mét diens e-mailadres, en dan
    # vindt de sessie niemand. Dat kostte me hier een kwartier, dus het staat erbij.
    p = ps.add("Wanda Vermeulen", "wv@nooch.earth")
    assert p.email == "wv@nooch.earth", "naam botst alsnog met de seed"
    ps.set_password(p.id, _auth.hash_password("geheim1234"), must_change=False)
    sessions = _auth.SessionStore()
    tok = sessions.create("wv@nooch.earth")
    httpd = HTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, "T", sessions=sessions))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=10)
        conn.request("GET", "/projects", headers={"Cookie": f"nv_session={tok}"})
        html = conn.getresponse().read().decode("utf-8", "replace")
        conn.close()
    finally:
        httpd.shutdown()
    av = re.search(r"<a class='c2-av'([^>]*)>([^<]*)</a>", html)
    assert av, "geen gevulde avatar in de header"
    assert f"/person?id={p.id}" in av.group(1)
    assert "Wanda Vermeulen" in av.group(1)               # title/aria-label
    assert av.group(2).strip() == "WV"
    assert _initials("Stefan Wobben") == "SW"             # voor- én achternaam, zoals het prototype


# ── 3. Wat niet stuk mag: paneel, hamburger, live-zoek ──────────────────────────────────────
def test_de_paneelknoppen_houden_hun_hele_contract():
    """Circle en Organization openen een uitklap. Het mechanisme hangt aan drie dingen tegelijk —
    `data-nav-paneel` (welk paneel), `aria-expanded` (de stand) en `aria-controls` (waar het
    landt) — plus de `href` als val-terug zonder JS. Alle vier, want met drie ervan werkt hij half.

    PROJECTS STOND HIER, tot hij op 23 september 2026 een gewone paginasprong werd (het paneel gaf
    een lijst terwijl `/projects` het bord is). Alleen `org` komt nog uit `_nav()` zelf — `ci` is
    cirkel-afhankelijk en wordt door `_send` ingevuld, zie de assert onderaan."""
    html = _nav()
    for paneel, href in (("org", "/node"),):
        el = re.search(rf"<a [^>]*data-nav-paneel='{paneel}'[^>]*>", html)
        assert el, paneel
        assert "aria-expanded=" in el.group(0) and "aria-controls='c2-paneel'" in el.group(0)
        assert f"href='{href}'" in el.group(0), paneel
    # HIER STOND CIRCLE, als plaatshouder die `_send` per verzoek invulde. Weg op 23 september
    # 2026: een cirkel is een rol die rollen bevat, dus wat hij toonde was altijd een deel van de
    # organisatieboom. Wat cirkel-afhankelijk BLIJFT zijn de twee overleg-knoppen.
    assert _SIDE_OVERLEG in html
    assert "id='c2-paneel'" in html                       # en het doelwit staat er ook


def test_de_hamburger_staat_buiten_de_zijbalk():
    """Anders verdwijnt de knop samen met wat hij opent. Hij staat vóór de zijbalk, zodat hij op
    beide standen bereikbaar blijft."""
    html = _nav()
    assert html.index("c2-burger") < html.index("<aside class='c2-side'>")
    assert "navToggle()" in html

def test_slash_doet_niets_in_een_veld_tekstvak_of_bewerkbaar_vlak():
    """Voorwaarde Stefan (B1): `/` opent het zoeken, maar niet terwijl je typt."""
    html = _nav()
    for stuk in ("tag==='input'", "tag==='textarea'", "isContentEditable", "getElementById('c2-zoek')"):
        assert stuk in html, stuk

# ── 4. De stijl ─────────────────────────────────────────────────────────────────────────────
def test_de_header_regels_zijn_weg():
    """Geen dode CSS: de header bestaat niet meer, dus ook geen regel die hem aankleedt."""
    assert not [sel for sel in _regels(CSS, met_media=True) if ".c2-header" in sel]

def test_de_zijbalk_begint_bovenaan():
    """Er is geen header meer om onder te beginnen."""
    zij = _regels(CSS).get(".c2-side", "").replace(" ", "")
    assert "top:0" in zij, zij

def test_de_zijbalk_toont_geen_zoek_of_begroeting_meer_op_mobiel():
    """De mobiele regel verstopte `.c2-search` en `.c2-greet` IN de balk. Die staan er niet
    meer, dus die uitzondering hoort ook weg — anders blijft er een regel staan die niets doet."""
    mobiel = _regels(CSS, met_media=True)
    for sel, decl in mobiel.items():
        if sel.startswith(".c2-side .c2-search") or sel.startswith(".c2-side .c2-greet"):
            raise AssertionError(f"dode mobiele regel: {sel} → {decl}")

def test_het_open_mobiele_menu_laat_de_hamburger_vrij():
    """De opengeklapte balk vult het scherm (er is geen header meer), maar begint ONDER de
    hamburger (40px op 10px): anders lag hij over de knop waarmee je hem weer dicht doet."""
    mobiel = _regels(CSS, met_media=True)
    decl = mobiel.get("body.navjs.navopen .c2-side", "").replace(" ", "")
    assert "top:0" in decl and "padding-top:3.6rem" in decl, decl

def test_het_open_menu_toont_woorden_en_geen_monogrammen():
    """De rail-regels verbergen `.c2-lbl` en tonen het monogram — dat klopt voor een balk van
    64px. De opengeklapte versie is het hele scherm breed, en dan stond er "PR ME WI CI AD OR"
    onder elkaar."""
    mobiel = _regels(CSS, met_media=True)
    assert "display:inline" in mobiel.get("body.navjs.navopen .c2-side .c2-lbl", "").replace(" ", "")
    assert "display:none" in mobiel.get("body.navjs.navopen .c2-side .c2-mono", "").replace(" ", "")
