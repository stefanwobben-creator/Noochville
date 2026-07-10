"""Dorp-brede LiveKit call bar — globale chrome onder aan élke cockpit-pagina (naast de Noochie-rail).

Twee states:
- **Toeschouwer** (default bij elke pagina-load): auto-connect naar de dorp-room `village`, video-tracks
  gesubscribed maar GEEN audio-playback (je hoort niets), tiles gedempt en niet klikbaar. De bar toont
  een camera-voorkeur-toggle + "Join gesprek". Geen permissie-popups bij binnenkomst (geen mic/cam).
- **Deelnemer** (na Join): mic aan + camera volgens voorkeur, audio-playback aan. Eigen tile vooraan
  (--green-dark rand). Muten van jezelf (eigen tile of mic-knop) en van een ander (klik op tile →
  server-side mute voor iedereen). Verlaten = mic+cam unpublishen + audio uit, NIET disconnecten.

De bekende "beeld zonder geluid"-bug wordt op drie plekken geborgd (zie de JS-commentaren):
  (1) audio-render-container die remote audio pas áán DOM hangt zodra je deelnemer bent,
  (2) startAudio() op de Join-klik (de user-gesture) + AudioPlaybackStatusChanged-handler met een
      "klik om geluid aan te zetten"-knop, (3) een expliciete mic-publish-verificatie (console.info).

CSS leeft in cockpit2_util._EXTRA_CSS (.c2-callbar/.cb-*); de --neon-token in web_base. Reuse:
.btn/.btn.ok/.btn.no (controls), .switch (camera-voorkeur), .c2-toast (mute-melding)."""
from __future__ import annotations


