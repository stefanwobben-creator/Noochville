"""Metrics/KPI-views — brok 8 van de cockpit2-split."""
from __future__ import annotations

import json
import logging
import os
import re
from typing import TYPE_CHECKING

from nooch_village.web_base import _e, _page, _banner
from nooch_village.cockpit2_util import (
    _DS_LINK,
    _name, _fmt_due, _bron_html,
    _IC_INFO, _IC_LINK, _IC_DL,
)
from nooch_village.metric_schema import (
    CADANS_LABEL, MEETTYPE_LABEL, MEETWIJZE_LABEL,
    VERIFICATIE_LABEL, AGGREGATIE, AGGREGATIE_LABEL, AARD_LABEL,
)
from nooch_village.metrics import window_cutoff, window_range, filter_samples
from nooch_village.definitions import aggregatie_for, DEFAULT_AGGREGATIE
from nooch_village.observations import ObservationStore
from nooch_village.meetcatalog import cadence_of
from nooch_village.i18n import t
from nooch_village import org
from nooch_village.cockpit2_util import _BUILD

if TYPE_CHECKING:
    from nooch_village.cockpit2 import _Stores

log = logging.getLogger(__name__)


# Centrale periode-picker (scope 6/PR2). Dropdown in Plausible-stijl met single-key sneltoetsen.
# 'actueel' = laatste waarde, alleen bij een live-capabele bron.
_MW = [("vandaag", "Vandaag"), ("gisteren", "Gisteren"), ("actueel", "Actueel"),
       ("7d", "7 dagen"), ("28d", "28 dagen"), ("kwartaal", "Kwartaal"),
       ("jaar", "Jaar"), ("aangepast", "Aangepast")]
# Single-key sneltoets per periode-optie (zoals Plausible): V/G/A/W/M/K/J/C.
_MW_KEYS = {"vandaag": "V", "gisteren": "G", "actueel": "A", "7d": "W",
            "28d": "M", "kwartaal": "K", "jaar": "J", "aangepast": "C"}
# Bronnen die 'live' bevraagd kunnen worden → 'Actueel' beschikbaar (anders uitgegrijsd).
_LIVE_TILE_SOURCES = {"pulse_visitors", "shopify"}
# Bron-KPI's: meetbaar uit bestaande dorpsdata (AI/agents schrijven hier al naartoe).
_SOURCE_KPIS = {"pulse_visitors": {"name": "Websitebezoekers (per dag)", "unit": "bezoekers"}}


def _row_at(r) -> float:
    """De tijd-as van een dag-observatie = de MEETDAG (`datum`), niet de schrijf-`ts`. Zo staan en
    sorteren reeksen chronologisch op meetdag; een backfill schrijft historische dagen op één dag (gelijke
    ts) en zou anders alles op die dag samenklonteren. `ts` dient daarna alleen als audit-veld. Terugval
    op ts als datum ontbreekt (legacy-reeksen zonder datum)."""
    import datetime as _dt
    d = r.get("datum")
    if d:
        try:
            return _dt.datetime.fromisoformat(d).timestamp()
        except (TypeError, ValueError):
            pass
    return r.get("ts", 0) or 0


def _pt_datum_label(p) -> str:
    """dd-mm-yy-label voor een punt: uit het meegedragen `datum` (3e tuple-element), anders round-trip via
    de datum-as (at). Nooit de schrijf-ts, zodat de ruwe-data-tabel de meetdag toont, niet de backfill-dag."""
    import datetime as _dt
    d = p[2] if len(p) > 2 else None
    if d:
        return f"{d[8:10]}-{d[5:7]}-{d[2:4]}"
    return _dt.datetime.fromtimestamp(p[0]).strftime('%d-%m-%y')


def _obs_points(rows) -> list:
    """Punten uit dag-observatie-rijen: (datum-as, waarde, datum). Meetdag stuurt sortering/positie/labels."""
    return [(_row_at(r), r.get("value"), r.get("datum")) for r in rows]


def _source_samples(dd: str, source: str):
    """Lees samples voor een bron-KPI. Twee HELDER onderscheiden reeksen (niet meer één 'pulse_visitors'
    die twee dingen betekent):
      - `pulse_visitors`     → de DAGREEKS (plausible_visitors_day, bron=plausible) uit observations.jsonl;
      - `pulse_visitors_7d`  → de rollende 7d-total (visitors_7d) uit pulse_history.jsonl (legacy snapshot).
    """
    if source == "pulse_visitors":
        store = ObservationStore(os.path.join(dd, "observations.jsonl"))
        return [{"at": _row_at(r), "value": r["value"], "datum": r.get("datum")}
                for r in store.daily_series("plausible_visitors_day", bron="plausible")]
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


def _is_system_kpi(item: dict) -> bool:
    """Systeem-gevoed (bron/auto/meetwijze) → geen handmatige invoer. NIET alleen `source`: een KPI die
    vóór de bron-veld-fix is aangemaakt heeft source='' maar auto=True/origin gezet. Eén criterium,
    gedeeld door de rij-render en de sectie-split (reference, don't copy)."""
    return bool(item.get("source") or item.get("origin") or item.get("auto")
                or item.get("meetwijze") == "systeem")


def _kpi_samples(st: _Stores, item: dict):
    """Samples voor een (bron-)KPI — één centrale route (voorheen 4× gedupliceerd):
      - bron + veld (source óf origin ∈ _DATA_SOURCES, + veld) → de dagreeks <source>_<veld>_day uit de
        ObservationStore. Dit is de generieke route; de dimensie-naad is `_obs_key_for_indicator` (later
        een dimensie-suffix), dus geen harde koppeling aan één reeks.
      - legacy bron-id (bv. pulse_visitors) → _source_samples;
      - anders → de handmatige samples van de KPI."""
    metric, bron = _obs_key_for_indicator(item.get("source") or item.get("origin") or "",
                                          item.get("veld", ""))
    if metric:
        return [{"at": _row_at(r), "value": r["value"], "datum": r.get("datum")}
                for r in st.observations.daily_series(metric, bron=bron)]
    if item.get("source"):
        return _source_samples(st.dd, item["source"])
    return item.get("samples", [])


def _metric_points(st: _Stores, item: dict, cutoff, end=None):
    return filter_samples(_kpi_samples(st, item), cutoff, end)


def _spark_svg(points, w=84, h=22, breaks_at=None) -> str:
    vals = [p[1] for p in points]
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


def _geen_data_html() -> str:
    """De ENIGE 'geen data in deze periode'-melding — gedeeld door alle reeks/verdeling-renderers
    (lijn, staaf, gestapelde staaf, horizontale balk), zodat de geen-data-afhandeling overal identiek is."""
    return (f"<div class='kpi-val'><span class='muted' style='font-size:.9rem'>"
            f"{_e(t('dashboard.geen_data_periode'))}</span></div>")


def _line_chart_svg(points, unit: str = "", prev=None) -> str:
    """Echt lijn-diagram (server-side SVG, cockpit2-stijl): x=datum, y=waarde, met leesbare assen
    (0-basislijn + datumbereik). ALTIJD met assen — een KPI-kaart toont nooit een assenloze sparkline
    (die mag alleen in compacte lijstrijen). Alleen de echte dagpunten als stippen, verbonden — geen
    interpolatie van ontbrekende dagen. `prev` (vorige periode) → een tweede, lichtere gestreepte lijn.
    De headline (het venster-aggregaat) staat in het kaart-skelet erboven; dit levert dus alleen de grafiek.
    0 punten → 'geen data'-melding (de visual toont 'm; de headline blijft dan leeg → geen dubbele melding);
    1 punt → korte notitie (nooit een vlakke lijn)."""
    if not points:
        return _geen_data_html()
    import datetime as _dt
    vals = [p[1] for p in points]
    if len(points) < 2:
        return "<div class='muted kc-hint'>1 meetpunt — te weinig voor een lijn</div>"
    prev = prev or []
    W, H = 300.0, 140.0
    ml, mr, mt, mb = 36.0, 8.0, 10.0, 20.0            # marges: links y-labels, onder x-labels
    iw, ih = W - ml - mr, H - mt - mb
    xs = [p[0] for p in points]
    x0, x1 = xs[0], xs[-1]
    xspan = (x1 - x0) or 1.0
    allvals = vals + [p[1] for p in prev]
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
        pxs = [p[0] for p in prev]
        pspan = (pxs[-1] - pxs[0]) or 1.0
        pfx = lambda t: ml + (t - pxs[0]) / pspan * iw
        ppoly = " ".join(f"{pfx(p[0]):.1f},{fy(p[1]):.1f}" for p in prev)
        prevline = f"<polyline points='{ppoly}' fill='none' stroke='var(--subtle)' stroke-width='1.2' stroke-dasharray='3 3'/>"
    poly = " ".join(f"{fx(p[0]):.1f},{fy(p[1]):.1f}" for p in points)
    line = f"<polyline points='{poly}' fill='none' stroke='var(--green)' stroke-width='1.8'/>"
    dots = "".join(f"<circle cx='{fx(p[0]):.1f}' cy='{fy(p[1]):.1f}' r='2.2' fill='var(--green)'/>" for p in points)
    return (f"<svg class='linechart' viewBox='0 0 {W:.0f} {H:.0f}' width='100%' height='140' preserveAspectRatio='xMidYMid meet'>"
            f"{axis}{ylab}{xlab}{prevline}{line}{dots}</svg>")


