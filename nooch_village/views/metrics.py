"""Metrics/KPI-views — brok 8 van de cockpit2-split."""
from __future__ import annotations

import json
import os
import re
from typing import TYPE_CHECKING

from nooch_village.web_base import _e, _page, _banner
from nooch_village.cockpit2_util import (
    _name, _fmt_due, _bron_html,
    _IC_INFO, _IC_LINK, _IC_DL,
)
from nooch_village.metric_schema import (
    CADANS_LABEL, MEETTYPE_LABEL, MEETWIJZE_LABEL,
    VERIFICATIE_LABEL, AGGREGATIE, AGGREGATIE_LABEL,
)
from nooch_village.metrics import window_cutoff, window_range, filter_samples
from nooch_village.observations import ObservationStore
from nooch_village.i18n import t
from nooch_village import org
from nooch_village.cockpit2_util import _EXTRA_CSS, _BUILD

if TYPE_CHECKING:
    from nooch_village.cockpit2 import _Stores


# Centrale periode-picker (scope 6). 'actueel' = laatste waarde, alleen bij een live-capabele bron.
_MW = [("vandaag", "Vandaag"), ("gisteren", "Gisteren"), ("actueel", "Actueel"),
       ("7d", "7 dagen"), ("28d", "28 dagen"), ("kwartaal", "Kwartaal"),
       ("jaar", "Jaar"), ("aangepast", "Aangepast")]
# Bronnen die 'live' bevraagd kunnen worden → 'Actueel' beschikbaar (anders uitgegrijsd).
_LIVE_TILE_SOURCES = {"pulse_visitors", "shopify"}
# Bron-KPI's: meetbaar uit bestaande dorpsdata (AI/agents schrijven hier al naartoe).
_SOURCE_KPIS = {"pulse_visitors": {"name": "Websitebezoekers (per dag)", "unit": "bezoekers"}}


def _source_samples(dd: str, source: str):
    """Lees samples voor een bron-KPI. Twee HELDER onderscheiden reeksen (niet meer één 'pulse_visitors'
    die twee dingen betekent):
      - `pulse_visitors`     → de DAGREEKS (visitors_day, bron=plausible) uit observations.jsonl;
      - `pulse_visitors_7d`  → de rollende 7d-total (visitors_7d) uit pulse_history.jsonl (legacy snapshot).
    """
    if source == "pulse_visitors":
        store = ObservationStore(os.path.join(dd, "observations.jsonl"))
        return [{"at": r["ts"], "value": r["value"]}
                for r in store.daily_series("visitors_day", bron="plausible")]
    if source == "pulse_visitors_7d":
        repo = os.path.join(os.path.dirname(__file__), "..", "..", "data", "pulse_history.jsonl")
        out = []
        for p in (os.path.join(dd, "pulse_history.jsonl"), repo):
            if not os.path.exists(p):
                continue
            try:
                for line in open(p):
                    line = line.strip()
                    if not line:
                        continue
                    d = json.loads(line)
                    v = d.get("visitors_7d")
                    if v is not None and d.get("ts"):
                        out.append({"at": float(d["ts"]), "value": float(v)})
            except Exception:
                pass
            if out:
                break
        return out
    return []


def _metric_points(st: _Stores, item: dict, cutoff, end=None):
    samples = _source_samples(st.dd, item["source"]) if item.get("source") else item.get("samples", [])
    return filter_samples(samples, cutoff, end)


def _spark_svg(points, w=84, h=22, breaks_at=None) -> str:
    vals = [v for _, v in points]
    if len(vals) < 2:
        return "<span class='muted' style='font-size:.7rem'>—</span>"
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1
    n = len(vals)
    pts = " ".join(f"{(i / (n - 1)) * w:.1f},{h - ((v - lo) / rng) * h:.1f}" for i, v in enumerate(vals))
    # reeksbreuk(en): een gestreepte verticale lijn waar de definitie-versie wisselt
    marks = ""
    for idx in (breaks_at or []):
        if 0 < idx < n:
            x = (idx / (n - 1)) * w
            marks += (f"<line x1='{x:.1f}' y1='0' x2='{x:.1f}' y2='{h}' stroke='var(--coral)' "
                      f"stroke-width='1' stroke-dasharray='2 2'/>")
    return (f"<svg class='spark' viewBox='0 0 {w} {h}' width='{w}' height='{h}' preserveAspectRatio='none'>"
            f"<polyline points='{pts}' fill='none' stroke='var(--green)' stroke-width='1.5'/>{marks}</svg>")


def _break_indices(samples) -> list:
    """Indexen (in op-tijd-gesorteerde samples) waar de definitie-versie (defv) omhoog springt."""
    sv = sorted(samples or [], key=lambda s: s.get("at", 0))
    out, prev = [], None
    for i, s in enumerate(sv):
        dv = s.get("defv")
        if prev is not None and dv is not None and dv != prev:
            out.append(i)
        prev = dv if dv is not None else prev
    return out


def _line_chart_svg(points, unit: str = "", prev=None) -> str:
    """Echt lijn-diagram (server-side SVG, cockpit2-stijl): x=datum, y=waarde, met leesbare assen.
    Alleen de echte dagpunten als stippen, verbonden — geen interpolatie van ontbrekende dagen.
    `prev` (vorige periode) → een tweede, lichtere gestreepte lijn over dezelfde breedte + y-schaal.
    0 punten → nette 'geen data'; 1 punt → 'te weinig voor een lijn' (nooit een vlakke lijn)."""
    if not points:
        return (f"<div class='kpi-val'><span class='muted' style='font-size:.9rem'>"
                f"{_e(t('dashboard.geen_data_periode'))}</span></div>")
    import datetime as _dt
    vals = [v for _, v in points]
    if len(points) < 2:
        return (f"<div class='tile-trend'><span class='kpi-val sm'>{_num(vals[-1])}</span>"
                f"<span class='muted' style='font-size:.7rem'>1 meetpunt — te weinig voor een lijn</span></div>")
    prev = prev or []
    W, H = 300.0, 140.0
    ml, mr, mt, mb = 36.0, 8.0, 10.0, 20.0            # marges: links y-labels, onder x-labels
    iw, ih = W - ml - mr, H - mt - mb
    xs = [t for t, _ in points]
    x0, x1 = xs[0], xs[-1]
    xspan = (x1 - x0) or 1.0
    allvals = vals + [v for _, v in prev]
    ymax = max(allvals)
    ymin = min(0, min(allvals))                       # 0-basislijn (of lager bij negatieve waarden)
    yspan = (ymax - ymin) or 1.0
    fx = lambda t: ml + (t - x0) / xspan * iw
    fy = lambda v: mt + (1 - (v - ymin) / yspan) * ih
    axis = (f"<line x1='{ml:.1f}' y1='{mt:.1f}' x2='{ml:.1f}' y2='{mt+ih:.1f}' stroke='var(--border)' stroke-width='1'/>"
            f"<line x1='{ml:.1f}' y1='{mt+ih:.1f}' x2='{ml+iw:.1f}' y2='{mt+ih:.1f}' stroke='var(--border)' stroke-width='1'/>")
    ylab = (f"<text x='{ml-4:.1f}' y='{fy(ymax)+3:.1f}' text-anchor='end' font-size='9' fill='var(--muted)'>{_num(ymax)}</text>"
            f"<text x='{ml-4:.1f}' y='{fy(ymin)+3:.1f}' text-anchor='end' font-size='9' fill='var(--muted)'>{_num(ymin)}</text>")
    fmt = lambda t: _dt.datetime.fromtimestamp(t).strftime('%d-%m')
    xlab = (f"<text x='{ml:.1f}' y='{H-5:.1f}' text-anchor='start' font-size='9' fill='var(--muted)'>{_e(fmt(x0))}</text>"
            f"<text x='{ml+iw:.1f}' y='{H-5:.1f}' text-anchor='end' font-size='9' fill='var(--muted)'>{_e(fmt(x1))}</text>")
    prevline = ""
    if len(prev) >= 2:                                # vorige periode: over dezelfde breedte, lichter+gestreept
        pxs = [t for t, _ in prev]
        pspan = (pxs[-1] - pxs[0]) or 1.0
        pfx = lambda t: ml + (t - pxs[0]) / pspan * iw
        ppoly = " ".join(f"{pfx(t):.1f},{fy(v):.1f}" for t, v in prev)
        prevline = f"<polyline points='{ppoly}' fill='none' stroke='var(--subtle)' stroke-width='1.2' stroke-dasharray='3 3'/>"
    poly = " ".join(f"{fx(t):.1f},{fy(v):.1f}" for t, v in points)
    line = f"<polyline points='{poly}' fill='none' stroke='var(--green)' stroke-width='1.8'/>"
    dots = "".join(f"<circle cx='{fx(t):.1f}' cy='{fy(v):.1f}' r='2.2' fill='var(--green)'/>" for t, v in points)
    u = f" <span class='kpi-unit'>{_e(unit)}</span>" if unit else ""
    head = f"<div class='tile-trend'><span class='kpi-val sm'>{_num(vals[-1])}{u}</span></div>"
    svg = (f"<svg class='linechart' viewBox='0 0 {W:.0f} {H:.0f}' width='100%' height='140' preserveAspectRatio='xMidYMid meet'>"
           f"{axis}{ylab}{xlab}{prevline}{line}{dots}</svg>")
    return head + svg


