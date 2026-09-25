"""Brok 3, stap 1: één sleep-implementatie, en een pas die het blokmodel heel houdt.

WAAROM DE NORMALISEERPAS GEEN VOORWERK IS MAAR EEN REPARATIE. Gemeten in de echte editor, op een
echte pagina: druk op de H-knop van de bestaande werkbalk en er staat daarna

    DIV.wb[h] · DIV.wb[p] · H4 · DIV.wb[p] · DIV.wb[h]

Die kale `H4` hoort in een `.wb` te zitten. `document.execCommand("formatBlock")` VERVANGT het
blok-omhulsel in plaats van de inhoud ervan te wijzigen, en `insertUnorderedList` doet het
andersom: die nest een `<ul>` ín het omhulsel en laat `data-blok="p"` staan terwijl er een lijst
in zit. Sinds brok 1 is dat omhulsel het ding waar een greep aan hangt — dus zonder deze pas
verliest een blok zijn greep zodra je zijn type wijzigt.

DE PAS IS BEWUST DOM. Hij kent geen markdown en geen syntaxis; hij kijkt naar de TAG van de
inhoud en zet het bijbehorende `data-blok`. De tabel die dat bepaalt staat in Python
(`BLOK_SOORTEN`) en reist als attribuut mee naar de browser — er is geen tweede lijst in JS die
kan gaan afwijken. Dat is geen voorzichtigheid maar noodzaak: er is in deze stack geen
JS-testrunner, dus alles wat in JS staat is alleen met de hand in een echte browser te
controleren. Hoe minder die pas weet, hoe minder er stil kan breken.

ÉÉN SLEEP, TWEE AANROEPERS. `NV.bord` was de pointer-sleep van het projectbord, met `.pcard` en
`.pcol` in de code gebakken. De blokken willen hetzelfde gedrag met andere selectors. Een tweede
implementatie zou betekenen dat de ene na een wijziging anders sleept dan de andere.
"""
from __future__ import annotations

import json
import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
JS = (REPO / "nooch_village" / "static" / "nooch.js").read_text()

from nooch_village.cockpit2_util import BLOK_SOORTEN, _md
from nooch_village.views.wiki import _body_html


def _zonder_commentaar(js: str) -> str:
    """Blok- en regelcommentaar eruit. Anders toetst een test de UITLEG waarin staat dat iets
    weg is — die val is in dit project al vaker toegeslagen."""
    js = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
    return re.sub(r"^\s*//[^\n]*", " ", js, flags=re.M)


# ── 1. De tabel woont op één plek ───────────────────────────────────────────────────────────
def test_de_soorten_tabel_dekt_elk_blok_dat_de_renderer_maakt():
    """Elke `data-blok` die `_md` schrijft moet in de tabel staan, en andersom moet elke tag in
    de tabel een blok opleveren dat de weg terug kent."""
    # `table: tabel` en `pre: code` KWAMEN ERBIJ op 24 september 2026: een ```-hek wordt één codeblok in plaats van
    # losse alinea's. Zonder deze regel verliest het zijn greep bij een blokcommando.
    # `figure: embed` kwam eerder op 24 september 2026: een regel die alleen een link is rendert
    # als embed-kaart, en die kaart is een `<figure>`. Zonder deze regel in de tabel verliest een
    # embed zijn greep zodra iemand er een blokcommando op loslaat — de normaliseerpas in
    # `nooch.js` heeft geen eigen lijst en leest precies deze tabel.
    assert BLOK_SOORTEN == {"h3": "h", "h4": "h", "h5": "h",
                            "ul": "ul", "ol": "ol", "blockquote": "q", "hr": "hr",
                            "figure": "embed", "pre": "code",
                            "table": "tabel"}


@pytest.mark.parametrize("bron,tag", [
    ("# kop", "h3"), ("## kop", "h4"), ("### kop", "h5"),
    ("- punt", "ul"), ("1. punt", "ol"), ("&gt; citaat", "blockquote"), ("---", "hr"),
])
def test_de_renderer_haalt_de_soort_uit_de_tabel(bron, tag):
    """MUTATIE-GEVOELIG: verandert de tabel, dan verandert de uitvoer mee. Stond de soort als
    letterlijke string in de renderer, dan zou deze test niets zeggen over die tabel."""
    bron = bron.replace("&gt;", ">")
    html = _md(bron, blokken=True)
    assert f"data-blok='{BLOK_SOORTEN[tag]}'" in html
    assert f"<{tag}" in html


