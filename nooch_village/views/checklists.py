"""Checklist-views — brok 5 van de cockpit2-split."""
from __future__ import annotations

from nooch_village.projects import PREP_CHECKLIST_TITLE

import urllib.parse
from typing import TYPE_CHECKING

from nooch_village.web_base import _e
from nooch_village.cockpit2_util import _name, _IC_CHECK
from nooch_village import org
from nooch_village.checklists import ChecklistStore, CADENCES, CADENCE_LABEL

if TYPE_CHECKING:
    from nooch_village.cockpit2 import _Stores


# DEFAULT-TITELS ZIJN GEEN NAMEN. Op productie heet 234 van de ~265 checklists "Uitvoerplan" —
# de naam die de wizard en de puls zetten, niet iets wat iemand bedacht. Die op elke kaart tonen is
# ruis met de vorm van informatie: je leest een kop die op 90% van de kaarten hetzelfde zegt.
#
# `Uitvoerplan` BLIJFT de identifier: hij gate't de Done-uitkomst, het aanbod-mechanisme, de wizard
# en de puls (`projects.PREP_CHECKLIST_TITLE`). Alleen de WEERGAVE vervalt — identifier is
# mechaniek, label is content, dezelfde scheiding als bij de verslag-voorzet.
_DEFAULT_TITELS = {PREP_CHECKLIST_TITLE.casefold(), "tasks", "checklist"}


def toon_titel(titel: str) -> str:
    """De titel zoals hij op het scherm hoort, of "" als het een default is.

    Alleen een titel die iemand ECHT zelf gaf verdient ruimte. Leeg → "", want een lege naam is
    ook geen naam."""
    t = (titel or "").strip()
    return "" if t.casefold() in _DEFAULT_TITELS else t


def _cl_target_label(st: _Stores, item: dict) -> str:
    if item.get("target_type") == "role" and item.get("target_id"):
        r = st.records.get(item["target_id"])
        return _name(r) if r else item["target_id"]
    return "All members"


def _cl_spark(item: dict) -> str:
    h = ChecklistStore.history(item, 6)
    if not h:
        return "<span class='cl-spark muted' title='no history yet'>—</span>"
    dots = "".join(f"<i class='{'ok' if b else 'no'}'>{'✓' if b else '✗'}</i>" for b in h)
    return f"<span class='cl-spark' title='last {len(h)} times'>{dots}</span>"


def _cl_row(st: _Stores, item: dict, csrf: str) -> str:
    cid = item["id"]
    status = ChecklistStore.current_status(item)
    tgt = f"<span class='chip muted'>{_e(_cl_target_label(st, item))}</span>"
    # rapporteer ✓/✗ voor de huidige periode (U5: numerieke waarde niet meer in de UI)
    if csrf:
        rep = (f"<form method='post' action='/action' class='cl-rep'>"
               f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
               f"<input type='hidden' name='cid' value='{_e(cid)}'>"
               f"<input type='hidden' name='action' value='cl_report'>"
               f"<input type='hidden' name='next' value='/node?id={_e(item['node'])}&tab=checklists'>"
               f"<button class='cl-check ok{(' on' if status is True else '')}' type='submit' name='ok' value='1' title='check'>✓</button>"
               f"<button class='cl-check no{(' on' if status is False else '')}' type='submit' name='ok' value='0' title='no check'>✗</button></form>")
        rm = (f"<form method='post' action='/action' style='display:inline'>"
              f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
              f"<input type='hidden' name='cid' value='{_e(cid)}'>"
              f"<input type='hidden' name='next' value='/node?id={_e(item['node'])}&tab=checklists'>"
              f"<button class='dellink' type='submit' name='action' value='cl_remove' title='remove'>✕</button></form>")
    else:
        rep = "" if status is None else (f"<span class='cl-check {'ok' if status else 'no'} on'>"
                                         f"{'✓' if status else '✗'}</span>")
        rm = ""
    danger = f"<span class='row-danger'>{rm}</span>" if rm else ""
    # Kleurcodering op rij-niveau, wederzijds uitsluitend: gemist=coral, te-doen=geel, gedaan=neutraal.
    # status is False (gemist) impliceert een rapport deze periode -> nooit tegelijk is_due (te-doen).
    if status is False:
        rowcls = " cl-attn"
    elif ChecklistStore.is_due(item):
        rowcls = " cl-todo"
    else:
        rowcls = ""
    return (f"<div class='cl-row{rowcls}'><div class='cl-main'><span class='cl-desc'>{_e(item['description'])}</span> {tgt}</div>"
            f"<div class='cl-act'>{_cl_spark(item)}<span class='cl-checks'>{rep}</span>{danger}</div></div>")


