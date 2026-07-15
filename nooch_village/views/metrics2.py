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
    _MW, _MW_KEYS, _LIVE_TILE_SOURCES, _spark_svg, _fetch,
)

# Korte weergave-labels voor de segment-knoppen (prototype-stijl); de lange labels blijven elders.
_FORM_SHORT = {"trend": "lijn", "staaf": "staaf", "getal": "getal", "gestapeld": "gestapeld",
               "horizontaal": "balk", "bullet": "bullet", "doelmeter": "meter", "burnup": "burn-up"}
# Tijdvenster als segment-balk (prototype had 4-5 pillen i.p.v. een lange dropdown).
_M2_PERIODS = [("vandaag", "Vandaag"), ("7d", "7 dagen"), ("28d", "28 dagen"),
               ("kwartaal", "Kwartaal"), ("jaar", "Jaar")]
# Sub-tabs (Mijn dashboard / Catalogus) togglen + segment-selects submitten hun formulier.
_M2_JS = ("<script>(function(){"
          "var t=document.querySelectorAll('.js-m2');"
          "function show(w){document.querySelectorAll('[data-m2v]').forEach(function(v){"
          "v.hidden=v.getAttribute('data-m2v')!==w;});"
          "t.forEach(function(b){b.classList.toggle('on',b.getAttribute('data-m2')===w);});}"
          "t.forEach(function(b){b.addEventListener('click',function(){show(b.getAttribute('data-m2'));});});"
          "})();</script>")


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
_CAT_DIMS = {"country", "product", "keyword", "land", "kw", "path", "per_status", "per_type"}
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
    """Weergave-schakelaar als segment-knoppen (prototype-stijl): lijn / staaf / getal. Alleen tonen als
    er echt wat te kiezen valt (meer dan één passende vorm)."""
    dim = tile.get("dim", "none")
    opts = _forms_for(dim)
    cur = tile.get("form", "getal")
    if cur not in opts:                                    # onbekende/verouderde vorm blijft kiesbaar
        opts = [cur] + opts
    if len(opts) < 2:
        return ""
    btns = "".join(_post("metrics2_form", node, _FORM_SHORT.get(f, f), ("on" if f == cur else ""),
                         csrf, nxt, tid=tile.get("id", ""), form=f) for f in opts)
    return f"<span class='seg'>{btns}</span>"


def _formula_operand_opts(st, rec) -> list:
    """Reeks-metingen (over tijd) uit de catalogus als operand-opties voor een formule."""
    opts = []
    for s in _sources_for(st, rec):
        sd = _series_dim(s)
        if not sd:
            continue
        for mid, ml in s["measures"]:
            opts.append((f"{s['id']}|{mid}|{sd}", f"{ml} · {s['label']}"))
    return opts


def _formula_form(rec, csrf: str, nxt: str, opts: list) -> str:
    """'+ Formule': maak van twee bestaande reeks-metingen een eigen KPI (A op B per dag, bv. conversie
    = orders ÷ bezoekers). Rekent live en fail-closed via de bestaande formule-tegel."""
    if len(opts) < 2:
        return ""
    o = "".join(f"<option value='{_e(v)}'>{_e(l)}</option>" for v, l in opts)
    ops = "".join(f"<option>{x}</option>" for x in ("÷", "×", "+", "−"))
    return (f"<details class='m-add'><summary class='btn sm'>+ Formule</summary>"
            f"<form method='post' action='/action' class='m-addform'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
            f"<input type='hidden' name='node' value='{_e(rec.id)}'>"
            f"<input type='hidden' name='next' value='{_e(nxt)}'>"
            f"<input type='hidden' name='f_agg' value='gemiddelde'>"
            f"<select name='f_a' aria-label='meting A'>{o}</select>"
            f"<select name='f_op' aria-label='bewerking'>{ops}</select>"
            f"<select name='f_b' aria-label='meting B'>{o}</select>"
            f"<input name='f_name' placeholder='Naam (bijv. Conversie)' autocomplete='off'>"
            f"<button class='btn ok sm' type='submit' name='action' value='metrics2_formula'>"
            f"Formule maken</button></form></details>")


