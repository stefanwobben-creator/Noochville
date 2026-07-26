"""Tag-onderhoud-review (/kennisbank/tags) — de mens keurt de weekvoorstellen van de Library.

Elk voorstel: merge (synoniemen → één tag), weg (ruis eruit) of abstractie (micro-tags →
één bruikbaar begrip), met motivatie en de aantallen erbij. ✓ voert het meteen door op
álle kaartjes (NotesStore.retag); ✗ wijst af en het voorstel komt niet opnieuw terug.
"""
from __future__ import annotations

from nooch_village.web_base import _e, _page, _banner
from nooch_village.cockpit2_util import _DS_LINK, _nav

# Display-mapping: de sleutels blijven de opgeslagen actie-waarden.
_ACTIE = {"merge": "🧩 merge", "weg": "🗑 drop", "abstractie": "🪁 abstract"}


def _hid(csrf: str, action: str, nxt: str, extra: dict | None = None) -> str:
    h = (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
         f"<input type='hidden' name='action' value='{_e(action)}'>"
         f"<input type='hidden' name='next' value='{_e(nxt)}'>")
    for k, v in (extra or {}).items():
        h += f"<input type='hidden' name='{_e(k)}' value='{_e(v)}'>"
    return h


def _voorstel_rij(v: dict, telling: dict, csrf: str, nxt: str) -> str:
    van = " ".join(f"<span class='chip'>{_e(t)} <span class='muted'>"
                   f"({telling.get(t, 0)})</span></span>" for t in v.get("van") or [])
    naar = (f" → <span class='chip ok'>{_e(v['naar'])}</span>" if v.get("naar") else "")
    knoppen = ""
    if csrf:
        knoppen = (
            f"<form method='post' action='/action'>"
            f"{_hid(csrf, 'tag_voorstel_besluit', nxt, {'vid': v['id'], 'keuze': 'doorvoeren'})}"
            f"<button class='btn ok' title='apply to all cards'>✓ apply</button>"
            f"</form>"
            f"<form method='post' action='/action'>"
            f"{_hid(csrf, 'tag_voorstel_besluit', nxt, {'vid': v['id'], 'keuze': 'afgewezen'})}"
            f"<button class='btn' title='reject — will not come back'>✗</button></form>")
    return (f"<div class='kn-lrow kn-tagvoorstel'>"
            f"<div class='kn-lt'><span class='chip muted'>{_ACTIE.get(v.get('actie'), v.get('actie'))}"
            f"</span> {van}{naar}"
            + (f"<span class='kn-src'>{_e(v.get('waarom') or '')}</span>" if v.get("waarom") else "")
            + f"</div>{knoppen}</div>")


def render_tag_onderhoud(st, csrf_token: str = "", msg: str = "") -> str:
    from nooch_village.tag_onderhoud import TagVoorstellenStore, tag_telling
    store = TagVoorstellenStore(f"{st.dd}/tag_voorstellen.json")
    telling = tag_telling(st.notes)
    open_vs = store.open_voorstellen()
    nxt = "/kennisbank/tags"
    rijen = ("".join(_voorstel_rij(v, telling, csrf_token, nxt) for v in open_vs)
             or "<p class='muted'>No open proposals. The Library reviews the tag list weekly; "
                "you can also run the round right now.</p>")
    draai = ""
    if csrf_token:
        draai = (f"<form method='post' action='/action' class='kn-lrow'>"
                 f"{_hid(csrf_token, 'tag_onderhoud_run', nxt)}"
                 f"<button class='btn'>▶ run the maintenance round now</button></form>")
    main = (f"<div class='c2-main'><div class='c2-bar'><a href='/kennisbank'>← Oracle</a></div>"
            f"<h1>🏷 Tag maintenance</h1>"
            f"<p class='muted'>The Library keeps the tag list clean every week: merging, "
            f"pruning, abstracting. You decide; ✓ updates all cards immediately.</p>"
            f"{_banner(msg)}{draai}{rijen}</div>")
    inner = f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>"
    return _page("Tag maintenance", inner)