def _checklists_tab_html(st: _Stores, rec, csrf: str = "", flt: str = "due", nav: str = "") -> str:
    # flt blijft in de signatuur voor caller-compat (render_node + werkoverleg geven 'm nog door),
    # maar filtert niet meer: sinds U4 tonen we altijd de hele checklist en highlighten we de
    # te-doen items met .cl-todo. (clf-threading opruimen kan later, apart.)
    is_c = org.is_circle(rec)
    items = st.checklists.for_node(rec.id)
    base = f"/node?id={_e(rec.id)}&tab=checklists"

    shown = items   # geen filter meer: altijd de hele checklist; kleurcodering per rij (cl-todo/cl-attn)

    # groepering per cadans
    groups = ""
    for cad in CADENCES:
        sub = [i for i in shown if i.get("cadence") == cad]
        if not sub:
            continue
        groups += (f"<div class='cl-group'><h4>{_e(CADENCE_LABEL[cad])}</h4>"
                   + "".join(_cl_row(st, i, csrf) for i in sub) + "</div>")
    if not groups:
        groups = "<p class='muted'>No checklist items yet.</p>"

    # toevoegen (governance-poort: alleen een al bestaande terugkerende actie)
    add = ""
    if csrf:
        if is_c:
            roles = sorted(org.roles_of(st.records.all(), rec.id), key=lambda r: _name(r).lower())
            opts = "<option value='all'>All circle members</option>" + "".join(
                f"<option value='role:{_e(r.id)}'>{_e(_name(r))}</option>" for r in roles)
            doel = (f"<label class='att-lbl'>Target</label><select name='doel'>{opts}</select>")
        else:
            doel = "<input type='hidden' name='doel' value='all'>"
        cadopts = "".join(f"<option value='{c}'>{_e(CADENCE_LABEL[c])}</option>" for c in CADENCES)
        add = (f"<details class='cl-add'><summary class='btn ok sm'>+ Checklist item</summary>"
               f"<form method='post' action='/action' class='cl-addform'>"
               f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
               f"<input type='hidden' name='node' value='{_e(rec.id)}'>"
               f"<input type='hidden' name='next' value='{base}'>"
               f"<label class='att-lbl'>Description</label>"
               f"<input name='description' placeholder='E.g. Invoices sent' autocomplete='off'>"
               f"<label class='att-lbl'>Cadence</label><select name='cadence'>{cadopts}</select>"
               f"{doel}"
               f"<label class='cl-gate'><input type='checkbox' name='bestaand' value='1'> "
               f"This is an <b>existing</b> recurring action (not a new expectation).</label>"
               f"<button class='btn ok sm' type='submit' name='action' value='cl_add'>Add</button>"
               f"</form></details>")

    head = (f"<div class='cl-head'><h3>Checklists</h3>{add}</div>"
            f"<p class='muted' style='font-size:.8rem'>Transparency about recurring work (pre-flight): "
            f"✓ or ✗ per period. New expectations go through the governance meeting.</p>")
    return f"<div class='c2-sec'>{head}</div>{groups}"


