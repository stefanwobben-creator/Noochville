"""Inbox — de wachtrij van mentions/spanningen gericht aan de eigenaar (als persoon of in een van zijn
rollen), plus de verwerk-pagina waar je ze afhandelt.

De lijst is kaal en scanbaar: per item een afgekapte titel op één regel, een Verwerk-knop en een
prullenbak. Verwerken gebeurt op een eigen twee-panelen-pagina: links de volledige spanning (met bron),
rechts de intentie-wizard (Wat heb je nodig? → per uitkomst een diagnostische vraag met een knop). Je
kunt meerdere uitkomsten op één spanning stapelen; elke keuze landt in het verwerk-record. Pas 'Klaar'
sluit het item. Zo is zichtbaar of een rol bij de eerste uitkomst stopt of er meer uithaalt.

Hergebruik: web_base (_e/_page), cockpit2_util (_name/_BUILD/_stamp), inbox_wizard (de declaratieve
beslisboom). Geen nieuwe opslag — leunt op NotifStore (met het verwerk-record).
"""
from __future__ import annotations

import json
import re

from nooch_village.web_base import _e, _page, _field
from nooch_village.cockpit2_util import _name, _rol_labels, _BUILD, _stamp, _DS_LINK, _nav
from nooch_village.inbox_wizard import FLOWS, GOVERNANCE, OTYPE_LABEL
from nooch_village.notifications import MENS_GETYPT, volledig as _volledig
from nooch_village.systeemtaal import ontjargon

_STATUS = {"nieuw": ("● new", "chip ok"), "gelezen": ("busy", "chip muted"),
           "verwerkt": ("✓ handled", "chip outline")}


#: Een project-id in lopende tekst: 12 hex-tekens. Smal genoeg om geen gewone woorden te raken.
_PID_IN_TEKST = re.compile(r"\b([0-9a-f]{12})\b")


#: Wat de vorm-woorden betekenen op het scherm. De sleutel is intern, de zin is voor de lezer.
_VORM_TEKST = {"accountability": "hoort structureel bij een rol (accountability)",
               "project": "meerdere stappen met één uitkomst (project)",
               "actie": "één handeling (actie)"}


def _triage_band(st, n: dict) -> str:
    """"Waarschijnlijk voor <rol>, omdat <accountability>" — een suggestie mét grond.

    DE RAUWE SPANNING BLIJFT ERONDER STAAN, onaangetast. Dit is een voorstel om te accepteren of te
    weerspreken, geen besluit dat al genomen is: de band vertelt WAT wij denken en WAAROM, en de
    tekst eronder laat je zelf oordelen.

    Zonder gegronde match verschijnt de reden in plaats van een naam. Een lege band zou de lezer
    laten raden of we niets vonden of niet hebben gekeken — en dat verschil is precies wat een
    suggestie bruikbaar maakt."""
    rol = str(n.get("triage_rol") or "")
    vorm = _VORM_TEKST.get(str(n.get("triage_vorm") or ""), "")
    grond = str(n.get("triage_grond") or "")
    if not (rol or vorm or grond):
        return ""
    if rol:
        rec = st.records.get(rol)
        naam = (_name(rec) if rec is not None else "") or rol
        kop = (f"<strong>Waarschijnlijk voor {_e(naam)}</strong>, omdat: "
               f"“{_e(str(n.get('triage_accountability') or ''))}”")
    else:
        kop = f"<strong>Geen rol gevonden</strong> — {_e(grond)}"
    staart = f"<br><span class='muted'>Vorm: {_e(vorm)}</span>" if vorm else ""
    return f"<p class='muted'>{kop}{staart}</p>"


def _herkomst_html(st, tekst: str) -> str:
    """Herkomst met KLIKBARE bron-ids.

    "project 2d5e7fac383b lag stil" is waar, en onbruikbaar: een mens kan dat id nergens intikken en
    ziet dus nooit wat er lag. Een herkomst die je niet kunt openen is handhaving zonder
    waarneembaarheid — hetzelfde patroon als het record dat de PLEK in `by` schreef.

    Alleen ids die ECHT bestaan worden een link; een onbekend id blijft gewone tekst. Een dode link
    is erger dan geen link: hij belooft context die er niet is."""
    def _vervang(m):
        pid = m.group(1)
        try:
            if st.projects.get(pid) is None:
                return pid
        except Exception:                                    # noqa: BLE001
            return pid
        return f"<a href='/project?pid={_e(pid)}'>{_e(pid)}</a>"
    return _PID_IN_TEKST.sub(_vervang, _e(tekst))


def _source_link(st, n: dict) -> str:
    pid = (n.get("project_id") or "").strip()
    p = st.projects.get(pid) if pid else None
    if p is not None:
        from nooch_village.notifications import preview
        scope = preview(str(p.get("scope") or "project"), 60)
        return f"<a href='/project?pid={_e(pid)}'>{_e(scope)}</a>"
    pag = dict(n.get("pagina") or {})
    if pag.get("aid"):
        # De bron van een pagina-voorstel is de pagina zelf, niet de afzender: dat is waar de lezer
        # heen wil om te zien wat er nu staat.
        from nooch_village import wiki
        return (f"<a href='{_e(wiki.pagina_url(str(pag['aid'])))}'>"
                f"{_e(str(pag.get('titel') or pag['aid']))}</a>")
    return _e(_who(st, n))


def _who(st, n: dict) -> str:
    by = (n.get("by") or "").strip()
    rec = st.records.get(by) if by else None
    if rec is not None:
        return _name(rec)
    # Niet elke afzender is een rol: een pagina-voorstel komt van een MENS. Zonder deze regel stond
    # er een kaal persoon-id op het scherm, dat eruitziet als een rol-id die niemand kent.
    # Defensief opgehaald: een weergave mag nooit omvallen omdat een store net iets anders is.
    lookup = getattr(getattr(st, "people", None), "get", None)
    p = lookup(by) if (by and callable(lookup)) else None
    if p is not None:
        return getattr(p, "name", "") or by
    return by or "someone"


def _one_line(text: str, cap: int = 90) -> str:
    """Eén regel voor de lijst, afgebroken op een WOORDGRENS.

    DE TWEEDE KOPIE VAN DE 160-CAP, en hij overleefde de veegronde van #389/#392. Daar haalden we de
    caps uit de STORE en de callers weg; deze zat in de WEERGAVE en kapte gewoon midden in een woord:
    "compleet overzicht beschikbaa", "die live updates lev", "an entrepre". Een halve zin leest als
    een defect, niet als een samenvatting.

    Eén afleidingsplek: `notifications.preview` doet dit al, inclusief de ellips-in-het-budget-regel.
    Hem hier opnieuw uitschrijven is precies hoe deze kopie ontstond."""
    from nooch_village.notifications import preview
    t = " ".join((text or "").split())
    return preview(t, cap) if t else "(no summary)"


def _hid(csrf: str, nid: str, nxt: str = "/inbox") -> str:
    return (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
            f"<input type='hidden' name='nid' value='{_e(nid)}'>"
            f"<input type='hidden' name='next' value='{_e(nxt)}'>")


def _btn(csrf: str, nid: str, action: str, label: str, cls: str = "flink", nxt: str = "/inbox") -> str:
    return (f"<form method='post' action='/action' class='emo-f'>{_hid(csrf, nid, nxt)}"
            f"<button class='{cls}' name='action' value='{action}'>{_e(label)}</button></form>")


# ── de lijst ────────────────────────────────────────────────────────────────────
# Wat een regel MOET tonen om scanbaar te zijn: waar het over gaat (de bevinding, niet de rauwe
# dump), en wat er van je gevraagd wordt (het type). Zonder dat tweede zien veertien regels er
# hetzelfde uit en moet je ze één voor één openen om te weten welke een besluit is.
_TYPE_CHIP = {"founder": "besluit", "naar_rol": "verzoek", "governance": "governance",
              "actie": "actie"}


