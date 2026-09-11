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

_CHIP = {"groen": ("chip green", "groen"), "oranje": ("chip amber", "oranje"),
         "rood": ("chip coral", "rood"), "grijs": ("chip muted", "niet gemeten")}

_ROL_LABEL = {"mother_earth__nooch__website_developer": "Website Developer"}


def _chip(kleur: str, tekst: str = "") -> str:
    cls, label = _CHIP.get(kleur, _CHIP["grijs"])
    return f"<span class='{cls}'>{_e(tekst or label)}</span>"


def _eigenaar(st, rol_id: str) -> str:
    if not rol_id:
        return "geen eigenaar"
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
    return f"<h2>Verloop</h2><p class='muted'>De laatste {len(runs)} runs, nieuwste bovenaan.</p>{rijen}"


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
        uitleg = ("dan staan hier de lampjes van het preview-thema (<code>mobiel_audit_dev_url</code> in "
                  "<code>config/settings.ini</code>): een eigen reeks, los van live, want een dev-run naast een "
                  "live-run zou een valse wissel zijn." if doel == "dev" else
                  "dan staan hier de lampjes van de shop: bereikbaar, snelheid, toegankelijkheid, best "
                  "practices, SEO en claims.")
        main = (f"<div class='c2-main'><h1>Site audit {_doel_seg(doel)}</h1>"
                f"<p class='muted'>Nog geen run. Draai <code>{_e(cmd)}</code> op de server; {uitleg}</p></div>")
    else:
        wissels = laatste.get("wissels") or []
        wissel_html = ""
        if wissels:
            regels = "".join(f"<li>{_e(w['naam'])}: {_chip(w['was'])} → {_chip(w['nu'])}</li>" for w in wissels)
            wissel_html = (f"<div class='card'><b>Gewisseld sinds de vorige run</b>"
                           f"<ul class='fbul'>{regels}</ul></div>")
        kaarten = "".join(_lamp_card(st, l) for l in laatste.get("lampjes") or [])
        wanneer = _age(float(laatste.get("ts") or 0)) if laatste.get("ts") else "?"
        dev_noot = (" Dit is het preview-thema, mét Shopify's preview-balk; vergelijk dev met live nooit op "
                    "één run, de labscore schommelt tientallen punten." if doel == "dev" else "")
        main = (f"<div class='c2-main'><h1>Site audit "
                f"{_chip(laatste.get('totaal') or 'grijs')} {_doel_seg(doel)}</h1>"
                f"<p class='muted'>{_e(laatste.get('url') or '')} · laatste run {_e(wanneer)} "
                f"({_e(laatste.get('datum') or '')}, {laatste.get('duur_s', '?')} s). Het slechtste lampje "
                f"bepaalt de kleur bovenaan; grijs is niet gemeten en telt niet mee. Een lampje dat van "
                f"kleur wisselt is het signaal, de stand is het scherm.{dev_noot}</p>"
                f"{wissel_html}<h2>Lampjes</h2>{kaarten}{_verloop_html(staat.verloop())}</div>")
    from nooch_village.views.overview import _tree_html
    rail = f"<div class='c2-rail'>{_tree_html(st, '')}</div>"
    return _page("Site audit", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}{rail}</div>")
