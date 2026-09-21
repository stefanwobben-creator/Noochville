"""Geen stylesheet voor schermen die niet meer bestaan.

DE AANLEIDING, met het getal erbij: bij het uitzoeken van de 33 kleur-alleen-statussen bleek dat
22 ervan door geen enkel `class=`-attribuut werden gerenderd — en dat alle 14 kennisbank-gevallen
daarbij zaten. De kennisbank-VIEW is in de opruiming van fase 1-9 verwijderd (#516), zijn
stylesheet niet. Dat zijn 192 regels CSS voor vijf schermen die er niet meer zijn.

WAAROM DAT MEER IS DAN ROMMEL. Dode CSS liegt op drie manieren tegelijk: hij telt mee in elke
meting (de "33" was voor tweederde een meetartefact), hij suggereert dat er een scherm is dat dit
gebruikt, en hij wordt bij elke stijlronde meegesleept — fase 9 en 12 hebben deze families braaf
meegeteld en meegewogen terwijl er niets achter zat.

WAT DEZE TEST BEWAAKT is niet "er staat niets doods in de CSS" — dat is met een statische toets
niet hard te maken, want een klasse kan dynamisch worden samengesteld. Hij bewaakt de ZES families
die op 20 september 2026 zijn opgeruimd: die komen niet terug zolang er geen renderer voor is. Komt
er ooit weer een kennisbank-scherm, dan komt de CSS gewoon mee met dat scherm — en dan faalt deze
test luid genoeg om hem in dezelfde beurt bij te werken.
"""
from __future__ import annotations

import glob
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[1]
CSS = (REPO / "nooch_village" / "static" / "nooch.css").read_text()
_ONT = re.sub(r"/\*.*?\*/", " ", CSS, flags=re.S)

#: De families die zijn opgeruimd, met wat er nog wél van leeft.
OPGERUIMD = ("kn-", "imp-pill", "wz-was", "wz-now", "rail-btn", "fkind", "avatar",
             # 21 september 2026: de inbox-lade. 72 regels in twee stylesheets voor een
             # scherm dat nooit gerenderd werd — `ibxToggle` en `render_inbox_chrome`
             # bestaan allebei niet. Zie `test_nav_ia`.
             "ibx-",
             # 21 september 2026: de 64px icoon-rail. Hij bestond voor één scherm (/messages) en
             # die uitzondering is vervallen — een balk die ergens anders breed is dan overal, is
             # een tweede navigatiemodel. De `rail`-parameter van `_nav` ging mee.
             "c2-side--rail")

#: De enige overlevende: hergebruikt door de claims-view, dus hij hoort te blijven.
OVERLEVER = "kn-searchbox"


def _gerenderde_klassen() -> set[str]:
    """Elke klassenaam die de code in een `class=`-attribuut kan zetten.

    Drie vormen, want dit project bouwt klassen op drie manieren: letterlijk in een attribuut,
    via `classList.add`, en via een variabele die daarna in een f-string landt (`rowcls = " cl-attn"`).
    De derde is de reden dat een naïeve grep hier twee keer de mist in ging."""
    uit = set()
    for f in (glob.glob(str(REPO / "nooch_village" / "**" / "*.py"), recursive=True)
              + glob.glob(str(REPO / "nooch_village" / "**" / "*.js"), recursive=True)):
        src = pathlib.Path(f).read_text()
        for m in re.findall(r"""class=\\?["']([^"']{0,400})""", src):
            for stuk in re.split(r"[\s{}'\"]+", m):
                if re.fullmatch(r"[a-z0-9_-]+", stuk or ""):
                    uit.add(stuk)
        uit |= set(re.findall(r"classList\.(?:add|toggle|remove)\(['\"]([a-z0-9_-]+)", src))
        uit |= set(re.findall(r"""=\s*["'] ?([a-z][a-z0-9_-]{2,})["']""", src))
    return uit


def _klassen_in_css(families) -> set[str]:
    uit = set()
    for sel, _b in re.findall(r"([^{}]+)\{([^{}]*)\}", _ONT):
        for k in re.findall(r"[.#]([a-z0-9_-]+)", sel):
            if any(k.startswith(f.rstrip("-")) for f in families):
                uit.add(k)
    return uit


def test_de_opgeruimde_families_zijn_weg():
    """192 regels eruit; wat terugkomt zonder scherm erbij, valt hier op."""
    rest = _klassen_in_css(OPGERUIMD) - {OVERLEVER}
    assert rest == set(), (
        f"deze klassen uit opgeruimde families staan weer in nooch.css: {sorted(rest)}. "
        "Hoort er een scherm bij? Dan mag de CSS mee — en dan hoort deze test in dezelfde beurt "
        "bijgewerkt te worden.")


