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


from nooch_village.cockpit2_util import _name, _rol_labels    # één naamregel, geen tweede vorm


II_PREFIX = "ii:"          # Individueel Initiatief: werk onder de cirkel, zonder rol


def ii_cirkel(role: str) -> str:
    """De cirkel uit een `ii:<circle>`-eigenaar, of "" als het er geen is."""
    r = (role or "").strip()
    return r[len(II_PREFIX):] if r.startswith(II_PREFIX) else ""


def _role_options(st, circle: str = "", eigen: list | None = None) -> str:
    """Alleen rollen die je vandaag werk kunt geven: WAKKER en niet gearchiveerd.

    Een slapende rol staat stil (geen thread, geen oordeel, geen nieuw werk) — hem in deze lijst
    laten staan is werk beloven dat blijft liggen. Zelfde reden als bij de uitkomst-rollijst van
    het werkoverleg: de keuze mag niet naar een bureau wijzen waar niemand zit.

    Plus 'Individuele actie': niet elk project hoort bij een mandaat. Die hangt onder de cirkel via
    het bestaande `ii:<circle>`-eigenaarschap — geen verzonnen pseudo-rol."""
    alle = st.records.all()
    kandidaten = [r for r in sorted(alle, key=lambda x: _name(x).lower())
                  if not getattr(r, "archived", False) and not getattr(r, "slaapt", False)
                  and not org.is_circle(r)]
    # EIGEN ROLLEN, als de aanroeper daarom vraagt (de inbox doet dat). Werk bij een ANDERE rol
    # neerleggen is een verzoek, geen project dat je voor hem aanmaakt — een rol is baas over zijn
    # eigen bord. Vanaf het projectbord blijft de volle lijst staan: daar kies je bewust een kolom.
    if eigen is not None:
        toegestaan = set(eigen)
        kandidaten = [r for r in kandidaten if r.id in toegestaan]
    labels = _rol_labels(kandidaten, alle)            # Circle Lead ≠ Circle Lead: welke cirkel?
    opts = [f"<option value='{_e(r.id)}'>{_e(labels.get(r.id) or _name(r))}</option>"
            for r in kandidaten]
    # INDIVIDUELE ACTIE HANGT ONDER EEN CIRKEL, en welke dat is mag niet stilzwijgend gekozen
    # worden. Kwam je van een `ii:<cirkel>`-baan, dan is het díe cirkel. Anders bieden we ze
    # allemaal aan met de naam erbij — één stil kiezen is precies de aanname die vandaag negen
    # acties op een vreemd project liet belanden.
    for cid in ([circle] if circle else _cirkels(st)):
        if not cid:
            continue
        naam = _name_of(st, cid)
        label = "Individual action (no role)" if len(_cirkels(st)) <= 1 and not circle \
            else f"Individual action in {naam}"
        opts.append(f"<option value='{II_PREFIX}{_e(cid)}'>{_e(label)}</option>")
    return "".join(opts)


def _cirkels(st) -> list:
    """Alle cirkels waar een individuele actie onder kan hangen, van binnen naar buiten."""
    try:
        recs = st.records.all()
        roots = org.roots(recs)
        if not roots:
            return []
        subs = [k.id for k in org.children_of(recs, roots[0].id) if org.is_circle(k)]
        return subs or [roots[0].id]
    except Exception:                                    # noqa: BLE001 — een lijst mag nooit omvallen
        return []


