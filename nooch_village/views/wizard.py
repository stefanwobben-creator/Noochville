"""Project-wizard view — de geleide Duolingo-flow om één goed project op het bord te zetten.

Server levert de pagina (/project/nieuw); de flow zelf draait client-side en praat via fetch met
drie endpoints (/wizard/sharpen, /wizard/plan, /wizard/create). De LLM-stappen (uitkomst scherp
maken, checklist voorstellen) gebeuren synchroon server-side in die endpoints — de mens wacht en
verwacht dat de AI meedenkt, precies zoals spelvraag. Fail-soft overal.
"""
from __future__ import annotations

from nooch_village import org
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


def render_wizard(st, csrf_token: str = "") -> str:
    role_opts = _role_options(st)
    trek_opts = _trekker_options(st)
    body = _WIZ_HTML.replace("__CSRF__", _e(csrf_token)) \
                    .replace("__ROLES__", role_opts) \
                    .replace("__TREK__", trek_opts)
    return _page("Nieuw project", body)


_WIZ_HTML = r"""
<style>
.wz{max-width:560px;margin:0 auto;padding:1.4rem 1rem 3rem}
.wz-top{display:flex;align-items:center;gap:.7rem;margin-bottom:1.3rem}
.wz-x{border:none;background:none;font-size:1.3rem;color:var(--muted);cursor:pointer;text-decoration:none}
.wz-track{flex:1;height:.8rem;background:var(--sand);border-radius:999px;overflow:hidden}
.wz-fill{height:100%;background:linear-gradient(90deg,var(--green),#57c07d);border-radius:999px;width:0;transition:width .35s}
.wz-who{font-size:.78rem;color:var(--subtle);white-space:nowrap}
.wz-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;box-shadow:0 2px 10px rgba(27,27,27,.05);padding:1.4rem 1.3rem;min-height:330px;display:flex;flex-direction:column}
.wz-k{font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--green-dark);margin-bottom:.4rem}
.wz-card h2{font-family:var(--font-display);font-weight:700;font-size:1.3rem;margin:0 0 .3rem;line-height:1.25}
.wz-hint{color:var(--subtle);font-size:.9rem;margin:0 0 1rem}
.wz textarea,.wz input,.wz select{width:100%;font:inherit;padding:.7rem .85rem;border:1.5px solid var(--border);border-radius:10px;background:var(--cream);color:var(--ink)}
.wz textarea:focus,.wz input:focus,.wz select:focus{outline:none;border-color:var(--green)}
.wz-grow{flex:1}
.wz-btn{font:inherit;font-weight:700;font-size:1rem;padding:.75rem 1.1rem;border-radius:999px;border:none;cursor:pointer;background:var(--green);color:#fff;box-shadow:0 3px 0 var(--green-dark)}
.wz-btn:active{transform:translateY(2px);box-shadow:0 1px 0 var(--green-dark)}
.wz-btn:disabled{background:var(--sand);color:var(--muted);box-shadow:0 3px 0 var(--border);cursor:not-allowed}
.wz-btn.ghost{background:var(--surface);color:var(--gray);border:1.5px solid var(--border);box-shadow:none;font-weight:600}
.wz-foot{display:flex;gap:.6rem;align-items:center;margin-top:1.1rem}
.wz-foot .wz-btn{flex:1}
.wz-skip{background:none;border:none;color:var(--subtle);font:inherit;font-weight:600;cursor:pointer;text-decoration:underline}
.wz-was{background:var(--error-tint);border-radius:10px;padding:.6rem .8rem;font-size:.9rem;color:#8f5b52;margin-bottom:.5rem}
.wz-now{background:var(--green-tint);border-radius:10px;padding:.75rem .85rem;border:1.5px solid var(--green)}
.wz-now .lb{font-size:.68rem;font-weight:700;text-transform:uppercase;color:var(--green-dark);letter-spacing:.04em}
.wz-now .tx{font-family:var(--font-display);font-weight:500;font-size:1.02rem;line-height:1.35;margin-top:.15rem}
.wz-think{color:var(--subtle);font-style:italic;font-size:.9rem;padding:.5rem 0}
.wz-item{display:flex;align-items:flex-start;gap:.5rem;padding:.55rem .1rem;border-top:1px solid var(--cream-2)}
.wz-item:first-child{border-top:none}
.wz-itxt{flex:1;font-size:.92rem}
.wz-badge{font-size:.64rem;font-weight:700;padding:.1rem .45rem;border-radius:999px;white-space:nowrap;margin-top:.1rem}
.wz-badge.ok{background:var(--green-tint);color:var(--green-dark)}
.wz-badge.no{background:var(--error-tint);color:#b3402f}
.wz-rm{border:none;background:none;color:var(--muted);cursor:pointer;font-size:1rem;margin-top:.1rem}
.wz-add{display:flex;gap:.4rem;margin-top:.6rem}
.wz-add input{flex:1}
.wz-add button{border:1.5px solid var(--border);background:var(--surface);border-radius:10px;padding:0 .9rem;font-weight:700;color:var(--green-dark);cursor:pointer}
.wz-chips{display:flex;flex-wrap:wrap;gap:.4rem;margin:.2rem 0 .9rem}
.wz-chip{border:1.5px solid var(--border);background:var(--surface);border-radius:999px;padding:.35rem .8rem;font-size:.85rem;font-weight:600;color:var(--gray);cursor:pointer}
.wz-chip.on{border-color:var(--green);background:var(--green-tint);color:var(--green-dark)}
.wz-clab{font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:var(--subtle);margin:.3rem 0 .1rem}
.wz-srow{display:flex;gap:.6rem;padding:.5rem 0;border-top:1px solid var(--cream-2);font-size:.9rem}
.wz-srow:first-child{border-top:none}.wz-sk{width:95px;flex:none;color:var(--subtle);font-weight:600}.wz-sv{flex:1}
.wz-cheer{text-align:center;padding:1rem 0}.wz-cheer .big{font-size:2.6rem}
</style>
<div class="wz">
  <div class="wz-top">
    <a class="wz-x" href="/" title="sluiten">✕</a>
    <div class="wz-track"><div class="wz-fill" id="wzfill"></div></div>
    <span class="wz-who" id="wzwho"></span>
  </div>
  <div class="wz-card" id="wzcard"></div>
</div>
<script>
const CSRF="__CSRF__";
const ROLEOPTS="__ROLES__", TREKOPTS="__TREK__";
const S={step:0,ruw:"",uitkomst:"",checklist:[],tijd:"",missie:"",business:"",role:"",trekker:""};
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
function restart(){Object.assign(S,{step:0,ruw:"",uitkomst:"",checklist:[],tijd:"",missie:"",business:"",role:"",trekker:""});render();}

function start(){card().innerHTML=`
 <div class="wz-k">Nieuw project</div>
 <h2>Laten we samen één goed project op het bord zetten 🌱</h2>
 <p class="wz-hint">In een paar stappen maken we er een scherpe uitkomst en een uitvoerbare checklist van.</p>
 <div class="wz-clab">Voor welke rol?</div><select id="role"><option value="">Kies een rol…</option>${ROLEOPTS}</select>
 <div class="wz-grow"></div>
 <div class="wz-foot"><button class="wz-btn" onclick="S.role=document.getElementById('role').value; if(!S.role){alert('Kies eerst een rol');return;} document.getElementById('wzwho').textContent=document.getElementById('role').selectedOptions[0].text; go(1)">Beginnen</button></div>`;}

function idee(){card().innerHTML=`
 <div class="wz-k">Stap 1 · Jouw idee</div>
 <h2>Wat wil je bereiken?</h2>
 <p class="wz-hint">Gewoon in je eigen woorden. Ruw mag, dat maken we zo samen scherp.</p>
 <textarea id="ruw" rows="3" placeholder="bijv. kijken naar afbreekbare zolen">${esc(S.ruw)}</textarea>
 <div class="wz-grow"></div>
 <div class="wz-foot"><button class="wz-btn ghost" onclick="go(0)">Terug</button>
 <button class="wz-btn" onclick="S.ruw=document.getElementById('ruw').value.trim(); if(!S.ruw)return; go(2)">Volgende</button></div>`;}

async function uitkomst(){
 card().innerHTML=`<div class="wz-k">Stap 2 · ✨ scherpe uitkomst</div><h2>Zo wordt het een échte uitkomst</h2><p class="wz-think">✨ denkt na over je doel…</p>`;
 if(!S.uitkomst){const r=await post('/wizard/sharpen',{ruw:S.ruw}); S.uitkomst=(r&&r.uitkomst)||S.ruw;}
 card().innerHTML=`
  <div class="wz-k">Stap 2 · ✨ scherpe uitkomst</div><h2>Zo wordt het een échte uitkomst</h2>
  <div class="wz-was">Jouw idee: <b>"${esc(S.ruw)}"</b> is nog een onderwerp, niet iets waarvan je wéét wanneer het klaar is.</div>
  <div class="wz-now"><span class="lb">De uitkomst (dit is meteen je 'klaar wanneer')</span>
   <div class="tx" contenteditable="true" id="uit">${esc(S.uitkomst)}</div></div>
  <div class="wz-grow"></div>
  <div class="wz-foot"><button class="wz-btn ghost" onclick="go(1)">Terug</button>
  <button class="wz-btn" onclick="S.uitkomst=document.getElementById('uit').innerText.trim(); S.checklist=[]; go(3)">Ziet er goed uit</button></div>`;}

async function checklist(){
 card().innerHTML=`<div class="wz-k">Stap 3 · ✨ de stappen</div><h2>Zo pak je het aan</h2><p class="wz-think">✨ maakt een checklist en toetst tegen je skills…</p>`;
 if(!S.checklist.length){const r=await post('/wizard/plan',{uitkomst:S.uitkomst,role:S.role}); S.checklist=(r&&r.items)||[];}
 draw();}
function draw(){
 const rows=S.checklist.map((it,i)=>`<div class="wz-item"><div class="wz-itxt">${esc(it.tekst)}</div>
  ${it.ok?`<span class="wz-badge ok">● ${esc(it.skill)}</span>`:`<span class="wz-badge no">○ ${esc(it.reden||'geen skill → mens')}</span>`}
  <button class="wz-rm" onclick="S.checklist.splice(${i},1);draw()">✕</button></div>`).join('')||'<p class="wz-hint">Nog geen stappen — voeg er hieronder één toe.</p>';
 card().innerHTML=`<div class="wz-k">Stap 3 · ✨ de stappen</div><h2>Zo pak je het aan</h2>
  <p class="wz-hint">Groen = een skill kan dit. Rood = menselijke taak. Voeg toe of gooi weg.</p>
  <div>${rows}</div>
  <div class="wz-add"><input id="ni" placeholder="stap toevoegen…" onkeydown="if(event.key==='Enter')addI()"><button onclick="addI()">+ toevoegen</button></div>
  <div class="wz-grow"></div>
  <div class="wz-foot"><button class="wz-btn ghost" onclick="go(2)">Terug</button>
  <button class="wz-btn" onclick="go(4)">Volgende</button></div>`;}
function addI(){const v=document.getElementById('ni').value.trim();if(!v)return;S.checklist.push({tekst:v,skill:null,ok:false,reden:'handmatig toegevoegd'});draw();}

function impact(){
 const chip=(g,val,cur)=>`<span class="wz-chip ${S[g]===val?'on':''}" onclick="S['${g}']=(S['${g}']==='${val}'?'':'${val}');impact()">${cur}</span>`;
 card().innerHTML=`<div class="wz-k">Stap 4 · Inschatting (optioneel)</div><h2>Hoe groot en hoe belangrijk?</h2>
  <p class="wz-hint">Handig voor het bord, maar je mag dit overslaan.</p>
  <div class="wz-clab">Tijd</div><div class="wz-chips">${chip('tijd','1u','1 uur')}${chip('tijd','1d','1 dag')}${chip('tijd','1w','1 week')}</div>
  <div class="wz-clab">Missie-impact</div><div class="wz-chips">${chip('missie','versterkt','versterkt')}${chip('missie','neutraal','neutraal')}${chip('missie','verzwakt','verzwakt')}</div>
  <div class="wz-clab">Business-impact</div><div class="wz-chips">${chip('business','hoog','hoog')}${chip('business','medium','medium')}${chip('business','laag','laag')}</div>
  <div class="wz-grow"></div>
  <div class="wz-foot"><button class="wz-btn ghost" onclick="go(3)">Terug</button>
  <button class="wz-btn" onclick="go(5)">Volgende</button>
  <button class="wz-skip" onclick="S.tijd=S.missie=S.business='';go(5)">sla over</button></div>`;}

function bemens(){card().innerHTML=`
 <div class="wz-k">Stap 5 · Op het bord</div><h2>Wie trekt het?</h2>
 <p class="wz-hint">Het project komt op het bord bij <b>${esc(document.getElementById('wzwho').textContent)}</b>.</p>
 <div class="wz-clab">Trekker</div><select id="trek">${TREKOPTS}</select>
 <div class="wz-grow"></div>
 <div class="wz-foot"><button class="wz-btn ghost" onclick="go(4)">Terug</button>
 <button class="wz-btn" id="mk" onclick="maak()">Op het bord zetten</button></div>`;}

async function maak(){
 S.trekker=document.getElementById('trek').value;
 document.getElementById('mk').disabled=true;document.getElementById('mk').textContent='Bezig…';
 const r=await post('/wizard/create',{uitkomst:S.uitkomst,items:JSON.stringify(S.checklist),
   tijd:S.tijd,missie:S.missie,business:S.business,role:S.role,trekker:S.trekker});
 if(r&&r.url){S.url=r.url;go(6);}else{alert((r&&r.error)||'Er ging iets mis');document.getElementById('mk').disabled=false;document.getElementById('mk').textContent='Op het bord zetten';}}

function klaar(){
 const done=S.checklist.filter(i=>i.ok).length,mens=S.checklist.length-done;
 const meta=[S.tijd&&('⏱ '+S.tijd),S.missie&&('missie: '+S.missie),S.business&&('business: '+S.business)].filter(Boolean).join(' · ')||'geen inschatting';
 card().innerHTML=`<div class="wz-cheer"><div class="big">🎉</div><h2>Op het bord!</h2><p class="wz-hint">${esc(document.getElementById('wzwho').textContent)} pakt het op.</p></div>
  <div class="wz-srow"><span class="wz-sk">Uitkomst</span><span class="wz-sv">${esc(S.uitkomst)}</span></div>
  <div class="wz-srow"><span class="wz-sk">Checklist</span><span class="wz-sv">${S.checklist.length} stappen · ${done} met skill, ${mens} mens-taak</span></div>
  <div class="wz-srow"><span class="wz-sk">Inschatting</span><span class="wz-sv">${esc(meta)}</span></div>
  <div class="wz-grow"></div>
  <div class="wz-foot"><a class="wz-btn ghost" style="text-align:center;text-decoration:none" href="${esc(S.url||'/')}">Bekijk op het bord</a>
  <button class="wz-btn" onclick="restart()">Nog een project</button></div>`;}
render();
</script>
"""
