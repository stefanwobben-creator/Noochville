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


def _agenda_substeps(st, crec, open_iid: str = "") -> str:
    """De gevangen punten als steekwoorden, genest onder de Agenda-stap in het linkermenu.

    Deze lijst verdween bij #355 toen de agenda-stap de GlassFrog-triage kreeg, en is nooit
    teruggekomen: een punt dat je boven typte kwam nergens in het menu te staan. Zonder deze
    lijst zie je alleen een teller, en een getal vertelt niet WÁT er op de agenda staat.

    Geen microcopy, geen knoppen — dit is een inhoudsopgave. Weghalen en verwerken doe je op de
    stap zelf. De klassen (`wo-substeps`, `rov-item`, `rov-title`) stonden nog in het
    designsysteem; alleen de markup was weg."""
    from nooch_village.views.vangst import _open_nxt

    base = f"/werkoverleg?circle={crec.id}&step=agenda"
    rijen = ""
    for it in st.werk.punten(crec.id):
        klaar = it.get("status") == "done"
        aan = " on" if it.get("id") == open_iid else ""
        url = _open_nxt(base, str(it.get("id") or ""))
        rijen += (f"<div class='rov-item{aan}{' done' if klaar else ''}'>"
                  f"<a class='js-modal rov-link' href='{url}' data-href='{url}'>"
                  f"<span class='rov-title'>{_e(it.get('title') or '')}</span></a></div>")
    return f"<div class='wo-substeps'>{rijen}</div>" if rijen else ""


def _wo_vangbar(st, crec, csrf: str, step: str) -> str:
    """De vangbalk — op ELKE stap, niet alleen op de agenda-stap.

    Wie tijdens de check-in of bij de projecten iets hoort, moet het daar kunnen opschrijven.
    Stond het veld alleen op stap 5, dan was de handeling in de praktijk "onthouden tot stap 5",
    en dat is precies wat vangen moet vervangen. Vangen is een regel typen; behandelen is een
    andere handeling, en die blijft onder de agenda-stap hangen.

    De teller is de terugkoppeling op de andere zes stappen: daar staat de lijst niet, dus moet
    het getal laten zien dat het punt geland is.

    Hij hoort in de LINKERKOLOM, boven het stappenmenu — zoals GlassFrog "Item aan agenda
    toevoegen" bovenaan de linkerbalk zet. Stond hij bovenaan het rechter inhoudsvlak, dan duwde
    hij op elke stap de eigenlijke stap-inhoud omlaag: een veld dat je zelden gebruikt kreeg de
    plek van het scherm waar je wél naar kijkt."""
    from nooch_village.views.vangst import _vang_form


    punten = st.werk.punten(crec.id)
    open_n = sum(1 for p in punten if p.get("status") != "done")
    onderw = f"{len(punten)} onderwerp" + ("" if len(punten) == 1 else "en")
    nxt = f"/werkoverleg?circle={crec.id}&step={step}"
    vang = _vang_form(crec.id, csrf, nxt, sub="wo") if csrf else ""
    # Teller + veld, verder niets. In de smalle linkerkolom duwt elke uitleg-zin het veld omlaag,
    # en de placeholder zegt het al ("punt in één regel — Enter"). De uitleg over `verwerken` hoort
    # bij de lijst, en die staat op de agenda-stap.
    #
    # De tellers worden na een vangst bijgewerkt door de gedeelde mechaniek: het lijst-fragment
    # draagt ze mee als `data-nv-mirror`-bron, dus ze kloppen ook op de zes stappen waar de lijst
    # zelf niet op het scherm staat.
    return (f"<div class='c2-sec'><h3>Punten behandelen <span class='muted'>("
            f"<span id='vang-tot'>{onderw}</span>, "
            f"<span id='vang-n'>{open_n}</span> te doen)</span></h3>{vang}</div>")


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
    return (f"<div class='c2-sec'><p class='muted'>Klik <em>verwerken</em> onder een punt om er "
            f"uitkomsten onder te leggen; er mogen er meerdere zijn, elk naar een andere rol.</p>"
            f"</div><div class='rdr-tool' id='vang-lijst'>{lijst}</div>")