def _kpi_card(st: _Stores, item: dict, cutoff, csrf: str, *, provider=False, circle="") -> str:
    pts = _metric_points(st, item, cutoff)
    val = f"{pts[-1][1]:g}" if pts else "—"
    unit = f" <span class='kpi-unit'>{_e(item.get('unit', ''))}</span>" if item.get("unit") else ""
    prov = ""
    if provider:
        r = st.records.get(item["node"])
        prov = f"<div class='kpi-prov muted'>levert: {_e(_name(r) if r else item['node'])}</div>"
    src = " <span class='chip muted'>auto</span>" if item.get("source") else ""
    # handmatige meting toevoegen (alleen niet-bron KPI's, met csrf)
    add = ""
    if csrf and not item.get("source"):
        add = (f"<form method='post' action='/action' class='kpi-add'>"
               f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
               f"<input type='hidden' name='mid' value='{_e(item['id'])}'>"
               f"<input type='hidden' name='next' value='/node?id={_e(item['node'])}&tab=metrics'>"
               f"<input name='value' inputmode='decimal' placeholder='meting' size='6'>"
               f"<button class='btn ok sm' type='submit' name='action' value='m_sample'>+</button></form>")
    pin = ""
    if csrf and circle:
        pinned = st.metrics.is_pinned(circle, item["id"])
        act = "m_unpin" if pinned else "m_pin"
        lbl = "losmaken" if pinned else "+ dashboard"
        pin = (f"<form method='post' action='/action' style='display:inline'>"
               f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
               f"<input type='hidden' name='mid' value='{_e(item['id'])}'>"
               f"<input type='hidden' name='circle' value='{_e(circle)}'>"
               f"<input type='hidden' name='next' value='/node?id={_e(circle)}&tab=metrics'>"
               f"<button class='flink' type='submit' name='action' value='{act}'>{lbl}</button></form>")
    rm = ""
    if csrf and not circle:
        rm = (f"<form method='post' action='/action' style='display:inline'>"
              f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
              f"<input type='hidden' name='mid' value='{_e(item['id'])}'>"
              f"<input type='hidden' name='next' value='/node?id={_e(item['node'])}&tab=metrics'>"
              f"<button class='dellink' type='submit' name='action' value='m_remove'>✕</button></form>")
    return (f"<div class='kpi-card'><div class='kpi-h'><span class='kpi-name'>{_e(item['name'])}{src}</span>{rm}</div>"
            f"<div class='kpi-body'><span class='kpi-val'>{val}{unit}</span>{_spark_svg(pts)}</div>"
            f"{prov}<div class='kpi-foot'>{add}{pin}</div></div>")


def _link_card(item: dict, csrf: str) -> str:
    rm = ""
    if csrf:
        rm = (f"<form method='post' action='/action' style='display:inline'>"
              f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
              f"<input type='hidden' name='mid' value='{_e(item['id'])}'>"
              f"<input type='hidden' name='next' value='/node?id={_e(item['node'])}&tab=metrics'>"
              f"<button class='dellink' type='submit' name='action' value='m_remove'>✕</button></form>")
    return (f"<div class='kpi-card kpi-link'><div class='kpi-h'>"
            f"<a href='{_e(item['url'])}' target='_blank' rel='noopener'>{_IC_LINK} {_e(item['name'])}</a>{rm}</div></div>")


def _metric_add_forms(st: _Stores, rec, csrf: str) -> str:
    base = f"/node?id={_e(rec.id)}&tab=metrics"
    src_opts = "".join(f"<option value='source:{k}'>{_e(v['name'])} (uit data)</option>"
                       for k, v in _SOURCE_KPIS.items())
    kpi = (f"<form method='post' action='/action' class='m-addform'>"
           f"<input type='hidden' name='csrf' value='{_e(csrf)}'><input type='hidden' name='node' value='{_e(rec.id)}'>"
           f"<input type='hidden' name='next' value='{base}'>"
           f"<label class='att-lbl'>KPI uit lijst of nieuw</label>"
           f"<select name='pick'><option value='manual'>Nieuwe KPI (handmatig)</option>{src_opts}</select>"
           f"<input name='name' placeholder='Naam (bij handmatig)' autocomplete='off'>"
           f"<input name='unit' placeholder='Eenheid (bijv. €, %, stuks)' autocomplete='off'>"
           f"<button class='btn ok sm' type='submit' name='action' value='m_add_kpi'>KPI toevoegen</button></form>")
    link = (f"<form method='post' action='/action' class='m-addform'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf)}'><input type='hidden' name='node' value='{_e(rec.id)}'>"
            f"<input type='hidden' name='next' value='{base}'>"
            f"<label class='att-lbl'>Link naar extern bestand</label>"
            f"<input name='name' placeholder='Naam' autocomplete='off'>"
            f"<input name='url' placeholder='https://…' autocomplete='off'>"
            f"<button class='btn sm' type='submit' name='action' value='m_add_link'>Link toevoegen</button></form>")
    return (f"<details class='m-add'><summary class='btn ok sm'>+ Metric</summary>"
            f"<div class='m-addgrid'>{kpi}{link}</div></details>")


def _shopify_window(dd: str):
    """Het 'alles'-venster uit shopify_metrics.json (snapshot met paren/orders/omzet/land/product)."""
    repo = os.path.join(os.path.dirname(__file__), "..", "..", "data", "shopify_metrics.json")
    for p in (os.path.join(dd, "shopify_metrics.json"), repo):
        if not os.path.exists(p):
            continue
        try:
            d = json.load(open(p))
            ws = d.get("windows") or {}
            return ws.get("0") or (list(ws.values())[0] if ws else None)
        except Exception:
            return None
    return None


def _sources_for(st: _Stores, rec):
    """Zelf-beschrijvende bron-catalogus voor de tegel-wizard: elke bron declareert measures + dims.
    Op een cirkel tellen ook de handmatige KPI's van de onderliggende rollen mee."""
    is_c = org.is_circle(rec)
    srcs = [
        {"id": "pulse_visitors", "label": "Websitebezoekers",
         "measures": [("visitors", "Bezoekers (per dag)")], "dims": [("time", "over tijd")]},
        {"id": "shopify", "label": "Verkoop",
         "measures": [("pairs_sold", "Paren verkocht"), ("orders", "Orders"),
                      ("revenue", "Omzet"), ("aov", "Gem. orderwaarde")],
         "dims": [("none", "totaal"), ("over_tijd", "over tijd"),
                  ("country", "per land"), ("product", "per product")]},
    ]
    # Werkoverleg-gezondheid (facilitator): leest het archief van de cirkel waar deze node onder valt.
    circle = rec.id if is_c else getattr(rec, "parent", None)
    if circle:
        srcs.append({"id": f"werk:{circle}", "label": "Werkoverleg",
                     "measures": [("tevredenheid", "Tevredenheid"), ("spanningen", "Spanningen verwerkt"),
                                  ("informatie", "Informatie verwerkt"), ("projecten", "Projecten"),
                                  ("acties", "Acties"), ("duur", "Duur (min)"),
                                  ("roloverleg", "Naar roloverleg"), ("nevermind", "Laat maar"),
                                  ("afwezigheid", "Afwezigheid")],
                     "dims": [("gemiddeld", "gemiddeld per overleg"), ("totaal", "totaal"),
                              ("over_tijd", "over tijd")]})
    nodes = [rec.id] + ([r.id for r in org.roles_of(st.records.all(), rec.id)] if is_c else [])
    for k in st.metrics.kpis_for_nodes(nodes):
        if k.get("source"):
            continue                                  # bron-KPI's al gedekt door built-ins
        srcs.append({"id": f"kpi:{k['id']}", "label": k["name"],
                     "measures": [("value", k["name"])], "dims": [("time", "over tijd")]})
    return srcs


_WERK_MEASURE = {"spanningen": "behandeld", "informatie": "info", "projecten": "projecten",
                 "acties": "acties", "tevredenheid": "tevredenheid", "duur": "duur_min",
                 "roloverleg": "roloverleg", "nevermind": "nevermind", "afwezigheid": "afwezig"}


def _werk_fetch(st: _Stores, circle: str, measure: str, dim: str, cutoff, end=None):
    key = _WERK_MEASURE.get(measure, "behandeld")
    samples = []
    for m in st.werk.log(circle):
        v = m.get(key)
        if key == "afwezig":
            v = len(v or [])          # lijst afwezigen → aantal
        if v is None:
            continue
        samples.append({"at": m.get("at", 0), "value": v})
    # Alle werkoverleg-tegels respecteren dezelfde periodefilter als de reeks-tegels: filter op
    # het venster vóór het aggregeren (gemiddeld/totaal), niet alleen bij de reeks.
    pts = filter_samples(samples, cutoff, end)     # [(at, value), ...] binnen het venster
    vals = [v for _, v in pts]
    unit = "/10" if measure == "tevredenheid" else ("min" if measure == "duur" else "")
    if dim == "over_tijd":
        return {"kind": "series", "points": pts, "unit": unit}
    if dim == "totaal" and measure != "tevredenheid":
        return {"kind": "number", "value": (sum(vals) if vals else None), "unit": unit}
    avg = round(sum(vals) / len(vals), 1) if vals else None   # gemiddeld (en tevredenheid-totaal)
    return {"kind": "number", "value": avg, "unit": unit}


def _default_form(dim: str) -> str:
    return {"time": "trend", "none": "getal"}.get(dim, "verdeling")


def _tile_combos(sources):
    out = []
    for s in sources:
        for mid, ml in s["measures"]:
            for did, dl in s["dims"]:
                out.append((f"{s['id']}|{mid}|{did}", f"{s['label']}: {ml} · {dl}", _default_form(did)))
    return out


def _tile_meta(st: _Stores, rec, tile) -> str:
    for s in _sources_for(st, rec):
        if s["id"] == tile["source"]:
            ml = dict(s["measures"]).get(tile["measure"], tile["measure"])
            dl = dict(s["dims"]).get(tile.get("dim", "none"), tile.get("dim", ""))
            return f"{s['label']}: {ml} · {dl}"
    return tile.get("measure", "metric")


def _measure_unit(source: str, measure: str) -> str:
    if source == "pulse_visitors":
        return "bezoekers"
    if source.startswith("werk:"):
        return "/10" if measure == "tevredenheid" else ("min" if measure == "duur" else "")
    if source == "shopify":
        return "EUR" if measure in ("revenue", "aov") else ("paren" if measure == "pairs_sold" else "")
    return ""


def _daily_obs_series(st: _Stores, source: str, measure: str, cutoff, end=None):
    """Dezelfde dagreeks-route als de bezoekers-tegel: leest de dag-observaties (daily_series) voor
    (source, measure) en levert een series-res voor het lijn-diagram (chart:'line'). None als deze
    bron/measure geen dag-observatie-mapping heeft. Lege dagreeks → lege points (→ 'geen data')."""
    metric, bron = _daily_obs_key(source, measure)
    if not metric:
        return None
    samples = [{"at": r["ts"], "value": r["value"]}
               for r in st.observations.daily_series(metric, bron=bron)]
    return {"kind": "series", "points": filter_samples(samples, cutoff, end),
            "unit": _measure_unit(source, measure), "chart": "line"}


