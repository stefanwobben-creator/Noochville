"""De weg terug: opgemaakte HTML → de markdown-bron (`_md_naar_bron`, 21 september 2026).

WAAROM DEZE FUNCTIE BESTAAT. De wiki-editor laat je in de tekst zelf typen. Wat de browser
terugstuurt is dus HTML, terwijl de opslag markdown is en blijft — er wordt nooit HTML bewaard.
Die omzetting staat op de SERVER, naast `_md`, en niet in JS: dan zou er een tweede opmaak-kenner
bestaan naast `_md`, en die twee lopen uiteen zodra er één regel bijkomt.

WAT DEZE TESTS BEWAKEN, in volgorde van gewicht:

  1. de heen-en-terug-eigenschap op de zes constructies die `_md` kent;
  2. fail-closed: wat niet in de whitelist staat wordt TEKST, nooit HTML die in de opslag belandt;
  3. de rommel die een browser zelf maakt (`<div>`, `<p>`, `<span style>`) verandert de bron niet;
  4. de eigenschap die er bij het opslaan werkelijk toe doet — de WEERGAVE verandert niet:

         _md(_md_naar_bron(_md(bron))) == _md(bron)

`_md` is niet omkeerbaar op eindwitruimte (hij strippt de laatste `<br>` en de inspringing van een
lijstregel), dus punt 4 is de harde belofte en punt 1 geldt op genormaliseerde bron. Op de 105
echte pagina's van productie (92.162 tekens) klopten ze op 21 september 2026 allebei, 105 van de
105 — óók de letterlijke variant. Die meting staat in de PR; deze tests draaien zonder die data.
"""
from __future__ import annotations

import json
import os
import random

import pytest

from nooch_village.cockpit2_util import _md, _md_naar_bron
from nooch_village.views.wiki import _body_html


class _Pagina:
    """Het minimum dat `wiki.resolve` van een pagina wil weten."""
    def __init__(self, pid: str, titel: str):
        self.id, self.title = pid, titel


_PAGS = [_Pagina("NOTE-COMPLI-021", "Claims beleid")]


def _norm(bron: str) -> str:
    """Wat `_md` sowieso met de bron doet voor hij hem rendert. Vergelijken met de RUWE bron zou
    deze functie afrekenen op verlies dat `_md` veroorzaakt."""
    return bron.replace("\r\n", "\n").replace("\r", "\n").strip("\n")


# ── 1. De zes constructies ───────────────────────────────────────────────────
@pytest.mark.parametrize("bron", [
    "gewone regel",
    "een **vette** en een *schuine* en een ~~doorgehaalde~~",
    "## Een kop\nmet tekst eronder",
    "- een\n- twee\n- drie",
    "boven de lijst\n- een\n- twee\nonder de lijst",
    "regel een\n\nregel drie",                      # een lege regel is een lege regel
    "link naar [nooch](https://nooch.earth) toe",
    "## Kop\n- punt met **vet**\n- punt twee\n\nslot",
    "verwijzing naar [[NOTE-COMPLI-021]] hier",     # bestaat → pill
    "verwijzing naar [[Bestaat Niet]] hier",        # bestaat niet → chip, blijft verlanglijst
    "- punt met [[NOTE-COMPLI-021]] erin\n- punt twee",
])
def test_heen_en_terug_levert_dezelfde_bron(bron):
    assert _md_naar_bron(_body_html(bron, _PAGS)) == _norm(bron)


def test_de_verwijzing_komt_terug_als_wat_er_stond_niet_als_de_titel():
    """`[[NOTE-COMPLI-021]]` rendert als de TITEL van die pagina ("Claims beleid"). Zonder het
    `data-ref`-attribuut zou de weg terug die titel oppakken, en dan wijst de verwijzing na één
    keer opslaan naar iets anders — of nergens meer heen."""
    html = _body_html("zie [[NOTE-COMPLI-021]]", _PAGS)
    assert "Claims beleid" in html and "data-ref='NOTE-COMPLI-021'" in html
    assert _md_naar_bron(html) == "zie [[NOTE-COMPLI-021]]"


