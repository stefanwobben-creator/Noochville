"""De navigatiebalk als accordeon (21 september 2026).

WAT ER VERANDERT. PR, ME en CI waren paginasprongen: je verliet het scherm waar je mee bezig was
om een lijst te zien, koos iets, en kwam ergens anders uit. Nu klapt die lijst open NAAST de balk.
WI en AD blijven een sprong — daar kies je niets uit een lijst. Erbij: een ZOEK-knop bovenaan, en
onderaan twee directe knoppen naar Werkoverleg en Roloverleg.

VIJF DINGEN MOETEN HARD ZIJN:

  1. de balk blijft VERTICAAL op elke schermbreedte (expliciet besluit, tegen de standaardreflex in);
  2. Werkoverleg en Roloverleg zijn geen kanaal en geen paneel maar een directe knop;
  3. het paneel rendert bestaande data — geen tweede lijst naast die van Messages of Projects;
  4. het paneel komt pas als je klikt, niet met elke pageload;
  5. zonder JS blijft elke knop een werkende link.
"""
from __future__ import annotations

import pathlib
import re

from nooch_village import channels, cockpit2
from nooch_village.cockpit2_util import _nav
from nooch_village.views.navpaneel import PANELEN, render_nav_paneel

CSS = (pathlib.Path(__file__).resolve().parents[1]
       / "nooch_village" / "static" / "nooch.css").read_text()
JS = (pathlib.Path(__file__).resolve().parents[1]
      / "nooch_village" / "static" / "nooch.js").read_text()

OWNER = "mother_earth__nooch__creator_of_shoes"


def _nav_ingevuld(cid: str = "mother_earth__nooch") -> str:
    """De balk zoals een PAGINA hem toont, niet zoals `_nav()` hem teruggeeft.

    `_nav()` heeft geen stores en laat twee plekken open als placeholder: de Circle-knop en de
    twee overleg-knoppen, want die dragen allebei een cirkel-id. `_send` vult ze in. Een test die
    alleen `_nav()` leest, kijkt dus langs precies het deel dat op 21 september stukging."""
    from nooch_village.cockpit2_util import _SIDE_CIRCLE, _SIDE_OVERLEG, _side_item, overleg_items
    h = _nav()
    h = h.replace(_SIDE_CIRCLE, _side_item(f"/node?id={cid}", "Circle", "ci"), 1)
    return h.replace(_SIDE_OVERLEG, overleg_items(cid), 1)


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    mens = st.people.add("Paneel Tester", "paneel@test.nl")
    st.assign.assign(OWNER, "person", mens.id)
    for i in range(3):
        pid = st.projects.create(OWNER, f"Project {i} mycelium", "human", status="running")
        st.projects.add_feed_entry(pid, f"bericht {i}", kind="comment",
                                   author_type="human", author_id=mens.id)
    st.doelen.add("De nieuwe website live", label="Website")
    return dd, cockpit2._Stores(dd), mens.id


# ── 1. De balk ───────────────────────────────────────────────────────────────
def test_de_balk_klapt_nooit_om_naar_horizontaal():
    """DE STANDAARDREFLEX IS HIER DE VERKEERDE, en hij stond er: onder 760px kreeg `.c2-side`
    `flex-direction:row` en werd de zijbalk een rij boven de inhoud. Dat maakt van één
    navigatiemodel twee — precies wat fase 7 opruimde — en de accordeon heeft een verticale balk
    nodig om een paneel naast te kunnen zetten. Smal betekent: de balk krimpt, het paneel gaat
    eronder."""
    smal = CSS.split("@media(max-width:760px)")
    assert len(smal) > 1
    blok = "".join(smal[1:])
    zijbalk = [r for r in re.findall(r"([^{}]*)\{([^{}]*)\}", blok) if ".c2-side{" in r[0] + "{"]
    assert zijbalk, "geen smalle-schermregel voor de zijbalk gevonden"
    for _sel, body in zijbalk:
        assert "flex-direction:row" not in body.replace(" ", ""), "de balk klapt om naar horizontaal"


