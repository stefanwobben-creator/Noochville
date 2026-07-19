"""Staging-view (/kennisbank/staging?batch=…) — "even nakijken" vóór de bibliotheek.

Toont de voorgestelde atomen uit één bron, bewerkbaar, met samenvoegen en weggooien.
Pas op "Voeg set toe aan bibliotheek" landen ze append-only in notes.json. Herkend brontype
staat bovenaan (verklaarbaar). Hergebruikt de kn-/kern-klassen; geen nieuwe machinerie zichtbaar.
"""
from __future__ import annotations

from nooch_village.web_base import _e, _page, _banner, _field
from nooch_village.cockpit2_util import _DS_LINK, _nav
from nooch_village.kennisbank_intake import SUBJECTS

_PROV = ("peer_reviewed", "certificate", "internal_data", "survey", "expert_opinion",
         "media", "advocacy", "internal_judgment", "unknown")


def _hid(csrf: str, action: str, nxt: str, extra: dict | None = None) -> str:
    h = (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
         f"<input type='hidden' name='action' value='{_e(action)}'>"
         f"<input type='hidden' name='next' value='{_e(nxt)}'>")
    for k, v in (extra or {}).items():
        h += f"<input type='hidden' name='{_e(k)}' value='{_e(v)}'>"
    return h


def _mece_hint(st, b: dict, a: dict, csrf: str, nxt: str) -> str:
    """MECE-bewaking in de review: lijkt dit voorstel op een bestaand kaartje, toon dat mét
    een koppel-knop ("dit is hetzelfde inzicht, andere bron") zodat de bibliotheek geen
    tweede kaartje krijgt. Exact gelijke claims worden bij commit sowieso gestapeld; deze
    hint vangt de GELIJKENDE gevallen — en daar beslist de mens. Deterministisch, geen LLM."""
    try:
        gelijk = st.notes.gelijkende(a.get("content") or "")
    except Exception:
        return ""
    if gelijk is None:
        return ""
    atom_id, claim, _score = gelijk
    kort = claim if len(claim) <= 140 else claim[:137] + "…"
    knop = ""
    if csrf:
        knop = (f"<form method='post' action='/action' class='kn-mece-koppel'>"
                f"{_hid(csrf, 'kb_stage_koppel', nxt, {'bid': b['id'], 'sid': a['sid'], 'doel': atom_id})}"
                f"<button class='btn' title='geen tweede kaartje: dit voorstel wordt een extra "
                f"bron onder het bestaande kaartje'>🔗 koppel als extra bron</button></form>")
    return (f"<div class='kn-mece'>≈ <span class='muted'>lijkt op bestaand kaartje:</span> "
            f"{_e(kort)} {knop}</div>")


def _atoom_kaartje(st, b: dict, a: dict, csrf: str, nxt: str) -> str:
    """Eén voorgesteld atoom: bewerkbaar (content/onderwerp/provenance) + aanvinken + weggooien."""
    sid = a["sid"]
    subj_opts = "<option value=''>— geen onderwerp —</option>" + "".join(
        f"<option value='{_e(s)}'{' selected' if a.get('subject') == s else ''}>{_e(s)}</option>"
        for s in SUBJECTS)
    prov_opts = "".join(
        f"<option value='{_e(p)}'{' selected' if a.get('provenance') == p else ''}>{_e(p)}</option>"
        for p in _PROV)
    body = (f"<details class='kn-nctrl'><summary>samengestelde inhoud</summary>"
            f"<div class='kn-ann'>{_e(a['body']).replace(chr(10), '<br>')}</div></details>"
            if (a.get("body") or "").strip() else "")
    # Herkomst zichtbaar in de review: bron ("project: <scope>" bij de rapport-lus) + reference.
    # Een INTERNE reference (bijv. "/project?id=<pid>") wordt klikbaar, zodat de reviewer het
    # bronproject naast de voorstellen kan openleggen; externe citaties (DOI/ISBN) blijven tekst.
    ref = a.get("reference") or ""
    ref_html = (f" · <a href='{_e(ref)}'>{_e(ref)}</a>" if ref.startswith("/")
                else (f" · {_e(ref)}" if ref else ""))
    bron = "bron: " + _e(a['source']) + ref_html
    # Verticale stapel-kaart op volle breedte (fix-brief bug 1): een grid met een
    # middenkolom minmax(0,1fr) zodat lange onbreekbare strings (URL-slugs) de kaart nooit
    # naar ~0 breedte kunnen persen. ⠿-handle links (drag&drop-merge, zelfde interactie als
    # de statements-lijst), inhoud+controls midden, × rechts.
    handle = ("<span class='kn-handle' draggable='true' "
              "title='sleep op een ander voorstel om te mergen'>⠿</span>" if csrf
              else "<span></span>")
    return (
        f"<div class='kn-stage' data-sid='{_e(sid)}'>"
        f"{handle}"
        f"<form method='post' action='/action' class='kn-stage-edit'>"
        f"{_hid(csrf, 'kb_stage_edit', nxt, {'bid': b['id'], 'sid': sid})}"
        f"<textarea name='content' rows='2'>{_e(a['content'])}</textarea>{body}"
        f"<span class='kn-stage-src'>{bron}</span>"
        f"<div class='kn-stage-ctrls'><select name='subject'>{subj_opts}</select>"
        f"<select name='provenance'>{prov_opts}</select>"
        f"<button class='btn'>Bewaar</button></div></form>"
        f"<form method='post' action='/action' class='kn-stage-del'>"
        f"{_hid(csrf, 'kb_stage_delete', nxt, {'bid': b['id'], 'sid': sid})}"
        f"<button class='btn' title='weggooien'>×</button></form>"
        f"{_mece_hint(st, b, a, csrf, nxt)}</div>")


