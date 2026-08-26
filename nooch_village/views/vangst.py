"""Vangst — punten vangen tijdens een overleg, verwerken doe je later.

Het probleem dat dit wegneemt: het bestaande spanningsscherm dwingt je een punt meteen te
formaliseren — type kiezen, kaart invullen, velden die verplicht zijn. Tijdens een overleg kan dat
niet, dus wordt er níets genoteerd. Een punt dat nooit is vastgelegd bestaat niet, hoe goed het
verwerk-scherm erna ook is.

**Vangen is niet verwerken.** Bij het vangen gebeurt er precies één ding: de zin wordt opgeslagen,
met wie hem inbracht en wanneer. Geen model, geen typering, geen kaart. De bevinding-schrijver en de
typering draaien pas bij het VERWERKEN, en dan langs exact dezelfde haak en typer als elke andere
verse spanning — `NotifStore.add` zonder type, en `spanning_ontstaat` doet de rest.

**Waar het punt landt.** De vangst schrijft in de persistente werkoverleg-backlog van de cirkel
(`backlog_add`) — er hoeft geen overleg open te staan, en bij het eerstvolgende overleg komt het punt
vanzelf op de agenda. De lijst hier leest backlog én agenda, want voor wie het scherm leest is dat
hetzelfde punt.

Vormgeving: geen nieuwe klasse en geen inline style. Hergebruikt letterlijk:
`.rov-add` (het één-regel-toevoegformulier van het werkoverleg), `.rdr-row`/`.rdr-body`/`.rdr-act`
(de inbox-lijst), `<details class='wo-ocd box-details'>` + `.wo-oc` (de uitkomst-uitklap van het
werkoverleg) en de pagina-frame-klassen (`.c2-wrap`, `.c2-main`, `.c2-bar`, `.c2-sec`, `.ptitle`,
`.chip`, `.muted`).
"""
from __future__ import annotations

from nooch_village import org
from nooch_village.cockpit2_util import _DS_LINK, _name, _nav, _stamp
from nooch_village.web_base import _banner, _e, _field, _page

# De drie routes die een gevangen punt uit kan. Alle drie bestaan al; hier wordt er niets nieuws
# gebouwd, alleen naartoe verwezen.
UITKOMSTEN = ("spanning", "project", "actie")


def _hid(csrf: str, circle: str, nxt: str, **velden) -> str:
    rijen = [f"<input type='hidden' name='csrf' value='{_e(csrf)}'>",
             f"<input type='hidden' name='circle' value='{_e(circle)}'>",
             f"<input type='hidden' name='next' value='{_e(nxt)}'>"]
    rijen += [f"<input type='hidden' name='{_e(k)}' value='{_e(v)}'>" for k, v in velden.items()]
    return "".join(rijen)


def _rollen(st, circle: str) -> list:
    return sorted(org.roles_of(st.records.all(), circle), key=lambda r: _name(r).lower())


def _rol_opties(st, circle: str, selected: str = "") -> str:
    return "".join(
        f"<option value='{_e(r.id)}'{' selected' if r.id == selected else ''}>{_e(_name(r))}</option>"
        for r in _rollen(st, circle))


def _project_opties(st, circle: str) -> str:
    """Projecten onder deze cirkel, gegroepeerd per rol — zelfde vorm als de werkoverleg-triage."""
    nodes = {circle} | {r.id for r in _rollen(st, circle)}
    per_rol: dict = {}
    for p in st.projects.all():
        if p.get("owner") in nodes and not p.get("archived"):
            per_rol.setdefault(p["owner"], []).append(p)
    uit = ""
    for rid in sorted(per_rol, key=lambda x: (_name(st.records.get(x)) if st.records.get(x) else x).lower()):
        rn = _name(st.records.get(rid)) if st.records.get(rid) else rid
        opts = "".join(f"<option value='{_e(p['id'])}'>{_e(str(p.get('scope') or p['id'])[:60])}</option>"
                       for p in per_rol[rid])
        uit += f"<optgroup label='{_e(rn)}'>{opts}</optgroup>"
    return uit


def _vang_form(circle: str, csrf: str, nxt: str) -> str:
    """Het altijd-zichtbare veld. Eén regel, één toets.

    `autofocus` is hier geen sier maar de hele functie: na het opslaan herlaadt de pagina, en zonder
    autofocus zou je voor élk volgend punt de muis moeten pakken. Drie punten achter elkaar typen
    moet kunnen zonder je handen van het toetsenbord te halen."""
    return (f"<form method='post' action='/action' class='rov-add' id='vang-form' "
            f"data-frag='/vangst?circle={_e(circle)}&frag=1'>"
            f"{_hid(csrf, circle, nxt)}"
            f"<input id='vang-input' name='punt' placeholder='+ point — type and press Enter' "
            f"autocomplete='off' autofocus aria-label='new point' maxlength='140'>"
            f"<button class='btn ok sm' type='submit' name='action' value='vangst_add'>+</button>"
            f"</form>")