def _fetch(st: _Stores, source: str, measure: str, dim: str, cutoff, end=None):
    """Haal de data voor een tegel op binnen [cutoff, end]. Resultaat: series/breakdown/number."""
    if source == "pulse_visitors":
        # De "over tijd"-reeks komt uit de dagelijkse observaties (bron=plausible), één datapunt per
        # dag → een echte dagreeks voor het lijn-diagram.
        return _daily_obs_series(st, source, measure, cutoff, end)
    if source == "shopify":
        if dim == "over_tijd":                       # dagreeks uit de observaties (leeg tot Shopify live is)
            return _daily_obs_series(st, source, measure, cutoff, end)
        w = _shopify_window(st.dd) or {}
        if dim == "country":
            return {"kind": "breakdown", "rows": [(c, n) for c, n in w.get("by_country", [])]}
        if dim == "product":
            return {"kind": "breakdown", "rows": [(p, n) for p, n in w.get("top_products", [])]}
        unit = "EUR" if measure in ("revenue", "aov") else ("paren" if measure == "pairs_sold" else "")
        return {"kind": "number", "value": w.get(measure), "unit": unit}
    if source.startswith("werk:"):
        if dim == "over_tijd":
            s = _daily_obs_series(st, source, measure, cutoff, end)
            if s is not None and s["points"]:        # dagreeks heeft data → nieuwe route
                return s
            # UITFASEREN: zolang de dagreeks (nog) leeg is, val terug op de oude log-aggregaat-route,
            # zodat er geen blinde periode ontstaat. Hard verwijderen pas als de nieuwe route vult.
        return _werk_fetch(st, source[5:], measure, dim, cutoff, end)
    if source.startswith("kpi:"):
        it = st.metrics.get(source[4:])
        if not it:
            return {"kind": "number", "value": None, "unit": ""}
        raw = _source_samples(st.dd, it["source"]) if it.get("source") else it.get("samples", [])
        return {"kind": "series", "points": filter_samples(raw, cutoff, end), "unit": it.get("unit", "")}
    return {"kind": "number", "value": None, "unit": ""}


def _num(v):
    return f"{v:g}" if isinstance(v, (int, float)) else "—"


def _agg(res):
    if res["kind"] == "series":
        return res["points"][-1][1] if res.get("points") else None
    if res["kind"] == "breakdown":
        return sum(n for _, n in res.get("rows", [])) if res.get("rows") else None
    return res.get("value")


def _render_bullet(res, target, richting, benchmark="") -> str:
    """Bullet graph (Few): waarde-balk + doel-tick + een 'goed'-zone, richtingbewust. Vervangt de
    vlakke doelmeter: toont in één balk waar je staat t.o.v. het doel, met de benchmark als label."""
    v = _agg(res)
    try:
        t = float(target)
    except (TypeError, ValueError):
        t = 0.0
    if not isinstance(v, (int, float)) or t <= 0:
        return _render_form(res, "doelmeter", target)   # val terug op de simpele meter
    down = richting == "down"          # lager = beter (CO2, bounce): goed-zone ligt onder het doel
    M = max(t * 1.25, v * 1.1, t + 1)
    W, H = 240.0, 26.0
    fx = lambda x: max(0.0, min(1.0, x / M)) * W
    # goed-zone: t..M (hoger=beter) of 0..t (lager=beter)
    gx0, gx1 = (fx(t), W) if not down else (0.0, fx(t))
    good = f"<rect x='{gx0:.1f}' y='0' width='{max(0, gx1 - gx0):.1f}' height='{H}' fill='var(--green-tint)'/>"
    on_good = (v >= t) if not down else (v <= t)
    barcol = "var(--green)" if on_good else "var(--coral)"
    bar = f"<rect x='0' y='{H*0.32:.0f}' width='{fx(v):.1f}' height='{H*0.36:.0f}' rx='2' fill='{barcol}'/>"
    tick = f"<line x1='{fx(t):.1f}' y1='2' x2='{fx(t):.1f}' y2='{H-2:.0f}' stroke='var(--ink)' stroke-width='2'/>"
    svg = (f"<svg class='bullet' viewBox='0 0 {W:.0f} {H:.0f}' width='100%' height='26' preserveAspectRatio='none'>"
           f"{good}{bar}{tick}</svg>")
    bm = f"<div class='muted bullet-bm'>benchmark: {_e(benchmark)}</div>" if benchmark else ""
    return (f"<div class='bullet-wrap'><div class='bullet-h'><b>{_num(v)}</b> "
            f"<span class='muted'>doel {_num(t)}</span></div>{svg}{bm}</div>")


def _data_table(res, bron: str = "") -> str:
    """Tufte 'show the data': de exacte ruwe datapunten onder een grafiek (datum · waarde · bron)."""
    kind = res.get("kind")
    b = _e(bron or "—")
    if kind == "series":
        pts = res.get("points") or []
        if not pts:
            return ""
        import datetime as _dt
        rows = "".join(f"<tr><td>{_dt.datetime.fromtimestamp(t).strftime('%d-%m-%y')}</td>"
                       f"<td class='num'>{_num(v)}</td><td>{b}</td></tr>" for t, v in pts[-12:])
        return (f"<table class='mtab'><tr><th>datum</th><th class='num'>waarde</th><th>bron</th></tr>"
                f"{rows}</table>")
    if kind == "breakdown":
        rows = res.get("rows") or []
        if not rows:
            return ""
        body = "".join(f"<tr><td>{_e(str(l))}</td><td class='num'>{_num(n)}</td><td>{b}</td></tr>"
                       for l, n in rows[:12])
        return f"<table class='mtab'><tr><th>categorie</th><th class='num'>waarde</th><th>bron</th></tr>{body}</table>"
    v = _agg(res)
    return (f"<table class='mtab'><tr><th>waarde</th><th>bron</th></tr>"
            f"<tr><td class='num'>{_num(v)}</td><td>{b}</td></tr></table>") if v is not None else ""


def _delta_badge(res) -> str:
    """Tufte 'comparison': verschil t.o.v. de vorige meting bij een reeks."""
    if res.get("kind") != "series":
        return ""
    pts = res.get("points") or []
    if len(pts) < 2:
        return ""
    d = pts[-1][1] - pts[-2][1]
    if d == 0:
        return "<span class='delta flat'>±0</span>"
    arrow, cls = ("▲", "up") if d > 0 else ("▼", "down")
    return f"<span class='delta {cls}'>{arrow} {abs(d):g}</span>"


def _render_burnup(res, target, project) -> str:
    """Burn-up naar een doel: cumulatieve werkelijke lijn tegen de ideaallijn (0 → streefwaarde
    over start → deadline), plus het dynamische catch-up-tempo (werkelijk/dag vs benodigd/dag)."""
    import datetime as _dt
    import time as _t
    try:
        tgt = float(target)
    except (TypeError, ValueError):
        tgt = 0.0
    due = (project or {}).get("due")
    if not (project and due and tgt > 0):
        return "<p class='muted'>Koppel een doel (project met deadline) én een streefwaarde.</p>"
    try:
        d = _dt.date.fromisoformat(str(due)[:10])
        deadline = _dt.datetime(d.year, d.month, d.day).timestamp()
    except Exception:
        return "<p class='muted'>Het gekoppelde doel heeft geen geldige deadline.</p>"
    day, now = 86400.0, _t.time()
    pts = list(res.get("points") or [])
    if not pts:
        v = _agg(res)
        pts = [(now, float(v))] if isinstance(v, (int, float)) else []
    latest = pts[-1][1] if pts else 0.0
    start = (project.get("created_at") or (pts[0][0] if pts else deadline - 90 * day))
    span = max(deadline - start, day)
    W, H = 240.0, 96.0
    fx = lambda ts: max(0.0, min(1.0, (ts - start) / span)) * W
    fy = lambda v: H - max(0.0, min(1.0, (v / tgt) if tgt else 0)) * H
    ideal = f"<line x1='{fx(start):.1f}' y1='{fy(0):.1f}' x2='{fx(deadline):.1f}' y2='{fy(tgt):.1f}' stroke='var(--subtle)' stroke-width='1' stroke-dasharray='3 3'/>"
    nowx = fx(now)
    nowline = f"<line x1='{nowx:.1f}' y1='0' x2='{nowx:.1f}' y2='{H:.0f}' stroke='var(--border)' stroke-width='1'/>"
    actual = ""
    if len(pts) >= 2:
        poly = " ".join(f"{fx(t):.1f},{fy(v):.1f}" for t, v in pts)
        actual = f"<polyline points='{poly}' fill='none' stroke='var(--green)' stroke-width='1.8'/>"
    elif pts:
        actual = f"<circle cx='{fx(pts[0][0]):.1f}' cy='{fy(latest):.1f}' r='2.4' fill='var(--green)'/>"
    svg = (f"<svg class='burnup' viewBox='0 0 {W:.0f} {H:.0f}' width='100%' height='96' preserveAspectRatio='none'>"
           f"{ideal}{nowline}{actual}</svg>")
    # tempo: dynamisch benodigd (catch-up) vs werkelijk
    days_left = max(0.0, (deadline - now) / day)
    remaining = max(0.0, tgt - latest)
    req = remaining / days_left if days_left > 0 else 0.0
    pace = None
    if len(pts) >= 2 and (pts[-1][0] - pts[0][0]) > 0:
        pace = (pts[-1][1] - pts[0][1]) / ((pts[-1][0] - pts[0][0]) / day)
    if pace is None:
        tempo = "<span class='muted'>nog te weinig metingen voor een tempo</span>"
    else:
        ontrack = pace >= req
        proj = latest + pace * days_left
        cls = "bu-ok" if ontrack else "bu-no"
        tempo = (f"<div class='bu-tempo'><span class='{cls}'>{pace:.1f}/dag</span> "
                 f"<span class='muted'>benodigd {req:.1f}/dag</span></div>"
                 f"<div class='muted bu-proj'>prognose: {proj:.0f} van {tgt:.0f} op de deadline</div>")
    head = f"<div class='bu-head'><b>{latest:.0f}</b> <span class='muted'>/ {tgt:.0f}</span></div>"
    return f"<div class='burnup-wrap'>{head}{svg}{tempo}</div>"


