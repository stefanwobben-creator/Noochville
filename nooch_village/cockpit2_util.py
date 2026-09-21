"""Pure HTML-helpers zonder _Stores-afhankelijkheid (brok 1 van de cockpit2-split)."""
from __future__ import annotations
import hashlib as _hashlib
import os as _os
import re
import time as _time
from html.parser import HTMLParser as _HTMLParser

from nooch_village.web_base import _e

_BUILD = _time.strftime("%H:%M")   # proces-starttijd: zichtbaar in de balk


# ── Tijd in de tijdzone van de lezer ─────────────────────────────────────────
#
# AANLEIDING (6 september 2026). De server draait op UTC, de mensen die het cockpit lezen zitten in
# CEST. Alles op het scherm liep dus twee uur achter op de klok aan de muur, zonder dat er iets
# fout stond: de tijdstempels kloppen, ze werden alleen in de verkeerde zone getoond.
#
# WAAROM NIET DE SERVERKLOK VERZETTEN. Dat is één commando en het lijkt gratis, maar dan verhuizen
# ook de logs, de periode-sleutels (`checklists.period_key`) en de dagreeksen van de collector mee —
# en die zijn met opzet UTC, want een dagreeks moet niet twee keer 02:30 hebben in oktober. De
# OPSLAG is hier al goed: alles staat als epoch (`time.time()`), dus tijdzone-loos. Alleen de
# WEERGAVE moest kiezen, en die koos stilzwijgend de servertijd.
#
# De zone is een setting en geen constante: het dorp draait op één plek, maar dat hoeft niet zo te
# blijven, en een hardcoded 'Europe/Amsterdam' is precies het soort aanname dat je pas ontdekt als
# iemand verhuist. Fail-soft: een onbekende zone valt terug op UTC met een logregel, want een
# verkeerd tijdstip is minder erg dan een pagina die niet laadt.

_TZ_DEFAULT = "Europe/Amsterdam"


def _zone(settings=None):
    naam = str((settings or {}).get("display_timezone") or
               _os.getenv("display_timezone") or _TZ_DEFAULT).strip()
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(naam)
    except Exception:                                  # noqa: BLE001 — onbekende zone mag niets breken
        import datetime as _dt
        return _dt.timezone.utc


def lokaal(ts, vorm: str = "%Y-%m-%d %H:%M", settings=None, leeg: str = "—") -> str:
    """Een epoch-tijdstempel in de zone van de lezer. Lege/kapotte invoer → `leeg`, nooit een crash.

    Gebruik dit overal waar een TIJDSTIP op het scherm komt. Voor een DATUM zonder tijd maakt de
    zone zelden verschil, maar rond middernacht wel — dus ook daar deze helper, niet
    `datetime.fromtimestamp` rechtstreeks.
    """
    if ts in (None, "", 0):
        return leeg
    try:
        import datetime as _dt
        return _dt.datetime.fromtimestamp(float(ts), _zone(settings)).strftime(vorm)
    except (TypeError, ValueError, OSError, OverflowError):
        return leeg

# De rol waarop de Backlog Builder (Notes-vervanger) leeft. Eén bron voor gate + view + coupling.
WEBSITE_DEVELOPER_ROLE = "mother_earth__nooch__website_developer"

# Fase 7 (prototype v15): policies/notes/tools zijn één Wiki-tab geworden — ze stonden altijd al
# in één AttachmentStore, alleen met een ander `kind`. Projects verhuisde naar een eigen scherm
# (/projects) maar blijft hier als GEFILTERDE weergave van deze node. Goals kwam erbij: dat stond
# als losse route in de footer-nav, terwijl het over deze cirkel gaat.
_CIRCLE_TABS = ["overview", "roles", "members", "goals", "wiki", "projects",
                "checklists", "metrics"]
_ROLE_TABS = ["overview", "wiki", "projects", "checklists", "metrics"]
# Persoon/AI-role-filler-view: een read-only aggregatie-lens over de rollen die iemand vervult,
# geen nieuwe autoriteitslaag. Spiegelt de rol-view-chrome via _tabbar(base="/person").
_PERSON_TABS = ["rollen", "projecten", "context", "metrics", "checklist"]

