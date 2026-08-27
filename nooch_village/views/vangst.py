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
    if not gezocht or gezocht == INDIVIDUELE_ACTIE.lower():
        return "", ""                          # geen rol — en dat mag, zie INDIVIDUELE_ACTIE
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
    """De rollen, met "Individuele actie" bovenaan: werk dat aan een persoon hangt en aan geen rol."""
    opts = f"<option value='{_e(INDIVIDUELE_ACTIE)}'>"
    opts += "".join(f"<option value='{_e(n)}'>" for n in sorted(rol_namen(st).values()))
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

# LEES-ONLY. De staat-keuze is uit het invulformulier gehaald: de wachtstatus vangen we al op
# projectniveau, en twee plekken die hetzelfde bijhouden lopen uit de pas. Deze constanten blijven
# bestaan omdat OUDE uitkomsten hem nog dragen en gewoon leesbaar moeten blijven — een stille drop
# zou betekenen dat een vastgelegde "in afwachting" ineens niets meer zegt.
VOLGENDE, WACHTEND = "volgende", "wachtend"

# Wie de uitkomst uitvoert. Leeg = "elk cirkellid": de rol is toegewezen, de persoon nog niet.
ELK_LID = ""
ELK_LID_WAARDE = "*"      # expliciete keuze "elk cirkellid" — te onderscheiden van "nog niets gekozen"

# ROL is in de LIVE VERWERKING niet verplicht. "Individuele actie" is de eerste keuze: werk dat aan
# een PERSOON hangt en aan geen enkele rol. Dat is geen slordigheid maar de werkelijkheid van een
# overleg — "Lotte belt de leverancier even" hoort bij Lotte, niet bij een mandaat.
#
# LET OP, DIT GELDT ALLEEN HIER. De AI-spanningen die getypeerd in de inbox belanden
# (`vangst_verwerk` → `spanning_ontstaat` → `zelf_verwerking`) houden hun rol-borging: daar is de
# rol de grond waarop een oordeel rust, en zonder rol is er geen accountability om aan te toetsen.
# Verruim die kant dus niet "voor de consistentie" — het zijn twee verschillende dingen.
INDIVIDUELE_ACTIE = "Individuele actie"


def _personen(st, circle: str) -> list:
    from nooch_village.views.overview import _members_of_circle
    return _members_of_circle(st, circle)


def _persoon_opties(st, circle: str, gekozen: str = "") -> str:
    """De persoon-keuze, met bovenaan een LEGE "— Kies persoon —".

    Die lege eerste optie is er zodat "elk cirkellid" een echte keuze is en niet iets waar je in
    rolt omdat het toevallig bovenaan stond. Bij een individuele actie moet je wél iemand kiezen —
    zonder rol én zonder persoon hangt het werk nergens."""
    leeg = " selected" if not gekozen else ""
    uit = f"<option value=''{leeg}>— Kies persoon —</option>"
    uit += f"<option value='{ELK_LID_WAARDE}'{' selected' if gekozen == ELK_LID_WAARDE else ''}>Elk cirkellid</option>"
    for p in _personen(st, circle):
        sel = " selected" if p.id == gekozen else ""
        uit += f"<option value='{_e(p.id)}'{sel}>{_e(p.name)}</option>"
    return uit


def _persoon_naam(st, pid: str) -> str:
    if not pid or pid == ELK_LID_WAARDE:
        return "elk cirkellid"
    p = st.people.get(pid)
    return getattr(p, "name", "") or pid


def _leeftijd(ts) -> str:
    """Hoe oud is dit? Fijn aan de korte kant, grof aan de lange.

    In een overleg is "42 seconden oud" informatie — je ziet dat iets net is vastgelegd. "Vandaag"
    zegt daar niets; dat is alles wat je die ochtend deed. Andersom: bij drie weken maakt het uur
    niet meer uit."""
    if not ts:
        return ""
    sec = int(time.time() - float(ts))
    if sec < 60:
        return f"{max(sec, 0)} seconde{'n' if sec != 1 else ''} oud"
    if sec < 3600:
        m = sec // 60
        return f"{m} minu{'ut' if m == 1 else 'ten'} oud"
    if sec < 86400:
        u = sec // 3600
        return f"{u} u{'ur' if u == 1 else 'ur'} oud"
    d = sec // 86400
    return f"{d} dag{'en' if d != 1 else ''} oud"


