"""Tools — al het gereedschap van het dorp op één plek (`/tools`).

WAAROM DIT GEEN DERDE PLEK IS. Dat was de zorg bij de Tensions/Actions-discussie: een nieuw scherm
dat náást bestaande komt te staan, en dan moet je weten waar iets ooit is neergezet. Hier gebeurt
het omgekeerde — gereedschap gaat WEG uit de wiki-tab per cirkel en komt op precies één plek te
staan. Van twee plekken naar één.

WAAROM EEN TOOL DAT VERDIENT. Hij is al een eigen soort in de data (`kind="tool"`), en hij is het
enige artefact-soort met een `url`: een note en een policy zijn er om te LEZEN, een tool om te
GEBRUIKEN. Die twee horen niet door hetzelfde filter — je zoekt een tool niet op "bij welke rol
stond hij ook alweer", je zoekt hem omdat je hem nodig hebt.

TWEE SOORTEN GEREEDSCHAP, en ze staan hier DOOR ELKAAR omdat ze voor de gebruiker hetzelfde zijn:

  1. TOOL-ARTEFACTEN uit de AttachmentStore (`by_kind("tool")`, dorpsbreed). Die kun je bewerken
     als je op hun eigenaar mag schrijven.
  2. SCHERM-TOOLS uit `_ROLE_TOOLS`/`_DOMAIN_TOOLS` in `views/overview.py`: vaste links die bij een
     rol of een domein horen. Die zijn code, geen data.

ÉÉN ALFABETISCHE LIJST, GEEN GROEPEN (29 september 2026). Tot dan stonden ze in twee blokken, en de
schermen nog eens onderverdeeld per rol. Dat is de indeling van de maker — waar komt dit ding
vandaan, bij wie hoort het — en niet die van de gebruiker: die weet bij "ik wil de site scannen"
niet of dat ooit als artefact of als scherm gebouwd is, en hoefde dat ook nooit te weten. Wie de
vraag WÉL per rol stelt, kijkt op de Tools-tab van die rol (`_role_tools_html`); die groepering
blijft daar, want daar is de rol het onderwerp.

De tabellen worden GEÏMPORTEERD en niet gekopieerd: één plek waar staat welk scherm bij welke rol
hoort, precies zoals `TOOL_ANCHOR` één plek is voor waar een tool-artefact hangt.
"""
from __future__ import annotations

from nooch_village import artefacts
from nooch_village.cockpit2_util import _DS_LINK, _nav, _name
from nooch_village.web_base import _e, _field, _page


def _eigenaar(st, anchor: str) -> str:
    rec = st.records.get(anchor or "")
    return (_name(rec) if rec is not None else "") or anchor or "—"


def _kaart(st, a, mag_bewerken: bool) -> str:
    """Eén tool-artefact. DE TITEL IS ALTIJD EEN LINK: met een url naar het SCHERM — een tool open
    je, je leest hem niet — en zonder url naar zijn eigen pagina.

    DAT LAATSTE WAS EEN GAT. Een tool zonder url was hier een doodlopende kaart: geen link naar
    het scherm (dat er niet is) en geen weg naar zijn pagina. Wie mocht schrijven kwam er nog via
    de bewerk-link; wie alleen las, nergens. Sinds de leespagina de beschrijving, de
    versiehistorie én het formulier draagt, is er altijd iéts om heen te gaan."""
    from nooch_village.wiki import pagina_url
    url = (getattr(a, "url", "") or "").strip()
    titel = _e(a.title or a.id)
    kop = (f"<a href='{_e(url)}'><b>\U0001f6e0 {titel}</b></a>" if url
           else f"<a href='{_e(pagina_url(a.id))}'><b>\U0001f6e0 {titel}</b></a>")
    body = (a.body or "").strip()
    # DE EIGENAAR BLIJFT ZICHTBAAR, ook nu de tool niet meer onder zijn rol staat. Wie hem mag
    # bewerken hangt eraan, en dat weten is de helft van "mag ik hier iets aan veranderen".
    bij = (f"<a class='chip' href='/node?id={_e(a.anchor)}&tab=wiki'>"
           f"{_e(_eigenaar(st, a.anchor))}</a>")
    bewerk = ""
    if mag_bewerken:
        # NAAR DE LEESPAGINA VAN DE TOOL ZELF, en niet meer naar de rol.
        #
        # HIER STOND "edit on the role", en dat klopte toen dit scherm werd gebouwd: het
        # formulier stónd op de rol-pagina. Sindsdien is het naar de leespagina van het artefact
        # verhuisd — één bewerkpad per artefact, dezelfde regel die een note sinds 21 september
        # al volgt. Doorverwijzen naar de rol zou nu wijzen naar een plek waar niets meer te
        # bewerken valt, en dat is erger dan geen link: je klikt en vindt niets.
        bewerk = f" <a class='flink' href='{_e(pagina_url(a.id))}'>Edit</a>"
    return (f"<div class='card'>{kop} {bij}{bewerk}"
            f"{f'<div class=muted>{_e(body)}</div>' if body else ''}</div>")


