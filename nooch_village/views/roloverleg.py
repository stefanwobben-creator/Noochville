"""Roloverleg-views — brok 4 van de cockpit2-split."""
from __future__ import annotations
import re
from typing import TYPE_CHECKING

from nooch_village.web_base import _e, _page
from nooch_village.cockpit2_util import _name, _psec, _IC_CHECK
from nooch_village.cockpit2_util import _EXTRA_CSS

if TYPE_CHECKING:
    from nooch_village.cockpit2 import _Stores


def _rov_kindlabel(kind: str) -> str:
    return {"add_role": "nieuwe rol", "remove_role": "rol verwijderen"}.get(kind, "rol wijzigen")


def _rov_children(st: _Stores, circle_id: str):
    """Directe kinderen van een cirkel: eigen rollen + subcirkels. Een supercirkel mag van een
    subcirkel de naam/purpose/accountabilities aanpassen, maar niet de rollen bínnen die subcirkel."""
    return [r for r in st.records.all()
            if getattr(r, "parent", None) == circle_id and not getattr(r, "archived", False)]


def _rov_items(st: _Stores, circle_id: str):
    """Alle agendapunten van DEZE cirkel (open + behandeld), voor de lijst en de groene knop."""
    cids = {r.id for r in _rov_children(st, circle_id)}
    return [it for it in st.agenda.all()
            if it.get("status") in ("open", "objected", "consented")
            and (it.get("role_id") in cids or it.get("change", {}).get("new_role_parent") == circle_id)]


def _rov_open(st: _Stores, circle_id: str):
    """Nog onbehandelde agendapunten (voor selectie en auto-door-naar-volgend)."""
    return [it for it in _rov_items(st, circle_id) if it.get("status") != "consented"]


def _rov_groups(st: _Stores, circle_id: str):
    """Agendapunten gegroepeerd per voorstel (GlassFrog: één voorstel kan meerdere rol-wijzigingen
    bevatten). Geeft [(group_id, [members])], in agenda-volgorde, leden op aanmaaktijd."""
    order, groups = [], {}
    for it in _rov_items(st, circle_id):
        gid = it.get("group") or it["id"]
        if gid not in groups:
            groups[gid] = []
            order.append(gid)
        groups[gid].append(it)
    return [(gid, sorted(groups[gid], key=lambda i: i.get("created_at", 0))) for gid in order]


def _rov_initials(text: str):
    """Splits een trailing '-SW' / '-JvdP' als initialen af. Geeft (rest, initialen)."""
    m = re.search(r"\s*-\s*([A-Za-z][A-Za-z.]{0,6})\s*$", text or "")
    if m:
        return text[:m.start()].strip(), m.group(1)
    return (text or "").strip(), ""


def _rov_add_item(st: _Stores, circle: str, naam_raw: str, group: str | None = None) -> bool:
    """Zet een rol-wijziging op de agenda: bestaande rol (naam matcht een kind) -> amend, anders
    nieuwe rol. Met `group` hangt de wijziging onder een bestaand voorstel (GlassFrog: meerdere
    wijzigingen per voorstel). Geeft True als er iets is toegevoegd."""
    naam, by = _rov_initials(naam_raw)        # '-SW' achteraan = initialen
    if not naam:
        return False
    match = next((r for r in _rov_children(st, circle) if _name(r).lower() == naam.lower()), None)
    if match is not None:
        st.agenda.add(match.id, "amend_role", {}, "", by=by or "founder", title=_name(match), group=group)
    else:
        slug = re.sub(r"[^a-z0-9]+", "_", naam.lower()).strip("_") or "rol"
        st.agenda.add(f"{circle}__{slug}", "add_role",
                      {"name": naam, "new_role_parent": circle, "purpose": "", "add_accountabilities": []},
                      "", by=by or "founder", title=naam, group=group)
    return True


def _rov_hard(st: _Stores, item: dict):
    """Mens-regel voor consent: een rol heeft een naam én minstens één accountability nodig
    (purpose is optioneel). Geeft een lijst blokkades terug (leeg = consent kan)."""
    if item.get("kind") == "remove_role":
        return []   # verwijderen mag (ook met verweesd werk; dat is advies, geen blok)
    d = _rov_draft(st, item)
    out = []
    if not (d.get("name") or "").strip():
        out.append("Geef de rol een naam.")
    if not [a for a in d.get("accs", []) if a.strip()]:
        out.append("Een rol heeft minstens één accountability nodig.")
    return out


