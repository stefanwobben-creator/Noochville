"""NgramCultureSkill — leest de lange-termijn culturele taalverschuiving via
het onofficiële JSON-endpoint van Google Books Ngram Viewer.

Dit is GEEN huidige zoekvraag maar een culturele tijdseries over decennia. We
vragen op tot het huidige jaar en laten de bron teruggeven wat hij heeft; het
echte eindjaar wordt door het corpus bepaald, niet door een eigen cap. Fail closed
als het netwerk niet bereikbaar is.

Locale-model:
  NL-woorden → corpus 10 (Dutch 2012)
  EN-woorden → corpus 26 (English 2019)
  Woorden komen uit het Lexicon (context.lexicon); valt terug op zaad-termen.

Output: `rows` (locale-bewust) + `terms` (backward compat).
  Elke row: {concept, locale, term, corpus, signal, freq_last}
        of: {concept, locale, term, corpus, no_data: True, reason: str}
  "geen data" is expliciet onderscheiden van een echte nul of vlak signaal.
"""
from __future__ import annotations
import datetime, json, time, urllib.request, urllib.parse
from nooch_village.skills import Skill

# Zaad-termen met expliciete locale — worden alleen gebruikt als het Lexicon ontbreekt
_SEED_TERMS: dict[str, list[str]] = {
    "nl": ["burger", "consument", "regeneratief", "plasticvrij", "duurzaam"],
    "en": ["citizen", "consumer", "regenerative", "plastic-free", "sustainable", "sufficiency"],
}

# Termen die op een Nederlandstalig corpus wijzen (voor payload-override zonder Lexicon)
_NL_INDICATORS = frozenset([
    "burger", "burgers", "consument", "consumenten", "duurzaam", "duurzame",
    "schoenen", "kleding", "milieu", "eerlijk", "transparantie", "bewust",
    "bewuste", "plastic-vrij", "plasticvrij", "regeneratief", "overproductie",
    "behoeften", "gemeenschap", "soberheid", "veganistisch",
])

_CORPUS_EN = 26   # English (2019)
_CORPUS_NL = 10   # Dutch (2012 — meest stabiele NL-corpus in de JSON-API)
_LANG_TO_CORPUS = {"nl": _CORPUS_NL, "en": _CORPUS_EN}
_YEAR_START = 1980
_SMOOTHING  = 3
# Geen eigen eindjaar-cap: we vragen op tot het huidige jaar en laten het corpus
# bepalen waar de data echt ophoudt (was hardgecodeerd op 2019, dat was zelf-opgelegd).
_RECENT_YEARS = 10   # venster voor de recente helling


def _detect_corpus(term: str) -> int:
    """Auto-detectie als fallback voor los opgegeven termen zonder Lexicon."""
    words = set(term.lower().replace("-", " ").replace("_", " ").split())
    return _CORPUS_NL if words & _NL_INDICATORS else _CORPUS_EN


