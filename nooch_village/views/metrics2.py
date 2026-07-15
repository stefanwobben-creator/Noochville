"""Metrieken 2 — het nieuwe catalogus-plus-dashboard-scherm (vervangt het oude metrics-scherm).

Deel 1: catalogus + favorieten (een 'favoriet' is een tegel (add_tile) op de node; het dashboard is
`tiles_of(node)`; de catalogus komt uit `_sources_for`, zelf-beschrijvend, met leesbare labels).
Deel 2: favorieten als échte grafiek-tegels (hergebruik `_render_tile`), globaal tijdvenster met
'vergelijk met de vorige periode', per-tegel weergave-schakelaar, kaart-omdraaien (ⓘ → definitie/bron).
Deel 3: segmentatie per tegel (dimensie wisselen). Deel 4: metric-vs-metric combo (staaf + lijn).

Twee ingangen, ÉÉN body (`_metrics2_body`):
- als node-tab (in de node-pagina, mét tabbar) via `render_metrics2_tab` — de primaire route;
- als losse volledige pagina via `render_metrics2` (`/metrics2?node=…`).
KPI's aanmaken gebeurt met de bestaande, rijke composer (`/kpi_new`); handmatige data-invoer blijft
onderaan behouden. Zo is niets van het oude scherm verloren.
"""
from __future__ import annotations

import time as _time

from nooch_village.web_base import _e, _page
from nooch_village.cockpit2_util import _DS_LINK, _BUILD, _name
from nooch_village.metrics import window_range
from nooch_village.views.metrics import (
    _sources_for, _default_form, _render_tile, _METRICS_JS,
    _MW, _MW_KEYS, _LIVE_TILE_SOURCES, _metrics_manage_html, _add_link_details,
)


def _post(action: str, node: str, label: str, cls: str, csrf: str, nxt: str, **fields) -> str:
    """Klein POST-formuliertje voor een tegel-actie (geen losse labels → ratchet-schoon). `nxt` bepaalt
    waar we na de actie terugkomen (de node-tab óf de losse pagina), zodat de context bewaard blijft."""
    hid = (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
           f"<input type='hidden' name='node' value='{_e(node)}'>"
           f"<input type='hidden' name='next' value='{_e(nxt)}'>")
    for k, v in fields.items():
        hid += f"<input type='hidden' name='{_e(k)}' value='{_e(str(v))}'>"
    return (f"<form method='post' action='/action' class='emo-f'>{hid}"
            f"<button class='{cls}' name='action' value='{action}'>{_e(label)}</button></form>")


def _star(action: str, node: str, csrf: str, nxt: str, faved: bool, **fields) -> str:
    """Favoriet-toggle als licht sterretje (geen knop met tekst): ★ = op je dashboard, ☆ = niet.
    De kleur draagt de staat (goud = favoriet), zodat de catalogus visueel rustig blijft."""
    glyph = "★" if faved else "☆"
    cls = "star on" if faved else "star"
    title = "van je dashboard halen" if faved else "op je dashboard zetten"
    hid = (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
           f"<input type='hidden' name='node' value='{_e(node)}'>"
           f"<input type='hidden' name='next' value='{_e(nxt)}'>")
    for k, v in fields.items():
        hid += f"<input type='hidden' name='{_e(k)}' value='{_e(str(v))}'>"
    return (f"<form method='post' action='/action' class='emo-f'>{hid}"
            f"<button class='{cls}' name='action' value='{action}' "
            f"aria-pressed='{'true' if faved else 'false'}' aria-label='favoriet' "
            f"title='{title}'>{glyph}</button></form>")


# ── weergave-schakelaar: welke vormen passen bij de aard van deze tegel ──────────
# Reeks (over tijd) → lijn/staaf/getal; categorie (uitsplitsing) → gestapeld/horizontaal;
# moment (één getal) → alleen getal. Één plek, spiegelt de Tufte-beslistabel uit het KPI-scherm.
_SERIES_DIMS = {"time", "over_tijd"}
_CAT_DIMS = {"country", "product", "keyword", "land", "kw", "path"}
_FORM_LABEL = {"trend": "Trend (lijn)", "staaf": "Staaf", "getal": "Getal",
               "gestapeld": "Gestapelde staaf", "horizontaal": "Horizontale balk",
               "bullet": "Bullet (waarde vs doel)", "doelmeter": "Doelmeter", "burnup": "Burn-up"}


