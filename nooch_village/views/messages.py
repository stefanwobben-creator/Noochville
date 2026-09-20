"""Messages — de gesprek-laag op één scherm (`/messages`, fase 8).

Drie soorten kanalen in één lijst, precies zoals het prototype ze toont: Projects, Circles,
Direct. Ze verschillen in waar ze over gaan, niet in wat ze zijn — één trail, één invoerveld.

WAT HIER NIET STAAT: je wachtrij. Die is `/inbox`, en dat blijft zo. Een kanaal is een gesprek dat
doorloopt; een inbox-item is werk dat afgehandeld moet worden. Ze op één scherm zetten maakt van de
338 open werk-items ruis in een chat, en van een chat een lijst die je moet bijhouden.

Hergebruikt het bestaande idioom: `.card`, `.c2-sec`, `.qadd-form`, `.fentry`-achtige regels. De
enige nieuwe familie is `msg-`, voor de tweekoloms-indeling (kanalenlijst links, draad rechts).
"""
from __future__ import annotations

from nooch_village import channels
from nooch_village.cockpit2_util import _DS_LINK, _nav, _name, _person_name, _stamp
from nooch_village.web_base import _e, _page, _banner


def _label(st, kanaal: str, ik: str = "") -> str:
    """De leesbare naam van een kanaal. Een DM heet naar de ANDER, niet naar het paar: je opent
    een gesprek met iemand, niet een gesprek tussen twee mensen van wie jij er een bent."""
    soort, doel = channels.soort_van(kanaal), channels.doel_van(kanaal)
    if soort == channels.PROJECT:
        p = st.projects.get(doel) or {}
        sc = p.get("scope")
        titel = sc if isinstance(sc, str) else (sc or {}).get("goal", "") if isinstance(sc, dict) else ""
        return titel or doel
    if soort == channels.CIRCLE:
        rec = st.records.get(doel)
        return _name(rec) if rec is not None else doel
    if soort == channels.TOPIC:
        return st.channels.naam_van(kanaal) or doel
    ander = next((x for x in channels.dm_leden(kanaal) if x != ik), "")
    return _person_name(st, ander) or ander or "direct"


#: Hoeveel projectkanalen er ZONDER zoekterm getoond worden. Op productie staan er 442, en die
#: lijst is geen lijst meer maar een muur — je scrolt langs honderden namen op zoek naar één.
#: Cirkels (20) en DM's blijven altijd compleet: die zijn op te overzien en je kiest er bewust een.
PROJECT_CAP = 25


def _laatst(st, kanaal: str) -> float:
    e = st.channels.laatste(kanaal)
    return float((e or {}).get("at") or 0)


def _kanalen(st, ik: str, q: str = "") -> tuple[dict[str, list[str]], dict[str, int]]:
    """De kanalen die deze mens ziet, per groep, plus per groep het TOTAAL vóór filteren.

    Projecten: die waar al een gesprek in staat — een leeg project-kanaal is geen gesprek maar een
    project, en dat staat op het bord. Cirkels: alle bestaande, ook lege, want een cirkelkanaal is
    een plek waar je iets kúnt zeggen. Direct: alleen de jouwe.

    Zonder zoekterm staan de projectkanalen op VOLGORDE VAN HET LAATSTE BERICHT en afgekapt op
    `PROJECT_CAP`. Alfabetisch afkappen zou willekeurig zijn; op recentheid afkappen laat precies
    zien waar het gesprek loopt. Mét zoekterm vervalt de cap — dan weet je wat je zoekt."""
    proj = [channels.project_kanaal(p["id"]) for p in st.projects.all()
            if (p.get("log") or []) and not p.get("archived")]
    cirk = [channels.circle_kanaal(r.id) for r in st.records.all()
            if not getattr(r, "archived", False) and getattr(r, "type", None)
            and str(getattr(r.type, "value", r.type)) == "circle"]
    dms = st.channels.kanalen_van(ik) if ik else []
    # Losse kanalen: ALLE, ook lege. Een kanaal dat je net hebt aangemaakt en niet ziet staan,
    # lijkt mislukt. En iedereen ziet ze allemaal — er is bewust geen lidmaatschap-begrip.
    onderwerpen = st.channels.topics()
    groepen = {"Projects": proj, "Circles": cirk, "Topics": onderwerpen, "Direct": dms}
    totaal = {g: len(r) for g, r in groepen.items()}

    naald = " ".join((q or "").split()).lower()
    if naald:
        groepen = {g: [k for k in r if naald in _label(st, k, ik).lower()]
                   for g, r in groepen.items()}
    else:
        groepen["Projects"] = sorted(proj, key=lambda k: -_laatst(st, k))[:PROJECT_CAP]
    return groepen, totaal


def _bericht(st, e: dict) -> str:
    a = e.get("author") or {}
    wie = (_person_name(st, a.get("id")) if a.get("type") in ("human", "person") else "") or "Someone"
    herk = ""
    h = e.get("herkomst") or {}
    if h.get("project"):
        p = st.projects.get(h["project"]) or {}
        sc = p.get("scope")
        titel = sc if isinstance(sc, str) else ""
        herk = (f"<span class='muted'> &middot; from project "
                f"<a href='/project?id={_e(h['project'])}'>{_e(titel or h['project'])}</a></span>")
    return (f"<div class='msg-item'><div class='msg-meta'>{_e(wie)} &middot; "
            f"{_e(_stamp(e.get('at')))}{herk}</div>"
            f"<div class='msg-text'>{_e(e.get('text') or '')}</div></div>")