def _name_of(st, cid: str) -> str:
    rec = st.records.get(cid)
    return _name(rec) if rec is not None else cid


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
                  ruw: str = "", uitkomst: str = "", trekker: str = "", nid: str = "",
                  vervullers: dict | None = None,
                  eigen: list | None = None) -> str:
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
    role_opts = _role_options(st, circle=ii_cirkel(role), eigen=eigen)
    trek_opts = _trekker_options(st)
    # EEN `ii:<cirkel>`-EIGENAAR IS EEN GELDIGE VOORSELECTIE. Hij staat niet in de records (het is
    # geen rol), dus de check hieronder wees hem af en je viel terug op "Pick a role…" — precies de
    # context die het bord al wist, weggegooid bij de klik.
    ii = ii_cirkel(role)
    if ii and st.records.get(ii) is not None:
        pre = role
    else:
        pre = role if role and st.records.get(role) is not None \
            and not org.is_circle(st.records.get(role)) else ""
    ruw, uitkomst = (ruw or "").strip(), (uitkomst or "").strip()
    # De spanning waar dit project uit voortkomt, als die er is. Reist mee tot aan
    # /wizard/create, die hem sluit zodra het project bestaat.
    nid = (nid or "").strip()
    # Geen startstap meer: het is ÉÉN form. De voorvulling landt gewoon in de velden, en de
    # opslaan-knop staat er meteen — dat is het verschil met de zes stappen die je moest doorlopen.
    body = _WIZ_HTML.replace("__CSRF__", _e(csrf_token)) \
                    .replace("__ROLES__", role_opts) \
                    .replace("__TREK__", trek_opts) \
                    .replace("__RUW__", _js(ruw)) \
                    .replace("__NID__", _js(nid)) \
                    .replace("__VERVULLERS__", json.dumps(vervullers or {})) \
                    .replace("__UIT__", _js(uitkomst)) \
                    .replace("__TREKKER__", _js(trekker)) \
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
// Alleen rollen met TWEE of meer vervullers (cockpit2.vervullers_map). Bij één is er
// niets te kiezen — die staat al als default in S.trekker — en bij nul niets te tonen.
const VERVULLERS=__VERVULLERS__;
// EEN FORM, SNELLE ROUTE EERST. Dit was een flow van zes stappen: je moest er doorheen om één
// project op het bord te krijgen, en elke stap was een plek om te blijven hangen. Nu staat de
// hele snelle route bovenaan — idee, uitkomst, rol, opslaan — en is alles daaronder opgevouwen
// en optioneel. Twee tikken: typ je idee, klik op het bord.
const S={ruw:"__RUW__",uitkomst:"__UIT__",nid:"__NID__",titel:"",checklist:[],planfout:"",tijd:"",missie:"",
         business:"",waarom:"",geschat:false,suggesties:[],sugBezig:false,checkInit:false,
         rollen:[],rollenInit:false,rollenfout:"",taken:[],role:PREROLE,
         trekker:"__TREKKER__",bezig:false,klaar:null};
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
// De checklist-suggestie krijgt langer, en dat is geen uitzondering maar een gevolg: die 12s zit er
// tegen een BLOKKERENDE wachttijd, en deze call blokkeert niets. Het invoerveld staat er al met de
// cursor erin (`suggesties()` wordt bewust niet ge-await), dus de enige vraag is hoe lang we willen
// wachten op een bonus die naast een bruikbaar veld landt.
//
// Het verschil is bovendien niet theoretisch: dit is een hoog-inzet-site (llm_keuze.HOOG_INZET), en
// die draait op het sterkste model dat we hebben — trager dan de goedkope tredes. Met 12s zou de
// browser er stelselmatig uitstappen zodra dat model wél antwoordt, en dan hebben we het werk
// betaald en weggegooid. Precies wat er op prod al gebeurde, alleen met een andere oorzaak.
const PLAN_TIMEOUT_MS=45000;

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
  <details class="box-details" ontoggle="if(this.open)rollen()"><summary>Who could pick this up <span class="wz-hint">(optional)</span></summary>
    <div id="wz-rollen"></div></details>
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
  const r=await post('/wizard/plan',{uitkomst:idee,role:S.role},PLAN_TIMEOUT_MS);
  S.sugBezig=false;
  S.planfout=(r&&r.__fout)||'';
  const heb=new Set(S.checklist.map(x=>(x.tekst||'').trim().toLowerCase()));
  S.suggesties=((r&&r.items)||[]).filter(x=>x&&x.tekst&&!heb.has(x.tekst.trim().toLowerCase()));
  S.sugAan=(S.sugAan||0)+S.suggesties.length; // hoeveel er ooit getoond zijn
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
  S.sugOver=(S.sugOver||0)+1;                 // dom tellen: aangetikt
  S.suggesties.splice(i,1); S.checklist.push(it); draw();}
