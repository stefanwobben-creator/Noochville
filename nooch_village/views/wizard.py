"""Project-wizard view — de geleide Duolingo-flow om één goed project op het bord te zetten.

Server levert de pagina (/project/nieuw); de flow zelf draait client-side en praat via fetch met
drie endpoints (/wizard/sharpen, /wizard/plan, /wizard/create). De LLM-stappen (uitkomst scherp
maken, checklist voorstellen) gebeuren synchroon server-side in die endpoints — de mens wacht en
verwacht dat de AI meedenkt, precies zoals spelvraag. Fail-soft overal.
"""
from __future__ import annotations

import json

from nooch_village import org
from nooch_village.cockpit2_util import _DS_LINK
from nooch_village.web_base import _e, _page


def _name(rec) -> str:
    d = getattr(rec, "definition", None)
    return (getattr(d, "name", None) or getattr(rec, "id", "") or "").strip() or rec.id


II_PREFIX = "ii:"          # Individueel Initiatief: werk onder de cirkel, zonder rol


def _role_options(st, circle: str = "") -> str:
    """Alleen rollen die je vandaag werk kunt geven: WAKKER en niet gearchiveerd.

    Een slapende rol staat stil (geen thread, geen oordeel, geen nieuw werk) — hem in deze lijst
    laten staan is werk beloven dat blijft liggen. Zelfde reden als bij de uitkomst-rollijst van
    het werkoverleg: de keuze mag niet naar een bureau wijzen waar niemand zit.

    Plus 'Individuele actie': niet elk project hoort bij een mandaat. Die hangt onder de cirkel via
    het bestaande `ii:<circle>`-eigenaarschap — geen verzonnen pseudo-rol."""
    opts = []
    for r in sorted(st.records.all(), key=lambda x: _name(x).lower()):
        if getattr(r, "archived", False) or getattr(r, "slaapt", False) or org.is_circle(r):
            continue
        opts.append(f"<option value='{_e(r.id)}'>{_e(_name(r))}</option>")
    cid = circle or _thuis_cirkel(st)
    if cid:
        opts.append(f"<option value='{II_PREFIX}{_e(cid)}'>Individual action (no role)</option>")
    return "".join(opts)


def _thuis_cirkel(st) -> str:
    """De cirkel waar een individuele actie onder hangt als er geen is meegegeven."""
    try:
        recs = st.records.all()
        roots = org.roots(recs)
        if not roots:
            return ""
        subs = [k for k in org.children_of(recs, roots[0].id) if org.is_circle(k)]
        return (subs[0].id if subs else roots[0].id)
    except Exception:                                    # noqa: BLE001 — een lijst mag nooit omvallen
        return ""


def _trekker_options(st) -> str:
    opts = ["<option value=''>— nog niemand</option>"]
    for pr in st.people.all():
        opts.append(f"<option value='person:{_e(pr.id)}'>{_e(pr.name)}</option>")
    for pid, p in (st.personas.all() if hasattr(st.personas, "all") else {}).items() \
            if not isinstance(st.personas.all(), list) else []:
        pass
    try:
        for p in st.personas.all().values():
            opts.append(f"<option value='persona:{_e(p.get('id'))}'>{_e(p.get('name'))} (AI)</option>")
    except Exception:
        pass
    return "".join(opts)


def _js(tekst: str) -> str:
    """Een string veilig in een JS-literal zetten. `_e` is voor HTML-attributen; hier staat de
    waarde IN een script, en daar is een aanhalingsteken of een regeleinde het probleem."""
    return json.dumps(tekst or "")[1:-1]


