"""Overview-views — brok 10 van de cockpit2-split."""
from __future__ import annotations

import json
import time
import urllib.parse
from typing import TYPE_CHECKING

from nooch_village.web_base import _e, _field, _page, _banner
from nooch_village.cockpit2_util import (
    _DS_LINK,
    _name, _initials, _tabbar, _avatar, _age, _md, md_editor,
    _psec, _person_name, _ICON_ADD_EMOJI,
    _IC_CHECK, _IC_CLOCK, _IC_LINK, _IC_TARGET, _nav,)
from nooch_village.views.feed import _mentionables
from nooch_village.views.checklists import _checklists_tab_html, _cl_row
from nooch_village.views.metrics import _metrics_tab_html, _METRICS_JS
from nooch_village.views.metrics2 import render_metrics2_tab, render_metrics2_person
from nooch_village.views.strategy import _strategy_tab_html
from nooch_village.views.projects import (
    _projects_tab_html, _scope_text, _person_projects_tab_html, _modal_html,
)
from nooch_village import (org, artefacts, acc_ids, skill_meta, skill_links,
                           skill_labels, wiki, claims_db)
from nooch_village.registry_factory import shared_registry
from nooch_village.cockpit2_util import _CIRCLE_TABS, _ROLE_TABS, _PERSON_TABS, WEBSITE_DEVELOPER_ROLE

if TYPE_CHECKING:
    from nooch_village.cockpit2 import _Stores

def _filler_html(st: _Stores, node_id: str, rec) -> str:
    fillers = st.assign.fillers_of(node_id, record=rec)
    if not fillers:
        return "<span class='muted'>Not filled yet.</span>"
    out = []
    for f in fillers:
        if f.type == "person":
            p = st.people.get(f.id)
            nm = p.name if p else f.id
            out.append(f"<span class='person'><span class='av'>{_e(_initials(nm))}</span>"
                       f"<a href='/person?id={_e(f.id)}'>{_e(nm)}</a></span>")
        else:
            pa = st.personas.get(f.id)
            nm = (pa.name if pa else f.id) + " (AI)"
            out.append(f"<span class='person'><span class='av ai'>AI</span>{_e(nm)}</span>")
    return "<div>" + " &nbsp; ".join(out) + "</div>"


def _members_of_circle(st: _Stores, circle_id: str) -> list:
    seen, ppl = set(), []
    anchors = [circle_id] + [r.id for r in org.roles_of(st.records.all(), circle_id)]
    for aid in anchors:
        rec = st.records.get(aid)
        for f in st.assign.fillers_of(aid, record=rec):
            if f.type == "person" and f.id not in seen:
                seen.add(f.id)
                p = st.people.get(f.id)
                if p:
                    ppl.append(p)
    return sorted(ppl, key=lambda p: p.name)


def _tree_html(st: _Stores, current_id: str) -> str:
    recs = st.records.all()
    # De cirkel die de huidige node bevat (en zijn ouders) staat open; de rest ingeklapt (native
    # <details>, geen JS, geen persistentie). Zo blijft de boom overzichtelijk bij 20+ rollen.
    ancestors = set(org.breadcrumb(recs, current_id)) if current_id else set()

    def kids_of(rec):
        # Kernrollen (Lead/Rep/Secretary/Facilitator) niet in de navigatie: die zie je via de
        # cirkel -> Rollen. Houdt de boom rustig.
        return sorted([k for k in org.children_of(recs, rec.id)
                       if org.is_circle(k) or _name(k).strip().lower() not in _CORE_ROLE_NAMES],
                      key=lambda r: (not org.is_circle(r), _name(r).lower()))

    def bezet_icoon(rec) -> str:
        """Bezet of vacant, als klein icoon vóór de rolnaam (fase 11, 1a).

        DEZELFDE VORMTAAL als het bord en de checklist: gevulde cirkel = bezet, gestippelde cirkel
        = vacant. Geen nieuwe kleur en geen nieuwe vorm — `.nu-status--icoon` is een kaderloze
        variant van het bestaande statusatoom, niet een tweede systeem.

        HET WOORD STAAT ERBIJ, in een `.sr`-span. Een vorm alleen is geen status: in zwart-wit,
        of voor wie die tinten niet onderscheidt, zijn twee cirkeltjes twee cirkeltjes. Dat is de
        regel uit de kop van nooch-ui.css, en hij geldt ook als de vorm klein is.

        Fail-soft: een onleesbare assignments-store maakt van de boom geen foutpagina. Geen
        uitspraak is dan beter dan de bewering "vacant" — dat is precies de bewering die op
        14 augustus 37 onterechte meldingen opleverde."""
        try:
            bezet = bool(st.assign.fillers_of(rec.id, record=rec))
        except Exception:                                    # noqa: BLE001
            return ""
        soort, woord = ("ok", "filled") if bezet else ("open", "vacant")
        return (f"<span class='nu-status nu-status--icoon nu-status--{soort}' "
                f"aria-hidden='true'></span><span class='sr'>{woord}: </span>")

    def node_li(rec, depth: int) -> str:
        is_c = org.is_circle(rec)
        cls = ("c" if is_c else "") + (" here" if rec.id == current_id else "")
        link = f"<a class='{cls}' href='/node?id={_e(rec.id)}'"
        if not is_c:
            # Alleen ROLLEN dragen het icoon. Een cirkel is geen stoel waar iemand in zit; een
            # bezet/vacant-merkteken erop zou een vraag beantwoorden die niemand stelt.
            return f"<li>{link}>{bezet_icoon(rec)}{_e(_name(rec))}</a></li>"
        inner = "".join(node_li(k, depth + 1) for k in kids_of(rec))
        if depth == 0:
            # De anchor (Mother Earth) blijft een vaste kop, niet inklapbaar.
            return f"<li>{link}>{_e(_name(rec))}</a><ul>{inner}</ul></li>"
        # Sub-cirkel (Nooch e.d.) inklapbaar; open als de huidige node erin zit. Klik op de naam
        # navigeert (stopPropagation → geen toggle), klik op de caret klapt in/uit.
        # Noochville staat altijd standaard open (de thuisbasis), ook zonder huidige node erin.
        op = " open" if (rec.id in ancestors
                         or _name(rec).strip().lower() == "noochville") else ""
        summ = f"{link} onclick='event.stopPropagation()'>{_e(_name(rec))}</a>"
        return (f"<li><details class='tree-c'{op}><summary>{summ}</summary>"
                f"<ul>{inner}</ul></details></li>")

    body = "".join(node_li(r, 0) for r in org.roots(recs)) or "<li class='muted'>empty</li>"
    return f"<div class='tree'><h3>Organization</h3><ul>{body}</ul></div>"


def _link_chip(t) -> str:
    """Een gekoppeld dorpsmiddel: mensentaal voorop, de technische capability eronder."""
    dom = skill_meta.schrijft_in_domein(t.skill)
    mark = f" <span class='muted'>· domain {_e(dom)}</span>" if dom else ""
    return (f"<span class='chip'>🔗 {_e(skill_labels.label(t.skill))}</span>"
            f"<span class='muted'> {_e(t.skill)}</span>{mark}")


def _middel_picker(st: _Stores, rec, role_id: str, acc_id: str, hid) -> str:
    """Picker voor dorpsmiddelen op deze belofte.

    Alleen skills die de rol nog niet via deze accountability voert, en alleen skills die de
    domeinpoort doorlaten: een beslis-skill verschijnt niet eens in de lijst bij een rol die het
    domein niet houdt. De poort in de dispatch is de tweede sleutel (verdediging in de diepte).
    """
    if rec is None:
        return ""
    try:
        namen = sorted(shared_registry().names())
    except Exception:                              # fail-closed: liever geen picker dan een lege belofte
        return "<p class='muted'>The resources catalog is briefly unavailable.</p>"
    al = {t.skill for t in skill_links.links_for_acc(st.ai, role_id, acc_id)}
    kies = [n for n in namen if n not in al and skill_meta.koppelbaar(n, rec)[0]]
    if not kies:
        return "<p class='muted'>No resource left to link here.</p>"
    opts = "".join(
        f"<option value='{_e(n)}'>{_e(skill_labels.label(n))} — {_e(n)}"
        f"{' (heavy: grant via governance)' if skill_meta.is_zwaar(n) else ''}</option>"
        for n in kies)
    return (f"<div class='pf'><form method='post' action='/action'>{hid()}"
            f"<label class='att-lbl' for='f-skilllink'>Link a village resource to this commitment</label>"
            f"<select id='f-skilllink' name='skill'>{opts}</select>"
            f"<button class='btn' type='submit' name='action' value='skilllink_add'>"
            f"Link resource</button></form></div>")


