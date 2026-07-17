"""Inbox — de wachtrij van mentions/spanningen gericht aan de eigenaar (als persoon of in een van zijn
rollen), plus de verwerk-pagina waar je ze afhandelt.

De lijst is kaal en scanbaar: per item een afgekapte titel op één regel, een Verwerk-knop en een
prullenbak. Verwerken gebeurt op een eigen twee-panelen-pagina: links de volledige spanning (met bron),
rechts de intentie-wizard (Wat heb je nodig? → per uitkomst een diagnostische vraag met een knop). Je
kunt meerdere uitkomsten op één spanning stapelen; elke keuze landt in het verwerk-record. Pas 'Klaar'
sluit het item. Zo is zichtbaar of een rol bij de eerste uitkomst stopt of er meer uithaalt.

Hergebruik: web_base (_e/_page), cockpit2_util (_name/_BUILD/_stamp), inbox_wizard (de declaratieve
beslisboom). Geen nieuwe opslag — leunt op NotifStore (met het verwerk-record).
"""
from __future__ import annotations

import json

from nooch_village.web_base import _e, _page, _field
from nooch_village.cockpit2_util import _name, _BUILD, _stamp, _DS_LINK, _nav
from nooch_village.inbox_wizard import INTENTS, OTYPE_LABEL

_STATUS = {"nieuw": ("● nieuw", "chip ok"), "gelezen": ("bezig", "chip muted"),
           "verwerkt": ("✓ verwerkt", "chip outline")}


def _source_link(st, n: dict) -> str:
    pid = (n.get("project_id") or "").strip()
    p = st.projects.get(pid) if pid else None
    if p is not None:
        scope = str(p.get("scope") or "project")[:60]
        return f"<a href='/project?pid={_e(pid)}'>{_e(scope)}</a>"
    return _e(n.get("by") or "onbekende bron")


def _who(st, n: dict) -> str:
    by = (n.get("by") or "").strip()
    rec = st.records.get(by) if by else None
    return _name(rec) if rec is not None else (by or "iemand")


def _one_line(text: str, cap: int = 90) -> str:
    t = " ".join((text or "").split())
    return (t[:cap] + "…") if len(t) > cap else (t or "(geen samenvatting)")


def _hid(csrf: str, nid: str, nxt: str = "/inbox") -> str:
    return (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
            f"<input type='hidden' name='nid' value='{_e(nid)}'>"
            f"<input type='hidden' name='next' value='{_e(nxt)}'>")


def _btn(csrf: str, nid: str, action: str, label: str, cls: str = "flink", nxt: str = "/inbox") -> str:
    return (f"<form method='post' action='/action' class='emo-f'>{_hid(csrf, nid, nxt)}"
            f"<button class='{cls}' name='action' value='{action}'>{_e(label)}</button></form>")


# ── de lijst ────────────────────────────────────────────────────────────────────
def _inbox_row(st, n: dict, csrf: str, done_nid: str = "") -> str:
    status = st.notif.status_of(n)
    lbl, chip = _STATUS.get(status, _STATUS["nieuw"])
    nid = n.get("id", "")
    sep = "<span class='fsep'>·</span>"
    meta = (f"<div class='rdr-meta'><span class='{chip}'>{_e(lbl)}</span> "
            f"<span class='muted'>via {_e(_who(st, n))}</span> {sep} {_source_link(st, n)} {sep} "
            f"<span class='muted'>{_e(_stamp(n.get('at')))}</span></div>")
    title = f"<div class='rdr-sig'>{_e(_one_line(n.get('snippet')))}</div>"

    if status == "verwerkt":
        vs = st.notif.verwerkingen_of(n)
        chips = " ".join(f"<span class='chip outline'>{_e(v.get('label') or 'uitkomst')}</span>" for v in vs) \
            or "<span class='chip outline'>verwerkt</span>"
        body = f"{meta}{title}<div class='ffoot-l'>{chips}</div>"
        act = f"<div class='rdr-act'>{_btn(csrf, nid, 'notif_archive', 'archiveren')}</div>"
        # Viermoment: de zojuist afgeronde spanning krijgt een groene rand + een kader met wat je vastlegde.
        if nid and nid == done_nid:
            regels = "".join(f"<li>{_e(v.get('label') or v.get('otype') or 'uitkomst')}</li>" for v in vs) \
                or "<li>geen uitkomst</li>"
            body += f"<div class='rdr-kader'>✓ Verwerkt. Dit legde je vast:<ul>{regels}</ul></div>"
            return f"<div class='rdr-row rdr-vier'><div class='rdr-body'>{body}</div>{act}</div>"
        return f"<div class='rdr-row'><div class='rdr-body'>{body}</div>{act}</div>"

    verwerk = f"<a class='btn ok sm' href='/inbox/verwerk?nid={_e(nid)}'>Verwerk</a>"
    prullenbak = _btn(csrf, nid, "notif_delete", "🗑", cls="flink")
    act = f"<div class='rdr-act'>{verwerk}{prullenbak}</div>"
    return f"<div class='rdr-row'><div class='rdr-body'>{meta}{title}</div>{act}</div>"


