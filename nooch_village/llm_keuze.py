"""Welk model gebruikt deze inwoner voor deze taak — en wat kostte dat?

Twee dingen die bij elkaar horen: de **keuze** vooraf (welke ladder geven we mee aan `reason()`)
en de **rekening** achteraf (wat verstookte deze persona de afgelopen dagen).

De keuze is een ladder van drie treden, smal naar breed:
1. de persona van de zittende inwoner heeft een voorkeur voor precies deze `call_site`
2. anders zijn algemene voorkeur
3. anders niets — en dan valt `reason()` terug op de dorpsladder, exact het huidige gedrag

Wat NIET hier gebeurt: throttlen. De LIMITER en de cooldowns in `llm.py` zijn procesbreed en
gedeeld. Een persona met een eigen model deelt dus dezelfde rem als de rest; een eigen throttle
per inwoner zou het dorp als geheel over de gratis limiet kunnen duwen.
"""
from __future__ import annotations

import json
import logging
import os
import time

_log = logging.getLogger("village.llm_keuze")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRIJZEN_PAD = os.path.join(BASE_DIR, "config", "llm_prijzen.json")


# ── De keuze ────────────────────────────────────────────────────────────────

def persona_van_rol(omgeving, role_id: str):
    """De persona die op deze rol zit, of None. Leest beide lagen (assignments én het
    legacy `persona_id`-veld op het record), want die lopen op prod uiteen."""
    try:
        personas = getattr(omgeving, "personas", None)
        records = getattr(omgeving, "records", None)
        if personas is None or records is None or not role_id:
            return None
        assign = getattr(omgeving, "assign", None)
        if assign is not None:
            for f in assign.fillers_of(role_id):
                if getattr(f, "type", None) == "persona":
                    p = personas.get(f.id)
                    if p is not None:
                        return p
        rec = records.get(role_id)
        return personas.get(getattr(rec, "persona_id", None)) if rec is not None else None
    except Exception:
        return None


# Call-sites waar een persona-voorkeur HARD is: alleen de eigen tredes, geen goedkope staart.
# Leeg by default — de zachte staart is de norm. Bedoeld voor oordeel-sites (een critic die een
# goedkoop oordeel liever niet geeft dan wel): daar is 'geen antwoord' een eerlijker uitkomst dan
# een goedkoop antwoord dat als premium oordeel wordt gelezen. Zet een call_site hier neer en de
# staart vervalt voor precies die site.
PREMIUM_ONLY: frozenset[str] = frozenset()


# ── De negen hoog-inzet-sites ────────────────────────────────────────────────────────────────
# Waar het OORDEEL telt, niet het tempo. Dit zijn de plekken waar een goedkoop antwoord niet
# "sneller hetzelfde" is maar iets anders: een plan dat de verkeerde taken bedenkt, een rapport dat
# een verzonnen getal doorlaat, een critic die een zwakke claim niet ziet. Daar hoort het sterkste
# brein dat we hebben, en kosten zijn hier bewust geen overweging.
HOOG_INZET: frozenset[str] = frozenset({
    "einddocument",              # het stuk dat de mens leest en waarop hij beslist
    "plan_checklist",            # bepaalt WELK werk er gebeurt — een fout hier plant zich voort
    "plan_checklist_retry",
    "skill_tegenspraak",         # de missie-critic; een zwak oordeel is erger dan geen oordeel
    "skill_synthesize",
    "skill_content_schrijven",   # gaat richting de site: hier landen claims
    "skill_bulletin",            # mens-facing
    "skill_voorstel",            # de mens beslist hierop
    "noochie_weigh_in",          # de brug naar The Source
})

# ── En de tegenhanger: waar goedkoop de JUISTE keuze is ──────────────────────────────────────
# Triage en routing kiezen alleen een BAK ("is dit structureel?", "welke rol?"). Dat is een grove
# beslissing met een goedkope fout: verkeerd gerouteerd werk komt terug, verkeerd geplande inhoud
# niet. Deze sites houden expliciet de dorpsladder — ze staan hier zodat "dorpsbreed premium" niet
# per ongeluk ook de hoogfrequente routeer-calls meeneemt.
GOEDKOOP: frozenset[str] = frozenset({
    "classify_tension", "cockpit_mention_triage", "escalation_route", "escaleer_keuze",
    "escaleer_classify", "scope_nudge_match", "governance_target_pick", "news_driver_pick",
    "cockpit_match_pair", "cockpit_match_keycheck", "wizard_title",
})