def _rov_signals(st: _Stores, item: dict):
    """Secretaris-signalen tijdens het overleg (advies, niet-blokkerend): domein-botsing (G1),
    accountability-duplicaat bij een ándere rol (G2), verweesd werk (G3), mechanische purpose (G0),
    plus de lichte checks (-en-vorm, duplicaat binnen de rol, rijpheid)."""
    from nooch_village.roloverleg import _proposal_from_item, secretary_check
    from nooch_village.governance import Gate
    g, c = Gate(), _proposal_from_item(item).change
    out = []
    for label, fn in (("Domein-botsing", g._g1), ("Dubbele accountability", g._g2),
                      ("Verweesd werk", g._g3)):
        ok, reason = fn(c, st.records)
        if not ok:
            out.append({"level": "let op", "msg": f"{label}: {reason}"})
    if (c.purpose or "").strip().lower().startswith("beheert en bewaakt "):
        out.append({"level": "let op",
                    "msg": "Purpose lijkt een woordcluster ('Beheert en bewaakt …'); "
                           "beschrijf een echte functie."})
    out += [i for i in secretary_check(item, st.records) if i["level"] == "let op"]
    return out


def _rov_dupes(st: _Stores, text: str, exclude_role: str = ""):
    """Bestaat een vergelijkbare accountability al bij een ándere rol? (woordoverlap/substring)."""
    words = {w for w in re.findall(r"[a-zA-Z]{4,}", (text or "").lower())}
    low = (text or "").strip().lower()
    hits = []
    if not low:
        return hits
    for r in st.records.all():
        if getattr(r, "archived", False) or r.id == exclude_role:
            continue
        for a in r.definition.accountabilities:
            al = a.lower()
            if (len(words & {w for w in re.findall(r"[a-zA-Z]{4,}", al)}) >= 2
                    or low in al or al in low):
                hits.append((_name(r), a))
    return hits[:3]


def _rov_apply(st: _Stores):
    """Voer aangenomen (consented) voorstellen door op de records (mens-regel; niet de strikte
    autonome Gate). Gebruikt Secretary._adopt voor de schrijfactie."""
    from nooch_village.event_bus import EventBus
    from nooch_village.governance import Secretary
    from nooch_village.roloverleg import _proposal_from_item
    sec = Secretary(st.records, EventBus(name="roloverleg2"))
    done = []
    for item in [i for i in st.agenda.all() if i["status"] == "consented"]:
        if _rov_hard(st, item):
            continue
        naam = (_rov_draft(st, item).get("name") or "").strip()
        sec._adopt(_proposal_from_item(item))
        # _adopt zet bij een nieuwe rol geen weergavenaam — die vullen we hier aan.
        if item.get("kind") == "add_role" and naam:
            rec = st.records.get(item.get("role_id"))
            if rec is not None:
                rec.definition.name = naam
                rec.version += 1
                st.records.put(rec)
        st.agenda.remove(item["id"])
        done.append(item.get("title"))
    return done


def _rov_draft(st: _Stores, item: dict) -> dict:
    """De bewerkbare rol-definitie van een agendapunt (naam/purpose/domeinen/accountabilities).
    Init uit het bestaande record (amend) of uit de change (nieuwe rol)."""
    d = item.get("draft")
    if d:
        return {"name": d.get("name", ""), "purpose": d.get("purpose", ""),
                "accs": list(d.get("accs", [])), "domains": list(d.get("domains", []))}
    if item.get("kind") == "add_role":
        ch = item.get("change", {})
        return {"name": item.get("title", ""), "purpose": ch.get("purpose", ""),
                "accs": list(ch.get("add_accountabilities", [])), "domains": list(ch.get("add_domains", []))}
    rec = st.records.get(item.get("role_id"))
    if rec is not None:
        de = rec.definition
        return {"name": _name(rec), "purpose": de.purpose or "",
                "accs": list(de.accountabilities), "domains": list(de.domains)}
    return {"name": item.get("title", ""), "purpose": "", "accs": [], "domains": []}


