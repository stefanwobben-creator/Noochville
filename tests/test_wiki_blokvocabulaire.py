"""Brok 2 van de Notion-stijl wiki: het VOCABULAIRE. Vijf blokken erbij, elk als PAAR.

WAT ER WAS. `_md` kende vijf dingen: `**vet**`, `*schuin*`, `~~door~~`, `## kop` en `- lijst`
(plus `[tekst](url)` en `[[verwijzing]]` inline). Geteld op productie, 105 pagina's: 82 gebruiken
een lijst, 24 vet, 15 een kop, 1 schuin, 0 doorhalen, 0 links. De gemiddelde pagina is 877 tekens
en 7 regels. Dit is het vocabulaire waar een blok-editor iets mee moet kunnen.

WAT ERBIJ KOMT, en waarom precies deze vijf:

    # kop / ### kop     er was maar ÉÉN kopniveau. Een pagina met twee lagen structuur kon niet.
    1. genummerd        179 regels op de project-wall beginnen al met "1. " en renderden als tekst
    > citaat            een geciteerde bron of een afspraak van iemand anders, herkenbaar apart
    ---                 35 regels op de wall zijn al een streep die geen streep werd
    - [ ] taak          de wiki is werkgeheugen; een afvinkbare regel hoort daarbij

DE HARDE REGEL VAN HET ONTWERP: geen renderer zonder terugweg. Een blok dat `_md` wél maakt en
`_md_naar_bron` niet kent, wordt bij het opslaan stilzwijgend platte tekst — precies wat er met
`<strike>` gebeurde (doorhalen wérkte op het scherm en was na opslaan verdwenen). Elke regel
hieronder toetst het paar, nooit één helft.

TWEE DINGEN DIE NIET VANZELF SPREKEN:

  1. `## kop` BLIJFT `<h4>`. `#` wordt h3 en `###` wordt h5, dus de 15 bestaande pagina's met een
     `##`-kop renderen byte voor byte hetzelfde. Een nieuw kopniveau mag geen bestaande pagina
     hertekenen;
  2. DE TAAK IS WIKI-ONLY (besluit Stefan): `_md` kent hem niet, `_body_html` maakt hem. Een dode
     checkbox in een chatbericht is verwarrender dan hij waard is. De terugweg kent hem wél —
     anders zou de wiki zijn eigen vinkjes bij het opslaan opeten.
"""
from __future__ import annotations

import pytest

from nooch_village.cockpit2_util import _md, _md_naar_bron
from nooch_village.views.wiki import _body_html


class _Pagina:
    def __init__(self, pid: str, titel: str):
        self.id, self.title = pid, titel


_PAGS = [_Pagina("NOTE-COMPLI-021", "Claims beleid")]


def _norm(bron: str) -> str:
    return bron.replace("\r\n", "\n").replace("\r", "\n").strip("\n")


# ── 1. Wat er stond blijft staan ────────────────────────────────────────────────────────────
@pytest.mark.parametrize("bron,html", [
    ("## Een kop", "<h4>Een kop</h4>"),
    ("- een\n- twee", "<ul class='fbul'><li>een</li><li>twee</li></ul>"),
    ("**vet** en *schuin* en ~~door~~",
     "<strong>vet</strong> en <em>schuin</em> en <del>door</del>"),
])
def test_het_oude_vocabulaire_rendert_onveranderd(bron, html):
    """15 pagina's hebben een `##`-kop en 82 een lijst. Een nieuw kopniveau erbij mag er geen
    één hertekenen."""
    assert _md(bron) == html


# ── 2. De vijf nieuwe blokken, elk als paar ─────────────────────────────────────────────────
@pytest.mark.parametrize("bron,tag", [
    ("# Grote kop", "h3"),
    ("## Middelste kop", "h4"),
    ("### Kleine kop", "h5"),
])
def test_drie_kopniveaus(bron, tag):
    assert _md(bron) == f"<{tag}>{bron.split(' ', 1)[1]}</{tag}>"
    assert _md_naar_bron(_md(bron)) == bron


def test_een_genummerde_lijst():
    assert _md("1. een\n2. twee") == "<ol class='fol'><li>een</li><li>twee</li></ol>"
    assert _md_naar_bron(_md("1. een\n2. twee")) == "1. een\n2. twee"


def test_een_genummerde_lijst_staat_los_van_een_bolletjeslijst():
    """Twee soorten achter elkaar zijn twee lijsten, geen samengeraapte derde."""
    uit = _md("- bolletje\n1. nummer")
    assert uit == "<ul class='fbul'><li>bolletje</li></ul><ol class='fol'><li>nummer</li></ol>"
    assert _md_naar_bron(uit) == "- bolletje\n1. nummer"


