"""founder_taken.py — de drie wachtrijen van de Founder Flow en het AI-voorstel per item.

Dit is de ORKESTRATIE-laag. Er zit geen nieuwe intelligentie in: elk voorstel komt uit een bron
die er al was, en elk effect loopt via een pad dat er al was. Wat hier bijkomt is uitsluitend
"welke items staan er klaar" en "wat zou het bestaande oordeel zeggen".

| Taak                | Wachtrij                                  | Voorstel komt uit                        |
|---------------------|-------------------------------------------|------------------------------------------|
| radar_triage        | `RadarStore.all_pending()`                | `mission.strategie_relevantie` (de lexicale Stage-0-baseline) |
| claim_oordeel       | werklijst-items met status `open`         | het stoplicht dat de claims-database zelf al aan de claim gaf |
| content_goedkeuring | Field Notes + vastgelegde bewijs-records  | `grounding.ground_field_note` resp. `claims_db.check_tekst`   |

Het voorstel is dus nergens een nieuw model, een nieuwe prompt of een nieuwe API-aanroep. Dat is
opzet: de lus meet of het OORDEEL dat we al hebben de founder kan vervangen. Blijkt van niet, dan
is dat een bevinding over de bestaande heuristiek — geen aanleiding om er stilletjes een LLM
tegenaan te gooien.
"""
from __future__ import annotations

import glob
import json
import logging
import os

from nooch_village import founder_flow as ff

log = logging.getLogger("village.founder_taken")

# Wie het werk krijgt als de founder corrigeert of doorzet. Eén plek, zodat de routing van de
# flow niet uiteen kan lopen met die van de claims-checker.
SCIENTIST_ROL = "harry_hemp"                  # "grounded in undeniable scientific truth"
COMPLIANCE_ROL = "compliance"
FIELD_NOTE_ROL = "website_watcher"            # schrijft de dagelijkse Field Note (seeds.py)


# ── 1. Radar-triage ──────────────────────────────────────────────────────────────────────────

def _radar_items(st, data_dir: str) -> list[dict]:
    drempel = int(ff.instellingen(data_dir, ff.RADAR).get("drempel", 1))
    uit = []
    for it in st.radar.all_pending():
        tekst = f"{it.get('content', '')} {it.get('rationale', '')}"
        voorstel, waarom = _radar_voorstel(tekst, drempel)
        uit.append({
            "item": it["id"],
            "titel": it.get("content", "")[:160],
            "detail": it.get("rationale", "")[:240],
            "context": it.get("feed", "") or it.get("source", ""),
            "link": it.get("link", ""),
            "ai": voorstel,
            "ai_waarom": waarom,
        })
    return uit


def _radar_voorstel(tekst: str, drempel: int) -> tuple[str, str]:
    """Het lexicale strategie-filter uit `mission.py` — exact de baseline waartegen Stage-0 elk
    model afzet. Raakt het signaal minstens `drempel` strategie-thema's, dan is het bewaren waard.

    Bewust deterministisch: dit draait op elke page-load, en een voorstel dat per keer verschilt
    is geen voorstel maar een dobbelsteen."""
    from nooch_village.mission import strategie_relevantie
    score, labels = strategie_relevantie(tekst or "")
    if score >= max(1, drempel):
        return "keep", f"touches {score} strategy theme(s): {', '.join(labels[:3])}"
    return "dismiss", "touches no strategy theme in the mission lexicon"


def _radar_effect(st, data_dir: str, item: str, oordeel: str) -> str:
    """Keep/dismiss via dezelfde statuswissel die de radar-knoppen op /signals doen."""
    it = st.radar.get(item)
    if it is None:
        return "✗ unknown radar signal"
    st.radar.set_status(item, "goedgekeurd" if oordeel == "keep" else "afgewezen")
    return "✓ kept — in the archive" if oordeel == "keep" else "🗑 dismissed"


