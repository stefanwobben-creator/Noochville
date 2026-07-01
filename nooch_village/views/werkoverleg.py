"""Werkoverleg-views — brok 3 van de cockpit2-split."""
from __future__ import annotations
from typing import TYPE_CHECKING

from nooch_village import org
from nooch_village.cockpit import _e, _page
from nooch_village.cockpit2_util import _name, _initials, _psec, _IC_CHECK, _IC_INFO
from nooch_village.werkoverleg import STEPS as _WO_STEPS
from nooch_village.cockpit2_util import _EXTRA_CSS
from nooch_village.views.overview import _members_of_circle
from nooch_village.views.metrics import _spark_svg, _tile_meta, _fetch, _num, _agg, _metrics_tab_html
from nooch_village.views.checklists import _checklists_tab_html
from nooch_village.views.projects import _projects_tab_html

if TYPE_CHECKING:
    from nooch_village.cockpit2 import _Stores


def _wo_hid(csrf, circle, nextu):
    return (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
            f"<input type='hidden' name='circle' value='{_e(circle)}'>"
            f"<input type='hidden' name='next' value='{_e(nextu)}'>")


def _wo_checkin(st: _Stores, crec, csrf: str) -> str:
    """Stap 1: aanwezigheid. ✓ = aanwezig, ✗ = afwezig/op verlof (taken pauzeren)."""
    ppl = _members_of_circle(st, crec.id)
    nxt = f"/werkoverleg?circle={crec.id}&step=checkin"
    if not ppl:
        return ("<div class='c2-sec'><h3>Check-in</h3>"
                "<p class='muted'>Nog geen mensen aan deze cirkel gekoppeld (zie Rollen → rolvervullers).</p></div>")
    rows = ""
    for p in ppl:
        present = st.werk.is_present(crec.id, p.id)
        if csrf:
            def b(val, lbl, c):
                on = " on" if present == val else ""
                return (f"<form method='post' action='/action' style='display:inline'>{_wo_hid(csrf, crec.id, nxt)}"
                        f"<input type='hidden' name='pid' value='{_e(p.id)}'>"
                        f"<input type='hidden' name='present' value='{'1' if val else '0'}'>"
                        f"<button class='cl-check {c}{on}' type='submit' name='action' value='wo_presence' "
                        f"title='{lbl}'>{'✓' if val else '✗'}</button></form>")
            ctrl = b(True, "aanwezig", "ok") + b(False, "afwezig (verlof)", "no")
        else:
            ctrl = f"<span class='cl-check {'ok' if present else 'no'} on'>{'✓' if present else '✗'}</span>"
        leave = "" if present else "<span class='wo-leave muted'>op verlof — taken gepauzeerd</span>"
        rows += (f"<div class='wo-mem{'' if present else ' absent'}'><span class='av'>{_e(_initials(p.name))}</span>"
                 f"<span class='wo-mem-n'>{_e(p.name)}</span>{leave}<span class='cl-checks'>{ctrl}</span></div>")
    allbtn = ""
    if csrf:
        allbtn = (f"<form method='post' action='/action'>{_wo_hid(csrf, crec.id, nxt)}"
                  f"<button class='btn sm' type='submit' name='action' value='wo_present_all'>Allen aanwezig</button></form>")
    return (f"<div class='c2-sec'><div class='cl-head'><h3>Check-in</h3>{allbtn}</div>"
            f"<p class='muted' style='font-size:.8rem'>Wie doet mee? Klik of gebruik ↑/↓ en dan "
            f"<b>v</b> (aanwezig) / <b>x</b> (afwezig). ✗ = op verlof: niet aanwezig en taken pauzeren.</p>"
            f"<div class='wo-mems' tabindex='0'>{rows}</div></div>")


def _wo_checklist(st: _Stores, crec, csrf: str) -> str:
    """Stap 2: de checklist-ronde. Hergebruikt het checklist-scherm; toont wie rapporteert
    (afwezigen met ✗)."""
    ppl = _members_of_circle(st, crec.id)
    chips = "".join(
        f"<span class='chip {'muted' if st.werk.is_present(crec.id, p.id) else 'coral'}'>"
        f"{'✗ ' if not st.werk.is_present(crec.id, p.id) else ''}{_e(p.name)}</span>" for p in ppl)
    who = f"<div class='wo-who'><span class='muted'>Rapporteren:</span> {chips}</div>" if ppl else ""
    # In het overleg: toon ALLES (afgevinkte items met hun resultaat blijven staan) en blijf in de modal.
    nav = f"/werkoverleg?circle={crec.id}&step=checklist"
    return who + _checklists_tab_html(st, crec, csrf, "all", nav=nav)


