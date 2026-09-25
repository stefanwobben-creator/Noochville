"""Slepen is zichtbaar: waar het blok landt, en dat het opgepakt is (25 september 2026).

EERST DE CORRECTIE, want die bepaalt wat deze stap wél en niet is. Het ontwerpdocument zegt bij
punt 3: *"Verplaatsen is een klik-menu, geen sleep. Het grip-icoontje oogt als een sleepgreep maar
opent een tekstmenu (omhoog/omlaag). Geen drag-and-drop."*

Dat klopt niet. Slepen bestaat en het werkt — ook op prod. `grepen()` roept `NV.sleep` al aan met
elk blok als zijn eigen drop-doel, en `onDrop` beslist vóór of ná op de muispositie. Gemeten met
echte PointerEvents op `NOTE-COMPLI-021`: de volgorde ging van `p,p,h,p,ul,…` naar `p,h,p,p,ul,…`
en het spookje verscheen en verdween netjes. (Waarom de browsercheck dit niet eerder zag: de
sleep-actie van de extensie stuurt alleen `pointermove`, geen `pointerdown`/`pointerup` — het
instrument kon dit gebaar niet uitvoeren. Daarom staat het nu ín de check, met eigen events.)

WAT ER DAN WÉL MISTE, en dat verklaart de waarneming: je ziet er niets van.

| | het bord | een wiki-blok |
|---|---|---|
| doel licht op | `.pcol.over` heeft vormgeving | `.wb.over` had er GEEN |
| bron vervaagt | `.pcard.pdrag-bron{opacity:.35}` | `.wb.pdrag-bron` had er GEEN |
| waar land ik | kolom is het doel, dus eenduidig | vóór of ná — nergens te zien |

De JS zette dus al jaren klassen die niets schilderden. Wie sleept ziet een kantelend spookje en
verder niets: geen doel, geen richting, en de oorspronkelijke plek ziet er onveranderd uit. Dan
voelt het niet alsof het werkt, en dat is precies wat er gemeld is.

DE RICHTING IS NIEUW EN DE REST IS VORMGEVING. `onDrop` berekende vóór/ná pas bij het loslaten;
om het tijdens het slepen te kunnen tonen komt er een `helft`-stand in `NV.sleep` die
`over-boven`/`over-onder` zet in plaats van `over`. Het bord geeft die stand niet mee en gedraagt
zich onveranderd.
"""
from __future__ import annotations

import pathlib
import re

from nooch_village.cockpit2_util import _md, _md_naar_bron

WORTEL = pathlib.Path(__file__).resolve().parents[1]
JS = (WORTEL / "nooch_village" / "static" / "nooch.js").read_text()
CSS = (WORTEL / "nooch_village" / "static" / "nooch.css").read_text()
NU = (WORTEL / "nooch_village" / "static" / "nooch-ui.css").read_text()
CHECK = (WORTEL / "claude" / "blok_browsercheck.js").read_text()

BRON = "### Een kop\n\nEerste alinea.\n\n- een\n- twee\n\nLaatste alinea."


def _blokken(html: str) -> list[str]:
    uit, diepte, start = [], 0, None
    for m in re.finditer(r"<div class='wb'[^>]*>|<div[^>]*>|</div>", html):
        if m.group(0) == "</div>":
            diepte -= 1
            if diepte == 0 and start is not None:
                uit.append(html[start:m.end()]); start = None
        else:
            if diepte == 0 and m.group(0).startswith("<div class='wb'"):
                start = m.start()
            diepte += 1
    return uit


def _verplaats(html: str, van: int, naar: int) -> str:
    b = _blokken(html)
    b.insert(naar, b.pop(van))
    return "".join(b)


# ── 1. De bron volgt de nieuwe volgorde (dit werkte al; nu vastgelegd) ───────
def test_een_blok_verplaatsen_verplaatst_de_tekst_in_de_bron():
    """DE EIS UIT HET ONTWERPDOCUMENT: verslepen moet *"netjes blijven round-tripen"*. Dat gaat
    vanzelf omdat slepen DOM-knopen verplaatst en de bestaande opslagweg de markdown opnieuw
    afleidt — er is geen tweede opslagpad. Deze toets legt dat vast."""
    bron = _md_naar_bron(_verplaats(_md(BRON, blokken=True), 0, 4))
    assert bron.index("Een kop") > bron.index("Eerste alinea")
    assert "### Een kop" in bron, "de kop verloor zijn soort bij het verplaatsen"


