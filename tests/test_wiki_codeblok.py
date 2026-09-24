"""Het codeblok: een ```-hek wordt één blok in plaats van losse alinea's (24 september 2026).

WAT ER NU GEBEURT. `_md` leest regel voor regel, dus een codeblok van vijf regels wordt vijf
alinea-blokken met een letterlijke ``` erboven en eronder. Het is niet stuk — de rondgang
overleeft het, want het is gewone tekst — maar het ziet er niet uit als code, en je kunt er niet
als blok mee omgaan.

DIT IS DE EERSTE MEERREGELIGE CONSTRUCTIE. `_md` was bewust regel-voor-regel; een hek loopt over
regels heen en vraagt dus een toestand in de renderlus. Dat is de architectuurwijziging in deze
stap, en de reden dat hij apart van de tabel staat.

WAT ER OP HET SPEL STAAT, en dit is geen theorie. `copycheck.py` parseert met
`_FENCE = re.compile(r"```check\\s*\\n(.*?)```")` de verboden-woordenlijsten uit vier policies:
COPYCHECK-001, POSITIONSTAT-001, TONEOFVOICE-001 en STANCE-001. Drie daarvan dragen een
```check-hek met JSON erin. Verminkt de rondgang dat hek of zijn taal-tag, dan stopt de
copy-checker STIL — hij vindt dan gewoon geen lijst meer. Daarom toetst dit bestand niet alleen
de rondgang maar ook of die regex er daarna nog op past.

DE TAAL-TAG REIST MEE als `data-taal`, net zoals een wiki-verwijzing zijn oorspronkelijke tekst
meedraagt in `data-ref`. Dat is geen stempel maar een stuk bron dat door de weergave heen moet:
zonder die tag komt ```check terug als een kaal ``` en is de betekenis weg.
"""
from __future__ import annotations

import re

import pytest

from nooch_village.cockpit2_util import BLOK_SOORTEN, _md, _md_naar_bron

CHECK_BLOK = '```check\n{"verboden": ["een", "twee"]}\n```'


def _rondgang(bron: str) -> bool:
    eerste = _md(bron)
    return _md(_md_naar_bron(eerste)) == eerste


# ── 1. Het wordt één blok ────────────────────────────────────────────────────
def test_een_hek_wordt_een_codeblok():
    html = _md("```\nvar x = 1;\n```")
    assert "<pre" in html and "<code>" in html
    assert "```" not in html, "het hek staat nog als tekst op het scherm"


def test_de_soortentabel_kent_het():
    """`nooch.js` heeft geen eigen lijst; zonder deze regel verliest een codeblok zijn greep
    zodra iemand er een blokcommando op loslaat."""
    assert BLOK_SOORTEN.get("pre") == "code"


def test_het_is_een_blok_en_niet_vijf():
    html = _md("```\neen\ntwee\ndrie\n```", blokken=True)
    assert html.count("class='wb'") == 1, "het codeblok valt nog uiteen in losse alinea's"
    assert "data-blok='code'" in html


def test_de_regels_binnen_het_hek_blijven_regels():
    html = _md("```\neen\ntwee\n```")
    inhoud = re.search(r"<code>(.*?)</code>", html, re.S).group(1)
    assert inhoud == "een\ntwee"


def test_tekst_eromheen_blijft_gewoon():
    html = _md("ervoor\n\n```\ncode\n```\n\nerna", blokken=True)
    assert "ervoor" in html and "erna" in html
    assert html.count("data-blok='code'") == 1


# ── 2. De rondgang ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("bron", [
    "```\nvar x = 1;\n```",
    CHECK_BLOK,
    "ervoor\n\n```\ncode\n```\n\nerna",
    "```\n\nmet een lege regel erin\n\n```",
    "```python\nprint(1)\n```",
])
def test_de_rondgang_blijft_gelijk(bron):
    assert _rondgang(bron), f"de rondgang breekt op {bron!r}"


def test_de_bron_komt_letterlijk_terug():
    assert _md_naar_bron(_md(CHECK_BLOK)) == CHECK_BLOK


def test_de_taal_tag_overleeft():
    """Zonder dit komt ```check terug als een kaal ``` en is de betekenis weg."""
    assert "check" in _md_naar_bron(_md(CHECK_BLOK)).split("\n")[0]


def test_lege_regels_in_code_blijven_staan():
    """In code hebben lege regels betekenis. Dit is precies waarom de platsla-lus eerst weg
    moest (#587)."""
    bron = "```\neen\n\n\ntwee\n```"
    assert _md_naar_bron(_md(bron)) == bron


def test_inspringing_blijft_staan():
    bron = "```\ndef f():\n    return 1\n```"
    assert _md_naar_bron(_md(bron)) == bron


def test_een_link_in_een_codeblok_raakt_niet_verminkt():
    """GEVONDEN DOOR EEN MUTATIE die groen bleef. `_md` vervangt `[tekst](url)` vóór de regellus
    draait, dus zo'n link belandt ook ín een codeblok als `<a>`. Ving de parser die tekst dan weg
    bij de linktekst, dan sloot `</a>` af met een LEEG label en kwam er `de docs[](https://…)`
    uit de rondgang — inhoud kapot.

    Op prod staat er in geen enkel codeblok een link (gemeten: 0 in 4 blokken), dus dit is
    preventief. Dat maakt het niet minder echt: het is stil verlies zodra iemand het wél doet."""
    bron = "```\nzie [de docs](https://example.org) hier\n```"
    assert _md_naar_bron(_md(bron)) == bron
    assert _rondgang(bron)


# ── 3. Wat er NIET kapot mag: de copy-checker ────────────────────────────────
def test_de_copycheck_regex_past_er_na_een_rondgang_nog_op():
    """DE TOETS DIE ERTOE DOET. `copycheck._FENCE` haalt de verboden-woordenlijsten uit vier
    policies. Overleeft het hek de rondgang niet, dan vindt hij stil geen lijst meer — geen
    foutmelding, gewoon een checker die niets meer afkeurt."""
    from nooch_village.copycheck import _FENCE
    bron = ('Wat tekst erboven.\n\n```check\n{"verboden": ["At Nooch, we believe"],\n'
            ' "bron_vereist": ["biodegradable"]}\n```\n\nEn tekst eronder.')
    voor = _FENCE.search(bron)
    assert voor, "de proefbron matcht de regex niet; dan meet deze toets niets"
    na = _FENCE.search(_md_naar_bron(_md(bron)))
    assert na, "na een bewerkronde vindt copycheck het hek niet meer"
    assert na.group(1) == voor.group(1), "de inhoud van het hek is veranderd"


# ── 4. Randgevallen ──────────────────────────────────────────────────────────
def test_een_hek_dat_niet_gesloten_wordt_verliest_geen_tekst():
    """Fail-soft: liever een codeblok tot het eind dan een halve pagina kwijt."""
    html = _md("```\nvar x = 1;")
    assert "var x = 1;" in html


def test_een_hek_midden_in_een_regel_is_geen_hek():
    html = _md("zie ``` hier in een zin")
    assert "<pre" not in html


def test_een_regel_die_met_een_hek_begint_maar_doorloopt_is_geen_hek():
    """DEZE DISCRIMINEERT, de vorige niet: "zie ``` hier" begint niet met een hek, dus `.match()`
    faalt daar sowieso en de toets bleef groen toen ik de anker-tekens uit de regex haalde. Een
    regel die er WEL mee begint maar daarna doortypt is het echte grensgeval — met `$` is dat
    geen hek, zonder wel."""
    html = _md("```js dit is geen hek maar een zin")
    assert "<pre" not in html
    assert "dit is geen hek" in html