def _nieuwe_tool_form(st, csrf_token: str, username: str | None) -> str:
    """"+ New tool", vanuit dit scherm zelf.

    WAAROM HIJ HIER MOEST KOMEN. Aanmaken kon alleen via "+ New page" op `/wiki`, en dat is de
    ingang die met deze stap verdwijnt — een tool is geen pagina om te lezen. Zonder dit formulier
    zou er nergens meer een tool bij kunnen; daarom staat hij er eerst, en gaat de wiki-kant pas
    daarna weg.

    DRIE VELDEN, EN GEEN EIGENAAR. Dat laatste is geen vereenvoudiging maar een gevolg: sinds #632
    dwingt `_act_artefact_add` zelf af dat een tool aan `artefacts.TOOL_ANCHOR` hangt. Een
    eigenaar-keuze hier zou een vraag zijn waarvan het antwoord genegeerd wordt — en dan staat de
    regel op twee plekken.

    GEEN DOMEIN- EN SECTIEVELD, en dat is precies waarom "+ New page" ze wél heeft: die twee
    bepalen waar een PAGINA in de wiki-navigatie landt. Een tool staat niet in die navigatie; hij
    staat hier.

    ZELFDE VORM ALS "+ New page" (`views/wiki._nieuwe_pagina_form`): een `<details class='qadd'>`
    met een `.qadd-form` erin, velden via `_field()` zodat label en veld een paar zijn, en dezelfde
    knoppenrij. Geen tweede formuliertaal voor dezelfde handeling."""
    if not csrf_token:
        return ""
    actor = st.people.by_email(username) if username and username != "guest" else None
    # "guest" (auth uit) mag alles, zoals overal in de cockpit; een onbekende naam mag niets. Dit
    # spiegelt de serverpoort: `_artefact_gate` laat op een artefact zonder domein elke herkende
    # persoon door, en weigert een naam die het dorp niet kent.
    if actor is None and username != "guest":
        return ""
    return (f"<details class='qadd'><summary>+ New tool</summary>"
            f"<form method='post' action='/action' class='qadd-form'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"<input type='hidden' name='action' value='artefact_add'>"
            f"<input type='hidden' name='kind' value='tool'>"
            f"<input type='hidden' name='next' value='/tools'>"
            f"{_field('Title', 'title', required=True, fid='nt-title')}"
            f"{_field('Link', 'url', kind='url', fid='nt-url', placeholder='https://… or /a-screen')}"
            f"{_field('What it does', 'body', kind='textarea', fid='nt-body')}"
            f"<div class='muted wiki-hint'>Every tool belongs to the village as a whole, so there "
            f"is no owner to pick. Without a link the tool gets its own page.</div>"
            f"<div class='qadd-row'>"
            f"<button class='btn ok' type='submit'>Create</button>"
            f"<button type='button' class='qadd-x' onclick=\"this.closest('details').open=false\" "
            f"aria-label='cancel'>&#10005;</button></div></form></details>")