def render_inbox(st, targets, csrf_token: str = "", naam: str = "", done: str = "") -> str:
    items = st.notif.open_for_targets(targets)
    nieuw = sum(1 for n in items if st.notif.status_of(n) == "nieuw")
    body = ("".join(_inbox_row(st, n, csrf_token, done_nid=done) for n in items) if items
            else "<p class='muted'>Je inbox is leeg. Zodra een rol of het overleg je @-mentiont, "
                 "verschijnt het hier.</p>")
    kop = f"Inbox{(' — ' + _e(naam)) if naam else ''}"
    telling = (f"<p class='muted'>{len(items)} open, waarvan {nieuw} nieuw. Klik Verwerk om een "
               f"spanning af te handelen, of gooi 'm weg.</p>")
    main = (f"<div class='c2-main'><div class='c2-bar'><a href='/'>← home</a></div>"
            f"<h1>{kop} <span class='chip'>{len(items)}</span></h1>{telling}"
            f"<div class='rdr-tool'>{body}</div></div>")
    inner = (f"{_DS_LINK}{_nav()}"
             f"<div class='c2-wrap'>{main}</div>")
    return _page("Inbox", inner)


# ── de verwerk-pagina (twee panelen) ─────────────────────────────────────────────
def _spanning_pane(st, n: dict) -> str:
    """Links: de volledige spanning met wie/rol, bron en leeftijd, plus het verwerk-record tot nu toe."""
    sep = "<span class='fsep'>·</span>"
    meta = (f"<div class='rdr-meta'><span class='muted'>via {_e(_who(st, n))}</span> {sep} "
            f"{_source_link(st, n)} {sep} <span class='muted'>{_e(_stamp(n.get('at')))}</span></div>")
    body = _e(n.get("snippet") or "(geen inhoud)").replace("\n", "<br>")
    vs = st.notif.verwerkingen_of(n)
    record = ""
    if vs:
        rows = "".join(f"<li>{_e(v.get('label') or v.get('otype') or 'uitkomst')}"
                       f"{(' — ' + _e(v.get('by'))) if v.get('by') else ''}</li>" for v in vs)
        record = (f"<div class='box rdr-rec'><strong>Al vastgelegd "
                  f"({len(vs)})</strong><ul>{rows}</ul></div>")
    return (f"<div class='rdr-pane'><h3>Spanning</h3>{meta}"
            f"<div class='fbubble rdr-rec'>{body}</div>{record}</div>")


def _outcome_form(otype: str, nid: str, csrf: str, prefill: str, role_opts: str, pj_opts: str,
                  nxt: str, uid: str) -> str:
    """Het compacte formulier achter een uitkomst-knop. Alleen relevante velden, met gekoppelde labels
    (for=/id via _field of expliciet). Post naar notif_outcome, blijft daarna op de verwerk-pagina zodat
    je uitkomsten kunt stapelen. `uid` maakt de veld-ids uniek (dezelfde uitkomst kan meermaals op de
    pagina staan)."""
    hid = (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
           f"<input type='hidden' name='nid' value='{_e(nid)}'>"
           f"<input type='hidden' name='otype' value='{_e(otype)}'>"
           f"<input type='hidden' name='next' value='{_e(nxt)}'>")
    if otype == "ping":
        sid = f"sel-{uid}"
        tgt = (f"<label class='att-lbl' for='{sid}'>Aan welke rol?</label>"
               f"<select id='{sid}' name='ping_role'>{role_opts}</select>")
    elif otype == "project":
        sid = f"sel-{uid}"
        tgt = (f"<label class='att-lbl' for='{sid}'>Op welke rol?</label>"
               f"<select id='{sid}' name='owner'>{role_opts}</select>")
    elif otype == "action":
        sid = f"sel-{uid}"
        tgt = (f"<label class='att-lbl' for='{sid}'>Aan welk project?</label>"
               f"<select id='{sid}' name='pid_link'>{pj_opts}</select>")
    elif otype == "note":
        sid = f"sel-{uid}"
        tgt = (f"<label class='att-lbl' for='{sid}'>Note bij welke rol?</label>"
               f"<select id='{sid}' name='note_role'>{role_opts}</select>")
    else:  # roloverleg — gebruikt de cirkel van de bron
        tgt = "<span class='muted'>Wordt een voorstel op de roloverleg-agenda (mens-route).</span>"
    inhoud = _field("Inhoud (bewerkbaar)", "content", kind="textarea", value=prefill, fid=f"ct-{uid}")
    return (f"<form method='post' action='/action' class='wo-oc'>{hid}"
            f"{inhoud}{tgt}"
            f"<button class='btn sm' name='action' value='notif_outcome'>Vastleggen</button></form>")