def _render_form(res, form, target=None, prev=None):
    unit = res.get("unit", "")
    kind = res.get("kind")
    # Vorm/dimensie-mismatch: val terug op een zinnige vorm i.p.v. een lege melding.
    if form in ("verdeling", "tabel") and kind != "breakdown":
        form = "trend" if kind == "series" else "getal"
    if form == "trend" and kind != "series":
        form = "getal"
    if form == "trend":
        pts = res.get("points") or []
        if res.get("chart") == "line":                 # echte dagreeks → lijn-diagram met assen
            return _line_chart_svg(pts, res.get("unit", ""), prev=(prev or {}).get("points"))
        return (f"<div class='tile-trend'><span class='kpi-val sm'>{_num(pts[-1][1] if pts else None)}</span>"
                f"{_spark_svg(pts)}</div>")
    if form in ("verdeling", "tabel"):
        rows = res.get("rows") or []
        if not rows:
            return "<p class='muted'>geen uitsplitsing</p>"
        if form == "tabel":
            body = "".join(f"<tr><td>{_e(str(l))}</td><td class='num'>{_num(n)}</td></tr>" for l, n in rows[:12])
            return f"<table class='mtab'>{body}</table>"
        mx = max((n for _, n in rows), default=1) or 1
        out = ""
        for l, n in rows[:8]:
            out += (f"<div class='bar-row'><span class='bar-l'>{_e(str(l))}</span>"
                    f"<span class='bar-t'><span class='bar-f' style='width:{int(n / mx * 100)}%'></span></span>"
                    f"<span class='bar-v'>{_num(n)}</span></div>")
        return f"<div class='bars'>{out}</div>"
    if form == "doelmeter":
        v = _agg(res) or 0
        t = target or 0
        pct = int(min(100, v / t * 100)) if t else 0
        return (f"<div class='goal'><span class='kpi-val sm'>{_num(v)} <span class='kpi-unit'>/ {_num(t)}</span></span>"
                f"<span class='bar-t'><span class='bar-f' style='width:{pct}%'></span></span></div>")
    # getal — leeg (None) is iets anders dan de waarde 0
    v = _agg(res)
    if v is None:
        return "<div class='kpi-val'><span class='muted' style='font-size:.9rem'>geen data</span></div>"
    u = f" <span class='kpi-unit'>{_e(unit)}</span>" if unit else ""
    return f"<div class='kpi-val'>{v:g}{u}</div>"


# Grondslag-laag (GAAP/IRIS): definitie, eenheid, bron, richting per bron-measure.
_SOURCE_GRONDSLAG = {
    "pulse_visitors|visitors": ("Unieke websitebezoekers per dag (dagreeks uit de observaties).",
                                "bezoekers", "observations (Plausible-dagwaarde)", "up"),
    "shopify|pairs_sold": ("Verkochte paren uit betaalde orders.", "paren", "Shopify", "up"),
    "shopify|orders": ("Aantal betaalde orders.", "orders", "Shopify", "up"),
    "shopify|revenue": ("Omzet uit betaalde orders.", "EUR", "Shopify", "up"),
    "shopify|aov": ("Gemiddelde orderwaarde (omzet ÷ orders).", "EUR", "Shopify", "up"),
}
_WERK_GRONDSLAG = {
    "tevredenheid": ("Gemiddelde check-out-score (0-10) per overleg.", "0-10", "up"),
    "spanningen": ("Aantal behandelde spanningen per overleg.", "", ""),
    "informatie": ("Aantal info-uitkomsten per overleg.", "", ""),
    "projecten": ("Aantal als project verwerkte uitkomsten.", "", ""),
    "acties": ("Aantal als actie verwerkte uitkomsten.", "", ""),
    "duur": ("Duur van het overleg in minuten.", "min", ""),
    "roloverleg": ("Aantal naar roloverleg doorgezette uitkomsten.", "", ""),
    "nevermind": ("Aantal ingetrokken punten per overleg.", "", ""),
    "afwezigheid": ("Aantal afwezigen per overleg.", "", ""),
}
_RICHTING = {"up": "hoger = beter", "down": "lager = beter", "": "—"}


def _grondslag(st: _Stores, source: str, measure: str) -> dict:
    if source.startswith("kpi:"):
        it = st.metrics.get(source[4:]) or {}
        origin = it.get("origin", "")
        bron = (_ORIGIN_LABEL.get(origin, origin) if origin
                else "Bron-KPI" if it.get("source") else "Handmatig (jij voert in)")
        if it.get("def_id"):
            bron += f" · catalogus v{it.get('def_version', 1)}"
        return {"definitie": it.get("definition", ""), "eenheid": it.get("unit", ""),
                "bron": bron, "richting": it.get("direction", ""), "drempel": it.get("threshold"),
                "cadans": it.get("cadence", ""), "meettype": it.get("meettype", ""),
                "venster": it.get("window", ""), "meetwijze": it.get("meetwijze", ""),
                "benchmark": it.get("benchmark", ""), "bron_url": it.get("bron_url", ""),
                "verificatie": it.get("verificatie", "")}
    if source.startswith("werk:"):
        d, u, r = _WERK_GRONDSLAG.get(measure, ("", "", ""))
        return {"definitie": d, "eenheid": u, "bron": "Werkoverleg-archief", "richting": r,
                "drempel": None, "cadans": "maand", "meettype": "snapshot", "venster": ""}
    d, u, b, r = _SOURCE_GRONDSLAG.get(f"{source}|{measure}", ("", "", "", ""))
    return {"definitie": d, "eenheid": u, "bron": b, "richting": r, "drempel": None,
            "cadans": "", "meettype": "", "venster": ""}


def _grondslag_popover(g: dict) -> str:
    rij = lambda k, v: f"<div class='gr-row'><span class='gr-k'>{k}</span><span>{_e(str(v))}</span></div>" if v else ""
    # meetmoment: cadans (hoe vaak) + meettype (hoe een waarde geldt) + eventueel venster
    cad = CADANS_LABEL.get(g.get("cadans"), "")
    mt = MEETTYPE_LABEL.get(g.get("meettype"), "")
    meet = ", ".join(x for x in (cad, mt) if x)
    if g.get("venster"):
        meet = f"{meet} ({g['venster']})" if meet else g["venster"]
    body = (rij("Definitie", g.get("definitie") or "— (nog niet vastgelegd)")
            + rij("Eenheid", g.get("eenheid")) + rij("Bron", g.get("bron"))
            + rij("Richting", _RICHTING.get(g.get("richting"), "—"))
            + (rij("Drempel", g.get("drempel")) if g.get("drempel") is not None else "")
            + rij("Meetmoment", meet)
            + rij("Meetwijze", MEETWIJZE_LABEL.get(g.get("meetwijze"), ""))
            + rij("Verificatie", VERIFICATIE_LABEL.get(g.get("verificatie"), ""))
            + (f"<div class='gr-row'><span class='gr-k'>Bron</span>{_bron_html(g['bron_url'])}</div>"
               if g.get("bron_url") else ""))
    return (f"<details class='tile-info'><summary title='grondslag'>{_IC_INFO}</summary>"
            f"<div class='gr-pop'>{body}</div></details>")


def _llm_says_comparable(old: dict, new: dict) -> bool:
    """LLM-check: blijft de historie vergelijkbaar onder de gewijzigde definitie? Zonder LLM-key
    (geen antwoord) → False, zodat de veilige default (reeksbreuk) geldt."""
    try:
        from nooch_village import llm
        prompt = (
            "Een indicator-definitie wijzigt. Blijven eerder gemeten waarden vergelijkbaar onder de "
            "nieuwe definitie (zodat we ze in dezelfde reeks mogen houden), of niet?\n"
            f"OUD: {old.get('definition','')} | eenheid {old.get('unit','')} | meettype {old.get('meettype','')}\n"
            f"NIEUW: {new.get('definition', old.get('definition',''))} | eenheid {new.get('unit', old.get('unit',''))} "
            f"| meettype {new.get('meettype', old.get('meettype',''))}\n"
            "Antwoord met exact één woord: VERGELIJKBAAR of BREUK.")
        out = (llm.reason(prompt) or "").strip().lower()
        return "vergelijkbaar" in out and "breuk" not in out
    except Exception:
        return False


def _compare_delta(res, prev_res) -> str:
    """Delta-badge (aard: moment): huidige periode vs de vorige periode."""
    cur, prv = _agg(res), _agg(prev_res)
    if not isinstance(cur, (int, float)) or not isinstance(prv, (int, float)):
        return ""
    d = cur - prv
    if d == 0:
        return "<span class='delta flat'>±0 vs vorige periode</span>"
    arrow, cls = ("▲", "up") if d > 0 else ("▼", "down")
    return f"<span class='delta {cls}'>{arrow} {abs(d):g} vs vorige periode</span>"


def _daily_obs_key(source: str, measure: str):
    """(observatie-metric, bron) voor 'Actueel' — de laatste bekende dagwaarde, zoals bij Plausible.
    (None, None) = deze bron heeft geen dag-observaties (→ 'geen live data')."""
    from nooch_village.observations import WERK_DAILY, SHOPIFY_DAILY
    if source == "pulse_visitors":
        return ("visitors_day", "plausible")
    if source.startswith("werk:") and measure in WERK_DAILY:
        return (WERK_DAILY[measure], "werkoverleg")
    if source == "shopify" and measure in SHOPIFY_DAILY:
        return (SHOPIFY_DAILY[measure], "shopify")
    return (None, None)


