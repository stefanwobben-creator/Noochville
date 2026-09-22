"""Messages — de gesprek-laag op één scherm (`/messages`, fase 8).

KANALEN ZIJN BEWUST (21 september 2026). Tot vandaag WAS elk project met een gesprek een kanaal:
123 op productie, plus 42 DM's. Dat is geen lijst maar een muur. De lijst heeft nu vier vaste
lagen — General (de wortelcirkel), één kanaal per open doel, losse kanalen, en je DM's — plus
Projects, en die vult je zelf door er een te openen of op te zoeken.

DE VERWIJZING NAAR `/inbox` IS WEG (21 september 2026). Die regel stond hier sinds fase 8 en
beloofde "je wachtrij staat op Inbox" — maar er is geen route `/inbox` in `do_GET`, geen
`views/inbox.py`, en de knop in de zijbalk riep een functie aan die niet bestaat. Een link naar
een 404, onder een alinea die uitlegt waarom het scherm hem niet zelf toont.

Hergebruikt het bestaande idioom: `.card`, `.c2-sec`, `.qadd-form`, `.fentry`-achtige regels. De
enige nieuwe familie is `msg-`, voor de tweekoloms-indeling (kanalenlijst links, draad rechts).
"""
from __future__ import annotations

import logging
import urllib.parse

from nooch_village import channels
from nooch_village.cockpit2_util import _DS_LINK, _nav, _name, _person_name, _stamp, _ICON_STICKER
from nooch_village.web_base import _e, _page, _banner

#: Hoe diep we per kanaal terugkijken voor de ongelezen-telling. De lijst toont hooguit "9+", dus
#: verder tellen verandert niets aan wat de lezer ziet — en het scheelt bij 442 kanalen een hoop
#: werk per pageload. Wie een kanaal een jaar niet opende krijgt "9+", en dat is het juiste antwoord.
_ONGELEZEN_CAP = 50


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
        # De WORTELCIRKEL heet "General" en niet "Mother Earth". Dit is het kanaal van het hele
        # dorp; wie hem opzoekt zoekt "algemeen", niet de naam van de cirkel die toevallig bovenaan
        # staat. De cirkel zelf houdt zijn naam overal elders.
        wortel = st.records.root()
        if wortel is not None and doel == wortel.id:
            return "General"
        rec = st.records.get(doel)
        return _name(rec) if rec is not None else doel
    if soort == channels.GOAL:
        d = st.doelen.get(doel)
        # Het LABEL, want dat is wat Projects ook toont (WEBSITE, STCB, MITH…). De volledige titel
        # staat op /goals; hier moet hij naast een tijd en een teller passen.
        return (d or {}).get("label") or (d or {}).get("titel") or doel
    if soort == channels.TOPIC:
        return st.channels.naam_van(kanaal) or doel
    leden = channels.dm_leden(kanaal)
    # EEN KANAAL MET JEZELF BESTAAT ECHT. Op prod is er één (`dm:<stefan>|<stefan>`): notificaties
    # waarvan de afzender dezelfde mens is als de vervuller van de doelrol — jij die je eigen rol
    # aanspreekt. Zonder deze regel heet dat kanaal "direct", net als elk ander naamloos kanaal.
    if leden and len(set(leden)) == 1:
        return "Yourself"
    ander = next((x for x in leden if x != ik), "")
    naam = _person_name(st, ander)
    if naam:
        return naam
    # De tegenpartij is geen persoon. Sinds de inbox-migratie kan dat: een gesignaleerd bericht
    # draagt de ROL of het systeem dat het stuurde als tegenpartij. Toon dan de rolnaam, en anders
    # de ruwe id — nooit "direct", want dan lijken twintig kanalen op elkaar.
    rec = st.records.get(ander) if ander else None
    return (_name(rec) if rec is not None else "") or ander or "direct"


def mag_project_lezen(st, pid: str, ik: str) -> bool:
    """Mag deze mens dit project zien?

    `private` betekent "alleen voor deze cirkel" (zie de knop op de projectkaart), dus dat is de
    vraag die hier gesteld wordt: ben je lid van de cirkel van de eigenaar-rol. Een niet-privé
    project is voor iedereen die is ingelogd, zoals het bord dat ook toont.

    Fail-closed: onbekend project of onbekende mens → nee."""
    from nooch_village.cockpit2 import resolve_circle_id, is_circle_member
    p = st.projects.get(pid or "")
    if p is None or not ik:
        return False
    if not p.get("private"):
        return True
    cid = resolve_circle_id(p.get("owner") or "", st.records)
    return bool(cid) and is_circle_member(ik, cid, st.records, st.assign)


