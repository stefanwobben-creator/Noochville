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


def _role_options(st) -> str:
    opts = []
    for r in st.records.all():
        if getattr(r, "archived", False) or org.is_circle(r):
            continue
        opts.append(f"<option value='{_e(r.id)}'>{_e(_name(r))}</option>")
    return "".join(opts)


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

    De startstap volgt daaruit: is er al een uitkomst, dan begin je bij het aanscherpen; is er
    alleen een zaadtekst, bij het idee; is er niets, bij de rolkeuze. Zonder rol altijd bij stap 0,
    want de wizard heeft een eigenaar nodig.

    De wz-CSS staat in static/nooch.css, dus beide paden dragen `_DS_LINK` — als volle pagina
    (`_page` linkt de component-CSS niet zelf) én als fragment (de overlay kan in een host
    hangen die het stylesheet nog niet had). Dezelfde URL = één download, geen dubbele kost."""
    role_opts = _role_options(st)
    trek_opts = _trekker_options(st)
    pre = role if role and st.records.get(role) is not None and not org.is_circle(st.records.get(role)) else ""
    ruw, uitkomst = (ruw or "").strip(), (uitkomst or "").strip()
    if not pre:
        stap = 0
    elif uitkomst:
        stap = 2
    elif ruw:
        stap = 1
    else:
        stap = 1
    body = _WIZ_HTML.replace("__CSRF__", _e(csrf_token)) \
                    .replace("__ROLES__", role_opts) \
                    .replace("__TREK__", trek_opts) \
                    .replace("__RUW__", _js(ruw)) \
                    .replace("__UIT__", _js(uitkomst)) \
                    .replace("__STAP__", str(stap)) \
                    .replace("__ROLE__", _e(pre))
    if fragment:
        return _DS_LINK + body
    return _page("New project", _DS_LINK + body)


_WIZ_HTML = r"""
<div class="wz">
  <div class="wz-top">
    <a class="wz-x" href="/" title="close" onclick="var x=document.querySelector('.ovl-x');if(x){x.click();return false;}">✕</a>
    <div class="wz-track"><div class="wz-fill" id="wzfill"></div></div>
    <span class="wz-who" id="wzwho"></span>
  </div>
  <div class="wz-card" id="wzcard"></div>
