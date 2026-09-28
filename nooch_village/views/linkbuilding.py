"""Linkbuilding — gidsen en lijstjes waar Nooch in vermeld wil worden (`/linkbuilding`).

WAT DIT SCHERM IS. Eén lijst doelwitten met hun prioriteit, en per regel twee knoppen: pitchen of
negeren. De prioriteit komt van de skill (een meting op de tekst van de gids: noemt hij je
concurrenten maar jou niet, dan is dat je sterkste pitch); het besluit komt van een mens.

WAT DIT SCHERM NIET IS. Geen restore van het scherm dat in #516 verdween. Dat draaide zijn
zoekopdracht synchroon en had geen opslag voor beslissingen. Dit volgt het patroon van
`/site-audit` (#634): een knop die een achtergrondthread start, een slot eromheen, een paneel dat
zichzelf ververst, en een spoor als het misgaat.

GEEN NIEUWE OPMAAK. `.card`, `.chip`, `.qadd-form`, `.cl-filter`, `.btn` en `_field()` bestaan
allemaal al; dit scherm zet ze in dezelfde volgorde neer als `/tools` en `/acties`.
"""
from __future__ import annotations

from nooch_village import linkbuilding as lb
from nooch_village.cockpit2_util import _DS_LINK, _age, _nav
from nooch_village.web_base import _e, _field, _page

#: De chip-variant per prioriteit. Kleur is nooit de enige drager: het WOORD staat er altijd bij —
#: dezelfde regel als bij de statusvormen van het designsysteem.
_PRIO_CHIP = {"hoog": "chip green", "midden": "chip amber",
              "laag": "chip muted", "onbekend": "chip muted"}
_PRIO_UITLEG = {
    "hoog": "mentions competitors but not Nooch — the strongest pitch",
    "midden": "no competitor mentioned, no Nooch either",
    "laag": "Nooch is already listed here",
    "onbekend": "the page could not be read",
}
_BESLUIT_LABEL = {"pursue": "to pitch", "ignore": "ignored"}

#: De rol die dit gereedschap draagt. Hij staat als sleutel in `_ROLE_TOOLS`; hier één keer als
#: constante, zodat de poort op het scherm en de kaart die ernaartoe wijst niet uit elkaar lopen.
MARKETING_LEAD = "mother_earth__nooch__marketing_lead"


def _rij(t: dict, csrf_token: str, mag: bool) -> str:
    """Eén doelwit: prioriteit, titel als link, herkomst, en wat je ermee kunt."""
    link = str(t.get("link") or "")
    prio = t.get("priority") or "onbekend"
    chip = (f"<span class='{_PRIO_CHIP.get(prio, 'chip muted')}' "
            f"title='{_e(_PRIO_UITLEG.get(prio, ''))}'>{_e(prio)}</span>")
    noemt = (f"<span class='muted'> &middot; mentions {_e(', '.join(t.get('mentions') or []))}</span>"
             if t.get("mentions") else "")
    snippet = (f"<div class='muted'>{_e(str(t.get('snippet') or '')[:220])}</div>"
               if t.get("snippet") else "")
    status = t.get("status") or "open"
    if status != "open":
        # AL BESLIST: wie en wanneer. Geen knoppen meer — het besluit staat, en opnieuw beslissen
        # is iets anders dan per ongeluk twee keer klikken.
        actie = (f"<span class='chip muted'>{_e(_BESLUIT_LABEL.get(status, status))}</span>"
                 f"<span class='muted'> by {_e(str(t.get('door') or 'someone'))} "
                 f"{_e(_age(t.get('besloten_op')))}</span>")
    elif mag and csrf_token:
        # TWEE KNOPPEN, ÉÉN FORMULIER: het besluit reist mee als veld, niet als twee formulieren
        # met elk hun eigen verborgen velden.
        actie = (f"<form method='post' action='/action' class='qadd-row'>"
                 f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                 f"<input type='hidden' name='link' value='{_e(link)}'>"
                 f"<input type='hidden' name='next' value='/linkbuilding'>"
                 f"<button class='btn ok sm' type='submit' name='besluit' value='pursue'>"
                 f"Pitch</button>"
                 f"<button class='btn sm' type='submit' name='besluit' value='ignore'>Ignore</button>"
                 f"<input type='hidden' name='action' value='linkbuilding_besluit'>"
                 f"</form>")
    else:
        actie = ""
    return (f"<div class='card'>"
            f"{chip} <a href='{_e(link)}' target='_blank' rel='noopener'>"
            f"<b>{_e(str(t.get('title') or link)[:140])}</b></a> "
            f"<span class='chip muted'>{_e(str(t.get('source') or ''))}</span>{noemt}"
            f"{snippet}{actie}</div>")