def _wo_metrics(st: _Stores, crec, csrf: str, kpi: str = "", win: str = "maand") -> str:
    """Stap 3: metrics-ronde. Hergebruikt het dashboard; optioneel één tegel uitvergroot met
    trend + tabel + een knop voor Noochie-duiding."""
    base = f"/werkoverleg?circle={crec.id}&step=metrics"
    focus = ""
    if kpi:
        tile = next((t for t in st.metrics.tiles_of(crec.id) if t["id"] == kpi), None)
        if tile is not None:
            res = _fetch(st, tile["source"], tile["measure"], tile.get("dim", "none"), None)
            pts = res.get("points") or []
            rows = res.get("rows") or []
            tbl = ""
            if pts:
                tbl = "<table class='mtab'>" + "".join(
                    f"<tr><td>{_dt(at)}</td><td class='num'>{v:g}</td></tr>" for at, v in pts[-12:]) + "</table>"
            elif rows:
                tbl = "<table class='mtab'>" + "".join(
                    f"<tr><td>{_e(str(l))}</td><td class='num'>{n:g}</td></tr>" for l, n in rows[:12]) + "</table>"
            ask = _e(f"{_tile_meta(st, crec, tile)} (laatste: {(_num(_agg(res)))})")
            ai = (f"<button class='btn sm' type='button' onclick=\"window.noochieAsk&&noochieAsk('{ask}')\">"
                  f"🐸 Noochie duidt deze KPI</button>")
            focus = (f"<div class='c2-sec wo-focus'><div class='cl-head'><h3>{_e(_tile_meta(st, crec, tile))}</h3>"
                     f"<a class='flink js-modal' href='{base}' data-href='{base}'>← terug</a></div>"
                     f"{_spark_svg(pts, 280, 70) if pts else ''}{tbl or '<p class=muted>geen data</p>'}"
                     f"<div style='margin-top:.6rem'>{ai}</div></div>")
    # uitvergroot-links per tegel
    links = ""
    for t in st.metrics.tiles_of(crec.id):
        u = f"{base}&kpi={t['id']}"
        links += f"<a class='chip outline js-modal' href='{u}' data-href='{u}'>{_e(_tile_meta(st, crec, t))}</a> "
    tabrow = f"<div class='wo-kpitabs'>{links}</div>" if links else ""
    return focus + tabrow + _metrics_tab_html(st, crec, csrf, win, nav=base)


def _wo_spanning_add(st: _Stores, crec, csrf: str) -> str:
    """Spanning toevoegen — staat bovenaan de linkerkolom (boven de stappen), altijd bereikbaar."""
    if not csrf:
        return "<span class='muted'>—</span>"
    base = f"/werkoverleg?circle={crec.id}&step=agenda"
    return (f"<form method='post' action='/action' class='rov-add wo-sp-add'>{_wo_hid(csrf, crec.id, base)}"
            f"<input name='naam' placeholder='Spanning… (-SW voor initialen)' autocomplete='off'>"
            f"<button class='btn ok sm' type='submit' name='action' value='wo_ag_add'>+</button></form>")


def _wo_spanning_items(st: _Stores, crec, csrf: str, active_iid: str = "") -> str:
    """Ingebrachte spanningen — genest onder de Agenda-stap in het linkermenu (geen microcopy)."""
    base = f"/werkoverleg?circle={crec.id}&step=agenda"
    rows = ""
    for it in st.werk.agenda(crec.id):
        done = it["status"] == "done"
        on = " on" if it["id"] == active_iid else ""
        url = f"{base}&iid={it['id']}"
        by = (it.get("by") or "").strip()
        av = f"<span class='av rov-by' title='door {_e(by)}'>{_e(by)}</span>" if by else ""
        rm = (f"<form method='post' action='/action' style='display:inline'>{_wo_hid(csrf, crec.id, base)}"
              f"<input type='hidden' name='iid' value='{_e(it['id'])}'>"
              f"<button class='flink' type='submit' name='action' value='wo_ag_remove'>✕</button></form>") if csrf else ""
        rows += (f"<div class='rov-item{on}{(' done' if done else '')}'>"
                 f"<a class='js-modal rov-link' href='{url}' data-href='{url}'><span class='rov-title'>{_e(it['title'])}</span></a>"
                 f"{av}{rm}</div>")
    return rows