def _leesbaar(n: dict, tekst: str) -> str:
    """De deterministische systeemjargon-swap op de LEESTEKST.

    Waarom ook hier, en niet alleen vóór het model: deze laag is gratis en moet gegarandeerd zijn.
    Faalt het model — geen krediet, storing — dan valt het scherm terug op de ruwe signalering, en
    dan hoort die tenminste geen `python -m …` en geen `niet-uitvoering` meer te bevatten.

    HIJ DRAAIT ALTIJD, OOK OP MENS-GETYPTE TEKST, en dat is een correctie op de eerste versie.
    Commando-strippen en model-herschrijven hingen aan dezelfde vlag, en dat lekte: een
    machine-melding die een MENS doorzette droeg `mens_getypt`, dus bleef "beoordeel via
    python -m nooch_village.inbox" gewoon staan op het scherm van diezelfde mens. Gemeten op prod,
    1 september 2026.

    De twee zorgen zijn niet hetzelfde. Een commando weghalen is geen herschrijving van iemands stem
    maar een DISPLAY-INVARIANT: een terminalopdracht hoort in geen enkele naar-mens-tekst, ongeacht
    wie hem indiende. Het model-herschrijven blijft wél gepoort op auteurschap — en dat auteurschap
    komt sinds deze fix uit de HERKOMST, niet uit `by`."""
    # Eerst de verpakking eraf, dan de swaps. `tensie_poort.kern` is DE plek die onze eigen omhulsels
    # kent ("⏸️ Project van X vastgelopen op 5 item(s): …") — die hier nog eens uitschrijven zou een
    # tweede vorm van hetzelfde zijn. Gemeten op prod: 84 van de laatste 30 dagen dragen dat omhulsel,
    # en op de LIJST stond het nog voluit; de detailweergave gebruikte `kern` al wél.
    from nooch_village import tensie_poort as tp
    return ontjargon(tp.kern(tekst) or tekst) or tekst



def _een_regel(n: dict) -> str:
    """De bevinding als hij er is, anders de rauwe signalering.

    De bevinding is de zin die voor een mens is geschreven; de snippet is de interne verpakking van
    160 tekens. Stond de snippet hier, dan is alle herformulering onzichtbaar precies op het scherm
    waar je kiest wat je opent."""
    b = dict(n.get("bevinding") or {})
    if b.get("ok") and b.get("spanning"):
        return _one_line(b["spanning"])
    return _one_line(_leesbaar(n, str(n.get("snippet") or "")))


def _inline_actie(st, n: dict, csrf: str) -> str:
    """De hoofdactie in de regel zelf. De modal blijft voor de diepte.

    Dezelfde knoppen als op de verwerk-pagina — letterlijk dezelfde bouwers, niet een tweede set.
    Is er voor dit type geen knop die in één handeling klopt (een governance-voorstel weegt de poort,
    dat doe je niet vanuit een lijst), dan staat er geen uitklap: een lege accordeon is erger dan
    geen accordeon."""
    soort = _type_van(n)
    if soort == "naar_rol" and n.get("pagina"):
        binnen = _verzoek_knoppen(n, csrf)
    elif soort == "naar_rol" or n.get("project_id"):
        # Decide-now stond hier ook, en is weg. Wat blijft is SLUITEN — met een reden als er een
        # vrager is. Een spanning met een bron-project heeft altijd iemand die op antwoord wacht,
        # en dat is precies waar "nee, want …" thuishoort.
        binnen = ""
    else:
        return ""
    return (f"<details class='wo-ocd box-details'><summary>handle here</summary>"
            f"{binnen}{_klaar_knop(n.get('id', ''), csrf, n=n)}</details>")


def _inbox_row(st, n: dict, csrf: str, done_nid: str = "") -> str:
    status = st.notif.status_of(n)
    lbl, chip = _STATUS.get(status, _STATUS["nieuw"])
    nid = n.get("id", "")
    sep = "<span class='fsep'>·</span>"
    soort = _type_van(n)
    tchip = (f"<span class='chip outline'>{_e(_TYPE_CHIP[soort])}</span> "
             if soort in _TYPE_CHIP else "")
    meta = (f"<div class='rdr-meta'><span class='{chip}'>{_e(lbl)}</span> {tchip}"
            f"<span class='muted'>via {_e(_who(st, n))}</span> {sep} {_source_link(st, n)} {sep} "
            f"<span class='muted'>{_e(_stamp(n.get('at')))}</span></div>")
    # `title=` draagt de hele zin: de regel blijft scanbaar, de rest is één hover ver. Zonder dat is
    # een afgebroken regel een doodlopende weg — je ziet dát er meer was, niet wát.
    _vol = _leesbaar(n, _volledig(n) or str(n.get("snippet") or ""))
    title = f"<div class='rdr-sig' title='{_e(_vol[:400])}'>{_e(_een_regel(n))}</div>"

    # 'verwerkt' (bekeken, blijft in de wachtrij) en 'klaar' (gesloten, verlaat hem) tonen allebei
    # hun record. Een gesloten spanning komt hier alleen langs voor het viermoment: `render_inbox`
    # zet hem daar eenmalig terug in de lijst.
    if status in ("verwerkt", "klaar"):
        vs = st.notif.verwerkingen_of(n)
        chips = " ".join(f"<span class='chip outline'>{_e(v.get('label') or 'outcome')}</span>" for v in vs) \
            or "<span class='chip outline'>handled</span>"
        body = f"{meta}{title}<div class='ffoot-l'>{chips}</div>"
        act = ("" if status == "klaar"                    # gesloten = al weg; niets meer te doen
               else f"<div class='rdr-act'>{_btn(csrf, nid, 'notif_archive', 'archive')}</div>")
        # Viermoment: de zojuist afgeronde spanning krijgt een groene rand + een kader met wat je vastlegde.
        if nid and nid == done_nid:
            regels = "".join(f"<li>{_e(v.get('label') or v.get('otype') or 'outcome')}</li>" for v in vs) \
                or "<li>no outcome</li>"
            body += f"<div class='rdr-kader'>✓ Handled. This is what you recorded:<ul>{regels}</ul></div>"
            return f"<div class='rdr-row rdr-vier'><div class='rdr-body'>{body}</div>{act}</div>"
        return f"<div class='rdr-row'><div class='rdr-body'>{body}</div>{act}</div>"

    # 'Process' is niet meer de enige weg: de hoofdactie zit in de regel, de modal is voor de
    # diepte (meerdere uitkomsten stapelen, de volle vraag, het verwerk-record).
    verwerk = f"<a class='btn sm' href='/inbox/verwerk?nid={_e(nid)}'>More…</a>"
    prullenbak = _btn(csrf, nid, "notif_delete", "🗑", cls="flink")
    act = f"<div class='rdr-act'>{verwerk}{prullenbak}</div>"
    inline = _inline_actie(st, n, csrf) if csrf else ""
    return (f"<div class='rdr-row'><div class='rdr-body'>{meta}{title}{inline}</div>{act}</div>")


