"""Een blok licht op als je er met de muis overheen gaat (25 september 2026).

WAT ER ONTBRAK. Van het hele blok verscheen alleen het grip-icoontje (`.wb:hover>.wb-greep`); de
rest bleef precies zoals in rust. Je zag dus wel dát er iets te pakken viel, maar niet WAT je
beetpakte — en bij een lijst of een tabel is dat precies de vraag.

TWEE KEUZES DIE STEFAN HEEFT GOEDGEKEURD:

1. **Alleen in bewerkstand** (`.wiki-aan`). De greep bestaat ook alleen dan — `grepen(body, aan)`
   hangt hem erin bij het aanzetten en haalt hem er weer uit. Een oplichtend blok in leesstand
   belooft een handeling die er niet is.
2. Geen nieuwe kleur en geen nieuwe klasse-familie: `--cream-2` is de bestaande zachte
   achtergrond, `--radius` de bestaande hoek, en `wb-` is een familie die al bestaat. De
   prefix-ratchet in `test_ui_ratchets` beweegt hier dus niet van.

DE GOOT HOORT BIJ HET BLOK. Dit is het enige stuk dat verder gaat dan één regel CSS. De greep
stond op `left:-1.5rem`, buiten de doos van `.wb`, in de padding van de body. Een achtergrond op
`.wb` dekt hem dan niet: je krijgt een oplichtend blok met een los icoontje ernaast in het wit.
Daarom verhuist de goot van de body naar het blok — negatieve marge plus evenveel padding, zodat
de TEKST geen millimeter opschuift maar de doos wel tot aan de rand loopt.
"""
from __future__ import annotations

import pathlib
import re

CSS = (pathlib.Path(__file__).resolve().parents[1]
       / "nooch_village" / "static" / "nooch.css").read_text()


def _regel(selector: str) -> str:
    m = re.search(re.escape(selector) + r"\{([^}]*)\}", CSS, re.S)
    assert m, f"{selector} bestaat niet (meer)"
    return m.group(1)


# ── 1. Het blok zelf licht op ────────────────────────────────────────────────
def test_het_hele_blok_krijgt_een_hover_en_niet_alleen_de_greep():
    """DE EIS. Er was al `.wb:hover>.wb-greep{opacity:1}` — dat laat het icoontje zien, niet het
    blok. Deze toets eist een regel die het BLOK zelf een achtergrond geeft."""
    inhoud = _regel(".wiki-body.wiki-aan .wb:hover")
    assert "background" in inhoud, "het blok krijgt geen achtergrond op hover"


def test_de_hover_gebruikt_een_bestaande_kleur():
    """Geen nieuwe tint erbij: de zachte achtergrond die het dorp al heeft."""
    assert "var(--" in _regel(".wiki-body.wiki-aan .wb:hover")


def test_de_greep_blijft_ook_verschijnen():
    """De bestaande affordance mag niet vervangen worden door de nieuwe."""
    assert ".wb:hover>.wb-greep" in CSS


# ── 2. Alleen in bewerkstand ─────────────────────────────────────────────────
def test_de_hover_hangt_aan_de_bewerkstand():
    """Keuze van Stefan: een oplichtend blok in leesstand belooft een handeling die er niet is.

    HIER STOND EERST EEN SUBSTRING-CHECK (`".wb:hover{background" not in CSS`), en die viel op de
    goede code: na het strippen van spaties bevat `.wiki-body.wiki-aan .wb:hover` diezelfde
    letters. Een selector toets je op zijn structuur, niet op een stukje tekst dat er toevallig
    ook in een langere selector staat. Dat doet de regex hieronder, en dus is dit nu één toets in
    plaats van twee.

    Meteen de leespagina uit #574/#594 afgedekt: `.att-body` zonder `.wiki-aan` heeft geen blokken
    en hoort niets van deze laag te merken."""
    for m in re.finditer(r"([^{}]*\.wb:hover[^{}]*)\{([^}]*)\}", CSS):
        if "background" in m.group(2):
            assert "wiki-aan" in m.group(1), f"{m.group(1).strip()!r} licht buiten de bewerkstand op"