# De dorpsbrede kop voor hoog-inzet: Sonnet, met de dorpsladder als staart (via `met_dorpsstaart`).
# Env-instelbaar zodat je 'm zonder deploy kunt bijstellen of uitzetten (leeg = geen kop).
# Sonnet 5: de huidige generatie, én een trede die in config/llm_prijzen.json een prijs heeft. Dat
# tweede is geen bijzaak — een premium-kop zonder prijs maakt de maandcap blind: alle calls tellen
# dan voor €0,00 en de zekering gaat nooit om. De guard-test bewaakt dat elke trede in deze kop
# een prijs heeft.
_DEFAULT_HOOG_INZET = "anthropic:claude-sonnet-5"


def hoog_inzet_ladder() -> str:
    """De dorpsbrede ladder-kop voor oordeel-sites. Env `LLM_HOOG_INZET_LADDER`; leeg = uit."""
    raw = os.getenv("LLM_HOOG_INZET_LADDER")
    return (_DEFAULT_HOOG_INZET if raw is None else raw).strip()


def ladder_voor(call_site: str, persona=None) -> str | None:
    """DE ladder-keuze voor één call-site. None = de dorpsladder (geen eigen kop).

    Volgorde, en die is niet willekeurig:
      1. de persona-voorkeur wint altijd — een inwoner mag zijn eigen brein kiezen;
      2. anders: is dit een hoog-inzet-site, dan de dorpsbrede Sonnet-kop met de dorpsstaart;
      3. anders (triage, routing, alles wat niet in HOOG_INZET staat): de dorpsladder.

    En daaroverheen de maandcap: is het premium-budget van deze maand op, dan vervalt de dure kop
    en blijft de dorpsladder over. Een goedkoper antwoord, geen géén antwoord — een cap die het
    dorp stil legt is erger dan een cap die hem goedkoper laat werken."""
    eigen = voorkeur_van(persona, call_site) if persona is not None else None
    if eigen:
        _meld_prijsloos(eigen, f"persona-voorkeur voor {call_site}")
        return eigen
    if call_site in GOEDKOOP or call_site not in HOOG_INZET:
        return None
    kop = hoog_inzet_ladder()
    if not kop:
        return None
    if premium_op():
        return None
    _meld_prijsloos(kop, "dorpsbrede hoog-inzet-kop")
    from nooch_village import llm as _llm
    return kop if call_site in PREMIUM_ONLY else _llm.met_dorpsstaart(kop)


# ── De maandcap op premium ───────────────────────────────────────────────────────────────────
# Kosten zijn geen constraint, maar een uitschieter mag het saldo niet stil leegtrekken. Deze cap
# is geen budgetbeheer — het is een zekering: hij gaat om bij een orde-van-grootte-afwijking, niet
# bij een dure week.
_CAP_ENV = "LLM_PREMIUM_MAAND_CAP_EUR"
_DEFAULT_CAP_EUR = 50.0
_CACHE_S = 300.0                       # de usage-log per 5 minuten herlezen, niet per call
_cap_cache: dict = {"tot": 0.0, "op": False, "eur": 0.0}


def premium_maand_cap() -> float:
    """De maandcap in euro. 0 of negatief = geen cap."""
    try:
        return float(os.getenv(_CAP_ENV, str(_DEFAULT_CAP_EUR)))
    except (TypeError, ValueError):
        return _DEFAULT_CAP_EUR


def premium_uitgaven_deze_maand(pad: str | None = None) -> float:
    """Wat de dure tredes deze kalendermaand kostten, uit het echte usage-log.

    Alleen de PREMIUM tredes tellen: de cap gaat over de kop, niet over het dorpsverbruik. Een
    maand vol goedkope calls mag de dure kop nooit uitschakelen."""
    import datetime
    import json as _json

    from nooch_village import llm_usage
    maand = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m")
    prijzen = _prijzen()
    totaal = 0.0
    try:
        with open(pad or llm_usage._path(), encoding="utf-8") as f:
            for regel in f:
                regel = regel.strip()
                if not regel:
                    continue
                try:
                    rij = _json.loads(regel)
                except ValueError:
                    continue
                if not str(rij.get("day", "")).startswith(maand):
                    continue
                tier = str(rij.get("tier") or "")
                if not _is_premium(tier):
                    continue
                eur = kosten_eur(tier, int(rij.get("in_tokens") or 0),
                                 int(rij.get("out_tokens") or 0), prijzen)
                if eur:
                    totaal += eur
    except OSError:
        return 0.0
    return round(totaal, 4)


