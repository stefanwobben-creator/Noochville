"""CO2-KPI van het dorp — geschatte inference-emissies van alle LLM-calls.

Context-KPI: NIET 'lager = beter'. Nul calls is een dood dorp; we bewaken uitschieters en trend, niet
minimalisatie. Eenheid: gram CO2e per dag. Grondslag: leveranciers-LCA waar beschikbaar + geschatte
factoren voor de overige tredes. EXPLICIET GEEN ISO-claim.

Kernprincipe (zelfde lijn als de rest van het dorp): we verzinnen geen factoren. `EMISSION_FACTORS` is
LEEG tot een mens er een ECHTE, bronvermelde waarde in zet. Een call zonder bekende factor telt als
'ongeschat' en wordt apart gerapporteerd — NOOIT stilzwijgend als nul. Zo liegt de tegel niet: hij
zegt eerlijk 'X gram geschat, N calls nog ongeschat' in plaats van een mooi-ogend maar verzonnen getal.
"""
from __future__ import annotations

# Gram CO2e per 1000 tokens, per trede-vendor (de prefix vóór ':' in 'vendor:model').
# VUL DIT MET ECHTE, BRONVERMELDE WAARDEN — één regel per vendor, met de bron als comment. Voorbeeld:
#   "mistral": 0.0,   # bron: Mistral LCA-rapport 2025 (<url/naam>), <waarde> g CO2e / 1k tokens
#   "gemini":  0.0,   # bron: Google efficiency-publicatie (<url>), herrekend naar per-token
# Zolang een vendor hier ontbreekt, tellen zijn calls als 'ongeschat'. Geen gok, geen ISO-claim.
EMISSION_FACTORS: dict = {}


def factor_for(tier: str):
    """Gram CO2e per 1000 tokens voor deze trede, of None (ongeschat) als er geen bronvermelde factor is."""
    vendor = (tier or "").split(":", 1)[0].strip().lower()
    return EMISSION_FACTORS.get(vendor)


def co2_for_day(rows, factors: dict | None = None) -> dict:
    """Aggregeer usage-rijen van één dag tot geschatte gram CO2e.

    Rijen met een bekende factor tellen mee in `gram_co2e`; rijen zonder factor tellen NIET als nul maar
    apart als `ongeschat_calls`/`ongeschat_tokens`, zodat zichtbaar blijft hoeveel van de dag nog niet
    gedekt is door een bronvermelde factor. `factors` overschrijfbaar (voor tests)."""
    fac = EMISSION_FACTORS if factors is None else factors
    gram = 0.0
    tokens_geschat = ongeschat_calls = ongeschat_tokens = 0
    for r in rows or []:
        toks = int(r.get("tokens") or 0)
        vendor = str(r.get("tier") or "").split(":", 1)[0].strip().lower()
        f = fac.get(vendor)
        if f is None:
            ongeschat_calls += 1
            ongeschat_tokens += toks
            continue
        gram += toks / 1000.0 * float(f)
        tokens_geschat += toks
    return {
        "gram_co2e": round(gram, 2),
        "calls": len(rows or []),
        "tokens_geschat": tokens_geschat,
        "ongeschat_calls": ongeschat_calls,
        "ongeschat_tokens": ongeschat_tokens,
    }
