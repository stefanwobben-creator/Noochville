"""Pure HTML-helpers zonder _Stores-afhankelijkheid (brok 1 van de cockpit2-split)."""
from __future__ import annotations
import re
import time as _time

from nooch_village.web_base import _e

_BUILD = _time.strftime("%H:%M")   # proces-starttijd: zichtbaar in de balk

# De rol waarop de Backlog Builder (Notes-vervanger) leeft. Eén bron voor gate + view + coupling.
WEBSITE_DEVELOPER_ROLE = "mother_earth__nooch__website_developer"

_CIRCLE_TABS = ["overview", "roles", "members", "policies", "notes", "tools", "projects",
                "checklists", "metrics"]
_ROLE_TABS = ["overview", "policies", "notes", "tools", "projects", "checklists", "metrics"]
# Persoon/AI-role-filler-view: een read-only aggregatie-lens over de rollen die iemand vervult,
# geen nieuwe autoriteitslaag. Spiegelt de rol-view-chrome via _tabbar(base="/person").
_PERSON_TABS = ["rollen", "projecten", "context", "metrics", "checklist"]

_TAB_LABEL = {
    "overview": "Overview", "strategy": "Strategy", "roles": "Roles", "members": "Members",
    "policies": "Policies", "notes": "Notes", "tools": "Tools", "projects": "Projects",
    "checklists": "Checklists", "metrics": "Metrics",
    "rollen": "Rollen", "projecten": "Projecten", "context": "Context", "checklist": "Checklist",
}

_NL_MND = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]


def _name(rec) -> str:
    return getattr(rec.definition, "name", "") or rec.id


def _initials(name: str) -> str:
    return "".join(w[0] for w in name.split()[:2]).upper() or "?"


def _tabbar(node_id: str, tabs: list, cur: str, base: str = "/node") -> str:
    # `base` parametriseert de route (rol-view: /node, persoon-view: /person). Component NIET
    # geforkt; bestaande callers gebruiken de default "/node" en veranderen niet.
    out = []
    for t in tabs:
        on = " on" if t == cur else ""
        out.append(f"<a class='c2-tab{on}' href='{base}?id={_e(node_id)}&tab={t}'>"
                   f"{_e(_TAB_LABEL[t])}</a>")
    return "<div class='c2-tabs'>" + "".join(out) + "</div>"


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
    """Lichte opmaak voor reacties/notities: HTML-veilig, met **vet**, *cursief*, ~~doorhalen~~,
    ## koppen, [tekst](url)-links (alleen http(s)), regelafbrekingen en '- ' lijstjes. CRLF (uit
    textareas/imports) wordt genormaliseerd zodat er geen losse \\r overblijft. XSS-veilig: de tekst
    is al ge-escaped (`_e`) vóór de opmaak-regexes draaien, en een link zonder http(s)-schema wordt
    NIET gelinkt (fail-closed, geen javascript:-urls)."""
    import re
    s = _e(text or "").replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)   # vet — vóór cursief, anders eet * de **
    s = re.sub(r"~~(.+?)~~", r"<del>\1</del>", s)             # doorhalen
    s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)               # cursief

    def _link(m):
        label, url = m.group(1), m.group(2)                  # label al ge-escaped; url gevalideerd op schema
        if url.startswith("http://") or url.startswith("https://"):
            return f"<a href='{url}' target='_blank' rel='noopener'>{label}</a>"
        return m.group(0)                                    # geen http(s) → laat de tekst staan (geen link)

    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _link, s)          # [tekst](url)
    out, in_ul = [], False
    for ln in s.split("\n"):
        if ln.strip().startswith("## "):                     # kop (regel-niveau, zoals de lijst)
            if in_ul:
                out.append("</ul>"); in_ul = False
            out.append(f"<h4>{ln.strip()[3:]}</h4>")
            continue
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


# De guarded wrapSel-definitie: één authoritatieve bron (`_WRAPSEL_DEF`), gebruikt door zowel de
# meegedragen editor-<script> (`_WRAPSEL_JS`) als de modal-controller (`_modal_html`). `if(!window.wrapSel)`
# → nooit dubbel gedefinieerd, ongeacht hoeveel editors of dat de modal 'm óók definieert. De modal heeft
# een eigen kopie nodig want een <script> in een fragment draait niet bij innerHTML (zie _modal_html).
_WRAPSEL_DEF = ("if(!window.wrapSel){window.wrapSel=function(btn,pre,post){"
                "var f=btn.closest('form');var t=f&&f.querySelector('textarea');if(!t)return;"
                "var s=t.selectionStart,e=t.selectionEnd,v=t.value;"
                "t.value=v.slice(0,s)+pre+v.slice(s,e)+post+v.slice(e);t.focus();"
                "t.selectionStart=s+pre.length;t.selectionEnd=e+pre.length;};}")
_WRAPSEL_JS = f"<script>{_WRAPSEL_DEF}</script>"


def md_editor(name: str, value: str = "", rows: int = 6,
              placeholder: str = "Body (markdown)…", help: bool = False) -> str:
    """De GEDEELDE opmaak-editor (markdown → veilige `_md`-weergave): `.editor`-kaart met mini-toolbar
    (vet/cursief/doorhalen/lijst/kop via wrapSel) boven een textarea. De link-knop is bewust weg; de
    renderer ondersteunt [tekst](url) nog wél (handmatig typen of plakken). Zelfvoorzienend — draagt de
    guarded wrapSel-JS zelf mee, zodat de editor op ELKE pagina werkt (ook zonder _modal_html) en een
    view 'm niet kan vergeten. `value` wordt hier ge-escaped; callers geven de RUWE waarde door.
    `help=True` toont een inklapbaar opmaak-spiekbriefje (bestaande `.tb-help`/`.md-help`-klassen)."""
    hlp = ("<details class='emoji-pick tb-help'><summary title='Opmaak-hulp'>?</summary>"
           "<div class='md-help'>**vet** · *cursief* · ~~doorhalen~~ · # kop · - lijst · [tekst](url)</div>"
           "</details>") if help else ""
    return (f"<div class='editor'><div class='editor-tb'>"
            f"<button type='button' class='tb-b' onclick=\"wrapSel(this,'**','**')\" title='Vet'><b>B</b></button>"
            f"<button type='button' class='tb-b' onclick=\"wrapSel(this,'*','*')\" title='Cursief'><i>I</i></button>"
            f"<button type='button' class='tb-b' onclick=\"wrapSel(this,'~~','~~')\" title='Doorhalen'><s>S</s></button>"
            f"<span class='tb-sep'></span>"
            f"<button type='button' class='tb-b' onclick=\"wrapSel(this,'- ','')\" title='Lijst'>•</button>"
            f"<button type='button' class='tb-b' onclick=\"wrapSel(this,'## ','')\" title='Kop'>H</button>"
            f"{hlp}</div>"
            f"<textarea name='{_e(name)}' rows='{rows}' placeholder='{_e(placeholder)}'>{_e(value)}</textarea>"
            f"</div>{_WRAPSEL_JS}")


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

