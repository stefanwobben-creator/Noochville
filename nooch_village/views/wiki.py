"""Pagina-view — de wiki-kant van een rol-note (`/pagina?id=NOTE-…`).

De Notes-tab op een rol blijft de index; dit is de permalink. Twee dingen passen niet in een
tab-kaartje en wonen daarom hier: de **feiten met hun grond** (die bij elk lezen opnieuw wordt
vergeleken) en de **backlinks** (welke pagina's hiernaar verwijzen).

Alles hergebruikt het bestaande artefact-idioom: `.card`, `.ptitle`, `.att-body`, `.qadd-form`,
`.c2-sec`, `.pill`, `.chip`. Bewerken en versie-historie komen letterlijk uit `views/overview.py`
— dezelfde knop, hetzelfde formulier, dezelfde poort (reference, don't copy).
"""
from __future__ import annotations

import html as _html_mod
import json as _json
import re

from nooch_village.web_base import _e, _page, _banner, _field
from nooch_village.cockpit2_util import (_DS_LINK, _nav, _md, _name, link_kaart,
                                         opmaak_werkbalk,
                                         BLOK_SOORTEN, blok_menu)
from nooch_village import domeinen, wiki

# Status → chip-icoon. Bewust vijf verschillende tekens: 'gegrond' en 'ongecontroleerd' mogen op
# het scherm nooit op elkaar lijken, want dat is precies het verschil tussen bewijs en herkomst.
_STATUS_ICON = {
    wiki.GEGROND: "✓",
    wiki.ONGECONTROLEERD: "◌",
    wiki.VERVALLEN: "⌛",
    wiki.ONTBREEKT: "✗",
    wiki.ONGEGROND: "—",
}

_SOORT_LABEL = {
    "kroniek": "Chronicle record",
    "cert": "Certificate",
    "policy": "Policy",
    "bron": "Cited source (URL)",
}


#: Wat er staat als een artefact nog geen tekst heeft. Op ÉÉN plek, want drie soorten pagina's
#: zeggen het: een note zonder body, een policy zonder body, en de tool die op prod leeg is
#: (TOOL-WEBSIT-001). Een pagina die dan niets zegt, ziet eruit als een fout.
_GEEN_TEKST = "<p class='muted'>This page has no text yet.</p>"

#: `<li>[ ] ` of `<li>[x] ` aan het begin van een lijstitem. De weg terug (`_md_naar_bron`) kent
#: het vakje wél — anders eet de wiki bij elke bewerking zijn eigen vinkjes op.
_TAAK_RE = re.compile(r"<li>\[([ xX])\] ")


def _body_html(body: str, pags: list, blokken: bool = False,
               secties: dict[str, str] | None = None) -> str:
    """De body als markdown, met `[[verwijzingen]]` omgezet in links.

    De substitutie draait NÁ `_md` (dus over ge-escapete HTML) en alleen hier — `_md` zelf wordt
    ook voor reacties en projectfeeds gebruikt, en die zijn geen wiki.

    `blokken=True` geeft elk blok op het hoogste niveau een eigen `<div class='wb'>`; zie `_md`.
    Ook hier standaard UIT: dezelfde functie rendert de Notes-tab op `/node`, en die heeft de
    blokken (nog) niet nodig.

    DE AFVINKBARE TAAK WORDT HIER GEMAAKT EN NIET IN `_md` (besluit Stefan, 22 september 2026):
    een dode checkbox in een chatbericht is verwarrender dan hij waard is, en `_md` rendert ook
    elke reactie en elk kanaalbericht. Dit is dezelfde plek en dezelfde techniek als de
    `[[verwijzingen]]` hieronder: een substitutie NA `_md`, alleen hier.

    `disabled`, want aanvinken met de muis is brok 3. Zonder dat attribuut is het vakje
    klikbaar en verandert er bij het opslaan niets — een knop die niets doet.

    GEEN SPATIE TUSSEN HET VAKJE EN DE TEKST, die komt uit `.wb-taak input`. Stond hij in de
    HTML, dan schreef de weg terug er één bij de zijne en werd `[ ] open` na elke bewerking
    `[ ]  open` — een spatie erbij per keer opslaan. De ruimte is opmaak, het haakje is inhoud."""
    html = _md(body or "", blokken=blokken)
    html = _TAAK_RE.sub(
        lambda m: (f"<li class='wb-taak'><input type='checkbox'"
                   f"{' checked' if m.group(1).lower() == 'x' else ''}>"),
        html)
    # HET BLOK KRIJGT ZIJN EIGEN SOORT, hier en niet in `_md`. Dezelfde reden als voor het vakje
    # zelf: `_md` rendert ook elke reactie en elk kanaalbericht, en daar hoort geen taak-blok. De
    # TAG blijft `ul` — een takenlijst ís een lijst — maar het blok heet `taak`, zodat de greep,
    # het menu en de vormgeving het verschil zien.
    if blokken:
        html = re.sub(r"<div class='wb' data-blok='ul'>(?=<ul[^>]*>(?:(?!</ul>).)*?wb-taak)",
                      "<div class='wb' data-blok='taak'>", html, flags=re.S)

    def _sub(m):
        ref = _html_mod.unescape(m.group(1)).strip()
        doel = wiki.resolve(ref, pags)
        if doel is None:
            # Bestaat (nog) niet, of de titel is niet uniek: zichtbaar laten staan als
            # verlanglijst-item. Nooit stilzwijgend naar een gok linken, nooit automatisch
            # aanmaken — een pagina krijgt een eigenaar, en dat is een besluit.
            return (f"<span class='chip muted' data-ref='{_e(ref)}' "
                    f"title='no unique page with this name'>{m.group(1)}</span>")
        # `data-ref` draagt de ORIGINELE verwijzing mee, niet de opgeloste titel. De inline-editor
        # stuurt deze HTML terug en `_md_naar_bron` moet er weer `[[…]]` van maken; zonder dit
        # attribuut zou `[[COMPLI-021]]` terugkomen als de titel van de pagina waar hij heen wees,
        # en dat is een andere verwijzing dan wat de schrijver typte.
        return (f"<a class='pill' data-ref='{_e(ref)}' "
                f"href='{_e(wiki.pagina_url(doel.id))}'>{_e(doel.title or doel.id)}</a>")

    html = wiki.LINK_RE.sub(_sub, html)
    # DE TOOL-KAART. Een blok dat ALLEEN een verwijzing naar een tool bevat wordt een kaart;
    # midden in een zin blijft het een pil. Zelfde grens als bij de embed, en om dezelfde reden:
    # anders verandert één woord in een alinea de vorm van de hele pagina.
    #
    # GEEN INSLUITING (besluit uit het ontwerp). Een interne tool is een SCHERM; insluiten vraagt
    # een iframe of een tweede renderpad per tool, en dat contract bestaat voor geen van de vijf
    # tools op prod.
    if blokken:
        html = _TOOLREF_RE.sub(lambda m: _tool_kaart(m, pags), html)
        # HET AFGELEIDE BLOK, als laatste. Feiten en backlinks wonen niet in de body: een
        # markering wijst alleen de PLEK aan, de inhoud komt van de aanroeper. Alleen in de
        # blokstand, want buiten die stand bestaan er geen blokken om dit aan op te hangen — en
        # een sectie tussen twee `<br>`'s is geen blok maar een ongeluk.
        html = _MARKER_BLOK_RE.sub(lambda m: _afgeleid_blok(m.group(1), secties), html)
    else:
        # BUITEN DE BLOKSTAND GEEN SECTIE MAAR EEN LABEL. De Notes-tab van `/node` rendert plat:
        # daar bestaan geen blokken, en een `.c2-sec` met een eigen kopje tussen twee `<br>`'s is
        # geen blok maar een ongeluk. Wat er WEL moet gebeuren is de accolades wegwerken — rauwe
        # `{{facts}}` op het scherm is het slechtste van twee werelden.
        html = _MARKER_PLAT_RE.sub(_afgeleid_label, html)
    return html


#: Een markering die alleen op zijn regel staat, in de platte stand: aan het begin of na een
#: `<br>`, en aan het eind of vóór een `<br>`. Dezelfde grens als hierboven — middenin een zin
#: blijft het tekst.
_MARKER_PLAT_RE = re.compile(r"(?<=<br>)\{\{([a-z]+)\}\}(?=<br>|$)|^\{\{([a-z]+)\}\}(?=<br>|$)")


