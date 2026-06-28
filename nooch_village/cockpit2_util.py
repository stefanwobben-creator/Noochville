"""Pure HTML-helpers zonder _Stores-afhankelijkheid (brok 1 van de cockpit2-split)."""
from __future__ import annotations
import re

from nooch_village.cockpit import _e

# Welke tabs "leven" (echt werken) en welke nog grijs zijn. Status: live | basic | grey.
_TAB_STATUS = {
    "overview": "live", "roles": "live", "members": "live", "notes": "basic",
    "metrics": "live", "checklists": "live", "projects": "live",
    "policies": "grey",
}
_TAB_LABEL = {
    "overview": "Overview", "roles": "Roles", "members": "Members", "policies": "Policies",
    "notes": "Notes", "projects": "Projects", "checklists": "Checklists", "metrics": "Metrics",
}

_NL_MND = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]


def _name(rec) -> str:
    return getattr(rec.definition, "name", "") or rec.id


def _initials(name: str) -> str:
    return "".join(w[0] for w in name.split()[:2]).upper() or "?"


def _tabbar(node_id: str, tabs: list, cur: str) -> str:
    out = []
    for t in tabs:
        status = _TAB_STATUS.get(t, "grey")
        on = " on" if t == cur else ""
        out.append(f"<a class='c2-tab{on}' href='/node?id={_e(node_id)}&tab={t}'>"
                   f"{_e(_TAB_LABEL[t])}<span class='dot {status}'></span></a>")
    return "<div class='c2-tabs'>" + "".join(out) + "</div>"


def _todo(wat: str) -> str:
    return f"<div class='todo'><b>Nog te bouwen.</b> {_e(wat)}</div>"


def _avatar(label: str, is_ai: bool) -> str:
    if is_ai:
        return "<span class='av ai'>AI</span>"
    return f"<span class='av'>{_e(_initials(label))}</span>"


def _age(ts) -> str:
    if not ts:
        return ""
    import time as _t
    d = max(0, int((_t.time() - ts) / 86400))
    if d == 0:
        return "vandaag"
    if d < 31:
        return f"{d} d oud"
    if d < 365:
        return f"{d//30} mnd oud"
    return f"{d//365} jr oud"


def _fmt_due(iso: str) -> str:
    """ISO-datum 'YYYY-MM-DD' → '25 jun 2026'."""
    if not iso:
        return ""
    try:
        y, m, d = iso.split("-")
        return f"{int(d)} {_NL_MND[int(m) - 1]} {y}"
    except Exception:
        return iso


def _created_full(ts) -> str:
    """Relatieve leeftijd + absolute datum, bijv. 'vandaag · 27 jun 2026' of '1 week oud · 20 jun 2026'."""
    if not ts:
        return "—"
    import datetime
    d = datetime.datetime.fromtimestamp(ts)
    return f"{_age(ts)} · {d.day} {_NL_MND[d.month - 1]} {d.year}"


def _bron_html(url: str) -> str:
    """Bron-bewijs: een echte klikbare link bij http(s); een intern pad zonder route tonen we als
    tekst (geen dode 404-link) tot de kennisbank-koppeling live is."""
    u = (url or "").strip()
    if u.startswith("http://") or u.startswith("https://"):
        return f"<a href='{_e(u)}' target='_blank' rel='noopener'>bewijs ↗</a>"
    return f"<span class='muted' title='koppeling nog niet live'>{_e(u)} (nog niet live)</span>"


def _stamp(ts) -> str:
    """Datum + tijd, bijv. '27 jun 2026, 14:32'."""
    if not ts:
        return ""
    import datetime
    d = datetime.datetime.fromtimestamp(ts)
    return f"{d.day} {_NL_MND[d.month - 1]} {d.year}, {d.hour:02d}:{d.minute:02d}"


