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
from nooch_village.cockpit2_util import (_DS_LINK, _nav, _md, _name, opmaak_werkbalk,
                                         BLOK_SOORTEN, blok_menu)
from nooch_village import wiki

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


def _body_html(body: str, pags: list, blokken: bool = False) -> str:
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
        lambda m: (f"<li class='wb-taak'><input type='checkbox' disabled"
                   f"{' checked' if m.group(1).lower() == 'x' else ''}>"),
        html)

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

    return wiki.LINK_RE.sub(_sub, html)


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
    return (f"<div class='card'><div class='ptitle'>{_e(feit.get('tekst') or '')}</div>"
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
    rijen = rijen or ("<div class='card muted'>No facts yet. A fact carries its own grounding: "
                      "a chronicle record, a certificate, a policy or a cited source.</div>")
    add = _feit_form(a.id, csrf_token) if can_edit else ""
    return f"<div class='c2-sec'><h3>Facts</h3>{rijen}{add}</div>"


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
        f"<a class='card' href='{_e(wiki.pagina_url(b.id))}'>"
        f"<b>{_e(b.title or b.id)}</b><div class='muted'>{_e(b.id)}</div></a>" for b in binnen)
    kaarten = kaarten or "<div class='card muted'>No page links here yet.</div>"
    ontbreekt = wiki.ontbrekende_links(a, pags)
    wens = ""
    if ontbreekt:
        # De verlanglijst: verwijzingen die nog nergens heen gaan. Zichtbaar, maar er wordt niets
        # automatisch aangemaakt — een pagina krijgt een eigenaar-rol, en dat is een besluit.
        wens = ("<p class='muted'>Wanted pages (referenced here, not written yet): "
                + ", ".join(f"<span class='chip muted'>{_e(r)}</span>" for r in ontbreekt) + "</p>")
    return f"<div class='c2-sec'><h3>Links here</h3>{kaarten}{wens}</div>"


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