def render_kennisbank_staging(st, bid: str, csrf_token: str = "", msg: str = "") -> str:
    b = st.staging.get(bid)
    if b is None:
        inner = (f"{_DS_LINK}<div class='c2-wrap'><div class='c2-main'>"
                 f"<p class='muted'>Deze staging-set is er niet (meer). "
                 f"<a href='/kennisbank'>← terug</a></p></div></div>")
        return _page("Even nakijken", inner)
    nxt = f"/kennisbank/staging?batch={bid}"
    atomen = b.get("atoms") or []
    kaartjes = "".join(_atoom_kaartje(st, b, a, csrf_token, nxt) for a in atomen) or (
        "<p class='muted'>Geen atomen meer in deze set.</p>")
    tab = " <span class='chip muted'>tabeldata</span>" if b.get("tabular") else ""

    commit = (f"<form method='post' action='/action'>"
              f"{_hid(csrf_token, 'kb_stage_commit', '/kennisbank', {'bid': bid})}"
              f"<button class='btn ok'>Voeg set toe aan bibliotheek ({len(atomen)})</button></form>"
              f"<form method='post' action='/action'>"
              f"{_hid(csrf_token, 'kb_stage_discard', '/kennisbank', {'bid': bid})}"
              f"<button class='btn'>Gooi de hele set weg</button></form>")

    main = (f"<div class='c2-main'><div class='c2-bar'><a href='/kennisbank'>← wat Nooch weet</a></div>"
            f"<h1>Even nakijken</h1>"
            f"<p class='muted'>Herkend als <b>{_e(b.get('kind'))}</b>{tab} · bron "
            f"<b>{_e(b.get('source_label'))}</b>. Bewerk, sleep het ene voorstel op het "
            f"andere om te mergen, of gooi weg. Pas op “Voeg set toe” landen ze in de "
            f"bibliotheek.</p>{_banner(msg)}"
            f"{kaartjes}<div class='kn-sec'>{commit}</div>"
            f"{_stg_merge_modal(bid, csrf_token, nxt)}</div>")
    inner = (f"{_DS_LINK}{_nav()}"
             f"<div class='c2-wrap'>{main}</div>{_STG_DRAG_JS if csrf_token else ''}")
    return _page("Even nakijken", inner)


