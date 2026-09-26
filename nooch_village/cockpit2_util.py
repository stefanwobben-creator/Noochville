"""Pure HTML-helpers zonder _Stores-afhankelijkheid (brok 1 van de cockpit2-split)."""
from __future__ import annotations
import hashlib as _hashlib
import os as _os
import re
import time as _time
from html.parser import HTMLParser as _HTMLParser

from nooch_village import wiki as _wiki
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


#: Blok-herkenning op regelniveau, als constanten zodat de vorm van een genummerde regel en van
#: een streep op ÉÉN plek staat in plaats van verspreid door de renderlus.
#: Het hek van een codeblok, met een optionele taal-tag erachter (`check`, `python`, …). DIE TAG
#: IS GEEN VERSIERING: `copycheck._FENCE` zoekt letterlijk naar ```check om de verboden-woorden-
#: lijsten uit vier policies te halen. Raakt hij kwijt, dan stopt de copy-checker stil.
#: Een tabelrij en de scheidingsrij eronder. GEEN TABEL ZONDER SCHEIDINGSRIJ: één regel die
#: toevallig met een pipe begint is een zin, geen tabel, en mag de weergave niet omgooien.
_PIPE_RE = re.compile(r"^\|.*")
_SCHEIDING_RE = re.compile(r"^\|[\s:|-]+\|?\s*$")


def _cellen(regel: str) -> list[str]:
    """De cellen van een pipe-rij, zonder de buitenste lege stukken."""
    deel = regel.strip().split("|")
    if deel and not deel[0].strip():
        deel = deel[1:]
    if deel and not deel[-1].strip():
        deel = deel[:-1]
    return [d.strip() for d in deel]


_HEK_RE = re.compile(r"^```([A-Za-z0-9_+-]*)\s*$")

#: De INHOUD van een codeblok, plus zijn twee hekken eromheen als losse groepen. Het openingshek
#: is met opzet exact dezelfde vorm als `_HEK_RE` hierboven: zou hij losser zijn, dan beschermde
#: hij regels die de regellus daarna NIET als codeblok ziet, en dan lopen de twee uit elkaar.
#: `\Z` als alternatief voor het sluithek, want `_md` sluit een openstaand hek zelf aan het eind
#: (fail-soft) — zonder dat alternatief was precies het laatste blok van een pagina onbeschermd.
_CODEBLOK_RE = re.compile(r"(?ms)^(```[A-Za-z0-9_+-]*[ \t]*\n)(.*?)(^```[ \t]*$|\Z)")

#: `` `code` `` op één regel. DRIE DINGEN ZITTEN IN DEZE REGEX:
#:   - `[^`\n]+` — minstens één teken, en niet over een regelovergang heen. Een paar dat een
#:     regelgrens oversteekt is bijna altijd een ongeluk, en het resultaat zou een halve alinea
#:     in een codevorm zijn.
#:   - de twee lookarounds houden een DUBBELE backtick eruit: ``a ``b`` c`` zou anders matchen op
#:     de binnenste twee en losse backticks laten staan. Nu blijft het gewoon tekst.
#:   - hij draait NA `_CODEBLOK_RE`, dus een hekregel staat er nog wél. Die matcht niet: na de
#:     eerste backtick staat er een tweede, en `[^`\n]+` eist daar een gewoon teken.
_INLINE_CODE_RE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")

_NUMMER_RE = re.compile(r"^(\d+)\. (.*)$")
_STREEP_RE = re.compile(r"^-{3,}$")

#: EEN REGEL DIE ALLEEN EEN LINK IS, is een embed. Twee vormen: een kale url, of de link zoals
#: `_link` hem hierboven al heeft omgezet — die substitutie draait VÓÓR de regellus, dus op dit
#: punt staat er geen markdown meer maar een `<a>`.
#: Het voorvoegsel van een bestand dat op ONZE server staat. Eén plek, want `_md`, de weg terug
#: en de embed-regex moeten het over hetzelfde hebben — zou dat uiteenlopen, dan rendert een
#: bijlage wel en komt hij niet terug uit de rondgang (of andersom).
EIGEN_BESTAND = "/wiki-bestand/"

#: Een kale url op een eigen regel. `/…` hoort erbij sinds eigen uploads bestaan; `//…` niet
#: (protocol-relatief, zie `_link`).
_EMBED_KAAL_RE = re.compile(r"^(https?://\S+|/wiki-bestand/\S+)$")
#: `[^<]*` EN NIET `.*` voor het label: met een gulzige punt matcht `<a>een</a> <a>twee</a>` als
#: één link met "een</a> <a …>twee" als tekst, en dan wordt een regel met twee links een embed.
_EMBED_LINK_RE = re.compile(
    r"^<a( data-beeld)? href='(https?://[^']+|/wiki-bestand/[^']+)' target='_blank' "
    r"rel='noopener'>([^<]*)</a>$")

#: url-kenmerk → (soort, herkomstlabel). DE VOLGORDE IS DE REGEL: een YouTube-link heeft geen
#: extensie, en een Drive-bestand evenmin, dus de hosts gaan vóór de extensies en Drive gaat
#: daarna — anders wordt `drive.google.com/…/x.pdf` een pdf-kaart terwijl het een Drive-link is.
_EMBED_HOSTS = (
    (("youtube.com/watch", "youtu.be/"), "video", "YouTube"),
    (("vimeo.com/",), "video", "Vimeo"),
)
_EMBED_EXT = (
    ((".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"), "afbeelding", "afbeelding"),
    ((".mp4", ".webm", ".mov"), "video", "video"),
    ((".pdf",), "pdf", "PDF"),
)
_EMBED_DRIVE = ("docs.google.com", "drive.google.com")

#: Per soort het icoon. Het staat in `data-chrome`, want een decoratief teken dat als TEKST wordt
#: opgeslagen komt na één bewerkronde letterlijk in de bron te staan — precies wat de greep (⠿)
#: van brok 3 een keer deed.
_EMBED_ICOON = {"afbeelding": "&#128247;", "video": "&#9654;", "pdf": "&#128196;",
                "drive": "&#128193;", "link": "&#128279;"}


def _embed_soort(url: str) -> tuple[str, str]:
    """(soort, herkomstlabel) op basis van de url. AFGELEID BIJ HET RENDEREN en nergens bewaard:
    wijst een link morgen naar iets anders, dan volgt de kaart. Zelfde regel als
    `wiki.grond_status` — een vergelijking, geen stempel."""
    laag = url.lower()
    for kenmerken, soort, label in _EMBED_HOSTS:
        if any(k in laag for k in kenmerken):
            return soort, label
    pad = laag.split("?")[0].split("#")[0]
    for staarten, soort, label in _EMBED_EXT:
        if pad.endswith(staarten):
            return soort, label
    if any(h in laag for h in _EMBED_DRIVE):
        return "drive", "Google Drive"
    return "link", "link"


#: De extensies waarbij een `![…]`-regel een ECHTE `<img>` wordt in plaats van een kaart. Ze komen
#: uit `_EMBED_EXT` en niet uit een tweede opsomming: die tabel bepaalt al wat "afbeelding" is, en
#: twee lijsten lopen uiteen zodra er één extensie bijkomt.
_BEELD_EXT = next(staarten for staarten, soort, _ in _EMBED_EXT if soort == "afbeelding")


def _is_beeldbestand(url: str) -> bool:
    """Eindigt deze url op een afbeeldingsextensie? Query en anker eraf, zoals `_embed_soort`."""
    return url.lower().split("?")[0].split("#")[0].endswith(_BEELD_EXT)


