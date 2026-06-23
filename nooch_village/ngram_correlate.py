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


def years_dict(values: list, year_start: int) -> dict[int, float]:
    """Zet een ngram-jaarlijst om naar {jaar: waarde} (index 0 = year_start). None's overslaan."""
    return {year_start + i: v for i, v in enumerate(values) if v is not None}


def calibrate(a: dict[int, float], b: dict[int, float], min_overlap: int = 5) -> dict:
    """Correleer twee {jaar: waarde}-reeksen over hun gedeelde jaren.

    Dit is de eerlijkheidstoets vóór we OpenAlex als voortzetting van ngram vertrouwen:
    correleren ze sterk over de overlap, dan is de proxy verdedigbaar. Geeft
    {'r', 'n', 'overlap': (van, tot)} of {'insufficient': True, 'n'} bij te weinig overlap.
    """
    shared = sorted(set(a) & set(b))
    if len(shared) < min_overlap:
        return {"insufficient": True, "n": len(shared)}
    r = pearson([a[y] for y in shared], [b[y] for y in shared])
    if r is None:
        return {"insufficient": True, "n": len(shared)}
    return {"r": round(r, 3), "n": len(shared), "overlap": (shared[0], shared[-1])}


def continue_arc(ngram: dict[int, float], openalex: dict[int, float],
                 anchor_year: int) -> dict[int, float]:
    """Geketende index, basis anchor_year = 100.

    Tot en met het ankerjaar: ngram, herschaald zodat het anker 100 is. Daarna: OpenAlex,
    herschaald op zijn eigen ankerwaarde. Beide raken elkaar op 100 in het ankerjaar, zodat de
    boog naadloos doorloopt voorbij de ngram-cutoff. Leeg als het anker in een van beide
    ontbreekt of nul is (dan kun je niet normaliseren)."""
    vn = ngram.get(anchor_year)
    vo = openalex.get(anchor_year)
    if not vn or not vo:
        return {}
    out: dict[int, float] = {}
    for y, v in sorted(ngram.items()):
        if y <= anchor_year:
            out[y] = round(100 * v / vn, 2)
    for y, v in sorted(openalex.items()):
        if y > anchor_year:
            out[y] = round(100 * v / vo, 2)
    return out


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