def _stg_merge_modal(bid: str, csrf: str, nxt: str) -> str:
    """De merge-modal, dezelfde interactie als de statements-lijst: na een drop kies je met
    een radio welke tekst de hoofdtekst wordt (of je past hem aan in het tekstveld), en de
    twee voorstellen worden één samengestelde kaart (kb_stage_merge: gekozen tekst = kop,
    beide originelen bewaard in de samengestelde inhoud). Zonder csrf niets te slepen."""
    if not csrf:
        return ""
    return (
        f"<div class='kn-overlay' id='kn-overlay' hidden></div>"
        f"<div class='kn-modal' id='kn-modal' hidden role='dialog' aria-modal='true' "
        f"aria-labelledby='kn-modaltitel'>"
        f"<h2 id='kn-modaltitel'>Voorstellen mergen</h2>"
        f"<p class='muted'>Kies welke tekst de hoofdtekst wordt (beide originelen blijven "
        f"bewaard in de samengestelde inhoud; bron en herkomst reizen mee).</p>"
        f"<form method='post' action='/action' id='kn-mergeform'>"
        f"{_hid(csrf, 'kb_stage_merge', nxt, {'bid': bid})}"
        f"<input type='hidden' name='sid' value=''>"
        f"<input type='hidden' name='sid' value=''>"
        f"<label class='kn-opt on' id='kn-opta' for='f-kn-keuze-a'>"
        f"<input type='radio' name='keuze' value='a' id='f-kn-keuze-a' checked>"
        f"<span></span></label>"
        f"<label class='kn-opt' id='kn-optb' for='f-kn-keuze-b'>"
        f"<input type='radio' name='keuze' value='b' id='f-kn-keuze-b'>"
        f"<span></span></label>"
        f"{_field('eventueel nog aanpassen', 'kop', kind='textarea', fid='f-kn-mergetekst')}"
        f"<div class='kn-modalbtns'>"
        f"<button type='button' class='btn' id='kn-mergecancel'>annuleer</button>"
        f"<button class='btn ok'>merge → één kaart</button></div></form></div>")


_STG_DRAG_JS = """<script>(function(){
 // ⠿ drag & drop mergen — zelfde interactie als de statements-lijst, maar dan op de
 // staging-voorstellen (.kn-stage, data-sid; de tekst leeft in de content-textarea).
 var dragSrc=null;
 function kaartVan(e){return e.target&&e.target.closest?e.target.closest('.kn-stage'):null;}
 document.addEventListener('dragstart',function(e){
   if(!(e.target.closest&&e.target.closest('.kn-handle')))return;
   var s=kaartVan(e); if(!s)return;
   dragSrc=s.dataset.sid; s.classList.add('dragging');
   e.dataTransfer.effectAllowed='move';
   try{e.dataTransfer.setData('text/plain',dragSrc);}catch(_){}
 });
 document.addEventListener('dragend',function(){
   dragSrc=null;
   document.querySelectorAll('.kn-stage.dragging,.kn-stage.dragover').forEach(function(x){
     x.classList.remove('dragging','dragover');});
 });
 document.addEventListener('dragover',function(e){
   var s=kaartVan(e);
   if(s&&dragSrc&&s.dataset.sid!==dragSrc){e.preventDefault();s.classList.add('dragover');}
 });
 document.addEventListener('dragleave',function(e){
   var s=kaartVan(e); if(s)s.classList.remove('dragover');
 });
 document.addEventListener('drop',function(e){
   var s=kaartVan(e); if(!s||!dragSrc)return;
   e.preventDefault(); s.classList.remove('dragover');
   if(s.dataset.sid!==dragSrc) openMerge(dragSrc,s.dataset.sid);
 });
 var modal=document.getElementById('kn-modal'), overlay=document.getElementById('kn-overlay');
 function tekstVan(sid){
   var el=document.querySelector('.kn-stage[data-sid="'+sid+'"] textarea[name=content]');
   return el?el.value.trim():'';
 }
 function kies(a){
   var oa=document.getElementById('kn-opta'), ob=document.getElementById('kn-optb');
   oa.classList.toggle('on',a); ob.classList.toggle('on',!a);
   document.getElementById('f-kn-keuze-'+(a?'a':'b')).checked=true;
   document.getElementById('f-kn-mergetekst').value=(a?oa:ob).querySelector('span').textContent;
 }
 function openMerge(srcSid,tgtSid){
   if(!modal)return;
   var f=document.getElementById('kn-mergeform');
   var sids=f.querySelectorAll('[name=sid]');
   sids[0].value=srcSid; sids[1].value=tgtSid;
   document.getElementById('kn-opta').querySelector('span').textContent=tekstVan(srcSid);
   document.getElementById('kn-optb').querySelector('span').textContent=tekstVan(tgtSid);
   kies(true);
   overlay.hidden=false; modal.hidden=false;
 }
 function sluitModal(){ if(modal){overlay.hidden=true; modal.hidden=true;} }
 if(modal){
   document.getElementById('kn-opta').addEventListener('click',function(){kies(true);});
   document.getElementById('kn-optb').addEventListener('click',function(){kies(false);});
   document.getElementById('kn-mergecancel').addEventListener('click',sluitModal);
   overlay.addEventListener('click',sluitModal);
   document.addEventListener('keydown',function(e){if(e.key==='Escape')sluitModal();});
 }
})();</script>"""