def _afgeleid_label(m) -> str:
    naam = m.group(1) or m.group(2)
    if naam not in wiki.AFGELEID:
        return m.group(0)
    return f"<span class='chip muted'>{_e(wiki.AFGELEID[naam])}</span>"


#: Een blok dat ALLEEN uit een markering bestaat. Zelfde vorm als `_TOOLREF_RE` hierboven.
_MARKER_BLOK_RE = re.compile(
    r"<div class='wb' data-blok='p'>\{\{([a-z]+)\}\}</div>")


def _afgeleid_blok(naam: str, secties: dict[str, str] | None) -> str:
    """De markering wordt het blok; de inhoud komt van buiten.

    DRIE DINGEN ZITTEN HIER IN ELKAAR:

    `data-blok-bron` draagt de BRON. Alles binnen dit blok is uitvoer die bij elk lezen opnieuw
    wordt berekend; kwam dat terug in de opslag, dan stonden de feiten na één bewerkronde als
    platte tekst in de pagina — twee waarheden, en de tweede veroudert stil. `_md_naar_bron`
    leest het attribuut en slaat de rest over.

    `contenteditable='false'` maakt er een ondeelbaar ding van. Zonder dat zet de browser de
    caret tussen de kaartjes en typt de lezer in iets dat bij het opslaan verdampt.

    GEEN EIGEN CSS-KLASSE OP HET OMHULSEL. Dat is hetzelfde `.wb` als elk ander blok — inclusief
    de greep, zodat je hem kunt verplaatsen. Een `wb-afgeleid` zou een klasse zijn zonder gemeten
    aanleiding, en dat is precies wat de huisstijl-regel verbiedt.

    DE SECTIE BRENGT ZIJN EIGEN VORM MEE, en die is sinds 26 september `.wiki-inline`: geen rand,
    geen achtergrondvlak en geen sectie-marge, want tussen twee alinea's maakt elk van die drie het
    "blok, witruimte, blok"-gevoel dat deze stap juist wegneemt. Het onderscheid — dit is een Feit
    en geen alinea — is een dunne accentlijn per rij.

    ZONDER SECTIE EEN LABEL, GEEN ACCOLADES. De Notes-tab van `/node` heeft geen `st` om feiten
    mee op te halen; rauwe `{{facts}}` op het scherm is dan het slechtste van twee werelden."""
    if naam not in wiki.AFGELEID:
        return f"<div class='wb' data-blok='p'>{{{{{_e(naam)}}}}}</div>"
    inhoud = (secties or {}).get(naam)
    if not inhoud:
        inhoud = (f"<div class='wiki-inline'><div class='muted'>"
                  f"{_e(wiki.AFGELEID[naam])}</div></div>")
    return (f"<div class='wb' data-blok='{_e(naam)}' "
            f"data-blok-bron='{{{{{_e(naam)}}}}}' contenteditable='false'>{inhoud}</div>")


#: Een blok dat ALLEEN uit één opgeloste verwijzing bestaat.
_TOOLREF_RE = re.compile(
    r"<div class='wb' data-blok='p'>"
    r"(<a class='pill' data-ref='([^']+)' href='([^']+)'>([^<]*)</a>)"
    r"</div>")


def _tool_kaart(m, pags: list) -> str:
    """Een verwijzing naar een TOOL wordt een kaart; naar iets anders blijft hij zoals hij was."""
    ref = _html_mod.unescape(m.group(2)).strip()
    doel = wiki.resolve(ref, pags)
    if doel is None or getattr(doel, "kind", "") != "tool":
        return m.group(0)
    bestemming = (getattr(doel, "url", "") or "").strip()
    waar = f"tool &middot; {_e(bestemming)}" if bestemming else "tool"
    return (f"<div class='wb' data-blok='embed'>"
            f"<figure class='card wb-emb wb-emb--tool'>"
            f"<span class='wb-emb-ico' data-chrome aria-hidden='true'>&#128295;</span>"
            f"{m.group(1)}"
            f"<span class='wb-emb-bron muted' data-chrome>{waar}</span>"
            f"</figure></div>")


def _grond_chip(g: dict) -> str:
    icon = _STATUS_ICON.get(g["status"], "—")
    label = f"{icon} {_e(g['label'])}"
    # Een geciteerde bron is altijd klikbaar, ongeacht de uitkomst van de laatste check: juist bij
    # "citaat niet meer gevonden" wil de lezer meteen kunnen kijken wat er dan wél staat.
    if g["soort"] == "bron" and g["url"]:
        label = (f"{icon} <a href='{_e(g['url'])}' target='_blank' rel='noopener'>"
                 f"{_e(g['label'])}</a>")
    detail = f" <span class='muted'>{_e(g['detail'])}</span>" if g["detail"] else ""
    return f"<span class='chip'>{label}</span>{detail}"


def _feit_html(i: int, feit: dict, st, aid: str, csrf_token: str, can_edit: bool) -> str:
    g = wiki.grond_status(feit, ledger=getattr(st, "evidence", None), store=st.att)
    citaat = (f"<div class='att-body muted'>“{_e(g['citaat'])}”</div>"
              if g.get("citaat") else "")
    weg = ""
    if can_edit:
        weg = (f"<form method='post' action='/action'>"
               f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
               f"<input type='hidden' name='aid' value='{_e(aid)}'>"
               f"<input type='hidden' name='i' value='{i}'>"
               f"<input type='hidden' name='next' value='{_e(wiki.pagina_url(aid))}'>"
               f"<button class='dellink' type='submit' name='action' value='pagina_feit_del' "
               f"onclick=\"return confirm('Remove this fact?')\">remove</button></form>")
    # GEEN `.card` (26 september 2026). Zodra een Feit tussen twee alinea's kan staan — en dat
    # kan het sinds `{{facts}}` in het blokmenu staat — botst een kaart met de tekst eromheen:
    # rand, achtergrond en eigen padding heeft een alinea alle drie niet. Het onderscheid blijft,
    # maar als een dunne accentlijn (`.wiki-inline`), niet als een losstaande doos.
    return (f"<div><div class='ptitle'>{_e(feit.get('tekst') or '')}</div>"
            f"<div>{_grond_chip(g)}</div>{citaat}{weg}</div>")


def _feit_form(aid: str, csrf_token: str) -> str:
    opts = "".join(f"<option value='{k}'>{_e(v)}</option>" for k, v in _SOORT_LABEL.items())
    # De veld-ids dragen de artefact-id (zelfde reden als _voorstel_form hieronder): zodra
    # feiten-secties van meerdere pagina's onder elkaar staan (Notes-tab, inline), laat een kale
    # id elk gekoppeld label naar de EERSTE kaart wijzen in plaats van zijn eigen kaart.
    soort_id = f"feit-soort-{aid}"
    return (f"<details class='qadd'><summary>+ Add fact</summary>"
            f"<form method='post' action='/action' class='qadd-form'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"<input type='hidden' name='aid' value='{_e(aid)}'>"
            f"<input type='hidden' name='next' value='{_e(wiki.pagina_url(aid))}'>"
            f"{_field('Fact', 'tekst', required=True, fid=f'feit-tekst-{aid}')}"
            f"<label class='att-lbl' for='{_e(soort_id)}'>Grounding</label>"
            f"<select id='{_e(soort_id)}' name='soort'>"
            f"<option value=''>none (shows as ungrounded)</option>{opts}</select>"
            f"{_field('Reference (record / policy id)', 'ref', fid=f'feit-ref-{aid}')}"
            f"{_field('URL (for a cited source)', 'url', kind='url', fid=f'feit-url-{aid}')}"
            f"{_field('Quote', 'citaat', kind='textarea', fid=f'feit-citaat-{aid}')}"
            f"<div class='qadd-row'>"
            f"<button class='btn ok' type='submit' name='action' value='pagina_feit_add'>Add</button>"
            f"<button type='button' class='qadd-x' onclick=\"this.closest('details').open=false\" "
            f"aria-label='cancel'>✕</button></div></form></details>")


