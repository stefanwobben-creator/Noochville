"""CO2-KPI van het dorp — geschatte inference-emissies van alle LLM-calls.

Context-KPI: NIET 'lager = beter'. Nul calls is een dood dorp; we bewaken uitschieters en trend, niet
minimalisatie. Eenheid: gram CO2e per dag. Grondslag: leveranciers-LCA waar beschikbaar + geschatte
factoren voor de overige tredes. EXPLICIET GEEN ISO-claim.

Kernprincipe (zelfde lijn als de rest van het dorp): we verzinnen geen factoren. De factoren leven in
`config/co2_factoren.json` — sleutel = de trede 'vendor:model' zoals llm.py hem logt (dezelfde sleutels
als `config/llm_prijzen.json`), per regel een factor, een bron en een datum. `EMISSION_FACTORS` in code
is LEEG: tot scope 58 stonden hier vier factoren met als bron "eigen meting", in tegenspraak met deze
docstring (skill-review 12-09-2026); nu is er één plek waar een mens een bron invult, en tellen de
premium-tredes mee zodra ze daar een factor hebben. Een call zonder bekende factor telt als
'ongeschat' en wordt apart gerapporteerd — NOOIT stilzwijgend als nul. Zo liegt de tegel niet: hij
zegt eerlijk 'X gram geschat, N calls nog ongeschat' in plaats van een mooi-ogend maar verzonnen getal.
"""
from __future__ import annotations

import json
import logging
import os

log = logging.getLogger("village.co2")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACTOREN_PAD = os.path.join(BASE_DIR, "config", "co2_factoren.json")

#: Bewust leeg: de factoren komen uit config/co2_factoren.json (zie de module-docstring).
EMISSION_FACTORS: dict = {}
#: Terugval voor de input-verhouding als de config hem niet noemt (input ≈ 1/5 van de output-
#: intensiteit). De config is leidend; dit getal staat hier alleen zodat een kapotte config niet
#: stil naar 0 valt.
_INPUT_RATIO_DEFAULT = 0.2


def _key(tier: str) -> str:
    """Normaliseer de trede tot de factor-sleutel: de volledige 'vendor:model', lowercase — dezelfde
    sleutel als in llm_prijzen.json, zodat één trede op beide plekken onder één naam staat."""
    return (tier or "").strip().lower()


def laad_config(pad: str | None = None) -> dict:
    """De ruwe config (tredes met factor/bron/datum, input_ratio). Fail-soft: onleesbaar → {} en een
    logregel; dan is elke call 'ongeschat', wat eerlijker is dan een verzonnen factor."""
    p = pad or FACTOREN_PAD
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception as e:                       # noqa: BLE001 — een kapotte config mag de puls niet breken
        log.warning("co2_factoren.json onleesbaar (%s): alle calls tellen als ongeschat", e)
        return {}


def factoren(config: dict | None = None) -> dict:
    """{genormaliseerde trede: factor} uit de config; alleen regels met een numerieke factor."""
    cfg = laad_config() if config is None else config
    uit = {}
    for trede, regel in (cfg.get("tredes") or {}).items():
        f = regel.get("factor") if isinstance(regel, dict) else regel
        try:
            if f is not None:
                uit[_key(trede)] = float(f)
        except (TypeError, ValueError):
            log.warning("co2_factoren.json: factor van '%s' is geen getal (%r) — trede telt als ongeschat", trede, f)
    return uit


def input_ratio(config: dict | None = None) -> float:
    cfg = laad_config() if config is None else config
    try:
        return float(cfg.get("input_ratio"))
    except (TypeError, ValueError):
        return _INPUT_RATIO_DEFAULT


def factor_for(tier: str, factors: dict | None = None):
    """De OUTPUT-factor (g CO2e / 1000 output-tokens) voor dit exacte model, of None (ongeschat) als er
    geen bronvermelde factor is. De input-factor is deze waarde × input_ratio. Sleutel = 'vendor:model'."""
    fac = factoren() if factors is None else factors
    return fac.get(_key(tier))


def co2_for_day(rows, factors: dict | None = None, *, ratio: float | None = None) -> dict:
    """Aggregeer usage-rijen van één dag tot geschatte gram CO2e, PER MODEL, met aparte input/output.

    Per rij: output-tokens × factor + input-tokens × factor × input_ratio. Rijen zonder model-factor
    tellen NIET als nul maar apart als `ongeschat_calls`/`ongeschat_tokens`, zodat zichtbaar blijft
    hoeveel van de dag nog niet gedekt is door een bronvermelde factor. `factors`/`ratio`
    overschrijfbaar (voor tests); default uit config/co2_factoren.json."""
    cfg = laad_config() if (factors is None or ratio is None) else {}
    fac = factoren(cfg) if factors is None else {_key(k): float(v) for k, v in factors.items()}
    r_in = input_ratio(cfg) if ratio is None else float(ratio)
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
        gram += ot / 1000.0 * float(f) + it / 1000.0 * float(f) * r_in
        tokens_geschat += it + ot
    return {
        "gram_co2e": round(gram, 3),
        "calls": len(rows or []),
        "tokens_geschat": tokens_geschat,
        "ongeschat_calls": ongeschat_calls,
        "ongeschat_tokens": ongeschat_tokens,
    }
