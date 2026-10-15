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
    ('nooch.css', '.av'),
    ('nooch.css', '.bu-proj'),
    ('nooch.css', '.bullet-bm'),
    ('nooch.css', '.c2-psub'),
    ('nooch.css', '.catcard .src'),
    ('nooch.css', '.ck-box'),
    ('nooch.css', '.ck-human'),
    ('nooch.css', '.ck-klaar-kop .muted'),
    ('nooch.css', '.ck-meta'),
    ('nooch.css', '.ck-prog .muted'),
    ('nooch.css', '.ck-skip'),
    ('nooch.css', '.cl-spark'),
    ('nooch.css', '.ctrl .car'),
    ('nooch.css', '.fstamp'),
    ('nooch.css', '.gr-pop'),
    ('nooch.css', '.kb-who'),
    ('nooch.css', '.kc-hint'),
    ('nooch.css', '.kpi-prov'),
    ('nooch.css', '.md-help'),
    ('nooch.css', '.msg-telling'),
    ('nooch.css', '.msg-tijd'),
    ('nooch.css', '.msg-uit'),
    ('nooch.css', '.noo-ctx'),
    ('nooch.css', '.noo-sub'),
    ('nooch.css', '.pcard-hint'),
    ('nooch.css', '.pmeta'),
    ('nooch.css', '.rov-by'),
    ('nooch.css', '.rov-kind'),
    ('nooch.css', '.rov-more'),
    ('nooch.css', '.statustrigger .caret'),
    ('nooch.css', '.tile-goal'),
    ('nooch.css', '.tree details.tree-c>summary::before'),
    ('nooch.css', '.wo-leave'),
    ('nooch.css', '.wo-num'),
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