def mag_kanaal_lezen(st, kanaal: str, ik: str) -> bool:
    """Mag deze mens dit kanaal lezen? ÉÉN regel, en alles wat een bijlage serveert vraagt hem.

    De soorten volgen precies de lijst die `_kanalen` toont:

        dm:       alleen de twee deelnemers — zoals `kanalen_van` al bepaalt
        project:  het leesrecht van dat project (privé = alleen die cirkel)
        circle:   iedereen die is ingelogd
        goal:     idem
        topic:    idem — er is bewust geen lidmaatschap-begrip op losse kanalen

    WAAROM DIT BESTAAT EN NIET "HET PAD RAADT NIEMAND". Een bijlage-URL mag geen sleutel zijn:
    wie de link doorstuurt hoort geen toegang weg te geven, de ontvanger moet door dezelfde poort.
    Daarom een route die eerst vraagt en dan pas leest, in plaats van een statisch pad.

    Fail-closed op een onbekende soort: liever niets serveren dan gokken."""
    if not ik or not kanaal:
        return False
    soort = channels.soort_van(kanaal)
    if soort == channels.DM:
        return ik in channels.dm_leden(kanaal)
    if soort == channels.PROJECT:
        return mag_project_lezen(st, channels.doel_van(kanaal), ik)
    return soort in (channels.CIRCLE, channels.GOAL, channels.TOPIC)


def kan_antwoorden(st, kanaal: str, ik: str = "") -> bool:
    """Mag er in dit kanaal geschreven worden?

    Alleen als de tegenpartij van een DM een BESTAANDE PERSOON is. Bij 333 van de 338 gemigreerde
    inbox-berichten is de afzender een rol- of systeemnaam (`compliance`, `claims-checker`, …), en
    die leest geen berichten. Een antwoordveld dat niets bereikt is erger dan geen antwoordveld —
    dat is het dead-letter-patroon dat in dit dorp al eens is vastgelegd."""
    if channels.soort_van(kanaal) != channels.DM:
        return True
    leden = channels.dm_leden(kanaal)
    if leden and len(set(leden)) == 1:
        return True          # je eigen kanaal: notities aan jezelf mogen gewoon
    ander = next((x for x in leden if x != ik), "")
    return bool(ander) and st.people.get(ander) is not None


# HIER STOND `PROJECT_CAP = 25`: hoeveel projectkanalen er zonder zoekterm getoond werden. Die cap
# is op 21 september 2026 niet verhoogd maar VERVANGEN. Hij liet je nog steeds langs namen scrollen
# die je niet zocht — hij maakte het probleem zichtbaar ("25 of 159 · search for the rest") zonder
# het op te lossen. Een project staat nu in je lijst omdat jij het hebt toegevoegd, en anders niet.


def _laatst(st, kanaal: str) -> float:
    e = st.channels.laatste(kanaal)
    return float((e or {}).get("at") or 0)


def _kort_tijd(at: float, nu: float | None = None) -> str:
    """Wanneer er voor het laatst iets gezegd is, in maximaal vier tekens (fase 11, 3b).

    WAAROM NIET `_stamp`. Die geeft een volledige datum-tijd, en dat past niet in een rij van
    210px naast een naam en een ongelezen-teller — dan valt de naam weg, en de naam is waarop je
    zoekt. Vandaag toont de klok, deze week de dag, daarvoor de datum: hoe ouder, hoe grover, want
    bij iets van vorige maand is het uur niet meer de vraag.

    Leeg bij 0: een kanaal waarin nog nooit iets is gezegd heeft geen tijdstip, en "01 Jan 1970"
    is geen tijdstip maar een bug die eruitziet als data."""
    import time as _t
    if not at:
        return ""
    nu = _t.time() if nu is None else nu
    verschil = nu - at
    lok = _t.localtime(at)
    if verschil < 0 or verschil >= 365 * 24 * 3600:
        return _t.strftime("%d/%m/%y", lok)
    if verschil < 12 * 3600 and _t.localtime(nu).tm_yday == lok.tm_yday:
        return _t.strftime("%H:%M", lok)
    if verschil < 7 * 24 * 3600:
        return _t.strftime("%a", lok)
    return _t.strftime("%d %b", lok)


def _wortelkanaal(st) -> str:
    """Het kanaal van de wortelcirkel — "General" op het scherm. Leeg als er geen wortel is."""
    wortel = st.records.root()
    return channels.circle_kanaal(wortel.id) if wortel is not None else ""


def _doelkanalen(st) -> list[str]:
    """Eén kanaal per OPEN doel, in de volgorde die Projects ook aanhoudt.

    Deze staan er altijd, zonder dat iemand ze aanmaakt: de doel-taxonomie bestaat al als
    eersteklas begrip (`data/doelen.json`, de filterbalk boven het bord), dus een kanaal per doel
    is geen nieuw concept maar dezelfde indeling op een tweede plek. Een gesloten doel valt vanzelf
    uit de lijst; zijn gesprek blijft bestaan en is via zoeken terug te vinden."""
    return [channels.goal_kanaal(d["id"]) for d in st.doelen.all()
            if d.get("status") == "open"]


def _projectkanalen_met_gesprek(st) -> list[str]:
    return [channels.project_kanaal(p["id"]) for p in st.projects.all()
            if (p.get("log") or []) and not p.get("archived")]


