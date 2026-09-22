"""Brok 1 van de Notion-stijl wiki: het BLOKMODEL. Nog geen greep, geen slepen, geen /-menu.

WAT DIT IS. `_md` levert een platte stroom: `<h4>kop</h4><ul><li>a</li></ul>tekst<br>meer`. Een
kop is te herkennen, maar "de derde alinea" bestaat niet als ding — er is alleen tekst met
`<br>`'s ertussen. Alles wat brok 3 wil (een greep per blok, slepen om te herordenen, een
`/`-menu dat er een invoegt) heeft dat ding nodig. Dit is dat ding: elk blok op het hoogste
niveau krijgt zijn eigen `<div class='wb' data-blok='…'>`.

DE ACCEPTATIE-EIS VAN STEFAN, en hij staat vóór alles hieronder: de weergave van de 105 echte
pagina's mag niet verschuiven. `tests/test_md_bron.py::test_de_echte_paginas_overleven_de_rondgang`
draait daarop; dit bestand voegt dezelfde belofte toe in de blokstand. Gemeten op een kopie van
`data/attachments.json` van productie (105 niet-gearchiveerde notes): groen vóór de wijziging,
groen erna.

DRIE DINGEN DIE FOUT KUNNEN GAAN, en daarom alle drie een test:

  1. `_md` is GEDEELD — reacties, de project-wall, Messages. Een blok-div die daar opduikt is
     een wijziging aan drie schermen die niemand vroeg. De stand is dus een parameter die
     standaard UIT staat, en een test vergelijkt de uit-stand byte voor byte met wat er stond;
  2. de weg terug telt blokgrenzen. `</li></ul></div>` zijn drie signalen voor één overgang;
     wie ze los telt, laat de tekst bij elke bewerking een regel verder uit elkaar staan — pas
     na vier keer opslaan merkbaar en dan niet meer terug te draaien (die val staat al in
     `test_een_blokgrens_telt_een_keer_niet_twee`, nu met een div erbij);
  3. een LEGE regel is in HTML iets anders dan een leeg blok. `a<br><br>b` toont een witregel;
     `<div></div>` is nul pixels hoog. Zonder de `<br>` erin verdwijnt elke witregel van elke
     pagina — een verschuiving die geen enkele bron-test ziet, want de bron klopt.
"""
from __future__ import annotations

import re

from nooch_village.cockpit2_util import _md, _md_naar_bron
from nooch_village.views.wiki import _body_html


class _Pagina:
    def __init__(self, pid: str, titel: str):
        self.id, self.title = pid, titel


_PAGS = [_Pagina("NOTE-COMPLI-021", "Claims beleid")]

_VOORBEELDEN = [
    "gewone regel",
    "een\ntwee\ndrie",
    "## Een kop\nmet tekst eronder",
    "- een\n- twee\n- drie",
    "boven de lijst\n- een\n- twee\nonder de lijst",
    "regel een\n\nregel drie",
    "## Kop\n- punt met **vet**\n- punt twee\n\nslot",
    "verwijzing naar [[NOTE-COMPLI-021]] hier",
    "- punt met [[NOTE-COMPLI-021]] erin\n- punt twee",
]


def _blokken(html: str) -> list[str]:
    """De `data-blok`-soorten op volgorde."""
    return re.findall(r"<div class='wb' data-blok='([a-z]+)'>", html)


# ── 1. De gedeelde renderer verandert niet ──────────────────────────────────────────────────
def test_zonder_de_vlag_is_er_niets_veranderd():
    """`_md` draait ook onder elke reactie, elke wall-comment en elk kanaalbericht. Byte voor
    byte dezelfde uitvoer, anders is dit een wijziging aan drie schermen die niemand vroeg."""
    for bron in _VOORBEELDEN:
        uit = _md(bron)
        assert "data-blok" not in uit and "class='wb'" not in uit, bron


