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
import os
import time

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


def voorkeur_van(persona, call_site: str) -> str | None:
    """De ladder-string van een al-opgehaalde persona. Los van `llm_voorkeur` omdat sommige
    aanroepers de persona al in handen hebben en geen stores kunnen doorgeven."""
    if persona is None:
        return None
    llm = getattr(persona, "llm", None) or {}
    keuze = ((llm.get("per_taak") or {}).get(call_site) or llm.get("default") or "").strip()
    return keuze or None


def llm_voorkeur(omgeving, role_id: str, call_site: str) -> str | None:
    """De ladder-string voor deze rol en taak, of None om de dorpsladder te gebruiken.

    None is een volwaardige uitkomst, geen fout: zonder persona-voorkeur hoort het gedrag
    byte-voor-byte gelijk te blijven aan hoe het dorp altijd al werkte."""
    return voorkeur_van(persona_van_rol(omgeving, role_id), call_site)


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
