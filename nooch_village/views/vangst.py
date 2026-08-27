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

import time

from nooch_village import org
from nooch_village.cockpit2_util import _DS_LINK, _name, _nav, _stamp
from nooch_village.web_base import _banner, _e, _field, _page

# De drie routes die een gevangen punt uit kan. Alle drie bestaan al; hier wordt er niets nieuws
# gebouwd, alleen naartoe verwezen.
UITKOMSTEN = ("spanning", "project", "actie")


def _open_nxt(nxt: str, iid: str) -> str:
    """De terug-URL met dit punt open. Zonder dit klapt het blok na elke uitkomst dicht."""
    return f"{nxt}{'&' if '?' in nxt else '?'}open={iid}"


def _hid(csrf: str, circle: str, nxt: str, **velden) -> str:
    rijen = [f"<input type='hidden' name='csrf' value='{_e(csrf)}'>",
             f"<input type='hidden' name='circle' value='{_e(circle)}'>",
             f"<input type='hidden' name='next' value='{_e(nxt)}'>"]
    rijen += [f"<input type='hidden' name='{_e(k)}' value='{_e(v)}'>" for k, v in velden.items()]
    return "".join(rijen)


def _rollen(st, circle: str) -> list:
    return sorted(org.roles_of(st.records.all(), circle), key=lambda r: _name(r).lower())


# ── ELKE rol, niet alleen deze cirkel ───────────────────────────────────────
#
# Dit is de kernfunctie van fase 2: het punt van persoon X wordt werk voor rol Y. Beperken tot de
# rollen van déze cirkel maakt precies de overdracht onmogelijk waar het overleg voor bestaat —
# iemand brengt iets in dat ergens anders thuishoort. Slapende en gearchiveerde rollen vallen af:
# daar werk neerleggen is het laten verdwijnen bij iemand die niet draait.

def alle_rollen(st) -> list:
    from nooch_village.villageraad import rollen as levende_rollen
    return sorted((r for r in levende_rollen(st.records) if not getattr(r, "slaapt", False)),
                  key=lambda r: _name(r).lower())


def rol_namen(st) -> dict:
    """{rol_id: unieke weergavenaam}. Dezelfde helper als de villageraad — drie rollen die
    allemaal 'Circle Lead' heten zijn in een autocomplete niet uit elkaar te houden."""
    from nooch_village.villageraad import labels
    return labels(alle_rollen(st), st.records)


def rol_uit_naam(st, naam: str) -> tuple:
    """(rol_id, reden). Leeg id = niet opgelost, en dan gebeurt er niets.

    Fail-closed op dubbelzinnigheid: twee rollen die op dezelfde naam matchen leveren géén keuze
    op. Werk bij de verkeerde rol neerleggen kost een hop en levert een vals gat-record op — een
    zichtbare 'niet gevonden' is eerlijker dan een gok."""
    gezocht = " ".join((naam or "").split()).lower()
    if not gezocht:
        return "", ""
    namen = rol_namen(st)
    exact = [rid for rid, n in namen.items() if n.lower() == gezocht]
    if len(exact) == 1:
        return exact[0], ""
    if len(exact) > 1:
        return "", f"meerdere rollen heten “{naam}”"
    if gezocht in namen:                       # iemand plakte een rol-id
        return gezocht, ""
    deel = [rid for rid, n in namen.items() if gezocht in n.lower()]
    if len(deel) == 1:
        return deel[0], ""
    if len(deel) > 1:
        return "", f"“{naam}” past op {len(deel)} rollen — wees specifieker"
    return "", f"geen rol gevonden voor “{naam}”"


def _rol_datalist(st, dl_id: str) -> str:
    opts = "".join(f"<option value='{_e(n)}'>" for n in sorted(rol_namen(st).values()))
    return f"<datalist id='{_e(dl_id)}'>{opts}</datalist>"


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
            f"<input id='vang-input' name='punt' "
            f"placeholder='punt in één regel (optioneel @rol) — Enter' "
            f"autocomplete='off' autofocus aria-label='punt' maxlength='140'>"
            f"<button class='btn ok sm' type='submit' name='action' value='vangst_add'>+</button>"
            f"</form>")


