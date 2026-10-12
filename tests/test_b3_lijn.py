"""B3 fase a+b (12 oktober 2026): tokens, en de buitenkant van een container is 1px zwart.

  a. Tokens: één ruimteschaal (`--s1`–`--s6` = 4 · 8 · 12 · 16 · 24 · 32 px) en `--hair` voor de lijn
     binnen een container.
  b. Containers (zijbalk, tabel, invoerveld, bordkolom, `.box`, popovers) krijgen 1px zwart: de token
     `--nu-border` droeg 2px en draagt nu 1px.

DE 2PX-GUARD. Een rand van 2px is voor het ene element dat eruit moet springen. Elke 2px-rand in de
CSS staat hieronder met een reden; een NIEUWE faalt deze toets. De lijst mag alleen korter worden.
"""
from __future__ import annotations

import pathlib
import re

CSS = (pathlib.Path(__file__).resolve().parents[1] / "nooch_village" / "static" / "nooch.css").read_text(
    encoding="utf-8")

#: selector → waarom hij 2px mag dragen.
TWEE_PX = {
    ":root .c2-subnav a.c2-overleg--live": "de lopende meeting: het ene element dat eruit springt",
    # focus is een toestand, geen rand: wie typt moet zien wáár (toegankelijkheid)
    ":root input[type=text]:focus": "focus-toestand van een invoerveld",
    # de oude laag (buiten de nu-scope), decoratief en geen kader
    ".c2-tab": "onderstreping van het actieve tabblad (transparant tot actief)",
    ".subtab": "onderstreping van het actieve subtabblad",
    ".stack-av .av": "witte ring tussen gestapelde avatars",
    "blockquote": "citaatstreep",
    ".noo-rail-top": "rand in de Noochie-rail (eigen donkere vlak)",
    ".wiki-inline>div": "inspring-streep van een ingevoegde wikipagina",
    ":root input.title-edit": "onderlijn van de bewerkbare titel (transparant tot focus)",
}


def _blokken(css: str):
    """(selector, declaraties) voor elke regel, ook binnen @media; commentaar weg."""
    kaal = re.sub(r"/\*.*?\*/", " ", css, flags=re.S)
    kaal = re.sub(r"@media[^{]*\{", " ", kaal)              # de @media-kop weg, de regels blijven
    for sel, decl in re.findall(r"([^{}]+)\{([^{}]*)\}", kaal):
        yield " ".join(sel.split()), decl


def _tweepx() -> set[str]:
    """De eerste selector van elke regel met een rand van 2px (geen radius, geen outline)."""
    uit = set()
    for sel, decl in _blokken(CSS):
        for d in re.findall(r"(border(?:-[a-z]+)*\s*:[^;]*)", decl):
            if "radius" in d.split(":")[0]:
                continue
            if re.search(r"\b2px\b", d):
                uit.add(sel.split(",")[0].strip())
    return uit


def _regel(selector: str) -> str:
    return " ".join(d for s, d in _blokken(CSS) if selector in [x.strip() for x in s.split(",")])


def test_de_tokens_bestaan():
    for naam, waarde in (("--s1", "4px"), ("--s2", "8px"), ("--s3", "12px"), ("--s4", "16px"),
                         ("--s5", "24px"), ("--s6", "32px"), ("--hair", "var(--nu-border-subtle)")):
        assert re.search(rf"{naam}:\s*{re.escape(waarde)}", CSS), naam


def test_de_container_rand_is_1px_zwart():
    assert re.search(r"--nu-border:\s*1px solid var\(--nu-text\)", CSS)
    assert "border-right: var(--nu-border)" in _regel(":root .c2-side")
    assert "border: var(--nu-border)" in _regel(":root table")
    assert "border: 1px solid var(--nu-text)" in _regel(":root .pcol")
    assert "border: 1px solid var(--nu-text)" in _regel(":root input[type=text]")      # invoerveld


def test_geen_nieuwe_rand_van_2px():
    nieuw = sorted(_tweepx() - set(TWEE_PX))
    assert nieuw == [], "een rand van 2px buiten de toegestane elementen: " + ", ".join(nieuw)


def test_de_2px_lijst_veroudert_niet():
    """Een uitzondering die geen 2px meer heeft, hoort eraf: de lijst mag alleen korter worden."""
    oud = sorted(set(TWEE_PX) - _tweepx())
    assert oud == [], "haal deze van TWEE_PX: " + ", ".join(oud)
