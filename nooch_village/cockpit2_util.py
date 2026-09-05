"""Pure HTML-helpers zonder _Stores-afhankelijkheid (brok 1 van de cockpit2-split)."""
from __future__ import annotations
import hashlib as _hashlib
import os as _os
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

# Sleutels zijn logica (tab-parameters in de URL) en blijven; alleen de getoonde labels zijn Engels.
_TAB_LABEL = {
    "overview": "Overview", "strategy": "Strategy", "roles": "Roles", "members": "Members",
    "policies": "Policies", "notes": "Notes", "tools": "Tools", "projects": "Projects",
    "checklists": "Checklists", "metrics": "Metrics",
    "rollen": "Roles", "projecten": "Projects", "context": "Context", "checklist": "Checklist",
}

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _name(rec) -> str:
    return getattr(rec.definition, "name", "") or rec.id


def _rol_labels(kandidaten, alle=None) -> dict:
    """rol-id → label voor een KEUZELIJST: de naam, met de cirkel erachter waar dat nodig is.

    Op prod heten drie rollen 'Circle Lead', drie 'Secretary', drie 'Facilitator' en twee
    'Circle Rep' — samen elf exemplaren onder vier namen. In een dropdown staan die dan als
    identieke regels onder elkaar en is er niets te kiezen; je kunt alleen gokken.

    Drie regels, en ze horen bij elkaar:

    1. **Alleen waar het botst.** Er wordt geteld binnen DEZE lijst, niet in de hele organisatie.
       Staat er maar één Facilitator op het scherm, dan is 'Facilitator' precies goed — een
       cirkelnaam erachter is ruis waar niets te verwarren valt.
    2. **De cirkel is de onderscheider**, want dat is wat de rollen daadwerkelijk uit elkaar houdt:
       de Circle Lead ván Nooch is een andere rol dan die ván Noochville.
    3. **Blijft het dan nog dubbel, dan wint eerlijkheid van netheid.** Twee rollen met dezelfde
       naam in dezelfde cirkel krijgen hun id erbij. Lelijk, maar een lijst die belooft te
       onderscheiden en dat niet doet is erger: dan denk je dat je kiest.
    """
    kandidaten = list(kandidaten or [])
    index = {getattr(r, "id", ""): r for r in (alle if alle is not None else kandidaten)}

    def _cirkel(rec) -> str:
        ouder = getattr(rec, "parent", "") or ""
        p = index.get(ouder)
        return _name(p) if p is not None else (ouder.split("__")[-1] if ouder else "")

    per_naam: dict = {}
    for r in kandidaten:
        per_naam.setdefault(_name(r), []).append(r)

    labels: dict = {}
    for naam, groep in per_naam.items():
        if len(groep) == 1:
            labels[groep[0].id] = naam
            continue
        voorlopig = {r.id: (f"{naam} ({_cirkel(r)})" if _cirkel(r) else naam) for r in groep}
        botsingen = {lab for lab in voorlopig.values()
                     if list(voorlopig.values()).count(lab) > 1}
        for rid, lab in voorlopig.items():
            labels[rid] = f"{lab} [{rid}]" if lab in botsingen else lab
    return labels


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
        return "today"
    if d < 31:
        return f"{d}d old"
    if d < 365:
        return f"{d//30}mo old"
    return f"{d//365}y old"


def _fmt_due(iso: str) -> str:
    """ISO-datum 'YYYY-MM-DD' → '25 jun 2026'."""
    if not iso:
        return ""
    try:
        y, m, d = iso.split("-")
        return f"{int(d)} {_MONTHS[int(m) - 1]} {y}"
    except Exception:
        return iso


def _created_full(ts) -> str:
    """Relatieve leeftijd + absolute datum, bijv. 'vandaag · 27 jun 2026' of '1 week oud · 20 jun 2026'."""
    if not ts:
        return "—"
    import datetime
    d = datetime.datetime.fromtimestamp(ts)
    return f"{_age(ts)} · {d.day} {_MONTHS[d.month - 1]} {d.year}"


