"""Inbox — de wachtrij van mentions gericht aan de eigenaar (als persoon of in een van zijn rollen).

Verzamelt de notificaties (NotifStore) voor alle doelen van de eigenaar, nieuwste eerst, en toont per
item de bron (het project waarin de mention staat) + wie 'm schreef, een tweeregelige samenvatting, en
een doorklik-link naar de bron waar je 'm verwerkt. Drie kleurstatussen (nieuw / gelezen / verwerkt) en
een archiveerknop voor wat verwerkt is. De afhandeling zelf gebeurt bij de bron, niet hier.

Hergebruik: web_base (_e/_page), cockpit2_util (_name/_BUILD). Geen nieuwe opslag — leunt op NotifStore.
"""
from __future__ import annotations

from nooch_village.web_base import _e, _page
from nooch_village.cockpit2_util import _name, _BUILD, _stamp

# status → (label, chip-klasse voor de kleurcodering)
_STATUS = {"nieuw": ("● nieuw", "chip ok"), "gelezen": ("gelezen", "chip muted"),
           "verwerkt": ("✓ verwerkt", "chip outline")}


def _source_link(st, n: dict) -> str:
    """Bron van de mention: het project (met link naar de wall) waar hij geschreven is, anders 'wie'."""
    pid = (n.get("project_id") or "").strip()
    p = st.projects.get(pid) if pid else None
    if p is not None:
        scope = str(p.get("scope") or "project")[:60]
        return f"<a href='/project?pid={_e(pid)}'>{_e(scope)}</a>"
    return _e(n.get("by") or "onbekende bron")


def _who(st, n: dict) -> str:
    """De rol/persoon die de mention schreef, als leesbare naam."""
    by = (n.get("by") or "").strip()
    rec = st.records.get(by) if by else None
    return _name(rec) if rec is not None else (by or "iemand")


def _inbox_row(st, n: dict, csrf: str) -> str:
    status = st.notif.status_of(n)
    lbl, chip = _STATUS.get(status, _STATUS["nieuw"])
    hid = (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
           f"<input type='hidden' name='nid' value='{_e(n.get('id',''))}'>"
           f"<input type='hidden' name='next' value='/inbox'>")
    acties = []
    if status == "nieuw":
        acties.append(f"<form method='post' action='/action' class='emo-f'>{hid}"
                      f"<button class='flink' name='action' value='notif_read'>markeer gelezen</button></form>")
    if status != "verwerkt":
        acties.append(f"<form method='post' action='/action' class='emo-f'>{hid}"
                      f"<button class='btn ok sm' name='action' value='notif_processed'>✓ verwerkt</button></form>")
    else:
        acties.append(f"<form method='post' action='/action' class='emo-f'>{hid}"
                      f"<button class='flink' name='action' value='notif_archive'>archiveren</button></form>")
    sep = "<span class='fsep'>·</span>"
    return (f"<div class='rdr-row'><div class='rdr-body'>"
            f"<div class='rdr-meta'><span class='{chip}'>{_e(lbl)}</span> "
            f"<span class='muted'>via {_e(_who(st, n))}</span> {sep} {_source_link(st, n)} {sep} "
            f"<span class='muted'>{_e(_stamp(n.get('at')))}</span></div>"
            f"<div class='rdr-sig'>{_e(n.get('snippet') or '(geen samenvatting)')}</div>"
            f"<div class='ffoot-l'>{sep.join(acties)}</div></div></div>")


def render_inbox(st, targets, csrf_token: str = "", naam: str = "") -> str:
    """De /inbox-pagina: niet-gearchiveerde mentions voor `targets` (persoon + zijn rollen), nieuwste
    eerst, met bron, wie, samenvatting, kleurstatus en verwerk/archiveer-knoppen."""
    items = st.notif.open_for_targets(targets)
    nieuw = sum(1 for n in items if st.notif.status_of(n) == "nieuw")
    body = ("".join(_inbox_row(st, n, csrf_token) for n in items) if items
            else "<p class='muted'>Je inbox is leeg. Zodra een rol of het overleg je @-mentiont, "
                 "verschijnt het hier.</p>")
    kop = f"Inbox{(' — ' + _e(naam)) if naam else ''}"
    telling = (f"<p class='muted'>{len(items)} open, waarvan {nieuw} nieuw. Klik door naar de bron om "
               f"te verwerken; markeer daarna hier als verwerkt.</p>")
    main = (f"<div class='c2-main'><div class='c2-bar'><a href='/'>← home</a></div>"
            f"<h1>{kop} <span class='chip'>{len(items)}</span></h1>{telling}"
            f"<div class='rdr-tool'>{body}</div></div>")
    inner = (f"<div class='bar'>cockpit 2 · GlassFrog (PoC) · build {_BUILD} · "
             "<a href='/'>home</a> · <a href='/inbox'>inbox</a></div>"
             f"<div class='c2-wrap'>{main}</div>")
    return _page("Inbox", inner)