def _is_mens(st, wie: str) -> bool:
    """Is deze tegenpartij een MENS uit de people-store?

    OP ID, NAAM ÉN E-MAIL, en dat is geen slordigheid maar precies het geval dat overblijft. De
    meeste DM-kanalen dragen een persoon-id aan beide kanten; een handvol draagt een NAAM
    ("Stefan Wobben") of een e-mailadres ("stefan@nooch.earth") als afzender — overblijfsels van
    de inbox-migratie. Die horen bij een mens en niet bij een rol, en ze op id alleen beoordelen
    zou ze bij het systeem zetten.

    Alles wat hier niet doorheen komt is een rol of een systeemnaam (`compliance`, `dialoog`,
    `claims-checker`, `Lara the Librarian`): die leest de berichten niet, en daar hoort een eigen
    groep bij."""
    if not wie:
        return False
    if st.people.get(wie) is not None:
        return True
    sleutel = wie.strip().casefold()
    return any(sleutel in ((p.name or "").strip().casefold(),
                           (p.email or "").strip().casefold())
               for p in st.people.all())


def _dm_groepen(st, ik: str) -> tuple[list, list]:
    """De DM-kanalen van deze mens, gesplitst in (echte gesprekken, rol- en systeemafzenders).

    WAAROM DIT EEN WEERGAVE IS EN GEEN MIGRATIE. Er lag een voorstel voor een vijfde kanaalsoort
    `role:<record_id>`, en dat is in dezelfde implementatiebrief weer INGETROKKEN: "vervalt, niet
    meer nodig nu er altijd een mens (rolvervuller of Stefan) als DM-ontvanger is". Dat argument
    staat nog; wat er nog wél mis is, is dat 37 rol-afzenders tussen twee echte gesprekken staan.
    Dat is een LIJST-probleem, en het wordt hier opgelost waar het zit — zonder één kanaal-id te
    verplaatsen, dus zonder migratie en zonder kans op verlies.

    Een gesprek met jezelf blijft Direct: dat is een notitie aan jezelf, geen systeemafzender."""
    uit_direct, uit_rollen = [], []
    for k in (st.channels.kanalen_van(ik) if ik else []):
        leden = channels.dm_leden(k)
        if leden and len(set(leden)) == 1:
            uit_direct.append(k)
            continue
        (uit_direct if all(_is_mens(st, x) for x in leden) else uit_rollen).append(k)
    return uit_direct, uit_rollen


def _kanalen(st, ik: str, q: str = "") -> tuple[dict[str, list[str]], dict[str, int], set[str]]:
    """De kanalen die deze mens ziet, per groep, plus per groep het TOTAAL en welke hij volgt.

    WAT HIER OP 21 SEPTEMBER 2026 IS VERVANGEN, en waarom het geen aanscherping van het oude model
    is. Elk project met een gesprek WAS een kanaal: 123 op productie, plus 42 DM's. Die lijst was
    geen lijst maar een muur, en de cap van 25 ("25 of 159 · search for the rest") maakte dat
    zichtbaar zonder het op te lossen — je scrolde nog steeds langs namen die je niet zocht.

    Nu zijn kanalen BEWUST (besluit Stefan). De lijst heeft vier vaste lagen en één die je zelf
    vult:

        General    het kanaal van de wortelcirkel — het hele dorp, altijd zichtbaar
        Goals      één per open doel; dezelfde taxonomie die het bord al gebruikt
        Channels   losse kanalen die een mens aanmaakt (+ new channel)
        Projects   ALLEEN wat jij volgt; leeg tot je iets toevoegt
        Direct     ongewijzigd

    DE ANDERE CIRKELS HEBBEN GEEN EIGEN RIJ MEER. Er zijn er twee (Mother Earth en Nooch) en de
    tweede is nog leeg; die valt samen met General tot de cirkel actief wordt (besluit Stefan).
    "Actief" is hier geen code-wijziging maar een VERGELIJKING: zodra er iets in zo'n kanaal staat,
    verschijnt hij onder Channels. Zo kan een gesprek nooit onbereikbaar worden doordat een lijst
    hem niet noemt — dezelfde regel als bij `wiki.grond_status`, die ook bij het lezen wordt
    uitgerekend in plaats van opgeslagen.

    ZOEKEN ZIET ALLES. Mét zoekterm komen ook de projectkanalen die je NIET volgt terug, want
    anders is een project dat je nog niet hebt toegevoegd onvindbaar — en dat is precies de enige
    manier waarop deze wijziging iets kapot zou maken."""
    gevolgd = set(st.people.gevolgd(ik)) if ik else set()

    alg = [k for k in (_wortelkanaal(st),) if k]
    doelen = _doelkanalen(st)
    # Losse kanalen: ALLE, ook lege. Een kanaal dat je net hebt aangemaakt en niet ziet staan,
    # lijkt mislukt. Plus de cirkelkanalen die niet General zijn én waar iets in staat.
    wortel = _wortelkanaal(st)
    andere_cirkels = [k for k in st.channels.bestaande(channels.CIRCLE) if k != wortel]
    onderwerpen = st.channels.topics() + andere_cirkels
    projecten_alles = _projectkanalen_met_gesprek(st)
    projecten = [k for k in projecten_alles if k in gevolgd]
    dms, _rollen = _dm_groepen(st, ik)

    # "ROLES & SYSTEM" STOND HIER ALS GROEP, en is op 22 september 2026 uit de lijst gehaald (eis
    # Stefan). VERBERGEN, NIET WISSEN: `_dm_groepen` blijft ze afsplitsen — dat is wat ze uit
    # Direct houdt — en de kanalen, hun berichten en hun bijlagen staan onveranderd in
    # `channels.json`. Wie een link heeft komt er nog gewoon in; `mag_kanaal_lezen` is
    # ongewijzigd. Wat verdwijnt is de 31 regels ruis boven je twee echte gesprekken.
    groepen = {"General": alg, "Goals": doelen, "Channels": onderwerpen,
               "Projects": projecten, "Direct": dms}
    totaal = {g: len(r) for g, r in groepen.items()}
    totaal["Projects"] = len(projecten_alles)      # "3 of 123" — wat je volgt van wat er is

    naald = " ".join((q or "").split()).lower()
    if naald:
        groepen["Projects"] = projecten_alles      # zoeken ziet ook wat je niet volgt
        groepen = {g: [k for k in r if naald in _label(st, k, ik).lower()]
                   for g, r in groepen.items()}
    else:
        # Op volgorde van het laatste bericht: dan staat bovenaan waar het gesprek loopt.
        groepen["Projects"] = sorted(projecten, key=lambda k: -_laatst(st, k))
    return groepen, totaal, gevolgd