def _poort_secties(st, items, csrf_token, done) -> str:
    """Groepeer op het oordeel van de tensie-poort: beslissingen bovenaan, mens-todo apart.

    De groepering is een INBOX-REGEL, geen beslissing. Bij de compliance-claims is dat het punt:
    veertien claims onder één kop, maar elke claim houdt zijn eigen regel en zijn eigen oordeel —
    een blanket-approve mag niet kunnen bestaan."""
    from nooch_village import tensie_poort as tp

    def _deur(n):
        return str((n.get("poort") or {}).get("deur") or "")

    groepen: dict[str, list] = {}
    ongetagd = []
    for n in items:
        d = _deur(n)
        if not d:
            ongetagd.append(n)
        else:
            sleutel = str((n.get("poort") or {}).get("sleutel") or d)
            groepen.setdefault(f"{d}|{sleutel}", []).append(n)

    KOP = {tp.DEUR_BESLUIT: "Decisions for you", tp.DEUR_ROL: "A role is missing",
           tp.DEUR_SKILL: "A capability is missing", tp.MENS_WERK: "Only you can do this",
           tp.ONBESLIST: "The gate could not classify these"}
    volgorde = [tp.DEUR_BESLUIT, tp.DEUR_ROL, tp.DEUR_SKILL, tp.MENS_WERK, tp.ONBESLIST]

    uit = []
    for deur in volgorde:
        mijn = {k: v for k, v in groepen.items() if k.split("|")[0] == deur}
        if not mijn:
            continue
        uit.append(f"<h2 class='ptitle'>{_e(KOP.get(deur, deur))}</h2>")
        if deur == tp.DEUR_BESLUIT:
            # Waarom ligt dit bij jou? Zonder de aangesproken accountability is tekenen een vinkje.
            from nooch_village import founder_kaart as fkaart
            for ns_ in mijn.values():
                for n_ in ns_:
                    k = fkaart.kaart(n_, projects=getattr(st, "projects", None),
                                     records=getattr(st, "records", None))
                    merk = "" if k["hoort_hier"] else " ⚠"
                    vanuit = (f" vanuit “{_e(k['vanuit'][:70])}”" if k.get("vanuit") else "")
                    waarom = (f" · {_e(k['behoefte'])}" if k.get("behoefte") else "")
                    uit.append(f"<p class='muted'>{_e(k['rol'])} werpt dit op{vanuit}"
                               f"{waarom}{merk}</p>")
        for _, ns in sorted(mijn.items(), key=lambda kv: -len(kv[1])):
            eerste = (ns[0].get("poort") or {})
            kop = eerste.get("klasse") or eerste.get("sleutel") or deur
            if len(ns) > 1:
                uit.append(f"<p class='muted'>{_e(kop)} — {len(ns)} meldingen. Elke regel houdt "
                           f"zijn eigen beslissing.</p>")
            uit.append("".join(_inbox_row(st, n, csrf_token, done_nid=done) for n in ns))
    if ongetagd:
        uit.append("<h2 class='ptitle'>Not yet through the gate</h2>")
        uit.append("".join(_inbox_row(st, n, csrf_token, done_nid=done) for n in ongetagd))
    return "".join(uit)


def render_inbox(st, targets, csrf_token: str = "", naam: str = "", done: str = "") -> str:
    items = st.notif.open_for_targets(targets)
    # HET VIERMOMENT MOET DE ZOJUIST GESLOTEN SPANNING NOG KUNNEN TONEN. Sinds sluiten de wachtrij
    # écht verkort, staat hij er niet meer in — en dan verdween precies het schermpje dat laat zien
    # wát je vastlegde. De gesloten spanning wordt daarom eenmalig terug in de lijst gezet, alleen
    # voor deze render, alleen als `done` hem noemt en hij van deze mens is.
    if done and not any(n.get("id") == done for n in items):
        gesloten = st.notif._find(done)
        if gesloten is not None and (gesloten.get("target_type"),
                                     gesloten.get("target_id")) in set(targets):
            items = [gesloten] + items
    nieuw = sum(1 for n in items if st.notif.status_of(n) == "nieuw")
    body = (_poort_secties(st, items, csrf_token, done) if items
            else "<p class='muted'>Your inbox is empty. As soon as a role or the meeting @-mentions you, "
                 "it appears here.</p>")
    kop = f"Inbox{(' — ' + _e(naam)) if naam else ''}"
    telling = (f"<p class='muted'>{len(items)} open, of which {nieuw} new. Handle one right here, "
               f"open More… for the full picture, or throw it away.</p>")
    main = (f"<div class='c2-main'><div class='c2-bar'><a href='/'>← home</a></div>"
            f"<h1>{kop} <span class='chip'>{len(items)}</span></h1>{telling}"
            f"<div class='rdr-tool'>{body}</div></div>")
    inner = (f"{_DS_LINK}{_nav()}"
             f"<div class='c2-wrap'>{main}</div>")
    return _page("Inbox", inner)


# ── de verwerk-pagina (twee panelen) ─────────────────────────────────────────────
# Wat elk type als LIJF en als ACTIE toont. De kop is voor alle vier gelijk (wie, vanuit welke
# accountability, de bevinding, het voorstel); daaronder verschilt wat er van de lezer gevraagd wordt.
_TYPE_LIJF = {
    "naar_rol":   ("Operationeel verzoek",
                   "Past dit bij jouw rol? Accepteer, pas de formulering aan, of weiger met reden. "
                   "Bij accepteren verschijnt het als project op je bord."),
    "governance": ("Governance-voorstel",
                   "Dit vraagt om een wijziging in wie waarvoor staat. De vraag is niet of je het "
                   "een goed idee vindt, maar of het schaadt of ons achteruit zet — en het loopt "
                   "langs de poort (G0-G4) met de botsingscheck."),
    "founder":    ("Besluit voor jou",
                   "Dit raakt een bevoegdheid die alleen jij hebt. Bevestig, pas aan, of verwerp."),
    # GEEN vraag maar toegewezen werk: er staat niet "past dit bij jou?", want dat is al bepaald.
    #
    # HERKOMST-NEUTRAAL, en dat is een correctie van 29 aug 2026. Hier stond "Actie uit het
    # werkoverleg / Afgesproken in het overleg". Toen een tweede bron acties ging leggen (een rol
    # die vastloopt, escalation_router.naar_mens) stond er op het scherm een kaart die zei dat het
    # in een overleg was afgesproken terwijl de herkomst-regel er direct boven iets anders zei.
    # Twee tegengestelde zinnen op één scherm — precies wat deze kaarten moesten wegnemen.
    #
    # De herkomst leeft in het `herkomst`-veld en wordt daar al getoond. Hem hier nóg eens in
    # andere woorden vertellen is `reference, don't copy` overtreden met tekst in plaats van een
    # getal: één van de twee gaat een keer niet meer kloppen, en dat is deze.
    "actie":      ("Actie voor jou",
                   "Waar hij vandaan komt staat hierboven. Doe hem en vink af, of maak er een "
                   "project van als het meer werk blijkt dan één handeling."),
}


def _type_van(n: dict) -> str:
    """Het type van dit item: uit het poort-oordeel, anders uit de tekst zelf (verse spanning)."""
    from nooch_village import tensie_poort as tp, zelf_verwerking as zv

    # Het type dat bij het ONTSTAAN is bepaald wint: dat is de bron, de poort komt later. Zonder
    # deze regel toonde een verse spanning wél de kaart maar niet de bijbehorende knoppen — de
    # linkerkant wist zijn type en de rechterkant niet.
    eigen = str(n.get("type") or "")
    if eigen in (zv.NAAR_ROL, zv.GOVERNANCE, zv.FOUNDER, zv.ACTIE):
        return eigen
    deur = str((n.get("poort") or {}).get("deur") or "")
    if deur == tp.DEUR_BESLUIT:
        return zv.FOUNDER
    if deur == tp.GEROUTEERD:
        return zv.NAAR_ROL
    tekst = _volledig(n)                     # de waarheid, niet de lijst-preview
    domein, _ = zv.founder_behoefte(tekst)
    if domein:
        return zv.FOUNDER
    # Governance heeft geen eigen poort-deur (de poort kent hem niet), dus wordt hij hier herkend
    # aan dezelfde twee signalen als in de zelf-verwerking. Zonder dit kreeg een
    # governance-spanning geen type-chip en geen lijf — dan is de kaart weer typeloos.
    kern_t = tp.kern(tekst)
    if zv._STRUCTUREEL.search(kern_t) and zv._STRUCTUUR_OBJECT.search(kern_t):
        return zv.GOVERNANCE
    return ""