def _verwerk_blok(st, circle: str, it: dict, csrf: str, nxt: str) -> str:
    """De lichte verwerk-actie: uitklappen, één keuze, klaar. Geen modal, geen tweede pagina.

    Drie routes, alle drie bestaand. De eerste is de getypeerde-kaart-pijplijn: het punt gaat als
    verse spanning naar een rol, en dáár schrijft de bestaande haak de bevinding en bepaalt de
    bestaande typer of het een verzoek, een governance-voorstel of een besluit is. De andere twee
    zijn de directe uitkomsten die het werkoverleg ook al kent."""
    iid = it["id"]
    lead = f"{circle}__circle_lead"
    default = lead if st.records.get(lead) is not None else ""

    def _blok(otype: str, samenvatting: str, binnenin: str, uitleg: str = "") -> str:
        return (f"<details class='wo-ocd box-details'><summary>{samenvatting}</summary>"
                f"<form method='post' action='/action' class='wo-oc'>"
                f"{_hid(csrf, circle, nxt, iid=iid, otype=otype)}"
                f"{('<p class=' + chr(39) + 'muted' + chr(39) + '>' + _e(uitleg) + '</p>') if uitleg else ''}"
                f"{binnenin}"
                f"<button class='btn sm' type='submit' name='action' value='vangst_verwerk'>"
                f"Record</button></form></details>")

    spanning = _blok(
        "spanning", "→ tension for a role",
        (f"<label class='att-lbl' for='vr-{_e(iid)}'>Which role?</label>"
         f"<select id='vr-{_e(iid)}' name='rol'>{_rol_opties(st, circle, default)}</select>"),
        "It lands as a fresh tension: the finding is written and typed by the existing pipeline, "
        "so it becomes a request, a governance proposal or a decision on its own.")
    project = _blok(
        "project", "→ project on a role",
        (f"<label class='att-lbl' for='vp-{_e(iid)}'>On which role?</label>"
         f"<select id='vp-{_e(iid)}' name='owner'>{_rol_opties(st, circle)}</select>"
         + _field("Scope (editable)", "tekst", value=it.get("title", ""), fid=f"vt-{iid}",
                  required=True)))
    opts = _project_opties(st, circle)
    actie = _blok(
        "actie", "→ action on a project",
        (f"<label class='att-lbl' for='va-{_e(iid)}'>Which project?</label>"
         f"<select id='va-{_e(iid)}' name='pid_link'>{opts}</select>"
         + _field("Action (editable)", "tekst", value=it.get("title", ""), fid=f"va-t-{iid}",
                  required=True))) if opts else ""
    return f"<div class='ffoot-l'>{spanning}{project}{actie}</div>"


def _punt_rij(st, circle: str, it: dict, csrf: str, nxt: str) -> str:
    door = (it.get("by") or "").strip()
    wie = f"<span class='muted'>by {_e(door)}</span>" if door else "<span class='muted'>by —</span>"
    sep = "<span class='fsep'>·</span>"
    bron = ("<span class='chip outline'>on the agenda</span>"
            if it.get("bron") == "agenda" else "")
    meta = (f"<div class='rdr-meta'>{wie} {sep} "
            f"<span class='muted'>{_e(_stamp(it.get('created_at')))}</span> {bron}</div>")
    titel = f"<div class='rdr-sig'>{_e(it.get('title') or '')}</div>"

    if it.get("status") == "done":
        oc = it.get("outcome") or {}
        kader = (f"<div class='ffoot-l'><span class='chip outline'>✓ "
                 f"{_e(oc.get('type') or 'handled')}</span> "
                 f"<span class='muted'>{_e(oc.get('detail') or '')}</span></div>")
        return f"<div class='rdr-row'><div class='rdr-body'>{meta}{titel}{kader}</div></div>"

    weg = (f"<form method='post' action='/action' class='emo-f'>{_hid(csrf, circle, nxt, iid=it['id'])}"
           f"<button class='flink' type='submit' name='action' value='vangst_remove' "
           f"title='delete'>🗑</button></form>")
    return (f"<div class='rdr-row' data-open='1'><div class='rdr-body'>{meta}{titel}"
            f"{_verwerk_blok(st, circle, it, csrf, nxt)}</div>"
            f"<div class='rdr-act'>{weg}</div></div>")


