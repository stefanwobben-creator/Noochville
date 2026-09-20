"""De dagelijkse legal-check: één inbox-item als er iets binnenkomt dat Nooch raakt.

WAAROM DIT HET ENIGE STUK IS DAT DE RADAR-OPRUIMING OVERLEEFT ALS NIEUWE CODE. De radar werd op
19 september 2026 een swipefile: feeds landen ongefilterd en het maandrapport (nog te bouwen) leegt
de bak. Voor drie van de vier feeds is dat precies goed — een trend hoeft niet vandaag gelezen te
worden. Voor de Legal & Green Claims-feed niet: een wetswijziging over duurzaamheidsclaims is geen
trend maar een deadline, en die hoort niet een maand in een bak te liggen.

Dus: geen rapport, geen wachtrij, geen status per signaal. Eén vraag per vers signaal — raakt dit
Nooch? — en bij ja één item in de human inbox van de founder. Niets anders.

GEEN EIGEN STATE, EN DE PRIJS DAARVAN STAAT HIER. De check kijkt naar signalen uit de laatste
`VENSTER_UREN` en niet verder terug. Dat scheelt een store, een migratie en een tweede waarheid over
"al gezien", maar het betekent ook: ligt de daemon anderhalve dag plat, dan is die dag legal-signaal
ongezien. Dat is een bewuste ruil en geen gat dat iemand later moet ontdekken. Het venster is ruimer
dan een dag zodat een late puls niets laat vallen; de dedup op de link in de inbox vangt de overlap.

Fail-closed zoals `reeds_bekend` en `onderzoeksvraag`: geen model, een leeg antwoord of welke fout
dan ook betekent GEEN item. Liever een gemiste melding dan een verzonnen juridisch alarm.
"""
from __future__ import annotations

import logging
import time

log = logging.getLogger("village.legal")

#: Het label uit `radar_store._DEFAULT_FEEDS` (overschrijfbaar via data/feeds.json).
FEED = "Legal & Green Claims"

#: Ruimer dan 24 uur: een puls die een paar uur later valt mag geen signaal laten vallen.
VENSTER_UREN = 36

#: Per puls, niet per feed. Een dag legal-nieuws is een handvol artikelen; loopt het hoger op, dan
#: is dat zelf het signaal (en de cap houdt de rekening voorspelbaar).
MAX_PER_PULS = 15

MAX_TOKENS = 300

_PROMPT = """You screen news for Nooch, a vegan, plastic-free shoe brand selling in the EU.

Nooch cares about: rules on sustainability and green claims (EU Green Claims Directive, EmpCo,
greenwashing enforcement), textile and footwear labelling, EPR and waste rules, and supply-chain
due diligence. Nooch does NOT care about: company results, funding rounds, awards, opinion pieces,
and anything outside the EU with no EU effect.

Answer on ONE line, exactly one of:
RELEVANT: <one sentence saying what Nooch would have to do or check>
NO

Headline: {titel}
Source: {bron}"""


def _vers(signalen: list, *, nu: float, venster_uren: float) -> list:
    """De signalen uit dit venster, nieuwste eerst. Alles zonder bruikbare tijd valt af — een
    signaal zonder tijdstempel is niet aantoonbaar vers, en 'misschien vers' is hier geen grond."""
    from nooch_village.radar_bronnen import tijdstip
    grens = nu - venster_uren * 3600
    uit = [(tijdstip(s), s) for s in signalen]
    return [s for t, s in sorted(uit, key=lambda p: -p[0]) if t >= grens]


def beoordeel(signaal: dict, *, reason_fn=None) -> str:
    """Raakt dit signaal Nooch? Geeft de reden terug, of "" bij nee/onbruikbaar.

    Side-effect-free: leest niets, schrijft niets, en geeft bij elke fout "" terug."""
    titel = " ".join(str(signaal.get("content") or "").split())[:300]
    if not titel:
        return ""
    if reason_fn is None:
        from nooch_village.llm import reason as reason_fn
    try:
        antwoord = reason_fn(_PROMPT.format(titel=titel, bron=signaal.get("source") or "?"),
                             max_tokens=MAX_TOKENS, call_site="legal_check")
    except Exception as e:                                  # noqa: BLE001 — nooit de puls breken
        log.info("legal-check overgeslagen (%s: %s)", type(e).__name__, e)
        return ""
    antwoord = (antwoord or "").strip()
    if not antwoord.upper().startswith("RELEVANT"):
        return ""
    reden = antwoord.split(":", 1)[1].strip() if ":" in antwoord else ""
    return reden[:400] or "raakt Nooch (geen toelichting gegeven)"