def _uitkomst_rij(st, circle: str, it: dict, u: dict, csrf: str, nxt: str,
                  toon_staat: bool = False) -> str:
    """Eén rij in de uitkomsten-tabel: WAT · wat precies · ROL · PERSOON · STAAT, met potlood en
    prullenbak. Plus onze toevoeging op GlassFrog: het Kroniek-record waaraan de herkomst hangt."""
    uid = u.get("id", "")
    soort = UITKOMST_LABEL.get(u.get("type"), u.get("type"))
    naar = rol_namen(st).get(u.get("rol") or "", u.get("rol") or "")
    wie = _persoon_naam(st, u.get("persoon") or "")
    # De staat-KOLOM verschijnt alleen als er in deze lijst nog een oud record staat dat hem
    # draagt. Zo blijft de vastgelegde waarde leesbaar zonder dat er een lege kolom overblijft
    # zodra het laatste oude record weg is.
    staat = ({WACHTEND: "In afwachting", VOLGENDE: "Volgende"}.get(u.get("staat"), "—")
             if toon_staat else None)
    bron = (f"<code class='pill' title='Kroniek-record'>{_e(u['kroniek'])}</code>"
            if u.get("kroniek") else "<span class='muted'>—</span>")
    acties = ""
    if csrf:
        acties = (f"<details class='wo-ocd box-details'><summary>✎</summary>"
                  f"<form method='post' action='/action' class='wo-oc'>"
                  f"{_hid(csrf, circle, _open_nxt(nxt, it['id']), iid=it['id'], uid=uid)}"
                  f"{_field('Tekst', 'tekst', value=u.get('tekst') or '', fid=f'ue-{uid}')}"
                  f"<label class='att-lbl' for='up-{_e(uid)}'>Persoon</label>"
                  f"<select id='up-{_e(uid)}' name='persoon'>"
                  f"{_persoon_opties(st, circle, u.get('persoon') or '')}</select>"
                  f"<button class='btn sm' type='submit' name='action' value='vangst_uitkomst_edit'>"
                  f"Opslaan</button></form></details>"
                  f"<form method='post' action='/action' class='emo-f'>"
                  f"{_hid(csrf, circle, _open_nxt(nxt, it['id']), iid=it['id'], uid=uid)}"
                  f"<button class='flink' type='submit' name='action' value='vangst_uitkomst_weg' "
                  f"title='verwijderen'>🗑</button></form>")
    slot = " 🔒" if u.get("prive") else ""
    staat_cel = f"<td>{_e(staat)}</td>" if staat is not None else ""
    return (f"<tr><td>{_e(soort)}{slot}</td><td>{_e(u.get('tekst') or '')}</td>"
            f"<td>{_e(naar)}</td><td>{_e(wie)}</td>{staat_cel}"
            f"<td>{bron}</td><td>{acties}</td></tr>")


def _uitkomsten_tabel(st, circle: str, it: dict, csrf: str, nxt: str) -> str:
    """"Uitkomsten van het overleg" — de tabel waarin ze zich opstapelen.

    In de referentie staan leeftijd en herkomst op de KOP van de spanning, niet per regel: het is
    de spanning die oud is, niet elk gevolg ervan. Per regel houden we wél het Kroniek-record, want
    dat is waaraan je later kunt terugtrekken."""
    rijen = it.get("uitkomsten") or []
    # De HERKOMST staat er zodra hij bekend is — ook als er nog geen uitkomst is. Dat is juist het
    # geval waarvoor hij bestaat: een vooraf ingevoerde spanning die je nu gaat behandelen.
    # De leeftijd komt er pas bij als er iets ligt om oud te zijn.
    delen = [d for d in (_herkomst_regel(st, it),) if d]
    if rijen:
        oudste = min((u.get("at") or 0) for u in rijen) or None
        if _leeftijd(oudste):
            delen.insert(0, _leeftijd(oudste))
    kop = f"<div class='rdr-meta'>{' · '.join(delen)}</div>" if delen else ""
    if not rijen:
        body = ("<p class='muted'>Er zijn (nog) geen uitkomsten vastgelegd. Vul het formulier "
                "hierboven in — zo vaak als nodig, er mogen er meerdere zijn.</p>")
    else:
        toon_staat = any(u.get("staat") for u in rijen)      # alleen voor oude records
        staat_kop = "<td><strong>Staat</strong></td>" if toon_staat else ""
        body = ("<table class='mtab'><tr><td><strong>Wat</strong></td>"
                "<td><strong>Wat precies</strong></td><td><strong>Rol</strong></td>"
                f"<td><strong>Persoon</strong></td>{staat_kop}"
                "<td><strong>Herkomst</strong></td><td></td></tr>"
                + "".join(_uitkomst_rij(st, circle, it, u, csrf, nxt, toon_staat) for u in rijen)
                + "</table>")
    return (f"<div class='c2-sec'><h3>Uitkomsten van het overleg "
            f"<span class='chip'>{len(rijen)}</span></h3>{kop}{body}</div>")