def _kaart_html(st, n: dict) -> str:
    """De vier-regel-kaart voor een spanning die de founder bereikt. "" als het geen kaart-item is.

    Fail-soft: valt hier iets om, dan valt de pagina terug op de rauwe tekst — een leeg scherm is
    erger dan een lelijke regel."""
    if n.get("pagina"):
        # Een pagina-voorstel heeft zijn eigen, concrete blok (`_pagina_blok`): welke pagina, van
        # wie, wat er zou komen te staan en wat er nu staat. De generieke founder-kaart zou daar een
        # tweede, vagere versie van vertellen — inclusief de zin "dan verschijnt het als project op
        # je bord", die hier juist NIET klopt. Twee tegengestelde zinnen op één scherm is precies
        # wat deze kaart moest wegnemen.
        return ""
    try:
        from nooch_village import founder_kaart as fkaart, tensie_poort as tp, zelf_verwerking as zv

        # EEN ACTIE WORDT NIET DOOR EEN ROL OPGEWORPEN. De founder-kaart vertelt "<rol> werpt dit
        # op" en zoekt die rol op in de records; bij een actie uit het overleg staat er een PERSOON
        # in `by`, en die vindt hij niet — dan stond er een kaal id op het scherm. De herkomst van
        # een actie is het overleg, en die dragen we al mee.
        if _type_van(n) == zv.ACTIE:
            regels = [f"<div class='fbubble'>{_e(_volledig(n))}</div>"]
            if n.get("herkomst"):
                regels.append(f"<p class='muted'>{_herkomst_html(st, str(n['herkomst']))}</p>")
            regels.append(_triage_band(st, n))
            titel, uitleg = _TYPE_LIJF["actie"]
            regels.insert(0, f"<p class='chip'>{_e(titel)}</p>")
            regels.append(f"<p class='muted'>{_e(uitleg)}</p>")
            return "".join(regels)

        tekst = _volledig(n)                     # de waarheid, niet de lijst-preview
        kern = tp.kern(tekst)
        domein, behoefte = zv.founder_behoefte(tekst)
        # Een VERSE spanning heeft nog geen poort-oordeel, dus geen klasse — en dan vond de kaart
        # geen founder-accountability en zette hij de ⚠ eronder terwijl er wél een behoefte stond.
        # Twee tegengestelde zinnen op één scherm. Het domein komt hier uit de tekst zelf.
        n = dict(n)
        if domein and not (n.get("poort") or {}).get("klasse"):
            n["poort"] = {**(n.get("poort") or {}), "klasse": f"{domein}-besluit"}
        k = fkaart.kaart(n, projects=getattr(st, "projects", None),
                         records=getattr(st, "records", None),
                         voorstel={"behoefte": behoefte})
        if not k.get("rol") and not behoefte:
            return ""                                   # niets te vertellen → gewoon de tekst
        regels = [f"<p class='ptitle'>{_e(k['rol'])} werpt dit op</p>"]
        if k.get("vanuit"):
            regels.append(f"<p class='muted'>vanuit accountability “{_e(k['vanuit'][:120])}”</p>")
        herschreven = dict(n.get("bevinding") or {})
        if herschreven.get("ok"):
            # De herschreven bevinding is de tekst die de founder leest; de ruwe blijft eronder
            # staan als herkomst, niet als hoofdtekst.
            regels.append(f"<div class='fbubble'>{_e(herschreven['spanning'])}</div>")
            if herschreven.get("voorstel"):
                regels.append(f"<p><strong>Voorstel:</strong> {_e(herschreven['voorstel'])}</p>")
            regels.append(f"<details class='box-details'><summary class='muted'>ruwe signalering"
                          f"</summary><p class='muted'>{_e(kern or tekst)}</p></details>")
        elif herschreven and not herschreven.get("ok"):
            # De hoofdtekst wordt opgeschoond; de "ruwe signalering" hierboven blijft letterlijk,
            # want dat blok is herkomst en herkomst poets je niet op.
            regels.append(f"<div class='fbubble'>{_e(_leesbaar(n, kern or tekst))}</div>")
            regels.append(f"<p class='muted'>⚠ moet herschreven: {_e(herschreven.get('reden'))}</p>")
        else:
            regels.append(f"<div class='fbubble'>{_e(_leesbaar(n, kern or tekst))}</div>")
        if behoefte:
            regels.append(f"<p><strong>Wat ik van jou nodig heb:</strong> {_e(behoefte)}</p>")
        # Het LIJF: per type een andere uitleg van wat er van de lezer gevraagd wordt.
        soort = _type_van(n)
        kop_lijf = _TYPE_LIJF.get(soort)
        if kop_lijf:
            titel, uitleg = kop_lijf
            regels.insert(0, f"<p class='chip'>{_e(titel)}</p>")
            regels.append(f"<p class='muted'>{_e(uitleg)}</p>")
        if soort == "founder" and not k.get("hoort_hier"):
            regels.append("<p class='muted'>⚠ dit raakt geen founder-bevoegdheid — kandidaat voor "
                          "herroutering</p>")
        return "".join(regels)
    except Exception:                                   # noqa: BLE001 — nooit het scherm breken
        return ""


def _pagina_blok(st, n: dict) -> str:
    """Een pagina-voorstel is al concreet: wélke pagina, waarom, en wat er precies zou komen te
    staan. De generieke spanningskaart is voor een rauw signaal van een rol; hier is de vraag exact
    bekend, dus tonen we hem exact — inclusief wat er nu staat, want dat is het verschil waar de
    eigenaar ja of nee op zegt."""
    pag = dict(n.get("pagina") or {})
    if not pag:
        return ""
    from nooch_village import wiki
    titel = str(pag.get("titel") or pag.get("aid") or "")
    link = f"<a href='{_e(wiki.pagina_url(str(pag.get('aid') or '')))}'>{_e(titel)}</a>"
    reden = f"<p class='muted'>{_e(pag.get('reden'))}</p>" if pag.get("reden") else ""

    def _blok(kop: str, tekst: str) -> str:
        return (f"<details class='box-details'><summary class='muted'>{_e(kop)}</summary>"
                f"<div class='fbubble'>{_e(tekst).replace(chr(10), '<br>')}</div></details>")

    return (f"<div class='box rdr-rec'><strong>Proposal for page {link}</strong>"
            f"<p class='muted'>from {_e(pag.get('van_naam') or 'someone')}</p>{reden}"
            f"{_blok('proposed text', str(pag.get('body') or '(empty)'))}"
            f"{_blok('what it says now', str(pag.get('was') or '(empty)'))}</div>")


def _spanning_pane(st, n: dict) -> str:
    """Links: de volledige spanning met wie/rol, bron en leeftijd, plus het verwerk-record tot nu toe."""
    sep = "<span class='fsep'>·</span>"
    meta = (f"<div class='rdr-meta'><span class='muted'>via {_e(_who(st, n))}</span> {sep} "
            f"{_source_link(st, n)} {sep} <span class='muted'>{_e(_stamp(n.get('at')))}</span></div>")
    # DE KAART, en niet de rauwe snippet. Dit is het scherm dat de founder echt opent: stond hier de
    # dump ("Project van X vastgelopen op 1 mens-/extern item: 'Deze taak vereist…'"), dan is alle
    # herformulering in de CLI voor hem onzichtbaar geweest. Vier regels: wie werpt het op, vanuit
    # welke eigen verantwoordelijkheid, wat de spanning is, en wat hij van de founder nodig heeft.
    body = _kaart_html(st, n) or _e(_volledig(n) or "(no content)").replace("\n", "<br>")
    # De volledige vraag van de bewoner (founder, 19 jul): de snippet is maar 160 tekens,
    # het échte voorstel staat in de bron-feed-entry waar de notificatie naar wijst.
    # Zonder die tekst kan de mens niet beslissen ("er staat 2 besluiten maar niet welke").
    volledig = ""
    src_pid, src_eid = n.get("project_id") or "", n.get("entry_id") or ""
    if src_pid and src_eid:
        try:
            p = st.projects.get(src_pid)
            e = next((x for x in ((p or {}).get("log") or []) if x.get("id") == src_eid), None)
            tekst = (e or {}).get("text") or ""
            if tekst and tekst.strip() != _volledig(n).strip():
                volledig = (f"<div class='box rdr-rec'><strong>The full question</strong>"
                            f"<div class='fbubble'>{_e(tekst).replace(chr(10), '<br>')}</div></div>")
        except Exception:
            volledig = ""                       # fail-soft: geen bron = gewoon de snippet
    vs = st.notif.verwerkingen_of(n)
    record = ""
    if vs:
        rows = "".join(f"<li>{_e(v.get('label') or v.get('otype') or 'outcome')}"
                       f"{(' — ' + _e(v.get('by'))) if v.get('by') else ''}</li>" for v in vs)
        record = (f"<div class='box rdr-rec'><strong>Already recorded "
                  f"({len(vs)})</strong><ul>{rows}</ul></div>")
    return (f"<div class='rdr-pane'><h3>{_e(_woorden(n)['paneel'])}</h3>{meta}"
            f"<div class='fbubble rdr-rec'>{body}</div>{_pagina_blok(st, n)}"
            f"{volledig}{record}</div>")