function addI(){const i=document.getElementById('wz-ni');const v=i.value.trim();if(!v)return;
  S.sugEigen=(S.sugEigen||0)+1;               // en zelf getypt — de eerlijke noemer
  S.checklist.push({tekst:v,skill:null,ok:false,reden:'added manually'});
  i.value=''; draw();}

// WIE KAN DIT OPPAKKEN. Gegrond, niet geraden: de match komt van de skills die een rol écht
// heeft, tegen de stap die de planner al een skill gaf. Er valt hier niets te fantaseren, dus
// werkt het ook zonder model — en zonder stappen-met-skill is de sectie gewoon leeg.
//
// Toewijzen gebruikt dezelfde routing als het werkoverleg (`route_werk`): een mens-vervulde rol
// krijgt het in zijn inbox, een AI-vervulde rol krijgt een project. Een AI-rol leest de NotifStore
// nooit, dus een bericht daarheen zou "verstuurd is kwijt" betekenen.
async function rollen(){
  const el=document.getElementById('wz-rollen'); if(!el)return;
  if(!S.rollenInit){
    S.rollenInit=true;
    el.innerHTML='<p class="wz-hint">✨ looking who has the skills…</p>';
    const r=await post('/wizard/rollen',{items:JSON.stringify(S.checklist)},AI_TIMEOUT_MS);
    S.rollen=(r&&r.rollen)||[]; S.rollenfout=(r&&r.__fout)||'';
  }
  drawRollen();
}
function drawRollen(){
  const el=document.getElementById('wz-rollen'); if(!el)return;
  const kaarten=S.rollen.map((r,i)=>`<div class="wz-item">
    <div class="wz-itxt"><strong>${esc(r.naam)}</strong>
      <span class="wz-hint">can do: ${esc((r.stappen||[]).join(' · '))}</span></div>
    <button type="button" class="wz-chip" onclick="taak(${i})">＋ add as task</button></div>`).join('');
  const leeg=S.rollen.length?'':`<p class="wz-hint">${S.rollenfout?('✨ '+esc(S.rollenfout)+' — ')
    :'No role has a matching skill for these steps — '}assign one yourself below.</p>`;
  const gekozen=S.taken.map((t,i)=>`<div class="wz-item"><div class="wz-itxt">→ ${esc(t.naam)}: ${esc(t.tekst)}</div>
    <button class="wz-rm" onclick="S.taken.splice(${i},1);drawRollen()">✕</button></div>`).join('');
  el.innerHTML=`${eigenaarBlok()}${leeg}${kaarten}
   <div class="wz-clab">Or assign a step yourself</div>
   <input id="wz-tt" placeholder="what should they do?">
   <div class="wz-add"><select id="wz-tr">${ROLEOPTS}</select>
     <button onclick="taakZelf()">＋ add</button></div>
   ${gekozen?`<div class="wz-clab">Tasks to hand out when you save</div>${gekozen}`:''}`;
}
/* DE OWNER-KIEZER. Alleen als de gekozen rol MEER DAN ÉÉN vervuller heeft: bij één staat hij al
   als default in S.trekker (onzichtbaar, want er valt niets te kiezen) en bij nul blijft "no owner".

   Hij staat BOVENAAN deze sectie en met zijn eigen kop, los van "Or assign a step yourself"
   eronder. Dat onderscheid is niet cosmetisch: dat tweede blok wijst een STAP toe aan een rol, dit
   zet de EIGENAAR van het project. Zonder de scheiding kiest iemand een stap-uitvoerder in de
   veronderstelling dat hij de eigenaar zet, en dan borgt het scherm stil de verkeerde intentie.

   "Owner" is bewust hetzelfde woord als op de projectkaart (views/projects.py, `<span class='dk'>
   Owner</span>`) — één term voor één ding. */