def _embed_html(url: str, label: str, beeld: bool = False) -> str:
    """Een regel die alleen media is: een `<img>` als het aantoonbaar een afbeelding is, anders
    een kaart met de bestandsnaam.

    HIER STOND "GEEN `<img>`, OOK NIET BIJ EEN AFBEELDING", met als reden dat inline laden elke
    paginaweergave een verzoek naar een DERDE PARTIJ laat doen en dat de Drive-links van dit dorp
    zonder sessie toch niet renderen. Die redenering klopt nog steeds — voor een externe url. Sinds
    #603 bestaan er eigen uploads (`/wiki-bestand/…`), en daar geldt geen van beide: dezelfde
    herkomst, geen derde partij, en hij rendert wel degelijk. Een geuploade foto als kale
    bestandsnaam tonen is dan geen voorzichtigheid meer maar een gat.

    DE POORT IS DUS INTENTIE ÉN VORM: `![…]` (de schrijver zegt "dit is beeld") én een
    afbeelingsextensie (de url maakt het waar). Een Drive-link met `![…]` heeft geen extensie en
    blijft dus een kaart — precies het geval waar de oude opmerking voor waarschuwde.

    EN ALLEEN VOOR EEN EIGEN BESTAND. Het ontwerpdocument schreef "`data-beeld` én een
    afbeeldingsextensie", zonder die derde voorwaarde — maar dat had stilzwijgend ook
    `![x](https://ergens/x.png)` een `<img>` gemaakt, en daarmee de beslissing omgedraaid die
    `test_er_wordt_geen_img_geladen` sinds de bloklaag-sprint bewaakt (één verzoek naar een vreemde
    host per paginaweergave). Die beslissing noemt het document niet, dus is hij hier niet
    teruggedraaid: de aanleiding was een geUPLOADE foto, en die staat op onze eigen server.

    Wil je externe afbeeldingen er later toch bij, dan is dat deze ene voorwaarde — plus een
    bewuste keuze over die verzoeken, en het bijwerken van die toets."""
    if beeld and url.startswith(EIGEN_BESTAND) and _is_beeldbestand(url):
        # GEEN `.card`. Zelfde regel als `.wiki-inline` uit #604: een blok dat tussen de tekst kan
        # staan, krijgt geen rand en geen eigen achtergrondvlak — een alinea heeft die ook niet.
        #
        # HET BIJSCHRIFT IS CHROME. Het toont de alt-tekst, en die staat al in het `alt`-attribuut;
        # zonder `data-chrome` zou hij bij de weg terug éóók als losse tekst in de bron belanden en
        # na één bewerkronde onder de afbeelding verdubbelen.
        return (f"<figure class='wb-img'><img src='{url}' alt='{label}' loading='lazy'>"
                f"<figcaption class='muted' data-chrome>{label}</figcaption></figure>")
    # INTENTIE WINT VAN DE URL. `_embed_soort` leidt de soort af uit de url, maar wie
    # `![foto](…)` schrijft zegt het expliciet — en dat staat nergens anders, want een
    # Drive-link heeft geen extensie.
    soort, herkomst = ("afbeelding", "afbeelding") if beeld else _embed_soort(url)
    # `wb-` EN GEEN EIGEN `emb-`-FAMILIE. De embed is een wiki-blok, dus hij hoort in het
    # vocabulaire dat brok 3 daarvoor al neerzette (`wb-greep`, `wb-menu`). Een eigen prefix zou
    # een nieuw privé-stylesheet zijn — precies wat `test_geen_nieuwe_klasse_prefixen` bewaakt.
    mark = " data-beeld" if beeld else ""
    return (f"<figure class='card wb-emb wb-emb--{soort}'>"
            f"<span class='wb-emb-ico' data-chrome aria-hidden='true'>{_EMBED_ICOON[soort]}</span>"
            f"<a{mark} href='{url}' target='_blank' rel='noopener'>{label}</a>"
            f"<span class='wb-emb-bron muted' data-chrome>{herkomst}</span></figure>")


#: Het omhulsel van één blok in de blokstand. ÉÉN plek, want de renderer schrijft hem en de
#: editor (brok 3) zoekt hem met `closest('.wb')` — twee spellingen is twee gedragingen.
BLOK_OPEN = "<div class='wb' data-blok='{soort}'>"
BLOK_DICHT = "</div>"

#: INHOUD-TAG → BLOKSOORT. De enige plek waar die koppeling bestaat (brok 3, 22 september 2026).
#: De renderer hieronder leest hem, en `views/wiki` geeft hem als `data-blok-soorten` mee aan de
#: browser — de normaliseerpas in `nooch.js` heeft dus GEEN eigen lijst.
#:
#: WAAROM DAT HIER ZO STRENG IS. `document.execCommand("formatBlock")` vervángt het blok-omhulsel
#: en `insertUnorderedList` nest juist ín het omhulsel; na zo'n commando klopt `data-blok` dus
#: niet meer, en sinds brok 1 hangt daar de greep aan. Iets moet dat repareren, en dat iets kan
#: alleen in de browser draaien — waar geen testrunner is. Hoe minder die pas zelf weet, hoe
#: minder er stil kan afwijken. Wat niet in deze tabel staat is een alinea.
BLOK_SOORTEN = {"h3": "h", "h4": "h", "h5": "h",
                "ul": "ul", "ol": "ol", "blockquote": "q", "hr": "hr",
                "figure": "embed", "pre": "code",
                "table": "tabel"}


#: Uitleg bij een bloktype dat je als RUWE MARKDOWN bewerkt. Alleen de tabel heeft er een, en dat
#: is geen willekeur: bij een codeblok is "typ hier je code" geen informatie, maar bij een tabel
#: staat er een `|---|---|`-regel in het sjabloon die er precies zo moet blijven staan — haal je
#: hem weg, dan is het geen tabel meer maar drie regels tekst met streepjes.
#:
#: HIER EN NIET IN `nooch.js`, om dezelfde reden als de rest van deze tabel: het vocabulaire woont
#: op één plek, en de browser kopieert alleen wat de server meestuurt. Op TAG en niet op label,
#: want een label is een naam die iemand vertaalt.
BLOK_HINT = {
    "table": ("Eerste regel = kolomnamen, tweede regel = |---|---| "
              "(laat die exact zo staan), daarna je gegevens."),
}

#: Dezelfde hints, maar op de BLOKSOORT in plaats van op de tag — dat is wat `data-blok` draagt,
#: en dus waar `_md` bij het renderen naar kijkt. AFGELEID uit `BLOK_SOORTEN` en niet apart
#: opgeschreven: een tweede vertaling tag→soort zou na één wijziging uit de pas lopen met de
#: eerste, en dan krijgt één van de twee routes stil geen uitleg meer.
_BLOK_HINT_PER_SOORT = {BLOK_SOORTEN[tag]: tekst
                        for tag, tekst in BLOK_HINT.items() if tag in BLOK_SOORTEN}


