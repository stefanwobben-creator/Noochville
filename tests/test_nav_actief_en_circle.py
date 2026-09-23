"""Twee dingen aan de navigatie: het Circle-paneel wist niet welke cirkel, en niets wist welke pagina.

1. HET CIRCLE-PANEEL WAS EEN PLAT DUPLICAAT VAN ORGANIZATION. `_paneel_circle` kreeg een
   `ik`-parameter en deed er niets mee; hij liep over `[wortel] + alle niet-gearchiveerde cirkels`
   en zette van elk de leden onder elkaar. De docstring ("de cirkel waar je in zit") en de href
   van de knop (`/node?id=<operationele cirkel>`, gevuld door `_send` uit `_home_node`) beloofden
   allebei ÉÉN cirkel. Wat je kreeg was de hele boom, plat — precies wat Organization al doet.

   De fix haalt de cirkel uit dezelfde bron die de href al gebruikt. Niet uit een nieuwe regel:
   dan zou "welke cirkel is de mijne" op twee plekken worden beantwoord, en dat is het patroon
   dat bij de goal-kanaal-bug en bij de platslag-regel al twee keer misging.

2. ER WAS GEEN HUIDIGE-PAGINA-MARKERING. Geen `aria-current`, geen route-vergelijking in
   `nooch.js`, en in de CSS alleen `:hover` — die verdwijnt zodra je de muis wegbeweegt. Je zag
   dus nooit waar je was.

   HET PAD IS ALLEEN IN `_send` BEKEND: `_nav()` heeft geen stores en geen request, en vult de
   Circle-knop daarom ook al daar in. De markering hoort op diezelfde plek.

   TWEE SOORTEN "ACTIEF", en ze zijn met opzet niet hetzelfde attribuut:
     * `aria-current="page"` — dit ís de pagina waar je bent (server-side gezet);
     * `aria-current="true"` — dit paneel staat open (client-side gezet); het pad verandert niet,
       dus "page" zou een belofte zijn die niet klopt.
   De CSS selecteert op `[aria-current]` en ziet dus beide.
"""
from __future__ import annotations

import pathlib
import re

from nooch_village import cockpit2
from nooch_village.views.navpaneel import render_nav_paneel

REPO = pathlib.Path(__file__).resolve().parents[1]
CSS = (REPO / "nooch_village" / "static" / "nooch.css").read_text()
JS = (REPO / "nooch_village" / "static" / "nooch.js").read_text()

NOOCH = "mother_earth__nooch"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def _zonder_commentaar(js: str) -> str:
    js = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
    return re.sub(r"^\s*//[^\n]*", " ", js, flags=re.M)


# ── 1. HET CIRCLE-PANEEL BESTAAT NIET MEER ─────────────────────────────────────────────────
#
# De vijf toetsen die hier stonden bewaakten dat `_paneel_circle` ÉÉN cirkel toonde in plaats van
# de hele boom plat. Op 23 september 2026 is het paneel zelf vervallen: een cirkel is een rol die
# rollen bevat, dus wat hij toonde was altijd een deel van de organisatieboom. De fix van 22
# september was juist — hij maakte alleen zichtbaar dat het ding erboven overbodig was.
#
# Het besluit, de meting en de toetsen die bewaken dat er niets zoekraakte:
# `tests/test_organisatie_is_de_enige_boom.py`.


# ── 2. De huidige-pagina-markering ──────────────────────────────────────────────────────────
def _nav_van(dd, pad: str) -> str:
    """De zijbalk zoals `_send` hem uitlevert voor dit pad."""
    from nooch_village.cockpit2_util import _nav
    body = f"<html><body>{_nav()}</body></html>"
    return cockpit2._nav_actief(pad, cockpit2._nav_chrome(cockpit2._Stores(dd), body))


def _actief(html: str) -> list[str]:
    """De labels van de items die als huidig gemarkeerd staan."""
    nav = html.split("<nav class='c2-subnav'>", 1)[1].split("</nav>", 1)[0]
    return re.findall(r"aria-current='page'[^>]*>.*?<span class='c2-lbl'>([^<]+)</span>",
                      nav, re.S)