# ── 2. Claim-oordeel ─────────────────────────────────────────────────────────────────────────

# Het stoplicht dat de claims-database aan een werklijst-claim gaf, is al een oordeel. Deze
# afbeelding maakt er de routing van die eruit volgt — geen nieuwe weging:
#   red        → de formulering mag niet blijven staan          → fix copy
#   orange     → mag mits genoemd bewijs                        → bank evidence
#   escaleren  → geen harde bron, iemand moet het gronden       → to Scientist
_STOPLICHT_ROUTE = {"red": "fix", "orange": "bewijs", "escaleren": "scientist"}


def _wacht_op_mens(status: str) -> bool:
    """Welke werklijst-statussen horen in de wachtrij van de founder?

    Niet alleen `open`. De wekelijkse scan zet zélf statussen (`claims_db.AUTO_STATUSSEN`), en
    twee daarvan betekenen letterlijk "hier moet een mens naar kijken":
      - `niet auto-verifieerbaar` — de byte-vergelijking kon niets vaststellen; dat is precies
        het geval waarin een oordeel nodig is, niet het geval waarin je niets hoeft te doen.
      - `open (regressie)` — een eerder opgeloste claim staat weer op de site.
    Op productie stond de hele werklijst in die twee statussen, waardoor de claim-taak een lege
    wachtrij had: de flow wachtte op 'open' terwijl de scan dat woord al lang niet meer gebruikt.

    Buiten de wachtrij blijven: `in behandeling` en `live` (werk loopt of is klaar) en
    `opgelost (auto-geverifieerd)` (de scan zag de claim van de site verdwijnen)."""
    s = str(status or "open").strip().lower()
    return s == "open" or s.startswith(("open (", "niet auto"))


def _claim_items(st, data_dir: str) -> list[dict]:
    from nooch_village import claims_db
    try:
        db = claims_db.load(data_dir=data_dir)
    except Exception as e:                           # noqa: BLE001 — een kapotte db mag de flow niet slopen
        log.warning("claims-database onleesbaar voor de founder flow: %s", e)
        return []
    uit = []
    for w in db.get("werklijst", []):
        if not _wacht_op_mens(w.get("status")):
            continue
        oordeel = str(w.get("oordeel", "")).lower()
        voorstel = _STOPLICHT_ROUTE.get(oordeel)
        uit.append({
            "item": f"claim:{w.get('nr')}",
            "titel": str(w.get("claim", ""))[:160],
            "detail": str(w.get("herformulering", ""))[:240],
            "context": f"traffic light: {oordeel or 'unknown'}",
            "link": "",
            "ai": voorstel,
            "ai_waarom": (f"the claims database already judged this {oordeel}"
                          if voorstel else "no traffic light in the database — no proposal"),
        })
    return uit


def _claim_nr(item: str) -> int | None:
    try:
        return int(item.split(":", 1)[1])
    except (IndexError, ValueError):
        return None


def _claim_regel(data_dir: str, nr: int) -> dict:
    from nooch_village import claims_db
    try:
        db = claims_db.load(data_dir=data_dir)
    except Exception:                                # noqa: BLE001
        return {}
    for w in db.get("werklijst", []):
        if int(w.get("nr", -1)) == nr:
            return w
    return {}