def _bron_html(url: str) -> str:
    """Bron-bewijs: een echte klikbare link bij http(s); een intern pad zonder route tonen we als
    tekst (geen dode 404-link) tot de kennisbank-koppeling live is."""
    u = (url or "").strip()
    if u.startswith("http://") or u.startswith("https://"):
        return f"<a href='{_e(u)}' target='_blank' rel='noopener'>evidence ↗</a>"
    return f"<span class='muted' title='link not live yet'>{_e(u)} (not live yet)</span>"


def _stamp(ts) -> str:
    """Datum + tijd, bijv. '27 jun 2026, 14:32'."""
    if not ts:
        return ""
    import datetime
    d = datetime.datetime.fromtimestamp(ts)
    return f"{d.day} {_MONTHS[d.month - 1]} {d.year}, {d.hour:02d}:{d.minute:02d}"


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


def _md_doc(text: str) -> str:
    """Vollere markdown-render voor het einddocument (leesbaar i.p.v. rauw). Kent kop-niveaus
    (# .. ###### -> h3..h6), **vet**/*cursief*/~~doorhalen~~, geordende (1.) en ongeordende (- )
    lijsten, [tekst](url)-links (alleen http(s)), alinea's en regelafbrekingen. Omringende
    codefences (```), waar de LLM het document soms in wikkelt, worden gestript. XSS-veilig: de
    tekst wordt eerst ge-escaped (`_e`), pas daarna draaien de opmaak-regexes. Losstaand van `_md`
    (de lichte comment-formatter blijft ongemoeid)."""
    import re
    s = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if s.startswith("```"):                                   # LLM-codefence om het hele document -> strippen
        lines = s.split("\n")[1:]
        while lines and not lines[-1].strip():
            lines.pop()
        if lines and lines[-1].strip().startswith("```"):
            lines.pop()
        s = "\n".join(lines)
    s = _e(s)                                                 # eerst escapen (fail-closed tegen XSS)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)   # vet vóór cursief
    s = re.sub(r"~~(.+?)~~", r"<del>\1</del>", s)
    s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)

    def _link(m):
        url = m.group(2)
        if url.startswith("http://") or url.startswith("https://"):
            return f"<a href='{url}' target='_blank' rel='noopener'>{m.group(1)}</a>"
        return m.group(0)

    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _link, s)
    out, mode = [], None                                      # mode: None | 'ul' | 'ol'
    for ln in s.split("\n"):
        t = ln.strip()
        h = re.match(r"(#{1,6})\s+(.*)", t)
        if h:
            if mode:
                out.append("</ul>" if mode == "ul" else "</ol>")
                mode = None
            tag = {1: "h3", 2: "h4", 3: "h5"}.get(len(h.group(1)), "h6")
            out.append(f"<{tag}>{h.group(2)}</{tag}>")
            continue
        o = re.match(r"\d+\.\s+(.*)", t)
        if o:
            if mode != "ol":
                if mode == "ul":
                    out.append("</ul>")
                out.append("<ol class='fbul'>")
                mode = "ol"
            out.append(f"<li>{o.group(1)}</li>")
            continue
        if t.startswith("- "):
            if mode != "ul":
                if mode == "ol":
                    out.append("</ol>")
                out.append("<ul class='fbul'>")
                mode = "ul"
            out.append(f"<li>{t[2:]}</li>")
            continue
        if mode:
            out.append("</ul>" if mode == "ul" else "</ol>")
            mode = None
        if t:
            out.append(f"<p>{ln}</p>")
    if mode:
        out.append("</ul>" if mode == "ul" else "</ol>")
    return "".join(out)


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