# Vangen zonder de pagina te verliezen.
#
# De eerste meting op het echte scherm: drie punten snel achter elkaar getypt, één aangekomen. Elk
# punt deed een volledige POST-redirect-GET, en de toetsaanslagen van het volgende punt vielen in het
# gat waarin de pagina herlaadde. Autofocus lost dat niet op — het veld komt terug, maar wat je in de
# tussentijd typte is weg. En precies die snelheid is de functie van dit scherm.
#
# Daarom stuurt het formulier zichzelf op met `fetch` en ververst alleen de lijst. Het veld verliest
# nooit de focus, dus er valt geen gat om iets in te verliezen. Zonder JavaScript blijft het een
# gewoon formulier dat post en herlaadt — de vangst werkt dan trager, niet minder.
_VANG_JS = """<script>(function(){
 var f=document.getElementById('vang-form'), inp=document.getElementById('vang-input'),
     lijst=document.getElementById('vang-lijst');
 if(!f||!inp||!lijst||f.dataset.wired)return; f.dataset.wired='1';
 var wacht=[], bezig=false;
 function ververs(){
   fetch(f.dataset.frag,{credentials:'same-origin'})
     .then(function(r){return r.text();})
     .then(function(h){
       lijst.innerHTML=h;
       // De teller staat in de kop en zou anders op zijn server-waarde blijven staan — een 0 boven
       // een lijst met drie punten is een leugen op het scherm. Hij wordt uit de lijst zelf geteld,
       // dus er is maar één bron.
       var n=document.getElementById('vang-n');
       if(n)n.textContent=lijst.querySelectorAll('.rdr-row[data-open]').length;
     }).catch(function(){});
 }
 function stuur(tekst){
   // `action` zit op de submit-KNOP, en new FormData(form) neemt knopwaarden niet mee. Zonder deze
   // regel komt de POST als naamloze actie binnen en doet de dispatch stil niets — 200, en weg.
   var d=new FormData(f); d.set('punt',tekst); d.set('action','vangst_add');
   return fetch('/action',{method:'POST',body:new URLSearchParams(d),credentials:'same-origin'});
 }
 function volgende(){
   if(bezig||!wacht.length)return; bezig=true;
   stuur(wacht.shift()).then(function(){bezig=false; volgende(); if(!wacht.length)ververs();})
     .catch(function(){bezig=false; f.submit();});
 }
 f.addEventListener('submit',function(e){
   var t=inp.value.trim(); if(!t)  {e.preventDefault(); return;}
   e.preventDefault(); inp.value=''; inp.focus();      // veld meteen vrij voor het volgende punt
   wacht.push(t); volgende();
 });
})();</script>"""


def render_vangst_frag(st, circle: str, csrf_token: str = "") -> str:
    """Alleen de lijst. Dezelfde rijen als de volle pagina — één bron, geen tweede vorm."""
    nxt = f"/vangst?circle={circle}"
    rijen = "".join(_punt_rij(st, circle, p, csrf_token, nxt)
                    for p in st.werk.punten(circle))
    return rijen or ("<div class='card muted'>Nothing captured yet. Type a sentence above and "
                     "press Enter — that is the whole action.</div>")


def render_vangst(st, circle: str, csrf_token: str = "", msg: str = "") -> str:
    crec = st.records.get(circle)
    if crec is None or not org.is_circle(crec):
        main = ("<div class='c2-main'><div class='c2-bar'><a href='/'>← home</a></div>"
                "<h1>Quick capture</h1><p class='muted'>Capture belongs to a circle. Open a circle "
                "and use its Quick capture button.</p></div>")
        return _page("Quick capture", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")

    punten = st.werk.punten(circle)
    open_n = sum(1 for p in punten if p.get("status") != "done")
    vang = _vang_form(circle, csrf_token, f"/vangst?circle={circle}") if csrf_token else ""
    rijen = render_vangst_frag(st, circle, csrf_token)
    kop = (f"<div class='c2-bar'><a href='/node?id={_e(circle)}'>← {_e(_name(crec))}</a>"
           f" <span class='fsep'>·</span> "
           f"<a href='/werkoverleg?circle={_e(circle)}'>tactical meeting</a></div>"
           f"<h1>Quick capture <span class='chip' id='vang-n'>{open_n}</span></h1>"
           f"<p class='muted'>Catch first, sort later. Typing a point records nothing but the "
           f"sentence, who raised it and when — the finding and the typing happen when you "
           f"process it.</p>")
    main = (f"<div class='c2-main'>{kop}{_banner(msg)}"
            f"<div class='c2-sec'>{vang}</div>"
            f"<div class='rdr-tool' id='vang-lijst'>{rijen}</div></div>")
    return _page("Quick capture",
                 f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>{_VANG_JS if vang else ''}")