def _claim_effect(st, data_dir: str, item: str, oordeel: str) -> str:
    """De drie routes, elk via een bestaand pad.

    `fix`       → `claims_board.zet_op_bord` maakt de taak bij de rol die de bestaande routing
                  aanwijst, en stuurt het bericht dat die rol wakker maakt.
    `bewijs`    → een @rol-bericht aan compliance: die bezit het bewijsregister en legt de bron en
                  het letterlijke citaat vast. De flow verzint geen citaat — dat zou precies het
                  soort onderbouwing zijn waartegen deze hele database bestaat.
    `scientist` → een @rol-bericht aan de Scientist, die de claim wetenschappelijk grondt.

    In alle drie de gevallen gaat het werklijst-item naar "in behandeling", zodat het uit de
    wachtrij verdwijnt en de volgende scan het niet opnieuw aanbiedt."""
    from nooch_village import claims_board, claims_db
    nr = _claim_nr(item)
    if nr is None:
        return "✗ unknown claim"
    regel = _claim_regel(data_dir, nr)
    if not regel:
        return "✗ claim is no longer on the worklist"
    claim = str(regel.get("claim", ""))
    herformulering = str(regel.get("herformulering", ""))
    melding = ""
    if oordeel == "fix":
        from nooch_village.views.claims import rol_voor
        bevinding = {
            "stoplicht": str(regel.get("oordeel", "")).lower(),
            "categorie": "Framing", "term": claim, "gevonden": [claim], "pagina": "",
            "alternatief": herformulering, "herkomst": "werklijst",
            "waarom": "worklist item, judged by the founder in the Founder Flow",
        }
        verslag = claims_board.zet_op_bord(st, _claims_db_stil(data_dir), [bevinding],
                                           "worklist", rol_voor, trigger="founder_flow")
        melding = (f"✓ copy fix on the board ({len(verslag['aangemaakt'])} task(s))"
                   if verslag["aangemaakt"] else "✓ copy fix — work was already running")
    elif oordeel == "bewijs":
        claims_board.bericht_aan_rol(
            st, COMPLIANCE_ROL,
            f"Bank the evidence for: {claim} — record source + literal quote in the Chronicle.",
            door="founder-flow")
        melding = "✓ handed to compliance to bank the evidence"
    elif oordeel == "scientist":
        claims_board.bericht_aan_rol(
            st, SCIENTIST_ROL,
            f"Ground this claim scientifically: {claim} — no hard source in the database yet.",
            door="founder-flow")
        melding = "✓ handed to the Scientist"
    else:
        return "✗ unknown judgement"
    try:
        claims_db.overlay_set_status(data_dir, nr, "in behandeling")
    except Exception as e:                           # noqa: BLE001 — routing is al gebeurd; niet stil falen
        log.warning("werklijst-status %s niet gezet: %s", nr, e)
        melding += " (worklist status unchanged)"
    return melding


def _claims_db_stil(data_dir: str) -> dict:
    from nooch_village import claims_db
    try:
        return claims_db.load(data_dir=data_dir)
    except Exception:                                # noqa: BLE001
        return {}


# ── 3. Content-goedkeuring ───────────────────────────────────────────────────────────────────

def _field_notes(data_dir: str, maximaal: int = 5) -> list[dict]:
    """De recentste Field Notes, met het grondings-oordeel dat er al is.

    `grounding.ground_field_note` toetst de tekst tegen de puls-data van diezelfde dag: verzonnen
    datums en ongegronde bezoekersaantallen. Leeg = niets ongegronds gevonden → publiceren."""
    from nooch_village import grounding
    uit = []
    paden = sorted(glob.glob(os.path.join(data_dir, "output", "field_note_*.md")), reverse=True)
    for p in paden[:maximaal]:
        datum = os.path.basename(p).replace("field_note_", "").replace(".md", "")
        try:
            body = open(p, encoding="utf-8").read()
        except OSError:
            continue
        plausible = _pulse_raw(data_dir, datum)
        issues = grounding.ground_field_note(body, plausible, datum)
        uit.append({
            "item": f"fieldnote:{datum}",
            "titel": f"Field Note {datum}",
            "detail": _eerste_alinea(body),
            "context": "field note",
            "link": "",
            "ai": "corrigeer" if issues else "publiceer",
            "ai_waarom": ("; ".join(issues)[:200] if issues
                          else "every date and visitor number traces back to the pulse data"),
        })
    return uit


