"""Business-case: maakt van een spanning een afweegbare kans.

Elke inwoner die een voorstel doet (rol uitbreiden, nieuwe rol, project) hangt er een
business-case aan: een hypothese plus een schatting van verwacht effect, inspanning en
vertrouwen — afgewogen tegen de noordster (1 miljoen paar/jaar). De kansen-backlog rangschikt
hierop, zodat 'bol staan van spanningen' geen ruis wordt maar een geprioriteerde lijst.

Pure module: geen I/O, los testbaar.
"""
from __future__ import annotations

_EFFORT_RANGE = (1, 5)        # 1 = klein, 5 = groot
_TIERS = {                    # leesbare effect-tier als de inwoner geen getal kan geven
    "xs": 1, "s": 3, "m": 10, "l": 30, "xl": 100,
}


def make_business_case(metric: str = "pairs_sold", *, effect=0, effort: int = 3,
                       confidence: float = 0.5, horizon: str = "",
                       rationale: str = "") -> dict:
    """Bouw een genormaliseerde business-case. effect = geschatte bijdrage aan de metriek
    (getal of tier xs/s/m/l/xl); effort 1-5; confidence 0-1."""
    if isinstance(effect, str):
        effect = _TIERS.get(effect.strip().lower(), 0)
    try:
        effect = max(0.0, float(effect))
    except (TypeError, ValueError):
        effect = 0.0
    try:
        effort = int(effort)
    except (TypeError, ValueError):
        effort = 3
    effort = min(_EFFORT_RANGE[1], max(_EFFORT_RANGE[0], effort))
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = min(1.0, max(0.0, confidence))
    return {"metric": metric or "pairs_sold", "effect": effect, "effort": effort,
            "confidence": confidence, "horizon": horizon or "", "rationale": rationale or ""}


def business_value(bc: dict | None) -> float:
    """Verwachte waarde per eenheid inspanning: effect × confidence ÷ effort.
    None of incompleet → 0.0 (zakt naar de bodem van de backlog)."""
    if not isinstance(bc, dict):
        return 0.0
    effect = bc.get("effect") or 0
    confidence = bc.get("confidence")
    effort = bc.get("effort") or _EFFORT_RANGE[0]
    try:
        effect = float(effect)
        confidence = 0.5 if confidence is None else float(confidence)
        effort = max(1.0, float(effort))
    except (TypeError, ValueError):
        return 0.0
    return round(effect * confidence / effort, 2)


def format_business_case(bc: dict | None) -> str:
    """Compacte, leesbare samenvatting voor de cockpit/CLI."""
    if not isinstance(bc, dict):
        return "—"
    parts = [f"+{bc.get('effect', 0):g} {bc.get('metric', 'pairs_sold')}",
             f"effort {bc.get('effort', '?')}/5",
             f"zekerheid {round(float(bc.get('confidence', 0)) * 100)}%"]
    if bc.get("horizon"):
        parts.append(str(bc["horizon"]))
    return " · ".join(parts) + f"  → waarde {business_value(bc):g}"