def _spark(st, rec, s: dict, mid: str) -> str:
    """Mini-sparkline van de echte data op een catalogus-kaart (prototype: je ziet de trend vóór je
    favoriet zet). Geen reeks/geen data → leeg (de kaart houdt z'n hoogte via CSS)."""
    sd = _series_dim(s)
    if not sd:
        return ""
    try:
        res = _fetch(st, s["id"], mid, sd, None, None)
    except Exception:
        return ""
    pts = res.get("points") or [] if isinstance(res, dict) else []
    return _spark_svg(pts, 210, 30) if len(pts) >= 2 else ""


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
            if tile:
                star = _star("metrics2_unfav", node, csrf, nxt, faved=True, tid=tile["id"])
            else:
                d0 = s["dims"][0][0] if s.get("dims") else "none"
                star = _star("metrics2_fav", node, csrf, nxt, faved=False,
                             source=s["id"], measure=mid, dim=d0, form=_default_form(d0))
            cards.append(f"<div class='catcard'>{star}<div class='nm'>{_e(ml)}</div>"
                         f"<div class='src'>{_e(s['label'])}</div>"
                         f"<div class='spark'>{_spark(st, rec, s, mid)}</div></div>")
        groups.append(f"<div class='catgroup'><h3>{_e(s['label'])}</h3>"
                      f"<div class='catgrid'>{''.join(cards)}</div></div>")
    return "".join(groups) or "<p class='muted'>Nog geen bronnen voor deze node.</p>"


def _window_bar(node: str, win: str, compare: bool, live: bool, base: str) -> str:
    """Tijdvenster als segment-balk (prototype-stijl) + 'vergelijk met de vorige periode'-schakelaar.
    Eén venster voor álle tegels; elke keuze is een reload-link (GET &mw=…&compare=…) op `base`."""
    cmp_q = "&compare=1" if compare else ""
    pills = "".join(f"<a class='{'on' if win == k else ''}' href='{base}&mw={k}{cmp_q}'>{_e(l)}</a>"
                    for k, l in _M2_PERIODS)
    seg = f"<span class='seg'>{pills}</span>"
    ct = " on" if compare else ""
    ct_url = f"{base}&mw={_e(win)}" + ("" if compare else "&compare=1")
    sw = (f"<span class='switch-field'>Vergelijk "
          f"<a class='switch{ct}' href='{ct_url}' role='switch' "
          f"aria-checked='{'true' if compare else 'false'}' title='vergelijk met de vorige periode'></a></span>")
    return f"<div class='cl-bar'><span class='muted'>Periode:</span> {seg}{sw}</div>"


def _favorites(st, rec, tiles, csrf: str, win: str, compare: bool, van: str, tot: str,
               nxt: str, editable: bool) -> str:
    node = rec.id
    if not tiles:
        if not editable:
            return "<p class='muted'>Nog geen metrieken op deze node.</p>"
        return ("<div class='m2empty'><span class='big'>☆</span>Nog niks op je dashboard.<br>"
                "Zet een ster in de catalogus.</div>")
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
        is_formule = t.get("form") == "formule" or t.get("source") == "formule"
        segment = "" if is_formule else _segment_menu(st, rec, node, t, csrf, nxt)
        # combo of formule bepaalt zelf de visual → geen losse weergave-keuze
        weergave = "" if (t.get("cmp_measure") or is_formule) else _weergave_menu(node, t, csrf, nxt)
        vergelijk = "" if is_formule else _compare_menu(st, rec, node, t, csrf, nxt)
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
            f"{_formula_form(rec, csrf, nxt, _formula_operand_opts(st, rec))}")
    # Twee sub-tabs zoals in het prototype: 'Mijn dashboard' (met telling) en 'Catalogus'. Standaard
    # open je op je dashboard; heb je nog niks, dan opent de catalogus zodat je meteen kunt kiezen.
    show_dash = bool(tiles)
    subtabs = (f"<div class='subtabs'>"
               f"<button type='button' class='subtab js-m2{' on' if show_dash else ''}' data-m2='dash'>"
               f"Mijn dashboard <span class='chip'>{len(tiles)}</span></button>"
               f"<button type='button' class='subtab js-m2{'' if show_dash else ' on'}' data-m2='cat'>"
               f"Catalogus</button></div>")
    dash = (f"<div data-m2v='dash'{'' if show_dash else ' hidden'}>"
            f"<div class='cl-head'><span class='muted'>Je dashboard</span>"
            f"<span class='kc-actions'>{maak}</span></div>"
            f"{_window_bar(node, win, compare, live, base)}"
            f"{_favorites(st, rec, tiles, csrf, win, compare, van, tot, nxt, editable=True)}</div>")
    cat = (f"<div data-m2v='cat'{' hidden' if show_dash else ''}>"
           f"{_catalog(st, rec, tiles, csrf, nxt)}</div>")
    return f"{subtabs}{dash}{cat}{_M2_JS}{_METRICS_JS}"


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