def test_een_citaat():
    assert _md("> iemand anders zei dit") == "<blockquote>iemand anders zei dit</blockquote>"
    assert _md_naar_bron(_md("> iemand anders zei dit")) == "> iemand anders zei dit"


def test_een_scheiding():
    assert _md("boven\n---\nonder") == "boven<br><hr>onder"
    assert _md_naar_bron(_md("boven\n---\nonder")) == "boven\n---\nonder"


def test_een_afvinkbare_taak_alleen_in_de_wiki():
    """BESLUIT STEFAN: een dode checkbox in een chatbericht is verwarrender dan hij waard is.
    `_md` laat de haakjes dus met rust; `_body_html` maakt er een vinkje van."""
    assert _md("- [ ] iets doen") == "<ul class='fbul'><li>[ ] iets doen</li></ul>"
    wiki = _body_html("- [ ] iets doen\n- [x] al gedaan", _PAGS)
    assert "type='checkbox'" in wiki and wiki.count("type='checkbox'") == 2
    assert "checked" in wiki
    assert "[ ]" not in wiki and "[x]" not in wiki


def test_de_taak_komt_terug_als_wat_er_stond():
    """De terugweg kent hem WEL, anders eet de wiki zijn eigen vinkjes op bij het opslaan."""
    for bron in ("- [ ] iets doen", "- [x] al gedaan", "- [ ] een\n- [x] twee\n- gewoon punt"):
        assert _md_naar_bron(_body_html(bron, _PAGS)) == bron


# ── 3. Geen renderer zonder terugweg ────────────────────────────────────────────────────────
_NIEUW = [
    "# Grote kop",
    "### Kleine kop",
    "1. een\n2. twee\n3. drie",
    "> een citaat met **vet** erin",
    "boven\n---\nonder",
    "- [ ] open\n- [x] af",
    "# Kop\n\n1. eerst\n2. daarna\n\n> en iemand zei\n\n---\n\n- [ ] nog doen",
]


@pytest.mark.parametrize("bron", _NIEUW)
def test_elk_nieuw_blok_overleeft_de_rondgang(bron):
    assert _md_naar_bron(_body_html(bron, _PAGS)) == _norm(bron)


@pytest.mark.parametrize("bron", _NIEUW)
def test_elk_nieuw_blok_overleeft_de_rondgang_in_de_blokstand(bron):
    assert _md_naar_bron(_body_html(bron, _PAGS, blokken=True)) == _norm(bron)


@pytest.mark.parametrize("bron", _NIEUW)
def test_de_weergave_verschuift_niet(bron):
    html = _body_html(bron, _PAGS, blokken=True)
    assert _body_html(_md_naar_bron(html), _PAGS, blokken=True) == html


@pytest.mark.parametrize("bron", _NIEUW)
def test_twee_keer_opslaan_verandert_niets_meer_dan_een_keer(bron):
    een = _md_naar_bron(_body_html(bron, _PAGS, blokken=True))
    twee = _md_naar_bron(_body_html(een, _PAGS, blokken=True))
    assert een == twee


def test_elk_nieuw_blok_is_ook_een_blok():
    """Ze moeten meedoen met brok 1, anders kan brok 3 er geen greep aan hangen."""
    import re
    html = _body_html("# Kop\n1. een\n> citaat\n---\n- [ ] taak", _PAGS, blokken=True)
    assert re.findall(r"data-blok='([a-z]+)'", html) == ["h", "ol", "q", "hr", "ul"]


# ── 4. De normalisatie die je moet weten ────────────────────────────────────────────────────
def test_een_genummerde_lijst_hernummert_bij_het_eerste_opslaan():
    """`1. 1. 1.` is geldige markdown en rendert als 1, 2, 3 — het `<ol>` telt zelf. De weg terug
    kan de oorspronkelijke cijfers niet kennen (ze staan niet in de HTML) en schrijft dus 1, 2, 3.

    DE BRON VERANDERT DUS ÉÉN KEER, de WEERGAVE nooit. Dat is de belofte die telt, en hij staat
    hier expliciet zodat niemand hem later als bug aanmerkt."""
    bron = "1. een\n1. twee\n1. drie"
    na = _md_naar_bron(_body_html(bron, _PAGS))
    assert na == "1. een\n2. twee\n3. drie"
    assert _md(na) == _md(bron)                      # het scherm is identiek
    assert _md_naar_bron(_body_html(na, _PAGS)) == na   # en daarna stabiel