def _bijlagen_html(e: dict, kanaal: str) -> str:
    """De bestanden onder een bericht. Een afbeelding als voorbeeld, de rest als regel met naam.

    DE LINK GAAT NAAR `/bijlage?kanaal=…`, niet naar een pad op schijf. Dat is het hele punt van
    die route: hij vraagt eerst of jij dit kanaal mag lezen. Een statisch pad zou de URL tot
    sleutel maken, en dan geeft doorsturen toegang weg."""
    rijen = []
    for b in (e.get("bijlagen") or []):
        url = (f"/bijlage?kanaal={urllib.parse.quote(kanaal)}"
               f"&id={urllib.parse.quote(str(b.get('id') or ''))}")
        naam = str(b.get("name") or "bestand")
        kb = int(b.get("size") or 0) // 1024
        if str(b.get("mime") or "").startswith("image/"):
            # EEN STICKER IS GEEN BIJLAGE-MET-EEN-PLAATJE. Hij staat kleiner en zonder kader: een
            # rand om een doorzichtige sticker tekent een vierkant dat er niet is. Het onderscheid
            # staat in de META (`soort`) en niet in een gok op het pad, want een Giphy-sticker
            # woont in dezelfde map als een geüploade foto.
            extra = " msg-bijlage--sticker" if b.get("soort") == "sticker" else ""
            rijen.append(f"<a class='msg-bijlage msg-bijlage--beeld{extra}' href='{_e(url)}' "
                         f"target='_blank' rel='noopener'>"
                         f"<img src='{_e(url)}' alt='{_e(naam)}' loading='lazy'></a>")
        else:
            rijen.append(f"<a class='msg-bijlage' href='{_e(url)}'>"
                         f"<span class='msg-bijlage-naam'>{_e(naam)}</span>"
                         f"<span class='muted'>{kb} kB</span></a>")
    return f"<div class='msg-bijlagen'>{''.join(rijen)}</div>" if rijen else ""


def _bericht(st, e: dict, kanaal: str = "", csrf_token: str = "") -> str:
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
    # REACTIES: HETZELFDE COMPONENT ALS DE PROJECTFEED, niet een tweede versie ervan. `reactie_blok`
    # is uit `_feed_entry_html` gelicht toen dit scherm het ook nodig had; zou Messages zijn eigen
    # emoji-lijst en eigen kiezer krijgen, dan is de ene lijst na één wijziging langer dan de
    # andere zonder dat iemand het merkt.
    from nooch_village.views.feed import reactie_blok
    rx, picker = reactie_blok(e, csrf_token, {"kanaal": kanaal}) if kanaal else ("", "")
    voet = f"<div class='msg-reacties'>{rx}{picker}</div>" if (rx or picker) else ""
    voet = _bijlagen_html(e, kanaal) + voet
    return (f"<div class='msg-item'><div class='msg-meta'>{_e(wie)} &middot; "
            f"{_e(_stamp(e.get('at')))}{herk}</div>"
            f"<div class='msg-text'>{_e(e.get('text') or '')}</div>{voet}</div>")