def _feiten_sectie(a, st, csrf_token: str, can_edit: bool) -> str:
    rijen = "".join(_feit_html(i, f, st, a.id, csrf_token, can_edit)
                    for i, f in enumerate(wiki.feiten(a)))
    rijen = rijen or ("<div class='muted'>No facts yet. A fact carries its own grounding: "
                      "a chronicle record, a certificate, a policy or a cited source.</div>")
    add = _feit_form(a.id, csrf_token) if can_edit else ""
    return f"<div class='wiki-inline'><h3>Facts</h3>{rijen}{add}</div>"


#: Een pagina die naar de coach wijst, krijgt het logboek eronder. Waarom aan de INHOUD opgehangen
#: en niet aan een titel of een rol-id: een titel is een naam die iemand herschrijft, en een rol-id
#: is precies het soort literal dat deze codebase vandaag twee keer uit de code heeft gehaald. Wat
#: blijft is de verwijzing zelf — wie de coach noemt, laat zien wat eruit kwam.
_COACH_URL = "/decision-coach"


def _besluiten_sectie(a, st, persoon: str = "") -> str:
    """De gelogde besluiten onder een pagina die naar de decision coach verwijst.

    AFGELEID BIJ HET LEZEN, NOOIT OPGESLAGEN — dezelfde vorm als `_feiten_sectie` en
    `_backlink_sectie` hierboven. De pagina bewaart geen kopie van een besluit: verdwijnt een rij
    uit het logboek of komt er een bij, dan klopt deze sectie de volgende pageload vanzelf. Een
    opgeslagen kopie zou uiteenlopen zonder dat iets zich meldt.

    Geen verwijzing naar de coach in de body → geen sectie. Zo bepaalt de pagina zelf of hij dit
    draagt, en hoeft er geen titel of rol-id in de code te staan."""
    from nooch_village import decision_sheets as ds
    from nooch_village.views.decision_coach import _KOPIEER_JS, kaarten, persoon_chips

    if _COACH_URL not in (a.body or ""):
        return ""
    data_dir = getattr(st, "dd", "") or ""
    rijen = ds.alle(data_dir) if data_dir else []
    getoond = [r for r in rijen if str(r.get("decider") or "") == persoon] if persoon else rijen
    chips = persoon_chips(rijen, persoon, basis=wiki.pagina_url(a.id))
    # De bestaande kopieer-JS gaat mee, anders is de Copy id-knop een knop die niets doet. Hij
    # staat één keer per pagina en is idempotent van opzet (event-delegatie op document).
    return (f"<div class='c2-sec'><h3>Decisions logged</h3>"
            f"<p class='muted'>Everyone in the circle can read these. The thinking report stays "
            f"private, in the chat of whoever did the session.</p>"
            f"{chips}{kaarten(getoond)}</div>{_KOPIEER_JS}")


def _backlink_sectie(a, pags: list) -> str:
    binnen = wiki.backlinks(a, pags)
    kaarten = "".join(
        f"<a href='{_e(wiki.pagina_url(b.id))}'>"
        f"<b>{_e(b.title or b.id)}</b><div class='muted'>{_e(b.id)}</div></a>" for b in binnen)
    kaarten = kaarten or "<div class='muted'>No page links here yet.</div>"
    ontbreekt = wiki.ontbrekende_links(a, pags)
    wens = ""
    if ontbreekt:
        # De verlanglijst: verwijzingen die nog nergens heen gaan. Zichtbaar, maar er wordt niets
        # automatisch aangemaakt — een pagina krijgt een eigenaar-rol, en dat is een besluit.
        wens = ("<p class='muted'>Wanted pages (referenced here, not written yet): "
                + ", ".join(f"<span class='chip muted'>{_e(r)}</span>" for r in ontbreekt) + "</p>")
    return f"<div class='wiki-inline'><h3>Links here</h3>{kaarten}{wens}</div>"


def _voorstel_form(st, a, csrf_token: str, *, next_url: str = "", prefill: str = "") -> str:
    """"Ik vind dat deze pagina Y moet zeggen" — voor wie de pagina niet bezit.

    Het loopt langs het bestaande verzoekmechanisme: het wordt een `naar_rol`-item in de inbox van
    de beslisser, met dezelfde drie knoppen (accepteren / aanpassen / weigeren). Hier staat alleen
    wie het krijgt en waarom, zodat niemand een verzoek de leegte in stuurt.

    `prefill` (scope 61, wiki_kennisborging.md — "wiki vóór archief"): komt een bezoeker hier via
    "→ To the wiki" op een projectrapport, dan is het rapport de tekst waar het om gaat, niet de
    huidige pagina-body. Leeg (het gewone geval) verandert er niets aan: dan vult het formulier
    zichzelf zoals altijd met `a.body`."""
    ontv = wiki.ontvanger(a.anchor, st.records, st.assign)
    rec = st.records.get(ontv["rol"])
    naar = _name(rec) if rec is not None else ontv["rol"]
    reden = f" ({_e(ontv['reden'])})" if ontv.get("reden") else ""
    return (f"<details class='qadd'><summary>✎ Suggest a change</summary>"
            f"<form method='post' action='/action' class='qadd-form'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"<input type='hidden' name='aid' value='{_e(a.id)}'>"
            # Terug naar waar je vandaan kwam: vanaf de Notes-tab is dat de tab, niet de
            # permalink. Je wordt niet verplaatst omdat je iets voorstelde.
            f"<input type='hidden' name='next' value='{_e(next_url or wiki.pagina_url(a.id))}'>"
            f"<p class='muted'>Goes to <strong>{_e(naar)}</strong>{reden}. "
            f"They accept, reshape or refuse — accepting saves your text as a new version.</p>"
            # De veld-ids dragen de artefact-id: op de Notes-tab staan meerdere pagina's onder
            # elkaar, en twee velden met dezelfde id laten elk gekoppeld label naar de eerste wijzen.
            f"{_field('Why', 'waarom', fid=f'vst-waarom-{a.id}', required=True, placeholder='one line: what is wrong now')}"
            f"{_field('Proposed text', 'voorstel', kind='textarea', value=(prefill or a.body), fid=f'vst-body-{a.id}')}"
            f"<div class='qadd-row'>"
            f"<button class='btn ok' type='submit' name='action' value='pagina_voorstel'>Send</button>"
            f"<button type='button' class='qadd-x' onclick=\"this.closest('details').open=false\" "
            f"aria-label='cancel'>✕</button></div></form></details>")


# ── De inline editor (21 september 2026) ─────────────────────────────────────────────────────
#
# WAT HIER WEG IS. Tot vandaag stond de opgemaakte tekst bovenaan in een kader, en opende "Edit
# page" daarONDER een tweede blok: een los TITLE-veld plus een textarea met de RUWE markdown
# (`## Four conditions`, `- **On the list.**`). Je las dus op de ene plek en typte op de andere,
# met dezelfde inhoud twee keer op het scherm — en je moest scrollen om van het een naar het ander
# te komen. Dat model is vervangen, niet verbeterd.
#
# WAT ERVOOR IN DE PLAATS KOMT. De tekst zelf wordt bewerkbaar, op de plek waar hij staat, met de
# opmaak zichtbaar terwijl je typt. Eén kopie op het scherm, en opslaan gebeurt waar je las.
#
# DE OPSLAG VERANDERT NIET. Wat de browser terugstuurt is HTML; `_md_naar_bron` (PR 2) maakt daar
# weer markdown van, en dat is wat in `AttachmentStore` belandt. Eén `artefact_edit`-actie, één
# `update()`, één versie-entry — precies als hiervoor.
#
# DE WERKBALK LEUNT OP `document.execCommand`. Geen editor-library: de opmaaktaal van `_md` telt
# zes constructies, en daar is een bibliotheek van tienduizenden regels een vreemde eend bij. De
# knoppen produceren `<strong>`/`<em>`/`<del>`/`<h4>`/`<ul>` — exact de tags die `_md_naar_bron`
# in zijn whitelist heeft staan.
#
# JS IS VEREIST, en dat is een besluit (Stefan, 21 september 2026), geen omissie. Er is bewust
# geen `<noscript>`-textarea als vangnet: twee bewerkpaden naast elkaar is precies wat deze
# vervanging moest opheffen.