def _cl_item_state(it: dict, done, skill) -> tuple[str, str]:
    """Bepaal de weergave-state van een checklist-item + de extra box-klasse.

    Vier onderscheidbare states (scope 1):
      done     ✓  afgevinkt
      exec     ·  uitvoerbaar (skill + payload in orde, nog niet gedraaid)
      warn     ⚠  payload onvolledig (payload_ok=False) — de checklist deugt niet
      noskill  ○  geen skill (skill=None) — er is (nog) geen software voor
      human    🙋 expliciete mens-taak (planner zag vooraf: fysiek/offline) — telt niet mee
      skipped  ⤳  bewust overgeslagen door de mens — telt niet mee

    Fail-soft (afgesproken): een ONTBREKEND payload_ok = 'niet gevalideerd' = gewoon uitvoerbaar (·),
    NIET ongeldig. Alleen expliciet payload_ok is False → ⚠. Zo staat een oud item (geprepareerd vóór
    PR #136, zonder het veld) niet ten onrechte als onvolledig gemarkeerd — consistent met hoe het
    primitief fail-soft is op skills zonder required_payload."""
    if it.get("skipped"):                        # bewust overgeslagen: telt niet meer mee (n.v.t./elders)
        return "skipped", " b-skip"
    if done:
        return "done", ""
    if it.get("human_task"):                     # planner zag vooraf: alleen een mens/externe partij
        return "human", " b-human"
    if not skill:
        return "noskill", " b-noskill"
    if it.get("payload_ok") is False:            # expliciet False; None/afwezig telt NIET als ongeldig
        return "warn", " b-warn"
    return "exec", ""


def _gate_samenvatting(items) -> tuple[str, int]:
    """Wat gebeurt er als ik op 'go ahead' klik?

    Dat is de enige vraag die die knop stelt, en het antwoord stond alleen verspreid over de items,
    elk met een eigen klein labeltje: een dichte of gestippelde checkbox, een groene skill-chip, een
    gemarkeerde mens-taak-regel. Je moest vier items decoderen om te weten wat er ging draaien.

    Hier staat het één keer, in de vorm waarin je het nodig hebt: hoeveel de rol draait en met welke
    skills, en wat er voor jou overblijft. Geeft (html, aantal-uitvoerbaar) terug; dat tweede getal
    bepaalt of de knop überhaupt iets belooft."""
    from collections import Counter
    telling: Counter = Counter()
    skills: list[str] = []
    for it in items:
        if it.get("done"):
            continue
        state, _ = _cl_item_state(it, False, it.get("skill"))
        telling[state] += 1
        if state == "exec" and it.get("skill"):
            skills.append(it["skill"])

    delen = []
    if telling["exec"]:
        chips = " ".join(f"<span class='ck-skill'>{_e(s)}</span>"
                         for s in dict.fromkeys(skills))         # dedup, volgorde behouden
        delen.append(f"<b>the role runs {telling['exec']}</b> {chips}")
    if telling["human"]:
        delen.append(f"{telling['human']} for you (hands-on)")
    if telling["noskill"]:
        delen.append(f"{telling['noskill']} nobody can run yet")
    if telling["warn"]:
        delen.append(f"{telling['warn']} incomplete, stays open")
    if not delen:
        return "<span class='muted'>nothing here for the role to run</span>", 0
    return " · ".join(delen), telling["exec"]


def _cl_fmt_payload(it: dict) -> str:
    """Compacte payload-weergave (zoals in het prototype: {sleutel: waarde}). Valt terug op query."""
    payload = it.get("payload")
    if isinstance(payload, dict) and payload:
        inner = ", ".join(f"{k}: {v}" for k, v in list(payload.items())[:4])
        return "{" + inner[:80] + "}"
    q = (it.get("query") or "").strip()
    return "{" + q[:60] + "}" if q else ""