def _wizard_pane(n: dict, csrf: str, role_opts: str, pj_opts: str) -> str:
    """Rechts: Wat heb je nodig? Per intentie een accordeon; per uitkomst een vraag + knop die het
    compacte formulier uitklapt. 'Niks nodig' sluit het item direct (FYI-klep)."""
    nid = n.get("id", "")
    prefill = n.get("snippet") or ""
    nxt = f"/inbox/verwerk?nid={nid}"
    groups = []
    for intent in INTENTS:
        opts = []
        for op in intent["options"]:
            q, otype, label, ready = op["q"], op["otype"], op["label"], op.get("ready", True)
            uid = f"{intent['key']}-{otype}"
            if not ready:
                opts.append(f"<div class='wo-ocd rdr-dim'><span class='muted'>{_e(q)}</span> → "
                            f"<strong>{_e(label)}</strong> <em>(volgt in stap 2)</em></div>")
            else:
                form = _outcome_form(otype, nid, csrf, prefill, role_opts, pj_opts, nxt, uid)
                opts.append(f"<details class='wo-ocd box-details'><summary>{_e(q)} → "
                            f"<strong>{_e(label)}</strong></summary>{form}</details>")
        groups.append(f"<details class='box-details'><summary><strong>{_e(intent['label'])}"
                      f"</strong></summary>{''.join(opts)}</details>")
    klaar = (f"<form method='post' action='/action' class='emo-f rdr-rec'>"
             f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
             f"<input type='hidden' name='nid' value='{_e(nid)}'>"
             f"<input type='hidden' name='next' value='/inbox'>"
             f"<button class='btn ok sm' name='action' value='notif_klaar'>Klaar met deze spanning</button></form>")
    return (f"<div class='rdr-pane'><h3>Wat heb je nodig?</h3>{''.join(groups)}{klaar}</div>")


def render_verwerk(st, n: dict, csrf_token: str = "", role_opts: str = "", pj_opts: str = "") -> str:
    """De verwerk-pagina voor één inbox-item: links de spanning, rechts de intentie-wizard."""
    if n is None:
        inner = (f"{_DS_LINK}<div class='c2-wrap'><div class='c2-main'><a href='/inbox'>← inbox</a>"
                 "<p class='muted'>Deze spanning bestaat niet meer.</p></div></div>")
        return _page("Verwerk", inner)
    split = (f"<div class='rdr-split'>"
             f"{_spanning_pane(st, n)}{_wizard_pane(n, csrf_token, role_opts, pj_opts)}</div>")
    main = (f"<div class='c2-main'><h1>Verwerk spanning</h1>{split}</div>")
    inner = (f"{_DS_LINK}<div class='c2-wrap'>{main}</div>")
    return _page("Verwerk", inner)


