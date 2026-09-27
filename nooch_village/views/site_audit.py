"""Site audit — de lampjes van nooch.earth, met klik-door naar de uitleg en het verloop.

Vormgeving: hetzelfde patroon als `views/skills.py` en `views/bronnen.py` (één `.card` per lampje
met `.cl-head` + `h3`, de kleur als bestaande chip-variant in `.kc-actions`, uitleg in `.muted`,
bevindingen in een `<details class='box-details'>`). Geen nieuwe CSS-klassen, geen inline styles.
Dit scherm leest alleen: de run gebeurt via `village site_audit` (en later via de weekklok).
"""
from __future__ import annotations

import time

from nooch_village.web_base import _e, _page
from nooch_village.cockpit2_util import _DS_LINK, _nav, _age
from nooch_village import site_audit

# DE SLEUTELS BLIJVEN NEDERLANDS: dat zijn opgeslagen waarden uit `site_audit`, geen tekst. Wat
# de lezer ziet is het tweede lid, en dat is Engels.
_CHIP = {"groen": ("chip green", "green"), "oranje": ("chip amber", "amber"),
         "rood": ("chip coral", "red"), "grijs": ("chip muted", "not measured")}

_ROL_LABEL = {"mother_earth__nooch__website_developer": "Website Developer"}


def _chip(kleur: str, tekst: str = "") -> str:
    cls, label = _CHIP.get(kleur, _CHIP["grijs"])
    return f"<span class='{cls}'>{_e(tekst or label)}</span>"


def _eigenaar(st, rol_id: str) -> str:
    if not rol_id:
        return "no owner"
    try:
        rec = st.records.get(rol_id)
        naam = (getattr(getattr(rec, "definition", None), "name", "") or "") if rec is not None else ""
    except Exception:                                  # noqa: BLE001
        naam = ""
    return naam or _ROL_LABEL.get(rol_id) or rol_id


def _lamp_card(st, lamp: dict) -> str:
    bev = lamp.get("bevindingen") or []
    details = ""
    if bev:
        items = "".join(f"<li>{_e(b)}</li>" for b in bev)
        details = (f"<details class='box-details'><summary class='muted'>{len(bev)} bevinding(en)"
                   f"</summary><ul class='fbul'>{items}</ul></details>")
    waarde = f" <span class='muted'>{_e(lamp.get('waarde') or '')}</span>" if lamp.get("waarde") else ""
    return (f"<div class='card'><div class='cl-head'><h3>{_e(lamp['naam'])}{waarde}</h3>"
            f"<span class='kc-actions'>{_chip(lamp['kleur'])}</span></div>"
            f"<div class='muted'>{_e(lamp.get('uitleg') or '')}</div>{details}"
            f"<div class='muted'>eigenaar: <code>{_e(_eigenaar(st, lamp.get('eigenaar', '')))}</code> · "
            f"bron: <code>{_e(lamp.get('bron') or '')}</code></div></div>")


def _verloop_html(runs: list[dict]) -> str:
    if len(runs) < 2:
        return ""
    rijen = ""
    for r in reversed(runs):
        chips = " ".join(_chip(l["kleur"], l["naam"].split(" ")[0]) for l in r.get("lampjes") or [])
        rijen += (f"<div class='c2-sec'><span class='muted'>{_e(r.get('datum') or '')}</span> {chips}</div>")
    return (f"<h2>History</h2><p class='muted'>The last {len(runs)} runs, newest first.</p>{rijen}")


_DOEL_LABEL = {"live": "Live", "dev": "Dev (preview)"}


def _doel_seg(doel: str) -> str:
    """Live · Dev als segment-balk (zelfde `.seg` als het tijdvenster op /metrics): twee reeksen,
    één scherm, nooit door elkaar."""
    links = "".join(f"<a class='{'on' if d == doel else ''}' href='/site-audit{'' if d == 'live' else '?doel=dev'}'>"
                    f"{_e(_DOEL_LABEL[d])}</a>" for d in site_audit.DOELEN)
    return f"<span class='seg'>{links}</span>"


def render_site_audit(st, doel: str = "live") -> str:
    doel = doel if doel in site_audit.DOELEN else "live"
    staat = site_audit.SiteAuditStaat(site_audit.pad_voor(st.dd, doel))
    laatste = staat.laatste()
    cmd = "python -m nooch_village.village site_audit" + (" --dev" if doel == "dev" else "")
    if laatste is None:
        uitleg = ("then the lights of the preview theme show up here (<code>mobiel_audit_dev_url</code> "
                  "in <code>config/settings.ini</code>): a series of its own, separate from live — a dev "
                  "run next to a live run would read as a false swing." if doel == "dev" else
                  "then the lights of the shop show up here: reachable, speed, accessibility, best "
                  "practices, SEO and claims.")
        main = (f"<div class='c2-main'><h1>Site audit {_doel_seg(doel)}</h1>"
                f"<p class='muted'>No run yet. Run <code>{_e(cmd)}</code> on the server; {uitleg}</p></div>")
    else:
        wissels = laatste.get("wissels") or []
        wissel_html = ""
        if wissels:
            regels = "".join(f"<li>{_e(w['naam'])}: {_chip(w['was'])} → {_chip(w['nu'])}</li>" for w in wissels)
            wissel_html = (f"<div class='card'><b>Changed since the previous run</b>"
                           f"<ul class='fbul'>{regels}</ul></div>")
        kaarten = "".join(_lamp_card(st, l) for l in laatste.get("lampjes") or [])
        wanneer = _age(float(laatste.get("ts") or 0)) if laatste.get("ts") else "?"
        dev_noot = (" Dit is het preview-thema, mét Shopify's preview-balk; vergelijk dev met live nooit op "
                    "one run; the lab score swings by tens of points." if doel == "dev" else "")
        main = (f"<div class='c2-main'><h1>Site audit "
                f"{_chip(laatste.get('totaal') or 'grijs')} {_doel_seg(doel)}</h1>"
                f"<p class='muted'>{_e(laatste.get('url') or '')} · last run {_e(wanneer)} "
                f"({_e(laatste.get('datum') or '')}, {laatste.get('duur_s', '?')} s). The worst light sets "
                f"the colour at the top; grey is not measured and does not count. A light that CHANGES "
                f"colour is the signal — the standing is just the screen.{dev_noot}</p>"
                f"{wissel_html}<h2>Lampjes</h2>{kaarten}{_verloop_html(staat.verloop())}</div>")
    return _page("Site audit", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
