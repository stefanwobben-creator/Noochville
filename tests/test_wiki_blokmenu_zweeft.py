"""Het bloktype-menu: zwevend, ook op een bestaand blok, en met eerlijke kop-labels.

Drie dingen die elkaar raken (26 september 2026):

2. Het "/"-menu hing met `appendChild` in de documentflow en viel op een lange pagina onder de
   vouw — dan kies je uit een lijst die je niet ziet. Er bestond al één positioneerder
   (`zweefBij`, gedeeld door de opmaakbalk en de link-kaart); die doet dit er nu bij.
3. De greep kon een blok verplaatsen en weggooien, maar niet OMZETTEN. Je moest de tekst knippen,
   het blok verwijderen, een nieuw blok maken en plakken.
4. "Kop 1/2/3" telde de koppen van deze pagina, niet die van het document: je kreeg een `h3`.
"""
from __future__ import annotations

import re

import pytest

from conftest import js_zonder_uitleg
from nooch_village.cockpit2_util import BLOK_MENU, blok_menu
import pathlib

CSS = (pathlib.Path(__file__).resolve().parents[1]
       / "nooch_village" / "static" / "nooch.css").read_text()
JS = (pathlib.Path(__file__).resolve().parents[1]
      / "nooch_village" / "static" / "nooch.js").read_text()


def _fn(naam: str) -> str:
    """De body van één functie uit `nooch.js`, zonder de uitleg erboven."""
    kaal = js_zonder_uitleg(JS)
    assert f"function {naam}(" in kaal, f"{naam} bestaat niet"
    return kaal.split(f"function {naam}(")[1].split("\n  function ")[0]


# ── Deel 2: het menu zweeft ──────────────────────────────────────────────────
def test_het_menu_wordt_gepositioneerd_en_niet_opgehangen():
    """`appendChild` zette hem waar het blok toevallig stond; op een lange pagina viel hij
    daarmee onder de vouw."""
    open_ = _fn("blokMenuOpen")
    assert "zweefBij(menu, blok.getBoundingClientRect())" in open_


def test_het_hergebruikt_de_bestaande_positioneerder():
    """Een derde implementatie zou betekenen dat het ene ding na een wijziging anders zweeft dan
    het andere — dezelfde reden die boven `NV.sleep` staat."""
    kaal = js_zonder_uitleg(JS)
    assert kaal.count("function zweefBij(") == 1
    assert kaal.count("zweefBij(") >= 4, "niet alle drie de zwevers gebruiken hem"


def test_het_sjabloon_draagt_de_zweef_klasse():
    """`zweefBij` rekent in VENSTERcoördinaten, en dat werkt alleen met `position:fixed`."""
    assert "wb-menu-zwevend" in blok_menu()
    m = re.search(r"(?:^|[};])\s*\.wb-menu-zwevend\{([^}]*)\}", CSS, re.M)
    assert m and "position:fixed" in m.group(1)


def test_de_greep_acties_blijven_bij_hun_greep():
    """Ze delen de `.wb-menu`-vorm maar niet dit gedrag: omhoog/omlaag/verwijderen horen wél bij
    de greep waar je op klikte, niet zwevend ergens anders."""
    m = re.search(r"(?:^|[};])\s*\.wb-menu\{([^}]*)\}", CSS, re.M)
    assert m and "position:absolute" in m.group(1)
    kaal = js_zonder_uitleg(JS)
    greep = kaal.split("function greepVoor(")[1].split("\n  function ")[0]
    assert "wb-menu-zwevend" not in greep, "het greep-menu is ook gaan zweven"


def test_er_is_een_menu_tegelijk():
    """Twee open menu's laten je raden bij welk blok je bezig bent."""
    kaal = js_zonder_uitleg(JS)
    assert "function sluitBlokMenu()" in kaal
    assert "sluitBlokMenu();" in _fn("blokMenuOpen"), "een tweede menu blijft naast het eerste open"


def test_escape_sluit_hem_nog_steeds():
    assert 'e.key === "Escape"' in _fn("blokMenu")


# ── Deel 3: een bestaand blok omzetten ───────────────────────────────────────
def test_de_greep_heeft_wijzig_type():
    kaal = js_zonder_uitleg(JS)
    acties = kaal.split("var GREEP_ACTIES")[1].split("];")[0]
    assert '"type"' in acties and "wijzig type" in acties