def _md(text: str, blokken: bool = False) -> str:
    """Lichte opmaak voor reacties/notities: HTML-veilig, met **vet**, *cursief*, ~~doorhalen~~,
    ## koppen, [tekst](url)-links (alleen http(s)), regelafbrekingen en '- ' lijstjes. CRLF (uit
    textareas/imports) wordt genormaliseerd zodat er geen losse \\r overblijft. XSS-veilig: de tekst
    is al ge-escaped (`_e`) vóór de opmaak-regexes draaien, en een link zonder http(s)-schema wordt
    NIET gelinkt (fail-closed, geen javascript:-urls).

    `blokken=True` — DE BLOKSTAND (brok 1 van de Notion-stijl wiki, 22 september 2026). Elk blok
    op het hoogste niveau krijgt zijn eigen `<div class='wb' data-blok='h|ul|p'>`. Zonder die div
    bestaat "de derde alinea" niet als DING: er is alleen tekst met `<br>`'s ertussen, en alles
    wat brok 3 wil (een greep per blok, slepen om te herordenen, een `/`-menu dat er een invoegt)
    heeft dat ding nodig.

    STANDAARD UIT, en dat is geen voorzichtigheid maar de scope. Deze functie rendert óók elke
    reactie, elke wall-comment en elk kanaalbericht; een blok-div daar is een wijziging aan drie
    schermen die niemand vroeg. Alleen `views/wiki._body_html` zet hem aan."""
    import re
    # HET NULTEKEN IS DE PLAATSHOUDER HIERONDER, dus het mag niet uit de tekst zelf komen. Het
    # rendert nergens, dus weghalen kost niets en het sluit de enige manier af waarop iemand de
    # bescherming zou kunnen omzeilen.
    s = _e((text or "").replace("\x00", "")).replace("\r\n", "\n").replace("\r", "\n")

    # ── DE INHOUD VAN EEN CODEBLOK GAAT EERST OPZIJ ──────────────────────────────────────────
    # Deze functie draait de inline-regexes over de HELE string en pas daarna de regellus die
    # hekken (```) herkent. Daardoor werd `**niet vet**` ín een codeblok gewoon vet — zichtbaar
    # fout, al bleef de rondgang heel omdat `_BRON_INLINE` er weer `**` van maakt.
    #
    # Met de backtick erbij is diezelfde volgorde niet meer alleen lelijk: een `` ` `` in een
    # codeblok zou een `<code>` BINNEN `<pre><code>` worden, en de weg terug negeert een `<code>`
    # in een `<pre>` bewust — dan verdwijnt de inhoud. Eén mechanisme lost allebei op, en het is
    # hetzelfde dat `_md_rijk` hieronder al gebruikt.
    bewaard: list[str] = []

    def _opzij(m):
        # DE REGELOVERGANG VÓÓR HET SLUITHEK BLIJFT BUITEN DE PLAATSHOUDER. Hij zit in groep 2
        # (het sluithek moet aan het begin van een regel staan, dus de `\n` hoort bij de inhoud),
        # maar als hij mee opzij gaat komt het sluithek op dezelfde regel als de plaatshouder te
        # staan. De regellus herkent hem dan niet meer als hek, het blok sluit nooit, en de
        # fail-soft aan het eind stopt de ``` ín het codeblok. Gemeten, niet beredeneerd.
        inhoud = m.group(2)
        staart = "\n" if inhoud.endswith("\n") else ""
        bewaard.append(inhoud[:-1] if staart else inhoud)
        return f"{m.group(1)}\x00{len(bewaard) - 1}\x00{staart}{m.group(3)}"

    s = _CODEBLOK_RE.sub(_opzij, s)

    # ── INLINE CODE VÓÓR DE REST ────────────────────────────────────────────────────────────
    # Wat tussen backticks staat is letterlijk, dus het mag niet langs de vet-/cursief-regexes.
    # Zelfde plaatshouder-truc, één stap kleiner: hier bewaren we de inhoud en zetten we het
    # `<code>`-omhulsel er meteen omheen.
    def _inline_code(m):
        bewaard.append(m.group(1))
        return f"<code>\x00{len(bewaard) - 1}\x00</code>"

    s = _INLINE_CODE_RE.sub(_inline_code, s)

    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)   # vet — vóór cursief, anders eet * de **
    s = re.sub(r"~~(.+?)~~", r"<del>\1</del>", s)             # doorhalen
    s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)               # cursief

    def _link(m):
        beeld, label, url = m.group(1), m.group(2), m.group(3)
        # `label` is al ge-escaped; de url is gevalideerd op schema.
        # EIGEN BESTANDEN ZIJN ROOT-RELATIEF (26 september 2026). Een upload op een wiki-pagina
        # wordt `/wiki-bestand/<pagina>/<naam>`; de host hoort niet in de inhoud te staan. Zonder
        # deze tak weigert de renderer hem, want hij eist een http(s)-schema.
        #
        # ALLEEN DIT VOORVOEGSEL, en niet "elk pad dat met een slash begint". Dat laatste was mijn
        # eerste versie, en twee bestaande toetsen wezen hem terecht af: `_md` weigert een intern
        # pad BEWUST (`test_link_niet_http_geen_link_failclosed`, `test_een_link_zonder_http_
        # wordt_geen_embed`). Gemeten op prod: nul pagina's hebben vandaag een relatieve
        # markdown-link, dus de brede variant had niets opgelost en wel een fail-closed-houding
        # opgegeven voor alles wat morgen getypt wordt. Dit is het kleinste gat dat de eis dekt.
        #
        # `//evil.nl/…` valt er vanzelf buiten: dat begint niet met `/wiki-bestand/`.
        if url.startswith(EIGEN_BESTAND) or url.startswith(("http://", "https://")):
            # HET UITROEPTEKEN REIST MEE ALS `data-beeld`. Het is INTENTIE, geen url-eigenschap:
            # een Drive-link naar een foto heeft geen extensie, dus zonder dit zou
            # `![foto](drive-url)` als een drive-kaart renderen en na één bewerkronde zijn
            # uitroepteken kwijt zijn. Zelfde mechaniek als `data-taal` en `data-ref`.
            mark = " data-beeld" if beeld else ""
            return f"<a{mark} href='{url}' target='_blank' rel='noopener'>{label}</a>"
        return m.group(0)                                    # geen http(s) → laat de tekst staan (geen link)

    s = re.sub(r"(!?)\[([^\]]+)\]\(([^)]+)\)", _link, s)      # [tekst](url) en ![alt](url)
    # `open_` en `dicht` zijn LEEG in de platte stand: dan staat er letterlijk dezelfde uitvoer
    # als vóór de blokstand bestond. Dat is wat `test_zonder_de_vlag_is_er_niets_veranderd`
    # byte voor byte vastlegt — deze functie rendert ook elke reactie en elk kanaalbericht.
    def open_(soort):
        # DE HINT HANGT AAN HET BLOK (26 september 2026), en niet alleen aan de menu-knop.
        # Hiervoor kreeg je de uitleg bij een NIEUWE tabel uit het blokmenu, maar niet als je een
        # bestaande openmaakte met "✎ bewerk als tekst" — dezelfde `|---|---|`-regel, dezelfde
        # val, geen uitleg. Nu draagt elk tabel-blok hem zelf, dus `naarBron()` hoeft alleen door
        # te geven wat er al staat.
        #
        # OP DE SOORT EN NIET OP DE TAG, want dat is wat `data-blok` draagt — en dit is de plek
        # waar `data-blok` gezet wordt. `_BLOK_HINT_PER_SOORT` leidt de sleutel af uit
        # `BLOK_SOORTEN`, zodat er geen tweede vertaling tag→soort ontstaat.
        if not blokken:
            return ""
        hint = _BLOK_HINT_PER_SOORT.get(soort)
        extra = f" data-wiki-hint='{_e(hint)}'" if hint else ""
        return BLOK_OPEN.format(soort=soort)[:-1] + extra + ">"

    dicht = BLOK_DICHT if blokken else ""
    out = []
    lijst = ""                       # "ul", "ol" of "" — welke lijst er open staat

    def sluit_lijst():
        nonlocal lijst
        if lijst:
            out.append(f"</{lijst}>" + dicht)
            lijst = ""

    # DE EERSTE MEERREGELIGE CONSTRUCTIE. Deze functie las tot nu toe regel voor regel; een
    # codeblok loopt over regels heen en heeft dus een toestand nodig. `code_uit` is None zolang
    # er geen hek open staat, en anders de lijst regels die we verzamelen.
    code_uit: list[str] | None = None
    code_taal = ""
    tabel_uit: list[str] | None = None

    def sluit_tabel():
        """Een verzamelde reeks pipe-regels wegschrijven. Zonder scheidingsrij op plek 2 is het
        geen tabel maar gewone tekst — dan gaan de regels alsnog als alinea's naar buiten, zodat
        er nooit inhoud verdwijnt."""
        nonlocal tabel_uit
        rijen, tabel_uit = tabel_uit, None
        if len(rijen) < 2 or not _SCHEIDING_RE.match(rijen[1].strip()):
            for r in rijen:
                out.append(f"{open_('p')}{r or '<br>'}{dicht}" if blokken else r + "<br>")
            return
        kop = _cellen(rijen[0])
        lijf = [_cellen(r) for r in rijen[2:]]
        thead = "<tr>" + "".join(f"<th>{c}</th>" for c in kop) + "</tr>"
        tbody = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in rij) + "</tr>" for rij in lijf)
        out.append(f"{open_(BLOK_SOORTEN['table'])}<table><thead>{thead}</thead>"
                   f"<tbody>{tbody}</tbody></table>{dicht}")

    def sluit_code():
        nonlocal code_uit, code_taal
        taal = f" data-taal='{code_taal}'" if code_taal else ""
        out.append(f"{open_(BLOK_SOORTEN['pre'])}<pre{taal}><code>"
                   f"{chr(10).join(code_uit)}</code></pre>{dicht}")
        code_uit, code_taal = None, ""

    for ln in s.split("\n"):
        kaal = ln.strip()
        # HET HEK. Openen sluit een eventuele lijst; sluiten schrijft het blok weg. Tussen de
        # hekken wordt er NIETS geïnterpreteerd — geen koppen, geen lijsten, geen links — en de
        # regel gaat RAUW mee (`ln`, niet `kaal`), want inspringing is in code betekenis.
        # TABEL. Een reeks pipe-regels wordt samen één blok; alles wat geen pipe-regel is sluit
        # de reeks. Het codeblok gaat vóór: binnen een hek betekent een pipe niets.
        if code_uit is None:
            if _PIPE_RE.match(kaal):
                if tabel_uit is None:
                    sluit_lijst()
                    tabel_uit = []
                tabel_uit.append(kaal)
                continue
            if tabel_uit is not None:
                sluit_tabel()
        hek = _HEK_RE.match(kaal)
        if code_uit is not None:
            if hek:
                sluit_code()
            else:
                code_uit.append(ln)
            continue
        if hek:
            sluit_lijst()
            code_uit, code_taal = [], hek.group(1)
            continue
        # KOPPEN. `## ` bleef `<h4>` (22 september 2026): 15 bestaande pagina's gebruiken hem, en
        # een nieuw niveau erbij mag er geen één hertekenen. `#` gaat er dus BOVEN zitten (h3) en
        # `###` eronder (h5).
        #
        # DE VOLGORDE MAAKT HIER NIET UIT, en dat stond er eerst anders ("langste eerst, anders
        # eet `# ` de andere twee op"). De SPATIE in elk voorvoegsel doet het werk: `"## kop"`
        # begint niet met `"# "`, want op plek 1 staat een `#` en geen spatie. Die uitleg is
        # nagerekend met een mutatie die de volgorde omdraaide — en die bleef groen.
        kop = next(((n, v) for n, v in (("### ", "h5"), ("## ", "h4"), ("# ", "h3"))
                    if kaal.startswith(n)), None)
        if kop:
            sluit_lijst()
            merk, tag = kop
            out.append(f"{open_(BLOK_SOORTEN[tag])}<{tag}>{kaal[len(merk):]}</{tag}>{dicht}")
            continue
        # SCHEIDING. Drie of meer streepjes op een eigen regel; in de bron blijft het `---`.
        if _STREEP_RE.match(kaal):
            sluit_lijst()
            out.append(f"{open_(BLOK_SOORTEN['hr'])}<hr>{dicht}")
            continue
        # CITAAT. Eén regel per citaat — geen samengevoegd blok van opeenvolgende `>`-regels: dan
        # zou de weg terug moeten raden waar de regelovergangen stonden.
        # `&gt; ` EN NIET `> `: `_e()` heeft de tekst al ge-escaped vóór deze lus draait (dat is
        # de XSS-volgorde, zie boven). Wie hier op `>` toetst, toetst op een teken dat er niet
        # meer staat — en dan doet het citaat het nooit.
        if kaal.startswith("&gt; "):
            sluit_lijst()
            out.append(f"{open_(BLOK_SOORTEN['blockquote'])}<blockquote>"
                       f"{kaal[5:]}</blockquote>{dicht}")
            continue
        # LIJSTEN, twee soorten. Ze sluiten elkaars blok: `- a` gevolgd door `1. b` zijn twee
        # lijsten, geen samengeraapte derde.
        genummerd = _NUMMER_RE.match(kaal)
        soort = "ul" if kaal.startswith("- ") else ("ol" if genummerd else "")
        if soort:
            if lijst != soort:
                sluit_lijst()
                out.append(open_(BLOK_SOORTEN[soort])
                           + f"<{soort} class='{'fbul' if soort == 'ul' else 'fol'}'>")
                lijst = soort
            out.append(f"<li>{genummerd.group(2) if genummerd else kaal[2:]}</li>")
            continue
        sluit_lijst()
        # EMBED. Een regel die ALLEEN een link is — kaal of als `[tekst](url)`, die laatste staat
        # hier al als `<a>` omdat `_link` vóór deze lus draait. Een link midden in een zin blijft
        # een gewone link: van de 1151 regels op prod is er nul die alleen een markdown-link is
        # en één die alleen een kale url is, dus dit verandert precies één bestaande regel.
        kaal_url = _EMBED_KAAL_RE.match(kaal)
        embed = _EMBED_LINK_RE.match(kaal)
        if kaal_url or embed:
            url = kaal_url.group(1) if kaal_url else embed.group(2)
            label = url if kaal_url else embed.group(3)
            beeld = bool(embed and embed.group(1))
            out.append(f"{open_(BLOK_SOORTEN['figure'])}"
                       f"{_embed_html(url, label, beeld)}{dicht}")
            continue
        # In de blokstand IS het omhulsel de regelafbreking, dus geen `<br>` erachter. Een
        # LEGE regel krijgt hem wél: `<div></div>` is nul pixels hoog, en zonder dit
        # verdwijnt elke witregel van elke pagina zonder dat een bron-test iets merkt.
        out.append(f"{open_('p')}{ln or '<br>'}{dicht}" if blokken else ln + "<br>")
    # FAIL-SOFT bij een hek dat niet gesloten wordt: liever een codeblok tot het eind dan een
    # halve pagina kwijt.
    if code_uit is not None:
        sluit_code()
    if tabel_uit is not None:
        sluit_tabel()
    sluit_lijst()
    html = "".join(out)
    # DE PLAATSHOUDERS TERUG, als allerlaatste. Wat hier terugkomt is al ge-escaped (dat gebeurde
    # vóór het opzijzetten), dus er gaat geen tekst alsnog ongezien naar buiten.
    if bewaard:
        html = re.sub(r"\x00(\d+)\x00", lambda m: bewaard[int(m.group(1))], html)
    if blokken:
        return html
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
#: `h3`/`h5`/`blockquote`/`hr` kwamen erbij met het vocabulaire van brok 2 (22 september 2026).
_BRON_BLOK = ("h3", "h4", "h5", "li", "div", "p", "blockquote", "hr", "figure")