</div>
<script data-modal-run>
(function(){
const CSRF="__CSRF__";
const ROLEOPTS="__ROLES__", TREKOPTS="__TREK__", PREROLE="__ROLE__";
const S={step:__STAP__,ruw:"__RUW__",uitkomst:"__UIT__",titel:"",checklist:[],tijd:"",missie:"",business:"",role:PREROLE,trekker:""};
const NST=6, card=()=>document.getElementById('wzcard');
function esc(s){return (s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function prog(){document.getElementById('wzfill').style.width=(S.step/(NST-1)*100)+'%';}
async function post(url,obj){
  const b=new URLSearchParams({csrf:CSRF,...obj});
  const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:b});
  return r.json();
}
function render(){prog();[start,idee,uitkomst,checklist,impact,bemens,klaar][S.step]();}
function go(n){S.step=n;render();}
function restart(){Object.assign(S,{step:0,ruw:"",uitkomst:"",titel:"",checklist:[],tijd:"",missie:"",business:"",role:"",trekker:""});render();}

function start(){card().innerHTML=`
 <div class="wz-k">New project</div>
 <h2>Let's put one good project on the board together 🌱</h2>
 <p class="wz-hint">In a few steps we'll turn it into a sharp outcome and a workable checklist.</p>
 <div class="wz-clab">For which role?</div><select id="role"><option value="">Pick a role…</option>${ROLEOPTS}</select>
 <div class="wz-grow"></div>
 <div class="wz-foot"><button class="wz-btn" onclick="S.role=document.getElementById('role').value; if(!S.role){alert('Pick a role first');return;} document.getElementById('wzwho').textContent=document.getElementById('role').selectedOptions[0].text; go(1)">Start</button></div>`;}

function idee(){card().innerHTML=`
 <div class="wz-k">Step 1 · Your idea</div>
 <h2>What do you want to achieve?</h2>
 <p class="wz-hint">Just in your own words. Rough is fine, we'll sharpen it together.</p>
 <textarea id="ruw" rows="3" placeholder="e.g. look into biodegradable soles">${esc(S.ruw)}</textarea>
 <div class="wz-grow"></div>
 <div class="wz-foot"><button class="wz-btn ghost" onclick="go(0)">Back</button>
 <button class="wz-btn" onclick="S.ruw=document.getElementById('ruw').value.trim(); if(!S.ruw)return; go(2)">Next</button></div>`;}

async function uitkomst(){
 card().innerHTML=`<div class="wz-k">Step 2 · ✨ sharp outcome</div><h2>This makes it a real outcome</h2><p class="wz-think">✨ is thinking about your goal…</p>`;
 if(!S.uitkomst){const r=await post('/wizard/sharpen',{ruw:S.ruw}); S.uitkomst=(r&&r.uitkomst)||S.ruw;}
 card().innerHTML=`
  <div class="wz-k">Step 2 · ✨ sharp outcome</div><h2>This makes it a real outcome</h2>
  <div class="wz-was">Your idea: <b>"${esc(S.ruw)}"</b> is still a topic, not something you'll know is done.</div>
  <div class="wz-now"><span class="lb">The outcome (this is also your 'done when')</span>
   <div class="tx" contenteditable="true" id="uit">${esc(S.uitkomst)}</div></div>
  <div class="wz-grow"></div>
  <div class="wz-foot"><button class="wz-btn ghost" onclick="go(1)">Back</button>
  <button class="wz-btn" onclick="S.uitkomst=document.getElementById('uit').innerText.trim(); S.checklist=[]; go(3)">Looks good</button></div>`;}

// DE CHECKLIST IS EEN BONUS, GEEN POORT.
//
// Deze stap wachtte zonder uitweg op de AI: geen overslaan-knop en geen timeout, dus een trage of
// ontbrekende LLM hield de mens vast bij iets kernachtigs — een project op het bord zetten. Nu
// route élke projectcreatie hierlangs, en dan is dat geen ongemak meer maar een gesloten deur.
//
// Drie dingen: de overslaan-knop staat er METEEN (ook tijdens het wachten), de call heeft een
// timeout, en mislukken levert een lege lijst met een nette melding in plaats van een hangend
// scherm. Je kunt altijd verder, met of zonder AI.
const PLAN_TIMEOUT_MS=12000;
async function planItems(){
 const ctl=new AbortController();
 const t=setTimeout(()=>ctl.abort(), PLAN_TIMEOUT_MS);
 try{
   const b=new URLSearchParams({csrf:CSRF,uitkomst:S.uitkomst,role:S.role});
   const r=await fetch('/wizard/plan',{method:'POST',signal:ctl.signal,
     headers:{'Content-Type':'application/x-www-form-urlencoded'},body:b});
   if(!r.ok)return {items:[],fout:'the assistant could not be reached'};
   const j=await r.json();
   return {items:(j&&j.items)||[],fout:(j&&j.error)?'the assistant could not help here':''};
 }catch(e){
   return {items:[],fout:(e&&e.name==='AbortError')?'the assistant took too long':'the assistant could not be reached'};
 }finally{clearTimeout(t);}
}
function wachtkaart(){card().innerHTML=`<div class="wz-k">Step 3 · ✨ the steps (optional)</div>
 <h2>Here's how to tackle it</h2>
 <p class="wz-think">✨ makes a checklist and checks it against your skills…</p>
 <div class="wz-grow"></div>
 <div class="wz-foot"><button class="wz-btn ghost" onclick="go(2)">Back</button>
 <button class="wz-btn ghost" onclick="S.checklist=[];go(4)">Skip this step</button></div>`;}
async function checklist(){
 wachtkaart();
 if(!S.checklist.length){
   const r=await planItems();
   if(S.step!==3)return;                       // al doorgeklikt terwijl de AI nog bezig was
   S.checklist=r.items; S.planfout=r.fout;
 }
 draw();}
function draw(){
 const rows=S.checklist.map((it,i)=>`<div class="wz-item"><div class="wz-itxt">${esc(it.tekst)}</div>
  ${it.ok?`<span class="wz-badge ok">● ${esc(it.skill)}</span>`:`<span class="wz-badge no">○ ${esc(it.reden||'no skill → human')}</span>`}
  <button class="wz-rm" onclick="S.checklist.splice(${i},1);draw()">✕</button></div>`).join('')||'<p class="wz-hint">No steps yet — add one below.</p>';
 const melding=S.planfout?`<p class="wz-hint">✨ ${esc(S.planfout)} — add steps yourself, or skip this step. Your project will be created either way.</p>`:'';
 card().innerHTML=`<div class="wz-k">Step 3 · ✨ the steps (optional)</div><h2>Here's how to tackle it</h2>
  <p class="wz-hint">Green = a skill can do this. Red = human task. Add or remove.</p>
  ${melding}
  <div>${rows}</div>
  <div class="wz-add"><input id="ni" placeholder="add step…" onkeydown="if(event.key==='Enter')addI()"><button onclick="addI()">+ add</button></div>
  <div class="wz-grow"></div>
  <div class="wz-foot"><button class="wz-btn ghost" onclick="go(2)">Back</button>
  <button class="wz-btn ghost" onclick="S.checklist=[];go(4)">Skip this step</button>
  <button class="wz-btn" onclick="go(4)">Next</button></div>`;}
function addI(){const v=document.getElementById('ni').value.trim();if(!v)return;S.checklist.push({tekst:v,skill:null,ok:false,reden:'added manually'});draw();}

function impact(){
 const chip=(g,val,cur)=>`<span class="wz-chip ${S[g]===val?'on':''}" onclick="S['${g}']=(S['${g}']==='${val}'?'':'${val}');impact()">${cur}</span>`;
 card().innerHTML=`<div class="wz-k">Step 4 · Estimate (optional)</div><h2>How big and how important?</h2>
  <p class="wz-hint">Handy for the board, but you can skip this.</p>
  <div class="wz-clab">Time</div><div class="wz-chips">${chip('tijd','1u','1 hour')}${chip('tijd','1d','1 day')}${chip('tijd','1w','1 week')}</div>
  <div class="wz-clab">Mission impact</div><div class="wz-chips">${chip('missie','versterkt','Strengthens')}${chip('missie','neutraal','Neutral')}${chip('missie','verzwakt','Weakens')}</div>
  <div class="wz-clab">Business impact</div><div class="wz-chips">${chip('business','hoog','High')}${chip('business','medium','Medium')}${chip('business','laag','Low')}</div>
  <div class="wz-grow"></div>
  <div class="wz-foot"><button class="wz-btn ghost" onclick="go(3)">Back</button>
  <button class="wz-btn" onclick="go(5)">Next</button>
  <button class="wz-skip" onclick="S.tijd=S.missie=S.business='';go(5)">skip</button></div>`;}

function bemens(){card().innerHTML=`
 <div class="wz-k">Step 5 · On the board</div><h2>Who owns it?</h2>
 <p class="wz-hint">The project lands on the board of <b>${esc(document.getElementById('wzwho').textContent)}</b>.</p>
 <div class="wz-clab">Owner</div><select id="trek">${TREKOPTS}</select>
 <div class="wz-grow"></div>
 <div class="wz-foot"><button class="wz-btn ghost" onclick="go(4)">Back</button>
 <button class="wz-btn" id="mk" onclick="maak()">Put on the board</button></div>`;}

async function maak(){
 S.trekker=document.getElementById('trek').value;
 document.getElementById('mk').disabled=true;document.getElementById('mk').textContent='Working…';
 const r=await post('/wizard/create',{uitkomst:S.uitkomst,items:JSON.stringify(S.checklist),
   tijd:S.tijd,missie:S.missie,business:S.business,role:S.role,trekker:S.trekker});
 if(r&&r.url){S.url=r.url;S.titel=(r&&r.titel)||'';if(window.__ovlDirty)window.__ovlDirty();go(6);}else{alert((r&&r.error)||'Something went wrong');document.getElementById('mk').disabled=false;document.getElementById('mk').textContent='Put on the board';}}

function klaar(){
 const done=S.checklist.filter(i=>i.ok).length,mens=S.checklist.length-done;
 const LBL={versterkt:'Strengthens',neutraal:'Neutral',verzwakt:'Weakens',hoog:'High',medium:'Medium',laag:'Low','1u':'1 hour','1d':'1 day','1w':'1 week'};
 const meta=[S.tijd&&('⏱ '+(LBL[S.tijd]||S.tijd)),S.missie&&('mission: '+(LBL[S.missie]||S.missie)),S.business&&('business: '+(LBL[S.business]||S.business))].filter(Boolean).join(' · ')||'no estimate';
 card().innerHTML=`<div class="wz-cheer"><div class="big">🎉</div><h2>On the board!</h2><p class="wz-hint">${esc(document.getElementById('wzwho').textContent)} takes it on.</p></div>
  ${S.titel?`<div class="wz-srow"><span class="wz-sk">Title</span><span class="wz-sv">${esc(S.titel)}</span></div>`:''}
  <div class="wz-srow"><span class="wz-sk">Done when</span><span class="wz-sv">${esc(S.uitkomst)}</span></div>
  <div class="wz-srow"><span class="wz-sk">Checklist</span><span class="wz-sv">${S.checklist.length} steps · ${done} with skill, ${mens} human task</span></div>
  <div class="wz-srow"><span class="wz-sk">Estimate</span><span class="wz-sv">${esc(meta)}</span></div>
  <div class="wz-grow"></div>
  <div class="wz-foot"><a class="wz-btn ghost" href="${esc(S.url||'/')}">View on the board</a>
  <button class="wz-btn" onclick="restart()">Another project</button></div>`;}
// Inline onclick-handlers in de gegenereerde HTML draaien in global scope; die functies moeten
// dus op window staan. De rest blijft in deze IIFE (zo botst een tweede modal-open niet op const).
window.S=S;window.go=go;window.draw=draw;window.addI=addI;window.impact=impact;window.maak=maak;window.restart=restart;
if(PREROLE){
  var _t=document.createElement('select');_t.innerHTML=ROLEOPTS;
  var _o=_t.querySelector("option[value='"+PREROLE+"']");
  document.getElementById('wzwho').textContent=_o?_o.textContent:'';
}
// De startstap komt van de server (`__STAP__`): die weet of er een uitkomst is meegekomen en dus
// of je bij het aanscherpen of bij het idee begint. Hier hem overschrijven zou de voorvulling
// weer in de eerste stap laten belanden.
render();
})();
</script>
"""