_EXTRA_CSS = """
/* Cockpit2: <details> is standaard KAAL (geen kaart). Wie een kaart wil, zet expliciet
   .box-details. Dit overschrijft de globale details{}-regel uit cockpit.py (laadt hierna).
   Legacy cockpit laadt deze _EXTRA_CSS niet en houdt dus zijn kaart-default. */
details{background:none;border:none;border-radius:0;box-shadow:none;padding:0}
.box-details{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);margin:.5rem 0;padding:.3rem .9rem;box-shadow:var(--shadow)}
.box-details[open]{padding-bottom:.8rem}
.c2-bar{color:var(--gray);font-size:.85rem;margin:.2rem 0 .5rem}
.c2-wrap{display:flex;gap:1.2rem;align-items:flex-start;margin-top:.6rem}
.c2-main{flex:1 1 auto;min-width:0}
.c2-rail{flex:0 0 280px;max-width:280px}
.c2-meet{display:flex;gap:.4rem;margin:.4rem 0}
.c2-tabs{display:flex;flex-wrap:wrap;gap:.1rem;border-bottom:1px solid var(--border);margin:.7rem 0 1rem}
.c2-tab{padding:.4rem .7rem;font-size:.85rem;border-bottom:2px solid transparent;color:var(--gray);text-decoration:none}
.c2-tab.on{border-bottom-color:var(--green-dark);color:var(--green-dark);font-weight:700}
/* NASA-EPIC-aardbol (alleen op de anchor-overview): bijna kolombreed, rond, gestapelde frames die
   traag cross-faden. width iets smaller dan de sectie-scheidingslijn; vierkant via aspect-ratio.
   Geen rand (transparant); de frames verder ingezoomd zodat de zwarte marge zo dun mogelijk is.
   Lange, zachte fade voor een vloeiende draaiing. */
.epic-earth{position:relative;box-sizing:border-box;width:92%;aspect-ratio:1/1;margin:.6rem auto .3rem;border-radius:50%;overflow:hidden}
.epic-frame{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;transform:scale(1.25);opacity:0;transition:opacity 5s ease}
.epic-frame.on{opacity:1}
.epic-cap{text-align:center;font-size:.72rem;color:var(--muted);margin-bottom:.4rem}
/* Wachtindicator: draaiende 🌍 + tekst over de (nog zwarte) bol, verdwijnt zodra het frame geladen is. */
.epic-loading{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:.5rem;z-index:2;color:var(--muted)}
.epic-earth.loaded .epic-loading{display:none}
.epic-globe{font-size:2.6rem;line-height:1;animation:epic-spin 3s linear infinite}
.epic-load-txt{font-size:.8rem;letter-spacing:.02em}
@keyframes epic-spin{to{transform:rotate(360deg)}}
@media (prefers-reduced-motion:reduce){.epic-globe{animation:none}}
.c2-sec{margin:1.1rem 0}
.c2-sec h3{font-family:var(--font-display);font-size:.72rem;text-transform:uppercase;letter-spacing:.04em;color:var(--green-dark);margin:0 0 .3rem}
ul.clean{list-style:none;padding:0;margin:0}
ul.clean li{padding:.22rem 0;border-bottom:1px solid var(--border)}
ul.clean li:last-child{border-bottom:none}
.person{display:inline-flex;align-items:center;gap:.35rem;padding:.15rem 0}
.av{width:22px;height:22px;border-radius:50%;background:var(--green);color:#fff;font-size:.62rem;display:inline-flex;align-items:center;justify-content:center;font-weight:700;flex:0 0 auto}
.av.ai{background:#7A5BD1}
.tree{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:.7rem .85rem;box-shadow:var(--shadow)}
.tree h3{font-family:var(--font-display);font-size:.72rem;text-transform:uppercase;color:var(--green-dark);margin:.1rem 0 .4rem}
.tree ul{list-style:none;margin:0;padding-left:.8rem}.tree>ul{padding-left:0}
.tree li{padding:.12rem 0;font-size:.86rem}
.tree .c{font-weight:700}
.tree .here{background:var(--green-tint);border-radius:5px;padding:0 .3rem}
/* Inklapbare sub-cirkels: native <details>/<summary> met een eigen caret; de naam-link (incl.
   .here-highlight) blijft in de summary zichtbaar, ook ingeklapt. */
/* padding:0 + [open]-reset overschrijven de globale details>summary/details[open]-regels uit web_base
   (anders krijgt elk boomitem .45rem summary-padding en .8rem onder een open cirkel — overtollig wit). */
.tree details.tree-c>summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:.2rem;padding:0;font-family:inherit;font-weight:inherit}
.tree details.tree-c[open]{padding-bottom:0}
.tree details.tree-c>summary::-webkit-details-marker{display:none}
.tree details.tree-c>summary::before{content:'\\0025B8';font-size:.6rem;color:var(--gray);flex:none;width:.6rem}
.tree details.tree-c[open]>summary::before{content:'\\0025BE'}
.pill{display:inline-block;font-size:.72rem;padding:.05rem .45rem;border-radius:var(--radius-pill);background:var(--cream-2);color:var(--gray);margin-left:.3rem}
.card{border:1px solid var(--border);border-radius:var(--radius);padding:.5rem .7rem;margin:.3rem 0;background:var(--surface)}
.pboard{display:flex;gap:.6rem;align-items:flex-start;overflow-x:auto}
.pcol{flex:1 1 0;min-width:160px;background:var(--cream-2);border:1px solid var(--border);border-radius:var(--radius);padding:.4rem}
.pcol-scroll{max-height:540px;overflow-y:auto}
.swim{margin:.6rem 0}
.swim-h{font-family:var(--font-display);font-weight:700;font-size:.85rem;color:var(--green-dark);margin:.2rem 0 .25rem}
.pcol-h{font-family:var(--font-display);font-weight:700;font-size:.72rem;text-transform:uppercase;letter-spacing:.03em;color:var(--green-dark);margin-bottom:.3rem}
.pcol .card{padding:.4rem .5rem;margin:.25rem 0;font-size:.85rem}
/* Subtiele status-tint per kolom (bevinding 4): het label blijft de primaire drager, de kleur
   versterkt alleen. doing=blauw (actief), waiting=amber (wacht, geen vol rood), done=groen,
   todo=grijs (toekomst). Lichte tinten → leesbaar, ook kleurenblind (label draagt de betekenis). */
.pcol[data-to='actief']{background:#eef3fb;border-color:#d3e0f4}
.pcol[data-to='wacht']{background:#fdf3e4;border-color:#efdcbf}
.pcol[data-to='done']{background:var(--green-tint);border-color:#cfe8d6}
.pcol[data-to='toekomst']{background:#f2f1ee;border-color:#e5e2db}
.dellink{background:none;border:none;color:var(--coral);font:inherit;font-size:.78rem;text-decoration:underline;cursor:pointer;padding:0;margin-left:.3rem}
.kpi-exp{color:var(--subtle);display:inline-flex;align-items:center;margin-left:.3rem}
.kpi-exp:hover{color:var(--green-dark)}
.kpi-exp svg{width:15px;height:15px}
.def-pick{display:flex;flex-direction:column;gap:.6rem;margin-top:.5rem}
.def-recs{display:flex;flex-wrap:wrap;align-items:center;gap:.35rem}
.def-rec{display:inline}
.def-grp{display:flex;flex-wrap:wrap;align-items:center;gap:.35rem;padding:.25rem 0;border-bottom:1px solid var(--border)}
.def-grp>.muted{flex:0 0 9rem}
.def-all{margin-top:.2rem}
.def-all>summary{cursor:pointer;list-style:none}
.def-share{display:flex;align-items:center;gap:.4rem;font-size:.82rem;color:var(--gray);margin:.2rem 0}
.cat-grid{display:grid;gap:.7rem;grid-template-columns:1fr}
@media(min-width:680px){.cat-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
.cat-card{border:1px solid var(--border);border-radius:var(--radius);padding:.6rem .7rem;background:var(--surface);min-width:0}
.cat-h{display:flex;align-items:center;justify-content:space-between;gap:.5rem;margin-bottom:.35rem}
.cat-use{font-size:.76rem;margin-top:.4rem}
.cat-hist{margin-top:.3rem;font-size:.78rem}
.cat-hist ul{margin:.3rem 0 0 1rem;padding:0}
.cat-hist summary{cursor:pointer;list-style:none}
.cat-nav{display:flex;flex-wrap:wrap;align-items:center;gap:.4rem;margin:.4rem 0 .9rem;position:sticky;top:0;background:var(--cream-2);padding:.5rem 0;z-index:5}
.cat-q{flex:1 1 14rem;min-width:10rem;border:1px solid var(--border);border-radius:var(--radius-pill);padding:.4rem .8rem;font:inherit}
.cat-f{border:1px solid var(--border);background:var(--surface);color:var(--gray);border-radius:var(--radius-pill);padding:.25rem .7rem;font-size:.8rem;cursor:pointer}
.cat-f.on{background:var(--green);color:#fff;border-color:var(--green)}
.cat-f-x{color:var(--subtle)}
.cat-count{margin-left:auto}
.cat-fg{display:inline-flex;align-items:center;gap:.3rem;flex-wrap:wrap}
.burnup-wrap{display:flex;flex-direction:column;gap:.25rem}
.bu-head b{font-size:1.2rem}
.burnup{display:block;border-bottom:1px solid var(--border)}
.bu-tempo{font-size:.85rem}
.bu-ok{color:var(--green-dark);font-weight:700}
.bu-no{color:var(--coral);font-weight:700}
.bu-proj{font-size:.74rem}
.tile-data{margin-top:.35rem;font-size:.76rem}
.tile-data>summary{cursor:pointer;list-style:none;color:var(--subtle);display:flex;align-items:center;gap:.4rem}
.tile-data>summary::-webkit-details-marker{display:none}
.tile-data>summary::before{content:'▸';color:var(--subtle)}
.tile-data[open]>summary::before{content:'▾'}
.tile-data .mtab{margin-top:.3rem;width:100%}
.delta{font-weight:700}
.delta.up{color:var(--green-dark)}
.delta.down{color:var(--coral)}
.delta.flat{color:var(--subtle)}
.bullet-wrap{display:flex;flex-direction:column;gap:.2rem}
.bullet-h b{font-size:1.1rem}
.bullet{display:block}
.bullet-bm{font-size:.72rem}
.kc-form{display:flex;flex-direction:column;gap:14px;max-width:34rem}
.kc-step{border:0.5px solid var(--border);border-radius:12px;padding:.7rem .9rem;background:var(--surface)}
.kc-h{display:flex;align-items:center;gap:8px;margin-bottom:.5rem}
.kc-n{display:inline-flex;align-items:center;justify-content:center;width:1.4rem;height:1.4rem;border-radius:999px;background:var(--green-tint);color:var(--green-dark);font-size:.8rem;font-weight:700}
.kc-form select,.kc-form input{width:100%;box-sizing:border-box;border:1px solid var(--border);border-radius:var(--radius);padding:.35rem .5rem;margin-bottom:.3rem}
.kc-radio{display:block;font-size:.88rem;padding:.15rem 0}
.kc-radio input{width:auto;margin-right:.4rem}
.kc-cond{margin:.3rem 0 .3rem 1.3rem}
.kc-hint{font-size:.72rem;margin:.2rem 0 0}
.tile-prov{font-size:.66rem;color:var(--coral);border:1px solid var(--coral);border-radius:var(--radius-pill);padding:0 .35rem;margin-left:.35rem;vertical-align:middle}
.cat-sec{margin-bottom:.6rem}
.cat-sec>summary{cursor:pointer;list-style:none;padding:.3rem 0;border-bottom:1px solid var(--border);font-size:.95rem}
.cat-sec>summary::-webkit-details-marker{display:none}
.cat-sec[open]>summary{margin-bottom:.5rem}
.cat-sec>summary::before{content:'▸ ';color:var(--subtle)}
.cat-sec[open]>summary::before{content:'▾ '}
.cat-tags{display:inline-flex;gap:.3rem;align-items:center}
.cat-card.hide{display:none}
.card.arch{opacity:.6}
.pcard{cursor:pointer;position:relative;transition:box-shadow .1s,border-color .1s}
.pcard:hover{border-color:var(--green);box-shadow:0 0 0 2px var(--green-tint)}
.pcard:active{cursor:grabbing}
.ptitle{font-weight:600}
.clabel{height:7px;border-radius:4px;margin:-.1rem 0 .35rem}
.pbadge{display:flex;align-items:center;gap:.35rem;margin-top:.35rem;font-size:.7rem;color:var(--muted)}
.pbar{height:6px;background:var(--border);border-radius:999px;overflow:hidden;width:70px}
.pbar>div{height:100%;background:var(--green)}
.pcol.over{outline:2px dashed var(--green);outline-offset:-2px;background:var(--green-tint)}
/* override de basis-details-stijl (wit kaartje) → ghost in de kolomkleur, Trello-stijl */
.qadd{margin-top:.15rem;padding:0}
.qadd>summary{list-style:none;cursor:pointer;color:var(--gray);font-family:var(--font-body);font-weight:500;font-size:.84rem;padding:.4rem .55rem;border-radius:var(--radius)}
.qadd>summary:hover{background:rgba(27,27,27,.07);color:var(--ink)}
.qadd>summary::-webkit-details-marker{display:none}
.qadd[open]{padding:0}
.qadd[open]>summary{display:none}
.qadd-form{display:flex;flex-direction:column;gap:.4rem;margin-top:.1rem}
.qadd-form textarea{width:100%;box-sizing:border-box;padding:.45rem .55rem;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface);box-shadow:var(--shadow);font:inherit;font-size:.85rem;resize:vertical}
.qadd-row{display:flex;align-items:center;gap:.4rem}
.qadd-x{background:none;border:none;font-size:1rem;color:var(--gray);cursor:pointer;padding:.1rem .3rem}
/* '+ project' krijgt dezelfde subtiele knop-vormgeving als de meeting-knoppen */
.addlink{display:inline-block;font-family:var(--font-body);font-weight:600;font-size:12px;
  border:1px solid rgba(27,27,27,.14);border-radius:var(--radius-pill);background:transparent;
  color:var(--gray);padding:.3rem .85rem;text-decoration:none;cursor:pointer;vertical-align:middle}
.addlink:hover{background:rgba(27,27,27,.05);color:var(--ink);text-decoration:none}
/* rollen-tab: rij met purpose + rechts uitgelijnde vervullers + toewijs-icoon */
.rrole{display:flex;align-items:flex-start;gap:1rem;padding:.6rem 0;border-bottom:1px solid var(--border)}
.rrole-info{flex:1 1 auto;min-width:0}
.rrole-pur{font-size:.84rem;margin-top:.1rem}
.rrole-fill{flex:0 0 220px;min-width:0}          /* vaste rechterkolom; inhoud links uitgelijnd */
.rrole-act{flex:0 0 auto}
.fillers{display:flex;flex-direction:column;gap:.15rem;align-items:flex-start}
.fperson{display:inline-flex;align-items:center;gap:.35rem;font-size:.86rem;color:var(--gray)}
.fillers.stack{flex-direction:row;align-items:center;gap:.3rem}
.stack-av{margin-left:-8px}.stack-av:first-child{margin-left:0}
.stack-av .av{border:2px solid var(--surface)}
.manage-ico{display:inline-flex;align-items:center;justify-content:center;color:var(--subtle);
  padding:.25rem;border-radius:var(--radius)}
.manage-ico:hover{color:var(--green-dark);background:rgba(27,27,27,.06)}
.accrow{display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;padding:.35rem 0;border-bottom:1px solid var(--border)}
.acc-text{flex:1 1 auto;min-width:0}
.acc-ai{flex:0 0 auto;display:flex;align-items:center;gap:.4rem;flex-wrap:wrap;justify-content:flex-end}
/* Chip-atoom: .chip (default = tint) + kleur-modifiers. Eén pill voor status/deadline/reactie/AI. */
.chip{display:inline-flex;align-items:center;gap:.3rem;border-radius:var(--radius-pill);padding:.1rem .55rem;font-size:.74rem;font-weight:700;line-height:1.5;background:var(--green-tint);color:var(--green-dark)}
.chip svg{width:13px;height:13px}
.chip.green{background:var(--green);color:#fff}
.chip.muted{background:var(--cream-2);color:var(--gray)}
.chip.outline{background:transparent;border:1px solid var(--border);color:var(--gray);font-weight:600}
.chip.coral{background:var(--error-tint);color:var(--coral);border:1px solid var(--coral)}
/* 'niet geconfigureerd' (ontbrekende creds) — bewust anders dan coral (kapotte API) en muted (geen data) */
.chip.amber{background:var(--yellow-light);color:#8a6d0b;border:1px solid var(--yellow)}
.chip.coral-solid{background:var(--coral);color:#fff;font-size:.64rem;text-transform:uppercase;padding:.04rem .4rem}
/* Impact-pills (scope 2): klikbare optie-chips met semantische kleur; elke pill toont z'n kleur (gedempt),
   de gekozen pill (.on) staat vol + met inset-ring. Kleuren per spec: g=groen, n=grijs, r=rood, l=lichtgrijs. */
.imp-wrap{display:flex;flex-wrap:wrap;gap:.3rem;align-items:center}
.imp-pill{padding:.14rem .55rem;border-radius:var(--radius-pill);border:1px solid transparent;font:inherit;font-size:.7rem;font-weight:700;line-height:1.5;cursor:pointer;opacity:.5}
.imp-pill:hover{opacity:.8}
.imp-pill.on{opacity:1;box-shadow:inset 0 0 0 1.5px currentColor}
.imp-pill.g{background:var(--green-tint);color:var(--green-dark)}
.imp-pill.n{background:var(--cream-2);color:var(--gray)}
.imp-pill.r{background:var(--error-tint);color:var(--coral)}
.imp-pill.l{background:var(--cream);color:var(--muted)}
/* Missie-impact-kleurstip op de bordkaart (alleen de stip, geen tekst): g=groen, n=grijs, r=rood. */
.mdot{display:inline-block;width:.55rem;height:.55rem;border-radius:50%;margin-right:.35rem;vertical-align:middle;flex:none}
.mdot.g{background:var(--green)}
.mdot.n{background:var(--gray)}
.mdot.r{background:var(--coral)}
/* Missie verzwakt: rode kaart-rand (signaal, geen blokkade) + infoblok in de modal. */
.pcard.verzwakt{border-color:var(--coral)}
.vzblock{border:1px solid var(--coral);background:var(--error-tint);border-radius:var(--radius);padding:.7rem .85rem;margin-bottom:.7rem}
.vz-h{font-weight:700;color:var(--coral);margin-bottom:.1rem}
.vz-t{color:var(--gray);font-size:.85rem;margin-bottom:.5rem}
.vz-form{margin:0}
.ai-gift{font-size:1rem;text-decoration:none;cursor:pointer;line-height:1}
.ai-on{font-size:.95rem;text-decoration:none;cursor:pointer;line-height:1;opacity:.8}
.ai-on:hover{opacity:1}
.ai-ov{margin:.2rem 0 .7rem}
.ai-ov-h{display:flex;align-items:center;gap:.4rem;margin-bottom:.2rem}
.ai-ov-list li{padding:.12rem 0}
.chiplink{text-decoration:none}
/* Knop-atoom: .btn (neutraal) + .ok (primair groen) + .no (gevaar) uit het design system,
   plus twee modifiers. Geen losse knop-varianten meer elders. */
.btn.sm{padding:.2rem .6rem;font-size:.74rem}
.btn.ghost{background:none;border-color:transparent}
.btn.ghost:hover{background:rgba(27,27,27,.05);border-color:var(--border)}
.dot{display:inline-block;width:.7rem;height:.7rem;border-radius:50%;margin-right:.35rem;vertical-align:middle}
.fentry{margin:0 0 .85rem}
.fhead{display:flex;align-items:center;gap:.45rem;margin-bottom:.2rem}
.fwho{min-width:0}
.fname{font-weight:700}
.frole{color:var(--subtle);font-weight:400;font-size:.85rem}
.fbubble{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:.5rem .65rem}
/* wall-post-accenten (scope 1): opdracht (groen) en bijlage (grijs) onderscheidbaar via linker rand.
   Bewuste afwijking van het prototype: deliverable-notes krijgen GEEN eigen accent — ze zijn in het
   huidige log-schema niet te onderscheiden van gewone rol-updates/faalnotities (add_role_message,
   {who:rol}). Een 'Deliverable'-badge vereist een schema-tag = datawijziging → scope 2. */
.fentry-opdracht .fbubble{border-left:3px solid var(--green);padding-top:.55rem}
.fentry-attach .fbubble{border-left:3px solid var(--border)}
.fkicker{display:block;font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--subtle);margin-bottom:.3rem}
.fbul{margin:.2rem 0 .2rem 1.1rem}
.ffoot{display:flex;align-items:center;justify-content:space-between;gap:.5rem;margin-top:.25rem}
.ffoot-l{display:flex;align-items:center;gap:.35rem;flex-wrap:wrap;min-width:0}
.emoji-pick{position:relative;display:inline-block;padding:0;margin:0}
.emoji-pick>summary{list-style:none;cursor:pointer;line-height:0;color:var(--subtle);display:inline-flex}
.emoji-pick>summary svg{width:18px;height:18px}
.emoji-pick>summary::-webkit-details-marker{display:none}
.emoji-pick[open]>summary,.emoji-pick>summary:hover{color:var(--green-dark)}
.emoji-pop{position:absolute;left:0;top:1.5rem;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);padding:.4rem;z-index:6;width:230px}
.emo-search{width:100%;box-sizing:border-box;border:1px solid var(--border);border-radius:var(--radius);padding:.3rem .45rem;margin-bottom:.35rem;font-size:.82rem}
.emo-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:.1rem;max-height:170px;overflow:auto}
.emo-f{display:inline}
.emo{border:none;background:none;cursor:pointer;font-size:1.05rem;padding:.15rem;border-radius:var(--radius);width:100%}
.emo:hover{background:var(--cream-2)}
.fstamp{color:var(--subtle);font-size:.72rem}
.flink{border:none;background:none;color:var(--gray);font-size:.78rem;cursor:pointer;text-decoration:underline;padding:0}
.flink:hover{color:var(--green-dark)}
.fsep{color:var(--subtle);font-size:.78rem}
.fedit{display:inline}
.fedit>summary{list-style:none;display:inline}
.fedit>summary::-webkit-details-marker{display:none}
.fedit textarea{width:100%;box-sizing:border-box;border:1px solid var(--border);border-radius:var(--radius);padding:.4rem .5rem}
.rov-list{margin-bottom:.6rem}
.rov-item{display:flex;align-items:center;gap:.3rem;padding:.25rem .3rem;border-radius:var(--radius)}
.rov-item.on{background:var(--cream-2)}
.rov-item:hover{background:var(--cream-2)}
.rov-link{flex:1 1 auto;min-width:0;display:flex;align-items:center;gap:.35rem;flex-wrap:wrap;text-decoration:none;color:var(--ink)}
.rov-title{font-weight:600}
.rov-kind{font-size:.68rem;flex-basis:100%}
@media(min-width:620px){.pgrid.rov-grid{grid-template-columns:minmax(0,1fr) minmax(0,3fr)}}
.rov-add{display:flex;gap:.4rem;margin-bottom:.6rem}
.rov-add input{flex:1 1 auto;min-width:0;border:1px solid var(--border);border-radius:var(--radius);padding:.35rem .5rem}
.rov-item.done .rov-title{text-decoration:line-through;color:var(--muted)}
.rov-by{font-size:.6rem;width:auto;min-width:1.4rem;padding:0 .25rem;height:1.4rem;display:inline-flex;align-items:center;justify-content:center}
.rov-foot{position:sticky;bottom:-1.3rem;z-index:6;background:var(--surface);border-top:1px solid var(--border);margin:1rem -1.5rem -1.3rem;padding:.8rem 1.5rem 1.3rem;display:flex;align-items:center;justify-content:space-between;gap:.6rem}
.rov-editor input[name=value]{width:100%;box-sizing:border-box;border:1px solid var(--border);border-radius:var(--radius);padding:.4rem .5rem}
.rovm{border:1px solid var(--border);border-radius:var(--radius);padding:.8rem .9rem;margin-bottom:.9rem;background:var(--surface)}
.rovm-h{display:flex;align-items:center;justify-content:space-between;gap:.5rem;margin-bottom:.6rem}
.rovm-kind{font-size:.72rem;text-transform:uppercase;letter-spacing:.04em;color:var(--subtle);font-weight:700}
.rovm-kind b{color:var(--gray)}
.rovm-close{background:none;border:none;color:var(--muted);cursor:pointer;font-size:.9rem;padding:0 .2rem}
.rovm-close:hover{color:var(--coral)}
.rovm-field{margin-top:.7rem}
.rovm-field input[name=value],.rovm-field textarea,.rovm-field select{width:100%;box-sizing:border-box;border:1px solid var(--border);border-radius:var(--radius);padding:.4rem .5rem;background:var(--surface);font:inherit}
.rovm-was{font-weight:400;text-transform:none;letter-spacing:0;color:var(--muted);font-style:italic}
.rovm-item{display:flex;align-items:center;gap:.5rem;padding:.25rem .4rem;border-radius:var(--radius);border:1px solid var(--border);margin-top:.3rem}
.rovm-iv{flex:1 1 auto;min-width:0}
.rovm-item.is-new{background:var(--green-tint);border-color:var(--green)}
.rovm-item.is-del{background:var(--cream-2);border-style:dashed}
.rovm-item.is-del .rovm-iv s{color:var(--muted)}
.rovm-foot{display:flex;align-items:center;gap:1rem;margin-top:.8rem;padding-top:.6rem;border-top:1px solid var(--border)}
.rov-addprop{margin-top:.4rem;padding-top:.8rem;border-top:1px dashed var(--border)}
.rov-addgrid{display:grid;gap:.8rem;grid-template-columns:1fr}
@media(min-width:560px){.rov-addgrid{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}}
.rov-addgrid select{width:100%;box-sizing:border-box;border:1px solid var(--border);border-radius:var(--radius);padding:.35rem .5rem;background:var(--cream-2);color:var(--muted)}
.is-soon{color:var(--muted)}
.rov-more{font-size:.7rem;color:var(--subtle);font-weight:700}
.rov-block{margin-top:.8rem}
.rov-field{display:flex;align-items:center;gap:.5rem;padding:.2rem 0;border-bottom:1px solid var(--border)}
.rov-fv{flex:1 1 auto;min-width:0}
.rov-addrow{display:flex;gap:.4rem;margin-top:.35rem}
.rov-addrow input{flex:1 1 auto;min-width:0;border:1px solid var(--border);border-radius:var(--radius);padding:.35rem .5rem}
.sec-issue{font-size:.78rem;border-radius:var(--radius);padding:.3rem .5rem;margin:.15rem 0 .4rem}
.sec-issue.let{background:var(--cream-2);color:var(--gray)}
.sec-issue.blok{background:var(--error-tint);color:var(--coral)}
.sec-block{margin-top:.9rem}
.sec-kop{font-size:.7rem;text-transform:uppercase;letter-spacing:.04em;color:var(--subtle);font-weight:700;margin-bottom:.3rem}
.rov-consent{margin-top:1rem}
.btn.ok:disabled,.btn:disabled{background:var(--cream-2);color:var(--muted);border-color:var(--border);cursor:not-allowed}
.kb-msg{margin-bottom:.55rem}
.kb-msg.jij{text-align:right}
.kb-who{font-size:.7rem;font-weight:700;color:var(--subtle)}
.kb-text{display:inline-block;text-align:left;background:var(--cream-2);border:1px solid var(--border);border-radius:var(--radius);padding:.4rem .55rem;margin-top:.15rem}
.kb-msg.note .kb-text{background:var(--error-tint);border-color:var(--coral);color:var(--coral)}
.kb-form textarea{width:100%;box-sizing:border-box;border:1px solid var(--border);border-radius:var(--radius);padding:.4rem .55rem}
.c2-wrap{margin-left:3.4rem}
.noo-rail{position:fixed;top:0;left:0;bottom:0;width:2.6rem;background:var(--green-dark);display:flex;flex-direction:column;align-items:center;justify-content:space-between;padding:.7rem 0;z-index:40}
.noo-rail-top{width:1.1rem;height:1.1rem;border-radius:50%;border:2px solid rgba(255,255,255,.45)}
.noo-cta{writing-mode:vertical-rl;transform:rotate(180deg);background:var(--coral);color:#fff;border:none;border-radius:var(--radius-pill);padding:.8rem .35rem;font-weight:800;letter-spacing:.05em;cursor:pointer;font-size:.78rem}
.noo-cta:hover{filter:brightness(1.06)}
.noo-ovl{position:fixed;inset:0;background:rgba(0,0,0,.22);z-index:70;display:flex;align-items:flex-end;justify-content:flex-end}
.noo-box{width:min(380px,94vw);max-height:80vh;margin:0 1.2rem 1.2rem 0;display:flex;flex-direction:column;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:0 14px 40px rgba(0,0,0,.25);overflow:hidden}
.noo-head{display:flex;align-items:center;justify-content:space-between;padding:.6rem .8rem;background:var(--green-tint);color:var(--green-dark);font-weight:800}
.noo-x{background:none;border:none;color:var(--green-dark);cursor:pointer;font-weight:700;font-size:.95rem}
.noo-win{display:flex;flex-direction:column;min-height:0}
.noo-sub{display:flex;align-items:center;justify-content:space-between;gap:.5rem;padding:.4rem .8rem;font-size:.72rem;color:var(--subtle);border-bottom:1px solid var(--border)}
.noo-ctx{display:flex;align-items:center;gap:.5rem;padding:.45rem .8rem;border-bottom:1px solid var(--border);font-size:.74rem}
.noo-feed{padding:.7rem .8rem;overflow-y:auto;max-height:46vh}
.noo-win .kb-form{padding:.7rem .8rem;border-top:1px solid var(--border)}
.kb-msg.noochie{text-align:left}
@media(max-width:760px){.c2-wrap{margin-left:2.8rem}}
.rov-delrole{margin-top:1rem;padding-top:.6rem;border-top:1px solid var(--border)}
.rov-delrole .flink{color:var(--coral)}
.rov-by{flex:0 0 auto}
.av.role{background:var(--green-dark);color:#fff}
.fkind{font-size:.64rem;text-transform:uppercase;letter-spacing:.04em;font-weight:700;border-radius:var(--radius-pill);padding:.03rem .45rem}
.fkind.upd{background:var(--green-tint);color:var(--green-dark)}
.fkind.cmt{background:var(--cream-2);color:var(--gray)}
.pgrid{display:grid;grid-template-columns:1fr;gap:1rem}
@media(min-width:620px){.pgrid{grid-template-columns:minmax(0,2fr) minmax(0,1fr)}}
.pmain{min-width:0}.pside{min-width:0}
.pcard-head{display:flex;align-items:flex-start;gap:.6rem;padding:0 2.6rem .8rem 0;border-bottom:1px solid var(--border);margin-bottom:1.1rem}
.pcard-head .titleform,.pcard-head .ptitle-ro{flex:1 1 auto;min-width:0}
.pcard-head-r{flex:0 0 auto;display:flex;align-items:center;gap:.5rem;padding-top:.2rem}
.menu-h{font-size:.62rem;text-transform:uppercase;letter-spacing:.04em;color:var(--subtle);font-weight:700;padding:.25rem .55rem .1rem}
.menu-sep{height:1px;background:var(--border);margin:.3rem 0}
.menuitem.on{font-weight:700;color:var(--green-dark);background:var(--green-tint)}
.pdetail-h{display:flex;align-items:flex-start;gap:.4rem;margin-bottom:.7rem}
.titleform{display:flex;gap:.4rem;align-items:center;flex:1;min-width:0}
.title-edit{flex:1;min-width:0;font-family:var(--font-display);font-size:1.5rem;font-weight:700;border:1px solid transparent;border-radius:var(--radius);padding:.15rem .35rem;background:none;color:var(--ink)}
.title-edit:hover{border-color:var(--border)}
.title-edit:focus{border-color:var(--green);background:var(--surface);outline:none}
.title-save{flex:0 0 auto;opacity:0;transition:opacity .12s}   /* alleen reveal-gedrag; styling uit .btn.ok.sm */
.titleform:focus-within .title-save{opacity:1}
.ptitle-ro{margin:.1rem 0;font-family:var(--font-display)}
.cardmenu{position:relative;flex:0 0 auto}
.cardmenu>summary{list-style:none;cursor:pointer;display:inline-flex;align-items:center;gap:.3rem;padding:0}
.cardmenu>summary::-webkit-details-marker{display:none}
.statustrigger .caret{color:var(--subtle);font-size:.7rem}
.statustrigger:hover .caret{color:var(--gray)}
.cardmenu-b{position:absolute;right:0;top:2rem;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);padding:.3rem;z-index:5;min-width:150px}
.menuitem{display:block;width:100%;text-align:left;border:none;background:none;padding:.4rem .55rem;border-radius:var(--radius);cursor:pointer;font-size:.85rem;color:var(--ink)}
.menuitem:hover{background:var(--cream-2)}
.menuitem.danger{color:var(--coral)}
.detailsbox{margin:0 0 1.1rem;border:1px solid var(--border);border-radius:var(--radius);padding:.7rem .8rem}
.detailsbox .psec-h{margin-bottom:.5rem}
.actioncards{display:flex;gap:.5rem;flex-wrap:wrap;margin:0 0 1.1rem}
.acard{display:inline-flex;align-items:center;gap:.4rem;background:var(--cream-2);border:1px solid var(--border);border-radius:var(--radius);padding:.4rem .75rem;font-size:.82rem;font-weight:600;color:var(--gray);cursor:pointer}
.acard:hover{border-color:var(--green);color:var(--green-dark)}
.acard svg{width:15px;height:15px}
.acard-off{opacity:.5;cursor:not-allowed}
.acard-off:hover{border-color:var(--border);color:var(--gray)}
.acard-d{position:relative;list-style:none;padding:0;margin:0}
.acard-d>summary{list-style:none}
.acard-d>summary::-webkit-details-marker{display:none}
.datepop{position:absolute;left:0;top:2.5rem;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);padding:.6rem;z-index:7}
.datepop input[type=date]{border:1px solid var(--border);border-radius:var(--radius);padding:.4rem .55rem;font-size:.88rem}
.checklist{margin:0 0 1.1rem}
.cl-head{display:flex;align-items:center;gap:.4rem;margin-bottom:.4rem}
.cl-head svg{width:15px;height:15px;color:var(--subtle)}
.cl-title{font-weight:700;font-size:.92rem}
.cl-del{margin-left:auto}
.dcol{display:grid;grid-template-columns:auto 1fr;gap:.35rem .8rem;align-content:start;min-width:0}
.dk{align-self:baseline;color:var(--subtle);font-size:.66rem;text-transform:uppercase;letter-spacing:.04em;font-weight:700;padding-top:.12rem}
.dv{min-width:0;font-size:.88rem}
.visform,.visform label{font-size:.85rem;margin:0;display:inline}
.fieldform{display:flex;gap:.4rem;align-items:center}
.fieldform select{flex:1 1 auto;min-width:0}
/* Bewerkbare Rol/Trekker in de zijbalk: label op een eigen regel (uitgelijnd) + dropdown op volle
   breedte eronder (label+veld spannen beide dcol-kolommen). .wide = bewust besluit, geen inline style. */
.dcol .dk.wide,.dcol .dv.wide{grid-column:1/-1}
.pside .fieldform{flex-wrap:wrap}
.pside .fieldform select{flex:1 1 100%;box-sizing:border-box;border:1px solid var(--border);border-radius:var(--radius);padding:.3rem .45rem;background:var(--surface)}
.descform textarea{width:100%;box-sizing:border-box;border:1px solid var(--border);border-radius:var(--radius);padding:.45rem .55rem;resize:vertical}
.desc-read{white-space:pre-wrap;line-height:1.4}
.descedit{margin-top:.3rem}
.descedit>summary{cursor:pointer;list-style:none;color:var(--subtle);font-size:.8rem;font-weight:500}
.descedit>summary::-webkit-details-marker{display:none}
.descedit>summary:hover{color:var(--ink)}
.att-pop{min-width:230px}
.att-lbl{display:block;font-size:.7rem;text-transform:uppercase;letter-spacing:.04em;color:var(--subtle);font-weight:700;margin-bottom:.25rem}
/* Leesbare artefact-body (note/policy/tool): donkerder dan .muted + wat regelhoogte. */
.att-body{color:var(--gray);line-height:1.5}
.att-pop input[type=text],.att-pop input[name=url],.att-pop input[name=title]{width:100%;box-sizing:border-box;border:1px solid var(--border);border-radius:var(--radius);padding:.35rem .5rem;font-size:.85rem}
.att-sep{height:1px;background:var(--border);margin:.6rem 0}
.card-del{margin-top:1.2rem;padding-top:.6rem;border-top:1px solid var(--border)}
.pdisc .psec{background:none;border:none;padding:0;margin:0}
.pdisc{background:var(--cream-2);border-radius:var(--radius);padding:.9rem;min-width:0}
.ment{color:var(--green-dark);font-weight:600}
.mention-pop{position:absolute;left:0;right:auto;top:100%;margin-top:2px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);z-index:8;min-width:180px;max-height:200px;overflow:auto}
.mention-it{display:block;width:100%;text-align:left;border:none;background:none;padding:.35rem .6rem;cursor:pointer;font-size:.85rem}
.mention-it:hover{background:var(--cream-2)}
.nt-list .nt-item{padding:.3rem 0;border-bottom:1px solid var(--border)}
.nt-dot{display:inline-block;width:.5rem;height:.5rem;border-radius:50%;background:var(--green);margin-right:.4rem;vertical-align:middle}
.ai-ask{margin:.1rem 0 1rem}
.comp-form{margin-bottom:1rem}
.comp-row{display:flex;align-items:center;gap:.5rem;margin-top:.4rem}
.comp-row .comp-attach{margin-right:auto}
/* Trello-stijl editor: omkaderde box met opmaak-toolbar boven een randloze textarea. */
.editor{width:100%;box-sizing:border-box;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface);overflow:visible}
.editor:focus-within{border-color:var(--green)}
.editor-tb{display:flex;align-items:center;gap:.1rem;padding:.25rem .35rem;border-bottom:1px solid var(--border);background:var(--cream-2);border-radius:var(--radius) var(--radius) 0 0}
.editor-tb .tb-b{background:none;border:none;cursor:pointer;color:var(--gray);border-radius:var(--radius);padding:.2rem .42rem;font-size:.85rem;line-height:1;display:inline-flex;align-items:center}
.editor-tb .tb-b:hover{background:var(--cream-3);color:var(--green-dark)}
.editor-tb .tb-b svg{width:14px;height:14px}
.tb-sep{width:1px;height:1.1rem;background:var(--border);margin:0 .25rem}
.tb-help{margin-left:auto}
.tb-help>summary{cursor:pointer;color:var(--subtle);padding:.2rem .45rem;font-weight:700;list-style:none}
.tb-help>summary::-webkit-details-marker{display:none}
.md-help{position:absolute;right:0;margin-top:.3rem;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:.45rem .6rem;font-size:.72rem;color:var(--gray);white-space:nowrap;box-shadow:0 6px 18px rgba(0,0,0,.12);z-index:5}
.editor textarea{border:none;width:100%;box-sizing:border-box;padding:.55rem .6rem;background:transparent;border-radius:0 0 var(--radius) var(--radius)}
.editor textarea:focus{outline:none}
/* Checklists */
.cl-head{display:flex;align-items:center;justify-content:space-between;gap:1rem}
.cl-bar{display:flex;align-items:center;gap:.6rem;margin-top:.5rem;font-size:.82rem}
.cl-filter{text-decoration:none;color:var(--gray);padding:.1rem .4rem;border-radius:var(--radius)}
.cl-filter.on{background:var(--green-tint);color:var(--green-dark);font-weight:700}
button.cl-filter{border:none;background:none;font:inherit;cursor:pointer}
.cl-group{margin:.2rem 0 1rem}
.cl-group h4{margin:.6rem 0 .3rem;font-size:.78rem;text-transform:uppercase;letter-spacing:.04em;color:var(--subtle)}
.cl-row{display:flex;align-items:center;justify-content:space-between;gap:.8rem;padding:.4rem 0;border-bottom:1px solid var(--border)}
.cl-main{flex:1 1 auto;min-width:0;display:flex;align-items:center;gap:.5rem;flex-wrap:wrap}
.cl-desc{font-weight:600}
.cl-act{flex:0 0 auto;display:flex;align-items:center;gap:.5rem}
.cl-spark{display:inline-flex;gap:1px;font-size:.62rem;letter-spacing:0}
.cl-spark i{font-style:normal;width:.95em;text-align:center}
.cl-spark i.ok{color:var(--green)}
.cl-spark i.no{color:var(--coral)}
.cl-checks{display:inline-flex;gap:.25rem}
.cl-check{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);cursor:pointer;width:1.7rem;height:1.7rem;line-height:1;font-size:.85rem;color:var(--muted)}
.cl-check.ok.on{background:var(--green);color:#fff;border-color:var(--green)}
.cl-check.no.on{background:var(--coral);color:#fff;border-color:var(--coral)}
.cl-attn{background:var(--error-tint)}     /* gemist checklist-item (rij-niveau, coral) */
.cl-todo{background:var(--yellow-light)}   /* te-doen checklist-item (rij-niveau, geel) */
.cl-add{display:inline-block}
.cl-add>summary{list-style:none;cursor:pointer}
.cl-add>summary::-webkit-details-marker{display:none}
.cl-addform{margin-top:.6rem;border:1px solid var(--border);border-radius:var(--radius);padding:.7rem .8rem;background:var(--surface);max-width:30rem}
.cl-addform input[name=description],.cl-addform select{width:100%;box-sizing:border-box;border:1px solid var(--border);border-radius:var(--radius);padding:.35rem .5rem;margin-bottom:.2rem}
.cl-gate{display:flex;gap:.4rem;align-items:flex-start;font-size:.8rem;color:var(--gray);margin:.5rem 0 .7rem}
/* Metrics */
.kpi-grid{display:grid;gap:.7rem;grid-template-columns:1fr}
@media(min-width:560px){.kpi-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
.kpi-card{border:1px solid var(--border);border-radius:var(--radius);padding:.6rem .7rem;background:var(--surface)}
.kpi-h{display:flex;align-items:center;justify-content:space-between;gap:.5rem}
.kpi-name{font-weight:700;font-size:.85rem}
.kpi-body{display:flex;align-items:flex-end;justify-content:space-between;gap:.6rem;margin:.35rem 0 .2rem}
.kpi-val{font-family:var(--font-display);font-size:1.6rem;line-height:1}
.kpi-unit{font-size:.8rem;color:var(--subtle);font-family:inherit}
.spark{display:block}
.linechart{display:block;margin-top:.3rem}
.kpi-prov{font-size:.72rem;margin-top:.1rem}
.kpi-foot{display:flex;align-items:center;justify-content:space-between;gap:.5rem;margin-top:.3rem}
.kpi-add{display:flex;gap:.3rem}
.kpi-add input{width:5rem;border:1px solid var(--border);border-radius:var(--radius);padding:.2rem .4rem}
.kpi-link a{text-decoration:none;color:var(--green-dark);display:inline-flex;align-items:center;gap:.35rem}
.kpi-link svg{width:14px;height:14px}
.m-add,.m-sel{display:inline-block}
.m-add>summary,.m-sel>summary{list-style:none;cursor:pointer}
.m-add>summary::-webkit-details-marker,.m-sel>summary::-webkit-details-marker{display:none}
.m-addgrid{display:grid;gap:.8rem;grid-template-columns:1fr;margin-top:.6rem}
@media(min-width:560px){.m-addgrid{grid-template-columns:repeat(2,minmax(0,1fr))}}
.m-addform{border:1px solid var(--border);border-radius:var(--radius);padding:.6rem .7rem;background:var(--surface)}
.m-addform input,.m-addform select{width:100%;box-sizing:border-box;border:1px solid var(--border);border-radius:var(--radius);padding:.3rem .45rem;margin-bottom:.25rem}
.m-selrow{display:flex;align-items:center;justify-content:space-between;gap:.6rem;padding:.25rem 0;border-bottom:1px solid var(--border);font-size:.84rem}
.flink.on{color:var(--green-dark);font-weight:700}
/* Mini-Looker tegels */
.tile-grid{display:grid;gap:.7rem;grid-template-columns:1fr}
@media(min-width:560px){.tile-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
.tile{border:1px solid var(--border);border-radius:var(--radius);padding:.6rem .7rem;background:var(--surface);min-width:0}
.tile-h{display:flex;align-items:center;justify-content:space-between;gap:.5rem;margin-bottom:.4rem}
.tile-t{font-size:.74rem;color:var(--subtle);font-weight:700;text-transform:uppercase;letter-spacing:.03em}
.tile-trend{display:flex;align-items:flex-end;justify-content:space-between;gap:.5rem}
.kpi-val.sm{font-size:1.15rem}
.tile-h-r{display:inline-flex;align-items:center;gap:.3rem}
.tile-rm{display:inline}
.tile-info{position:relative;display:inline-block}
.tile-info>summary{list-style:none;cursor:pointer;color:var(--subtle);display:inline-flex;background:none;border:none;box-shadow:none;padding:0;opacity:.5}
.tile-info>summary:hover,.tile-info[open]>summary{opacity:1}
.tile-info>summary::-webkit-details-marker{display:none}
.tile-info>summary svg{width:13px;height:13px}
.gr-pop{position:absolute;right:0;bottom:calc(100% + 5px);z-index:6;width:15rem;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:0 8px 24px rgba(0,0,0,.14);padding:.5rem .6rem;font-size:.74rem}
.gr-row{display:flex;gap:.5rem;padding:.12rem 0;border-bottom:1px solid var(--border)}
.gr-k{flex:0 0 4.5rem;color:var(--subtle);font-weight:700}
.tile-goal{font-size:.72rem;margin-top:.3rem}
.tile-warn{color:var(--coral);margin-left:.3rem}
.bars{display:flex;flex-direction:column;gap:.25rem}
.bar-row{display:grid;grid-template-columns:minmax(0,7rem) 1fr auto;align-items:center;gap:.5rem;font-size:.78rem}
.bar-l{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bar-t{display:block;height:.55rem;background:var(--cream-2);border-radius:var(--radius-pill);overflow:hidden}
.bar-f{display:block;height:100%;background:var(--green)}
.bar-v{color:var(--subtle);font-variant-numeric:tabular-nums}
.mtab{width:100%;border-collapse:collapse;font-size:.8rem}
.mtab td{padding:.2rem .3rem;border-bottom:1px solid var(--border)}
.mtab td.num{text-align:right;font-variant-numeric:tabular-nums}
.goal{display:flex;flex-direction:column;gap:.35rem}
.kpidata-row{display:flex;align-items:center;gap:.6rem;padding:.35rem 0;border-bottom:1px solid var(--border);flex-wrap:wrap}
.kpidata-n{flex:1 1 auto;min-width:0;font-weight:600}
.kpidata-v{font-variant-numeric:tabular-nums;color:var(--green-dark);font-weight:700}
/* Werkoverleg: stap-navigatie (hergebruikt rov-grid + rov-foot) */
.wo-nav{display:flex;flex-direction:column;gap:.2rem}
.wo-step{display:flex;align-items:center;gap:.5rem;text-decoration:none;color:var(--gray);padding:.4rem .5rem;border-radius:var(--radius);font-size:.86rem}
.wo-step:hover{background:var(--cream-2)}
.wo-step.on{background:var(--green-tint);color:var(--green-dark);font-weight:700}
.wo-num{display:inline-flex;align-items:center;justify-content:center;width:1.4rem;height:1.4rem;border-radius:50%;background:var(--cream-2);color:var(--gray);font-size:.72rem;font-weight:700;flex:0 0 auto}
.wo-step.on .wo-num{background:var(--green);color:#fff}
.wo-step.done{color:var(--green-dark)}
.wo-step.done .wo-num{background:var(--green);color:#fff}
.wo-sec{font-size:.8rem;margin-top:.4rem}
.wo-sp-add{margin:0}
.wo-substeps{padding:.1rem 0 .3rem 1.6rem}
.wo-substeps .rov-item{padding:.2rem .3rem}
.wo-substeps .rov-title{font-weight:400}
.wo-back-bar{margin:0 0 .8rem}
/* Werkoverleg 3-koloms layout (Brok 2): links stappen ~250px, midden content, rechts video. */
.wo-head{display:flex;align-items:center;gap:.6rem;margin:0 0 .9rem}
.wo-head h2{margin:0;font-size:1.05rem}
.wo-timer{margin-left:auto;font-variant-numeric:tabular-nums;font-size:.78rem;color:var(--gray);background:var(--cream-2);border:1px solid var(--border);border-radius:1rem;padding:.15rem .6rem}
.wo-leave{font-size:.8rem;color:var(--gray);text-decoration:none;border:1px solid var(--border);border-radius:var(--radius);padding:.3rem .55rem}
.wo-leave:hover{background:var(--coral-tint,#ffeeea);border-color:var(--coral,#e2574a);color:var(--coral,#e2574a)}
.wo-grid{display:grid;grid-template-columns:1fr;gap:1rem}
@media(min-width:760px){.wo-grid{grid-template-columns:250px minmax(0,1fr) 230px}}
.wo-left{min-width:0}
.wo-mid{min-width:0;display:flex;flex-direction:column}
.wo-right{background:var(--cream-2);border-radius:var(--radius);padding:.7rem;min-width:0}
.wo-right-h{font-size:.72rem;text-transform:uppercase;letter-spacing:.04em;color:var(--gray);margin:.1rem .1rem .6rem}
.wo-video-empty{border:1px dashed var(--border);border-radius:var(--radius);padding:.9rem;text-align:center;color:var(--gray);font-size:.78rem}
.wo-next{display:flex;justify-content:flex-end;padding-top:1rem;margin-top:auto}
.wo-close-wrap{display:flex;flex-direction:column;align-items:center;gap:.4rem;padding-top:1.4rem}
.wo-close-btn{padding:.7rem 2rem;font-size:1rem}
/* LiveKit-tiles (Brok 3): mens = camera + naam in #wo-video; AI = presence-tile eronder. */
.wo-video{display:flex;flex-direction:column;gap:.5rem}
.wo-ai-list{display:flex;flex-direction:column;gap:.5rem;margin-top:.5rem}
.wo-tile{border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;background:#fff}
.wo-cam{width:100%;aspect-ratio:4/3;object-fit:cover;display:block;background:#2c2a25}
.wo-cam-off{display:grid;place-items:center;color:#9a9382;font-size:1.4rem}
.wo-tile-lbl{display:flex;align-items:center;gap:.35rem;padding:.3rem .5rem;font-size:.78rem}
.wo-tile.ai{border-color:var(--purple,#7a5bd1);background:var(--purple-tint,#eee9fa)}
.wo-tile.ai .wo-tile-lbl{color:var(--purple,#7a5bd1);font-weight:700}
.wo-ai-face{background:var(--purple-tint,#eee9fa);color:var(--purple,#7a5bd1);font-size:1.6rem}
.wo-ai-badge{margin-left:auto;font-size:.62rem;background:var(--purple,#7a5bd1);color:#fff;border-radius:1rem;padding:.05rem .4rem}
.wo-back-bar.wo-back-foot{margin:1rem 0 0;padding-top:.8rem;border-top:1px solid var(--border)}
.wo-mems:focus{outline:none}
.wo-mem{display:flex;align-items:center;gap:.6rem;padding:.4rem .5rem;border-radius:var(--radius);border:1px solid transparent;border-bottom:1px solid var(--border)}
.wo-mem.sel{background:var(--cream-2);border-color:var(--border)}
.wo-mem.absent .wo-mem-n{color:var(--muted);text-decoration:line-through}
.wo-mem-n{flex:1 1 auto;min-width:0;font-weight:600}
.wo-leave{font-size:.74rem}
.wo-who{display:flex;flex-wrap:wrap;gap:.3rem;align-items:center;margin-bottom:.6rem}
.cl-rep{display:inline-flex;gap:.25rem;align-items:center}
.row-danger{margin-left:.7rem;padding-left:.7rem;border-left:1px solid var(--border);opacity:.6}
.row-danger:hover{opacity:1}
.wo-kpitabs{display:flex;flex-wrap:wrap;gap:.3rem;margin-bottom:.6rem}
.wo-focus .mtab{margin-top:.5rem}
.wo-outcomes{margin-top:.9rem;display:flex;flex-direction:column;gap:.5rem}
/* .wo-ocd krijgt zijn kader nu van .box-details (zie werkoverleg-template) */
.wo-ocd>summary{cursor:pointer;list-style:none;padding:.4rem .6rem;font-weight:600;font-size:.86rem}
.wo-ocd>summary::-webkit-details-marker{display:none}
.wo-ocd>summary:hover{background:var(--cream-2)}
.wo-ocd[open]>summary{border-bottom:1px solid var(--border)}
.wo-ocd .wo-oc{padding:.5rem .6rem}
.wo-scale{display:inline-flex;flex-wrap:wrap;gap:.2rem}
.wo-sc{width:1.7rem;height:1.7rem;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface);cursor:pointer;font-size:.78rem;color:var(--gray)}
.wo-sc.on{background:var(--green);color:#fff;border-color:var(--green)}
.wo-sc.prev{background:var(--green-tint);color:var(--green-dark);border-color:var(--green-tint)}
.wo-avg{font-weight:700;color:var(--green-dark)}
.wo-oc{display:flex;gap:.4rem;align-items:center;flex-wrap:wrap}
.wo-oc input,.wo-oc textarea,.wo-oc select{flex:1 1 12rem;min-width:0;border:1px solid var(--border);border-radius:var(--radius);padding:.3rem .45rem}
.wo-oc button{flex:0 0 auto}
.wo-sum{display:flex;flex-direction:column;gap:.2rem}
.wo-sumrow{display:flex;justify-content:space-between;gap:1rem;padding:.3rem 0;border-bottom:1px solid var(--border)}
.cfetti{position:fixed;top:-14px;width:9px;height:9px;border-radius:2px;z-index:9999;pointer-events:none;animation:cfall 2.2s linear forwards}
@keyframes cfall{to{transform:translateY(110vh) rotate(600deg);opacity:.5}}
.c2-toast{position:fixed;left:50%;bottom:2.2rem;transform:translateX(-50%) translateY(8px);z-index:9998;background:var(--green-dark);color:#fff;padding:.45rem .9rem;border-radius:var(--radius-pill);font-size:.82rem;font-weight:700;box-shadow:0 6px 20px rgba(0,0,0,.2);opacity:0;transition:opacity .15s,transform .15s;pointer-events:none}
.c2-toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
.pdetail-h h2{margin:.1rem 0 .5rem;font-family:var(--font-display);font-size:1.35rem;line-height:1.2}
.psec{margin:0 0 1.15rem}
.psec-h{display:flex;align-items:center;gap:.4rem;color:var(--subtle);font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;font-weight:700;margin-bottom:.45rem}
.psec-h svg{width:14px;height:14px;opacity:.75;flex:0 0 auto}
.pside .psec{background:var(--cream-2);border:1px solid var(--border);border-radius:var(--radius);padding:.65rem .75rem;margin-bottom:.8rem}
/* structuur-kantlijn blijft in beeld tijdens scrollen door de wall (scope 1) */
@media(min-width:620px){.pside.psticky{position:sticky;top:.8rem;align-self:start}}
.wall-head{display:flex;align-items:baseline;justify-content:space-between;gap:.5rem;margin-bottom:.6rem}
.wall-head h2{font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;color:var(--subtle);margin:0;font-weight:700}
.wall-scroll{max-height:62vh;overflow-y:auto}
.opdracht-add{margin:0 0 .85rem}
.c2-main.pdetail{max-width:1120px}
.dangling-warn{margin-bottom:.3rem}
.smeta{margin:0}
.smeta dt{font-size:.62rem;text-transform:uppercase;letter-spacing:.04em;color:var(--subtle);font-weight:700;margin-top:.55rem}
.smeta dt:first-child{margin-top:0}
.smeta dd{margin:.1rem 0 0}
.ckadd{display:flex;gap:.4rem;margin-top:.5rem}
.ckadd input{flex:1 1 auto;min-width:0}
.ckadd .btn{flex:0 0 auto;white-space:nowrap}
.composer{margin-top:.6rem}
.editbox{margin:0 0 .5rem}
.editbox>summary{cursor:pointer;font-weight:700;font-size:.85rem;color:var(--green-dark)}
.actrow{display:flex;gap:.6rem;align-items:center;flex-wrap:wrap}
.sugg{background:#F4F1FB;border:1px solid #E0D7F5;border-radius:var(--radius);padding:.5rem .7rem;margin:.5rem 0}
.sugg-h{font-weight:700;color:#5b3fa6;font-size:.82rem;margin-bottom:.3rem}
.bagadd{padding:0;margin-top:.8rem}
.bagadd>summary{cursor:pointer;color:var(--subtle);font-size:.82rem;list-style:none}
.bagadd>summary:hover{color:#5b3fa6}
.frow{display:flex;align-items:flex-start;gap:.5rem;padding:.4rem 0;border-bottom:1px solid var(--border)}
.ffocus{padding:0;margin:0}
.ffocus>summary{list-style:none;cursor:pointer}
.ffocus>summary::-webkit-details-marker{display:none}
.ovl{position:fixed;inset:0;background:rgba(27,27,27,.45);z-index:50;display:flex;align-items:flex-start;justify-content:center}
.ovl-box{background:var(--surface);max-width:980px;width:95%;margin:4vh auto;border-radius:12px;padding:1.3rem 1.5rem;max-height:88vh;overflow:auto;position:relative;box-shadow:0 12px 48px rgba(27,27,27,.35)}
.ovl-x{position:absolute;top:.5rem;right:.7rem;border:none;background:none;font-size:1.2rem;cursor:pointer;color:var(--gray)}
.vswitch{display:inline-flex;gap:.2rem;align-items:center}
.vbtn{font-size:12px;font-weight:600;padding:.3rem .85rem;border:1px solid var(--border);border-radius:var(--radius-pill);color:var(--gray);text-decoration:none}
.vbtn.on{background:var(--green);color:#fff;border-color:var(--green)}
.ck-prog{display:flex;align-items:center;gap:.6rem;margin:.2rem 0 .6rem}
.ck-prog .pbar{flex:1 1 auto;width:auto}
.ck-prog .muted{flex:0 0 auto;font-size:.74rem;min-width:2.5rem;text-align:right}
.ck-list{}.ck-item{display:flex;align-items:center;gap:.5rem;padding:.25rem .3rem;border:none;border-radius:var(--radius)}
.ck-item:hover{background:var(--cream-2)}
.ck-box{width:18px;height:18px;border:1.5px solid var(--subtle);border-radius:4px;background:var(--surface);cursor:pointer;font-size:.72rem;line-height:1;color:#fff;flex:0 0 auto}
.ck-box.on{background:var(--green);border-color:var(--green)}
.ck-item .dellink{margin-left:auto;opacity:0}
.ck-item:hover .dellink{opacity:1}
.ck-done{text-decoration:line-through;color:var(--muted)}
/* checklist-item-states (scope 1): ✓ done · uitvoerbaar ⚠ payload-onvolledig ○ geen-skill.
   ⚠ (coral) en ○ (grijs/sand) MOETEN visueel verschillen — ze vragen om verschillende actie. */
.ck-item{align-items:flex-start}
.ck-item .ck-box{margin-top:.1rem}
.ck-txt{flex:1 1 auto;min-width:0}
.ck-meta{display:block;margin-top:.15rem;font-size:.7rem;line-height:1.5}
.ck-skill{font-family:ui-monospace,Menlo,monospace;font-size:.66rem;color:var(--green-dark);background:var(--green-tint);padding:.02rem .35rem;border-radius:5px}
.ck-payload{font-family:ui-monospace,Menlo,monospace;font-size:.64rem;color:var(--subtle)}
.ck-warn{font-size:.68rem;color:var(--coral);background:var(--error-tint);padding:.02rem .35rem;border-radius:5px}
.ck-noskill{font-size:.68rem;color:var(--gray);background:var(--sand);padding:.02rem .35rem;border-radius:5px}
.ck-box.b-warn{border-color:var(--coral)}
.ck-box.b-noskill{border-color:var(--subtle);border-style:dashed}
.ck-item form{display:contents}
.attcard{display:flex;align-items:center;gap:.55rem;background:var(--cream-2);border:1px solid var(--border);border-radius:var(--radius);padding:.45rem .6rem;margin-bottom:.4rem}
.att-ic{flex:0 0 auto;color:var(--gray);display:inline-flex}
.att-ic svg{width:16px;height:16px}
.att-name{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:600;text-decoration:none;color:var(--ink)}
.att-name:hover{text-decoration:underline}
.att-x{flex:0 0 auto}
.ghost-off{opacity:.55;cursor:not-allowed}
.btn.grey{color:var(--muted);border-style:dashed;cursor:not-allowed}
@media(max-width:760px){.c2-wrap{flex-direction:column}.c2-rail{max-width:none;flex-basis:auto}}
/* ── Design-systeem-bouwstenen (metrics-UI visuele pariteit) ────────────────────────────────
   Herbruikbare interactieve chip/pill + wrap-rij, en een schuif-toggle. Referentie: kpi-wizard-v2.html
   (chips) en de dashboard-tab van het eerdere prototype (toggle). Nog geen scherm gekoppeld. */
.chip-wrap{display:flex;flex-wrap:wrap;gap:.5rem}
.chip-opt{display:inline-block;padding:.4rem .8rem;border-radius:var(--radius-pill);border:1px solid var(--border);background:var(--cream);color:var(--ink);font:inherit;font-size:13px;line-height:1.2;cursor:pointer;text-decoration:none}
.chip-opt:hover{border-color:var(--muted)}
.chip-opt.on{background:var(--ink);color:var(--cream);border-color:var(--ink)}
.switch{display:inline-block;width:34px;height:19px;flex:none;border:none;padding:0;border-radius:var(--radius-pill);background:var(--border);position:relative;cursor:pointer;vertical-align:middle;transition:background .15s}
.switch::after{content:'';position:absolute;top:2px;left:2px;width:15px;height:15px;border-radius:50%;background:var(--surface);transition:left .15s}
.switch.on{background:var(--green)}
.switch.on::after{left:17px}
.switch-field{display:inline-flex;align-items:center;gap:.5rem;font-size:12.5px;color:var(--muted)}
"""

