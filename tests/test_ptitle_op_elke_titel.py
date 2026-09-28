"""Eén stijl voor een paginatitel (28 september 2026).

WAT ER MISGING, en het is niet te zien zonder twee schermen naast elkaar te leggen. Er zijn twee
stylesheets: het inline blok in `web_base._CSS` (tokens en basis-atomen) en `static/nooch.css` (de
componentlaag). Het eerste zei `h1{font-weight:800}`, het tweede `.ptitle{font-weight:600}` — en
een klasse wint van een element-selector. Gevolg: een paginatitel woog 600 op de zeven views die de
klasse droegen en 800 op de zevenentwintig andere. Geen van beide was fout; ze waren het alleen
oneens.

DE KEUZE (route a van twee, besluit Stefan). `.ptitle` gaat op ELKE paginatitel en het gewicht
verdwijnt uit het h1-atoom. De andere route — het hele inline blok opheffen en de rest naar
nooch.css verhuizen — is bewust niet genomen: CLAUDE.md legt vast dat tokens en basis-atomen JUIST
inline blijven (`:root` staat erin, en `web_base` wordt ook zonder designsysteem-link gerenderd).
Familie, grootte en marge blijven dus staan; alleen het gewicht verhuist naar de klasse die er al
een uitspraak over deed.

DEZE RATCHET houdt het zo. Een nieuwe view met een kale `<h1>` valt om, met de reden erbij.
"""
from __future__ import annotations

import pathlib
import re

WORTEL = pathlib.Path(__file__).resolve().parents[1]
VIEWS = sorted((WORTEL / "nooch_village" / "views").glob("*.py"))
CSS = (WORTEL / "nooch_village" / "static" / "nooch.css").read_text(encoding="utf-8")

#: BEWUST ZONDER `.ptitle`, met de reden erbij. Leeg, en dat hoort zo: elke `<h1>` in een view is
#: de titel van een pagina. De login- en wachtwoordpagina's in `auth.py` staan hier niet omdat ze
#: buiten de schil vallen — ze bouwen hun eigen HTML met hun eigen `<style>` en laden nooch.css
#: niet, dus daar zou de klasse niets doen.
BUITEN: dict[str, str] = {}


def _koppen() -> dict[str, list[str]]:
    """Elke `<h1…>` per bestand, zoals hij in de bron staat."""
    uit = {}
    for p in VIEWS:
        koppen = re.findall(r"<h1[^>]*>", p.read_text(encoding="utf-8"))
        if koppen:
            uit[p.name] = koppen
    return uit


# ══ De ratchet ═══════════════════════════════════════════════════════════════
def test_elke_paginatitel_draagt_de_klasse():
    """DE HELE POINTE. Zonder `.ptitle` valt een titel terug op het h1-atoom, en dat doet sinds
    deze stap geen uitspraak meer over gewicht — dan bepaalt de browser het."""
    kaal = {naam: [k for k in koppen if "ptitle" not in k]
            for naam, koppen in _koppen().items()}
    kaal = {n: k for n, k in kaal.items() if k and n not in BUITEN}
    assert not kaal, (
        f"paginatitel zonder class='ptitle': {kaal}. Zet de klasse erop, of zet het bestand in "
        f"`BUITEN` in deze toets met een reden.")


def test_het_gewicht_staat_op_precies_een_plek():
    """Twee stylesheets die hetzelfde element iets anders vertellen, is waar dit mee begon."""
    from nooch_village.web_base import _CSS as INLINE
    regel = re.search(r"(?:^|})h1\{([^}]*)\}", INLINE, re.M)
    assert regel, "het h1-atoom is verdwenen"
    assert "font-weight" not in regel.group(1), "het inline blok doet weer een uitspraak"
    assert ".ptitle{font-weight:600}" in CSS


def test_de_klasse_bestaat_nog_in_de_componentlaag():
    """Een klasse die nergens meer gedefinieerd is, laat elke titel op de browser-default vallen —
    en dat zou stil gebeuren, want er verdwijnt geen HTML."""
    assert re.search(r"(?:^|})\.ptitle\{", CSS, re.M)


def test_de_uitzonderingen_bestaan_nog():
    bestanden = set(_koppen())
    assert not (set(BUITEN) - bestanden), f"staat in BUITEN maar heeft geen h1: {set(BUITEN) - bestanden}"


# ══ Op het scherm, niet alleen in de bron ════════════════════════════════════
def test_de_echte_pagina_levert_hem_ook_zo_uit(tmp_path):
    """DE BRON IS DE SPELLING, HET SCHERM IS DE WAARHEID. Een view die zijn kop via een helper
    samenstelt zou de tekstscan kunnen passeren en toch een kale `<h1>` uitleveren."""
    from nooch_village import cockpit2
    from nooch_village.views.acties import render_acties
    from nooch_village.views.messages import render_messages
    from nooch_village.views.site_audit import render_site_audit
    from nooch_village.views.tools import render_tools
    from nooch_village.views.wiki import render_wiki_index

    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    mens = st.people.add("Aap", "aap@test.nl")
    schermen = {
        "/acties": render_acties(st, mens.id, "TOK"),
        "/messages": render_messages(st, ik=mens.id, csrf_token="TOK"),
        "/tools": render_tools(st, csrf_token="TOK", username="aap@test.nl"),
        "/wiki": render_wiki_index(st, csrf_token="TOK"),
        "/site-audit": render_site_audit(st, csrf_token="TOK", username="aap@test.nl"),
    }
    kaal = {pad: [k for k in re.findall(r"<h1[^>]*>", html) if "ptitle" not in k]
            for pad, html in schermen.items()}
    kaal = {p: k for p, k in kaal.items() if k}
    assert not kaal, f"uitgeleverde pagina met een kale titel: {kaal}"
    # En er staat er ook echt één op elk scherm — anders toetst het bovenstaande niets.
    for pad, html in schermen.items():
        assert "<h1" in html, f"{pad} heeft helemaal geen titel"


def test_de_titel_weegt_overal_hetzelfde(tmp_path):
    """Waar het om begon: twee schermen naast elkaar hoorden dezelfde titel te tonen. De klasse is
    nu de enige uitspraak, dus dat is geen kwestie meer van welk bestand je toevallig opent."""
    koppen = {k for lijst in _koppen().values() for k in lijst}
    assert koppen == {"<h1 class='ptitle'>"}, sorted(koppen)