def _sticker_kiezer(kanaal: str, csrf_token: str) -> str:
    """De stickerkiezer onder het schrijfveld: de vaste rij, en daaronder een zoekveld.

    HETZELFDE POPUP-RECEPT ALS DE REACTIE-KIEZER — `<details class='emoji-pick'>` met een
    `.emoji-pop` eronder, en de stickers in een `.emo-grid` net als de emoji's. Geen nieuwe
    familie dus, en dezelfde declaraties die de @-lijst ook al deelt. Eén knop per sticker is
    één formulier, precies zoals `reactie_blok` het met emoji's doet: zo werkt de vaste rij
    ZONDER JavaScript.

    Het zoekveld doet dat niet, en dat is het verschil tussen de twee helften: de vaste rij is
    HTML die er al staat, de Giphy-treffers komen per toetsaanslag van de server. Valt Giphy
    weg, dan blijft het bovenste deel gewoon werken en vindt het onderste niets — dat is de
    fail-soft-eis, hier zichtbaar als twee losse helften in plaats van één lijst.

    ER REIST GEEN URL MEE, alleen het Giphy-id. Wat de server ophaalt hoort de server te
    bepalen; zie `giphy.haal`."""
    from nooch_village.cockpit2 import STICKERS_PICKER
    knoppen = "".join(
        f"<form method='post' action='/action' class='emo-f'>"
        f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
        f"<input type='hidden' name='kanaal' value='{_e(kanaal)}'>"
        f"<input type='hidden' name='next' value='/messages?k={_e(kanaal)}'>"
        f"<input type='hidden' name='naam' value='{_e(naam)}'>"
        f"<button class='emo' type='submit' name='action' value='sticker_post' "
        f"title='{_e(naam[:-4].replace('-', ' '))}'>"
        f"<img src='/static/stickers/{_e(naam)}' alt='{_e(naam[:-4].replace('-', ' '))}' "
        f"loading='lazy'></button></form>"
        for naam in STICKERS_PICKER)
    return (f"<details class='emoji-pick'>"
            f"<summary class='emoji-add' title='sticker' aria-label='add sticker'>"
            f"{_ICON_STICKER}</summary>"
            f"<div class='emoji-pop emo-st' data-giphy data-kanaal='{_e(kanaal)}' "
            f"data-csrf='{_e(csrf_token)}'>"
            f"<div class='emo-grid'>{knoppen}</div>"
            f"<input class='emo-search' type='search' data-giphy-q "
            f"placeholder='Search Nooch stickers…' aria-label='Search Nooch stickers'>"
            f"<div class='emo-grid' data-giphy-uit></div>"
            f"</div></details>")


