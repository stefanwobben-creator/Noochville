"""Site audit — de lampjes van nooch.earth, met klik-door naar de uitleg en het verloop.

Vormgeving: hetzelfde patroon als `views/skills.py` en `views/bronnen.py` (één `.card` per lampje
met `.cl-head` + `h3`, de kleur als bestaande chip-variant in `.kc-actions`, uitleg in `.muted`,
bevindingen in een `<details class='box-details'>`). Geen nieuwe CSS-klassen, geen inline styles.
Dit scherm leest alleen: de run gebeurt via `village site_audit` (en later via de weekklok).

EN SINDS 28 SEPTEMBER OOK VIA EEN KNOP, en die staat sindsdien HIER.

Eerst hing hij aan de pagina die de audit noemde (het Website Handboek), zodat er geen titel of
artefact-id in de rendercode hoefde te staan. Diezelfde dag is die pagina verwijderd, en toen bleek
de indirectie precies zo sterk als haar aanknopingspunt: geen pagina, geen knop, en een zaai-functie
die naar een titel zocht die niet meer bestond. Het scherm dat de uitslag toont is de plek waar je
tóch al staat als je hem wilt verversen — dat had het eerste antwoord moeten zijn.

Het blijft een BEWUSTE doorbreking van "de run draait nooit in het cockpit", met het slot eromheen,
omdat er drie ingangen zijn die elkaar kunnen kruisen (CLI, knop, en de klok van scope 47).
"""
from __future__ import annotations

import time
import urllib.parse

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


def scan_paneel(data_dir: str, csrf_token: str = "", *, mag: bool = False,
                terug: str = "", doel: str = "live") -> str:
    """De stand van de scan plus de knop — als fragment, zodat de pagina hem kan verversen.

    DRIE TOESTANDEN, en ze lezen alle drie anders:

      * DRAAIT — sinds wanneer en door wie. Geen knop, want er is niets te starten.
      * MISLUKT — de vorige poging sneuvelde; dat hoort niet hetzelfde te lezen als "er is nog
        niets gebeurd". Zie `site_audit.laatste_fout`.
      * VRIJ — wanneer de laatste run was, en de knop.

    HIJ RENDERT ZIJN EIGEN OMHULSEL met `id`, want `nooch.js` vervangt precies dit element. Zonder
    vaste id zou de poller moeten raden waar hij het moet neerzetten.

    GEEN NIEUWE KLASSEN: `.card`, `.qadd-row`, `.btn ok sm`, `.chip`, `.muted` bestaan allemaal al.
    """
    bezet = site_audit.slot_staat(data_dir, doel)
    laatste = site_audit.SiteAuditStaat(site_audit.pad_voor(data_dir, doel)).laatste()
    fout = site_audit.laatste_fout(data_dir, doel)

    wanneer = (f"Last scan {_e(_age(laatste.get('ts')))} &middot; "
               f"{_e(str(laatste.get('totaal') or ''))}" if laatste
               else "No scan yet")
    if bezet:
        # `aria-live` op het omhulsel: de poller vervangt de inhoud, en wie het voorgelezen krijgt
        # hoort dán dat de scan klaar is in plaats van het te moeten navragen.
        binnen = (f"<span class='chip amber'>scanning&hellip;</span> "
                  f"<span class='muted'>started {_e(_age(bezet.get('sinds')))} by "
                  f"{_e(str(bezet.get('door') or 'someone'))} &middot; a Lighthouse run takes "
                  f"20-60 seconds</span>")
    else:
        knop = ""
        if mag and csrf_token:
            knop = (f"<form method='post' action='/action' class='fentry-inline'>"
                    f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                    f"<input type='hidden' name='next' value='{_e(terug)}'>"
                    # HET DOEL REIST MEE. Op de dev-tab hoort de knop de DEV-reeks te meten; zonder
                    # dit veld zou hij live scannen terwijl het scherm iets anders zegt — en
                    # allebei de reeksen hebben hun eigen slot, dus dat zou ook nog eens twee runs
                    # naast elkaar toestaan.
                    f"<input type='hidden' name='doel' value='{_e(doel)}'>"
                    f"<input type='hidden' name='action' value='site_audit_run'>"
                    f"<button class='btn ok sm' type='submit'>Run scan</button></form>")
        binnen = f"<span class='muted'>{wanneer}</span>{knop}"
    melding = (f"<div class='muted'>&#9888; the last attempt failed "
               f"({_e(_age(fout.get('ts')))}): {_e(str(fout.get('fout') or ''))}</div>"
               if fout and not bezet else "")
    return (f"<div class='card' id='scan-paneel' aria-live='polite'>"
            f"<div class='qadd-row'>{binnen}</div>"
            f"<div class='muted'>Checks the live shop: reachable, Lighthouse (mobile), claims. "
            f"The result lands on <a href='/site-audit'>Site audit</a>.</div>{melding}</div>")


def render_site_audit(st, doel: str = "live", *, csrf_token: str = "",
                      username: str | None = None) -> str:
    """De lampjes, en de knop die er nieuwe ophaalt.

    DE POORT WORDT TWEE KEER GESTELD, hier en in `_act_site_audit_run` — met dezelfde functie op
    dezelfde rol. Een knop tonen die de server daarna weigert is wat deze codebase op vijf andere
    plekken al heeft opgeruimd.

    LEZEN BLIJFT VRIJ: wie de rol niet vervult ziet de stand van de scan gewoon, alleen zonder de
    knop erbij."""
    from nooch_village.cockpit2 import _role_gate
    from nooch_village.cockpit2_util import WEBSITE_DEVELOPER_ROLE

    doel = doel if doel in site_audit.DOELEN else "live"
    staat = site_audit.SiteAuditStaat(site_audit.pad_voor(st.dd, doel))
    laatste = staat.laatste()
    cmd = "python -m nooch_village.village site_audit" + (" --dev" if doel == "dev" else "")
    hier = "/site-audit" + ("?doel=dev" if doel == "dev" else "")
    mag = bool(csrf_token) and _role_gate(WEBSITE_DEVELOPER_ROLE, username, st) is None
    # `data-poll` = de generieke poller uit `nooch.js`. Zonder hem blijft "scanning…" staan tot de
    # lezer zelf ververst, en dan is de knop wél veilig maar de terugkoppeling nutteloos.
    paneel = (f"<div data-poll='/scan-status?doel={_e(doel)}&amp;"
              f"next={_e(urllib.parse.quote(hier))}' data-poll-ms='5000'>"
              f"{scan_paneel(st.dd, csrf_token if mag else '', mag=mag, terug=hier, doel=doel)}"
              f"</div>")
    if laatste is None:
        uitleg = ("then the lights of the preview theme show up here (<code>mobiel_audit_dev_url</code> "
                  "in <code>config/settings.ini</code>): a series of its own, separate from live — a dev "
                  "run next to a live run would read as a false swing." if doel == "dev" else
                  "then the lights of the shop show up here: reachable, speed, accessibility, best "
                  "practices, SEO and claims.")
        main = (f"<div class='c2-main'><h1>Site audit {_doel_seg(doel)}</h1>"
                f"<p class='muted'>No run yet &mdash; press <b>Run scan</b> below, or run "
                f"<code>{_e(cmd)}</code> on the server; {uitleg}</p>{paneel}</div>")
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
                f"{paneel}{wissel_html}<h2>Lampjes</h2>{kaarten}"
                f"{_verloop_html(staat.verloop())}</div>")
    return _page("Site audit", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
