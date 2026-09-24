"""Het taak-blok: een lijst met vinkjes is een eigen soort, en je kunt ze aanzetten (24 sept 2026).

WAAR HET STOND. De wiki rendert `- [ ] tekst` al als een vakje, maar met `disabled` erop en met de
opmerking "aanvinken met de muis is brok 3" — een knop die niets doet. En het BLOK was een gewone
`ul`, dus de greep en het menu zagen geen verschil met een opsomming.

TWEE DINGEN, EN ALLEBEI NODIG. Een taak-blok waarin je niets kunt aanvinken is geen taak-blok; een
aanvinkbaar vakje zonder eigen bloksoort is een opsomming met een rare li. Ze horen bij elkaar.

DE SOORT WORDT IN DE WIKI-LAAG GEZET, niet in `_md`. Dat is het besluit van 22 september en het
staat nog: `_md` rendert ook elke reactie en elk kanaalbericht, en een dode checkbox in een
chatbericht is verwarrender dan hij waard is. De wiki markeert het blok dus ná de substitutie —
dezelfde plek en dezelfde techniek als het vakje zelf.

HET ATTRIBUUT, NIET DE PROPERTY. Een aangevinkt vakje verandert zijn `checked`-PROPERTY, maar
`innerHTML` schrijft het ATTRIBUUT. Zonder synchronisatie vlak vóór het opslaan verdampt elk vinkje
dat je zet — exact dezelfde val als bij de textarea van het tabel-blok, en daar gevonden.
"""
from __future__ import annotations

import pathlib
import re

from nooch_village.cockpit2_util import _md, _md_naar_bron
from nooch_village.views.wiki import _body_html

TAKEN = "- [ ] open punt\n- [x] afgerond punt"


def _js() -> str:
    js = (pathlib.Path(__file__).resolve().parents[1]
          / "nooch_village" / "static" / "nooch.js").read_text()
    js = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
    return re.sub(r"^\s*//[^\n]*", " ", js, flags=re.M)


# ── 1. Het is een eigen bloksoort ────────────────────────────────────────────
def test_een_lijst_met_vinkjes_is_een_taak_blok():
    html = _body_html(TAKEN, [], blokken=True)
    assert "data-blok='taak'" in html
    assert "data-blok='ul'" not in html


def test_een_gewone_opsomming_blijft_een_opsomming():
    html = _body_html("- een\n- twee", [], blokken=True)
    assert "data-blok='ul'" in html
    assert "data-blok='taak'" not in html


def test_de_soort_wordt_in_de_wiki_laag_gezet_en_niet_in_md():
    """Besluit 22 september: `_md` rendert ook reacties en kanaalberichten, en een dode checkbox
    in een chatbericht is verwarrender dan hij waard is."""
    assert "data-blok='taak'" not in _md(TAKEN, blokken=True)
    assert "type='checkbox'" not in _md(TAKEN, blokken=True)


# ── 2. Aanvinken werkt ───────────────────────────────────────────────────────
def test_het_vakje_is_niet_meer_dood():
    html = _body_html(TAKEN, [], blokken=True)
    assert "disabled" not in html, "het vakje is nog steeds een knop die niets doet"


def test_een_aangevinkt_vakje_staat_aan():
    html = _body_html(TAKEN, [], blokken=True)
    assert html.count("checked") == 1, "precies één van de twee taken hoort aan te staan"


def test_de_weg_terug_leest_het_vinkje():
    html = _body_html(TAKEN, [], blokken=True)
    assert _md_naar_bron(html) == TAKEN


def test_een_omgezet_vinkje_komt_in_de_bron():
    """Wat de gebruiker aanvinkt moet in de markdown belanden, anders is het een knop zonder
    gevolg — precies wat het `disabled` verhinderde."""
    html = _body_html("- [ ] open punt", [], blokken=True)
    aangevinkt = html.replace("<input type='checkbox'", "<input type='checkbox' checked")
    assert _md_naar_bron(aangevinkt) == "- [x] open punt"


# ── 3. De twee vallen die dit blok deelt met het tabel-blok ──────────────────
def test_het_vinkje_wordt_gesynchroniseerd_voor_het_opslaan():
    """HETZELFDE ALS BIJ DE TEXTAREA. Een vakje verandert zijn `checked`-PROPERTY; `innerHTML`
    schrijft het ATTRIBUUT. Zonder deze synchronisatie verdampt elk vinkje dat je zet."""
    bron = _js()
    assert "type=\"checkbox\"" in bron or "checkbox" in bron
    i = bron.index("wiki-body-veld")
    sync = bron.rfind("toggleAttribute(\"checked\"", 0, i)
    assert sync > 0, "er wordt niets gesynchroniseerd, of het staat ná het uitlezen"


def test_de_pas_laat_een_taak_blok_met_rust():
    """De normaliseerpas kent alleen tag→soort, en de tag is hier `ul`. Zonder een uitzondering
    zet hij `data-blok` terug op `ul` en is het blok zijn identiteit kwijt — dezelfde vorm als de
    guard voor het open bewerkvlak."""
    bron = _js()
    # OP DE CODE, NIET OP EEN SCHRIJFWIJZE: mijn eerste versie zocht `data-blok="taak"` en
    # `'taak'`, en de code schrijft `dataset.blok === "taak"`. Dan faalt de toets op de
    # aanhalingstekens in plaats van op het gedrag.
    assert 'dataset.blok === "taak"' in bron


# ── 4. De rondgang ───────────────────────────────────────────────────────────
def test_de_rondgang_blijft_gelijk():
    eerste = _body_html(TAKEN, [], blokken=True)
    assert _body_html(_md_naar_bron(eerste), [], blokken=True) == eerste


def test_er_komt_geen_spatie_bij_per_bewerkronde():
    """Stond de spatie tussen vakje en tekst in de HTML, dan schreef de weg terug er één bij de
    zijne — `[ ] open` werd `[ ]  open`, elke keer opslaan een spatie erbij."""
    bron = TAKEN
    for _ in range(3):
        bron = _md_naar_bron(_body_html(bron, [], blokken=True))
    assert bron == TAKEN


def test_het_juiste_vakje_wordt_gezet_en_niet_alleen_het_juiste_aantal():
    """GEMETEN IN DE BROWSER, en bijna misgegaan. Vink je de eerste taak aan en de tweede uit, dan
    blijft het AANTAL `checked` gelijk — één. Een toets die telt ziet dus niets, ook als de sync
    stukgaat en het oude vakje blijft staan. Deze kijkt naar WELK vakje."""
    bron = "- [ ] eerste\n- [x] tweede"
    html = _body_html(bron, [], blokken=True)
    # de gebruiker zet de eerste aan en de tweede uit
    li = html.split("<li")
    omgezet = ("<li" + li[1].replace("type='checkbox'", "type='checkbox' checked")
               + "<li" + li[2].replace(" checked", ""))
    terug = _md_naar_bron(html.split("<li")[0] + omgezet)
    assert terug == "- [x] eerste\n- [ ] tweede", terug
