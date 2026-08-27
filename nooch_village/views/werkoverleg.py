"""Werkoverleg-views — brok 3 van de cockpit2-split."""
from __future__ import annotations
from typing import TYPE_CHECKING

from nooch_village import org
from nooch_village.web_base import _e, _page
from nooch_village.cockpit2_util import _DS_LINK, _name, _initials, _psec, _IC_CHECK, _IC_INFO
from nooch_village.werkoverleg import STEPS as _WO_STEPS
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
                "<p class='muted'>No people linked to this circle yet (see Roles → role fillers).</p></div>")
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
            ctrl = b(True, "present", "ok") + b(False, "absent (on leave)", "no")
        else:
            ctrl = f"<span class='cl-check {'ok' if present else 'no'} on'>{'✓' if present else '✗'}</span>"
        leave = "" if present else "<span class='wo-leave muted'>on leave — tasks paused</span>"
        rows += (f"<div class='wo-mem{'' if present else ' absent'}'><span class='av'>{_e(_initials(p.name))}</span>"
                 f"<span class='wo-mem-n'>{_e(p.name)}</span>{leave}<span class='cl-checks'>{ctrl}</span></div>")
    allbtn = ""
    if csrf:
        allbtn = (f"<form method='post' action='/action'>{_wo_hid(csrf, crec.id, nxt)}"
                  f"<button class='btn sm' type='submit' name='action' value='wo_present_all'>All present</button></form>")
    return (f"<div class='c2-sec'><div class='cl-head'><h3>Check-in</h3>{allbtn}</div>"
            f"<p class='muted' style='font-size:.8rem'>Who is joining? Click, or use ↑/↓ and then "
            f"<b>v</b> (present) / <b>x</b> (absent). ✗ = on leave: not present and tasks pause.</p>"
            f"<div class='wo-mems' tabindex='0'>{rows}</div></div>")


def _wo_checklist(st: _Stores, crec, csrf: str) -> str:
    """Stap 2: de checklist-ronde. Hergebruikt het checklist-scherm; toont wie rapporteert
    (afwezigen met ✗)."""
    ppl = _members_of_circle(st, crec.id)
    chips = "".join(
        f"<span class='chip {'muted' if st.werk.is_present(crec.id, p.id) else 'coral'}'>"
        f"{'✗ ' if not st.werk.is_present(crec.id, p.id) else ''}{_e(p.name)}</span>" for p in ppl)
    who = f"<div class='wo-who'><span class='muted'>Reporting:</span> {chips}</div>" if ppl else ""
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
            ask = _e(f"{_tile_meta(st, crec, tile)} (latest: {(_num(_agg(res)))})")
            ai = (f"<button class='btn sm' type='button' onclick=\"window.noochieAsk&&noochieAsk('{ask}')\">"
                  f"🐸 Noochie reads this KPI</button>")
            focus = (f"<div class='c2-sec wo-focus'><div class='cl-head'><h3>{_e(_tile_meta(st, crec, tile))}</h3>"
                     f"<a class='flink js-modal' href='{base}' data-href='{base}'>← back</a></div>"
                     f"{_spark_svg(pts, 280, 70) if pts else ''}{tbl or '<p class=muted>no data</p>'}"
                     f"<div style='margin-top:.6rem'>{ai}</div></div>")
    # uitvergroot-links per tegel
    links = ""
    for t in st.metrics.tiles_of(crec.id):
        u = f"{base}&kpi={t['id']}"
        links += f"<a class='chip outline js-modal' href='{u}' data-href='{u}'>{_e(_tile_meta(st, crec, t))}</a> "
    tabrow = f"<div class='wo-kpitabs'>{links}</div>" if links else ""
    return focus + tabrow + _metrics_tab_html(st, crec, csrf, win, nav=base)


def _wo_vangbar(st, crec, csrf: str, step: str) -> str:
    """De vangbalk — op ELKE stap, niet alleen op de agenda-stap.

    Wie tijdens de check-in of bij de projecten iets hoort, moet het daar kunnen opschrijven.
    Stond het veld alleen op stap 5, dan was de handeling in de praktijk "onthouden tot stap 5",
    en dat is precies wat vangen moet vervangen. Vangen is een regel typen; behandelen is een
    andere handeling, en die blijft onder de agenda-stap hangen.

    De teller is de terugkoppeling op de andere zes stappen: daar staat de lijst niet, dus moet
    het getal laten zien dat het punt geland is."""
    from nooch_village.views.vangst import _vang_form

    punten = st.werk.punten(crec.id)
    open_n = sum(1 for p in punten if p.get("status") != "done")
    onderw = f"{len(punten)} onderwerp" + ("" if len(punten) == 1 else "en")
    nxt = f"/werkoverleg?circle={crec.id}&step={step}"
    vang = _vang_form(crec.id, csrf, nxt) if csrf else ""
    hint = ("Typ een punt en druk Enter — dat is de hele handeling. Klik <em>verwerken</em> onder "
            "een punt om er uitkomsten onder te leggen; er mogen er meerdere zijn, elk naar een "
            "andere rol." if step == "agenda" else
            "Typ een punt en druk Enter — hij komt op de agenda te staan. Behandelen doe je bij "
            "stap 5; je hoeft daar nu niet heen.")
    # De tellers worden na een vangst bijgewerkt door de gedeelde mechaniek: het lijst-fragment
    # draagt ze mee als `data-nv-mirror`-bron, dus ze kloppen ook op de zes stappen waar de lijst
    # zelf niet op het scherm staat.
    return (f"<div class='c2-sec'><h3>Punten behandelen <span class='muted'>("
            f"<span id='vang-tot'>{onderw}</span>, "
            f"<span id='vang-n'>{open_n}</span> te doen)</span></h3>"
            f"<p class='muted'>{hint}</p>{vang}</div>")


