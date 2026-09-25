"""Een kaart op het projectenbord is aan te klikken (25 september 2026).

DE BUG, GEMETEN OP PROD VOORDAT IK IETS SCHREEF. Op `/projects` staan 159 kaarten en geen enkele
reageert op een klik. Geen navigatie, geen overlay, en niets in de console:

    kaarten: 159 · eersteTag: DIV · heeftEchteHref: false · heeftDataHref: true
    overlayOpDePagina: false · ovlOpenBestaat: "undefined" · cursor: "grab"

Dus geen overlay die de klik onderschept en geen JS-fout — er is simpelweg GEEN afhandelaar. Een
ingelogde kaart is bewust een `<div>` met `data-href` (hij moet sleepbaar zijn; een `<a>` met
`draggable` sleept de link), en de klik wordt bedraad door de modal-controller uit `_modal_html`.
`/node` en `/person` voegen die toe, `/projects` niet — en `/projects` is sinds fase 7 juist de
voordeur. De kaart was daar dus een dode div.

TWEE DEFECTEN, ÉÉN OORZAAK, en ze hangen aan elkaar. `render_projects_screen` roept
`_projects_tab_html` aan zonder te zeggen WAAR het bord staat, dus elke terugkeer-URL wees naar
`/node?id=…&tab=projects`. Dat is niet cosmetisch zodra de kaart wél opengaat: de overlay doet
`history.replaceState(…, back)` vóór hij de kaart pusht, dus sluiten (`history.back()`) zette je
niet terug op het bord maar op de cirkelpagina. "Een project openen" en "het weer sluiten" zijn
voor de mens één handeling; ze moeten allebei op het bord uitkomen.

Gemeten op prod: van de links in de hoofdkolom van `/projects` wezen er 8 naar `/node` en 0 naar
`/projects`, inclusief allebei de Group by-knoppen.
"""
from __future__ import annotations

import tempfile
import urllib.parse

from nooch_village import cockpit2
from nooch_village.views.projects import render_projects_screen, _projects_tab_html


def _dorp():
    dd = tempfile.mkdtemp()
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    home = cockpit2._home_node(st.records.all())
    rec = st.records.get(home)
    rol = [r.id for r in st.records.all() if getattr(r, "parent", None) == home][0]
    pid = st.projects.create(rol, "Een proefproject", "human")
    st.projects.start(pid)
    return st, rec, pid


def _bord(**kw) -> str:
    st, rec, _ = _dorp()
    return render_projects_screen(st, rec, csrf_token=kw.pop("csrf", "TOK"),
                                  username="b@t.nl", **kw)


# ── 1. De kaart is aan te klikken ────────────────────────────────────────────
def test_het_bord_toont_kaarten():
    """Zonder dit meet de rest van dit bestand niets."""
    assert _bord().count("class='card pcard") >= 1


def test_de_modal_controller_staat_op_het_scherm():
    """DE BUG ZELF. Een ingelogde kaart is een `<div data-href>` die door deze controller wordt
    bedraad. Zonder hem is er geen afhandelaar en gebeurt er bij een klik niets — geen navigatie,
    geen melding, niets om aan te zien dat er iets stuk is."""
    html = _bord()
    assert "ovl-x" in html, "de overlay ontbreekt"
    assert "openCard" in html, "er is niets dat een kaart opent"


def test_elke_kaart_wordt_ook_echt_bedraad():
    """De controller bedraadt op `.pcard[data-href]`. Rendert de kaart die selector niet, dan
    staat de controller er wel maar raakt hij niets."""
    html = _bord()
    assert "data-href" in html
    assert ".pcard[data-href]" in html


def test_zonder_csrf_blijft_de_kaart_een_echte_link():
    """BESTAAND GEDRAG DAT NIET MAG BREKEN. Publiek/alleen-lezen is er geen modal-JS, en dan
    navigeert de kaart zelf; `/project` stuurt een niet-ingelogde bezoeker naar `/login`."""
    html = _bord(csrf="")
    assert "pcard-link" in html
    assert "ovl-x" not in html, "zonder schrijf-sessie hoort er geen overlay te staan"


# ── 2. Openen en sluiten komen allebei op het bord uit ───────────────────────
def _paden(html: str, attribuut: str = "href") -> set[str]:
    import re
    uit = set()
    for m in re.finditer(rf"{attribuut}='([^']+)'", html):
        u = m.group(1)
        if u.startswith("/"):
            uit.add(u.split("?")[0])
    return uit


def test_de_kaart_keert_terug_naar_het_bord_en_niet_naar_de_cirkel():
    """De overlay zet de huidige history-entry op `back` vóór hij de kaart pusht, dus `back`
    bepaalt waar je uitkomt als je hem sluit. Wees hij naar `/node`, dan verdwijn je bij het
    sluiten van het bord af — een sprong die niemand vroeg."""
    import re
    html = _bord()
    hrefs = re.findall(r"data-href='([^']+)'", html)
    kaarten = [h for h in hrefs if h.startswith("/project?")]
    assert kaarten, "geen kaart om te meten"
    for h in kaarten:
        back = urllib.parse.parse_qs(urllib.parse.urlparse(h).query).get("back", [""])[0]
        assert back.startswith("/projects"), f"terug naar {back!r} in plaats van naar het bord"