def _rov_snapshot(st: _Stores, item: dict):
    if item.get("kind") == "add_role":
        return None
    rec = st.records.get(item.get("role_id"))
    if rec is None:
        return None
    de = rec.definition
    return {"name": _name(rec), "purpose": de.purpose,
            "accountabilities": list(de.accountabilities), "domains": list(de.domains)}


def _rov_save_draft(st: _Stores, iid: str, draft: dict) -> None:
    """Sla de draft op én herbereken de change (diff t.o.v. de huidige rol) via roloverleg-logica."""
    item = st.agenda.get(iid)
    if item is None:
        return
    from nooch_village.roloverleg import build_change_from_fields
    change, _rid, title = build_change_from_fields(
        item, _rov_snapshot(st, item), naam=draft["name"], purpose=draft["purpose"],
        accs=draft["accs"], domeinen=draft["domains"])
    st.agenda.update_fields(iid, draft=draft, change=change, title=title or item.get("title"))


def _rov_member_block(st: _Stores, item: dict, csrf: str, back: str, circle_id: str = "") -> tuple[str, list]:
    """Eén rol-wijziging binnen een voorstel (GlassFrog: een voorstel kan er meerdere bevatten).
    Velden: naam, purpose, domeinen, accountabilities. Diff-weergave: verwijderd = doorgestreept
    (pas weg na consent) met herstel, toegevoegd = als 'nieuw' gemarkeerd. Geeft (html, harde-regels)."""
    draft = _rov_draft(st, item)
    iid = item["id"]
    snap = _rov_snapshot(st, item)
    is_amend = snap is not None and item.get("kind") != "add_role"

    def hid():
        return (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
                f"<input type='hidden' name='iid' value='{_e(iid)}'>"
                f"<input type='hidden' name='circle' value='{_e(circle_id)}'>"
                f"<input type='hidden' name='next' value='{_e(back)}'>")
    keep = f"data-reopen='{_e(back)}'"
    sub = "this.form.requestSubmit?this.form.requestSubmit():this.form.submit()"

    def _iss_html(lst):
        return "".join(f"<div class='sec-issue {('blok' if i['level'] == 'blok' else 'let')}'>📋 {_e(i['msg'])}</div>"
                       for i in lst)

    rm_member = (f"<form method='post' action='/action' style='display:inline' {keep}>{hid()}"
                 f"<button class='rovm-close' type='submit' name='action' value='rov2_remove' "
                 f"title='Verwijder uit voorstel'>✕</button></form>")

    # --- verwijder-rol blok ---
    if item.get("kind") == "remove_role":
        nm = _name(st.records.get(item.get("role_id"))) or item.get("title")
        adv = _rov_signals(st, item)
        sec = (f"<div class='sec-block'><div class='sec-kop'>📋 Secretaris (advies)</div>{_iss_html(adv)}</div>"
               if adv else "")
        revert = (f"<form method='post' action='/action' {keep}>{hid()}"
                  f"<input type='hidden' name='kind' value='amend_role'>"
                  f"<button class='flink' type='submit' name='action' value='rov2_setkind'>← terug naar wijzigen</button></form>")
        note = ("<p class='muted' style='font-size:.78rem;margin:.2rem 0 .6rem'>"
                "De secretaris signaleert alleen; het overleg beslist. Consent verwijdert de rol, "
                "ook als er werk verweesd raakt.</p>")
        html = (f"<div class='rovm rovm-del'><div class='rovm-h'>"
                f"<span class='rovm-kind'>Verwijderen · <b>{_e(nm)}</b></span>{rm_member}</div>"
                f"<p>Deze rol wordt <b>verwijderd</b> als het voorstel wordt aangenomen.</p>{sec}{note}{revert}</div>")
        return html, []

    # --- amend / add blok ---
    acc_issues, general = {}, []
    for iss in _rov_signals(st, item):
        hit = next((a for a in draft["accs"] if a and a[:40].lower() in iss["msg"].lower()), None)
        if hit is not None:
            acc_issues.setdefault(hit, []).append(iss)
        else:
            general.append(iss)
    hard = _rov_hard(st, item)

    def field_form(field, label, value, was=""):
        waschip = f" <span class='rovm-was'>was: {_e(was)}</span>" if was else ""
        return (f"<div class='rovm-field'><label class='att-lbl'>{label}{waschip}</label>"
                f"<form method='post' action='/action' {keep}>{hid()}"
                f"<input type='hidden' name='action' value='rov2_set'><input type='hidden' name='field' value='{field}'>"
                f"<input name='value' value='{_e(value)}' onchange='{sub}'></form></div>")

    name_was = (snap.get("name", "") if (is_amend and (snap.get("name", "") or "") != draft["name"]) else "")
    purp_was = (snap.get("purpose", "") if (is_amend and snap.get("purpose")
                and (snap.get("purpose", "") or "") != draft["purpose"]) else "")
    name_f = field_form("name", "Naam", draft["name"], name_was)
    purpose_f = field_form("purpose", "Purpose", draft["purpose"], purp_was)

    def diff_list(label, orig, drafted, add_action, rm_action, per_issue=None):
        ol = {x.lower() for x in orig}
        dl = {x.lower() for x in drafted}

        def itform(text, action, lbl, cls):
            return (f"<form method='post' action='/action' style='display:inline' {keep}>{hid()}"
                    f"<input type='hidden' name='text' value='{_e(text)}'>"
                    f"<button class='{cls}' type='submit' name='action' value='{action}'>{lbl}</button></form>")
        rows = ""
        for x in orig:                                   # bestaand: behouden of (doorgestreept) verwijderd
            if x.lower() in dl:
                rows += (f"<div class='rovm-item'><span class='rovm-iv'>{_e(x)}</span>"
                         f"{itform(x, rm_action, '✕', 'dellink')}</div>"
                         f"{_iss_html(per_issue.get(x, [])) if per_issue else ''}")
            else:
                rows += (f"<div class='rovm-item is-del'><span class='rovm-iv'><s>{_e(x)}</s></span>"
                         f"{itform(x, add_action, 'herstel', 'flink')}</div>")
        for x in drafted:                                # nieuw toegevoegd
            if x.lower() not in ol:
                badge = "<span class='chip green'>nieuw</span> " if is_amend else ""
                rows += (f"<div class='rovm-item is-new'><span class='rovm-iv'>{badge}{_e(x)}</span>"
                         f"{itform(x, rm_action, '✕', 'dellink')}</div>"
                         f"{_iss_html(per_issue.get(x, [])) if per_issue else ''}")
        addf = (f"<form method='post' action='/action' class='rov-addrow' {keep}>{hid()}"
                f"<input name='text' placeholder='{_e(label.lower())} toevoegen…'>"
                f"<button class='btn ok sm' type='submit' name='action' value='{add_action}'>+</button></form>")
        return f"<div class='rovm-field'><label class='att-lbl'>{_e(label)}</label>{rows}{addf}</div>"

    acc_b = diff_list("Accountabilities", list(snap["accountabilities"]) if snap else [], draft["accs"],
                      "rov2_acc_add", "rov2_acc_remove", per_issue=acc_issues)
    dom_b = diff_list("Domeinen", list(snap["domains"]) if snap else [], draft["domains"],
                      "rov2_dom_add", "rov2_dom_remove")

    sec = ""
    if general:
        sec += f"<div class='sec-block'><div class='sec-kop'>📋 Secretaris (advies)</div>{_iss_html(general)}</div>"
    if hard:
        sec += ("<div class='sec-block'>"
                + "".join(f"<div class='sec-issue blok'>⛔ {_e(h)}</div>" for h in hard) + "</div>")

    # GlassFrog: 'verwijder deze rol' + 'maak van deze rol een cirkel' (roadmap, grijs).
    footer = ""
    if item.get("kind") == "amend_role":
        delrole = (f"<form method='post' action='/action' {keep}>{hid()}"
                   f"<input type='hidden' name='kind' value='remove_role'>"
                   f"<button class='flink' type='submit' name='action' value='rov2_setkind'>Rol verwijderen</button></form>")
        circ = "<span class='flink is-soon' title='Binnenkort'>Maak van deze rol een cirkel</span>"
        footer = f"<div class='rovm-foot rov-delrole'>{delrole}{circ}</div>"

    kindlbl = "Nieuwe rol" if item.get("kind") == "add_role" else "Wijzigen rol"
    nm = draft["name"] or item.get("title")
    head = f"<div class='rovm-h'><span class='rovm-kind'>{kindlbl} · <b>{_e(nm)}</b></span>{rm_member}</div>"
    html = f"<div class='rovm'>{head}{name_f}{purpose_f}{acc_b}{dom_b}{sec}{footer}</div>"
    return html, hard