def _is_premium(tier: str) -> bool:
    """Welke tredes tellen mee voor de cap: alles wat niet in de dorpsladder staat.

    Afgeleid, niet overgetypt: verandert de dorpsladder, dan verschuift de grens vanzelf mee. Zou
    hier een lijstje modelnamen staan, dan telt een nieuw premium-model stilzwijgend niet mee."""
    from nooch_village import llm as _llm
    return tier not in set(_llm.tier_namen(_llm.dorpsladder()))


def premium_op(nu: float | None = None) -> bool:
    """Is de maandcap bereikt? Gecachet (5 min): een usage-log per LLM-call herlezen is zonde.

    Fail-open: kan de uitgave niet worden gelezen, dan is de cap NIET bereikt. Een onleesbaar
    logbestand mag het dorp niet naar de goedkope ladder duwen zonder dat iemand het weet — dat
    zou als kwaliteitsverlies lezen zonder oorzaak."""
    cap = premium_maand_cap()
    if cap <= 0:
        return False
    nu = nu if nu is not None else time.time()
    if nu - _cap_cache["tot"] < _CACHE_S:
        return bool(_cap_cache["op"])
    try:
        eur = premium_uitgaven_deze_maand()
    except Exception as e:                                   # noqa: BLE001
        _log.warning("premium-cap kon niet worden gelezen (cap niet toegepast): %s", e)
        return False
    op = eur >= cap
    if op and not _cap_cache["op"]:
        _log.warning("PREMIUM_CAP: €%.2f van €%.2f deze maand op de dure tredes — hoog-inzet-calls "
                     "vallen terug op de dorpsladder tot de volgende maand.", eur, cap)
    _cap_cache.update({"tot": nu, "op": op, "eur": eur})
    return op


def prijsloze_tredes(ladder: str) -> list[str]:
    """De tredes in deze ladder waarvoor `config/llm_prijzen.json` geen prijs kent.

    Bestaat omdat een prijsloze trede de maandcap BLIND maakt: die calls tellen voor €0,00 en de
    zekering gaat nooit om. Op productie liepen er drie verschillende Sonnet-ids naast elkaar
    (4-5, 4-6, en 'anthropic:default'), geen enkele met een prijs — 50 calls die nergens meetelden."""
    prijzen = _prijzen()
    uit = []
    for trede in (ladder or "").split(","):
        trede = trede.strip()
        if trede and kosten_eur(trede, 1000, 1000, prijzen) is None:
            uit.append(trede)
    return uit


_gemeld_prijsloos: set = set()


def _meld_prijsloos(ladder: str, herkomst: str) -> None:
    """Waarschuw ÉÉN keer per onbekende trede. Fail-loud, niet fail-silent: een ladder die de cap
    niet kan zien is geen detail, maar hij mag ook geen logspam worden."""
    for trede in prijsloze_tredes(ladder):
        if trede in _gemeld_prijsloos:
            continue
        _gemeld_prijsloos.add(trede)
        _log.warning("PRIJSLOZE_TREDE: '%s' (%s) staat niet in config/llm_prijzen.json — deze "
                     "calls tellen voor EUR 0,00 en zijn dus onzichtbaar voor de maandcap. "
                     "Zet er een prijs bij of lijn de trede uit met de dorpskop (%s).",
                     trede, herkomst, hoog_inzet_ladder())


def premium_stand() -> dict:
    """{uitgaven, cap, op} — voor een scherm of een logregel, zonder de cache te omzeilen."""
    return {"uitgaven": premium_uitgaven_deze_maand(), "cap": premium_maand_cap(),
            "op": premium_op()}


def eigen_keuze(persona, call_site: str) -> str | None:
    """De ladder-string zoals de persona hem ZELF opschreef, zonder staart. Dit is de maatstaf voor
    'is dit document nog wat er gevraagd werd?' — zie `eigen_tredes`."""
    if persona is None:
        return None
    llm = getattr(persona, "llm", None) or {}
    keuze = ((llm.get("per_taak") or {}).get(call_site) or llm.get("default") or "").strip()
    return keuze or None


def eigen_tredes(persona, call_site: str) -> set[str]:
    """De trede-labels die als de EIGEN keuze van deze persona tellen (de kop, zonder staart).

    Een `reason()`-trede die hier niet in zit, is een terugval: het antwoord kwam van de goedkope
    staart. Leeg = deze persona vroeg niets bijzonders, dus is er ook niets om van terug te vallen."""
    from nooch_village import llm as _llm
    keuze = eigen_keuze(persona, call_site)
    return set(_llm.tier_namen(keuze)) if keuze else set()


