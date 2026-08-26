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

from nooch_village.web_base import _e, _page, _field
from nooch_village.cockpit2_util import _name, _BUILD, _stamp, _DS_LINK, _nav
from nooch_village.inbox_wizard import INTENTS, OTYPE_LABEL

_STATUS = {"nieuw": ("● new", "chip ok"), "gelezen": ("busy", "chip muted"),
           "verwerkt": ("✓ handled", "chip outline")}


def _source_link(st, n: dict) -> str:
    pid = (n.get("project_id") or "").strip()
    p = st.projects.get(pid) if pid else None
    if p is not None:
        scope = str(p.get("scope") or "project")[:60]
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
    t = " ".join((text or "").split())
    return (t[:cap] + "…") if len(t) > cap else (t or "(no summary)")


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
_TYPE_CHIP = {"founder": "besluit", "naar_rol": "verzoek", "governance": "governance"}


def _een_regel(n: dict) -> str:
    """De bevinding als hij er is, anders de rauwe signalering.

    De bevinding is de zin die voor een mens is geschreven; de snippet is de interne verpakking van
    160 tekens. Stond de snippet hier, dan is alle herformulering onzichtbaar precies op het scherm
    waar je kiest wat je opent."""
    b = dict(n.get("bevinding") or {})
    if b.get("ok") and b.get("spanning"):
        return _one_line(b["spanning"])
    return _one_line(n.get("snippet"))


def _inline_actie(st, n: dict, csrf: str) -> str:
    """De hoofdactie in de regel zelf. De modal blijft voor de diepte.

    Dezelfde knoppen als op de verwerk-pagina — letterlijk dezelfde bouwers, niet een tweede set.
    Is er voor dit type geen knop die in één handeling klopt (een governance-voorstel weegt de poort,
    dat doe je niet vanuit een lijst), dan staat er geen uitklap: een lege accordeon is erger dan
    geen accordeon."""
    soort = _type_van(n)
    if soort == "naar_rol":
        binnen = _verzoek_knoppen(n, csrf)
    elif n.get("project_id"):
        binnen = _besluit_knoppen(n, csrf)
    else:
        return ""
    if not binnen:
        return ""
    return (f"<details class='wo-ocd box-details'><summary>handle here</summary>"
            f"{binnen}{_klaar_knop(n.get('id', ''), csrf)}</details>")


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
    title = f"<div class='rdr-sig'>{_e(_een_regel(n))}</div>"

    if status == "verwerkt":
        vs = st.notif.verwerkingen_of(n)
        chips = " ".join(f"<span class='chip outline'>{_e(v.get('label') or 'outcome')}</span>" for v in vs) \
            or "<span class='chip outline'>handled</span>"
        body = f"{meta}{title}<div class='ffoot-l'>{chips}</div>"
        act = f"<div class='rdr-act'>{_btn(csrf, nid, 'notif_archive', 'archive')}</div>"
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
}


def _type_van(n: dict) -> str:
    """Het type van dit item: uit het poort-oordeel, anders uit de tekst zelf (verse spanning)."""
    from nooch_village import tensie_poort as tp, zelf_verwerking as zv

    # Het type dat bij het ONTSTAAN is bepaald wint: dat is de bron, de poort komt later. Zonder
    # deze regel toonde een verse spanning wél de kaart maar niet de bijbehorende knoppen — de
    # linkerkant wist zijn type en de rechterkant niet.
    eigen = str(n.get("type") or "")
    if eigen in (zv.NAAR_ROL, zv.GOVERNANCE, zv.FOUNDER):
        return eigen
    deur = str((n.get("poort") or {}).get("deur") or "")
    if deur == tp.DEUR_BESLUIT:
        return zv.FOUNDER
    if deur == tp.GEROUTEERD:
        return zv.NAAR_ROL
    tekst = str(n.get("snippet") or "")
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

        tekst = str(n.get("snippet") or "")
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
            regels.append(f"<div class='fbubble'>{_e(kern or tekst)}</div>")
            regels.append(f"<p class='muted'>⚠ moet herschreven: {_e(herschreven.get('reden'))}</p>")
        else:
            regels.append(f"<div class='fbubble'>{_e(kern or tekst)}</div>")
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
    body = _kaart_html(st, n) or _e(n.get("snippet") or "(no content)").replace("\n", "<br>")
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
            if tekst and tekst.strip() != (n.get("snippet") or "").strip():
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
    return (f"<div class='rdr-pane'><h3>Tension</h3>{meta}"
            f"<div class='fbubble rdr-rec'>{body}</div>{_pagina_blok(st, n)}"
            f"{volledig}{record}</div>")