def _wo_checkout(st: _Stores, crec, csrf: str) -> str:
    """Stap 6: check-out. Ja of nee per deelnemer — dezelfde vorm als de check-in.

    Hier stond een schaal van 0 tot 10 met een gemiddelde erboven. Een cijfer geven over een
    overleg is een oordeel dat niemand kan onderbouwen, en het gemiddelde poetste het verschil
    tussen vier tevreden mensen en één die niets kreeg netjes weg. De vraag die ertoe doet is of
    je hebt gekregen wat je nodig had, en dat is ja of nee.

    De ghost van het vorige overleg toont alleen een ja/nee. Een oude score van 7 is geen "ja" —
    dat is een vertaling die niemand kan verantwoorden, en dus doen we hem niet."""
    ppl = _members_of_circle(st, crec.id)
    nxt = f"/werkoverleg?circle={crec.id}&step=checkout"
    antw = st.werk.checkout(crec.id)
    if not ppl:
        return "<div class='c2-sec'><h3>Check-out</h3><p class='muted'>No members.</p></div>"
    prev = st.werk.prev_checkout(crec.id)               # vorige overleg (ghost)
    ja = sum(1 for p in ppl if antw.get(p.id) is True)
    nee = sum(1 for p in ppl if antw.get(p.id) is False)
    rows = ""
    oud_gezien = False
    for p in ppl:
        cur = antw.get(p.id)
        pv = prev.get(p.id)
        pv = pv if isinstance(pv, bool) else None       # oude cijfers vertalen we niet
        if not isinstance(cur, bool) and cur is not None:
            oud_gezien = True                           # een cijfer uit een eerder overleg-record
        if csrf:
            def b(val, lbl, c, _cur=cur, _pv=pv, _p=p):
                on = " on" if _cur is val else (" prev" if _cur is None and _pv is val else "")
                title = " title='last time'" if (_pv is val and _cur is not val) else f" title='{lbl}'"
                return (f"<form method='post' action='/action' style='display:inline'>"
                        f"{_wo_hid(csrf, crec.id, nxt)}"
                        f"<input type='hidden' name='pid' value='{_e(_p.id)}'>"
                        f"<input type='hidden' name='ok' value='{'1' if val else '0'}'>"
                        f"<button class='cl-check {c}{on}'{title} type='submit' name='action' "
                        f"value='wo_checkout'>{'✓' if val else '✗'}</button></form>")
            ctrl = b(True, "yes", "ok") + b(False, "no", "no")
        else:
            merk = "—" if not isinstance(cur, bool) else ("✓" if cur else "✗")
            ctrl = f"<span class='kpidata-v'>{merk}</span>"
        rows += (f"<div class='wo-mem'><span class='av'>{_e(_initials(p.name))}</span>"
                 f"<span class='wo-mem-n'>{_e(p.name)}</span>"
                 f"<span class='cl-checks'>{ctrl}</span></div>")
    # De legenda alleen als er ook echt een ghost te zien is. Een vorig overleg met alleen oude
    # cijfers levert er geen — die vertalen we niet — en dan is "lighter = last time" een uitleg
    # bij iets wat niet op het scherm staat.
    ghost = any(isinstance(v, bool) for v in prev.values())
    legend = "<span class='muted'>lighter = last time</span>" if ghost else ""
    oud = ("<p class='muted'>An earlier score from this circle is kept as written — old 0-10 "
           "scores are not converted.</p>" if oud_gezien else "")
    return (f"<div class='c2-sec'><div class='cl-head'><h3>Check-out</h3>"
            f"<span class='muted'>{ja} yes · {nee} no</span></div>"
            f"<p class='muted'>Did this meeting give you what you needed? "
            f"<b>✓</b> yes / <b>✗</b> no. {legend}</p>{oud}"
            f"<div class='wo-mems' tabindex='0'>{rows}</div></div>")


def _wo_summary(st: _Stores, crec, csrf: str) -> str:
    """Stap 7: samenvatting + sluiten (confetti via wo_close)."""
    s = st.werk.summary(crec.id)
    pres = st.werk.presence(crec.id)
    ppl = _members_of_circle(st, crec.id)
    aanwezig = [p.name for p in ppl if pres.get(p.id, True)]
    afwezig = [p.name for p in ppl if pres.get(p.id) is False]
    # De check-out is ja/nee. `tevredenheid` bestaat alleen nog voor archieven van vóór die
    # wijziging; is hij er, dan tonen we hem erbij in plaats van hem stilzwijgend te laten vallen.
    uit = f"{s.get('checkout_ja', 0)} yes · {s.get('checkout_nee', 0)} no"
    rij = lambda k, v: f"<div class='wo-sumrow'><span>{k}</span><b>{v}</b></div>"
    body = (rij("Present", ", ".join(aanwezig) or "—")
            + rij("Absent", ", ".join(afwezig) or "—")
            + rij("Items handled", s["behandeld"])
            # Alleen tonen als een OUD overleg hem draagt: 'info' is als keuze verdwenen, en een
            # regel die eeuwig 0 toont is ruis. De historie houdt wél zijn getal.
            + (rij("Information processed", s["info"]) if s.get("info") else "")
            + rij("Projects added", s["projecten"])
            + rij("Actions", s.get("acties", 0))
            + rij("Items for governance meeting", s["roloverleg"])
            + rij("Check-out", uit)
            + (rij("Average satisfaction (old scale)", f"{s['tevredenheid']}/10")
               if s.get("tevredenheid") is not None else "")
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
        if k == "agenda":
            # De punten genest onder de Agenda-stap. Het `id` is het doelwit van de gedeelde
            # mechaniek: het lijst-fragment draagt deze markup mee, dus na een vangst ververst
            # hij zonder herladen — net als de teller.
            nav += (f"<div id='wo-agenda-sub'>"
                    f"{_agenda_substeps(st, crec, iid)}</div>")
    # Het vangveld en de puntenlijst stonden hier als tweede kopie in de linkerkolom. Ze wonen nu
    # in de Agenda-stap zelf, want dat is waar je ze gebruikt — en het is één component.
    # Vangen staat BOVEN het stappenmenu: het hoort bij het overleg, niet bij een stap. Eén
    # instantie, dus hij verhuist niet mee en het veld wordt bij het wisselen van stap niet
    # opnieuw opgebouwd.
    left = (_wo_vangbar(st, crec, csrf_token, cur)
            + _psec(_IC_CHECK, "Meeting", f"<div class='wo-nav'>{nav}</div>"))

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