def _derive_signal(timeseries: list[float]) -> dict:
    """Leidt richting af: stijgend / dalend / vlak.

    Gebruikt slope_recent (laatste _RECENT_YEARS jaar) als primair signaal.
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

    direction = (
        "stijgend" if slope_recent > threshold else
        "dalend"   if slope_recent < -threshold else
        "vlak"
    )
    return {
        "direction":     direction,
        "slope_recent":  round(slope_recent, 12),
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


def _locale_term_groups(context) -> dict[str, list[tuple[str, str]]]:
    """Laadt per locale de te bevragen termen vanuit het Lexicon.

    Returns:
        {lang: [(term, concept_id), ...]}
        Alle talen die het Lexicon kent, aangevuld met Library-goedkeuringen
        waarvoor nog geen concept bestaat.

    Valt terug op _SEED_TERMS als het Lexicon niet beschikbaar is.
    """
    lexicon = getattr(context, "lexicon", None)
    if not lexicon:
        return {
            lang: [(t, t) for t in terms]
            for lang, terms in _SEED_TERMS.items()
        }

    groups: dict[str, list[tuple[str, str]]] = {}
    seen_terms: set[str] = set()

    for cid, entry in lexicon.all().items():
        for lang, word in entry.get("words", {}).items():
            if word:
                groups.setdefault(lang, []).append((word, cid))
                seen_terms.add(word.lower())

    # Voeg Library-woorden toe die nog niet in het Lexicon zitten
    lib = getattr(context, "library", None)
    if lib:
        for word, entry in lib.all().items():
            if entry.get("status") == "approved" and word.lower() not in seen_terms:
                lang = "nl" if _detect_corpus(word) == _CORPUS_NL else "en"
                groups.setdefault(lang, []).append((word, word))
                seen_terms.add(word.lower())

    return groups


class NgramCultureSkill(Skill):
    name = "ngram_culture"
    cost = "rate_limited"
    description = (
        "Analyseert de lange-termijn culturele taalverschuiving via Google Books Ngram Viewer. "
        "Geeft per term/locale de richting (stijgend/dalend/vlak) over decennia. "
        "NL-woorden → corpus 10 (2012); EN-woorden → corpus 26 (2019). "
        "Fail-closed per locale: één locale-fout faalt alleen dat segment."
    )

    def run(self, payload: dict, context) -> dict:
        year_start = int(payload.get("year_start", _YEAR_START))
        year_end   = int(payload.get("year_end",   datetime.date.today().year))
        smoothing  = int(payload.get("smoothing",  _SMOOTHING))

        # Payload-override: losse termen zonder Lexicon-context
        if payload.get("terms"):
            locale_groups: dict[str, list[tuple[str, str]]] = {}
            for term in payload["terms"]:
                lang = "nl" if _detect_corpus(term) == _CORPUS_NL else "en"
                locale_groups.setdefault(lang, []).append((term, term))
        else:
            locale_groups = _locale_term_groups(context)

        rows: list[dict] = []
        legacy_terms: dict[str, dict] = {}

        for lang, term_pairs in locale_groups.items():
            corpus = _LANG_TO_CORPUS.get(lang, _CORPUS_EN)
            terms_list = [t for t, _ in term_pairs]
            concept_of = {t: c for t, c in term_pairs}

            for i in range(0, len(terms_list), 5):
                batch = terms_list[i:i + 5]
                try:
                    raw   = _fetch_ngram(batch, corpus, year_start, year_end, smoothing)
                    found = {item.get("ngram", "").lower(): item for item in raw}
                    for term in batch:
                        item = found.get(term.lower())
                        if item and item.get("timeseries"):
                            ts     = item["timeseries"]
                            signal = _derive_signal(ts)
                            row = {
                                "concept":    concept_of.get(term, term),
                                "locale":     lang,
                                "term":       term,
                                "corpus":     corpus,
                                "signal":     signal,
                                "freq_last":  round(ts[-1], 12) if ts else None,
                                "freq_peak":  round(max(ts), 12) if ts else None,
                                "timeseries": ts,   # volledige jaarreeks voor correlatie-analyse
                            }
                            legacy_terms[term] = {
                                "corpus":    corpus,
                                "signal":    signal,
                                "freq_last": row["freq_last"],
                                "freq_peak": row["freq_peak"],
                            }
                        else:
                            row = {
                                "concept": concept_of.get(term, term),
                                "locale":  lang,
                                "term":    term,
                                "corpus":  corpus,
                                "no_data": True,
                                "reason":  "term niet gevonden in corpus",
                            }
                            legacy_terms[term] = {
                                "corpus": corpus,
                                "error":  "term niet gevonden in corpus",
                            }
                        rows.append(row)
                except Exception as exc:
                    for term in batch:
                        row = {
                            "concept": concept_of.get(term, term),
                            "locale":  lang,
                            "term":    term,
                            "corpus":  corpus,
                            "no_data": True,
                            "reason":  str(exc),
                        }
                        rows.append(row)
                        legacy_terms[term] = {"corpus": corpus, "error": str(exc)}
                time.sleep(1.5)   # onofficieel endpoint — vriendelijk blijven

        return {
            "rows":       rows,          # locale-bewust (nieuw)
            "terms":      legacy_terms,  # backward compat
            "year_start": year_start,
            "year_end":   year_end,
        }
