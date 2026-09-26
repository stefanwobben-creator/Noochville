"""Eén bolletje is één blok (26 september 2026).

DE MELDING: "een hele reeks regels gedraagt zich als ÉÉN blok — er zit maar één greep op, en je
kunt het alleen verplaatsen of verwijderen, niet per regel bewerken."

DE OORZAAK, gemeten en niet geraden. Op de genoemde pagina (NOTE-STRATE-004) reproduceerde het
niet: 62 bronregels → 62 blokken → 62 grepen. Een scan over alle actieve pagina's van prod gaf
acht pagina's die minder blokken opleveren dan ze regels hebben, en in alle acht is de oorzaak
dezelfde: `_md` voegde een reeks `- `-regels samen tot één `<ul>` in één `.wb`. Op
NOTE-STRATE-003 vielen 43 bronregels zo samen in 12 blokken, met runs van 3 tot 7 items.

Dat was een bewuste keuze ("een lijst sleep je als geheel"), maar hij botst met het model waar
deze editor op mikt: daar is elk bolletje zijn eigen blok met zijn eigen greep.

WAT NIET VERANDERT: de platte stand. Die rendert reacties, kanaalberichten en de leespagina van
een policy; daar bestaan geen blokken en is een lijst gewoon een lijst.
"""
from __future__ import annotations

import pathlib
import re

from conftest import js_zonder_uitleg
from nooch_village.cockpit2_util import _md, _md_naar_bron

CSS = (pathlib.Path(__file__).resolve().parents[1]
       / "nooch_village" / "static" / "nooch.css").read_text()
JS = (pathlib.Path(__file__).resolve().parents[1]
      / "nooch_village" / "static" / "nooch.js").read_text()


def _soorten(html: str) -> list[str]:
    return re.findall(r"<div class='wb' data-blok='([a-z]+)'", html)


# ── De splitsing zelf ────────────────────────────────────────────────────────
def test_elk_bolletje_is_een_blok():
    html = _md("- een\n- twee\n- drie", blokken=True)
    assert _soorten(html) == ["ul", "ul", "ul"]
    assert html.count("<li>") == 3


def test_elk_genummerd_punt_ook():
    html = _md("1. een\n2. twee\n3. drie", blokken=True)
    assert _soorten(html) == ["ol", "ol", "ol"]


def test_de_nummering_loopt_door():
    """Los van elkaar begint elke `<ol>` weer bij 1; zonder `start` werd een genummerde lijst van
    zeven regels zeven keer "1."."""
    html = _md("1. een\n2. twee\n3. drie", blokken=True)
    assert "start='1'" in html and "start='2'" in html and "start='3'" in html


def test_een_bolletjeslijst_ertussen_reset_de_teller():
    """`- a` gevolgd door `1. b` zijn twee lijsten, geen samengeraapte derde — die regel stond er
    al en blijft gelden."""
    html = _md("1. een\n- tussendoor\n1. opnieuw", blokken=True)
    assert _soorten(html) == ["ol", "ul", "ol"]
    assert html.count("start='1'") == 2, "de nummering loopt door over de bolletjes heen"


def test_de_blokken_blijven_op_het_hoogste_niveau():
    """Een blok IN een blok is geen blok meer: `closest('.wb')` zou dan het verkeerde ding
    pakken."""
    html = _md("Tekst\n- een\n- twee\nslot", blokken=True)
    diepte = maximum = 0
    for stuk in re.findall(r"<div[^>]*>|</div>", html):
        diepte += 1 if stuk != "</div>" else -1
        maximum = max(maximum, diepte)
    assert maximum == 1, html


# ── De rondgang ──────────────────────────────────────────────────────────────
def test_de_rondgang_houdt_een_bolletjeslijst_heel():
    bron = "- een\n- twee\n- drie"
    assert _md_naar_bron(_md(bron, blokken=True)) == bron


def test_de_rondgang_houdt_de_nummering_heel():
    """DE VAL VAN DEZE STAP. Zonder `start` in de weg terug komt een genummerde lijst terug als
    "1. / 1. / 1." — en dan is hij na één bewerkronde stuk in de opslag."""
    bron = "1. een\n2. twee\n3. drie"
    assert _md_naar_bron(_md(bron, blokken=True)) == bron


