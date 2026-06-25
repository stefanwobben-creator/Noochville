"""Trend-toestand uit een interest-over-time-reeks (Google Trends, ~5 jaar maandelijks).

Een ervaren trendwatcher leest niet één percentage maar de vórm van de curve: stijgt het nog,
is het afgevlakt, is de piek voorbij, of zakt het weg. Deze module zet een reeks relatieve
interesse-waarden om in zo'n toestand. Pure functie, geen I/O — los te testen.
"""
from __future__ import annotations

STATES = ("opkomend", "stabiel", "piek-voorbij", "dalend")


def _slope(ys: list[float]) -> float:
    """Kleinste-kwadraten-helling per stap (maand)."""
    m = len(ys)
    if m < 2:
        return 0.0
    mx = (m - 1) / 2.0
    my = sum(ys) / m
    num = sum((i - mx) * (y - my) for i, y in enumerate(ys))
    den = sum((i - mx) ** 2 for i in range(m))
    return num / den if den else 0.0


def trend_state(values, *, threshold: float = 0.01) -> str | None:
    """Classificeer een interesse-reeks in opkomend / stabiel / piek-voorbij / dalend.

    threshold = minimale genormaliseerde helling per stap (fractie van het gemiddelde niveau)
    om als stijging/daling te tellen; daaronder is het 'stabiel'. None bij te weinig data.
    """
    vals = [float(v) for v in (values or []) if isinstance(v, (int, float))]
    if len(vals) < 8:
        return None
    n = len(vals)
    avg = (sum(vals) / n) or 1.0
    overall = _slope(vals) / avg
    recent = (_slope(vals[-12:]) if n >= 12 else _slope(vals[n // 2:])) / avg
    peak = max(range(n), key=lambda i: vals[i])

    if overall < -threshold:
        return "dalend"
    if recent > threshold and overall > 0:
        return "opkomend"
    if peak < n - 6 and vals[peak] > avg * 1.25 and recent < 0:
        return "piek-voorbij"
    return "stabiel"


_STATE_VIEW = {
    "opkomend":     "▲ opkomend",
    "stabiel":      "▬ stabiel",
    "piek-voorbij": "⤵ piek voorbij",
    "dalend":       "▼ dalend",
}


def trend_state_label(state: str | None) -> str:
    """Leesbaar label met pijl voor de cockpit."""
    return _STATE_VIEW.get(state or "", "—")