# ── Inline bewerken: één component, twee gebruikers ──────────────────────────────────────────
# Het bewerkveld neemt de PLEK in van wat het bewerkt; er komt geen tweede blok ernaast. Dat was
# eerst twee keer los gebouwd: de comment-edit toggelde `[data-fb]`/`[data-fe]` binnen `.fentry`,
# en "Edit before confirming" op /rapport opende een <details> met een tweede textarea ónder het
# gerenderde concept. Twee implementaties van dezelfde interactie lopen uiteen zodra er één
# verandert — en de gebruiker leert het patroon twee keer.
#
# De wrapper draagt zijn eigen klasse (`.editor-inline`), zodat de JS niet afhangt van de gastheer:
# `.fentry` op de wall, de conceptkaart op /rapport, en wat er hierna bij komt.
_INLINE_TOON_JS = ("var w=this.closest('.editor-inline');"
                   "w.querySelector('[data-toon]').hidden=true;"
                   "var e=w.querySelector('[data-bewerk]');e.hidden=false;"
                   "var t=e.querySelector('textarea');if(t){t.focus();"
                   "t.setSelectionRange(t.value.length,t.value.length);}")
_INLINE_TERUG_JS = ("var w=this.closest('.editor-inline');"
                    "w.querySelector('[data-bewerk]').hidden=true;"
                    "w.querySelector('[data-toon]').hidden=false;")


def inline_edit(getoond: str, formulier_inhoud: str, *, sleutel: str,
                opslaan: str, opslaan_label: str = "Save", verborgen: str = "",
                toon_cls: str = "") -> str:
    """Het getoonde blok plus een bewerkformulier dat er OP dezelfde plek voor in de plaats komt.

    `getoond`          de gerenderde weergave (bubbel, conceptverslag, …)
    `formulier_inhoud` het invoerveld, meestal `md_editor(...)`
    `sleutel`          uniek per blok op de pagina — twee blokken die dezelfde sleutel delen
                       zouden elkaars knoppen aanspreken
    `opslaan`          de dispatch-actie van de opslaan-knop
    `verborgen`        de hidden inputs (csrf, pid, next, …)

    Geeft alleen het PAAR terug; de knop die het opent komt uit `inline_edit_knop`, want die staat
    bij de andere acties en niet in de bubbel.

    DE GASTHEER MARKEERT DE GRENS, niet deze helper: zet `editor-inline` op het element dat zowel
    het paar ALS de knop omvat (`.fentry` op de wall, de conceptkaart op /rapport). Een wrapper hier
    zou strakker om het paar zitten dan om de knop, en dan vindt `closest()` hem niet — precies wat
    er misging toen ik het wél zo probeerde."""
    return (f"<div data-toon='{_e(sleutel)}'"
            f"{f' class={chr(39)}{toon_cls}{chr(39)}' if toon_cls else ''}>{getoond}</div>"
            f"<form method='post' action='/action' class='pf editor-inline-f' "
            f"data-bewerk='{_e(sleutel)}' hidden>{verborgen}{formulier_inhoud}"
            f"<div class='qadd-row'>"
            f"<button class='btn ok sm' type='submit' name='action' value='{_e(opslaan)}'>"
            f"{_e(opslaan_label)}</button>"
            f"<button class='flink' type='button' onclick=\"{_INLINE_TERUG_JS}\">Cancel</button>"
            f"</div></form>")


def inline_edit_knop(label: str = "Edit") -> str:
    """De knop die het bewerkveld op zijn plek zet. Hoort binnen dezelfde `.editor-inline`."""
    return (f"<button class='flink' type='button' onclick=\"{_INLINE_TOON_JS}\">"
            f"{_e(label)}</button>")