def _forms_for(dim: str) -> list[str]:
    if dim in _SERIES_DIMS:
        return ["trend", "staaf", "getal"]
    if dim in _CAT_DIMS:
        return ["gestapeld", "horizontaal"]
    return ["getal"]


def _source_of(st, rec, sid: str):
    for s in _sources_for(st, rec):
        if s["id"] == sid:
            return s
    return None


def _series_dim(s: dict) -> str:
    """De reeks-dimensie (over tijd) die deze bron aanbiedt, of "" als de bron geen reeks kent."""
    dims = {d for d, _l in (s.get("dims") or [])}
    for cand in ("over_tijd", "time"):
        if cand in dims:
            return cand
    return ""


def _segment_menu(st, rec, node: str, tile: dict, csrf: str, nxt: str) -> str:
    """Segmentatie-schakelaar: wissel de dimensie van deze tegel (over tijd / per land / per product /
    totaal). Alleen tonen als de bron meer dan één dimensie aanbiedt."""
    s = _source_of(st, rec, tile.get("source"))
    dims = (s.get("dims") if s else None) or []
    if len(dims) < 2:
        return ""
    cur = tile.get("dim", "none")
    items = []
    for did, dl in dims:
        on = " on" if did == cur else ""
        items.append(_post("metrics2_dim", node, dl, f"menuitem{on}", csrf, nxt,
                           tid=tile.get("id", ""), dim=did, form=_default_form(did)))
    cur_lbl = dict(dims).get(cur, cur)
    return (f"<details class='cardmenu'><summary class='statustrigger' aria-label='segment kiezen'>"
            f"↔ {_e(cur_lbl)} <span class='caret'>▾</span></summary>"
            f"<div class='cardmenu-b'><div class='menu-h'>Segment</div>{''.join(items)}</div></details>")


def _compare_menu(st, rec, node: str, tile: dict, csrf: str, nxt: str) -> str:
    """Metric-vs-metric: koppel een tweede reeks als lijn over deze staven (combo, dubbele as). Alleen
    zinvol op een reeks-tegel (over tijd); anders verborgen. 'Geen' haalt de vergelijking eraf."""
    if tile.get("dim") not in _SERIES_DIMS:
        return ""
    cur = tile.get("cmp_measure") or ""
    items = [_post("metrics2_compare", node, "— geen —", "menuitem" + ("" if cur else " on"), csrf, nxt,
                   tid=tile.get("id", ""), cmp_source="", cmp_measure="", cmp_dim="")]
    for s in _sources_for(st, rec):
        sdim = _series_dim(s)
        if not sdim:
            continue
        for mid, ml in s["measures"]:
            if s["id"] == tile.get("source") and mid == tile.get("measure"):
                continue                                  # jezelf combineren heeft geen zin
            on = " on" if (cur == mid) else ""
            items.append(_post("metrics2_compare", node, f"{ml} · {s['label']}", f"menuitem{on}", csrf, nxt,
                               tid=tile.get("id", ""), cmp_source=s["id"], cmp_measure=mid, cmp_dim=sdim))
    if len(items) < 2:
        return ""
    lbl = "vergelijk" if not cur else f"vs {_e(cur)}"
    return (f"<details class='cardmenu'><summary class='statustrigger' aria-label='meting vergelijken'>"
            f"⇄ {lbl} <span class='caret'>▾</span></summary>"
            f"<div class='cardmenu-b'><div class='menu-h'>Vergelijk met</div>{''.join(items)}</div></details>")


def _weergave_menu(node: str, tile: dict, csrf: str, nxt: str) -> str:
    """Dropdown om de vorm van deze tegel te wisselen (POST → metrics2_form). Alleen tonen als er
    echt wat te kiezen valt (meer dan één passende vorm)."""
    dim = tile.get("dim", "none")
    opts = _forms_for(dim)
    cur = tile.get("form", "getal")
    if cur not in opts:                                    # onbekende/verouderde vorm blijft kiesbaar
        opts = [cur] + opts
    if len(opts) < 2:
        return ""
    items = []
    for f in opts:
        on = " on" if f == cur else ""
        items.append(_post("metrics2_form", node, _FORM_LABEL.get(f, f), f"menuitem{on}", csrf, nxt,
                           tid=tile.get("id", ""), form=f))
    cur_lbl = _FORM_LABEL.get(cur, cur)
    return (f"<details class='cardmenu'><summary class='statustrigger' aria-label='weergave kiezen'>"
            f"{_e(cur_lbl)} <span class='caret'>▾</span></summary>"
            f"<div class='cardmenu-b'><div class='menu-h'>Weergave</div>{''.join(items)}</div></details>")


