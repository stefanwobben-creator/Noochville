"""Het afbeelding-blok: `![alt](url)` (24 september 2026).

DIT REPAREERT TEGELIJK EEN BESTAANDE FOUT. `_md` kende de afbeeldings-vorm niet: de link-vervanging
matchte alleen `[tekst](url)`, dus `![alt](url)` werd een LETTERLIJKE uitroepteken gevolgd door een
gewone link. Op het scherm stond dan `!Batch4` met een link erachter.

DE UITROEPTEKEN IS INTENTIE, GEEN URL-EIGENSCHAP, en dat is de reden dat hij moet meereizen. De
embed-kaart leidt zijn soort af uit de url (`.jpg` → afbeelding), maar een Drive-link naar een foto
heeft geen extensie. Schrijft iemand `![foto](https://drive.google.com/uc?id=…)`, dan zegt hij
expliciet "dit is een afbeelding" — en dat staat nergens anders. Daarom draagt de link
`data-beeld`, zoals een codeblok zijn `data-taal` draagt en een wiki-verwijzing zijn `data-ref`:
een stuk bron dat door de weergave heen moet.

GEEN `<img>`, zoals afgesproken in het ontwerp. Een afbeelding-embed toont een kaart met het alt-
label. Inline laden zou elke paginaweergave een verzoek naar een derde partij laten doen, en de
Drive-links die dit dorp gebruikt renderen zonder sessie toch niet.

OP PROD STAAN NUL AFBEELDINGEN (gemeten). Deze stap verandert dus geen enkele bestaande pagina —
behalve dat de `!`-bug weg is, en die kwam ook nergens voor.
"""
from __future__ import annotations

import pytest

from nooch_village.cockpit2_util import _md, _md_naar_bron


def _rondgang(bron: str) -> bool:
    eerste = _md(bron)
    return _md(_md_naar_bron(eerste)) == eerste


# ── 1. De bestaande fout ─────────────────────────────────────────────────────
def test_het_uitroepteken_lekt_niet_meer_als_tekst():
    """DE BUG DIE DIT OPLOST. Vóór vandaag: `!` gevolgd door een gewone link."""
    html = _md("![Batch4](https://example.org/foto.jpg)")
    assert ">!" not in html and "!<a" not in html


# ── 2. Herkenning ────────────────────────────────────────────────────────────
def test_een_afbeelding_op_een_eigen_regel_wordt_een_embed():
    html = _md("![Batch4](https://example.org/foto.jpg)")
    assert "<figure" in html and "emb--afbeelding" in html


def test_de_intentie_wint_van_de_url():
    """Een Drive-link heeft geen extensie. Zonder het uitroepteken zou dit een `drive`-kaart zijn;
    mét is het een afbeelding, want dat is wat de schrijver zei."""
    zonder = _md("https://drive.google.com/uc?id=abc")
    met = _md("![foto](https://drive.google.com/uc?id=abc)")
    assert "emb--drive" in zonder
    assert "emb--afbeelding" in met


def test_het_alt_label_staat_op_de_kaart():
    html = _md("![Batch4 toepuffs](https://example.org/foto.jpg)")
    assert "Batch4 toepuffs" in html


def test_er_wordt_geen_img_geladen():
    """Bewuste keuze uit het ontwerp: geen verzoek naar een derde partij bij elke paginaweergave,
    en een Drive-link rendert zonder sessie toch niet."""
    assert "<img" not in _md("![x](https://example.org/foto.jpg)")


def test_een_afbeelding_in_een_zin_blijft_inline():
    """Alleen een regel die ALLEEN de afbeelding is wordt een kaart — zelfde grens als bij de
    gewone embed."""
    html = _md("zie ![foto](https://example.org/f.jpg) hier")
    assert "<figure" not in html
    assert "<a " in html


# ── 3. De rondgang ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("bron", [
    "![Batch4](https://example.org/foto.jpg)",
    "![foto](https://drive.google.com/uc?id=abc)",
    "zie ![foto](https://example.org/f.jpg) hier",
    "tekst\n\n![foto](https://example.org/f.png)\n\nmeer tekst",
])
def test_de_rondgang_blijft_gelijk(bron):
    assert _rondgang(bron), f"de rondgang breekt op {bron!r}"


def test_het_uitroepteken_komt_terug():
    """Zonder dit wordt een afbeelding na één bewerkronde een gewone link, en is de intentie weg."""
    bron = "![Batch4](https://example.org/foto.jpg)"
    assert _md_naar_bron(_md(bron)) == bron


def test_een_gewone_link_krijgt_geen_uitroepteken():
    bron = "[Batch4](https://example.org/rapport.pdf)"
    assert _md_naar_bron(_md(bron)) == bron
