"""NgramCultureSkill — leest de lange-termijn culturele taalverschuiving via
het onofficiële JSON-endpoint van Google Books Ngram Viewer.

Data stopt ~2019: dit is GEEN huidige zoekvraag maar een culturele tijdseries
over decennia. Fail closed als het netwerk niet bereikbaar is.
"""
from __future__ import annotations
import json, time, urllib.request, urllib.parse
from nooch_village.skills import Skill

# Zaad-termen die het burgerframe en de missie dragen; aangevuld vanuit de Library
_SEED_TERMS: list[str] = [
    "burger",        # NL: burger/burgerkader
    "consument",     # NL: consumentisme vs. burgerwaarden
    "sufficiency",   # EN: sufficiency movement
    "regenerative",  # EN: regenerative design
    "plastic-free",  # EN: plastic-free movement
]

# Termen die op een Nederlandstalig corpus wijzen
_NL_INDICATORS = frozenset([
    "burger", "burgers", "consument", "consumenten", "duurzaam", "duurzame",
    "schoenen", "kleding", "milieu", "eerlijk", "transparantie", "bewust",
    "bewuste", "plastic-vrij", "overproductie", "behoeften", "gemeenschap",
])

_CORPUS_EN = 26   # English (2019)
_CORPUS_NL = 10   # Dutch (2012 — meest stabiele NL-corpus in de JSON-API)
_YEAR_START = 1980
_YEAR_END   = 2019
_SMOOTHING  = 3
_RECENT_YEARS = 10   # venster voor de recente helling


def _detect_corpus(term: str) -> int:
    words = set(term.lower().replace("-", " ").replace("_", " ").split())
    return _CORPUS_NL if words & _NL_INDICATORS else _CORPUS_EN


def _derive_signal(timeseries: list[float]) -> dict:
    """Leidt richting af: stijgend / dalend / vlak.

    Gebruikt twee hellingen:
    - slope_overall : over de hele reeks (trend over decennia)
    - slope_recent  : laatste _RECENT_YEARS jaar (huidige momentum)
    Beslissing op basis van slope_recent ten opzichte van het gemiddelde.
    """
    valid = [v for v in timeseries if v is not None]
    if len(valid) < 2:
        return {"direction": "onbekend", "slope_recent": None, "slope_overall": None}

    n = len(valid)
    slope_overall = (valid[-1] - valid[0]) / n

    recent = valid[-_RECENT_YEARS:] if n >= _RECENT_YEARS else valid
    slope_recent = (recent[-1] - recent[0]) / len(recent)

    avg = sum(valid) / n
    threshold = avg * 0.05 if avg > 0 else 1e-14

    if slope_recent > threshold:
        direction = "stijgend"
    elif slope_recent < -threshold:
        direction = "dalend"
    else:
        direction = "vlak"

    return {
        "direction": direction,
        "slope_recent": round(slope_recent, 12),
        "slope_overall": round(slope_overall, 12),
    }


def _fetch_ngram(batch: list[str], corpus: int,
                 year_start: int, year_end: int, smoothing: int) -> list[dict]:
    """Roept het onofficiële JSON-endpoint aan. Gooit bij netwerk- of parse-fouten."""
    params = urllib.parse.urlencode({
        "content":    ",".join(batch),
        "year_start": year_start,
        "year_end":   year_end,
        "corpus":     corpus,
        "smoothing":  smoothing,
    })
    url = f"https://books.google.com/ngrams/json?{params}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; NoochVillage/1.0; research)"
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def _load_lexicon_terms(context) -> list[str]:
    """Zaad + goedgekeurde bibliotheekwoorden (Librarian-domein, alleen lezen)."""
    terms = list(_SEED_TERMS)
    lib = getattr(context, "library", None)
    if lib:
        for word, entry in lib.all().items():
            if entry.get("status") == "approved" and word not in terms:
                terms.append(word)
    return terms


class NgramCultureSkill(Skill):
    name = "ngram_culture"
    description = (
        "Analyseert de lange-termijn culturele taalverschuiving via Google Books Ngram Viewer. "
        "Geeft per term de richting (stijgend/dalend/vlak) over decennia. "
        "Data stopt ~2019; geen huidige zoekvraag maar een culturele tijdseries."
    )

    def run(self, payload: dict, context) -> dict:
        terms: list[str] = payload.get("terms") or _load_lexicon_terms(context)
        year_start = int(payload.get("year_start", _YEAR_START))
        year_end   = int(payload.get("year_end",   _YEAR_END))
        smoothing  = int(payload.get("smoothing",  _SMOOTHING))

        # Groepeer per corpus; per groep max 5 termen per HTTP-request
        by_corpus: dict[int, list[str]] = {}
        for term in terms:
            by_corpus.setdefault(_detect_corpus(term), []).append(term)

        results: dict[str, dict] = {}
        for corpus, group in by_corpus.items():
            for i in range(0, len(group), 5):
                batch = group[i:i + 5]
                try:
                    raw = _fetch_ngram(batch, corpus, year_start, year_end, smoothing)
                    found = {item.get("ngram", "").lower(): item for item in raw}
                    for term in batch:
                        item = found.get(term.lower())
                        if item and item.get("timeseries"):
                            ts = item["timeseries"]
                            results[term] = {
                                "corpus":    corpus,
                                "signal":    _derive_signal(ts),
                                "freq_last": round(ts[-1], 12) if ts else None,
                                "freq_peak": round(max(ts), 12) if ts else None,
                            }
                        else:
                            results[term] = {
                                "corpus": corpus,
                                "error":  "term niet gevonden in corpus",
                            }
                except Exception as exc:
                    for term in batch:
                        results[term] = {"corpus": corpus, "error": str(exc)}
                time.sleep(1.5)   # onofficieel endpoint — vriendelijk blijven

        return {"terms": results, "year_start": year_start, "year_end": year_end}