def test_alleen_een_punt_maakt_een_genummerde_lijst():
    """`1) een` is elders geldige markdown, maar met twee schrijfwijzen kan de weg terug er maar
    één teruggeven — en dan verandert de bron bij elke bewerking. Eén vorm, geen normalisatie."""
    assert _md("1) een") == "1) een"


# ── 5. De echte pagina's ────────────────────────────────────────────────────────────────────
def test_de_echte_paginas_overleven_het_nieuwe_vocabulaire():
    """Dezelfde acceptatie-eis als brok 1, nu met vijf blokken erbij. Draait waar de data staat."""
    from tests.test_wiki_blokmodel import _echte_paginas
    notes = _echte_paginas()
    if not notes:
        pytest.skip("geen attachments.json — deze toets draait waar de echte pagina's staan")
    pags = [_Pagina(a["id"], a.get("title") or "") for a in notes]
    for a in notes:
        html = _body_html(a.get("body") or "", pags, blokken=True)
        assert _body_html(_md_naar_bron(html), pags, blokken=True) == html, \
            f"weergave verschoof op {a['id']}"


# ── 6. Twee blokken die je moet KUNNEN ZIEN ─────────────────────────────────────────────────
#
# GEMETEN IN DE BROWSER, niet aangenomen. Een `<blockquote>` krijgt van de browser alleen 40px
# inspringing: geen lijn, geen andere kleur, geen cursief. Op het scherm was het een alinea die
# toevallig wat naar rechts stond — en een citaat dat er niet als citaat uitziet, is geen citaat.
# Een `<hr>` kwam binnen als `border-style: inset` in rgb(128,128,128): de 3D-streep van de
# browser, niet de haarlijn van dit huis.
import os as _os
import re as _re

_CSS = open(_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                          "nooch_village", "static", "nooch.css"), encoding="utf-8").read()
_NU = open(_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                         "nooch_village", "static", "nooch-ui.css"), encoding="utf-8").read()


def _regel(css: str, selector: str) -> str:
    kaal = _re.sub(r"/\*.*?\*/", " ", css, flags=_re.S)
    for sel, body in _re.findall(r"([^{}]+)\{([^{}]*)\}", kaal):
        if selector in [" ".join(d.split()) for d in sel.split(",")]:
            return body
    return ""


def test_een_citaat_draagt_een_lijn():
    body = _regel(_CSS, "blockquote")
    assert "border-left" in body, "een citaat zonder lijn leest als een gewone alinea"
    assert "var(--border)" in body
    assert "var(--nu-border-subtle)" in _regel(_NU, ".nu blockquote")


def test_een_scheiding_is_de_haarlijn_van_het_huis():
    body = _regel(_CSS, "hr")
    assert "border:none" in body.replace(" ", ""), "de 3D-streep van de browser staat nog aan"
    assert "var(--border)" in body
    assert "var(--nu-border-subtle)" in _regel(_NU, ".nu hr")


# ── 7. Twee gaten die de mutatiecontrole aanwees ────────────────────────────────────────────
#
# Beide mutaties bleven eerst GROEN, en dat is precies waarvoor die controle er is: alles
# hierboven toetste één genummerde lijst per pagina en niemand toetste dat de taak buiten de
# wiki blijft.
def test_een_tweede_genummerde_lijst_begint_weer_bij_een():
    """De teller hoort bij de LIJST, niet bij de pagina. Deed hij dat niet, dan werd de tweede
    lijst bij het opslaan "3. 4." — en dan verspringt de nummering elke keer dat je de pagina
    aanraakt, zonder dat iemand iets typte."""
    bron = "1. een\n2. twee\n\ntussenzin\n\n1. opnieuw\n2. nog een"
    assert _md_naar_bron(_body_html(bron, _PAGS)) == bron
    assert _md_naar_bron(_body_html(bron, _PAGS, blokken=True)) == bron


def test_een_bolletjeslijst_ertussen_reset_de_teller_ook():
    bron = "1. een\n- bolletje\n1. weer een"
    assert _md_naar_bron(_body_html(bron, _PAGS)) == bron


def test_de_taak_lekt_niet_naar_de_gedeelde_renderer():
    """`_md` draait onder elke reactie, elke wall-comment en elk kanaalbericht. Een `<input>` dat
    daar opduikt is een dode checkbox in een chatbericht — precies wat het besluit uitsloot."""
    for tekst in ("- [ ] iets doen", "- [x] al gedaan", "gewone tekst met [ ] erin"):
        assert "<input" not in _md(tekst), tekst
        assert "checkbox" not in _md(tekst), tekst
