"""De opmaak-werkbalk zweeft bij je selectie (26 september 2026).

Hij stond als vaste balk boven het bewerkvlak (`position:sticky`). Twee problemen, en het tweede
kwam er pas bij toen bewerken de stand werd: op een lange pagina scrolde hij weg zodra je ver
genoeg naar beneden was, en sindsdien stond hij bovendien op élke pagina permanent in beeld
terwijl je alleen aan het lezen was.

Een balkje dat bij je selectie verschijnt lost dat STRUCTUREEL op — er is geen vaste balk meer om
weg te scrollen. Met dezelfde knoppen, dezelfde handlers en dezelfde server-kant; alleen hoe hij
verschijnt verandert.
"""
from __future__ import annotations

import pathlib
import re

from nooch_village.cockpit2_util import BLOK_MENU, _OPMAAK_KNOPPEN, blok_menu, opmaak_werkbalk

CSS = (pathlib.Path(__file__).resolve().parents[1]
       / "nooch_village" / "static" / "nooch.css").read_text()
NU = (pathlib.Path(__file__).resolve().parents[1]
      / "nooch_village" / "static" / "nooch-ui.css").read_text()
JS = (pathlib.Path(__file__).resolve().parents[1]
      / "nooch_village" / "static" / "nooch.js").read_text()


def _kaal(js: str) -> str:
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", js, flags=re.S)


def _wikiedit() -> str:
    return _kaal(JS).split("function wikiEdit(")[1].split("\n  function ")[0]


# ── 1. De werkbalk draagt alleen nog wat écht inline is ──────────────────────
def test_alleen_de_vier_inline_commandos():
    assert [c for c, *_ in _OPMAAK_KNOPPEN] == ["bold", "italic", "strikeThrough", "nvCode"]


def test_lijst_en_kop_staan_nog_maar_op_een_plek():
    """EEN MANIER PER HANDELING. Het blokmenu heeft Lijst, Genummerde lijst en Kop 1/2/3 al; ze
    ook in de werkbalk zetten is twee wegen naar dezelfde uitkomst, en die lopen uiteen zodra er
    aan één van de twee iets verandert. Dezelfde reden waarom het losse uploadformulier verviel
    toen Afbeelding in het blokmenu kwam."""
    werkbalk = {c for c, *_ in _OPMAAK_KNOPPEN if c}
    menu = {cmd for _t, _l, cmd, _a in BLOK_MENU}
    assert not (werkbalk & menu), f"deze commando's staan op twee plekken: {werkbalk & menu}"
    for weg in ("insertUnorderedList", "formatBlock"):
        assert weg not in werkbalk, f"{weg} hoort exclusief in het blokmenu"
        assert weg in menu, f"{weg} is uit het blokmenu verdwenen in plaats van uit de werkbalk"


def test_de_scheiding_is_mee_verdwenen():
    """Vier knoppen die allemaal hetzelfde doen hebben niets te scheiden; het streepje zat er om
    inline van blok te scheiden, en die tweedeling staat nu in twee verschillende menu's."""
    assert "tb-sep" not in opmaak_werkbalk()


def test_de_knoppen_zelf_zijn_niet_veranderd():
    """DE OPDRACHT WAS EXPLICIET: alleen hoe de balk verschijnt verandert, niet wat de knoppen
    doen. Zelfde atomen, zelfde haakjes, zelfde uitzondering voor inline code."""
    html = opmaak_werkbalk()
    assert "class='editor-tb wiki-tb'" in html and "id='wiki-tb'" in html
    assert html.count("class='tb-b'") == 4
    assert "data-wiki-cmd='nvCode'" in html


def test_de_server_rendert_hem_nog_steeds():
    """De knoppentaal woont op één plek. Zou `nooch.js` de knoppen zelf bouwen, dan was dat de
    tweede plek — en de enige zonder toets."""
    from nooch_village.views.wiki import _wiki_editor
    assert "opmaak_werkbalk" in pathlib.Path(
        "nooch_village/views/wiki.py").read_text(), "de view rendert de werkbalk niet meer"
    assert callable(_wiki_editor)


# ── 2. Hij verschijnt bij een selectie ───────────────────────────────────────
def test_hij_is_standaard_verborgen():
    assert "hidden>" in opmaak_werkbalk(), "de balk staat open zonder selectie"


def test_hij_hangt_aan_de_selectie_en_niet_aan_de_bewerkstand():
    """Hier stond `tb.hidden = !aan` in `editeerbaar()`. Als STAND betekende dat: een vaste balk op
    elke pagina, altijd — want bewerken is sinds #606 de stand en geen modus meer."""
    haak = _wikiedit()
    assert "function balkBijSelectie()" in haak
    assert 'document.addEventListener("selectionchange", balkBijSelectie)' in haak
    editeerbaar = haak.split("function editeerbaar(")[1].split("\n    }")[0]
    assert "tb.hidden = !aan" not in editeerbaar, "de balk hangt nog aan de bewerkstand"


def test_een_gewone_cursor_toont_niets():
    """Een samengevallen selectie is een cursor, en daar valt niets op te maken. Een balkje dat
    dan verschijnt, springt bij elke klik in beeld."""
    haak = _wikiedit()
    assert "sel.isCollapsed" in haak and "balkWeg()" in haak