# Sleutels zijn logica (tab-parameters in de URL) en blijven; alleen de getoonde labels zijn Engels.
_TAB_LABEL = {
    "overview": "Overview", "strategy": "Strategy", "roles": "Roles", "members": "Members",
    "wiki": "Wiki", "goals": "Goals", "projects": "Projects",
    "checklists": "Checklists", "metrics": "Metrics",
    # Oude sleutels blijven in de labeltabel staan: bestaande links (bookmarks, /node?tab=notes in
    # documentatie) mogen niet als rauwe sleutel op het scherm eindigen.
    "policies": "Policies", "notes": "Notes", "tools": "Tools",
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


def _stamp(ts, settings=None) -> str:
    """Datum + tijd, bijv. '27 jun 2026, 14:32'. In de zone van de LEZER, niet van de server.

    Dit is de tijd onder elke wall-bubbel — de meest gelezen tijd in het hele cockpit. Hij stond op
    servertijd (UTC) terwijl iedereen die hem leest in CEST zit; zie de notitie bij `lokaal`."""
    if not ts:
        return ""
    import datetime
    try:
        d = datetime.datetime.fromtimestamp(float(ts), _zone(settings))
    except (TypeError, ValueError, OSError, OverflowError):
        return ""
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


# ── De weg terug: opgemaakte HTML → de markdown-bron ─────────────────────────────────────────
#
# WAAROM DIT OP DE SERVER STAAT. De wiki-editor laat je in de tekst zelf typen (contenteditable),
# dus wat de browser terugstuurt is HTML. Ergens moet daar weer markdown van gemaakt worden, want
# de OPSLAG blijft markdown — er wordt nooit HTML bewaard. Die omzetting hoort hier, naast `_md`,
# en niet in JS: dan zou er een tweede opmaak-kenner bestaan naast deze, en die twee lopen uiteen
# zodra er één regel bijkomt. Dezelfde afweging die de voorbeeldknop al maakte (`/md-preview`
# haalt zijn weergave bij `_md` zelf op, niet bij een parser in de browser).
#
# Bijvangst die zwaarder weegt dan hij lijkt: een omzetter in Python is met pytest te bewijzen op
# de 105 echte pagina's. Een omzetter in JS niet — er is in deze stack geen JS-testrunner.
#
# FAIL-CLOSED OP EEN GESLOTEN WHITELIST. Een browser maakt bij Enter en bij plakken zijn eigen
# HTML (`<div>`, `<p>`, `<span style=…>`, hele Word-fragmenten). Alles wat hieronder niet met naam
# staat, wordt zijn eigen TEKST — nooit ruwe HTML die straks in de opslag belandt.
#
# WAT NIET TERUGKOMT, EN DAT IS GEEN BUG. `_md` gooit zelf al dingen weg: hij strippt de
# inspringing van een lijst- of kopregel, normaliseert CRLF, en haalt de laatste `<br>` weg. `_md`
# is dus niet omkeerbaar op eindwitruimte, en deze functie doet niet alsof. De eigenschap die WEL
# hard is, en die `tests/test_md_bron.py` op elke echte pagina aantoont:
#
#     _md(_md_naar_bron(_md(bron))) == _md(bron)
#
# oftewel: door de editor heen en weer halen verandert niets aan wat je op het scherm ziet.

#: tag → (voor, na) in de bron. Bewust dezelfde tekens die `_md` produceert, geen synoniemen.
# `strike` STOND HIER NIET, EN DAT KOSTTE EEN LIVE BUG (gevonden bij de klik-doorloop van
# 21 september 2026). Doorhalen wérkte op het scherm, maar was na opslaan en herladen platte tekst:
# Chrome's `execCommand("strikeThrough")` levert `<strike>`, niet `<del>` en niet `<s>`. Die tag
# viel buiten de whitelist en werd dus — precies zoals afgesproken — zijn eigen tekst. Fail-closed
# deed hier exact wat het moest, alleen op een tag die er wél in hoorde.
#
# DE ECHTE FOUT ZAT IN DE TEST, niet in de code. `test_de_werkbalk_gebruikt_alleen_tags_die_de
# _omzetter_kent` voerde `<del>x</del>` in als "wat de knop oplevert" — een AANNAME over de
# browser, opgeschreven als meting. Hij test nu alle vormen die een browser werkelijk produceert.
_BRON_INLINE = {"strong": ("**", "**"), "b": ("**", "**"),
                "em": ("*", "*"), "i": ("*", "*"),
                "del": ("~~", "~~"), "s": ("~~", "~~"), "strike": ("~~", "~~")}

#: tags die een regel afsluiten. `div` en `p` staan erbij omdat een contenteditable ze zelf maakt.
_BRON_BLOK = ("h4", "li", "div", "p")


class _BronParser(_HTMLParser):
    """Loopt de opgemaakte HTML af en schrijft de markdown-bron terug.

    Geen DOM-boom: `_md` produceert een platte reeks, dus een lineaire lezer met één stapel voor
    de open inline-tags is genoeg — en hij kan niet omvallen op HTML die niet goed genest is,
    want die krijgt hij van een browser."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.uit: list[str] = []
        self._ref = ""            # de oorspronkelijke [[verwijzing]], als die er was
        self._href = ""
        self._linktekst: list[str] = []
        #: kwam het laatste regeleinde van een BLOK-grens (`</li>`, `</h4>`, `</p>`) of van een
        #: `<br>`? Dat verschil beslist of het eindregeleinde erbij hoort; zie `_md_naar_bron`.
        self._blok_einde = False

    # ── hulpjes ──────────────────────────────────────────────────────────────
    def _schrijf(self, tekst: str) -> None:
        (self._linktekst if self._href or self._ref else self.uit).append(tekst)
        if tekst:
            self._blok_einde = False

    def _nieuwe_regel(self) -> None:
        """Eén regeleinde, nooit twee achter elkaar door een blok-tag. Een browser sluit een
        alinea met `</p>` én begint de volgende met `<p>`; dat zijn twee signalen voor één
        overgang, en wie ze allebei telt laat de tekst bij elke bewerking verder uit elkaar staan."""
        if self.uit and not self.uit[-1].endswith("\n"):
            self.uit.append("\n")
        self._blok_einde = True

    # ── de drie haken van HTMLParser ─────────────────────────────────────────
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "br":
            self.uit.append("\n")
            self._blok_einde = False          # een <br> IS de tekst, geen scheiding eromheen
        elif tag in _BRON_INLINE:
            self._schrijf(_BRON_INLINE[tag][0])
        elif tag == "h4":
            self._nieuwe_regel(); self.uit.append("## ")
        elif tag == "li":
            self._nieuwe_regel(); self.uit.append("- "); self._in_li = True
        elif tag in ("a", "span"):
            # Een wiki-verwijzing draagt zijn ORIGINELE tekst mee (`data-ref`), want op het scherm
            # staat de opgeloste titel en die is niet hetzelfde. Zonder dat attribuut zou
            # `[[compliance-beleid]]` terugkomen als de titel van de pagina waar hij heen wees.
            self._ref = d.get("data-ref") or ""
            self._href = "" if self._ref else (d.get("href") or "")
            self._linktekst = []
        elif tag in _BRON_BLOK:
            self._nieuwe_regel()

    def handle_endtag(self, tag):
        if tag in _BRON_INLINE:
            self._schrijf(_BRON_INLINE[tag][1])
        elif tag in ("a", "span"):
            label = "".join(self._linktekst)
            if self._ref:
                self.uit.append(f"[[{self._ref}]]")
            elif self._href.startswith(("http://", "https://")):
                self.uit.append(f"[{label}]({self._href})")
            else:
                # DEZELFDE POORT ALS `_md`, EEN STAP EERDER. `_md` weigert al een link zonder
                # http(s)-schema, dus een `javascript:`-url zou toch als platte tekst renderen —
                # maar hij zou dan wél in de OPSLAG staan, klaar voor de dag waarop iemand een
                # tweede renderer schrijft die minder streng is. Hier houdt alleen de tekst over.
                self.uit.append(label)
            self._ref = self._href = ""
            self._linktekst = []
            self._blok_einde = False
        elif tag in ("h4", "li", "div", "p"):
            self._nieuwe_regel()

    def handle_data(self, data):
        self._schrijf(data)


def _md_naar_bron(html: str) -> str:
    """De omgekeerde van `_md`: opgemaakte HTML terug naar de markdown-bron.

    Alles buiten de whitelist hierboven degradeert naar platte tekst. Geeft nooit HTML terug."""
    parser = _BronParser()
    parser.feed(html or "")
    parser.close()
    uit = "".join(parser.uit).replace("\r\n", "\n").replace("\r", "\n")
    # Regeleindes die alleen uit blok-grenzen komen mogen zich niet opstapelen. Drie of meer is
    # nooit iets anders dan twee.
    while "\n\n\n" in uit:
        uit = uit.replace("\n\n\n", "\n\n")
    # Aan het BEGIN hetzelfde verhaal als aan het eind: een `<br>` vooraan is de lege regel die
    # de schrijver typte. Hij wordt dus niet weggepoetst — `_md` zet hem straks gewoon terug.
    # HET EINDREGELEINDE IS NIET ALTIJD HETZELFDE DING, en dat is de subtielste regel hier.
    # Sluit de tekst af met een BLOK (`</li>`, `</h4>`), dan is het laatste regeleinde de grens
    # van dat blok en hoort het niet in de bron: `- a` rendert naar `<ul><li>a</li></ul>` en moet
    # als `- a` terugkomen, niet als `- a\n`. Komt het van een `<br>`, dan is het de lege regel die
    # de schrijver zelf typte, en die hoort te blijven — anders verspringt de weergave bij het
    # eerste het beste opslaan.
    return uit.rstrip("\n") if parser._blok_einde else uit


def _md_doc(text: str) -> str:
    """Vollere markdown-render voor het einddocument (leesbaar i.p.v. rauw). Kent kop-niveaus
    (# .. ###### -> h3..h6), **vet**/*cursief*/~~doorhalen~~, geordende (1.) en ongeordende (- )
    lijsten, [tekst](url)-links (alleen http(s)), alinea's en regelafbrekingen. Omringende
    codefences (```), waar de LLM het document soms in wikkelt, worden gestript; een codefence
    BINNEN het document (een opdracht om te plakken, een commando) wordt een `<pre>`-blok waarin
    niets wordt opgemaakt — sinds Noochie's memo (scope 42a) die een Claude Code-opdracht kan
    dragen. XSS-veilig: de tekst wordt eerst ge-escaped (`_e`), pas daarna draaien de
    opmaak-regexes; een codeblok wordt apart ge-escaped. Losstaand van `_md` (de lichte
    comment-formatter blijft ongemoeid)."""
    import re
    s = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    fences = sum(1 for ln in s.split("\n") if ln.strip().startswith("```"))
    if s.startswith("```") and fences <= 2:                   # LLM-codefence om het hele document -> strippen
        lines = s.split("\n")[1:]
        while lines and not lines[-1].strip():
            lines.pop()
        if lines and lines[-1].strip().startswith("```"):
            lines.pop()
        s = "\n".join(lines)
    # Codeblokken eerst uit de tekst halen: wat erin staat is letterlijk (geen vet, geen lijst,
    # geen link), dus het mag niet door de regexes hieronder. Ze komen aan het eind terug als <pre>.
    blokken: list[str] = []

    def _vang(m):
        blokken.append(m.group(1))
        return f"\n\x00CODE{len(blokken) - 1}\x00\n"

    s = re.sub(r"```[^\n]*\n(.*?)\n?```", _vang, s, flags=re.S)
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
    html = "".join(out)
    for i, code in enumerate(blokken):
        html = html.replace(f"<p>\x00CODE{i}\x00</p>", f"<pre>{_e(code)}</pre>")
    return html


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
    # VOORBEELD-KNOP (fase 10, punt 4b). De werkbalk toonde `**vet**` als `**vet**` tot je opsloeg,
    # en op een lange wiki-pagina bewerk je dan een hele pagina in broncode. De knop haalt de
    # weergave op bij `/md-preview`, dus bij `_md` zelf — niet bij een tweede parser in JS, want die
    # twee lopen uiteen zodra er één opmaakregel bij komt.
    return (f"<div class='editor' data-md-preview><div class='editor-tb'>"
            f"<button type='button' class='tb-b' onclick=\"wrapSel(this,'**','**')\" title='Bold'><b>B</b></button>"
            f"<button type='button' class='tb-b' onclick=\"wrapSel(this,'*','*')\" title='Italic'><i>I</i></button>"
            f"<button type='button' class='tb-b' onclick=\"wrapSel(this,'~~','~~')\" title='Strikethrough'><s>S</s></button>"
            f"<span class='tb-sep'></span>"
            f"<button type='button' class='tb-b' onclick=\"wrapSel(this,'- ','')\" title='List'>•</button>"
            f"<button type='button' class='tb-b' onclick=\"wrapSel(this,'## ','')\" title='Heading'>H</button>"
            f"<span class='tb-sep'></span>"
            f"<button type='button' class='tb-b' data-md-toggle title='Preview'>👁</button>"
            f"{hlp}</div>"
            f"<textarea name='{_e(name)}' rows='{rows}' placeholder='{_e(placeholder)}'>{_e(value)}</textarea>"
            f"<div class='editor-prev att-body' hidden></div>"
            f"</div>{_WRAPSEL_JS}")


# ── De werkbalk voor bewerken IN de tekst (21 september 2026) ────────────────────────────────
#
# Zusje van `md_editor` hierboven, en hij woont hier om dezelfde reden: de knoppentaal van een
# opmaak-werkbalk (`editor-tb`, `tb-b`, `tb-sep`) hoort op ÉÉN plek te staan. Het verschil zit
# in wat de knop aanstuurt — `md_editor` schrijft tekens in een textarea (`wrapSel`), deze roept
# `document.execCommand` aan op een `contenteditable`. Dezelfde vorm, andere motor.

#: De werkbalk-knoppen: (commando, argument, label, titel). `formatBlock` maakt een kop, de rest
#: is een inline-opmaak die `_md` kent. Geen link-knop — `_md` ondersteunt `[tekst](url)` wel,
#: maar een linkdialoog is een scherm op zich en hoort bij een eigen scope.
_OPMAAK_KNOPPEN = (("bold", "", "<b>B</b>", "Bold"),
               ("italic", "", "<i>I</i>", "Italic"),
               ("strikeThrough", "", "<s>S</s>", "Strikethrough"),
               ("", "", "", ""),                       # scheiding
               ("insertUnorderedList", "", "&bull;", "List"),
               # DE PUNTHAKEN ZIJN VERPLICHT. `formatBlock` met "h4" doet in Chrome en Safari
               # niets — geen fout, geen effect; alleen met "<h4>" maakt hij een kop. Dat is de
               # tweede helft van dezelfde bug als bij `strike`: een aanname over de browser.
               ("formatBlock", "<h4>", "H", "Heading"))


def opmaak_werkbalk() -> str:
    """Zelfde atomen als de bestaande markdown-werkbalk (`.editor-tb`, `.tb-b`, `.tb-sep`), zodat
    er geen tweede knoppentaal ontstaat voor dezelfde handeling."""
    knoppen = []
    for cmd, arg, label, titel in _OPMAAK_KNOPPEN:
        if not cmd:
            knoppen.append("<span class='tb-sep'></span>")
            continue
        extra = f" data-wiki-arg='{_e(arg)}'" if arg else ""
        knoppen.append(f"<button type='button' class='tb-b' data-wiki-cmd='{_e(cmd)}'{extra} "
                       f"title='{_e(titel)}'>{label}</button>")
    return f"<div class='editor-tb wiki-tb' id='wiki-tb' hidden>{''.join(knoppen)}</div>"


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

# ── Nooch UI v1 (fase 9) ───────────────────────────────────────────────────────
# Een TWEEDE stylesheet, bewust niet vermengd met nooch.css. Alles erin staat onder `.nu`, dus een
# pagina zonder die klasse merkt er niets van — zie de kop van static/nooch-ui.css voor waarom het
# geen tweede globale `:root` is (vier botsende tokennamen, waarvan `--border` 147 randen sloopt).
with open(_os.path.join(_os.path.dirname(__file__), "static", "nooch-ui.css"),
          encoding="utf-8") as _nu_f:
    _NU_CSS = _nu_f.read()
_NU_VERSION = _hashlib.md5(_NU_CSS.encode("utf-8")).hexdigest()[:10]
_NU_LINK = (f'<link rel="stylesheet" href="/static/nooch-ui.css?v={_NU_VERSION}">'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
            'family=Archivo:wght@400;500;600;700&display=swap">')


# ── De zijbalk: ÉÉN gedeelde navigatie (fase 7, 19 september 2026) ─────────────
# Hiervóór was de navigatie over drie plekken verdeeld: een topbar met logo+zoek, een footer met
# drie links (Goals · Metrics · People) en een organisatieboom in de RECHTERrail die `_send` op elke
# pagina injecteerde. Het prototype (v15) zet die drie bij elkaar in één vaste zijbalk links, en dat
# is wat hier gebeurt — alleen de structuur, niet de vormgeving; die komt in fase 9 over alle
# schermen tegelijk.
#
# Messages stond hier in fase 7 BEWUST niet, omdat het scherm toen nog geen data had. Sinds fase 8
# is de channel-laag er (project-, cirkel- en DM-kanalen), dus staat hij er wel — met een echt
# scherm erachter en niet als doorverwijzing.
#
# Goals en Metrics zijn GEEN zijbalk-items meer maar tabs op de cirkel, zoals in het prototype.
# Hun routes (`/goals`, `/metrics2`) blijven bestaan — geen dode links, dezelfde regel als bij de
# vorige nav-slanking.
#: (href, label, paneel). `paneel` leeg = gewone paginasprong; anders klapt er een lijst open
#: NAAST de balk in plaats van dat je het scherm verlaat. PR, ME en CI zijn lijsten waar je iets
#: uit kiest; WI en AD niet — daar val je binnen op een scherm, en dan is een tussenlijst een
#: extra klik zonder winst. (IN stond hier ook, tot bleek dat die knop een functie aanriep die
#: niet bestond; zie #531.)
_SIDE_ITEMS = (
    ("/projects", "Projects", "pr"),
    # MESSAGES IS GEEN PANEEL (eis Stefan, 21 september 2026). Hij was het wel, en het leverde een
    # halve Messages op: het paneel toonde de kanalenlijst terwijl je nog op je vorige scherm
    # stond, dus het gesprek was nergens en de oude pagina keek er langs. Klikken op een kanaal
    # bracht je alsnog op `/messages`, maar de tussenstand las als kapot.
    #
    # De diepere reden dat het niet past: Messages is als ENIGE van de vijf een scherm dat zelf al
    # uit lijst + detail bestaat. Een paneel kan daar alleen de lijst van tonen, en die lijst is
    # een kopie van wat de pagina zelf al heeft. Bij Projects, Circle en Organization voegt het
    # paneel iets toe dat de pagina niet heeft; hier haalde het iets weg.
    ("/messages", "Messages", ""),
    ("/wiki",     "Wiki",     ""),
)

#: Werkoverleg en Roloverleg zijn GEEN kanalen (correctie Stefan, 21 september 2026). Het zijn twee
#: bestaande schermen, en ze horen dus als directe knop op de balk — geen paneel, geen lijst ervoor.
#: Ze staan onder een scheiding, los van de PR/ME/WI/CI/AD-groep, omdat ze een ander soort ding zijn.
#:
#: ZE DRAGEN EEN CIRKEL-ID, EN DAAROM ZIJN HET PLACEHOLDERS. De eerste versie linkte kaal naar
#: `/werkoverleg` en `/roloverleg2`. Beide routes bestaan, maar ze zijn niet dorpsbreed: ze tonen
#: HET OVERLEG VAN EEN CIRKEL en beginnen met `st.records.get(circle_id)`. Zonder `?circle=` is dat
#: None en kreeg je "No circle." respectievelijk "Unknown." — één gedeelde oorzaak, geen twee
#: ontbrekende routes. `_nav()` heeft geen stores en kan die cirkel dus niet zelf opzoeken;
#: `_send` vult hem in, net als bij `_SIDE_CIRCLE` hieronder.
_SIDE_OVERLEG = "<!--c2-overleg-->"


def overleg_items(circle_id: str, *, werk_open: bool = False) -> str:
    """De twee overleg-knoppen, mét de cirkel waar ze over gaan. Leeg zonder cirkel: een knop naar
    een overleg dat niet bestaat is erger dan geen knop.

    DRAAIT ER EEN WERKOVERLEG, DAN WORDT DE KNOP EEN UITNODIGING. Wie later binnenkomt kan nu
    alleen weten dat er iets loopt door erop te klikken; dat is precies de informatie die op de
    knop hoort te staan.

    TWEE DRAGERS, geen kleur alleen: het rondje ÉN de tekst veranderen ("Join meeting"). Een
    pulserend groen stipje dat het enige verschil is, is onzichtbaar in zwart-wit en voor wie
    groen niet ziet. Groen en niet rood, bewust: rood leest hier als "opname/stop", groen als
    "kom erbij".

    ALLEEN WERKOVERLEG deze ronde. Roloverleg heeft geen open/dicht-staat — zijn agenda is een
    lijst governance-voorstellen, en "er loopt nu een roloverleg" bestaat daar niet als feit. Die
    staat erbij bouwen is echt werk en een eigen klus (besluit Stefan, 21 september 2026)."""
    if not circle_id:
        return ""
    uit = []
    for h, label in (("/werkoverleg", "Werk&shy;overleg"),
                     ("/roloverleg2", "Rol&shy;overleg")):
        live = werk_open and h == "/werkoverleg"
        cls = "c2-overleg" + (" c2-overleg--live" if live else "")
        stip = "<span class='c2-live' aria-hidden='true'></span>" if live else ""
        tekst = "Join meeting" if live else label
        uit.append(f"<a class='{cls}' href='{h}?circle={_e(circle_id)}'>{stip}{tekst}</a>")
    return "".join(uit)

#: `_send` vult deze twee plekken per pagina in (het is per-sessie/per-records-informatie, en
#: `_nav()` heeft geen stores). Zelfde patroon als de begroeting.
_SIDE_CIRCLE = "<!--c2-circle-->"
# `_SIDE_ORG` STOND HIER. De organisatieboom werd met elke pagina meegerenderd in de zijbalk; hij
# is op 21 september 2026 een nav-paneel geworden (`/nav-paneel?p=org`) en wordt dus opgehaald als
# je erop klikt. Eén uitklap-mechanisme in de balk in plaats van twee.


def _monogram(label: str) -> str:
    """Twee letters als icoon-vorm. Geen icoonset erbij halen voor vijf items, en twee letters
    blijven leesbaar in zwart-wit — dezelfde afweging als bij de statusvormen."""
    return (label.strip()[:2] or "?").upper()


def _side_item(href: str, label: str, paneel: str = "") -> str:
    """Eén navigatie-item: het monogram voor de rail, het woord voor de volle zijbalk.

    BEIDE STAAN ALTIJD IN DE DOM; CSS kiest welke je ziet. Het alternatief — twee varianten
    renderen — geeft twee plekken waar een nieuw item vergeten kan worden, en een schermlezer die
    in de rail alleen nog "PR" hoort.

    MET `paneel` WORDT HET EEN KNOP en geen link. Dat is geen opmaakdetail: een element dat een
    paneel open- en dichtklapt is een knop, draagt `aria-expanded`, en hoort niet in de tab-volgorde
    te beloven dat je ergens heen gaat. Zonder JS blijft de knop stil staan — daarom draagt hij óók
    de href, zodat de val-terug een echte navigatie is en geen dood element."""
    if not paneel:
        return (f"<a href='{href}' title='{_e(label)}'>"
                f"<span class='c2-mono' aria-hidden='true'>{_e(_monogram(label))}</span>"
                f"<span class='c2-lbl'>{_e(label)}</span></a>")
    return (f"<a href='{href}' title='{_e(label)}' data-nav-paneel='{_e(paneel)}' "
            f"aria-expanded='false' aria-controls='c2-paneel'>"
            f"<span class='c2-mono' aria-hidden='true'>{_e(_monogram(label))}</span>"
            f"<span class='c2-lbl'>{_e(label)}</span></a>")


def _nav(context: str = "GlassFrog (PoC)") -> str:
    """De gedeelde zijbalk: logo, zoek, wie je bent, de navigatie en de organisatieboom.

    Elke pagina roept dit aan, dus de navigatie staat overal — één bron, zoals de topbar die hij
    vervangt. `context` blijft in de signatuur voor compat (niet getoond); ~40 aanroepers geven
    hem niet mee en hoeven daarom niet aangeraakt te worden.

    HIER STOND EEN INBOX-KNOP, en hij deed niets. Het `onclick` riep `ibxToggle()` aan — een
    functie die nergens in de repo gedefinieerd is — en de docstring beloofde een lade
    (`render_inbox_chrome`) die net zo min bestaat. Klikken gaf een JS-fout in de console en verder
    niets. Weg op 21 september 2026, samen met de 72 stylesheet-regels die hem aankleedden.
    Wat de functie zou moeten doen, doet Messages.

    `rail=True` STOND HIER: op /messages klapte de balk in tot 64px, want drie kolommen
    (navigatie, kanalen, gesprek) passen niet. Die uitzondering is op 21 september 2026 vervallen
    (eis Stefan) — een balk die op één scherm anders breed is dan op alle andere, is een tweede
    navigatiemodel, precies wat fase 7 opruimde. De ruimte komt uit de kanalenlijst, niet uit de
    navigatie. De parameter had daarna nog één aanroeper en nu geen, dus hij is weg; de
    `c2-side--rail`-CSS ging in dezelfde beurt mee."""
    return (
        # De hamburger staat BUITEN de zijbalk, anders verdwijnt de knop samen met wat hij opent.
        "<button type='button' class='c2-burger' onclick='navToggle()' "
        "aria-label='Menu' aria-expanded='false'>\u2630</button>"
        "<aside class='c2-side'>"
        "<a class='c2-logo' href='/' title='home'><img src='/static/nooch-logo.png' alt='nooch' "
        "onerror=\"this.onerror=null;this.src='/static/nooch-logo.svg'\"></a>"
        "<form class='c2-search' action='/search' method='get' role='search' autocomplete='off'>"
        "<input id='gs-input' type='search' name='q' placeholder='Search people, roles, projects…' "
        "autocomplete='off' aria-label='global search'>"
        "<kbd class='c2-kbd' aria-hidden='true'>/</kbd>"
        "<div id='gs-drop' class='gs-drop' hidden></div>"
        "</form>"
        # Persoonlijke begroeting; _send vult de naam van de ingelogde persoon in (leeg = onzichtbaar).
        "<span class='c2-greet' id='c2-greet'></span>"
        "<nav class='c2-subnav'>"
        + _side_item("/search", "Search", "zoek")
        + "".join(_side_item(h, l, pn) for h, l, pn in _SIDE_ITEMS)
        + "<div class='c2-subnav-div'></div>"
        # EÉN Circle-item, niet twee. De eerste versie zette er een statische `/node` naast deze
        # placeholder — in de rail stonden toen twee knoppen "CI" onder elkaar, allebei anders.
        # Dit is de cirkel-bewuste: `_send` weet welke cirkel, `_nav` niet.
        + _SIDE_CIRCLE
        + _side_item("/admin", "Admin")
        # ORGANISATIE ALS GEWOON NAV-ITEM (voorstel Stefan, 21 september 2026). Hij hing als
        # `<details class='c2-orgfly'>` onder de balk: een tweede uitklap-mechanisme naast de
        # panelen, op een plek waar je hem alleen vond door naar beneden te scrollen. Nu dezelfde
        # knop en dezelfde flyout als Projects, Messages en Circle.
        + _side_item("/node", "Organization", "org")
        # De twee overleggen, onder een eigen scheiding. Een ander soort knop, dus ook zichtbaar
        # een ander blok — geen zesde item in dezelfde rij.
        + "<div class='c2-subnav-div'></div>"
        + _SIDE_OVERLEG
        + "</nav>"
        # HIER STOND HET ORG-UITKLAPJE (`c2-orgfly`). Het is een nav-item geworden met een
        # flyout, zoals de andere; een tweede uitklap-mechanisme onder de balk hoefde niet te
        # blijven bestaan naast het eerste.
        + "</aside>"
        # HET PANEEL STAAT LEEG IN DE DOM en wordt pas gevuld als je een knop indrukt. Zou de
        # inhoud meekomen met elke pageload, dan betaalt élk scherm in het dorp voor een
        # projectlijst en een kanalenlijst die je meestal niet opent — op productie 442 projecten
        # en 123 kanalen, per keer. Zie `views/navpaneel.py`.
        + "<aside class='c2-paneel' id='c2-paneel' hidden>"
          "<div class='c2-paneel-in' id='c2-paneel-in'></div></aside>"
        + _GS_LIVE_JS + _NAV_JS)


# Live-zoek: terwijl je typt haalt dit de dropdown-resultaten op (fragment via /search?frag=1), debounced.
# Klik buiten de balk sluit de dropdown; Enter opent de volledige /search-pagina (het form submit).
_GS_LIVE_JS = """<script>(function(){
 // SNELTOETS (fase 7): `/` en Cmd/Ctrl+K zetten de cursor in de zoekbalk. `/` alleen als je
 // niet al in een veld staat — anders kun je geen schuine streep meer typen in een formulier.
 addEventListener('keydown', function(e){
   var b=document.getElementById('gs-input'); if(!b) return;
   var t=e.target||{}, tag=(t.tagName||'').toLowerCase();
   var tikt = tag==='input'||tag==='textarea'||tag==='select'||t.isContentEditable;
   if(e.key==='/' && !tikt){ e.preventDefault(); b.focus(); b.select(); return; }
   if((e.metaKey||e.ctrlKey) && (e.key==='k'||e.key==='K')){ e.preventDefault(); b.focus(); b.select(); }
 });
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


#: De hamburger werkt alleen als dit script draait, dus zet het script zelf de klasse die hem
#: nodig maakt. Zonder JS blijft de zijbalk op mobiel staan zoals hij altijd stond — een menu dat
#: je niet kunt openen omdat een bestand niet laadde is erger dan een menu dat altijd zichtbaar is.
_NAV_JS = """<script>(function(){
 document.body.classList.add('navjs');
 window.navToggle=function(){
   var open=document.body.classList.toggle('navopen');
   var b=document.querySelector('.c2-burger');
   if(b)b.setAttribute('aria-expanded',open?'true':'false');
 };
 // Een keuze sluit het menu. Zonder dit blijft de overlay over de pagina hangen die je net opende.
 document.addEventListener('click',function(e){
   if(!document.body.classList.contains('navopen'))return;
   if(e.target.closest&&e.target.closest('.c2-side a'))window.navToggle();
 });
})();</script>"""


def _footer() -> str:
    """De gedeelde footer: alleen nog cockpit-meta. Wordt globaal door `_send` vóór </body>
    geïnjecteerd, zodat de build op elke pagina te zien is.

    HIER STONDEN DRIE NAV-LINKS (Goals · Metrics · People). Ze zijn in fase 7 naar de zijbalk
    verhuisd, of preciezer: Goals en Metrics zijn tabs op de cirkel geworden en Admin staat in de
    zijbalk. Navigatie op twee plekken is navigatie die uiteen gaat lopen."""
    return (f"<footer class='c2-foot'>cockpit 2 · {_e('GlassFrog (PoC)')} · build {_BUILD}</footer>")