# ── de globale inbox-drawer (chrome op elke pagina) + het lijst-fragment ──────────
def _ibx_row(st, n: dict) -> str:
    """Eén kaartje in de drawer. Open item → klik opent de modal-wizard; verwerkt item → sleep naar
    rechts om te archiveren."""
    nid = n.get("id", "")
    status = st.notif.status_of(n)
    title = _e(_one_line(n.get("snippet")))
    who = _e(_who(st, n))
    if status == "verwerkt":
        vs = st.notif.verwerkingen_of(n)
        kader = "".join(f"<div class='ibx-kader'>✓ {_e(v.get('label') or 'uitkomst')}</div>" for v in vs)
        return (f"<div class='ibx-row done' data-nid='{_e(nid)}'><span class='ibx-dot read'></span>"
                f"<div class='ibx-rb'><div class='ibx-title'>{title}</div>"
                f"<div class='ibx-meta'>verwerkt · {who}</div>{kader}</div>"
                f"<span class='ibx-swipe'>sleep &rarr; archiveer</span></div>")
    dot = "ibx-dot read" if status == "gelezen" else "ibx-dot"
    return (f"<div class='ibx-row' data-nid='{_e(nid)}' onclick=\"ibxOpen('{_e(nid)}')\">"
            f"<span class='{dot}'></span><div class='ibx-rb'><div class='ibx-title'>{title}</div>"
            f"<div class='ibx-meta'>via {who} &middot; {_e(_stamp(n.get('at')))}</div></div>"
            f"<button class='ibx-trash' title='weggooien' "
            f"onclick=\"event.stopPropagation();ibxTrash('{_e(nid)}')\">&#128465;</button></div>")


def render_inbox_frag(st, targets, csrf_token: str = "") -> str:
    """Het dynamische deel van de drawer: telling + rijen, opgehaald via /inbox?frag=1. Geen page-shell
    (de shell is de chrome). De drawer-JS leest data-count/data-sub en vult de lijst."""
    items = st.notif.open_for_targets(targets)
    nieuw = sum(1 for n in items if st.notif.status_of(n) == "nieuw")
    rows = "".join(_ibx_row(st, n) for n in items) or \
        "<div class='ibx-empty'><div class='ibx-party'>&#127881;</div>Je inbox is leeg.</div>"
    sub = f"{len(items)} open, waarvan {nieuw} nieuw" if items else "Alles verwerkt — geniet ervan."
    return f"<div data-count='{len(items)}' data-sub='{_e(sub)}'>{rows}</div>"


def _person_role_options(st, targets) -> str:
    """Opties voor 'vanuit welke rol voel je het' bij zelf een spanning toevoegen: de rollen die de
    ingelogde persoon vervult, plus 'als mezelf'."""
    opts = ["<option value=''>als mezelf</option>"]
    for ty, tid in targets:
        if ty == "role":
            rec = st.records.get(tid)
            if rec is not None:
                opts.append(f"<option value='{_e(tid)}'>{_e(_name(rec))}</option>")
    return "".join(opts)


