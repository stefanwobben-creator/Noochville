"""claims_context.py — de contextlaag over de deterministische claim-scan (founder, 21 jul).

De regex-database (`claims_db.check_tekst`) vlagt op woordniveau: staat een verboden/risico-term
ergens in de tekst, dan is het een bevinding. Dat mist context. Een tekst die 'carbon neutral'
juist ontmaskert, een ontkenning ('a recycled lace does not fix a coal-fired factory'), een
citaat of een definitie krijgt zo onterecht een rode vlag.

Deze module legt ÉÉN LLM-oordeel over de rode/oranje bevindingen: wordt hier een marketingclaim
GEDAAN over Nooch's eigen product (iets wat ACM/EmpCo zou toetsen), of wordt de term alleen
besproken (kritiek, ontkenning, citaat, definitie, vraag, of over een ander merk)? 'geen-claim'
verhuist naar een aparte groep (`uitslag['in_context']`) en telt niet mee in de score; 'claim' en
niet-beoordeelde bevindingen blijven staan en tellen mee. Fail-soft: zonder LLM valt alles terug
op het oude, strenge gedrag (alles telt), expliciet gelabeld via `context_beoordeeld`.

Bewust term-niveau (v1): een term met meerdere vindplaatsen krijgt één oordeel; is er twijfel of
één vindplaats wél een claim is, dan luidt het oordeel 'claim' (streng). Puur logica met een
injecteerbare `reason_fn`, zodat dit testbaar is los van de LLM.
"""
from __future__ import annotations

import json
import re

from nooch_village.claims_db import score as _score
from nooch_village.llm import reason

_ZIN = re.compile(r"[^.!?\n]*[.!?]|[^.!?\n]+", re.S)


def zinnen_rond(tekst: str, frases, *, max_zinnen: int = 3, max_len: int = 220) -> list[str]:
    """De zinnen waarin één van `frases` voorkomt (case-insensitive), ontdubbeld en ingekort."""
    tekst = tekst or ""
    frases = [f for f in (frases or []) if f]
    treffers: list[str] = []
    for z in _ZIN.findall(tekst):
        zl = z.lower()
        if any(f.lower() in zl for f in frases):
            s = re.sub(r"\s+", " ", z).strip()
            if s and s not in treffers:
                treffers.append(s[:max_len])
        if len(treffers) >= max_zinnen:
            break
    return treffers


def beoordeel(tekst: str, bevindingen: list[dict], *, reason_fn=reason) -> bool:
    """Vraag de LLM per rode/oranje bevinding of het een echte claim is. Muteert de bevindingen
    (zet `context_oordeel` = 'claim'|'geen-claim'|'' en `context_reden`). Geeft terug of er
    daadwerkelijk beoordeeld is. Fail-soft: bij uitval blijft `context_oordeel` leeg (telt mee)."""
    kandidaten = [b for b in bevindingen if b.get("stoplicht") in ("red", "orange")]
    if not kandidaten:
        return False
    blokken = []
    for i, b in enumerate(kandidaten):
        ctx = zinnen_rond(tekst, b.get("gevonden") or [b.get("term", "")])
        blokken.append({"nr": i, "term": b.get("term", ""),
                        "contexten": ctx or ["(geen zin gevonden)"]})
    prompt = (
        "Je bent compliance-assistent voor Nooch (duurzame veganistische schoenen). Een regex-scan "
        "heeft onderstaande termen in een tekst gevlagd. Bepaal PER term of er in de context een "
        "MARKETINGCLAIM wordt GEDAAN over Nooch's eigen product of merk (iets wat een toezichthouder "
        "als ACM/EmpCo zou toetsen), OF dat de term alleen als onderwerp voorkomt: kritiek of "
        "ontmaskering, een ontkenning ('does not', 'niet', 'geen'), een citaat, een definitie, een "
        "vraag, of een uitspraak over een ánder merk.\n"
        "'claim' = er wordt echt iets beweerd waarmee Nooch zich zou aanprijzen. "
        "'geen-claim' = de term valt alleen als gespreksonderwerp.\n"
        "Bij twijfel, of als één vindplaats wél een claim lijkt: 'claim' (streng).\n\n"
        f"TERMEN MET CONTEXT:\n{json.dumps(blokken, ensure_ascii=False)}\n\n"
        'Antwoord UITSLUITEND met JSON: '
        '{"oordelen":[{"nr":0,"oordeel":"claim of geen-claim","reden":"kort"}]}')
    raw = reason_fn(prompt, max_tokens=700, json_mode=True, call_site="claims_context")
    data = _extract(raw)
    if not isinstance(data, dict) or not isinstance(data.get("oordelen"), list):
        return False
    per = {o["nr"]: o for o in data["oordelen"]
           if isinstance(o, dict) and isinstance(o.get("nr"), int)}
    for i, b in enumerate(kandidaten):
        o = per.get(i) or {}
        oordeel = o.get("oordeel")
        b["context_oordeel"] = ("geen-claim" if oordeel == "geen-claim"
                                else "claim" if oordeel == "claim" else "")
        b["context_reden"] = str(o.get("reden") or "")[:200]
    return True


def herweeg(uitslag: dict) -> dict:
    """Split 'geen-claim'-bevindingen af naar `uitslag['in_context']` en herbereken tellingen en
    score. Groen en escaleren blijven ongemoeid (die beoordeelt de contextlaag niet)."""
    bev = uitslag.get("bevindingen", [])
    blijft = [b for b in bev if b.get("context_oordeel") != "geen-claim"]
    uitslag["in_context"] = [b for b in bev if b.get("context_oordeel") == "geen-claim"]
    uitslag["bevindingen"] = blijft
    rood = sum(1 for b in blijft if b.get("stoplicht") == "red")
    oranje = sum(1 for b in blijft if b.get("stoplicht") == "orange")
    uitslag["rood"] = rood
    uitslag["oranje"] = oranje
    uitslag["groen"] = sum(1 for b in blijft if b.get("stoplicht") == "green")
    uitslag["score"] = _score(rood, oranje)
    return uitslag


def verrijk(uitslag: dict, *, reason_fn=reason) -> dict:
    """De volledige contextlaag: beoordeel + herweeg, fail-soft. Zet `context_beoordeeld` (bool)
    zodat de weergave kan tonen of het strenge oude gedrag geldt."""
    if uitslag.get("error"):
        return uitslag
    try:
        beoordeeld = beoordeel(uitslag.get("tekst", ""), uitslag.get("bevindingen", []),
                               reason_fn=reason_fn)
    except Exception:
        beoordeeld = False
    uitslag["context_beoordeeld"] = bool(beoordeeld)
    if beoordeeld:
        herweeg(uitslag)
    else:
        uitslag.setdefault("in_context", [])
    return uitslag


def _extract(raw):
    if not raw:
        return None
    s = re.sub(r"```(?:json)?", "", str(raw)).strip()
    try:
        return json.loads(s[s.find("{"):s.rfind("}") + 1])
    except (ValueError, IndexError):
        return None