def md_editor(name: str, value: str = "", rows: int = 6,
              placeholder: str = "Body (markdown)…", help: bool = False) -> str:
    """De GEDEELDE opmaak-editor (markdown → veilige `_md`-weergave): `.editor`-kaart met mini-toolbar
    (vet/cursief/doorhalen/lijst/kop via wrapSel) boven een textarea. De link-knop is bewust weg; de
    renderer ondersteunt [tekst](url) nog wél (handmatig typen of plakken). Zelfvoorzienend — draagt de
    guarded wrapSel-JS zelf mee, zodat de editor op ELKE pagina werkt (ook zonder _modal_html) en een
    view 'm niet kan vergeten. `value` wordt hier ge-escaped; callers geven de RUWE waarde door.
    `help=True` toont een inklapbaar opmaak-spiekbriefje (bestaande `.tb-help`/`.md-help`-klassen)."""
    hlp = ("<details class='emoji-pick tb-help'><summary title='Formatting help'>?</summary>"
           "<div class='md-help'>**bold** · *italic* · ~~strikethrough~~ · # heading · - list · [text](url)</div>"
           "</details>") if help else ""
    return (f"<div class='editor'><div class='editor-tb'>"
            f"<button type='button' class='tb-b' onclick=\"wrapSel(this,'**','**')\" title='Bold'><b>B</b></button>"
            f"<button type='button' class='tb-b' onclick=\"wrapSel(this,'*','*')\" title='Italic'><i>I</i></button>"
            f"<button type='button' class='tb-b' onclick=\"wrapSel(this,'~~','~~')\" title='Strikethrough'><s>S</s></button>"
            f"<span class='tb-sep'></span>"
            f"<button type='button' class='tb-b' onclick=\"wrapSel(this,'- ','')\" title='List'>•</button>"
            f"<button type='button' class='tb-b' onclick=\"wrapSel(this,'## ','')\" title='Heading'>H</button>"
            f"{hlp}</div>"
            f"<textarea name='{_e(name)}' rows='{rows}' placeholder='{_e(placeholder)}'>{_e(value)}</textarea>"
            f"</div>{_WRAPSEL_JS}")


def _ic(path: str) -> str:
    return (f"<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' "
            f"stroke-linecap='round' stroke-linejoin='round'>{path}</svg>")


def _parse_multipart(body: bytes, boundary: str):
    """Minimale multipart/form-data parser → (velden{str:str}, bestanden{str:(filename,bytes)}).

    Byte-exact: verwijder alleen de multipart-FRAMING rond de content — de leidende CRLF ná de boundary en
    EXACT één afsluitende CRLF vóór de volgende boundary — nooit méér. Een eerdere `part.strip(b"\\r\\n")`
    strípte álle trailing \\r/\\n, waardoor de laatste byte(s) van elk binair bestand (bv. een PDF die op
    `\\n` eindigt) verdwenen → corruptie van elke geüploade file."""
    fields, files = {}, {}
    delim = ("--" + boundary).encode()
    for part in body.split(delim):
        if part.startswith(b"\r\n"):
            part = part[2:]                       # leidende CRLF ná de boundary weg
        if not part or part.startswith(b"--") or b"\r\n\r\n" not in part:
            continue                              # preamble, sluit-boundary (--), of geen headers
        head, _, content = part.partition(b"\r\n\r\n")
        if content.endswith(b"\r\n"):
            content = content[:-2]                # EXACT de afsluitende framing-CRLF weg (niet de content-bytes)
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

# ── Design-systeem-CSS (component-laag) ─────────────────────────────────────
# De CSS is een écht bestand (static/nooch.css): bewerkbaar met CSS-tooling,
# gecachet door de browser (via /static/nooch.css?v=<inhoud-hash>), één bron.
# _EXTRA_CSS blijft als symbool bestaan voor modal-fragmenten (_frag) en tests.
_EXTRA_CSS_PATH = _os.path.join(_os.path.dirname(__file__), "static", "nooch.css")
with open(_EXTRA_CSS_PATH, encoding="utf-8") as _css_f:
    _EXTRA_CSS = _css_f.read()
# Cache-buster op inhoud (niet op proces-start): zelfde CSS → zelfde URL → cache-hit,
# nieuwe CSS → nieuwe URL → verse download. Views zetten _DS_LINK vooraan in de body.
_DS_VERSION = _hashlib.md5(_EXTRA_CSS.encode("utf-8")).hexdigest()[:10]
_DS_LINK = f'<link rel="stylesheet" href="/static/nooch.css?v={_DS_VERSION}">'


