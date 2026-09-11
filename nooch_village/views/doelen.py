"""Doelen — het overzicht (`/goals`) en de doelpagina (`/goal?id=…`).

Vormgeving: de mockup `docs/MITH_doelen_incockpit.html` vertaald naar het designsysteem, klasse voor
klasse (zie de pariteitstabel in de commit): `.objhead` → `.card.doel`, `.glabel` → `.chip.doel`,
`.bar` → `<progress class='pbar wide'>`, `.pill` → `.cl-filter.pill`. Verder alleen bestaande klassen
(`.card`, `.cl-head`, `.kc-actions`, `.qadd-form`, `_field()`, `.fbul`, `.box-details`). Geen inline
styles. Alle cijfers komen uit `doelen.voortgang` en `doelen.kritieke_pad`; dit bestand rekent niet.
"""
from __future__ import annotations

import urllib.parse

from nooch_village.web_base import _e, _page, _field
from nooch_village.cockpit2_util import _DS_LINK, _nav, _fmt_due, _name, _IC_CLOCK
from nooch_village import doelen as _D
from nooch_village import org as _org
from nooch_village import projects as _PJ
from nooch_village.projects import KLAAR as _KLAAR

_STATUS_LABEL = {"open": "open", "behaald": "achieved", "gestopt": "stopped"}
_STATUS_CHIP = {"open": "chip doel", "behaald": "chip green", "gestopt": "chip muted"}


def _titel(p: dict) -> str:
    s = p.get("scope")
    if isinstance(s, dict):
        return " · ".join(f"{k}: {v}" for k, v in s.items())
    return str(s or p.get("label") or p.get("id") or "")


def _plink(p: dict, terug: str) -> str:
    return (f"<a href='/project?pid={_e(p['id'])}&back={urllib.parse.quote(terug, safe='')}'>"
            f"{_e(_titel(p)[:90])}</a>")


def _balk(v: dict) -> str:
    return (f"<div class='pbadge' title='{v['punten']} of {v['totaal']} (done counts 1, open projects their checklist ratio)'>"
            f"<progress class='pbar wide' value='{v['pct']}' max='100'></progress>"
            f"<span>{v['pct']}% · {v['af']}/{v['totaal']} done</span></div>")


def _deadline_chip(d: dict) -> str:
    if not d.get("deadline"):
        return "<span class='muted'>no deadline</span>"
    return f"<span class='chip outline'>{_IC_CLOCK}{_e(_fmt_due(d['deadline']) or d['deadline'])}</span>"


def _rail(st) -> str:
    from nooch_village.views.overview import _tree_html
    return f"<div class='c2-rail'>{_tree_html(st, '')}</div>"


# ── /goals ───────────────────────────────────────────────────────────────────

def render_goals(st, csrf_token: str = "", username: str | None = None, msg: str = "") -> str:
    alle = st.projects.all()
    kaarten = ""
    for d in st.doelen.all():
        v = _D.voortgang(d, alle)
        kaarten += (f"<div class='card'><div class='cl-head'><h3><a href='/goal?id={_e(d['id'])}'>🎯 {_e(d['titel'])}</a></h3>"
                    f"<span class='kc-actions'><span class='{_STATUS_CHIP.get(d.get('status'), 'chip muted')}'>"
                    f"{_e(_STATUS_LABEL.get(d.get('status'), d.get('status') or ''))}</span> {_deadline_chip(d)}</span></div>"
                    f"{_balk(v)}"
                    + (f"<div class='muted'>{_e(d['dod'][:200])}</div>" if d.get("dod") else "")
                    + "</div>")
    if not kaarten:
        kaarten = ("<p class='muted'>No goals yet. Seed the five with <code>python -m nooch_village.village "
                   "doelen_zaad --apply</code> on the server, or add one below.</p>")
    nieuw = ""
    if csrf_token:
        nieuw = (f"<details class='box-details'><summary class='muted'>+ goal</summary>"
                 f"<form method='post' action='/action' class='qadd-form'>"
                 f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                 f"<input type='hidden' name='next' value='/goals'>"
                 f"{_field('Title', 'titel', required=True, placeholder='The new website live')}"
                 f"{_field('Short label (on the cards)', 'label', placeholder='Website')}"
                 f"{_field('Deadline', 'deadline', kind='date')}"
                 f"{_field('Definition of done', 'dod', kind='textarea', placeholder='What is true when this goal is achieved?')}"
                 f"{_field('Work packages (one per line, optional)', 'activiteiten', kind='textarea')}"
                 f"<div><button class='btn ok sm' type='submit' name='action' value='goal_add'>Create goal</button></div>"
                 f"</form></details>")
    main = (f"<div class='c2-main'><h1>Goals</h1>"
            f"<p class='muted'>Where the work is heading. A project stays with its role and points at a goal; "
            f"progress is derived: done projects count 1, open projects their checklist ratio.</p>"
            + (f"<p class='muted'>{_e(msg)}</p>" if msg else "")
            + f"{kaarten}{nieuw}</div>")
    return _page("Goals", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}{_rail(st)}</div>")


