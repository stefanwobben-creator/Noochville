"""Keyword-lenzen (IA-fase 3) — vier rollen, ÉÉN datalaag.

Elke rol kijkt via een lens naar dezelfde `build_keyword_layer`-laag; ze delen de cijfers i.p.v.
elk een eigen bron te tellen. Een lens-switcher bovenaan maakt zichtbaar dat het één laag is,
vier keer bekeken. Read-only; curatie/nominatie komt in fase 4.

Lenzen:
- marketing : volume + richting — waar maak je content voor (approved doelwit-woorden).
- scientist : nieuwe signalen — opkomst/stijgend vs. blip (Sid's trend-herindexering).
- trends    : kansrijkheid + suggesties — de scout-analyse (Billy Buzz).
- library   : convergentie — waar signaal + volume + open status samenkomen (Lara's cureer-lens).
"""
from __future__ import annotations

from nooch_village.web_base import _e, _page
from nooch_village.cockpit2_util import _DS_LINK, _nav
from nooch_village.keyword_layer import build_keyword_layer, converges

_LENSES = [
    ("marketing", "Marketing", "volume + richting — waar maak je content voor"),
    ("scientist", "Scientist", "nieuwe signalen — opkomst vs. blip"),
    ("trends", "Trends & Competition", "kansrijkheid + suggesties"),
    ("library", "Library", "convergentie — waar curatie loont"),
]
_LENS_KEYS = {k for k, _l, _d in _LENSES}

_STATUS_CHIP = {"approved": "chip green", "escalated": "chip amber",
                "forbidden": "chip coral"}
_SIGNAL_LABEL = {"emergence": "opkomst", "trend": "stijgend", "peak": "blip", "flat": "vlak"}
_SIGNAL_CHIP = {"emergence": "chip green", "trend": "chip green",
                "peak": "chip amber", "flat": "chip muted"}
_SIGNAL_ORDER = {"emergence": 0, "trend": 1, "peak": 2, "flat": 3}


def _num(v) -> str:
    if isinstance(v, (int, float)):
        return f"{v:,.0f}".replace(",", ".") if v >= 1000 else f"{v:g}"
    return "—"


def _status_chip(status) -> str:
    return f"<span class='{_STATUS_CHIP.get(status, 'chip muted')}'>{_e(status or '—')}</span>"


def _signal_chip(st) -> str:
    return f"<span class='{_SIGNAL_CHIP.get(st, 'chip muted')}'>{_e(_SIGNAL_LABEL.get(st, '—'))}</span>"


def _window(row) -> str:
    m = row.get("recent_months") or []
    if not m:
        return "—"
    return f"{m[0]} – {m[-1]}" if len(m) > 1 else m[0]


def _table(headers: str, body_rows: str) -> str:
    return f"<table class='mtab'><tr>{headers}</tr>{body_rows}</table>"


def _leeg(tekst: str) -> str:
    return f"<p class='muted'>{tekst}</p>"


# ── de vier lenzen ─────────────────────────────────────────────────────────────

def _lens_marketing(rows: list) -> str:
    items = [r for r in rows if (r.get("volume") or 0) > 0 or
             (r.get("status") == "approved" and r.get("function") == "doelwit")]
    items.sort(key=lambda r: -(r.get("volume") or 0))
    if not items:
        return _leeg("Nog geen woorden met volume. Zet de verrijking aan (Keywords Everywhere, GSC) "
                     "zodat volume en richting binnenkomen.")
    body = "".join(
        f"<tr><td>{_e(r['term'])}</td>{('<td>' + _status_chip(r['status']) + '</td>')}"
        f"<td class='num'>{_num(r.get('volume'))}</td>"
        f"<td>{_e(r.get('direction') or '—')}</td>"
        f"<td class='num'>{_num(r.get('opportunity'))}</td></tr>" for r in items)
    return _table("<th>Woord</th><th>Status</th><th class='num'>Volume</th><th>Richting</th>"
                  "<th class='num'>Kansrijkheid</th>", body)


