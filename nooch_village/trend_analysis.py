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


def trend_state(values, *, threshold: float = 0.01, peak_drop: float = 0.25) -> str | None:
    """Classificeer een interesse-reeks in opkomend / stabiel / piek-voorbij / dalend.

    threshold = minimale genormaliseerde helling per stap (fractie van het gemiddelde niveau)
    om als stijging/daling te tellen; daaronder telt het als vlak.
    peak_drop = hoeveel het recente niveau onder de piek moet liggen (fractie) om 'piek-voorbij'
    te heten. Streng: een milde afkoeling vanaf een oude piek blijft 'stabiel'. None bij te weinig data.
    """
    vals = [float(v) for v in (values or []) if isinstance(v, (int, float))]
    if len(vals) < 8:
        return None
    n = len(vals)
    avg = (sum(vals) / n) or 1.0
    overall = _slope(vals) / avg
    recent = (_slope(vals[-12:]) if n >= 12 else _slope(vals[n // 2:])) / avg
    peak = max(range(n), key=lambda i: vals[i])
    recent_level = sum(vals[-12:]) / min(12, n)
    drop_from_peak = (vals[peak] - recent_level) / vals[peak] if vals[peak] else 0.0

    if overall < -threshold:
        return "dalend"
    if recent > threshold and overall >= 0:
        return "opkomend"
    # piek-voorbij: een duidelijke piek in het verleden ÉN het recente niveau ligt er fors
    # onder ÉN het loopt niet meer op. Anders (vlakke afkoeling, hoog plateau) → stabiel.
    if (peak < n - 6 and vals[peak] > avg * 1.25
            and drop_from_peak > peak_drop and recent <= 0):
        return "piek-voorbij"
    return "stabiel"


def recent_move(values, *, jump: float = 0.30, trim_last: int = 1) -> tuple[str | None, float | None]:
    """Detecteer een AANHOUDENDE recente verschuiving (opleving of daling) en geef de richting +
    procentuele verandering. Cadans-bewust: 5-jaars Google Trends is wekelijks (~260 punten),
    12-maands is maandelijks. Vergelijkt het recente kwartaal met het jaar daarvóór, zodat één
    losse uitschieter niet meetelt. Trimt het laatste (vaak onvolledige) Trends-punt weg.

    Retourneert ('stijgend'|'dalend'|None, pct). None = geen duidelijke verschuiving / te weinig data.
    """
    vals = [float(v) for v in (values or []) if isinstance(v, (int, float))]
    if trim_last and len(vals) > trim_last:
        vals = vals[:-trim_last]                           # laatste, vaak onvolledige periode eruit
    n = len(vals)
    recent_w, base_w = (13, 52) if n >= 160 else (3, 12)   # wekelijks vs maandelijks
    if n < recent_w + base_w:
        return (None, None)
    recent = sum(vals[-recent_w:]) / recent_w
    base = sum(vals[-(recent_w + base_w):-recent_w]) / base_w
    if base <= 0:
        return (None, None)
    pct = round((recent - base) / base * 100, 1)
    if pct >= jump * 100:
        return ("stijgend", pct)
    if pct <= -jump * 100:
        return ("dalend", pct)
    return (None, pct)


def recent_surge(values, **kw) -> bool:
    """Back-compat: True bij een aanhoudende recente OPLEVING (zie recent_move)."""
    return recent_move(values, **{k: v for k, v in kw.items() if k in ("jump", "trim_last")})[0] == "stijgend"


_STATE_VIEW = {
    "opkomend":     "▲ opkomend",
    "stabiel":      "▬ stabiel",
    "piek-voorbij": "⤵ piek voorbij",
    "dalend":       "▼ dalend",
}


def trend_state_label(state: str | None) -> str:
    """Leesbaar label met pijl voor de cockpit."""
    return _STATE_VIEW.get(state or "", "—")
