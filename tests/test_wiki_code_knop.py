"""De inline-code-knop in de werkbalk (25 september 2026).

VERVOLG OP PR 1. Daar kreeg `_md` de enkele backtick; wat ontbrak was een manier om hem te maken
zonder het teken zelf te typen. Deze knop stond in mijn ontwerp bij PR 1 en is bewust doorgeschoven
naar hier: er is GEEN `execCommand` voor inline code, dus hij vraagt eigen JS én een gemeten
browser-uitkomst voor de guard in `test_wiki_inline_editor` — en die meet je in een browser, niet
aan een bureau.

HET ENIGE ITEM IN DE WERKBALK DAT WIJ ZELF MAKEN. Vandaar de naam `nvCode` en niet `code`: wie
`bold` leest weet dat de browser het doet, wie `nvCode` leest weet dat wij het doen. `nooch.js`
vangt hem af vóór de `execCommand`-regel.

WAT DE METING ERBIJ OPLEVERDE, en dat is de reden dat deze knop meer is dan drie regels. Chrome
vervangt bij `insertHTML` de spaties NAAST de invoeging door een harde spatie:

    Een&nbsp;<code>gewone</code>&nbsp;alinea met wat tekst erin.

De rondgang overleeft dat — gecontroleerd — maar in de opgeslagen markdown staat dan een
ONZICHTBAAR ander teken dan de schrijver typte. Dat is precies het soort stille vervuiling dat hier
al twee keer is opgeruimd: de tien pagina's met `\\r`, en de spatie die in het taak-blok bij elke
bewerkronde aangroeide. `ontharde()` haalt daarom de randtekens weg — alléén de randtekens, want
een harde spatie midden in een zin kan iemand bewust hebben geplakt.
"""
from __future__ import annotations

import pathlib

from nooch_village.cockpit2_util import _OPMAAK_KNOPPEN, _md, _md_naar_bron, opmaak_werkbalk

JS = (pathlib.Path(__file__).resolve().parents[1]
      / "nooch_village" / "static" / "nooch.js").read_text()


def _fn(naam: str) -> str:
    return JS.split(f"function {naam}")[1].split("\n  function ")[0]


# ── 1. De knop bestaat en zegt wat hij doet ──────────────────────────────────
def test_de_werkbalk_heeft_een_code_knop():
    cmds = {cmd for cmd, _arg, _label, _titel in _OPMAAK_KNOPPEN if cmd}
    assert "nvCode" in cmds


def test_de_knop_draagt_een_titel():
    """Zonder titel is `</>`-icoon een raadsel."""
    titels = {cmd: titel for cmd, _a, _l, titel in _OPMAAK_KNOPPEN if cmd}
    assert titels["nvCode"] == "Inline code"


def test_de_knop_staat_in_de_gerenderde_werkbalk():
    html = opmaak_werkbalk()
    assert "data-wiki-cmd='nvCode'" in html
    assert "title='Inline code'" in html


def test_de_naam_maakt_zichtbaar_dat_wij_hem_maken():
    """Elke andere knop is een browser-commando. Een naam als `code` zou suggereren dat
    `execCommand` hem kent — die bestaat niet, en dan zoek je bij een bug op de verkeerde plek."""
    browser_cmds = {cmd for cmd, _a, _l, _t in _OPMAAK_KNOPPEN if cmd and not cmd.startswith("nv")}
    assert "code" not in browser_cmds


# ── 2. De JS-tak ─────────────────────────────────────────────────────────────
def test_de_knop_loopt_niet_langs_execcommand():
    """Er is geen browser-commando voor inline code; `execCommand('nvCode')` zou stilletjes niets
    doen — een knop die niets doet, en dat merk je pas als je hem gebruikt."""
    handler = JS.split("tb.querySelectorAll")[1][:700]
    assert 'wikiCmd === "nvCode"' in handler
    assert "inlineCode()" in handler