def test_de_knoppen_die_een_paneel_openen_en_die_dat_niet_doen():
    h = _nav_ingevuld()
    for sleutel in ("pr", "ci", "org"):
        assert f"data-nav-paneel='{sleutel}'" in h, sleutel
    # WI, AD én ME springen gewoon naar hun pagina: daar kies je niets uit een lijst, en een
    # tussenlijst is dan een extra klik zonder winst. Messages kwam er op 21 september bij — zie
    # `test_messages_is_geen_paneel_want_het_scherm_is_al_lijst_plus_detail`.
    me = h.split("/messages")[1][:120]
    assert "data-nav-paneel" not in me
    wi = h.split("/wiki")[1][:120]
    assert "data-nav-paneel" not in wi
    ad = h.split("/admin")[1][:120]
    assert "data-nav-paneel" not in ad
    assert "Inbox" not in h                       # verwijderd in #531, komt niet terug


def test_elke_paneelknop_blijft_zonder_js_een_werkende_link():
    """Zonder deze regel is de balk bij een JS-fout een rij dode elementen. De knop draagt zijn
    href, en `preventDefault` gebeurt pas als het paneel echt opengaat."""
    h = _nav_ingevuld()
    for sleutel, href in (("pr", "/projects"),
                          ("ci", "/node?id=mother_earth__nooch"), ("org", "/node")):
        stuk = h.split(f"data-nav-paneel='{sleutel}'")[0][-160:]
        assert f"href='{href}'" in stuk, f"{sleutel} heeft geen val-terug-link"
    assert "e.preventDefault()" in JS


def test_de_twee_overleggen_zijn_geen_kanaal_en_geen_paneel():
    """CORRECTIE OP HET PROTOTYPE (Stefan, 21 september 2026): Werkoverleg en Roloverleg stonden
    daar eerst als kanaal. Het zijn twee bestaande schermen; één klik, geen lijst ervoor."""
    h = _nav_ingevuld()
    for href in ("/werkoverleg", "/roloverleg2"):
        assert f"class='c2-overleg' href='{href}?circle=" in h
        # OP HET ELEMENT ZELF, niet op de 160 tekens erna. Sinds de overleg-pillen bovenaan
        # staan (22 september 2026) volgt Projects er direct op, en díe draagt wél een paneel —
        # dan meet je de buurman in plaats van de knop.
        el = re.search(rf"<a class='c2-overleg[^>]*href='{re.escape(href)}[^>]*>", h)
        assert el, href
        assert "data-nav-paneel" not in el.group(0), el.group(0)
    # EN ZE STAAN LOS VAN DE PR/ME/WI/CI/AD-GROEP, met een eigen scheiding — alleen staat die
    # scheiding sinds 22 september ERACHTER in plaats van ervoor: de pillen verhuisden naar
    # boven, want dat is de snelste ingang naar een overleg dat NU loopt. De bewering is
    # dezelfde (ze horen niet in dezelfde rij), de volgorde is omgedraaid.
    assert h.index("c2-overleg") < h.index("c2-subnav-div")


# ── 2. Eén paneel tegelijk, en dicht met dezelfde knop ───────────────────────
def test_het_paneel_gedraagt_zich_als_een_accordeon():
    assert 'if (open === sleutel) { sluit(); return; }' in JS      # nogmaals = sluiten
    assert 'k === knop ? "true" : "false"' in JS                   # precies één aria-expanded
    assert '"Escape"' in JS                                        # en met het toetsenbord dicht


def test_het_paneel_staat_leeg_in_de_pagina():
    """LAZY, en dat is de hele reden dat het een route is. Zou de inhoud meekomen met elke
    pageload, dan betaalt élk scherm voor een projectlijst (442) en een kanalenlijst (123) die je
    meestal niet opent."""
    h = _nav()
    leeg = h.split("id='c2-paneel-in'")[1].split("</aside>")[0]
    assert leeg.strip() in (">", "></div>"), f"het paneel draagt al inhoud: {leeg[:80]!r}"
    assert "/nav-paneel?p=" in JS