# ── De top-nav: ÉÉN gedeelde balk (was inline gedupliceerd over ~18 views) ──────
# IA-fase 1: rol-gecentreerd. De nav is geslankt tot drie ankers — Metrics (catalogus
# + bronnen samengevoegd, landt op het dashboard), Kennisbank ("Wat Nooch weet": waar
# beloftes/inzichten/signalen samenkomen) en Deelnemers. Home/inbox/beloftes/inzichten/
# signalen/accountabilities zijn uit de nav; hun routes blijven bestaan (geen dode links),
# hun inhoud verhuist in latere fasen. "Reference, don't copy": één bron voor de nav.
# Kennisbank woont sinds de IA-opruiming onder de Librarian-rol (Tools-tab), niet in de top-nav.
_NAV_ITEMS = (
    ("/metrics2", "Metrics"),
    ("/admin", "People"),
)


def _nav(context: str = "GlassFrog (PoC)") -> str:
    """De gedeelde top-header: het Nooch-logo links en een globale zoekbalk ernaast (zoekt door
    rollen, projecten en de kennisbank). Elke pagina roept dit aan, dus logo + zoek staan overal.
    De meta-links (Metrics, Deelnemers, build) zijn naar de footer verhuisd (zie `_footer`), zodat
    de bovenrand rustig blijft. `context` blijft in de signatuur voor compat (niet meer getoond)."""
    return (
        "<div class='c2-topbar'>"
        "<a class='c2-logo' href='/' title='home'><img src='/static/nooch-logo.png' alt='nooch' "
        "onerror=\"this.onerror=null;this.src='/static/nooch-logo.svg'\"></a>"
        "<form class='c2-search' action='/search' method='get' role='search' autocomplete='off'>"
        "<input id='gs-input' type='search' name='q' placeholder='Search people, roles, accountabilities…' "
        "autocomplete='off' aria-label='global search'>"
        "<div id='gs-drop' class='gs-drop' hidden></div>"
        "</form>"
        # Persoonlijke begroeting rechts; _send vult de naam van de ingelogde persoon in (leeg = onzichtbaar).
        "<span class='c2-greet' id='c2-greet'></span>"
        "</div>"
        + _GS_LIVE_JS)


# Live-zoek: terwijl je typt haalt dit de dropdown-resultaten op (fragment via /search?frag=1), debounced.
# Klik buiten de balk sluit de dropdown; Enter opent de volledige /search-pagina (het form submit).
_GS_LIVE_JS = """<script>(function(){
 var box=document.getElementById('gs-input'), drop=document.getElementById('gs-drop'), t;
 if(!box||!drop||box.dataset.wired)return; box.dataset.wired='1';
 function hide(){drop.hidden=true;} function show(){if(drop.innerHTML.trim())drop.hidden=false;}
 function run(){
   var q=box.value.trim();
   if(q.length<2){drop.innerHTML='';hide();return;}
   fetch('/search?frag=1&q='+encodeURIComponent(q),{credentials:'same-origin'})
     .then(function(r){return r.text();})
     .then(function(h){drop.innerHTML=h; show();}).catch(function(){});
 }
 box.addEventListener('input',function(){clearTimeout(t);t=setTimeout(run,180);});
 box.addEventListener('focus',show);
 document.addEventListener('click',function(e){if(!e.target.closest('.c2-search'))hide();});
})();</script>"""


def _footer() -> str:
    """De gedeelde footer met de cockpit-meta en de admin-links (Metrics, Deelnemers). Wordt globaal
    door `_send` vóór </body> geïnjecteerd, zodat hij op elke pagina staat, ook de tool-pagina's."""
    links = " · ".join(f"<a href='{href}'>{_e(label)}</a>" for href, label in _NAV_ITEMS)
    return (f"<footer class='c2-foot'>cockpit 2 · {_e('GlassFrog (PoC)')} · build {_BUILD} · "
            f"{links}</footer>")