def voorkeur_van(persona, call_site: str) -> str | None:
    """De ladder-string van een al-opgehaalde persona. Los van `llm_voorkeur` omdat sommige
    aanroepers de persona al in handen hebben en geen stores kunnen doorgeven.

    De uitkomst is de eigen keuze MET de dorpsladder als staart: een voorkeur vult de goedkope
    tredes aan, hij vervangt ze niet. Valt de dure leverancier weg, dan volgt alsnog een goedkoop
    antwoord — zichtbaar gemarkeerd als terugval, nooit stil doorgaand voor een premium exemplaar.
    Uitzondering: `PREMIUM_ONLY`-sites houden de harde kop."""
    from nooch_village import llm as _llm
    keuze = eigen_keuze(persona, call_site)
    if not keuze:
        return None
    return keuze if call_site in PREMIUM_ONLY else _llm.met_dorpsstaart(keuze)


def llm_voorkeur(omgeving, role_id: str, call_site: str) -> str | None:
    """De ladder-string voor deze rol en taak, of None om de dorpsladder te gebruiken.

    None is een volwaardige uitkomst, geen fout: zonder persona-voorkeur hoort het gedrag
    byte-voor-byte gelijk te blijven aan hoe het dorp altijd al werkte."""
    # Via `ladder_voor`, niet direct via `voorkeur_van`: zo krijgt ELKE bestaande hook de
    # dorpsbrede hoog-inzet-kop erbij zodra de persona zelf niets kiest. Eén ingang, geen tweede
    # plek waar de default opnieuw bedacht wordt.
    return ladder_voor(call_site, persona_van_rol(omgeving, role_id))


# ── De rekening ─────────────────────────────────────────────────────────────

def _prijzen() -> dict:
    try:
        with open(PRIJZEN_PAD, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def kosten_eur(tier: str, in_tokens: int, uit_tokens: int, prijzen: dict | None = None) -> float | None:
    """Kosten van één call in euro, of None als de prijs van deze trede onbekend is.

    None ≠ 0. Een onbekende prijs als nul tellen maakt een verbruiksoverzicht onwaar op
    precies de plek waar het duur kan worden."""
    prijzen = prijzen if prijzen is not None else _prijzen()
    trede = (prijzen.get("tredes") or {}).get(tier or "")
    if not trede or trede.get("in") is None or trede.get("uit") is None:
        return None
    usd = (in_tokens / 1_000_000) * trede["in"] + (uit_tokens / 1_000_000) * trede["uit"]
    return usd * float(prijzen.get("usd_per_eur") or 1.0)


def verbruik(data_dir: str, call_sites: set[str] | None = None, dagen: int = 14,
             nu: float | None = None) -> dict:
    """Verbruik per call_site over de laatste `dagen`, uit het echte usage-log.

    Eén scan over het bestand (niet 14×), en de uitkomst scheidt bewust wat geteld kon worden
    van wat niet: `onbekende_calls` zijn calls op een trede zonder prijs. Die verdwijnen niet
    stilletjes in het totaal."""
    import datetime

    nu = nu or time.time()
    vandaag = datetime.datetime.fromtimestamp(nu, datetime.timezone.utc).date()
    venster = {(vandaag - datetime.timedelta(days=n)).isoformat() for n in range(dagen)}
    prijzen = _prijzen()

    per_site: dict[str, dict] = {}
    totaal_eur, onbekende_calls = 0.0, 0
    pad = os.path.join(data_dir, "llm_usage.jsonl")
    try:
        with open(pad, encoding="utf-8") as f:
            for regel in f:
                regel = regel.strip()
                if not regel:
                    continue
                try:
                    rij = json.loads(regel)
                except ValueError:
                    continue
                if rij.get("day") not in venster:
                    continue
                site = rij.get("call_site") or "onbekend"
                if call_sites is not None and site not in call_sites:
                    continue
                vak = per_site.setdefault(site, {"calls": 0, "tokens": 0, "eur": 0.0,
                                                 "onbekend": 0, "tier": rij.get("tier", "")})
                vak["calls"] += 1
                vak["tokens"] += int(rij.get("tokens") or 0)
                vak["tier"] = rij.get("tier", vak["tier"])
                eur = kosten_eur(rij.get("tier", ""), int(rij.get("in_tokens") or 0),
                                 int(rij.get("out_tokens") or 0), prijzen)
                if eur is None:
                    vak["onbekend"] += 1
                    onbekende_calls += 1
                else:
                    vak["eur"] += eur
                    totaal_eur += eur
    except OSError:
        pass
    return {"per_site": per_site, "totaal_eur": round(totaal_eur, 4),
            "onbekende_calls": onbekende_calls, "dagen": dagen,
            "geschat": True}          # tokens zijn schattingen (llm_usage.estimated), dus euro's ook
