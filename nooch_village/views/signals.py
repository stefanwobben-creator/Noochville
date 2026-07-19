"""Signals — dé centrale trechter van de library: hier komt álles binnen.

De radar verhuisde van de rol-pagina's naar deze ene plek (founder, 19 jul): bovenaan de
wachtrij (status 'wacht', alle feeds, ✓/✗), daaronder de goedgekeurde signalen. Vanaf hier
promoveer je naar de kennisbank: één signaal via "→ kenniskaartje", of meerdere tegelijk via
de selectievakjes — beide landen in dezelfde Even-nakijken-set (staging), waar de bron gelezen
en geatomiseerd is en je kunt bewerken, mergen of weggooien vóór er kaartjes ontstaan.

Read-only aggregatie via RadarStore (all_pending/all_approved) — geen nieuwe opslag.
Hergebruik: web_base (_e/_page), cockpit2_util (_DS_LINK/_name/_nav) en .rdr-*/.kn-*-stijl."""
from __future__ import annotations

from nooch_village.web_base import _e, _page
from nooch_village.cockpit2_util import _DS_LINK, _name, _nav

_KIND = {"kaart": "🃏 signaal", "seed": "🌱 kiem", "doelwit": "🎯 doelwit", "concurrent": "🏁 concurrent"}


def _sig_date(s: str) -> str:
    s = (s or "").strip()
    return s[:10] if s else ""


def radar_promote_ctl(it: dict, csrf: str, nxt: str) -> str:
    """Promotie-control op een GOEDGEKEURD radar-signaal: knop '→ kenniskaartje' zolang het
    niet gepromoveerd is (POST /action, actie radar_promote; leidt naar de Even-nakijken-set),
    daarna een chip '→ in kennisbank' die via het bestaande zoekpad (tag 'signal') naar de
    bibliotheek linkt. Geen csrf en niet gepromoveerd → niets."""
    if it.get("promoted_atom_id"):
        return ("<a class='chip rdr-inkb' href='/kennisbank?q=signal' "
                "title='dit signaal is al een kenniskaartje'>→ in kennisbank</a>")
    if not csrf:
        return ""
    return (f"<form method='post' action='/action' class='cl-rep rdr-promoteform'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
            f"<input type='hidden' name='rid' value='{_e(it.get('id', ''))}'>"
            f"<input type='hidden' name='next' value='{_e(nxt)}'>"
            f"<button class='rdr-promote' type='submit' name='action' value='radar_promote' "
            f"title='lees de bron en zet voorstellen klaar bij Even nakijken (daarna in Oracle)'>"
            f"→ Oracle</button></form>")


def _sig_body(st, it) -> str:
    """De gedeelde kern van een signaal-kaart: content, rationale en meta-regel."""
    orec = st.records.get(it.get("role", ""))
    rolenaam = _name(orec) if orec else it.get("role", "")
    kind = it.get("kind", "")
    # Het generieke type verzwijgen we: álles op deze pagina is een signaal. Alleen de
    # betekenisvolle soorten (kiem/doelwit/concurrent) houden hun chip.
    klabel = "" if kind in ("", "kaart") else _KIND.get(kind, kind)
    pub = _sig_date(it.get("published_at", ""))
    src = (it.get("source") or "").strip()
    link = (it.get("link") or "").strip()
    bron = (f"<a href='{_e(link)}' target='_blank' rel='noopener'>{_e(src or 'bron')}</a>"
            if link else _e(src))
    rat = (it.get("rationale") or "").strip()
    meta = " · ".join(x for x in (
        (f"<span class='chip muted'>{_e(klabel)}</span>" if klabel else ""),
        (f"<span class='chip muted'>📅 {_e(pub)}</span>" if pub else ""),
        (f"<span class='chip'>{_e(it.get('feed', ''))}</span>" if it.get("feed") else ""),
        f"<span class='muted'>via {_e(rolenaam)}</span>",
        bron) if x)
    return (f"<div class='rdr-body'>"
            f"<div class='rdr-sig'>{_e(it.get('content', ''))}</div>"
            + (f"<div class='muted rdr-rat'>{_e(rat)}</div>" if rat else "")
            + f"<div class='rdr-meta'>{meta}</div></div>")


