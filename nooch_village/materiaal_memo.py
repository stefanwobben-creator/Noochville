"""De twee materiaal-memo's van de radar: kwartaaloverzicht en maandelijkse shortlist.

WAAROM EEN MEMO EN GEEN STORE. De radar produceert al dagelijks (8 items/dag in de feed Material
Innovation, 423 sinds de start). Wat ontbrak was niet de bron maar de UITGANG: 84 items stonden te
wachten en 181 goedgekeurde gingen nergens heen behalve een lijst. Een memo is de vorm die een mens
leest; de atomiseur zou er opnieuw een store van maken, en dat is precies wat de kennisbank-analyse
als probleem aanwees (96% van de atomen is wereldkennis die het model al heeft).

WAAROM UIT DE OPGESLAGEN STROOM. De watch-skills opnieuw aanroepen betekent vier externe API's die
tegelijk moeten meewerken, binnen één puls. De radar heeft de stroom al gepersisteerd, mét bron en
status. Sneller, reproduceerbaar, en hij faalt niet stil op een hangende API.

DE TWEE LATTEN VERSCHILLEN, EN DAT IS HET PUNT:

  kwartaal    oriëntatie. Geen marktrijp-filter, geen selectie — waar beweegt het.
  maandelijks 1-2 kandidaten die marktrijp zijn, een footwear-toepassing kennen en bij Nooch passen.

Allebei landen ze via één lookup (`triage_rol.menselijke_eigenaar`) bij de rol die het materiaal-
domein bezit, live geresolved. Geen rol-id in deze module.
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone

from nooch_village.checklists import period_key
from nooch_village.skills import Skill
from nooch_village.util import JsonStore

log = logging.getLogger("village.materiaal_memo")

#: Waar de memo's bijhouden wat ze al deden. Twee dingen: welke periode al gedraaid is (het ritme),
#: en welke kandidaten al zijn voorgelegd (het geheugen).
STATE = "materiaal_memo.json"

#: De feed waar de stroom in zit. Zelfde label als `radar_store._DEFAULT_FEEDS`.
FEED = "Material Innovation"


# ── de staat: ritme én geheugen ───────────────────────────────────────────────────────────────

class _MemoStore(JsonStore):
    """De staat van de memo's: welke periode al gedraaid is, en wat al is voorgelegd.

    Via de bewaakte schrijfroute, niet via `atomic_write_json` — er is ÉÉN schrijfweg per store
    (CONVENTIES, #419), en een bestand van twee sleutels is daar geen uitzondering op. Juist de
    kleine schrijfacties glippen anders langs het slot."""

    _WRITE_METHODS = ("zet",)

    def __init__(self, path: str):
        self.path = path
        self._items = {}
        try:
            self._load()
        except (OSError, ValueError, RuntimeError) as e:
            # Fail-open MAAR LUID (CONVENTIES): dit is een cache van wat we al deden, geen record.
            # Leeg beginnen kost hooguit één herhaalde kandidaat; niet starten zet de memo stil.
            log.warning("%s onleesbaar (%s) — leeg gestart; een kandidaat kan één keer herhalen",
                        path, e)
            self._items = {}
            try:
                self._save()                     # het kapotte bestand meteen vervangen
            except OSError:
                pass

    def zet(self, staat: dict) -> None:
        self._items = staat
        self._save()


def _lees(data_dir: str) -> dict:
    return dict(_MemoStore(os.path.join(data_dir, STATE))._items)


def _schrijf(data_dir: str, staat: dict) -> None:
    _MemoStore(os.path.join(data_dir, STATE)).zet(staat)


def periode_gedaan(data_dir: str, memo: str, periode: str) -> bool:
    return (_lees(data_dir).get("perioden") or {}).get(memo) == periode


def noteer_periode(data_dir: str, memo: str, periode: str) -> None:
    st = _lees(data_dir)
    st.setdefault("perioden", {})[memo] = periode
    _schrijf(data_dir, st)


# ── het geheugen: wat is al voorgelegd, en waar kwam nee op ───────────────────────────────────

def voorgelegd(data_dir: str) -> dict:
    """{sleutel: {"wanneer": iso, "oordeel": ""|"nee"}} — wat de shortlist al aan een mens gaf.

    ZONDER DIT WORDT DE RADAR RUIS. Dezelfde ontdekking komt maand na maand terug omhoog: de feed
    blijft hem aanleveren, en een filter zonder geheugen kent geen verschil tussen "nieuw" en
    "vorige maand al afgewezen". Dat is de accountability op de rol, niet een optimalisatie."""
    return _lees(data_dir).get("voorgelegd") or {}


def onthoud_voorgelegd(data_dir: str, sleutels: list[str]) -> None:
    st = _lees(data_dir)
    boek = st.setdefault("voorgelegd", {})
    nu = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for s in sleutels:
        boek.setdefault(s, {"wanneer": nu, "oordeel": ""})
    _schrijf(data_dir, st)


def noteer_oordeel(data_dir: str, sleutel: str, oordeel: str) -> bool:
    """Het antwoord van de mens terug in het geheugen. 'nee' betekent: nooit meer voorleggen."""
    st = _lees(data_dir)
    boek = st.setdefault("voorgelegd", {})
    if sleutel not in boek:
        return False
    boek[sleutel]["oordeel"] = str(oordeel or "")[:40]
    boek[sleutel]["beoordeeld"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _schrijf(data_dir, st)
    return True


def sleutel_van(item: dict) -> str:
    """De identiteit van een kandidaat. De LINK is het anker, niet de tekst: dezelfde ontdekking
    krijgt bij een tweede bron een andere formulering, en een tekst-sleutel zou hem dan als nieuw
    lezen. Geen link → terugval op de inhoud, want geen sleutel is erger dan een zwakke."""
    return (str(item.get("link") or "").strip().lower()
            or str(item.get("content") or "").strip().lower()[:120])


# ── de stroom lezen ───────────────────────────────────────────────────────────────────────────

def _items(st, sinds: float) -> list[dict]:
    """De goedgekeurde items uit de materiaal-feed vanaf `sinds`, nieuwste eerst.

    Alleen GOEDGEKEURD: een wachtend item is nog niet beoordeeld en een afgewezen item is dat wél —
    negatief. Beide in een memo stoppen zou het oordeel dat er al ligt weggooien."""
    uit = []
    for it in st.radar.all_items():
        if it.get("feed") != FEED or it.get("status") != "goedgekeurd":
            continue
        try:
            at = float(it.get("at") or 0)
        except (TypeError, ValueError):
            at = 0.0
        if at >= sinds:
            uit.append({**it, "at": at})
    return sorted(uit, key=lambda x: -x["at"])


def _bron_regel(it: dict) -> str:
    """Bron + link, altijd. Een kandidaat zonder bron is een bewering."""
    bron = str(it.get("source") or "onbekende bron")
    link = str(it.get("link") or "")
    return f"{bron}{f' — {link}' if link else ''}"


# ── memo 1: het kwartaaloverzicht ─────────────────────────────────────────────────────────────

class MateriaalKwartaalSkill(Skill):
    """Waar beweegt materiaalinnovatie? Oriëntatie, geen selectie."""

    name = "materiaal_kwartaal"
    cost = "free"                       # leest de eigen store; de LLM-ladder is de enige kost
    side_effect_free = False
    description = ("Kwartaaloverzicht van materiaalrichtingen uit de opgeslagen radar-stroom. "
                   "Geen marktrijp-filter: dit is oriëntatie.")
    output_schema = "ok, periode, skipped, reden, aantal, headsup"

    #: 92 dagen terug: één kwartaal, ruim genomen. Bewust niet exact op kwartaalgrenzen geknipt —
    #: de vraag is "wat bewoog er recent", niet "wat viel administratief in Q3".
    VENSTER = 92 * 24 * 3600

    def run(self, payload: dict, context=None) -> dict:
        payload = payload or {}
        data_dir = getattr(context, "data_dir", ".")
        periode = payload.get("_periode") or period_key("kwartaal")
        if not payload.get("force") and periode_gedaan(data_dir, self.name, periode):
            return {"ok": True, "periode": periode, "skipped": True,
                    "reden": "dit kwartaal al gedraaid"}

        st = payload.get("_stores") or _stores(data_dir)
        items = _items(st, time.time() - self.VENSTER)
        if not items:
            # GEEN NUL ZONDER REDEN (#426): niets gevonden is een uitkomst, geen stilte.
            noteer_periode(data_dir, self.name, periode)
            return {"ok": True, "periode": periode, "skipped": False, "aantal": 0,
                    "reden": "geen goedgekeurde signalen in dit venster"}

        tekst = _schrijf_memo(context, periode, items)
        noteer_periode(data_dir, self.name, periode)
        ontv = ontvanger(st, data_dir, f"Kwartaaloverzicht materiaalrichtingen {periode}")
        return {"ok": True, "periode": periode, "skipped": False, "aantal": len(items),
                "ontvanger": ontv["rol"], "ontvanger_grond": ontv["waarom"],
                "headsup": tekst}


def _stores(data_dir: str):
    from nooch_village.cockpit2 import _Stores
    return _Stores(data_dir)


def _schrijf_memo(context, periode: str, items: list[dict]) -> str:
    """De memo als tekst. Valt terug op een kale opsomming als er geen model is.

    FAIL-OPEN MET DE FEITEN. Zonder ladder is een lijst met bronnen nog steeds bruikbaar; een lege
    memo of een uitzondering zou de hele uitgang stilzetten omdat de verf ontbreekt."""
    regels = [f"- {str(it.get('content'))[:160]}\n  bron: {_bron_regel(it)}" for it in items[:25]]
    kaal = (f"Materiaalbeweging {periode} — {len(items)} goedgekeurde signalen.\n\n"
            + "\n".join(regels))
    prompt = (
        "Je schrijft een KORTE oriëntatie-memo over materiaalinnovatie voor schoeisel.\n"
        "Dit is geen selectie en geen advies: je zegt waar beweging zit, niet wat we moeten doen.\n\n"
        "REGELS:\n"
        "- Maximaal 250 woorden, Nederlands.\n"
        "- Groepeer in 3-5 richtingen. Per richting: wat er beweegt, en welke signalen dat dragen.\n"
        "- Noem alleen wat in de signalen staat. Verzin geen marktcijfers, geen leveranciers en\n"
        "  geen verwachtingen — als het er niet staat, staat het er niet.\n"
        "- Sluit af met wat je NIET kon zien in deze stroom. Een blinde vlek benoemen is\n"
        "  informatiever dan hem verzwijgen.\n\n"
        f"PERIODE: {periode}\nSIGNALEN:\n" + "\n".join(regels))
    try:
        from nooch_village.llm import reason
        uit = reason(prompt, call_site="materiaal_kwartaal")
    except Exception:                                        # noqa: BLE001
        log.warning("kwartaalmemo: model niet bereikbaar", exc_info=True)
        uit = None
    if not uit:
        log.info("kwartaalmemo zonder model — kale opsomming met bronnen")
        return kaal
    return f"📐 Materiaalbeweging {periode}\n\n{uit.strip()}\n\n({len(items)} signalen)"


# ── wie krijgt de memo ────────────────────────────────────────────────────────────────────────

def eigenaar_domein(data_dir: str) -> str:
    """Het domein dat de uitkomst van de materiaal-feed bezit, uit de feed-config.

    Niet uit deze module: `role` (wie kijkt) en `eigenaar_domein` (wie bezit) horen bij elkaar in
    één governance-aanpasbare plek, en dat is `data/feeds.json` met `_DEFAULT_FEEDS` als bodem."""
    try:
        from nooch_village.radar_store import load_feeds
        for f in load_feeds(data_dir):
            if f.get("label") == FEED:
                return str(f.get("eigenaar_domein") or "")
    except Exception:                                        # noqa: BLE001
        log.warning("feed-config niet leesbaar voor het eigenaar-domein", exc_info=True)
    return ""


def ontvanger(st, data_dir: str, waarover: str) -> dict:
    """De rol die deze memo hoort te lezen → {rol, mens, waarom, via}.

    ÉÉN LOOKUP voor de memo en voor het project dat er straks uit volgt (#434/#435): domein →
    secretary-terugval → Circle Lead → founder, met de luide config-fout als het geconfigureerde
    domein door niemand gehouden wordt. Geen rol-id in deze module."""
    from nooch_village.triage_rol import menselijke_eigenaar
    try:
        return menselijke_eigenaar(st, waarover, domein=eigenaar_domein(data_dir))
    except Exception:                                        # noqa: BLE001
        # FAIL-SOFT, MAAR LUID. De memo is de waarde; een mislukte adressering mag hem niet
        # opeten. Zonder ontvanger valt de pulslus terug op de founder — dan komt hij aan bij de
        # verkeerde mens in plaats van bij niemand.
        log.warning("ontvanger niet te bepalen voor %r — terugval op de founder", waarover,
                    exc_info=True)
        return {"rol": "", "mens": None, "waarom": "ontvanger niet te bepalen", "via": "fout"}


# ── memo 2: de maandelijkse shortlist ─────────────────────────────────────────────────────────

#: De drie filters, letterlijk zoals ze in de spec staan. Ze zitten in de PROMPT en niet in code,
#: want "marktrijp" en "past bij Nooch" zijn oordelen, geen tellingen — een regex die doet alsof
#: hij dat kan beslissen, is een verzonnen zekerheid.
_FILTERS = (
    "MARKTRIJP — het materiaal is te koop of te bemonsteren, niet 'in ontwikkeling', "
    "'veelbelovend' of 'onderzoekers werken aan'.",
    "FOOTWEAR — er is een concrete toepassing in schoeisel (bovenwerk, zool, lijm, garen, voering).",
    "PAST BIJ NOOCH — plantaardig, plasticvrij en/of aantoonbaar lagere CO2. Geen leer, geen "
    "fossiele kunststof, geen dierlijk materiaal.",
)


class MateriaalShortlistSkill(Skill):
    """1-2 kandidaat-materialen per maand, elk mét bron, als voorstel — niet als bevinding."""

    name = "materiaal_shortlist"
    cost = "free"
    side_effect_free = False
    description = ("Maandelijkse shortlist van 1-2 marktrijpe materiaalkandidaten uit de "
                   "radar-stroom, met bron, ter beoordeling.")
    output_schema = "ok, periode, skipped, reden, kandidaten, ontvanger, headsup"

    #: Eén maand terug plus wat marge: de feed levert ~8 per dag, dus dit is ruim genoeg om niets
    #: te missen zonder de prompt te laten dichtslibben.
    VENSTER = 45 * 24 * 3600
    #: Hoeveel er hoogstens aan een mens gegeven wordt. De spec zegt 1-2; meer is geen shortlist.
    MAX = 2

    def run(self, payload: dict, context=None) -> dict:
        payload = payload or {}
        data_dir = getattr(context, "data_dir", ".")
        periode = payload.get("_periode") or period_key("maand")
        if not payload.get("force") and periode_gedaan(data_dir, self.name, periode):
            return {"ok": True, "periode": periode, "skipped": True,
                    "reden": "deze maand al gedraaid"}

        st = payload.get("_stores") or _stores(data_dir)
        verse = _nieuw_voor_de_mens(st, data_dir, time.time() - self.VENSTER)
        if not verse:
            noteer_periode(data_dir, self.name, periode)
            return {"ok": True, "periode": periode, "skipped": False, "kandidaten": 0,
                    "reden": "geen ongeziene signalen in dit venster"}

        gekozen = _schift(context, verse, self.MAX)
        noteer_periode(data_dir, self.name, periode)
        if not gekozen:
            # EEN LEGE SHORTLIST IS EEN UITKOMST. Niets haalde de lat; dat is informatie, geen
            # stilte — en het zegt de mens dat er WEL gekeken is.
            return {"ok": True, "periode": periode, "skipped": False, "kandidaten": 0,
                    "reden": f"{len(verse)} ongeziene signalen bekeken, geen enkele haalde de lat"}

        onthoud_voorgelegd(data_dir, [k["sleutel"] for k in gekozen])
        ontv = ontvanger(st, data_dir, f"Materiaalkandidaten {periode}: sample aanvragen")
        return {"ok": True, "periode": periode, "skipped": False, "kandidaten": len(gekozen),
                "ontvanger": ontv["rol"], "ontvanger_grond": ontv["waarom"],
                "headsup": _shortlist_tekst(periode, gekozen, len(verse))}


def _nieuw_voor_de_mens(st, data_dir: str, sinds: float) -> list[dict]:
    """Goedgekeurde signalen die nog NOOIT aan een mens zijn voorgelegd.

    HET GEHEUGEN IS HET VERSCHIL TUSSEN EEN RADAR EN RUIS. De feed blijft dezelfde ontdekking
    aanleveren — via een tweede bron, een vervolgartikel, een persbericht. Zonder dit boek kent de
    schifting geen verschil tussen 'nieuw' en 'vorige maand al afgewezen', en duwt hij elke maand
    hetzelfde omhoog tot de mens stopt met lezen.

    Een 'nee' is definitief: één keer afgewezen betekent nooit meer voorleggen."""
    boek = voorgelegd(data_dir)
    return [it for it in _items(st, sinds) if sleutel_van(it) not in boek]


def _schift(context, kandidaten: list[dict], maxaantal: int) -> list[dict]:
    """De drie filters, door het model. Geeft [{sleutel, wat, waarom, leverancier, bron}].

    DIT IS EEN OORDEEL, GEEN TELLING. "Marktrijp" en "past bij Nooch" zijn niet met een regex te
    beslissen; een filter dat doet alsof, verzint zekerheid. Vandaar het model — en vandaar dat de
    uitkomst een VOORSTEL heet en geen bevinding (harry_hemp's eigen "je oordeelt NIET"-regel: hij
    draagt aan, de mens beslist).

    Geen model → LEGE shortlist, geen ongefilterde lijst. Alles doorgeven zou de schifting
    overslaan en de mens de ruis geven die dit juist moet wegnemen; dat is erger dan niets sturen,
    want het ziet eruit als een selectie."""
    regels = [f"[{i}] {str(k.get('content'))[:200]}\n     bron: {_bron_regel(k)}"
              for i, k in enumerate(kandidaten[:60])]
    prompt = (
        "Je selecteert hoogstens "
        f"{maxaantal} materiaal-kandidaten voor een vegan schoenenmerk, uit de signalen hieronder.\n"
        "Je BESLIST NIET of we het gaan gebruiken; je draagt voor, en een mens oordeelt.\n\n"
        "EEN KANDIDAAT HAALT DE LIJST ALLEEN ALS ALLE DRIE KLOPPEN:\n"
        + "\n".join(f"  {i+1}. {f}" for i, f in enumerate(_FILTERS)) + "\n\n"
        "Twijfel je bij één ervan, dan valt de kandidaat af. Liever nul dan een zwakke.\n\n"
        "ANTWOORD als JSON: {\"kandidaten\": [{\"nr\": <getal uit de lijst>, "
        "\"wat\": \"...\", \"waarom\": \"...\", \"leverancier\": \"...\"}]}\n"
        "- `wat`: in één zin, wat het materiaal is.\n"
        "- `waarom`: waarom het bij dit merk past — alleen op grond van wat er in het signaal staat.\n"
        # GEVONDEN IN DE DROGE RUN: het model zette "Newswise (via wetenschappelijke bronnen)" als
        # leverancier — dat is de NIEUWSSITE. De hele exit is "sample aanvragen bij [leverancier]",
        # dus een publicatie op die plek stuurt de mens naar de verkeerde deur. De bron staat er al
        # apart onder; leeg laten is beter dan iets dat op een leverancier lijkt.
        "- `leverancier`: de MAKER van het materiaal — het bedrijf of lab dat het produceert.\n"
        "  NOOIT de nieuwssite, het tijdschrift of de uitgever waar je het las: die staat al\n"
        "  als bron vermeld. Kun je de maker niet uit het signaal halen, antwoord dan \"\".\n"
        "- Staat er niets dat de drie filters haalt, antwoord dan {\"kandidaten\": []}.\n\n"
        "SIGNALEN:\n" + "\n".join(regels))
    try:
        from nooch_village.llm import reason
        rauw = reason(prompt, call_site="materiaal_shortlist", json_mode=True)
    except Exception:                                        # noqa: BLE001
        log.warning("shortlist: model niet bereikbaar", exc_info=True)
        rauw = None
    if not rauw:
        log.info("shortlist zonder model — LEGE lijst, geen ongefilterde ruis")
        return []
    try:
        data = json.loads(rauw)
        rijen = data.get("kandidaten") if isinstance(data, dict) else None
    except ValueError:
        log.warning("shortlist: antwoord is geen geldige JSON — lege lijst")
        return []
    uit = []
    for r in (rijen or [])[:maxaantal]:
        if not isinstance(r, dict):
            continue
        try:
            bron_item = kandidaten[int(r.get("nr"))]
        except (TypeError, ValueError, IndexError):
            # EEN KANDIDAAT ZONDER BRONSIGNAAL BESTAAT NIET. Zou het model er een verzinnen, dan
            # heeft hij geen link, geen bron en geen sleutel — en precies dat maakt hem
            # onnavolgbaar voor de mens die hem moet beoordelen.
            log.warning("shortlist: kandidaat verwijst niet naar een signaal — overgeslagen")
            continue
        uit.append({"sleutel": sleutel_van(bron_item),
                    "wat": str(r.get("wat") or "")[:300],
                    "waarom": str(r.get("waarom") or "")[:300],
                    "leverancier": str(r.get("leverancier") or "")[:120],
                    "bron": _bron_regel(bron_item)})
    return uit


def _shortlist_tekst(periode: str, gekozen: list[dict], bekeken: int) -> str:
    """De memo. KANDIDAAT-VOOR-OORDEEL, niet bevinding — dat verschil staat in de kop én per item.

    De actie is geen knop in deze tekst maar de bestaande inbox-weg: dit bericht is een spanning, en
    'verwerken tot project' opent de wizard met deze tekst als zaad (#428). Zo landt het sample-
    project op dezelfde geresolveerde rol, en sluit de spanning zichzelf zodra het project bestaat."""
    kop = (f"🧪 Materiaalkandidaten {periode} — {len(gekozen)} ter beoordeling "
           f"(uit {bekeken} ongeziene signalen)\n"
           "Dit zijn VOORSTELLEN, geen bevindingen: ik draag aan, jij oordeelt.\n")
    blokken = []
    for k in gekozen:
        lev = k["leverancier"] or "leverancier niet genoemd in de bron"
        blokken.append(
            f"\n• {k['wat']}\n"
            f"  waarom hier: {k['waarom']}\n"
            f"  leverancier: {lev}\n"
            f"  bron: {k['bron']}\n"
            f"  → sample aanvragen: verwerk deze spanning tot een project")
    return kop + "".join(blokken)