def test_alleen_een_selectie_binnen_dit_bewerkvlak():
    """De titel heeft óók `contenteditable`; een selectie daarbuiten gaat deze balk niet aan."""
    haak = _wikiedit()
    assert "body.contains(" in haak, "elke selectie op de pagina opent de balk"


def test_een_tekstknoop_heeft_geen_closest():
    """`commonAncestorContainer` IS een tekstknooppunt zodra je binnen één alinea selecteert —
    het gewone geval. Zonder deze stap gooit de eerste de beste selectie een TypeError."""
    haak = _wikiedit()
    assert "nodeType === 3" in haak


def test_de_focus_verlaten_sluit_hem():
    haak = _wikiedit()
    assert 'body.addEventListener("focusout"' in haak


def test_een_klik_op_de_balk_sluit_hem_niet():
    """De balk staat BUITEN het bewerkvlak, dus een klik erop is een `focusout`. Zonder deze
    uitzondering sluit hij zichzelf op het moment dat je hem gebruikt."""
    haak = _wikiedit()
    uit = haak.split('body.addEventListener("focusout"')[1].split("});")[0]
    assert "tb.contains(e.relatedTarget)" in uit


def test_hij_beweegt_mee_bij_scrollen():
    """De positie is in venstercoördinaten. Zonder dit blijft de balk staan waar hij stond terwijl
    de tekst eronder wegschuift — en dat is precies het probleem dat deze stap oplost."""
    haak = _wikiedit()
    assert 'window.addEventListener("scroll", balkBijSelectie, true)' in haak
    assert 'window.addEventListener("resize", balkBijSelectie)' in haak


# ── 3. Hij staat nooit half buiten beeld ─────────────────────────────────────
def test_hij_wordt_boven_de_selectie_gezet():
    haak = _wikiedit()
    assert "getBoundingClientRect()" in haak
    assert "vak.top - eigen.height" in haak, "hij hangt niet boven de selectie"


def test_bij_een_selectie_bovenin_gaat_hij_eronder():
    """DE EIS: "nooit half buiten beeld". Bovenin het scherm past er niets boven de selectie."""
    haak = _wikiedit()
    assert "vak.bottom" in haak, "er is geen terugval onder de selectie"


def test_hij_blijft_binnen_het_venster():
    """Een selectie onderaan zou hem eronder duwen, een selectie ver rechts over de rand."""
    haak = _wikiedit()
    assert "window.innerHeight" in haak and "window.innerWidth" in haak


def test_eerst_tonen_dan_meten():
    """Een verborgen element heeft geen maat: `getBoundingClientRect()` geeft nul. Zou de meting
    vóór het tonen staan, dan rekent hij met hoogte 0 en landt hij pal op de selectie."""
    haak = _wikiedit()
    positie = haak.split("function balkBijSelectie()")[1].split("\n    }")[0]
    assert positie.index("tb.hidden = false") < positie.index("tb.getBoundingClientRect()")


# ── 4. De vormgeving ─────────────────────────────────────────────────────────
def _regel(sel: str) -> str:
    m = re.search(r"(?:^|[};])\s*" + re.escape(sel) + r"\{([^}]*)\}", CSS, re.M)
    assert m, f"{sel} bestaat niet"
    return m.group(1)


def test_hij_is_niet_meer_sticky():
    body = _regel(".wiki-tb")
    assert "position:sticky" not in body
    assert "position:fixed" in body, "hij zweeft niet"


def test_venstercoordinaten_horen_bij_fixed():
    """`nooch.js` meet met `getBoundingClientRect()`, en dat zijn venstercoördinaten. Met
    `absolute` moet je die omrekenen naar de dichtstbijzijnde gepositioneerde voorouder — een
    rekensom die stilzwijgend meeverandert zodra iemand ergens een `position:relative` toevoegt."""
    assert "position:fixed" in _regel(".wiki-tb")
    haak = _wikiedit()
    assert "pageYOffset" not in haak and "scrollY" not in haak, \
        "er wordt omgerekend alsof hij absoluut gepositioneerd is"


def test_hij_ziet_eruit_als_iets_dat_zweeft():
    """`.editor-tb` geeft hem een ONDERrand en vierkante onderhoeken — die vorm hoort bij een balk
    die bovenop een tekstvak plakt. Een zwevend balkje heeft vier hoeken en niets om tegenaan te
    zitten."""
    body = _regel(".wiki-tb")
    assert "border-bottom:none" in body
    assert "box-shadow" in body, "hij hangt niet boven de tekst maar erin"


def test_de_huisstijl_kent_hem_ook():
    """Les uit #598: een nieuwe zichtbare vorm zonder `.nu`-tegenhanger laat de huisstijl-ratchet
    vallen, en terecht — deze laag kent geen zachte randen en geen schaduwen."""
    assert ".nu .wiki-tb" in NU


def test_het_sjabloon_van_het_blokmenu_is_niet_geraakt():
    """Twee zwevende dingen naast elkaar; dit is de andere. Hij hoort niet mee te veranderen."""
    assert "id='wb-menu-sjabloon'" in blok_menu()
