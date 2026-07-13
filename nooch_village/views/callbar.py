"""Dorp-brede LiveKit call bar — draait in een same-origin **iframe** (`/callbar`) onder aan élke
cockpit-pagina, naast de Noochie-rail. De iframe isoleert de LiveKit-realm in een eigen document met
eigen tokens/CSS; de parent bevat GEEN LiveKit-code (alleen de iframe + een dunne glue: postMessage-
toast met origin-check + de `.has-callbar`-klasse).

⚠ KOSTENBEWUST — lazy connect. De bar verbindt NIET automatisch met de dorp-room. Op page-load haalt-ie
alleen een token op (bevestigt dat LiveKit geconfigureerd is) en pollt `/livekit-presence` om te tonen
of er een gesprek gaande is. Een echte WebRTC-verbinding (en dus LiveKit-deelnemer-minuten) ontstaat
PAS bij 'Join gesprek', en 'Verlaten' koppelt écht los (`room.disconnect`). Zo kost een open tabblad
zonder gesprek nul minuten. (Vroeger verbond iedereen zich meteen als stille toeschouwer — dat slurpte
de gratis WebRTC-minuten leeg zonder dat er ook maar gebeld werd.)

Twee states:
- **Niet-verbonden** (default): geen WebRTC-verbinding. Presence-hint via poll ("🟢 N in gesprek"),
  camera-voorkeur-toggle + "Join gesprek" (of "Start gesprek" als er nog niemand is). Kost geen minuten.
- **Deelnemer** (na Join): room.connect + mic aan + camera volgens voorkeur + audio; eigen tile vooraan
  (--green-dark rand), muten van jezelf/een ander. Verlaten = room.disconnect → terug naar poll-only.

Multi-tab (elke tab = eigen iframe): identity = `<server-base>#tab-<sessionStorage-id>`, uniek per tab.
Dubbel-join-preventie via BroadcastChannel ('callbar'): de tab die deelnemer wordt roept dat om; andere
tabs van dezelfde base tonen een subtiele hint ("je neemt deel in een ander tabblad") i.p.v. de Join-
knop. Sluit die tab (pagehide → leave + disconnect) dan komt Join direct terug; crasht die tab dan
vervalt de claim na 15s zonder heartbeat en keert Join VANZELF terug (visibilitychange/focus-check omdat
een achtergrondtab de interval throttlet). Geen observers meer → geen ghost-stapeling van verbindingen.

De "beeld zonder geluid"-bug blijft geborgd op de Join-gesture: (1) audio-render-container die remote
audio pas áán de DOM hangt zodra je deelnemer bent, (2) startAudio() op de Join-gesture, (3) mic-publish-
verificatie (console.info).

Reuse: web_base._CSS (tokens + .btn), .switch (camera-voorkeur). Toast: postMessage → parent .c2-toast."""
from __future__ import annotations

from nooch_village.web_base import _CSS, _FONTS