def _at_doelen(st) -> list:
    """Wie kun je met `@` kiezen: WAKKERE rollen en personen. Meer niet.

    Slapende en gearchiveerde rollen staan er bewust niet bij — werk beloven aan een bureau waar
    niemand zit is precies wat we bij de afslanking wilden voorkomen, en het is dezelfde regel als
    in de wizard-rolkiezer en de uitkomst-rollijst van het werkoverleg.

    Cirkels ook niet: een cirkel heeft geen handen (harde regel 7), die delegeert."""
    from nooch_village import org
    alle = st.records.all()
    rollen = [r for r in alle
              if not org.is_circle(r) and not getattr(r, "archived", False)
              and not getattr(r, "slaapt", False)]
    labels = _rol_labels(rollen, alle)                 # Circle Lead ≠ Circle Lead: welke cirkel?
    uit = [{"id": r.id, "kind": "role", "label": labels.get(r.id) or _name(r)} for r in rollen]
    try:                                               # personen zijn een aanvulling, geen vereiste
        for p in st.people.all():
            naam = (getattr(p, "name", "") or "").strip()
            if naam:
                uit.append({"id": p.id, "kind": "person", "label": naam})
    except Exception:                                  # noqa: BLE001 — zonder personen kies je een rol
        pass
    return sorted(uit, key=lambda d: d["label"].lower())


_WIZ_OPEN = (
    "var f=this.closest('form');"
    "var q=new URLSearchParams({role:(f.owner?f.owner.value:''),"
    "ruw:(f.content?f.content.value:'')});"
    "var u='/project/nieuw?'+q.toString();"
    "if(window.__ovlOpen){window.__ovlOpen(u);}else{location.href=u;}"
)


def _actie_form(st, nid: str, csrf: str, prefill: str, pj_opts: str, nxt: str) -> str:
    """Flow 1 — Actie. Tekst, wie het doet (default jijzelf, `@` voor een ander), optioneel een
    lopend project.

    GEEN EIGEN ROUTING. Dit formulier post naar `notif_outcome`, en die roept `route_werk` aan —
    dezelfde regel als het werkoverleg en de wizard: een mens-vervulde rol krijgt het in zijn inbox,
    een AI-vervulde rol krijgt een project, want die leest de NotifStore nooit. Een tweede kopie van
    die regel hier zou na één wijziging uit de pas lopen en werk stil op de verkeerde plek laten
    landen — precies wat #364 wegnam."""
    doelen = _at_doelen(st)
    lijst = "".join(f"<option value='@{_e(d['label'])}'></option>" for d in doelen)
    kaart = _json_min([{"l": d["label"], "v": f"{d['kind']}:{d['id']}"} for d in doelen])
    # `.qadd-form` (kolom) en niet `.wo-oc` (rij): `.wo-oc` is `display:flex; align-items:center`
    # en bedoeld voor de compacte twee-veld-vorm. Met drie veldgroepen zet die de labels NAAST de
    # velden — op het scherm gezien, niet in een test. Hergebruik het bestaande vocabulaire uit
    # docs/UX_PATTERNS.md; geen nieuwe klasse.
    return (f"<form method='post' action='/action' class='qadd-form' "
            f"onsubmit='return ibxAtResolve(this)'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
            f"<input type='hidden' name='nid' value='{_e(nid)}'>"
            f"<input type='hidden' name='otype' value='action'>"
            f"<input type='hidden' name='next' value='{_e(nxt)}'>"
            f"<input type='hidden' name='doel' value=''>"
            f"<script type='application/json' data-at-kaart>{kaart}</script>"
            + _field("What needs to happen?", "content", kind="textarea", value=prefill,
                     fid=f"act-ct-{nid}")
            + f"<label class='att-lbl' for='act-wie-{_e(nid)}'>Who does it?</label>"
              f"<input id='act-wie-{_e(nid)}' data-at-veld list='at-{_e(nid)}' "
              f"placeholder='you — type @ for someone else' autocomplete='off'>"
              f"<datalist id='at-{_e(nid)}'>{lijst}</datalist>"
            + f"<label class='att-lbl' for='act-pj-{_e(nid)}'>Part of a running project? "
              f"(optional)</label>"
              f"<select id='act-pj-{_e(nid)}' name='pid_link'>"
              f"<option value=''>no — just an action</option>{pj_opts}</select>"
              f"<p class='muted'>Linked to a project, it becomes a step in that project's "
              f"checklist — the project's role owns that list.</p>"
            + f"<button class='btn ok sm' name='action' value='notif_outcome'>Add action</button>"
            f"</form>")


def _json_min(rows: list) -> str:
    """JSON voor in een <script>-blok. `<` wordt geëscaped zodat een label nooit het blok kan
    sluiten — dat is de enige injectie-route die een JSON-script-tag heeft."""
    import json
    return json.dumps(rows, ensure_ascii=False).replace("<", "\u003c")


def _outcome_form(otype: str, nid: str, csrf: str, prefill: str, role_opts: str, pj_opts: str,
                  nxt: str, uid: str) -> str:
    """Wat er achter een flow-kop uitklapt.

    Nog twee gevallen, en dat is de hele opruiming: PROJECT is een DEUR naar de wizard, en
    ROLOVERLEG staat ongewijzigd tot flow 3 apart ontworpen is. De oude takken (`ping`, `action`,
    `note`) zijn weg — `action` heeft nu zijn eigen formulier met `@`-keuze (`_actie_form`), en
    `ping`/`note` waren de info-intentie die uit de inbox verdwijnt.

    EEN INGANG IS EEN DEUR, GEEN FORMULIER (docs/CONVENTIES.md, geleerd bij #375). Hier stond een
    tekstveld plus een rolkiezer plus een knop — dat ziet eruit als een tweede plek waar je een
    project maakt, en de rolkiezer bood bovendien de rollen van ANDEREN aan. Werk bij een andere rol
    neerleggen is een verzoek, en een verzoek is een actie met `@`; een rol is baas over zijn eigen
    bord. Dus: één link, met de spanningstekst als zaad en de wizard gescoped op je eigen rollen."""
    if otype == "project":
        # `mine=1` scopet de rolkiezer van de wizard op de rollen die JIJ vervult, plus Individuele
        # actie. `target=_top` omdat de verwerk-pagina als iframe in de inbox-lade draait: zonder
        # dat opent de wizard in een strook van 460 pixels.
        # `nid` MOET MEE. Zonder dat kent de wizard de spanning niet, kan hij geen uitkomst
        # terugmelden en blijft de bron open — precies het subsidie-geval: project gemaakt, spanning
        # bleef staan, en de mens moest zelf raden dat er nog een klik nodig was.
        href = "/project/nieuw?" + _urlencode({"ruw": prefill, "mine": "1", "nid": nid})
        return (f"<a class='btn ok sm' href='{_e(href)}' target='_top'>"
                f"Open the project wizard</a>")
    # roloverleg — ongewijzigd: gebruikt de cirkel van de bron.
    hid = (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
           f"<input type='hidden' name='nid' value='{_e(nid)}'>"
           f"<input type='hidden' name='otype' value='{_e(otype)}'>"
           f"<input type='hidden' name='next' value='{_e(nxt)}'>")
    tgt = ("<span class='muted'>Becomes a proposal on the governance meeting agenda "
           "(human route).</span>")
    inhoud = _field("Content (editable)", "content", kind="textarea", value=prefill, fid=f"ct-{uid}")
    knop = "<button class='btn sm' name='action' value='notif_outcome'>Record</button>"
    return (f"<form method='post' action='/action' class='wo-oc'>{hid}"
            f"{inhoud}{tgt}{knop}</form>")


def _urlencode(d: dict) -> str:
    from urllib.parse import urlencode
    return urlencode({k: v for k, v in d.items() if v})


# ── De hoofdactie, één keer geschreven ───────────────────────────────────────
#
# Deze drie bouwers stonden als geneste functies in `_wizard_pane`, en dat was prima zolang de
# verwerk-pagina de enige plek was waar je iets kon afhandelen. Nu de lijst hetzelfde inline aanbiedt
# zouden het twee kopieën worden: dezelfde drie knoppen, met de kans dat er over een maand één set
# een veld erbij krijgt en de andere niet. Eén bouwer, twee plekken die hem aanroepen.