def _render_tile(st: _Stores, rec, tile, cutoff, csrf: str, end=None, compare=False,
                 prev_win=None, actueel=False) -> str:
    if tile.get("form") == "formule":          # fail-closed live-berekening A op B per dag
        return _render_formula_tile(st, rec, tile, csrf, cutoff, end)
    g = _grondslag(st, tile["source"], tile["measure"])
    goal = ""
    gp = st.projects.get(tile.get("goal_pid")) if tile.get("goal_pid") else None
    form = tile.get("form", "getal")
    # 'Actueel' = laatste bekende dagwaarde uit de observatie-store (dezelfde betekenis als Plausible);
    # geen dag-observaties voor deze bron → 'geen live data'.
    ak_metric, ak_bron = _daily_obs_key(tile["source"], tile["measure"]) if actueel else (None, None)
    if actueel:
        rows = st.observations.daily_series(ak_metric, bron=ak_bron) if ak_metric else []
        pts = [(r["ts"], r["value"]) for r in rows]
        latest = pts[-1][1] if pts else None
        res = {"kind": "number", "value": latest}
        body = (f"<div class='kpi-val'>{_num(latest)}</div>" if latest is not None
                else f"<div class='kpi-val'><span class='muted'>{_e(t('dashboard.geen_live_data'))}</span></div>")
        data = ""
        if pts:
            dt = _data_table({"kind": "series", "points": pts}, bron=ak_bron)
            data = f"<details class='tile-data'><summary>ruwe data</summary>{dt}</details>"
    else:
        res = _fetch(st, tile["source"], tile["measure"], tile.get("dim", "none"), cutoff, end)
        prev_res = None
        if compare and prev_win and prev_win[0] is not None:
            prev_res = _fetch(st, tile["source"], tile["measure"], tile.get("dim", "none"), prev_win[0], prev_win[1])
        if form == "burnup":
            body = _render_burnup(res, tile.get("target"), gp)
        elif form == "doelmeter":
            body = _render_bullet(res, tile.get("target"), g.get("richting"), g.get("benchmark"))
        else:
            body = _render_form(res, form, tile.get("target"), prev=prev_res)
        # aard: moment → delta-badge naast het getal (reeks krijgt al de tweede lijn in de grafiek)
        if compare and prev_res is not None and res.get("chart") != "line":
            body += _compare_delta(res, prev_res)
        # Uitklap: de exacte ruwe datapunten (datum · waarde · bron)
        data = ""
        if form in ("trend", "verdeling", "doelmeter", "burnup"):
            dt = _data_table(res, bron=g.get("bron", tile["source"]))
            if dt:
                data = f"<details class='tile-data'><summary>ruwe data{_delta_badge(res)}</summary>{dt}</details>"
    if gp is not None:
        due = _fmt_due(gp.get("due")) if gp.get("due") else ""
        goal = (f"<div class='tile-goal muted'>naar doel: <b>{_e(str(gp.get('scope') or gp['id'])[:50])}</b>"
                f"{(' · ' + _e(due)) if due else ''}</div>")
    # Drempel-signaal (Kaizen 'aandacht nodig'): waarde de verkeerde kant op t.o.v. de drempel.
    warn = ""
    thr, val = g.get("drempel"), _agg(res)
    if thr is not None and isinstance(val, (int, float)):
        bad = (val < thr) if g.get("richting") == "up" else (val > thr) if g.get("richting") == "down" else False
        if bad:
            warn = f"<span class='tile-warn' title='onder/over de drempel ({thr:g})'>⚠</span>"
    if g.get("verificatie") == "voorlopig":
        warn += "<span class='tile-prov' title='voorlopige waarde, nog niet geverifieerd'>voorlopig</span>"
    rm = ""
    if csrf:
        rm = (f"<form method='post' action='/action' class='tile-rm'>"
              f"<input type='hidden' name='csrf' value='{_e(csrf)}'><input type='hidden' name='node' value='{_e(rec.id)}'>"
              f"<input type='hidden' name='tid' value='{_e(tile['id'])}'>"
              f"<input type='hidden' name='next' value='/node?id={_e(rec.id)}&tab=metrics'>"
              f"<button class='dellink' type='submit' name='action' value='tile_remove'>✕</button></form>")
    flip = "<button class='dellink js-flip' type='button' title='betekenis / formule'>ⓘ</button>"
    # ⓘ-achterkant: de betekenis uit het catalogus-item (grondslag)
    std = f" · standaard: {_e(g['standaard'])}" if g.get("standaard") else ""
    back = (f"<div class='tile-back' hidden><b>{_e(_tile_meta(st, rec, tile))}</b>"
            f"<div class='muted'>{_e(g.get('definitie') or 'Geen definitie in het catalogus-item.')}</div>"
            f"<div class='muted'>Bron: {_e(g.get('bron') or tile['source'])}{std}</div>"
            f"<button class='dellink js-flipback' type='button'>↩ terug</button></div>")
    front = (f"<div class='tile-front'><div class='tile-h'><span class='tile-t'>{_e(_tile_meta(st, rec, tile))}{warn}</span>"
             f"<span class='tile-h-r'>{flip}{rm}</span></div>"
             f"<div class='tile-b'>{body}</div>{data}{goal}</div>")
    return f"<div class='tile'>{front}{back}</div>"


def _kpi_id_from_def(st: _Stores, node: str, did: str):
    """Geef de KPI-id voor een catalogus-definitie op deze node; maak hem aan als hij nog niet
    bestaat. Kopieert ALLE definitievelden mee (geen veld-lek). Eén bron blijft de catalogus."""
    cur = st.defs.current(did) if did else None
    if not cur:
        return None
    for it in st.metrics.for_node(node):
        if it.get("kind") == "kpi" and it.get("def_id") == did:
            return it["id"]
    it = st.metrics.add_kpi(
        node, cur.get("name"), cur.get("unit", ""), definition=cur.get("definition", ""),
        direction=cur.get("direction", ""), threshold=cur.get("threshold"),
        cadence=cur.get("cadence", "ad-hoc"), meettype=cur.get("meettype", "snapshot"),
        window=cur.get("window", ""), def_id=did, def_version=st.defs.current_version_no(did),
        origin=cur.get("source", ""), meetwijze=cur.get("meetwijze", ""),
        auto=cur.get("meetwijze") == "systeem", benchmark=cur.get("benchmark", ""),
        bron_url=cur.get("bron_url", ""), verificatie=cur.get("verificatie", ""),
        tijd=cur.get("tijd", ""), bruikbaar=cur.get("bruikbaar", ""),
        standaard=cur.get("standaard", ""), waarde=cur.get("waarde"))
    return it["id"] if it else None


def _goal_options(st: _Stores, rec) -> str:
    """Projecten onder deze node als koppelbare doelen (= outcome + deadline)."""
    is_c = org.is_circle(rec)
    nodes = {rec.id} | ({r.id for r in org.roles_of(st.records.all(), rec.id)} if is_c else set())
    out = "<option value=''>— geen doel —</option>"
    for p in st.projects.all():
        if p.get("owner") in nodes and not p.get("archived"):
            out += f"<option value='{_e(p['id'])}'>{_e(str(p.get('scope') or p['id'])[:50])}</option>"
    return out


def _metric_csv(st: _Stores, mid: str) -> tuple[str, str] | None:
    """(bestandsnaam, csv-tekst) met alle metingen van een KPI; None als de KPI niet bestaat."""
    it = st.metrics.get(mid)
    if it is None or it.get("kind") != "kpi":
        return None
    raw = _source_samples(st.dd, it["source"]) if it.get("source") else it.get("samples", [])
    pts = filter_samples(raw, None)
    import csv as _csv
    import datetime as _dt
    import io as _io
    from nooch_village.metric_schema import SCHEMA_FIELDS
    buf = _io.StringIO()
    w = _csv.writer(buf)
    # 1. het volledige indicator-schema (grondslag + meetmoment), ook lege velden
    w.writerow(["indicator-schema", ""])
    for f in SCHEMA_FIELDS:
        v = it.get(f, "")
        w.writerow([f, "" if v is None else v])
    w.writerow([])
    # 2. de metingen
    w.writerow(["datum", "waarde", "eenheid"])
    for at, v in pts:
        dt = _dt.datetime.fromtimestamp(at).strftime("%Y-%m-%d %H:%M")
        w.writerow([dt, v, it.get("unit", "")])
    safe = "".join(c if c.isalnum() else "_" for c in (it.get("name") or "kpi"))[:40]
    return f"{safe}.csv", buf.getvalue()


def _kpi_data_row(st: _Stores, item: dict, csrf: str) -> str:
    raw = _source_samples(st.dd, item["source"]) if item.get("source") else item.get("samples", [])
    pts = filter_samples(raw, None)
    val = _num(pts[-1][1]) if pts else "—"
    unit = f" {_e(item.get('unit', ''))}" if item.get("unit") else ""
    # systeem-gemeten KPI (live-bron of catalogus-origin uit een systeembron): geen handmatige invoer
    is_sys = bool(item.get("source") or item.get("auto"))
    src = " <span class='chip muted'>systeem</span>" if is_sys else ""
    add = ""
    if csrf and not is_sys:
        add = (f"<form method='post' action='/action' class='kpi-add'>"
               f"<input type='hidden' name='csrf' value='{_e(csrf)}'><input type='hidden' name='mid' value='{_e(item['id'])}'>"
               f"<input type='hidden' name='next' value='/node?id={_e(item['node'])}&tab=metrics'>"
               f"<input name='value' inputmode='decimal' placeholder='meting' size='6'>"
               f"<button class='btn ok sm' type='submit' name='action' value='m_sample'>+</button></form>")
    # grondslag (definitie + meetmoment) op de rij zelf, naast de naam (klik op de ⓘ)
    info = _grondslag_popover(_grondslag(st, f"kpi:{item['id']}", "value"))
    exp = (f"<a class='kpi-exp' href='/metric_export?mid={_e(item['id'])}' "
           f"title='Metingen exporteren (CSV)'>{_IC_DL}</a>")
    rm = ""
    if csrf:
        # destructief: vraagt bevestiging (en wijst op export) — een KPI met historie is niet terug te halen
        conf = (f"&#39;{_e(item['name'])}&#39; en alle metingen verwijderen? "
                "Dit kan niet ongedaan worden. Exporteer eventueel eerst de data.")
        rm = (f"<form method='post' action='/action' style='display:inline' data-confirm='{conf}'>"
              f"<input type='hidden' name='csrf' value='{_e(csrf)}'><input type='hidden' name='mid' value='{_e(item['id'])}'>"
              f"<input type='hidden' name='next' value='/node?id={_e(item['node'])}&tab=metrics'>"
              f"<button class='dellink' type='submit' name='action' value='m_remove'>✕</button></form>")
    bidx = _break_indices(item.get("samples", [])) if item.get("breaks") else None
    return (f"<div class='kpidata-row'><span class='kpidata-n'>{_e(item['name'])}{src} {info}</span>"
            f"<span class='kpidata-v'>{val}{unit}</span>{_spark_svg(pts, breaks_at=bidx)}{add}{exp}{rm}</div>")