def _wo_triage(st: _Stores, crec, csrf: str, item: dict) -> str:
    """Stap 5b: een spanning verwerken. Noteer spanning/rol/behoefte en kies een uitkomst:
    info delen, project toevoegen, punt voor roloverleg, of nevermind."""
    iid = item["id"]
    base = f"/werkoverleg?circle={crec.id}&step=agenda"
    back = f"{base}&iid={iid}"
    note = item.get("note", {})
    done = item["status"] == "done"
    roles = sorted(org.roles_of(st.records.all(), crec.id), key=lambda r: _name(r).lower())
    keep = f"data-reopen='{_e(back)}'"
    sub = "this.form.requestSubmit?this.form.requestSubmit():this.form.submit()"

    def setf(field, label, value, ta=False):
        inp = (f"<textarea name='value' rows='2' onchange='{sub}'>{_e(value)}</textarea>" if ta
               else f"<input name='value' value='{_e(value)}' onchange='{sub}'>")
        return (f"<div class='rovm-field'><label class='att-lbl'>{label}</label>"
                f"<form method='post' action='/action' {keep}>{_wo_hid(csrf, crec.id, back)}"
                f"<input type='hidden' name='iid' value='{_e(iid)}'><input type='hidden' name='field' value='{field}'>"
                f"<input type='hidden' name='action' value='wo_ag_note'>{inp}</form></div>")

    ropts = "".join(f"<option value='{_e(r.id)}'>{_e(_name(r))}</option>" for r in roles)
    cur_role = note.get("role", "")
    ropts_role = "".join(f"<option value='{_e(r.id)}'{' selected' if r.id == cur_role else ''}>{_e(_name(r))}</option>"
                         for r in roles)
    head = f"<div class='cl-head'><h3>Spanning verwerken</h3><a class='flink js-modal' href='{base}' data-href='{base}'>← agenda</a></div>"
    if done:
        oc = item.get("outcome", {})
        return (f"<div class='c2-sec'>{head}<p><b>{_e(item['title'])}</b></p>"
                f"<div class='sec-issue let'>Afgehandeld als <b>{_e(oc.get('type', ''))}</b>"
                f"{(': ' + _e(oc.get('detail', ''))) if oc.get('detail') else ''}</div>"
                f"<form method='post' action='/action' {keep} style='margin-top:.5rem'>{_wo_hid(csrf, crec.id, back)}"
                f"<input type='hidden' name='iid' value='{_e(iid)}'>"
                f"<button class='flink' type='submit' name='action' value='wo_ag_reopen'>↺ heropenen</button></form></div>")

    # Spanning + rol (optioneel) als eigen blok, los van de uitkomsten. 'Wat heb je nodig' is weg:
    # dat is altijd de uitkomst zelf.
    fields = (f"<div class='wo-spanning'>"
              + setf("spanning", "Wat is de spanning?", note.get("spanning", ""), ta=True)
              + f"<div class='rovm-field'><label class='att-lbl'>Welke rol voelt 'm? (optioneel)</label>"
                f"<form method='post' action='/action' {keep}>{_wo_hid(csrf, crec.id, back)}"
                f"<input type='hidden' name='iid' value='{_e(iid)}'><input type='hidden' name='field' value='role'>"
                f"<input type='hidden' name='action' value='wo_ag_note'>"
                f"<select name='value' onchange='{sub}'><option value=''>—</option>{ropts_role}</select></form></div></div>")

    # Progressive disclosure: kies eerst het type, dan verschijnt het juiste veld. Gelijkwaardig
    # (geen primary-kleur die naar één uitkomst stuurt).
    def oc_details(otype, summary, inner):
        return (f"<details class='wo-ocd box-details'><summary>{summary}</summary>"
                f"<form method='post' action='/action' {keep} class='wo-oc'>{_wo_hid(csrf, crec.id, base)}"
                f"<input type='hidden' name='iid' value='{_e(iid)}'><input type='hidden' name='otype' value='{otype}'>"
                f"{inner}<button class='btn sm' type='submit' name='action' value='wo_ag_resolve'>Vastleggen</button></form></details>")

    # projecten onder deze cirkel (om een actie optioneel aan te koppelen = checklist-item),
    # gegroepeerd per rol zodat het ook bij veel projecten navigeerbaar blijft (+ type-ahead).
    circle_nodes = {crec.id} | {r.id for r in roles}
    by_role: dict = {}
    for p in st.projects.all():
        if p.get("owner") in circle_nodes and not p.get("archived"):
            by_role.setdefault(p["owner"], []).append(p)
    pj_opts = "<option value=''>— los (geen project) —</option>"
    for rid in sorted(by_role, key=lambda x: _name(st.records.get(x) or crec).lower()):
        rn = _name(st.records.get(rid)) if st.records.get(rid) else rid
        opts = "".join(f"<option value='{_e(p['id'])}'>{_e(str(p.get('scope') or p['id'])[:60])}</option>"
                       for p in by_role[rid])
        pj_opts += f"<optgroup label='{_e(rn)}'>{opts}</optgroup>"

    info = oc_details("info", "Informatie",
                      "<select name='dir'><option value='delen'>delen</option>"
                      "<option value='nodig'>nodig</option></select>"
                      "<textarea name='detail' rows='2' placeholder='Wat? Gebruik @naam of @rol voor "
                      "gericht; anders geldt het voor iedereen'></textarea>")
    proj = oc_details("project", "Project toevoegen",
                      f"<select name='owner'>{ropts}</select>"
                      f"<input name='detail' placeholder='formulering van het project' autocomplete='off'>")
    act = oc_details("action", "Actie",
                     "<input name='detail' placeholder='wat ga je doen? (bv. meeting plannen, mail doorsturen)' autocomplete='off'>"
                     f"<select name='pid_link'>{pj_opts}</select>"
                     "<span class='muted' style='font-size:.74rem'>Gaat altijd door. Aan een project gekoppeld "
                     "= checklist-item; los = losse actie. Terugkerend werk? Overweeg het roloverleg.</span>")
    rov = oc_details("roloverleg", "Punt voor roloverleg",
                     "<textarea name='detail' rows='2' placeholder='kans / probleem / behoefte / eerste rol-schets'></textarea>")
    nm = (f"<form method='post' action='/action' {keep} class='wo-oc'>{_wo_hid(csrf, crec.id, base)}"
          f"<input type='hidden' name='iid' value='{_e(iid)}'><input type='hidden' name='otype' value='nevermind'>"
          f"<button class='flink' type='submit' name='action' value='wo_ag_resolve'>Niet nodig</button></form>")
    # secretaris-signaal (licht): mis je info/scope? (Noochie zit al in de balk; geen losse knop.)
    hint = ""
    if not (note.get("spanning") or "").strip():
        hint = "<div class='sec-issue let'>📋 Secretaris: noteer kort de spanning zodat 'm te verwerken is.</div>"
    return (f"<div class='c2-sec'>{head}<p><b>{_e(item['title'])}</b></p>{hint}{fields}"
            f"<div class='wo-outcomes'><div class='sec-kop'>Uitkomst kiezen</div>{info}{proj}{act}{rov}{nm}</div></div>")