#: Tags zonder eindtag. De chrome-teller hieronder mag hier niet op oplopen: er komt geen
#: `handle_endtag` die hem weer omlaag haalt, en dan blijft alles NA de void-tag stil verdwijnen
#: tot de volgende willekeurige eindtag. Gemeten met een `<input type='hidden'>` in een
#: chrome-span: "Zichtbaar" achter die input kwam niet meer uit de rondgang. Dat viel tot nu toe
#: niet op omdat elke chrome die er stond alleen tekst bevatte — het feiten-blok draagt
#: formulieren, en die bestaan uit niets anders.
_VOID = frozenset(("area", "base", "br", "col", "embed", "hr", "img", "input",
                   "link", "meta", "param", "source", "track", "wbr"))

#: tag → het voorvoegsel in de bron. Eén tabel, zodat een nieuw kopniveau op één plek bestaat.
_BRON_KOP = {"h3": "# ", "h4": "## ", "h5": "### "}


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
        #: droeg deze link een uitroepteken? Dan is het een afbeelding, en dat moet terug.
        self._beeld = False
        self._linktekst: list[str] = []
        #: kwam het laatste regeleinde van een BLOK-grens (`</li>`, `</h4>`, `</p>`) of van een
        #: `<br>`? Dat verschil beslist of het eindregeleinde erbij hoort; zie `_md_naar_bron`.
        self._blok_einde = False
        #: staan we in een `<ol>`, en bij welk nummer? De teller hoort bij de LIJST en niet bij
        #: het item: een `<ul>` ertussen moet hem resetten.
        self._ol = False
        self._nr = 0
        #: hoe diep zitten we in een `data-chrome`-element? Zie `handle_starttag`.
        self._chrome = 0
        # HOE DIEP WE IN EEN `<pre>` ZITTEN. Een `<code>` betekent twee verschillende dingen: in
        # een `<pre>` is hij het binnenwerk van een codeblok (het hek staat op de `<pre>`), daar
        # buiten is hij inline code met backticks eromheen. Zonder deze teller krijgt elk codeblok
        # er backticks bij.
        self._pre = 0
        #: de cel die nu open staat, en de rij die we aan het vullen zijn. Tekst binnen een
        #: tabel gaat NIET rechtstreeks naar `uit`: hij hoort bij een cel, en pas als de rij
        #: dicht is weten we hoe de pipe-regel eruitziet.
        #: staat er een ruw bewerkvlak open? Dan is elke tekst markdown en gaat hij letterlijk
        #: door — geen blok-grenzen, geen samenvoeging.
        self._bron = False
        self._cel: list[str] | None = None
        self._rij: list[str] = []
        self._kop_gehad = False
        #: staan we ín een embed-kaart? Alleen daar mag een link waarvan de TEKST gelijk is aan
        #: zijn url terugkomen als kale url — zie `handle_endtag`.
        self._embed = False

    # ── hulpjes ──────────────────────────────────────────────────────────────
    def _doel(self) -> list:
        """Waar de volgende tekst heen gaat. ÉÉN PLEK, want er zijn er nu drie: een open link
        vangt zijn eigen label, een open tabelcel vangt haar inhoud, en anders is het de uitvoer.
        Stond die keuze op twee plekken, dan viel een link ín een tabelcel tussen wal en schip."""
        if self._href or self._ref:
            return self._linktekst
        if self._cel is not None:
            return self._cel
        return self.uit

    def _schrijf(self, tekst: str) -> None:
        self._doel().append(tekst)
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
        # `data-chrome` = DIT HOORT BIJ HET SCHERM, NIET BIJ DE TEKST (brok 3, 22 september 2026).
        #
        # De blok-greep is een knop ín een bewerkbaar veld, en alles binnen dat veld gaat bij het
        # opslaan mee als `innerHTML`. De fail-closed-regel hierboven maakt van een tag die hij
        # niet kent zijn eigen TEKST — gemeten: `<button>⠿</button>` in een blok gaf na opslaan
        # letterlijk `⠿Een alinea.` in de bron. Voor chrome is dat precies de verkeerde kant op.
        #
        # DIT IS HET VANGNET, NIET DE EERSTE VERDEDIGING: de editor haalt zijn grepen er zelf uit
        # vóór het versturen. Maar één gemiste strip is anders een vervuilde pagina, en dat is
        # het soort fout dat je pas een week later in een diff terugziet.
        # EEN AFGELEID BLOK DRAAGT ZIJN BRON IN EEN ATTRIBUUT. Wat er tussen de tags staat is
        # uitvoer — feiten uit `meta`, backlinks uit andere pagina's — en dat hoort nooit in de
        # opslag terecht te komen. De BRON is één regel tekst (`{{facts}}`), en die staat hier.
        #
        # Dit moet VÓÓR de chrome-check staan: de rest van het blok is chrome, maar dan moet het
        # attribuut al gelezen zijn. De `<textarea>` verderop is de andere kant van dezelfde munt
        # — daar is de INHOUD de bron, hier het attribuut.
        if not self._chrome and tag != "textarea" and "data-blok-bron" in d:
            self._nieuwe_regel()
            self.uit.append(d["data-blok-bron"] or "")
            self._nieuwe_regel()
            self._chrome += 1
            return
        if self._chrome or "data-chrome" in d:
            # Een void-tag krijgt geen eindtag en mag de teller dus niet verhogen; zie `_VOID`.
            if tag not in _VOID:
                self._chrome += 1
            return
        if tag == "br":
            self.uit.append("\n")
            self._blok_einde = False          # een <br> IS de tekst, geen scheiding eromheen
        elif tag in _BRON_INLINE:
            self._schrijf(_BRON_INLINE[tag][0])
        elif tag in _BRON_KOP:
            self._nieuwe_regel(); self.uit.append(_BRON_KOP[tag])
        elif tag == "blockquote":
            self._nieuwe_regel(); self.uit.append("> ")
        elif tag == "hr":
            # Een `<hr>` heeft geen inhoud en dus geen EINDTAG. Hij moet zijn regel daarom zelf
            # aan beide kanten afsluiten: zonder de tweede aanroep plakt de tekst erna eraan vast
            # ("---onder"), want in de platte stand staat daar geen `<div>` omheen.
            self._nieuwe_regel(); self.uit.append("---"); self._nieuwe_regel()
        elif tag in ("ul", "ol"):
            # DE TELLER STAAT HIER, niet bij `<li>`. Een genummerde lijst telt vanaf 1 per lijst,
            # en een `<ul>` ertussen moet die teller resetten — anders loopt de nummering door
            # over een bolletjeslijst heen.
            self._nieuwe_regel(); self._ol = (tag == "ol"); self._nr = 0
        elif tag == "li":
            self._nieuwe_regel()
            if self._ol:
                self._nr += 1
                self.uit.append(f"{self._nr}. ")
            else:
                self.uit.append("- ")
        elif tag == "img":
            # DE WEG TERUG VAN EEN ECHTE AFBEELDING. Zonder deze tak is een `<img>` een tag die de
            # parser niet kent, en de fail-closed-regel maakt er dan zijn eigen TEKST van: na één
            # bewerkronde staat er letterlijk niets meer waar de foto stond. Dezelfde klasse fout
            # als de bijlage die #603 moest repareren.
            #
            # DEZELFDE POORT ALS `_md`, want dit is dezelfde poort een stap eerder: een `src` die
            # geen eigen bestand en geen http(s) is, zou hier de opslag in glippen terwijl de
            # renderer hem nooit had geproduceerd.
            _src = d.get("src") or ""
            if _src.startswith(EIGEN_BESTAND) or _src.startswith(("http://", "https://")):
                self._schrijf(f"![{d.get('alt') or ''}]({_src})")
        elif tag == "input" and d.get("type") == "checkbox":
            # DE TAAK IS WIKI-ONLY aan de RENDER-kant (`views/wiki._body_html`), maar de weg terug
            # moet hem kennen: anders eet de wiki bij elke bewerking zijn eigen vinkjes op. Het
            # vakje staat ín een `<li>`, dus het voorvoegsel staat er al — hier alleen de haakjes.
            self.uit.append("[x] " if "checked" in d else "[ ] ")
            self._blok_einde = False
        elif tag in ("a", "span"):
            # Een wiki-verwijzing draagt zijn ORIGINELE tekst mee (`data-ref`), want op het scherm
            # staat de opgeloste titel en die is niet hetzelfde. Zonder dat attribuut zou
            # `[[compliance-beleid]]` terugkomen als de titel van de pagina waar hij heen wees.
            self._beeld = "data-beeld" in d
            self._ref = d.get("data-ref") or ""
            self._href = "" if self._ref else (d.get("href") or "")
            self._linktekst = []
        elif tag == "textarea" and "data-blok-bron" in d:
            # HET BEWERKVLAK VAN EEN TABEL OF CODEBLOK. `contenteditable` en `execCommand` kunnen
            # die twee niet fatsoenlijk aan — een Enter in een cel maakt iets anders dan een
            # nieuwe rij — dus je bewerkt daar de RUWE bron. Wat erin staat IS markdown en gaat
            # dus letterlijk door, zonder blok-logica.
            #
            # Zo blijft de omzetting op één plek: de browser levert tekst, de server maakt er een
            # blok van. Er komt geen tweede renderer in JS.
            self._nieuwe_regel()
            self._bron = True
        elif tag == "table":
            self._nieuwe_regel()
            self._kop_gehad = False
        elif tag in ("thead", "tbody", "tr"):
            self._rij = [] if tag == "tr" else self._rij
        elif tag in ("th", "td"):
            self._cel = []
        elif tag == "pre":
            self._nieuwe_regel()
            self._pre += 1
            self.uit.append("```" + (d.get("data-taal") or "") + "\n")
            self._blok_einde = False
        elif tag == "code":
            # Binnen een `<pre>` staat het hek al op de `<pre>` — daar doet hij niets. Daarbuiten
            # is dit inline code en horen de backticks erbij.
            if not self._pre:
                self._schrijf("`")
        elif tag == "figure":
            self._embed = True
            self._nieuwe_regel()
        elif tag in _BRON_BLOK:
            self._nieuwe_regel()

    def handle_endtag(self, tag):
        if self._chrome:
            self._chrome -= 1
            return
        if tag == "code":
            # ALLEEN BUITEN EEN `<pre>`. Het sluithek van een codeblok staat op de `</pre>`
            # hieronder; hier zou het een tweede zijn.
            if not self._pre:
                self._schrijf("`")
        elif tag in _BRON_INLINE:
            self._schrijf(_BRON_INLINE[tag][1])
        elif tag in ("a", "span"):
            label = "".join(self._linktekst)
            # EERST LOSLATEN, DAN PAS HET DOEL BEPALEN. Zolang `_href`/`_ref` nog staan, wijst
            # `_doel()` naar de linktekst zelf — dan schreef een link ín een tabelcel zichzelf
            # terug in zijn eigen buffer en kwam de cel leeg uit de rondgang.
            ref, href, beeld = self._ref, self._href, self._beeld
            self._ref = self._href = ""
            self._beeld = False
            doel = self._doel()
            if ref:
                doel.append(f"[[{ref}]]")
            elif href.startswith(("http://", "https://")) or href.startswith(EIGEN_BESTAND):
                # BINNEN EEN EMBED komt een link waarvan de tekst zijn eigen url is terug als
                # KALE url. Anders typt iemand `https://x` en staat er na één bewerkronde
                # `[https://x](https://x)` in de bron — een andere tekst dan hij schreef.
                #
                # En ALLEEN binnen een embed: in een zin zou dezelfde regel
                # `zie [https://x](https://x) hier` veranderen in `zie https://x hier`, en dat is
                # geen link meer. Dan breekt de rondgang.
                if self._embed and label == href and not beeld:
                    doel.append(href)
                else:
                    doel.append(("!" if beeld else "") + f"[{label}]({href})")
            else:
                # DEZELFDE POORT ALS `_md`, EEN STAP EERDER — en dus ook hetzelfde ene
                # voorvoegsel voor eigen bestanden (`EIGEN_BESTAND`). Zonder die
                # tak hierboven at de weg terug elke geüploade bijlage op: de kaart rendert, en
                # bij de eerste bewerkronde staat er alleen nog de bestandsnaam als platte tekst.
                #
                # `_md` weigert een link zonder http(s)-schema, dus een `javascript:`-url zou
                # toch als platte tekst renderen —
                # maar hij zou dan wél in de OPSLAG staan, klaar voor de dag waarop iemand een
                # tweede renderer schrijft die minder streng is. Hier houdt alleen de tekst over.
                doel.append(label)
            self._linktekst = []
            self._blok_einde = False
        elif tag == "textarea" and self._bron:
            self._bron = False
            self._nieuwe_regel()
        elif tag in ("th", "td"):
            self._rij.append("".join(self._cel or []).strip())
            self._cel = None
        elif tag == "tr":
            self.uit.append("| " + " | ".join(self._rij) + " |")
            self._nieuwe_regel()
            if not self._kop_gehad:
                # DE SCHEIDINGSRIJ WORDT OPNIEUW OPGEBOUWD, met precies zoveel kolommen als de
                # kop. Op prod staat er een tabel met drie kolommen en een scheidingsrij van twee;
                # dat parseert toevallig, maar het is geen bron die je letterlijk wilt bewaren.
                self.uit.append("|" + "---|" * len(self._rij))
                self._nieuwe_regel()
                self._kop_gehad = True
            self._rij = []
        elif tag == "table":
            self._nieuwe_regel()
        elif tag == "pre":
            self._pre = max(0, self._pre - 1)
            self.uit.append("\n```")
            self._nieuwe_regel()
        elif tag == "figure":
            self._embed = False
            self._nieuwe_regel()
        elif tag in _BRON_BLOK:
            self._nieuwe_regel()
        elif tag in ("ul", "ol"):
            self._ol = False

    def handle_data(self, data):
        if self._chrome:
            return                      # tekst ín chrome is een label, geen inhoud
        # GEEN EIGEN TAK VOOR HET BEWERKVLAK. Ik had er een ("ruwe markdown gaat letterlijk"),
        # maar `_schrijf` doet precies hetzelfde zolang er geen link of tabelcel open staat — en
        # binnen een <textarea> staat dat allebei niet. Een mutatie die de tak uitschakelde bleef
        # groen; dan is hij dood, en dood is weg. Wat het bewerkvlak WEL nodig heeft zijn de
        # regeleindes eromheen, en die staan bij de start- en eindtag.
        # GEEN UITZONDERING VOOR CODE, en dat is met opzet. Ik had hier eerst een tak die de
        # tekst binnen een `<pre>` rechtstreeks wegschreef "omdat elk teken daar inhoud is".
        # Die was overbodig — `_schrijf` doet precies hetzelfde zolang er geen link open staat —
        # én schadelijk: stond er een `[tekst](url)` ín het codeblok, dan ging het label langs
        # `_linktekst` heen en sloot `</a>` af met een LEEG label. Uit de rondgang kwam dan
        # `de docs[](https://…)`. Een mutatie die de hele tak uitschakelde bleef groen; daarmee
        # was hij aantoonbaar dood, en de eenvoudigste vorm is ook de juiste.
        self._schrijf(data)