# ── CSS die alleen de bar (in de iframe) nodig heeft. web_base._CSS levert de tokens (incl --neon) +
#    .btn/.btn.ok/.btn.no; hieronder alleen de transparante body-override, .switch (bron: cockpit2_util)
#    en de bar-eigen .c2-callbar/.cb-*. Geen inline styles. ──────────────────────────────────────────
_CALLBAR_CSS = """
html,body{background:transparent;margin:0;padding:0;max-width:none;height:100%;overflow:hidden}
.switch{display:inline-block;width:34px;height:19px;flex:none;border:none;padding:0;border-radius:var(--radius-pill);background:var(--border);position:relative;cursor:pointer;vertical-align:middle;transition:background .15s}
.switch::after{content:'';position:absolute;top:2px;left:2px;width:15px;height:15px;border-radius:50%;background:var(--surface);transition:left .15s}
.switch.on{background:var(--green)}
.switch.on::after{left:17px}
.switch-field{display:inline-flex;align-items:center;gap:.5rem;font-size:12.5px;color:var(--muted);border:none;background:transparent;cursor:pointer;font:inherit}
.c2-callbar{display:flex;align-items:center;gap:12px;padding:0 18px;height:100%;background:rgba(255,255,255,.93);backdrop-filter:blur(8px);border-top:1px solid var(--border)}
.cb-tiles{display:flex;gap:10px;align-items:center;min-width:0;overflow-x:auto}
.cb-spacer{flex:1}
.cb-controls{display:flex;gap:10px;align-items:center;flex:none}
.cb-hint{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--gray)}
.cb-elsewhere{color:var(--muted);font-style:italic}
.cb-tile{position:relative;width:56px;height:56px;border-radius:14px;overflow:hidden;box-shadow:0 0 0 1px var(--border);user-select:none;transition:box-shadow .18s ease,transform .12s ease,opacity .2s ease}
.cb-tile.cb-click{cursor:pointer}
.cb-tile.cb-click:hover{transform:translateY(-2px)}
.cb-tile.self{box-shadow:0 0 0 2px var(--green-dark)}
.cb-tile.speaking,.cb-tile.self.speaking{box-shadow:0 0 0 3px var(--neon),0 0 16px rgba(43,255,111,.65);animation:cb-pulse 1.3s ease-in-out infinite}
@keyframes cb-pulse{0%,100%{box-shadow:0 0 0 3px var(--neon),0 0 10px rgba(43,255,111,.5)}50%{box-shadow:0 0 0 3px var(--neon),0 0 22px rgba(43,255,111,.85)}}
@media(prefers-reduced-motion:reduce){.cb-tile.speaking,.cb-tile.self.speaking{animation:none}}
.cb-face{width:100%;height:100%;object-fit:cover;display:block;background:#2c2a25}
.cb-initials{width:100%;height:100%;display:flex;align-items:center;justify-content:center;background:#44443f;color:#fff;font-weight:800;font-size:16px;letter-spacing:.5px}
.cb-mute-badge{position:absolute;top:3px;right:3px;width:17px;height:17px;border-radius:50%;background:var(--coral);color:#fff;font-size:9px;display:flex;align-items:center;justify-content:center;box-shadow:0 1px 3px rgba(0,0,0,.25);pointer-events:none}
.cb-hovername{position:absolute;bottom:2px;left:2px;right:2px;background:rgba(0,0,0,.55);color:#fff;font-size:9.5px;font-weight:700;text-align:center;border-radius:8px;padding:2px 0;opacity:0;transition:opacity .15s ease;pointer-events:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cb-tile:hover .cb-hovername{opacity:1}
"""


