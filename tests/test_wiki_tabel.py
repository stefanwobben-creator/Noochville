"""Het tabel-blok: pipe-rijen worden één tabel (24 september 2026).

DE BRON IS DE GANGBARE MARKDOWN-CONVENTIE: een rij `| a | b |`, met op de tweede regel een
scheidingsrij van streepjes. Alle vijf de tabellen op prod (31 rijen in DESIGNSYSTEM-001) hebben
precies die vorm, dus er is geen dialect nodig.

WAT `_md` NU DOET: elke pipe-regel wordt een eigen alinea-blok. Niet stuk — het is gewone tekst en
de rondgang overleeft het — maar het ziet eruit als een lijst streepjes in plaats van een tabel.

DE SCHEIDINGSRIJ WORDT OPNIEUW OPGEBOUWD op de weg terug, en dat is bewust. Blok 1 op prod heeft
drie kolommen maar een scheidingsrij met twee cellen; dat parseert prima en niemand ziet het,
maar het is geen bron die je letterlijk wilt bewaren. De belofte gaat over de HTML
(`_md(_md_naar_bron(_md(x))) == _md(x)`), niet over teken-voor-teken gelijke markdown — en die
blijft gelden.

GEEN TABEL ZONDER SCHEIDINGSRIJ. Een losse regel die toevallig met een pipe begint is geen tabel;
die blijft een alinea. Anders verandert één streepje in een zin de hele weergave.
"""
from __future__ import annotations

import re

import pytest

from nooch_village.cockpit2_util import BLOK_SOORTEN, _md, _md_naar_bron

TABEL = "| Token | Hex |\n|---|---|\n| Brand Green | #00FF00 |\n| Black | #000000 |"


def _rondgang(bron: str) -> bool:
    eerste = _md(bron)
    return _md(_md_naar_bron(eerste)) == eerste


# ── 1. Herkenning ────────────────────────────────────────────────────────────
def test_pipe_rijen_met_een_scheidingsrij_worden_een_tabel():
    html = _md(TABEL)
    assert "<table" in html and "<th>" in html and "<td>" in html
    assert "|" not in re.sub(r"<[^>]+>", "", html), "er staan nog pipes op het scherm"


def test_de_soortentabel_kent_het():
    assert BLOK_SOORTEN.get("table") == "tabel"


def test_het_is_een_blok_en_niet_vier():
    html = _md(TABEL, blokken=True)
    assert html.count("class='wb'") == 1
    assert "data-blok='tabel'" in html


def test_de_eerste_rij_is_de_kop():
    html = _md(TABEL)
    assert "<th>Token</th>" in html and "<th>Hex</th>" in html
    assert "<td>Brand Green</td>" in html


def test_zonder_scheidingsrij_is_het_geen_tabel():
    """Eén regel die toevallig met een pipe begint mag de weergave niet omgooien."""
    html = _md("| dit is gewoon tekst met een pipe")
    assert "<table" not in html
    assert "dit is gewoon tekst" in html


def test_twee_pipe_regels_zonder_scheiding_blijven_alinea():
    html = _md("| een |\n| twee |")
    assert "<table" not in html


def test_tekst_eromheen_blijft_gewoon():
    html = _md("ervoor\n\n" + TABEL + "\n\nerna", blokken=True)
    assert "ervoor" in html and "erna" in html
    assert html.count("data-blok='tabel'") == 1


# ── 2. De rondgang ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("bron", [
    TABEL,
    "| A |\n|---|\n| 1 |",
    "ervoor\n\n" + TABEL + "\n\nerna",
    "| A | B | C |\n|---|---|---|\n| 1 | 2 | 3 |",
])
def test_de_rondgang_blijft_gelijk(bron):
    assert _rondgang(bron), f"de rondgang breekt op {bron!r}"


def test_een_scheve_scheidingsrij_wordt_rechtgetrokken():
    """DE ENIGE PLEK WAAR DE BRON VERANDERT, en dat is met opzet: blok 1 op prod heeft drie
    kolommen en een scheidingsrij met twee cellen. Dat parseert prima, maar het is geen bron die
    je letterlijk wilt bewaren. De HTML blijft gelijk — dat is wat de belofte zegt."""
    scheef = "| A | B | C |\n|---|---|\n| 1 | 2 | 3 |"
    assert _rondgang(scheef)
    assert _md_naar_bron(_md(scheef)).split("\n")[1].count("---") == 3