def test_een_gewone_regel_is_geen_tag_uit_de_tabel():
    """Alles wat niet in de tabel staat is een alinea. Dat is de terugval, en hij hoort er te
    zijn — anders krijgt onbekende inhoud geen blok."""
    assert "data-blok='p'" in _md("gewone regel", blokken=True)


# ── 2. De browser krijgt diezelfde tabel, niet een kopie ────────────────────────────────────
def test_de_tabel_reist_mee_naar_het_scherm():
    html = _body_html("een regel", [], blokken=True)
    assert "data-blok-soorten" not in html, "de tabel hoort op de bewerk-container, niet per blok"


def test_de_bewerk_container_draagt_de_tabel(tmp_path):
    from nooch_village import cockpit2
    from nooch_village.views.wiki import render_pagina
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    a = st.att.add("mother_earth", "note", "Een pagina", "## Kop\n- punt")
    html = render_pagina(cockpit2._Stores(dd), a.id, csrf_token="t", username="guest")
    m = re.search(r"id='wiki-body' data-blok-soorten='([^']+)'", html)
    assert m, "geen soorten-tabel op #wiki-body"
    # `_e()` escapet de dubbele quotes; de browser maakt ze weer heel. Dit is wat `dataset` geeft.
    import html as _h
    assert json.loads(_h.unescape(m.group(1))) == BLOK_SOORTEN


def test_javascript_draagt_geen_eigen_soorten_lijst():
    """`reference, don't copy`. Zou de lijst ook in nooch.js staan, dan loopt hij uiteen zodra er
    één bloktype bijkomt — en dat merkt niemand, want er is geen JS-testrunner."""
    kaal = _zonder_commentaar(JS)
    for tag in BLOK_SOORTEN:
        assert f'"{tag}"' not in kaal and f"'{tag}'" not in kaal, \
            f"nooch.js noemt de tag {tag} zelf; de tabel hoort uit `data-blok-soorten` te komen"


# ── 3. Eén sleep-implementatie ──────────────────────────────────────────────────────────────
def test_er_is_maar_een_sleep_implementatie():
    """Twee `pointerdown`-lussen zijn twee sleepgedragingen die na één wijziging uit de pas
    lopen. `NV.bord` hoort een aanroeper van `NV.sleep` te zijn, geen tweede kopie."""
    kaal = _zonder_commentaar(JS)
    assert "NV.sleep = function" in kaal
    assert kaal.count("addEventListener(\"pointerdown\"") == 1


def test_het_bord_gebruikt_de_gedeelde_sleep():
    kaal = _zonder_commentaar(JS)
    m = re.search(r"NV\.bord = function[^{]*\{(.*?)\n  \};", kaal, re.S)
    assert m, "NV.bord niet gevonden"
    assert "NV.sleep(" in m.group(1)
    # en hij geeft zijn eigen selectors mee in plaats van ze in de sleep te bakken
    assert ".pcard[data-pid]" in m.group(1) and ".pcol[data-to]" in m.group(1)


def test_de_sleep_kent_de_selectors_van_het_bord_niet_meer():
    """Gebakken selectors in het gedeelde stuk = het bord dat meelift in de blokken."""
    kaal = _zonder_commentaar(JS)
    m = re.search(r"NV\.sleep = function[^{]*\{(.*?)\n  \};", kaal, re.S)
    assert m, "NV.sleep niet gevonden"
    assert "pcard" not in m.group(1) and "pcol" not in m.group(1)


def test_touch_blijft_buiten_de_sleep():
    """Dezelfde regel als op het bord: een sleepgebaar dat scrollen blokkeert maakt een scherm op
    een telefoon onbruikbaar. Slepen is een versnelling, geen vervanging."""
    kaal = _zonder_commentaar(JS)
    assert 'pointerType === "touch"' in kaal