_CALLBAR_JS = r"""
(function(){
  var CSRF='__CSRF__';
  // Tab-suffix: uniek per tab, stabiel over same-tab navigatie/reload (sessionStorage).
  var TAB=(function(){try{var t=sessionStorage.getItem('cb-tab');
    if(!t){t=Math.random().toString(36).slice(2,10);sessionStorage.setItem('cb-tab',t);}return t;}
    catch(e){return 'nostore';}})();
  var LKURL=null,TOKEN=null,MYID=null,MYBASE=null;
  var room=null,joined=false,camPref=true;
  var speaking={};                 // full-identity -> true
  var audioMap={};                 // trackSid -> <audio>
  var bc=null,otherTab=null;       // BroadcastChannel + {tab,ts} van een deelnemende tab van dezelfde base
  var HB=2500,EXPIRE=15000;        // claim-verval na 15s zonder heartbeat (crash) → Join komt vanzelf terug
  var POLL=12000;                  // presence-poll interval (alleen NIET-verbonden + tab zichtbaar)
  var presence={count:0};
  var pollTimer=null;
  var bar=document.getElementById('c2-callbar');
  var tilesEl=document.getElementById('cb-tiles');
  var hintEl=document.getElementById('cb-hint');
  var ctlEl=document.getElementById('cb-controls');
  var audioEl=document.getElementById('cb-audio');
  var ORIGIN=location.origin;
  if(!bar){return;}

  function LK(){return window.LivekitClient;}
  function esc(s){return (s==null?'':String(s));}
  function initials(n){return esc(n).trim().slice(0,2).toUpperCase()||'?';}
  function baseOf(id){var i=String(id||'').indexOf('#tab-');return i>=0?String(id).slice(0,i):String(id);}
  function isPart(p){return !!((p.audioTrackPublications&&p.audioTrackPublications.size>0)||
                               (p.videoTrackPublications&&p.videoTrackPublications.size>0));}
  function pName(p){return p.name||baseOf(p.identity);}
  function toast(t){try{window.parent.postMessage({type:'cb-toast',text:String(t).slice(0,120)},ORIGIN);}catch(e){}}

  // ── init: token halen (bevestigt configuratie + levert token voor LATER). GEEN auto-connect: de
  //    dorp-room verbindt PAS bij 'Join gesprek'. Zo kost een open tabblad nul WebRTC-minuten. De
  //    "wie is er in gesprek"-awareness loopt via een goedkope server-poll (/livekit-presence). ──
  fetch('/livekit-token?tab='+encodeURIComponent(TAB))
    .then(function(r){return r.json().then(function(d){return {ok:r.ok,d:d};});})
    .then(function(res){
      if(!res.ok||!res.d||!res.d.token||!res.d.server_url){return;}   // niet geconfigureerd → verborgen
      TOKEN=res.d.token;LKURL=res.d.server_url;MYID=res.d.identity;MYBASE=baseOf(MYID);
      try{window.parent.postMessage({type:'cb-ready'},ORIGIN);}catch(e){}   // parent: toon iframe + .has-callbar
      setupBC();
      loadSdk(function(){});          // SDK vast voorladen zodat Join meteen kan verbinden
      startPolling();                 // presence via poll i.p.v. een eigen (betaalde) toeschouwer-verbinding
      render();
    }).catch(function(){});

  function setupBC(){
    try{bc=new BroadcastChannel('callbar');}catch(e){bc=null;}
    if(!bc)return;
    bc.onmessage=function(ev){var m=ev.data||{};
      if(m.base!==MYBASE||m.tab===TAB)return;              // alleen ANDERE tabs van DEZELFDE gebruiker
      if(m.type==='join'||m.type==='alive'){otherTab={tab:m.tab,ts:Date.now()};updateControls();}
      else if(m.type==='leave'){if(otherTab&&otherTab.tab===m.tab){otherTab=null;updateControls();}}
    };
    setInterval(function(){
      if(joined)bcSend('alive');                           // heartbeat zolang wij deelnemen
      checkClaim();
    },HB);
    document.addEventListener('visibilitychange',function(){
      if(document.hidden){stopPolling();}else{onVisible();}});
    window.addEventListener('focus',onVisible);
    // deze tab sluit/navigeert: laat andere tabs los EN koppel onze eigen verbinding echt af
    window.addEventListener('pagehide',function(){
      if(joined){bcSend('leave');try{room&&room.disconnect();}catch(e){}}});
  }
  function checkClaim(){if(otherTab&&Date.now()-otherTab.ts>EXPIRE){otherTab=null;updateControls();}}
  function onVisible(){if(joined)bcSend('alive');checkClaim();if(!joined)startPolling();}
  function bcSend(type){if(bc){try{bc.postMessage({type:type,base:MYBASE,tab:TAB});}catch(e){}}}

  // ── presence: goedkope server-poll i.p.v. een eigen WebRTC-verbinding ──
  function startPolling(){
    if(joined||document.hidden||!LKURL)return;
    stopPolling();pollPresence();pollTimer=setInterval(pollPresence,POLL);
  }
  function stopPolling(){if(pollTimer){clearInterval(pollTimer);pollTimer=null;}}
  function pollPresence(){
    if(joined){stopPolling();return;}
    fetch('/livekit-presence').then(function(r){return r.json();}).then(function(d){
      presence={count:(d&&d.count)||0};if(!joined)render();
    }).catch(function(){});
  }

  function loadSdk(cb){
    if(window.LivekitClient){cb();return;}
    var s=document.getElementById('lk-sdk');
    if(s){s.addEventListener('load',cb);return;}
    s=document.createElement('script');s.id='lk-sdk';s.src='/static/livekit-client.umd.min.js';
    s.addEventListener('load',cb);document.head.appendChild(s);
  }

  // connect wordt UITSLUITEND vanuit joinCall aangeroepen (nooit meer op page-load)
  function connect(after){
    var C=LK();if(!C){toast('videolaag nog niet geladen, probeer zo weer');return;}
    var ev=C.RoomEvent;
    room=new C.Room({adaptiveStream:true,dynacast:true});
    [ev.ParticipantConnected,ev.ParticipantDisconnected,ev.TrackSubscribed,ev.TrackUnsubscribed,
     ev.TrackMuted,ev.TrackUnmuted,ev.LocalTrackPublished,ev.LocalTrackUnpublished]
      .forEach(function(e){room.on(e,render);});
    room.on(ev.TrackSubscribed,function(track){if(track.kind===C.Track.Kind.Audio)renderAudio();});
    room.on(ev.TrackUnsubscribed,function(track){try{track.detach();}catch(e){}renderAudio();});
    room.on(ev.ActiveSpeakersChanged,function(sps){speaking={};
      sps.forEach(function(p){speaking[p.identity]=true;});render();});
    room.on(ev.AudioPlaybackStatusChanged,function(){updateControls();});
    room.on(ev.Disconnected,function(){cleanupRoom();});
    room.on(ev.DataReceived,function(payload,participant,kind,topic){
      if(topic!=='mute')return;
      try{var m=JSON.parse(new TextDecoder().decode(payload));
        toast(esc(m.by)+' heeft '+esc(m.who)+(m.muted?' gemute':' ge-unmute'));}catch(e){}
    });
    try{room.prepareConnection&&room.prepareConnection(LKURL,TOKEN);}catch(e){}
    room.connect(LKURL,TOKEN,{autoSubscribe:true}).then(function(){if(after)after();render();})
      .catch(function(e){console.error('[callbar] connect faalde',e);toast('verbinden niet gelukt');cleanupRoom();});
  }

  // volledig loskoppelen → terug naar poll-only (en de minuten stoppen)
  function cleanupRoom(){
    joined=false;
    Object.keys(audioMap).forEach(function(sid){try{audioMap[sid].remove();}catch(e){}});audioMap={};
    room=null;speaking={};
    startPolling();render();
  }

  // remote audio pas áán de DOM als je DEELNEMER bent (er zijn geen observers meer; de guard blijft)
  function renderAudio(){
    if(!room||!joined)return;
    room.remoteParticipants.forEach(function(p){p.audioTrackPublications.forEach(function(pub){
      if(pub.track&&!audioMap[pub.trackSid]){var el=pub.track.attach();audioEl.appendChild(el);audioMap[pub.trackSid]=el;}
    });});
  }

  // Dedup: één tile per base-identity; representant = de deelnemende sessie als die er is.
  function groupByBase(){
    var all=[];room.remoteParticipants.forEach(function(p){all.push(p);});all.push(room.localParticipant);
    var by={},order=[];
    all.forEach(function(p){var b=baseOf(p.identity);
      if(!(b in by)){by[b]=p;order.push(b);}
      else if(isPart(p)&&!isPart(by[b])){by[b]=p;}});
    return order.map(function(b){return by[b];});
  }

  function tileFor(rep){
    var C=LK();
    var isSelf=baseOf(rep.identity)===MYBASE;
    var camPub=rep.getTrackPublication(C.Track.Source.Camera);
    var camOn=!!(camPub&&camPub.track&&!camPub.isMuted);
    var micPub=rep.getTrackPublication(C.Track.Source.Microphone);
    var micMuted=!(micPub&&!micPub.isMuted);
    var el=document.createElement('div');
    el.className='cb-tile'+(isSelf?' self':'')+(speaking[rep.identity]?' speaking':'')+(joined?' cb-click':'');
    if(camOn){var v=camPub.track.attach();v.className='cb-face';v.muted=true;v.setAttribute('playsinline','');el.appendChild(v);}
    else{var d=document.createElement('div');d.className='cb-initials';d.textContent=initials(pName(rep));el.appendChild(d);}
    if(micMuted){var b=document.createElement('div');b.className='cb-mute-badge';b.textContent='🔇';el.appendChild(b);}
    var nm=esc(pName(rep))+(isSelf?' (jij)':'');
    el.title=nm+(joined&&!isSelf?' · klik om te '+(micMuted?'unmuten':'muten'):'');
    var hn=document.createElement('div');hn.className='cb-hovername';hn.textContent=nm;el.appendChild(hn);
    if(joined){el.addEventListener('click',function(){
      if(isSelf){toggleSelfMic();}else{muteOther(rep,!micMuted);}});}
    return el;
  }

  function render(){
    if(joined&&room){
      tilesEl.innerHTML='';
      groupByBase().forEach(function(rep){tilesEl.appendChild(tileFor(rep));});
      hintEl.textContent='';
    } else {
      tilesEl.innerHTML='';
      hintEl.textContent=presence.count>0
        ? '🟢 '+presence.count+(presence.count===1?' iemand in gesprek':' mensen in gesprek')
        : '';
    }
    updateControls();
  }

  function updateControls(){
    if(!LKURL){ctlEl.innerHTML='';return;}
    var h='';
    if(!joined){
      if(otherTab){
        // Subtiele status-hint, GEEN uitgegrijsde knop: zodra de andere tab sluit (leave) of z'n
        // heartbeat 15s wegblijft, vervalt otherTab en keert Join vanzelf terug.
        h+='<span class="cb-hint cb-elsewhere" title="De Join-knop komt terug zodra dat tabblad sluit">🎧 je neemt deel in een ander tabblad</span>';
      } else {
        h+='<button type="button" class="switch-field cb-camtoggle" title="Kies of je met camera joint">'
          +'<span>🎥 met camera</span><span class="switch'+(camPref?' on':'')+'"></span></button>';
        h+='<button type="button" class="btn ok cb-join">'+(presence.count>0?'Join gesprek':'Start gesprek')+'</button>';
      }
    } else {
      var mic=room.localParticipant.isMicrophoneEnabled;
      var cam=room.localParticipant.isCameraEnabled;
      h+='<button type="button" class="btn'+(mic?'':' no')+' cb-mic" title="'
        +(mic?'Je mic staat aan · klik om te muten':'Je staat op mute · klik om te unmuten')+'">'
        +(mic?'🎙️ Mute':'🔇 Unmute')+'</button>';
      h+='<button type="button" class="btn cb-icon cb-cam" title="'+(cam?'Camera uitzetten':'Camera aanzetten')+'">'
        +(cam?'🎥':'🚫')+'</button>';
      h+='<button type="button" class="btn cb-icon cb-leave" title="Gesprek verlaten">✕</button>';
      if(room.canPlaybackAudio===false){
        h+='<button type="button" class="btn no cb-audio-on">🔈 klik om geluid aan te zetten</button>';
      }
    }
    ctlEl.innerHTML=h;wireControls();
  }

  function wireControls(){
    var q=function(c){return ctlEl.querySelector(c);};
    var j=q('.cb-join');if(j)j.addEventListener('click',joinCall);
    var ct=q('.cb-camtoggle');if(ct)ct.addEventListener('click',function(){camPref=!camPref;updateControls();});
    var mc=q('.cb-mic');if(mc)mc.addEventListener('click',toggleSelfMic);
    var cm=q('.cb-cam');if(cm)cm.addEventListener('click',toggleSelfCam);
    var lv=q('.cb-leave');if(lv)lv.addEventListener('click',leaveCall);
    var ao=q('.cb-audio-on');if(ao)ao.addEventListener('click',function(){room.startAudio().then(updateControls).catch(function(){});});
  }

  // ── join: verbind NU pas met de dorp-room, dan mic/cam publiceren ──
  function joinCall(){
    if(otherTab||joined)return;                            // dubbel-join-preventie
    joined=true;stopPolling();bcSend('join');updateControls();
    var publish=function(){
      room.localParticipant.setMicrophoneEnabled(true).then(function(){
        var pubs=room.localParticipant.audioTrackPublications;
        console.info('[callbar] mic gepubliceerd:',!!(pubs&&pubs.size>0));render();   // bug #3
      }).catch(function(e){console.error('[callbar] mic publiceren faalde',e);});
      if(camPref){room.localParticipant.setCameraEnabled(true).then(render).catch(function(){});}
      renderAudio();
      if(room.canPlaybackAudio===false){room.startAudio().catch(function(){});}       // bug #2
      toast('Je doet mee met het gesprek'+(camPref?'':' · camera uit'));render();
    };
    if(room){publish();}else{connect(publish);}            // verbind pas op deze gesture
  }

  // ── leave: ECHT loskoppelen (i.t.t. vroeger, toen de verbinding bleef staan) → minuten stoppen ──
  function leaveCall(){
    var r=room;joined=false;bcSend('leave');
    try{r&&r.disconnect();}catch(e){}                       // Disconnected-event → cleanupRoom
    cleanupRoom();
    toast('Je bent uit het gesprek · verbinding gesloten');
  }

  function toggleSelfMic(){
    if(!joined||!room)return;
    var on=room.localParticipant.isMicrophoneEnabled;
    room.localParticipant.setMicrophoneEnabled(!on).then(render).catch(function(){});
    toast(on?'Je hebt jezelf gemute':'Je microfoon staat aan');
  }
  function toggleSelfCam(){
    if(!joined||!room)return;
    var on=room.localParticipant.isCameraEnabled;
    room.localParticipant.setCameraEnabled(!on).then(render).catch(function(){});
    toast(on?'Camera uit':'Camera aan');
  }

  function muteOther(rep,mute){
    if(!joined)return;
    var body=new URLSearchParams();
    body.set('action','lk_mute');body.set('csrf',CSRF);body.set('identity',rep.identity);body.set('muted',mute?'1':'0');
    fetch('/action',{method:'POST',body:body}).then(function(r){return r.text();}).then(function(){
      publishMute(pName(rep),mute);
      toast('Je hebt '+esc(pName(rep))+(mute?' gemute':' ge-unmute'));
    }).catch(function(){toast('muten niet gelukt');});
  }
  function publishMute(who,mute){
    if(!room||!joined)return;
    try{var payload=new TextEncoder().encode(JSON.stringify({by:room.localParticipant.name||'Iemand',who:who,muted:mute}));
      room.localParticipant.publishData(payload,{reliable:true,topic:'mute'});}catch(e){}
  }
})();
"""