def _catalog(st, rec, tiles, csrf: str, nxt: str) -> str:
    node = rec.id
    faved = {}
    for t in tiles:
        faved.setdefault((t.get("source"), t.get("measure")), t)
    groups = []
    for s in _sources_for(st, rec):
        cards = []
        for mid, ml in s["measures"]:
            tile = faved.get((s["id"], mid))
            segbaar = len(s.get("dims") or []) > 1
            seg = "<span class='chip'>segmenteerbaar</span>" if segbaar else ""
            if tile:
                btn = _star("metrics2_unfav", node, csrf, nxt, faved=True, tid=tile["id"])
            else:
                d0 = s["dims"][0][0] if s.get("dims") else "none"
                btn = _star("metrics2_fav", node, csrf, nxt, faved=False,
                            source=s["id"], measure=mid, dim=d0, form=_default_form(d0))
            cards.append(f"<div class='card'>{btn}<div class='rdr-sig'>{_e(ml)}</div>"
                         f"<div class='rdr-meta'><span class='muted'>{_e(s['label'])}</span> {seg}</div></div>")
        groups.append(f"<h2>{_e(s['label'])}</h2><div class='rdr-cards'>{''.join(cards)}</div>")
    return "".join(groups) or "<p class='muted'>Nog geen bronnen voor deze node.</p>"


def _window_bar(node: str, win: str, compare: bool, live: bool, base: str) -> str:
    """Globaal tijdvenster (Plausible-stijl dropdown) + 'vergelijk met de vorige periode'-schakelaar.
    Eén venster voor álle tegels; elke keuze is een reload-link (GET &mw=…&compare=…) op `base`."""
    cmp_q = "&compare=1" if compare else ""

    def opt(k, lbl):
        on = " on" if win == k else ""
        key = _MW_KEYS.get(k, "")
        kbd = f" <kbd>{_e(key)}</kbd>" if key else ""
        if k == "actueel" and not live:
            return (f"<span class='menuitem muted' title='alleen bij een live-capabele bron'>"
                    f"{_e(lbl)}{kbd}</span>")
        return f"<a class='menuitem{on}' href='{base}&mw={k}{cmp_q}'>{_e(lbl)}{kbd}</a>"

    active_lbl = dict(_MW).get(win, "Periode")
    dd = (f"<details class='cardmenu'><summary class='statustrigger' aria-label='periode kiezen'>"
          f"{_e(active_lbl)} <span class='caret'>▾</span></summary><div class='cardmenu-b'>"
          f"<div class='menu-h'>Periode</div>" + "".join(opt(k, lbl) for k, lbl in _MW) + "</div></details>")
    ct = " on" if compare else ""
    ct_url = f"{base}&mw={_e(win)}" + ("" if compare else "&compare=1")
    sw = (f"<span class='switch-field'>Vergelijk "
          f"<a class='switch{ct}' href='{ct_url}' role='switch' "
          f"aria-checked='{'true' if compare else 'false'}' title='vergelijk met de vorige periode'></a></span>")
    return f"<div class='cl-bar'><span class='muted'>Periode:</span> {dd}{sw}</div>"


def _favorites(st, rec, tiles, csrf: str, win: str, compare: bool, van: str, tot: str,
               nxt: str, editable: bool) -> str:
    node = rec.id
    if not tiles:
        if not editable:
            return "<p class='muted'>Nog geen metrieken op deze node.</p>"
        return ("<div class='rdr-tool'><p class='muted'>Nog niks op je dashboard. Zet hieronder een ster "
                "bij wat je wilt volgen.</p></div>")
    now = _time.time()
    start, end = window_range(win, now, van, tot)
    prev_win = None
    if compare and start is not None and end is not None:
        prev_win = (start - (end - start), start)         # vorige periode = zelfde lengte, teruggeschoven
    cells = []
    for t in tiles:
        # csrf="" bij _render_tile → geen ingebouwde verwijder-knop; onze eigen bediening staat eronder
        # (segment/weergave/vergelijk/verwijderen) zodat alles op dit scherm blijft.
        chart = _render_tile(st, rec, t, start, "", end=end, compare=compare, prev_win=prev_win,
                             actueel=(win == "actueel"), win=win, now=now)
        if not editable:
            cells.append(f"<div class='tile-wrap'>{chart}</div>")
            continue
        segment = _segment_menu(st, rec, node, t, csrf, nxt)
        weergave = "" if t.get("cmp_measure") else _weergave_menu(node, t, csrf, nxt)   # combo bepaalt de visual
        vergelijk = _compare_menu(st, rec, node, t, csrf, nxt)
        rm = _post("metrics2_unfav", node, "verwijderen", "dellink", csrf, nxt, tid=t.get("id", ""))
        ctrls = f"<div class='tile-foot-l'>{segment}{weergave}{vergelijk}</div>"
        foot = f"<div class='tile-foot'>{ctrls}<div class='tile-foot-r'>{rm}</div></div>"
        cells.append(f"<div class='tile-wrap'>{chart}{foot}</div>")
    return f"<div class='tile-grid'>{''.join(cells)}</div>"