def test_elk_item_markeert_zijn_eigen_pagina(tmp_path):
    """De vier items die een ECHT scherm hebben. `/node` staat er niet bij, en dat is geen
    vergeten regel: zie `test_de_terugval_van_organization_leidt_naar_een_dode_pagina`."""
    dd = _dd(tmp_path)
    for pad, label in (("/projects", "Projects"), ("/messages", "Messages"),
                       ("/wiki", "Wiki"), ("/admin", "Admin")):
        assert _actief(_nav_van(dd, pad)) == [label], pad


def test_de_terugval_van_organization_leidt_naar_een_dode_pagina(tmp_path):
    """GEVONDEN BIJ HET METEN, niet gezocht. Organization is een PANEEL-knop: met JavaScript
    opent hij het paneel en navigeert hij nooit. Zijn `href` is de terugval voor wie geen JS
    heeft — en die wijst naar `/node` zónder id, en dat rendert "Node not found", zonder zijbalk.

    Deze test legt de huidige stand vast in plaats van hem stil te repareren: de knop werkt zoals
    bedoeld zolang JS aanstaat, en de terugval is kapot. Dat vraagt een eigen besluit (welke node
    is "de organisatie"?), niet een regel die ik er hier bij verzin."""
    dd = _dd(tmp_path)
    from nooch_village.views.overview import render_node
    html = render_node(cockpit2._Stores(dd), "", "overview", csrf_token="t", username="guest")
    assert "Node not found" in html
    assert "c2-subnav" not in html, "als deze pagina wél een balk krijgt, hoort Organization erop"


def test_elke_node_markeert_organization(tmp_path):
    """DIT WAREN TWEE TOETSEN: de eigen cirkel markeerde Circle, elke andere node Organization,
    en de "meest specifieke treffer wint"-regel besliste tussen die twee. Sinds Circle op 23
    september 2026 verviel is er nog één `/node`-item, en markeert élke node Organization.

    De regel zelf blijft bewaakt door `test_de_meest_specifieke_treffer_wint_ook_als_hij_later_staat`,
    die hem op een synthetische nav meet en dus niet afhangt van welke items er toevallig zijn."""
    dd = _dd(tmp_path)
    assert _actief(_nav_van(dd, f"/node?id={NOOCH}")) == ["Organization"]
    assert _actief(_nav_van(dd, "/node?id=mother_earth")) == ["Organization"]


def test_een_scherm_zonder_nav_item_markeert_niets(tmp_path):
    """MUTATIE-CONTROLE: "markeer altijd iets" zou op de tests hierboven ook slagen."""
    dd = _dd(tmp_path)
    for pad in ("/vangst", "/werkoverleg", "/pagina"):
        assert _actief(_nav_van(dd, pad)) == [], pad


def test_de_querystring_van_een_ander_item_telt_niet_mee(tmp_path):
    """`/messages?k=…` is nog steeds Messages; een item zonder query mag niet kieskeurig worden."""
    dd = _dd(tmp_path)
    assert _actief(_nav_van(dd, "/messages?k=circle:mother_earth")) == ["Messages"]


# ── 3. Tweede drager, en het paneel ─────────────────────────────────────────────────────────
def test_de_actieve_staat_draagt_meer_dan_kleur():
    """Dezelfde regel die al voor de overleg-knoppen geldt: kleur alleen is onzichtbaar in
    zwart-wit en voor wie hem niet ziet."""
    kaal = re.sub(r"/\*.*?\*/", " ", CSS, flags=re.S)
    per = {s.strip(): b for s, b in re.findall(r"([^{}]+)\{([^{}]*)\}", kaal)}
    regel = per.get(".c2-subnav [aria-current]", "")
    assert regel, "geen stijlregel voor de actieve nav-knop"
    assert "border-left" in regel, "geen vorm-drager naast de kleur"
    assert "font-weight" in regel, "geen gewicht-drager naast de kleur"


def test_de_markering_schuift_de_tekst_niet_op():
    """Een rand erbij zonder de padding te corrigeren laat élk label een paar pixels verspringen
    zodra je van pagina wisselt."""
    kaal = re.sub(r"/\*.*?\*/", " ", CSS, flags=re.S)
    per = {s.strip(): b for s, b in re.findall(r"([^{}]+)\{([^{}]*)\}", kaal)}
    assert "padding-left" in per.get(".c2-subnav [aria-current]", "")