def render_callbar(csrf_token: str = "") -> str:
    """Standalone `/callbar`-pagina (de body van de iframe): eigen <html>, eigen tokens (via web_base._CSS),
    transparante achtergrond. Bevat de bar-markup + de LiveKit-IIFE. csrf ingebed voor de mute-POST."""
    head = (f'<!doctype html><html lang="nl"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>call bar</title>{_FONTS}<style>{_CSS}{_CALLBAR_CSS}</style></head>')
    body = ("<body>"
            "<div id='c2-callbar' class='c2-callbar'>"
            "<div id='cb-tiles' class='cb-tiles'></div>"
            "<div id='cb-hint' class='cb-hint'></div>"
            "<div class='cb-spacer'></div>"
            "<div id='cb-controls' class='cb-controls'></div></div>"
            "<div id='cb-audio' hidden></div>"
            "<script>" + _CALLBAR_JS.replace("__CSRF__", csrf_token) + "</script></body></html>")
    return head + body


def _callbar_frame() -> str:
    """De iframe + dunne parent-glue (GEEN LiveKit-code): toont de iframe + zet .has-callbar zodra de
    iframe 'cb-ready' meldt, en rendert mute-toasts (.c2-toast) uit postMessage — met een strikte
    origin+source-check. De iframe start `hidden` zodat een niet-geconfigureerde bar geen clicks vangt."""
    frame = ("<iframe src='/callbar' id='cb-frame' class='cb-frame' title='NoochVille call bar' "
             "allow='camera; microphone' hidden></iframe>")
    glue = ("<script>(function(){var f=document.getElementById('cb-frame');"
            "window.addEventListener('message',function(e){"
            "if(e.origin!==location.origin||!f||e.source!==f.contentWindow)return;"   # strikte origin+source-check
            "var m=e.data||{};"
            "if(m.type==='cb-ready'){f.hidden=false;document.body.classList.add('has-callbar');}"
            "else if(m.type==='cb-toast'&&m.text){var d=document.createElement('div');d.className='c2-toast';"
            "d.textContent=String(m.text).slice(0,120);document.body.appendChild(d);"
            "setTimeout(function(){d.classList.add('show');},10);"
            "setTimeout(function(){d.classList.remove('show');},2600);"
            "setTimeout(function(){d.remove();},3000);}"
            "});})();</script>")
    return frame + glue