def _keuze_form(nid: str, csrf: str, *, actie: str, veld: str, keuze: str, label: str, cls: str,
                hint: str, verplicht: bool, tekstveld: str, nxt: str = "/inbox") -> str:
    req = " required" if verplicht else ""
    return (f"<details class='wo-ocd box-details'><summary><strong>{label}</strong></summary>"
            f"<form method='post' action='/action' class='wo-oc'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
            f"<input type='hidden' name='nid' value='{_e(nid)}'>"
            f"<input type='hidden' name='{_e(veld)}' value='{_e(keuze)}'>"
            f"<input type='hidden' name='next' value='{_e(nxt)}'>"
            f"<textarea name='{_e(tekstveld)}' rows='2' placeholder='{_e(hint)}' "
            f"aria-label='note'{req}></textarea>"
            f"<button class='btn {cls}sm' name='action' value='{_e(actie)}'>{label}"
            f"</button></form></details>")


def _verzoek_knoppen(n: dict, csrf: str, nxt: str = "/inbox") -> str:
    """Accepteren / aanpassen / weigeren op een PAGINA-voorstel.

    Alleen daar nog. Voor een operationeel verzoek stond dit ook, en dat was fout op twee manieren:
    ongebruikt (0 weigeringen en 0 herformuleringen over de hele historie) én in strijd met de regel
    dat rol-werk je borgt en andermans werk je doorgeeft. Een pagina-voorstel is een ander geval:
    accepteren IS er de handeling (een nieuwe versie), niet een project dat het nog moet gaan doen."""
    nid = n.get("id", "")

    def _f(keuze, label, cls, hint, verplicht):
        return _keuze_form(nid, csrf, actie="verzoek_besluit", veld="keuze", keuze=keuze,
                           label=label, cls=cls, hint=hint, verplicht=verplicht,
                           tekstveld="tekst", nxt=nxt)
    return (_f("accepteer", "✓ Accepteren", "ok ", "optioneel: een notitie bij je ja", False)
            + _f("aanpassen", "✎ Formulering aanpassen", "",
                 "hoe zou het verzoek wél kloppen? gaat terug naar de vrager", True)
            + _f("weiger", "✗ Weigeren", "", "waarom niet — de vrager leert hiervan", True)
            # Bij een pagina-voorstel is accepteren de handeling zélf (nieuwe versie), niet een
            # project dat het nog moet gaan doen. Eén zin, maar hij bepaalt wat de lezer denkt
            # te tekenen.
            + "<p class='muted'>Accepting saves the proposed text as a new version of the "
              "page — no project.</p>")


# De kop, de knop en de paginatitel volgen het TYPE. Eén neutrale term zou voor alles half goed
# zijn: "spanning" klopt voor een gesensd signaal maar niet voor een afspraak uit een overleg, en
# "item" klopt nergens echt. De kaart weet zijn type al (`_type_van`), dus laat de woorden dat
# volgen. Alleen de ACTIE wijkt af; verzoek, governance en besluit houden hun eigen vocabulaire, en
# alles zonder eigen type blijft "tension".
_TYPE_WOORDEN = {
    "actie": {"kop": "Actie afronden", "paneel": "Actie", "klaar": "Actie afgerond"},
}
_STANDAARD_WOORDEN = {"kop": "Process tension", "paneel": "Tension",
                      "klaar": "Done with this tension"}


def _woorden(n: dict | None) -> dict:
    return _TYPE_WOORDEN.get(_type_van(n or {}), _STANDAARD_WOORDEN)


def _klaar_knop(nid: str, csrf: str, nxt: str = "/inbox", n: dict | None = None) -> str:
    """De VIERDE uitkomst, en de enige die er altijd al was: sluiten.

    Sinds Decide-now weg is draagt hij een optionele REDEN. Dat is geen nieuwe flow maar het gat dat
    de drie handelings-flows per definitie niet dekken: actie, project en governance veronderstellen
    alle drie dát er iets gebeurt, en "nee, want …" is precies het tegendeel.

    De reden gaat TERUG NAAR DE VRAGER als comment op de bron-feed — opslaan alleen zou de
    terugkoppeling stil laten verdwijnen die Decide-now's "nee" wél gaf."""
    reden = ""
    if n is not None and n.get("project_id"):
        reden = _field("Why (optional) — goes back to whoever asked", "reden", kind="textarea",
                       value="", fid=f"kl-r-{nid}")
    return (f"<form method='post' action='/action' class='emo-f rdr-rec'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
            f"<input type='hidden' name='nid' value='{_e(nid)}'>"
            f"<input type='hidden' name='next' value='{_e(nxt)}'>{reden}"
            f"<button class='btn ok sm' name='action' value='notif_klaar'>"
            f"{_e(_woorden(n)['klaar'])}</button></form>")


def _wizard_pane(st, n: dict, csrf: str, role_opts: str, pj_opts: str) -> str:
    """Rechts: wat doe je met deze spanning?

    Drie vormen, en welke je krijgt hangt van het TYPE af — een verzoek en een al afgesproken actie
    hebben hun eigen, kortere handeling. Alleen een gewone spanning krijgt de twee flows.
    'Klaar' sluit het item ook zonder uitkomst (FYI-klep)."""
    from nooch_village import zelf_verwerking as zv

    nid = n.get("id", "")
    prefill = _volledig(n)                   # de flows werken op de hele tekst
    nxt = f"/inbox/verwerk?nid={nid}"
    klaar = _klaar_knop(nid, csrf, n=n)

    # DE DRIE KNOPPEN op een operationeel verzoek: accepteren, aanpassen, weigeren. Dat is het
    # "in één handeling" waar de kaart om vraagt — een uitleg zonder knop laat de lezer alsnog
    # zoeken waar hij ja moet zeggen.
    # EEN OPERATIONEEL VERZOEK KRIJGT HET GEWONE SCHERM. Hier stonden accepteren / aanpassen /
    # weigeren, en de meting over de hele prod-historie zei: 0 weigeringen, 0 herformuleringen, 3
    # accepteringen — die alle drie een project werden. Eén gebruikte tak van de drie.
    #
    # En de twee dode takken waren niet alleen ongebruikt maar verkeerd. Hoort het verzoek bij jouw
    # rol, dan BORG je het (project); hoort het er niet bij, dan DEEL je het door (actie naar wie het
    # wél draagt). "Nee" is in beide gevallen het verkeerde werkwoord: het sluit een vraag zonder
    # hem ergens te laten landen. Zie docs/CONVENTIES.md — het werkwoord bepaalt of het werk
    # doorloopt.
    #
    # Een PAGINA-voorstel blijft wél zijn eigen scherm houden, en dat is geen uitzondering op de
    # regel maar een ander geval: daar IS accepteren de handeling zelf (een nieuwe versie van de
    # pagina), niet een project dat het nog moet gaan doen.
    if _type_van(n) == "naar_rol" and n.get("pagina"):
        return ("<div class='rdr-pane'><h3>Wat doe je met dit voorstel?</h3>"
                + _verzoek_knoppen(n, csrf) + klaar + "</div>")

    # EEN ACTIE IS AL AFGESPROKEN. De flows vragen "wat doe je hiermee?" en dat is hier de verkeerde
    # vraag: het besluit is al genomen. Twee handelingen blijven over — afvinken, of erkennen dat
    # het meer is dan één handeling en er een project van maken.
    if _type_van(n) == zv.ACTIE:
        pj = _outcome_form("project", nid, csrf, prefill, role_opts, pj_opts, nxt, "actie-project")
        return ("<div class='rdr-pane'><h3>Wat doe je met deze actie?</h3>"
                f"{klaar}"
                f"<details class='wo-ocd box-details'><summary>Meer dan één handeling? → "
                f"<strong>maak er een project van</strong></summary>{pj}</details></div>")

    # TWEE CONCRETE FLOWS, en het label draagt de uitleg. De oude boom vroeg je eerst je INTENTIE te
    # classificeren ('info' / 'zelf' / 'iemand anders') voordat je iets mocht doen; over 560 items
    # leverde dat 42 uitkomsten op, waarvan 26x 'niks nodig' en 0x een actie.
    groups = []
    for flow in FLOWS:
        body = (_actie_form(st, nid, csrf, prefill, pj_opts, nxt) if flow["key"] == "action"
                else _outcome_form("project", nid, csrf, prefill, role_opts, pj_opts, nxt,
                                   f"flow-{flow['key']}"))
        groups.append(
            f"<details class='box-details'><summary><strong>{_e(flow['label'])}</strong> "
            f"<span class='muted'>&mdash; {_e(flow['regel'])}</span></summary>"
            f"<p class='muted'>{_e(flow['hulp'])}</p>{body}</details>")
    # De governance-route staat er ongewijzigd bij tot flow 3 apart ontworpen is.
    groups.append(
        f"<details class='box-details'><summary><strong>{_e(GOVERNANCE['label'])}</strong> "
        f"<span class='muted'>&mdash; {_e(GOVERNANCE['regel'])}</span></summary>"
        + _outcome_form("roloverleg", nid, csrf, prefill, role_opts, pj_opts, nxt, "flow-gov")
        + "</details>")

    # DECIDE NOW IS WEG. Een eigen knoppenrij (ja / nee / suggestie) voor 12 van de 570 items, en
    # negen daarvan waren gewoon een ACTIE: een antwoord waarmee een vastgelopen bewoner verder kan.
    # Die lopen nu via flow 1, met de AI-rol als ontvanger — `route_werk` maakt daar een project van,
    # want een AI-rol leest de inbox nooit.
    #
    # De tiende vorm, "nee, want …", paste in géén van de drie handelings-flows: die veronderstellen
    # alle drie dát er iets gebeurt. Die hoort bij de VIERDE uitkomst, sluiten — zie `_klaar_knop`,
    # dat nu een optioneel reden-veld draagt en die reden terugstuurt naar de vrager.
    return (f"<div class='rdr-pane'><h3>What do you do with this?</h3>"
            f"{''.join(groups)}{klaar}</div>")