def _bar_chart_svg(points, unit: str = "") -> str:
    """Staafdiagram voor een reeks (server-side SVG): één staaf per datapunt, 0-basislijn + datumbereik.
    De headline staat in het kaart-skelet erboven; dit levert alleen de grafiek. 0 punten → 'geen data';
    1 punt → korte notitie."""
    if not points:
        return _geen_data_html()
    import datetime as _dt
    vals = [p[1] for p in points]
    if len(points) < 2:
        return "<div class='muted kc-hint'>1 meetpunt</div>"
    W, H = 300.0, 140.0
    ml, mr, mt, mb = 36.0, 8.0, 10.0, 20.0
    iw, ih = W - ml - mr, H - mt - mb
    ymax = max(vals + [0]); ymin = min(0, min(vals)); yspan = (ymax - ymin) or 1.0
    fy = lambda v: mt + (1 - (v - ymin) / yspan) * ih
    slot = iw / len(points); bw = slot * 0.7; y0 = fy(0)
    bars = ""
    for i, p in enumerate(points):
        v = p[1]
        x = ml + i * slot + (slot - bw) / 2
        yv = fy(v); top = min(yv, y0); h = abs(yv - y0)
        bars += f"<rect x='{x:.1f}' y='{top:.1f}' width='{bw:.1f}' height='{max(0.5, h):.1f}' rx='1' fill='var(--green)'/>"
    axis = (f"<line x1='{ml:.1f}' y1='{mt:.1f}' x2='{ml:.1f}' y2='{mt+ih:.1f}' stroke='var(--border)' stroke-width='1'/>"
            f"<line x1='{ml:.1f}' y1='{fy(0):.1f}' x2='{ml+iw:.1f}' y2='{fy(0):.1f}' stroke='var(--border)' stroke-width='1'/>")
    ylab = (f"<text x='{ml-4:.1f}' y='{fy(ymax)+3:.1f}' text-anchor='end' font-size='9' fill='var(--muted)'>{_num(ymax)}</text>"
            f"<text x='{ml-4:.1f}' y='{fy(ymin)+3:.1f}' text-anchor='end' font-size='9' fill='var(--muted)'>{_num(ymin)}</text>")
    fmt = lambda ts: _dt.datetime.fromtimestamp(ts).strftime('%d-%m')
    xlab = (f"<text x='{ml:.1f}' y='{H-5:.1f}' text-anchor='start' font-size='9' fill='var(--muted)'>{_e(fmt(points[0][0]))}</text>"
            f"<text x='{ml+iw:.1f}' y='{H-5:.1f}' text-anchor='end' font-size='9' fill='var(--muted)'>{_e(fmt(points[-1][0]))}</text>")
    return (f"<svg class='barchart' viewBox='0 0 {W:.0f} {H:.0f}' width='100%' height='140' "
            f"preserveAspectRatio='xMidYMid meet'>{axis}{ylab}{xlab}{bars}</svg>")


def _combo_svg(a_points, b_points, a_label: str = "", b_label: str = "") -> str:
    """Metric-vs-metric combo: reeks A als staven (linker-as, groen), reeks B als lijn (rechter-as,
    koraal). Dubbele y-as, want twee metingen met mogelijk verschillende eenheden. Fail-loud als een
    van beide geen reeks levert (geen verzonnen nul-lijn)."""
    a = [(p[0], p[1]) for p in (a_points or []) if isinstance(p[1], (int, float))]
    b = [(p[0], p[1]) for p in (b_points or []) if isinstance(p[1], (int, float))]
    if not a or not b:
        return "<div class='muted kc-hint'>geen twee reeksen om te combineren in dit venster</div>"
    import datetime as _dt
    W, H = 300.0, 140.0
    ml, mr, mt, mb = 34.0, 32.0, 10.0, 20.0
    iw, ih = W - ml - mr, H - mt - mb
    xs = [t for t, _ in a] + [t for t, _ in b]
    x0, x1 = min(xs), max(xs); xspan = (x1 - x0) or 1.0
    amax = max(v for _, v in a); amin = min(0, min(v for _, v in a)); aspan = (amax - amin) or 1.0
    bmax = max(v for _, v in b); bmin = min(0, min(v for _, v in b)); bspan = (bmax - bmin) or 1.0
    fx = lambda t: ml + (t - x0) / xspan * iw
    fya = lambda v: mt + (1 - (v - amin) / aspan) * ih
    fyb = lambda v: mt + (1 - (v - bmin) / bspan) * ih
    slot = iw / max(1, len(a)); bw = slot * 0.6; y0 = fya(0)
    bars = ""
    for t, v in a:
        x = fx(t) - bw / 2; yv = fya(v); top = min(yv, y0); h = abs(yv - y0)
        bars += (f"<rect x='{x:.1f}' y='{top:.1f}' width='{max(1.0, bw):.1f}' "
                 f"height='{max(0.5, h):.1f}' rx='1' fill='var(--green)' opacity='.6'/>")
    poly = " ".join(f"{fx(t):.1f},{fyb(v):.1f}" for t, v in b)
    line = f"<polyline points='{poly}' fill='none' stroke='var(--coral)' stroke-width='1.8'/>"
    dots = "".join(f"<circle cx='{fx(t):.1f}' cy='{fyb(v):.1f}' r='2.2' fill='var(--coral)'/>" for t, v in b)
    axis = (f"<line x1='{ml:.1f}' y1='{mt:.1f}' x2='{ml:.1f}' y2='{mt+ih:.1f}' stroke='var(--border)' stroke-width='1'/>"
            f"<line x1='{ml+iw:.1f}' y1='{mt:.1f}' x2='{ml+iw:.1f}' y2='{mt+ih:.1f}' stroke='var(--border)' stroke-width='1'/>"
            f"<line x1='{ml:.1f}' y1='{mt+ih:.1f}' x2='{ml+iw:.1f}' y2='{mt+ih:.1f}' stroke='var(--border)' stroke-width='1'/>")
    ylab = (f"<text x='{ml-4:.1f}' y='{fya(amax)+3:.1f}' text-anchor='end' font-size='9' fill='var(--green-dark)'>{_num(amax)}</text>"
            f"<text x='{ml+iw+4:.1f}' y='{fyb(bmax)+3:.1f}' text-anchor='start' font-size='9' fill='var(--coral)'>{_num(bmax)}</text>")
    fmt = lambda t: _dt.datetime.fromtimestamp(t).strftime('%d-%m')
    xlab = (f"<text x='{ml:.1f}' y='{H-5:.1f}' text-anchor='start' font-size='9' fill='var(--muted)'>{_e(fmt(x0))}</text>"
            f"<text x='{ml+iw:.1f}' y='{H-5:.1f}' text-anchor='end' font-size='9' fill='var(--muted)'>{_e(fmt(x1))}</text>")
    svg = (f"<svg class='combochart' viewBox='0 0 {W:.0f} {H:.0f}' width='100%' height='140' "
           f"preserveAspectRatio='xMidYMid meet'>{axis}{ylab}{xlab}{bars}{line}{dots}</svg>")
    legend = (f"<div class='muted'><span class='chip'>{_e(a_label)} (staaf)</span> "
              f"<span class='chip amber'>{_e(b_label)} (lijn)</span></div>")
    return f"{svg}{legend}"


_CAT_PALETTE = ["var(--green)", "var(--green-dark)", "var(--yellow)", "var(--coral)", "var(--subtle)", "var(--muted)"]


def _stacked_bar_svg(rows) -> str:
    """Gestapelde staaf (deel-op-geheel) voor een categorie-uitsplitsing: één horizontale staaf,
    per categorie een segment, met een legenda. 0 rijen → 'geen data'."""
    rows = [(l, n) for l, n in (rows or []) if isinstance(n, (int, float))]
    if not rows:
        return _geen_data_html()
    total = sum(n for _, n in rows) or 1
    W, H = 300.0, 30.0
    x = 0.0; segs = ""; legend = ""
    for i, (l, n) in enumerate(rows[:6]):
        w = n / total * W; col = _CAT_PALETTE[i % len(_CAT_PALETTE)]
        segs += f"<rect x='{x:.1f}' y='0' width='{max(0.5, w):.1f}' height='{H}' fill='{col}'/>"
        x += w
        legend += f"<span class='chip outline'>{_e(str(l))}: {_num(n)}</span> "
    svg = (f"<svg class='stackbar' viewBox='0 0 {W:.0f} {H:.0f}' width='100%' height='30' "
           f"preserveAspectRatio='none'>{segs}</svg>")
    return f"<div class='tile-trend'>{svg}<div class='muted'>{legend}</div></div>"


def _hbar_svg(rows) -> str:
    """Horizontale balken (gesorteerd) voor een categorie-uitsplitsing: één balk per categorie.
    0 rijen → 'geen data'."""
    rows = sorted([(l, n) for l, n in (rows or []) if isinstance(n, (int, float))],
                  key=lambda r: r[1], reverse=True)[:8]
    if not rows:
        return _geen_data_html()
    mx = max((n for _, n in rows), default=1) or 1
    W = 300.0; rowh = 18.0; H = len(rows) * rowh; lx = 96.0
    bars = ""
    for i, (l, n) in enumerate(rows):
        y = i * rowh; w = max(0.5, n / mx * (W - lx - 30))
        bars += (f"<text x='{lx-6:.1f}' y='{y+rowh*0.68:.1f}' text-anchor='end' font-size='9' fill='var(--ink)'>{_e(str(l)[:16])}</text>"
                 f"<rect x='{lx:.1f}' y='{y+3:.1f}' width='{w:.1f}' height='{rowh-6:.1f}' rx='1' fill='var(--green)'/>"
                 f"<text x='{lx+w+3:.1f}' y='{y+rowh*0.68:.1f}' font-size='9' fill='var(--muted)'>{_num(n)}</text>")
    return (f"<svg class='hbar' viewBox='0 0 {W:.0f} {H:.0f}' width='100%' height='{H:.0f}' "
            f"preserveAspectRatio='xMidYMid meet'>{bars}</svg>")


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
    # Interne bronnen die live uit de stores rekenen (geen sleutel nodig, meteen data).
    srcs.append({"id": f"projects:{rec.id}", "label": "Projecten",
                 "measures": [("afgerond", "Afgerond"), ("lopend", "In uitvoering"),
                              ("doorlooptijd", "Doorlooptijd (dagen)")],
                 "dims": [("over_tijd", "over tijd"), ("totaal", "totaal"), ("per_status", "per status")]})
    srcs.append({"id": f"inbox:{rec.id}", "label": "Inbox / spanningen",
                 "measures": [("verwerkt", "Verwerkt"), ("open", "Open")],
                 "dims": [("over_tijd", "over tijd"), ("totaal", "totaal"), ("per_type", "per uitkomst")]})
    srcs.append({"id": "co2", "label": "LLM-gebruik & CO₂",
                 "measures": [("gram_co2e", "CO₂ (gram)"), ("calls", "LLM-calls"),
                              ("ongeschat_calls", "Calls zonder telling")],
                 "dims": [("over_tijd", "over tijd"), ("totaal", "totaal")]})
    nodes = [rec.id] + ([r.id for r in org.roles_of(st.records.all(), rec.id)] if is_c else [])
    for k in st.metrics.kpis_for_nodes(nodes):
        if k.get("source"):
            continue                                  # bron-KPI's al gedekt door built-ins
        dims = [("time", "over tijd"), ("none", "laatste waarde")]        # 'none' → geen "· NONE"
        dimension = _source_dimensions().get(k.get("origin") or k.get("source"))
        if dimension and k.get("veld") and dimension in _DIM_LABEL:        # scope 2/4: bron mét DIMENSION
            dims.append(_DIM_LABEL[dimension])                             # 'per keyword' (GSC) / 'per land' (Plausible)
        srcs.append({"id": f"kpi:{k['id']}", "label": k["name"],
                     "measures": [("value", "waarde")],                    # niet de KPI-naam → geen dubbele naam
                     "dims": dims})
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
    pts = filter_samples(samples, cutoff, end)     # [(at, value, datum), ...] binnen het venster
    vals = [p[1] for p in pts]
    unit = "/10" if measure == "tevredenheid" else ("min" if measure == "duur" else "")
    if dim == "over_tijd":
        return {"kind": "series", "points": pts, "unit": unit}
    if dim == "totaal" and measure != "tevredenheid":
        return {"kind": "number", "value": (sum(vals) if vals else None), "unit": unit}
    avg = round(sum(vals) / len(vals), 1) if vals else None   # gemiddeld (en tevredenheid-totaal)
    return {"kind": "number", "value": avg, "unit": unit}


