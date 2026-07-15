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

from nooch_village.web_base import _e, _page, _field
from nooch_village.cockpit2_util import _name, _BUILD, _stamp
from nooch_village.inbox_wizard import INTENTS, OTYPE_LABEL

_STATUS = {"nieuw": ("● nieuw", "chip ok"), "gelezen": ("bezig", "chip muted"),
           "verwerkt": ("✓ verwerkt", "chip outline")}


def _source_link(st, n: dict) -> str:
    pid = (n.get("project_id") or "").strip()
    p = st.projects.get(pid) if pid else None
    if p is not None:
        scope = str(p.get("scope") or "project")[:60]
        return f"<a href='/project?pid={_e(pid)}'>{_e(scope)}</a>"
    return _e(n.get("by") or "onbekende bron")


def _who(st, n: dict) -> str:
    by = (n.get("by") or "").strip()
    rec = st.records.get(by) if by else None
    return _name(rec) if rec is not None else (by or "iemand")


def _one_line(text: str, cap: int = 90) -> str:
    t = " ".join((text or "").split())
    return (t[:cap] + "…") if len(t) > cap else (t or "(geen samenvatting)")


def _hid(csrf: str, nid: str, nxt: str = "/inbox") -> str:
    return (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
            f"<input type='hidden' name='nid' value='{_e(nid)}'>"
            f"<input type='hidden' name='next' value='{_e(nxt)}'>")


def _btn(csrf: str, nid: str, action: str, label: str, cls: str = "flink", nxt: str = "/inbox") -> str:
    return (f"<form method='post' action='/action' class='emo-f'>{_hid(csrf, nid, nxt)}"
            f"<button class='{cls}' name='action' value='{action}'>{_e(label)}</button></form>")


# ── de lijst ────────────────────────────────────────────────────────────────────
def _inbox_row(st, n: dict, csrf: str, done_nid: str = "") -> str:
    status = st.notif.status_of(n)
    lbl, chip = _STATUS.get(status, _STATUS["nieuw"])
    nid = n.get("id", "")
    sep = "<span class='fsep'>·</span>"
    meta = (f"<div class='rdr-meta'><span class='{chip}'>{_e(lbl)}</span> "
            f"<span class='muted'>via {_e(_who(st, n))}</span> {sep} {_source_link(st, n)} {sep} "
            f"<span class='muted'>{_e(_stamp(n.get('at')))}</span></div>")
    title = f"<div class='rdr-sig'>{_e(_one_line(n.get('snippet')))}</div>"

    if status == "verwerkt":
        vs = st.notif.verwerkingen_of(n)
        chips = " ".join(f"<span class='chip outline'>{_e(v.get('label') or 'uitkomst')}</span>" for v in vs) \
            or "<span class='chip outline'>verwerkt</span>"
        body = f"{meta}{title}<div class='ffoot-l'>{chips}</div>"
        act = f"<div class='rdr-act'>{_btn(csrf, nid, 'notif_archive', 'archiveren')}</div>"
        # Viermoment: de zojuist afgeronde spanning krijgt een groene rand + een kader met wat je vastlegde.
        if nid and nid == done_nid:
            regels = "".join(f"<li>{_e(v.get('label') or v.get('otype') or 'uitkomst')}</li>" for v in vs) \
                or "<li>geen uitkomst</li>"
            body += f"<div class='rdr-kader'>✓ Verwerkt. Dit legde je vast:<ul>{regels}</ul></div>"
            return f"<div class='rdr-row rdr-vier'><div class='rdr-body'>{body}</div>{act}</div>"
        return f"<div class='rdr-row'><div class='rdr-body'>{body}</div>{act}</div>"

    verwerk = f"<a class='btn ok sm' href='/inbox/verwerk?nid={_e(nid)}'>Verwerk</a>"
    prullenbak = _btn(csrf, nid, "notif_delete", "🗑", cls="flink")
    act = f"<div class='rdr-act'>{verwerk}{prullenbak}</div>"
    return f"<div class='rdr-row'><div class='rdr-body'>{meta}{title}</div>{act}</div>"


def render_inbox(st, targets, csrf_token: str = "", naam: str = "", done: str = "") -> str:
    items = st.notif.open_for_targets(targets)
    nieuw = sum(1 for n in items if st.notif.status_of(n) == "nieuw")
    body = ("".join(_inbox_row(st, n, csrf_token, done_nid=done) for n in items) if items
            else "<p class='muted'>Je inbox is leeg. Zodra een rol of het overleg je @-mentiont, "
                 "verschijnt het hier.</p>")
    kop = f"Inbox{(' — ' + _e(naam)) if naam else ''}"
    telling = (f"<p class='muted'>{len(items)} open, waarvan {nieuw} nieuw. Klik Verwerk om een "
               f"spanning af te handelen, of gooi 'm weg.</p>")
    main = (f"<div class='c2-main'><div class='c2-bar'><a href='/'>← home</a></div>"
            f"<h1>{kop} <span class='chip'>{len(items)}</span></h1>{telling}"
            f"<div class='rdr-tool'>{body}</div></div>")
    inner = (f"<div class='bar'>cockpit 2 · GlassFrog (PoC) · build {_BUILD} · "
             "<a href='/'>home</a> · <a href='/inbox'>inbox</a></div>"
             f"<div class='c2-wrap'>{main}</div>")
    return _page("Inbox", inner)