_CALLBAR_JS = r"""
(function(){
  var CSRF='__CSRF__';
  var LKURL=null, TOKEN=null, MYID=null;
  var room=null, joined=false, camPref=true;
  var speaking={};                 // identity -> true (actieve sprekers)
  var audioMap={};                 // trackSid -> <audio> element (alleen als deelnemer)
  var bar=document.getElementById('c2-callbar');
  var tilesEl=document.getElementById('cb-tiles');
  var hintEl=document.getElementById('cb-hint');
  var ctlEl=document.getElementById('cb-controls');
  var audioEl=document.getElementById('cb-audio');
  if(!bar){return;}

  function LK(){return window.LivekitClient;}
  function esc(s){return (s==null?'':String(s));}
  function initials(n){return esc(n).trim().slice(0,2).toUpperCase()||'?';}
  function myName(){return (room&&room.localParticipant&&room.localParticipant.name)||'Iemand';}

  function toast(t){var d=document.createElement('div');d.className='c2-toast';d.textContent=t;
    document.body.appendChild(d);setTimeout(function(){d.classList.add('show');},10);
    setTimeout(function(){d.classList.remove('show');},2600);setTimeout(function(){d.remove();},3000);}

  // ── init: token halen; zonder LIVEKIT_URL (503) blijft de bar verborgen ──────────────────────
  fetch('/livekit-token').then(function(r){return r.json().then(function(d){return {ok:r.ok,d:d};});})
    .then(function(res){
      if(!res.ok||!res.d||!res.d.token||!res.d.server_url){return;}   // niet geconfigureerd → geen bar
      TOKEN=res.d.token; LKURL=res.d.server_url; MYID=res.d.identity;
      document.body.classList.add('has-callbar','cb-observer');
      bar.hidden=false;
      loadSdk(connect);
    }).catch(function(){});

  function loadSdk(cb){
    if(window.LivekitClient){cb();return;}
    var s=document.getElementById('lk-sdk');
    if(s){s.addEventListener('load',cb);return;}
    s=document.createElement('script');s.id='lk-sdk';s.src='/static/livekit-client.umd.min.js';
    s.addEventListener('load',cb);document.head.appendChild(s);
  }

  function connect(){
    var C=LK(); var ev=C.RoomEvent;
    room=new C.Room({adaptiveStream:true,dynacast:true});
    [ev.ParticipantConnected,ev.ParticipantDisconnected,ev.TrackSubscribed,ev.TrackUnsubscribed,
     ev.TrackMuted,ev.TrackUnmuted,ev.LocalTrackPublished,ev.LocalTrackUnpublished]
      .forEach(function(e){room.on(e,render);});
    room.on(ev.TrackSubscribed,function(track){if(track.kind===C.Track.Kind.Audio)renderAudio();});
    room.on(ev.TrackUnsubscribed,function(track){try{track.detach();}catch(e){}renderAudio();});
    room.on(ev.ActiveSpeakersChanged,function(sps){speaking={};
      sps.forEach(function(p){speaking[p.identity]=true;});render();});
    room.on(ev.AudioPlaybackStatusChanged,function(){updateControls();});
    room.on(ev.DataReceived,function(payload,participant,kind,topic){
      if(topic!=='mute')return;
      try{var m=JSON.parse(new TextDecoder().decode(payload));
        toast(esc(m.by)+' heeft '+esc(m.who)+(m.muted?' gemute':' ge-unmute'));}catch(e){}
    });
    try{room.prepareConnection&&room.prepareConnection(LKURL,TOKEN);}catch(e){}
    room.connect(LKURL,TOKEN,{autoSubscribe:true}).then(render)
      .catch(function(e){console.error('[callbar] connect faalde',e);bar.hidden=true;
        document.body.classList.remove('has-callbar','cb-observer');});
  }

  // ── audio-render (RoomAudioRenderer-equivalent): remote audio pas áán de DOM als je DEELNEMER bent;
  //    observer hoort dus niets. Bij verlaten worden de tracks losgekoppeld (playback stopt). ────────
  function renderAudio(){
    if(!room)return;
    if(joined){
      room.remoteParticipants.forEach(function(p){
        p.audioTrackPublications.forEach(function(pub){
          if(pub.track&&!audioMap[pub.trackSid]){
            var el=pub.track.attach();audioEl.appendChild(el);audioMap[pub.trackSid]=el;}
        });
      });
    } else {
      room.remoteParticipants.forEach(function(p){p.audioTrackPublications.forEach(function(pub){
        if(pub.track){try{pub.track.detach();}catch(e){}}});});
      Object.keys(audioMap).forEach(function(sid){try{audioMap[sid].remove();}catch(e){}});
      audioMap={};
    }
  }

  function tileFor(p,isSelf){
    var C=LK();
    var camPub=p.getTrackPublication(C.Track.Source.Camera);
    var camOn=!!(camPub&&camPub.track&&!camPub.isMuted);
    var micPub=p.getTrackPublication(C.Track.Source.Microphone);
    var micMuted=!(micPub&&!micPub.isMuted);
    var el=document.createElement('div');
    el.className='cb-tile'+(isSelf?' self':'')+(speaking[p.identity]?' speaking':'')+(joined?' cb-click':'');
    if(camOn){var v=camPub.track.attach();v.className='cb-face';v.muted=true;v.setAttribute('playsinline','');el.appendChild(v);}
    else{var d=document.createElement('div');d.className='cb-initials';d.textContent=initials(p.name||p.identity);el.appendChild(d);}
    if(micMuted){var b=document.createElement('div');b.className='cb-mute-badge';b.textContent='🔇';el.appendChild(b);}
    var nm=esc(p.name||p.identity)+(isSelf?' (jij)':'');
    el.title=nm+(joined&&!isSelf?' · klik om te '+(micMuted?'unmuten':'muten'):'');
    var hn=document.createElement('div');hn.className='cb-hovername';hn.textContent=nm;el.appendChild(hn);
    if(joined){el.addEventListener('click',function(){
      if(isSelf){toggleSelfMic();}else{muteOther(p,!micMuted);}});}
    return el;
  }

  function render(){
    if(!room)return;
    tilesEl.innerHTML='';
    if(joined){tilesEl.appendChild(tileFor(room.localParticipant,true));}
    var remotes=[];room.remoteParticipants.forEach(function(p){remotes.push(p);});
    remotes.forEach(function(p){tilesEl.appendChild(tileFor(p,false));});
    hintEl.textContent=(!joined&&remotes.length)?'🔇 Gesprek gaande · je luistert niet mee':'';
    updateControls();
  }

  function updateControls(){
    if(!room){ctlEl.innerHTML='';return;}
    var mic=room.localParticipant.isMicrophoneEnabled;
    var cam=room.localParticipant.isCameraEnabled;
    var h='';
    if(!joined){
      h+='<button type="button" class="switch-field cb-camtoggle" title="Kies of je met camera joint">'
        +'<span>🎥 met camera</span><span class="switch'+(camPref?' on':'')+'"></span></button>';
      h+='<button type="button" class="btn ok cb-join">Join gesprek</button>';
    } else {
      h+='<button type="button" class="btn'+(mic?'':' no')+' cb-mic" title="'
        +(mic?'Je mic staat aan · klik om te muten':'Je staat op mute · klik om te unmuten')+'">'
        +(mic?'🎙️ Mute':'🔇 Unmute')+'</button>';
      h+='<button type="button" class="btn cb-icon cb-cam" title="'+(cam?'Camera uitzetten':'Camera aanzetten')+'">'
        +(cam?'🎥':'🚫')+'</button>';
      h+='<button type="button" class="btn cb-icon cb-leave" title="Gesprek verlaten">✕</button>';
    }
    // Bekende bug (geluid geblokkeerd tot user-gesture): toon een aanzet-knop zodra playback faalt.
    if(joined&&room.canPlaybackAudio===false){
      h+='<button type="button" class="btn no cb-audio-on">🔈 klik om geluid aan te zetten</button>';
    }
    ctlEl.innerHTML=h;
    wireControls();
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

  function joinCall(){
    if(!room)return;
    joined=true;document.body.classList.remove('cb-observer');
    // mic ALTIJD publiceren + verifiëren (bekende bug #3: beeld zonder geluid door niet-gepubliceerde mic)
    room.localParticipant.setMicrophoneEnabled(true).then(function(){
      var pubs=room.localParticipant.audioTrackPublications;
      console.info('[callbar] mic gepubliceerd:',!!(pubs&&pubs.size>0));render();
    }).catch(function(e){console.error('[callbar] mic publiceren faalde',e);});
    if(camPref){room.localParticipant.setCameraEnabled(true).then(render).catch(function(){});}
    // audio-playback áán met de Join-klik als user-gesture (bekende bug #2)
    renderAudio();
    if(room.canPlaybackAudio===false){room.startAudio().catch(function(){});}
    toast('Je doet mee met het gesprek'+(camPref?'':' · camera uit'));render();
  }

  function leaveCall(){
    if(!room)return;
    joined=false;document.body.classList.add('cb-observer');
    try{room.localParticipant.setMicrophoneEnabled(false);}catch(e){}
    try{room.localParticipant.setCameraEnabled(false);}catch(e){}
    renderAudio();                                   // detacht remote audio → playback stopt
    toast('Je bent uit het gesprek gestapt · verbinding blijft');render();
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

  function muteOther(p,mute){
    if(!joined)return;                               // alleen deelnemers muten anderen (client-state-check)
    var body=new URLSearchParams();
    body.set('action','lk_mute');body.set('csrf',CSRF);
    body.set('identity',p.identity);body.set('muted',mute?'1':'0');
    fetch('/action',{method:'POST',body:body}).then(function(r){return r.text();}).then(function(){
      publishMute(p.name||p.identity,mute);
      toast('Je hebt '+esc(p.name||p.identity)+(mute?' gemute':' ge-unmute'));
    }).catch(function(){toast('muten niet gelukt');});
  }
  function publishMute(who,mute){
    if(!room||!joined)return;
    try{var payload=new TextEncoder().encode(JSON.stringify({by:myName(),who:who,muted:mute}));
      room.localParticipant.publishData(payload,{reliable:true,topic:'mute'});}catch(e){}
  }
})();
"""


def _callbar_chrome(csrf_token: str = "") -> str:
    """Globale call bar-chrome (op elke cockpit-pagina, geïnjecteerd door cockpit2._send naast de
    Noochie-rail). Start verborgen; de JS onthult 'm alleen als LiveKit geconfigureerd is (token ok)."""
    bar = ("<div id='c2-callbar' class='c2-callbar' hidden>"
           "<div id='cb-tiles' class='cb-tiles'></div>"
           "<div id='cb-hint' class='cb-hint'></div>"
           "<div class='cb-spacer'></div>"
           "<div id='cb-controls' class='cb-controls'></div></div>"
           "<div id='cb-audio' hidden></div>")
    js = "<script>" + _CALLBAR_JS.replace("__CSRF__", csrf_token) + "</script>"
    return bar + js