def _wo_checkout(st: _Stores, crec, csrf: str) -> str:
    """Stap 6: check-out. Per persoon een tevredenheidsscore 0-10."""
    ppl = _members_of_circle(st, crec.id)
    nxt = f"/werkoverleg?circle={crec.id}&step=checkout"
    scores = st.werk.checkout(crec.id)
    if not ppl:
        return "<div class='c2-sec'><h3>Check-out</h3><p class='muted'>Geen leden.</p></div>"
    prev = st.werk.prev_checkout(crec.id)               # scores van het vorige overleg (ghost)
    vals = [v for v in scores.values() if isinstance(v, int)]
    avg = f"{round(sum(vals) / len(vals), 1)}/10" if vals else "—"
    rows = ""
    for p in ppl:
        cur = scores.get(p.id)
        pv = prev.get(p.id)
        if csrf:
            cells = ""
            for n in range(0, 11):
                cls = "wo-sc" + (" on" if cur == n else (" prev" if cur is None and pv == n else ""))
                title = " title='vorige keer'" if (pv == n and cur != n) else ""
                cells += (f"<form method='post' action='/action' style='display:inline'>{_wo_hid(csrf, crec.id, nxt)}"
                          f"<input type='hidden' name='pid' value='{_e(p.id)}'><input type='hidden' name='score' value='{n}'>"
                          f"<button class='{cls}'{title} type='submit' name='action' value='wo_checkout'>{n}</button></form>")
            sel = f"<span class='wo-scale'>{cells}</span>"
        else:
            sel = f"<span class='kpidata-v'>{cur if cur is not None else '—'}</span>"
        rows += (f"<div class='wo-mem'><span class='av'>{_e(_initials(p.name))}</span>"
                 f"<span class='wo-mem-n'>{_e(p.name)}</span>{sel}</div>")
    legend = ("<span class='muted' style='font-size:.74rem'>lichter = vorige keer</span>"
              if prev else "")
    return (f"<div class='c2-sec'><div class='cl-head'><h3>Check-out</h3>"
            f"<span class='muted'>gemiddeld: <span class='wo-avg'>{avg}</span></span></div>"
            f"<p class='muted' style='font-size:.8rem'>Op een schaal van 0-10: hoe tevreden ben je met "
            f"de uitkomst van dit overleg? {legend}</p>{rows}</div>")


