"""B3 fase c (13 oktober 2026): items op een hairline.

Besluiten (Stefan, 12 en 13 oktober):
  - Kaarten, rijen en pills/chips: 1px `--hair` in plaats van 1,5px. Een interactieve kaart of pill
    wordt zwart bij hover; een etiket dat niets doet niet.
  - Invoervelden en checkboxes houden een zwarte 1px-rand.
  - Geen dubbele randen; nav-items zonder rand.

DE GUARD OP HET PATROON. Een nieuwe kaart, rij of pill krijgt de hairline vanzelf via `.card`,
`.pill`/`.chip` en `--hair`. Wat hier faalt:
  1. een rand in de hairline-kleur die niet 1px is (`--hair` of `--nu-border-subtle`);
  2. een NIEUWE rand van 1,5px. De bestaande staan hieronder met een reden (knoppen, statusvormen,
     het actieve tabblad); de lijst mag alleen korter worden.
De dubbele randen worden lokaal in Chromium gemeten (geen Chromium in CI voor deze meting).
"""
from __future__ import annotations

import re

from tests.test_b3_lijn import CSS, _blokken, _regel

#: selector → waarom hij 1,5px mag houden. Geen items: knoppen en vormen met een eigen betekenis.
ANDERHALF = {
    ":root .btn": "knop (fase d bepaalde de knoppen; geen item)",
    ":root .addlink": "knop: de per-kolom \"+ add project\" en de link-knoppen",
    ":root .wz-btn": "knop in de wizard",
    ".wz-btn.ghost": "knop in de wizard (oude laag)",
    ".wz-add button": "knop in de wizard (oude laag)",
    ":root .c2-burger": "knop: menu en zoeken op mobiel",
    ":root .wb-menu": "menu van de wiki-werkbalk (een paneel, geen item)",
    ":root .wiki-tb": "de wiki-werkbalk (een paneel, geen item)",
    ":root .c2-tabs a.on": "het actieve tabblad: sluit met een witte onderrand aan op de inhoud",
    ":root .c2-av": "avatar-ring",
    ":root .c2-live": "de live-stip van een overleg",
    ":root .pcol-h::before": "statusvorm in de kolomkop",
    ".mdot.n": "statusstip",
    ":root .sec-issue": "melding die eruit moet springen",
    ":root .blok": "alarm (rood): mag niet opgaan in de rust",
}

#: De families en hun regel. Een nieuwe kaart of rij erft dit; hier staat het om te zien dat het zo
#: BLIJFT.
KAARTEN = (":root .card", ":root .pkaart", ":root .kcard", ":root .attcard", ":root .gs-hit",
           ":root .tile", ":root .pcol .card", ":root .tree", ":root .outline", ":root .msg-bijlage")
RIJEN = {":root .uk-rij": "top", ":root .uk-voet": "top", ":root .c2-foot": "top",
         ":root .msg-balk": "top", ":root .wo-mem": "bottom", ":root .qadd-bar": "top",
         ":root .c2-orgfly > summary": "bottom", ":root .wo-ocd .wo-band": "bottom"}


def _randen():
    for sel, decl in _blokken(CSS):
        for d in re.findall(r"(border(?:-[a-z]+)*\s*:[^;]*)", decl):
            naam = d.split(":")[0].strip()
            if "radius" in naam or naam.endswith("-color") or naam.endswith("-style"):
                continue
            yield sel, d.strip()


def test_een_hairline_is_altijd_1px():
    fout = [(s, d) for s, d in _randen()
            if re.search(r"var\(--(hair|nu-border-subtle)\)", d) and not re.search(r"(?<![\d.])1px\b", d)]
    assert fout == [], fout


def test_geen_nieuwe_rand_van_anderhalve_pixel():
    nu = {s.split(",")[0].strip() for s, d in _randen() if "1.5px" in d}
    assert sorted(nu - set(ANDERHALF)) == [], "nieuwe 1,5px-rand: geef een item 1px --hair"
    assert sorted(set(ANDERHALF) - nu) == [], "haal van ANDERHALF af (geen 1,5px meer)"


def test_kaarten_staan_op_de_hairline():
    for sel in KAARTEN:
        assert "border: 1px solid var(--hair)" in _regel(sel), sel


def test_rijen_staan_op_de_hairline():
    for sel, kant in RIJEN.items():
        assert f"border-{kant}: 1px solid var(--hair)" in _regel(sel), sel


def test_pills_zijn_neutraal_met_een_hairline():
    r = _regel(":root .pill")
    assert "border: 1px solid var(--hair)" in r
    assert "background: var(--nu-surface)" in r and "color: var(--nu-text)" in r


def test_interactieve_items_worden_zwart_bij_hover():
    for sel in (":root .pkaart:hover", ":root .pcard:hover", ":root .vswitch a:hover", ":root .vswitch a.on",
                ":root a.pill:hover", ":root summary.chip:hover", ":root summary.outline:hover",
                ":root .gs-hit:hover", ":root .pkaart-rail .chip.outline:hover"):
        assert "border-color: var(--nu-text)" in _regel(sel), sel
    # en het etiket dat niets doet niet: geen hover op `span.pill` of de kale `.pill`
    assert _regel(":root .pill:hover") == "" and _regel(":root span.pill:hover") == ""


def test_de_bordkaart_hover_is_een_lijn_niet_twee():
    """De groene hover droeg een rand én een outline 3px naar binnen: twee lijnen om één kaart."""
    assert "outline" not in _regel(":root .pcard:hover")


def test_invoervelden_en_checkboxes_houden_1px_zwart():
    assert "border: 1px solid var(--nu-text)" in _regel(":root input[type=text]")
    assert "border:1px solid var(--nu-text)" in _regel(".ck-box")
    assert "border:1px solid var(--nu-text)" in _regel(".wz textarea")
    for sel in (":root .uk-sub input", ":root .att-pop input[type=text]", ":root .qadd-form textarea",
                ":root .msg-zoek input[type=search]"):
        assert "border-bottom: 1px solid var(--nu-text)" in _regel(sel), sel


def test_nav_items_hebben_geen_rand():
    """Alleen het balkje links (transparant, of neon op de huidige plek). De meeting-knoppen bovenin
    de zijbalk zijn knoppen met een hairline, geen nav-items."""
    for sel, d in _randen():
        delen = [x.strip() for x in sel.split(",")]
        if any(re.search(r"\.c2-subnav a(?![\w.-])|\.c2-subnav \[aria-current\]", x) and "c2-overleg" not in x
               for x in delen):
            assert d.startswith("border-left") or re.fullmatch(r"border\s*:\s*(0|none)", d), (sel, d)