def _rov_editor(st: _Stores, item: dict, csrf: str, back: str, circle_id: str = "") -> str:
    """Een voorstel (GlassFrog-model): één of meer rol-wijzigingen samen, met diff-weergave en één
    consent voor het hele voorstel. 'Toevoegen aan voorstel' betrekt nog een (bestaande of nieuwe)
    rol erbij. Werkafspraak/verkiezing zijn roadmap (grijs)."""
    base = f"/roloverleg2?circle={circle_id}"
    gid = st.agenda.group_of(item["id"])
    members = st.agenda.members_of_group(gid) or [item]
    back = f"{base}&iid={item['id']}"

    blocks, all_hard = "", []
    for m in members:
        b, hard = _rov_member_block(st, m, csrf, back, circle_id)
        blocks += b
        all_hard += hard

    def hid():
        return (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
                f"<input type='hidden' name='iid' value='{_e(item['id'])}'>"
                f"<input type='hidden' name='circle' value='{_e(circle_id)}'>"
                f"<input type='hidden' name='next' value='{_e(back)}'>")
    keep = f"data-reopen='{_e(back)}'"

    roles = sorted(_rov_children(st, circle_id), key=lambda r: _name(r).lower())
    dl = "".join(f"<option value='{_e(_name(r))}'>" for r in roles)
    add_role = (f"<form method='post' action='/action' class='rov-addrow' {keep}>{hid()}"
                f"<input type='hidden' name='group' value='{_e(gid)}'>"
                f"<input name='naam' list='rov-roles-add' placeholder='Bestaande of nieuwe rol… (-SW)' autocomplete='off'>"
                f"<datalist id='rov-roles-add'>{dl}</datalist>"
                f"<button class='btn ok sm' type='submit' name='action' value='rov2_add_to_group'>+</button></form>")
    soon = "<select disabled><option>Binnenkort</option></select>"
    add_block = (f"<div class='rov-addprop'><div class='sec-kop'>Toevoegen aan voorstel</div>"
                 f"<div class='rov-addgrid'>"
                 f"<div><label class='att-lbl'>Rol toevoegen/wijzigen</label>{add_role}</div>"
                 f"<div><label class='att-lbl is-soon'>Werkafspraak toevoegen/wijzigen</label>{soon}</div>"
                 f"</div></div>")

    if all_hard:
        consent = ("<button class='btn ok' disabled>Neem voorstel aan</button> "
                   "<span class='muted'>los de blokkade(s) op</span>")
    else:
        consent = (f"<form method='post' action='/action'>{hid()}"
                   f"<button class='btn ok' type='submit' name='action' value='rov2_consent' "
                   f"data-reopen='{_e(base)}'>Neem voorstel aan</button></form>")

    return (f"<div class='rov-editor'>{blocks}{add_block}"
            f"<div class='rov-consent'>{consent}</div></div>")