def _wo_agenda(st, crec, csrf: str, iid: str = "") -> str:
    """De agenda-stap: DEZELFDE vang-en-verwerk als `/vangst`, niet een tweede versie ervan.

    Hier stond een eigen triage-scherm met een uitkomst per spanning, een rollenlijst die tot deze
    cirkel beperkt was, en een aparte notitie-vorm. Dat was een kopie die uit de pas liep zodra
    /vangst iets leerde. Nu roept deze stap de componenten aan die het vangscherm ook gebruikt:
    een plek waar de vorm wordt bepaald.

    Het vangveld zelf staat niet meer hier maar in `_wo_vangbar`, boven de inhoud van elke stap.
    Deze functie levert alleen de puntenlijst, die daar direct onder komt te hangen.

    De formulieren posten via `fetch`: het vangveld via de gedeelde mechaniek
    (`static/nooch.js`), de rest via de modal-controller die elk formulier in de overlay
    onderschept. Er reist geen script mee — een `<script>` in een fragment draait toch niet als de
    modal het via `innerHTML` invoegt, en dát is precies waarom de mechaniek in een echt
    bestand hoort dat de pagina al geladen heeft."""
    from nooch_village.views.vangst import render_vangst_frag

    nxt = f"/werkoverleg?circle={crec.id}&step=agenda"
    lijst = render_vangst_frag(st, crec.id, csrf, open_iid=iid, nxt=nxt)
    return f"<div class='rdr-tool' id='vang-lijst'>{lijst}</div>"


def _wo_checkout(st: _Stores, crec, csrf: str) -> str:
    """Stap 6: check-out. Per persoon een tevredenheidsscore 0-10."""
    ppl = _members_of_circle(st, crec.id)
    nxt = f"/werkoverleg?circle={crec.id}&step=checkout"
    scores = st.werk.checkout(crec.id)
    if not ppl:
        return "<div class='c2-sec'><h3>Check-out</h3><p class='muted'>No members.</p></div>"
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
                title = " title='last time'" if (pv == n and cur != n) else ""
                cells += (f"<form method='post' action='/action' style='display:inline'>{_wo_hid(csrf, crec.id, nxt)}"
                          f"<input type='hidden' name='pid' value='{_e(p.id)}'><input type='hidden' name='score' value='{n}'>"
                          f"<button class='{cls}'{title} type='submit' name='action' value='wo_checkout'>{n}</button></form>")
            sel = f"<span class='wo-scale'>{cells}</span>"
        else:
            sel = f"<span class='kpidata-v'>{cur if cur is not None else '—'}</span>"
        rows += (f"<div class='wo-mem'><span class='av'>{_e(_initials(p.name))}</span>"
                 f"<span class='wo-mem-n'>{_e(p.name)}</span>{sel}</div>")
    legend = ("<span class='muted' style='font-size:.74rem'>lighter = last time</span>"
              if prev else "")
    return (f"<div class='c2-sec'><div class='cl-head'><h3>Check-out</h3>"
            f"<span class='muted'>average: <span class='wo-avg'>{avg}</span></span></div>"
            f"<p class='muted' style='font-size:.8rem'>On a scale of 0-10: how satisfied are you with "
            f"the outcome of this meeting? {legend}</p>{rows}</div>")


def _wo_summary(st: _Stores, crec, csrf: str) -> str:
    """Stap 7: samenvatting + sluiten (confetti via wo_close)."""
    s = st.werk.summary(crec.id)
    pres = st.werk.presence(crec.id)
    ppl = _members_of_circle(st, crec.id)
    aanwezig = [p.name for p in ppl if pres.get(p.id, True)]
    afwezig = [p.name for p in ppl if pres.get(p.id) is False]
    tev = f"{s['tevredenheid']}/10" if s["tevredenheid"] is not None else "n/a"
    rij = lambda k, v: f"<div class='wo-sumrow'><span>{k}</span><b>{v}</b></div>"
    body = (rij("Present", ", ".join(aanwezig) or "—")
            + rij("Absent", ", ".join(afwezig) or "—")
            + rij("Items handled", s["behandeld"])
            + rij("Information processed", s["info"])
            + rij("Projects added", s["projecten"])
            + rij("Actions", s.get("acties", 0))
            + rij("Items for governance meeting", s["roloverleg"])
            + rij("Average satisfaction", tev)
            + rij("Duration", f"{s['duur_min']} min"))
    return (f"<div class='c2-sec'><h3>Summary</h3><div class='wo-sum'>{body}</div>"
            f"<p class='muted' style='font-size:.8rem;margin-top:.6rem'>Click “Close meeting” below: "
            f"all outcomes are processed and the meeting closes.</p></div>")