# ── 4. De normaliseerpas ────────────────────────────────────────────────────────────────────
def test_de_pas_bestaat_en_leest_de_tabel_van_het_scherm():
    kaal = _zonder_commentaar(JS)
    assert "NV.blokNormaliseer = function" in kaal
    assert "data-blok-soorten" in kaal


def _pas_bron() -> str:
    """Alleen de body van `NV.blokNormaliseer`. Zelfde reden als bij `_wiki_edit_bron`: elders in
    het bestand staan ook toewijzingen aan `data-blok`, en die meten niet wat deze toets beweert."""
    kaal = _zonder_commentaar(JS)
    m = re.search(r"NV\.blokNormaliseer = function \(body\) \{(.*?)\n  \};", kaal, re.S)
    assert m, "blokNormaliseer niet gevonden"
    return m.group(1)


def test_de_pas_kijkt_eerst_naar_de_tag_van_het_omhulsel_zelf():
    """GEMETEN IN FIREFOX 154, 23 september 2026. `formatBlock` HERNOEMT daar het omhulsel op zijn
    plek — `DIV.wb[data-blok=p]` wordt `BLOCKQUOTE.wb[data-blok=p]` — waar Chrome het VERVANGT door
    een kale tag. Keek de pas alleen naar de inhoud, dan vond hij in de hernoemde versie alleen de
    greep en liet `p` staan: een citaat dat zichzelf een alinea noemt.

    Wat de browsercheck (`claude/blok_browsercheck.js`) meet is het gedrag; deze toets bewaakt
    alleen dat de eigen tag nog vóór de inhoud wordt geraadpleegd, want dat is de regel die
    weggerefactord kan worden zonder dat iets in deze stack het merkt."""
    body = _pas_bron()
    m = re.search(r"if \(node\.classList\.contains\(\"wb\"\)\) \{(.*?)\n      \}", body, re.S)
    assert m, "de .wb-tak van de pas niet gevonden"
    tak = m.group(1)
    assert "soorten[node.tagName.toLowerCase()]" in tak, (
        "de pas leest de eigen tag van het omhulsel niet meer; in Firefox valt elk blok dan "
        "terug op 'p'")
    eigen = tak.index("soorten[node.tagName.toLowerCase()]")
    inhoud = tak.index("inhoudVan(node)")
    assert eigen < inhoud, "de inhoud wint van de eigen tag; dan is de Firefox-vorm weer stuk"


def _wiki_edit_bron() -> str:
    """Alleen de body van `wikiEdit`. NIET zomaar het hele bestand afzoeken: de eerste versie van
    de test hieronder greep de klikhandler van de MD-PREVIEW-knop, die toevallig dezelfde vorm
    heeft, en mat dus iets anders dan hij beweerde."""
    kaal = _zonder_commentaar(JS)
    m = re.search(r"function wikiEdit\(root\) \{(.*?)\n  \}\n", kaal, re.S)
    assert m, "wikiEdit niet gevonden"
    return m.group(1)


def test_de_werkbalk_normaliseert_na_elk_commando():
    """Hier zit de reparatie: `formatBlock` vervangt het omhulsel, `insertUnorderedList` nest
    erin. Zonder een pas erachter verliest het blok zijn `.wb` of zijn juiste `data-blok`."""
    bron = _wiki_edit_bron()
    m = re.search(r"execCommand\(knop\.dataset\.wikiCmd.*?\n", bron, re.S)
    assert m, "het werkbalk-commando niet gevonden"
    na = bron[m.end():m.end() + 200]
    assert "blokNormaliseer" in na, "na het commando wordt niet genormaliseerd"


def test_de_pas_draait_ook_voor_het_opslaan():
    """Wat er op het scherm staat is wat er wordt opgeslagen. Een blok dat tijdens het typen zijn
    omhulsel kwijtraakte, hoort niet als kale tag in de POST te belanden."""
    bron = _wiki_edit_bron()
    m = re.search(r'form\.addEventListener\("submit", function \(\) \{(.*?)\n    \}\);', bron, re.S)
    assert m, "de submit-handler niet gevonden"
    assert "blokNormaliseer" in m.group(1)
    assert m.group(1).index("blokNormaliseer") < m.group(1).index("body.innerHTML"), \
        "normaliseren moet VOOR het uitlezen van de HTML, anders post hij de oude stand"