def test_zonder_selectie_gebeurt_er_niets():
    """Een lege code-chip is niets waard en staat wel in de bron."""
    fn = _fn("inlineCode")
    assert "if (!tekst) return;" in fn


def test_binnen_een_codeblok_doet_de_knop_niets():
    """Daar is elk teken al letterlijk, en een `<code>` ín een `<pre><code>` is precies de vorm
    die `_md_naar_bron` bewust negeert — dan zou de inhoud verdwijnen. Zelfde grens als in `_md`,
    een laag hoger."""
    fn = _fn("inlineCode")
    # OP `<code>` EN NIET OP `<pre>`. Die eerste versie liet
    # `test_javascript_draagt_geen_eigen_soorten_lijst` vallen, en terecht: `pre` staat in
    # `BLOK_SOORTEN` en `nooch.js` mag geen bloktags bij naam noemen. Het was bovendien
    # overbodig — `_md` rendert een codeblok altijd als `<pre><code>`, dus elke selectie
    # erbinnen zit ook in een `<code>`, en dát is de schade: een `<code>` in een `<code>`.
    assert 'closest("code")' in fn
    assert 'closest("pre")' not in fn, "nooch.js noemt een bloktag bij naam"
    assert "data-blok-bron" in fn, "het bron-bewerkvlak is ook tekst, geen opmaak"


def test_de_geselecteerde_tekst_wordt_geescaped():
    """Wat je selecteert is TEKST. Stond er `<b>` in en plakken we hem rauw terug, dan maakt de
    browser er opmaak van die de schrijver nooit typte. Gemeten in Chrome: de code-inhoud is
    daarna letterlijk `<b>dit</b>` en er staat geen echte `<b>` in het blok."""
    fn = _fn("inlineCode")
    for teken in ("&amp;", "&lt;", "&gt;"):
        assert teken in fn, f"{teken} wordt niet ge-escaped"


def test_de_harde_spatie_van_de_browser_gaat_eruit():
    """DE VONDST VAN DE METING. Chrome maakt `Een&nbsp;<code>x</code>&nbsp;alinea`. Zie de
    kop van dit bestand."""
    assert "function ontharde" in JS
    # EN HIJ MOET OOK AANGEROEPEN WORDEN. Een mutatie die alleen de AANROEP weghaalde bleef
    # groen: de functie stond er nog, keurig getoetst, en deed niets meer.
    assert "ontharde(" in _fn("inlineCode"), "inlineCode roept ontharde niet aan"
    fn = _fn("ontharde")
    assert "\\u00a0" in fn
    # ALLEEN DE RANDTEKENS: een harde spatie midden in een zin blijft staan.
    assert "^\\u00a0" in fn and "\\u00a0$" in fn


def test_ontharde_laat_de_chrome_met_rust():
    """De greep en zijn menu hangen ín het blok. Hun tekst is scherm, geen inhoud."""
    assert 'closest("[data-chrome]")' in _fn("ontharde")


# ── 3. Wat de server ervan maakt ─────────────────────────────────────────────
def test_wat_de_knop_oplevert_wordt_een_backtick():
    """De meting uit Chrome, door de échte weg terug gehaald."""
    assert _md_naar_bron("<div class='wb' data-blok='p'>Een <code>gewone</code> alinea.</div>"
                         ).strip() == "Een `gewone` alinea."


def test_de_rondgang_houdt_na_de_knop():
    bron = "Een `gewone` alinea."
    eerste = _md(bron, blokken=True)
    assert _md(_md_naar_bron(eerste), blokken=True) == eerste


def test_geescapete_html_in_de_code_overleeft():
    """Het geval uit de browser-meting: `<b>dit</b>` als INHOUD van de code, niet als opmaak."""
    html = "<div class='wb' data-blok='p'>kijk naar <code>&lt;b&gt;dit&lt;/b&gt;</code> stuk</div>"
    bron = _md_naar_bron(html)
    assert bron.strip() == "kijk naar `<b>dit</b>` stuk"
    assert "<b>" not in _md(bron), "de code-inhoud werd alsnog opmaak"
