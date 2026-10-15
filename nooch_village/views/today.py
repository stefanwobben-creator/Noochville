"""Today — een leesoverzicht op bestaande gegevens (`/today`, 13 oktober 2026).

Stefan gebruikt het een week en beslist dan: nieuwe startpagina, aanvullen op My actions, of laten
vallen. Tot dan blijft `/` naar `/projects` gaan.

ALLEEN LEZEN, NIETS NIEUWS UITREKENEN. Elk getal komt uit een functie die al bestond of die voor
deze pagina is losgemaakt zodat beide plekken dezelfde gebruiken:
  Critical Numbers   `views.metrics.cn_stand`   (zelfde `_fetch`, doel en `_grens` als de tegels)
  My actions         `views.acties._mijn_projecten`, `_van_mijn_projecten`, `_mijn_checklist_items`
  Open questions     `views.open_vragen.stand`  (dezelfde telling als /open-questions)
  Goals              `doelen.voortgang`         (zelfde voortgang als /goals)
Nieuw is alleen de deadline-zin van een doel ("Overdue N days"): een vergelijking met vandaag.

FINANCE. De route geeft de kijker-versie van de stores (`zicht.voor`). CN2 komt dan niet uit
`cn_stand`, en wie Finance niet mag zien krijgt de tegel niet — ook niet als lege plek, en de HTML
bevat geen runway-getal of Finance-term. Geen enkele kop (`h1`/`h2`) draagt een Finance-getal: Noochie
stuurt de eerste kop van de pagina mee als context.

LAGEN (atom → molecule → pattern), allemaal bestaand — geen nieuwe klasse, geen inline style:
  atom      `.nu-status` (vorm + woord) · `progress.pbar` (meter) · `.kpi-val`/`.kpi-unit` · `.muted`
  molecule  `.tile` met `.tile-h`/`.tile-t`/`.tile-goal` (CN) · `.card` met `.cl-head` (blok) ·
            `.pbadge` (balk met getal) · `ul.clean`
  pattern   dit scherm: `.catgrid` (drie CN-tegels; één kolom op een telefoon), `.tile-grid` (twee
            blokken naast elkaar; één kolom op een telefoon), daaronder de doelen
Today heeft geen hoofdactie, dus geen neon: "Open …" zijn gewone links.
"""
from __future__ import annotations

import time

from nooch_village import doelen as _D
from nooch_village import wiki_dekking as dek
from nooch_village.cockpit2_util import _DS_LINK, _fmt_due, _nav
from nooch_village.web_base import _e, _page

#: Hoeveel doelen en hoeveel open vragen de pagina toont; de rest staat op de eigen pagina.
MAX_DOELEN = 5
MAX_VRAGEN = 5


def _num(v) -> str:
    from nooch_village.views.metrics import _num as m_num
    return m_num(v)


def _status(vorm: str, woord: str) -> str:
    return f"<span class='nu-status nu-status--{vorm}'>{_e(woord)}</span>"


# ── Critical Numbers ─────────────────────────────────────────────────────────

def _cn_tegel(n: dict) -> str:
    kop = f"<div class='tile-h'><span class='tile-t'>{_e(n['titel'])}</span></div>"
    if n["waarde"] is None:
        # GEEN WAARDE IS GEEN NUL: dat staat er, met de volgende stap.
        link = f" <a href='{_e(n['link'])}'>{_e(n['link_tekst'])}</a>" if n["link"] else ""
        return (f"<div class='tile'>{kop}<div class='tile-b'><p class='muted'>No data yet</p></div>"
                f"<div class='tile-goal muted'>{_e(n['stap'])}{link}</div></div>")
    getal = (f"<div class='tile-b'><span class='kpi-val'>{_num(n['waarde'])}</span> "
             f"<span class='kpi-unit'>{_e(n['eenheid'])}</span></div>")
    meter = ""
    if isinstance(n["target"], (int, float)) and n["target"] > 0:
        meter = (f"<progress class='pbar wide' value='{min(max(n['waarde'], 0), n['target']):g}' "
                 f"max='{n['target']:g}' aria-label='{_e(n['titel'])}: {_num(n['waarde'])} of "
                 f"{_num(n['target'])}'></progress>")
    regels = ""
    if n["regel"]:
        regels += f"<div class='tile-goal muted'>{_e(n['regel'])}</div>"
    st = n["status"]
    if st and st.get("vorm"):
        regels += f"<div class='tile-goal muted'>{_status(st['vorm'], st['woord'])} {_e(st['tekst'])}</div>"
    elif st:
        regels += f"<div class='tile-goal muted'>{_e(st['tekst'])}</div>"
    return f"<div class='tile'>{kop}{getal}{meter}{regels}</div>"


