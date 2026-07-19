"""Tag-onderhoud-review (/kennisbank/tags) — de mens keurt de weekvoorstellen van de Library.

Elk voorstel: merge (synoniemen → één tag), weg (ruis eruit) of abstractie (micro-tags →
één bruikbaar begrip), met motivatie en de aantallen erbij. ✓ voert het meteen door op
álle kaartjes (NotesStore.retag); ✗ wijst af en het voorstel komt niet opnieuw terug.
"""
from __future__ import annotations

from nooch_village.web_base import _e, _page, _banner
from nooch_village.cockpit2_util import _DS_LINK, _nav

_ACTIE = {"merge": "🧩 samenvoegen", "weg": "🗑 weg", "abstractie": "🪁 abstraheren"}


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
            f"<button class='btn ok' title='voer door op alle kaartjes'>✓ doorvoeren</button>"
            f"</form>"
            f"<form method='post' action='/action'>"
            f"{_hid(csrf, 'tag_voorstel_besluit', nxt, {'vid': v['id'], 'keuze': 'afgewezen'})}"
            f"<button class='btn' title='afwijzen — komt niet opnieuw terug'>✗</button></form>")
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
             or "<p class='muted'>Geen open voorstellen. De Library kijkt wekelijks naar de "
                "taglijst; je kunt de ronde ook nu draaien.</p>")
    draai = ""
    if csrf_token:
        draai = (f"<form method='post' action='/action' class='kn-lrow'>"
                 f"{_hid(csrf_token, 'tag_onderhoud_run', nxt)}"
                 f"<button class='btn'>▶ draai de onderhoudsronde nu</button></form>")
    main = (f"<div class='c2-main'><div class='c2-bar'><a href='/kennisbank'>← Oracle</a></div>"
            f"<h1>🏷 Tag-onderhoud</h1>"
            f"<p class='muted'>De Library houdt de taglijst wekelijks schoon: samenvoegen, "
            f"opschonen, abstraheren. Jij keurt; ✓ werkt meteen alle kaartjes bij.</p>"
            f"{_banner(msg)}{draai}{rijen}</div>")
    inner = f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>"
    return _page("Tag-onderhoud", inner)