def _md_naar_bron(html: str) -> str:
    """De omgekeerde van `_md`: opgemaakte HTML terug naar de markdown-bron.

    Alles buiten de whitelist hierboven degradeert naar platte tekst. Geeft nooit HTML terug."""
    parser = _BronParser()
    parser.feed(html or "")
    parser.close()
    uit = "".join(parser.uit).replace("\r\n", "\n").replace("\r", "\n")
    # HIER STOND EEN LUS die drie of meer regeleindes terugbracht tot twee, met de aanname "drie
    # of meer is nooit iets anders dan twee". Die klopt niet: typt de schrijver ÉCHT twee lege
    # regels, dan is drie regeleindes precies wat hij bedoelde, en at elke bewerkronde er één op.
    #
    # Waar hij tegen beschermde is een echt probleem — een browser sluit een alinea met `</p>` én
    # opent de volgende met `<p>`, twee signalen voor één overgang — maar dat wordt al opgevangen
    # door `_nieuwe_regel`, die weigert een regeleinde toe te voegen als er al één staat. Deze lus
    # was dus een tweede verdediging tegen iets dat de eerste al tegenhield, en zij was degene die
    # inhoud kostte. Weggehaald op 24 september 2026, nadat gemeten was dat de rondgang zonder hem
    # heel blijft op alle 122 artefacten van prod en de volle suite groen blijft.
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