def test_de_rondgang_blijft_heel_na_een_verplaatsing():
    eerste = _md(_md_naar_bron(_verplaats(_md(BRON, blokken=True), 0, 4)), blokken=True)
    assert _md(_md_naar_bron(eerste), blokken=True) == eerste


def test_een_lijst_blijft_een_lijst_na_verplaatsen():
    html = _md(BRON, blokken=True)
    lijst = next(i for i, b in enumerate(_blokken(html)) if "<ul" in b)
    assert _md_naar_bron(_verplaats(html, lijst, 0)).startswith("- een\n- twee")


def test_een_tabel_en_een_codeblok_overleven_een_verplaatsing():
    """De twee soorten met een eigen bewerkvlak; juist daar zou een naïeve knip ze halveren."""
    html = _md("Ervoor.\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n```\nx = 1\n```\n\nErna.", blokken=True)
    tabel = next(i for i, x in enumerate(_blokken(html)) if "<table" in x)
    terug = _md_naar_bron(_verplaats(html, tabel, 0))
    assert terug.startswith("| A | B |")
    assert "```\nx = 1\n```" in terug


# ── 2. Je ziet waar het blok landt ───────────────────────────────────────────
def test_het_doelblok_licht_op():
    """`.pcol.over` had vormgeving, `.wb.over` niet — de JS zette een klasse die niets deed."""
    assert re.search(r"\.wb\.over[-a-z]*\{", CSS), "het doelblok krijgt geen vormgeving"


def test_je_ziet_of_je_er_boven_of_onder_landt():
    """Een enkele omlijning zegt niet of je vóór of ná dit blok terechtkomt, en juist dat is wat
    `onDrop` beslist. Twee klassen, twee kanten, en allebei een EIGEN richtingsteken.

    DE EERSTE VERSIE VAN DEZE TOETS KEEK OF DE NAMEN VOORKWAMEN, en dat was te weinig: de twee
    delen de achtergrondregel, dus een mutatie die de streep aan de bovenkant weghaalde bleef
    groen — en dan lichten beide kanten identiek op en ben je terug bij "waar land ik?".
    Gemeten in Chrome: `box-shadow: rgb(31,157,85) 0px 2px 0px 0px inset` aan de bovenkant."""
    # OP EEN REGELGRENS ZOEKEN, niet ergens in de tekst: `.wb.over-boven,.wb.over-onder{…}` bevat
    # `.wb.over-onder{` als achterstuk, en dan vind je de gedeelde achtergrondregel in plaats van
    # de eigen richtingsregel.
    for kant, richting in (("over-boven", "inset 0 2px"), ("over-onder", "inset 0 -2px")):
        m = re.search(rf"(?:^|[}};])\s*\.wb\.{kant}\{{([^}}]*)\}}", CSS, re.M)
        assert m, f".wb.{kant} heeft geen eigen regel"
        assert richting in m.group(1), f".wb.{kant} toont geen richting: {m.group(1)!r}"


def test_de_js_rekent_de_kant_ook_echt_uit():
    """DE CSS KAN KLOPPEN TERWIJL DE KLASSE NOOIT WORDT GEZET. Een mutatie die `kant` op een vaste
    `"over"` zette liet alle CSS-toetsen groen; de helft-stand deed dan niets. Hier staat dat de
    berekening er is — het bewijs dát hij werkt komt uit de browser (zie het PR-verslag)."""
    assert '"over-boven" : "over-onder"' in JS


def test_het_opgepakte_blok_vervaagt():
    """Zoals `.pcard.pdrag-bron{opacity:.35}` op het bord. Zonder dit ziet de oorspronkelijke plek
    er tijdens het slepen onveranderd uit."""
    assert re.search(r"\.wb\.pdrag-bron\{[^}]*opacity", CSS)