# ── 2. Fail-closed ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("html,verwacht", [
    ("<script>alert(1)</script>", "alert(1)"),
    ("<iframe src='http://kwaad'></iframe>", ""),
    ("<img src=x onerror=alert(1)>", ""),
    ("<span style='color:red'>rood</span>", "rood"),
    ("<font face='Arial'>geplakt uit Word</font>", "geplakt uit Word"),
    ("<table><tr><td>cel</td></tr></table>", "cel"),
    ("<h1>een kop die _md niet kent</h1>", "een kop die _md niet kent"),
])
def test_wat_niet_in_de_whitelist_staat_wordt_tekst(html, verwacht):
    """De browser stuurt terug wat de gebruiker plakt, en dat is soms een half Word-document. Een
    onbekende tag wordt zijn eigen tekst — nooit ruwe HTML die straks in de opslag staat."""
    uit = _md_naar_bron(html)
    assert uit.strip() == verwacht
    assert "<" not in uit and ">" not in uit


def test_er_komt_nooit_werkzame_markup_uit_ook_niet_bij_kapotte_invoer():
    """Een contenteditable levert geen gegarandeerd nette boom: niet-gesloten tags, verkeerde
    nesting, losse sluittags.

    DE TOETS IS DE WEERGAVE, niet de bron. Een `<` in de BRON is gewoon een teken dat iemand mag
    typen — `_md` escapet hem bij het renderen. Verbieden in de bron zou de verkeerde belofte
    zijn (en `<<>>` als bug aanmerken terwijl de gebruiker dat letterlijk intikte). Wat niet mag,
    is dat er na de rondgang een WERKENDE tag op het scherm staat."""
    for rommel in ("<strong>open gelaten", "<em><strong>fout genest</em></strong>",
                   "</div></p>los", "<b>a<i>b</b>c</i>", "<<>>", "<div",
                   "<script>alert(1)</script>", "<img src=x onerror=alert(1)>",
                   "<a href='javascript:alert(1)'>klik</a>"):
        bron = _md_naar_bron(rommel)
        for gevaar in ("<script", "<img", "<iframe", "onerror", "javascript:"):
            assert gevaar not in _md(bron).lower(), (
                f"{gevaar} overleeft de rondgang van {rommel!r}")
            # En hij hoort ook niet in de OPSLAG te belanden: `_md` weigert een niet-http(s)-link
            # bij het renderen, maar dat is de tweede verdedigingslinie, niet de eerste.
            assert gevaar not in bron.lower(), f"{gevaar} wordt opgeslagen uit {rommel!r}"


# ── 3. Wat de browser er zelf bij verzint ────────────────────────────────────
@pytest.mark.parametrize("html,bron", [
    ("<div>een</div><div>twee</div>", "een\ntwee"),          # Chrome bij Enter
    ("<p>een</p><p>twee</p>", "een\ntwee"),                  # Firefox/Safari bij Enter
    ("een<br>twee", "een\ntwee"),
    ("<div>een<br></div>", "een"),                           # de trailing br van een lege regel
    ("<b>vet</b> en <strong>ook vet</strong>", "**vet** en **ook vet**"),
    ("<i>schuin</i> en <em>ook schuin</em>", "*schuin* en *ook schuin*"),
    # DRIE VORMEN VOOR ÉÉN KNOP. Chrome's execCommand("strikeThrough") levert `<strike>`,
    # Safari `<s>`, en `_md` zelf rendert `~~` als `<del>`. Dat `<strike>` hier ontbrak kostte een
    # live bug: doorhalen werkte op het scherm en was na opslaan weg (21 september 2026).
    ("<s>door</s> en <del>ook door</del>", "~~door~~ en ~~ook door~~"),
    ("<strike>door</strike> en <s>ook door</s>", "~~door~~ en ~~ook door~~"),
])
def test_de_rommel_van_de_browser_geeft_dezelfde_bron(html, bron):
    """`document.execCommand('bold')` levert in de ene browser `<b>` en in de andere `<strong>`.
    Beide horen `**` te worden; anders hangt de opgeslagen bron af van wie zat te typen."""
    assert _md_naar_bron(html) == bron


