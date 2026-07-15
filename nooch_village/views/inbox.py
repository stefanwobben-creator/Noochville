"""Inbox — de wachtrij van mentions gericht aan de eigenaar (als persoon of in een van zijn rollen).

Verzamelt de notificaties (NotifStore) voor alle doelen van de eigenaar, nieuwste eerst, en toont per
item de bron (het project waarin de mention staat) + wie 'm schreef, een tweeregelige samenvatting, en
DE VERWERK-FLOW ter plekke: je klapt de vijf uitkomsten (Info/Project/Actie/Note/Roloverleg) inline uit
en legt er één vast, of je handelt 'm af zonder uitkomst (pure FYI). Vastleggen maakt de uitkomst én zet
het item op verwerkt met die uitkomst als historie — je springt nergens heen. Drie kleurstatussen
(nieuw / gelezen / verwerkt), en een archiveerknop voor wat verwerkt is.

Hergebruik: web_base (_e/_page), cockpit2_util (_name/_BUILD), views.feed (dezelfde vijf-uitkomsten-kiezer
als op de wall). Geen nieuwe opslag — leunt op NotifStore.
"""
from __future__ import annotations

from nooch_village.web_base import _e, _page
from nooch_village.cockpit2_util import _name, _BUILD, _stamp
from nooch_village.views.feed import _wall_outcome_opts, _wall_outcome_form

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


def _has_source(st, n: dict) -> bool:
    """Bestaat de bron-comment nog (project + entry)? Alleen dan kan de vijf-uitkomsten-kiezer draaien;
    die vereist herkomst (net als op de wall). Zonder bron blijft alleen 'afgehandeld, geen uitkomst'."""
    pid = (n.get("project_id") or "").strip()
    eid = (n.get("entry_id") or "").strip()
    if not pid or not eid:
        return False
    p = st.projects.get(pid)
    return bool(p and any(e.get("id") == eid for e in (p.get("log") or [])))


def _hid(csrf: str, nid: str) -> str:
    return (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
            f"<input type='hidden' name='nid' value='{_e(nid)}'>"
            f"<input type='hidden' name='next' value='/inbox'>")


def _btn(csrf: str, nid: str, action: str, label: str, cls: str = "flink") -> str:
    return (f"<form method='post' action='/action' class='emo-f'>{_hid(csrf, nid)}"
            f"<button class='{cls}' name='action' value='{action}'>{_e(label)}</button></form>")


def _inbox_row(st, n: dict, csrf: str, role_opts: str = "", pj_opts: str = "") -> str:
    status = st.notif.status_of(n)
    lbl, chip = _STATUS.get(status, _STATUS["nieuw"])
    nid = n.get("id", "")
    sep = "<span class='fsep'>·</span>"
    meta = (f"<div class='rdr-meta'><span class='{chip}'>{_e(lbl)}</span> "
            f"<span class='muted'>via {_e(_who(st, n))}</span> {sep} {_source_link(st, n)} {sep} "
            f"<span class='muted'>{_e(_stamp(n.get('at')))}</span></div>")
    sig = f"<div class='rdr-sig'>{_e(n.get('snippet') or '(geen samenvatting)')}</div>"

    if status == "verwerkt":
        # Historie: toon wat het werd + wie, plus de archiveerknop.
        uit = _e(n.get("outcome") or "verwerkt")
        door = n.get("processed_by") or ""
        hist = (f"<span class='chip outline'>uitkomst: {uit}"
                f"{(' — ' + _e(door)) if door else ''}</span>")
        foot = f"<div class='ffoot-l'>{hist} {sep} {_btn(csrf, nid, 'notif_archive', 'archiveren')}</div>"
        return f"<div class='rdr-row'><div class='rdr-body'>{meta}{sig}{foot}</div></div>"

    # Nog te verwerken: de vijf-uitkomsten-kiezer inline (als er een bron-comment is) + de FYI-klep.
    acties = []
    if status == "nieuw":
        acties.append(_btn(csrf, nid, "notif_read", "markeer gelezen"))
    if _has_source(st, n):
        extra = (f"<input type='hidden' name='nid' value='{_e(nid)}'>"
                 f"<input type='hidden' name='next' value='/inbox'>")
        chooser = _wall_outcome_form(n.get("project_id", ""), n.get("entry_id", ""), csrf,
                                     n.get("snippet") or "", role_opts, pj_opts,
                                     extra_hid=extra, summary="Verwerk ▸")
    else:
        chooser = ("<span class='muted'>Geen bron-comment meer om een uitkomst aan te hangen — "
                   "handel 'm af als FYI.</span>")
    acties.append(_btn(csrf, nid, "notif_done", "afgehandeld, geen uitkomst"))
    foot = f"<div class='ffoot-l'>{chooser}{sep.join([''] + acties)}</div>"
    return f"<div class='rdr-row'><div class='rdr-body'>{meta}{sig}{foot}</div></div>"


def render_inbox(st, targets, csrf_token: str = "", naam: str = "") -> str:
    """De /inbox-pagina: niet-gearchiveerde mentions voor `targets` (persoon + zijn rollen), nieuwste
    eerst. Per item: bron, wie, samenvatting, kleurstatus, en de verwerk-flow ter plekke (vijf uitkomsten
    inline + 'afgehandeld, geen uitkomst'). Verwerkte items tonen hun uitkomst als historie."""
    items = st.notif.open_for_targets(targets)
    nieuw = sum(1 for n in items if st.notif.status_of(n) == "nieuw")
    role_opts, pj_opts = _wall_outcome_opts(st) if items else ("", "")
    body = ("".join(_inbox_row(st, n, csrf_token, role_opts, pj_opts) for n in items) if items
            else "<p class='muted'>Je inbox is leeg. Zodra een rol of het overleg je @-mentiont, "
                 "verschijnt het hier.</p>")
    kop = f"Inbox{(' — ' + _e(naam)) if naam else ''}"
    telling = (f"<p class='muted'>{len(items)} open, waarvan {nieuw} nieuw. Verwerk een mention hier "
               f"direct: kies een uitkomst of handel 'm af zonder uitkomst.</p>")
    main = (f"<div class='c2-main'><div class='c2-bar'><a href='/'>← home</a></div>"
            f"<h1>{kop} <span class='chip'>{len(items)}</span></h1>{telling}"
            f"<div class='rdr-tool'>{body}</div></div>")
    inner = (f"<div class='bar'>cockpit 2 · GlassFrog (PoC) · build {_BUILD} · "
             "<a href='/'>home</a> · <a href='/inbox'>inbox</a></div>"
             f"<div class='c2-wrap'>{main}</div>")
    return _page("Inbox", inner)
