"""De uitklappanelen van de navigatiebalk (`/nav-paneel`, 21 september 2026).

WAT DIT VERVANGT. PR, ME en CI waren paginasprongen: je verliet het scherm waar je mee bezig was om
een lijst te zien, koos iets, en kwam ergens anders uit. Nu klapt die lijst open NAAST de balk en
blijft de inhoud rechts staan. WI, IN en AD blijven een sprong — daar kies je niets uit een lijst.

DRIE DINGEN DIE DIT BEWUST NIET IS:

1. GEEN NIEUWE DATA. Elk paneel rendert wat elders al bestaat: de kanalenlijst is `messages._kanalen`,
   de projectlijst is dezelfde "mijn projecten"-definitie als de persoon-lens (`owner ∈ roles_of`),
   de rollen zijn `org`-leden, en zoeken is `search.render_search_fragment`. Een tweede bron zou
   betekenen dat "wat staat er in mijn lijst" op twee plekken wordt beantwoord.

2. GEEN RENDER OP ELKE PAGINA. Het paneel wordt pas opgehaald als je erop klikt (fragment-route,
   zoals de zoek-dropdown al deed). Zou hij meekomen met elke pageload, dan betaalt elk scherm in
   het dorp voor een projectlijst en een kanalenlijst die je meestal niet opent — en dat is 123
   kanalen en 442 projecten per keer.

3. GEEN EIGEN VORMGEVING. `.row`, `.grouplabel` en `.seg` uit het prototype zijn hier `.c2-prij`,
   `.c2-pgroep` en `.cl-filter` — de bestaande atomen, niet een nieuwe familie.
"""
from __future__ import annotations

import logging
import urllib.parse

from nooch_village import channels
from nooch_village.web_base import _e

log = logging.getLogger("village.navpaneel")

#: De panelen die bestaan. Alles daarbuiten geeft een lege string (fail-closed, geen gok).
PANELEN = ("ci", "org")


def _rij(href: str, tekst: str, *, sub: str = "", tag: str = "") -> str:
    # HET DOEL-ETIKET IS EEN `chip`, GEEN EIGEN KLASSE. De eerste versie had er een: een groene
    # tint zonder tweede drager, en de kleur-alleen-guard ving hem meteen. Terecht — maar de
    # oplossing was niet er een randje bij verzinnen, want dit ís een chip zoals overal elders
    # (het bord, de kaart, de wiki-kop). Eén etiket-atoom voor het hele dorp.
    rechts = (f"<span class='chip'>{_e(tag)}</span>" if tag
              else (f"<span class='c2-psub'>{_e(sub)}</span>" if sub else ""))
    return (f"<a class='c2-prij' href='{_e(href)}'>"
            f"<span class='c2-pnaam'>{_e(tekst)}</span>{rechts}</a>")


def _groep(naam: str) -> str:
    return f"<p class='c2-pgroep'>{_e(naam)}</p>"


def _leeg(tekst: str) -> str:
    return f"<p class='muted c2-pleeg'>{_e(tekst)}</p>"


