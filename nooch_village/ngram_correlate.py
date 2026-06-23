"""Lange-boog-correlaties tussen missietermen in de ngram-reeks.

Harry's echte waarde zit niet in recente hypes maar in structurele verschuiving over
decennia: welke termen samen opkomen (co-beweging) en welke elkaar verdringen
(substitutie, negatieve correlatie). Pure berekening op reeksen die de ngram-skill al
levert — geen netwerk, geen LLM.

Reeksen zijn relatieve frequenties (ngram-output), dus onderling vergelijkbaar. We
correleren alleen binnen dezelfde locale/corpus (gelijke jaren); de aanroeper groepeert.
"""
from __future__ import annotations
import math
from itertools import combinations


def pearson(xs: list[float], ys: list[float]) -> float | None:
    """Pearson-correlatie. None als ongedefinieerd (< 2 punten of nul-variantie)."""
    n = len(xs)
    if n < 2 or len(ys) != n:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sx = sum((x - mx) ** 2 for x in xs)
    sy = sum((y - my) ** 2 for y in ys)
    if sx == 0 or sy == 0:
        return None
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return cov / math.sqrt(sx * sy)


def _align(a: list[float], b: list[float]) -> tuple[list[float], list[float]]:
    """Lijn twee reeksen uit op de gemeenschappelijke lengte (vanaf het begin: zelfde
    startjaar) en laat paren weg waar een van beide None is."""
    m = min(len(a), len(b))
    xs, ys = [], []
    for i in range(m):
        if a[i] is not None and b[i] is not None:
            xs.append(a[i])
            ys.append(b[i])
    return xs, ys


def correlate_terms(series: dict[str, list[float]],
                    min_overlap: int = 5, strong: float = 0.6) -> list[dict]:
    """Pairwise correlatie tussen termen. Geeft per paar r, het aantal overlap-jaren en
    een label: 'co-beweging' (r >= strong), 'substitutie' (r <= -strong), anders 'zwak'.
    Gesorteerd op |r| aflopend (sterkste verbanden eerst)."""
    usable = [t for t, v in series.items()
              if v and sum(1 for x in v if x is not None) >= min_overlap]
    results: list[dict] = []
    for a, b in combinations(sorted(usable), 2):
        xs, ys = _align(series[a], series[b])
        if len(xs) < min_overlap:
            continue
        r = pearson(xs, ys)
        if r is None:
            continue
        label = ("co-beweging" if r >= strong else
                 "substitutie" if r <= -strong else "zwak")
        results.append({"a": a, "b": b, "r": round(r, 3), "label": label, "n": len(xs)})
    results.sort(key=lambda d: -abs(d["r"]))
    return results


def findings_from_rows(rows: list[dict], min_overlap: int = 5,
                       strong: float = 0.6) -> list[dict]:
    """Uit ngram-skill-rijen de sterkste co-beweging en sterkste substitutie per locale.

    Correleert alleen binnen dezelfde locale (gelijk corpus, gelijke jaren). Rijen zonder
    `timeseries` of met `no_data` worden overgeslagen. Geeft een platte lijst van bevindingen,
    elk met `locale` erbij. Leeg als er te weinig data is."""
    per_locale: dict[str, dict[str, list]] = {}
    for r in rows:
        ts = r.get("timeseries")
        if r.get("no_data") or not ts:
            continue
        per_locale.setdefault(r.get("locale", "?"), {})[r["term"]] = ts

    out: list[dict] = []
    for locale, series in sorted(per_locale.items()):
        cors = correlate_terms(series, min_overlap, strong)
        co  = next((c for c in cors if c["label"] == "co-beweging"), None)
        sub = next((c for c in cors if c["label"] == "substitutie"), None)
        if co:
            out.append({**co, "locale": locale})
        if sub:
            out.append({**sub, "locale": locale})
    return out
