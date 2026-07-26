"""Keyword-lenzen (IA-fase 3) + nominatie-instrument (IA-fase 4) — vier rollen, ÉÉN datalaag.

Elke rol kijkt via een lens naar dezelfde `build_keyword_layer`-laag; ze delen de cijfers i.p.v.
elk een eigen bron te tellen. Een lens-switcher bovenaan maakt zichtbaar dat het één laag is.

Fase 4 (instrument, nog geen sturing): iedereen mag een keyword NOMINEREN; alleen Lara (de
Library-rolvervuller) beslist en SCHRIJFT naar de beschermde woordenschat. Elke beslissing wordt
append-only in de Kroniek geborgd; een aparte lens toont die beslissingsgeschiedenis.

Lenzen:
- marketing : volume + richting — waar maak je content voor (approved doelwit-woorden).
- scientist : nieuwe signalen — opkomst/stijgend vs. blip (Sid's trend-herindexering).
- trends    : kansrijkheid + suggesties — de scout-analyse (Billy Buzz).
- library   : convergentie — waar signaal + volume + open status samenkomen (Lara's cureer-lens) +
              de pending nominatie-wachtrij (Lara beslist).
- kroniek   : de beslissingsgeschiedenis (wie, woord, accept/reject, reden).
"""
from __future__ import annotations

from nooch_village.web_base import _e, _page
from nooch_village.cockpit2_util import _DS_LINK, _nav
from nooch_village.keyword_layer import build_keyword_layer, converges

_LENSES = [
    ("marketing", "Marketing", "volume + direction — what do you make content for"),
    ("scientist", "Scientist", "new signals — emergence vs. blip"),
    ("trends", "Trends & Competition", "opportunity + suggestions"),
    ("library", "Library", "convergence + nomination queue"),
    ("kroniek", "Chronicle", "decision history — who, word, accept/reject, reason"),
]
_LENS_KEYS = {k for k, _l, _d in _LENSES}

# Display-mapping: de sleutels blijven de opgeslagen signaal-/statuswaarden.
_STATUS_CHIP = {"approved": "chip green", "escalated": "chip amber",
                "forbidden": "chip coral"}
_SIGNAL_LABEL = {"emergence": "emerging", "trend": "rising", "peak": "blip", "flat": "flat"}
_SIGNAL_CHIP = {"emergence": "chip green", "trend": "chip green",
                "peak": "chip amber", "flat": "chip muted"}
_SIGNAL_ORDER = {"emergence": 0, "trend": 1, "peak": 2, "flat": 3}


def _hid(csrf: str, action: str, nxt: str, extra: dict | None = None) -> str:
    h = (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
         f"<input type='hidden' name='action' value='{_e(action)}'>"
         f"<input type='hidden' name='next' value='{_e(nxt)}'>")
    for k, v in (extra or {}).items():
        h += f"<input type='hidden' name='{_e(k)}' value='{_e(v)}'>"
    return h


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


# ── de vier rol-lenzen ─────────────────────────────────────────────────────────

def _lens_marketing(rows: list) -> str:
    items = [r for r in rows if (r.get("volume") or 0) > 0 or
             (r.get("status") == "approved" and r.get("function") == "doelwit")]
    items.sort(key=lambda r: -(r.get("volume") or 0))
    if not items:
        return _leeg("No words with volume yet. Switch the enrichment on (Keywords Everywhere, GSC) "
                     "so volume and direction come in.")
    body = "".join(
        f"<tr><td>{_e(r['term'])}</td><td>{_status_chip(r['status'])}</td>"
        f"<td class='num'>{_num(r.get('volume'))}</td>"
        f"<td>{_e(r.get('direction') or '—')}</td>"
        f"<td class='num'>{_num(r.get('opportunity'))}</td></tr>" for r in items)
    return _table("<th>Word</th><th>Status</th><th class='num'>Volume</th><th>Direction</th>"
                  "<th class='num'>Opportunity</th>", body)