def _md(text: str) -> str:
    """Lichte opmaak voor reacties: HTML-veilig, met **vet**, regelafbrekingen en '- ' lijstjes."""
    import re
    s = _e(text or "")
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    out, in_ul = [], False
    for ln in s.split("\n"):
        if ln.strip().startswith("- "):
            if not in_ul:
                out.append("<ul class='fbul'>"); in_ul = True
            out.append(f"<li>{ln.strip()[2:]}</li>")
        else:
            if in_ul:
                out.append("</ul>"); in_ul = False
            out.append(ln + "<br>")
    if in_ul:
        out.append("</ul>")
    html = "".join(out)
    return html[:-4] if html.endswith("<br>") else html


def _ic(path: str) -> str:
    return (f"<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' "
            f"stroke-linecap='round' stroke-linejoin='round'>{path}</svg>")


def _parse_multipart(body: bytes, boundary: str):
    """Minimale multipart/form-data parser → (velden{str:str}, bestanden{str:(filename,bytes)})."""
    fields, files = {}, {}
    delim = ("--" + boundary).encode()
    for part in body.split(delim):
        part = part.strip(b"\r\n")
        if not part or part == b"--" or b"\r\n\r\n" not in part:
            continue
        head, _, content = part.partition(b"\r\n\r\n")
        headers = head.decode("utf-8", "replace")
        mname = re.search(r'name="([^"]*)"', headers)
        if not mname:
            continue
        mfile = re.search(r'filename="([^"]*)"', headers)
        if mfile:
            files[mname.group(1)] = (mfile.group(1), content)
        else:
            fields[mname.group(1)] = content.decode("utf-8", "replace")
    return fields, files


def _link_host(url: str) -> str:
    """Domeinnaam uit een URL als nette weergavenaam (zoals Trello bij een bijlage zonder titel)."""
    u = (url or "").split("//", 1)[-1]
    return u.split("/", 1)[0] or url


def _psec(icon: str, title: str, body: str) -> str:
    return (f"<div class='psec'><div class='psec-h'>{icon}<span>{_e(title)}</span></div>"
            f"<div class='psec-b'>{body}</div></div>")


_ICON_ADD_EMOJI = (
    "<svg width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='currentColor' "
    "stroke-width='2' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>"
    "<circle cx='10' cy='12' r='8'/>"
    "<line x1='7.5' y1='10.5' x2='7.5' y2='10.5'/>"
    "<line x1='12.5' y1='10.5' x2='12.5' y2='10.5'/>"
    "<path d='M7 15a3.5 2.5 0 0 0 6 0'/>"
    "<path d='M20 2.6v4M18 4.6h4'/></svg>")


def _person_name(st, pid: str) -> str:
    p = st.people.get(pid)
    return p.name if p else (pid or "")


_IC_CHECK = _ic("<polyline points='9 11 12 14 20 6'/><path d='M20 12v6a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h9'/>")
_IC_INFO = _ic("<circle cx='12' cy='12' r='9'/><line x1='12' y1='11' x2='12' y2='16'/><line x1='12' y1='8' x2='12' y2='8'/>")
_IC_CHAT = _ic("<path d='M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z'/>")
_IC_LINK   = _ic("<path d='M10 13a5 5 0 0 0 7 0l2-2a5 5 0 0 0-7-7l-1 1'/><path d='M14 11a5 5 0 0 0-7 0l-2 2a5 5 0 0 0 7 7l1-1'/>")
_IC_DL     = _ic("<path d='M12 4v10'/><polyline points='8 11 12 15 16 11'/><line x1='5' y1='19' x2='19' y2='19'/>")
_IC_DESC   = _ic("<line x1='4' y1='7' x2='20' y2='7'/><line x1='4' y1='12' x2='20' y2='12'/><line x1='4' y1='17' x2='14' y2='17'/>")
_IC_CLOCK  = _ic("<circle cx='12' cy='12' r='9'/><polyline points='12 7 12 12 15 14'/>")
_IC_FILE   = _ic("<path d='M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z'/><path d='M14 3v5h5'/>")
_IC_TARGET = _ic("<circle cx='12' cy='12' r='9'/><circle cx='12' cy='12' r='5'/><circle cx='12' cy='12' r='1.5'/>")