# ── 5. Stap 2: de greep en zijn menu ────────────────────────────────────────────────────────
#
# DE GREEP IS CHROME IN EEN BEWERKBAAR VELD, en dat is het hele probleem. Alles binnen
# `#wiki-body` gaat bij het opslaan mee als `innerHTML`, en `_md_naar_bron` maakt van een tag die
# hij niet kent zijn eigen TEKST. Gemeten: `<button>⠿</button>` in een blok levert na opslaan
# letterlijk `⠿Een alinea.` in de bron. De greep moet er dus uit vóór het versturen — én de
# server moet hem negeren als dat een keer misgaat, want één gemiste strip is anders een
# vervuilde pagina.
def test_de_server_negeert_chrome_in_plaats_van_het_tot_tekst_te_maken():
    """HET VANGNET. Fail-closed maakt van een onbekende tag zijn eigen tekst; voor chrome is dat
    juist de verkeerde kant op. `data-chrome` zegt: dit hoort bij het scherm, niet bij de tekst."""
    from nooch_village.cockpit2_util import _md_naar_bron
    met = ("<div class='wb' data-blok='p'>"
           "<button class='wb-greep' data-chrome contenteditable='false'>⠿</button>"
           "Een alinea.</div>")
    assert _md_naar_bron(met) == "Een alinea."


def test_het_vangnet_geldt_voor_de_hele_inhoud_van_het_chrome_element():
    """Een menu ín de greep is ook chrome. Alleen de buitenste tag negeren zou de menu-teksten
    alsnog in de bron laten belanden."""
    from nooch_village.cockpit2_util import _md_naar_bron
    met = ("<div class='wb' data-blok='p'><span data-chrome>"
           "<button>⠿</button><ul><li>omhoog</li><li>omlaag</li></ul></span>Tekst.</div>")
    assert _md_naar_bron(met) == "Tekst."


def test_gewone_inhoud_blijft_gewoon():
    """MUTATIE-CONTROLE: zonder dit zou 'negeer alles' ook echte tekst kunnen opeten."""
    from nooch_village.cockpit2_util import _md_naar_bron
    assert _md_naar_bron("<div class='wb' data-blok='p'>Gewoon <strong>vet</strong>.</div>") \
        == "Gewoon **vet**."


def test_de_greep_wordt_verwijderd_voor_het_opslaan():
    """De eerste verdediging. Het vangnet hierboven is de tweede — allebei, want dit is het enige
    punt waar chrome in de opgeslagen tekst kan lekken."""
    bron = _wiki_edit_bron()
    m = re.search(r'form\.addEventListener\("submit", function \(\) \{(.*?)\n    \}\);', bron, re.S)
    assert m, "de submit-handler niet gevonden"
    assert "data-chrome" in m.group(1)
    assert m.group(1).index("data-chrome") < m.group(1).index("body.innerHTML"), \
        "de greep moet eruit VOOR de HTML wordt uitgelezen"


def test_de_greep_staat_buiten_de_tekststroom():
    """`contenteditable=false` houdt de cursor eruit; zonder dat typt iemand ín zijn greep."""
    kaal = _zonder_commentaar(JS)
    m = re.search(r"function greepVoor\(.*?\n  \}", kaal, re.S)
    assert m, "greepVoor niet gevonden"
    assert 'contentEditable = "false"' in m.group(0)
    assert "data-chrome" in m.group(0)


def test_de_greep_verschijnt_alleen_tijdens_bewerken():
    """Een greep op een pagina die je alleen leest, belooft iets dat niet kan."""
    bron = _wiki_edit_bron()
    m = re.search(r"function editeerbaar\(aan\) \{(.*?)\n    \}", bron, re.S)
    assert m, "editeerbaar() niet gevonden"
    assert "grepen" in m.group(1).lower() or "greep" in m.group(1).lower()


def test_slepen_begint_bij_de_greep_en_niet_in_de_tekst():
    """Slepen vanaf de tekst zou vechten met het selecteren van woorden."""
    kaal = _zonder_commentaar(JS)
    m = re.search(r"NV\.sleep = function[^{]*\{(.*?)\n  \};", kaal, re.S)
    assert m, "NV.sleep niet gevonden"
    assert "opties.greep" in m.group(1)


