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

from nooch_village.web_base import _e, _page, _banner, _field
from nooch_village.cockpit2_util import _DS_LINK, _nav, _md, _name
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


def _body_html(body: str, pags: list) -> str:
    """De body als markdown, met `[[verwijzingen]]` omgezet in links.

    De substitutie draait NÁ `_md` (dus over ge-escapete HTML) en alleen hier — `_md` zelf wordt
    ook voor reacties en projectfeeds gebruikt, en die zijn geen wiki."""
    html = _md(body or "")

    def _sub(m):
        ref = _html_mod.unescape(m.group(1)).strip()
        doel = wiki.resolve(ref, pags)
        if doel is None:
            # Bestaat (nog) niet, of de titel is niet uniek: zichtbaar laten staan als
            # verlanglijst-item. Nooit stilzwijgend naar een gok linken, nooit automatisch
            # aanmaken — een pagina krijgt een eigenaar, en dat is een besluit.
            return f"<span class='chip muted' title='no unique page with this name'>{m.group(1)}</span>"
        return f"<a class='pill' href='{_e(wiki.pagina_url(doel.id))}'>{_e(doel.title or doel.id)}</a>"

    return wiki.LINK_RE.sub(_sub, html)


def _grond_chip(g: dict) -> str:
    icon = _STATUS_ICON.get(g["status"], "—")
    label = f"{icon} {_e(g['label'])}"
    if g["status"] == wiki.ONGECONTROLEERD and g["soort"] == "bron" and g["url"]:
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
    return (f"<details class='qadd'><summary>+ Add fact</summary>"
            f"<form method='post' action='/action' class='qadd-form'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"<input type='hidden' name='aid' value='{_e(aid)}'>"
            f"<input type='hidden' name='next' value='{_e(wiki.pagina_url(aid))}'>"
            f"{_field('Fact', 'tekst', required=True, fid='feit-tekst')}"
            f"<label class='att-lbl' for='feit-soort'>Grounding</label>"
            f"<select id='feit-soort' name='soort'>"
            f"<option value=''>none (shows as ungrounded)</option>{opts}</select>"
            f"{_field('Reference (record / policy id)', 'ref', fid='feit-ref')}"
            f"{_field('URL (for a cited source)', 'url', kind='url', fid='feit-url')}"
            f"{_field('Quote', 'citaat', kind='textarea', fid='feit-citaat')}"
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


def render_pagina(st, aid: str, csrf_token: str = "", username: str | None = None,
                  msg: str = "") -> str:
    """Eén wiki-pagina. Onbekende id of een ander artefact-soort → nette melding, geen lege pagina."""
    from nooch_village.views.overview import (_artefact_edit_form, _artefact_versions_html,
                                              _can_edit_artefacts, _dt)

    a = st.att.get(aid)
    if a is None or a.kind != wiki.PAGINA_KIND:
        main = ("<div class='c2-main'><div class='c2-bar'><a href='/'>← home</a></div>"
                "<h1>Page not found</h1><p class='muted'>There is no page with this id. "
                "A page is a role note; open a role and use its Notes tab.</p></div>")
        return _page("Page not found", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")

    eigenaar = st.records.get(a.anchor)
    can_edit = bool(eigenaar is not None
                    and _can_edit_artefacts(st, eigenaar, csrf_token, username))
    pags = wiki.paginas(st.att)

    eig_chip = ""
    if eigenaar is not None:
        eig_chip = (f" <a class='chip' href='/node?id={_e(a.anchor)}&tab=notes'>"
                    f"{_e(_name(eigenaar))}</a>")
    kop = (f"<div class='c2-bar'><a href='/node?id={_e(a.anchor)}&tab=notes'>← notes</a></div>"
           f"<h1>📄 <code class='pill'>{_e(a.id)}</code> {_e(a.title or a.id)}{eig_chip}</h1>"
           f"<p class='muted'>Owned by this role — everyone reads, the role curates. "
           f"Last edited: {_dt(getattr(a, 'updated_at', 0))}</p>")

    body = (f"<div class='card'><div class='att-body'>{_body_html(a.body, pags)}</div></div>"
            if a.body else "<div class='card muted'>This page has no text yet.</div>")
    bewerk = (_artefact_edit_form(a, csrf_token, next_url=wiki.pagina_url(a.id))
              if can_edit else "")
    hist = _artefact_versions_html(a)

    main = (f"<div class='c2-main'>{kop}{_banner(msg)}{body}{bewerk}{hist}"
            f"{_feiten_sectie(a, st, csrf_token, can_edit)}"
            f"{_backlink_sectie(a, pags)}</div>")
    return _page(f"{a.title or a.id} — page",
                 f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