def _cl_item_meta(state: str, skill, it: dict) -> str:
    """De meta-regel onder een checklist-item: skill-naam + payload, en per state het ⚠/○-signaal.
    ⚠ (coral) en ○ (grijs) verschillen bewust visueel — ze vragen om verschillende actie."""
    if state == "done":
        return ""                                # afgerond → geen ruis; het resultaat staat in de wall
    if state == "skipped":
        why = (it.get("skip_reason") or "").strip()
        return (f"<span class='ck-meta'><span class='ck-skip'>⤳ skipped — does not count"
                f"{' · ' + _e(why) if why else ''}</span></span>")
    if state == "human":
        why = (it.get("reason") or "").strip()
        return (f"<span class='ck-meta'><span class='ck-human'>🙋 human task — does not count towards "
                f"done{' · ' + _e(why) if why else ''}</span></span>")
    reason = (it.get("reason") or "").strip()
    parts = []
    if skill:
        parts.append(f"<span class='ck-skill'>{_e(str(skill))}</span>")
        pl = _cl_fmt_payload(it)
        if pl:
            parts.append(f"<span class='ck-payload'>{_e(pl)}</span>")
    if state == "warn":
        parts.append(f"<span class='ck-warn'>⚠ payload incomplete{': ' + _e(reason) if reason else ''}</span>")
    elif state == "noskill":
        parts.append(f"<span class='ck-noskill'>○ no skill{' · ' + _e(reason) if reason else ' · needs a human'}</span>")
    return f"<span class='ck-meta'>{' '.join(parts)}</span>" if parts else ""


def _cl_resolve_row(it: dict, hid: str, clitem: str, role_opts: str) -> str:
    """De drie mens-uitkomsten op een item dat alleen een mens kan oplossen (geen skill, of een
    onvolledige payload). Zonder deze knoppen sluit de mens wel de spanning maar blijft het item open
    en het project geparkeerd — de herhaal-lus. 'Gedaan' zit al op het ✓-vakje ernaast (dat loopt via
    dezelfde resolutie-route), hier staan 'overslaan' en 'overdragen'."""
    # 'skip (n/a)' IS WEG. Hij stond naast het ✓-vakje en deed vrijwel hetzelfde: een item dat
    # niet meer hoeft, vink je af of haal je weg. Twee knoppen voor één gedachte maakt de keuze
    # zwaarder dan de handeling. De `skipped`-STAAT blijft bestaan (oude items dragen hem nog en
    # `checklist_progress` telt hem correct niet mee); alleen de knop om hem te zetten is weg.
    # ÉÉN VELD, GEEN PROJECTFORMULIER. Hier stonden een rol-dropdown en een 'done when…' naast
    # elkaar, en die bouwden een heel project op het bord van de ontvanger. Twee dingen mis: het
    # vroeg om een projectdoel terwijl de bedoeling "@iemand, kijk jij hier even naar" is, en de drie
    # velden naast de itemtekst persten die tekst op het scherm samen tot één woord per regel.
    #
    # Nu: één `@`-veld met dezelfde doelenlijst als de inbox (rollen én personen), en de server
    # routeert het langs `route_werk`. `ck-doorgeef` is een modifier binnen de bestaande `ck-`-familie,
    # geen nieuw prefix — zie de klasse-ratchet.
    # HET UITKLAP-BLOK IS DE `ck-resolve` ZELF, en niet iets in een span eromheen. Alleen zo kan de
    # CSS op `[open]` zien dat het paneel openstaat en het over de volle breedte ONDER de tekst
    # zetten. Stond het in een wikkel, dan had je `:has()` nodig om vanaf de ouder naar het kind te
    # kijken, en dat is een omweg om een structuurfout heen.
    hand = (f"<details class='fedit ck-resolve'><summary class='flink'>📤 hand off</summary>"
            f"<form method='post' action='/action' class='ck-doorgeef'>{hid}{clitem}"
            # `@` STAAT IN DE OPTIEWAARDEN, niet alleen in de placeholder. Een datalist filtert op de
            # waarde: stonden daar kale namen, dan matcht de eerste `@` die je typt niets en lijkt
            # het veld stuk. De server strippen we hem er weer af (`lstrip("@")`), dus dit is puur
            # de kant die de mens ziet — en het is dezelfde vorm als het `@`-veld in de inbox.
            f"<input name='naar' list='ck-doelen' autocomplete='off' "
            f"placeholder='type @ to pick a role or person'>"
            f"<datalist id='ck-doelen'>{role_opts}</datalist>"
            f"<button class='btn sm' type='submit' name='action' value='check_handoff'>"
            f"hand off</button></form></details>") if role_opts else ""
    return hand


