"""App-shell-fundament: de client-side swap-primitive zodat het document dat de callbar-iframe bezit
niet meer vervangen wordt bij een `.c2-main`-verversing → de LiveKit-call overleeft.

Dit is het FUNDAMENT, niet de volledige app-shell. Het levert:
- `window.shellSwap(url, opts)`: fetch de URL, ruim geregistreerde timers/listeners op (teardown),
  vervang `.c2-main`, werk `<title>` bij, her-evalueer de content-`<script>`s (rebind drag e.d.),
  scroll naar top + focus (nieuwe nav) of herstel niets (popstate).
- Gedelegeerde klik voor `.js-modal`/`.pcard` (één listener op `document`, overleeft elke swap) →
  de modal (`window.__shellOpenCard`, gezet door `_modal_html`). Vervangt de per-kaart-binding.
- Een op shell-entries gegate `popstate`-handler (dormant tot de link-interceptor 1a pushState gebruikt;
  laat de bestaande modal-history met rust).

De cleanup-REGISTRY (`window.registerSwapCleanup`) staat bewust in web_base._page (head), zodat
content-scripts hem al kennen wanneer ze draaien — hij is er dus vóór dit chrome-script. Zie
docs/ONTWERP_callbar_appshell.md. De globale `<a href>`-interceptor (1a) is een aparte scope."""
from __future__ import annotations


_SHELL_JS = r"""
(function(){
  var swapping=false;
  function runCleanups(){var a=window.__swapCleanups||[];
    for(var i=0;i<a.length;i++){try{a[i]();}catch(e){}}window.__swapCleanups=[];}
  // <script>-tags draaien niet bij replaceWith/innerHTML → opnieuw uitvoeren (rebind drag, herstart aardbol).
  function reinit(root){
    var scr=root.querySelectorAll('script');
    for(var i=0;i<scr.length;i++){var old=scr[i],s=document.createElement('script');
      if(old.src){s.src=old.src;}else{s.textContent=old.textContent;}
      old.parentNode.replaceChild(s,old);}
  }
  window.shellSwap=function(url,opts){
    opts=opts||{};
    if(swapping)return Promise.resolve();
    swapping=true;
    return fetch(url,{credentials:'same-origin'}).then(function(r){return r.text();}).then(function(h){
      var doc=new DOMParser().parseFromString(h,'text/html');
      var fresh=doc.querySelector('.c2-main'),live=document.querySelector('.c2-main');
      if(!fresh||!live){swapping=false;location.href=url;return;}       // geen .c2-main → veilige full nav
      runCleanups();                                                    // teardown timers/listeners VÓÓR de swap
      live.replaceWith(fresh);
      if(doc.title){document.title=doc.title;}
      reinit(fresh);                                                    // her-eval content-scripts
      if(opts.push){history.pushState({shell:1,url:url},'',url);}
      if(!opts.pop){window.scrollTo(0,0);var h1=document.querySelector('.c2-main h1');
        if(h1){h1.setAttribute('tabindex','-1');try{h1.focus({preventScroll:true});}catch(e){}}}
      swapping=false;
    }).catch(function(){swapping=false;location.href=url;});             // fout → veilige fallback
  };
  // popstate alleen op shell-gepushte entries (laat de modal-history met rust). Dormant tot 1a pusht.
  window.addEventListener('popstate',function(e){
    if(e.state&&e.state.shell){window.shellSwap(location.href,{push:false,pop:true});}
  });
  try{history.scrollRestoration='manual';}catch(e){}
  // Gedelegeerde klik: .js-modal/.pcard BUITEN de modal → openCard. Eén listener, overleeft elke swap.
  document.addEventListener('click',function(e){
    if(window.__pdrag)return;                                          // niet openen tijdens een drag
    var t=e.target,a=(t&&t.closest)?t.closest('a.js-modal[data-href],.pcard[data-href]'):null;
    if(!a||a.closest('#ovl')||!window.__shellOpenCard)return;          // in-modal of geen modal → laat lopen
    e.preventDefault();window.__shellOpenCard(a.getAttribute('data-href'));
  });
})();
"""


def _shell_chrome() -> str:
    """Globale shell-JS (op elke cockpit-pagina, geïnjecteerd door cockpit2._send naast de Noochie-rail
    en de callbar-iframe). Zie module-docstring. De registry-stub leeft apart in web_base._page (head)."""
    return "<script>" + _SHELL_JS + "</script>"