def _meta_blok(a, eigenaar, csrf_token: str, can_edit: bool, records=None,
               *, tab: str = "notes", st=None, username: str | None = None) -> str:
    """Alle paginametadata als ÉÉN element, in het vocabulaire dat de app al heeft.

    WAT HIER WERD OPGELOST. De metadata stond als losse controls om de titel heen: het ID in de
    kop, de eigenaar als los tagje, en daarnaast een kale `<select>` met een knop ernaast. Gemeten
    in de browser, en dat verklaart waarom het rommelig oogde:

        select      onderlijn, hoogte 18px, 13.3px browser-font, padding 0
        Move page   volle rand, hoogte 30px, 12.8px, kapitalen
        Edit page   volle rand, hoogte 30px, 12.8px, kapitalen  ← identiek aan Move

    Drie dingen mis: de select stond niet op dezelfde voet als de knoppen, hij hield het
    browser-font, en de twee knoppen waren visueel even zwaar terwijl de één een structuurwijziging
    is en de ander de hoofdactie van de pagina.

    GEEN NIEUW VOCABULAIRE — dit is de hele opdracht. Wat de app al heeft:

        `.dcol` + `.dk`/`.dv`   sleutel-waarde-raster, in gebruik op de projectkaart
        `.fieldform`            een RIJ met een veld en een knop erin, mét eigen `.nu`-regel
        `.btn ghost`            de secundaire knop-variant, met een zachte rand
        `.card`                 het content-blok

    DE UITLEG ZIT ÍN DE CEL van zijn veld, niet eronder los. Daarmee groepeert het raster hem
    vanzelf onder de dropdown: één kolom, één onderwerp. Zelfde vorm bij de eigenaar, waar de
    governance-zin onder de rolnaam hangt.
    """
    from nooch_village.views.overview import _artefact_versions_html, _dt

    rijen = []

    def rij(sleutel: str, waarde: str, hint: str = "") -> None:
        h = f"<div class='muted wiki-hint'>{hint}</div>" if hint else ""
        rijen.append(f"<span class='dk'>{_e(sleutel)}</span>"
                     f"<span class='dv'>{waarde}{h}</span>")

    if eigenaar is not None:
        rij("Owner",
            f"<a href='/node?id={_e(a.anchor)}&tab={_e(tab)}'>{_e(_name(eigenaar))}</a>",
            "Everyone reads, this role curates.")
    # HET BAKJE ERBIJ, want dat is wat je op de index ZIET. Het domein is de sleutel
    # (`bibliotheek`), het bakje de plek; zonder die vertaling moet je de classificatietabel uit
    # je hoofd kennen om een keuze te kunnen maken. De records moeten mee: drie van de vijf
    # stappen van `bakje_van` hebben de recordboom nodig, en zonder valt elke pagina zonder eigen
    # domein terug op Overig — een hint die liegt is erger dan geen hint.
    from nooch_village import domeinen as _dom
    bakje, _waarom = _dom.bakje_van(a, list(records or []))
    waar = f"Where this page sits in the wiki structure &mdash; now: {_e(_dom.label(bakje))}"
    # `st` EN `username` REIZEN MEE, want wie het domein mag verzetten hangt sinds
    # 26 september af van wie het domein HOUDT — en dat staat in de records, niet in `a`.
    dom = _domein_form(a, eigenaar, csrf_token, can_edit, records,
                       st=st, username=username)
    if dom:
        rij("Domain", dom, waar)
    else:
        # Zonder bewerkrecht geen keuze, maar wél te lezen waar de pagina hangt.
        rij("Domain", _e(getattr(a, "domain", "") or "—"), waar)
    rij("Id", f"<code class='pill'>{_e(a.id)}</code>")
    rij("Last edited", _e(_dt(getattr(a, "updated_at", 0))))
    hist = _artefact_versions_html(a)
    if hist:
        rij("History", hist)
    # ARCHIVE EN DELETE, IN DE VOET. Ze horen bij de administratie van de pagina en niet bij de
    # inhoud, dus hier en niet in de kop — waar sinds #604 alleen de titel en de hoofdactie staan.
    rijen.append(_opruim_knoppen(a, csrf_token, can_edit, tab=tab))
    # `.wiki-meta` EN NIET `.card` (26 september 2026). Het blok staat sinds deze stap ONDER de
    # inhoud in plaats van boven, en daar is het een voet: een scheidingslijn met de administratie
    # eronder. Een kaart onderaan leest als nog een inhoudsblok, en dat is precies wat het niet is.
    # De rijen blijven hetzelfde `.dcol`-raster met `.dk`/`.dv`.
    return f"<div class='wiki-meta'><div class='dcol'>{''.join(rijen)}</div></div>"


def _opruim_knoppen(a, csrf_token: str, can_edit: bool, *, tab: str = "notes") -> str:
    """Archiveren en definitief verwijderen, als rij in het metadata-raster.

    ARCHIVE IS GEEN NIEUWE ACTIE. `artefact_archive` bestaat al sinds het artefact-model en werkt
    op elk soort artefact — een pagina is een note, dus hij kon dit altijd al; er was alleen nooit
    een knop. Een eigen `wiki_archive` zou een tweede weg naar dezelfde handeling zijn, precies
    wat het losse uploadformulier hierboven fout deed.

    DELETE IS DAT WÉL, want die bestond nergens voor artefacten. Hij heeft daarom een ZWAARDERE
    poort dan archiveren: archiveren mag de rolvervuller, weggooien alleen de Circle Lead —
    dezelfde verdeling als bij projecten, en om dezelfde reden: een pagina kan bewijs dragen waar
    iemand anders naar verwijst.

    GEEN KNOPPEN ZONDER RECHT. Wie niet mag bewerken, krijgt ze niet te zien; de server weigert
    ze daarna alsnog, maar een knop tonen die straks 403 geeft is een belofte die je niet nakomt.

    `.dellink` EN DE CONFIRM-TEKST komen letterlijk van `proj_delete` — dezelfde handeling hoort
    er hetzelfde uit te zien en hetzelfde te vragen.

    `.btn sm` EN NIET `.btn ghost sm` VOOR ARCHIVE, hoewel het ontwerpdocument "twee ghost-knoppen"
    zegt. Gemeten in Firefox: `ghost` tekent in deze app een 1px TRANSPARANTE rand — zichtbaar pas
    bij hover. Naast een `.dellink` levert dat twee dingen op die allebei als kale tekst lezen, en
    dan is er geen knop meer te zien in die cel. Ghost werkt als er een zwaardere knop náást staat
    (zo gebruikt #602 hem voor "Move page", náást "Edit page"); hier staat die er niet. De
    projectkaart, die het document als patroon aanwijst, gebruikt op deze plek ook `.btn sm`."""
    if not can_edit or not csrf_token:
        return ""
    verborgen = (f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                 f"<input type='hidden' name='aid' value='{_e(a.id)}'>"
                 f"<input type='hidden' name='next' value='/node?id={_e(a.anchor)}&tab={_e(tab)}'>")
    if getattr(a, "status", "active") == "archived":
        # AL GEARCHIVEERD: dan is archiveren geen keuze meer. Wat overblijft is weggooien.
        knoppen = (f"<span class='chip muted'>archived</span>"
                   f"<button class='dellink' type='submit' name='action' value='artefact_delete' "
                   f"onclick=\"return confirm('Delete permanently? This cannot be undone.')\">"
                   f"delete</button>")
    else:
        knoppen = (f"<button class='btn sm' type='submit' name='action' "
                   f"value='artefact_archive'>Archive</button>"
                   f"<button class='dellink' type='submit' name='action' value='artefact_delete' "
                   f"onclick=\"return confirm('Delete permanently? Archiving keeps the page.')\">"
                   f"Delete</button>")
    return (f"<span class='dk'>Clean up</span><span class='dv'>"
            f"<form method='post' action='/action' class='qadd-row'>{verborgen}{knoppen}</form>"
            f"<div class='muted wiki-hint'>Archiving hides the page and keeps its history. "
            f"Deleting removes it and its uploaded files for good.</div></span>")


def _domein_chip(a) -> str:
    """Het domein als vast label, voor wie het niet mag verzetten.

    LEZEN BLIJFT VRIJ, cureren niet — dezelfde domein-eigenaarschapsregel als voor de Library en
    het certificaten-register. Wie hier komt ziet dus wáár de pagina hangt, alleen zonder de
    keuzelijst en zonder de knop ernaast: een knop die de server daarna weigert, belooft iets wat
    niet kan."""
    return f"<span class='chip muted'>{_e(getattr(a, 'domain', '') or '—')}</span>"


