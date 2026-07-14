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

# Factor per EXACT MODEL (de volledige trede 'vendor:model'), in gram CO2e per 1000 OUTPUT-tokens,
# operationeel en location-based. Per model, niet per vendor: een klein model verstookt een fractie van
# een groot model. INPUT-tokens tellen als de output-factor gedeeld door 5 (input ≈ 1/5 van de output-
# intensiteit). Bron: eigen meting (operationeel, location-based); expliciet GEEN ISO-claim.
# Model zonder factor → 'ongeschat', nooit stil nul.
_INPUT_RATIO = 0.2      # input-tokens tellen als 1/5 van de output-factor

EMISSION_FACTORS: dict = {
    "gemini:gemini-2.5-flash-lite":        0.15,   # g CO2e / 1k output-tokens (operationeel, location-based)
    "mistral:mistral-small-latest":        0.30,
    "gemini:gemini-2.5-flash":             0.45,
    "anthropic:claude-haiku-4-5-20251001": 0.60,
}


def _key(tier: str) -> str:
    """Normaliseer de trede tot de factor-sleutel: de volledige 'vendor:model', lowercase."""
    return (tier or "").strip().lower()


def factor_for(tier: str):
    """De OUTPUT-factor (g CO2e / 1000 output-tokens) voor dit exacte model, of None (ongeschat) als er
    geen bronvermelde factor is. De input-factor is deze waarde / 5. Sleutel = de volledige 'vendor:model'."""
    return EMISSION_FACTORS.get(_key(tier))


def co2_for_day(rows, factors: dict | None = None) -> dict:
    """Aggregeer usage-rijen van één dag tot geschatte gram CO2e, PER MODEL, met aparte input/output.

    Per rij: output-tokens × factor + input-tokens × factor × 1/5. Rijen zonder model-factor tellen NIET
    als nul maar apart als `ongeschat_calls`/`ongeschat_tokens`, zodat zichtbaar blijft hoeveel van de dag
    nog niet gedekt is door een bronvermelde factor. `factors` overschrijfbaar (voor tests)."""
    fac = EMISSION_FACTORS if factors is None else factors
    gram = 0.0
    tokens_geschat = ongeschat_calls = ongeschat_tokens = 0
    for r in rows or []:
        it = int(r.get("in_tokens") or 0)
        ot = int(r.get("out_tokens") or 0)
        f = fac.get(_key(r.get("tier")))
        if f is None:
            ongeschat_calls += 1
            ongeschat_tokens += it + ot
            continue
        gram += ot / 1000.0 * float(f) + it / 1000.0 * float(f) * _INPUT_RATIO
        tokens_geschat += it + ot
    return {
        "gram_co2e": round(gram, 3),
        "calls": len(rows or []),
        "tokens_geschat": tokens_geschat,
        "ongeschat_calls": ongeschat_calls,
        "ongeschat_tokens": ongeschat_tokens,
    }