def _pulse_raw(data_dir: str, datum: str) -> dict:
    """De ruwe pulsdata van die dag — de grond waartegen de Field Note wordt getoetst."""
    try:
        with open(os.path.join(data_dir, "output", f"pulse_raw_{datum}.json"), encoding="utf-8") as f:
            rauw = json.load(f)
        return rauw if isinstance(rauw, dict) else {}
    except (OSError, ValueError):
        return {}


def _eerste_alinea(body: str, maximaal: int = 240) -> str:
    for regel in (body or "").splitlines():
        regel = regel.strip()
        if regel and not regel.startswith("#"):
            return regel[:maximaal]
    return ""


def _bewijs_entries(st, data_dir: str, maximaal: int = 10) -> list[dict]:
    """De vastgelegde onderbouwingen uit de Kroniek — publiek bewijs onder een eigen claim, dus
    content die de founder hoort af te tekenen.

    Het voorstel komt uit de claims-database zelf: claim + citaat door `check_tekst` halen. Vindt
    de scan daar een rode of oranje formulering, dan onderbouwt dit bewijs een claim die zelf nog
    niet compliant is — corrigeren dus."""
    from nooch_village import claims_db, claims_substantiatie
    try:
        rijen = claims_substantiatie.vastgelegd(st.evidence, limiet=maximaal)
    except Exception:                                # noqa: BLE001
        return []
    uit = []
    for r in rijen:
        claim = (r.get("meta") or {}).get("claim") or r.get("query", "")
        citaat = r.get("result_ref", "")
        try:
            uitslag = claims_db.check_tekst(f"{claim}\n{citaat}", data_dir=data_dir)
            zwaar = [b for b in uitslag.get("bevindingen", [])
                     if b.get("stoplicht") in ("red", "orange", "escaleren")]
        except Exception:                            # noqa: BLE001 — fail-closed: geen oordeel
            zwaar, uitslag = None, {}
        if zwaar is None:
            voorstel, waarom = None, "the claims scan could not judge this text"
        elif zwaar:
            voorstel = "corrigeer"
            waarom = f"the claims scan flags {len(zwaar)} wording(s) in claim or quote"
        else:
            voorstel, waarom = "publiceer", "no flagged wording in claim or quote"
        uit.append({
            "item": f"bewijs:{r.get('id', '')}",
            "titel": str(claim)[:160],
            "detail": str(citaat)[:240],
            "context": f"proof entry · {r.get('source', '') or 'no source'}",
            "link": r.get("source", ""),
            "ai": voorstel,
            "ai_waarom": waarom,
        })
    return uit


def _content_items(st, data_dir: str) -> list[dict]:
    return _field_notes(data_dir) + _bewijs_entries(st, data_dir)


def _content_effect(st, data_dir: str, item: str, oordeel: str) -> str:
    """Goedkeuren is de vastlegging zelf — het label ís de handtekening; er wordt niets herschreven.
    Corrigeren routeert het werk naar de rol die de content bezit, via het bestaande @rol-bericht."""
    from nooch_village import claims_board
    soort, _, sleutel = item.partition(":")
    if oordeel == "publiceer":
        return "✓ approved — recorded as a label"
    rol = FIELD_NOTE_ROL if soort == "fieldnote" else COMPLIANCE_ROL
    wat = f"Field Note {sleutel}" if soort == "fieldnote" else f"proof entry {sleutel}"
    claims_board.bericht_aan_rol(
        st, rol, f"The founder asks for a correction on {wat}.", door="founder-flow")
    return f"✎ correction requested from {rol}"


# ── De gedeelde ingang ───────────────────────────────────────────────────────────────────────

_WACHTRIJEN = {ff.RADAR: _radar_items, ff.CLAIM: _claim_items, ff.CONTENT: _content_items}
_EFFECTEN = {ff.RADAR: _radar_effect, ff.CLAIM: _claim_effect, ff.CONTENT: _content_effect}