# ── 3. Wat de panelen tonen is bestaande data ────────────────────────────────
def test_messages_is_geen_paneel_want_het_scherm_is_al_lijst_plus_detail(tmp_path):
    """HET WAS EEN PANEEL, EN DAT LEVERDE EEN HALVE MESSAGES OP. Je klikte ME vanaf een ander
    scherm, kreeg de kanalenlijst naast de balk — en het gesprek was nergens, want je stond nog op
    je vorige pagina, die er gewoon naast bleef staan. Klikken op een kanaal bracht je alsnog op
    `/messages`, maar de tussenstand las als kapot.

    De diepere reden: Messages is als ENIGE van de vijf een scherm dat zelf al uit lijst + detail
    bestaat. Een paneel kan daar alleen de lijst van tonen, en die lijst is een kopie van wat de
    pagina zelf al heeft. Bij Projects, Circle en Organization voegt het paneel iets toe dat de
    pagina niet heeft; hier haalde het iets weg (eis Stefan, 21 september 2026)."""
    dd, st, ik = _dorp(tmp_path)
    assert "me" not in PANELEN
    assert render_nav_paneel(st, "me", ik) == ""          # fail-closed, geen half scherm
    h = _nav_ingevuld()
    me = h.split("/messages")[1][:120]
    assert "data-nav-paneel" not in me, "Messages opent nog een paneel"
    # en de lijst bestaat gewoon nog, één klik verder, in zijn volledige vorm
    from nooch_village.views.messages import render_messages
    assert "msg-lijst" in render_messages(st, ik=ik, csrf_token="t")


def test_het_projects_paneel_opent_op_mijn_projecten(tmp_path):
    """Standaard "mijn projecten", met dezelfde definitie als de persoon-lens: een project is van
    jou als zijn eigenaar-rol door jou wordt vervuld. Een tweede definitie zou hier stilletjes een
    andere lijst geven dan op je eigen pagina."""
    dd, st, ik = _dorp(tmp_path)
    mijn = render_nav_paneel(st, "pr", ik)
    assert "My projects" in mijn and mijn.count("c2-prij") == 3
    # een mens zonder rollen ziet bij "mijn" niets, en bij "alle" alles
    vreemd = st.people.add("Zonder Rol", "zonder@test.nl")
    assert render_nav_paneel(st, "pr", vreemd.id).count("c2-prij") == 0
    assert render_nav_paneel(st, "pr", vreemd.id, welke="alle").count("c2-prij") == 3


def test_het_circle_paneel_meldt_een_rol_zonder_vervuller(tmp_path):
    """"open — nobody" is informatie. Een lege regel laat het lezen als een weergavefout."""
    dd, st, ik = _dorp(tmp_path)
    h = render_nav_paneel(st, "ci", ik)
    assert "c2-prij" in h and "open — nobody" in h
    assert "Paneel Tester" in h                    # en wie wél vervult staat erbij


def test_een_onbekend_paneel_geeft_niets(tmp_path):
    """Fail-closed: geen gok, geen foutpagina in een fragment dat in een open scherm wordt gezet."""
    dd, st, ik = _dorp(tmp_path)
    assert render_nav_paneel(st, "bestaat-niet", ik) == ""
    assert render_nav_paneel(st, "", ik) == ""


# ── 4. Zoeken in het paneel ──────────────────────────────────────────────────
def test_het_zoekveld_is_de_enige_ingang(tmp_path):
    """DIT HEETTE `test_het_zoekpaneel_gebruikt_de_bestaande_zoekmachine`, en het paneel is er op
    22 september 2026 uit (eis Stefan).

    Er waren TWEE zoek-ingangen in de balk: het altijd zichtbare `c2-search`-veld (met de
    `/`-sneltoets en een typeahead-dropdown) en een "Search"-knop die een paneel opende — allebei
    naar dezelfde `/search`-inhoud. De knop had zijn reden toen hij gebouwd werd: in de rail-stand
    was het veld verborgen, dus op /messages was er geen zoek. Die rail verviel op 21 september
    (#544) en daarmee de reden voor de knop, zonder dat iemand hem weghaalde.

    Wat deze test nu bewaakt: het veld is er, het draagt de sneltoets en de typeahead, en het
    paneel is fail-closed leeg."""
    dd, st, ik = _dorp(tmp_path)
    h = _nav_ingevuld()
    assert "id='gs-input'" in h and "id='gs-drop'" in h      # veld + typeahead
    assert "action='/search'" in h or 'action="/search"' in h
    assert "c2-kbd" in h                                      # de `/`-sneltoets staat erbij
    assert ">Search<" not in h, "de dubbele ingang staat er nog"
    assert "zoek" not in PANELEN
    assert render_nav_paneel(st, "zoek", ik) == ""            # fail-closed