def _critical_numbers(st) -> str:
    from nooch_village.views.metrics import cn_stand
    nummers = cn_stand(st)
    if not nummers:
        return ("<div class='c2-sec'><h2>Critical numbers</h2><p class='muted'>No critical numbers "
                "this quarter yet. They are set in config/critical_numbers.json.</p></div>")
    return (f"<div class='c2-sec'><h2>Critical numbers</h2>"
            f"<div class='catgrid'>{''.join(_cn_tegel(n) for n in nummers)}</div></div>")


# ── My actions ───────────────────────────────────────────────────────────────

def _mijn_acties(st, ik: str) -> str:
    from nooch_village.views.acties import (_mijn_checklist_items, _mijn_projecten, _projectnaam,
                                            _van_mijn_projecten)
    kop = ("<div class='cl-head'><h3>My actions</h3>"
           "<span class='kc-actions'><a href='/acties'>Open My actions</a></span></div>")
    if not ik:
        return (f"<div class='card'>{kop}<p class='muted'>Log in as a person to see your actions "
                f"&mdash; an action belongs to someone.</p></div>")
    eigen = [a for a in st.acties.voor(ik) if not a.get("done")]
    mijn = _mijn_projecten(st, ik)                              # één keer, voor beide blokken
    van_projecten = _van_mijn_projecten(st, ik, mijn)
    stappen = _mijn_checklist_items(st, ik, mijn)
    regels = [(f"<b>{len(eigen)} open of your own</b>" if eigen
               else "<b>Nothing open of your own.</b> <span class='muted'>Quiet.</span>")]
    if van_projecten:
        namen = list(dict.fromkeys(_projectnaam(st, str(p.get("id") or "")) for _a, p in van_projecten))
        regels.append(f"<b>{len(van_projecten)} from your projects</b> "
                      f"<span class='muted'>{_e(', '.join(namen[:3]))}</span>")
    if stappen:
        per: dict[str, int] = {}
        for _it, _cl, p in stappen:
            naam = _projectnaam(st, str(p.get("id") or ""))
            per[naam] = per.get(naam, 0) + 1
        groot = sorted(per.items(), key=lambda kv: (-kv[1], kv[0].lower()))[:3]
        # "NEED A HUMAN" WAS EEN AI-RESTANT (15 oktober 2026): sinds er geen uitvoerder meer is, is
        # elk item mensenwerk. Een neutrale telling zegt hetzelfde zonder de tegenstelling.
        regels.append(f"<b>{len(stappen)} checklist item{'s' if len(stappen) != 1 else ''} open"
                      f"</b> <span class='muted'>across {len(per)} project"
                      f"{'s' if len(per) != 1 else ''}, biggest: "
                      f"{_e(', '.join(f'{n} ({k})' for n, k in groot))}</span>")
    if not eigen and not van_projecten and not stappen:
        regels.append("<span class='muted'>Nothing waits on you. Jot an action down on My actions "
                      "when something comes up.</span>")
    return f"<div class='card'>{kop}<ul class='clean'>{''.join(f'<li>{r}</li>' for r in regels)}</ul></div>"


# ── Open questions ───────────────────────────────────────────────────────────