def render_verwerk(st, n: dict, csrf_token: str = "", role_opts: str = "", pj_opts: str = "") -> str:
    """De verwerk-pagina voor één inbox-item: links de spanning, rechts de intentie-wizard."""
    if n is None:
        inner = (f"{_DS_LINK}<div class='c2-wrap'><div class='c2-main'><a href='/inbox'>← inbox</a>"
                 "<p class='muted'>This tension no longer exists.</p></div></div>")
        return _page("Process", inner)
    split = (f"<div class='rdr-split'>"
             f"{_spanning_pane(st, n)}{_wizard_pane(st, n, csrf_token, role_opts, pj_opts)}</div>")
    main = (f"<div class='c2-main'><h1>{_e(_woorden(n)['kop'])}</h1>{split}</div>")
    # De @-resolver hoort HIER, niet in de chrome: deze pagina draait als iframe in de inbox-lade en
    # krijgt de drawer-JS dus niet mee (chrome=False).
    inner = (f"{_DS_LINK}<div class='c2-wrap'>{main}</div><script>{_AT_JS}</script>")
    return _page("Process", inner)


# ── de globale inbox-drawer (chrome op elke pagina) + het lijst-fragment ──────────
def _ibx_row(st, n: dict) -> str:
    """Eén kaartje in de drawer. Open item → klik opent de modal-wizard; verwerkt item → sleep naar
    rechts om te archiveren."""
    nid = n.get("id", "")
    status = st.notif.status_of(n)
    # De VOLLE tekst als bron, niet de 160-tekens-preview: die was zelf al afgekapt, en dan kapte
    # `_one_line` de afkapping nog eens af. `title=` op het element geeft de hele zin bij hover, zodat
    # de korte regel scanbaar blijft zonder de rest te verliezen.
    _vol = _leesbaar(n, _volledig(n) or str(n.get("snippet") or ""))
    title = _e(_one_line(_vol))
    _hover = _e(_vol[:400])
    who = _e(_who(st, n))
    # 'verwerkt' (bekeken, blijft in de wachtrij) en 'klaar' (gesloten, verlaat hem) tonen allebei
    # hun record. Een gesloten spanning komt hier alleen langs voor het viermoment: `render_inbox`
    # zet hem daar eenmalig terug in de lijst.
    if status in ("verwerkt", "klaar"):
        vs = st.notif.verwerkingen_of(n)
        kader = "".join(f"<div class='ibx-kader'>✓ {_e(v.get('label') or 'outcome')}</div>" for v in vs)
        return (f"<div class='ibx-row done' data-nid='{_e(nid)}'><span class='ibx-dot read'></span>"
                f"<div class='ibx-rb'><div class='ibx-title' title='{_hover}'>{title}</div>"
                f"<div class='ibx-meta'>processed · {who}</div>{kader}</div>"
                f"<span class='ibx-swipe'>swipe &rarr; archive</span></div>")
    dot = "ibx-dot read" if status == "gelezen" else "ibx-dot"
    return (f"<div class='ibx-row' data-nid='{_e(nid)}' onclick=\"ibxOpen('{_e(nid)}')\">"
            f"<span class='{dot}'></span><div class='ibx-rb'><div class='ibx-title' title='{_hover}'>{title}</div>"
            f"<div class='ibx-meta'>via {who} &middot; {_e(_stamp(n.get('at')))}</div></div>"
            f"<button class='ibx-trash' title='delete' "
            f"onclick=\"event.stopPropagation();ibxTrash('{_e(nid)}')\">&#128465;</button></div>")


def render_inbox_frag(st, targets, csrf_token: str = "") -> str:
    """Het dynamische deel van de drawer: telling + rijen, opgehaald via /inbox?frag=1. Geen page-shell
    (de shell is de chrome). De drawer-JS leest data-count/data-sub en vult de lijst."""
    items = st.notif.open_for_targets(targets)
    nieuw = sum(1 for n in items if st.notif.status_of(n) == "nieuw")
    rows = "".join(_ibx_row(st, n) for n in items) or \
        "<div class='ibx-empty'><div class='ibx-party'>&#127881;</div>Your inbox is empty.</div>"
    sub = f"{len(items)} open, of which {nieuw} new" if items else "All processed — enjoy it."
    return f"<div data-count='{len(items)}' data-sub='{_e(sub)}'>{rows}</div>"


def _person_role_options(st, targets) -> str:
    """Opties voor 'vanuit welke rol voel je het' bij zelf een spanning toevoegen: de rollen die de
    ingelogde persoon vervult, plus 'als mezelf'."""
    recs = [r for r in (st.records.get(tid) for ty, tid in targets if ty == "role")
            if r is not None]
    labels = _rol_labels(recs, st.records.all())      # Circle Lead ≠ Circle Lead: welke cirkel?
    opts = ["<option value=''>as myself</option>"]
    opts += [f"<option value='{_e(r.id)}'>{_e(labels.get(r.id) or _name(r))}</option>"
             for r in recs]
    return "".join(opts)


# De `@`-resolver. Het zichtbare veld is een gewone tekst-input met een datalist (autocomplete op
# elk toetsaanslag, zonder eigen dropdown-implementatie); bij het versturen vertaalt dit het GEKOZEN
# LABEL naar `kind:id`. Staat er iets dat niet in de lijst staat, dan blijft `doel` leeg en is de
# actie voor jezelf — FAIL-CLOSED: liever bij jezelf dan bij een geraden ander.
_AT_JS = """
function ibxAtResolve(f){
  var veld=f.querySelector('[data-at-veld]'), kaart=f.querySelector('[data-at-kaart]');
  var doel=f.querySelector("input[name='doel']");
  if(!veld||!kaart||!doel)return true;
  var t=(veld.value||'').trim().replace(/^@/,'').toLowerCase();
  doel.value='';
  if(!t)return true;
  try{
    var rows=JSON.parse(kaart.textContent||'[]');
    for(var i=0;i<rows.length;i++){
      if((rows[i].l||'').toLowerCase()===t){doel.value=rows[i].v;break;}
    }
  }catch(e){}
  return true;
}
"""

