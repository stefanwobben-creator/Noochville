"""Metrieken 2 — het nieuwe catalogus-plus-dashboard-scherm (deel 1: catalogus + favorieten).

Bouwt bovenop de bestaande metrics-store: een 'favoriet' is een tegel (add_tile) op de node, en het
dashboard is `tiles_of(node)`. De catalogus komt uit `_sources_for` (zelf-beschrijvend: bron → measures
+ dims, met leesbare labels), zodat kiezen niet-technisch is. Draait NAAST het bestaande metrics-scherm;
de grafieken, weergave-schakelaar, kaart-omdraaien, tijdvenster en vergelijken volgen in deel 2+.
"""
from __future__ import annotations

from nooch_village.web_base import _e, _page
from nooch_village.cockpit2_util import _DS_LINK, _BUILD, _name
from nooch_village.views.metrics import _sources_for, _default_form


def _post(action: str, node: str, label: str, cls: str, csrf: str, **fields) -> str:
    """Klein POST-formuliertje voor een favoriet-actie (geen losse labels → ratchet-schoon)."""
    hid = (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
           f"<input type='hidden' name='node' value='{_e(node)}'>"
           f"<input type='hidden' name='next' value='/metrics2?node={_e(node)}'>")
    for k, v in fields.items():
        hid += f"<input type='hidden' name='{_e(k)}' value='{_e(str(v))}'>"
    return (f"<form method='post' action='/action' class='emo-f'>{hid}"
            f"<button class='{cls}' name='action' value='{action}'>{_e(label)}</button></form>")


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
                btn = _post("metrics2_unfav", node, "★ favoriet", "btn ok sm", csrf, tid=tile["id"])
            else:
                d0 = s["dims"][0][0] if s.get("dims") else "none"
                btn = _post("metrics2_fav", node, "☆ favoriet", "btn sm", csrf,
                            source=s["id"], measure=mid, dim=d0, form=_default_form(d0))
            cards.append(f"<div class='card'><div class='rdr-sig'>{_e(ml)}</div>"
                         f"<div class='rdr-meta'><span class='muted'>{_e(s['label'])}</span> {seg}</div>"
                         f"<div class='ffoot-l'>{btn}</div></div>")
        groups.append(f"<h2>{_e(s['label'])}</h2><div class='rdr-cards'>{''.join(cards)}</div>")
    return "".join(groups) or "<p class='muted'>Nog geen bronnen voor deze node.</p>"


def _favorites(st, rec, tiles, csrf: str) -> str:
    node = rec.id
    if not tiles:
        return ("<div class='rdr-tool'><p class='muted'>Nog niks op je dashboard. Zet hieronder een ster "
                "bij wat je wilt volgen.</p></div>")
    rows = []
    for t in tiles:
        naam = str(t.get("source", "")).replace("kpi:", "") + " · " + str(t.get("measure", ""))
        rm = _post("metrics2_unfav", node, "verwijderen", "flink", csrf, tid=t.get("id", ""))
        rows.append(f"<div class='rdr-row'><div class='rdr-body'><div class='rdr-sig'>{_e(naam)}</div>"
                    f"<div class='rdr-meta'><span class='muted'>vorm: {_e(t.get('form','getal'))} · "
                    f"dim: {_e(t.get('dim','none'))}</span></div></div><div class='rdr-act'>{rm}</div></div>")
    return f"<div class='rdr-tool'>{''.join(rows)}</div>"


def render_metrics2(st, rec, csrf_token: str = "") -> str:
    """Deel 1: bovenaan je favorieten (het begin van je dashboard), daaronder de catalogus om uit te kiezen."""
    if rec is None:
        inner = (f"{_DS_LINK}<div class='c2-wrap'><div class='c2-main'>"
                 "<p class='muted'>Kies een cirkel of rol om metrieken voor te bekijken.</p></div></div>")
        return _page("Metrieken", inner)
    tiles = st.metrics.tiles_of(rec.id)
    main = (f"<div class='c2-main'><h1>Metrieken — {_e(_name(rec))}</h1>"
            f"<p class='muted'>Scan de catalogus en zet een ster bij wat je wilt volgen. "
            f"Je hoeft niet te weten wat interessant is; het overzicht staat er.</p>"
            f"<h2>Mijn dashboard</h2>{_favorites(st, rec, tiles, csrf_token)}"
            f"<h2>Catalogus</h2>{_catalog(st, rec, tiles, csrf_token)}</div>")
    inner = (f"{_DS_LINK}<div class='bar'>cockpit 2 · GlassFrog (PoC) · build {_BUILD} · "
             "<a href='/'>home</a></div>"
             f"<div class='c2-wrap'>{main}</div>")
    return _page("Metrieken", inner)