def test_de_zoekmachine_zelf_is_onaangeroerd(tmp_path):
    """DE TWEE GATEN DIE BIJ DE KNOP WERDEN GEDICHT ZITTEN IN DE ZOEKMACHINE, niet in het paneel:
    de groep `Channels` (kanalen op naam) en de goal- en topic-trails in `Messages`. Die zijn met
    de knop niet meegegaan — ze werken via het veld, want dat gaat naar dezelfde `_zoek`."""
    from nooch_village.views.search import _GROEPEN, render_search_fragment
    dd, st, ik = _dorp(tmp_path)
    assert "Channels" in [label for label, _fn in _GROEPEN]
    h = render_search_fragment(st, "mycelium")
    assert "gs-group" in h and "Projects" in h


def test_zoeken_vindt_een_kanaal_op_zijn_naam(tmp_path):
    """HET GAT DAT DICHTGING. `_gesprekken` zocht in de TEKST van berichten: zoek je op "Website",
    dan vond je berichten waarin dat woord viel, maar niet het Website-kanaal zelf — en dat is
    meestal precies wat je zocht. Doel- en losse kanalen vielen er helemaal buiten."""
    from nooch_village.views.search import _zoek
    dd, st, ik = _dorp(tmp_path)
    res = dict(_zoek(st, ["website"])[0])
    assert [h["titel"] for h in res["Channels"]] == ["Website"]
    assert res["Channels"][0]["url"].startswith("/messages?k=goal:")


def test_een_dm_blijft_buiten_de_zoek(tmp_path):
    """Een privégesprek doorzoekbaar maken voor iedereen die is ingelogd is geen zoekfunctie maar
    een lek. Dat gold al voor de berichten; het geldt net zo voor de NAAM van het gesprek."""
    from nooch_village.views.search import _zoek
    dd, st, ik = _dorp(tmp_path)
    ander = st.people.add("Geheime Vriend", "geheim@test.nl")
    st.channels.post(channels.dm_kanaal(ik, ander.id), "iets vertrouwelijks", author_id=ik)
    st2 = cockpit2._Stores(dd)
    for term in ("geheime", "vertrouwelijks"):
        res = dict(_zoek(st2, [term])[0])
        assert res["Channels"] == [] and res["Messages"] == [], term


# ── 5. Elke knop in de balk gaat ergens heen dat bestaat ─────────────────────
#
# DE LES VAN 21 SEPTEMBER, 's MIDDAGS. De twee overleg-knoppen linkten kaal naar `/werkoverleg` en
# `/roloverleg2`. Beide routes bestaan — maar ze zijn niet dorpsbreed: ze tonen HET OVERLEG VAN EEN
# CIRKEL en beginnen met `st.records.get(circle_id)`. Zonder `?circle=` is dat None, en kreeg je
# "No circle." en "Unknown.". Eén gedeelde oorzaak, geen twee ontbrekende routes.
#
# Het gat zat niet in de code maar in de dekking: er was geen enkele test die een link uit de balk
# ook echt OPVROEG. Dat is wat hieronder gebeurt.

def test_de_overleg_knoppen_dragen_de_cirkel_waar_ze_over_gaan():
    from nooch_village.cockpit2_util import overleg_items
    h = overleg_items("mother_earth__nooch")
    assert "/werkoverleg?circle=mother_earth__nooch" in h
    assert "/roloverleg2?circle=mother_earth__nooch" in h


def test_zonder_cirkel_staat_er_geen_knop():
    """Fail-closed: een knop naar een overleg dat niet bestaat is erger dan geen knop. Precies wat
    er misging — er stónd een knop, hij deed alleen niets."""
    from nooch_village.cockpit2_util import overleg_items
    assert overleg_items("") == ""