def _metrics2_body(st, rec, csrf: str, win: str = "7d", compare: bool = False,
                   van: str = "", tot: str = "", base: str = "") -> str:
    """De gedeelde inhoud van het metrics-scherm (zonder pagina-chrome). `base` = de terugkeer-URL
    (node-tab óf losse pagina); `csrf` leeg → read-only lens (alleen de tegels, geen bediening)."""
    node = rec.id
    editable = bool(csrf)
    if not base:
        base = f"/metrics2?node={_e(node)}"
    nxt = f"{base}&mw={_e(win)}" + ("&compare=1" if compare else "")
    tiles = st.metrics.tiles_of(node)
    if not editable:                                        # read-only aggregatie-lens (bv. persoon)
        return _favorites(st, rec, tiles, "", win, compare, van, tot, nxt, editable=False)
    live = any((t.get("source") in _LIVE_TILE_SOURCES) or t.get("source", "").startswith("shopify")
               or t.get("source", "").startswith("werk:") for t in tiles)
    maak = (f"<a class='btn ok sm' href='/kpi_new?node={_e(node)}'>+ KPI maken</a>"
            f"{_add_link_details(rec, csrf, nxt)}")
    head = (f"<div class='cl-head'><h2>Mijn dashboard</h2><span class='kc-actions'>{maak}</span></div>")
    out = (f"{head}{_window_bar(node, win, compare, live, base)}"
           f"{_favorites(st, rec, tiles, csrf, win, compare, van, tot, nxt, editable=True)}"
           f"<h2>Catalogus</h2>{_catalog(st, rec, tiles, csrf, nxt)}"
           f"{_metrics_manage_html(st, rec, csrf)}{_METRICS_JS}")
    return out


def render_metrics2_tab(st, rec, csrf_token: str = "", win: str = "7d",
                        compare: bool = False, van: str = "", tot: str = "") -> str:
    """De metrics-NODE-TAB: dezelfde body, ingebed in de node-pagina (die levert de tabbar + h1).
    Terugkeer-URL = de node-tab, zodat elke actie op deze tab blijft."""
    base = f"/node?id={_e(rec.id)}&tab=metrics"
    return _metrics2_body(st, rec, csrf_token, win, compare, van, tot, base=base)


def render_metrics2_person(st, rec, base: str) -> str:
    """Read-only aggregatie-lens voor een persoonspagina: alleen de tegels van deze rol."""
    return _metrics2_body(st, rec, "", base=base)


def render_metrics2(st, rec, csrf_token: str = "", win: str = "7d",
                    compare: bool = False, van: str = "", tot: str = "") -> str:
    """De losse volledige pagina (`/metrics2?node=…`): dezelfde body met eigen pagina-chrome."""
    if rec is None:
        inner = (f"{_DS_LINK}<div class='c2-wrap'><div class='c2-main'>"
                 "<p class='muted'>Kies een cirkel of rol om metrieken voor te bekijken.</p></div></div>")
        return _page("Metrieken", inner)
    body = _metrics2_body(st, rec, csrf_token, win, compare, van, tot,
                          base=f"/metrics2?node={_e(rec.id)}")
    main = (f"<div class='c2-main'><h1>Metrieken — {_e(_name(rec))}</h1>"
            f"<p class='muted'>Scan de catalogus en zet een ster bij wat je wilt volgen. "
            f"Je hoeft niet te weten wat interessant is; het overzicht staat er.</p>{body}</div>")
    inner = (f"{_DS_LINK}<div class='bar'>cockpit 2 · GlassFrog (PoC) · build {_BUILD} · "
             "<a href='/'>home</a></div>"
             f"<div class='c2-wrap'>{main}</div>")
    return _page("Metrieken", inner)