def test_het_menu_biedt_een_weg_zonder_slepen():
    """Touch kent geen sleep (zelfde regel als het bord) en een toetsenbord al helemaal niet.
    Omhoog/omlaag/verwijderen in het menu is die weg — anders is herordenen muis-only."""
    kaal = _zonder_commentaar(JS)
    for actie in ("omhoog", "omlaag", "verwijder"):
        assert actie in kaal, f"geen {actie} in het greep-menu"


# ── 6. Stap 3: het /-menu ───────────────────────────────────────────────────────────────────
#
# WAT HET NIET MAG WORDEN. Een lijst bloktypes in JS zou de derde plek zijn waar het vocabulaire
# woont (naast `_md` en `_md_naar_bron`), en de enige waar geen test bij kan. De server rendert
# het menu daarom als sjabloon; JS kloont het en voert uit wat erin staat.
def test_het_menu_kent_alleen_blokken_die_de_renderer_ook_maakt():
    from nooch_village.cockpit2_util import BLOK_MENU, BLOK_SOORTEN
    for tag, label, cmd, arg in BLOK_MENU:
        assert label and cmd
        assert tag == "p" or tag in BLOK_SOORTEN, f"{tag} is geen blok dat de renderer kent"


#: Wat `execCommand` van elk menu-item MAAKT, gemeten in Chrome op een echte `.wb`-div — niet
#: afgeleid uit de naam van het commando. `formatBlock` vervangt het omhulsel, de twee
#: lijst-commando's nesten erín, en `insertHorizontalRule` levert er een `id="null"` bij omdat
#: `null` als argument wordt doorgegeven.
#:
#: OP HET LABEL EN NIET OP DE TAG (26 september 2026). De tag-kolom is niet uniek: "Tekst",
#: "Feiten" en "Backlinks" staan alle drie op `p`, want er béstaat geen HTML-tag voor een afgeleid
#: blok — de tag zegt alleen wat de browser na het commando overhoudt. Op de tag sleutelen gaf
#: hier stil de uitkomst van "Tekst" voor alle drie.
_UITKOMST = {
    "Tekst": ("<p>regel</p>", "regel"),
    "Kop 1": ("<h3>regel</h3>", "# regel"),
    "Kop 2": ("<h4>regel</h4>", "## regel"),
    "Kop 3": ("<h5>regel</h5>", "### regel"),
    "Lijst": ("<div class='wb' data-blok='p'><ul><li>regel</li></ul></div>", "- regel"),
    "Genummerde lijst": ("<div class='wb' data-blok='p'><ol><li>regel</li></ol></div>",
                         "1. regel"),
    "Citaat": ("<blockquote>regel</blockquote>", "> regel"),
    "Scheiding": ("<div class='wb' data-blok='p'><hr id=\"null\"></div>", "---"),
    # TABEL EN CODEBLOK LOPEN NIET LANGS `execCommand` (25 september 2026). Die twee kan de
    # browser niet maken: een `formatBlock` op een `<pre>` haalt de regelovergangen eruit en een
    # tabel kent hij als commando niet eens. Ze openen daarom het BRON-BEWERKVLAK met het
    # markdown-sjabloon van de server erin — dezelfde `<textarea data-blok-bron>` die de
    # greep-actie "bewerk als tekst" al gebruikte. Wat de weg terug dus leest is die textarea,
    # niet een omhulsel dat de browser bouwde.
    "Tabel": ("<div class='wb' data-blok='p'><textarea data-blok-bron>| A | B |\n|---|---|\n"
              "| | |</textarea></div>", "| A | B |\n|---|---|\n| | |"),
    "Codeblok": ("<div class='wb' data-blok='p'><textarea data-blok-bron>```\ncode\n```"
                 "</textarea></div>", "```\ncode\n```"),
    # FEITEN EN BACKLINKS lopen langs hetzelfde bron-pad als tabel en codeblok, met de markering
    # als sjabloon. Dat de weg terug één regel `{{facts}}` oplevert is het hele punt: de INHOUD
    # (feiten uit `meta`, backlinks uit andere pagina's) hoort nooit in de opslag te komen.
    "Feiten": ("<div class='wb' data-blok='p'><textarea data-blok-bron>{{facts}}"
               "</textarea></div>", "{{facts}}"),
    "Backlinks": ("<div class='wb' data-blok='p'><textarea data-blok-bron>{{backlinks}}"
                  "</textarea></div>", "{{backlinks}}"),
}