def test_een_link_in_een_cel_overleeft():
    bron = "| Naam | Bron |\n|---|---|\n| X | [docs](https://example.org) |"
    assert _rondgang(bron)
    assert "[docs](https://example.org)" in _md_naar_bron(_md(bron))


def test_lege_cellen_blijven_leeg():
    bron = "| A | B |\n|---|---|\n| 1 |  |"
    assert _rondgang(bron)


# ── 3. De echte tabellen van prod ────────────────────────────────────────────
def test_de_vorm_van_de_echte_tabellen():
    """Zoals ze in DESIGNSYSTEM-001 staan: kop, scheidingsrij, rijen — en cellen met backticks
    erin, want die pagina gebruikt inline code voor hex-waarden."""
    bron = ("| Token | Hex | Usage |\n|---|---|\n"
            "| Brand Green | `#00FF00` | Primary brand color. |")
    assert _rondgang(bron)
    html = _md(bron)
    assert "<table" in html
    assert "#00FF00" in html


# ── 4. Het bewerkvlak (tabel en code bewerk je als tekst) ────────────────────
def _js() -> str:
    import pathlib
    import re
    js = (pathlib.Path(__file__).resolve().parents[1]
          / "nooch_village" / "static" / "nooch.js").read_text()
    js = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
    return re.sub(r"^\s*//[^\n]*", " ", js, flags=re.M)


def test_het_bewerkvlak_komt_terug_als_ruwe_markdown():
    """DE HELE ARBEIDSVERDELING IN ÉÉN TOETS. De browser levert tekst, de server maakt er een
    blok van. Er komt geen tweede renderer in JS — dus wat in het bewerkvlak staat gaat letterlijk
    door en wordt bij het opslaan opnieuw door `_md` gehaald."""
    html = ("<div class='wb' data-blok='tabel'><textarea class='wb-bron' data-blok-bron>"
            "| A | B |\n|---|---|\n| 1 | 2 |</textarea></div>")
    bron = _md_naar_bron(html)
    assert bron == "| A | B |\n|---|---|\n| 1 | 2 |"
    assert "<table" in _md(bron), "de bewerkte bron rendert niet meer als tabel"


def test_een_bewerkt_codeblok_komt_ook_terug():
    html = ("<div class='wb' data-blok='code'><textarea class='wb-bron' data-blok-bron>"
            "```check\n{\"verboden\": []}\n```</textarea></div>")
    bron = _md_naar_bron(html)
    assert bron.startswith("```check")
    assert "<pre" in _md(bron)


def test_alleen_een_tabel_en_een_codeblok_krijgen_de_ingang():
    """Bij een alinea zou "bewerk als tekst" verwarrend zijn: die bewerk je gewoon ter plekke."""
    bron = _js()
    assert 'blok.dataset.blok === "tabel" || blok.dataset.blok === "code"' in bron


def test_de_browser_kent_maar_een_klein_stukje_markdown():
    """`blokBron` is de ENIGE plek waar de browser iets van het formaat weet, en het blijft bij
    pipes en hekken. De weg terug doet de server."""
    bron = _js()
    assert "function blokBron(" in bron
    assert bron.count("function blokBron(") == 1


def test_de_pas_laat_een_open_bewerkvlak_met_rust():
    """Zonder deze regel ziet de normaliseerpas alleen een <textarea>, vindt die niet in de
    soorten-tabel, en maakt er een alinea van — het blok dat je bewerkt verliest zijn identiteit."""
    bron = _js()
    assert 'querySelector("[data-blok-bron]")' in bron


def test_het_bewerkvlak_wordt_gesynchroniseerd_voor_het_opslaan():
    """GEMETEN IN DE BROWSER, NIET BEDACHT. Een `<textarea>` geeft in `innerHTML` zijn
    OORSPRONKELIJKE inhoud terug, niet wat de gebruiker erin typte. Zonder deze synchronisatie
    wordt elke bewerking van een tabel of codeblok stil weggegooid en staat er na het opslaan
    weer de oude tekst — geen foutmelding, gewoon een wijziging die verdampt."""
    bron = _js()
    assert 'textarea[data-blok-bron]' in bron
    i = bron.index("wiki-body-veld")
    assert bron.rindex("t.textContent = t.value") < i, \
        "de synchronisatie staat NA het uitlezen van de body; dan is hij te laat"