# ── /goal?id= ────────────────────────────────────────────────────────────────

def render_goal(st, doel_id: str, csrf_token: str = "", username: str | None = None, msg: str = "") -> str:
    d = st.doelen.get(doel_id)
    if d is None:
        return _page("Not found", f"{_DS_LINK}{_nav()}<div class='c2-wrap'><div class='c2-main'>"
                                  f"<p>This goal does not exist.</p><p><a class='btn' href='/goals'>← goals</a></p></div></div>")
    alle = st.projects.all()
    terug = f"/goal?id={d['id']}"
    v = _D.voortgang(d, alle)
    ps = _D.projecten_van(d["id"], alle)
    per_id = {p["id"]: p for p in alle}
    rw = bool(csrf_token)

    def hid() -> str:
        return (f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                f"<input type='hidden' name='id' value='{_e(d['id'])}'>"
                f"<input type='hidden' name='next' value='{_e(terug)}'>")

    # kop: titel, status, deadline, balk (prototype .objhead)
    kop = (f"<div class='card doel'><div class='cl-head'><h3>🎯 {_e(d['titel'])}</h3>"
           f"<span class='kc-actions'><span class='{_STATUS_CHIP.get(d.get('status'), 'chip muted')}'>"
           f"{_e(_STATUS_LABEL.get(d.get('status'), ''))}</span> {_deadline_chip(d)}</span></div>"
           f"{_balk(v)}"
           + (f"<div class='muted'>{_e(d['dod'])}</div>" if d.get("dod") else "<div class='muted'>No definition of done yet.</div>")
           + (f"<div class='muted'>Work packages: {_e(' · '.join(d['activiteiten']))}</div>" if d.get("activiteiten") else "")
           + "</div>")

    # het kritieke pad
    try:
        kp = _D.kritieke_pad(d, alle)
    except _D.Kringloop as exc:                       # noqa: BLE001
        kp = {"kring": str(exc)}
    pad = _kritieke_pad_html(kp, per_id, terug, d)

    # de projecten van dit doel, per status
    groepen: dict[str, list] = {}
    for p in ps:
        groepen.setdefault(p.get("status") or "?", []).append(p)
    # bord-statussen eerst, dan de rest in de canonieke volgorde (afgeleid, niet opgesomd)
    volgorde = list(_PJ.OP_HET_BORD) + [x for x in _PJ.STATUSSEN if x not in _PJ.OP_HET_BORD]
    lijst = ""
    for status in [s for s in volgorde if s in groepen] + [s for s in groepen if s not in volgorde]:
        items = "".join(f"<li>{_plink(p, terug)}"
                        + (f" <span class='muted'>· {_e(p['activiteit'])}</span>" if p.get("activiteit") else "")
                        + (f" <span class='chip outline'>{_IC_CLOCK}{_e(_fmt_due(p['due']) or p['due'])}</span>" if p.get("due") else "")
                        + "</li>" for p in groepen[status])
        lijst += f"<div class='c2-sec'><h3>{_e(status)} ({len(groepen[status])})</h3><ul class='fbul'>{items}</ul></div>"
    if not ps:
        lijst = "<p class='muted'>No projects linked yet. Link them below, or per project in the rail (Goal).</p>"
    cirkel = _bord_cirkel(st, ps)
    bord = (f"<p><a class='btn sm' href='/node?id={_e(cirkel)}&tab=projects&goal={_e(d['id'])}'>"
            f"board filtered on this goal →</a></p>") if cirkel else ""

    # bulk koppelen + bewerken (alleen met csrf; de poort zit in de dispatch)
    koppel = bewerk = ""
    if rw:
        los = [p for p in alle if not p.get("archived") and not p.get("doel_id")
               and p.get("status") not in _KLAAR]
        los.sort(key=lambda p: _titel(p).lower())
        if los:
            def _eig(p) -> str:
                rec = st.records.get(p.get("owner") or "")
                return _name(rec) if rec is not None else (p.get("owner") or "")
            rijen = "".join(f"<li><input type='checkbox' id='pid-{_e(p['id'])}' name='pids' value='{_e(p['id'])}'> "
                            f"<label for='pid-{_e(p['id'])}'>{_e(_titel(p)[:90])} <span class='muted'>· {_e(_eig(p))}"
                            f" · {_e(p.get('status') or '')}</span></label></li>" for p in los)
            koppel = (f"<details class='box-details'><summary class='muted'>Link projects ({len(los)} open projects without a goal)</summary>"
                      f"<form method='post' action='/action'>{hid()}<ul class='fbul'>{rijen}</ul>"
                      f"<button class='btn ok sm' type='submit' name='action' value='goal_link'>Link selected to this goal</button>"
                      f"</form></details>")
        sopts = "".join(f"<option value='{s}'{' selected' if d.get('status') == s else ''}>{_e(_STATUS_LABEL[s])}</option>"
                        for s in _D.STATUSSEN)
        bewerk = (f"<details class='box-details'><summary class='muted'>Edit goal</summary>"
                  f"<form method='post' action='/action' class='qadd-form'>{hid()}"
                  f"{_field('Title', 'titel', value=d['titel'], required=True)}"
                  f"{_field('Short label', 'label', value=d.get('label') or '')}"
                  f"{_field('Deadline', 'deadline', kind='date', value=d.get('deadline') or '')}"
                  f"{_field('Definition of done', 'dod', kind='textarea', value=d.get('dod') or '')}"
                  f"{_field('Work packages (one per line)', 'activiteiten', kind='textarea', value=chr(10).join(d.get('activiteiten') or []))}"
                  f"<label class='att-lbl' for='f-status'>Status</label><select id='f-status' name='status' class='ctrl'>{sopts}</select>"
                  f"<div><button class='btn ok sm' type='submit' name='action' value='goal_edit'>Save</button></div>"
                  f"</form></details>")

    main = (f"<div class='c2-main'><div class='c2-bar'><a href='/goals'>← goals</a></div>"
            f"<h1>Goal</h1>" + (f"<p class='muted'>{_e(msg)}</p>" if msg else "")
            + f"{kop}<h2>Critical path</h2>{pad}<h2>Projects</h2>{bord}{lijst}{koppel}{bewerk}</div>")
    return _page(f"Goal · {d['titel']}", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}{_rail(st)}</div>")