def _lens_scientist(rows: list) -> str:
    items = [r for r in rows if r.get("in_trends")]
    items.sort(key=lambda r: (_SIGNAL_ORDER.get(r.get("signal_type") or "flat", 9),
                              -(r.get("recent_sustained") or 0)))
    signalen = [r for r in items if r.get("is_signal")]
    if not items:
        return _leeg("No trend observations yet. The daily trend reindex (Sid) fills the layer.")
    tel = (f"<p class='muted'><b>{len(signalen)}</b> of {len(items)} terms are a real signal "
           f"(emerging or rising, not a blip).</p>")
    body = "".join(
        f"<tr><td>{_e(r['term'])}</td><td>{_signal_chip(r.get('signal_type'))}</td>"
        f"<td class='num'>{_num(r.get('recent_sustained'))}</td>"
        f"<td class='num'>{_num(r.get('peak'))}</td>"
        f"<td>{_e(_window(r))}</td>"
        f"<td class='num'>{'✓' if r.get('is_signal') else '—'}</td></tr>" for r in items)
    return tel + _table("<th>Term</th><th>Signal</th><th class='num'>Recent</th>"
                        "<th class='num'>Peak</th><th>Window</th><th class='num'>Signal?</th>", body)


def _lens_trends(rows: list) -> str:
    items = [r for r in rows if r.get("in_library")]
    items.sort(key=lambda r: -(r.get("opportunity") or 0))
    if not items:
        return _leeg("No evaluated keywords yet. The sources (Trends, GSC, KE) feed the library.")
    body = "".join(
        f"<tr><td>{_e(r['term'])}</td><td>{_status_chip(r.get('status'))}</td>"
        f"<td class='num'>{_num(r.get('volume'))}</td>"
        f"<td class='num'>{_num(r.get('competition'))}</td>"
        f"<td class='num'><b>{_num(r.get('opportunity'))}</b></td>"
        f"<td>{_e(r.get('source') or '—')}</td></tr>" for r in items)
    tabel = _table("<th>Keyword</th><th>Status</th><th class='num'>Volume</th>"
                   "<th class='num'>Competition</th><th class='num'>Opportunity</th><th>Source</th>", body)
    sugg = [r for r in items if r.get("status") == "approved"][:8]
    if sugg:
        chips = "".join(f"<span class='chip green'>{_e(r['term'])} "
                        f"<span class='muted'>· {_num(r.get('opportunity'))}</span></span> " for r in sugg)
        tabel += (f"<div class='c2-sec'><h2>Suggestions</h2><p class='muted'>Approved, promising "
                  f"keywords to steer on (content or link building).</p>{chips}</div>")
    return tabel


def _lens_library(rows: list, pending: list, csrf: str, nxt: str, can_decide: bool) -> str:
    # bovenaan: de convergentie (waar curatie loont)
    conv = [r for r in rows if converges(r)]
    conv.sort(key=lambda r: (not r.get("is_signal"), -(r.get("volume") or 0)))
    if conv:
        body = "".join(
            f"<tr><td>{_e(r['term'])}</td><td>{_status_chip(r.get('status'))}</td>"
            f"<td>{_signal_chip(r.get('signal_type'))}</td>"
            f"<td class='num'>{_num(r.get('volume'))}</td>"
            f"<td>{_e(r.get('direction') or '—')}</td></tr>" for r in conv)
        conv_html = ("<p class='muted'>Terms where signal, volume and status converge — this is where "
                     "curation pays off most.</p>" + _table("<th>Term</th><th>Status</th><th>Signal</th>"
                     "<th class='num'>Volume</th><th>Direction</th>", body))
    else:
        conv_html = _leeg("No convergence yet: no term where a real signal and measurable "
                          "volume/open status come together.")

    # daaronder: de pending nominatie-wachtrij — alleen Lara beslist (accept/reject)
    if pending:
        rijen = ""
        for it in pending:
            term = it.get("term") or ""
            if can_decide:
                acties = (
                    f"<form method='post' action='/action' class='qadd-row'>"
                    f"{_hid(csrf, 'kw_nom_accept', nxt, {'term': term, 'status': 'approved'})}"
                    f"<button class='btn ok'>✓ accept</button></form>"
                    f"<form method='post' action='/action' class='qadd-row'>"
                    f"{_hid(csrf, 'kw_nom_reject', nxt, {'term': term})}"
                    f"<input type='text' name='reason' placeholder='reason for rejection (required)'>"
                    f"<button class='btn no'>✗ reject</button></form>")
            else:
                acties = "<span class='muted'>only Lara decides</span>"
            rijen += (f"<div class='card'><b>{_e(term)}</b> "
                      f"<span class='muted'>nominated by {_e(it.get('by') or '—')} · "
                      f"{_e(it.get('created_at') or '')}</span><div class='qadd-row'>{acties}</div></div>")
        queue = (f"<div class='c2-sec'><h2>Nomination queue ({len(pending)})</h2>"
                 f"<p class='muted'>Nominated keywords await Lara's verdict. Accepting writes "
                 f"to the library; rejecting requires a reason. Both are recorded in the Chronicle.</p>"
                 f"{rijen}</div>")
    else:
        queue = ("<div class='c2-sec'><h2>Nomination queue</h2>"
                 "<p class='muted'>No open nominations.</p></div>")
    return conv_html + queue