def _wo_summary(st: _Stores, crec, csrf: str) -> str:
    """Stap 7: samenvatting + sluiten (confetti via wo_close)."""
    s = st.werk.summary(crec.id)
    pres = st.werk.presence(crec.id)
    ppl = _members_of_circle(st, crec.id)
    aanwezig = [p.name for p in ppl if pres.get(p.id, True)]
    afwezig = [p.name for p in ppl if pres.get(p.id) is False]
    tev = f"{s['tevredenheid']}/10" if s["tevredenheid"] is not None else "n.v.t."
    rij = lambda k, v: f"<div class='wo-sumrow'><span>{k}</span><b>{v}</b></div>"
    body = (rij("Aanwezig", ", ".join(aanwezig) or "—")
            + rij("Afwezig", ", ".join(afwezig) or "—")
            + rij("Punten behandeld", s["behandeld"])
            + rij("Informatie verwerkt", s["info"])
            + rij("Projecten toegevoegd", s["projecten"])
            + rij("Acties", s.get("acties", 0))
            + rij("Punten voor roloverleg", s["roloverleg"])
            + rij("Gemiddelde tevredenheid", tev)
            + rij("Duur", f"{s['duur_min']} min"))
    return (f"<div class='c2-sec'><h3>Samenvatting</h3><div class='wo-sum'>{body}</div>"
            f"<p class='muted' style='font-size:.8rem;margin-top:.6rem'>Klik “Sluit overleg” onderaan: "
            f"alle uitkomsten worden verwerkt en het overleg sluit.</p></div>")