def paneel(st, context, data_dir: str, csrf_token: str = "", *, mag: bool = False) -> str:
    """De stand, de zoekknop en de lijst — als één fragment, zodat de poller het kan vervangen.

    DRIE TOESTANDEN, en ze lezen alle drie anders: er loopt een zoekopdracht · de vorige poging
    mislukte · vrij. Zelfde vorm als het scan-paneel van de site-audit, en om dezelfde reden: een
    achtergrondthread heeft geen scherm om op te vallen.

    HIJ RENDERT ZIJN EIGEN OMHULSEL met een vaste id; `nooch.js` vervangt precies dit element."""
    store = st.linktargets
    bezet = lb.slot(data_dir).staat()
    fout = lb.laatste_fout(data_dir)
    tel = store.telling()
    rijen = store.alle()

    sleutel = lb.sleutel_aanwezig(context)
    merken = lb.merken(context)
    # WAT DE ZOEKOPDRACHT NODIG HEEFT, vóór de knop en niet als foutmelding erna.
    waarschuwing = ""
    if not sleutel:
        waarschuwing += ("<div class='muted'>&#9888; no SerpAPI key configured "
                         "(<code>SERPAPI_API_KEY</code>) &mdash; searching is off until it is set.</div>")
    if not merken:
        waarschuwing += ("<div class='muted'>&#9888; no confirmed competitor brands yet. The search "
                         "still runs, but without brands it cannot tell a guide that lists your "
                         "competitors from one that lists nobody &mdash; so nothing will come back "
                         "as <b>hoog</b>.</div>")

    if bezet:
        kop = (f"<span class='chip amber'>searching&hellip;</span> "
               f"<span class='muted'>started {_e(_age(bezet.get('sinds')))} by "
               f"{_e(str(bezet.get('door') or 'someone'))} &middot; reading guide pages takes "
               f"20-60 seconds</span>")
    else:
        vorm = ""
        if mag and csrf_token and sleutel:
            # HET ONDERWERP IS EEN VELD, niet een aanname. De skill neemt payload > config en
            # weigert zichtbaar als er geen van beide is; dit veld is de payload-helft, en leeg
            # laten betekent "gebruik de staande `linkbuilding_query`".
            vorm = (f"<form method='post' action='/action' class='qadd-form'>"
                    f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                    f"<input type='hidden' name='action' value='linkbuilding_zoek'>"
                    f"<input type='hidden' name='next' value='/linkbuilding'>"
                    f"{_field('Topic', 'topic', fid='lb-topic', placeholder='e.g. best barefoot shoe brands')}"
                    f"<div class='muted'>Leave empty to use the standing "
                    f"<code>linkbuilding_query</code> from the config.</div>"
                    f"<div class='qadd-row'>"
                    f"<button class='btn ok sm' type='submit'>Find targets</button></div></form>")
        laatste = (f"<span class='muted'>{tel['open']} open &middot; {tel['pursue']} to pitch "
                   f"&middot; {tel['ignore']} ignored</span>" if rijen
                   else "<span class='muted'>No targets yet.</span>")
        kop = f"{laatste}{vorm}"
    melding = (f"<div class='muted'>&#9888; the last search failed "
               f"({_e(_age(fout.get('ts')))}): {_e(str(fout.get('fout') or ''))}</div>"
               if fout and not bezet else "")

    lijst = "".join(_rij(t, csrf_token, mag) for t in rijen)
    return (f"<div id='lb-paneel' aria-live='polite'>"
            f"<div class='card'>{kop}{waarschuwing}{melding}"
            f"<div class='muted'>Guides and listicles where Nooch could be mentioned. The priority "
            f"is measured on the page; pitching or ignoring is your call.</div></div>"
            f"{lijst}</div>")


def render_linkbuilding(st, context, data_dir: str, *, csrf_token: str = "",
                        username: str | None = None, msg: str = "") -> str:
    """Het scherm. Lezen is vrij; zoeken en beslissen is voor de Marketing Lead.

    DE POORT WORDT TWEE KEER GESTELD, hier en in de dispatch-takken — met dezelfde functie op
    dezelfde rol. Een knop tonen die de server daarna weigert is wat deze codebase elders al heeft
    opgeruimd."""
    from nooch_village.cockpit2 import _role_gate
    from nooch_village.views.overview import _banner

    mag = bool(csrf_token) and _role_gate(MARKETING_LEAD, username, st) is None
    main = (f"<div class='c2-main'><h1 class='ptitle'>Linkbuilding</h1>"
            f"<p class='muted'>Where Nooch wants to be mentioned &mdash; found with the "
            f"<code>linkbuilding_targets</code> skill, decided by you.</p>"
            f"{_banner(msg)}"
            # `data-poll` = de generieke poller uit `nooch.js`. Zonder hem blijft "searching…"
            # staan tot de lezer zelf ververst, en dan is de knop wél veilig maar de
            # terugkoppeling nutteloos.
            f"<div data-poll='/linkbuilding-status' data-poll-ms='5000'>"
            f"{paneel(st, context, data_dir, csrf_token if mag else '', mag=mag)}</div></div>")
    return _page("Linkbuilding", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