#: De werkbalk-knoppen: (commando, argument, label, titel). Geen link-knop — `_md` ondersteunt
#: `[tekst](url)` wel, maar een linkdialoog is een scherm op zich en hoort bij een eigen scope.
#:
#: ALLEEN WAT ÉCHT INLINE IS (26 september 2026). Hier stonden ook een bullet-lijst
#: (`insertUnorderedList`) en een kop (`formatBlock <h4>`), en dat waren twee handelingen met twee
#: ingangen: het blokmenu heeft Lijst, Genummerde lijst en Kop 1/2/3 al. Twee wegen naar dezelfde
#: uitkomst lopen uiteen zodra er aan één van de twee iets verandert — dezelfde reden waarom het
#: losse uploadformulier verviel toen Afbeelding in het blokmenu kwam.
#:
#: DE SCHEIDING GING MEE. Vier knoppen die allemaal hetzelfde doen (een stukje tekst opmaken)
#: hebben niets te scheiden; het streepje zat er juist om inline van blok te scheiden, en die
#: tweedeling staat nu in twee verschillende menu's.
_OPMAAK_KNOPPEN = (("bold", "", "<b>B</b>", "Bold"),
               ("italic", "", "<i>I</i>", "Italic"),
               ("strikeThrough", "", "<s>S</s>", "Strikethrough"),
               # INLINE CODE HEEFT GEEN `execCommand`. De browser kent er geen commando voor, dus
               # dit is het enige item in deze werkbalk met een EIGEN naam: `nooch.js` vangt hem
               # af vóór de execCommand-regel. De naam begint met `nv` om precies dat verschil
               # zichtbaar te maken — een lezer die `bold` ziet weet dat de browser het doet, en
               # bij `nvCode` dat wij het doen.
               ("nvCode", "", "&lt;/&gt;", "Inline code"))