# ── Interne bronnen: projecten-doorstroom, inbox/spanningen, LLM-gebruik & CO₂ ──────────────────
# Deze rekenen LIVE uit de stores (geen aparte observatie-schrijf nodig), dus ze hebben meteen data.
# Fail-loud: geen data in het venster → lege reeks (→ 'geen data'), nooit een verzonnen nul.
_PROJ_STATUS_LABEL = {"draft": "concept", "queued": "wachtrij", "running": "in uitvoering",
                      "blocked": "geblokkeerd", "future": "toekomst", "done": "afgerond"}


def _project_scope(st: _Stores, node: str) -> set:
    """De node zelf, plus (op een cirkel) de rollen eronder — zodat een cirkel de projecten van haar
    rollen meetelt, net als de werkoverleg-bron."""
    rec = st.records.get(node)
    if rec is None:
        return {node}
    if org.is_circle(rec):
        return {rec.id} | {r.id for r in org.roles_of(st.records.all(), rec.id)}
    return {rec.id}


def _project_fetch(st: _Stores, node: str, measure: str, dim: str, cutoff, end=None):
    projs = [p for p in st.projects.all() if p.get("owner") in _project_scope(st, node)]
    if dim == "per_status":
        counts: dict = {}
        for p in projs:
            if p.get("archived"):
                continue
            counts[p.get("status", "")] = counts.get(p.get("status", ""), 0) + 1
        rows = sorted(((_PROJ_STATUS_LABEL.get(s, s or "?"), n) for s, n in counts.items()),
                      key=lambda x: -x[1])
        return {"kind": "breakdown", "rows": rows, "unit": "projecten"}
    if measure == "lopend":
        return {"kind": "number", "value": sum(1 for p in projs if p.get("status") == "running"),
                "unit": "projecten"}
    if measure == "doorlooptijd":                    # gemiddelde doorlooptijd (dagen) van afgeronde projecten
        samples = []
        for p in projs:
            up, cr = p.get("updated_at"), p.get("created_at")
            if p.get("status") == "done" and up and cr:
                samples.append({"at": up, "value": max(0.0, (up - cr)) / 86400.0, "datum": _day_key(up)})
        pts = filter_samples(samples, cutoff, end)
        if dim == "over_tijd":
            return {"kind": "series", "points": pts, "unit": "dagen", "chart": "line"}
        vals = [v for _a, v, _d in pts]
        return {"kind": "number", "value": (round(sum(vals) / len(vals), 1) if vals else None),
                "unit": "dagen"}
    # measure == "afgerond": doorstroom — afgeronde projecten per dag (updated_at = afrondmoment)
    by_day: dict = {}
    for p in projs:
        at = p.get("updated_at")
        if p.get("status") == "done" and at:
            e = by_day.setdefault(_day_key(at), [0, at])
            e[0] += 1
            e[1] = max(e[1], at)
    samples = [{"at": at, "value": c, "datum": d} for d, (c, at) in by_day.items()]
    pts = filter_samples(samples, cutoff, end)
    if dim == "over_tijd":
        return {"kind": "series", "points": pts, "unit": "projecten", "chart": "line"}
    return {"kind": "number", "value": (sum(v for _a, v, _d in pts) if pts else 0), "unit": "projecten"}


def _inbox_targets(st: _Stores, node: str) -> set:
    rec = st.records.get(node)
    if rec is not None and org.is_circle(rec):
        return {("role", r.id) for r in org.roles_of(st.records.all(), rec.id)} | {("role", rec.id)}
    return {("role", node)}


def _inbox_fetch(st: _Stores, node: str, measure: str, dim: str, cutoff, end=None):
    tgts = _inbox_targets(st, node)
    items = [n for n in st.notif.all()
             if (n.get("target_type"), n.get("target_id")) in tgts and not n.get("deleted")]
    if dim == "per_type":                            # uitkomsten per type (uit de verwerkingen)
        counts: dict = {}
        for n in items:
            for v in st.notif.verwerkingen_of(n):
                counts[v.get("otype") or "onbekend"] = counts.get(v.get("otype") or "onbekend", 0) + 1
        rows = sorted(((k, v) for k, v in counts.items()), key=lambda x: -x[1])
        return {"kind": "breakdown", "rows": rows, "unit": ""}
    if measure == "open":
        n = sum(1 for it in items if not it.get("processed") and not it.get("archived"))
        return {"kind": "number", "value": n, "unit": ""}
    # measure == "verwerkt": verwerkte spanningen per dag (op verwerkmoment = laatste verwerking, anders at)
    by_day: dict = {}
    for it in items:
        if not it.get("processed"):
            continue
        vs = st.notif.verwerkingen_of(it)
        at = (vs[-1].get("at") if vs else None) or it.get("at")
        if not at:
            continue
        e = by_day.setdefault(_day_key(at), [0, at])
        e[0] += 1
        e[1] = max(e[1], at)
    samples = [{"at": at, "value": c, "datum": d} for d, (c, at) in by_day.items()]
    pts = filter_samples(samples, cutoff, end)
    if dim == "over_tijd":
        return {"kind": "series", "points": pts, "unit": "", "chart": "line"}
    return {"kind": "number", "value": (sum(v for _a, v, _d in pts) if pts else 0), "unit": ""}


def _co2_fetch(st: _Stores, measure: str, dim: str, cutoff, end=None):
    """Dorpsbrede LLM-uitstoot/-gebruik uit de dag-observaties (bron=co2_village, gevoed door de pulse)."""
    metric, bron = _obs_key_for_indicator("co2_village", measure)
    if not metric:
        return {"kind": "number", "value": None, "unit": ""}
    samples = [{"at": _row_at(r), "value": r["value"], "datum": r.get("datum")}
               for r in st.observations.daily_series(metric, bron=bron)]
    pts = filter_samples(samples, cutoff, end)
    unit = _measure_unit("co2", measure)
    if dim == "totaal":
        vals = [v for _a, v, _d in pts]
        return {"kind": "number", "value": (sum(vals) if vals else None), "unit": unit}
    return {"kind": "series", "points": pts, "unit": unit, "chart": "line"}


def _default_form(dim: str) -> str:
    return {"time": "trend", "over_tijd": "trend", "none": "getal", "totaal": "getal",
            "per_status": "horizontaal", "per_type": "horizontaal"}.get(dim, "verdeling")


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
    if source.startswith("projects:"):
        return "dagen" if measure == "doorlooptijd" else "projecten"
    if source == "co2":
        return "g CO₂e" if measure == "gram_co2e" else "calls"
    return ""


def _daily_obs_series(st: _Stores, source: str, measure: str, cutoff, end=None):
    """Dezelfde dagreeks-route als de bezoekers-tegel: leest de dag-observaties (daily_series) voor
    (source, measure) en levert een series-res voor het lijn-diagram (chart:'line'). None als deze
    bron/measure geen dag-observatie-mapping heeft. Lege dagreeks → lege points (→ 'geen data')."""
    metric, bron = _daily_obs_key(source, measure)
    if not metric:
        return None
    samples = [{"at": _row_at(r), "value": r["value"], "datum": r.get("datum")}
               for r in st.observations.daily_series(metric, bron=bron)]
    if cadence_of(metric, bron) == "irregular":
        samples = _collapse_daily_mean(samples)     # meerdere meetpunten/dag → één punt = dag-gemiddelde
    return {"kind": "series", "points": filter_samples(samples, cutoff, end),
            "unit": _measure_unit(source, measure), "chart": "line"}


def _collapse_daily_mean(samples: list) -> list:
    """Klap meerdere meetpunten op dezelfde meetdag samen tot één punt = het dag-GEMIDDELDE. Nodig voor
    irreguliere reeksen (bv. werkoverleg: meerdere overleggen/dag) zodat de tegel per dag het gemiddelde
    toont i.p.v. twee losse punten of alleen de laatste. Regulier (≤1/dag) is dit een no-op. De
    per-overleg-observaties blijven ongewijzigd in de store; dit is puur de display-samenvatting.
    (De twee irreguliere observatie-metrics — tevredenheid en duur — zijn beide 'gemiddelde'-aard.)"""
    by_day: dict = {}
    for s in samples:
        by_day.setdefault(s.get("datum") or _day_key(s["at"]), []).append(s)
    out = []
    for _d, ss in by_day.items():
        vals = [x["value"] for x in ss if isinstance(x["value"], (int, float))]
        if vals:
            out.append({"at": max(x["at"] for x in ss), "value": sum(vals) / len(vals),
                        "datum": ss[0].get("datum")})
    return out


def _def_obs_key(st: _Stores, did: str):
    """(metric, bron) voor een catalogus-def-id — de ÉNE gedeelde def-resolutie, voor zowel de losse
    tegel als de formule-operand (reference, don't copy). Loopt via _obs_key_for_indicator, zodat een
    def-operand exact dezelfde metric-id oplevert als een KPI/tegel op diezelfde indicator. Werk-defs
    binden aan de werkoverleg-bron via hun werk_measure. (None, None) = def onbekend / geen obs-veld."""
    c = st.defs.current(did) or {}
    wm = c.get("werk_measure")
    if wm:
        return _obs_key_for_indicator("werkoverleg", wm)
    return _obs_key_for_indicator(c.get("source", ""), c.get("veld", ""))