def test_een_lijst_tussen_tekst_overleeft_de_rondgang():
    bron = "Tekst ervoor.\n- een\n- twee\n\n1. x\n2. y\nTekst erna."
    assert _md_naar_bron(_md(bron, blokken=True)) == bron


def test_een_onzinnige_start_telt_gewoon_vanaf_een():
    """Fail-soft: een kapot attribuut hoort geen exception te geven maar de gewone nummering."""
    vuil = "<div class='wb' data-blok='ol'><ol start='abc'><li>x</li></ol></div>"
    assert _md_naar_bron(vuil) == "1. x"


# ── De platte stand blijft zoals hij was ─────────────────────────────────────
def test_de_platte_stand_houdt_de_lijst_bij_elkaar():
    """DIT IS EEN WIJZIGING AAN DE EDITOR, niet aan de opmaak. Zou de platte stand meeveranderen,
    dan valt elke lijst in elke reactie en elk kanaalbericht uit elkaar."""
    plat = _md("- een\n- twee\n- drie")
    assert plat.count("<ul") == 1 and plat.count("<li>") == 3
    assert "<div class='wb'" not in plat


def test_de_platte_stand_zet_geen_start():
    """Daar staan de items in één lijst, dus de browser telt zelf."""
    assert "start=" not in _md("1. een\n2. twee")


# ── De browser houdt de splitsing vast ───────────────────────────────────────
def _normaliseer() -> str:
    return js_zonder_uitleg(JS).split("NV.blokNormaliseer = function")[1].split("\n  NV.")[0]


def test_de_pas_splitst_een_lijst_met_meerdere_items():
    """De server levert ze gesplitst, maar de BROWSER doet dat niet: druk je Enter in een
    bolletje, dan zet hij er een tweede `<li>` bij in dezelfde `<ul>`. Zonder deze pas groeit een
    lijst vanzelf weer terug naar één blok met één greep."""
    pas = _normaliseer()
    assert 'querySelector("li")' in pas
    assert "items.length < 2" in pas, "er wordt niet op meerdere items gecontroleerd"
    assert "insertBefore(wrap" in pas, "de extra items krijgen geen eigen blok"


def test_de_pas_noemt_geen_bloktypes():
    """`test_javascript_draagt_geen_eigen_soorten_lijst` verbiedt een tweede lijst van soorten in
    JS. Een `<li>` is geen bloksoort maar het onderdeel waar dit over gaat; zijn ouder is per
    definitie de lijst."""
    pas = _normaliseer()
    for tag in ("ul", "ol"):
        assert f'"{tag}"' not in pas and f"'{tag}'" not in pas


def test_de_nummering_klopt_ook_tijdens_het_typen():
    """Zonder dit begint elke losse `<ol>` weer bij 1 en staat er "1. 1. 1." op het scherm tot je
    opslaat. De server rekent hem daarna opnieuw uit, maar wat je ziet moet ook kloppen."""
    pas = _normaliseer()
    assert 'getAttribute("start")' in pas and 'setAttribute("start"' in pas


def test_een_genest_lijstje_blijft_met_rust():
    """Een `<li>` in een `<li>` hoort bij zijn ouder-item; die uit elkaar trekken zou de nesting
    weggooien."""
    assert "lijst.parentNode !== blok" in _normaliseer()


# ── De vormgeving ────────────────────────────────────────────────────────────
def test_opeenvolgende_bolletjes_sluiten_aan():
    """Elk item heeft nu een eigen `<div>`, dus de onder- en bovenmarge kunnen niet meer
    samenvallen en tellen op. Gemeten: een lijst die eerst aaneengesloten was, viel uit elkaar in
    losse regels met dubbele witruimte."""
    assert ".wb[data-blok='ul'] + .wb[data-blok='ul'] .fbul{margin-top:0}" in CSS
    assert ".wb[data-blok='ol'] + .wb[data-blok='ol'] .fol{margin-top:0}" in CSS


def test_de_marge_rond_de_hele_lijst_blijft():
    """Alleen tussen twee items van dezelfde soort gaat hij eraf; vóór het eerste en ná het
    laatste grenst de lijst aan gewone tekst en hoort er ruimte te staan."""
    m = re.search(r"(?:^|[};])\s*\.fbul\{([^}]*)\}", CSS, re.M)
    assert m and "margin:.2rem 0 .2rem 1.1rem" in m.group(1)
