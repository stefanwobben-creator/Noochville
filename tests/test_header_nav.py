"""De gedeelde chrome, gesplitst in een horizontale header en een kale zijbalk.

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
NU = open(os.path.join(BASIS, "nooch_village", "static", "nooch-ui.css"), encoding="utf-8").read()


def _regels(css: str, met_media: bool = False):
    kaal = re.sub(r"/\*.*?\*/", " ", css, flags=re.S)
    if not met_media:
        kaal = re.sub(r"@media[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", " ", kaal)
    return {re.sub(r"\s+", " ", s.strip()): b
            for sel, b in re.findall(r"([^{}]+)\{([^{}]*)\}", kaal) for s in sel.split(",")}


def _tussen(html: str, start: str, eind: str) -> str:
    return html.split(start, 1)[1].split(eind, 1)[0]


# ── 1. De splitsing ─────────────────────────────────────────────────────────────────────────
def test_logo_zoek_en_profiel_staan_in_de_header():
    html = _nav()
    kop = _tussen(html, "<header class='c2-header'>", "</header>")
    for stuk in ("c2-logo", "c2-search", "gs-input", "c2-av"):
        assert stuk in kop, stuk


def test_de_zijbalk_houdt_alleen_navigatie():
    """Alles wat naar de header ging, hoort daar niet meer te staan — anders staat het er twee
    keer en is de "één bron"-regel van deze functie stuk."""
    html = _nav()
    zij = _tussen(html, "<aside class='c2-side'>", "</aside>")
    for stuk in ("c2-logo", "c2-search", "gs-input", "c2-greet"):
        assert stuk not in zij, stuk
    assert "c2-subnav" in zij


def test_de_header_staat_vóór_de_zijbalk():
    html = _nav()
    assert html.index("<header class='c2-header'>") < html.index("<aside class='c2-side'>")


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
    """Anders verdwijnt de knop samen met wat hij opent. Hij staat vóór de header én vóór de
    zijbalk, zodat hij op beide standen bereikbaar blijft."""
    html = _nav()
    assert html.index("c2-burger") < html.index("<header class='c2-header'>")
    assert "navToggle()" in html


def test_de_live_zoek_hangt_nog_aan_hetzelfde_veld():
    """`_GS_LIVE_JS` is niet herschreven, alleen verplaatst: hij zoekt `#gs-input` en `#gs-drop`
    en die moeten er dus nog precies zo zijn."""
    html = _nav()
    assert "id='gs-input'" in html and "id='gs-drop'" in html
    assert "getElementById('gs-input')" in html and "getElementById('gs-drop')" in html
    assert "/search?frag=1&q=" in html


# ── 4. De stijl ─────────────────────────────────────────────────────────────────────────────
def test_de_header_is_sticky_en_draagt_de_zwarte_onderrand():
    per = _regels(CSS)
    kop = per.get(".c2-header", "")
    assert "position:sticky" in kop.replace(" ", "")
    assert "top:0" in kop.replace(" ", "")
    assert "height:56px" in kop.replace(" ", "")
    # De 2px zwarte lijn zit in het TOKEN `--nu-border` (= 2px solid var(--nu-text)); die naam
    # is de bron, de kleur erachter niet iets om hier over te typen.
    nu = _regels(NU).get(".nu .c2-header", "")
    assert "border-bottom: var(--nu-border)" in nu, nu


def test_de_zijbalk_begint_onder_de_header():
    """Hij is `position:fixed` en zou anders ONDER de sticky header door lopen."""
    zij = _regels(CSS).get(".c2-side", "").replace(" ", "")
    assert "top:56px" in zij, zij


def test_de_zijbalk_toont_geen_zoek_of_begroeting_meer_op_mobiel():
    """De mobiele regel verstopte `.c2-search` en `.c2-greet` IN de balk. Die staan er niet
    meer, dus die uitzondering hoort ook weg — anders blijft er een regel staan die niets doet."""
    mobiel = _regels(CSS, met_media=True)
    for sel, decl in mobiel.items():
        if sel.startswith(".c2-side .c2-search") or sel.startswith(".c2-side .c2-greet"):
            raise AssertionError(f"dode mobiele regel: {sel} → {decl}")

def test_het_mobiele_menu_valt_niet_over_de_header():
    """GEMETEN, NIET BEDACHT. De opengeklapte balk stond eerst op `inset:0` en lag dus óver de
    sticky header: je zag het menu wél, maar logo, zoek, profiel én de hamburger waarmee je het
    weer dicht zou doen verdwenen eronder. Hij begint nu op dezelfde hoogte als de header —
    56px, hetzelfde getal als `.c2-header{height}`."""
    mobiel = _regels(CSS, met_media=True)
    kop_hoogte = re.search(r"height:\s*(\d+)px", _regels(CSS)[".c2-header"]).group(1)
    for sel in (".c2-side", "body.navjs.navopen .c2-side"):
        decl = mobiel.get(sel, "")
        assert decl, sel
        top = re.search(r"top:\s*(\d+)px", decl)
        assert top and top.group(1) == kop_hoogte, (sel, decl)


def test_het_open_menu_toont_woorden_en_geen_monogrammen():
    """De rail-regels verbergen `.c2-lbl` en tonen het monogram — dat klopt voor een balk van
    64px. De opengeklapte versie is het hele scherm breed, en dan stond er "PR ME WI CI AD OR"
    onder elkaar."""
    mobiel = _regels(CSS, met_media=True)
    assert "display:inline" in mobiel.get("body.navjs.navopen .c2-side .c2-lbl", "").replace(" ", "")
    assert "display:none" in mobiel.get("body.navjs.navopen .c2-side .c2-mono", "").replace(" ", "")