function eigenaarBlok(){
  const opties=VERVULLERS[S.role]||[];
  if(opties.length<2)return '';
  const rijen=opties.map(o=>`<option value="${esc(o.v)}"${S.trekker===o.v?' selected':''}>${esc(o.n)}</option>`).join('');
  return `<div class="wz-clab">Owner</div>
   <p class="wz-hint">This role has more than one person. Pick who owns the project, or leave it open.</p>
   <select id="wz-owner" onchange="S.trekker=this.value">
     <option value="">— no owner —</option>${rijen}</select>
   <div class="wz-clab">Hand out steps</div>`;
}
function taak(i){const r=S.rollen[i]; if(!r)return;
  S.taken.push({rol:r.rol,naam:r.naam,tekst:(r.stappen||[])[0]||''}); drawRollen();}
function taakZelf(){
  const t=document.getElementById('wz-tt'), sel=document.getElementById('wz-tr');
  const tekst=(t.value||'').trim(), rol=sel.value;
  if(!tekst||!rol||rol.indexOf('ii:')===0)return;      // een taak hoort bij een ROL, niet bij "geen rol"
  S.taken.push({rol:rol,naam:sel.selectedOptions[0].text,tekst:tekst});
  t.value=''; drawRollen();}

async function maak(){
  lees();
  if(!kanOpslaan())return;
  S.bezig=true; stelKnop();
  const b=document.getElementById('wz-save'); if(b)b.textContent='Putting it on the board…';
  // GEEN UITKOMST IS GEEN BLOKKADE: dan is je idee de uitkomst, en scherp je hem later aan.
  const r=await post('/wizard/create',{role:S.role,uitkomst:(S.uitkomst||S.ruw),
    trekker:S.trekker,tijd:S.tijd,missie:S.missie,business:S.business,nid:S.nid||'',
    items:JSON.stringify(S.checklist),taken:JSON.stringify(S.taken),
    sug_aan:String(S.sugAan||0),sug_over:String(S.sugOver||0),sug_eigen:String(S.sugEigen||0)});
  S.bezig=false;
  if(r&&r.url){S.klaar=r; if(window.__ovlDirty)window.__ovlDirty(); gereed();return;}
  if(b){b.disabled=false;b.textContent='Put on the board';}
  const h=document.getElementById('wz-aihint');
  if(h)h.textContent='⚠ '+((r&&(r.error||r.__fout))||'not saved — try again');
}
function gereed(){
  const r=S.klaar;
  const taken=(r.taken||[]).map(t=>`<div class="wz-item"><div class="wz-itxt">${esc(t.ref)}</div></div>`).join('');
  card().innerHTML=`<div class="wz-cheer"><div class="big">🎉</div><h2>On the board!</h2>
   <p class="wz-hint">${esc(r.titel||'')}</p></div>
   ${taken?`<div class="wz-clab">Handed out</div>${taken}`:''}
   <div class="wz-foot"><a class="wz-btn ghost" href="${esc(r.url)}">View on the board</a>
   <button class="wz-btn" onclick="restart()">Another project</button></div>`;
}
function restart(){Object.assign(S,{ruw:"",uitkomst:"",titel:"",checklist:[],planfout:"",tijd:"",
  missie:"",business:"",waarom:"",geschat:false,suggesties:[],sugBezig:false,checkInit:false,
  rollen:[],rollenInit:false,rollenfout:"",taken:[],trekker:"",bezig:false,klaar:null}); form();}

window.S=S;window.scherp=scherp;window.maak=maak;window.impact=impact;window.draw=draw;
window.addI=addI;window.restart=restart;window.stelKnop=stelKnop;window.checklist=checklist;
window.schat=schat;window.neem=neem;window.drawSug=drawSug;
window.rollen=rollen;window.drawRollen=drawRollen;window.taak=taak;window.taakZelf=taakZelf;
form();
})();
</script>
"""