def render_messages(st, *, ik: str = "", kanaal: str = "", csrf_token: str = "",
                    msg: str = "", q: str = "") -> str:
    groepen, totaal = _kanalen(st, ik, q)
    if not kanaal:
        # OPEN OP IETS DAT GEZEGD IS. De eerste versie pakte simpelweg het eerste kanaal, en dat
        # was de anchor-cirkel: je landde op "Nothing said here yet" terwijl er drie kanalen
        # verderop wél gesprek stond. Een leeg kanaal als voordeur laat het scherm dood lijken.
        # LET OP: `groepen` is hier al gefilterd en afgekapt. Voor de voordeur wil je juist het
        # volledige veld, anders hangt "waar land ik" af van een zoekterm.
        alles, _ = _kanalen(st, ik, "")
        volgorde = [k for g in ("Direct", "Topics", "Projects", "Circles") for k in alles[g]]
        kanaal = next((k for k in volgorde if st.channels.trail(k, limit=1)),
                      volgorde[0] if volgorde else "")

    # Het zoekveld is een GET-formulier en geen JS-filter: zo werkt hij zonder scripts, is de
    # uitkomst deelbaar als URL, en hoeven er geen 442 regels naar de browser die je toch verbergt.
    zoek = (f"<form class='msg-zoek' method='get' action='/messages'>"
            f"<input type='hidden' name='k' value='{_e(kanaal)}'>"
            f"<label class='att-lbl' for='msg-q'>Find a channel</label>"
            f"<input id='msg-q' type='search' name='q' value='{_e(q)}' "
            f"placeholder='Project, circle or person…'>"
            f"<div class='qadd-row'><button class='btn sm' type='submit'>Search</button>"
            + (f"<a class='flink' href='/messages?k={_e(kanaal)}'>clear</a>" if q else "")
            + "</div></form>")

    # Een kanaal beginnen. Tot 20 september kon dat niet: een kanaal bestond omdat zijn onderwerp
    # bestond (een project, een cirkel, een persoon). Dit is het eerste kanaal dat een mens zelf
    # maakt — zie `_act_topic_add` voor de poort en voor de herziening die eraan voorafging.
    nieuw = ""
    if csrf_token and ik:
        nieuw = (f"<details class='qadd'><summary class='muted'>＋ new channel</summary>"
                 f"<form method='post' action='/action' class='qadd-form'>"
                 f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                 f"<input type='hidden' name='next' value='/messages'>"
                 f"<label class='att-lbl' for='topic-naam'>Channel name</label>"
                 f"<input id='topic-naam' name='naam' maxlength='80' "
                 f"placeholder='Batch 4, Packaging, Trade fair…'>"
                 f"<div class='qadd-row'><button class='btn ok sm' type='submit' name='action' "
                 f"value='topic_add'>Create</button></div></form></details>")

    lijst = []
    for groep, rij in groepen.items():
        if not rij:
            continue
        aantal = ""
        if groep == "Projects" and not q and totaal[groep] > len(rij):
            aantal = (f" <span class='msg-telling'>{len(rij)} of {totaal[groep]} "
                      f"&middot; search for the rest</span>")
        elif q:
            aantal = f" <span class='msg-telling'>{len(rij)} of {totaal[groep]}</span>"
        lijst.append(f"<p class='muted msg-groep'>{_e(groep)}{aantal}</p>")
        for k in rij:
            aan = " on" if k == kanaal else ""
            qs = f"&q={_e(q)}" if q else ""
            lijst.append(f"<a class='msg-kanaal{aan}' href='/messages?k={_e(k)}{qs}'>"
                         f"{_e(_label(st, k, ik))}</a>")
    leeg = ("<p class='muted'>No channel matches that.</p>" if q
            else "<p class='muted'>No channels yet.</p>")
    nav = f"<nav class='msg-lijst'>{zoek}{nieuw}{''.join(lijst) or leeg}</nav>"

    trail = st.channels.trail(kanaal) if kanaal else []
    draad = "".join(_bericht(st, e) for e in trail) or (
        "<p class='muted'>Nothing said here yet.</p>" if kanaal else "")

    schrijf = ""
    if kanaal and csrf_token and ik:
        schrijf = (f"<form method='post' action='/action' class='qadd-form'>"
                   f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                   f"<input type='hidden' name='kanaal' value='{_e(kanaal)}'>"
                   f"<input type='hidden' name='next' value='/messages?k={_e(kanaal)}'>"
                   f"<label class='att-lbl' for='msg-tekst'>Write a message</label>"
                   f"<textarea id='msg-tekst' name='tekst' rows='2' "
                   f"placeholder='Write a reply, or ask a colleague to weigh in…'></textarea>"
                   f"<div class='qadd-row'><button class='btn ok sm' type='submit' name='action' "
                   f"value='msg_post'>Post</button></div></form>")
    elif kanaal and not ik:
        schrijf = ("<p class='muted'>Log in as a person to write here &mdash; a message needs an "
                   "author.</p>")

    kop = _e(_label(st, kanaal, ik)) if kanaal else "Messages"
    main = (f"<div class='c2-main'><h1>Messages</h1>"
            f"<p class='muted'>One channel type, four flavours: a project, a circle, a topic of "
            f"your own, or a person. "
            f"Your queue is on <a href='/inbox'>Inbox</a> &mdash; that is work to handle, not talk.</p>"
            f"{_banner(msg)}"
            f"<div class='msg-layout'>{nav}"
            f"<section class='msg-draad'><h2 class='msg-kop'>{kop}</h2>{draad}{schrijf}</section>"
            f"</div></div>")
    return _page("Messages", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
