"""Signals — de dorp-brede lijst van goedgekeurde radar-signalen, verzameld uit álle rollen.

Het startpunt van de library: hier komen de signalen samen die mensen op de Tools-tab (Radar) van hun
rol relevant achtten (status 'goedgekeurd'). Read-only aggregatie via RadarStore.all_approved — geen
nieuwe opslag, raakt de radar-flow niet. Vanaf hier maak je later inzichten. Filterbaar op feed.

Hergebruik: web_base (_e/_page), cockpit2_util (_name/_DS_LINK/_BUILD) en de .rdr-*/.chip-opt-stijl."""
from __future__ import annotations

from nooch_village.web_base import _e, _page
from nooch_village.cockpit2_util import _DS_LINK, _name, _BUILD, _nav

_KIND = {"kaart": "🃏 signaal", "seed": "🌱 kiem", "doelwit": "🎯 doelwit", "concurrent": "🏁 concurrent"}


def _sig_date(s: str) -> str:
    s = (s or "").strip()
    return s[:10] if s else ""


def _signal_card(st, it) -> str:
    orec = st.records.get(it.get("role", ""))
    rolenaam = _name(orec) if orec else it.get("role", "")
    klabel = _KIND.get(it.get("kind", ""), it.get("kind", ""))
    pub = _sig_date(it.get("published_at", ""))
    src = (it.get("source") or "").strip()
    link = (it.get("link") or "").strip()
    bron = (f"<a href='{_e(link)}' target='_blank' rel='noopener'>{_e(src or 'bron')}</a>"
            if link else _e(src))
    rat = (it.get("rationale") or "").strip()
    meta = " · ".join(x for x in (
        f"<span class='chip muted'>{_e(klabel)}</span>",
        (f"<span class='chip muted'>📅 {_e(pub)}</span>" if pub else ""),
        (f"<span class='chip'>{_e(it.get('feed', ''))}</span>" if it.get("feed") else ""),
        f"<span class='muted'>via {_e(rolenaam)}</span>",
        bron) if x)
    return (f"<div class='rdr-row rdr-arch'><div class='rdr-body'>"
            f"<div class='rdr-sig'>{_e(it.get('content', ''))}</div>"
            + (f"<div class='muted rdr-rat'>{_e(rat)}</div>" if rat else "")
            + f"<div class='rdr-meta'>{meta}</div></div></div>")


def render_signals(st, csrf_token: str = "", feed: str = "") -> str:
    """De /signals-pagina: alle goedgekeurde signalen, nieuwste eerst, optioneel gefilterd op feed."""
    items = st.radar.all_approved()
    feeds = sorted({it.get("feed", "") for it in items if it.get("feed")})
    if feed:
        items = [it for it in items if it.get("feed") == feed]
    chips = ""
    if feeds:
        opts = [("", "alle")] + [(f, f) for f in feeds]
        chips = ("<div class='c2-sec'>" + "".join(
            f"<a class='chip-opt{(' on' if feed == val else '')}' "
            f"href='/signals{('?feed=' + _e(val)) if val else ''}'>{_e(lbl)}</a>"
            for val, lbl in opts) + "</div>")
    body = ("".join(_signal_card(st, it) for it in items) if items
            else "<p class='muted'>Nog geen goedgekeurde signalen. Keur ze goed op de Tools-tab "
                 "(Radar) van een rol, dan verschijnen ze hier.</p>")
    main = (f"<div class='c2-main'><div class='c2-bar'><a href='/'>← home</a></div>"
            f"<h1>Signalen <span class='chip'>library</span></h1>"
            f"<p class='muted'>Goedgekeurde radar-signalen, verzameld uit de rollen. "
            f"Het startpunt voor inzichten.</p>{chips}"
            f"<div class='rdr-tool'>{body}</div></div>")
    inner = (f"{_DS_LINK}"
             f"{_nav()}"
             f"<div class='c2-wrap'>{main}</div>")
    return _page("Signalen", inner)