def test_de_overleg_links_leveren_een_echt_scherm_op(tmp_path):
    """DE TEST DIE ER NIET WAS. Hij volgt de link uit de balk tot in de renderer en controleert dat
    daar geen "not found" uitkomt. Een assertie op de HTML van de balk alleen had dit nooit
    gevangen: de href zag er prima uit."""
    from nooch_village.cockpit2 import _home_node
    from nooch_village.cockpit2_util import overleg_items
    from nooch_village.views.werkoverleg import render_werkoverleg
    from nooch_village.views.roloverleg import render_roloverleg2
    dd, st, ik = _dorp(tmp_path)
    cid = _home_node(st.records.all())
    assert cid, "geen cirkel gevonden om naartoe te linken"
    assert f"circle={cid}" in overleg_items(cid)
    for render in (render_werkoverleg, render_roloverleg2):
        uit = render(st, cid, csrf_token="t")
        assert "Not found" not in uit and "No circle" not in uit and "Unknown" not in uit, (
            f"{render.__name__} geeft een niet-gevonden-pagina voor circle={cid}")


def test_de_balk_draagt_circle_precies_een_keer():
    """Er stonden er TWEE: een statische `/node` naast de placeholder die `_send` invult. In de
    rail waren dat twee knoppen "CI" onder elkaar, die naar verschillende plekken gingen."""
    from nooch_village.cockpit2_util import _SIDE_CIRCLE
    h = _nav()
    assert h.count(">Circle<") == 0, "Circle staat hardgecodeerd in de balk"
    assert h.count(_SIDE_CIRCLE) == 1, "de cirkel-placeholder hoort er precies één keer te staan"
    # `href='/node'` MAG WEER, maar precies één keer en alleen als val-terug van Organization.
    # De oorspronkelijke fout was een tweede CIRCLE-knop; dit is een ander item met een ander
    # paneel, dat zonder JS naar de organisatie navigeert.
    assert h.count("href='/node'") == 1
    stuk = h.split("href='/node'")[1][:80]
    assert "data-nav-paneel='org'" in stuk


# ── 6. Het paneel moet ook echt náást de inhoud staan ────────────────────────
#
# GEVONDEN IN DE DOORLOOP, met de meting erbij: het paneel liep tot x=764 terwijl de inhoud al op
# x=580 begon — 184px overlap. Twee dingen tegelijk, met één oorzaak.

def _decls(css: str, selector: str, *, moet: str = "") -> dict:
    """De declaraties van de EERSTE regel op `selector` die `moet` zet.

    Dat filter is nodig: `.c2-paneel` heeft twee regels — de brede-schermvorm (`position:fixed`,
    `left`, `width`) en de smalle (`position:static`, `width:auto`). Zonder `moet` pak je er
    willekeurig een, en dan meet de toets de verkeerde."""
    zonder = re.sub(r"/\*.*?\*/", " ", css, flags=re.S)
    for sel, body in re.findall(r"([^{}]*)\{([^{}]*)\}", zonder):
        if selector in sel and (not moet or moet in body):
            return {k.strip(): v.strip() for k, v in
                    (d.split(":", 1) for d in body.split(";") if ":" in d)}
    return {}


def test_geen_enkele_css_variabele_is_ongedefinieerd():
    """`--card` werd zes keer gebruikt en was nergens gedefinieerd. Een browser geeft dan een lege
    string terug, dus `background:var(--card)` is géén achtergrond — de zijbalk én het paneel
    waren doorzichtig. Geen foutmelding, want een ontbrekende variabele is geldige CSS."""
    from nooch_village.web_base import _CSS
    nu = (pathlib.Path(__file__).resolve().parents[1]
          / "nooch_village" / "static" / "nooch-ui.css").read_text()
    bekend = set(re.findall(r"(--[a-z0-9-]+)\s*:", _CSS + nu))
    for naam, css in (("nooch.css", CSS), ("nooch-ui.css", nu)):
        gebruikt = set(re.findall(r"var\((--[a-z0-9-]+)\)", css))
        assert not (gebruikt - bekend), f"{naam} gebruikt ongedefinieerd: {gebruikt - bekend}"