def test_elk_menu_item_levert_iets_op_dat_de_weg_terug_leest():
    """DE HARDE REGEL VAN BROK 2, nu voor de knoppen: geen knop voor een blok waarvan de weg
    terug niet bestaat — anders is het bij het opslaan stilzwijgend platte tekst.

    GEDRAG EN GEEN LIJST. De eerste versie toetste of de tag in `_BRON_BLOK` stond, en wees `ul`
    en `ol` af terwijl die prima teruggelezen worden — de parser doet ze in een eigen tak. Die
    test mat waar de code stond in plaats van wat hij doet."""
    from nooch_village.cockpit2_util import BLOK_MENU, _md_naar_bron
    for tag, label, cmd, arg in BLOK_MENU:
        html, verwacht = _UITKOMST[label]
        assert _md_naar_bron(html) == verwacht, f"{label} ({tag}) komt niet terug als bron"
        # Bij een `bron`-item is het sjabloon van de server WAT ER IN DAT VELD KOMT. Staan die
        # twee niet gelijk, dan toetst de regel hierboven een uitkomst die nooit ontstaat.
        if cmd == "bron":
            assert verwacht == arg, f"{label}: sjabloon {arg!r} ≠ getoetste uitkomst {verwacht!r}"


def test_het_sjabloon_staat_in_de_editor(tmp_path):
    from nooch_village import cockpit2
    from nooch_village.cockpit2_util import BLOK_MENU
    from nooch_village.views.wiki import render_pagina
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    a = st.att.add("mother_earth", "note", "Een pagina", "tekst")
    html = render_pagina(cockpit2._Stores(dd), a.id, csrf_token="t", username="guest")
    assert "id='wb-menu-sjabloon'" in html
    for _tag, label, cmd, _arg in BLOK_MENU:
        assert label in html and f"data-wiki-cmd='{cmd}'" in html


def test_het_sjabloon_is_chrome(tmp_path):
    """Hij staat buiten het bewerkbare veld, maar draagt `data-chrome` voor als hij er ooit in
    beland — dezelfde twee verdedigingen als bij de greep."""
    from nooch_village.cockpit2_util import blok_menu
    assert "data-chrome" in blok_menu()


def test_javascript_kent_de_labels_niet():
    """`reference, don't copy`, nu voor de menu-teksten.

    OP STRING-LITERALEN EN NIET OP LOSSE WOORDEN. De eerste versie zocht het label ergens in het
    bestand, en sloeg aan op de FUNCTIENAAM `blokTekst` omdat "Tekst" daarin voorkomt. Een eigen
    lijst zou eruitzien als een string in de code; daar toetst hij nu op."""
    from nooch_village.cockpit2_util import BLOK_MENU
    kaal = _zonder_commentaar(JS)
    for _tag, label, _cmd, _arg in BLOK_MENU:
        assert f'"{label}"' not in kaal and f"'{label}'" not in kaal, \
            f"nooch.js draagt het label {label!r} als string"


def test_de_schuine_streep_opent_het_menu():
    """De editor moet hem WIREN, en de /-lus moet het server-sjabloon gebruiken. De eerste versie
    zocht allebei in de body van `wikiEdit` — maar `blokMenu` is een buurfunctie, niet een stuk
    van die body, dus die test mat de verkeerde plek."""
    assert "blokMenu(body)" in _wiki_edit_bron(), "de editor zet het /-menu niet aan"
    kaal = _zonder_commentaar(JS)
    m = re.search(r"function blokMenu\(body\) \{(.*?)\n  \}", kaal, re.S)
    assert m, "blokMenu niet gevonden"
    assert "wb-menu-sjabloon" in m.group(1), "het menu komt niet van het server-sjabloon"
    assert '"/"' in m.group(1), "er wordt nergens op de schuine streep gelet"