def _lens_kroniek(kroniek: list) -> str:
    if not kroniek:
        return _leeg("No decisions recorded yet. As soon as Lara accepts or rejects a nomination, "
                     "the history appears here.")
    import time as _t
    rows = sorted(kroniek, key=lambda r: -(r.get("ts") or 0))
    body = ""
    for r in rows:
        dec = r.get("decision")
        chip = "chip green" if dec == "accept" else "chip coral"
        lbl = "accepted" if dec == "accept" else "rejected"
        when = _t.strftime("%Y-%m-%d %H:%M", _t.localtime(r.get("ts"))) if r.get("ts") else "—"
        body += (f"<tr><td>{_e(r.get('term') or '—')}</td>"
                 f"<td><span class='{chip}'>{lbl}</span></td>"
                 f"<td>{_e(r.get('reason') or '—')}</td>"
                 f"<td>{_e(r.get('role_id') or '—')}</td>"
                 f"<td>{_e(when)}</td></tr>")
    return ("<p class='muted'>Every nomination decision, recorded append-only. This is the memory "
            "of the library curation.</p>" + _table(
                "<th>Word</th><th>Decision</th><th>Reason</th><th>By</th><th>When</th>", body))


def _switcher(active: str) -> str:
    opts = "".join(
        f"<a class='chip-opt{(' on' if k == active else '')}' href='/keywords?lens={k}' "
        f"title='{_e(desc)}'>{_e(label)}</a>" for k, label, desc in _LENSES)
    return f"<div class='c2-sec'>{opts}</div>"


def _nominate_form(csrf: str, nxt: str) -> str:
    return (f"<form method='post' action='/action' class='qadd-row'>"
            f"{_hid(csrf, 'kw_nominate', nxt)}"
            f"<input type='text' name='term' placeholder='nominate a keyword…'>"
            f"<button class='btn'>🗳 Nominate</button></form>")


def render_keyword_lens(st, lens: str = "trends", csrf_token: str = "",
                        can_decide: bool = False) -> str:
    if lens not in _LENS_KEYS:
        lens = "trends"
    nxt = f"/keywords?lens={lens}"
    rows = build_keyword_layer(st.dd)
    _label = next(l for k, l, _d in _LENSES if k == lens)
    _desc = next(d for k, _l, d in _LENSES if k == lens)

    if lens == "library":
        body = _lens_library(rows, st.nominations.pending(), csrf_token, nxt, can_decide)
    elif lens == "kroniek":
        body = _lens_kroniek(st.nom_kroniek.all_records())
    elif lens == "marketing":
        body = _lens_marketing(rows)
    elif lens == "scientist":
        body = _lens_scientist(rows)
    else:
        body = _lens_trends(rows)

    # nomineren kan vanuit elke rol-lens (niet vanaf de Kroniek zelf)
    nom = _nominate_form(csrf_token, nxt) if (csrf_token and lens != "kroniek") else ""

    main = (f"<div class='c2-main'><h1>Keywords <span class='chip'>{_e(_label.lower())}</span></h1>"
            f"<p class='muted'>One keyword data layer ({len(rows)} terms), five lenses. "
            f"This lens: {_e(_desc)}.</p>{_switcher(lens)}{nom}{body}</div>")
    inner = (f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
    return _page(f"Keywords — {_label}", inner)
