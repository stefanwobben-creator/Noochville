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
           ":root .tile", ":root .pcol .card", ":root .tree", ":root .msg-bijlage")
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


def test_een_label_dat_niets_doet_heeft_geen_rand():
    """Besluit 13 oktober: een rand betekent aanklikbaar. De basis is transparant (de hoogte blijft
    gelijk aan de pills mét rand), het vlak neutraal."""
    for sel in (":root .pill", ":root .outline"):
        assert "border: 1px solid transparent" in _regel(sel), sel
    r = _regel(":root .pill")
    assert "background: var(--nu-surface)" in r and "color: var(--nu-text)" in r
    assert "border" not in _regel(":root .pill.muted")


def test_een_aanklikbare_pill_heeft_de_hairline():
    for sel in (":root a.pill", ":root a.chip", ":root button.chip", ":root summary.chip"):
        assert "border-color: var(--hair)" in _regel(sel), sel


#: Regels die een label een zichtbare rand geven zonder tag in de selector, met de reden.
LABEL_RAND_UITZONDERING = {
    ":root .pkaart-rail .chip.outline": "de Deadline-opener op de projectrail: altijd een <summary>",
    ":root .pkaart-rail .chip.outline:hover": "idem, bij hover",
    ":root .pkaart-rail details[open] > .chip.outline": "idem, als de popover open is",
    ":root .chip.coral-solid": "rand in de vulkleur: geen zichtbare lijn, alleen het rode vlak",
}


def _label_klassen() -> set[str]:
    """pill/chip/badge/outline plus elke klasse die in de views SAMEN met een label staat (`doel`,
    `amber`, `muted` …): een regel op `:root .doel` raakt het label net zo goed."""
    import pathlib
    views = pathlib.Path(__file__).resolve().parents[1] / "nooch_village"
    kern = {"pill", "chip", "badge", "outline"}
    uit = set(kern)
    for f in [*views.glob("*.py"), *(views / "views").glob("*.py")]:
        for m in re.finditer(r"class=['\"]([^'\"{}]*)", f.read_text(encoding="utf-8")):
            kl = set(m.group(1).split())
            if kl & kern:
                uit |= kl
    return uit


def _zichtbare_rand(decl: str) -> bool:
    for d in re.findall(r"(border(?:-(?:top|right|bottom|left))?(?:-color)?\s*:[^;]*)", decl):
        waarde = d.split(":", 1)[1].strip()
        if "radius" in d or re.fullmatch(r"(0|none)", waarde) or "transparent" in waarde:
            continue
        return True
    return False


def test_geen_rand_op_een_label_tenzij_het_aanklikbaar_is():
    labels = _label_klassen()
    fout = []
    for sel, decl in _blokken(CSS):
        if not _zichtbare_rand(decl):
            continue
        for deel in (x.strip() for x in sel.split(",")):
            if not deel.startswith(":root") or deel in LABEL_RAND_UITZONDERING:
                continue
            laatste = re.split(r"[\s>+~]+", deel)[-1]
            klassen = set(re.findall(r"\.([\w-]+)", laatste.split(":")[0]))
            tag = re.match(r"[a-z]+", laatste)
            if klassen and klassen <= labels and not (tag and tag.group(0) in ("a", "button", "summary")):
                fout.append(deel)
    assert fout == [], "een rand op een label dat niets doet: " + ", ".join(sorted(set(fout)))


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


def test_secundaire_knoppen_hebben_1px_zwart_en_de_hoofdactie_houdt_haar_vorm():
    """B3 fase e, commit 1 (13 oktober 2026): .btn, .addlink, de wizardknoppen en de menuknop van
    1,5px naar 1px zwart. De neon hoofdactie verandert niet van vorm: vulling, transparante rand ter
    breedte van de andere knoppen (geen eigen breedte, dus even hoog)."""
    for sel, decl in ((":root .btn", "border: 1px solid var(--nu-text)"),
                      (":root .addlink", "border: 1px solid var(--nu-text)"),
                      (":root .wz-btn", "border: 1px solid var(--nu-text)"),
                      (":root .c2-burger", "border: 1px solid var(--nu-text)"),
                      (".wz-btn.ghost", "border:1px solid var(--nu-text)"),
                      (".wz-add button", "border:1px solid var(--nu-text)")):
        assert decl in _regel(sel), sel
    ok = _regel(":root .btn.ok")
    assert "background: var(--nu-neon)" in ok and "border-color: transparent" in ok
    assert not re.search(r"border(-width)?\s*:\s*[\d.]+px", ok)        # volgt de breedte van .btn