def _wiki_editor(a, pags: list, csrf_token: str, can_edit: bool) -> str:
    """De tekst van de pagina — te lezen, en voor de eigenaar ook te bewerken op zijn plek."""
    # DE BLOKSTAND STAAT HIER AAN EN NERGENS ANDERS (brok 1, 22 september 2026). Dit is het
    # scherm waar je bewerkt; de Notes-tab op `/node` toont dezelfde tekst read-only en heeft de
    # blokken niet nodig. Visueel verandert er niets — een `<div>` op de plek van een `<br>`-regel
    # heeft dezelfde hoogte, en een lege regel houdt zijn `<br>`. Wat er wél is: elk blok is nu
    # een element met een soort, zodat brok 3 er een greep aan kan hangen.
    inhoud = _body_html(a.body, pags, blokken=True) if a.body else _GEEN_TEKST
    # DE SOORTEN-TABEL REIST MEE, als attribuut op de bewerk-container. De normaliseerpas in
    # `nooch.js` leest hem daar; zo bestaat de koppeling tag→bloksoort op precies één plek
    # (`cockpit2_util.BLOK_SOORTEN`) in plaats van ook nog eens in JS, waar geen test bij kan.
    soorten = _e(_json.dumps(BLOK_SOORTEN, separators=(",", ":"), sort_keys=True))
    lees = (f"<div class='card'><div class='att-body wiki-body' id='wiki-body' "
            f"data-blok-soorten='{soorten}'>{inhoud}</div></div>")
    if not can_edit or not csrf_token:
        return lees

    # De verborgen velden worden bij het versturen door `nooch.js` gevuld met wat er in de twee
    # bewerkbare elementen staat. Het formulier staat ONDER de tekst maar is geen tweede kopie:
    # er staat niets in dat je kunt lezen, alleen de opslaan-balk.
    return (opmaak_werkbalk() + lees + blok_menu()
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

    kop = (f"<div class='c2-bar'><a href='{thuis}'>← {_e(tab)}</a></div>"
           f"<h1>{_KIND_ICON.get(a.kind, '')} <code class='pill'>{_e(a.id)}</code> "
           f"{_e(a.title or a.id)}{dom_chip}{eig_chip}</h1>"
           f"<div class='wiki-kopbalk'>"
           f"<p class='muted'>Edited on the owning role, not here &mdash; one place per artefact. "
           f"Last edited: {_dt(getattr(a, 'updated_at', 0))}</p>"
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

    main = (f"<div class='c2-main'>{kop}{_banner(msg)}{url_regel}{lees}"
            f"{_artefact_versions_html(a)}</div>")
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
    pags = wiki.paginas(st.att)

    eig_chip = ""
    if eigenaar is not None:
        eig_chip = (f" <a class='chip' href='/node?id={_e(a.anchor)}&tab=notes'>"
                    f"{_e(_name(eigenaar))}</a>")
    # De titel is een eigen element omdat hij BEWERKBAAR wordt, op zijn plek in de kop. Het losse
    # TITLE-veld onder aan de pagina is daarmee vervallen.
    titel = f"<span id='wiki-titel' class='wiki-titel'>{_e(a.title or a.id)}</span>"
    kop = (f"<div class='c2-bar'><a href='/node?id={_e(a.anchor)}&tab=notes'>← notes</a></div>"
           f"<h1>📄 <code class='pill'>{_e(a.id)}</code> {titel}{eig_chip}</h1>"
           f"<div class='wiki-kopbalk'>"
           f"<p class='muted'>Owned by this role — everyone reads, the role curates. "
           f"Last edited: {_dt(getattr(a, 'updated_at', 0))}</p>"
           + (f"<button type='button' class='btn sm' data-wiki-start>✎ Edit page</button>"
              if can_edit else "")
           + f"</div>")

    body = _wiki_editor(a, pags, csrf_token, can_edit)
    # Eigenaar bewerkt in de tekst zelf; ieder ander doet een voorstel. Geen csrf-token = geen
    # schrijf-sessie (publieke view), dan ook geen voorstelknop.
    voorstel = "" if can_edit else (_voorstel_form(st, a, csrf_token) if csrf_token else "")
    hist = _artefact_versions_html(a)

    main = (f"<div class='c2-main'>{kop}{_banner(msg)}{body}{voorstel}{hist}"
            f"{_feiten_sectie(a, st, csrf_token, can_edit)}"
            f"{_besluiten_sectie(a, st, persoon)}"
            f"{_backlink_sectie(a, pags)}</div>")
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


def _wiki_domein(a) -> str:
    """Het domein waaronder dit item hoort. Leeg → de verzamelgroep."""
    return (getattr(a, "domain", "") or "").strip()


def render_wiki_index(st, csrf_token: str = "", soort: str = "all") -> str:
    """Alles wat het dorp heeft opgeschreven, op één scherm."""
    soort = soort if soort in {k for k, _ in _WIKI_SOORTEN} else "all"
    items = _wiki_items(st, soort)

    chips = "".join(
        f"<a class='cl-filter{' on' if soort == k else ''}' href='/wiki?kind={k}'>{_e(lbl)}</a>"
        for k, lbl in _WIKI_SOORTEN)

    # Linkerkolom: per domein, ingeklapt behalve de eerste. Native <details>, geen JS.
    per_domein: dict[str, list] = {}
    for a in items:
        per_domein.setdefault(_wiki_domein(a) or "No domain yet", []).append(a)
    kolom = []
    for n, (dom, rij) in enumerate(sorted(per_domein.items(), key=lambda kv: (kv[0] == "No domain yet", kv[0]))):
        links = "".join(
            f"<li><a href='/pagina?id={_e(a.id)}'>{_e(a.title or a.id)} "
            f"<span class='pill'>{_e(a.kind)}</span></a></li>" for a in rij)
        kolom.append(f"<details{' open' if n == 0 else ''}><summary>{_e(dom)} "
                     f"<span class='muted'>{len(rij)}</span></summary><ul class='clean'>{links}</ul></details>")
    nav = f"<nav class='wiki-doms'>{''.join(kolom) or ''}</nav>"

    kaarten = "".join(
        f"<div class='card'><div class='cl-head'>"
        f"<h3><a href='/pagina?id={_e(a.id)}'>{_WIKI_ICOON.get(a.kind, '')} {_e(a.title or a.id)}</a></h3>"
        f"<span class='kc-actions'><span class='pill'>{_e(a.kind)}</span>"
        + (f"<span class='pill'>{_e(_wiki_domein(a))}</span>" if _wiki_domein(a) else
           "<span class='pill muted'>no domain</span>")
        + f"</span></div>"
          f"<p class='muted'>Owner: {_e(_name(st.records.get(a.anchor)) if st.records.get(a.anchor) else a.anchor)}"
        + (f" &middot; {_e((a.body or '')[:120])}" if a.body else "") + "</p></div>"
        for a in items)
    if not kaarten:
        kaarten = ("<p class='muted'>Nothing written down yet. A policy, note or tool starts on the "
                   "role or circle that owns it &mdash; open its Wiki tab.</p>")

    main = (f"<div class='c2-main'><h1>Wiki</h1>"
            f"<p class='muted'>All policies, notes and tools from across the village &middot; "
            f"by domain where known. Edit an item where it lives: on its owning role or circle.</p>"
            f"<div class='cl-filters'>{chips}</div>"
            f"<div class='c2-wiki'>{nav}<section>{kaarten}</section></div></div>")
    return _page("Wiki", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