def render_messages(st, *, ik: str = "", kanaal: str = "", csrf_token: str = "",
                    msg: str = "", q: str = "", lijst: bool = False, wie: str = "") -> str:
    """Het Messages-scherm. `lijst=True` is de MOBIELE kanalenlijst (drill-down, niveau 2).

    DRILL-DOWN IS EEN CSS-KEUZE, GEEN TWEEDE RENDERING. Beide panelen staan altijd in de DOM; op
    een telefoon toont `data-mob` er één. Zo blijft er één weergave om te onderhouden, werkt de
    terug-pijl zonder JS, en is elke stand een deelbare URL — hetzelfde uitgangspunt als het
    zoekveld hieronder, dat bewust een GET-formulier is en geen JS-filter."""
    groepen, totaal, gevolgd = _kanalen(st, ik, q)
    if not kanaal:
        # OPEN OP IETS DAT GEZEGD IS. De eerste versie pakte simpelweg het eerste kanaal, en dat
        # was de anchor-cirkel: je landde op "Nothing said here yet" terwijl er drie kanalen
        # verderop wél gesprek stond. Een leeg kanaal als voordeur laat het scherm dood lijken.
        # LET OP: `groepen` is hier al gefilterd. Voor de voordeur wil je juist het volledige veld,
        # anders hangt "waar land ik" af van een zoekterm.
        alles, _t, _g = _kanalen(st, ik, "")
        # DE VOORDEUR IS GENERAL, altijd (besluit Stefan, 21 september 2026).
        #
        # HIER STOND "open op iets dat gezegd is", in de volgorde Direct → Projects → Goals →
        # Channels → General. Dat klonk goed — een leeg kanaal als voordeur laat het scherm dood
        # lijken — maar Direct staat vooraan en `kanalen_van` sorteert op kanaal-id. Op productie
        # landde je daardoor in `dm:Candy Cotton|…`: een willekeurige DM, alfabetisch eerste van de
        # 35 die allemaal een bericht hadden. Gemeten bij een klik-doorloop, niet beredeneerd.
        #
        # "Meest recent actief" lost dat niet op: dat kan net zo goed weer een DM zijn. Ongevraagd
        # in andermans privégesprek landen is het probleem, niet welk gesprek precies. General is
        # in dit hele traject de voordeur van het dorp — dan hoort de landing dat ook te zijn.
        volgorde = [k for g in ("General", "Goals", "Channels", "Projects", "Direct")
                    for k in alles[g]]
        kanaal = volgorde[0] if volgorde else ""

    # OPENEN IS TOEVOEGEN (besluit Stefan). Een projectkanaal dat je opent hoort daarna in je
    # lijst te staan; anders moet je hem elke keer opnieuw opzoeken en is "toevoegen" een tweede
    # handeling voor iets wat je met je klik al zei. De andere soorten staan er sowieso, dus die
    # hoeven niet gevolgd te worden.
    if ik and kanaal and channels.soort_van(kanaal) == channels.PROJECT and not lijst:
        if st.people.volg(ik, kanaal):
            groepen, totaal, gevolgd = _kanalen(st, ik, q)

    # ── ongelezen: een VERGELIJKING, geen opgeslagen vlag ────────────────────
    #
    # Per kanaal: hoeveel berichten kwamen er ná het moment dat deze mens het kanaal voor het laatst
    # opende, en niet van hemzelf. Dat laatste is de helft die je makkelijk vergeet — je eigen
    # bericht als "ongelezen" tonen maakt de indicator meteen onbetrouwbaar, en een indicator die
    # er één keer naast zit kijk je daarna niet meer aan.
    #
    # Het kanaal dat je NU opent markeren we hieronder pas, ná het tellen: anders staat het nooit
    # als ongelezen in de lijst waar je het net in aanklikte, en zie je nooit wat je zojuist opende.
    ongelezen: dict = {}
    if ik:
        gz = st.people.gezien(ik)
        for groep_rij in groepen.values():
            for k in groep_rij:
                sinds = float(gz.get(k) or 0)
                n = 0
                for e in st.channels.trail(k, limit=_ONGELEZEN_CAP):
                    if float(e.get("at") or 0) <= sinds:
                        continue
                    if (e.get("author") or {}).get("id") == ik:
                        continue                       # je eigen woorden zijn niet nieuw voor jou
                    n += 1
                if n:
                    ongelezen[k] = n

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

    # EEN GESPREK BEGINNEN DAT NOG NIET BESTAAT. Tot nu kon een DM pas gevonden worden nadat er
    # al een bericht in stond: `kanalen_van` leest `channels.json`, en daar staat niets tot iemand
    # iets zegt. Wie het eerste bericht wilde sturen had dus geen ingang.
    #
    # DEZELFDE BRON ALS DE GLOBALE ZOEK, letterlijk: `search._people`. Een eigen personenlijst hier
    # zou een tweede antwoord geven op "wie werkt hier" zodra er aan één iets verandert.
    #
    # DUS OOK DEZELFDE BEPERKING: die functie matcht op NAAM, niet op e-mailadres. Het veld belooft
    # daarom ook alleen een naam. Zou ik hier wél op e-mail zoeken, dan geeft dit veld treffers die
    # de globale zoek niet geeft — en dan is "dezelfde bron" een halve waarheid. Moet e-mail erbij,
    # dan hoort dat in `_people` en dus op beide plekken tegelijk.
    nieuw_dm = ""
    if csrf_token and ik:
        rijen_p = []
        if wie.strip():
            from nooch_village.views.search import _people
            termen = [t for t in wie.lower().split() if t]
            for h in _people(st, termen):
                pid = h.get("id") or ""
                if not pid or pid == ik:
                    continue                      # jezelf staat al als "Yourself" in de lijst
                k = channels.dm_kanaal(ik, pid)
                rijen_p.append(f"<a class='msg-kanaal' href='/messages?k={_e(k)}'>"
                               f"<span class='msg-knaam'>{_e(h.get('titel') or pid)}</span></a>")
            if not rijen_p:
                rijen_p.append("<p class='muted msg-leeg'>Nobody by that name.</p>")
        nieuw_dm = (f"<details class='qadd msg-nieuw-dm'{' open' if wie.strip() else ''}>"
                    f"<summary class='muted'>＋ new conversation</summary>"
                    f"<form method='get' action='/messages'>"
                    f"<input type='hidden' name='k' value='{_e(kanaal)}'>"
                    f"<label class='att-lbl' for='msg-wie'>Who do you want to write to?</label>"
                    f"<input id='msg-wie' type='search' name='wie' value='{_e(wie)}' "
                    f"placeholder='Name…'>"
                    f"<div class='qadd-row'><button class='btn sm' type='submit'>Find</button>"
                    + (f"<a class='flink' href='/messages?k={_e(kanaal)}'>clear</a>" if wie else "")
                    + f"</div></form>{''.join(rijen_p)}</details>")

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

    # `rijen`, NIET `lijst`: die naam is sinds fase 11 de parameter die de mobiele drill-down-stand
    # draagt. De eerste versie hergebruikte hem hier en overschreef dus zijn eigen argument — het
    # scherm stond daarna altijd in lijst-stand, en markeerde daardoor nooit meer iets als gelezen.
    rijen = []
    for groep, rij in groepen.items():
        if not rij:
            continue
        aantal = ""
        if groep == "Projects" and not q and totaal[groep] > len(rij):
            # "3 of 123" leest nu anders dan hiervoor: wat JIJ volgt, van wat er bestaat. De
            # oude tekst ("search for the rest") suggereerde dat de lijst afgekapt was; hij is
            # niet afgekapt, hij is van jou.
            aantal = (f" <span class='msg-telling'>{len(rij)} of {totaal[groep]} "
                      f"&middot; search to add more</span>")
        elif q:
            aantal = f" <span class='msg-telling'>{len(rij)} of {totaal[groep]}</span>"
        rijen.append(f"<p class='muted msg-groep'>{_e(groep)}{aantal}</p>")
        for k in rij:
            aan = " on" if k == kanaal else ""
            qs = f"&q={_e(q)}" if q else ""
            n = ongelezen.get(k, 0)
            merk = " msg-kanaal--nieuw" if n else ""
            stip = f"<span class='msg-nieuw'>{n if n < 10 else '9+'}</span>" if n else ""
            # DRIE DELEN, VASTE VOLGORDE (fase 11, 3b): naam, wanneer, hoeveel nieuw. De naam mag
            # afkappen (daar is hij het breedst en het minst kritisch), de andere twee nooit — een
            # afgekapte teller of tijd is erger dan geen.
            tijd = _kort_tijd(_laatst(st, k))
            klok = f"<span class='msg-tijd'>{_e(tijd)}</span>" if tijd else ""
            # NIET-GEVOLGD IS EEN EIGEN TOESTAND, GEEN AFWEZIGHEID. Bij het zoeken staan er
            # projectkanalen tussen die je (nog) niet volgt; zonder merkteken zie je niet welke
            # van de treffers al van jou is en welke je zou toevoegen. Twee dragers, want kleur
            # alleen is nooit genoeg: een gestippelde rand én het woord "add".
            nieuw_voor_jou = (groep == "Projects" and ik and k not in gevolgd)
            merk += " msg-kanaal--vreemd" if nieuw_voor_jou else ""
            toevoeg = (f"<span class='msg-add' aria-hidden='true'>+ add</span>"
                       if nieuw_voor_jou else "")
            rijen.append(f"<a class='msg-kanaal{aan}{merk}' href='/messages?k={_e(k)}{qs}'>"
                         f"<span class='msg-knaam'>{_e(_label(st, k, ik))}</span>"
                         f"{toevoeg}{klok}{stip}</a>")
    leeg = ("<p class='muted'>No channel matches that.</p>" if q
            else "<p class='muted'>No channels yet.</p>")
    nav = f"<nav class='msg-lijst'>{zoek}{nieuw_dm}{nieuw}{''.join(rijen) or leeg}</nav>"

    # HET OPENEN IS HET LEZEN. Geen aparte "markeer als gelezen"-knop: dat is een tweede handeling
    # voor iets wat je met je ogen al deed, en hij loopt gegarandeerd achter op de werkelijkheid.
    # Fail-soft: lukt het markeren niet, dan blijft het kanaal ongelezen staan — vervelend, maar de
    # andere kant (stil op gelezen zetten wat je niet zag) is erger.
    trail = st.channels.trail(kanaal) if kanaal else []
    # NIET IN DE LIJST-STAND. "Het openen is het lezen" klopt alleen als je het gesprek ook ZIET;
    # op een telefoon toont de lijst-stand juist de kanalenlijst, met de draad verborgen. Zonder
    # deze voorwaarde markeert het openen van de lijst het kanaal dat toevallig als voordeur is
    # gekozen als gelezen — en dan is het ongelezen-merk weg voor iets dat niemand las.
    if ik and kanaal and not lijst:
        laatste = trail[-1] if trail else None
        if laatste is not None:
            try:
                st.people.markeer_gezien(ik, kanaal, float(laatste.get("at") or 0))
            except Exception:                          # noqa: BLE001
                logging.getLogger("village.messages").debug(
                    "gezien-stand niet bijgewerkt", exc_info=True)
    draad = "".join(_bericht(st, e, kanaal, csrf_token) for e in trail) or (
        "<p class='muted'>Nothing said here yet.</p>" if kanaal else "")

    schrijf = ""
    if kanaal and not kan_antwoorden(st, kanaal, ik):
        schrijf = ("<p class='muted'>No reply box: the other side of this channel is a role, not a "
                   "person, and a role does not read messages. Need something done? Start a "
                   "project or write to the person who fills the role.</p>")
    elif kanaal and csrf_token and ik:
        # DE PAPERCLIP VOLGT HET ANTWOORDVELD, één voorwaarde. Hij staat in dezelfde tak, dus er
        # is geen tweede regel die kan gaan afwijken: waar je niet kunt schrijven, kun je ook
        # niets bijvoegen.
        #
        # EIGEN FORMULIER, want dit is `multipart/form-data` en het antwoordveld is dat niet. Eén
        # ronde: het bericht wordt hier geplaatst en het bestand hangt er direct aan.
        bijlage_form = (
            f"<details class='qadd msg-bijlage-add'>"
            f"<summary class='muted'>📎 attach a file</summary>"
            f"<form method='post' action='/action' class='qadd-form' "
            f"enctype='multipart/form-data'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"<input type='hidden' name='kanaal' value='{_e(kanaal)}'>"
            f"<input type='hidden' name='next' value='/messages?k={_e(kanaal)}'>"
            f"<input type='hidden' name='action' value='kanaal_bijlage'>"
            f"<label class='att-lbl' for='msg-file'>File</label>"
            f"<input id='msg-file' type='file' name='file' required "
            f"accept='{_e(','.join(sorted(channels.BIJLAGE_TYPES)))}'>"
            f"<label class='att-lbl' for='msg-file-tekst'>Caption (optional)</label>"
            f"<input id='msg-file-tekst' name='tekst' maxlength='200' "
            f"placeholder='What is this?'>"
            f"<div class='qadd-row'><button class='btn ok sm' type='submit'>Upload</button>"
            f"<span class='muted'>max 20 MB &middot; image, pdf, txt, csv, docx, xlsx, pptx</span>"
            f"</div></form></details>")
        # GEREEDSCHAP BOVEN HET VELD, EN BUITEN HET SCHRIJFFORMULIER. Allebei dragen ze hun
        # eigen <form> (de paperclip post multipart, elke sticker post zijn eigen naam), en een
        # <form> in een <form> is geen HTML: de browser gooit de binnenste weg en je klikt op
        # een knop die niets doet. Vandaar één `.qadd-row` ernaast in plaats van erin — geen
        # nieuwe klasse, dezelfde rij die overal de knoppen naast elkaar zet.
        gereedschap = (f"<div class='qadd-row'>{bijlage_form}"
                       f"{_sticker_kiezer(kanaal, csrf_token)}</div>")
        # ONDER HET VELD, NIET ERBOVEN. De kiezer klapt naar beneden open (`.emoji-pop` hangt
        # onder zijn knop); staat de rij bovenaan, dan legt hij zich over het tekstvak waar je
        # net in typte. Onderaan klapt hij open in de lege ruimte eronder — en het is meteen de
        # plek waar een chatbalk zijn gereedschap heeft.
        schrijf = (f"<form method='post' action='/action' class='qadd-form'>"
                   f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                   f"<input type='hidden' name='kanaal' value='{_e(kanaal)}'>"
                   f"<input type='hidden' name='next' value='/messages?k={_e(kanaal)}'>"
                   f"<label class='att-lbl' for='msg-tekst'>Write a message</label>"
                   # `data-mention` = de @-typhulp uit nooch.js. Puur typen: wat je kiest
                   # wordt platte tekst, er hangt geen notificatie of link achter.
                   f"<textarea id='msg-tekst' name='tekst' rows='2' data-mention "
                   f"placeholder='Write a reply, or ask a colleague to weigh in…'></textarea>"
                   f"<div class='qadd-row'><button class='btn ok sm' type='submit' name='action' "
                   f"value='msg_post'>Post</button></div></form>") + gereedschap
    elif kanaal and not ik:
        schrijf = ("<p class='muted'>Log in as a person to write here &mdash; a message needs an "
                   "author.</p>")

    kop = _e(_label(st, kanaal, ik)) if kanaal else "Messages"
    # UIT JE LIJST HALEN MOET KUNNEN, anders is "openen is toevoegen" een eenrichtingsdeur: één
    # klik op een zoekresultaat en het staat er voorgoed. Alleen bij een PROJECT, want de andere
    # soorten staan er sowieso — een knop die niets doet is erger dan geen knop.
    if (ik and csrf_token and kanaal and channels.soort_van(kanaal) == channels.PROJECT
            and kanaal in gevolgd):
        kop += (f"<form method='post' action='/action' class='msg-uit'>"
                f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                f"<input type='hidden' name='kanaal' value='{_e(kanaal)}'>"
                f"<input type='hidden' name='next' value='/messages'>"
                f"<button class='flink' type='submit' name='action' value='kanaal_ontvolg'>"
                f"remove from list</button></form>")
    # NIVEAU 3 → NIVEAU 2. Op desktop staat de lijst er gewoon naast, dus daar is deze link ruis;
    # `.msg-terug` toont hem alleen op telefoonbreedte. Een gewone link, geen knop: hij navigeert.
    qs_t = f"&q={_e(q)}" if q else ""
    terug = (f"<a class='msg-terug flink' href='/messages?list=1&amp;k={_e(kanaal)}{qs_t}'>"
             f"&larr; All channels</a>")
    main = (f"<div class='c2-main'><h1>Messages</h1>"
            f"<p class='muted'>One channel type, five flavours: the village, a goal, a topic of "
            f"your own, a project you added, or a person. Projects only show up once you open or "
            f"search for them.</p>"
            f"{_banner(msg)}"
            f"<div class='msg-layout' data-mob='{'lijst' if lijst else 'draad'}'>{nav}"
            f"<section class='msg-draad'>{terug}<h2 class='msg-kop'>{kop}</h2>"
            f"{draad}{schrijf}</section>"
            f"</div></div>")
    # DE ZIJBALK KLAPT IN (fase 11). Messages heeft zijn eigen lijst-paneel, en drie volle kolommen
    # naast elkaar passen niet. De rail houdt de navigatie bereikbaar zonder de kanalenlijst te
    # verdringen; de organisatieboom zit hier achter zijn icoon, want die heb je tijdens een
    # gesprek niet nodig.
    # `rail=True` STOND HIER, en dat was de enige plek. De zijbalk klapte op /messages in tot een
    # 64px icoon-rail omdat drie volle kolommen niet pasten: navigatie, kanalenlijst, gesprek.
    #
    # WEG OP 21 SEPTEMBER 2026 (eis Stefan). Een balk die op één scherm anders breed is dan op alle
    # andere, is een tweede navigatiemodel — precies wat fase 7 opruimde — en je verliest de woorden
    # op het scherm waar je ze het hardst nodig hebt: als je uit een gesprek komt weet je niet meer
    # welke twee letters waar heen gingen. De ruimte komt uit de kanalenlijst (210px), niet uit de
    # navigatie.
    return _page("Messages", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