def test_de_overlever_leeft_echt_nog():
    """`kn-searchbox` is als enige blijven staan omdat de claims-view hem hergebruikt. Verdwijnt
    díe renderer, dan is ook dit laatste restje dood — en dan hoort het weg, niet bewaard."""
    assert OVERLEVER in _klassen_in_css(("kn-",)), "de overlever is uit de CSS verdwenen"
    assert OVERLEVER in _gerenderde_klassen(), (
        f".{OVERLEVER} wordt nergens meer gerenderd — haal hem dan ook uit de CSS")


def test_er_hangen_geen_wezen_aan_de_opgeruimde_families():
    """Een keyframe of een id-selector die alleen door verwijderde regels werd gebruikt, blijft
    anders stil achter. `@keyframes kn-vgvullen` en `#kn-biebresults` waren precies dat."""
    for naam in ("kn-vgvullen", "kn-vgpuls", "kn-biebresults"):
        assert naam not in CSS, f"{naam} hoort bij een verwijderd scherm"


def test_de_css_is_nog_geldig():
    """Knippen in een stylesheet met een script: de goedkoopste controle die een halve regel vangt.

    Alleen de accolade-balans, en bewust niet "er staat nergens `}}`" — een media-query en een
    keyframe sluiten legitiem dubbel af. Een controle die op de normale vorm afgaat, is een
    controle die wordt uitgezet."""
    assert CSS.count("{") == CSS.count("}"), "ongebalanceerde accolades na het knippen"
    assert not re.search(r"\{\s*\}", _ONT), "lege regel overgebleven na het knippen"


# ── De inbox-lade (21 september 2026) ────────────────────────────────────────────────────────
#
# Het gevaarlijkste deel van die opruiming was niet het weghalen maar het KNIPPEN: zeventien van
# de regels deelden hun selectorlijst met een levende klasse (`.nu .ibx-row, .nu .wo-oc, .nu
# .rdr-tool, …`). Wie zo'n regel in zijn geheel weggooit, haalt de vorm weg bij het werkoverleg en
# de radar-lezer — en dat merk je pas op een screenshot.

NU_CSS = (REPO / "nooch_village" / "static" / "nooch-ui.css").read_text()

#: De levende klassen die in de gedeelde selectorlijsten van de lade meeliftten.
MEELIFTERS = ("wo-oc", "rdr-tool", "rdr-kader", "rdr-vier", "fsep", "ck-item")


def test_de_lade_is_uit_beide_stylesheets_weg():
    """Geen enkele `ibx-`-selector meer, in geen van beide bestanden. (De prose mag hem noemen —
    dat is de uitleg waaróm hij weg is, en die hoort te blijven staan.)"""
    for naam, css in (("nooch.css", CSS), ("nooch-ui.css", NU_CSS)):
        zonder = re.sub(r"/\*.*?\*/", " ", css, flags=re.S)
        rest = re.findall(r"[^{}]*\.ibx-[a-z-]*[^{}]*\{", zonder)
        assert not rest, f"{naam} draagt nog {len(rest)} ibx-selector(s): {rest[:2]}"


def test_de_meelifters_hebben_hun_vorm_gehouden():
    """DE ANDERE KANT. Elke klasse die met de lade in één selectorlijst stond, moet nog steeds
    door minstens één regel bediend worden. Zonder deze test leest de vorige als "knip alles weg
    waar ibx in staat", en dat is precies de manier waarop dit fout gaat."""
    for klasse in MEELIFTERS:
        gevonden = any(re.search(rf"\.{re.escape(klasse)}(?![\w-])", sel)
                       for css in (CSS, NU_CSS)
                       for sel in re.findall(r"([^{}]*)\{", re.sub(r"/\*.*?\*/", " ", css, flags=re.S)))
        assert gevonden, f".{klasse} liftte mee met de lade en is per ongeluk meegeknipt"


def test_de_tweede_stylesheet_is_ook_nog_geldig():
    """Zelfde goedkope controle als hierboven, nu voor `nooch-ui.css` — daar is óók in geknipt."""
    assert NU_CSS.count("{") == NU_CSS.count("}"), "ongebalanceerde accolades in nooch-ui.css"
    assert not re.search(r"\{\s*\}", re.sub(r"/\*.*?\*/", " ", NU_CSS, flags=re.S)), (
        "lege regel overgebleven in nooch-ui.css")