def render_wizard(st, csrf_token: str = "", *, role: str = "", fragment: bool = False,
                  ruw: str = "", uitkomst: str = "") -> str:
    """De geleide project-wizard. `role` voorselecteert een rol (dan start de flow bij stap 1).
    `fragment=True` levert alleen de wizard-body (voor de modal-overlay); het inline <script> is
    gemarkeerd met data-modal-run zodat de overlay het opnieuw uitvoert na innerHTML-injectie.

    `ruw` en `uitkomst` zijn VOORVULLING uit de plek waar je vandaan komt: het bord geeft de titel
    en de done-when mee, een inbox-spanning geeft zijn tekst als zaad. Wat de mens al heeft
    ingetypt hoort hij niet over te tikken — dat is de reden dat die kale formulieren bestonden.

    Er zijn geen stappen meer: alles staat in één form, met de snelle route bovenaan en de
    verrijking opgevouwen eronder. De voorvulling landt in de velden; opslaan kan meteen.

    De wz-CSS staat in static/nooch.css, dus beide paden dragen `_DS_LINK` — als volle pagina
    (`_page` linkt de component-CSS niet zelf) én als fragment (de overlay kan in een host
    hangen die het stylesheet nog niet had). Dezelfde URL = één download, geen dubbele kost."""
    role_opts = _role_options(st)
    trek_opts = _trekker_options(st)
    pre = role if role and st.records.get(role) is not None and not org.is_circle(st.records.get(role)) else ""
    ruw, uitkomst = (ruw or "").strip(), (uitkomst or "").strip()
    # Geen startstap meer: het is ÉÉN form. De voorvulling landt gewoon in de velden, en de
    # opslaan-knop staat er meteen — dat is het verschil met de zes stappen die je moest doorlopen.
    body = _WIZ_HTML.replace("__CSRF__", _e(csrf_token)) \
                    .replace("__ROLES__", role_opts) \
                    .replace("__TREK__", trek_opts) \
                    .replace("__RUW__", _js(ruw)) \
                    .replace("__UIT__", _js(uitkomst)) \
                    .replace("__ROLE__", _e(pre))
    if fragment:
        return _DS_LINK + body
    return _page("New project", _DS_LINK + body)