def test_de_streep_verdwijnt_maar_pas_na_het_commando():
    """DE VOLGORDE IS OMGEKEERD AAN WAT JE ZOU KIEZEN, en dat is gemeten. Deze test eiste eerst
    dat het blok LEEG was vóór `execCommand` — logisch: anders staat er `/Kop 1`. In de browser
    bleek dat `formatBlock` op een leeg blok met een samengevallen selectie NIETS doet: het
    bloktype veranderde niet en de streep was al weg. Het commando krijgt de streep dus als
    inhoud, en daarna wordt hij eruit gehaald."""
    kaal = _zonder_commentaar(JS)
    m = re.search(r"function blokMenuKies\(.*?\n  \}", kaal, re.S)
    assert m, "blokMenuKies niet gevonden"
    bron = m.group(0)
    # VANAF HET COMMANDO MEten (25 september 2026). Sinds tabel en codeblok erbij zijn, begint
    # deze functie met een eigen tak die het bron-bewerkvlak opent en daarna `return`t — mét een
    # eigen `blokNormaliseer`. Die stond vóór alles wat hier gemeten wordt, en dan meet je de
    # volgorde van een ANDERE tak. Een knip op "de eerste return" werkte ook niet: `if (!n)
    # return;` staat daar al bovenaan. Wat deze toets bedoelt is de volgorde binnen het
    # `execCommand`-pad, dus dat is waar de meting begint.
    assert "execCommand(knop" in bron, "het commando-pad bestaat niet meer"
    na_cmd = bron[bron.index("execCommand(knop"):]
    assert "streep.remove()" in na_cmd, \
        "de streep wordt weggehaald vóór het commando — dan doet het commando niets"
    assert na_cmd.index("streep.remove()") < na_cmd.index("blokNormaliseer"), \
        "de streep moet weg zijn voordat het blokmodel wordt bijgewerkt"
    assert bron.count("streepNode(") == 2, \
        ("het knooppunt wordt hergebruikt in plaats van opnieuw gezocht; `formatBlock` bouwt het "
         "element opnieuw op en dan is de oude referentie losgekoppeld")
    assert "blokNormaliseer" in bron, "na het commando klopt het blokmodel niet meer"


def test_de_tekst_van_een_blok_telt_de_greep_niet_mee():
    """GEMETEN IN DE BROWSER, niet voorzien. De greep hangt ÍN het blok, dus `textContent` bevat
    ook zijn menu-labels ("↑ omhoog↓ omlaag✕ verwijderen"). Elk blok leek daardoor gevuld en de
    /-lus kon nooit aanslaan. Het opslaan liep er niet op stuk — de grepen gaan er eerst uit en
    de server negeert `data-chrome` — maar alles wat de tekst van een blok LEEST wel."""
    kaal = _zonder_commentaar(JS)
    assert "function blokTekst(" in kaal
    m = re.search(r"function blokTekst\(blok\) \{(.*?)\n  \}", kaal, re.S)
    assert "data-chrome" in m.group(1), "blokTekst filtert de chrome niet weg"
    mm = re.search(r"function blokMenu\(body\) \{(.*?)\n  \}", kaal, re.S)
    assert "blokTekst(blok)" in mm.group(1), "de /-lus gebruikt de rauwe textContent nog"


def test_het_wissen_van_de_streep_laat_de_greep_staan():
    """`blok.textContent = ""` zou de greep meenemen, en dan is het blok zijn handvat kwijt zodra
    je er één keer een bloktype op toepast. Er wordt daarom één TEKSTKNOOP aangepast, en die
    wordt gezocht met de chrome overgeslagen (`streepNode`)."""
    kaal = _zonder_commentaar(JS)
    m = re.search(r"function blokMenuKies\(.*?\n  \}", kaal, re.S)
    assert 'blok.textContent = ""' not in m.group(0), "de greep wordt met de tekst weggegooid"
    assert "streepNode(" in m.group(0)
    s = re.search(r"function streepNode\(waar\) \{(.*?)\n  \}", kaal, re.S)
    assert s and "data-chrome" in s.group(1), "streepNode slaat de chrome niet over"