def test_een_open_paneel_markeert_zijn_eigen_knop():
    """Het pad verandert niet als je een paneel opent, dus de server kan dit niet weten."""
    kaal = _zonder_commentaar(JS)
    m = re.search(r"function navPaneel\(root\) \{(.*?)\n  \}\n", kaal, re.S)
    assert m, "navPaneel niet gevonden"
    assert "aria-current" in m.group(1)


def test_een_open_paneel_belooft_niet_dat_het_de_pagina_is():
    """`aria-current="page"` zegt "dit is de pagina waar je bent". Een open paneel is dat niet;
    `true` zegt "dit is het huidige item in de set", en dat klopt wél.

    DE EERSTE VERSIE VERBOOD HET WOORD "page" IN DE HELE FUNCTIE, en dat was te grof: de JS
    moet `page` wél kunnen herstellen op de knop die de SERVER zo markeerde. Wat niet mag is
    `page` zetten op een knop die alleen maar een paneel openzet — en dat is precies de regel
    hieronder."""
    kaal = _zonder_commentaar(JS)
    m = re.search(r"function markeer\(actief\) \{(.*?)\n    \}", kaal, re.S)
    assert m, "markeer() niet gevonden"
    assert 'pagina ? "page" : "true"' in m.group(1), \
        "een open paneel dat niet de huidige pagina is, hoort `true` te krijgen en geen `page`"


def test_de_stijl_pakt_allebei_de_soorten():
    """De CSS selecteert op `[aria-current]` zonder waarde, dus zowel `page` als `true`."""
    kaal = re.sub(r"/\*.*?\*/", " ", CSS, flags=re.S)
    assert ".c2-subnav [aria-current]" in kaal
    assert "[aria-current=" not in kaal, "de stijl is aan één waarde vastgeklonken"


def test_de_meest_specifieke_treffer_wint_ook_als_hij_later_staat():
    """DEZE TEST BESTAAT OMDAT EEN MUTATIE NIETS BEWEES. "Meest specifieke wint" vervangen door
    "eerste treffer wint" liet alles groen — want in de echte balk staat Circle toevallig vóór
    Organization, dus de eerste treffer IS de juiste. De regel werd dus niet getoetst, de
    volgorde van de markup.

    Hier staat de generieke `/node` eerst. Wint die, dan is de regel weg."""
    nav = ("<x><nav class='c2-subnav'>"
           "<a href='/node'><span class='c2-lbl'>Organization</span></a>"
           "<a href='/node?id=abc'><span class='c2-lbl'>Circle</span></a>"
           "</nav></x>")
    assert _actief(cockpit2._nav_actief("/node?id=abc", nav)) == ["Circle"]
    assert _actief(cockpit2._nav_actief("/node", nav)) == ["Organization"]


def test_de_overlegknoppen_krijgen_geen_pagina_markering(tmp_path):
    """ZE STAAN WÉL IN DE SUBNAV, maar ze zijn een ander soort ding: ze dragen al een eigen
    live-staat met eigen kleuren. Een markering eroverheen zou die overschrijven — precies de
    regressie die `test_de_live_knop_wint_van_de_nav_regel` sinds 21 september bewaakt, toen de
    knop live kleurloos bleek."""
    dd = _dd(tmp_path)
    html = _nav_van(dd, f"/werkoverleg?circle={NOOCH}")
    nav = html.split("<nav class='c2-subnav'>", 1)[1].split("</nav>", 1)[0]
    assert "c2-overleg" in nav, "geen overleg-knop in de balk — dan meet deze test niets"
    assert "aria-current" not in nav


def test_de_stijlregel_verliest_bewust_van_de_overlegknop():
    """Dezelfde eis, een laag lager. `.c2-subnav [aria-current]` is (0,2,0) en `.c2-subnav
    a.c2-overleg` (0,2,1); met een `a` erbij stonden ze gelijk en besliste de volgorde in het
    bestand. Een toeval is geen regel."""
    def spec(sel):
        return (sel.count("#"), sel.count(".") + sel.count("["), len(re.findall(r"(?<![.\[#\w-])[a-z]+", sel)))
    assert spec(".c2-subnav [aria-current]") < spec(".c2-subnav a.c2-overleg")