def _def_series(st: _Stores, did: str, cutoff, end=None) -> dict:
    """Dagreeks-res voor een `def:<id>`-operand in een formule. Resolvet via de gedeelde _def_obs_key en
    leest de dag-observaties. FAIL-LOUD (nooit meer een stille lege cel):
      - niet resolvebaar → issue='unresolved' + WARNING FORMULA_OPERAND_UNRESOLVED
      - resolvet, maar de metric-id heeft geen rijen → issue='empty' + WARNING FORMULA_OPERAND_EMPTY"""
    metric, bron = _def_obs_key(st, did)
    if not metric:
        log.warning("FORMULA_OPERAND_UNRESOLVED def:%s — def onbekend of zonder observatie-veld", did)
        return {"kind": "series", "points": [], "issue": "unresolved"}
    raw = st.observations.daily_series(metric, bron=bron)
    if not raw:
        log.warning("FORMULA_OPERAND_EMPTY def:%s → %s (bron=%s) levert geen rijen", did, metric, bron)
    samples = [{"at": _row_at(r), "value": r["value"], "datum": r.get("datum")} for r in raw]
    return {"kind": "series", "points": filter_samples(samples, cutoff, end),
            "issue": None if raw else "empty"}


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
    if source.startswith("projects:"):
        return _project_fetch(st, source[len("projects:"):], measure, dim, cutoff, end)
    if source.startswith("inbox:"):
        return _inbox_fetch(st, source[len("inbox:"):], measure, dim, cutoff, end)
    if source == "co2":
        return _co2_fetch(st, measure, dim, cutoff, end)
    if source.startswith("kpi:"):
        it = st.metrics.get(source[4:])
        if not it:
            return {"kind": "number", "value": None, "unit": ""}
        if dim in _DIM_KEYS:                # scope 2/4: uitsplitsing per dimensie-waarde (keyword/land) → breakdown
            base, bron = _obs_key_for_indicator(it.get("source") or it.get("origin") or "", it.get("veld", ""))
            rows = []
            if base:
                for kw, series in st.observations.dimensioned_series(base, bron=bron).items():
                    pts = filter_samples([{"at": _row_at(r), "value": r["value"], "datum": r.get("datum")}
                                          for r in series], cutoff, end)
                    if pts:
                        rows.append((kw, pts[-1][1]))       # laatste waarde binnen het venster per keyword
            rows.sort(key=lambda x: (-(x[1] or 0), x[0]))
            return {"kind": "breakdown", "rows": rows, "unit": it.get("unit", "")}
        raw = _kpi_samples(st, it)          # bron+veld → dagreeks uit de store; anders legacy/handmatig
        return {"kind": "series", "points": filter_samples(raw, cutoff, end), "unit": it.get("unit", "")}
    return {"kind": "number", "value": None, "unit": ""}


def _num(v):
    return f"{v:g}" if isinstance(v, (int, float)) else "—"


def _agg(res, agg: str = DEFAULT_AGGREGATIE):
    """De headline-waarde van een resultaat, samengevat over het venster volgens de aggregatieregel:
    som = optellen, gemiddelde = Ø, laatste_waarde = laatste punt. Breakdown = som van de rijen;
    number = de waarde zelf (aggregatie niet van toepassing)."""
    if res["kind"] == "series":
        pts = res.get("points") or []
        vals = [p[1] for p in pts if isinstance(p[1], (int, float))]
        if not vals:
            return None
        if agg == "som":
            return sum(vals)
        if agg == "gemiddelde":
            return sum(vals) / len(vals)
        return pts[-1][1]                       # laatste_waarde (stand)
    if res["kind"] == "breakdown":
        return sum(n for _, n in res.get("rows", [])) if res.get("rows") else None
    return res.get("value")


def _tile_agg(st: _Stores, source: str, measure: str) -> str:
    """De aggregatieregel (som/gemiddelde/laatste_waarde) waarmee de headline over het venster wordt
    samengevat. Eén bron: de catalogus (definitions.aggregatie_for op (bron, veld)); een kpi:-item dat
    z'n eigen regel draagt gaat voor. Onbekend → DEFAULT_AGGREGATIE (laatste_waarde = stand)."""
    if source.startswith("kpi:"):
        it = st.metrics.get(source[4:]) or {}
        return (it.get("aggregatie")
                or aggregatie_for(it.get("source") or it.get("origin") or "", it.get("veld", ""))
                or DEFAULT_AGGREGATIE)
    if source == "pulse_visitors":              # legacy bron-id → canonieke plausible-reeks
        return aggregatie_for("plausible", measure) or DEFAULT_AGGREGATIE
    if source.startswith("werk:"):
        return aggregatie_for("werkoverleg", measure) or DEFAULT_AGGREGATIE
    if source.startswith("projects:"):
        return {"afgerond": "som", "lopend": "laatste_waarde", "doorlooptijd": "gemiddelde"}.get(
            measure, DEFAULT_AGGREGATIE)
    if source.startswith("inbox:"):
        return {"verwerkt": "som", "open": "laatste_waarde"}.get(measure, DEFAULT_AGGREGATIE)
    if source == "co2":
        return "som"                              # dorpsbrede uitstoot/gebruik telt op over het venster
    return aggregatie_for(source, measure) or DEFAULT_AGGREGATIE   # shopify e.d.


def _render_bullet(res, target, richting, benchmark="", agg=DEFAULT_AGGREGATIE) -> str:
    """Bullet graph (Few): waarde-balk + doel-tick + een 'goed'-zone, richtingbewust. Vervangt de
    vlakke doelmeter: toont in één balk waar je staat t.o.v. het doel, met de benchmark als label."""
    v = _agg(res, agg)
    try:
        t = float(target)
    except (TypeError, ValueError):
        t = 0.0
    if not isinstance(v, (int, float)) or t <= 0:
        return _render_form(res, "doelmeter", target, agg=agg)   # val terug op de simpele meter
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
    # De waarde staat in de kaart-headline; hier de balk + doel-tick + het doel/benchmark als context.
    return (f"<div class='bullet-wrap'><div class='bullet-h'><span class='muted'>doel {_num(t)}</span></div>"
            f"{svg}{bm}</div>")


def _data_table(res, bron: str = "") -> str:
    """Tufte 'show the data': de exacte ruwe datapunten onder een grafiek (datum · waarde · bron)."""
    kind = res.get("kind")
    b = _e(bron or "—")
    if kind == "series":
        pts = res.get("points") or []
        if not pts:
            return ""
        # géén afkapping: de tabel toont exact dezelfde dataset als de grafiek (zelfde venster, alle punten).
        rows = "".join(f"<tr><td>{_pt_datum_label(p)}</td>"
                       f"<td class='num'>{_num(p[1])}</td><td>{b}</td></tr>" for p in pts)
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
        poly = " ".join(f"{fx(p[0]):.1f},{fy(p[1]):.1f}" for p in pts)
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


def _render_form(res, form, target=None, prev=None, agg=DEFAULT_AGGREGATIE):
    unit = res.get("unit", "")
    kind = res.get("kind")
    # Vorm/dimensie-mismatch: val terug op een zinnige vorm i.p.v. een lege melding.
    if form in ("verdeling", "tabel") and kind != "breakdown":
        form = "trend" if kind == "series" else "getal"
    if form == "trend" and kind != "series":
        form = "getal"
    if form == "trend":
        # In een KPI-kaart ALTIJD het lijn-diagram met assen (0-lijn + datumbereik); nooit een assenloze
        # sparkline. Sparklines mogen alleen in compacte lijstrijen (_kpi_card / _kpi_data_row).
        pts = res.get("points") or []
        return _line_chart_svg(pts, res.get("unit", ""), prev=(prev or {}).get("points"))
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
        # De waarde staat in de kaart-headline; hier alleen de voortgangsbalk + het doel als context.
        v = _agg(res, agg) or 0
        t = target or 0
        pct = int(min(100, v / t * 100)) if t else 0
        return (f"<div class='goal'><span class='bar-t'><span class='bar-f' style='width:{pct}%'></span></span>"
                f"<span class='muted'>doel {_num(t)}</span></div>")
    # getal — de headline in het kaart-skelet toont de waarde; hier geen dubbel getal. Bij geen data
    # (None) toont het skelet niets, dus tonen we hier de 'geen data'-melding (één keer, geen dubbel).
    return _geen_data_html() if _agg(res, agg) is None else ""