# ── 3. De greep ligt ín de oplichtende doos ──────────────────────────────────
def test_de_goot_hoort_bij_het_blok_en_niet_bij_de_body():
    """Anders dekt de achtergrond de greep niet en staat het icoontje in het wit ernaast.
    Negatieve marge + evenveel padding: de doos groeit naar links, de tekst blijft staan."""
    inhoud = _regel(".wiki-body.wiki-aan .wb")
    marge = re.search(r"margin-left:(-[\d.]+)rem", inhoud)
    padding = re.search(r"padding-left:([\d.]+)rem", inhoud)
    assert marge and padding, "de goot verhuist niet naar het blok"
    assert float(marge.group(1)) == -float(padding.group(1)), \
        "marge en padding zijn niet gelijk — de tekst schuift op bij het bewerken"


def test_de_greep_staat_binnen_het_blok():
    """Hij stond op `left:-1.5rem`, buiten de doos. Binnen de nieuwe doos moet hij een POSITIEVE
    offset hebben, anders ligt hij alsnog naast de oplichting."""
    inhoud = _regel(".wiki-body.wiki-aan .wb-greep")
    m = re.search(r"left:([\d.-]+)rem", inhoud)
    assert m and float(m.group(1)) >= 0, "de greep ligt buiten het oplichtende blok"


def test_deze_wijziging_verschuift_de_tekst_niet():
    """DE TITEL HIERVAN WAS EERST EEN LEUGEN. Hij heette "de tekst staat op dezelfde plek als in
    leesstand", en dat is níet waar: gemeten in Chrome staat de tekst in leesstand op x=62 en in
    bewerkstand op x=92. Die sprong van 1,9rem komt van `.wiki-body.wiki-aan{padding-left}` en
    bestond al vóór deze wijziging — met de CSS van `origin/main` erbij gemeten is hij identiek
    (62 → 92). Ik had de eigenschap getoetst en de uitkomst BEWEERD.

    Wat deze toets wél bewaakt is dat DEZE wijziging niets verschuift: de body houdt zijn padding
    (anders verspringt er alsnog iets) en het blok compenseert zijn eigen padding met een even
    grote negatieve marge. De bestaande sprong is een los punt; die staat in het PR-verslag, niet
    stilzwijgend hier verstopt."""
    assert "padding-left:1.9rem" in _regel(".wiki-body.wiki-aan")
    inhoud = _regel(".wiki-body.wiki-aan .wb")
    assert "margin-left:-1.9rem" in inhoud and "padding-left:1.9rem" in inhoud


# ── 4. Geen nieuw vocabulaire ────────────────────────────────────────────────
# HIER STOND EEN EIGEN WITTE LIJST van toegestane klasse-prefixen, en die was fout bij de eerste
# run — ik had hem uit mijn hoofd geschreven. Belangrijker: `test_ui_ratchets` bevriest het aantal
# prefix-families al, projectbreed en met een gemeten plafond. Een tweede, handgeschreven lijst is
# precies het dubbele-waarheid-probleem dat dit project elders verbiedt: hij loopt uit de pas en
# meldt zich niet. De ratchet doet dit werk; deze toets hoort hier niet.


# ── 5. De nu-laag ────────────────────────────────────────────────────────────
def test_de_nu_laag_heeft_een_eigen_hover():
    """`test_fase10_huisstijl` viel hierop, en terecht: een nieuwe zichtbare klasse in de oude
    laag zonder tegenhanger in `nooch-ui.css` is precies wat die ratchet bewaakt. `--cream-2` is
    een warme crèmetint die in de nieuwe huisstijl niet bestaat, dus de tegenhanger gebruikt
    `--nu-bg-alt` en vierkante hoeken, zoals de rest van die laag."""
    nu = (pathlib.Path(__file__).resolve().parents[1]
          / "nooch_village" / "static" / "nooch-ui.css").read_text()
    assert ".nu .wiki-body.wiki-aan .wb:hover" in nu
    assert "--nu-bg-alt" in nu.split(".nu .wiki-body.wiki-aan .wb:hover")[1][:80]
    assert "cream" not in nu.split(".nu .wiki-body.wiki-aan .wb:hover")[1][:80]