# ── ZOEK ─────────────────────────────────────────────────────────────────────
#
# HET ZOEKPANEEL IS OP 22 SEPTEMBER 2026 VERVALLEN (eis Stefan) en de functie blijft staan omdat
# hij niets kost en de reden hier hoort te staan: er waren TWEE zoek-ingangen in de balk, het
# altijd zichtbare `c2-search`-veld (met `/`-sneltoets en typeahead) en deze knop, en ze gingen
# naar dezelfde `/search`-inhoud.
#
# De knop had zijn reden toen hij gebouwd werd: in de rail-stand was `.c2-search` verborgen, dus
# op /messages was er geen zoek. Die rail verviel op 21 september (#544) en daarmee de reden voor
# de knop — zonder dat iemand hem weghaalde. `zoek` staat niet meer in `PANELEN`.
#
# WAT BLEEF: de twee gaten die bij het bouwen van deze knop werden gedicht, zitten in de
# ZOEKMACHINE zelf en niet in het paneel — de groep `Channels` (kanalen op naam) en de goal- en
# topic-trails in `Messages`. Die werken onveranderd via het zoekveld.
def _paneel_zoek(st, ik: str, q: str) -> str:
    """Het bestaande globale zoeken, in het paneel.

    GEEN TWEEDE ZOEKMACHINE. `views/search.py` doorzoekt al negen bronnen (mensen, rollen,
    accountabilities, projecten, checklist-stappen, wiki-pagina's inclusief hun feiten, berichten,
    radar-inzichten en het lexicon), met per groep een eigen fail-soft die "niet geladen" van "0
    treffers" onderscheidt. Gemeten op productie: 17-23 ms over 442 projecten, ook bij een
    zoekterm van één letter die bijna alles matcht. Er is dus geen index of cache nodig, en een
    tweede index zou een tweede antwoord geven op "wat is vindbaar".

    DM'S BLIJVEN ERBUITEN. Dat is een bestaand besluit en geen omissie: een privégesprek
    doorzoekbaar maken voor iedereen die is ingelogd is geen zoekfunctie maar een lek."""
    from nooch_village.views.search import render_search_fragment
    # HET LABEL STAAT ER WEL, MAAR JE ZIET HET NIET. Boven dit veld staat al "SEARCH" als
    # paneeltitel; "Search everything" eronder is hetzelfde woord twee keer. Weghalen mag niet —
    # een zoekveld zonder label is voor een schermlezer een naamloos invoerveld — dus hij gaat in
    # `.sr`, het bestaande visueel-verborgen atoom.
    veld = (f"<form class='c2-pzoek' method='get' action='/search' role='search'>"
            f"<label class='sr' for='c2-pq'>Search everything</label>"
            f"<input id='c2-pq' type='search' name='q' value='{_e(q)}' autocomplete='off' "
            f"placeholder='People, roles, projects, channels, wiki…' data-nav-zoek>"
            f"</form>")
    if len((q or "").strip()) < 2:
        return veld + _leeg("Type to search people, roles, projects, channels and wiki at once.")
    return veld + f"<div class='c2-pzoekuit'>{render_search_fragment(st, q)}</div>"


# ── PR ───────────────────────────────────────────────────────────────────────
# HET PROJECTS-PANEEL IS OP 23 SEPTEMBER 2026 VERVALLEN (eis Stefan) en de functie blijft staan
# omdat hij niets kost en de reden hier hoort te staan — zelfde behandeling als `_paneel_messages`
# hieronder. Het paneel gaf een LIJST terwijl `/projects` het BORD is: je koos een project uit een
# platte lijst om daarna op een bord te landen dat je meteen had kunnen zien. Het filter dat het
# paneel wél toevoegde ("mijn projecten") bestaat op het bord zelf als groepering. `pr` staat
# daarom niet meer in `PANELEN`; de knop is een paginasprong, zoals Messages, Wiki en Admin.
def _paneel_projects(st, ik: str, welke: str) -> str:
    """Standaard "mijn projecten", zoals het prototype toont.

    DEZELFDE DEFINITIE ALS DE PERSOON-LENS: een project is van jou als zijn eigenaar-rol door jou
    wordt vervuld (`owner ∈ roles_of("person", ik)`). Die stond er al; een tweede definitie van
    "mijn" zou hier stilletjes een andere lijst geven dan op je eigen pagina."""
    alle = [p for p in st.projects.all()
            if not p.get("archived") and p.get("status") not in ("done", "draft")]
    rollen = set(st.assign.roles_of("person", ik)) if ik else set()
    mijn = [p for p in alle if p.get("owner") in rollen]
    lijst = alle if welke == "alle" else mijn

    def _knop(v: str, label: str) -> str:
        aan = " on" if welke == v else ""
        return (f"<a class='cl-filter pill{aan}' href='/nav-paneel?p=pr&welke={v}' "
                f"data-nav-frag>{_e(label)}</a>")

    kop = f"<div class='cl-group c2-pseg'>{_knop('mijn', 'My projects')}{_knop('alle', 'All')}</div>"
    if not lijst:
        return kop + _leeg("No projects yet." if welke == "alle"
                           else "None of your roles owns a project yet.")
    rijen = []
    for p in lijst[:60]:
        d = st.doelen.get(p.get("doel_id") or "") if p.get("doel_id") else None
        rijen.append(_rij(f"/project?id={p.get('id')}", str(p.get("scope") or p.get("id") or ""),
                          tag=(d or {}).get("label", "")))
    meer = (_leeg(f"+{len(lijst) - 60} more — use search.") if len(lijst) > 60 else "")
    return kop + "".join(rijen) + meer