def _lens_scientist(rows: list) -> str:
    items = [r for r in rows if r.get("in_trends")]
    items.sort(key=lambda r: (_SIGNAL_ORDER.get(r.get("signal_type") or "flat", 9),
                              -(r.get("recent_sustained") or 0)))
    signalen = [r for r in items if r.get("is_signal")]
    if not items:
        return _leeg("Nog geen trend-observaties. De dagelijkse trend-herindexering (Sid) vult de laag.")
    tel = (f"<p class='muted'><b>{len(signalen)}</b> van {len(items)} termen zijn een écht signaal "
           f"(opkomst of stijgend, geen blip).</p>")
    body = "".join(
        f"<tr><td>{_e(r['term'])}</td><td>{_signal_chip(r.get('signal_type'))}</td>"
        f"<td class='num'>{_num(r.get('recent_sustained'))}</td>"
        f"<td class='num'>{_num(r.get('peak'))}</td>"
        f"<td>{_e(_window(r))}</td>"
        f"<td class='num'>{'✓' if r.get('is_signal') else '—'}</td></tr>" for r in items)
    return tel + _table("<th>Term</th><th>Signaal</th><th class='num'>Recent</th>"
                        "<th class='num'>Piek</th><th>Venster</th><th class='num'>Signaal?</th>", body)


def _lens_trends(rows: list) -> str:
    items = [r for r in rows if r.get("in_library")]
    items.sort(key=lambda r: -(r.get("opportunity") or 0))
    if not items:
        return _leeg("Nog geen geëvalueerde keywords. De bronnen (Trends, GSC, KE) voeden de bibliotheek.")
    body = "".join(
        f"<tr><td>{_e(r['term'])}</td><td>{_status_chip(r.get('status'))}</td>"
        f"<td class='num'>{_num(r.get('volume'))}</td>"
        f"<td class='num'>{_num(r.get('competition'))}</td>"
        f"<td class='num'><b>{_num(r.get('opportunity'))}</b></td>"
        f"<td>{_e(r.get('source') or '—')}</td></tr>" for r in items)
    tabel = _table("<th>Keyword</th><th>Status</th><th class='num'>Volume</th>"
                   "<th class='num'>Concurrentie</th><th class='num'>Kansrijkheid</th><th>Bron</th>", body)
    sugg = [r for r in items if r.get("status") == "approved"][:8]
    if sugg:
        chips = "".join(f"<span class='chip green'>{_e(r['term'])} "
                        f"<span class='muted'>· {_num(r.get('opportunity'))}</span></span> " for r in sugg)
        tabel += (f"<div class='c2-sec'><h2>Suggesties</h2><p class='muted'>Goedgekeurde, kansrijke "
                  f"keywords om op te sturen (content of linkbuilding).</p>{chips}</div>")
    return tabel


def _lens_library(rows: list) -> str:
    items = [r for r in rows if converges(r)]
    items.sort(key=lambda r: (not r.get("is_signal"), -(r.get("volume") or 0)))
    if not items:
        return _leeg("Nog geen convergentie: geen term waar een écht signaal én meetbaar volume/open "
                     "status samenkomen. Zodra de bronnen elkaar raken, verschijnen hier de cureer-kandidaten.")
    body = "".join(
        f"<tr><td>{_e(r['term'])}</td><td>{_status_chip(r.get('status'))}</td>"
        f"<td>{_signal_chip(r.get('signal_type'))}</td>"
        f"<td class='num'>{_num(r.get('volume'))}</td>"
        f"<td>{_e(r.get('direction') or '—')}</td></tr>" for r in items)
    return (f"<p class='muted'>Termen waar signaal, volume en status samenkomen — hier loont curatie het "
            f"meest.</p>" + _table("<th>Term</th><th>Status</th><th>Signaal</th><th class='num'>Volume</th>"
                                   "<th>Richting</th>", body))


_LENS_FN = {"marketing": _lens_marketing, "scientist": _lens_scientist,
            "trends": _lens_trends, "library": _lens_library}


def _switcher(active: str) -> str:
    opts = "".join(
        f"<a class='chip-opt{(' on' if k == active else '')}' href='/keywords?lens={k}' "
        f"title='{_e(desc)}'>{_e(label)}</a>" for k, label, desc in _LENSES)
    return f"<div class='c2-sec'>{opts}</div>"


def render_keyword_lens(data_dir: str, lens: str = "trends") -> str:
    if lens not in _LENS_KEYS:
        lens = "trends"
    rows = build_keyword_layer(data_dir)
    _label = next(l for k, l, _d in _LENSES if k == lens)
    _desc = next(d for k, _l, d in _LENSES if k == lens)
    body = _LENS_FN[lens](rows)
    main = (f"<div class='c2-main'><h1>Keywords <span class='chip'>{_e(_label.lower())}</span></h1>"
            f"<p class='muted'>Eén keyword-datalaag ({len(rows)} termen), vier rol-lenzen. "
            f"Deze lens: {_e(_desc)}.</p>{_switcher(lens)}{body}</div>")
    inner = (f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
    return _page(f"Keywords — {_label}", inner)