_IBX_JS = """
var IBX_CSRF=__IBX_CSRF__;
function ibxToggle(){var d=document.getElementById('ibx-drawer');d.classList.toggle('open');
  if(d.classList.contains('open'))ibxRefresh();}
function ibxAddToggle(){document.getElementById('ibx-add').classList.toggle('open');}
function ibxPost(a,x){return fetch('/action',{method:'POST',
  headers:{'Content-Type':'application/x-www-form-urlencoded'},
  body:new URLSearchParams(Object.assign({action:a,csrf:IBX_CSRF,next:'/inbox'},x||{}))});}
function ibxRefresh(){return fetch('/inbox?frag=1').then(function(r){return r.text();}).then(function(h){
  var t=document.createElement('div');t.innerHTML=h;var w=t.firstElementChild;
  var cnt=w?parseInt(w.getAttribute('data-count')||'0',10):0;
  document.getElementById('ibx-list').innerHTML=w?w.innerHTML:h;
  document.getElementById('ibx-hct').textContent=cnt;
  var b=document.getElementById('ibx-badge');b.textContent=cnt;b.classList.toggle('hide',cnt===0);
  document.getElementById('ibx-launch').classList.toggle('zero',cnt===0);
  document.getElementById('ibx-icon').textContent=cnt?'\\uD83D\\uDCE5':'\\uD83C\\uDF89';
  document.getElementById('ibx-sub').textContent=w?(w.getAttribute('data-sub')||''):'';
  ibxBindSwipe();});}
function ibxOpen(nid){var f=document.getElementById('ibx-frame');
  f.src='/inbox/verwerk?nid='+encodeURIComponent(nid);
  document.getElementById('ibx-scrim').classList.add('open');}
function ibxCloseModal(){document.getElementById('ibx-scrim').classList.remove('open');
  document.getElementById('ibx-frame').src='about:blank';}
function ibxFrameLoad(){try{var p=document.getElementById('ibx-frame').contentWindow.location.pathname;
  if(p==='/inbox'){ibxCloseModal();ibxThumb();ibxRefresh();}}catch(e){}}
function ibxAddSubmit(){var t=document.getElementById('ibx-addtext'),r=document.getElementById('ibx-addrole');
  if(!t.value.trim())return;ibxPost('notif_add',{text:t.value.trim(),role:r.value}).then(function(){
    t.value='';ibxAddToggle();ibxRefresh();});}
function ibxTrash(nid){ibxPost('notif_delete',{nid:nid}).then(ibxRefresh);}
function ibxThumb(){var t=document.getElementById('ibx-thumb');t.classList.add('on');
  setTimeout(function(){t.classList.remove('on');},900);}
function ibxBindSwipe(){var rows=document.querySelectorAll('.ibx-row.done');
  for(var i=0;i<rows.length;i++){(function(el){var sx=0,dx=0,drag=false;
    el.onpointerdown=function(e){drag=true;sx=e.clientX;el.setPointerCapture(e.pointerId);};
    el.onpointermove=function(e){if(!drag)return;dx=Math.max(0,e.clientX-sx);
      el.style.setProperty('transform','translateX('+dx+'px)');
      el.style.setProperty('opacity',String(1-Math.min(dx/220,.6)));};
    var end=function(){if(!drag)return;drag=false;
      if(dx>90){el.style.setProperty('transform','translateX(120%)');el.style.setProperty('opacity','0');
        ibxPost('notif_archive',{nid:el.getAttribute('data-nid')}).then(function(){setTimeout(ibxRefresh,160);});}
      else{el.style.setProperty('transform','');el.style.setProperty('opacity','');}dx=0;};
    el.onpointerup=end;el.onpointercancel=end;})(rows[i]);}}
document.getElementById('ibx-frame').addEventListener('load',ibxFrameLoad);
ibxRefresh();
"""


def render_inbox_chrome(csrf_token: str = "", role_opts: str = "") -> str:
    """De globale inbox-drawer die op elke ingelogde pagina wordt geïnjecteerd: launcher-knop met badge,
    uitschuif-paneel links, en de modal die de bestaande verwerk-pagina in een iframe toont. De lijst en
    de telling worden lui opgehaald via /inbox?frag=1 (JS), zodat de injectie zelf licht blijft."""
    launch = ("<button class='ibx-launch' id='ibx-launch' title='Inbox' onclick='ibxToggle()'>"
              "<span id='ibx-icon'>&#128229;</span><span class='ibx-ct hide' id='ibx-badge'>0</span></button>")
    add = ("<div class='ibx-add' id='ibx-add'>"
           "<label for='ibx-addtext'>Wat voel je?</label>"
           "<textarea id='ibx-addtext' placeholder='een spanning, vraag of losse gedachte…'></textarea>"
           "<label for='ibx-addrole'>Vanuit welke rol?</label>"
           f"<select id='ibx-addrole'>{role_opts}</select>"
           "<div class='rdr-rec'><button class='btn ok sm' onclick='ibxAddSubmit()'>Toevoegen</button> "
           "<button class='btn sm' onclick='ibxAddToggle()'>Annuleer</button></div></div>")
    drawer = ("<aside class='ibx-drawer' id='ibx-drawer'>"
              "<div class='ibx-head'><h2>Inbox</h2><span class='ibx-hct' id='ibx-hct'>0</span>"
              "<button class='ibx-plus' title='Spanning toevoegen' onclick='ibxAddToggle()'>+</button>"
              "<button class='ibx-x' title='sluiten' onclick='ibxToggle()'>&times;</button></div>"
              "<div class='ibx-sub' id='ibx-sub'></div>" + add +
              "<div class='ibx-list' id='ibx-list'></div></aside>")
    modal = ("<div class='ibx-scrim' id='ibx-scrim'><div class='ibx-modal'>"
             "<button class='ibx-mx' title='sluiten' onclick='ibxCloseModal()'>&times;</button>"
             "<iframe class='ibx-iframe' id='ibx-frame' title='Verwerk spanning'></iframe></div></div>"
             "<div class='ibx-thumb' id='ibx-thumb'>&#128077;</div>")
    return (launch + drawer + modal + "<script>"
            + _IBX_JS.replace("__IBX_CSRF__", json.dumps(csrf_token)) + "</script>")