def render_werkoverleg(st: _Stores, circle_id: str, step: str = "checkin", csrf_token: str = "",
                       fragment: bool = False, iid: str = "", kpi: str = "", mw: str = "maand") -> str:
    """Werkoverleg-modal: links de vaste stap-navigatie, rechts de inhoud per stap. De inhoud
    HERGEBRUIKT de bestaande schermen (members/checklists/metrics/projecten). Alleen de secretaris
    opent en sluit. Brok 1: frame + ingebedde schermen; de overleg-specifieke stappen volgen."""
    crec = st.records.get(circle_id)
    if crec is None or not org.is_circle(crec):
        return ("<p class='muted'>No circle.</p>" if fragment
                else _page("Not found", "<p>No circle.</p>"))
    base = f"/werkoverleg?circle={circle_id}"
    sec = "<div class='wo-sec muted'>Only the secretary opens and closes this meeting.</div>"

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
                     f"data-reopen='{_e(su)}'>Start tactical meeting</button></form>")
        body = (f"<h2 style='margin-top:0'>Tactical meeting — {_e(_name(crec))}</h2>"
                f"<p class='muted'>Fixed order: check-in, checklist, metrics, projects, agenda, "
                f"check-out, close.</p>{sec}<div style='margin-top:1rem'>{start}</div>")
        return body if fragment else _page(
            "Tactical meeting", f"{_DS_LINK}<div class='c2-wrap'>{body}</div>")

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
    # Het vangveld en de puntenlijst stonden hier als tweede kopie in de linkerkolom. Ze wonen nu
    # in de Agenda-stap zelf, want dat is waar je ze gebruikt — en het is één component.
    left = _psec(_IC_CHECK, "Meeting", f"<div class='wo-nav'>{nav}</div>")

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
        content = _wo_agenda(st, crec, csrf_token, iid)
    elif cur == "checkout":
        content = _wo_checkout(st, crec, csrf_token)
    else:
        content = _wo_summary(st, crec, csrf_token)

    # De vangbalk hoort bij het OVERLEG, niet bij stap 5. Hij staat daarom boven de inhoud van
    # elke stap; alleen de puntenlijst blijft onder de agenda-stap hangen.
    content = _wo_vangbar(st, crec, csrf_token, cur) + content

    # Per-stap actie i.p.v. de oude vaste onderbalk: stap 1-6 = "Volgende", stap 7 = centrale
    # "Sluit overleg" onder de samenvatting (die samenvatting is zelf de bevestiging).
    _keys = [k for k, _ in _WO_STEPS]
    _ni = _keys.index(cur)
    if cur == "sluiten":
        step_action = (
            f"<div class='wo-close-wrap'><form method='post' action='/action'>"
            f"{hid(f'/node?id={circle_id}')}"
            f"<button class='btn ok wo-close-btn' type='submit' name='action' value='wo_close'>"
            f"Close meeting</button></form>"
            f"<span class='muted'>Terminal action · outcomes are already recorded per item</span></div>")
    else:
        _nu = f"{base}&step={_keys[_ni + 1]}"
        step_action = (f"<div class='wo-next'><a class='btn ok js-modal' href='{_nu}' "
                       f"data-href='{_nu}'>Next →</a></div>")

    # Header: titel + timer (klein rechts) + "verlaat overleg" (sluit je view/room, geen afronden).
    _leave = f"/node?id={circle_id}"
    header = (f"<div class='wo-head'><h2>Tactical meeting — {_e(_name(crec))}</h2>"
              f"<span class='wo-timer' title='running since start'>⏱ {st.werk.duration_min(circle_id)} min</span>"
              f"<a class='wo-leave' href='{_leave}' "
              f"title='Leave your view — the meeting continues' "
              f"onclick=\"var o=this.closest('.ovl');if(o){{var x=o.querySelector('.ovl-x');"
              f"if(x){{x.click();return false;}}}}\">✕ leave meeting</a></div>")

    # LiveKit verhuist naar een dorp-brede call bar (volgende scope); het werkoverleg heeft geen
    # eigen "In de room"-kolom meer. Twee kolommen: links de stap-navigatie, rechts de inhoud.
    detail = (f"{header}<div class='wo-grid'><div class='wo-left'>{left}</div>"
              f"<div class='wo-mid'>{content}{step_action}</div></div>")
    if fragment:
        return detail
    return _page("Tactical meeting", f"{_DS_LINK}<div class='c2-wrap'>"
                 f"<div class='c2-main' style='max-width:1160px'>{detail}</div></div>")