# ── de verwerk-pagina (twee panelen) ─────────────────────────────────────────────
def _spanning_pane(st, n: dict) -> str:
    """Links: de volledige spanning met wie/rol, bron en leeftijd, plus het verwerk-record tot nu toe."""
    sep = "<span class='fsep'>·</span>"
    meta = (f"<div class='rdr-meta'><span class='muted'>via {_e(_who(st, n))}</span> {sep} "
            f"{_source_link(st, n)} {sep} <span class='muted'>{_e(_stamp(n.get('at')))}</span></div>")
    body = _e(n.get("snippet") or "(geen inhoud)").replace("\n", "<br>")
    vs = st.notif.verwerkingen_of(n)
    record = ""
    if vs:
        rows = "".join(f"<li>{_e(v.get('label') or v.get('otype') or 'uitkomst')}"
                       f"{(' — ' + _e(v.get('by'))) if v.get('by') else ''}</li>" for v in vs)
        record = (f"<div class='box rdr-rec'><strong>Al vastgelegd "
                  f"({len(vs)})</strong><ul>{rows}</ul></div>")
    return (f"<div class='rdr-pane'><h3>Spanning</h3>{meta}"
            f"<div class='fbubble rdr-rec'>{body}</div>{record}</div>")


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
    if otype == "project":
        sid = f"sel-{uid}"
        tgt = (f"<label class='att-lbl' for='{sid}'>Op welke rol?</label>"
               f"<select id='{sid}' name='owner'>{role_opts}</select>")
    elif otype == "action":
        sid = f"sel-{uid}"
        tgt = (f"<label class='att-lbl' for='{sid}'>Aan welk project?</label>"
               f"<select id='{sid}' name='pid_link'>{pj_opts}</select>")
    elif otype == "note":
        sid = f"sel-{uid}"
        tgt = (f"<label class='att-lbl' for='{sid}'>Note bij welke rol?</label>"
               f"<select id='{sid}' name='note_role'>{role_opts}</select>")
    else:  # roloverleg — gebruikt de cirkel van de bron
        tgt = "<span class='muted'>Wordt een voorstel op de roloverleg-agenda (mens-route).</span>"
    inhoud = _field("Inhoud (bewerkbaar)", "content", kind="textarea", value=prefill, fid=f"ct-{uid}")
    return (f"<form method='post' action='/action' class='wo-oc'>{hid}"
            f"{inhoud}{tgt}"
            f"<button class='btn sm' name='action' value='notif_outcome'>Vastleggen</button></form>")


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
                            f"<strong>{_e(label)}</strong> <em>(volgt in stap 2)</em></div>")
            else:
                form = _outcome_form(otype, nid, csrf, prefill, role_opts, pj_opts, nxt, uid)
                opts.append(f"<details class='wo-ocd box-details'><summary>{_e(q)} → "
                            f"<strong>{_e(label)}</strong></summary>{form}</details>")
        groups.append(f"<details class='box-details'><summary><strong>{_e(intent['label'])}"
                      f"</strong></summary>{''.join(opts)}</details>")
    klaar = (f"<form method='post' action='/action' class='emo-f rdr-rec'>"
             f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
             f"<input type='hidden' name='nid' value='{_e(nid)}'>"
             f"<input type='hidden' name='next' value='/inbox'>"
             f"<button class='btn ok sm' name='action' value='notif_klaar'>Klaar met deze spanning</button></form>")
    return (f"<div class='rdr-pane'><h3>Wat heb je nodig?</h3>{''.join(groups)}{klaar}</div>")


def render_verwerk(st, n: dict, csrf_token: str = "", role_opts: str = "", pj_opts: str = "") -> str:
    """De verwerk-pagina voor één inbox-item: links de spanning, rechts de intentie-wizard."""
    if n is None:
        inner = ("<div class='c2-wrap'><div class='c2-main'><a href='/inbox'>← inbox</a>"
                 "<p class='muted'>Deze spanning bestaat niet meer.</p></div></div>")
        return _page("Verwerk", inner)
    split = (f"<div class='rdr-split'>"
             f"{_spanning_pane(st, n)}{_wizard_pane(n, csrf_token, role_opts, pj_opts)}</div>")
    main = (f"<div class='c2-main'><div class='c2-bar'><a href='/inbox'>← inbox</a></div>"
            f"<h1>Verwerk spanning</h1>{split}</div>")
    inner = (f"<div class='bar'>cockpit 2 · GlassFrog (PoC) · build {_BUILD} · "
             "<a href='/'>home</a> · <a href='/inbox'>inbox</a></div>"
             f"<div class='c2-wrap'>{main}</div>")
    return _page("Verwerk", inner)