def test_ook_de_wiki_weergave_staat_standaard_uit():
    """`_body_html` heeft twee aanroepers: de permalink en de Notes-tab. Allebei krijgen de
    blokstand pas als ze er expliciet om vragen."""
    assert "data-blok" not in _body_html("een\ntwee", _PAGS)


# ── 2. Met de vlag: elk blok is een ding ────────────────────────────────────────────────────
def test_elke_regel_wordt_een_eigen_blok():
    assert _blokken(_body_html("een\ntwee\ndrie", _PAGS, blokken=True)) == ["p", "p", "p"]


def test_een_kop_en_een_lijst_zijn_eigen_blokken():
    html = _body_html("## Kop\n- een\n- twee\nslot", _PAGS, blokken=True)
    assert _blokken(html) == ["h", "ul", "p"]


def test_een_lijst_is_een_blok_en_niet_een_blok_per_punt():
    """Een lijst sleep je als geheel; de punten erbinnen zijn geen losse blokken. Dat is
    dezelfde keuze die `_md` al maakte door ze in één `<ul>` te zetten."""
    html = _body_html("- een\n- twee\n- drie", _PAGS, blokken=True)
    assert _blokken(html) == ["ul"]
    assert html.count("<li>") == 3


def test_de_blokken_staan_op_het_hoogste_niveau_en_niet_in_elkaar():
    """Een blok IN een blok is geen blok meer: `closest('.wb')` van de greep zou dan het
    verkeerde ding pakken."""
    html = _body_html("## Kop\n- een\nslot", _PAGS, blokken=True)
    diepte = maximum = 0
    for stuk in re.findall(r"<div[^>]*>|</div>", html):
        diepte += 1 if stuk != "</div>" else -1
        maximum = max(maximum, diepte)
    assert maximum == 1, html


def test_een_lege_regel_houdt_zijn_hoogte():
    """`<div></div>` is nul pixels hoog. Zonder een `<br>` erin verdwijnt elke witregel van elke
    pagina — en geen enkele bron-test ziet dat, want de bron klopt gewoon."""
    html = _body_html("een\n\ntwee", _PAGS, blokken=True)
    assert _blokken(html) == ["p", "p", "p"]
    assert "<div class='wb' data-blok='p'><br></div>" in html


# ── 3. De weg terug ─────────────────────────────────────────────────────────────────────────
def _norm(bron: str) -> str:
    return bron.replace("\r\n", "\n").replace("\r", "\n").strip("\n")


def test_heen_en_terug_levert_dezelfde_bron_in_de_blokstand():
    for bron in _VOORBEELDEN:
        assert _md_naar_bron(_body_html(bron, _PAGS, blokken=True)) == _norm(bron), bron


def test_een_blokgrens_telt_ook_met_een_div_eromheen_een_keer():
    """`</li></ul></div>` zijn drie signalen voor één overgang."""
    uit = _md_naar_bron(_body_html("- een\n- twee\nslot", _PAGS, blokken=True))
    assert uit == "- een\n- twee\nslot"


def test_de_weergave_verschuift_niet_door_de_editor_heen():
    """DE HARDE BELOFTE, in de blokstand: opslaan zonder iets te typen verandert de pagina niet."""
    for bron in _VOORBEELDEN:
        html = _body_html(bron, _PAGS, blokken=True)
        assert _body_html(_md_naar_bron(html), _PAGS, blokken=True) == html, bron


def test_twee_keer_opslaan_verandert_niets_meer_dan_een_keer():
    for bron in _VOORBEELDEN:
        een = _md_naar_bron(_body_html(bron, _PAGS, blokken=True))
        twee = _md_naar_bron(_body_html(een, _PAGS, blokken=True))
        assert een == twee, f"niet idempotent bij {bron!r}: {een!r} → {twee!r}"