def render_roloverleg2(st: _Stores, circle_id: str, iid: str = "", csrf_token: str = "",
                       fragment: bool = False) -> str:
    """Roloverleg in modal-vorm. Brok 1: frame + agenda links (toevoegen, lijst, selecteren)."""
    crec = st.records.get(circle_id)
    if crec is None:
        return ("<p class='muted'>Onbekende cirkel.</p>" if fragment
                else _page("Niet gevonden", "<p>Onbekend.</p>"))
    base = f"/roloverleg2?circle={circle_id}"
    roles = sorted(_rov_children(st, circle_id), key=lambda r: _name(r).lower())

    def hid(nextu):
        return (f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                f"<input type='hidden' name='circle' value='{_e(circle_id)}'>"
                f"<input type='hidden' name='next' value='{_e(nextu)}'>")

    # Agenda-lijst: één rij per VOORSTEL (GlassFrog: een voorstel kan meerdere rol-wijzigingen
    # bevatten). Behandeld = doorgestreept; initialen van de indiener achteraan.
    items_all = _rov_items(st, circle_id)
    items_open = _rov_open(st, circle_id)
    active = iid or (items_open[0]["id"] if items_open else "")
    rows = ""
    for gid, members in _rov_groups(st, circle_id):
        primary = members[0]
        done = all(m.get("status") == "consented" for m in members)
        on = any(m["id"] == active for m in members)
        cls = "rov-item" + (" on" if on else "") + (" done" if done else "")
        url = f"{base}&iid={primary['id']}"
        rm = (f"<form method='post' action='/action' style='display:inline'>{hid(base)}"
              f"<input type='hidden' name='iid' value='{_e(primary['id'])}'>"
              f"<button class='flink' type='submit' name='action' value='rov2_remove_group'>✕</button></form>")
        by = (primary.get("by") or "").strip()
        av = f"<span class='av rov-by' title='door {_e(by)}'>{_e(by)}</span>" if by and by != "founder" else ""
        title = primary.get("title") or primary.get("role_id")
        extra = f" <span class='rov-more'>+{len(members) - 1}</span>" if len(members) > 1 else ""
        rows += (f"<div class='{cls}'><a class='js-modal rov-link' href='{url}' data-href='{url}'>"
                 f"<span class='rov-title'>{_e(title)}{extra}</span></a>"
                 f"{av}{rm}</div>")
    if not rows:
        rows = "<p class='muted'>Nog geen agendapunten.</p>"

    # Toevoegen boven de lijst; minimalistisch: één veld (Enter of '+'); smart-search op bestaande rollen.
    dl = "".join(f"<option value='{_e(_name(r))}'>" for r in roles)
    add = (f"<form method='post' action='/action' class='rov-add'>{hid(base)}"
           f"<input name='naam' list='rov-roles' placeholder='Rol… (-SW voor initialen)' autocomplete='off'>"
           f"<datalist id='rov-roles'>{dl}</datalist>"
           f"<button class='btn ok sm' type='submit' name='action' value='rov2_add'>+</button></form>")
    left = _psec(_IC_CHECK, "Agenda", f"{add}<div class='rov-list'>{rows}</div>")

    # Rechts: editor van het geselecteerde voorstel; geen iid -> auto-selecteer het eerste open punt
    # (zo land je na consent vanzelf op het volgende).
    sel = next((it for it in items_all if it["id"] == iid), None) or (items_open[0] if items_open else None)
    if sel:
        right = _rov_editor(st, sel, csrf_token, f"{base}&iid={sel['id']}", circle_id=circle_id)
    else:
        right = "<p class='muted'>Geen open agendapunten meer. Voeg er een toe, of sluit de vergadering.</p>"

    n_consent = sum(1 for it in items_all if it.get("status") == "consented")
    confirm = (f"Overleg sluiten? {n_consent} aangenomen voorstel(len) worden doorgevoerd in de "
               f"records. Dit kan niet ongedaan." if n_consent
               else "Overleg sluiten? Er zijn geen aangenomen voorstellen om door te voeren.")
    foot = (f"<div class='rov-foot'><form method='post' action='/action' data-confirm='{_e(confirm)}'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"<input type='hidden' name='circle' value='{_e(circle_id)}'>"
            f"<input type='hidden' name='next' value='/node?id={_e(circle_id)}'>"
            f"<button class='btn ok' type='submit' name='action' value='rov2_end'>"
            f"Vergadering sluiten</button></form></div>")
    sec_note = ("<p class='wo-sec muted' style='margin:.2rem 0 .6rem'>Alleen de secretaris opent en "
                "sluit dit overleg.</p>")
    detail = (f"<h2 style='margin-top:0'>Governance meeting — {_e(_name(crec))}</h2>{sec_note}"
              f"<div class='pgrid rov-grid'><div class='pmain'>{left}</div>"
              f"<aside class='pdisc'>{right}</aside></div>{foot}")
    if fragment:
        return detail
    main = f"<div class='c2-main' style='max-width:980px'><div class='c2-bar'><a href='/node?id={_e(circle_id)}'>← terug</a></div>{detail}</div>"
    return _page("Roloverleg", f"<style>{_EXTRA_CSS}</style><div class='c2-wrap'>{main}</div>")