# ── ME ───────────────────────────────────────────────────────────────────────
#
# HET MESSAGES-PANEEL IS OP 21 SEPTEMBER 2026 VERVALLEN (eis Stefan) en de functie blijft staan
# omdat hij niets kost en de reden hier hoort te staan: Messages is als enige van de vijf een
# scherm dat zelf al uit lijst + detail bestaat. Een paneel kon daar alleen de lijst van tonen —
# een kopie van wat de pagina zelf heeft — terwijl het gesprek nergens was en je vorige scherm
# ernaast bleef staan. `me` staat daarom niet meer in `PANELEN`; de knop is een paginasprong,
# zoals Wiki en Admin.
def _paneel_messages(st, ik: str) -> str:
    """De kanalenlijst uit PR 5, op een andere plek gerenderd. NIET MEER BEREIKBAAR — zie hierboven.

    DIT IS EEN RENDER-PLEK-WIJZIGING EN GEEN NIEUWE LIJST: `_kanalen` is dezelfde functie die
    `/messages` gebruikt, met dezelfde vier vaste lagen en dezelfde "alleen wat jij volgt" voor
    projecten. Verandert daar iets, dan verandert het hier mee."""
    from nooch_village.views.messages import _kanalen, _label
    groepen, totaal, _gevolgd = _kanalen(st, ik, "")
    uit = []
    for naam, rij in groepen.items():
        if not rij:
            if naam == "Projects":
                uit.append(_groep(naam) + _leeg("None followed yet. Search on Messages to add one."))
            continue
        extra = (f" ({len(rij)} of {totaal[naam]})"
                 if naam == "Projects" and totaal[naam] > len(rij) else "")
        uit.append(_groep(naam + extra))
        for k in rij[:40]:
            uit.append(_rij(f"/messages?k={urllib.parse.quote(k)}", _label(st, k, ik)))
    return "".join(uit) or _leeg("No channels yet.")


# ── CI ───────────────────────────────────────────────────────────────────────
def _paneel_circle(st, ik: str) -> str:
    """De rollen van JOUW cirkel, met wie ze vervult. Eén cirkel, niet de hele boom.

    HIJ TOONDE ZE ALLEMAAL. De lus liep over `[wortel] + alle niet-gearchiveerde cirkels` en
    zette van elk de leden onder elkaar — terwijl de docstring hier ("de cirkel waar je in zit")
    en de href van de knop (`/node?id=<operationele cirkel>`) allebei ÉÉN cirkel beloofden. Wat
    je kreeg was Organization, plat. Twee nav-items met dezelfde inhoud, en dat is precies wat
    opviel.

    DEZELFDE BRON ALS DE KNOP, letterlijk `_home_node`. Die vult `_send` al in de href; hem hier
    opnieuw afleiden zou betekenen dat "welke cirkel is de mijne" op twee plekken wordt
    beantwoord — het patroon dat in dit dorp al twee keer een bug opleverde (de goal-kanaal-lijst
    en de platslag-regel).

    `ik` IS NOG STEEDS ONGEBRUIKT, en dat is nu een bewuste stand: er is één operationele cirkel
    en iedereen kijkt naar dezelfde. Wordt het dorp ooit een boom met meerdere teams, dan is dit
    de plek waar het persoonlijk wordt — en dan is het een keuze, geen vergeten parameter.

    Een rol zonder vervuller staat er MET die melding bij — "open" is informatie, geen lege
    regel."""
    from nooch_village.cockpit2 import _home_node
    from nooch_village.cockpit2_util import _name
    recs = st.records.all()
    cid = _home_node(recs)
    cirkel = st.records.get(cid) if cid else None
    if cirkel is None:
        return _leeg("No circle yet.")
    leden = [r for r in recs if not r.archived and getattr(r, "parent", None) == cirkel.id]
    uit = [_groep(_name(cirkel))] if leden else []
    for rec in leden:
        namen = []
        try:
            for f in st.assign.fillers_of(rec.id, record=rec):
                if getattr(f, "type", "") == "person":
                    pers = st.people.get(getattr(f, "id", ""))
                    if pers is not None:
                        namen.append(pers.name)
        except Exception:                                  # noqa: BLE001
            log.debug("vervullers niet te lezen voor %s", rec.id, exc_info=True)
        uit.append(_rij(f"/node?id={rec.id}", _name(rec),
                        sub=", ".join(namen) or "open — nobody"))
    return "".join(uit) or _leeg("No roles yet.")