_IBX_JS = """
var IBX_CSRF=__IBX_CSRF__;
function ibxToggle(){var d=document.getElementById('ibx-drawer');d.classList.toggle('open');
  if(d.classList.contains('open'))ibxRefresh();}
function ibxAddToggle(){document.getElementById('ibx-add').classList.toggle('open');}
function ibxWeigering(u){try{var q=new URL(u,location.origin).searchParams;
  if(q.get('ok')!=='0')return '';return q.get('msg')||'\u26a0 geweigerd';}catch(e){return '';}}
function ibxMelding(t){var e=document.getElementById('ibx-melding');
  if(!e)return;e.textContent=t||'';e.classList.toggle('hide',!t);}
/* EEN MISLUKTE POST MOET ZICHZELF MELDEN. Stond hier eerst een kale fetch: het veld leegde zich,
   de drawer klapte dicht, de lijst ververste — en er was niets toegevoegd. Een 403 na een herstart
   (sessie en CSRF-token leven in het procesgeheugen) zag er precies zo uit als succes. */
function ibxPost(a,x){return fetch('/action',{method:'POST',
  headers:{'Content-Type':'application/x-www-form-urlencoded'},
  body:new URLSearchParams(Object.assign({action:a,csrf:IBX_CSRF,next:'/inbox'},x||{}))})
  .then(function(r){
    /* DEZELFDE BLINDE VLEK ALS BIJ DE PROJECTEN-DONE: `r.ok` meet het TRANSPORT, niet de UITKOMST.
       Een inhoudelijke weigering ("✗ …", "No access — …") reist als melding op een 303; fetch volgt
       die, de status is 200, en dit zette de drawer op groen. De server markeert de weigering nu
       zelf met ok=0; wij lezen die markering en tonen de reden die er al bij zat. */
    if(r.ok){var w=ibxWeigering(r.url);
             if(w){ibxMelding(w.slice(0,140));throw new Error('ibxPost geweigerd');}
             ibxMelding('');return r;}
    ibxMelding(r.status===403?'Your session expired — reload the page and sign in again.'
                             :'Could not save that ('+r.status+'). Nothing was added.');
    throw new Error('ibxPost '+r.status);})
  .catch(function(e){
    if(String(e.message||'').indexOf('ibxPost')!==0)
      ibxMelding('No connection to the village. Nothing was added.');
    throw e;});}
function ibxRefresh(){return fetch('/inbox?frag=1').then(function(r){
  if(!r.ok){ibxMelding(r.status===403?'Your session expired — reload the page and sign in again.'
                                     :'Could not load the inbox ('+r.status+').');
            throw new Error('ibxRefresh '+r.status);}
  return r.text();}).then(function(h){
  var t=document.createElement('div');t.innerHTML=h;var w=t.firstElementChild;
  var cnt=w?parseInt(w.getAttribute('data-count')||'0',10):0;
  document.getElementById('ibx-list').innerHTML=w?w.innerHTML:h;
  document.getElementById('ibx-hct').textContent=cnt;
  var b=document.getElementById('ibx-badge');b.textContent=cnt;b.classList.toggle('hide',cnt===0);
  document.getElementById('ibx-launch').classList.toggle('zero',cnt===0);
  document.getElementById('ibx-icon').textContent=cnt?'\\uD83D\\uDCE5':'\\uD83C\\uDF89';
  document.getElementById('ibx-sub').textContent=w?(w.getAttribute('data-sub')||''):'';
  ibxBindSwipe();});}
function ibxOpen(nid){var f=document.getElementById('ibx-frame');
  f.src='/inbox/verwerk?nid='+encodeURIComponent(nid);
  document.getElementById('ibx-scrim').classList.add('open');}
function ibxCloseModal(){document.getElementById('ibx-scrim').classList.remove('open');
  document.getElementById('ibx-frame').src='about:blank';}
function ibxFrameLoad(){try{var p=document.getElementById('ibx-frame').contentWindow.location.pathname;
  if(p==='/inbox'){ibxCloseModal();ibxThumb();ibxRefresh();}}catch(e){}}
function ibxAddSubmit(){var t=document.getElementById('ibx-addtext'),r=document.getElementById('ibx-addrole');
  if(!t.value.trim())return;ibxPost('notif_add',{text:t.value.trim(),role:r.value}).then(function(){
    t.value='';ibxAddToggle();ibxRefresh();}).catch(function(){/* melding staat er al; tekst blijft
    staan zodat de mens hem niet opnieuw hoeft te typen */});}
function ibxTrash(nid){ibxPost('notif_delete',{nid:nid}).then(ibxRefresh);}
function ibxThumb(){var t=document.getElementById('ibx-thumb');t.classList.add('on');
  setTimeout(function(){t.classList.remove('on');},900);}
function ibxBindSwipe(){var rows=document.querySelectorAll('.ibx-row.done');
  for(var i=0;i<rows.length;i++){(function(el){var sx=0,dx=0,drag=false;
    el.onpointerdown=function(e){drag=true;sx=e.clientX;el.setPointerCapture(e.pointerId);};
    el.onpointermove=function(e){if(!drag)return;dx=Math.max(0,e.clientX-sx);
      el.style.setProperty('transform','translateX('+dx+'px)');
      el.style.setProperty('opacity',String(1-Math.min(dx/220,.6)));};
    var end=function(){if(!drag)return;drag=false;
      if(dx>90){el.style.setProperty('transform','translateX(120%)');el.style.setProperty('opacity','0');
        ibxPost('notif_archive',{nid:el.getAttribute('data-nid')}).then(function(){setTimeout(ibxRefresh,160);});}
      else{el.style.setProperty('transform','');el.style.setProperty('opacity','');}dx=0;};
    el.onpointerup=end;el.onpointercancel=end;})(rows[i]);}}
document.getElementById('ibx-frame').addEventListener('load',ibxFrameLoad);
ibxRefresh();
"""


def render_inbox_chrome(csrf_token: str = "", role_opts: str = "") -> str:
    """De globale inbox-drawer die op elke ingelogde pagina wordt geïnjecteerd: launcher-knop met badge,
    uitschuif-paneel links, en de modal die de bestaande verwerk-pagina in een iframe toont. De lijst en
    de telling worden lui opgehaald via /inbox?frag=1 (JS), zodat de injectie zelf licht blijft."""
    launch = ("<button class='ibx-launch' id='ibx-launch' title='Inbox' onclick='ibxToggle()'>"
              "<span id='ibx-icon'>&#128229;</span><span class='ibx-ct hide' id='ibx-badge'>0</span></button>")
    add = ("<div class='ibx-add' id='ibx-add'>"
           "<label for='ibx-addtext'>What do you feel?</label>"
           "<textarea id='ibx-addtext' placeholder='a tension, question or loose thought…'></textarea>"
           "<label for='ibx-addrole'>From which role?</label>"
           f"<select id='ibx-addrole'>{role_opts}</select>"
           "<div class='rdr-rec'><button class='btn ok sm' onclick='ibxAddSubmit()'>Add</button> "
           "<button class='btn sm' onclick='ibxAddToggle()'>Cancel</button></div></div>")
    drawer = ("<aside class='ibx-drawer' id='ibx-drawer'>"
              "<div class='ibx-head'><h2>Inbox</h2><span class='ibx-hct' id='ibx-hct'>0</span>"
              "<button class='ibx-plus' title='Add tension' onclick='ibxAddToggle()'>+</button>"
              "<button class='ibx-x' title='close' onclick='ibxToggle()'>&times;</button></div>"
              "<div class='ibx-sub' id='ibx-sub'></div>"
              "<div class='ibx-sub ibx-err hide' id='ibx-melding'></div>" + add +
              "<div class='ibx-list' id='ibx-list'></div></aside>")
    modal = ("<div class='ibx-scrim' id='ibx-scrim'><div class='ibx-modal'>"
             "<button class='ibx-mx' title='close' onclick='ibxCloseModal()'>&times;</button>"
             "<iframe class='ibx-iframe' id='ibx-frame' title='Process tension'></iframe></div></div>"
             "<div class='ibx-thumb' id='ibx-thumb'>&#128077;</div>")
    return (launch + drawer + modal + "<script>"
            + _IBX_JS.replace("__IBX_CSRF__", json.dumps(csrf_token)) + "</script>")