def _open_vragen(st, ik: str) -> str:
    from nooch_village.views.bom import _DEK_VORM, _sprong
    from nooch_village.views.open_vragen import STATUSSEN, stand
    sd = stand(st)
    totaal = len(sd["alle"])
    kop = (f"<div class='cl-head'><h3>Open questions</h3>"
           f"<span class='kc-actions'><a href='/open-questions'>Open questions</a></span></div>")
    if not totaal:
        return (f"<div class='card'>{kop}<p class='muted'>No open questions: every material and "
                f"supplier page has a checked answer. New pages bring new questions; they show up "
                f"here by themselves.</p></div>")
    uitleg = (f"<p class='muted'><b>Not tasks.</b> These are facts the wiki still lacks about "
              f"materials and suppliers, {sd['paginas']} page{'s' if sd['paginas'] != 1 else ''} in all.</p>")
    voor_jou = ""
    if ik:
        mijn_rollen = set(st.assign.roles_of("person", ik))
        n = sum(k for rid, _naam, k in sd["per_eigenaar"] if rid in mijn_rollen)
        if n:
            voor_jou = f"<p><b>{n} for your roles</b></p>"
    telling = " ".join(f"{_status(*_DEK_VORM[s])} {sd['telling'][s]}" for s in STATUSSEN)
    eerst = [r for r in sd["alle"] if r["status"] in (dek.CONFLICT, dek.ONGECHECKT)][:MAX_VRAGEN]
    lijst = ""
    if eerst:
        items = []
        for r in eerst:
            naam = (f"<a href='{_e(_sprong(r['pagina'], r['kop'], r['k']))}'>{_e(r['naam'])}</a>"
                    if r["pagina"] is not None else _e(r["naam"]))
            items.append(f"<li>{_status(*_DEK_VORM[r['status']])} {naam} "
                         f"<span class='muted'>{_e(r['vraag'])}</span></li>")
        lijst = f"<ul class='clean'>{''.join(items)}</ul>"
    balken = "".join(
        f"<div class='pbadge'><progress class='pbar wide' value='{k}' max='{totaal}' "
        f"aria-label='{_e(naam)}: {k} of {totaal}'></progress><span>{_e(naam)} · {k}</span></div>"
        for _rid, naam, k in sd["per_eigenaar"])
    return (f"<div class='card'>{kop}{uitleg}{voor_jou}<p><b>{totaal} open</b> {telling}</p>"
            f"{lijst}{balken}</div>")


# ── Goals ────────────────────────────────────────────────────────────────────

def _deadline(d: dict, vandaag: str) -> tuple[int, str, str, str]:
    """(sorteervolgorde, vorm, woord, sorteersleutel). Achterstallig eerst, dan op deadline, zonder
    deadline laatst. DE ENIGE NIEUWE AFLEIDING op deze pagina: deadline vergeleken met vandaag."""
    dl = str(d.get("deadline") or "")[:10]
    if not dl:
        return (2, "open", "No deadline", "")
    if dl < vandaag:
        dagen = (time.mktime(time.strptime(vandaag, "%Y-%m-%d"))
                 - time.mktime(time.strptime(dl, "%Y-%m-%d"))) // 86400
        return (0, "off", f"Overdue {int(dagen)} day{'s' if int(dagen) != 1 else ''}", dl)
    return (1, "wait", f"Due {_fmt_due(dl) or dl}", dl)


def _doelen(st) -> str:
    from nooch_village.views.doelen import _balk
    kop = ("<div class='cl-head'><h3>Goals</h3>"
           "<span class='kc-actions'><a href='/goals'>Open Goals</a></span></div>")
    vandaag = time.strftime("%Y-%m-%d")
    open_ = [d for d in st.doelen.all() if (d.get("status") or "open") == "open"]
    if not open_:
        return (f"<div class='c2-sec'><div class='card'>{kop}<p class='muted'>No open goals. Add one on "
                f"Goals and link projects to it; its progress shows up here.</p></div></div>")
    alle = st.projects.all()
    rijen = sorted(((_deadline(d, vandaag), d) for d in open_), key=lambda t: (t[0][0], t[0][3]))
    items = []
    for (_volg, vorm, woord, _k), d in rijen[:MAX_DOELEN]:
        v = _D.voortgang(d, alle)
        items.append(f"<li><a href='/goal?id={_e(d['id'])}'>{_e(d.get('titel') or d['id'])}</a> "
                     f"{_status(vorm, woord)}{_balk(v)}</li>")
    meer = (f"<p class='muted'>{len(open_) - MAX_DOELEN} more on Goals.</p>"
            if len(open_) > MAX_DOELEN else "")
    return f"<div class='c2-sec'><div class='card'>{kop}<ul class='clean'>{''.join(items)}</ul>{meer}</div></div>"


# ── De pagina ────────────────────────────────────────────────────────────────

def render_today(st, ik: str = "") -> str:
    """`st` is de kijker-versie (`zicht.voor`), `ik` het persoon-id van de gebruiker (of leeg)."""
    datum = time.strftime("%A %-d %B %Y")
    main = (f"<div class='c2-main'><h1 class='ptitle'>Today</h1><p class='muted'>{_e(datum)}</p>"
            f"{_critical_numbers(st)}"
            f"<div class='c2-sec'><div class='tile-grid'>{_mijn_acties(st, ik)}{_open_vragen(st, ik)}</div></div>"
            f"{_doelen(st)}</div>")
    return _page("Today", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
