"""De gedeelde fragment-mechaniek: één implementatie, en een ratchet die de volgende plek vangt.

Dezelfde ziekte dook drie keer op drie schermen op — /vangst, de modal-verwerking en de
agenda-balk — en werd drie keer apart gerepareerd. Wat er misgaat als een stuk pagina zichzelf
vervangt is elke keer hetzelfde: je toetsaanslagen verdwijnen, de verse formulieren zijn niet
bedraad (en navigeren je weg), of ze zijn twéé keer bedraad (en posten dubbel).

Deze test bewaakt twee dingen:

1. de mechaniek bestaat één keer, in `static/nooch.js`, en wordt door elke volle pagina geladen;
2. een view die zélf een fragment inplakt is een nieuwe kopie van het probleem — het plafond per
   bestand mag dalen (door over te stappen op `NV.swap`), nooit stijgen, en een nieuw bestand
   begint op nul.

Zelfde principe als de inline-style-ratchet: bestaande schuld staat vast, nieuwe schuld faalt.
"""
from __future__ import annotations

import pathlib
import re

from nooch_village import cockpit2, web_base

ROOT = pathlib.Path(__file__).resolve().parents[1] / "nooch_village"
JS = ROOT / "static" / "nooch.js"

# Het idiom van een rauwe fragment-inplak: `…innerHTML = h` (of `w`) ná een fetch. Bestaande
# plekken met hun huidige aantal; MONOTOON DALEND. Ga je zo'n scherm toch aanraken, zet hem dan
# over op NV.swap en verlaag het plafond. Een bestand dat hier niet in staat mag er nul hebben.
PLAFOND = {
    "cockpit2_util.py": 1,
    "views/callbar.py": 1,          # LiveKit-tegels: eigen levenscyclus, geen server-fragment
    "views/claims.py": 1,
    "views/inbox.py": 2,
    "views/kennisbank.py": 1,
    "views/kennisbank_spel.py": 1,
    "views/noochie.py": 1,
    "views/projects.py": 1,         # de modal-controller zélf — dit IS de gastheer van fragmenten
}

_SWAP = re.compile(r"innerHTML\s*=\s*[hw]\b")


def _telling() -> dict[str, int]:
    uit: dict[str, int] = {}
    for f in sorted(ROOT.rglob("*.py")):
        n = len(_SWAP.findall(f.read_text(encoding="utf-8")))
        if n:
            uit[str(f.relative_to(ROOT))] = n
    return uit


def test_de_mechaniek_bestaat_een_keer():
    """De wachtrij, het cursor-herstel en het opnieuw bedraden staan in één bestand."""
    bron = JS.read_text(encoding="utf-8")
    assert "NV.swap" in bron and "NV.wire" in bron
    assert "wacht.push" in bron                      # de wachtrij
    assert "setSelectionRange" in bron               # het cursor-herstel
    assert "data-nv-wired" in bron or "nvWired" in bron   # idempotent bedraden
    # en geen enkele view schrijft er een tweede versie van
    kopieen = [str(f.relative_to(ROOT)) for f in ROOT.rglob("*.py")
               if "wacht.push" in f.read_text(encoding="utf-8")]
    assert kopieen == [], f"eigen wachtrij buiten static/nooch.js: {kopieen}"


def test_elke_volle_pagina_laadt_de_mechaniek():
    """Een fragment draagt geen script mee (innerHTML voert scripts niet uit) — de pagina waarin
    het geopend wordt moet hem al hebben."""
    html = web_base._page("t", "<p>x</p>")
    assert f'/static/nooch.js?v={web_base._JS_VERSION}' in html
    assert "nooch.js" in cockpit2._STATIC_TYPES      # anders 404 op de eigen pagina


def test_geen_nieuwe_rauwe_fragment_inplak():
    """Ratchet: bestaande plekken vast, nieuwe op nul, dalen mag."""
    nu = _telling()
    nieuw = {k: v for k, v in nu.items() if k not in PLAFOND}
    assert nieuw == {}, (
        f"nieuwe rauwe fragment-inplak in {sorted(nieuw)} — gebruik `NV.swap(doel, url)` uit "
        "static/nooch.js: die bedraadt opnieuw, zet je cursor terug en werkt de tellers bij")
    te_hoog = {k: (v, PLAFOND[k]) for k, v in nu.items() if v > PLAFOND[k]}
    assert te_hoog == {}, f"plafond overschreden (nu, max): {te_hoog}"
    gedaald = {k: (nu.get(k, 0), v) for k, v in PLAFOND.items() if nu.get(k, 0) < v}
    assert gedaald == {}, f"schuld opgeruimd — verlaag het plafond in PLAFOND: {gedaald}"
