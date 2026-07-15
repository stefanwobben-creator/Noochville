"""Metrieken 2 — het nieuwe catalogus-plus-dashboard-scherm.

Deel 1: catalogus + favorieten (een 'favoriet' is een tegel (add_tile) op de node; het dashboard is
`tiles_of(node)`; de catalogus komt uit `_sources_for`, zelf-beschrijvend, met leesbare labels).
Deel 2: de favorieten renderen als échte grafiek-tegels (hergebruik van `_render_tile`), een globaal
tijdvenster met 'vergelijk met de vorige periode', per-tegel een weergave-schakelaar (vorm), en de
kaart-omdraaien (ⓘ → definitie + bron). Draait NAAST het bestaande metrics-scherm.
"""
from __future__ import annotations

import time as _time

from nooch_village.web_base import _e, _page
from nooch_village.cockpit2_util import _DS_LINK, _BUILD, _name
from nooch_village.metrics import window_range
from nooch_village.views.metrics import (
    _sources_for, _default_form, _render_tile, _grondslag, _METRICS_JS,
    _MW, _MW_KEYS, _LIVE_TILE_SOURCES,
)


def _post(action: str, node: str, label: str, cls: str, csrf: str, **fields) -> str:
    """Klein POST-formuliertje voor een tegel-actie (geen losse labels → ratchet-schoon)."""
    hid = (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
           f"<input type='hidden' name='node' value='{_e(node)}'>"
           f"<input type='hidden' name='next' value='/metrics2?node={_e(node)}'>")
    for k, v in fields.items():
        hid += f"<input type='hidden' name='{_e(k)}' value='{_e(str(v))}'>"
    return (f"<form method='post' action='/action' class='emo-f'>{hid}"
            f"<button class='{cls}' name='action' value='{action}'>{_e(label)}</button></form>")


def _star(action: str, node: str, csrf: str, faved: bool, **fields) -> str:
    """Favoriet-toggle als licht sterretje (geen knop met tekst): ★ = op je dashboard, ☆ = niet.
    De kleur draagt de staat (goud = favoriet), zodat de catalogus visueel rustig blijft."""
    glyph = "★" if faved else "☆"
    cls = "star on" if faved else "star"
    title = "van je dashboard halen" if faved else "op je dashboard zetten"
    hid = (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
           f"<input type='hidden' name='node' value='{_e(node)}'>"
           f"<input type='hidden' name='next' value='/metrics2?node={_e(node)}'>")
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


def _weergave_menu(node: str, tile: dict, csrf: str) -> str:
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
        items.append(_post("metrics2_form", node, _FORM_LABEL.get(f, f), f"menuitem{on}", csrf,
                           tid=tile.get("id", ""), form=f))
    cur_lbl = _FORM_LABEL.get(cur, cur)
    return (f"<details class='cardmenu'><summary class='statustrigger' aria-label='weergave kiezen'>"
            f"{_e(cur_lbl)} <span class='caret'>▾</span></summary>"
            f"<div class='cardmenu-b'><div class='menu-h'>Weergave</div>{''.join(items)}</div></details>")


def _catalog(st, rec, tiles, csrf: str) -> str:
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
                btn = _star("metrics2_unfav", node, csrf, faved=True, tid=tile["id"])
            else:
                d0 = s["dims"][0][0] if s.get("dims") else "none"
                btn = _star("metrics2_fav", node, csrf, faved=False,
                            source=s["id"], measure=mid, dim=d0, form=_default_form(d0))
            cards.append(f"<div class='card'>{btn}<div class='rdr-sig'>{_e(ml)}</div>"
                         f"<div class='rdr-meta'><span class='muted'>{_e(s['label'])}</span> {seg}</div></div>")
        groups.append(f"<h2>{_e(s['label'])}</h2><div class='rdr-cards'>{''.join(cards)}</div>")
    return "".join(groups) or "<p class='muted'>Nog geen bronnen voor deze node.</p>"


def _window_bar(node: str, win: str, compare: bool, live: bool) -> str:
    """Globaal tijdvenster (Plausible-stijl dropdown) + 'vergelijk met de vorige periode'-schakelaar.
    Eén venster voor álle tegels; elke keuze is een reload-link (GET &mw=…&compare=…)."""
    base = f"/metrics2?node={_e(node)}"
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
    return f"<div class='cl-bar'><span class='muted'>Periode</span> {dd}{sw}</div>"


def _favorites(st, rec, tiles, csrf: str, win: str, compare: bool, van: str, tot: str) -> str:
    node = rec.id
    if not tiles:
        return ("<div class='rdr-tool'><p class='muted'>Nog niks op je dashboard. Zet hieronder een ster "
                "bij wat je wilt volgen.</p></div>")
    now = _time.time()
    start, end = window_range(win, now, van, tot)
    prev_win = None
    if compare and start is not None and end is not None:
        prev_win = (start - (end - start), start)         # vorige periode = zelfde lengte, teruggeschoven
    cells = []
    for t in tiles:
        # csrf="" → geen ingebouwde verwijder-knop; wij zetten onderaan onze eigen bediening
        # (weergave-schakelaar + verwijderen van het dashboard) zodat 'verwijderen' op /metrics2 blijft.
        chart = _render_tile(st, rec, t, start, "", end=end, compare=compare, prev_win=prev_win,
                             actueel=(win == "actueel"), win=win, now=now)
        weergave = _weergave_menu(node, t, csrf)
        rm = _post("metrics2_unfav", node, "verwijderen", "dellink", csrf, tid=t.get("id", ""))
        foot = f"<div class='tile-foot'>{weergave}<div class='tile-foot-r'>{rm}</div></div>"
        cells.append(f"<div class='tile-wrap'>{chart}{foot}</div>")
    return f"<div class='tile-grid'>{''.join(cells)}</div>"


def render_metrics2(st, rec, csrf_token: str = "", win: str = "7d",
                    compare: bool = False, van: str = "", tot: str = "") -> str:
    """Bovenaan je favorieten als échte grafiek-tegels (met tijdvenster + vergelijken + weergave-
    schakelaar + kaart-omdraaien), daaronder de catalogus om uit te kiezen."""
    if rec is None:
        inner = (f"{_DS_LINK}<div class='c2-wrap'><div class='c2-main'>"
                 "<p class='muted'>Kies een cirkel of rol om metrieken voor te bekijken.</p></div></div>")
        return _page("Metrieken", inner)
    tiles = st.metrics.tiles_of(rec.id)
    live = any((t.get("source") in _LIVE_TILE_SOURCES) or t.get("source", "").startswith("shopify")
               or t.get("source", "").startswith("werk:") for t in tiles)
    main = (f"<div class='c2-main'><h1>Metrieken — {_e(_name(rec))}</h1>"
            f"<p class='muted'>Scan de catalogus en zet een ster bij wat je wilt volgen. "
            f"Je hoeft niet te weten wat interessant is; het overzicht staat er.</p>"
            f"<h2>Mijn dashboard</h2>{_window_bar(rec.id, win, compare, live)}"
            f"{_favorites(st, rec, tiles, csrf_token, win, compare, van, tot)}"
            f"<h2>Catalogus</h2>{_catalog(st, rec, tiles, csrf_token)}</div>")
    inner = (f"{_DS_LINK}<div class='bar'>cockpit 2 · GlassFrog (PoC) · build {_BUILD} · "
             "<a href='/'>home</a></div>"
             f"<div class='c2-wrap'>{main}</div>{_METRICS_JS}")
    return _page("Metrieken", inner)
