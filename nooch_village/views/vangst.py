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
UITKOMST_SOORTEN = (
    ("info", "Info-melding", "landt als bericht bij de rol"),
    ("project", "Project", "komt op het bord van de rol"),
    ("actie", "Actie", "checklist-item op een lopend project van die rol"),
    ("governance", "Governance-punt", "gaat naar de roloverleg-agenda van de cirkel"),
)


def _uitkomst_regel(st, circle: str, it: dict, u: dict, csrf: str, nxt: str) -> str:
    """Eén al toegevoegde uitkomst. Blijft staan, ook nadat het punt is afgevinkt."""
    namen = rol_namen(st)
    soort = dict((k, lbl) for k, lbl, _ in UITKOMST_SOORTEN).get(u.get("type"), u.get("type"))
    naar = namen.get(u.get("rol") or "", u.get("rol") or "")
    doel = f" → <strong>{_e(naar)}</strong>" if naar else ""
    ref = f" <span class='muted'>{_e(u.get('ref') or '')}</span>" if u.get("ref") else ""
    weg = (f"<form method='post' action='/action' class='emo-f'>"
           f"{_hid(csrf, circle, _open_nxt(nxt, it['id']), iid=it['id'], uid=u.get('id', ''))}"
           f"<button class='flink' type='submit' name='action' value='vangst_uitkomst_weg' "
           f"title='remove'>✕</button></form>") if csrf else ""
    return (f"<div class='rdr-meta'><span class='chip outline'>{_e(soort)}</span>{doel} "
            f"<span class='muted'>{_e(u.get('tekst') or '')}</span>{ref} {weg}</div>")


def _verwerk_blok(st, circle: str, it: dict, csrf: str, nxt: str, open_iid: str = "") -> str:
    """FASE 2 — verwerken. Pas hier de volledige spanningstekst en de uitkomsten.

    Drie dingen die deze fase anders maken dan het oude werkoverleg-scherm:

    1. **Meerdere uitkomsten per spanning.** Eén punt levert zelden één ding op; een radio-knop
       dwingt je te kiezen wélke van de drie je opschrijft en de andere twee raak je kwijt.
    2. **Elke rol, niet alleen deze cirkel.** Het punt van persoon X wordt werk voor rol Y — dat is
       waar een overleg voor bestaat. Beperken tot de eigen cirkel maakt precies die overdracht
       onmogelijk.
    3. **Geen modal.** Uitklappen in de lijst, zoals de inbox: je houdt zicht op de rest van de
       agenda terwijl je er één verwerkt.
    """
    iid = it["id"]
    if not csrf:
        return ""
    dl = f"vr-dl-{iid}"
    sub = "this.form.requestSubmit?this.form.requestSubmit():this.form.submit()"

    tekst = (it.get("note") or {}).get("spanning") or ""
    veld = _field("De volledige spanning", "tekst", kind="textarea", value=tekst,
                  fid=f"vs-{iid}", attrs=f'onchange="{sub}"')
    tekstveld = (f"<form method='post' action='/action' class='wo-oc'>"
                 f"{_hid(csrf, circle, _open_nxt(nxt, iid), iid=iid)}{veld}"
                 f"<input type='hidden' name='action' value='vangst_tekst'></form>")

    regels = "".join(_uitkomst_regel(st, circle, it, u, csrf, nxt)
                     for u in (it.get("uitkomsten") or []))
    regels = regels or "<p class='muted'>Nog geen uitkomst. Voeg er hieronder één toe — meerdere mag.</p>"

    opts = "".join(f"<option value='{k}'>{_e(lbl)} — {_e(hint)}</option>"
                   for k, lbl, hint in UITKOMST_SOORTEN)
    toevoegen = (f"<form method='post' action='/action' class='wo-oc'>"
                 f"{_hid(csrf, circle, _open_nxt(nxt, iid), iid=iid)}"
                 f"<label class='att-lbl' for='vu-{_e(iid)}'>Wat levert dit op?</label>"
                 f"<select id='vu-{_e(iid)}' name='otype'>{opts}</select>"
                 f"<label class='att-lbl' for='vw-{_e(iid)}'>Voor welke rol?</label>"
                 f"<input id='vw-{_e(iid)}' name='rol' list='{_e(dl)}' autocomplete='off' "
                 f"placeholder='typ een rolnaam…'>"
                 f"{_rol_datalist(st, dl)}"
                 f"{_field('Wat precies', 'tekst', value=it.get('title', ''), fid=f'vut-{iid}')}"
                 f"<button class='btn sm' type='submit' name='action' value='vangst_uitkomst'>"
                 f"+ uitkomst</button></form>")

    klaar = it.get("status") == "done"
    vink = (f"<form method='post' action='/action' class='emo-f'>"
            f"{_hid(csrf, circle, _open_nxt(nxt, iid), iid=iid, klaar='0' if klaar else '1')}"
            f"<button class='btn {'' if klaar else 'ok '}sm' type='submit' name='action' "
            f"value='vangst_klaar'>{'↺ heropen' if klaar else '✓ verwerkt'}</button></form>")

    # Het blok blijft open na een toevoeging. Eén spanning levert meerdere uitkomsten op; elke keer
    # opnieuw moeten uitklappen maakt van "meerdere mag" alsnog een drempel per regel.
    op = " open" if open_iid and open_iid == iid else ""
    return (f"<details class='wo-ocd box-details'{op}><summary>verwerken</summary>"
            f"{tekstveld}<div class='ffoot-l'>{regels}</div>{toevoegen}{vink}</details>")


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


def render_vangst_frag(st, circle: str, csrf_token: str = "", open_iid: str = "") -> str:
    """Alleen de lijst. Dezelfde rijen als de volle pagina — één bron, geen tweede vorm."""
    nxt = f"/vangst?circle={circle}"
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
    rijen = render_vangst_frag(st, circle, csrf_token, open_iid)
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