def _outcome_form(otype: str, nid: str, csrf: str, prefill: str, role_opts: str, pj_opts: str,
                  nxt: str, uid: str) -> str:
    """Het compacte formulier achter een uitkomst-knop. Alleen relevante velden, met gekoppelde labels
    (for=/id via _field of expliciet). Post naar notif_outcome, blijft daarna op de verwerk-pagina zodat
    je uitkomsten kunt stapelen. `uid` maakt de veld-ids uniek (dezelfde uitkomst kan meermaals op de
    pagina staan)."""
    hid = (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
           f"<input type='hidden' name='nid' value='{_e(nid)}'>"
           f"<input type='hidden' name='otype' value='{_e(otype)}'>"
           f"<input type='hidden' name='next' value='{_e(nxt)}'>")
    if otype == "ping":
        sid = f"sel-{uid}"
        tgt = (f"<label class='att-lbl' for='{sid}'>To which role?</label>"
               f"<select id='{sid}' name='ping_role'>{role_opts}</select>")
    elif otype == "project":
        sid = f"sel-{uid}"
        tgt = (f"<label class='att-lbl' for='{sid}'>On which role?</label>"
               f"<select id='{sid}' name='owner'>{role_opts}</select>")
    elif otype == "action":
        sid = f"sel-{uid}"
        tgt = (f"<label class='att-lbl' for='{sid}'>To which project?</label>"
               f"<select id='{sid}' name='pid_link'>{pj_opts}</select>")
    elif otype == "note":
        sid = f"sel-{uid}"
        tgt = (f"<label class='att-lbl' for='{sid}'>Note on which role?</label>"
               f"<select id='{sid}' name='note_role'>{role_opts}</select>")
    else:  # roloverleg — gebruikt de cirkel van de bron
        tgt = "<span class='muted'>Becomes a proposal on the governance meeting agenda (human route).</span>"
    inhoud = _field("Content (editable)", "content", kind="textarea", value=prefill, fid=f"ct-{uid}")
    return (f"<form method='post' action='/action' class='wo-oc'>{hid}"
            f"{inhoud}{tgt}"
            f"<button class='btn sm' name='action' value='notif_outcome'>Record</button></form>")


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
    """Accepteren / aanpassen / weigeren op een operationeel verzoek."""
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
            + ("<p class='muted'>Accepting saves the proposed text as a new version of the "
               "page — no project.</p>" if n.get("pagina") else
               "<p class='muted'>Bij accepteren verschijnt dit als project op je bord.</p>"))


def _besluit_knoppen(n: dict, csrf: str, nxt: str = "/inbox") -> str:
    """Ja / nee / suggestie op een vraag van een bewoner. Alleen met een bron-project: het antwoord
    landt als reactie in die feed, en zonder bron is er niets om op te antwoorden."""
    if not n.get("project_id"):
        return ""
    nid = n.get("id", "")

    def _f(keuze, label, cls, hint, verplicht):
        return _keuze_form(nid, csrf, actie="notif_besluit", veld="besluit", keuze=keuze,
                           label=label, cls=cls, hint=hint, verplicht=verplicht,
                           tekstveld="toelichting", nxt=nxt)
    return (_f("ja", "✓ Yes", "ok ", "optional: note with your yes", False)
            + _f("nee", "✗ No", "", "optional: why not — the inhabitant learns from it", False)
            + _f("suggestie", "💬 Suggestion", "", "your suggestion or counter-question", True))


def _klaar_knop(nid: str, csrf: str, nxt: str = "/inbox") -> str:
    return (f"<form method='post' action='/action' class='emo-f rdr-rec'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
            f"<input type='hidden' name='nid' value='{_e(nid)}'>"
            f"<input type='hidden' name='next' value='{_e(nxt)}'>"
            f"<button class='btn ok sm' name='action' value='notif_klaar'>Done with this tension"
            f"</button></form>")


def _wizard_pane(n: dict, csrf: str, role_opts: str, pj_opts: str) -> str:
    """Rechts: Wat heb je nodig? Per intentie een accordeon; per uitkomst een vraag + knop die het
    compacte formulier uitklapt. 'Niks nodig' sluit het item direct (FYI-klep)."""
    nid = n.get("id", "")
    prefill = n.get("snippet") or ""
    nxt = f"/inbox/verwerk?nid={nid}"
    groups = []
    for intent in INTENTS:
        opts = []
        for op in intent["options"]:
            q, otype, label, ready = op["q"], op["otype"], op["label"], op.get("ready", True)
            uid = f"{intent['key']}-{otype}"
            if not ready:
                opts.append(f"<div class='wo-ocd rdr-dim'><span class='muted'>{_e(q)}</span> → "
                            f"<strong>{_e(label)}</strong> <em>(coming in step 2)</em></div>")
            else:
                form = _outcome_form(otype, nid, csrf, prefill, role_opts, pj_opts, nxt, uid)
                opts.append(f"<details class='wo-ocd box-details'><summary>{_e(q)} → "
                            f"<strong>{_e(label)}</strong></summary>{form}</details>")
        groups.append(f"<details class='box-details'><summary><strong>{_e(intent['label'])}"
                      f"</strong></summary>{''.join(opts)}</details>")
    klaar = _klaar_knop(nid, csrf)
    # Beslis direct (founder, 19 jul): op een vraag van een bewoner wil de mens gewoon ja,
    # nee of een suggestie kunnen zeggen — het antwoord landt als reactie op de bron-feed
    # (@rol, de bewoner pakt het zelf op) en de spanning sluit. Alleen als er een
    # bron-project is; de triage-intenties hieronder blijven voor al het andere.
    # DE DRIE KNOPPEN op een operationeel verzoek: accepteren, aanpassen, weigeren. Dat is het
    # "in één handeling" waar de kaart om vraagt — een uitleg zonder knop laat de lezer alsnog
    # zoeken waar hij ja moet zeggen.
    besluit = ""
    if _type_van(n) == "naar_rol":
        return ("<div class='rdr-pane'><h3>Wat doe je met dit verzoek?</h3>"
                + _verzoek_knoppen(n, csrf) + "</div>")

    if n.get("project_id"):
        besluit = (f"<details class='box-details' open><summary><strong>Decide now</strong>"
                   f"</summary><p class='muted'>Your answer lands as a reply to the inhabitant, "
                   f"who can take it further — that's how the village learns to resolve tensions. "
                   f"The tension closes immediately.</p>"
                   + _besluit_knoppen(n, csrf) + "</details>")
    return (f"<div class='rdr-pane'><h3>What do you need?</h3>{besluit}{''.join(groups)}{klaar}</div>")