def _acc_row(st: _Stores, rec, i: int, text: str, csrf_token: str) -> str:
    """Eén accountability-regel: de belofte, de dorpsmiddelen die eraan hangen, en de ingang naar
    het beheer daarvan.

    Sinds scope 39 staat hier GEEN autonome AI-laag meer. Die beloofde dat een AI de belofte
    zelfstandig uitvoert, maar `kind="autonoom"` werd nergens buiten deze view gelezen: er was geen
    daemon, geen puls en geen planner die er ooit iets mee deed. Een scherm dat uitvoering belooft
    die niet bestaat, is dezelfde fout als een skill die 'gelukt' meldt zonder iets te doen.

    Wat een rol kan uitvoeren komt uit zijn DNA plus de rugzakken (`skillset.py`) — standaard
    beschikbaar voor elke rol, niet per belofte te koppelen. Hulp aanbieden doen de stagiairs
    langs de bestaande verzoek-route."""
    aid = acc_ids.acc_id_at(rec.definition, i)
    links = skill_links.links_for_acc(st.ai, rec.id, aid)
    # De middelen onder de belofte: mensentaal voorop, de technische capability klein erachter.
    mid = ""
    if links:
        chips = "".join(f"<span class='chip'>🔗 {_e(skill_labels.label(t.skill))}</span>"
                        f"<span class='muted'> {_e(t.skill)}</span>" for t in links)
        mid = f"<div class='muted'>{chips}</div>"      # bestaande klasse; geen nieuwe CSS
    # Ingang naar het middelenbeheer. Stond hier eerder als 🎁 ("een AI kan dit zelfstandig"); het
    # is nu wat het altijd al was: welke dorpsmiddelen dienen deze belofte. Zonder csrf (auth uit,
    # leesweergave) tonen we geen beheerknop.
    beheer = ""
    if csrf_token:
        url = f"/middelen?role={_e(rec.id)}&acc_id={_e(aid)}"
        beheer = (f"<a class='manage-ico js-modal' href='{url}' data-href='{url}' "
                  f"title='Village resources on this commitment'>🔗</a>")
    return (f"<div class='accrow'><div class='acc-text'>{_e(text)}{mid}</div>"
            f"<div class='acc-ai'>{beheer}</div></div>")




def _overview_html(st: _Stores, rec, csrf_token: str = "") -> str:
    d = rec.definition
    is_c = org.is_circle(rec)
    parts = [f"<div class='c2-sec'><h3>Purpose</h3><div>{_e(d.purpose) or '<span class=muted>—</span>'}</div></div>"]
    if is_c:
        # Strategie geïntegreerd in overview (aparte strategy-tab vervallen). De
        # `with_purpose_chain=False` die hier stond is overbodig geworden: de keten zelf is weg,
        # want de enige plek die hem MET keten aanriep was de onbereikbare `tab == "strategy"`.
        parts.append(_strategy_tab_html(st, rec))
    doms = d.domains or []
    doms_list = ("<ul class='clean'>" + "".join(f"<li>{_e(x)}</li>" for x in doms) + "</ul>") if doms else ""
    # Op de anchor-cirkel stond hier een live NASA-EPIC-aardbol. Weg op 19 september 2026
    # (fase 6): mooi, maar het was een dagelijkse externe ophaal plus een schijf-cache voor een
    # plaatje, en in een codebase die we halveren is dat geen domein.
    domains_inner = doms_list or "<span class='muted'>No domain.</span>"
    parts.append(f"<div class='c2-sec'><h3>Domains</h3>{domains_inner}</div>")
    accs = d.accountabilities or []
    if not is_c:
        parts.append("<div class='c2-sec'><h3>Accountabilities</h3>"
                     + ("".join(_acc_row(st, rec, i, a, csrf_token) for i, a in enumerate(accs))
                        if accs else "<span class='muted'>No accountabilities.</span>") + "</div>")
    elif accs:
        parts.append("<div class='c2-sec'><h3>Accountabilities</h3><ul class='clean'>"
                     + "".join(f"<li>{_e(x)}</li>" for x in accs) + "</ul></div>")
    if not is_c:
        parts.append(f"<div class='c2-sec'><h3>Role Fillers "
                     f"{_manage_fillers_ico(rec.id, csrf_token)}</h3>"
                     f"{_filler_html(st, rec.id, rec)}</div>")
    return "".join(parts)


def _fillsummary(st: _Stores, rec) -> str:
    fs = st.assign.fillers_of(rec.id, record=rec)
    if not fs:
        return "— not filled"
    names = []
    for f in fs:
        if f.type == "person":
            p = st.people.get(f.id); names.append(p.name if p else f.id)
        else:
            names.append("AI")
    return "· " + ", ".join(names)


_CORE_ROLE_NAMES = {"circle lead", "lead link", "facilitator", "secretary", "secretaris",
                    "rep link", "circle rep", "cross link"}


# Genderneutraal 'persoon + toevoegen'-icoon (silhouet + plus), kleurt mee met currentColor.
_ICON_ADD_PERSON = (
    "<svg width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='currentColor' "
    "stroke-width='2' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>"
    "<circle cx='9' cy='8' r='3.2'/>"
    "<path d='M3.5 20c0-3.2 2.5-5.6 5.5-5.6s5.5 2.4 5.5 5.6'/>"
    "<path d='M18.5 8.5v5M16 11h5'/></svg>")

# Reactie toevoegen: neutrale lijn-smiley met plus (zelfde stijl als persoon-toevoegen).


def _fillers_block(st: _Stores, role) -> str:
    """Rechts uitgelijnde rolvervullers; bij 3+ gestapelde avatars + '+ nog N'."""
    fillers = st.assign.fillers_of(role.id, record=role)
    resolved = []
    for f in fillers:
        if f.type == "person":
            p = st.people.get(f.id)
            resolved.append((p.name if p else f.id, False, f.id))
        else:
            pa = st.personas.get(f.id)
            resolved.append(((pa.name if pa else f.id), True, f.id))
    if not resolved:
        return "<span class='muted' style='font-size:.8rem'>not filled</span>"
    if len(resolved) >= 3:
        avs = "".join(f"<span class='stack-av'>{_avatar(n, ai)}</span>" for n, ai, fid in resolved[:3])
        extra = f"<span class='muted' style='font-size:.82rem'>+ {len(resolved)-3} more</span>" if len(resolved) > 3 else ""
        return f"<div class='fillers stack'>{avs}{extra}</div>"
    rows = ""
    for n, ai, fid in resolved:
        # De AI-inwoner is nu een klikbaar dossier i.p.v. platte tekst — dat is de ingang
        # naar /inwoner vanaf de rol-pagina.
        nm = (f"<a href='/person?id={_e(fid)}'>{_e(n)}</a>" if not ai
              else f"<a href='/inwoner?id={_e(fid)}'>{_e(n)}</a> (AI)")
        rows += f"<div class='fperson'>{_avatar(n, ai)}<span>{nm}</span></div>"
    return f"<div class='fillers'>{rows}</div>"


def _manage_fillers_ico(role_id: str, csrf_token: str) -> str:
    """De ingang naar het vervullers-scherm — één definitie, twee plekken.

    Stond alleen in `_role_row`, dus alleen op de Roles-tab van de CIRKEL. Wie op de rol zelf
    stond zag onder 'Role Fillers' alleen 'Not filled yet.' en geen enkele knop; de rol was daar
    niet te bemensen en dat las als "het kan niet". Zelfde control, zelfde URL, nu ook waar je
    hem zoekt. Geen csrf-token (uitgelogd/publieke render) = geen beheer-affordance, precies
    zoals de rij op de cirkelpagina dat al deed."""
    if not csrf_token:
        return ""
    url = f"/rolefillers?role={_e(role_id)}"
    return (f"<a class='manage-ico js-modal' href='{url}' data-href='{url}' "
            f"title='manage role fillers'>{_ICON_ADD_PERSON}</a>")


def _role_row(st: _Stores, role, csrf_token: str) -> str:
    purpose = role.definition.purpose or ""
    pur = f"<div class='muted rrole-pur'>{_e(purpose)}</div>" if purpose else ""
    assign = _manage_fillers_ico(role.id, csrf_token)
    return (f"<div class='rrole'>"
            f"<div class='rrole-info'><a href='/node?id={_e(role.id)}'>{_e(_name(role))}</a>{pur}</div>"
            f"<div class='rrole-fill'>{_fillers_block(st, role)}</div>"
            f"<div class='rrole-act'>{assign}</div></div>")


def _roles_html(st: _Stores, rec, csrf_token: str = "") -> str:
    recs = st.records.all()
    subs = sorted(org.subcircles_of(recs, rec.id), key=lambda r: _name(r).lower())
    roles = sorted(org.roles_of(recs, rec.id), key=lambda r: _name(r).lower())
    core = [r for r in roles if _name(r).strip().lower() in _CORE_ROLE_NAMES]
    rest = [r for r in roles if _name(r).strip().lower() not in _CORE_ROLE_NAMES]
    out = []
    if core:
        out.append("<div class='c2-sec'><h3>Core roles</h3>"
                   + "".join(_role_row(st, r, csrf_token) for r in core) + "</div>")
    out.append("<div class='c2-sec'><h3>Roles</h3>"
               + ("".join(_role_row(st, r, csrf_token) for r in rest)
                  if rest else "<span class='muted'>No roles.</span>") + "</div>")
    if subs:
        out.append("<div class='c2-sec'><h3>Subcircles</h3><ul class='clean'>"
                   + "".join(f"<li><a href='/node?id={_e(s.id)}'>{_e(_name(s))}</a> "
                             f"<span class='chip'>circle</span></li>" for s in subs) + "</ul></div>")
    return "".join(out)