# ── ORG ──────────────────────────────────────────────────────────────────────
def _paneel_org(st, ik: str, hier: str) -> str:
    """De organisatieboom, als gewoon paneel naast de balk.

    HIJ HING ERONDER, IN EEN EIGEN UITKLAPJE. `_nav()` zette hem onderaan de zijbalk in een
    `<details class='c2-orgfly'>` — een tweede uitklap-mechanisme naast de panelen, op een plek
    waar je hem alleen vond door naar beneden te scrollen. Nu is het een nav-item zoals de andere,
    met dezelfde flyout ernaast (voorstel Stefan, 21 september 2026).

    DEZELFDE BOOM, NIET EEN TWEEDE. `_tree_html` is de functie die `_send` ook in de zijbalk
    injecteerde; hier wordt hij alleen op een andere plek gerenderd. Een eigen boomweergave zou
    betekenen dat "waar zit deze rol" twee antwoorden heeft zodra er aan één iets verandert."""
    from nooch_village.views.overview import _tree_html
    try:
        return f"<div class='c2-org'>{_tree_html(st, hier)}</div>"
    except Exception:                                      # noqa: BLE001
        log.debug("organisatieboom niet te renderen", exc_info=True)
        return _leeg("The organization tree could not be loaded.")


# ── de route ─────────────────────────────────────────────────────────────────
def render_nav_paneel(st, p: str = "", ik: str = "", q: str = "", welke: str = "mijn",
                      hier: str = "") -> str:
    """Het fragment voor één paneel. Onbekende sleutel → leeg, geen gok en geen foutpagina.

    `hier` LEEG BETEKENT NIET "NERGENS". `nooch.js` vult hem alleen als je op een `/node`-pagina
    staat — een fragment weet niet waar het landt. Vanaf Messages, Wiki of Projects kwam de boom
    daardoor dicht en ongemarkeerd binnen, terwijl `_tree_html` het openklappen (`org.breadcrumb`)
    en markeren (`.here`) allang kan. Er ontbrak dus geen machinerie maar een DEFAULT: je eigen
    cirkel.

    Die default komt uit `_home_node`, dezelfde bron als de twee overleg-knoppen, `/projects` en
    `/vangst`. Een eigen "welke cirkel is van mij"-regel hier zou een tweede antwoord geven op
    een vraag die al beantwoord is — precies de fout die `_paneel_circle` maakte voordat hij
    verviel."""
    titels = {"ci": "Circle", "org": "Organization"}
    if p not in PANELEN:
        return ""
    if p == "org":
        if not hier:
            from nooch_village.cockpit2 import _home_node
            hier = _home_node(st.records.all())
        inhoud = _paneel_org(st, ik, hier)
    else:
        inhoud = _paneel_circle(st, ik)
    return f"<h2 class='c2-pkop'>{_e(titels[p])}</h2>{inhoud}"