#: De lege checklist. "no items yet" CONSTATEERT; dit NODIGT UIT — en zegt erbij waar een eerste
#: item vandaan komt, want dat is de vraag waar iemand op vastloopt. Eigen klasse binnen de bestaande
#: .cl--familie: de andere lege staten in het systeem zijn losse <span class='muted'>-zinnen, en die
#: dragen geen ruimte of toon.
_CL_LEEG = ("<li class='cl-empty'>No actions yet. Put the first step from the meeting "
            "here — or split the end document into what still needs doing.</li>")


#: Slepen om te herordenen. Zelfde idioom als de statements-lijst in de kennisbank en het
#: projectbord: een ⠿-greep die `draggable` is, gedelegeerde listeners, en een formulier dat pas bij
#: de drop gebouwd wordt. Bewust géén optimistische verplaatsing in de DOM: zou de POST geweigerd
#: worden (rol-poort, verlopen csrf), dan staat het item op het scherm ergens waar het in de data
#: niet staat. Dezelfde blinde vlek die `ibxPost` had.
#:
#: DE RICHTING BEPAALT HET ANKER, en dat is het enige stukje rekenwerk hier. Sleep je omhoog, dan
#: kom je vóór het item waar je loslaat. Sleep je omlaag, dan verwacht je ONDER dat item te landen —
#: het anker is dan zijn buurman. Zonder dat onderscheid komt elk item bij omlaag slepen één plek te
#: hoog terecht, en dat voelt als een bug in plaats van als een regel.
#: `json.dumps` en niet `_e` voor csrf en next: dit is een SCRIPT-context, geen HTML-context.
#: HTML-escapen maakt van `&back=` een `&amp;back=`, en dan post de sleep naar een URL die niet
#: bestaat. Zelfde keuze als in `projects.py`, om dezelfde reden.
def _ck_sleep_js(csrf: str, nxt: str) -> str:
    import json
    return _CK_SLEEP_JS_ROMP.replace("__VARS__",
                                     f"var csrf={json.dumps(csrf)},nxt={json.dumps(nxt)},bron=null;")


_CK_SLEEP_JS_ROMP = (
    "<script>(function(){"
    "__VARS__"
    "function li(e){return e.target&&e.target.closest?e.target.closest('.ck-item'):null;}"
    "document.addEventListener('dragstart',function(e){"
    "if(!e.target||!e.target.classList||!e.target.classList.contains('ck-greep'))return;"
    "bron=e.target.closest('.ck-item');if(!bron)return;"
    "bron.classList.add('sleept');e.dataTransfer.effectAllowed='move';"
    "try{e.dataTransfer.setData('text/plain',bron.getAttribute('data-item')||'');}catch(_){}"
    "});"
    "document.addEventListener('dragend',function(){bron=null;"
    "document.querySelectorAll('.ck-item.sleept,.ck-item.erover').forEach(function(x){"
    "x.classList.remove('sleept','erover');});});"
    "document.addEventListener('dragover',function(e){var d=li(e);"
    "if(!d||!bron||d===bron)return;"
    "if(d.getAttribute('data-clid')!==bron.getAttribute('data-clid'))return;"   # niet tussen lijsten
    "e.preventDefault();d.classList.add('erover');});"
    "document.addEventListener('dragleave',function(e){var d=li(e);if(d)d.classList.remove('erover');});"
    "document.addEventListener('drop',function(e){var d=li(e);"
    "if(!d||!bron||d===bron)return;"
    "if(d.getAttribute('data-clid')!==bron.getAttribute('data-clid'))return;"
    "e.preventDefault();d.classList.remove('erover');"
    "var rij=[].slice.call(d.parentNode.querySelectorAll('.ck-item'));"
    "var vanaf=rij.indexOf(bron),naar=rij.indexOf(d);if(vanaf<0||naar<0)return;"
    "var anker=d;"
    "if(vanaf<naar){anker=rij[naar+1]||null;}"                                  # omlaag → onder d
    "var f=document.createElement('form');f.method='post';f.action='/action';"
    "function a(n,v){var i=document.createElement('input');i.type='hidden';i.name=n;i.value=v;"
    "f.appendChild(i);}"
    "a('csrf',csrf);a('next',nxt);a('action','check_move');"
    "a('pid',bron.getAttribute('data-pid')||'');"
    "a('clid',bron.getAttribute('data-clid')||'');"
    "a('item',bron.getAttribute('data-item')||'');"
    "a('voor',anker?(anker.getAttribute('data-item')||''):'');"
    "document.body.appendChild(f);f.submit();});"
    "})();</script>")