#: Deze bron levert `fail-closed` aan de weekmemo: geen model, een leeg antwoord of welke fout dan
#: ook betekent GEEN signaal. Dat staat al in de kop van deze module en het verandert niet door de
#: pijplijn — de drempel hoort bij de bron, niet bij de lezer.
DREMPEL = "fail-closed"


def verzamel(data_dir: str, *, sinds: float = 0.0, nu: float | None = None, reason_fn=None,
             cap: int = MAX_PER_PULS) -> list:
    """De verse legal-signalen die Nooch raken, als `weekmemo.Signaal`.

    DIT IS `check()` ZONDER DE AFLEVERING. Waar `check` een item in de human inbox zette, geeft
    deze een lijst terug en schrijft niets — dat is de hele scheiding die stap 2 aanbrengt: een
    verzamelaar WAARNEEMT, de memo beslist wat de lezer ziet, en de mens beslist wat er gebeurt.

    `sinds` in plaats van `venster_uren`: de weekmemo kijkt een week terug en niet 36 uur, en het
    venster is dus een eigenschap van de AANROEP geworden. 0 betekent: alles wat de radar heeft.

    Side-effect-free, net als `beoordeel`. Dat is geen detail maar de eigenschap waar stap 7 een
    ratchet op zet: een verzamelaar die schrijft is de terugkeer van precies het probleem dat deze
    pijplijn opheft."""
    import os

    from nooch_village.radar_bronnen import tijdstip
    from nooch_village.radar_store import RadarStore
    from nooch_village.weekmemo import Signaal

    nu = time.time() if nu is None else nu
    try:
        radar = RadarStore(os.path.join(data_dir, "radar.json"))
        alles = [s for s in radar.all_items() if str(s.get("feed") or "") == FEED]
    except Exception:                                       # noqa: BLE001 — fail-closed, luid
        log.warning("radar niet leesbaar — geen legal-signalen", exc_info=True)
        return []

    kandidaten = [s for s in alles if tijdstip(s) >= sinds]
    kandidaten.sort(key=tijdstip, reverse=True)
    uit = []
    for s in kandidaten[:cap]:
        reden = beoordeel(s, reason_fn=reason_fn)
        if not reden:
            continue                                        # fail-closed: geen reden = geen signaal
        uit.append(Signaal(
            bron="legal", tekst=str(s.get("content") or ""),
            vindplaats=str(s.get("link") or s.get("source") or ""),
            gevonden_op=float(tijdstip(s) or 0.0),
            herkomst=str(s.get("id") or s.get("link") or ""),
            # De REDEN is wat het model toevoegde, en die hoort niet in `tekst`: `tekst` is wat de
            # bron zei, `extra` is wat wij ervan vonden. In de memo staan ze daarom apart.
            extra={"reden": reden, "bron_naam": str(s.get("source") or "")}))
    return uit


def check(data_dir: str, inbox, *, nu: float | None = None, reason_fn=None,
          venster_uren: float = VENSTER_UREN, cap: int = MAX_PER_PULS) -> list[str]:
    """De dagelijkse ronde. Geeft de id's van de aangemaakte inbox-items terug (leeg = niets).

    `inbox` wordt geïnjecteerd, niet hier geopend: de aanroeper (Village) heeft er al een, en twee
    HumanInbox-objecten op hetzelfde bestand is precies de soort dubbele schrijver waar de
    lock-discipline over gaat."""
    from nooch_village.radar_store import RadarStore
    import os

    nu = time.time() if nu is None else nu
    radar = RadarStore(os.path.join(data_dir, "radar.json"))
    legal = [s for s in radar.all_items() if str(s.get("feed") or "") == FEED]
    uit: list[str] = []
    for s in _vers(legal, nu=nu, venster_uren=venster_uren)[:cap]:
        reden = beoordeel(s, reason_fn=reason_fn)
        if not reden:
            continue
        try:
            iid = inbox.add_legal_signaal(link=str(s.get("link") or ""),
                                          titel=str(s.get("content") or ""),
                                          bron=str(s.get("source") or ""), reden=reden)
        except Exception as e:                              # noqa: BLE001
            log.warning("legal-item niet aangemaakt: %s", e)
            continue
        if iid:
            uit.append(iid)
    if uit:
        log.info("⚖️ legal-check: %d signaal/signalen naar de inbox", len(uit))
    return uit