def wachtrij(st, data_dir: str, taak: str, labels: list[dict] | None = None) -> list[dict]:
    """De open items van één taak: alles wat nog niet is beoordeeld (door mens óf AI).

    Elk item draagt zijn AI-voorstel al mee. Dat is bewust: het voorstel wordt ALTIJD berekend,
    ook op niveau A/B waar het niet getoond wordt, want zonder voorstel is er niets te meten. De
    view beslist of het zichtbaar is (`founder_flow.toont_voorstel_vooraf`) — de wachtrij niet."""
    if taak not in _WACHTRIJEN:
        return []
    labels = ff.alle(data_dir) if labels is None else labels
    gedaan = ff.beoordeelde_items(labels, taak)
    return [i for i in _WACHTRIJEN[taak](st, data_dir) if i["item"] not in gedaan]


def item_van(st, data_dir: str, taak: str, item: str) -> dict | None:
    """Eén item opnieuw ophalen — inclusief zijn voorstel — ook als het al beoordeeld is.

    Nodig bij het vastleggen: de POST mag het voorstel niet uit het formulier geloven. Een
    voorstel dat de client meestuurt, is een voorstel dat de client kan vervalsen, en daarmee is
    de hele overeenstemmings-meting waardeloos."""
    if taak not in _WACHTRIJEN:
        return None
    return next((i for i in _WACHTRIJEN[taak](st, data_dir) if i["item"] == item), None)


def voer_uit(st, data_dir: str, taak: str, item: str, oordeel: str) -> str:
    """Voer het oordeel uit via het bestaande pad. Geeft een korte melding terug."""
    if taak not in _EFFECTEN or oordeel not in ff.OORDELEN[taak]:
        return "✗ unknown action"
    try:
        return _EFFECTEN[taak](st, data_dir, item, oordeel)
    except Exception as e:                           # noqa: BLE001 — het label is al waardevol
        log.exception("founder-flow effect faalde (%s/%s)", taak, item)
        return f"⛔ recorded, but the follow-up failed: {e}"


def verwerk_automatisch(st, data_dir: str, taak: str, niveau: str, cfg: dict,
                        labels: list[dict] | None = None) -> dict:
    """Niveau C/D: pas het AI-voorstel toe op alles buiten de auditsteekproef.

    Dit is de plek waar een rijpheidsniveau écht iets betekent — zonder deze functie is C/D een
    sticker. Twee grenzen zitten er hard in:
      - de auditsteekproef wordt NOOIT automatisch verwerkt; die blijft blind naar de mens, zodat
        er ook op D een schone meetreeks blijft lopen en drift zichtbaar wordt;
      - een item zonder voorstel wordt overgeslagen, niet gegokt (fail-closed).

    De uitvoering hangt bewust aan een expliciete klik in de flow en niet aan de dagpuls: zolang
    de daemon dit niet aanroept, gebeurt autonome verwerking alleen terwijl de founder kijkt.
    Dat is de naad waar het later aan de puls kan — een besluit, geen bijvangst."""
    verslag = {"verwerkt": 0, "audit": 0, "zonder_voorstel": 0, "meldingen": []}
    if niveau not in ("C", "D"):
        return verslag
    labels = ff.alle(data_dir) if labels is None else labels
    for it in wachtrij(st, data_dir, taak, labels):
        audit = ff.in_auditsteekproef(taak, it["item"], cfg.get("audit_pct", 0))
        if not ff.ai_handelt_zelf(niveau, audit):
            verslag["audit"] += 1
            continue
        if not it.get("ai"):
            verslag["zonder_voorstel"] += 1
            continue
        melding = voer_uit(st, data_dir, taak, it["item"], it["ai"])
        ff.leg_vast(data_dir, taak=taak, item=it["item"], mens=None, ai=it["ai"],
                    ai_getoond=False, niveau=niveau, door="ai", audit=False,
                    titel=it.get("titel", ""))
        verslag["verwerkt"] += 1
        verslag["meldingen"].append(melding)
    return verslag