def test_het_staat_bovenaan_want_het_raakt_de_inhoud():
    """De drie eronder verplaatsen of verwijderen alleen."""
    kaal = js_zonder_uitleg(JS)
    acties = kaal.split("var GREEP_ACTIES")[1].split("];")[0]
    assert acties.index('"type"') < acties.index('"omhoog"')


def test_het_opent_hetzelfde_menu():
    """DEZELFDE TABEL VAN DE SERVER. Een tweede lijst bloktypes zou de plek zijn waar het
    vocabulaire uiteen gaat lopen — precies wat `blok_menu()` voorkomt."""
    actie = _fn("blokActie")
    assert 'actie === "type"' in actie
    assert "blokMenuOpen(blok, body)" in actie


def test_het_commando_werkt_op_de_bestaande_inhoud():
    """`execCommand` werkt op de SELECTIE, dus zonder iets te selecteren gebeurt er niets. Bij de
    `/`-weg is dat de streep; bij een bestaand blok de inhoud die er al staat."""
    kies = _fn("kiesInhoud")
    assert "streepNode(blok)" in kies, "de streep-weg is verdwenen"
    assert "firstElementChild" in kies, "een blok met inhoud levert niets om op te werken"


def test_de_chrome_blijft_buiten_de_selectie():
    """De greep en zijn menu hangen ín het blok; meeselecteren maakt er een kop van mét het
    greep-icoon erin."""
    assert 'hasAttribute("data-chrome")' in _fn("kiesInhoud")


def test_zonder_streep_gaat_er_niets_stuk():
    """`blokMenuKies` begon met `if (!n) return` op het streep-knooppunt; op een bestaand blok is
    dat er niet, dus zou hij er meteen uit zijn gestapt."""
    kies = _fn("blokMenuKies")
    assert "kiesInhoud(blok)" in kies
    assert "streepNode(blok)" not in kies, "hij zoekt de streep nog rechtstreeks"


def test_het_opruimen_van_de_streep_is_voorwaardelijk():
    """Bij "wijzig type" is er geen streep om weg te halen; dat mag geen fout geven."""
    kies = _fn("blokMenuKies")
    na = kies[kies.index("execCommand(knop"):]
    assert "if (streep) streep.remove();" in na


def test_het_uitvoerpad_is_niet_veranderd():
    """"Het uitvoerpad blijft hetzelfde execCommand/formatBlock- of `bron`-pad als nu.\""""
    kies = _fn("blokMenuKies")
    assert 'knop.dataset.wikiCmd === "bron"' in kies
    assert "document.execCommand(knop.dataset.wikiCmd" in kies
    assert "NV.blokNormaliseer(body)" in kies and "grepen(body, true)" in kies


# ── Deel 4: de kop-labels ────────────────────────────────────────────────────
def test_de_koppen_heten_naar_wat_ze_worden():
    """"Kop 1" telde de koppen van deze pagina, niet die van het document: `_md` begint bij h3,
    want de paginatitel is de h1. Wie "Kop 1" koos kreeg dus geen h1."""
    per_tag = {tag: label for tag, label, _c, _a in BLOK_MENU}
    assert per_tag["h3"] == "H2" and per_tag["h4"] == "H3" and per_tag["h5"] == "H4"


def test_alleen_het_label_veranderde():
    """De tag en het `execCommand`-argument blijven h3/h4/h5, dus de markdown-opslag is niet
    geraakt. Zou dat wel zo zijn, dan verschuift elke bestaande kop een niveau."""
    koppen = [(t, c, a) for t, _l, c, a in BLOK_MENU if c == "formatBlock" and t.startswith("h")]
    assert koppen == [("h3", "formatBlock", "<h3>"),
                      ("h4", "formatBlock", "<h4>"),
                      ("h5", "formatBlock", "<h5>")]


def test_de_labels_staan_in_het_sjabloon():
    html = blok_menu()
    for label in ("H2", "H3", "H4"):
        assert f">{label}</button>" in html


def test_de_oude_namen_zijn_weg():
    labels = {label for _t, label, _c, _a in BLOK_MENU}
    assert not (labels & {"Kop 1", "Kop 2", "Kop 3"})