def _checklists_html(p: dict, csrf: str, pid: str, back: str, rw: bool, st: _Stores = None) -> str:
    """Named checklists (Trello-stijl): titel + voortgangsbalk + items + verwijderen."""
    def hid():
        nxt = f"/project?pid={pid}&back=" + urllib.parse.quote(back, safe="")
        return (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
                f"<input type='hidden' name='pid' value='{_e(pid)}'>"
                f"<input type='hidden' name='next' value='{_e(nxt)}'>")

    from nooch_village.projects import checklist_progress, uitvoerlijst
    # Welke lijst werkt de rol af? Alleen relevant als er meer dan één is; bij één lijst valt er
    # niets te kiezen en zou de melding ruis zijn.
    _uit_id = (uitvoerlijst(p) or {}).get("id")
    _meerdere = len(p.get("checklists") or []) > 1
    # Doelen voor het doorgeven: ROLLEN ÉN PERSONEN, uit dezelfde bron die het `@`-veld in de inbox
    # voedt (reference, don't copy). Stond hier eerst op `_wall_outcome_opts`, dat alleen rollen geeft
    # — terwijl je een item meestal aan een PERSOON wilt geven.
    role_opts = ""
    if rw and st is not None:
        try:
            from nooch_village.views.inbox import _at_doelen
            role_opts = "".join(f"<option value='@{_e(d['label'])}'></option>"
                                for d in _at_doelen(st))
        except Exception:
            role_opts = ""
    out = ""
    for cl in (p.get("checklists") or []):
        items = cl.get("items", [])
        done, tot = checklist_progress(cl)          # overgeslagen items tellen niet mee in de noemer
        pct = round(100 * done / tot) if tot else 0
        bar = (f"<div class='ck-prog'><div class='pbar' style='flex:1'><div style='width:{pct}%'></div></div>"
               f"<span class='muted'>{pct}% ({done}/{tot})</span></div>") if tot else ""
        # Het uitvoerplan is een VOORSTEL tot een mens het goedkeurt (projects.plan_wacht_op_akkoord).
        # Deze knop is de enige weg naar akkoord; zonder hem staat de daemon stil en zie je niet waarom.
        poort = ""
        if cl.get("akkoord") is False:
            wat, n_exec = _gate_samenvatting(items)
            knop = (f"<form method='post' action='/action'>{hid()}"
                    f"<input type='hidden' name='clid' value='{_e(cl['id'])}'>"
                    f"<button class='btn ok sm' type='submit' name='action' value='plan_akkoord'>"
                    f"▶ go ahead</button></form>") if (rw and n_exec) else ""
            # Geen knop als er niets te draaien valt: dan is 'go ahead' een lege belofte, en de
            # samenvatting zegt al waarom. Weggooien of zelf afvinken is dan de weg.
            poort = (f"<div class='ck-gate'><span class='chip amber'>⏸ waiting for your go-ahead</span>"
                     f"{knop}<span class='ck-gate-wat'>{wat}</span></div>")
        elif cl.get("akkoord_door"):
            wat, n_exec = _gate_samenvatting(items)
            # DRIE TOESTANDEN, NIET TWEE. Tussen "goedgekeurd" en "klaar" zit een gat waarin de rol
            # bezig is, en dat was onzichtbaar: je klikte, de kaart herlaadde meteen, er stond nog
            # niets, en daarna bewoog het scherm niet meer. Je moest zelf raden wanneer je moest
            # verversen. Dat is geen nieuwe state om op te slaan — hij is af te leiden uit wat er
            # al staat: goedgekeurd, en er staan nog items open die een skill hebben.
            if n_exec:
                poort = (f"<div class='ck-gate' data-bezig='1'>"
                         f"<span class='chip amber'>⏳ the role is working — {n_exec} to go</span>"
                         f"<span class='ck-gate-wat'>{wat}</span></div>")
            else:
                poort = (f"<div class='ck-gate'><span class='chip muted'>▶ approved by "
                         f"{_e(cl['akkoord_door'])}</span><span class='ck-gate-wat'>{wat}</span></div>")
        rows = ""
        for it in items:
            d = it.get("done")
            skill = it.get("skill")
            state, box_extra = _cl_item_state(it, d, skill)
            clitem = (f"<input type='hidden' name='clid' value='{_e(cl['id'])}'>"
                      f"<input type='hidden' name='item' value='{_e(it['id'])}'>")
            chk = (f"<form method='post' action='/action'>{hid()}{clitem}"
                   f"<button class='ck-box{' on' if d else ''}{box_extra}' type='submit' name='action' "
                   f"value='check_toggle'>{'✓' if d else ''}</button></form>") if rw else ("☑" if d else "☐")
            rm = (f"<form method='post' action='/action'>{hid()}{clitem}"
                  f"<button class='dellink' type='submit' name='action' value='check_remove'>✕</button></form>") if rw else ""
            # ⠿ SLEEPGREEP, NIET DE HELE REGEL. Een `draggable` <li> vecht met tekstselectie en met
            # het ✓-vakje: elke poging om een woord te selecteren wordt een sleep. Een greep is
            # hetzelfde idioom als de statements-lijst in de kennisbank, dus geen nieuwe interactie
            # om te leren. Alleen zichtbaar bij hover, net als de ✕ ernaast.
            greep = (f"<span class='ck-greep' draggable='true' title='drag to reorder'>⠿</span>"
                     if rw else "")
            # BEWERKEN WAS ER NIET, alleen weggooien. Wie een tikfout wilde herstellen moest het item
            # verwijderen en opnieuw typen — en gooide daarmee de skill en payload weg die eraan
            # hingen. Zelfde `fedit`-uitklap als de hand-off, en dus ook onder de tekst.
            edit = (f"<details class='fedit ck-bewerk'><summary class='flink' title='edit text'>✎</summary>"
                    f"<form method='post' action='/action' class='ck-doorgeef'>{hid()}{clitem}"
                    f"<input name='text' value='{_e(it['text'])}' autocomplete='off' "
                    f"aria-label='item text'>"
                    f"<button class='btn sm' type='submit' name='action' value='check_rename'>"
                    f"save</button></form></details>") if rw else ""
            txt = (f"<span class='ck-txt'><span class='{'ck-done' if d else ''}'>{_e(it['text'])}</span>"
                   f"{_cl_item_meta(state, skill, it)}</span>")
            # Stil skill-aanbod (cockpit-match): alleen als het item nog geen skill heeft. Klik = accepteren
            # (skill+payload aan het item, uitvoering door de daemon); negeren = afwijzen.
            offer = it.get("offer") if not skill else None
            offer_html = (f"<form method='post' action='/action'>{hid()}{clitem}"
                          f"<button class='btn ghost sm' type='submit' name='action' value='check_accept' "
                          f"title='skill: {_e(str((offer or {}).get('skill','')))}'>🤖 can pick this up</button>"
                          f"</form>") if (rw and offer) else ""
            # Een item dat geen enkele skill kan draaien blijft anders eeuwig open en houdt het project
            # geparkeerd. Geef de mens hier de twee uitkomsten die dat doorbreken (✓ = de derde).
            resolve = (_cl_resolve_row(it, hid(), clitem, role_opts)
                       if (rw and state in ("noskill", "warn", "human")) else "")
            unskip = (f"<form method='post' action='/action' class='emo-f'>{hid()}{clitem}"
                      f"<button class='flink' type='submit' name='action' value='check_unskip'>"
                      f"undo skip</button></form>") if (rw and state == "skipped") else ""
            # `data-item`/`data-clid` dragen de sleep: de JS leest ze bij drop en post ze terug.
            # Ze staan op de <li> en niet op de greep, want de drop-doelen zijn de REGELS.
            rows += (f"<li class='ck-item' data-pid='{_e(pid)}' data-item='{_e(it['id'])}' "
                     f"data-clid='{_e(cl['id'])}'>"
                     f"{greep}{chk}{txt}{offer_html}{edit}{resolve}{unskip}{rm}</li>")
        add = (f"<form method='post' action='/action' class='ckadd'>{hid()}"
               f"<input type='hidden' name='clid' value='{_e(cl['id'])}'>"
               # EEN PLACEHOLDER IS EEN UITNODIGING OF EEN GRIJS VLAK. "add item…" beschrijft het
               # veld; een voorbeeld laat zien wat er in hoort en hoe fijn een item mag zijn.
               f"<input name='text' placeholder='E.g. Ask three suppliers for a sample'>"
               f"<button class='btn ok' type='submit' name='action' value='check_add'>+ item</button></form>") if rw else ""
        delc = (f"<form method='post' action='/action' style='display:inline'>{hid()}"
                f"<input type='hidden' name='clid' value='{_e(cl['id'])}'>"
                f"<button class='dellink cl-del' type='submit' name='action' value='checklist_remove' "
                f"onclick=\"return confirm('Remove checklist?')\">remove</button></form>") if rw else ""
        # De stille valkuil zichtbaar maken: een lijst met skill-items die de rol NIET afwerkt.
        # Zonder deze regel accepteer je een aanbod en gebeurt er nooit iets, zonder enig spoor.
        rol_lijst = ""
        if _meerdere:
            if cl["id"] == _uit_id:
                rol_lijst = ("<div class='ck-gate'><span class='chip muted'>"
                             "▶ the role works this list</span></div>")
            elif any(it.get("skill") for it in items):
                knop = (f"<form method='post' action='/action'>{hid()}"
                        f"<input type='hidden' name='clid' value='{_e(cl['id'])}'>"
                        f"<button class='btn sm' type='submit' name='action' value='checklist_uitvoer'>"
                        f"make this the role's list</button></form>") if rw else ""
                rol_lijst = (f"<div class='ck-gate'><span class='chip amber'>"
                             f"⏸ the role doesn't work this list</span>"
                             f"<span class='muted'>items with a skill sit here unused</span>{knop}</div>")
        _titel = toon_titel(cl.get("title", ""))
        out += (f"<div class='checklist'><div class='cl-head'>{_IC_CHECK}"
                + (f"<span class='cl-title'>{_e(_titel)}</span>" if _titel else "")
                + f"{delc}</div>"
                f"{rol_lijst}{poort}{bar}<ul class='clean ck-list'>{rows or _CL_LEEG}</ul>{add}</div>")
    if rw and out:
        out += _ck_sleep_js(csrf, f"/project?pid={pid}&back=" + urllib.parse.quote(back, safe=""))
    return out