def _members_html(st: _Stores, rec, csrf_token: str = "") -> str:
    # Deelnemerbeheer (toevoegen/verwijderen/wijzigen) zit op de admin-pagina (/admin),
    # niet hier. Members toont alleen wie deze cirkel vervullen.
    ppl = _members_of_circle(st, rec.id)
    admin = ("<p class='muted' style='font-size:.8rem;margin-top:.8rem'>"
             "Add or manage people? → <a href='/admin'>People (admin)</a></p>"
             if csrf_token else "")
    if not ppl:
        return ("<div class='c2-sec'><h3>Members</h3><span class='muted'>No people.</span>"
                f"{admin}</div>")
    cells = "".join(
        f"<div class='card'><span class='person'><span class='av'>{_e(_initials(p.name))}</span>"
        f"<a href='/person?id={_e(p.id)}'>{_e(p.name)}</a></span></div>" for p in ppl)
    return f"<div class='c2-sec'><h3>Members ({len(ppl)})</h3>{cells}{admin}</div>"


def render_admin(st: _Stores, csrf_token: str = "", msg: str = "") -> str:
    """Admin-pagina 'People': mensen toevoegen, wijzigen, wachtwoord resetten en verwijderen.

    DIT SCHERM IS NOOIT MEEGEGAAN met fase 9/10/12 (gevonden 21 september 2026, door zelf in te
    loggen en te kijken in plaats van op een rapport te vertrouwen). Het droeg een eigen
    `<style>`-blok, zeventien kale `<input>`s zonder gekoppeld label, en twaalf inline styles —
    terwijl `_field()`, `.qadd-form`, `.card` en `.att-lbl` al bestonden. Het resultaat zag eruit
    als een ander product dan de rest van de cockpit.

    Wat het nu gebruikt, en waarom precies dat: `.card` voor de container (de enige rol die een
    kader hoort te dragen), `.qadd-form` voor het toevoeg-formulier (hetzelfde patroon als elk
    ander 'voeg iets toe'-blok), `_field()` voor elk veld (label en veld als onlosmakelijk paar) en
    `.btn`-varianten voor de knoppen. Geen eigen CSS, geen inline styles.

    TWEE DODE LINKS ZIJN HIER WEGGEHAALD: "Inhabitants (AI personas)" wees naar `/inwoners` en
    "Founder Flow" naar `/founder`. Beide routes bestaan niet meer; ze gaven een 404. Zie de
    commit voor wat er áchter die schermen nog aan dode code stond."""
    people = st.people.all()
    rw = bool(csrf_token)

    def _status(p):
        if getattr(p, "last_login", 0):
            return (f"<span class='chip'>active</span>"
                    f"<span class='muted'> · {_e(_age(p.last_login))}</span>")
        if getattr(p, "password_hash", ""):
            return "<span class='chip outline'>invited</span>"
        return "<span class='chip muted'>no access</span>"

    def _hid(pid: str, nxt: str = "/admin") -> str:
        return (f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                f"<input type='hidden' name='pid' value='{_e(pid)}'>"
                f"<input type='hidden' name='next' value='{_e(nxt)}'>")

    rijen = ""
    for p in people:
        nrol = len(st.assign.roles_of("person", p.id))
        if rw:
            # Eén rij = één formulier met twee velden naast elkaar. `_field` koppelt label en veld;
            # de id's moeten uniek zijn omdat elke rij dezelfde veldnamen draagt.
            hoofd = (f"<form method='post' action='/action' class='qadd-form admin-row-form'>"
                     f"{_hid(p.id)}"
                     + _field("Name", "name", value=p.name, fid=f"f-naam-{p.id}")
                     + _field("Email", "email", kind="email", value=p.email,
                              fid=f"f-mail-{p.id}")
                     + f"<div class='qadd-row'>"
                       f"<button class='btn ok sm' type='submit' name='action' "
                       f"value='person_edit'>Save</button></div></form>")
            warn = f" — also removes {nrol} role assignment(s)" if nrol else ""
            acties = (f"<form method='post' action='/action'>{_hid(p.id)}"
                      f"<button class='btn sm' type='submit' name='action' "
                      f"value='person_reset_password'>Reset password</button></form>"
                      f"<form method='post' action='/action'>{_hid(p.id)}"
                      f"<button class='btn ghost sm' type='submit' name='action' "
                      f"value='person_remove' "
                      f"onclick=\"return confirm('Delete {_e(p.name)}?{warn}')\">Delete</button>"
                      f"</form>")
        else:
            hoofd = (f"<b>{_e(p.name)}</b>"
                     f"<span class='muted'> · {_e(p.email) or 'no email'}</span>")
            acties = ""
        rijen += (f"<div class='admin-row'><div class='admin-main'>{hoofd}</div>"
                  f"<div class='admin-meta'>{_status(p)}"
                  f"<span class='muted'> · {nrol} role(s)</span>"
                  f"<span class='admin-act'>{acties}</span></div></div>")

    toevoegen = ""
    if rw:
        toevoegen = (
            f"<details class='qadd' open><summary class='muted'>＋ Add person</summary>"
            f"<form method='post' action='/action' class='qadd-form'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"<input type='hidden' name='action' value='person_add'>"
            f"<input type='hidden' name='next' value='/admin'>"
            + _field("First name", "voornaam", required=True)
            + _field("Last name", "achternaam", required=True)
            + _field("Email address", "email", kind="email", required=True)
            + f"<div class='qadd-row'><button class='btn ok sm' type='submit'>Add</button></div>"
              f"</form></details>")

    main = (f"<div class='c2-main'><div class='c2-bar'><a href='/'>← home</a></div>"
            f"<h1>People <span class='chip'>admin</span></h1>"
            f"<p class='muted'>Add, edit, reset a password or remove people. "
            f"This page requires login.</p>{_banner(msg)}{toevoegen}"
            f"<div class='c2-sec'><h3>People ({len(people)})</h3>"
            f"<div class='card'>{rijen or '<p class=muted>No one yet.</p>'}</div></div></div>")
    return _page("People — admin", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")


def _att_html(st: _Stores, rec, kind: str, leeg: str) -> str:
    items = st.att.list(rec.id, kind)
    if not items:
        return (f"<p class='muted'>{_e(leeg)}</p>"
                "<p class='muted' style='font-size:.8rem'>Storage already works; entry/display "
                "(and the meeting link) is still to come.</p>")
    out = "<ul class='clean'>"
    for a in items:
        meta = ""
        if a.meta:
            meta = " <span class='pill'>" + _e(", ".join(f"{k}: {v}" for k, v in a.meta.items())) + "</span>"
        out += f"<li><b>{_e(a.title) or '—'}</b>{meta}<br><span class='muted'>{_e(a.body)}</span></li>"
    return out + "</ul>"

# ── Artefact-tabs (Notes / Policies / Tools) ────────────────────────────────
# Twee secties per tab: "Van deze rol" (eigen artefacten, edit alleen voor de vervuller) en
# "Geldend hier" (geërfd + governance-owned, read-only met herkomst). Alles afgeleid uit de
# domein-/erf-query (artefacts.own_and_inherited); niks handmatig gecureerd.
_KIND_ICON = {"note": "📄", "policy": "📜", "tool": "🛠"}
_KIND_LABEL = {"note": "Note", "policy": "Policy", "tool": "Tool"}
_KIND_TAB = {"note": "notes", "policy": "policies", "tool": "tools"}


def _tab_for(kind: str) -> str:
    return _KIND_TAB.get(kind, "notes")


def _dt(ts) -> str:
    try:
        from nooch_village.cockpit2_util import lokaal
        return lokaal(ts)                              # zone van de lezer, niet van de server
    except (TypeError, ValueError):
        return "—"


def _slaap_blok(rec) -> str:
    """Waarom deze rol slaapt en hoe je hem wakker maakt. Eén regel, geen nieuw patroon.

    De terugweg staat er letterlijk bij: slapen is omkeerbaar, en dat is alleen waar als je kunt
    zien hóe. Een status zonder de weg terug leest als een verwijdering."""
    if not getattr(rec, "slaapt", False):
        return ""
    reden = str(getattr(rec, "slaap_reden", "") or "geen reden vastgelegd")
    return (f"<div class='card muted'><strong>💤 Deze rol slaapt.</strong> Hij staat volledig in het "
            f"register — purpose, accountabilities en historie zijn ongewijzigd — maar hij draait "
            f"niet, oordeelt niet en krijgt geen nieuw werk toegewezen.<br>"
            f"<span class='muted'>{_e(reden)}</span><br>"
            f"Weer wakker: <code>village afslanken wek {_e(getattr(rec, 'id', ''))}</code></div>")


def _can_edit_artefacts(st: _Stores, rec, csrf_token: str, username: str | None) -> bool:
    """Mag de huidige kijker artefacten van deze rol bewerken? Vereist een schrijf-sessie
    (csrf_token) én — via can_write_artefact — vervuller of Circle Lead zijn. "guest" (auth uit)
    mag alles, net als in de rest van de cockpit."""
    if not csrf_token:
        return False
    if username == "guest":
        return True
    actor = st.people.by_email(username) if username else None
    return bool(actor) and artefacts.can_write_artefact("person", actor.id, rec.id, st.records, st.assign)


def _artefact_versions_html(a) -> str:
    vs = getattr(a, "versions", None) or []
    if not vs:
        return ""
    rows = ""
    for v in vs:
        gref = f" · gov:{_e(v['governance_ref'])}" if v.get("governance_ref") else ""
        rows += (f"<li><span class='muted'>v{v.get('version_nr')} · {_dt(v.get('ts'))} · "
                 f"{_e(v.get('actor_id') or '—')} · {_e(v.get('change_note') or '')}{gref}</span></li>")
    return (f"<details class='c2-hist'><summary class='muted'>"
            f"historie ({len(vs)})</summary><ul class='clean'>{rows}</ul></details>")


def _domain_field(domains: list) -> str:
    """Domein-keuze voor een policy-add-form. Eén domein → vaste regel (hidden input, geen dropdown);
    twee of meer → een select. Bron: de écht via governance toegewezen `definition.domains`."""
    if len(domains) == 1:
        d = domains[0]
        return (f"<label class='att-lbl'>Domain</label>"
                f"<div class='muted'>{_e(d)}</div>"
                f"<input type='hidden' name='domain' value='{_e(d)}'>")
    opts = "".join(f"<option value='{_e(d)}'>{_e(d)}</option>" for d in domains)
    return f"<label class='att-lbl'>Domain</label><select name='domain'>{opts}</select>"


def _artefact_add_form(rec, kind: str, csrf_token: str, domains: list | None = None) -> str:
    dom = _domain_field(domains or []) if kind == "policy" else ""
    urlf = (f"<label class='att-lbl'>URL</label>"
            f"<input type='url' name='url' placeholder='https://…'>" if kind == "tool" else "")
    return (f"<details class='qadd qadd-top'><summary>+ Add {_e(_KIND_LABEL[kind])}</summary>"
            f"<form method='post' action='/action' class='qadd-form'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"<input type='hidden' name='owner' value='{_e(rec.id)}'>"
            f"<input type='hidden' name='kind' value='{_e(kind)}'>"
            f"<input type='hidden' name='next' value='/node?id={_e(rec.id)}&tab={_tab_for(kind)}'>"
            f"<label class='att-lbl'>Title</label><input name='title' required>"
            f"{dom}"
            f"<label class='att-lbl'>Body</label>{md_editor('body')}"
            f"{urlf}"
            f"<div class='qadd-row'>"
            f"<button class='btn ok' type='submit' name='action' value='artefact_add'>Add</button>"
            f"<button type='button' class='qadd-x' onclick=\"this.closest('details').open=false\" "
            f"aria-label='cancel'>✕</button></div></form></details>")


def _artefact_edit_form(a, csrf_token: str, *, next_url: str = "") -> str:
    # `next_url` parametriseert waar je na opslaan landt (default: de tab van de eigenaar-rol).
    # De pagina-view (/pagina) geeft zijn eigen permalink mee — zelfde formulier, zelfde poort.
    nxt = next_url or f"/node?id={a.anchor}&tab={_tab_for(a.kind)}"
    urlf = (f"<label class='att-lbl'>URL</label>"
            f"<input type='url' name='url' value='{_e(a.url)}'>" if a.kind == "tool" else "")
    # INLINE BEWERKEN (fase 10 punt 4). Wat er NIET verandert: één formulier, één submit, één
    # `artefact_edit`-actie, één `update()`-aanroep, één versie-entry met change_note "bewerkt".
    # Wat wél verandert is waar de knop staat. De opslaan-balk is `hidden` tot er echt iets is
    # getypt (`data-qadd-dirty`), en de tekst op de pagina opent het formulier bij een klik
    # (`data-qadd-open`, zie nooch.js). De `<details>` blijft als drager staan en niet uit
    # nostalgie: zonder JS is de "edit"-summary de enige manier om er nog in te komen, en op een
    # lijst met twintig artefacten wil je geen twintig openstaande tekstvakken.
    #
    # Eén save-actie en dus ÉÉN change_note, bewust: per veld opslaan zou drie versie-entries
    # geven voor wat de schrijver als één wijziging ervaart (besluit Stefan, 20 september 2026).
    return (f"<details class='qadd' data-qadd-inline><summary class='muted'>edit</summary>"
            f"<form method='post' action='/action' class='qadd-form' data-qadd-dirty>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"<input type='hidden' name='aid' value='{_e(a.id)}'>"
            f"<input type='hidden' name='next' value='{_e(nxt)}'>"
            f"<label class='att-lbl'>Title</label><input name='title' value='{_e(a.title)}'>"
            f"<label class='att-lbl'>Body</label>{md_editor('body', a.body)}"
            f"{urlf}"
            f"<div class='qadd-row qadd-bar'>"
            f"<button class='btn ok sm' type='submit' name='action' value='artefact_edit'>Save</button>"
            f"<button type='button' class='qadd-x' data-qadd-cancel "
            f"aria-label='cancel'>✕</button></div></form></details>")


def _artefact_archive_form(a, csrf_token: str) -> str:
    return (f"<form method='post' action='/action'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"<input type='hidden' name='aid' value='{_e(a.id)}'>"
            f"<input type='hidden' name='next' value='/node?id={_e(a.anchor)}&tab={_tab_for(a.kind)}'>"
            f"<button class='dellink' type='submit' name='action' value='artefact_archive' "
            f"onclick=\"return confirm('Archive {_e(a.title or a.id)}?')\">archive</button></form>")


def _laatst_gewijzigd(a) -> str:
    return (f"<div class='muted'>last edited: "
            f"{_dt(getattr(a, 'updated_at', 0))}</div>")


def _artefact_id_chip(a) -> str:
    """Stabiel, verwijsbaar id (policy: {DOMEINSLUG}-{NNN}) als code-chip."""
    return f"<code class='pill'>{_e(a.id)}</code>"


def _artefact_head(a, *, extra: str = "") -> str:
    icon = _KIND_ICON.get(a.kind, "")
    dom = (f" <span class='chip muted'>{_e(a.domain)}</span>"
           if a.kind == "policy" and getattr(a, "domain", "") else "")
    # Een note IS een wiki-pagina (nooch_village/wiki.py): geen aparte pagina die je moet
    # aanmaken, dezelfde data. Dus de titel zelf is de link naar de permalink (feiten,
    # backlinks, versiegeschiedenis) -- niet een los chipje ernaast dat je apart moet vinden.
    # Klikken op de kaart is wat iemand hier verwacht. Ook op een geërfde note (lezen mag altijd).
    if a.kind == wiki.PAGINA_KIND:
        titel = f"<a href='{_e(wiki.pagina_url(a.id))}'>{_e(a.title) or _e(a.id)}</a>"
    else:
        titel = _e(a.title) or _e(a.id)
    head = f"<div class='ptitle'>{icon} {_artefact_id_chip(a)} {titel}{dom}{extra}</div>"
    if a.kind == "tool" and a.url:
        head += (f"<div class='muted'>"
                 f"<a href='{_e(a.url)}' target='_blank' rel='noopener'>{_e(a.url)}</a></div>")
    return head


def _artefact_body_html(a, *, st: _Stores | None = None, pags: list | None = None) -> str:
    """De body van een artefact. Een wiki-pagina (note) krijgt zijn `[[links]]` opgelost naar
    andere pagina's — net als op de permalink (`views/wiki.py::_body_html`); elk ander soort
    (policy, tool) kent dat idioom niet en blijft kale markdown.

    `pags=None` (geen paginalijst aangeleverd) valt terug op kale markdown — nooit een crash,
    hoogstens een ongelinkte `[[verwijzing]]`."""
    if not a.body:
        return ""
    if a.kind == wiki.PAGINA_KIND and pags is not None:
        from nooch_village.views.wiki import _body_html as _pagina_body_html
        return f"<div class='att-body'>{_pagina_body_html(a.body, pags)}</div>"
    return f"<div class='att-body'>{_md(a.body)}</div>"


def _wiki_extras(a, st: _Stores | None, pags: list | None, csrf_token: str, can_edit: bool) -> str:
    """Feiten en backlinks, rechtstreeks op de kaart (scope: "nou notes zijn nog niet wiki" — geen
    aparte pagina meer nodig om ze te zien). Alleen voor een echte wiki-pagina, en alleen als er
    genoeg is aangeleverd (st + pags) om ze live te berekenen."""
    if a.kind != wiki.PAGINA_KIND or st is None or pags is None:
        return ""
    from nooch_village.views.wiki import _feiten_sectie, _backlink_sectie
    return f"{_feiten_sectie(a, st, csrf_token, can_edit)}{_backlink_sectie(a, pags)}"


def _artefact_own_card(a, csrf_token: str, can_edit: bool, *, anders: str = "",
                       st: _Stores | None = None, pags: list | None = None) -> str:
    """`anders` is wat iemand mag die NIET de eigenaar is — op een note het voorstelpad.

    De keuze is exclusief: wie mag bewerken krijgt geen voorstelknop (hij zou zijn eigen voorstel
    moeten goedkeuren), wie niet mag bewerken krijgt geen bewerkknop die toch afketst op de poort."""
    body = _artefact_body_html(a, st=st, pags=pags)
    actions = anders
    if can_edit:
        # EEN NOTE WORDT HIER NIET MEER BEWERKT (21 september 2026). Een note IS een wiki-pagina,
        # en die heeft sinds vandaag een inline editor op zijn eigen permalink: je klikt in de
        # tekst en typt daar. Het oude formulier hier laten staan zou een TWEEDE bewerkpad zijn
        # voor precies hetzelfde object — twee plekken die uiteen gaan lopen zodra er aan één van
        # de twee iets verandert. Dus: hier de weg ernaartoe, daar het bewerken.
        # Een tool of policy is geen wiki-pagina (een tool heeft een URL-veld) en houdt zijn
        # formulier onveranderd.
        if a.kind == wiki.PAGINA_KIND:
            bewerk = (f"<div class='qadd-row'><a class='btn sm' "
                      f"href='{_e(wiki.pagina_url(a.id))}'>✎ Edit on its page</a></div>")
        else:
            # Bewerk-formulier op volledige kaartbreedte (eigen blok, NIET als smal flex-item in een
            # .qadd-row náást 'archiveren'); 'archiveren' als losse actie eronder.
            bewerk = _artefact_edit_form(a, csrf_token)
        actions = (f"{bewerk}"
                   f"<div class='qadd-row'>{_artefact_archive_form(a, csrf_token)}</div>")
    extras = _wiki_extras(a, st, pags, csrf_token, can_edit)
    return (f"<div class='card'>{_artefact_head(a)}{body}{_laatst_gewijzigd(a)}"
            f"{_artefact_versions_html(a)}{actions}{extras}</div>")


def _artefact_inherited_card(it, *, st: _Stores | None = None, pags: list | None = None) -> str:
    a = it["artefact"]
    badge = (f" <a class='chip' href='/node?id={_e(it['origin_id'])}&tab={_tab_for(a.kind)}' "
             f"title='click = go to the source role'>via {_e(it['origin_name'])}</a>")
    body = _artefact_body_html(a, st=st, pags=pags)
    # Read-only hier (geen csrf, can_edit=False): wie dit ziet is niet de eigenaar-rol, en
    # bewerken/feiten-toevoegen gebeurt bij de bron — zelfde regel als de kaart eronder al meldt
    # ("Applies here ... edit at the source").
    extras = _wiki_extras(a, st, pags, "", False)
    return f"<div class='card'>{_artefact_head(a, extra=badge)}{body}{_laatst_gewijzigd(a)}{extras}</div>"


def _artefact_tab_html(st: _Stores, rec, kind: str, csrf_token: str, username: str | None,
                       *, titel: str, leeg: str, van_rapport: str = "") -> str:
    can_edit = _can_edit_artefacts(st, rec, csrf_token, username)
    oi = artefacts.own_and_inherited(rec.id, kind, st.records, st.att)

    # Policies zijn geen verbod maar een voorwaarde, en zijn governance-eigendom: één regel boven de
    # lijst i.p.v. een badge/slotje per item.
    kop = ("<p class='muted'>All policies below are "
           "governance-owned.</p>" if kind == "policy" else "")

    # Wiki vóór archief (scope 61): kom je hier via "→ To the wiki" op een projectrapport, dan is
    # het RAPPORT de tekst die het voorstel-formulier moet voorinvullen, niet de pagina's eigen
    # body. Fail-soft: geen rapport leesbaar (project weg, geen store) → gewoon terugvallen op de
    # normale voorinvulling, geen fout op het scherm.
    rapport_tekst = ""
    if van_rapport and kind == wiki.PAGINA_KIND:
        try:
            store = getattr(st, "project_docs", None)
            rapport_tekst = (store.read(van_rapport) or "").strip() if store is not None else ""
        except Exception:                                    # noqa: BLE001 — nooit de tab breken
            rapport_tekst = ""

    # Een note IS een wiki-pagina, en op de permalink kan wie hem niet bezit al een wijziging
    # voorstellen. Op déze tab kon dat niet: een niet-eigenaar zag alleen tekst, zonder enige weg om
    # te zeggen dat er iets niet klopt. Zelfde formulier, zelfde verzoekpad — niet een tweede vorm.
    def _anders(a) -> str:
        if kind != wiki.PAGINA_KIND or can_edit or not csrf_token:
            return ""
        from nooch_village.views.wiki import _voorstel_form
        return _voorstel_form(st, a, csrf_token,
                              next_url=f"/node?id={rec.id}&tab={_tab_for(kind)}",
                              prefill=rapport_tekst)

    _pags = wiki.paginas(st.att) if kind == wiki.PAGINA_KIND else None
    own = "".join(_artefact_own_card(a, csrf_token, can_edit, anders=_anders(a), st=st, pags=_pags)
                  for a in oi["own"])
    own = own or f"<div class='card muted'>{_e(leeg)}</div>"

    add = ""
    if can_edit:
        if kind == "policy":
            # Een policy kan alleen op een domein dat de rol écht via governance bezit.
            domains = list(getattr(rec.definition, "domains", None) or [])
            if domains:
                add = _artefact_add_form(rec, kind, csrf_token, domains)
            else:
                add = ("<div class='card muted'>This role has no domain yet — first assign one "
                       "via governance, then you can create a policy on that domain here.</div>")
        else:
            add = _artefact_add_form(rec, kind, csrf_token)
    sec_own = f"<div class='c2-sec'><h3>From this role</h3>{own}{add}</div>"

    inh = "".join(_artefact_inherited_card(it, st=st, pags=_pags) for it in oi["inherited"])
    inh = inh or "<div class='card muted'>Nothing applies here from above.</div>"
    sec_inh = (f"<div class='c2-sec'><h3>Applies here</h3>"
               f"<p class='muted'>Inherited from parent roles/circles "
               f"(read-only) — edit at the source.</p>{inh}</div>")
    return f"<h2>{_e(titel)}</h2>{kop}{sec_own}{sec_inh}"


# IA-fase 2: een tool "woont" onder zijn eigenaar-rol. Deze registry hangt de tool-schermen als
# kaart op de Tools-tab van de juiste rol (via Deelnemers → rol → Tools). De schermen blijven losse
# routes; hier maken we ze vindbaar vanuit de rol. In fase 3 worden de keyword-tools rol-lenzen op
# één gedeelde datalaag. Sleutel = record-id van de rol.
# Fase 3: de keyword-tools zijn rol-LENZEN op één gedeelde datalaag (/keywords?lens=…). Elke rol
# ziet dezelfde laag door zijn eigen bril, dus niet vier losse cijferbronnen.
_ROLE_TOOLS = {
    "mother_earth__nooch__marketing_lead": [
        ("Linkbuilding", "Pitch or ignore linkbuilding targets", "/linkbuilding"),
        ("Keywords — volume & direction", "What you make content for", "/keywords?lens=marketing")],
    # De convergentie-check is automatisch (nieuwe woorden dragen 28 dagen een ster op de
    # woordenschat) en signalen zijn ontsloten via de Kennisbank — dus hier alleen nog het
    # ene Library-oppervlak.
    "librarian": [
        ("Library", "Approved words, ranked by opportunity", "/woordenschat"),
        # Lege href = uitgeschakelde kaart. Het Oracle-scherm (/kennisbank) is met de rest
        # van de kennisbank-schermen in #516 verwijderd; de opgeslagen inzichten staan er
        # nog (kennisbank.json), het scherm niet. Weghalen zou het vermogen stil laten
        # verdwijnen, laten staan gaf een kale 404.
        ("Oracle", "The screen was removed on 20 September 2026 — the stored insights are still in the data", "")],
    "concurrent_scout": [
        ("Keywords — analysis", "Opportunity + suggestions, ranked", "/keywords?lens=trends")],
    "harry_hemp": [
        ("Long-term trends", "Structural rise versus blip (trend reindexing)", "/keywords?lens=scientist")],
    # De Backlog Builder stond op de Notes-tab van deze rol. Een gereedschap hoort onder Tools,
    # naast de andere rol-tools — en zo houdt de rol zijn eigen notes/wiki-pagina's.
    # De copy-policies wonen bij Community & Email, maar ze gelden voor iedereen die voor Nooch
    # schrijft. Daarom staan generator en checker op de CIRKEL: vooraf de prompt, achteraf de
    # toets, tegen precies dezelfde policies.
    "mother_earth__nooch": [
        ("Copy prompt generator", "The copy policies as a ready-made prompt", "/copy-prompt"),
        ("Copy checker", "Check a text against the copy policies — layer 1, then the judgement",
         "/copy-check")],
    WEBSITE_DEVELOPER_ROLE: [
        ("Site audit", "Green, orange, red for reachability, speed, accessibility, SEO and claims "
         "of the shop, with the reasons behind each light", "/site-audit")],
}


# Tools die bij een DOMEIN horen in plaats van bij een rol-id. De claims-toets stond hier als
# `_ROLE_TOOLS["compliance"]`; die rol verhuisde naar de Nooch-cirkel en kreeg een nieuw id,
# waarna de kaart zonder één foutmelding van de rol verdween. Een domein is governance-eigendom
# en verhuist mee met de rol die het bezit, dus de tools hangen daaraan. `{rol}` wordt vervangen
# door het id van de rol die het domein nú bezit.
_DOMAIN_TOOLS = {
    claims_db.DOMEIN: [
        ("Claims checker", "EmpCo/ACM check on text or page: red, orange, green", "/claims"),
        # `&amp;` en niet `&`: de kaart zet de href ongeëscapet in het attribuut (de bestaande
        # tool-URLs hebben geen tweede parameter), dus de escaping hoort hier in de waarde.
        ("Claim pages", "One wiki page per claim, with its evidence or what is still missing",
         "/node?id={rol}&amp;tab=notes")],
}


def _tool_kaart(label: str, desc: str, href: str) -> str:
    """Eén tool-kaart. Lege href = het scherm bestaat niet (meer): dan géén link, maar een
    zichtbaar uitgeschakelde kaart met de reden in de beschrijving. Waarom niet gewoon
    weghalen: een kaart die stilletjes verdwijnt laat niemand merken dat er een vermogen weg
    is. Waarom niet laten staan: een dode link laat het wél merken, maar als een kale 404."""
    if not href:
        return (f"<div class='card muted'><b>🛠 {_e(label)}</b> "
                f"<span class='chip muted'>○ not available</span>"
                f"<div class='muted'>{_e(desc)}</div></div>")
    return (f"<a class='card' href='{href}'><b>🛠 {_e(label)}</b>"
            f"<div class='muted'>{_e(desc)}</div></a>")


def _role_tools_html(rec) -> str:
    """De tool-schermen die onder deze rol wonen, als kaarten bovenaan de Tools-tab. Geen
    eigenaar-mapping en geen domein-mapping → lege string (dan toont de tab alleen radar +
    artefact-tools)."""
    rid = getattr(rec, "id", "")
    tools = list(_ROLE_TOOLS.get(rid, []))
    for d in (getattr(getattr(rec, "definition", None), "domains", None) or []):
        for label, desc, href in _DOMAIN_TOOLS.get(" ".join(str(d).split()).lower(), []):
            tools.append((label, desc, href.replace("{rol}", _e(rid))))
    if not tools:
        return ""
    cards = "".join(_tool_kaart(label, desc, href) for label, desc, href in tools)
    return (f"<div class='c2-sec'><h3>This role's tools</h3>"
            f"<div class='tile-grid'>{cards}</div></div>")


def _ritme_html(st: _Stores, rec) -> str:
    """Het terugkerende ritme van deze rol: wat draait er vanzelf, wanneer draaide het laatst,
    en wat kwam eruit.

    Waarom dit blok bestaat: een rol die 'elke week scant' is een belofte. Zonder zichtbare
    laatste run moet je erop vertrouwen. Staat de puls over tijd, dan tonen we DAT — een oude
    datum die er nog netjes uitziet wekt precies het verkeerde vertrouwen."""
    from nooch_village.role_rhythm import ritmes_voor
    ritmes = ritmes_voor(getattr(rec, "id", ""), rec, st.dd)
    if not ritmes:
        return ""
    rijen = ""
    for r in ritmes:
        if r["overtijd"]:
            chip = f"<span class='chip coral'>⚠ {_e(r['overtijd_tekst'])}</span>"
        elif r["laatst"]:
            chip = f"<span class='chip'>{_e(r['laatst'])}</span>"
        else:
            chip = "<span class='chip muted'>not run yet</span>"
        rijen += (f"<div class='c2-sec'><b>{_e(r['naam'])}</b> {chip}"
                  f"<div class='muted'>{_e(r['uitkomst'])}</div></div>")
    return f"<div class='c2-sec'><h3>Recurring rhythm</h3>{rijen}</div>"


def render_node(st: _Stores, node_id: str, tab: str, csrf_token: str = "", msg: str = "",
                group: str = "", clf: str = "due", mw: str = "7d", username: str | None = None,
                van: str = "", tot: str = "", compare: bool = False, goal: str = "",
                van_rapport: str = "", kind_flt: str = "") -> str:
    # OUDE TABNAMEN BLIJVEN WERKEN. policies/notes/tools zijn sinds fase 7 één Wiki-tab. De alias
    # staat HIER en niet in de route, zodat elke aanroeper hem krijgt — de route, een test, een
    # ingebedde render. Hij vertaalt naar het juiste voorfilter, wat preciezer is dan doorsturen.
    if tab in ("policies", "notes", "tools"):
        kind_flt = kind_flt or {"policies": "policy", "notes": "note", "tools": "tool"}[tab]
        tab = "wiki"
    rec = st.records.get(node_id)
    if rec is None:
        return _page("Not found", "<p>Node not found.</p><p><a href='/'>← home</a></p>")
    is_c = org.is_circle(rec)
    tabs = _CIRCLE_TABS if is_c else _ROLE_TABS
    if tab not in tabs:
        tab = "overview"
    recs = st.records.all()
    # HIER WERD EEN BREADCRUMB BEREKEND die nergens in de uitvoer terechtkwam: het kruimelpad zelf
    # is weggehaald toen de organisatieboom de positie ging tonen, de berekening bleef staan. Wie
    # de plek in de organisatie zoekt, ziet hem in de boom — daar is de node gemarkeerd.
    chip = "<span class='chip'>circle</span>" if is_c else "<span class='chip'>role</span>"
    # SLAPEND: zichtbaar, want een slapende rol ziet er verder uit als elke andere. Het record is
    # compleet — purpose, accountabilities, vervuller staan er allemaal nog — en juist daarom moet
    # er iets zeggen dat hij niet draait, anders lees je een rol die er is als een rol die werkt.
    if getattr(rec, "slaapt", False):
        reden = str(getattr(rec, "slaap_reden", "") or "geen reden vastgelegd")
        chip += (f" <span class='chip muted' title='{_e(reden)}'>💤 slaapt</span>")

    if tab == "overview":
        content = _overview_html(st, rec, csrf_token)
    elif tab == "roles":
        content = _roles_html(st, rec, csrf_token)
    elif tab == "members":
        content = _members_html(st, rec, csrf_token)
    elif tab == "wiki":
        # ÉÉN TAB VOOR DRIE SOORTEN (fase 7). Policies, Notes en Tools waren drie tabs boven één
        # AttachmentStore; het enige verschil is `kind`. Drie deuren naar één kamer dwingen je te
        # weten waar iets ooit is neergezet vóór je het kunt vinden. Nu: één oppervlak met een
        # filter, precies zoals het prototype het toont — en zonder migratie, want `kind` bestond al.
        #
        # De tool-specifieke blokken (rol-tools, ritme, radar) horen bij `kind="tool"` en staan
        # daarom onder het tool-filter; bij "all" staan ze eronder, niet ertussen.
        soort = (kind_flt or "all").lower()
        if soort not in ("all", "policy", "note", "tool"):
            soort = "all"
        chips = "".join(
            f"<a class='cl-filter{' on' if soort == k else ''}' "
            f"href='/node?id={_e(node_id)}&tab=wiki&kind={k}'>{_e(lbl)}</a>"
            for k, lbl in (("all", "All"), ("policy", "Policy"), ("note", "Note"), ("tool", "Tool")))
        delen = [f"<div class='cl-filters'>{chips}</div>"]
        if soort in ("all", "policy"):
            delen.append(_artefact_tab_html(st, rec, "policy", csrf_token, username,
                                            titel="Policies",
                                            leeg="No policies on this role/circle yet."))
        if soort in ("all", "note"):
            delen.append(_artefact_tab_html(st, rec, "note", csrf_token, username, titel="Notes",
                                            leeg="No notes on this role/circle yet.",
                                            van_rapport=van_rapport))
        if soort in ("all", "tool"):
            delen.append(_role_tools_html(rec) + _ritme_html(st, rec)
                         + _artefact_tab_html(st, rec, "tool", csrf_token, username, titel="Tools",
                                              leeg="No tools on this role/circle yet."))
        content = "".join(delen)
    elif tab == "metrics":
        # Het nieuwe metrics-scherm (catalogus + dashboard + segmentatie + vergelijken), ingebed als
        # node-tab. Vervangt het oude _metrics_tab_html; KPI-aanmaken loopt via de rijke composer.
        content = render_metrics2_tab(st, rec, csrf_token, win=mw, compare=compare, van=van, tot=tot)
    elif tab == "goals":
        # Dezelfde inhoud als /goals, uit dezelfde functie. Een tweede kopie zou na één wijziging
        # uit de pas lopen — de regel die ook bij het projectenbord geldt.
        from nooch_village.views.doelen import render_goals
        content = render_goals(st, csrf_token=csrf_token, username=username, inner_only=True)
    elif tab == "checklists":
        content = _checklists_tab_html(st, rec, csrf_token, flt=clf)
    elif tab == "projects":
        content = _projects_tab_html(st, rec, csrf_token, group=group, username=username, goal=goal)
    else:
        content = ""      # onbekende tab (niet in de tab-lijst) → geen inhoud

    # DE TWEE OVERLEG-KNOPPEN STONDEN HIER ÉN IN DE ZIJBALK. Dit blok bouwde zijn eigen
    # `.c2-meet`-rij met precies dezelfde live-status-check (`_rov_items`, `st.werk.is_open`)
    # die `overleg_items()` al doet — twee renders van dezelfde knop uit dezelfde bron. Dat
    # loopt uit de pas zodra er iets aan één van de twee verandert, en dan zie je twee knoppen
    # die elkaar tegenspreken; de zijbalk kreeg op 21 september de live-uitnodiging en deze
    # niet, dus dat was al begonnen.
    # De zijbalk-versie blijft: hij is circle-scoped, kent de open/dicht-stand en staat op elk
    # scherm op dezelfde plek. Zelfde opruiming als de dubbele organisatieboom hieronder.
    # GEEN RECHTERRAIL MEER (fase 10 punt 3). De organisatieboom stond hier én in de zijbalk
    # links: twee keer dezelfde boom op hetzelfde scherm. De linker blijft, deze gaat weg.
    # Er verdwijnt niets: de volledige rollenlijst staat op de Roles-tab hieronder, en de positie
    # in de organisatie (welke node je open hebt) wordt nu in de ZIJBALK gemarkeerd — `_send`
    # geeft de huidige node-id door aan `_tree_html`, wat de rail hiervoor deed.
    # Breadcrumb was al eerder weg (founder 23 jul), om dezelfde reden: de hiërarchie stond er al.
    main = (f"<div class='c2-main'>"
            f"<h1>{_e(_name(rec))} {chip}</h1>{_banner(msg)}{_slaap_blok(rec)}"
            f"{_tabbar(node_id, tabs, tab)}{content}</div>")
    modal = _modal_html(json.dumps(_mentionables(st)[0])) if csrf_token else ""
    inner = (f"{_DS_LINK}"
             f"{_nav()}"
             f"<div class='c2-wrap'>{main}</div>{modal}")
    return _page(_name(rec), inner)


def _person_context_tab_html(st: _Stores, filler_type: str, pid: str) -> str:
    """Union van de context-notes (kind='note') over de rollen die deze filler vervult. Eén lijst,
    tools en docs door elkaar, met een visueel onderscheid op subtype (leeg/ontbrekend → 'doc')."""
    rows, total = "", 0
    for rid in sorted(set(st.assign.roles_of(filler_type, pid))):
        orec = st.records.get(rid)
        owner = _e(_name(orec) if orec else rid)
        for a in st.att.list(rid, "note"):
            total += 1
            sub = (getattr(a, "subtype", "") or "doc")
            icon = "🛠" if sub == "tool" else "📄"
            title = _e(a.title or (a.body[:60] if a.body else "(no title)"))
            rows += (f"<li>{icon} <span class='chip muted'>{_e(sub)}</span> {title} "
                     f"<span class='muted'>· {owner}</span></li>")
    body = (f"<ul class='clean'>{rows}</ul>" if rows
            else "<span class='muted'>No context notes on this person's roles.</span>")
    return f"<div class='c2-sec'><h3>Context ({total})</h3>{body}</div>"


def _person_metrics_tab_html(st: _Stores, filler_type: str, pid: str) -> str:
    """Aggregatie-lens: DEZELFDE metric-render als op rol-niveau (het nieuwe metrics-scherm, mét
    grafieken), per rol die deze filler vervult. Read-only, dus geen '+ KPI maken'/data-invoer. Geen
    tweede render — een KPI/grafiek die je op een rol toevoegt, verschijnt hier automatisch
    (reference, not copy)."""
    out = ""
    for rid in sorted(set(st.assign.roles_of(filler_type, pid))):
        rec = st.records.get(rid)
        if rec is None or not st.metrics.tiles_of(rid):
            continue
        base = f"/node?id={_e(rid)}&tab=metrics"
        out += (f"<h4 class='muted'>{_e(_name(rec))}</h4>"
                + render_metrics2_person(st, rec, base))
    if not out:
        return ("<div class='c2-sec'><span class='muted'>No metrics on this person's "
                "roles.</span></div>")
    return out + _METRICS_JS      # één keer de kaart-omdraai-JS voor alle rol-tegels samen


def _person_checklists_tab_html(st: _Stores, filler_type: str, pid: str, csrf: str) -> str:
    """Union van checklists.for_node(rid) over de rollen, gegroepeerd per rol. Hergebruikt _cl_row:
    die toont het target_type-label ("Alle leden" bij all = cirkel-verplichting, de rol bij role) en
    de afvink-form ALLEEN met csrf (conform effective_csrf). Geen per-lid-status; wie afvinkte staat
    in reports.by. Afvinken loopt via cl_report, achter de is_role_filler/Circle-Lead-gate."""
    sections, total = "", 0
    for rid in sorted(set(st.assign.roles_of(filler_type, pid))):
        items = st.checklists.for_node(rid)
        if not items:
            continue
        orec = st.records.get(rid)
        owner = _e(_name(orec) if orec else rid)
        rows = "".join(_cl_row(st, it, csrf) for it in items)
        sections += f"<h4 class='muted' style='margin:.6rem 0 .2rem'>{owner}</h4>{rows}"
        total += len(items)
    body = (sections if sections
            else "<span class='muted'>No checklist items on this person's roles.</span>")
    return f"<div class='c2-sec'><h3>Checklist ({total})</h3>{body}</div>"


def render_person(st: _Stores, pid: str, tab: str = "rollen", username: str | None = None,
                  csrf_token: str = "") -> str:
    """Persoon/AI-role-filler-view: read-only aggregatie-lens over de rollen die iemand vervult,
    met de rol-view-chrome (tabs via _tabbar(base="/person")). Vult rollen/projecten/context; de
    overige tabs zijn read-only placeholders. Geen schrijfacties, geen csrf. `username` = de sessie
    (voor de context-drempel); GEEN persoons-gate — de context-tab hangt op 'is er een sessie',
    niet op 'ben jij deze persoon'. Handelt zowel een mens (people) als een AI-inwoner (personas) af."""
    p = st.people.get(pid)
    if p is not None:
        filler_type, name, subtitle = "person", p.name, (p.email or "no email")
        avatar = f"<span class='av' style='width:28px;height:28px'>{_e(_initials(p.name))}</span>"
        chip = ""
    else:
        pa = st.personas.get(pid)
        if pa is None:
            return _page("Not found", "<p>Person not found.</p><p><a href='/'>← home</a></p>")
        filler_type, name = "persona", pa.name
        subtitle = "AI inhabitant" + (f" · {pa.mbti}" if pa.mbti else "")
        avatar = "<span class='av ai' style='width:28px;height:28px'>AI</span>"
        chip = "<span class='chip'>AI</span>"

    if tab not in _PERSON_TABS:
        tab = "rollen"
    role_ids = st.assign.roles_of(filler_type, pid)

    if tab == "rollen":
        # Eén blok per rol, uitklapbaar (<details>, geen JS) naar de accountabilities van de rol
        # (rec.definition.accountabilities). set() = "toon elke rol één keer", geen dedup-magie.
        uniek = sorted(set(role_ids))
        blocks = ""
        for rid in uniek:
            rec = st.records.get(rid)
            if rec is None:
                continue
            crumb = " › ".join(_e(_name(st.records.get(i)))
                               for i in org.breadcrumb(st.records.all(), rid)[:-1])
            crumb_html = f" <span class='muted'>· {crumb}</span>" if crumb else ""
            accs = rec.definition.accountabilities or []
            acc_html = ("<ul class='clean'>" + "".join(f"<li>{_e(a)}</li>" for a in accs) + "</ul>"
                        if accs else "<span class='muted'>No accountabilities.</span>")
            blocks += (f"<details class='c2-acc'><summary>"
                       f"<a href='/node?id={_e(rid)}'>{_e(_name(rec))}</a>{crumb_html} "
                       f"<span class='muted' style='font-size:.75rem'>· {len(accs)} accountabilities"
                       f"</span></summary>{acc_html}</details>")
        content = (f"<div class='c2-sec'><h3>Roles ({len(uniek)})</h3>"
                   + (blocks if blocks else "<span class='muted'>No roles.</span>") + "</div>")
    elif tab == "projecten":
        # Hergebruikt de kanban-component (_projects_board), gefilterd op mijn rollen; csrf → drag-drop.
        content = _person_projects_tab_html(st, filler_type, pid, csrf_token)
    elif tab == "context":
        # AUTHZ: iedereen-ingelogd — de context-tab is zichtbaar voor elk INGELOGD village-lid, niet
        # voor anonieme guests. Drempel op "is er een sessie", niet op "ben jij deze persoon" (geen
        # persoons-gate). "guest" (auth uit) en geen sessie → geen inhoud.
        if not username or username == "guest":
            content = "<div class='c2-sec'><p class='muted'>Log in to see context.</p></div>"
        else:
            content = _person_context_tab_html(st, filler_type, pid)
    elif tab == "metrics":
        # Read-only union van de rol-metrics; schrijven blijft op rol-niveau (geen knop hier).
        content = _person_metrics_tab_html(st, filler_type, pid)
    elif tab == "checklist":
        # Union van de rol-checklists; afvinken via cl_report achter de is_role_filler-gate.
        # Afvink-form alleen met csrf (effective_csrf) — guest/niet-ingelogd → geen knop.
        content = _person_checklists_tab_html(st, filler_type, pid, csrf_token)
    else:
        content = ("<div class='c2-sec'><p class='muted'>Read-only aggregation lens over the roles "
                   "this person fills. This tab follows in a separate task.</p></div>")

    main = (f"<div class='c2-main'><h1>{avatar} {_e(name)} {chip}</h1>"
            f"<div class='muted'>{_e(subtitle)}</div>"
            f"{_tabbar(pid, _PERSON_TABS, tab, base='/person')}{content}</div>")
    # Kaart-klik op het kanban-bord opent de project-detail-modal, net als op de node-view.
    modal = _modal_html(json.dumps(_mentionables(st)[0])) if csrf_token else ""
    inner = (f"{_DS_LINK}"
             f"{_nav()}"
             f"<div class='c2-wrap'>{main}</div>{modal}")
    return _page(name, inner)






def render_rolefillers(st: _Stores, role_id: str, csrf_token: str = "", fragment: bool = False) -> str:
    rec = st.records.get(role_id)
    if rec is None:
        return ("<p class='muted'>Unknown role.</p>" if fragment
                else _page("Not found", "<p>Unknown.</p>"))
    back = f"/node?id={(rec.parent or rec.id)}&tab=roles"

    def hid():
        return (f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                f"<input type='hidden' name='role' value='{_e(role_id)}'>"
                f"<input type='hidden' name='next' value='{_e(back)}'>")

    fillers = st.assign.fillers_of(role_id, record=rec)
    rows = ""
    for f in fillers:
        if f.type == "person":
            p = st.people.get(f.id); label = (p.name if p else f.id); ai = False
            name = f"<a href='/person?id={_e(f.id)}'>{_e(label)}</a>"
        else:
            pa = st.personas.get(f.id); label = (pa.name if pa else f.id); ai = True
            name = f"{_e(label)} (AI)"
        prev = f" <span class='muted' style='font-size:.8rem'>· {_e(f.focus)}</span>" if f.focus else ""
        rows += (
            f"<div class='frow'>"
            f"<details class='ffocus' style='flex:1'>"
            f"<summary>{_avatar(label, ai)} {name}{prev}</summary>"
            f"<form method='post' action='/action' style='margin:.3rem 0 .2rem 30px'>{hid()}"
            f"<input type='hidden' name='filler' value='{f.type}:{_e(f.id)}'>"
            f"<input name='focus' value='{_e(f.focus)}' placeholder='Focus (optional)' "
            f"style='padding:.3rem .4rem;border:1px solid var(--border);border-radius:var(--radius)'> "
            f"<button class='btn' type='submit' name='action' value='role_focus'>Save focus</button>"
            f"</form></details>"
            f"<form method='post' action='/action' style='display:inline'>{hid()}"
            f"<input type='hidden' name='filler' value='{f.type}:{_e(f.id)}'>"
            f"<button class='dellink' type='submit' name='action' value='role_unassign'>remove</button>"
            f"</form></div>")
    if not rows:
        rows = "<p class='muted'>No one assigned yet.</p>"
    # Alleen mensen vervullen een rol; AI koppel je per accountability (niet hier).
    opts = "<option value=''>— pick person —</option>"
    opts += "".join(f"<option value='person:{_e(p.id)}'>{_e(p.name)}</option>" for p in st.people.all())
    add = (f"<div class='pf' style='margin-top:.6rem'><form method='post' action='/action'>{hid()}"
           f"<label>Add to {_e(_name(rec))}</label>"
           f"<select name='filler'>{opts}</select>"
           f"<button class='btn ok' type='submit' name='action' value='role_assign' "
           f"style='margin-top:.4rem'>Assign</button></form></div>")
    frag = (f"<h2 style='margin-top:0'>Manage role fillers — {_e(_name(rec))}</h2>"
            f"<div>{rows}</div>{add}")
    if fragment:
        return frag
    main = (f"<div class='c2-main' style='max-width:560px'>"
            f"<div class='c2-bar'><a href='{_e(back)}'>← back</a></div>{frag}</div>")
    return _page("Role fillers", f"{_DS_LINK}<div class='c2-wrap'>{main}</div>")


def render_middelen(st: _Stores, role_id: str, acc_id: str, csrf_token: str = "",
                    fragment: bool = False) -> str:
    """Welke dorpsmiddelen dienen deze ene belofte, en het beheer daarvan.

    Heette tot scope 39 `render_aitask` en deed twee dingen tegelijk: een AI aan een belofte hangen
    die hem 'zelfstandig uitvoert', en een dorpsmiddel koppelen. Het eerste was een belofte zonder
    uitvoering (`kind="autonoom"` werd buiten de view nergens gelezen) en is weg. Wat overblijft is
    het middel: welke capability uit de registry staat deze belofte ter beschikking.

    Het roloverleg heeft zijn eigen koppelknop in het uitvoerbaarheids-stoplicht; dit scherm is de
    plek waar je een gelegde koppeling ook weer LOS kunt maken, en die is er verder niet.
    """
    rec = st.records.get(role_id)
    acc_text = acc_ids.text_for(rec.definition, acc_id) if rec else ""
    back = f"/node?id={role_id}&tab=overview"

    def hid():
        return (f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                f"<input type='hidden' name='role' value='{_e(role_id)}'>"
                f"<input type='hidden' name='acc_id' value='{_e(acc_id)}'>"
                f"<input type='hidden' name='next' value='{_e(back)}'>")

    def delform(tid: str) -> str:
        return (f"<form method='post' action='/action' style='display:inline'>"
                f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                f"<input type='hidden' name='tid' value='{_e(tid)}'>"
                f"<input type='hidden' name='next' value='{_e(back)}'>"
                f"<button class='dellink' type='submit' name='action' value='middel_remove'>remove</button>"
                f"</form>")

    rows = ""
    for t in skill_links.links_for_acc(st.ai, role_id, acc_id):
        rows += f"<div class='frow'><span style='flex:1'>{_link_chip(t)}</span>{delform(t.id)}</div>"
    if not rows:
        rows = "<p class='muted'>No village resource is linked to this commitment yet.</p>"

    # De picker: registry-skills die deze rol nog niet via deze belofte voert. De domeinpoort
    # filtert beslis-skills weg bij een rol die het domein niet houdt.
    middel = _middel_picker(st, rec, role_id, acc_id, hid)

    frag = (f"<h2 style='margin-top:0'>Village resources on this commitment</h2>"
            f"<p class='muted'>Accountability: {_e(acc_text) or '—'}</p>"
            f"<p style='font-size:.82rem;color:var(--gray)'>A resource says this village capability "
            f"serves this commitment. It never changes the TEXT of the accountability, and it never "
            f"runs by itself: the role filler stays responsible.</p>{rows}{middel}")
    if fragment:
        return frag
    main = (f"<div class='c2-main' style='max-width:560px'>"
            f"<div class='c2-bar'><a href='{_e(back)}'>← back</a></div>{frag}</div>")
    return _page("Village resources", f"{_DS_LINK}<div class='c2-wrap'>{main}</div>")