def _wachtrij_card(st, it, csrf: str, nxt: str) -> str:
    """Eén wachtend signaal in de centrale wachtrij: ✓ (relevant → goedgekeurd) en
    ✗ (wegklikken). Zonder csrf alleen-lezen."""
    body = _sig_body(st, it)
    if not csrf:
        return f"<div class='rdr-row'>{body}</div>"
    ctl = (f"<form method='post' action='/action' class='cl-rep'>"
           f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
           f"<input type='hidden' name='rid' value='{_e(it['id'])}'>"
           f"<input type='hidden' name='next' value='{_e(nxt)}'>"
           f"<button class='cl-check ok' type='submit' name='action' value='radar_approve' "
           f"title='relevant — naar de goedgekeurde lijst'>✓</button>"
           f"<button class='cl-check no' type='submit' name='action' value='radar_dismiss' "
           f"title='niet relevant — wegklikken'>✗</button></form>")
    return f"<div class='rdr-row'>{ctl}{body}</div>"


def _signal_card(st, it, csrf: str = "", nxt: str = "/signals") -> str:
    """Eén te verwerken signaal: ⠿-handle (sleep op een ander signaal om te mergen),
    selectievakje (multi-promotie), promotie-control en een ✗ om het alsnog te verwijderen —
    de lijst is een inbox en hoort naar nul te kunnen."""
    weg = handle = ""
    actief = bool(csrf) and not it.get("promoted_atom_id")
    if actief:
        handle = ("<span class='kn-handle' draggable='true' "
                  "title='sleep op een ander signaal om te mergen'>⠿</span>")
        weg = (f"<form method='post' action='/action' class='rdr-wegform'>"
               f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
               f"<input type='hidden' name='rid' value='{_e(it.get('id', ''))}'>"
               f"<input type='hidden' name='next' value='{_e(nxt)}'>"
               f"<button class='rdr-weg' type='submit' name='action' value='radar_dismiss' "
               f"title='toch niet relevant — verwijderen'>✗</button></form>")
    ctl = radar_promote_ctl(it, csrf, nxt)
    rid_attr = f" data-rid='{_e(it.get('id', ''))}'" if actief else ""
    extra = len(it.get("merged_sources") or [])
    plus = (f"<span class='chip muted' title='herkomst van eerder samengevoegde signalen "
            f"reist mee'>+{extra} bron{'nen' if extra != 1 else ''}</span>" if extra else "")
    return (f"<div class='rdr-row rdr-arch'{rid_attr}>{handle}{ctl}"
            f"{_sig_body(st, it)}{_kb_hint(st, it, csrf, nxt)}{plus}{weg}</div>")


def _kb_hint(st, it, csrf: str, nxt: str) -> str:
    """MECE op de inbox zelf: staat dit signaal (vrijwel) al in de kennisbank, zeg dat er
    dan bij — met één knop om de herkomst te koppelen aan het bestaande kaartje, waarna
    het signaal verwerkt is en uit de lijst verdwijnt. Deterministisch, geen LLM."""
    if it.get("promoted_atom_id"):
        return ""
    content = (it.get("content") or "").strip()
    source = ((it.get("source") or "").strip() or (it.get("feed") or "").strip() or "radar")
    link = (it.get("link") or "").strip()
    try:
        from nooch_village.radar_promote import find_duplicate
        doel = find_duplicate(st.notes, content, source, link) or st.notes.find_claim_equal(content)
        if doel is not None:
            kaart = st.notes.get(doel)
            label = "al in Oracle"
            kort = (kaart.claim if kaart else "")[:120]
        else:
            g = st.notes.gelijkende(content)
            if g is None:
                return ""
            doel, kort, _score = g
            label = "lijkt op een bestaand signal"
            kort = kort[:120]
    except Exception:
        return ""
    knop = ""
    if csrf:
        knop = (f"<form method='post' action='/action' class='kn-mece-koppel'>"
                f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
                f"<input type='hidden' name='action' value='radar_koppel'>"
                f"<input type='hidden' name='next' value='{_e(nxt)}'>"
                f"<input type='hidden' name='rid' value='{_e(it.get('id', ''))}'>"
                f"<input type='hidden' name='doel' value='{_e(doel)}'>"
                f"<button class='btn' title='geen tweede kaartje: dit signaal wordt een "
                f"extra bron onder het bestaande kaartje en is daarmee verwerkt'>"
                f"🔗 koppel herkomst</button></form>")
    return (f"<div class='kn-mece'>≈ <span class='muted'>{label}:</span> {_e(kort)} "
            f"{knop}</div>")