def _mag_domein_wijzigen(a, st, username: str | None) -> bool:
    """Wie mag deze pagina naar een ander domein verplaatsen?

    DE REGEL ZELF STAAT IN `artefacts.mag_schrijven_op_domein`, sinds 26 september, want de
    server stelt bij elke schrijfactie dezelfde vraag over hetzelfde domein (`_artefact_gate`).
    Hier stond een tweede uitwerking van diezelfde regel; twee kopieën lopen na één wijziging
    uiteen, en dan geeft het scherm een ander antwoord dan de server — een veld dat je mag
    bedienen tot je erop drukt, of andersom.

    WAT HIER BLIJFT is de UI-terugval. Zonder `st`, zonder gebruiker, of bij een naam die het dorp
    niet kent, kan deze functie de vraag niet stellen; dan toont hij het veld en laat hij het
    oordeel aan de server. Dit bepaalt alleen wat je te zien krijgt — `_act_artefact_edit` toetst
    daarna alsnog.

    DE CIRKEL IS DIE VAN DE PAGINA. De Circle Lead van de cirkel waar de eigenaar-rol in hangt mag
    er sowieso bij, ook als het domein bij een rol in een andere cirkel hoort."""
    from nooch_village import artefacts
    from nooch_village.cockpit2 import resolve_circle_id

    if st is None or not username or username == "guest":
        return True
    actor = st.people.by_email(username)
    if actor is None:
        return True                       # onbekende gebruiker: `can_edit` heeft al geoordeeld
    return artefacts.mag_schrijven_op_domein(
        st, getattr(a, "domain", "") or "", actor.id,
        circle_id=resolve_circle_id(a.anchor, st.records) or "")


def _domein_form(a, eigenaar, csrf_token: str, can_edit: bool, records=None,
                 *, st=None, username: str | None = None) -> str:
    """De domein-keuze van deze pagina, in de kopbalk.

    EEN EIGEN FORMULIER, NAAST DE BLOK-EDITOR. De opslaan-balk van `wiki-form` verschijnt pas als
    je "Edit page" hebt geklikt; een keuzelijst die altijd zichtbaar is maar alleen dán opslaat,
    is een val — je verandert iets en er gebeurt niets. Dit formuliertje werkt altijd en raakt de
    editor niet aan.

    GEEN TWEEDE SCHRIJFPAD, want het stuurt DEZELFDE actie (`artefact_edit`) met dezelfde
    server-side poort. Dat een formulier met alleen een domein daar doorheen kan is geen toeval:
    `title`, `body` en `url` zijn er allemaal optioneel, en `update()` laat een veld dat `None` is
    met rust.

    Alleen voor een note: een policy en een tool worden bij de eigenaar-rol bewerkt, mét
    domein-veld (#585). Twee plekken voor dezelfde keuze is precies wat de leespagina van #574
    vermijdt."""
    from nooch_village.views.overview import _domain_field, _geen_domein_uitleg

    if not can_edit or not csrf_token or a.kind != wiki.PAGINA_KIND:
        return ""
    if not _mag_domein_wijzigen(a, st, username):
        return _domein_chip(a)
    rol_domeinen = list(getattr(getattr(eigenaar, "definition", None), "domains", None) or [])
    if not rol_domeinen:
        return _geen_domein_uitleg("file this page under it")
    veld = _domain_field(rol_domeinen, getattr(a, "domain", "") or "",
                         fid=f"f-domain-{a.id}", toon_label=False)
    # WAT DIT VELD DOET staat in de uitleg-regel die `_meta_blok` eronder zet, ín dezelfde
    # rastercel. Waarom het veld überhaupt blijft: gemeten op de 122 artefacten van prod
    # verschuiven 10 pagina's van bakje als het verdwijnt, zijn 11 policy-ID's uit de domeinslug
    # gemunt (en een ID is een permalink), en loggen 33 changelog-regels tegen `domain:<x>`.
    tip = "Moves this page to another part of the wiki. Does not change its text."
    # `.fieldform` EN NIET `.qadd-row`: dat is de klasse die de app al heeft voor "een veld en een
    # knop op één rij", inclusief een eigen `.nu`-regel die de onderlijn bij het VELD laat en niet
    # om de rij heen legt. `.qadd-row` is de knoppenbalk van een toevoegformulier; die stond hier
    # omdat er ooit alleen een knop stond.
    #
    # `ghost` OP DE KNOP. Gemeten stonden Move page en Edit page er identiek bij: zelfde rand,
    # zelfde hoogte, zelfde kapitalen. Twee even zware knoppen naast elkaar betekent dat geen van
    # beide de hoofdactie is. Verplaatsen is een structuurwijziging en secundair; `ghost` is de
    # variant die de app daar al voor heeft.
    #
    # DE UITLEG STAAT HIER NIET MEER. Hij zit in de cel van `_meta_blok`, onder het veld, zodat
    # het raster hem groepeert in plaats van dat hij los onder de rij hangt.
    return (f"<form method='post' action='/action' class='fieldform' title='{_e(tip)}'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"<input type='hidden' name='aid' value='{_e(a.id)}'>"
            f"<input type='hidden' name='next' value='{_e(wiki.pagina_url(a.id))}'>"
            f"{veld}"
            f"<button class='btn ghost sm' type='submit' name='action' value='artefact_edit' "
            f"title='{_e(tip)}'>Move page</button></form>")


def _wiki_editor(a, pags: list, csrf_token: str, can_edit: bool,
                 secties: dict[str, str] | None = None) -> str:
    """De tekst van de pagina — te lezen, en voor de eigenaar ook te bewerken op zijn plek."""
    # DE BLOKSTAND STAAT HIER AAN EN NERGENS ANDERS (brok 1, 22 september 2026). Dit is het
    # scherm waar je bewerkt; de Notes-tab op `/node` toont dezelfde tekst read-only en heeft de
    # blokken niet nodig. Visueel verandert er niets — een `<div>` op de plek van een `<br>`-regel
    # heeft dezelfde hoogte, en een lege regel houdt zijn `<br>`. Wat er wél is: elk blok is nu
    # een element met een soort, zodat brok 3 er een greep aan kan hangen.
    inhoud = _body_html(a.body, pags, blokken=True, secties=secties) if a.body else _GEEN_TEKST
    # DE SOORTEN-TABEL REIST MEE, als attribuut op de bewerk-container. De normaliseerpas in
    # `nooch.js` leest hem daar; zo bestaat de koppeling tag→bloksoort op precies één plek
    # (`cockpit2_util.BLOK_SOORTEN`) in plaats van ook nog eens in JS, waar geen test bij kan.
    soorten = _e(_json.dumps(BLOK_SOORTEN, separators=(",", ":"), sort_keys=True))
    # GEEN `.card` MEER OM DE TEKST (26 september 2026). De kaart tekende een rand met een eigen
    # vlak om de BODY, terwijl de titel erbuiten stond — en daarmee las een pagina als een kop met
    # een los kader eronder in plaats van als één document. Gemeten stond de titel bovendien op een
    # andere linkerrand dan de tekst (de kaartpadding zat ertussen).
    #
    # DE GOOT BLIJFT WEL. `.wiki-doc` in `render_pagina` draagt de inspringing die de kaart had,
    # zodat de blok-greep (`left:-1.5rem`, buiten de doos van `.wb`) nog ergens in past. Zonder
    # die ruimte hangt hij over de rand van de pagina.
    lees = (f"<div class='att-body wiki-body' id='wiki-body' "
            f"data-blok-soorten='{soorten}'>{inhoud}</div>")
    if not can_edit or not csrf_token:
        return lees

    # De verborgen velden worden bij het versturen door `nooch.js` gevuld met wat er in de twee
    # bewerkbare elementen staat. Het formulier staat ONDER de tekst maar is geen tweede kopie:
    # er staat niets in dat je kunt lezen, alleen de opslaan-balk.
    # DE LINK-KAART STAAT NAAST HET BEWERKVLAK, niet erin — zoals de werkbalk en het
    # blokmenu. Alles binnen `#wiki-body` gaat bij het opslaan mee als `body_html`.
    return (opmaak_werkbalk() + lees + blok_menu() + link_kaart()
            + f"<form method='post' action='/action' class='wiki-form' id='wiki-form' hidden>"
              f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
              f"<input type='hidden' name='aid' value='{_e(a.id)}'>"
              f"<input type='hidden' name='next' value='{_e(wiki.pagina_url(a.id))}'>"
              f"<input type='hidden' name='title' id='wiki-titel-veld' value=''>"
              f"<input type='hidden' name='body_html' id='wiki-body-veld' value=''>"
              f"<div class='qadd-row qadd-bar'>"
              f"<button class='btn ok sm' type='submit' name='action' value='artefact_edit'>"
              f"Save</button>"
              f"<button type='button' class='qadd-x' data-wiki-cancel aria-label='cancel'>✕</button>"
              f"<span class='muted wiki-hint'>Click in the text and type. Formatting stays visible."
              f"</span></div></form>")