def test_group_by_houdt_je_op_het_bord():
    """Klik je op `/projects` op "by person", dan hoor je op `/projects` te blijven. Tot nu toe
    wees die knop naar `/node` en stond je ineens op de cirkelpagina."""
    import re
    html = _bord()
    knoppen = re.findall(r"<a class='vbtn[^']*' href='([^']+)'", html)
    assert knoppen, "geen Group by-knoppen gevonden"
    for u in knoppen:
        assert u.startswith("/projects"), f"Group by wijst naar {u!r}"


def test_de_group_by_url_is_een_geldige_url():
    """`?` bij de eerste parameter, `&` bij de volgende. Een base zonder query kreeg hiervoor
    klakkeloos een `&` erachter geplakt — `/projects&group=rol` is geen filter maar een 404 op een
    pad dat niet bestaat."""
    import re
    for u in re.findall(r"<a class='vbtn[^']*' href='([^']+)'", _bord()):
        assert "&group=" not in u.split("?")[0], f"parameter vóór de ? in {u!r}"
        assert "?" in u, f"geen query-scheiding in {u!r}"


def test_de_gekozen_groepering_blijft_staan():
    """Een filter dat zichzelf vergeet is erger dan geen filter."""
    html = _bord(group="rol")
    assert "vbtn on" in html


# ── 3. Wat op de andere schermen stond blijft daar ───────────────────────────
def test_de_cirkel_tab_wijst_nog_steeds_naar_de_cirkel():
    """`/node?tab=projects` is de GEFILTERDE weergave van díe cirkel; daar hoort de terugweg naar
    de cirkel te gaan. Deze fix mag alleen het eigen scherm raken.

    EN DE URL MOET HEEL BLIJVEN. Hier stond alleen "`/node?id=` komt voor", en dat was te weinig:
    een mutatie die `_plus` altijd een `?` liet plakken maakte er `/node?id=…&tab=projects?group=rol`
    van en deze toets bleef groen. Precies één vraagteken is wat de helper doet — dus dat is wat er
    gemeten hoort te worden."""
    import re
    st, rec, _ = _dorp()
    html = _projects_tab_html(st, rec, "TOK")
    assert "/node?id=" in html
    assert "/projects?" not in html
    knoppen = re.findall(r"<a class='vbtn[^']*' href='([^']+)'", html)
    assert knoppen, "geen Group by-knoppen gevonden"
    for u in knoppen:
        assert u.count("?") == 1, f"kapotte URL: {u!r}"
        assert "group=" in u.split("?", 1)[1]


def test_in_een_overleg_wint_de_modal_route():
    """`nav` betekent "het bord draait IN een modal" en zet de links om naar js-modal. Dat is iets
    anders dan "waar sta ik", en het mag niet door de nieuwe parameter overstemd worden."""
    st, rec, _ = _dorp()
    html = _projects_tab_html(st, rec, "TOK", nav="/werkoverleg?id=x", terug="/projects")
    assert "js-modal" in html
    assert "/werkoverleg" in html
    assert "/projects?" not in html, "de modal-route werd overstemd"


def test_de_doel_pillen_wijzen_naar_het_bord_en_de_route_leest_ze():
    """Een pil die naar `/projects?goal=…` wijst terwijl de route `goal` niet leest, is erger dan
    een pil die je wegstuurt: dan lijkt het filter te werken en gebeurt er niets. De link en de
    route horen bij elkaar, dus ze staan in één toets."""
    import inspect
    import re
    st, rec, _ = _dorp()
    st.doelen.add("Q4: 1000 pairs", label="Q4", deadline="2026-12-31")
    html = render_projects_screen(st, rec, csrf_token="TOK", username="b@t.nl")
    pillen = re.findall(r"<a class='cl-filter pill[^']*' href='([^']+)'", html)
    assert pillen, "geen doel-pillen gevonden"
    for u in pillen:
        assert u.startswith("/projects"), f"doel-pil wijst naar {u!r}"

    from nooch_village import cockpit2 as c2
    # TOT DE VOLGENDE ROUTE, niet de eerste 800 tekens: die knip viel midden in het commentaar
    # boven de aanroep en liet de toets falen op iets dat er wél stond.
    blok = inspect.getsource(c2).split('if path == "/projects":')[1].split('if path == "/node"')[0]
    assert 'qs.get("goal")' in blok, "de route leest het doel-filter niet"


def test_het_scherm_hergebruikt_de_bestaande_modal_en_maakt_geen_tweede():
    """Zelfde regel als `test_het_bord_is_niet_gedupliceerd`: één controller, geen variant die na
    één wijziging uit de pas loopt."""
    import inspect
    from nooch_village.views.projects import render_projects_screen
    src = inspect.getsource(render_projects_screen)
    assert "_modal_html" in src
    assert "<script" not in src, "dit scherm schrijft eigen JS in plaats van de controller te delen"