def render_werkoverleg(st: _Stores, circle_id: str, step: str = "checkin", csrf_token: str = "",
                       fragment: bool = False, iid: str = "", kpi: str = "", mw: str = "maand") -> str:
    """Werkoverleg-modal: links de vaste stap-navigatie, rechts de inhoud per stap. De inhoud
    HERGEBRUIKT de bestaande schermen (members/checklists/metrics/projecten). Alleen de secretaris
    opent en sluit. Brok 1: frame + ingebedde schermen; de overleg-specifieke stappen volgen."""
    crec = st.records.get(circle_id)
    if crec is None or not org.is_circle(crec):
        return ("<p class='muted'>Geen cirkel.</p>" if fragment
                else _page("Niet gevonden", "<p>Geen cirkel.</p>"))
    base = f"/werkoverleg?circle={circle_id}"
    sec = "<div class='wo-sec muted'>Alleen de secretaris opent en sluit dit overleg.</div>"

    def hid(nextu):
        return (f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                f"<input type='hidden' name='circle' value='{_e(circle_id)}'>"
                f"<input type='hidden' name='next' value='{_e(nextu)}'>")

    if not st.werk.is_open(circle_id):
        start = ""
        if csrf_token:
            su = f"{base}&step=checkin"
            start = (f"<form method='post' action='/action'>{hid(su)}"
                     f"<button class='btn ok' type='submit' name='action' value='wo_open' "
                     f"data-reopen='{_e(su)}'>Werkoverleg starten</button></form>")
        body = (f"<h2 style='margin-top:0'>Werkoverleg — {_e(_name(crec))}</h2>"
                f"<p class='muted'>Vaste volgorde: check-in, checklist, metrics, projecten, agenda, "
                f"check-out, sluiten.</p>{sec}<div style='margin-top:1rem'>{start}</div>")
        return body if fragment else _page(
            "Werkoverleg", f"<style>{_EXTRA_CSS}</style><div class='c2-wrap'>{body}</div>")

    cur = step if step in dict(_WO_STEPS) else "checkin"
    st.werk.mark_visited(circle_id, cur)                 # voortgang: bezochte stappen
    visited = set(st.werk.visited(circle_id))
    nav = ""
    for i, (k, lbl) in enumerate(_WO_STEPS, 1):
        url = f"{base}&step={k}"
        done = k in visited and k != cur
        num = "✓" if done else str(i)
        cls = "wo-step" + (" on" if k == cur else "") + (" done" if done else "")
        nav += (f"<a class='{cls} js-modal' href='{url}' data-href='{url}'>"
                f"<span class='wo-num'>{num}</span>{_e(lbl)}</a>")
        if k == "agenda":   # ingebrachte spanningen genest onder de Agenda-stap
            items = _wo_spanning_items(st, crec, csrf_token, iid)
            if items:
                nav += f"<div class='wo-substeps'>{items}</div>"
    # Spanning toevoegen staat bovenaan (boven Check-in); de stappen eronder.
    left = (_psec(_IC_INFO, "Spanningen", _wo_spanning_add(st, crec, csrf_token))
            + _psec(_IC_CHECK, "Overleg", f"<div class='wo-nav'>{nav}</div>"))

    if cur == "checkin":
        content = _wo_checkin(st, crec, csrf_token)
    elif cur == "checklist":
        content = _wo_checklist(st, crec, csrf_token)
    elif cur == "metrics":
        content = _wo_metrics(st, crec, csrf_token, kpi, win=mw)
    elif cur == "projecten":
        # In het overleg worden projecten via de triage (agenda) toegevoegd, niet hier los.
        content = _projects_tab_html(st, crec, csrf_token, group="", add=False)
    elif cur == "agenda":
        item = st.werk.agenda_get(crec.id, iid) if iid else None
        content = (_wo_triage(st, crec, csrf_token, item) if item is not None
                   else "<div class='c2-sec'><h3>Spanning verwerken</h3>"
                        "<p class='muted'>Kies links een spanning om te verwerken, of voeg er een toe.</p></div>")
    elif cur == "checkout":
        content = _wo_checkout(st, crec, csrf_token)
    else:
        content = _wo_summary(st, crec, csrf_token)

    foot = (f"<div class='rov-foot'><form method='post' action='/action' "
            f"data-confirm='Overleg sluiten en alle uitkomsten verwerken? Dit kan niet ongedaan.'>"
            f"{hid(f'/node?id={circle_id}')}"
            f"<button class='btn ok' type='submit' name='action' value='wo_close'>Sluit overleg</button></form>"
            f"<span class='muted'>loopt {st.werk.duration_min(circle_id)} min</span></div>")
    detail = (f"<h2 style='margin-top:0'>Werkoverleg — {_e(_name(crec))}</h2>"
              f"<div class='pgrid rov-grid'><div class='pmain'>{left}</div>"
              f"<aside class='pdisc'>{content}</aside></div>{foot}")
    if fragment:
        return detail
    return _page("Werkoverleg", f"<style>{_EXTRA_CSS}</style><div class='c2-wrap'>"
                 f"<div class='c2-main' style='max-width:1000px'>{detail}</div></div>")