def render_tools(st, csrf_token: str = "", username: str | None = None, msg: str = "") -> str:
    """Alle tools van het dorp. Lezen is vrij; bewerken blijft bij de eigenaar van het artefact."""
    from nooch_village.views.overview import _DOMAIN_TOOLS, _ROLE_TOOLS, _banner, _tool_kaart

    actor = st.people.by_email(username) if username and username != "guest" else None
    actor_id = getattr(actor, "id", "")

    # ── één lijst, en dat is het hele punt ───────────────────────────────────
    #
    # TOT 29 SEPTEMBER STONDEN ZE IN TWEE BLOKKEN: "Tools" (artefacten) en "Screens per role" (de
    # ingebouwde schermen, met een kopje per rol). Dat is de indeling van de MAKER — waar komt dit
    # ding vandaan, bij wie hoort het — en niet die van de gebruiker: die zoekt een tool omdat hij
    # hem nodig heeft, en weet meestal niet of het gereedschap ooit als artefact of als scherm is
    # gebouwd. Wie wél wil zien wat bij een rol hoort, kijkt op de Tools-tab van die rol
    # (`_role_tools_html`) — daar is de rol de vraag, hier niet.
    #
    # DE TABELLEN WORDEN GEÏMPORTEERD EN NIET GEKOPIEERD, onveranderd: één plek waar staat welk
    # scherm bij welke rol hoort.
    regels: list[tuple[str, str]] = []                  # (sorteernaam, html)

    for a in st.att.by_kind("tool"):
        regels.append(((a.title or a.id or "").lower(),
                       _kaart(st, a, bool(actor_id) and artefacts.can_write_artefact(
                           "person", actor_id, a.anchor, st.records, st.assign))))

    # DE SCHERM-TOOLS HANGEN AAN EEN RECORD, ook nu de rol niet meer op het scherm staat: een
    # domein-tool vult zijn eigen rol-id in (`{rol}`), en een gearchiveerde rol hoort hier niet.
    gezien: set[tuple[str, str]] = set()
    for rec in st.records.all():
        if getattr(rec, "archived", False):
            continue
        tools = list(_ROLE_TOOLS.get(rec.id, []))
        for d in (getattr(getattr(rec, "definition", None), "domains", None) or []):
            for label, desc, href in _DOMAIN_TOOLS.get(" ".join(str(d).split()).lower(), []):
                tools.append((label, desc, href.replace("{rol}", _e(rec.id))))
        for label, desc, href in tools:
            # ZONDER DE ROL-KOPPEN IS EEN DUBBELE KAART EEN DUBBELE KAART. Twee rollen met hetzelfde
            # domein leverden eerst twee kaarten onder twee kopjes — leesbaar. Naast elkaar in één
            # lijst is dat ruis, en de tweede voegt niets toe: zelfde naam, zelfde bestemming.
            if (label, href) in gezien:
                continue
            gezien.add((label, href))
            regels.append((label.lower(), _tool_kaart(label, desc, href)))

    regels.sort(key=lambda r: r[0])
    lijst = ("".join(h for _n, h in regels) if regels else
             "<p class='muted'>No tools in the village yet.</p>")
    # HET FORMULIER STAAT ER OOK BIJ NUL TOOLS. Zou hij alleen onder een gevulde lijst hangen, dan
    # is de enige stand waarin je hem écht nodig hebt precies de stand waarin hij ontbreekt.
    blok = (f"<div class='c2-sec'><div class='tile-grid'>{lijst}</div>"
            f"{_nieuwe_tool_form(st, csrf_token, username)}</div>")

    main = (f"<div class='c2-main'><h1 class='ptitle'>Tools</h1>"
            f"<p class='muted'>Everything in the village you can <em>use</em>, on one page. "
            f"A tool is not something to read &mdash; it is something to open.</p>"
            f"{_banner(msg)}{blok}</div>")
    return _page("Tools", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