def test_een_blokgrens_telt_een_keer_niet_twee():
    """`</p><p>` zijn twee signalen voor één overgang. Wie ze allebei als regeleinde telt, laat de
    tekst bij elke bewerking een regel verder uit elkaar staan — pas na vier keer opslaan merkbaar,
    en dan niet meer terug te draaien."""
    uit = _md_naar_bron("<p>een</p><p>twee</p><p>drie</p>")
    assert uit == "een\ntwee\ndrie"
    twee_keer = _md_naar_bron(_md(_md_naar_bron("<p>een</p><p>twee</p>")))
    assert twee_keer == "een\ntwee"


# ── 4. De belofte die er bij het opslaan toe doet ────────────────────────────
def _corpus(n: int = 300) -> list[str]:
    """Een vaste, gegenereerde stapel bronteksten uit de zes constructies.

    Vast zaad, want een test die per run iets anders toetst, meldt een fout op een dag waarop je
    niets veranderde — en is dan meteen de test die wordt uitgezet."""
    r = random.Random(20260921)
    stukken = ["platte tekst", "**vet**", "*schuin*", "~~door~~",
               "[link](https://nooch.earth)", "[[NOTE-COMPLI-021]]", "[[Bestaat Niet]]", ""]
    uit = []
    for _ in range(n):
        regels = []
        for _ in range(r.randint(1, 6)):
            inhoud = " ".join(r.choice(stukken) for _ in range(r.randint(1, 4))).strip()
            soort = r.choice(("tekst", "tekst", "kop", "punt"))
            regels.append({"tekst": inhoud, "kop": f"## {inhoud}", "punt": f"- {inhoud}"}[soort]
                          if inhoud else "")
        uit.append("\n".join(regels))
    return uit


def test_door_de_editor_heen_verandert_de_weergave_niet():
    """DE HARDE BELOFTE. Opslaan zonder iets te typen mag de pagina niet veranderen. Dat is een
    eigenschap van de WEERGAVE, niet van de bron: `_md` strippt zelf inspringing en eindwitruimte,
    dus de bron mag onderweg genormaliseerd worden — het scherm niet."""
    for bron in _corpus():
        html = _body_html(bron, _PAGS)
        assert _body_html(_md_naar_bron(html), _PAGS) == html, f"weergave verschoof bij {bron!r}"


def test_twee_keer_opslaan_verandert_niets_meer_dan_een_keer():
    """Een omzetting die per ronde één spatie toevoegt, valt bij één test niet op en sloopt een
    pagina die tien keer bewerkt wordt. Idempotent op de bron, na de eerste normalisatie."""
    for bron in _corpus(120):
        een = _md_naar_bron(_body_html(bron, _PAGS))
        twee = _md_naar_bron(_body_html(een, _PAGS))
        assert een == twee, f"niet idempotent bij {bron!r}: {een!r} → {twee!r}"


# ── 5. Dezelfde belofte op de ECHTE pagina's ─────────────────────────────────
def _echte_paginas() -> list[dict]:
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


def test_de_echte_paginas_overleven_de_rondgang():
    """Draait waar de data staat (lokaal, prod) en slaat over waar hij niet staat (CI). Dat is
    bewust GEEN vervanging van de gegenereerde corpus hierboven — die draait overal, altijd.
    Dit is de bevestiging op echte tekst, met echte koppen, lijsten en halve zinnen."""
    notes = _echte_paginas()
    if not notes:
        pytest.skip("geen data/attachments.json — deze toets draait waar de echte pagina's staan")
    pags = [_Pagina(a["id"], a.get("title") or "") for a in notes]
    for a in notes:
        html = _body_html(a.get("body") or "", pags)
        assert _body_html(_md_naar_bron(html), pags) == html, f"weergave verschoof op {a['id']}"
