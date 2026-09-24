"""Het embed-blok: een regel die alleen een link is, wordt een kaart (24 september 2026).

WAAROM DIT VEILIG KON. Gemeten over alle 121 artefacten op prod: van de 1151 regels is er
**nul** die alleen een markdown-link is, en **één** die alleen een kale url is (in de
gearchiveerde policy `NOOCHEARTH-001`). Automatisch herkennen verandert het uiterlijk van precies
die ene regel. Dat is het soort getal dat het verschil maakt tussen "automatisch mag" en "alleen
expliciet".

DE SOORT WORDT BIJ HET RENDEREN AFGELEID, NIET OPGESLAGEN. Dezelfde regel als bij
`wiki.grond_status` en bij `domeinen.bakje_van`: een vergelijking, geen stempel. Wijst een link
morgen naar een pdf in plaats van een video, dan volgt de kaart — er staat nergens een verouderde
`data-soort` die iemand moet bijwerken.

GEEN `<img>`, EN DAT IS EEN KEUZE. Een afbeelding-embed toont een kaart met de bestandsnaam, niet
het plaatje zelf. Inline laden zou elke paginaweergave een verzoek naar een derde partij laten
doen, en de Drive-links die dit dorp gebruikt renderen zonder sessie toch niet. Het prototype doet
het ook zo.

DE RONDGANG IS DE HARDE EIS. `_md(_md_naar_bron(_md(bron))) == _md(bron)` moet blijven gelden,
ook voor de nieuwe vorm — anders eet de editor bij elke bewerking zijn eigen embeds op. Voor een
KALE url betekent dat iets extra's: de weg terug mag er geen `[url](url)` van maken, want dan
staat er na één bewerkronde iets anders in de bron dan de mens typte.
"""
from __future__ import annotations

import re

import pytest

from nooch_village.cockpit2_util import BLOK_SOORTEN, _md, _md_naar_bron


def _rondgang(bron: str) -> bool:
    """De belofte: twee keer renderen met de weg terug ertussen geeft hetzelfde scherm."""
    eerste = _md(bron)
    return _md(_md_naar_bron(eerste)) == eerste


# ── 1. Herkenning ────────────────────────────────────────────────────────────
@pytest.mark.parametrize("bron", [
    "https://example.org/rapport.pdf",
    "[Batch4_QA_report.pdf](https://example.org/rapport.pdf)",
])
def test_een_regel_die_alleen_een_link_is_wordt_een_embed(bron):
    html = _md(bron)
    assert "<figure" in html, f"geen embed-kaart voor {bron!r}"


def test_een_link_middenin_een_zin_blijft_een_gewone_link():
    """DE GRENS. Zou elke link een kaart worden, dan verandert elke bestaande pagina van vorm."""
    html = _md("Zie [het rapport](https://example.org/r.pdf) voor de cijfers.")
    assert "<figure" not in html
    assert "<a href='https://example.org/r.pdf'" in html


def test_een_kale_url_middenin_een_zin_blijft_tekst():
    html = _md("Kijk op https://example.org en dan verder.")
    assert "<figure" not in html
    assert "<a " not in html


def test_twee_links_op_een_regel_zijn_geen_embed():
    html = _md("[een](https://a.nl) [twee](https://b.nl)")
    assert "<figure" not in html


def test_een_link_zonder_http_wordt_geen_embed():
    """Zelfde poort als `_md` al had: zonder http(s)-schema geen link, dus ook geen kaart."""
    html = _md("[lokaal](/decision-coach)")
    assert "<figure" not in html


# ── 2. De soort komt uit de url ──────────────────────────────────────────────
@pytest.mark.parametrize("url,soort", [
    ("https://example.org/foto.jpg", "afbeelding"),
    ("https://example.org/foto.PNG", "afbeelding"),
    ("https://example.org/x.webp", "afbeelding"),
    ("https://www.youtube.com/watch?v=abc", "video"),
    ("https://youtu.be/abc", "video"),
    ("https://vimeo.com/123", "video"),
    ("https://example.org/clip.mp4", "video"),
    ("https://example.org/rapport.pdf", "pdf"),
    ("https://docs.google.com/document/d/abc/edit", "drive"),
    ("https://drive.google.com/file/d/abc/view", "drive"),
    ("https://example.org/pagina", "link"),
])
def test_de_soort_wordt_uit_de_url_afgeleid(url, soort):
    html = _md(url)
    assert f"emb--{soort}" in html, f"{url} werd geen {soort}: {html[:160]}"