# De vier vormen die een uitkomst kan hebben. Alle vier bestaan al elders in het dorp; hier worden
# ze alleen naast elkaar gezet zodat één spanning er meerdere tegelijk kan opleveren.
# De vier uitkomsttypen van de GlassFrog-triage, in die volgorde. Het type wordt PER UITKOMST
# gekozen, niet per spanning — dat is precies het verschil met een radio-knop: één spanning kan
# tegelijk een actie, een project én een punt voor het roloverleg opleveren.
# Het derde veld is het label van het tekstveld: dat verandert mee met het type, want "project"
# vragen en "te nemen actie" vragen zijn niet dezelfde vraag.
UITKOMST_SOORTEN = (
    ("actie", "Actie", "Te nemen actie"),
    ("project", "Project", "Project"),
    ("governance", "Punt voor roloverleg", "Punt voor het roloverleg"),
    ("info", "Informatie", "Wat je wilt delen"),
)
UITKOMST_LABEL = {k: lbl for k, lbl, _ in UITKOMST_SOORTEN}
UITKOMST_VELD = {k: veld for k, _, veld in UITKOMST_SOORTEN}

# "Volgende" = een eerstvolgende actie waar iemand mee aan de slag kan; "In afwachting" = het
# wacht op iets of iemand anders. GlassFrog onderscheidt die twee omdat een wachtend item geen
# werk is dat je vandaag kunt oppakken, en het dus ook niet op je lijstje van vandaag hoort.
VOLGENDE, WACHTEND = "volgende", "wachtend"

# Wie de uitkomst uitvoert. Leeg = "elk cirkellid": de rol is toegewezen, de persoon nog niet.
ELK_LID = ""


def _personen(st, circle: str) -> list:
    from nooch_village.views.overview import _members_of_circle
    return _members_of_circle(st, circle)


def _persoon_opties(st, circle: str, gekozen: str = "") -> str:
    """De persoon-keuze. "Elk cirkellid" staat vooraan en is de default: de rol is toegewezen, wie
    het doet mag later blijken. Een verplichte persoon zou het overleg ophouden met een vraag die
    niet altijd te beantwoorden is."""
    uit = (f"<option value=''{' selected' if not gekozen else ''}>elk cirkellid</option>")
    for p in _personen(st, circle):
        sel = " selected" if p.id == gekozen else ""
        uit += f"<option value='{_e(p.id)}'{sel}>{_e(p.name)}</option>"
    return uit


def _persoon_naam(st, pid: str) -> str:
    if not pid:
        return "elk cirkellid"
    p = st.people.get(pid)
    return getattr(p, "name", "") or pid