def _uitkomst_formulier(st, circle: str, it: dict, csrf: str, nxt: str) -> str:
    """HET uitkomst-formulier, uitgelijnd naar het GlassFrog-raster: twee kolommen, twee rijen.

        WAT  | TE NEMEN ACTIE        (label verandert mee met het type)
        ROL  | PERSOON
        ( ) Volgende  ( ) In afwachting                          [Opslaan]

    Eén formulier, zo vaak in te vullen als nodig — na Opslaan reset het en zakt de uitkomst in de
    tabel eronder. Geen radio-knop die je dwingt te kiezen wélke van de dingen die deze spanning
    oplevert je opschrijft.

    `.rov-addgrid` is het bestaande twee-koloms formulierraster (stapelt onder 560px); er komt geen
    nieuwe klasse bij."""
    iid = it["id"]
    dl = f"vr-dl-{iid}"
    lbl_id = f"vl-{iid}"
    # De labeltekst verandert mee met het type. Dat gebeurt met een inline `onchange`-attribuut en
    # niet met een <script>-blok: een script in een fragment draait niet als de modal het via
    # innerHTML invoegt, een attribuut-handler wél.
    veldnamen = ";".join(f"{k}:{v}" for k, v in UITKOMST_VELD.items())
    swap = (f"var m='{veldnamen}'.split(';'),l=document.getElementById('{lbl_id}');"
            f"for(var i=0;i&lt;m.length;i++){{var p=m[i].split(':');"
            f"if(p[0]===this.value&amp;&amp;l)l.textContent=p[1];}}")
    opts = "".join(f"<option value='{k}'>{_e(lbl)}</option>" for k, lbl, _ in UITKOMST_SOORTEN)
    eerste_veld = UITKOMST_SOORTEN[0][2]

    rij1 = (f"<div><label class='att-lbl' for='vu-{_e(iid)}'>Wat</label>"
            f"<select id='vu-{_e(iid)}' name='otype' onchange=\"{swap}\">{opts}</select></div>"
            f"<div><label class='att-lbl' id='{lbl_id}' for='vut-{_e(iid)}'>{_e(eerste_veld)}</label>"
            f"<input id='vut-{_e(iid)}' name='tekst' value='{_e(it.get('title') or '')}'></div>")
    rij2 = (f"<div><label class='att-lbl' for='vw-{_e(iid)}'>Rol</label>"
            f"<input id='vw-{_e(iid)}' name='rol' list='{_e(dl)}' autocomplete='off' "
            f"placeholder='{_e(INDIVIDUELE_ACTIE)} — of typ een rolnaam'>"
            f"{_rol_datalist(st, dl)}</div>"
            f"<div><label class='att-lbl' for='vp-{_e(iid)}'>Persoon</label>"
            f"<select id='vp-{_e(iid)}' name='persoon'>{_persoon_opties(st, circle)}</select></div>")
    # Volgende / In afwachting als twee radio's naast elkaar, zoals in de referentie — niet als
    # dropdown. Twee opties die je in één blik ziet zijn geen keuzelijst.
    # GEEN staat-keuze meer. De wachtstatus leeft op projectniveau; hem hier óók vragen levert
    # twee plekken op die hetzelfde bijhouden en na een week uit de pas lopen.
    afsluit = (f"<div class='qadd-row'>"
               f"<label class='kc-radio' for='vpr-{_e(iid)}'>"
               f"<input type='checkbox' id='vpr-{_e(iid)}' name='prive' value='1'>"
               f"Alleen zichtbaar voor de cirkel</label>"
               f"<button class='btn ok sm' type='submit' name='action' value='vangst_uitkomst'>"
               f"Opslaan</button></div>")
    return (f"<form method='post' action='/action' class='wo-oc'>"
            f"{_hid(csrf, circle, _open_nxt(nxt, iid), iid=iid)}"
            f"<div class='rov-addgrid'>{rij1}{rij2}</div>{afsluit}</form>")