def test_de_nu_laag_kent_de_sleep_toestanden():
    """Les uit PR 2: een nieuwe zichtbare klasse in de oude laag zonder tegenhanger laat
    `test_fase10_huisstijl` vallen."""
    # ALLEBEI, EN OP HUN EIGEN REGEL. Met `or` bleef een mutatie die er één weghaalde groen; met
    # een kale substring-check ook, want de twee delen de achtergrondregel en die bevat allebei de
    # namen. Dezelfde val als in de toets hierboven, twee keer op één dag.
    for kant in ("over-boven", "over-onder"):
        assert re.search(rf"(?:^|[}};])\s*\.nu \.wb\.{kant}\{{[^}}]*box-shadow", NU, re.M), \
            f".nu .wb.{kant} heeft geen eigen richtingsregel"


# ── 3. De gedeelde sleep-machinerie ──────────────────────────────────────────
def test_er_komt_geen_tweede_sleep_implementatie():
    """De reden staat in de code zelf: twee implementaties gaan na één wijziging anders slepen."""
    assert JS.count("NV.sleep = function") == 1


def test_het_bord_geeft_de_helft_stand_niet_mee():
    """DE ZWAARSTE EIS. `NV.bord` moet zich onveranderd gedragen: een kaart valt in een KOLOM, en
    daar bestaat geen boven- of onderhelft."""
    bord = JS.split("NV.bord = function")[1].split("\n  }")[0]
    assert "helft" not in bord, "het bord kreeg de nieuwe stand ongevraagd"


def test_de_wiki_vraagt_de_helft_stand_wel():
    """TOT AAN HET EINDE VAN DE AANROEP, niet de eerste 1200 tekens: die knip viel midden in het
    commentaar boven `NV.sleep` en liet de toets falen op iets dat er wél stond."""
    aanroep = JS.split("function grepen")[1].split("/* ── Het /-menu")[0]
    assert "helft: true" in aanroep, "de wiki-sleep toont geen richting"


def test_touch_blijft_het_menu_houden():
    """`NV.sleep` weigert een touch-pointer: een sleepgebaar dat scrollen blokkeert maakt een
    scherm op een telefoon onbruikbaar. Omhoog/omlaag blijft daar de route."""
    assert 'e.pointerType === "touch"' in JS
    assert '"omhoog"' in JS


# ── 4. De greep vertelt wat hij kan ──────────────────────────────────────────
def test_de_greep_zegt_dat_je_hem_kunt_slepen():
    """Waarom de melding "geen drag-and-drop" ontstond: klikken opent een menu, dus het icoontje
    leest als een menuknop. De `cursor:grab` is er wel, maar die zie je pas als je er al bent."""
    # TOT HET EIND VAN DE FUNCTIE, niet de eerste 900 tekens: de plus-knop uit de volgende stap
    # kwam ervóór te staan en duwde de `title` het venster uit. Dezelfde val als bij de
    # route-toets van het projectenbord — een venster op tekens is geen venster op een functie.
    greep = JS.split("function greepVoor")[1].split("\n  function ")[0]
    assert 'knop.setAttribute("title"' in greep, "de greep draagt geen uitleg"


def test_de_greep_praat_engels():
    """De UI is sinds i18n-fase 1 Engels; hier stond nog `aria-label='blok verplaatsen of
    wijzigen'`. Meegenomen omdat ik toch in deze functie zat."""
    greep = JS.split("function greepVoor")[1].split("\n  function ")[0]
    assert "blok verplaatsen of wijzigen" not in greep


# ── 5. De browsercheck bewijst het gebaar ────────────────────────────────────
def test_de_browsercheck_sleept_echt():
    """DIT IS DE KERN VAN DEZE STAP. Dat slepen werkt was niet te zien, en daardoor stond in een
    ontwerpdocument dat het niet bestond. De sleep-actie van de extensie stuurt alleen
    `pointermove`, dus de check moet zijn eigen `pointerdown`/`pointerup` sturen."""
    assert "pointerdown" in CHECK and "pointerup" in CHECK
    assert "sleep" in CHECK.lower()