def _bord_cirkel(st, ps) -> str:
    """De cirkel waar het bord van dit doel staat: de vaakst voorkomende ouder-cirkel van de
    gekoppelde projecten; zonder projecten de wortelcirkel. Nergens een cirkel-id hardgecodeerd."""
    telling: dict[str, int] = {}
    for p in ps:
        rec = st.records.get(p.get("owner") or "")
        ouder = getattr(rec, "parent", None) if rec is not None else None
        if ouder:
            telling[ouder] = telling.get(ouder, 0) + 1
    if telling:
        return max(telling, key=lambda k: (telling[k], k))
    roots = _org.roots(st.records.all())
    return roots[0].id if roots else ""


def _kritieke_pad_html(kp: dict, per_id: dict, terug: str, d: dict) -> str:
    if kp.get("kring"):
        p = per_id.get(kp["kring"])
        return (f"<div class='card'><span class='chip coral'>dependency loop</span> "
                f"{_plink(p, terug) if p else _e(kp['kring'])} waits on something that waits on it. "
                f"Fix the dependencies first; there is no path through a loop.</div>")
    if not kp.get("open"):
        return "<p class='muted'>No open projects: nothing left on the path.</p>"
    if not kp.get("met_afhankelijkheden"):
        return (f"<p class='muted'>{kp['open']} open project(s), none with dependencies yet. Set "
                f"“Depends on” in a project's rail and the chain appears here.</p>")
    uit = ""
    keten = kp.get("keten") or []
    if len(keten) > 1:
        stappen = " → ".join(_plink(per_id[pid], terug) for pid in keten if pid in per_id)
        uit += (f"<div class='card doel'><b>Longest chain</b> ({len(keten)} open projects, in order): "
                f"{stappen} → 🎯</div>")
    if kp.get("knelpunt"):
        k = kp["knelpunt"]
        p = per_id.get(k["pid"])
        uit += (f"<div class='card'><b>Bottleneck:</b> {_plink(p, terug) if p else _e(k['pid'])} "
                f"<span class='muted'>· {k['wachtenden']} other project(s) cannot finish before this one does</span></div>")
    if kp.get("vlaggen"):
        regels = "".join(f"<li>{_plink(per_id[f['pid']], terug) if f['pid'] in per_id else _e(f['pid'])} "
                         f"<span class='chip coral'>due {_e(_fmt_due(f['due']) or f['due'])}</span>"
                         f"{' · on the chain' if f.get('in_keten') else ''}</li>" for f in kp["vlaggen"])
        uit += (f"<div class='card'><b>Past the goal deadline</b> ({_e(_fmt_due(d['deadline']) or d['deadline'])}):"
                f"<ul class='fbul'>{regels}</ul></div>")
    if kp.get("wachtend"):
        regels = "".join(f"<li>{_plink(per_id[pid], terug)} <span class='muted'>waits on</span> "
                         + ", ".join(_plink(per_id[x], terug) for x in deps if x in per_id) + "</li>"
                         for pid, deps in kp["wachtend"] if pid in per_id)
        uit += f"<details class='box-details'><summary class='muted'>Waiting ({len(kp['wachtend'])})</summary><ul class='fbul'>{regels}</ul></details>"
    if kp.get("vrij"):
        regels = "".join(f"<li>{_plink(per_id[pid], terug)}</li>" for pid in kp["vrij"] if pid in per_id)
        uit += f"<details class='box-details'><summary class='muted'>Free to pick up now ({len(kp['vrij'])})</summary><ul class='fbul'>{regels}</ul></details>"
    return uit