def _accept(alleen_beeld: bool = False) -> str:
    """De `accept`-waarde voor de bestandskiezer, UIT DE BESTAANDE ALLOWLIST.

    GEEN TWEEDE LIJST. `channels.BIJLAGE_TYPES` bepaalt wat de server accepteert; zou hier een
    eigen opsomming staan, dan biedt het menu morgen een type aan dat de server weigert (of
    andersom) zonder dat iemand dat besloot. Dezelfde regel als bij `BLOK_SOORTEN` en `AFGELEID`.

    DE DOORSNEDE BIJ "ALLEEN BEELD", en die is smaller dan je zou raden: `_BEELD_EXT` kent `.svg`,
    de uploadlijst niet — een SVG is een document dat script kan dragen en staat er bewust niet op.
    Precies daarom is dit een doorsnede en geen kopie van één van de twee.
    """
    from nooch_village import channels as _ch
    ext = sorted(_ch.BIJLAGE_TYPES)
    if alleen_beeld:
        ext = [e for e in ext if e in _BEELD_EXT]
    return ",".join(ext)


#: Het menu-label van een afgeleid blok. `wiki.AFGELEID` draagt het Engelse KOPJE dat boven de
#: sectie op het scherm staat ("Links here"); in dit menu staat waar je het BLOK bij noemt, in de
#: taal van de andere negen knoppen. Ontbreekt een naam hier, dan valt hij terug op het kopje —
#: een nieuwe markering krijgt zo altijd een knop, nooit stilzwijgend geen.
_AFGELEID_LABEL = {"facts": "Feiten", "backlinks": "Backlinks"}

#: HET /-MENU: welk bloktype je kunt invoegen, hoe het heet, en met welk commando. De vierde
#: kolom is het argument voor `execCommand`.
#:
#: DIT STAAT HIER EN NIET IN JS, en dat is dezelfde regel als bij `BLOK_SOORTEN`: een lijst
#: bloktypes in de browser zou de derde plek zijn waar het vocabulaire woont (naast `_md` en
#: `_md_naar_bron`) en de enige waar geen test bij kan. De server rendert het menu als sjabloon;
#: `nooch.js` kloont het en voert uit wat erin staat.
#:
#: GEEN KNOP ZONDER WEG TERUG — dezelfde regel als in brok 2. Elke tag hieronder staat in
#: `_BRON_BLOK` (of is `p`, de terugval), en een test bewaakt dat.
BLOK_MENU = (
    ("p", "Tekst", "formatBlock", "<p>"),
    ("h3", "Kop 1", "formatBlock", "<h3>"),
    ("h4", "Kop 2", "formatBlock", "<h4>"),
    ("h5", "Kop 3", "formatBlock", "<h5>"),
    ("ul", "Lijst", "insertUnorderedList", ""),
    ("ol", "Genummerde lijst", "insertOrderedList", ""),
    ("blockquote", "Citaat", "formatBlock", "<blockquote>"),
    ("hr", "Scheiding", "insertHorizontalRule", ""),
    # TABEL EN CODE KUNNEN NIET VIA `execCommand`. Een `formatBlock` op een `<pre>` haalt de
    # regelovergangen eruit en een tabel kent de browser als commando niet eens. Die twee krijgen
    # daarom hun MARKDOWN-SJABLOON mee (vierde kolom) en openen het bron-bewerkvlak dat voor deze
    # twee soorten al bestaat — hetzelfde `bron`-pad als de greep-actie "bewerk als tekst".
    #
    # HET SJABLOON STAAT HIER en niet in `nooch.js`, om dezelfde reden als de rest van deze
    # tabel: dan zou het vocabulaire op een derde plek wonen, en op de enige zonder toets.
    ("table", "Tabel", "bron", "| A | B |\n|---|---|\n| | |"),
    ("pre", "Codeblok", "bron", "```\ncode\n```"),
) + tuple(
    # FEITEN EN BACKLINKS HOREN ER OOK IN (26 september 2026). De markering `{{facts}}` bestaat
    # sinds #595 en de renderer maakt er een volwaardig blok van — met greep, met sleepstand —
    # maar hij was alleen te plaatsen door de syntax te typen. Dat is precies wat dit menu moest
    # wegnemen: voor wie het menu gebruikt bestond die plaatsbaarheid dus niet.
    #
    # `p` ALS TAG, en dat is geen slordigheid: er IS geen HTML-tag voor een afgeleid blok. De
    # server maakt er bij het opslaan een `<div data-blok='facts'>` van, net zoals bij een tabel
    # het `bron`-pad de `<table>` maakt. De tag-kolom zegt alleen wat de BROWSER na het commando
    # overhoudt, en dat is hier de terugval — hetzelfde als bij `table` en `pre`.
    #
    # DE LIJST KOMT UIT `wiki.AFGELEID` en niet uit een tweede opsomming hier: die tabel bepaalt
    # wat de renderer herkent, en een knop voor een markering die hij niet kent is een knop die
    # bij het opslaan platte tekst oplevert. Alleen het LABEL staat hier, want dit menu is
    # Nederlands ("Tekst", "Codeblok") terwijl `AFGELEID` de Engelse schermkopjes draagt.
    ("p", _AFGELEID_LABEL.get(naam, engels), "bron", _wiki.marker(naam))
    for naam, engels in _wiki.AFGELEID.items()
) + (
    # AFBEELDING EN BESTAND (26 september 2026). Ze openen een bestandskiezer in plaats van een
    # `execCommand`: de derde soort menu-item, naast "de browser maakt het blok" (formatBlock) en
    # "de server levert een sjabloon" (bron). De upload-aanroep is dezelfde `wiki_bijlage`-actie
    # als het formulier dat hiermee vervalt — geen tweede uploadpad.
    #
    # `p` ALS TAG, om dezelfde reden als bij Feiten en Backlinks: er is geen tag die de BROWSER
    # hier achterlaat. Wat er komt te staan, rendert de server.
    ("p", "Afbeelding", "upload", _accept(alleen_beeld=True)),
    ("p", "Bestand", "upload", _accept()),
)


def blok_menu() -> str:
    """Het sjabloon voor het /-menu. Verborgen; `nooch.js` kloont hem naar het blok waar je typt.

    `data-chrome` hoewel hij BUITEN het bewerkbare veld staat: als hij er ooit in belandt (een
    kloon die niet wordt opgeruimd, een plakactie) hoort hij nog steeds geen tekst te worden.
    Dezelfde twee verdedigingen als bij de greep."""
    knoppen = "".join(
        f"<button type='button' class='wb-menu-item' data-wiki-cmd='{_e(cmd)}'"
        + (f" data-wiki-arg='{_e(arg)}'" if arg else "")
        # DE HINT REIST MEE ALS ATTRIBUUT, zoals het sjabloon en de soorten-tabel. `nooch.js` zet
        # hem neer bij het bewerkvlak; hij bedenkt hem niet.
        + (f" data-wiki-hint='{_e(BLOK_HINT[_tag])}'" if _tag in BLOK_HINT else "")
        + f">{_e(label)}</button>"
        for _tag, label, cmd, arg in BLOK_MENU)
    return (f"<div id='wb-menu-sjabloon' class='wb-menu' data-chrome hidden>"
            f"{knoppen}</div>")


def opmaak_werkbalk() -> str:
    """Zelfde atomen als de bestaande markdown-werkbalk (`.editor-tb`, `.tb-b`, `.tb-sep`), zodat
    er geen tweede knoppentaal ontstaat voor dezelfde handeling.

    HIJ ZWEEFT SINDS 26 SEPTEMBER. Hiervoor stond hij als vaste balk bovenaan het bewerkvlak,
    `position:sticky` — en toen bewerken de stand werd, stond die balk dus op elke pagina, altijd.
    Op een lange pagina scrolde hij bovendien weg zodra je ver genoeg naar beneden was.

    Nu verschijnt hij bij een TEKSTSELECTIE, vlak erboven. Dat lost het wegscrollen structureel
    op: er is geen vaste balk meer om weg te scrollen. Hij komt waar je selectie is.

    DE SERVER RENDERT HEM NOG STEEDS HIER, en dat blijft de regel: de knoppentaal woont op één
    plek. `nooch.js` toont en positioneert hem alleen."""
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