# bron-herkomst → leesbaar label (voor de grondslag-popover van een catalogus-KPI)
_ORIGIN_LABEL = {
    "gsc": "Google Search Console", "plausible": "Plausible", "shopify": "Shopify",
    "trends": "Google Trends", "keywords_everywhere": "Keywords Everywhere", "ngram": "Google Ngram",
    "openalex": "OpenAlex", "semantic_scholar": "Semantic Scholar", "site_health": "Site health",
    "competitor_news": "Nieuws-monitor", "linkbuilding": "Linkbuilding", "budget": "Budget",
    "werkoverleg": "Werkoverleg-archief",
    # cross-domein bronnen (nog geen live-koppeling; handmatig in te voeren tot we ze koppelen)
    "erp": "ERP / voorraad", "monitoring": "IT-monitoring", "support": "Klantenservice",
    "survey": "Enquête", "hris": "HR-systeem", "impact": "Impact / LCA", "finance": "Boekhouding",
}
# lichte bron→functie-affiniteit bovenop tekstoverlap (zodat de juiste rol de juiste bron ziet)
_SOURCE_AFFINITY = {
    "gsc": "marketing seo zoek vindbaarheid content website",
    "trends": "marketing seo zoek trend content",
    "keywords_everywhere": "marketing seo zoek content",
    "plausible": "marketing website verkeer bezoekers analytics",
    "shopify": "verkoop sales omzet order webshop commerce conversie",
    "ngram": "content cultuur taal merk",
    "openalex": "onderzoek kennis wetenschap bewijs",
    "semantic_scholar": "onderzoek kennis wetenschap bewijs",
    "site_health": "website techniek beschikbaarheid developer ontwikkelaar",
    "competitor_news": "concurrent markt merk nieuws",
    "linkbuilding": "marketing seo link backlink",
    "budget": "budget kosten inkoop financ",
    "werkoverleg": "facilitator overleg proces governance gezondheid",
}
_DEF_STOP = {"beheert", "bewaakt", "zorgt", "rondom", "binnen", "deze", "wordt", "worden"}


def _def_tokens(text: str) -> set:
    return {w for w in re.findall(r"[a-zà-ÿ]+", (text or "").lower())
            if len(w) > 3 and w not in _DEF_STOP}


def _role_text(rec) -> str:
    d = rec.definition
    parts = [getattr(d, "name", "") or "", d.purpose or ""]
    parts += list(d.accountabilities or [])
    parts += list(d.domains or [])
    return " ".join(parts)


def _role_relevant_defs(st: _Stores, rec, limit: int = 6) -> list[tuple[str, dict]]:
    """Catalogus-definities gerangschikt op relevantie voor deze rol (knows-approximately).
    Score = tekstoverlap (rol-purpose/accountabilities/domeinen × definitie) + bron-affiniteit."""
    rt = _def_tokens(_role_text(rec))
    if not rt:
        return []
    scored = []
    for d in st.defs.all():
        cur = st.defs.current(d["id"]) or {}
        dt = _def_tokens(cur.get("name", "") + " " + cur.get("definition", ""))
        aff = _def_tokens(_SOURCE_AFFINITY.get(cur.get("source", ""), ""))
        score = len(rt & dt) * 2 + len(rt & aff)
        if score > 0:
            scored.append((score, cur.get("name", ""), d["id"], cur))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [(did, cur) for _s, _n, did, cur in scored[:limit]]


_METRICS_JS = """<script>(function(){
 function flip(b,front){var t=b.closest('.tile'); if(!t)return;
   var f=t.querySelector('.tile-front'), k=t.querySelector('.tile-back');
   if(f) f.hidden=!front; if(k) k.hidden=front;}
 document.querySelectorAll('.js-flip').forEach(function(b){b.addEventListener('click',function(){flip(b,false);});});
 document.querySelectorAll('.js-flipback').forEach(function(b){b.addEventListener('click',function(){flip(b,true);});});
})();</script>"""


def _metrics_tab_html(st: _Stores, rec, csrf: str = "", win: str = "7d", nav: str = "",
                      van: str = "", tot: str = "", compare: bool = False) -> str:
    import time as _t
    now = _t.time()
    start, end = window_range(win, now, van, tot)     # één centraal venster voor ALLE tegels
    prev_win = None
    if compare and start is not None and end is not None:
        prev_win = (start - (end - start), start)     # vorige periode = zelfde lengte, teruggeschoven
    base = f"/node?id={_e(rec.id)}&tab=metrics"
    tiles = st.metrics.tiles_of(rec.id)
    live = any((t.get("source") in _LIVE_TILE_SOURCES) or t.get("source", "").startswith("shopify")
               or t.get("source", "").startswith("werk:") for t in tiles)
    cmp_q = "&compare=1" if compare else ""

    def pl(k, lbl):
        on = " on" if win == k else ""
        if k == "actueel" and not live:               # alleen bij een live-capabele bron
            return f"<span class='cl-filter muted' title='alleen beschikbaar bij een live-capabele bron'>{_e(lbl)}</span>"
        if nav:   # in het werkoverleg: blijf in de modal
            u = f"{nav}&mw={k}"
            return f"<a class='cl-filter{on} js-modal' href='{u}' data-href='{u}'>{_e(lbl)}</a>"
        return f"<a class='cl-filter{on}' href='{base}&mw={k}{cmp_q}'>{_e(lbl)}</a>"
    wbar = (f"<div class='cl-bar'><span class='muted'>{_e(t('dashboard.periode'))}</span> "
            + "".join(pl(k, lbl) for k, lbl in _MW))
    if not nav:                                        # compare-toggle (server-side)
        ct = " on" if compare else ""
        ct_url = f"{base}&mw={_e(win)}" + ("" if compare else "&compare=1")
        wbar += (f" <span class='muted'>·</span> <a class='cl-filter{ct}' href='{ct_url}'>"
                 f"{_e(t('dashboard.vergelijk'))}</a>")
    wbar += "</div>"
    if win == "aangepast" and not nav:                 # van/tot-formulier
        wbar += (f"<form method='get' action='/node' class='cl-bar'>"
                 f"<input type='hidden' name='id' value='{_e(rec.id)}'>"
                 f"<input type='hidden' name='tab' value='metrics'><input type='hidden' name='mw' value='aangepast'>"
                 + ("<input type='hidden' name='compare' value='1'>" if compare else "")
                 + f"<input type='date' name='van' value='{_e(van)}'> <span class='muted'>tot</span> "
                 f"<input type='date' name='tot' value='{_e(tot)}'> "
                 f"<button class='btn sm' type='submit'>Toon</button></form>")
    # In het werkoverleg (nav gezet) selecteer/bekijk je KPI's, je maakt ze daar niet aan.
    creating = bool(csrf) and not nav
    addlink = ""
    if creating:
        addlink = (f"<details class='m-add'><summary class='btn sm'>+ Link</summary>"
                   f"<form method='post' action='/action' class='m-addform'>"
                   f"<input type='hidden' name='csrf' value='{_e(csrf)}'><input type='hidden' name='node' value='{_e(rec.id)}'>"
                   f"<input type='hidden' name='next' value='{base}'>"
                   f"<input name='name' placeholder='Naam' autocomplete='off'>"
                   f"<input name='url' placeholder='https://…' autocomplete='off'>"
                   f"<button class='btn ok sm' type='submit' name='action' value='m_add_link'>Link toevoegen</button></form></details>")
    mk = (f"<a class='btn ok sm' href='/kpi_new?node={_e(rec.id)}'>+ KPI maken</a>" if creating else "")
    head = f"<div class='cl-head'><h3>Metrics</h3><span class='kc-actions'>{mk}{addlink}</span></div>{wbar}"

    # 1. Dashboard van tegels (de KPI's) — één centrale periode voor alle tegels
    dash = ("".join(_render_tile(st, rec, t, start, csrf, end=end, compare=compare, prev_win=prev_win,
                                 actueel=(win == "actueel")) for t in tiles) if tiles
            else "<p class='muted'>Nog geen KPI's op het dashboard. Maak er een met “+ KPI maken”.</p>")
    out = f"<div class='c2-sec'>{head}</div><div class='c2-sec'><div class='tile-grid'>{dash}</div></div>{_METRICS_JS}"

    # 2. Eigen KPI's: data invoeren voor handmatige KPI's (aanmaken gaat via + KPI maken / de catalogus)
    kpis = [i for i in st.metrics.for_node(rec.id) if i.get("kind") == "kpi"]
    if kpis:
        rows = "".join(_kpi_data_row(st, i, csrf) for i in kpis)
        out += f"<div class='c2-sec'><div class='cl-head'><h3>Eigen KPI's (data invoeren)</h3></div>{rows}</div>"

    # 3. Links naar externe bestanden (cijfers die elders leven)
    links = st.metrics.links_for(rec.id)
    if links:
        lc = "".join(_link_card(i, csrf) for i in links)
        out += f"<div class='c2-sec'><div class='cl-head'><h3>Links</h3></div><div class='kpi-grid'>{lc}</div></div>"
    return out


def _dir_select(name: str, cur: str) -> str:
    opt = [("", "Richting (geen)"), ("up", "hoger = beter"), ("down", "lager = beter")]
    return (f"<select name='{name}'>"
            + "".join(f"<option value='{v}'{' selected' if v == (cur or '') else ''}>{_e(l)}</option>"
                      for v, l in opt) + "</select>")