# Grondslag-laag (GAAP/IRIS): definitie, eenheid, bron, richting per bron-measure.
_SOURCE_GRONDSLAG = {
    "pulse_visitors|visitors": ("Unieke websitebezoekers per dag (dagreeks uit de observaties).",
                                "bezoekers", "observations (Plausible-dagwaarde)", "up"),
    "shopify|pairs_sold": ("Verkochte paren uit betaalde orders.", "paren", "Shopify", "up"),
    "shopify|orders": ("Aantal betaalde orders.", "orders", "Shopify", "up"),
    "shopify|revenue": ("Omzet uit betaalde orders.", "EUR", "Shopify", "up"),
    "shopify|aov": ("Gemiddelde orderwaarde (omzet ÷ orders).", "EUR", "Shopify", "up"),
    "co2|gram_co2e": ("Geschatte CO₂-uitstoot van alle LLM-calls in het dorp.", "g CO₂e",
                      "co2_village (llm_usage.jsonl)", "down"),
    "co2|calls": ("Aantal LLM-calls in het dorp.", "calls", "co2_village (llm_usage.jsonl)", ""),
    "co2|ongeschat_calls": ("LLM-calls zonder tokentelling (schatting).", "calls",
                            "co2_village (llm_usage.jsonl)", "down"),
}
_PROJECT_GRONDSLAG = {
    "afgerond": ("Afgeronde projecten (status 'done') per periode.", "projecten", "up"),
    "lopend": ("Projecten die nu in uitvoering zijn (status 'running').", "projecten", ""),
    "doorlooptijd": ("Gemiddelde doorlooptijd (aangemaakt → afgerond) van afgeronde projecten.",
                     "dagen", "down"),
}
_INBOX_GRONDSLAG = {
    "verwerkt": ("Verwerkte spanningen/berichten per periode.", "", "up"),
    "open": ("Nog openstaande (onverwerkte) items in de inbox.", "", "down"),
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
    if source.startswith("projects:"):
        d, u, r = _PROJECT_GRONDSLAG.get(measure, ("", "", ""))
        return {"definitie": d, "eenheid": u, "bron": "Projectenboek", "richting": r,
                "drempel": None, "cadans": "", "meettype": "", "venster": ""}
    if source.startswith("inbox:"):
        d, u, r = _INBOX_GRONDSLAG.get(measure, ("", "", ""))
        return {"definitie": d, "eenheid": u, "bron": "Inbox / notificaties", "richting": r,
                "drempel": None, "cadans": "", "meettype": "", "venster": ""}
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
        out = (llm.reason(prompt, call_site="metrics_reeks_vergelijkbaar") or "").strip().lower()
        return "vergelijkbaar" in out and "breuk" not in out
    except Exception:
        return False


def _compare_delta(res, prev_res, agg=DEFAULT_AGGREGATIE) -> str:
    """Delta-badge: aggregaat van de huidige periode vs. dat van de vorige periode, volgens dezelfde
    aggregatieregel. Alleen zichtbaar als 'Vergelijk met vorige periode' aan staat."""
    cur, prv = _agg(res, agg), _agg(prev_res, agg)
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
        # Via dezelfde generieke bron-veld-derivatie als een plausible/visitors-KPI (één sleutel-route):
        # levert plausible_visitors_day — identieke waardes, geen aparte special-case meer.
        return _obs_key_for_indicator("plausible", "visitors")
    if source.startswith("werk:") and measure in WERK_DAILY:
        return (WERK_DAILY[measure], "werkoverleg")
    if source == "shopify" and measure in SHOPIFY_DAILY:
        return (SHOPIFY_DAILY[measure], "shopify")
    return (None, None)


# ── Data-vers-signaal per indicator (3 staten), gedeeld door koppelscherm + KPI-wizard ──────────
# Vaste drempel voor de huidige dagelijkse bronnen. LATER: cadans-bewuste drempel (mediaan inter-punt-
# interval) zodra er trage bronnen zijn die met 7 dagen ten onrechte als 'dood' worden gemarkeerd.
_FRESH_DAYS = 7
# Bron-velden waarvoor 'recente data' zin heeft (data-bronnen). Manueel/formule/kpi → geen signaal.
# AFGELEID uit de geregistreerde DataSourceSkills (zie _data_source_classes) plus de legacy niet-skill-
# bron 'werkoverleg' — geen handmatige literal meer die achterloopt op de registry.
def _data_sources() -> set:
    return {getattr(cls, "SOURCE", "") for cls in _data_source_classes()} | {"werkoverleg"}


def _source_dimensions() -> dict:
    """{bron-id: DIMENSION} voor skills die een dimensie declareren (class-attr DIMENSION), afgeleid uit
    de skills zelf — geen aparte lijst. Nu {'gsc':'query', 'plausible':'country'}."""
    return {cls.SOURCE: cls.DIMENSION for cls in _data_source_classes() if getattr(cls, "DIMENSION", None)}


# DIMENSION → (tegel-dim-sleutel, label in de composer). De dim-sleutel is wat de tegel opslaat; _fetch
# behandelt elke dim-sleutel hieruit als een breakdown per dimensie-waarde.
_DIM_LABEL = {"query": ("keyword", "per keyword"), "country": ("country", "per land"),
              "concept": ("concept", "per concept")}
_DIM_KEYS = {k for k, _l in _DIM_LABEL.values()}


def _obs_key_for_indicator(source: str, veld: str, dim: str = ""):
    """(observatie-metric, bron) voor een catalogus-indicator. Canoniek schema: `<source>_<veld>_day`
    met bron=`<source>`. `dim` (een dimensie-slug, bijv. een Library-keyword) hangt als `::<dim>`-suffix
    aan de sleutel → `<source>_<veld>_day::<dim>` — de dimensie-naad (scope 2). Zonder `dim` ongewijzigd.
    Werkoverleg houdt z'n legacy cirkel-sleutel (buiten het API-mechanisme). (None, None) = geen bron-veld."""
    from nooch_village.observations import WERK_DAILY
    if source == "werkoverleg" and veld in WERK_DAILY:
        return (WERK_DAILY[veld], "werkoverleg")
    if source in _data_sources() and veld:
        base = f"{source}_{veld}_day"
        return (f"{base}::{dim}" if dim else base, source)
    return (None, None)


# ── Snapshot vs flux: declaratief van de DataSourceSkill (niet geraden uit daily_values) ─────────
_PERIOD_DAYS = {"daily": 1, "weekly": 7, "monthly": 30}
_PERIOD_LABEL = {"daily": "dag", "weekly": "week", "monthly": "maand"}


def _data_source_classes():
    """De DataSourceSkill-klassen — AFGELEID uit de skill-registry (de bron van waarheid), niet meer een
    handmatige lijst die uiteendreef met de werkelijkheid. Elke geregistreerde DataSourceSkill is zo
    automatisch koppelbaar (kind/frequency/velden komen uit de class-attributen). Ontdubbeld op klasse,
    volgorde-stabiel. Fail-soft: een registry-bouwfout → lege tuple (de metrics-view crasht nooit)."""
    try:
        from nooch_village.registry_factory import build_skill_registry
        from nooch_village.skills import DataSourceSkill
        seen, out = set(), []
        for s in build_skill_registry().all():
            cls = type(s)
            if isinstance(s, DataSourceSkill) and getattr(cls, "SOURCE", None) and cls not in seen:
                seen.add(cls)
                out.append(cls)
        return tuple(out)
    except Exception:
        return ()


def _source_kind(source: str) -> str:
    """'snapshot' of 'flux' — declaratief van de DataSourceSkill, niet afgeleid uit hoe daily_values
    toevallig geschreven is. Onbekende bron → 'flux' (het bestaande gedrag)."""
    for sk in _data_source_classes():
        if sk.SOURCE == source:
            return getattr(sk, "kind", "flux")
    return "flux"


def _source_frequency(source: str) -> str:
    for sk in _data_source_classes():
        if sk.SOURCE == source:
            return getattr(sk, "DEFAULT_FREQUENCY", "daily")
    return "daily"


def _snapshot_delta(points, frequency: str):
    """Genormaliseerde delta van een cumulatieve snapshot-reeks: (laatste stand − vorige stand),
    geschaald naar de frequentie-periode. `points` = [(ts, value), ...]. Geeft (delta_per_periode,
    interval_dagen), of (None, None) bij < 2 metingen. Het interval is het WERKELIJKE aantal dagen
    tussen de twee gebruikte metingen, zodat een delta over een gemiste periode niet misleidt."""
    pts = sorted([p for p in (points or []) if p[1] is not None], key=lambda p: p[0])
    if len(pts) < 2:
        return None, None
    t_prev, v_prev = pts[-2][0], pts[-2][1]
    t_last, v_last = pts[-1][0], pts[-1][1]
    interval_days = max(1, round((t_last - t_prev) / 86400))    # meetdag-as → écht aantal dagen ertussen
    period = _PERIOD_DAYS.get(frequency, 7)
    return (v_last - v_prev) * period / interval_days, interval_days


def _snapshot_body(st: _Stores, tile: dict, frequency: str):
    """(body, data) voor een snapshot-tegel: standaard de genormaliseerde delta (+N/periode) met het
    werkelijke meet-interval; de absolute stand + oplopende reeks blijven beschikbaar in de uitklap."""
    metric, bron = _obs_key_for_indicator(tile["source"], tile["measure"])
    rows = st.observations.daily_series(metric, bron=bron) if metric else []
    points = _obs_points(rows)                         # (meetdag-as, waarde, datum), datum-gesorteerd
    delta, interval = _snapshot_delta(points, frequency)
    stand = points[-1][1] if points else None
    plabel = _PERIOD_LABEL.get(frequency, "periode")
    if delta is None:
        body = "<div class='kpi-val'><span class='muted'>nog te weinig metingen</span></div>"
    else:
        sign = "+" if delta >= 0 else "−"
        body = (f"<div class='kpi-val'>{sign}{_num(abs(round(delta)))}"
                f" <span class='muted'>/{_e(plabel)}</span></div>"
                f"<div class='muted'>gemeten over {interval} dagen · stand nu: {_num(stand)}</div>")
    data = ""
    if points:
        dt = _data_table({"kind": "series", "points": points}, bron=bron)
        data = f"<details class='tile-data'><summary>ruwe data (absolute stand)</summary>{dt}</details>"
    return body, data


def _fresh_threshold(source: str) -> int:
    """De vers-drempel in dagen. Flux → vast 7. Snapshot → de frequentie-periode + marge (weekly ≈10,
    monthly ≈45), zodat een net-gemeten snapshot niet vroegtijdig 'dood' lijkt en een gemiste periode
    wél. Het kind-veld stuurt hier — de eerder uitgestelde drempel-per-frequentie-koppeling."""
    if _source_kind(source) != "snapshot":
        return _FRESH_DAYS
    period = _PERIOD_DAYS.get(_source_frequency(source), 7)
    return period + max(3, period // 2)


def indicator_freshness(st, source: str, veld: str, today=None):
    """Vier staten van een indicator, uit DEZELFDE observatie-store als de tegels:
      'fresh'        = datapunt ≤ _FRESH_DAYS dagen oud            → bron vult
      'stale'        = reeks bestaat, laatste punt ouder           → gekoppeld-maar-dood (API/data kapot)
      'unconfigured' = bron actief maar creds ontbreken            → eigen status, los van 'dood'
      'none'         = geen reeks (bron inactief of niet gevoed)
    Geeft None terug voor niet-bron-velden (manueel/formule) → dan géén chip tonen."""
    if source not in _data_sources():
        return None
    srcs = getattr(st, "sources", None)
    if srcs is not None and srcs.active(source) and srcs.configured(source) is False:
        return "unconfigured"        # ontbrekende creds ≠ kapotte API
    metric, bron = _obs_key_for_indicator(source, veld)
    if not metric:
        return "none"
    rows = st.observations.daily_series(metric, bron=bron)
    datum = rows[-1].get("datum") if rows else None
    if not datum:
        return "none"
    import datetime
    try:
        age = ((today or datetime.date.today()) - datetime.date.fromisoformat(datum)).days
    except (TypeError, ValueError):
        return "none"
    return "fresh" if age <= _fresh_threshold(source) else "stale"


_FRESH_META = {"fresh": "green", "stale": "coral", "none": "muted", "unconfigured": "amber"}


def freshness_chip(state) -> str:
    """De 3-staten-chip (recente data / geen recente data / geen data). '' voor None (geen bron-veld)."""
    if state not in _FRESH_META:
        return ""
    return (f"<span class='chip {_FRESH_META[state]}' title='{_e(t('data.vers.' + state + '.tip'))}'>"
            f"{_e(t('data.vers.' + state))}</span>")


_WIN_LABEL = {"7d": "7d", "28d": "28d", "kwartaal": "kwartaal", "jaar": "jaar",
              "gisteren": "gisteren", "vandaag": "vandaag", "actueel": "actueel", "aangepast": "periode"}


def _agg_label(agg: str, win: str, res, end, now: float | None = None) -> str:
    """Label bij de headline volgens de aggregatieregel: 'totaal 7d' (som), 'Ø per dag' (gemiddelde),
    'stand per <datum>' (laatste_waarde). Een stand die vandaag gemeten is → 'stand per nu' (last-standen
    pakken vandaag mee). Hergebruikt .muted; geen nieuwe klasse/inline-style."""
    if res.get("kind") not in ("series", "number", "breakdown"):
        return ""
    if agg == "som":
        return f"<div class='muted'>totaal {_e(_WIN_LABEL.get(win, 'periode'))}</div>"
    if agg == "gemiddelde":
        return "<div class='muted'>Ø per dag</div>"
    # laatste_waarde: 'stand per nu' als de laatste meetdag vandaag is, anders 'stand per <datum>'.
    import datetime as _dt
    today = _dt.datetime.fromtimestamp(now).strftime('%Y-%m-%d') if now else None
    pts = res.get("points") or []
    if pts:
        last = pts[-1]
        ld = last[2] if len(last) > 2 and last[2] else _dt.datetime.fromtimestamp(last[0]).strftime('%Y-%m-%d')
        if today and ld == today:
            return "<div class='muted'>stand per nu</div>"
        return f"<div class='muted'>stand per {_e(_pt_datum_label(last))}</div>"
    if end:
        d = _dt.datetime.fromtimestamp(end - 1).strftime('%d-%m-%y')   # end exclusief → laatste dag = end-1
        return f"<div class='muted'>stand per {_e(d)}</div>"
    return ""


def _range_label(cutoff, end) -> str:
    """Expliciet datumbereik van het venster: '03-07 t/m 09-07'. Leeg bij een open venster (Actueel)."""
    if cutoff is None or end is None:
        return ""
    import datetime as _dt
    a = _dt.datetime.fromtimestamp(cutoff).strftime('%d-%m')
    b = _dt.datetime.fromtimestamp(end - 1).strftime('%d-%m')          # end exclusief → laatste dag = end-1
    return f"<div class='muted'>{a} t/m {b}</div>"


def _tile_headline(res, agg: str, win: str, cutoff, end, now: float | None = None) -> str:
    """Het vaste kaart-skelet-kopblok: headline (venster-aggregaat, kpi-val) + aggregatielabel +
    datumbereik. Eén plek, voor élke vorm gelijk. Waarde None → "" (het skelet toont dan niets; de
    visual/getal-tak toont zelf 'geen data'), zodat er nooit een dubbele 'geen data' verschijnt."""
    v = _agg(res, agg)
    if v is None:
        return ""
    unit = res.get("unit", "")
    u = f" <span class='kpi-unit'>{_e(unit)}</span>" if unit else ""
    num = f"<div class='kpi-val'>{_num(v)}{u}</div>"
    return num + _agg_label(agg, win, res, end, now) + _range_label(cutoff, end)


def _render_tile(st: _Stores, rec, tile, cutoff, csrf: str, end=None, compare=False,
                 prev_win=None, actueel=False, win: str = "", now: float | None = None) -> str:
    if tile.get("form") == "formule":          # fail-closed live-berekening A op B per dag
        return _render_formula_tile(st, rec, tile, csrf, cutoff, end)
    import time as _t
    now = now if now is not None else _t.time()
    g = _grondslag(st, tile["source"], tile["measure"])
    goal = ""
    gp = st.projects.get(tile.get("goal_pid")) if tile.get("goal_pid") else None
    form = tile.get("form", "getal")
    agg = _tile_agg(st, tile["source"], tile["measure"])   # venster-samenvatregel voor de headline
    # last-standen pakken vandaag WÉL mee (headline 'stand per nu'): effectief venster-einde = nu i.p.v.
    # middernacht vandaag. som/gemiddelde blijven strikt complete dagen (vandaag uit).
    end_eff = now if (agg == "laatste_waarde" and end is not None) else end
    # 'Actueel' = laatste bekende dagwaarde uit de observatie-store (dezelfde betekenis als Plausible);
    # geen dag-observaties voor deze bron → 'geen live data'.
    ak_metric, ak_bron = _daily_obs_key(tile["source"], tile["measure"]) if actueel else (None, None)
    if _source_kind(tile["source"]) == "snapshot" and not actueel:
        # Snapshot-bron: standaard de genormaliseerde delta (+N/periode), niet de oplopende stand.
        body, data = _snapshot_body(st, tile, _source_frequency(tile["source"]))
        res = {"kind": "number", "value": None}       # delta-tegel → geen drempel-warn op een stand
    elif actueel:
        rows = st.observations.daily_series(ak_metric, bron=ak_bron) if ak_metric else []
        pts = _obs_points(rows)                        # datum-gesorteerd → [-1] = laatste MEETDAG
        latest = pts[-1][1] if pts else None
        res = {"kind": "number", "value": latest}
        body = (f"<div class='kpi-val'>{_num(latest)}</div>" if latest is not None
                else f"<div class='kpi-val'><span class='muted'>{_e(t('dashboard.geen_live_data'))}</span></div>")
        data = ""
        if pts:
            dt = _data_table({"kind": "series", "points": pts}, bron=ak_bron)
            data = f"<details class='tile-data'><summary>ruwe data</summary>{dt}</details>"
    else:
        res = _fetch(st, tile["source"], tile["measure"], tile.get("dim", "none"), cutoff, end_eff)
        prev_res = None
        if compare and prev_win and prev_win[0] is not None:
            prev_res = _fetch(st, tile["source"], tile["measure"], tile.get("dim", "none"), prev_win[0], prev_win[1])
        # De VISUAL (grafiek/meter/bars) — zonder eigen headline-getal; het skelet levert de headline.
        cmp_meas = tile.get("cmp_measure")
        if cmp_meas:                                     # metric-vs-metric combo (staaf A + lijn B, dubbele as)
            b_res = _fetch(st, tile.get("cmp_source") or tile["source"], cmp_meas,
                           tile.get("cmp_dim", "over_tijd"), cutoff, end_eff)
            visual = _combo_svg(res.get("points") or [], b_res.get("points") or [],
                                tile["measure"], cmp_meas)
        elif form == "burnup":
            visual = _render_burnup(res, tile.get("target"), gp)
        elif form in ("doelmeter", "bullet"):          # bullet = de definitieve naam (Tufte-beslistabel)
            visual = _render_bullet(res, tile.get("target"), g.get("richting"), g.get("benchmark"), agg=agg)
        elif form == "staaf":
            visual = _bar_chart_svg(res.get("points") or [], res.get("unit", ""))
        elif form == "gestapeld":
            visual = _stacked_bar_svg(res.get("rows"))
        elif form == "horizontaal":
            visual = _hbar_svg(res.get("rows"))
        else:
            visual = _render_form(res, form, tile.get("target"), prev=prev_res, agg=agg)
        # ÉÉN kaart-skelet: headline (venster-aggregaat) + aggregatielabel + datumbereik ALTIJD bovenaan,
        # dan de visual. Burnup houdt z'n eigen kop (doel-prognose) en krijgt geen los skelet-getal.
        head = "" if form == "burnup" else _tile_headline(res, agg, win, cutoff, end_eff, now)
        body = head + visual
        # Delta alleen bij 'Vergelijk met vorige periode': aggregaat huidig venster vs. vorig, zelfde regel.
        if compare and prev_res is not None and res.get("chart") != "line" and not cmp_meas:
            body += _compare_delta(res, prev_res, agg=agg)
        # Uitklap: de exacte ruwe datapunten (datum · waarde · bron) — zelfde dataset als de grafiek.
        data = ""
        if form in ("trend", "staaf", "verdeling", "horizontaal", "gestapeld", "doelmeter", "bullet", "burnup"):
            dt = _data_table(res, bron=g.get("bron", tile["source"]))
            if dt:
                data = f"<details class='tile-data'><summary>ruwe data</summary>{dt}</details>"
    if gp is not None:
        due = _fmt_due(gp.get("due")) if gp.get("due") else ""
        goal = (f"<div class='tile-goal muted'>naar doel: <b>{_e(str(gp.get('scope') or gp['id'])[:50])}</b>"
                f"{(' · ' + _e(due)) if due else ''}</div>")
    # Drempel-signaal (Kaizen 'aandacht nodig'): waarde de verkeerde kant op t.o.v. de drempel.
    warn = ""
    thr, val = g.get("drempel"), _agg(res, agg)
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
        standaard=cur.get("standaard", ""), waarde=cur.get("waarde"),
        veld=cur.get("veld", ""), categorie=cur.get("categorie", ""), aard=cur.get("aard", ""),
        aggregatie=cur.get("aggregatie", ""))
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
    raw = _kpi_samples(st, it)
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
    for p in pts:
        d = p[2] if len(p) > 2 and p[2] else _dt.datetime.fromtimestamp(p[0]).strftime("%Y-%m-%d")
        w.writerow([d, p[1], it.get("unit", "")])
    safe = "".join(c if c.isalnum() else "_" for c in (it.get("name") or "kpi"))[:40]
    return f"{safe}.csv", buf.getvalue()


def _kpi_data_row(st: _Stores, item: dict, csrf: str) -> str:
    raw = _kpi_samples(st, item)
    pts = filter_samples(raw, None)
    val = _num(pts[-1][1]) if pts else "—"
    unit = f" {_e(item.get('unit', ''))}" if item.get("unit") else ""
    # systeem-gemeten KPI (bron/auto/meetwijze): geen handmatige invoer
    is_sys = _is_system_kpi(item)
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


def _metrics_manage_html(st: _Stores, rec, csrf: str = "") -> str:
    """Het beheer-blok onder het dashboard: eigen (handmatige) KPI's om data in te voeren, de aanvullende
    lijst systeem-KPI's (automatisch gevoed, nog niet getegeld), en links naar externe cijfers. Eén bron,
    hergebruikt door zowel het oude als het nieuwe metrics-scherm zodat er niets verloren gaat."""
    out = ""
    tiles = st.metrics.tiles_of(rec.id)
    kpis = [i for i in st.metrics.for_node(rec.id) if i.get("kind") == "kpi"]
    # Systeem-KPI's die AL als tegel op dit dashboard staan niet nóg eens in de lijst tonen: de lijst is
    # aanvullend ("wat kan ik nog meer activeren"), geen herhaling van de tegels bovenaan.
    tiled_kids = {t.get("source", "")[4:] for t in tiles if t.get("source", "").startswith("kpi:")}
    # Een systeembron-KPI (bron/auto/meetwijze) hoort NOOIT in de invoer-sectie — hij heeft geen handmatige
    # meting. Het criterium is _is_system_kpi (meetwijze/auto/origin/source), niet alleen `source`.
    handmatig = [i for i in kpis if not _is_system_kpi(i)]
    systeem = [i for i in kpis if _is_system_kpi(i) and i["id"] not in tiled_kids]
    if handmatig:
        rows = "".join(_kpi_data_row(st, i, csrf) for i in handmatig)
        out += f"<div class='c2-sec'><div class='cl-head'><h3>Eigen KPI's (data invoeren)</h3></div>{rows}</div>"
    if systeem:
        rows = "".join(_kpi_data_row(st, i, csrf) for i in systeem)
        out += f"<div class='c2-sec'><div class='cl-head'><h3>Systeem-KPI's (automatisch gevoed)</h3></div>{rows}</div>"
    links = st.metrics.links_for(rec.id)
    if links:
        lc = "".join(_link_card(i, csrf) for i in links)
        out += f"<div class='c2-sec'><div class='cl-head'><h3>Links</h3></div><div class='kpi-grid'>{lc}</div></div>"
    return out


def _add_link_details(rec, csrf: str, nxt: str) -> str:
    """De '+ Link'-affordance (externe cijfers die elders leven). Gedeeld tussen oud en nieuw scherm."""
    return (f"<details class='m-add'><summary class='btn sm'>+ Link</summary>"
            f"<form method='post' action='/action' class='m-addform'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf)}'><input type='hidden' name='node' value='{_e(rec.id)}'>"
            f"<input type='hidden' name='next' value='{_e(nxt)}'>"
            f"<input name='name' placeholder='Naam' autocomplete='off'>"
            f"<input name='url' placeholder='https://…' autocomplete='off'>"
            f"<button class='btn ok sm' type='submit' name='action' value='m_add_link'>Link toevoegen</button></form></details>")


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

    # Periode-opties = een dropdown-menu (Plausible-stijl), hergebruik van het bestaande cardmenu-patroon
    # (details/summary + .menuitem, zoals het status-menu in projects). Elke optie blijft een reload-link
    # (GET &mw=…); de summary toont de actieve periode. Sneltoets-hint per optie via <kbd>.
    def opt(k, lbl):
        on = " on" if win == k else ""
        key = _MW_KEYS.get(k, "")
        kbd = f" <kbd>{_e(key)}</kbd>" if key else ""
        if k == "actueel" and not live:               # alleen bij een live-capabele bron
            return f"<span class='menuitem muted' title='alleen beschikbaar bij een live-capabele bron'>{_e(lbl)}{kbd}</span>"
        u = f"{nav}&mw={k}" if nav else f"{base}&mw={k}{cmp_q}"
        cls = "menuitem js-modal" if nav else "menuitem"
        dh = f" data-href='{u}'" if nav else ""
        return f"<a class='{cls}{on}' href='{u}'{dh}>{_e(lbl)}{kbd}</a>"
    active_lbl = dict(_MW).get(win, "Periode")
    periode_lbl = _e(t('dashboard.periode'))
    dd = (f"<details class='cardmenu'><summary class='statustrigger' aria-label='periode kiezen'>"
          f"{_e(active_lbl)} <span class='caret'>▾</span></summary><div class='cardmenu-b'>"
          f"<div class='menu-h'>{periode_lbl}</div>" + "".join(opt(k, lbl) for k, lbl in _MW) + "</div></details>")
    wbar = f"<div class='cl-bar'><span class='muted'>{periode_lbl}</span> {dd}"
    if not nav:
        ct = " on" if compare else ""
        ct_url = f"{base}&mw={_e(win)}" + ("" if compare else "&compare=1")
        wbar += (f"<span class='switch-field'>{_e(t('dashboard.vergelijk'))} "
                 f"<a class='switch{ct}' href='{ct_url}' role='switch' "
                 f"aria-checked='{'true' if compare else 'false'}' title='vergelijk met de vorige periode'></a></span>")
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
    # Single-key sneltoetsen voor de periode-dropdown (alleen op de hoofdpagina, niet in de modal).
    # Vuurt niet in invoervelden of met modifier-toetsen; navigeert naar &mw=<optie>.
    keys_js = ""
    if not nav:
        import json as _json
        kmap = {v.lower(): f"{base}&mw={k}{cmp_q}" for k, v in _MW_KEYS.items()
                if not (k == "actueel" and not live)}
        keys_js = ("<script>(function(){var M=" + _json.dumps(kmap) + ";"
                   "document.addEventListener('keydown',function(e){"
                   "if(e.metaKey||e.ctrlKey||e.altKey)return;"
                   "var t=e.target||{},tn=(t.tagName||'').toLowerCase();"
                   "if(tn==='input'||tn==='textarea'||tn==='select'||t.isContentEditable)return;"
                   "var u=M[(e.key||'').toLowerCase()];if(u)location.href=u;});})();</script>")

    # 1. Dashboard van tegels (de KPI's) — één centrale periode voor alle tegels
    dash = ("".join(_render_tile(st, rec, t, start, csrf, end=end, compare=compare, prev_win=prev_win,
                                 actueel=(win == "actueel"), win=win, now=now) for t in tiles) if tiles
            else "<p class='muted'>Nog geen KPI's op het dashboard. Maak er een met “+ KPI maken”.</p>")
    out = f"<div class='c2-sec'>{head}</div><div class='c2-sec'><div class='tile-grid'>{dash}</div></div>{_METRICS_JS}{keys_js}"

    # 2/3. Het beheer-blok (eigen KPI's om data in te voeren, systeem-KPI's, links) — gedeeld met het
    # nieuwe metrics-scherm zodat de migratie niets van deze functionaliteit verliest.
    out += _metrics_manage_html(st, rec, csrf)
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


def _def_value(st: _Stores, c: dict, did: str, circle: str) -> tuple[str, bool]:
    """(resolutie-value, has_data) voor één catalogus-def. Werk-defs binden aan de cirkel en tonen de
    reeks (aggregatie zit al vast in de def, deelopdracht 1); plausible/shopify-defs mappen op hun live
    data-pad; de rest blijft def:id met liveness uit de bron-whitelist."""
    wm = c.get("werk_measure")
    if wm and circle:
        return f"werk:{circle}|{wm}|over_tijd", True     # werk blijft cirkel-gebonden: def:<id> heeft geen cirkel-slot
    src = c.get("source", "")
    # Observatie-gebaseerde indicatoren (plausible/shopify/…) → uniform def:<id>. De formule- én
    # tegel-resolutie leiden de metric-id af via _def_obs_key. De plausible-visitors-special-case is
    # weg (werd wél nog geresolved): def:<id> resolveert nu symmetrisch naar plausible_visitors_day én
    # plausible_pageviews_day, zodat "pageviews ÷ visitors" niet meer stil leeg rekent.
    return f"def:{did}", (src in _LIVE_DEF_SOURCES)


def _wizard_indicators(st: _Stores, rec) -> list[dict]:
    """Eén regel per metric: de geconsolideerde catalogus-defs (één per metric), gegroepeerd op
    categorie, elk met z'n resolutie-value + liveness (via `_def_value`). Werk staat één keer (via
    werk_measure), niet meer als losse gemiddeld/totaal/over-tijd-combos."""
    circle = rec.id if rec is not None else ""
    out = []
    for d in st.defs.all():
        c = st.defs.current(d["id"]) or {}
        name = c.get("name")
        if not name:
            continue
        value, live = _def_value(st, c, d["id"], circle)
        out.append({"value": value, "name": name, "categorie": c.get("categorie") or "Overig",
                    "aard": c.get("aard") or "moment", "has_data": live,
                    "bron": c.get("source", ""), "veld": c.get("veld", ""),
                    "uitleg": c.get("definition", "")})
    # node-eigen handmatige KPI's blijven kiesbaar (categorie 'Eigen KPI's'), één regel per KPI.
    if rec is not None:
        for s in _sources_for(st, rec):
            if not s["id"].startswith("kpi:"):
                continue
            for mid, ml in s["measures"]:
                out.append({"value": f"{s['id']}|{mid}|time", "name": ml, "categorie": "Eigen KPI's",
                            "aard": "reeks", "has_data": True, "bron": "handmatig", "uitleg": ""})
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
    for p in (res.get("points") or []):
        out[_day_key(p[0])] = (p[0], p[1])
    return out


def _formula_daily(st: _Stores, tile, cutoff, end=None) -> list[dict]:
    """Per-dag A op B over twee bronnen, FAIL-CLOSED: mist één bron een dag, dan is die dag no_data
    (nooit doorrekenen met een oude waarde, nooit stilzwijgend 0). Deling door 0 → ook no_data.
    Geeft rijen [{at, value, no_data}] voor álle dagen die in minstens één bron voorkomen."""
    issues: list = []

    def _map(combo, label):
        combo = combo or ""
        if combo.startswith("def:"):          # def:<id>-operand → gedeelde def-resolutie (fail-loud in _def_series)
            res = _def_series(st, combo[4:], cutoff, end)
            if res.get("issue"):
                issues.append({"operand": label, "code": res["issue"]})
            return _series_day_map(res)
        parts = combo.split("|")
        if len(parts) != 3 or not parts[0]:   # onparseerbare combo → fail-loud (nooit meer stil leeg)
            log.warning("FORMULA_OPERAND_UNRESOLVED operand %s=%r — geen parseerbare vorm", label, combo)
            issues.append({"operand": label, "code": "unresolved"})
            return {}
        return _series_day_map(_fetch(st, parts[0], parts[1], parts[2], cutoff, end))

    amap = _map(tile.get("f_a"), "A")
    bmap = _map(tile.get("f_b"), "B")
    op = _FORMULA_OPS.get(tile.get("f_op", "÷"))
    rows = []
    for day in sorted(set(amap) | set(bmap)):
        at = (amap.get(day) or bmap.get(day))[0]
        av = amap.get(day, (None, None))[1]
        bv = bmap.get(day, (None, None))[1]
        val = None if (av is None or bv is None or op is None) else op(av, bv)
        rows.append({"at": at, "value": None if val is None else round(val, 4),
                     "datum": day, "no_data": val is None})
    return rows, issues


def _render_formula_tile(st: _Stores, rec, tile, csrf: str, cutoff=None, end=None) -> str:
    """Formule-tegel: live A op B per dag, fail-closed. Grafiek toont alleen dagen MÉT waarde
    (no_data = gat, nooit 0/interpolatie); de tabel toont ÁLLE dagen met no_data expliciet."""
    rows, issues = _formula_daily(st, tile, cutoff, end)
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
    # fail-loud: een operand die niet resolvet of geen rijen levert → zichtbare hint (nooit stil leeg)
    if issues:
        _lbl = {"unresolved": "bron onbekend", "empty": "bron levert geen data"}
        _txt = "; ".join(f"operand {i['operand']}: {_lbl.get(i['code'], i['code'])}" for i in issues)
        body += f"<div class='muted'>⚠ {_e(_txt)}</div>"
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
    cat_chips = "".join(f"<button type='button' class='chip-opt kc-cat' data-cat='{_e(c)}'>{_e(c)}</button>"
                        for c in cats)

    def _radio(i: dict) -> str:
        dis = "" if i["has_data"] else " disabled"
        mut = "" if i["has_data"] else " muted"
        tip = "Bron: " + (i["bron"] or "—") + (f" · {i['uitleg']}" if i["uitleg"] else "")
        # één regel per metric: de aard als tag (reeks/moment/categorie), of grijs 'nog geen data'
        tag = (f"<span class='chip outline'>{_e(AARD_LABEL.get(i['aard'], i['aard']))}</span>"
               if i["has_data"] else "<span class='chip muted'>nog geen data</span>")
        # tweede signaal naast de aard-tag: levert de bron recente data? (gedeelde helper, 3 staten)
        vers = freshness_chip(indicator_freshness(st, i["bron"], i.get("veld", "")))
        return (f"<label class='kc-radio kc-metric{mut}' data-cat='{_e(i['categorie'])}' "
                f"data-aard='{_e(i['aard'])}' data-name='{_e(i['name'].lower())}' hidden>"
                f"<input type='radio' name='combo' value='{_e(i['value'])}'{dis}> "
                f"<span class='kc-mname' title='{_e(tip)}'>{_e(i['name'])}</span> {tag}{vers}</label>")
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
        "<p class='muted kc-hint'>Kies eerst een categorie</p>"
        f"<div class='chip-wrap kc-cats'>{cat_chips}</div>"
        "<div class='kc-picked' hidden>"
        "<p class='muted kc-hint kc-picked-label'></p>"
        "<input class='kc-search' type='text' placeholder='Zoek binnen deze categorie…' autocomplete='off' hidden>"
        f"<div class='kc-metrics'>{metrics_html}</div></div>"
        "<p class='muted kc-hint kc-empty'>Kies hierboven een categorie om de indicatoren te zien. "
        "Metrics zonder data staan grijs; wijs de naam aan voor uitleg.</p></div>"
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

    step4_inner = (f"<input type='hidden' name='node' value='{_e(node_id)}'>") if not standalone else (
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
            + step("3", "Standaard weergave (volgt de aard, niet bindend)",
                   "<select name='form'><option value=''>—</option></select>"
                   "<p class='muted kc-hint kc-tufte'>Kies eerst een indicator; de weergaves die bij de "
                   "aard passen verschijnen dan.</p>")
            + step4_inner
            + "<button class='btn ok' type='submit' name='action' value='tile_add' disabled>Kies eerst een indicator</button></form>")
    main = (f"<div class='c2-main'><div class='c2-bar'><a href='{back}'>← terug</a></div>"
            f"<h1>KPI maken <span class='chip'>focus</span></h1>{_banner(msg)}"
            f"<p class='muted'>Een KPI is alleen de definitie van wat je meet. Periode en weergave kies "
            f"je op het dashboard.</p>"
            f"<div class='c2-sec'>{form}</div></div>")
    inner = (f"{_DS_LINK}"
             f"<div class='bar'>cockpit 2 · GlassFrog (PoC) · build {_BUILD} · <a href='/'>home</a> · "
             "<a href='/catalog'>catalogus</a></div>"
             f"<div class='c2-wrap'>{main}</div>{_KPI_COMPOSER_JS}")
    return _page("KPI maken", inner)


_KPI_COMPOSER_JS = """<script>
(function(){
 var f=document.querySelector('.kc-form'); if(!f) return;
 var modeInp=f.querySelector('[name=mode]');
 var formSel=f.querySelector('[name=form]'), tgt=f.querySelector('[name=target]');
 var tufteEl=f.querySelector('.kc-tufte');
 var search=f.querySelector('.kc-search');
 var picked=f.querySelector('.kc-picked'), pickLbl=f.querySelector('.kc-picked-label');
 var empty=f.querySelector('.kc-empty');
 var btn=f.querySelector('button[value=tile_add]');
 // stap 3 — Tufte-beslistabel: de passende vormen per aard × referentie. De eerste is de aanbevolen
 // (voorgeselecteerd), met de reden als microcopy. Dit is de ENIGE plek die de vorm van een tegel bepaalt.
 var VORMEN={
  'reeks|0':[{v:'trend',l:'Trend (lijn)',t:'een reeks over tijd lees je het snelst als één lijn.'},
             {v:'staaf',l:'Staaf',t:'losse periodes naast elkaar zetten? staven.'},
             {v:'getal',l:'Getal',t:'alleen de samengevatte waarde, zonder ruis.'}],
  'reeks|1':[{v:'bullet',l:'Bullet (waarde vs doel)',t:'waarde tegen de doellijn in één balk (Few).'},
             {v:'trend',l:'Trend (lijn)',t:'de reeks over tijd als lijn.'},
             {v:'getal',l:'Getal',t:'de samengevatte waarde.'}],
  'moment|0':[{v:'getal',l:'Getal',t:'een momentopname is per definitie één getal.'}],
  'moment|1':[{v:'getal',l:'Getal',t:'een momentopname is per definitie één getal.'}],
  'categorie|0':[{v:'gestapeld',l:'Gestapelde staaf',t:'deel-op-geheel in één gestapelde staaf.'},
                 {v:'horizontaal',l:'Horizontale balk',t:'veel categorieën? horizontale balken, gesorteerd.'}],
  'categorie|1':[{v:'gestapeld',l:'Gestapelde staaf',t:'deel-op-geheel in één gestapelde staaf.'},
                 {v:'horizontaal',l:'Horizontale balk',t:'veel categorieën? horizontale balken, gesorteerd.'}]
 };
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

 // categorie VERPLICHT eerst: lijst leeg tot een categorie is gekozen; zoekbalk alleen bij >8 items.
 function filter(cat,q){
   q=(q||'').toLowerCase();
   f.querySelectorAll('.kc-metric').forEach(function(m){
     m.hidden=!((m.dataset.cat===cat) && (!q || (m.dataset.name||'').indexOf(q)>=0));
   });
 }
 function countCat(cat){var n=0;
   f.querySelectorAll('.kc-metric').forEach(function(m){if(m.dataset.cat===cat)n++;}); return n;}
 f.querySelectorAll('.kc-cat').forEach(function(c){c.addEventListener('click',function(){
   f.querySelectorAll('.kc-cat').forEach(function(x){x.classList.toggle('on',x===c);});
   var cat=c.dataset.cat;
   if(empty) empty.hidden=true;
   if(picked) picked.hidden=false;
   if(pickLbl) pickLbl.textContent=cat+' — kies een indicator';
   if(search){ search.hidden=(countCat(cat)<=8); search.value=''; }
   filter(cat,'');
 });});
 if(search) search.addEventListener('input',function(){
   var a=f.querySelector('.kc-cat.on'); if(a) filter(a.dataset.cat, search.value);
 });

 // referentie: benchmark/doel-conditionals + de vergelijkwaarde in het verborgen target-veld
 function syncRef(){
   var rk=ref();
   f.querySelectorAll('.kc-cond').forEach(function(c){c.hidden=(c.dataset.for!==rk);});
   var bt=f.querySelector('[name=bench_target]'), dt=f.querySelector('[name=doel_target]');
   tgt.value = rk==='benchmark'?(bt?bt.value:'') : rk==='doel'?(dt?dt.value:'') : '';
 }

 function syncBtn(){
   if(modeInp.value==='formule'){ btn.disabled=false; btn.textContent='Maak KPI — formule'; return; }
   var r=f.querySelector('.kc-metric input:checked');
   btn.disabled=!r; btn.textContent = r ? 'Maak KPI' : 'Kies eerst een indicator';
 }

 // stap 3: herbereken de vorm-opties zodra aard (gekozen indicator) of referentie wijzigt.
 function showTufte(){
   var o=formSel.options[formSel.selectedIndex];
   if(tufteEl) tufteEl.textContent = (o && o.dataset.t) ? 'Tufte: '+o.dataset.t : '';
 }
 function syncVorm(){
   if(!curAard){ formSel.innerHTML="<option value=''>—</option>";
     if(tufteEl) tufteEl.textContent='Kies eerst een indicator; de weergaves die bij de aard passen verschijnen dan.';
     return; }
   var list=VORMEN[curAard+'|'+(ref()?1:0)]||VORMEN['reeks|0'];
   var keep=formSel.value, has=false;
   formSel.innerHTML='';
   list.forEach(function(o,i){
     var opt=document.createElement('option');
     opt.value=o.v; opt.textContent=o.l+(i===0?' — aanbevolen':''); opt.dataset.t=o.t;
     formSel.appendChild(opt); if(o.v===keep) has=true;
   });
   formSel.value = has ? keep : list[0].v;      // behoud een nog-geldige keuze, anders de aanbevolen
   showTufte();
 }
 formSel.addEventListener('change',showTufte);

 f.addEventListener('change',function(e){
   var nm=e.target && e.target.name;
   if(nm==='combo'){var lab=e.target.closest('.kc-metric'); curAard=lab?lab.dataset.aard:'';}
   if(nm==='combo'||nm==='ref_kind'){ syncRef(); syncVorm(); }
   syncBtn();
 });
 f.addEventListener('input',syncRef);
 setMode('indicator'); syncRef(); syncVorm(); syncBtn();
})();
</script>"""