_ICON_STICKER = (
    # Een sticker: een vierkant met een omgekruld hoekje. Zelfde lijnstijl en maat als
    # `_ICON_ADD_EMOJI` hieronder, want ze staan naast elkaar in dezelfde balk.
    "<svg width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='currentColor' "
    "stroke-width='2' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>"
    "<path d='M15.5 3H6a3 3 0 0 0-3 3v12a3 3 0 0 0 3 3h6l9-9V6a3 3 0 0 0-3-3z'/>"
    "<path d='M12 21v-5a4 4 0 0 1 4-4h5'/>"
    "</svg>")


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
#: NAAST de balk in plaats van dat je het scherm verlaat. Alleen CI is nog zo'n lijst; WI, AD, ME
#: en PR niet — daar val je binnen op een scherm, en dan is een tussenlijst een extra klik zonder
#: winst. (IN stond hier ook, tot bleek dat die knop een functie aanriep die niet bestond; zie
#: #531.)
_SIDE_ITEMS = (
    # PROJECTS IS GEEN PANEEL MEER (eis Stefan, 23 september 2026) — dezelfde beweging die
    # Messages twee dagen eerder maakte, en om dezelfde reden. Het paneel gaf een LIJST van
    # projecten terwijl `/projects` het BORD is: kolommen, kaarten, groepering per rol of
    # persoon. Je koos dus eerst een project uit een platte lijst om daarna op een bord te
    # landen dat je meteen had kunnen zien. De lijst liet bovendien bewust van alles weg
    # (status, doel, kolom) wat het bord wél toont.
    #
    # Het oude argument hieronder — "bij Projects voegt het paneel iets toe dat de pagina niet
    # heeft" — klopte alleen zolang je het paneel als filter las ("mijn projecten"). Dat filter
    # bestaat op het bord zelf als groepering, dus er ging niets verloren.
    ("/projects", "Projects", ""),
    # MESSAGES IS GEEN PANEEL (eis Stefan, 21 september 2026). Hij was het wel, en het leverde een
    # halve Messages op: het paneel toonde de kanalenlijst terwijl je nog op je vorige scherm
    # stond, dus het gesprek was nergens en de oude pagina keek er langs. Klikken op een kanaal
    # bracht je alsnog op `/messages`, maar de tussenstand las als kapot.
    #
    # De diepere reden dat het niet past: Messages is een scherm dat zelf al uit lijst + detail
    # bestaat. Een paneel kan daar alleen de lijst van tonen, en die lijst is een kopie van wat de
    # pagina zelf al heeft. (Dit argument noemde Projects nog als tegenvoorbeeld — "daar voegt het
    # paneel iets toe". Sinds 23 september geldt dat ook voor Projects niet meer: zie de comment
    # bij het item hierboven. Wat overblijft is Circle, en dat is precies het item waarvan nu de
    # vraag ligt of het als concept nog bestaansrecht heeft.)
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
#: `_send` vult hem in, net als bij `_SIDE_OVERLEG` hieronder.
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

#: `_send` vult deze plek per pagina in (het is per-sessie/per-records-informatie, en `_nav()`
#: heeft geen stores). Zelfde patroon als de begroeting. `_SIDE_CIRCLE` stond hier ook, voor de
#: Circle-knop; die verviel op 23 september 2026 — zie de comment in `_nav()`.
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
        # De hamburger staat BUITEN de header én buiten de zijbalk, anders verdwijnt de knop
        # samen met wat hij opent.
        "<button type='button' class='c2-burger' onclick='navToggle()' "
        "aria-label='Menu' aria-expanded='false'>\u2630</button>"
        # ── DE HORIZONTALE HEADER ──────────────────────────────────────────────────────────
        # Logo, zoek en profiel stonden ONDER elkaar bovenin de zijbalk. Drie dingen die niets
        # met elkaar te maken hebben, gestapeld in de kolom waar de navigatie hoort — en het
        # zoekveld was daardoor zo breed als die kolom (216px) terwijl het het enige veld in
        # het dorp is waar je een hele zin in typt.
        # Nu een eigen balk over de volle breedte: logo links, zoek in het midden (max 520px),
        # profiel rechts. De zijbalk houdt alleen nog navigatie.
        "<header class='c2-header'>"
        "<a class='c2-logo' href='/' title='home'><img src='/static/nooch-logo.png' alt='nooch' "
        "onerror=\"this.onerror=null;this.src='/static/nooch-logo.svg'\"></a>"
        # HET ZOEKFORMULIER IS VERPLAATST, NIET HERSCHREVEN. `_GS_LIVE_JS` hangt aan `#gs-input`
        # en `#gs-drop`; beide id's blijven exact zoals ze waren, inclusief de `/`-sneltoets en
        # de typeahead-dropdown.
        "<form class='c2-search' action='/search' method='get' role='search' autocomplete='off'>"
        "<input id='gs-input' type='search' name='q' placeholder='Search people, roles, projects…' "
        "autocomplete='off' aria-label='global search'>"
        "<kbd class='c2-kbd' aria-hidden='true'>/</kbd>"
        "<div id='gs-drop' class='gs-drop' hidden></div>"
        "</form>"
        # WAS "Hoi Stefan". `_send` vult hier de initialen van de ingelogde persoon in, met de
        # volle naam in title/aria-label en dezelfde link naar zijn eigen pagina. Leeg = niets
        # te zien; een lege cirkel zou beloven dat er iemand achter zit.
        "<span class='c2-av' id='c2-av'></span>"
        "</header>"
        "<aside class='c2-side'>"
        "<nav class='c2-subnav'>"
        # DE TWEE OVERLEGGEN STAAN BOVENAAN. Ze stonden onderaan, achter een scheiding, als
        # "een ander soort knop". Dat klopt nog steeds — het is een andere soort — maar het is
        # ook de snelste ingang naar iets dat NU loopt, en daar hoort de plek bij waar je het
        # eerst kijkt. De scheiding eronder houdt het verschil zichtbaar.
        + _SIDE_OVERLEG
        + "<div class='c2-subnav-div'></div>"
        # HIER STOND EEN "SEARCH"-ITEM dat het zoekpaneel opende. Het zoekVELD staat er al, één
        # regel hoger, met de `/`-sneltoets en een typeahead-dropdown — en beide gingen naar
        # dezelfde `/search`-inhoud. Twee ingangen naar één ding.
        #
        # De knop had zijn reden toen hij gebouwd werd: in de rail-stand was `.c2-search`
        # verborgen, dus op /messages was er géén zoek. Die rail is op 21 september 2026 vervallen
        # (#544) en de balk is overal even breed — daarmee verviel de reden voor de knop zonder
        # dat iemand hem weghaalde. Weg op 22 september (eis Stefan).
        + "".join(_side_item(h, l, pn) for h, l, pn in _SIDE_ITEMS)
        + "<div class='c2-subnav-div'></div>"
        # HIER STOND CIRCLE (`_SIDE_CIRCLE`, door `_send` per verzoek ingevuld met de eigen
        # cirkel). Weg op 23 september 2026, en niet als bug maar als concept: een cirkel IS een
        # rol die rollen bevat, dus wat "mijn cirkel" toonde was altijd een deel van de
        # organisatieboom — een voorvoegsel, geen tweede perspectief. Sinds Organization zonder
        # `hier` op je eigen cirkel landt (uitgeklapt én gemarkeerd) toont die knop alles wat
        # Circle toonde, plus het pad erheen. De vier governancerollen die de boom bewust weglaat
        # staan op de Roles-tab van die cirkel, onder "Core roles".
        + _side_item("/admin", "Admin")
        # ORGANISATIE ALS GEWOON NAV-ITEM (voorstel Stefan, 21 september 2026). Hij hing als
        # `<details class='c2-orgfly'>` onder de balk: een tweede uitklap-mechanisme naast de
        # panelen, op een plek waar je hem alleen vond door naar beneden te scrollen. Nu dezelfde
        # knop en dezelfde flyout als Projects en Messages toen nog hadden.
        + _side_item("/node", "Organization", "org")
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