def _cad_select(name: str, cur: str) -> str:
    return (f"<select name='{name}'>"
            + "".join(f"<option value='{k}'{' selected' if k == cur else ''}>meet: {_e(v)}</option>"
                      for k, v in CADANS_LABEL.items()) + "</select>")


def _mt_select(name: str, cur: str) -> str:
    return (f"<select name='{name}'>"
            + "".join(f"<option value='{k}'{' selected' if k == cur else ''}>{_e(v)}</option>"
                      for k, v in MEETTYPE_LABEL.items()) + "</select>")


def _opt_select(name: str, label_map: dict, cur: str, empty: str) -> str:
    return (f"<select name='{name}'><option value=''>{_e(empty)}</option>"
            + "".join(f"<option value='{k}'{' selected' if k == cur else ''}>{_e(v)}</option>"
                      for k, v in label_map.items()) + "</select>")


def _aard_chips(cur: dict) -> str:
    out = ""
    if cur.get("tijd"):
        out += f"<span class='chip outline'>{_e(cur['tijd'])}</span>"
    if cur.get("bruikbaar"):
        cls = "chip green" if cur["bruikbaar"] == "actionable" else "chip muted"
        out += f"<span class='{cls}'>{_e(cur['bruikbaar'])}</span>"
    return out


def _mw_select(name: str, cur: str) -> str:
    return (f"<select name='{name}' title='meetwijze: hoe komt de waarde tot stand?'>"
            + "".join(f"<option value='{k}'{' selected' if k == cur else ''}>meetwijze: {_e(v)}</option>"
                      for k, v in MEETWIJZE_LABEL.items()) + "</select>")


def _mw_chip(mw: str) -> str:
    cls = {"systeem": "chip muted", "handmatig": "chip outline", "enquete": "chip coral"}.get(mw, "chip muted")
    return f"<span class='{cls}'>{_e(MEETWIJZE_LABEL.get(mw, mw or 'handmatig'))}</span>"



# Bronnen die actief data leveren → indicatoren daaruit zijn klikbaar; de rest staat grijs (nog geen
# data). Combos (source|measure|dim) zijn zelf altijd echte data-paden.
_LIVE_DEF_SOURCES = {"plausible", "shopify", "gsc", "werkoverleg", "library"}
_COMBO_CATEGORIE = {"pulse_visitors": "Website", "shopify": "Verkoop"}
_FORM_AARD = {"trend": "reeks", "getal": "moment", "verdeling": "categorie"}


def _wizard_indicators(st: _Stores, rec) -> list[dict]:
    """Alle kiesbare indicatoren voor de wizard met categorie/aard/heeft-data/bron/uitleg. Twee
    herkomsten: de 'beschikbaar op deze plek'-combos (echte data-paden) en de catalogus-defs."""
    out = []
    if rec is not None:
        for value, label, df in _tile_combos(_sources_for(st, rec)):
            source, measure = value.split("|")[0], value.split("|")[1]
            cat = "Werkoverleg" if source.startswith("werk:") else _COMBO_CATEGORIE.get(source, "Beschikbaar hier")
            g = _grondslag(st, source, measure) or {}
            out.append({"value": value, "name": label, "categorie": cat,
                        "aard": _FORM_AARD.get(df, "reeks"), "has_data": True,
                        "bron": g.get("bron", source), "uitleg": g.get("definitie", "")})
    for d in st.defs.all():
        c = st.defs.current(d["id"]) or {}
        if not c.get("name"):
            continue
        out.append({"value": f"def:{d['id']}", "name": c["name"],
                    "categorie": c.get("categorie") or "Overig", "aard": c.get("aard") or "moment",
                    "has_data": c.get("source", "") in _LIVE_DEF_SOURCES,
                    "bron": c.get("source", ""), "uitleg": c.get("definition", "")})
    return out


_FORMULA_OPS = {
    "÷": lambda a, b: (a / b) if b else None,          # deling door 0 → geen waarde (fail-closed)
    "%": lambda a, b: (a / b * 100) if b else None,
    "+": lambda a, b: a + b,
    "−": lambda a, b: a - b, "-": lambda a, b: a - b,
    "×": lambda a, b: a * b, "*": lambda a, b: a * b,
}


def _day_key(ts: float) -> str:
    import datetime as _dt
    return _dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


def _series_day_map(res) -> dict:
    """{dag → (ts, waarde)} uit een series-res; de laatste meting per dag wint."""
    out = {}
    for t, v in (res.get("points") or []):
        out[_day_key(t)] = (t, v)
    return out


def _formula_daily(st: _Stores, tile, cutoff, end=None) -> list[dict]:
    """Per-dag A op B over twee bronnen, FAIL-CLOSED: mist één bron een dag, dan is die dag no_data
    (nooit doorrekenen met een oude waarde, nooit stilzwijgend 0). Deling door 0 → ook no_data.
    Geeft rijen [{at, value, no_data}] voor álle dagen die in minstens één bron voorkomen."""
    def _map(combo):
        parts = (combo or "").split("|")
        if len(parts) != 3 or not parts[0]:
            return {}
        return _series_day_map(_fetch(st, parts[0], parts[1], parts[2], cutoff, end))
    amap, bmap = _map(tile.get("f_a")), _map(tile.get("f_b"))
    op = _FORMULA_OPS.get(tile.get("f_op", "÷"))
    rows = []
    for day in sorted(set(amap) | set(bmap)):
        at = (amap.get(day) or bmap.get(day))[0]
        av = amap.get(day, (None, None))[1]
        bv = bmap.get(day, (None, None))[1]
        val = None if (av is None or bv is None or op is None) else op(av, bv)
        rows.append({"at": at, "value": None if val is None else round(val, 4), "no_data": val is None})
    return rows


def _render_formula_tile(st: _Stores, rec, tile, csrf: str, cutoff=None, end=None) -> str:
    """Formule-tegel: live A op B per dag, fail-closed. Grafiek toont alleen dagen MÉT waarde
    (no_data = gat, nooit 0/interpolatie); de tabel toont ÁLLE dagen met no_data expliciet."""
    rows = _formula_daily(st, tile, cutoff, end)
    agg = tile.get("aggregatie", "")
    vals = [r["value"] for r in rows if not r["no_data"]]          # no_data telt niet mee
    if agg == "som":
        head = sum(vals) if vals else None
    elif agg == "laatste_waarde":
        head = vals[-1] if vals else None
    else:
        head = round(sum(vals) / len(vals), 2) if vals else None    # gemiddelde
    pts = [(r["at"], r["value"]) for r in rows if not r["no_data"]]  # no_data = gat in de grafiek
    if len(pts) >= 2:
        body = _line_chart_svg(pts, "")
    elif head is not None:
        body = f"<div class='kpi-val'>{_num(head)}</div>"
    else:
        body = "<div class='kpi-val'><span class='muted'>geen data</span></div>"
    import datetime as _dt
    trows = "".join(
        f"<tr><td>{_dt.datetime.fromtimestamp(r['at']).strftime('%d-%m-%y')}</td>"
        f"<td class='num'>{'—' if r['no_data'] else _num(r['value'])}</td>"
        f"<td>{'geen data' if r['no_data'] else 'formule'}</td></tr>" for r in rows)
    data = (f"<details class='tile-data'><summary>ruwe data</summary>"
            f"<table class='mtab'><tr><th>datum</th><th class='num'>waarde</th><th>bron</th></tr>"
            f"{trows}</table></details>") if rows else ""
    rm = ""
    if csrf:
        rm = (f"<form method='post' action='/action' class='tile-rm'>"
              f"<input type='hidden' name='csrf' value='{_e(csrf)}'><input type='hidden' name='node' value='{_e(rec.id)}'>"
              f"<input type='hidden' name='tid' value='{_e(tile['id'])}'>"
              f"<input type='hidden' name='next' value='/node?id={_e(rec.id)}&tab=metrics'>"
              f"<button class='dellink' type='submit' name='action' value='tile_remove'>✕</button></form>")
    flip = "<button class='dellink js-flip' type='button' title='betekenis / formule'>ⓘ</button>"
    op = tile.get("f_op", "÷")
    back = (f"<div class='tile-back' hidden><b>{_e(tile.get('measure', 'formule'))}</b>"
            f"<div class='muted'>Formule: A {_e(op)} B, per dag berekend en dan geaggregeerd "
            f"({_e(agg or 'gemiddelde')}). Mist één bron een dag, dan telt die dag niet mee (fail-closed).</div>"
            f"<button class='dellink js-flipback' type='button'>↩ terug</button></div>")
    front = (f"<div class='tile-front'><div class='tile-h'>"
             f"<span class='tile-t'>{_e(tile.get('measure', 'formule'))} <span class='chip muted'>formule</span></span>"
             f"<span class='tile-h-r'>{flip}{rm}</span></div>"
             f"<div class='tile-b'>{body}</div>{data}</div>")
    return f"<div class='tile'>{front}{back}</div>"


