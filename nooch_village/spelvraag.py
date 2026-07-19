"""Spelvraag — de verleidelijke opening van de suggestiekaart (founder, 19 jul).

De deterministische voorzet (kennisbank_spel.spel_suggesties) blijft het startpunt van
het SPEL; dit module maakt er de UITNODIGING van: één kleine LLM-call herformuleert de
spanning in het cluster tot één vraag ("de claim is informatie, de vraag is verleiding").

Regels:
- de vraag mag alleen HERORDENEN wat al in de kaarten staat, nooit een feit toevoegen —
  een harde grond-check weigert jaartallen, percentages en grote getallen die niet
  letterlijk in de kaarten voorkomen (hallucinatie-guard, zelfde geest als Lara's
  "wijs elke claim zonder bron af");
- gecachet per cluster (data/spelvraag_cache.json): steady-state nul calls per GET,
  hooguit één generatie per verse kandidaat — bewuste herziening van het eerdere
  "geen LLM op GET"-besluit (founder, 19 jul), begrensd door de cache en het
  retry-venster van een dag voor mislukte generaties;
- fail-soft: geen bruikbare vraag → de caller toont gewoon de claim, zoals voorheen.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time

from nooch_village.llm import reason
from nooch_village.util import atomic_write_json

_CACHE_BESTAND = "spelvraag_cache.json"
_RETRY_NA_S = 24 * 3600          # mislukte generatie: hooguit één nieuwe poging per dag
_MAX_KAARTEN = 6                 # meer kaarten = langere prompt, niet méér spanning


def _sleutel(kand: dict) -> str:
    """Stabiele cache-sleutel: het cluster (gesorteerde atom_ids) + de voorzet-claim.
    Verandert het cluster of de representatieve kaart, dan is het een nieuwe vraag."""
    basis = "|".join(sorted(kand.get("atom_ids") or [])) + "§" + (kand.get("hunch") or "")[:80]
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


def _laad(pad: str) -> dict:
    try:
        with open(pad, encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _grond_ok(vraag: str, bronnen: str) -> bool:
    """Harde grond-check: elk jaartal, percentage of getal van drie of meer cijfers in de
    vraag moet letterlijk in de kaarten staan — de vraag mag herordenen, nooit toevoegen."""
    plat = bronnen.replace(" ", "")
    for m in re.findall(r"\b(?:19|20)\d{2}\b|\b\d+(?:[.,]\d+)?\s*%|\b\d{3,}\b", vraag):
        if m.replace(" ", "") not in plat:
            return False
    return True


def _valide(out, bronnen: str) -> str | None:
    """Eén nette vraag of None: 20-280 tekens, eindigt op '?', gegrond in de kaarten."""
    v = re.sub(r"\s+", " ", (out or "")).strip().strip('"“”‘’ ').strip()
    if not v or len(v) < 20 or len(v) > 280 or not v.endswith("?"):
        return None
    if not _grond_ok(v, bronnen):
        return None
    return v


def vraag_voor(kand: dict, atoms: dict, *, data_dir: str, reason_fn=reason,
               nu: float | None = None) -> str | None:
    """De gecachete spelvraag voor één kandidaat-cluster, of None (→ caller toont de claim).

    Hooguit één generatie per verse kandidaat; een mislukking wordt mét tijdstempel
    gecachet en pas na _RETRY_NA_S opnieuw geprobeerd — geen call-storm op GET, en een
    ladder die tijdelijk plat ligt maakt de kennisbank niet trager dan hij was."""
    pad = os.path.join(data_dir, _CACHE_BESTAND)
    cache = _laad(pad)
    k = _sleutel(kand)
    nu = time.time() if nu is None else nu
    rij = cache.get(k)
    if rij:
        if rij.get("vraag"):
            return rij["vraag"]
        if nu - (rij.get("at") or 0) < _RETRY_NA_S:
            return None
    claims = [((atoms.get(aid) or {}).get("claim") or "").strip()
              for aid in (kand.get("atom_ids") or [])[:_MAX_KAARTEN]]
    claims = [c for c in claims if c]
    vraag = None
    if claims:
        regels = "\n".join(f"- {c}" for c in claims)
        out = reason_fn(
            "Je schrijft de opening van een kennisspel in een kennisbank. Hieronder staan "
            "kaarten (claims) uit één cluster. Formuleer ÉÉN prikkelende Nederlandse vraag "
            "van maximaal twee zinnen die de spanning of het open eind tussen deze kaarten "
            "blootlegt.\n\n"
            "KEIHARDE REGEL: gebruik uitsluitend feiten die letterlijk in de kaarten staan. "
            "Voeg géén cijfers, data, namen of gebeurtenissen toe die er niet in staan.\n\n"
            f"KAARTEN:\n{regels}\n\n"
            "OUTPUT: alleen de vraag zelf, geen inleiding of aanhalingstekens.",
            max_tokens=120, call_site="spelvraag")
        vraag = _valide(out, " ".join(claims))
    cache[k] = {"vraag": vraag or "", "at": nu}
    atomic_write_json(pad, cache)
    return vraag
