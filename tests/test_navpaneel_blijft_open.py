"""Het nav-paneel overleeft een paginalaad (23 september 2026).

WAT ER MIS WAS. "Welk paneel staat open" leefde alleen in de variabele `open` binnen
`navPaneel()`, en die begint bij elke navigatie opnieuw op null. Klikken op een rol in de
organisatieboom is een gewone link, dus het paneel viel dicht en je moest voor élke volgende rol
opnieuw op Organization klikken — precies het doorbladeren waar de boom voor bedoeld is.

WAAROM `sessionStorage` EN NIET DE SERVER. Het is een voorkeur van dít tabblad, geen feit over het
dorp: het hoort niet in de records, niet in een serversessie en niet in een querystring die je per
ongeluk deelt. Per tab, en weg als het tabblad weg is.

DE BOOM ZELF IS NIET AANGERAAKT. `_tree_html` klopt al: geneste `<details>`, dus een subcirkel
onder Nooch schaalt vanzelf mee. Dit gaat alleen over het paneel dat eromheen staat.

TOETSEN OP DE BRON, en dat is geen luiheid maar de stand van deze stack: er is geen JS-testrunner
(geen package.json, geen node_modules). Wat hier staat bewaakt de BEDRADING; het GEDRAG is met een
echte browser gemeten — zie de terugkoppeling bij de PR. Daarom leest elke toets hieronder de
bron ZONDER commentaar: anders houdt een uitleg over wat er weg is de toets groen.
"""
from __future__ import annotations

import pathlib
import re

JS = (pathlib.Path(__file__).resolve().parents[1]
      / "nooch_village" / "static" / "nooch.js").read_text()


def _zonder_commentaar(js: str) -> str:
    js = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
    return re.sub(r"^\s*//[^\n]*", " ", js, flags=re.M)


def _navpaneel_bron() -> str:
    """Alleen de body van `navPaneel`. NIET het hele bestand: elders staat ook een `sluit()` en
    een `vul()`, en dan meet je de buurman — dezelfde val als bij `_wiki_edit_bron`."""
    kaal = _zonder_commentaar(JS)
    m = re.search(r"function navPaneel\(root\) \{(.*?)\n  \}\n", kaal, re.S)
    assert m, "navPaneel niet gevonden"
    return m.group(1)


# ── 1. De stand wordt onthouden ──────────────────────────────────────────────
def test_de_stand_leeft_in_sessionstorage_en_nergens_anders():
    bron = _navpaneel_bron()
    assert "sessionStorage" in bron
    assert "localStorage" not in bron, (
        "localStorage overleeft het tabblad; een open paneel is geen blijvende voorkeur")
    assert "document.cookie" not in bron, "dit hoort niet naar de server te lekken"


def test_de_bewaarsleutel_staat_op_een_plek():
    """Twee literals voor dezelfde sleutel is precies hoe schrijven en lezen uit elkaar gaan
    lopen. Reference, don't copy, ook voor een string van twaalf tekens."""
    bron = _navpaneel_bron()
    assert bron.count('"nv-navpaneel"') == 1, "de sleutel staat meer dan één keer als literal"
    assert "BEWAARSLEUTEL" in bron


def test_lezen_en_schrijven_mogen_allebei_falen():
    """`sessionStorage` gooit in privémodus en bij geblokkeerde opslag. Dan hoort het paneel te
    werken zoals vroeger — open zolang je op de pagina blijft — en niet de rest van de navigatie
    mee te slepen."""
    bron = _navpaneel_bron()
    for naam in ("function onthoud(", "function bewaard("):
        i = bron.index(naam)
        lichaam = bron[i:bron.index("\n    }", i)]
        assert "try {" in lichaam and "catch" in lichaam, f"{naam} is niet fail-soft"


# ── 2. Het herstel gebruikt dezelfde deur als de klik ────────────────────────
def test_er_is_maar_een_plek_die_het_paneel_opent():
    """DE KERN VAN DE WIJZIGING. Zou het herstel zijn eigen kopie van "paneel openen" hebben, dan
    is een herstelde stand net iets anders dan een geklikte — en dat merk je pas als er aan één
    van de twee iets bijkomt."""
    bron = _navpaneel_bron()
    assert bron.count('vul("/nav-paneel?p=" +') == 1, (
        "het paneel wordt op meer dan één plek gevuld met een paneel-sleutel")
    assert "function openen(" in bron


def test_de_klik_roept_openen_aan_en_doet_het_niet_zelf():
    kaal = _navpaneel_bron()
    i = kaal.index('knop.addEventListener("click"')
    handler = kaal[i:kaal.index("});", i)]
    assert "openen(sleutel)" in handler
    assert "paneel.hidden" not in handler, "de klik zet de stand nog zelf"


def test_het_herstel_draait_bij_het_laden():
    bron = _navpaneel_bron()
    assert re.search(r"if \(bewaard\(\)\) openen\(bewaard\(\)\);", bron), (
        "er is niets dat het paneel na een paginalaad terugzet")


def test_het_herstel_richt_zich_op_de_node_waar_je_landde():
    """`hier` maakt dat de boom de tak openklapt en de node markeert. Zonder dit komt het paneel
    wel terug, maar dichtgeklapt — en dan is doorbladeren nog steeds onwerkbaar."""
    bron = _navpaneel_bron()
    i = bron.index("function openen(")
    lichaam = bron[i:bron.index('vul("/nav-paneel?p=" +', i)]
    assert 'location.pathname === "/node"' in lichaam
    assert 'get("id")' in lichaam


# ── 3. Dicht is dicht, en een oude sleutel geneest ───────────────────────────
def test_sluiten_vergeet_de_stand():
    """Anders komt een paneel dat je expliciet dichtklikte bij de volgende pagina weer terug, en
    dat is erger dan het probleem dat dit oplost."""
    bron = _navpaneel_bron()
    i = bron.index("function sluit()")
    lichaam = bron[i:bron.index("\n    }", i)]
    assert 'onthoud("")' in lichaam


def test_een_sleutel_van_een_verdwenen_paneel_ruimt_zichzelf_op():
    """`pr` (weg in #575) en `ci` (weg in #576) kunnen nog in iemands tabblad staan. Dan hoort er
    niets te gebeuren én hoort het geheugen leeg te gaan, anders probeert elke paginalaad opnieuw
    een knop te vinden die niet bestaat."""
    bron = _navpaneel_bron()
    i = bron.index("function openen(")
    lichaam = bron[i:bron.index("\n    }", i)]
    assert re.search(r"if \(!knop\) \{ onthoud\(\"\"\); return; \}", lichaam), (
        "een onbekende sleutel wordt niet opgeruimd")


# ── 4. Wat bewust NIET is aangeraakt ─────────────────────────────────────────
def test_de_server_hoeft_hier_niets_van_te_weten():
    """Geen route, geen parameter, geen sessie erbij: `/nav-paneel` krijgt exact dezelfde twee
    dingen als eerst (`p` en optioneel `hier`)."""
    import inspect

    from nooch_village.views import navpaneel
    bron = inspect.getsource(navpaneel.render_nav_paneel)
    for woord in ("session", "storage", "open="):
        assert woord not in bron.lower(), f"de server weet nu van {woord!r}"


def test_de_boom_zelf_is_ongewijzigd():
    """`_tree_html` klopte al — geneste `<details>`, dus een subcirkel onder Nooch schaalt mee.
    Deze scope mocht daar niet aankomen."""
    import inspect

    from nooch_village.views import overview
    bron = inspect.getsource(overview._tree_html)
    assert "details class='tree-c'" in bron
    assert "sessionStorage" not in bron