_WIZ_HTML = r"""
<div class="wz">
  <div class="wz-top">
    <a class="wz-x" href="/" title="close" onclick="var x=document.querySelector('.ovl-x');if(x){x.click();return false;}">✕</a>
    <span class="wz-who" id="wzwho"></span>
  </div>
  <div class="wz-card" id="wzcard"></div>
</div>
<script data-modal-run>
(function(){
const CSRF="__CSRF__";
const ROLEOPTS="__ROLES__", TREKOPTS="__TREK__", PREROLE="__ROLE__";
// EEN FORM, SNELLE ROUTE EERST. Dit was een flow van zes stappen: je moest er doorheen om één
// project op het bord te krijgen, en elke stap was een plek om te blijven hangen. Nu staat de
// hele snelle route bovenaan — idee, uitkomst, rol, opslaan — en is alles daaronder opgevouwen
// en optioneel. Twee tikken: typ je idee, klik op het bord.
const S={ruw:"__RUW__",uitkomst:"__UIT__",titel:"",checklist:[],planfout:"",tijd:"",missie:"",
         business:"",waarom:"",geschat:false,suggesties:[],sugBezig:false,checkInit:false,
         role:PREROLE,trekker:"",bezig:false,klaar:null};
const card=()=>document.getElementById('wzcard');
function esc(s){return (s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
async function post(url,obj,ms){
  const ctl=new AbortController(); const t=ms?setTimeout(()=>ctl.abort(),ms):null;
  try{
    const b=new URLSearchParams({csrf:CSRF,...obj});
    const r=await fetch(url,{method:'POST',signal:ctl.signal,
      headers:{'Content-Type':'application/x-www-form-urlencoded'},body:b});
    if(!r.ok)return {__fout:'the assistant could not be reached'};
    return await r.json();
  }catch(e){return {__fout:(e&&e.name==='AbortError')?'the assistant took too long':'the assistant could not be reached'};}
  finally{if(t)clearTimeout(t);}
}
// FAIL-OPEN OP DE AI, overal dezelfde vorm als in #369: een timeout, en mislukken levert een
// nette melding in plaats van een hangend scherm. Geen model betekent: je typt het zelf.
const AI_TIMEOUT_MS=12000;

function lees(){
  const g=id=>{const el=document.getElementById(id);return el?el.value.trim():'';};
  S.ruw=g('wz-ruw'); S.uitkomst=g('wz-uit'); S.role=g('wz-role')||S.role;
}
function kanOpslaan(){return !!(document.getElementById('wz-ruw')||{}).value.trim() && !!S.role;}
function stelKnop(){
  const b=document.getElementById('wz-save'); if(!b)return;
  b.disabled=!kanOpslaan()||S.bezig;
}

async function scherp(){
  lees();
  if(!S.ruw)return;
  const veld=document.getElementById('wz-uit'), knop=document.getElementById('wz-ai');
  if(knop){knop.disabled=true;knop.textContent='✨ thinking…';}
  const r=await post('/wizard/sharpen',{ruw:S.ruw},AI_TIMEOUT_MS);
  if(knop){knop.disabled=false;knop.textContent='✨ suggest';}
  const hint=document.getElementById('wz-aihint');
  if(r&&r.__fout){if(hint)hint.textContent='✨ '+r.__fout+' — type it yourself, saving still works.';return;}
  if(hint)hint.textContent='';
  if(veld&&r&&r.uitkomst){veld.value=r.uitkomst;S.uitkomst=r.uitkomst;stelKnop();}
}

function form(){
  card().innerHTML=`
  <div class="wz-k">New project</div>
  <h2>What do you want to achieve?</h2>
  <div class="wz-clab">Your idea</div>
  <textarea id="wz-ruw" rows="2" placeholder="e.g. look into biodegradable soles"
    oninput="stelKnop()">${esc(S.ruw)}</textarea>

  <div class="wz-clab">Done when <span class="wz-hint">— optional, ✨ can suggest one</span></div>
  <div class="wz-add"><input id="wz-uit" value="${esc(S.uitkomst)}"
      placeholder="you'll know it's done when…" oninput="stelKnop()">
    <button type="button" id="wz-ai" onclick="scherp()">✨ suggest</button></div>
  <p class="wz-hint" id="wz-aihint"></p>

  <div class="wz-clab">For which role?</div>
  <select id="wz-role" onchange="S.role=this.value;stelKnop()">
    <option value="">Pick a role…</option>${ROLEOPTS}</select>

  <div class="wz-foot"><button class="wz-btn" id="wz-save" onclick="maak()">Put on the board</button></div>

  <details class="box-details" ontoggle="if(this.open)schat()"><summary>Impact and effort <span class="wz-hint">(optional)</span></summary>
    <div id="wz-impact"></div></details>
  <details class="box-details" ontoggle="if(this.open)checklist()"><summary>Checklist <span class="wz-hint">(optional)</span></summary>
    <div id="wz-check"><p class="wz-hint">Open this to write steps. ✨ suggests some while you type; leaving it empty is fine.</p></div></details>
  `;
  const sel=document.getElementById('wz-role');
  if(S.role){sel.value=S.role;}
  toonWie(); impact(); stelKnop();
  const t=document.getElementById('wz-ruw'); if(t&&!S.ruw)t.focus();
}
function toonWie(){
  const sel=document.getElementById('wz-role'), w=document.getElementById('wzwho');
  if(sel&&w)w.textContent=(sel.selectedOptions[0]&&sel.value)?sel.selectedOptions[0].text:'';
}

// De GOK laadt pas als je de sectie opent — net als de checklist. Geen model betekent lege chips
// en een regel tekst; opslaan werkt de hele tijd door, de knop staat erboven.
async function schat(){
  if(S.geschat)return; S.geschat=true;
  lees();
  const idee=(S.uitkomst||S.ruw); if(!idee){impact('Type your idea first.');return;}
  impact('✨ estimating…');
  const r=await post('/wizard/impact',{idee:idee,role:S.role},AI_TIMEOUT_MS);
  if(r&&r.__fout){impact('✨ '+r.__fout+' — set it yourself, or leave it empty.');return;}
  // Alleen overnemen wat de mens nog niet zelf koos: een gok mag geen keuze overschrijven.
  ['tijd','missie','business'].forEach(k=>{if(!S[k]&&r&&r[k])S[k]=r[k];});
  S.waarom=(r&&r.waarom)||'';
  impact();
}
function label(){
  // Afgeleid, nooit opgeslagen: als het getal verandert verandert het label vanzelf mee.
  if((S.tijd==='1u'||S.tijd==='1d')&&S.business==='hoog')return 'Quick win';
  if(S.tijd==='1w'&&S.business==='laag')return 'Slow burner';
  return '';
}
function impact(melding){
  const el=document.getElementById('wz-impact'); if(!el)return;
  const chip=(g,val,lbl)=>`<span class="wz-chip ${S[g]===val?'on':''}" onclick="S['${g}']=(S['${g}']==='${val}'?'':'${val}');impact()">${lbl}</span>`;
  const lbl=label(), kop=lbl?`<span class="wz-badge ok">${esc(lbl)}</span> `:'';
  const uitleg=melding?`<p class="wz-hint">${esc(melding)}</p>`
    :(S.waarom?`<p class="wz-hint">${kop}✨ guessed: ${esc(S.waarom)} — one tap to change.</p>`
              :(lbl?`<p class="wz-hint">${kop}</p>`:''));
  el.innerHTML=`${uitleg}
   <div class="wz-clab">Time</div><div class="wz-chips">${chip('tijd','1u','1 hour')}${chip('tijd','1d','1 day')}${chip('tijd','2d','2 days')}${chip('tijd','1w','1 week')}</div>
   <div class="wz-clab">Mission impact</div><div class="wz-chips">${chip('missie','versterkt','Strengthens')}${chip('missie','neutraal','Neutral')}${chip('missie','verzwakt','Weakens')}</div>
   <div class="wz-clab">Business impact</div><div class="wz-chips">${chip('business','hoog','High')}${chip('business','medium','Medium')}${chip('business','laag','Low')}</div>`;
}

// OPENEN IS TYPEN. Hier stond een wachtscherm: "✨ maakt een checklist…" met een spinner van
// maximaal twaalf seconden, en pas daarna kon je iets. Dat is de AI vóór de mens zetten bij een
// lijstje afvinken. Nu is de lijst meteen bruikbaar — het invoerveld staat er direct, met de
// cursor erin — en komen de suggesties er los bij als "tik om toe te voegen".
//
// De AI blokkeert dus nooit meer: hij haalt je in, of hij haalt je niet in. Beide zijn goed.
async function checklist(){
  if(S.checkInit)return; S.checkInit=true;
  draw();
  suggesties();                       // BEWUST niet ge-await: de lijst is al bruikbaar
}
async function suggesties(){
  lees();
  const idee=(S.uitkomst||S.ruw); if(!idee)return;
  S.sugBezig=true; drawSug();
  const r=await post('/wizard/plan',{uitkomst:idee,role:S.role},AI_TIMEOUT_MS);
  S.sugBezig=false;
  S.planfout=(r&&r.__fout)||'';
  const heb=new Set(S.checklist.map(x=>(x.tekst||'').trim().toLowerCase()));
  S.suggesties=((r&&r.items)||[]).filter(x=>x&&x.tekst&&!heb.has(x.tekst.trim().toLowerCase()));
  drawSug();
}
function draw(){
  const el=document.getElementById('wz-check'); if(!el)return;
  const rows=S.checklist.map((it,i)=>`<div class="wz-item">
   <input class="wz-itxt" value="${esc(it.tekst)}" aria-label="step ${i+1}"
     oninput="S.checklist[${i}].tekst=this.value">
   ${it.ok?`<span class="wz-badge ok">● ${esc(it.skill)}</span>`:''}
   <button class="wz-rm" onclick="S.checklist.splice(${i},1);draw();drawSug()">✕</button></div>`).join('');
  el.innerHTML=`<div id="wz-rows">${rows}</div>
   <div class="wz-add"><input id="wz-ni" placeholder="type a step and press Enter…"
     onkeydown="if(event.key==='Enter'){event.preventDefault();addI();}"><button onclick="addI()">+ add</button></div>
   <div id="wz-sug"></div>`;
  const i=document.getElementById('wz-ni'); if(i)i.focus();
  drawSug();
}
function drawSug(){
  const el=document.getElementById('wz-sug'); if(!el)return;
  if(S.sugBezig){el.innerHTML='<p class="wz-hint">✨ thinking along — you can keep typing.</p>';return;}
  if(S.planfout){el.innerHTML=`<p class="wz-hint">✨ ${esc(S.planfout)} — your own steps work fine.</p>`;return;}
  if(!S.suggesties.length){el.innerHTML='';return;}
  const chips=S.suggesties.map((it,i)=>`<button type="button" class="wz-chip"
    onclick="neem(${i})">＋ ${esc(it.tekst)}</button>`).join('');
  el.innerHTML=`<p class="wz-hint">✨ suggests — tap to add:</p><div class="wz-chips">${chips}</div>`;
}
function neem(i){const it=S.suggesties[i]; if(!it)return;
  S.suggesties.splice(i,1); S.checklist.push(it); draw();}
function addI(){const i=document.getElementById('wz-ni');const v=i.value.trim();if(!v)return;
  S.checklist.push({tekst:v,skill:null,ok:false,reden:'added manually'});
  i.value=''; draw();}

async function maak(){
  lees();
  if(!kanOpslaan())return;
  S.bezig=true; stelKnop();
  const b=document.getElementById('wz-save'); if(b)b.textContent='Putting it on the board…';
  // GEEN UITKOMST IS GEEN BLOKKADE: dan is je idee de uitkomst, en scherp je hem later aan.
  const r=await post('/wizard/create',{role:S.role,uitkomst:(S.uitkomst||S.ruw),
    trekker:S.trekker,tijd:S.tijd,missie:S.missie,business:S.business,
    items:JSON.stringify(S.checklist)});
  S.bezig=false;
  if(r&&r.url){S.klaar=r; if(window.__ovlDirty)window.__ovlDirty(); gereed();return;}
  if(b){b.disabled=false;b.textContent='Put on the board';}
  const h=document.getElementById('wz-aihint');
  if(h)h.textContent='⚠ '+((r&&(r.error||r.__fout))||'not saved — try again');
}
function gereed(){
  const r=S.klaar;
  card().innerHTML=`<div class="wz-cheer"><div class="big">🎉</div><h2>On the board!</h2>
   <p class="wz-hint">${esc(r.titel||'')}</p></div>
   <div class="wz-foot"><a class="wz-btn ghost" href="${esc(r.url)}">View on the board</a>
   <button class="wz-btn" onclick="restart()">Another project</button></div>`;
}
function restart(){Object.assign(S,{ruw:"",uitkomst:"",titel:"",checklist:[],planfout:"",tijd:"",
  missie:"",business:"",waarom:"",geschat:false,suggesties:[],sugBezig:false,checkInit:false,
  trekker:"",bezig:false,klaar:null}); form();}

window.S=S;window.scherp=scherp;window.maak=maak;window.impact=impact;window.draw=draw;
window.addI=addI;window.restart=restart;window.stelKnop=stelKnop;window.checklist=checklist;
window.schat=schat;window.neem=neem;window.drawSug=drawSug;
form();
})();
</script>
"""