def render_kpi_composer(st: _Stores, node_id: str = "", csrf_token: str = "", msg: str = "") -> str:
    """Wizard (scope 5): stap 1 = 'wat je meet' met een modus-toggle (bestaande indicator vs formule);
    indicatoren categorie-eerst met zoek + ⓘ-tooltip + grijs-bij-geen-data. Plaats is context-afgeleid
    (of een keuze bij een losstaande start). Vorm biedt alleen weergaves die bij de aard passen."""
    rec = st.records.get(node_id) if node_id else None
    if node_id and rec is None:
        return _page("Niet gevonden", "<p>Node niet gevonden.</p>")
    standalone = rec is None
    back = "/" if standalone else f"/node?id={_e(node_id)}&tab=metrics"

    inds = _wizard_indicators(st, rec)
    cats = []
    for i in inds:
        if i["categorie"] not in cats:
            cats.append(i["categorie"])
    cat_chips = "".join(f"<button type='button' class='cl-filter kc-cat' data-cat='{_e(c)}'>{_e(c)}</button>"
                        for c in cats)

    def _radio(i: dict) -> str:
        dis = "" if i["has_data"] else " disabled"
        mut = "" if i["has_data"] else " muted"
        tip = "Bron: " + (i["bron"] or "—") + (f" · {i['uitleg']}" if i["uitleg"] else "")
        tag = "" if i["has_data"] else " <span class='chip muted'>nog geen data</span>"
        return (f"<label class='kc-radio kc-metric{mut}' data-cat='{_e(i['categorie'])}' "
                f"data-aard='{_e(i['aard'])}' data-name='{_e(i['name'].lower())}' hidden>"
                f"<input type='radio' name='combo' value='{_e(i['value'])}'{dis}> "
                f"<span class='kc-mname'>{_e(i['name'])}</span> "
                f"<span class='chip muted' title='{_e(tip)}'>ⓘ</span>{tag}</label>")
    metrics_html = "".join(_radio(i) for i in inds) or "<p class='muted'>Geen indicatoren beschikbaar.</p>"
    metric_opts = "".join(f"<option value='{_e(i['value'])}'>{_e(i['categorie'])} — {_e(i['name'])}</option>"
                          for i in inds if i["has_data"])
    agg_opts = "".join(f"<option value='{a}'>{_e(AGGREGATIE_LABEL[a])}</option>" for a in AGGREGATIE)

    proj_opts = _goal_options(st, rec) if rec is not None else ""
    step = lambda n, t, inner: (f"<div class='kc-step'><div class='kc-h'><span class='kc-n'>{n}</span>"
                                f"<b>{_e(t)}</b></div>{inner}</div>")

    step1 = (
        "<div class='cl-bar'>"
        f"<button type='button' class='cl-filter kc-mode-btn on' data-mode='indicator'>{_e(t('wizard.modus.indicator'))}</button>"
        f"<button type='button' class='cl-filter kc-mode-btn' data-mode='formule'>{_e(t('wizard.modus.formule'))}</button></div>"
        "<input type='hidden' name='mode' value='indicator'>"
        "<div class='kc-mode' data-mode='indicator'>"
        f"<div class='cl-bar kc-cats'>{cat_chips}</div>"
        "<input class='kc-search' type='text' placeholder='Zoek binnen deze categorie…' autocomplete='off' hidden>"
        f"<div class='kc-metrics'>{metrics_html}</div>"
        "<p class='muted kc-hint'>Kies een categorie. Metrics zonder data staan grijs; klik ⓘ voor uitleg.</p></div>"
        "<div class='kc-mode' data-mode='formule' hidden>"
        f"<label class='att-lbl'>Metric A</label><select name='f_a'>{metric_opts}</select>"
        "<label class='att-lbl'>Bewerking</label>"
        "<select name='f_op'><option>÷</option><option>+</option><option>−</option><option>%</option></select>"
        f"<label class='att-lbl'>Metric B</label><select name='f_b'>{metric_opts}</select>"
        "<label class='att-lbl'>Naam van de formule</label>"
        "<input name='f_name' placeholder='bijv. Conversie' autocomplete='off'>"
        f"<label class='att-lbl'>Aggregatie (verplicht)</label><select name='f_agg'>"
        f"<option value=''>— kies —</option>{agg_opts}</select>"
        "<p class='muted kc-hint'>Een formule rekent live over de twee indicatoren (berekening volgt).</p></div>")

    step4_inner = (f"<div class='muted'>{_e(_name(rec))} · dashboard</div>"
                   f"<input type='hidden' name='node' value='{_e(node_id)}'>") if not standalone else (
        "<select name='node'>" + "".join(
            f"<option value='{_e(r.id)}'>{_e(_name(r))}</option>"
            for r in st.records.all() if not getattr(r, "archived", False)) + "</select>"
        "<p class='muted kc-hint'>Losstaande start — kies waar de KPI komt.</p>")

    form = (f"<form method='post' action='/action' class='kc-form'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"<input type='hidden' name='next' value='{back}'>"
            f"<input type='hidden' name='target' value=''>"
            + step("1", "Wat je meet", step1)
            + step("2", "Referentie (de vergelijking)",
                   "<label class='kc-radio'><input type='radio' name='ref_kind' value='' checked> geen — alleen volgen</label>"
                   "<label class='kc-radio'><input type='radio' name='ref_kind' value='benchmark'> benchmark</label>"
                   "<div class='kc-cond' data-for='benchmark' hidden>"
                   "<input name='bench_target' inputmode='decimal' placeholder='benchmark-waarde (bijv. 13.6)' autocomplete='off'>"
                   "<p class='muted kc-hint'>Later koppelbaar aan de kennisbank. Nu de vergelijkwaarde.</p></div>"
                   "<label class='kc-radio'><input type='radio' name='ref_kind' value='doel'> doel (project)</label>"
                   f"<div class='kc-cond' data-for='doel' hidden><select name='goal_pid'>{proj_opts}</select>"
                   "<input name='doel_target' inputmode='decimal' placeholder='streefwaarde (bijv. 1000)' autocomplete='off'></div>")
            + step("3", "Vorm (past bij de aard)",
                   "<select name='form'>"
                   "<option value='trend' data-aard='reeks' data-ref=''>Trend (lijn)</option>"
                   "<option value='getal' data-aard='moment' data-ref=''>Getal</option>"
                   "<option value='verdeling' data-aard='categorie' data-ref=''>Verdeling (staaf)</option>"
                   "<option value='doelmeter' data-aard='' data-ref='benchmark doel'>Bullet (waarde vs referentie)</option>"
                   "<option value='burnup' data-aard='' data-ref='doel'>Doel-tempo (burn-up)</option>"
                   "</select>"
                   "<p class='muted kc-hint'>Alleen de opening-weergave; op het dashboard altijd te wijzigen.</p>")
            + step("4", "Plaats", step4_inner)
            + "<button class='btn ok' type='submit' name='action' value='tile_add' disabled>Kies eerst een indicator</button></form>")
    main = (f"<div class='c2-main'><div class='c2-bar'><a href='{back}'>← terug</a></div>"
            f"<h1>KPI maken <span class='chip'>focus</span></h1>{_banner(msg)}"
            f"<p class='muted'>Een KPI is alleen de definitie van wat je meet. Periode en weergave kies "
            f"je op het dashboard.</p>"
            f"<div class='c2-sec'>{form}</div></div>")
    inner = (f"<style>{_EXTRA_CSS}</style>"
             f"<div class='bar'>cockpit 2 · GlassFrog (PoC) · build {_BUILD} · <a href='/'>home</a> · "
             "<a href='/catalog'>catalogus</a> · <a href='/catalogus_koppelen'>koppelen</a></div>"
             f"<div class='c2-wrap'>{main}</div>{_KPI_COMPOSER_JS}")
    return _page("KPI maken", inner)


_KPI_COMPOSER_JS = """<script>
(function(){
 var f=document.querySelector('.kc-form'); if(!f) return;
 var modeInp=f.querySelector('[name=mode]');
 var sel=f.querySelector('[name=form]'), tgt=f.querySelector('[name=target]');
 var search=f.querySelector('.kc-search');
 var btn=f.querySelector('button[value=tile_add]');
 var curAard='';
 function ref(){var r=f.querySelector('[name=ref_kind]:checked'); return r?r.value:'';}

 // stap 1: modus-toggle (bestaande indicator / formule)
 function setMode(m){
   modeInp.value=m;
   f.querySelectorAll('.kc-mode-btn').forEach(function(b){b.classList.toggle('on', b.dataset.mode===m);});
   f.querySelectorAll('.kc-mode').forEach(function(el){el.hidden=(el.dataset.mode!==m);});
   syncBtn();
 }
 f.querySelectorAll('.kc-mode-btn').forEach(function(b){b.addEventListener('click',function(){setMode(b.dataset.mode);});});

 // categorie-eerst + zoeken (via het hidden-attribuut, geen inline styles)
 function filter(cat,q){
   q=(q||'').toLowerCase();
   f.querySelectorAll('.kc-metric').forEach(function(m){
     m.hidden=!((m.dataset.cat===cat) && (!q || (m.dataset.name||'').indexOf(q)>=0));
   });
 }
 f.querySelectorAll('.kc-cat').forEach(function(c){c.addEventListener('click',function(){
   f.querySelectorAll('.kc-cat').forEach(function(x){x.classList.toggle('on',x===c);});
   if(search) search.hidden=false;
   filter(c.dataset.cat, search?search.value:'');
 });});
 if(search) search.addEventListener('input',function(){
   var a=f.querySelector('.kc-cat.on'); if(a) filter(a.dataset.cat, search.value);
 });

 // stap 3: alleen vormen die bij de aard (van de gekozen indicator) en de referentie passen
 function syncVorm(){
   var rk=ref();
   f.querySelectorAll('.kc-cond').forEach(function(c){c.hidden=(c.dataset.for!==rk);});
   Array.prototype.forEach.call(sel.options,function(o){
     var aardOk=(!o.dataset.aard)||(o.dataset.aard===curAard)||(curAard==='');
     var refOk=(o.dataset.ref||'').split(' ').indexOf(rk)>=0 || (rk===''&&o.dataset.ref==='');
     o.hidden=!(aardOk&&refOk); o.disabled=!(aardOk&&refOk);
   });
   var cur=sel.options[sel.selectedIndex];
   if(!cur||cur.disabled){for(var i=0;i<sel.options.length;i++){if(!sel.options[i].disabled){sel.selectedIndex=i;break;}}}
   var bt=f.querySelector('[name=bench_target]'), dt=f.querySelector('[name=doel_target]');
   tgt.value = rk==='benchmark'?(bt?bt.value:'') : rk==='doel'?(dt?dt.value:'') : '';
 }

 function syncBtn(){
   if(modeInp.value==='formule'){ btn.disabled=false; btn.textContent='Maak KPI — formule'; return; }
   var r=f.querySelector('.kc-metric input:checked');
   btn.disabled=!r; btn.textContent = r ? 'Maak KPI' : 'Kies eerst een indicator';
 }

 f.addEventListener('change',function(e){
   if(e.target && e.target.name==='combo'){var lab=e.target.closest('.kc-metric'); curAard=lab?lab.dataset.aard:'';}
   syncVorm(); syncBtn();
 });
 f.addEventListener('input',syncVorm);
 setMode('indicator'); syncVorm(); syncBtn();
})();
</script>"""