def _leeftijd(ts) -> str:
    """Hoe oud is deze uitkomst? GlassFrog toont dat, en met reden: een actie van drie weken oud
    die er nog staat zegt iets anders dan een van vanochtend."""
    if not ts:
        return ""
    dagen = int((time.time() - float(ts)) // 86400)
    if dagen <= 0:
        return "vandaag"
    return f"{dagen} dag{'en' if dagen != 1 else ''} oud"


def _uitkomst_regel(st, circle: str, it: dict, u: dict, csrf: str, nxt: str) -> str:
    """Eén regel in "Uitkomsten van het overleg": wat het is, voor wie, waar het vandaan komt en
    hoe oud het is. Bewerkbaar en verwijderbaar — een uitkomst die je niet meer kunt bijstellen
    dwingt je hem weg te gooien en opnieuw te typen."""
    uid = u.get("id", "")
    soort = UITKOMST_LABEL.get(u.get("type"), u.get("type"))
    naar = rol_namen(st).get(u.get("rol") or "", u.get("rol") or "")
    wie = _persoon_naam(st, u.get("persoon") or "")
    wacht = " <span class='chip muted'>in afwachting</span>" if u.get("staat") == WACHTEND else ""
    # HERKOMST: het Kroniek-record, niet alleen de rolnaam. Zo is elke uitkomst van het overleg
    # net zo natrekbaar als elk ander feit in het dorp — je kunt teruglopen naar wat er gezegd is.
    bron = (f"<span class='muted'>herkomst <code class='pill'>{_e(u['kroniek'])}</code></span>"
            if u.get("kroniek") else "<span class='muted'>herkomst niet vastgelegd</span>")
    oud = f" · {_e(_leeftijd(u.get('at')))}" if u.get("at") else ""
    ref = f" · {_e(u.get('ref') or '')}" if u.get("ref") else ""

    kop = (f"<div class='rdr-meta'><span class='chip outline'>{_e(soort)}</span> "
           f"→ <strong>{_e(naar)}</strong> <span class='muted'>({_e(wie)})</span>{wacht} "
           f"{bron}{oud}{ref}</div>"
           f"<div class='rdr-sig'>{_e(u.get('tekst') or '')}</div>")
    if not csrf:
        return f"<div class='rdr-row'><div class='rdr-body'>{kop}</div></div>"

    weg = (f"<form method='post' action='/action' class='emo-f'>"
           f"{_hid(csrf, circle, _open_nxt(nxt, it['id']), iid=it['id'], uid=uid)}"
           f"<button class='flink' type='submit' name='action' value='vangst_uitkomst_weg' "
           f"title='verwijderen'>✕</button></form>")
    bewerk = (f"<details class='wo-ocd box-details'><summary>bewerken</summary>"
              f"<form method='post' action='/action' class='wo-oc'>"
              f"{_hid(csrf, circle, _open_nxt(nxt, it['id']), iid=it['id'], uid=uid)}"
              f"{_field('Tekst', 'tekst', value=u.get('tekst') or '', fid=f'ue-{uid}')}"
              f"<label class='att-lbl' for='up-{_e(uid)}'>Persoon</label>"
              f"<select id='up-{_e(uid)}' name='persoon'>"
              f"{_persoon_opties(st, circle, u.get('persoon') or '')}</select>"
              f"<label class='att-lbl' for='us-{_e(uid)}'>Staat</label>"
              f"<select id='us-{_e(uid)}' name='staat'>"
              f"<option value='{VOLGENDE}'{'' if u.get('staat') == WACHTEND else ' selected'}>"
              f"Volgende</option>"
              f"<option value='{WACHTEND}'{' selected' if u.get('staat') == WACHTEND else ''}>"
              f"In afwachting</option></select>"
              f"<button class='btn sm' type='submit' name='action' value='vangst_uitkomst_edit'>"
              f"Opslaan</button></form></details>")
    return (f"<div class='rdr-row'><div class='rdr-body'>{kop}{bewerk}</div>"
            f"<div class='rdr-act'>{weg}</div></div>")


def _uitkomst_formulier(st, circle: str, it: dict, csrf: str, nxt: str) -> str:
    """HET uitkomst-formulier. Eén formulier, zo vaak in te vullen als nodig — na Opslaan reset het
    en zakt de uitkomst in de lijst eronder. Geen radio-knop die je dwingt te kiezen wélke van de
    drie dingen die deze spanning oplevert je opschrijft."""
    iid = it["id"]
    dl = f"vr-dl-{iid}"
    lbl_id = f"vl-{iid}"
    # De labeltekst verandert mee met het type. Dat gebeurt met een inline `onchange`-attribuut en
    # niet met een <script>-blok: een script in een fragment draait niet als de modal het via
    # innerHTML invoegt, een attribuut-handler wél. Zo werkt dit scherm in het werkoverleg net zo
    # goed als op zichzelf.
    veldnamen = ";".join(f"{k}:{v}" for k, v in UITKOMST_VELD.items())
    swap = (f"var m='{veldnamen}'.split(';'),l=document.getElementById('{lbl_id}');"
            f"for(var i=0;i&lt;m.length;i++){{var p=m[i].split(':');"
            f"if(p[0]===this.value&amp;&amp;l)l.textContent=p[1];}}")
    opts = "".join(f"<option value='{k}'>{_e(lbl)}</option>" for k, lbl, _ in UITKOMST_SOORTEN)
    eerste_veld = UITKOMST_SOORTEN[0][2]
    return (f"<form method='post' action='/action' class='wo-oc'>"
            f"{_hid(csrf, circle, _open_nxt(nxt, iid), iid=iid)}"
            f"<label class='att-lbl' for='vu-{_e(iid)}'>Wat</label>"
            f"<select id='vu-{_e(iid)}' name='otype' onchange=\"{swap}\">{opts}</select>"
            f"<label class='att-lbl' id='{lbl_id}' for='vut-{_e(iid)}'>{_e(eerste_veld)}</label>"
            f"<input id='vut-{_e(iid)}' name='tekst' value='{_e(it.get('title') or '')}'>"
            f"<label class='att-lbl' for='vw-{_e(iid)}'>Rol</label>"
            f"<input id='vw-{_e(iid)}' name='rol' list='{_e(dl)}' autocomplete='off' "
            f"placeholder='typ een rolnaam…'>{_rol_datalist(st, dl)}"
            f"<label class='att-lbl' for='vp-{_e(iid)}'>Persoon</label>"
            f"<select id='vp-{_e(iid)}' name='persoon'>{_persoon_opties(st, circle)}</select>"
            f"<label class='att-lbl' for='vst-{_e(iid)}'>Staat</label>"
            f"<select id='vst-{_e(iid)}' name='staat'>"
            f"<option value='{VOLGENDE}'>Volgende</option>"
            f"<option value='{WACHTEND}'>In afwachting</option></select>"
            f"<button class='btn ok sm' type='submit' name='action' value='vangst_uitkomst'>"
            f"Opslaan</button></form>")


def _verwerk_blok(st, circle: str, it: dict, csrf: str, nxt: str, open_iid: str = "") -> str:
    """De VERWERK-KANT, naar de anatomie van het GlassFrog-triagescherm.

    Van boven naar beneden: de spanningstekst (bewerkbaar, en pas hier ingevuld — bij het VANGEN is
    het label genoeg), dan één uitkomst-formulier, dan de lijst "Uitkomsten van het overleg".

    Waar ons oude scherm faalde: het dwong één uitkomst per spanning af. "De FSC-verklaring verloopt"
    is tegelijk een actie voor inkoop, een project bij compliance en een punt voor het roloverleg.
    Een radio-knop laat je kiezen wélke van die drie je opschrijft; de andere twee raak je kwijt.
    Daarom reset het formulier na Opslaan en zakt de uitkomst in de lijst — zo vaak als nodig.
    """
    iid = it["id"]
    if not csrf:
        return ""
    sub = "this.form.requestSubmit?this.form.requestSubmit():this.form.submit()"

    # De spanningstekst bovenaan. Leeg is een geldige toestand — GlassFrog toont dan "⚡ Geen" —
    # want bij het vangen typ je een label, geen spanning.
    tekst = (it.get("note") or {}).get("spanning") or ""
    veld = _field("Spanning", "tekst", kind="textarea", value=tekst, fid=f"vs-{iid}",
                  placeholder="⚡ Geen — beschrijf hier wat er speelt",
                  attrs=f'onchange="{sub}"')
    kop = (f"<form method='post' action='/action' class='wo-oc'>"
           f"{_hid(csrf, circle, _open_nxt(nxt, iid), iid=iid)}{veld}"
           f"<input type='hidden' name='action' value='vangst_tekst'></form>")

    uitkomsten = it.get("uitkomsten") or []
    regels = "".join(_uitkomst_regel(st, circle, it, u, csrf, nxt) for u in uitkomsten)
    lijst = (f"<div class='c2-sec'><h3>Uitkomsten van het overleg "
             f"<span class='chip'>{len(uitkomsten)}</span></h3>"
             + (regels or "<p class='muted'>Nog geen uitkomst. Vul het formulier hierboven in — "
                          "zo vaak als nodig, er mogen er meerdere zijn.</p>") + "</div>")

    klaar = it.get("status") == "done"
    vink = (f"<form method='post' action='/action' class='emo-f'>"
            f"{_hid(csrf, circle, _open_nxt(nxt, iid), iid=iid, klaar='0' if klaar else '1')}"
            f"<button class='btn {'' if klaar else 'ok '}sm' type='submit' name='action' "
            f"value='vangst_klaar'>{'↺ heropen' if klaar else '✓ afgetikt'}</button></form>")

    op = " open" if open_iid and open_iid == iid else ""
    return (f"<details class='wo-ocd box-details'{op}><summary>verwerken</summary>"
            f"{kop}{_uitkomst_formulier(st, circle, it, csrf, nxt)}{lijst}{vink}</details>")


def _punt_rij(st, circle: str, it: dict, csrf: str, nxt: str, open_iid: str = "") -> str:
    door = (it.get("by") or "").strip()
    wie = f"<span class='muted'>door {_e(door)}</span>" if door else "<span class='muted'>door —</span>"
    sep = "<span class='fsep'>·</span>"
    klaar = it.get("status") == "done"
    n_uit = len(it.get("uitkomsten") or [])
    chips = ""
    if it.get("bron") == "agenda":
        chips += "<span class='chip outline'>op de agenda</span> "
    if n_uit:
        chips += f"<span class='chip outline'>{n_uit} uitkomst{'en' if n_uit != 1 else ''}</span> "
    if it.get("rol_hint"):
        naam = rol_namen(st).get(it["rol_hint"], it["rol_hint"])
        chips += f"<span class='chip muted'>@{_e(naam)}</span> "
    meta = (f"<div class='rdr-meta'>{wie} {sep} "
            f"<span class='muted'>{_e(_stamp(it.get('created_at')))}</span> {chips}</div>")
    # Afgevinkt verdwijnt niet: doorgestreept blijven staan. Wie het overleg terugleest moet kunnen
    # zien wát er langskwam, niet alleen wat er nog open is.
    titel = (f"<div class='rdr-sig{' ck-done' if klaar else ''}'>"
             f"{_e(it.get('title') or '')}</div>")

    weg = ""
    if csrf and not klaar:
        weg = (f"<form method='post' action='/action' class='emo-f'>"
               f"{_hid(csrf, circle, nxt, iid=it['id'])}"
               f"<button class='flink' type='submit' name='action' value='vangst_remove' "
               f"title='weggooien'>🗑</button></form>")
    return (f"<div class='rdr-row'{'' if klaar else " data-open='1'"}>"
            f"<div class='rdr-body'>{meta}{titel}"
            f"{_verwerk_blok(st, circle, it, csrf, nxt, open_iid)}</div>"
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


def render_vangst_frag(st, circle: str, csrf_token: str = "", open_iid: str = "",
                       nxt: str = "") -> str:
    """Alleen de lijst. Dezelfde rijen als de volle pagina — één bron, geen tweede vorm.

    `nxt` is waar de formulieren naartoe terugkeren. De aanroeper bepaalt dat: in het werkoverleg
    is dat de agenda-stap, niet /vangst. Zonder deze parameter werd je na elke uitkomst het overleg
    uit gegooid — de component werkte, maar hij nam je mee naar zijn eigen huis."""
    nxt = nxt or f"/vangst?circle={circle}"
    rijen = "".join(_punt_rij(st, circle, p, csrf_token, nxt, open_iid)
                    for p in st.werk.punten(circle))
    return rijen or ("<div class='card muted'>Nog niets gevangen. Typ hierboven een regel en "
                     "druk op Enter — dat is de hele handeling.</div>")


def render_vangst(st, circle: str, csrf_token: str = "", msg: str = "",
                  open_iid: str = "") -> str:
    crec = st.records.get(circle)
    if crec is None or not org.is_circle(crec):
        main = ("<div class='c2-main'><div class='c2-bar'><a href='/'>← home</a></div>"
                "<h1>Vangen</h1><p class='muted'>Vangen hoort bij een cirkel. Open het "
                "werkoverleg van een cirkel, of gebruik het +-je in je inbox voor een los "
                "punt.</p></div>")
        return _page("Vangen", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")

    punten = st.werk.punten(circle)
    open_n = sum(1 for p in punten if p.get("status") != "done")
    vang = _vang_form(circle, csrf_token, f"/vangst?circle={circle}") if csrf_token else ""
    rijen = render_vangst_frag(st, circle, csrf_token, open_iid, nxt=f"/vangst?circle={circle}")
    kop = (f"<div class='c2-bar'><a href='/node?id={_e(circle)}'>← {_e(_name(crec))}</a>"
           f" <span class='fsep'>·</span> "
           f"<a href='/werkoverleg?circle={_e(circle)}'>tactical meeting</a></div>"
           f"<h1>Vangen <span class='chip' id='vang-n'>{open_n}</span></h1>"
           f"<p class='muted'>Eerst vangen, later sorteren. Typ een regel en druk Enter — meer "
           f"gebeurt er niet. Wát het oplevert en voor welke rol bepaal je pas bij "
           f"<em>verwerken</em>, en dan mogen het er meerdere zijn.</p>")
    main = (f"<div class='c2-main'>{kop}{_banner(msg)}"
            f"<div class='c2-sec'>{vang}</div>"
            f"<div class='rdr-tool' id='vang-lijst'>{rijen}</div></div>")
    return _page("Vangen",
                 f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>{_VANG_JS if vang else ''}")