def _artefact_pagina(st, a, csrf_token: str, username: str | None, msg: str) -> str:
    """De permalink van een policy of tool: een LEESPAGINA, geen tweede editor.

    WAAROM DIT EEN EIGEN PAGINA IS en niet de note-pagina met een ruimere `if`. Gemeten over de
    14 artefacten die op prod een dode link hadden: een policy heeft altijd een `domain` en nooit
    een url, een tool altijd een url en nooit een domein, en allebei hebben ze nul feiten en nul
    `[[links]]`. Drie dingen van de note-pagina passen hier dus niet:

      1. FEITEN leven in `meta["feiten"]`, en `artefacts._feiten_van` geeft voor een niet-note
         bewust een lege lijst. Een feiten-formulier hier zou feiten opleveren die de
         context-laag nooit leest.
      2. `[[LINKS]]` lossen op tegen `wiki.paginas`, en dat zijn notes. Een verwijzing vanuit een
         policy komt nergens op uit — `_artefact_body_html` zegt dat al.
      3. BEWERKEN gebeurt bij de eigenaar-rol, op het formulier dat daar staat. Een note is het
         tegenovergestelde geval (die wordt júist op zijn permalink bewerkt), en `_artefact_own_card`
         legt uit waarom je die twee niet allebei mag hebben: twee bewerkpaden voor hetzelfde
         object lopen uiteen zodra er aan één van de twee iets verandert.

    Punt 3 faalt bovendien STIL als je het negeert. `_act_artefact_edit` is niet op soort gepoort
    en zou een policy gewoon opslaan, maar `pagina_feit_add`, `pagina_feit_del` en
    `pagina_voorstel` zijn dat wél: die antwoorden met "✗ page not found". Een pagina die die
    formulieren toont, belooft iets wat de actie daarna weigert.

    Wat deze pagina dus wél doet: tonen wat er staat, met het veld erbij waar de soort om draait
    (het domein van een policy, de url van een tool), plus de versiehistorie en de weg naar de
    plek waar hij bewerkt wordt."""
    from nooch_village.views.overview import (_KIND_ICON, _artefact_versions_html,
                                              _can_edit_artefacts, _dt, _tab_for)

    eigenaar = st.records.get(a.anchor)
    can_edit = bool(eigenaar is not None
                    and _can_edit_artefacts(st, eigenaar, csrf_token, username))
    tab = _tab_for(a.kind)
    thuis = f"/node?id={_e(a.anchor)}&tab={_e(tab)}"

    eig_chip = (f" <a class='chip' href='{thuis}'>{_e(_name(eigenaar))}</a>"
                if eigenaar is not None else "")
    # Het domein hoort bij een policy zoals de url bij een tool: het is niet een extraatje maar
    # waar het ding aan hangt. Zelfde chip als op de kaart (`_artefact_head`), geen eigen variant.
    dom_chip = (f" <span class='chip muted'>{_e(a.domain)}</span>"
                if a.kind == "policy" and getattr(a, "domain", "") else "")

    # DEZELFDE VORM ALS DE NOTE-PAGINA (PR 2). Hiervóór droeg deze kop zijn eigen variant: het ID
    # vóór de titel, twee losse chips ernaast en een eigen herkomst-zin. Drie renderers met drie
    # koppen is precies hoe ze uit elkaar lopen; het metadata-blok is nu gedeeld.
    kop = (f"<div class='c2-bar'><a href='{thuis}'>← {_e(tab)}</a></div>"
           f"<h1>{_KIND_ICON.get(a.kind, '')} {_e(a.title or a.id)}</h1>"
           f"<div class='wiki-kopbalk'>"
           f"<p class='muted'>Edited on the owning role, not here &mdash; one place per "
           f"artefact.</p>"
           + (f"<a class='btn sm' href='{thuis}'>&#9998; Edit on the role</a>"
              if can_edit else "")
           + f"</div>")

    # De url is het punt van een tool: zonder hem is de pagina minder waard dan de kaart waar hij
    # vandaan komt. Zelfde vorm als daar.
    url_regel = (f"<div class='card'><div class='muted'>"
                 f"<a href='{_e(a.url)}' target='_blank' rel='noopener'>{_e(a.url)}</a>"
                 f"</div></div>" if a.kind == "tool" and getattr(a, "url", "") else "")

    # Kale markdown, geen `[[link]]`-oplossing: dit soort kent dat idioom niet (zie 2 hierboven).
    lees = (f"<div class='card'><div class='att-body'>"
            f"{_md(a.body) if a.body else _GEEN_TEKST}</div></div>")

    # DE METADATA STAAT ONDERAAN, net als op de note-pagina (26 september 2026). Drie renderers
    # met drie volgordes is precies hoe ze uit elkaar lopen.
    meta = _meta_blok(a, eigenaar, csrf_token, can_edit, st.records.all(),
                      tab=tab, st=st, username=username)
    main = (f"<div class='c2-main'>{kop}{_banner(msg)}{url_regel}{lees}{meta}</div>")
    return _page(f"{a.title or a.id} — {a.kind}",
                 f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")


def render_pagina(st, aid: str, csrf_token: str = "", username: str | None = None,
                  msg: str = "", persoon: str = "") -> str:
    """De permalink van een artefact. Een note krijgt de wiki-pagina (feiten, backlinks, de
    inline editor); een policy of tool de leespagina hierboven. Onbekend id of een soort die het
    dorp niet kent → nette melding, geen lege pagina.

    DE POORT IS `ARTEFACT_KINDS`, en met opzet niet een lijstje hier. Dat is dezelfde lijst waar
    `_WIKI_SOORTEN` zijn chips uit haalt, en juist het uiteenlopen van die twee was de bug: de
    index linkte policies en tools naar een pagina die alleen notes doorliet, goed voor 28 dode
    links naar 14 artefacten op prod. Komt er ooit een vierde soort bij, dan krijgt die hier
    automatisch een pagina in plaats van opnieuw een dode link."""
    from nooch_village.attachments import ARTEFACT_KINDS
    from nooch_village.views.overview import (_artefact_versions_html,
                                              _can_edit_artefacts, _dt)

    a = st.att.get(aid)
    if a is None or a.kind not in ARTEFACT_KINDS:
        main = ("<div class='c2-main'><div class='c2-bar'><a href='/'>← home</a></div>"
                "<h1>Page not found</h1><p class='muted'>There is no page with this id. "
                "A page is a note, policy or tool; open the role that owns it and use its "
                "Notes, Policies or Tools tab.</p></div>")
        return _page("Page not found", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
    if a.kind != wiki.PAGINA_KIND:
        return _artefact_pagina(st, a, csrf_token, username, msg)

    eigenaar = st.records.get(a.anchor)
    can_edit = bool(eigenaar is not None
                    and _can_edit_artefacts(st, eigenaar, csrf_token, username))
    pags = wiki.verwijsbaar(st.att)

    # De titel is een eigen element omdat hij BEWERKBAAR wordt, op zijn plek in de kop. Het losse
    # TITLE-veld onder aan de pagina is daarmee vervallen.
    titel = f"<span id='wiki-titel' class='wiki-titel'>{_e(a.title or a.id)}</span>"
    # HET ID STAAT NIET MEER IN DE KOP. Het is een interne sleutel, geen onderwerp, en het stond
    # vóór de titel — het eerste wat je las was techniek. Hij VERDWIJNT NIET: het ID wordt als
    # verwijzing gebruikt (in het ontwerpdocument zelf ook) en staat in `_meta_blok`.
    # DE KOP DRAAGT NOG ÉÉN DING: de hoofdactie. Alles wat metadata is — eigenaar, domein, ID,
    # laatst bewerkt, historie — staat in `_meta_blok`, in één raster, en sinds 26 september
    # ONDERAAN de pagina in plaats van hier direct onder de titel. Hiervóór stond de herkomst-zin
    # hier én de eigenaar in het blok: twee plekken voor hetzelfde, en dat is precies wat deze PR
    # opruimt.
    kop = (f"<div class='c2-bar'><a href='/node?id={_e(a.anchor)}&tab=notes'>← notes</a></div>"
           f"<h1>📄 {titel}</h1>")
    # GEEN "EDIT PAGE"-KNOP MEER (26 september 2026). Wie de pagina mag bewerken, bewerkt hem —
    # zoals een tekstverwerker: je klikt in de tekst en typt. De knop was de laatste rest van het
    # model "lezen is de stand, bewerken is een modus", en met hem verdwijnt ook de kopbalk die
    # alleen hém nog droeg.
    #
    # WAT NIET VERANDERT: zonder bewerkrecht blijft de pagina read-only. Dat is geen aparte tak
    # hier maar een gevolg — `_wiki_editor` rendert dan geen `#wiki-form`, en `nooch.js` zet zonder
    # dat formulier niets aan. De poort staat dus nog steeds op één plek.
    #
    # OPSLAAN BLIJFT EXPLICIET. Er is geen autosave; de opslaan-balk komt tevoorschijn zodra er
    # iets verandert. Zie `wikiEdit` in `nooch.js`.

    # DE TWEE AFGELEIDE SECTIES. Ze worden altijd gerenderd, maar landen op één van twee
    # plekken: in de tekst als de schrijver er een markering neerzette, anders eronder zoals ze
    # altijd stonden. Nooit allebei — twee keer dezelfde feiten op één scherm is precies de
    # verwarring die deze stap opruimt.
    secties = {"facts": _feiten_sectie(a, st, csrf_token, can_edit),
               "backlinks": _backlink_sectie(a, pags)}
    geplaatst = wiki.markers(a.body)
    #: Heeft deze sectie IETS te melden? Dat is een vraag over de inhoud, niet over het scherm,
    #: dus hij wordt hier één keer beantwoord en niet uit de HTML teruggelezen.
    gevuld = {"facts": bool(wiki.feiten(a)),
              "backlinks": bool(wiki.backlinks(a, pags) or wiki.ontbrekende_links(a, pags))}

    def _onder(k: str) -> str:
        """Wat er ONDERAAN de pagina bij komt — en dat is in twee gevallen niets.

        ZELF GEPLAATST: staat de markering in de tekst, dan landt de sectie dáár. Hem hier nog
        eens tonen zou dezelfde feiten twee keer op één scherm zetten.

        LEEG: een kopje "Facts" met "No facts yet" eronder is geen informatie maar meubilair. Op
        de 92 pagina's van prod heeft er vandaag nul een feit, dus dit stond op elke pagina — twee
        lege secties onder elke tekst, ongeacht of iemand ze ooit ging gebruiken.

        EN DIE TWEE MOGEN NIET SAMENVALLEN. Heeft de schrijver de sectie zélf via het blokmenu
        neergezet, dan blijft hij staan ook als hij nog leeg is: dat is bewuste plaatsing en dus
        een lege plek die op gevuld wacht, geen restant. Vandaar dat de leeg-regel alleen geldt
        voor de sectie die hier automatisch bij komt."""
        if k in geplaatst:
            return ""
        return secties[k] if gevuld[k] else ""

    body = _wiki_editor(a, pags, csrf_token, can_edit, secties)
    # Eigenaar bewerkt in de tekst zelf; ieder ander doet een voorstel. Geen csrf-token = geen
    # schrijf-sessie (publieke view), dan ook geen voorstelknop.
    voorstel = "" if can_edit else (_voorstel_form(st, a, csrf_token) if csrf_token else "")
    hist = _artefact_versions_html(a)

    # DE VOLGORDE BLIJFT ZOALS HIJ WAS: feiten, besluiten, backlinks. Ze in één klap achteraan
    # plakken scheelt twee regels en verschuift "Decisions logged" naar boven de feiten — een
    # wijziging die niemand vroeg, op een scherm dat verder niets van deze stap hoort te merken.
    # DE HISTORIE ZIT IN HET METADATA-BLOK, niet meer los onder de tekst: het is metadata over de
    # pagina, en dat hoort bij de rest ervan.
    #
    # EN HET BLOK STAAT ONDERAAN (26 september 2026). Het stond direct onder de titel, en daarmee
    # kreeg de administratie — eigenaar, domein, ID, laatst bewerkt, historie — de plek van de
    # inhoud: boven de vouw las je vijf regels techniek voor je bij de eerste zin was. Boven blijft
    # nu alleen de titel en de hoofdactie; alles wat OVER de pagina gaat staat eronder, na de
    # inhoud en na de twee afgeleide secties.
    meta = _meta_blok(a, eigenaar, csrf_token, can_edit, st.records.all(),
                      tab="notes", st=st, username=username)
    # HET LOSSE UPLOADFORMULIER IS WEG (26 september 2026). Het stond hier als `<details>` onder
    # de tekst en plakte zijn regel altijd ACHTER de body. Sinds "Afbeelding" en "Bestand" in het
    # blokmenu staan is dat de tweede weg naar dezelfde handeling — precies het risico dat de
    # code-comment bij dat formulier zélf al benoemde. Erger nog: het werd ingediend midden in een
    # bewerksessie, dus de server schreef in de OPGESLAGEN body en gooide je onbewaarde tekst weg.
    # ÉÉN DOORLOPEND DOCUMENT (26 september 2026). Titel, tekst en de afgeleide secties zitten in
    # hetzelfde omhulsel en delen dus één linkerrand en één vlak; de metadata-voet valt er met zijn
    # scheidingslijn vanzelf onder. Hiervoor stond de titel los bóven een omrande kaart, en dan
    # leest een pagina als twee dingen die toevallig onder elkaar staan.
    main = (f"<div class='c2-main'><div class='wiki-doc'>{kop}{_banner(msg)}{body}{voorstel}"
            f"{_onder('facts')}{_besluiten_sectie(a, st, persoon)}{_onder('backlinks')}"
            f"{meta}</div></div>")
    return _page(f"{a.title or a.id} — page",
                 f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")


# ── /wiki — de dorpsbrede index (fase 7) ─────────────────────────────────────
#
# Hiervóór was er geen index: je kwam bij een pagina via de Notes/Tools/Policies-tab van de rol die
# hem toevallig bezat. Dat werkt alleen als je al weet wie dat is. Het prototype (v15) zet alles op
# één scherm, gegroepeerd per domein, met een filter per soort — en dat kan zonder migratie, want
# `AttachmentStore.kind` onderscheidt note/tool/policy al en `by_kind` leest over alle anchors heen.
#
# GEEN TWEEDE WAARHEID OVER EIGENAARSCHAP. Het domein komt van de policy zelf (`a.domain`); een
# note of tool heeft er geen, en die staan onder "No domain yet" — precies zoals het prototype het
# toont. Wie een item mag wijzigen verandert niet: dat blijft de eigenaar-rol, via zijn eigen tab.

_WIKI_SOORTEN = (("all", "All"), ("policy", "Policy"), ("note", "Note"), ("tool", "Tool"))
_WIKI_ICOON = {"policy": "&#128193;", "note": "&#128196;", "tool": "&#128295;"}


def _wiki_items(st, soort: str = "all") -> list:
    """Alle artefacten van het dorp, nieuwste eerst, eventueel op soort gefilterd."""
    soorten = [k for k, _ in _WIKI_SOORTEN[1:]] if soort == "all" else [soort]
    uit = []
    for k in soorten:
        uit.extend(st.att.by_kind(k))
    return sorted(uit, key=lambda a: a.updated_at or a.created_at, reverse=True)


def _wiki_domein(a, records=None) -> str:
    """Het BAKJE waaronder dit item hoort, als weergavenaam.

    DIT LAS VROEGER ALLEEN `a.domain`, en dat veld was tot 23 september 2026 alleen voor policies
    gevuld: 110 van de 121 artefacten vielen daardoor samen in één "No domain yet"-bak. De index
    groepeerde dus wel, maar op iets dat er bijna nooit was.

    Nu komt het bakje uit `domeinen.bakje_van` — afgeleid bij het lezen, nergens opgeslagen. Een
    herclassificatie verschuift alle pagina's mee zonder migratie. Zonder records (oude
    aanroepers) valt hij terug op het kale domein, zodat niets stukgaat dat er al was."""
    if records is None:
        return (getattr(a, "domain", "") or "").strip()
    return domeinen.label(domeinen.bakje_van(a, records)[0])


#: De soorten die je vanuit de wiki zelf kunt starten.
#:
#: GEEN POLICY, EN DAT IS EEN KEUZE. Een policy is geen pagina die je schrijft maar een REGEL op
#: een domein dat een rol via governance bezit: `_act_artefact_add` eist dat het gekozen domein in
#: `definition.domains` van de eigenaar-rol staat, en weigert anders. Hier zou dat op twee manieren
#: misgaan. Een individuele actie (`ii:<cirkel>`) heeft helemaal geen rol en dus geen domeinen, dus
#: die combinatie kan niet bestaan. En bij een gewone rol zou de domeinlijst van stáp 2 (alle
#: domeinen van het dorp) botsen met de lijst waar de server op toetst (alleen die van de rol) —
#: dan bied je een keuze aan die daarna wordt geweigerd.
#:
#: Een policy heeft al een plek waar dat wél klopt: de Wiki-tab van de rol die het domein houdt.
_NIEUW_SOORTEN = (("note", "Page"), ("tool", "Tool"))


def _nieuwe_pagina_form(st, csrf_token: str, username: str | None) -> str:
    """"+ New page", vanuit de wiki zelf.

    WAAROM DIT HIER HOORT. Een pagina starten kon alleen via de cockpit van een rol, achter de
    poort van díé rol. Je moest dus eerst weten bij wie iets hoorde vóór je het kon opschrijven —
    precies andersom als hoe schrijven gaat.

    TWEE STAPPEN IN ÉÉN FORMULIER, en niet twee pagina's. De vragen zijn "van wie is dit?" en
    "waar in de navigatie?"; die staan hier als twee genummerde stappen onder elkaar. Twee
    round-trips zouden een half aangemaakte pagina of een sessie-state nodig hebben, en dat is
    machinerie voor een formulier met drie velden.

    DE DOMEINLIJST IS GEFILTERD OP WAT JE MÁG. Een domein dat een ander in beheer heeft, aanbieden
    en daarna weigeren is een knop die niet doet wat hij belooft; de zin eronder zegt waarom er
    minder staat dan je misschien verwacht."""
    from nooch_village import artefacts
    from nooch_village.views.wizard import _role_options

    if not csrf_token:
        return ""
    actor = st.people.by_email(username) if username and username != "guest" else None
    # "guest" (auth uit) mag alles, zoals overal in de cockpit; een onbekende naam mag niets.
    if actor is None and username != "guest":
        return ""
    aid = actor.id if actor is not None else ""

    alle = artefacts.alle_domeinen(st.records)
    mag = [d for d in alle
           if username == "guest" or artefacts.mag_schrijven_op_domein(st, d, aid)]
    opties = "".join(f"<option value='{_e(d)}'>{_e(d)}</option>" for d in mag)
    weg = len(alle) - len(mag)
    # AFGEVALLEN DOMEINEN KRIJGEN EEN REDEN. Stilzwijgend een kortere lijst tonen laat je zoeken
    # naar iets dat er hoort te zijn.
    uitleg = (f"<div class='muted wiki-hint'>{weg} domain(s) are not listed: another role owns "
              f"them, and only that role or its Circle Lead can file a page there.</div>"
              if weg else "")
    soorten = "".join(f"<option value='{_e(k)}'>{_e(lbl)}</option>" for k, lbl in _NIEUW_SOORTEN)
    return (f"<details class='qadd'><summary>+ New page</summary>"
            f"<form method='post' action='/action' class='qadd-form'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"<input type='hidden' name='action' value='artefact_add'>"
            # NAAR DE NIEUWE PAGINA, en de actie weet pas bíí het aanmaken welk id dat wordt —
            # vandaar een vlag in plaats van een url die hier al vastligt.
            f"<input type='hidden' name='naar_pagina' value='1'>"
            f"<input type='hidden' name='next' value='/wiki'>"
            f"<label class='att-lbl' for='np-owner'>1. Whose is this?</label>"
            f"<select id='np-owner' name='owner' required>{_role_options(st)}</select>"
            f"<label class='att-lbl' for='np-domain'>2. Where in the navigation?</label>"
            f"<select id='np-domain' name='domain'>"
            f"<option value=''>&mdash; no domain yet &mdash;</option>{opties}</select>{uitleg}"
            f"<label class='att-lbl' for='np-kind'>Kind</label>"
            f"<select id='np-kind' name='kind'>{soorten}</select>"
            f"{_field('Title', 'title', required=True, fid='np-title')}"
            f"{_field('Link (for a tool)', 'url', kind='url', fid='np-url')}"
            f"<div class='qadd-row'>"
            f"<button class='btn ok' type='submit'>Create</button>"
            f"<button type='button' class='qadd-x' onclick=\"this.closest('details').open=false\" "
            f"aria-label='cancel'>✕</button></div></form></details>")


def render_wiki_index(st, csrf_token: str = "", soort: str = "all",
                      username: str | None = None) -> str:
    """Alles wat het dorp heeft opgeschreven, op één scherm."""
    soort = soort if soort in {k for k, _ in _WIKI_SOORTEN} else "all"
    items = _wiki_items(st, soort)

    chips = "".join(
        f"<a class='cl-filter{' on' if soort == k else ''}' href='/wiki?kind={k}'>{_e(lbl)}</a>"
        for k, lbl in _WIKI_SOORTEN)

    # Linkerkolom: per domein, ingeklapt behalve de eerste. Native <details>, geen JS.
    # DE VOLGORDE IS DE WAARDEKETEN, niet het alfabet: de kolom leest van product naar klant en
    # daarna de ondersteunende functies, met Overig achteraan. Lege bakjes blijven weg — een kopje
    # waar nooit iets in zit is navigatie-ruis, en op prod zijn dat er vandaag twee.
    recs = st.records.all()
    per_bak: dict[str, list] = {}
    for a in items:
        per_bak.setdefault(domeinen.bakje_van(a, recs)[0], []).append(a)
    kolom = []
    for n, (sleutel, label) in enumerate(b for b in domeinen.BAKJES if per_bak.get(b[0])):
        rij = per_bak[sleutel]
        links = "".join(
            f"<li><a href='/pagina?id={_e(a.id)}'>{_e(a.title or a.id)} "
            f"<span class='pill'>{_e(a.kind)}</span></a></li>" for a in rij)
        kolom.append(f"<details{' open' if n == 0 else ''}><summary>{_e(label)} "
                     f"<span class='muted'>{len(rij)}</span></summary><ul class='clean'>{links}</ul></details>")
    nav = f"<nav class='wiki-doms'>{''.join(kolom) or ''}</nav>"

    kaarten = "".join(
        f"<div class='card'><div class='cl-head'>"
        f"<h3><a href='/pagina?id={_e(a.id)}'>{_WIKI_ICOON.get(a.kind, '')} {_e(a.title or a.id)}</a></h3>"
        f"<span class='kc-actions'><span class='pill'>{_e(a.kind)}</span>"
        + f"<span class='pill'>{_e(_wiki_domein(a, recs))}</span>"
        + f"</span></div>"
          f"<p class='muted'>Owner: {_e(_name(st.records.get(a.anchor)) if st.records.get(a.anchor) else a.anchor)}"
        + (f" &middot; {_e((a.body or '')[:120])}" if a.body else "") + "</p></div>"
        for a in items)
    if not kaarten:
        kaarten = ("<p class='muted'>Nothing written down yet. A policy, note or tool starts on the "
                   "role or circle that owns it &mdash; open its Wiki tab.</p>")

    main = (f"<div class='c2-main'><h1>Wiki</h1>"
            f"<p class='muted'>All policies, notes and tools from across the village &middot; "
            f"by domain where known. A page is editable by anyone unless it sits in a domain "
            f"another role owns.</p>"
            f"{_nieuwe_pagina_form(st, csrf_token, username)}"
            f"<div class='cl-filters'>{chips}</div>"
            f"<div class='c2-wiki'>{nav}<section>{kaarten}</section></div></div>")
    return _page("Wiki", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