def _merge_modal(csrf: str, nxt: str) -> str:
    """De merge-modal, zelfde interactie als de statements-lijst en de staging-review: na
    een drop kies je welke tekst de hoofdtekst wordt (of je past hem aan) en de twee
    signalen worden er één (radar_merge; de herkomst van allebei reist mee)."""
    if not csrf:
        return ""
    return (
        f"<div class='kn-overlay' id='kn-overlay' hidden></div>"
        f"<div class='kn-modal' id='kn-modal' hidden role='dialog' aria-modal='true' "
        f"aria-labelledby='kn-modaltitel'>"
        f"<h2 id='kn-modaltitel'>Signalen mergen</h2>"
        f"<p class='muted'>Kies welke tekst de hoofdtekst wordt; de bronnen van allebei "
        f"blijven bewaard en stapelen straks mee op het signal in Oracle.</p>"
        f"<form method='post' action='/action' id='kn-mergeform'>"
        f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
        f"<input type='hidden' name='action' value='radar_merge'>"
        f"<input type='hidden' name='next' value='{_e(nxt)}'>"
        f"<input type='hidden' name='target_rid' value=''>"
        f"<input type='hidden' name='source_rid' value=''>"
        f"<label class='kn-opt on' id='kn-opta' for='f-kn-keuze-a'>"
        f"<input type='radio' name='keuze' value='a' id='f-kn-keuze-a' checked>"
        f"<span></span></label>"
        f"<label class='kn-opt' id='kn-optb' for='f-kn-keuze-b'>"
        f"<input type='radio' name='keuze' value='b' id='f-kn-keuze-b'>"
        f"<span></span></label>"
        f"<label for='f-kn-mergetekst'>eventueel nog aanpassen</label>"
        f"<textarea name='tekst' id='f-kn-mergetekst'></textarea>"
        f"<div class='kn-modalbtns'>"
        f"<button type='button' class='btn' id='kn-mergecancel'>annuleer</button>"
        f"<button class='btn ok'>merge → één signaal</button></div></form></div>")