def _herkomst_regel(st, it: dict) -> str:
    """Wie dit punt opwierp, en vanuit welke rol — AUTOMATISCH, geen invulveld.

    In een live overleg tikt de secretaris dit niet per punt in; daar is geen tijd voor en het
    gesprek ís de verwerking. Bij een vooraf ingevoerde spanning is het al bekend (wie hem ving,
    en de `@rol` die hij erbij zette), en dan hoort het gewoon te staan — zoals GlassFrog
    "gevoeld vanuit rol X" toont."""
    door = (it.get("by") or "").strip()
    rol = it.get("rol_hint") or ""
    delen = []
    if rol:
        delen.append(f"gevoeld vanuit <strong>{_e(rol_namen(st).get(rol, rol))}</strong>")
    if door:
        delen.append(f"ingebracht door {_e(door)}")
    return f"<span class='muted'>{' · '.join(delen)}</span>" if delen else ""


def _spanning_titel(st, circle: str, it: dict, csrf: str, nxt: str) -> str:
    """De spanningstekst als KLEINE bewerkbare titel, niet als blok dat om invulling vraagt.

    Het grote tekstvak stond bovenaan en bleef in de praktijk leeg: in een live overleg is er geen
    tijd om een spanning uit te schrijven. Alleen wie een punt VOORAF invoert vult hem, en dan moet
    hij er gewoon staan. Daarom: ingevuld → je leest hem meteen; leeg → één klein "⚡ Geen" dat je
    kunt openklappen als je hem tóch wilt vullen, en dat verder niets van je vraagt."""
    iid = it["id"]
    sub = "this.form.requestSubmit?this.form.requestSubmit():this.form.submit()"
    tekst = (it.get("note") or {}).get("spanning") or ""
    herkomst = _herkomst_regel(st, it)

    kort = " ".join(tekst.split())
    samenvatting = (f"⚡ {_e(kort[:110])}{'…' if len(kort) > 110 else ''}" if kort
                    else "<span class='muted'>⚡ Geen</span>")
    veld = _field("Spanning", "tekst", kind="textarea", value=tekst, fid=f"vs-{iid}",
                  placeholder="optioneel — meestal vul je dit vooraf in, niet tijdens het overleg",
                  attrs=f'onchange="{sub}"')
    bewerk = (f"<details class='wo-ocd box-details'><summary>{samenvatting}</summary>"
              f"<form method='post' action='/action' class='wo-oc'>"
              f"{_hid(csrf, circle, _open_nxt(nxt, iid), iid=iid)}{veld}"
              f"<input type='hidden' name='action' value='vangst_tekst'></form></details>")
    # De herkomst staat op de kop van de uitkomsten-tabel (zoals in de referentie), NIET hier —
    # anders lees je hem twee keer op één scherm.
    return bewerk


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
    kop = _spanning_titel(st, circle, it, csrf, nxt)

    lijst = _uitkomsten_tabel(st, circle, it, csrf, nxt)

    klaar = it.get("status") == "done"
    vink = (f"<form method='post' action='/action' class='emo-f'>"
            f"{_hid(csrf, circle, _open_nxt(nxt, iid), iid=iid, klaar='0' if klaar else '1')}"
            f"<button class='btn {'' if klaar else 'ok '}sm' type='submit' name='action' "
            f"value='vangst_klaar'>{'↺ heropen' if klaar else '✓ afgetikt'}</button></form>")

    op = " open" if open_iid and open_iid == iid else ""
    # HET UITKOMST-FORMULIER STAAT VOOROP. Daar werkt de secretaris live in; de spanningstekst is
    # één regel erboven en vraagt nergens om.
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