def render_verwerk(st, n: dict, csrf_token: str = "", role_opts: str = "", pj_opts: str = "") -> str:
    """De verwerk-pagina voor één inbox-item: links de spanning, rechts de intentie-wizard."""
    if n is None:
        inner = (f"{_DS_LINK}<div class='c2-wrap'><div class='c2-main'><a href='/inbox'>← inbox</a>"
                 "<p class='muted'>This tension no longer exists.</p></div></div>")
        return _page("Process", inner)
    split = (f"<div class='rdr-split'>"
             f"{_spanning_pane(st, n)}{_wizard_pane(n, csrf_token, role_opts, pj_opts)}</div>")
    main = (f"<div class='c2-main'><h1>Process tension</h1>{split}</div>")
    inner = (f"{_DS_LINK}<div class='c2-wrap'>{main}</div>")
    return _page("Process", inner)


# ── de globale inbox-drawer (chrome op elke pagina) + het lijst-fragment ──────────
def _ibx_row(st, n: dict) -> str:
    """Eén kaartje in de drawer. Open item → klik opent de modal-wizard; verwerkt item → sleep naar
    rechts om te archiveren."""
    nid = n.get("id", "")
    status = st.notif.status_of(n)
    title = _e(_one_line(n.get("snippet")))
    who = _e(_who(st, n))
    if status == "verwerkt":
        vs = st.notif.verwerkingen_of(n)
        kader = "".join(f"<div class='ibx-kader'>✓ {_e(v.get('label') or 'outcome')}</div>" for v in vs)
        return (f"<div class='ibx-row done' data-nid='{_e(nid)}'><span class='ibx-dot read'></span>"
                f"<div class='ibx-rb'><div class='ibx-title'>{title}</div>"
                f"<div class='ibx-meta'>processed · {who}</div>{kader}</div>"
                f"<span class='ibx-swipe'>swipe &rarr; archive</span></div>")
    dot = "ibx-dot read" if status == "gelezen" else "ibx-dot"
    return (f"<div class='ibx-row' data-nid='{_e(nid)}' onclick=\"ibxOpen('{_e(nid)}')\">"
            f"<span class='{dot}'></span><div class='ibx-rb'><div class='ibx-title'>{title}</div>"
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
    opts = ["<option value=''>as myself</option>"]
    for ty, tid in targets:
        if ty == "role":
            rec = st.records.get(tid)
            if rec is not None:
                opts.append(f"<option value='{_e(tid)}'>{_e(_name(rec))}</option>")
    return "".join(opts)


_IBX_JS = """
var IBX_CSRF=__IBX_CSRF__;
function ibxToggle(){var d=document.getElementById('ibx-drawer');d.classList.toggle('open');
  if(d.classList.contains('open'))ibxRefresh();}
function ibxAddToggle(){document.getElementById('ibx-add').classList.toggle('open');}
function ibxPost(a,x){return fetch('/action',{method:'POST',
  headers:{'Content-Type':'application/x-www-form-urlencoded'},
  body:new URLSearchParams(Object.assign({action:a,csrf:IBX_CSRF,next:'/inbox'},x||{}))});}
function ibxRefresh(){return fetch('/inbox?frag=1').then(function(r){return r.text();}).then(function(h){
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
    t.value='';ibxAddToggle();ibxRefresh();});}
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
              "<div class='ibx-sub' id='ibx-sub'></div>" + add +
              "<div class='ibx-list' id='ibx-list'></div></aside>")
    modal = ("<div class='ibx-scrim' id='ibx-scrim'><div class='ibx-modal'>"
             "<button class='ibx-mx' title='close' onclick='ibxCloseModal()'>&times;</button>"
             "<iframe class='ibx-iframe' id='ibx-frame' title='Process tension'></iframe></div></div>"
             "<div class='ibx-thumb' id='ibx-thumb'>&#128077;</div>")
    return (launch + drawer + modal + "<script>"
            + _IBX_JS.replace("__IBX_CSRF__", json.dumps(csrf_token)) + "</script>")
