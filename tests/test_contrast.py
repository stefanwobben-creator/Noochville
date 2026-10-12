"""Tekstcontrast (A1 f, 11 oktober 2026): geen tekstkleur zonder gemeten 4,5:1.

Drie lagen:
1. DE TOKENS. Elke tekstkleur-token haalt 4,5:1 op wit, #FFFAFA (--nu-bg) en #E2FFE3 (--nu-bg-alt);
   het lichte grijs voor donkere vlakken haalt 4,5:1 op zwart.
2. DE REGELS. Een vulkleur of randkleur mag niet als `color:` terugkomen (--green, --nu-accent,
   --coral, --nu-danger, --border, #1F9D55): die haalden 1,4-3,9:1. Tekstgroen = --nu-accent-text
   (= --green-dark), tekstrood = --danger-text.
3. WIT OP GROEN (#1F9D55, 3,49:1) als RATCHET: de bestaande regels staan hieronder (de `:root`-laag
   wint er in de praktijk van); een nieuwe faalt, en de lijst kan alleen krimpen.
"""
from __future__ import annotations

import pathlib
import re

from nooch_village import web_base

CSS = (pathlib.Path(__file__).resolve().parents[1] / "nooch_village" / "static" / "nooch.css").read_text()
BRONNEN = (("web_base._CSS", web_base._CSS), ("nooch.css", CSS))

TEKST = ("--nu-text", "--ink", "--gray", "--nu-muted", "--subtle", "--muted", "--green-dark",
         "--nu-accent-text", "--danger-text")
#: De lichte achtergronden waarop tekst staat: wit, --nu-bg, --nu-bg-alt en de twee crèmes (gemeten:
#: een `summary` op --cream-2 haalde met #727272 net 4,46:1).
ACHTERGROND = ("--surface", "--nu-surface", "--nu-bg", "--nu-bg-alt", "--cream", "--cream-2")
VERBODEN_ALS_TEKST = re.compile(
    r"(?<![-\w])color\s*:\s*(var\(--(green|nu-accent|coral|nu-danger|border)\s*[,)]|#1F9D55\b|#00A551\b)", re.I)

#: De regels met wit op --green die er op 11 oktober stonden. Alleen weghalen.
WIT_OP_GROEN = {
    ("web_base._CSS", ".btn.ok"), ("nooch.css", ".av"), ("nooch.css", ".chip.green"),
    ("nooch.css", ".cl-filter.pill.on"), ("nooch.css", ".cl-check.ok.on"), ("nooch.css", ".cl-check.ok:hover"),
    ("nooch.css", ".rdr-promote:hover"), ("nooch.css", ".wo-step.on .wo-num"),
    ("nooch.css", ".wo-step.done .wo-num"), ("nooch.css", ".vbtn.on"), ("nooch.css", ".c2-navct"),
    ("nooch.css", ".c2-subnav a.c2-overleg:hover"), ("nooch.css", ".c2-subnav a.c2-overleg--live"),
    ("nooch.css", ".wz-btn"),
}


def _regels():
    for naam, css in BRONNEN:
        for m in re.finditer(r"([^{}@]+)\{([^{}]*)\}", re.sub(r"/\*.*?\*/", "", css, flags=re.S)):
            yield naam, " ".join(m.group(1).split()), m.group(2)


def _tokens() -> dict[str, str]:
    uit = {}
    for _naam, sel, body in _regels():
        if ":root" in sel and "--" in body:
            for t in re.finditer(r"(--[\w-]+)\s*:\s*([^;]+)", body):
                uit[t.group(1)] = t.group(2).strip()
    return uit


def _hex(tokens: dict, t: str) -> str:
    v = tokens[t]
    for _ in range(5):
        m = re.match(r"var\((--[\w-]+)", v)
        if not m:
            break
        v = tokens[m.group(1)]
    v = v.lstrip("#")
    return "".join(c * 2 for c in v) if len(v) == 3 else v


def _lum(h: str) -> float:
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (f(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a: str, b: str) -> float:
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def test_elke_teksttoken_haalt_4_5_op_elke_lichte_achtergrond():
    tk = _tokens()
    fout = [(t, a, round(ratio(_hex(tk, t), _hex(tk, a)), 2)) for t in TEKST for a in ACHTERGROND
            if ratio(_hex(tk, t), _hex(tk, a)) < 4.5]
    assert fout == [], fout


def test_licht_grijs_op_zwart():
    tk = _tokens()
    assert ratio(_hex(tk, "--text-on-dark-muted"), _hex(tk, "--nu-text")) >= 4.5


def test_tekstgroen_is_green_dark():
    assert _tokens()["--nu-accent-text"] == "var(--green-dark)"


def test_geen_vul_of_randkleur_als_tekstkleur():
    fout = [(naam, sel, m.group(0)) for naam, sel, body in _regels() for m in VERBODEN_ALS_TEKST.finditer(body)]
    assert fout == [], fout


def test_wit_op_groen_alleen_de_bekende_schuld():
    nu = set()
    for naam, sel, body in _regels():
        if (re.search(r"(?<![-\w])color\s*:\s*(#fff\b|#ffffff\b|white\b)", body, re.I)
                and re.search(r"background(-color)?\s*:\s*var\(--(green|nu-accent)\)", body)):
            nu.add((naam, sel))
    assert nu - WIT_OP_GROEN == set(), f"nieuw wit op groen (3,49:1): {sorted(nu - WIT_OP_GROEN)}"
    assert WIT_OP_GROEN - nu == set(), f"niet meer wit op groen — haal uit WIT_OP_GROEN: {sorted(WIT_OP_GROEN - nu)}"


def test_de_paren_van_b3_fase_d():
    """B3 fase d (13 oktober 2026): de gekozen modus is wit op zwart, de hoofdactie zwart op neon,
    de huidige plek zwart op --nu-bg-alt. Alle drie gemeten tegen 4,5:1."""
    tk = _tokens()
    for tekst, vlak in (("--nu-surface", "--nu-text"), ("--nu-text", "--nu-neon"), ("--nu-text", "--nu-bg-alt")):
        assert ratio(_hex(tk, tekst), _hex(tk, vlak)) >= 4.5, (tekst, vlak, round(ratio(_hex(tk, tekst), _hex(tk, vlak)), 2))