_MERGE_JS = """<script>(function(){
 var dragSrc=null;
 function kaartVan(e){return e.target&&e.target.closest?e.target.closest('.rdr-row[data-rid]'):null;}
 document.addEventListener('dragstart',function(e){
   if(!(e.target.closest&&e.target.closest('.kn-handle')))return;
   var s=kaartVan(e); if(!s)return;
   dragSrc=s.dataset.rid; s.classList.add('dragging');
   e.dataTransfer.effectAllowed='move';
   try{e.dataTransfer.setData('text/plain',dragSrc);}catch(_){}
 });
 document.addEventListener('dragend',function(){
   dragSrc=null;
   document.querySelectorAll('.rdr-row.dragging,.rdr-row.dragover').forEach(function(x){
     x.classList.remove('dragging','dragover');});
 });
 document.addEventListener('dragover',function(e){
   var s=kaartVan(e);
   if(s&&dragSrc&&s.dataset.rid!==dragSrc){e.preventDefault();s.classList.add('dragover');}
 });
 document.addEventListener('dragleave',function(e){
   var s=kaartVan(e); if(s)s.classList.remove('dragover');
 });
 document.addEventListener('drop',function(e){
   var s=kaartVan(e); if(!s||!dragSrc)return;
   e.preventDefault(); s.classList.remove('dragover');
   if(s.dataset.rid!==dragSrc) openMerge(dragSrc,s.dataset.rid);
 });
 var modal=document.getElementById('kn-modal'), overlay=document.getElementById('kn-overlay');
 function tekstVan(rid){
   var el=document.querySelector('.rdr-row[data-rid="'+rid+'"] .rdr-sig');
   return el?el.textContent.trim():'';
 }
 function kies(a){
   var oa=document.getElementById('kn-opta'), ob=document.getElementById('kn-optb');
   oa.classList.toggle('on',a); ob.classList.toggle('on',!a);
   document.getElementById('f-kn-keuze-'+(a?'a':'b')).checked=true;
   document.getElementById('f-kn-mergetekst').value=(a?oa:ob).querySelector('span').textContent;
 }
 function openMerge(srcRid,tgtRid){
   if(!modal)return;
   var f=document.getElementById('kn-mergeform');
   f.querySelector('[name=target_rid]').value=tgtRid;
   f.querySelector('[name=source_rid]').value=srcRid;
   document.getElementById('kn-opta').querySelector('span').textContent=tekstVan(srcRid);
   document.getElementById('kn-optb').querySelector('span').textContent=tekstVan(tgtRid);
   kies(false);
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


_VG_OVERLAY = (
    "<div class='kn-overlay' id='rdr-bezig' hidden>"
    "<div class='kn-modal kn-vgmodal'><h2>📖 De bron wordt gelezen</h2>"
    "<div class='kn-vgbaan'><div class='kn-vgbalk'></div></div>"
    "<p class='muted'>Artikel ophalen, in voorstellen knippen, herkomst eraan… daarna "
    "kijk jij ze na bij Even nakijken.</p></div></div>"
    "<script>(function(){var o=document.getElementById('rdr-bezig');if(!o)return;"
    "function toon(){o.removeAttribute('hidden');}"
    "var i,fs=document.querySelectorAll('.rdr-promoteform');"
    "for(i=0;i<fs.length;i++){fs[i].addEventListener('submit',toon);}"
    "})();</script>")


def _bron_knop(csrf: str) -> str:
    """＋ Bron toevoegen, uitklapbaar (founder, 19 jul): dezelfde intake als bij Oracle
    (plak een link/notitie of kies een bestand → atomiser → Even nakijken), maar dan hier,
    waar je toch al aan het verwerken bent. Hergebruik van het Oracle-paneel, inclusief de
    voortgangsbalk."""
    if not csrf:
        return ""
    from nooch_village.views.kennisbank import _bron_toevoegen
    return (f"<details class='kn-bronvorm rdr-bronvorm'><summary class='btn ok'>"
            f"＋ Bron toevoegen</summary>"
            f"<div class='card kn-capture'>{_bron_toevoegen(csrf)}</div></details>")


def render_signals(st, csrf_token: str = "", feed: str = "") -> str:
    """De /signals-pagina: centrale wachtrij bovenaan, dan de goedgekeurde signalen
    (nieuwste eerst), optioneel gefilterd op feed."""
    nxt = "/signals" + (f"?feed={feed}" if feed else "")
    wachtend = st.radar.all_pending()
    alle = st.radar.all_approved()
    # Gepromoveerde signalen zijn kenniskaartjes geworden — signalen zijn de wachtkamer,
    # niet het archief (founder, 18/19 jul): eenmaal verwerkt verdwijnen ze hier restloos.
    items = [it for it in alle if not it.get("promoted_atom_id")]
    # Feed-chips uit de CONFIGURATIE, niet uit wat er toevallig staat (founder, 19 jul):
    # een nieuw aangesloten feed hoort hier meteen zichtbaar te zijn, ook als hij nog
    # leeg is. Feeds die alleen in oude data voorkomen (hernoemd/verdwenen) blijven erbij.
    from nooch_village.radar_store import load_feeds
    feeds = [f.get("label") or f.get("env") or "" for f in load_feeds(st.dd)]
    for extra in sorted({it.get("feed", "") for it in (items + wachtend) if it.get("feed")}):
        if extra not in feeds:
            feeds.append(extra)
    feeds = [f for f in feeds if f]
    if feed:
        items = [it for it in items if it.get("feed") == feed]
        wachtend = [it for it in wachtend if it.get("feed") == feed]
    chips = ""
    if feeds:
        opts = [("", "alle")] + [(f, f) for f in feeds]
        chips = ("<div class='c2-sec'>" + "".join(
            f"<a class='chip-opt{(' on' if feed == val else '')}' "
            f"href='/signals{('?feed=' + _e(val)) if val else ''}'>{_e(lbl)}</a>"
            for val, lbl in opts) + "</div>")
    # ── wachtrij (centraal: alle feeds, alle rollen); leeg → onzichtbaar ─────
    wacht = ""
    if wachtend:
        wacht = (f"<div class='rdr-sub'>Wachtrij <span class='muted'>· {len(wachtend)} nieuw "
                 f"signaal{'en' if len(wachtend) != 1 else ''}, jij bepaalt wat relevant is"
                 f"</span></div>"
                 f"<div class='rdr-tool'>"
                 + "".join(_wachtrij_card(st, it, csrf_token, nxt) for it in wachtend)
                 + "</div>")
    body = ("".join(_signal_card(st, it, csrf_token, nxt) for it in items) if items
            else "<p class='muted'>🎉 Nul — niets meer te verwerken. Wat je in de wachtrij "
                 "goedkeurt verschijnt hier.</p>")
    main = (f"<div class='c2-main'><div class='c2-bar'><a href='/'>← home</a></div>"
            f"<h1>Signalen <span class='chip'>library</span></h1>"
            f"{_bron_knop(csrf_token)}"
            f"<p class='muted'>Hier komt alles binnen. Sleep signalen op elkaar om te "
            f"mergen, stuur ze door naar Oracle of verwijder ze — werk naar nul.</p>"
            f"{chips}"
            f"{wacht}"
            f"<div class='rdr-sub'>Te verwerken <span class='muted'>· {len(items)} — sleep om "
            f"te mergen, promoveer of verwijder; net als je mailbox is nul het doel</span></div>"
            f"<div class='rdr-tool'>{body}</div>"
            f"{_merge_modal(csrf_token, nxt)}"
            f"{_VG_OVERLAY if csrf_token else ''}</div>")
    inner = (f"{_DS_LINK}"
             f"{_nav()}"
             f"<div class='c2-wrap'>{main}</div>{_MERGE_JS if csrf_token else ''}")
    return _page("Signalen", inner)
