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
# `Uitvoerplan` BLIJFT de identifier: hij gate't de Done-uitkomst, de wizard
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
        rm = (f"<form method='post' action='/action' class='fentry-inline'>"
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
    # DE RIJSTATUS DRAAGT DRIE DINGEN, niet één. De tint was er al; de rand-stijl (solide/
    # gestippeld, zie nooch.css) overleeft zwart-wit, en het woord hieronder bereikt een
    # schermlezer — die ziet noch de tint noch de rand. Zelfde redenering als de
    # ongelezen-indicator in Messages, die bewust op gewicht, telling én tint tegelijk leunt.
    if status is False:
        rowcls, woord = " cl-attn", "Missed"
    elif ChecklistStore.is_due(item):
        rowcls, woord = " cl-todo", "Due"
    else:
        rowcls, woord = "", ""
    merk = f"<span class='sr'>{woord}: </span>" if woord else ""
    return (f"<div class='cl-row{rowcls}'><div class='cl-main'>{merk}"
            f"<span class='cl-desc'>{_e(item['description'])}</span> {tgt}</div>"
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


def _cl_item_state(it: dict, done) -> tuple[str, str]:
    """Bepaal de weergave-state van een checklist-item + de extra box-klasse.

      done     ✓  afgevinkt
      open        nog te doen
      human    🙋 expliciete mens-taak (oud planner-veld) — telt niet mee
      skipped  ⤳  bewust overgeslagen door de mens — telt niet mee

    DE AI-STATES ZIJN WEG (15 oktober 2026, besluit Stefan). `exec`, `warn` en `noskill` bestonden
    voor de uitvoerder die sinds #516 (19-20 september) niet meer bestaat: ze beloofden werk dat niets
    meer deed. De `skill`- en `payload`-velden op oude items blijven in de opslag staan; ze worden
    alleen niet meer getoond. `human` en `skipped` blijven, want `checklist_progress` telt ze nog
    steeds niet mee en dat moet op het scherm te zien zijn."""
    if it.get("skipped"):                        # bewust overgeslagen: telt niet meer mee (n.v.t./elders)
        return "skipped", " b-skip"
    if done:
        return "done", ""
    if it.get("human_task"):                     # oud planner-veld: telt niet mee in de voortgang
        return "human", " b-human"
    return "open", ""


def _cl_item_meta(state: str, it: dict) -> str:
    """De meta-regel onder een checklist-item, alleen waar hij iets zegt over de TELLING: een
    overgeslagen item en een mens-taak tellen niet mee. Verder is een item een tekstregel met vinkje
    (geen skill, payload, "no skill · needs a human" of "ran, but returned nothing" meer)."""
    if state == "skipped":
        why = (it.get("skip_reason") or "").strip()
        return (f"<span class='ck-meta'><span class='ck-skip'>⤳ skipped — does not count"
                f"{' · ' + _e(why) if why else ''}</span></span>")
    if state == "human":
        why = (it.get("reason") or "").strip()
        return (f"<span class='ck-meta'><span class='ck-human'>🙋 human task — does not count towards "
                f"done{' · ' + _e(why) if why else ''}</span></span>")
    return ""


#: De lege checklist. "no items yet" CONSTATEERT; dit NODIGT UIT — en zegt erbij waar een eerste
#: item vandaan komt, want dat is de vraag waar iemand op vastloopt. Eigen klasse binnen de bestaande
#: .cl--familie: de andere lege staten in het systeem zijn losse <span class='muted'>-zinnen, en die
#: dragen geen ruimte of toon.
_CL_LEEG = ("<li class='cl-empty'>No actions yet. Put the first step from the meeting "
            "here.</li>")


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
    return _CK_SLEEP_JS_ROMP.replace(
        "__VARS__",
        f"var csrf={json.dumps(csrf)},nxt={json.dumps(nxt)},bron=null;")


# DE STAND MEETEEN ZIEN staat in `static/nooch.js` en niet meer hier. Dit was een `<script>` in
# dit fragment, en dat werkt op een volle pagina — maar de projectkaart opent normaal in de MODAL,
# en die zet zijn inhoud met `innerHTML`. Een script dat zo binnenkomt voert de browser nooit uit,
# dus de microinteractie was onzichtbaar op precies de plek waar je hem het vaakst ziet, zonder dat
# er iets faalde. Gevonden bij de handmatige doorloop tegen het prototype (20 september 2026).
#
# De haken blijven hier: `data-ck-item` op het vakje, `data-ck-bar`/`data-ck-tot` op de balk en
# `data-ck-tel` op de teller. Eén gedelegeerde listener in het gedeelde bestand leest ze.


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
    # ── Ter plekke afhandelen in plaats van de hele pagina herladen ─────────────────────────────
    #
    # WAAROM. Elk vinkje, elk skill-aanbod en elke bewerking gooide de hele pagina weg en bouwde hem
    # opnieuw op. Functioneel prima, maar het voelt als stilstand: je klikt, het scherm knippert, en
    # je zoekt opnieuw waar je was. Een lijst afwerken is de handeling die je het vaakst doet, dus
    # daar telt dat het zwaarst.
    #
    # DRIE REGELS DIE IK NIET OMDRAAI, en ze staan alle drie al in dit huis:
    #
    # 1. `r.ok` MEET HET TRANSPORT, NIET DE UITKOMST. Een inhoudelijke weigering ("✗ …",
    #    "No access — …") reist als melding op een 303; fetch volgt die en de status is 200. De
    #    server markeert een weigering met `ok=0`; wij lezen díe. Exact de blinde vlek die in
    #    `ibxPost` staat uitgeschreven.
    # 2. NIETS OPTIMISTISCH BIJWERKEN. De rij blijft staan tot de server hem echt heeft veranderd;
    #    we halen de nieuwe stand op bij de server (`?fragment=1`, die route bestond al) in plaats
    #    van te gokken wat er zou moeten staan. Zelfde regel als `.ibx-row.gk.bezig`.
    # 3. BIJ TWIJFEL GEWOON HET FORMULIER. Gaat er iets mis — transport, weigering, of een pagina
    #    die er anders uitziet dan we verwachten — dan versturen we het originele formulier alsnog
    #    op de oude manier. De mens krijgt dan de melding die hij altijd al kreeg. Zonder JS werkt
    #    alles ook gewoon, want we hangen aan `submit` en niet aan `click`.
    "function ckWeigering(u){try{var q=new URL(u,location.origin).searchParams;"
    "return q.get('ok')==='0'?(q.get('msg')||'geweigerd'):'';}catch(e){return '';}}"
    # ── Samensmelten per ITEM, niet per lijst ───────────────────────────────────────────────────
    #
    # Eerst verving dit de hele lijst en kreeg elk item de fade. Voor één klik is dat te billijken;
    # voor een lijst die zichzelf afwerkt is het een knipperlicht. Alleen het item dat écht anders
    # is wordt vervangen, en alleen dát item beweegt. De rest staat stil, en juist daardoor zíe je
    # welk vinkje omvalt.
    "function ckBezet(el){"
    # Een item met de focus erin of een open uitklap-paneel is werk van de MENS. Dat onder zijn
    # handen vervangen wist wat hij aan het typen is, en dat is erger dan een verouderde regel.
    "return el.contains(document.activeElement)||!!el.querySelector('details[open]');}"
    "function ckFade(el){el.classList.add('ck-vers');setTimeout(function(){"
    "el.classList.remove('ck-vers');},450);}"
    "function ckSmelt(h){var d=new DOMParser().parseFromString(h,'text/html');"
    "var nw=d.querySelectorAll('.checklist'),ou=document.querySelectorAll('.checklist');"
    # Een andere vorm dan verwacht betekent dat de pagina iets anders is gaan doen. Dan niet half
    # bijwerken maar eerlijk herladen: een lijst die deels van gisteren is, is erger dan een knipper.
    "if(!nw.length||nw.length!==ou.length){location.reload();return -1;}"
    "var n=0;"
    "for(var i=0;i<ou.length;i++){"
    "var a=ou[i].querySelectorAll('.ck-item'),b=nw[i].querySelectorAll('.ck-item');"
    # Item erbij, eraf of versleept: dan is de VORM anders en zou per-item bijwerken het verkeerde
    # item raken. In dat geval de lijst in één keer.
    "if(a.length!==b.length){if(ou[i].innerHTML!==nw[i].innerHTML){"
    "ou[i].innerHTML=nw[i].innerHTML;ckFade(ou[i]);n++;}continue;}"
    "for(var j=0;j<a.length;j++){"
    "if(a[j].getAttribute('data-item')!==b[j].getAttribute('data-item')){"
    "ou[i].innerHTML=nw[i].innerHTML;ckFade(ou[i]);n++;break;}"
    "if(a[j].innerHTML===b[j].innerHTML||ckBezet(a[j]))continue;"
    "a[j].innerHTML=b[j].innerHTML;ckFade(a[j]);n++;}}"
    "return n;}"
    "function ckVervers(){return fetch(nxt+'&fragment=1',{cache:'no-store'})"
    ".then(function(r){if(!r.ok)throw new Error('ck '+r.status);return r.text();})"
    ".then(ckSmelt);}"
    "function ckPost(f){var fd=new FormData(f),b=new URLSearchParams();"
    "fd.forEach(function(v,k){b.append(k,v);});"
    "var knop=f.querySelector('[name=action]');if(knop)b.set('action',knop.value);"
    "return fetch('/action',{method:'POST',"
    "headers:{'Content-Type':'application/x-www-form-urlencoded'},body:b})"
    ".then(function(r){if(!r.ok)throw new Error('ck '+r.status);"
    "if(ckWeigering(r.url))throw new Error('ckgeweigerd');"
    "return ckVervers();});}"
    "document.addEventListener('submit',function(e){"
    "var f=e.target;if(!f||!f.closest||!f.closest('.ck-list'))return;"
    "var knop=f.querySelector('[name=action]');if(!knop)return;"
    # Alleen de handelingen die je vaak achter elkaar doet. Verwijderen en doorgeven blijven een
    # hele paginabeurt: dat zijn eindpunten, geen ritme, en daar is een duidelijke overgang beter
    # dan een vloeiende.
    "if(['check_toggle','check_rename'].indexOf(knop.value)<0)return;"
    "var rij=f.closest('.ck-item');e.preventDefault();"
    "if(rij)rij.classList.add('bezig');"
    "ckPost(f).catch(function(){"
    # Alles wat niet goed ging valt terug op de oude weg, zodat de mens de melding krijgt die de
    # server altijd al gaf. Stil falen zou hier het ergst zijn: dan lijkt je klik gelukt.
    "if(rij)rij.classList.remove('bezig');f.submit();});},true);"
    # HET MEEKIJKEN IS WEG (15 oktober 2026). Hier pollde de pagina zolang "een rol" de lijst
    # afwerkte. Die uitvoerder bestaat sinds #516 niet meer; er beweegt niets meer buiten deze browser.
    "})();</script>")


def _checklists_html(p: dict, csrf: str, pid: str, back: str, rw: bool, st: _Stores = None) -> str:
    """Named checklists (Trello-stijl): titel + voortgangsbalk + items + verwijderen."""
    def hid():
        nxt = f"/project?pid={pid}&back=" + urllib.parse.quote(back, safe="")
        return (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
                f"<input type='hidden' name='pid' value='{_e(pid)}'>"
                f"<input type='hidden' name='next' value='{_e(nxt)}'>")

    from nooch_village.projects import checklist_progress
    # GEEN AI-RESTANTEN MEER (15 oktober 2026, besluit Stefan). Hier stonden de akkoord-poort ("go
    # ahead", "the role is working — N to go"), de uitvoerlijst-keuze ("the role works this list"),
    # het skill-aanbod ("can pick this up") en de hand-off naar een rol. Allemaal voor de uitvoerder
    # die sinds #516 (19-20 september) niet meer bestaat. Een item is een tekstregel met een vinkje.
    #
    # EEN ITEM AAN EEN PERSOON GEVEN (15 oktober 2026, besluit Stefan): één optionele persoon per
    # item, gekozen in het ✎-formulier uit de gebruikers (wie een e-mail heeft). Een verwijderde
    # gebruiker valt stil terug naar niet-toegewezen (`project_items.toegewezen`).
    from nooch_village import project_items
    mensen = []
    if st is not None:
        try:
            mensen = sorted((m for m in st.people.all() if (m.email or "").strip()),
                            key=lambda m: (m.name or "").lower())
        except Exception:                                 # noqa: BLE001 — de lijst mag de kaart nooit breken
            mensen = []
    out = ""
    for cl in (p.get("checklists") or []):
        items = cl.get("items", [])
        done, tot = checklist_progress(cl)          # overgeslagen items tellen niet mee in de noemer
        pct = round(100 * done / tot) if tot else 0
        # HETZELFDE ATOOM als op de projectkaart en in de doelkop (fase 11, 2a). Stond hier als
        # twee geneste divs met twee inline breedtes; de `flex:1` die erbij stond deed niets — dat
        # regelt `.ck-prog .pbar` al. `data-ck-bar` is de haak voor de live-stand hieronder.
        bar = (f"<div class='ck-prog'>"
               f"<progress class='nu-progress' value='{pct}' max='100' "
               f"data-ck-bar='{_e(cl['id'])}' data-ck-tot='{tot}'></progress>"
               f"<span class='muted' data-ck-tel='{_e(cl['id'])}'>{pct}% ({done}/{tot})</span>"
               f"</div>") if tot else ""
        rows = ""
        for it in items:
            d = it.get("done")
            state, box_extra = _cl_item_state(it, d)
            wie = project_items.toegewezen(st, it) if st is not None else None
            clitem = (f"<input type='hidden' name='clid' value='{_e(cl['id'])}'>"
                      f"<input type='hidden' name='item' value='{_e(it['id'])}'>")
            # `data-ck-item` koppelt het vakje aan de balk van DEZELFDE lijst (fase 11, 2b). De
            # POST blijft precies zoals hij was — de opslag is leidend; dit is alleen de weergave
            # die meteen meebeweegt in plaats van pas na de herlaadbeurt.
            chk = (f"<form method='post' action='/action' class='ck-chk'>{hid()}{clitem}"
                   f"<button class='ck-box{' on' if d else ''}{box_extra}' type='submit' name='action' "
                   f"value='check_toggle' data-ck-item='{_e(cl['id'])}' "
                   f"data-ck-done='{'1' if d else '0'}'>{'✓' if d else ''}</button></form>"
                   ) if rw else ("☑" if d else "☐")
            rm = (f"<form method='post' action='/action'>{hid()}{clitem}"
                  f"<button class='dellink' type='submit' name='action' value='check_remove'>✕</button></form>") if rw else ""
            # ⠿ SLEEPGREEP, NIET DE HELE REGEL. Een `draggable` <li> vecht met tekstselectie en met
            # het ✓-vakje: elke poging om een woord te selecteren wordt een sleep. Een greep is
            # hetzelfde idioom als de statements-lijst in de kennisbank, dus geen nieuwe interactie
            # om te leren. Alleen zichtbaar bij hover, net als de ✕ ernaast.
            greep = (f"<span class='ck-greep' draggable='true' title='drag to reorder'>⠿</span>"
                     if rw else "")
            # BEWERKEN WAS ER NIET, alleen weggooien. Wie een tikfout wilde herstellen moest het item
            # verwijderen en opnieuw typen. Een `fedit`-uitklap, onder de tekst.
            keuze = ""
            if mensen:
                opties = "".join(
                    f"<option value='{_e(m.id)}'{' selected' if wie is not None and wie.id == m.id else ''}>"
                    f"{_e(m.name)}</option>" for m in mensen)
                keuze = (f"<select name='persoon' aria-label='Assigned to'>"
                         f"<option value=''>Nobody</option>{opties}</select>")
            edit = (f"<details class='fedit ck-bewerk'><summary class='flink' title='edit item'>✎</summary>"
                    f"<form method='post' action='/action' class='ck-doorgeef'>{hid()}{clitem}"
                    f"<input name='text' value='{_e(it['text'])}' autocomplete='off' "
                    f"aria-label='item text'>{keuze}"
                    f"<button class='btn sm' type='submit' name='action' value='check_rename'>"
                    f"save</button></form></details>") if rw else ""
            label = (f" <span class='chip muted' title='Assigned to {_e(wie.name)}'>{_e(wie.name)}</span>"
                     if wie is not None else "")
            txt = (f"<span class='ck-txt'><span class='{'ck-done' if d else ''}'>{_e(it['text'])}</span>"
                   f"{label}{_cl_item_meta(state, it)}</span>")
            unskip = (f"<form method='post' action='/action' class='emo-f'>{hid()}{clitem}"
                      f"<button class='flink' type='submit' name='action' value='check_unskip'>"
                      f"undo skip</button></form>") if (rw and state == "skipped") else ""
            # `data-item`/`data-clid` dragen de sleep: de JS leest ze bij drop en post ze terug.
            # Ze staan op de <li> en niet op de greep, want de drop-doelen zijn de REGELS.
            rows += (f"<li class='ck-item' data-pid='{_e(pid)}' data-item='{_e(it['id'])}' "
                     f"data-clid='{_e(cl['id'])}'>"
                     f"{greep}{chk}{txt}{edit}{unskip}{rm}</li>")
        add = (f"<form method='post' action='/action' class='ckadd'>{hid()}"
               f"<input type='hidden' name='clid' value='{_e(cl['id'])}'>"
               # EEN PLACEHOLDER IS EEN UITNODIGING OF EEN GRIJS VLAK. "add item…" beschrijft het
               # veld; een voorbeeld laat zien wat er in hoort en hoe fijn een item mag zijn.
               f"<input name='text' placeholder='E.g. Ask three suppliers for a sample'>"
               f"<button class='btn ok' type='submit' name='action' value='check_add'>+ item</button></form>") if rw else ""
        delc = (f"<form method='post' action='/action' class='fentry-inline'>{hid()}"
                f"<input type='hidden' name='clid' value='{_e(cl['id'])}'>"
                f"<button class='dellink cl-del' type='submit' name='action' value='checklist_remove' "
                f"onclick=\"return confirm('Remove checklist?')\">remove</button></form>") if rw else ""
        _titel = toon_titel(cl.get("title", ""))
        out += (f"<div class='checklist'><div class='cl-head'>{_IC_CHECK}"
                + (f"<span class='cl-title'>{_e(_titel)}</span>" if _titel else "")
                + f"{delc}</div>"
                f"{bar}<ul class='clean ck-list'>{rows or _CL_LEEG}</ul>{add}</div>")
    if rw and out:
        out += _ck_sleep_js(csrf, f"/project?pid={pid}&back=" + urllib.parse.quote(back, safe=""))
    return out