def test_de_soort_staat_nergens_opgeslagen():
    """Afleiden, geen stempel: er is geen veld en geen attribuut dat de soort bewaart, dus er kan
    ook niets verouderen. De klasse op het scherm is uitvoer, geen opslag."""
    bron = "https://example.org/foto.jpg"
    assert "soort" not in _md_naar_bron(_md(bron))
    assert _md_naar_bron(_md(bron)) == bron


# ── 3. De rondgang ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("bron", [
    "https://example.org/rapport.pdf",
    "[Batch4_QA_report.pdf](https://example.org/rapport.pdf)",
    "https://www.youtube.com/watch?v=abc",
    "https://docs.google.com/document/d/abc/edit",
    "Een kop\n\nhttps://example.org/foto.jpg\n\nTekst erna.",
    "- lijst\n- items\n\nhttps://example.org/x.pdf\n",
])
def test_de_rondgang_blijft_gelijk(bron):
    assert _rondgang(bron), f"de rondgang breekt op {bron!r}"


def test_een_kale_url_komt_kaal_terug():
    """Zou de weg terug er `[url](url)` van maken, dan staat er na één bewerkronde iets anders in
    de bron dan de mens typte — en dat is precies wat de blokstand moest voorkomen."""
    assert _md_naar_bron(_md("https://example.org/x.pdf")) == "https://example.org/x.pdf"


def test_een_link_met_tekst_houdt_zijn_tekst():
    bron = "[Batch4_QA_report.pdf](https://example.org/rapport.pdf)"
    assert _md_naar_bron(_md(bron)) == bron


def test_een_link_waarvan_de_tekst_de_url_is_buiten_een_embed_blijft_een_link():
    """DE VAL DIE IK BIJNA MAAKTE. "label == url → geef de kale url terug" mag ALLEEN binnen een
    embed gelden. In een zin zou die regel `zie [https://x](https://x) hier` veranderen in
    `zie https://x hier`, en dat is geen link meer — de rondgang breekt dan."""
    bron = "zie [https://example.org](https://example.org) hier"
    assert _rondgang(bron)
    assert "<a href=" in _md(bron)


# ── 4. Chrome telt niet als tekst ────────────────────────────────────────────
def test_het_icoon_is_chrome_en_geen_inhoud():
    """Dezelfde les als de greep (⠿) van brok 3: een decoratief teken dat als tekst wordt
    opgeslagen, staat na één bewerkronde letterlijk in de bron."""
    html = _md("https://example.org/rapport.pdf")
    icoon = re.search(r"<span[^>]*data-chrome[^>]*>([^<]*)</span>", html)
    assert icoon, "het icoon draagt geen data-chrome"
    terug = _md_naar_bron(html)
    assert icoon.group(1).strip() not in terug, "het icoon belandt in de bron"
    assert terug == "https://example.org/rapport.pdf"


def test_het_bronlabel_is_ook_chrome():
    html = _md("https://www.youtube.com/watch?v=abc")
    assert "YouTube" in html, "de herkomst staat niet op de kaart"
    assert "YouTube" not in _md_naar_bron(html), "de herkomst belandt in de bron"


# ── 5. Het blokmodel kent de nieuwe soort ────────────────────────────────────
def test_de_soortentabel_kent_het_embed_blok():
    """`nooch.js` heeft geen eigen lijst: hij krijgt deze tabel als attribuut mee. Zonder deze
    regel verliest een embed zijn greep zodra iemand er een blokcommando op loslaat."""
    assert BLOK_SOORTEN.get("figure") == "embed"


def test_een_embed_krijgt_zijn_eigen_omhulsel_in_de_blokstand():
    html = _md("https://example.org/rapport.pdf", blokken=True)
    assert "data-blok='embed'" in html
    assert html.count("class='wb'") == 1


def test_zonder_de_blokstand_staat_er_geen_omhulsel():
    html = _md("https://example.org/rapport.pdf")
    assert "class='wb'" not in html
    assert "<figure" in html