def test_de_blokstand_en_de_platte_stand_leveren_dezelfde_bron():
    """Allebei de standen zijn dezelfde tekst; alleen de omhulsels verschillen. Liepen ze uit
    elkaar, dan hing de opgeslagen bron af van of de editor aan stond."""
    for bron in _VOORBEELDEN:
        plat = _md_naar_bron(_body_html(bron, _PAGS))
        blok = _md_naar_bron(_body_html(bron, _PAGS, blokken=True))
        assert plat == blok, bron


# ── 4. De acceptatie-eis: de 105 echte pagina's ─────────────────────────────────────────────
def _echte_paginas() -> list[dict]:
    """Dezelfde bron als `test_md_bron._echte_paginas`: `data/attachments.json` waar hij staat.
    Op CI staat hij niet en slaat deze toets over — de gegenereerde voorbeelden hierboven
    draaien overal, altijd."""
    import json
    import os
    dd = os.environ.get("NOOCH_DATA_DIR") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    pad = os.path.join(dd, "attachments.json")
    if not os.path.exists(pad):
        return []
    with open(pad, encoding="utf-8") as fh:
        d = json.load(fh) or {}
    items = d.get("items", d)
    return [a for a in items.values()
            if isinstance(a, dict) and a.get("kind") == "note" and not a.get("archived")]


def test_de_echte_paginas_overleven_de_blokstand():
    """DE ACCEPTATIE-EIS (Stefan, 22 september 2026): de weergave van de echte pagina's mag niet
    verschuiven vóór er iets visueels verandert.

    Gemeten op een kopie van productie, 105 niet-gearchiveerde notes: 0 verschoven, 0 niet-
    idempotent, en 0 waar de blokstand een andere bron opleverde dan de platte stand."""
    import pytest
    notes = _echte_paginas()
    if not notes:
        pytest.skip("geen attachments.json — deze toets draait waar de echte pagina's staan")
    pags = [_Pagina(a["id"], a.get("title") or "") for a in notes]
    for a in notes:
        bron = a.get("body") or ""
        html = _body_html(bron, pags, blokken=True)
        assert _body_html(_md_naar_bron(html), pags, blokken=True) == html, \
            f"weergave verschoof op {a['id']}"
        een = _md_naar_bron(html)
        assert een == _md_naar_bron(_body_html(een, pags, blokken=True)), \
            f"niet idempotent op {a['id']}"
        assert een == _md_naar_bron(_body_html(bron, pags)), \
            f"blokstand geeft een andere bron dan de platte stand op {a['id']}"


# ── 5. Waar de stand aan staat ──────────────────────────────────────────────────────────────
#
# DEZE TWEE ONTBRAKEN EERST, en de mutatiecontrole wees het aan: `/pagina` terugzetten naar de
# platte stand liet alle 45 tests groen. Alles hierboven toetst de FUNCTIE; niets toetste dat het
# scherm hem ook gebruikt.
def _dorp_met_pagina(tmp_path):
    from nooch_village import cockpit2
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    a = st.att.add("mother_earth", "note", "Een pagina", "## Kop\n- punt\ntekst")
    return cockpit2._Stores(dd), a


def test_de_permalink_rendert_blokken(tmp_path):
    from nooch_village.views.wiki import render_pagina
    st, a = _dorp_met_pagina(tmp_path)
    html = render_pagina(st, a.id, csrf_token="t", username="guest")
    assert "data-blok='h'" in html and "data-blok='ul'" in html and "data-blok='p'" in html


def test_de_notes_tab_verandert_niet(tmp_path):
    """Hetzelfde artefact, read-only op `/node`. Daar wordt niet bewerkt, dus daar zijn geen
    blokken nodig — en een wijziging aan dat scherm zat niet in deze brok."""
    from nooch_village.views.overview import render_node
    st, a = _dorp_met_pagina(tmp_path)
    html = render_node(st, "mother_earth", "wiki", csrf_token="t", username="guest")
    assert "Kop" in html, "de pagina staat niet eens op dit scherm — dan meet deze test niets"
    assert "data-blok" not in html