def test_het_paneel_schuift_niet_mee_met_de_sibling_marge():
    """DE OORZAAK, en hij zat niet in de breedte. Het paneel is een SIBLING van de zijbalk, dus
    `.c2-side ~ *{margin-left}` trof hem ook — en `margin-left` SCHUIFT een `position:fixed`
    element. Daardoor stond hij 232px verder naar rechts dan zijn eigen `left` zegt."""
    zonder = re.sub(r"/\*.*?\*/", " ", CSS, flags=re.S)
    sibling = [sel.strip() for sel, body in re.findall(r"([^{}]*)\{([^{}]*)\}", zonder)
               if ".c2-side ~" in sel and "margin-left" in body]
    assert sibling, "de sibling-marge is verdwenen; deze toets meet dan niets"
    for sel in sibling:
        assert ":not(.c2-paneel)" in sel, (
            f"{sel} schuift het paneel mee; het overlapt dan de inhoud")


def test_het_paneel_eindigt_vóór_de_inhoud_begint():
    """DE REKENSOM, niet de selector. Links + breedte van het paneel moet passen binnen de marge
    die de inhoud opschuift — anders staat het paneel er nog steeds overheen, hoe de regel ook
    geschreven is."""
    paneel = _decls(CSS, ".c2-paneel", moet="position:fixed")
    assert paneel, "de paneelregel is niet te vinden"
    links = int(re.sub(r"\D", "", paneel["left"]))
    breed = int(re.sub(r"\D", "", paneel["width"]))
    duw = _decls(CSS, "body.navpaneel-open .c2-side ~ *", moet="margin-left:548")
    marge = int(re.sub(r"\D", "", duw["margin-left"]))
    assert links + breed <= marge, (
        f"paneel loopt tot {links + breed}px, de inhoud begint op {marge}px — "
        f"{links + breed - marge}px overlap")


# ── 7. Zoeken zegt niet twee keer hetzelfde ──────────────────────────────────
def test_het_zoekveld_draagt_nog_steeds_een_label(tmp_path):
    """DEZE TEST GING OVER EEN DUBBELING BINNEN HET PANEEL ("SEARCH" als titel, "SEARCH EVERYTHING"
    eronder). Het paneel is weg, en daarmee die dubbeling — maar de onderliggende eis niet: een
    zoekveld zonder label is voor een schermlezer een naamloos invoerveld. Het veld in de balk
    heeft er een, en die mag niet stilletjes sneuvelen bij een volgende opruiming."""
    h = _nav_ingevuld()
    veld = h.split("id='gs-input'")[1][:200]
    assert "aria-label='global search'" in veld or "aria-label=\"global search\"" in veld


# ── 8. De organisatieboom is een paneel geworden ─────────────────────────────
def test_de_organisatieboom_is_een_paneel_geworden(tmp_path):
    """Hij hing als los `<details class='c2-orgfly'>` ONDER de balk: een tweede uitklap-mechanisme
    naast de panelen, op een plek waar je hem alleen vond door naar beneden te scrollen."""
    dd, st, ik = _dorp(tmp_path)
    h = _nav()
    assert "c2-orgfly" not in h, "het losse uitklapje staat er nog"
    assert "data-nav-paneel='org'" in h
    paneel = render_nav_paneel(st, "org", ik)
    assert "c2-org" in paneel and "Organization" in paneel


def test_de_boom_komt_uit_dezelfde_functie_als_hiervoor(tmp_path):
    """DEZELFDE BOOM, NIET EEN TWEEDE. Een eigen boomweergave zou betekenen dat "waar zit deze
    rol" twee antwoorden heeft zodra er aan één iets verandert."""
    from nooch_village.views.overview import _tree_html
    dd, st, ik = _dorp(tmp_path)
    paneel = render_nav_paneel(st, "org", ik)
    direct = _tree_html(st, "")
    assert direct and direct in paneel


def test_de_boom_klapt_open_waar_je_staat(tmp_path):
    """Wat de oude injectie extra deed mag niet verdwijnen. `hier` komt nu van de client, want
    een fragment weet niet op welke pagina het landt."""
    dd, st, ik = _dorp(tmp_path)
    rol = "mother_earth__nooch__creator_of_shoes"
    met = render_nav_paneel(st, "org", ik, hier=rol)
    zonder = render_nav_paneel(st, "org", ik)
    assert met != zonder, "de boom reageert niet op waar je staat"
    assert "data-nav-paneel" not in met                    # het paneel is inhoud, geen knoppen
