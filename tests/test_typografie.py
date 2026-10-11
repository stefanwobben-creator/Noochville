"""Typografie (A1, 11 oktober 2026): geen tekst onder 12px — als RATCHET, niet als retrofit.

De lijst hieronder is de bekende schuld op 11 oktober: elke CSS-regel (in `web_base._CSS` en
`static/nooch.css`) met een `font-size` onder 12px. Twee regels:

1. EEN NIEUWE REGEL ONDER 12PX FAALT. Wie een kleine tekst nodig heeft, gebruikt `var(--type-12)`.
2. DE LIJST KAN ALLEEN KRIMPEN. Brengt een fase een regel naar 12px of meer, dan faalt de toets tot
   die regel ook hier weg is — zo blijft de lijst de echte stand en niet een historisch plafond.

Gemeten in px bij een root van 16px (rem en em × 16); `var(...)` en `clamp(...)` tellen niet: die
wijzen naar de schaal.
"""
from __future__ import annotations

import re

from nooch_village import web_base

STATIC = __import__("pathlib").Path(__file__).resolve().parents[1] / "nooch_village" / "static" / "nooch.css"

#: (bron, selector) — de regels die NU nog onder 12px staan. Alleen weghalen, nooit toevoegen.
SCHULD = {
    ('nooch.css', '.att-lbl'),
    ('nooch.css', '.av'),
    ('nooch.css', '.btn.sm'),
    ('nooch.css', '.bu-proj'),
    ('nooch.css', '.bullet-bm'),
    ('nooch.css', '.c2-kbd'),
    ('nooch.css', '.c2-navct'),
    ('nooch.css', '.c2-pgroep'),
    ('nooch.css', '.c2-psub'),
    ('nooch.css', '.c2-sec h3,.wiki-inline h3'),
    ('nooch.css', '.c2-subnav a.c2-overleg'),
    ('nooch.css', '.catcard .src'),
    ('nooch.css', '.catgroup>h3'),
    ('nooch.css', '.chip'),
    ('nooch.css', '.chip.coral-solid'),
    ('nooch.css', '.ck-box'),
    ('nooch.css', '.ck-gate .muted'),
    ('nooch.css', '.ck-gate-wat'),
    ('nooch.css', '.ck-human'),
    ('nooch.css', '.ck-klaar-kop .muted'),
    ('nooch.css', '.ck-leeg'),
    ('nooch.css', '.ck-meta'),
    ('nooch.css', '.ck-noskill'),
    ('nooch.css', '.ck-payload'),
    ('nooch.css', '.ck-prog .muted'),
    ('nooch.css', '.ck-skill'),
    ('nooch.css', '.ck-skip'),
    ('nooch.css', '.ck-warn'),
    ('nooch.css', '.cl-spark'),
    ('nooch.css', '.ctrl .car'),
    ('nooch.css', '.dk'),
    ('nooch.css', '.fkicker'),
    ('nooch.css', '.fstamp'),
    ('nooch.css', '.gr-pop'),
    ('nooch.css', '.gs-hit .gs-kind'),
    ('nooch.css', '.gs-kind'),
    ('nooch.css', '.kb-who'),
    ('nooch.css', '.kc-hint'),
    ('nooch.css', '.kpi-prov'),
    ('nooch.css', '.md-help'),
    ('nooch.css', '.menu-h'),
    ('nooch.css', '.msg-add'),
    ('nooch.css', '.msg-groep'),
    ('nooch.css', '.msg-telling'),
    ('nooch.css', '.msg-tijd'),
    ('nooch.css', '.msg-uit'),
    ('nooch.css', '.noo-ctx'),
    ('nooch.css', '.noo-sub'),
    ('nooch.css', '.pbadge'),
    ('nooch.css', '.pcard-hint'),
    ('nooch.css', '.pchip-k'),
    ('nooch.css', '.pcol-h'),
    ('nooch.css', '.pill'),
    ('nooch.css', '.pmeta'),
    ('nooch.css', '.psec-h'),
    ('nooch.css', '.pstatus'),
    ('nooch.css', '.rail-kop'),
    ('nooch.css', '.rov-by'),
    ('nooch.css', '.rov-kind'),
    ('nooch.css', '.rov-more'),
    ('nooch.css', '.rovm-kind'),
    ('nooch.css', '.sec-kop'),
    ('nooch.css', '.seg>form button,.seg>a'),
    ('nooch.css', '.selseg'),
    ('nooch.css', '.smeta dt'),
    ('nooch.css', '.statustrigger .caret'),
    ('nooch.css', '.tile-goal'),
    ('nooch.css', '.tile-prov'),
    ('nooch.css', '.tile-t'),
    ('nooch.css', '.tree details.tree-c>summary::before'),
    ('nooch.css', '.tree h3'),
    ('nooch.css', '.uk-badge'),
    ('nooch.css', '.uk-staat'),
    ('nooch.css', '.wall-head h2'),
    ('nooch.css', '.wo-leave'),
    ('nooch.css', '.wo-num'),
    ('nooch.css', '.wz-badge'),
    ('nooch.css', '.wz-clab'),
    ('nooch.css', '.wz-k'),
    ('nooch.css', ':root .msg-nieuw'),
    ('nooch.css', ':root .nu-eyebrow, :root .c2-sec h3, :root .wiki-inline h3, :root .tree h3, :root .pcol-h, :root .fkicker, :root .rovm-kind, :root .sec-kop, :root .menu-h, :root .dk, :root .att-lbl, :root .cl-group h4, :root .psec-h, :root .pchip-k, :root .rail-kop, :root .wz-k, :root .wz-clab, :root .gs-group, :root .gs-kind'),
    ('nooch.css', ':root .pill, :root .chip, :root .badge'),
    ('web_base._CSS', '.badge'),
    ('web_base._CSS', 'th'),
}


def _onder_12() -> set[tuple[str, str]]:
    uit = set()
    for naam, css in (("web_base._CSS", web_base._CSS), ("nooch.css", STATIC.read_text())):
        schoon = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        for m in re.finditer(r"([^{}@]+)\{([^{}]*)\}", schoon):
            for f in re.finditer(r"font-size\s*:\s*([^;]+)", m.group(2)):
                w = re.match(r"^([\d.]+)(px|rem|em)$", f.group(1).replace("!important", "").strip())
                if w and float(w.group(1)) * (1 if w.group(2) == "px" else 16) < 12:
                    uit.add((naam, " ".join(m.group(1).split())))
    return uit


def test_geen_nieuwe_tekst_onder_12px():
    nieuw = _onder_12() - SCHULD
    assert not nieuw, f"nieuwe CSS-regel onder 12px (gebruik var(--type-12)): {sorted(nieuw)}"


def test_de_schuldlijst_krimpt_mee():
    weg = SCHULD - _onder_12()
    assert not weg, f"deze regels staan niet meer onder 12px — haal ze uit SCHULD: {sorted(weg)}"


def test_de_schaal_bestaat():
    css = STATIC.read_text()
    for t, w in (("--type-12", ".75rem"), ("--type-13", ".8125rem"), ("--type-15", ".9375rem"),
                 ("--type-18", "1.125rem"), ("--type-24", "1.5rem"), ("--type-32", "2rem")):
        assert f"{t}: {w};" in css, t
