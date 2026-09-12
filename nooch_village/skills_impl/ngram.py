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
  Elke row: {concept, locale, term, corpus, signal, freq_last, freq_peak, timeseries, tekst}
        of: {concept, locale, term, corpus, no_data: True, reason: "term niet gevonden in corpus"}
        of: {concept, locale, term, corpus, error: str}          (netwerk-/parse-fout voor die batch)
  "geen data" is expliciet onderscheiden van een echte nul of vlak signaal, én van een storing.

TOPNIVEAU FAIL-CLOSED (scope 54, skill-review 12-09-2026). Tot dan was het resultaat ALTIJD
{rows, terms, year_start, year_end}: een run waarin élke term een time-out gaf, kwam terug als een
lijst rijen die elk `no_data` zeiden, en dat las de uitvoerlaag als GELUKT — 48 runs afgevinkt zonder
één cijfer, de Kroniek zei "bevestigd". Nu: alle rijen een storing → `error`; alle rijen "niet
gevonden" → `no_data` + reason; anders gelukt (een mix van gevonden en niet-gevonden is een antwoord).
`rows` blijft in alle drie de gevallen staan, want de TijdgeestWachter leest ze.

Per rij een `tekst` ("rising over 2010–2019; last 1.2e-06, peak 2.0e-06 in 2014") omdat de richting —
het hele punt van de skill — anders het verslag niet haalt: `signal` is een dict en geen strekkingveld.
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
    """Roept het onofficiële JSON-endpoint aan. Gooit bij netwerk- of parse-fouten.

    `case_insensitive=true` (scope 54): een term als "Vegan" aan het begin van een zin telde niet mee
    en een planner schrijft termen nu eens met, dan zonder hoofdletter. De bron geeft dan per term de
    losse varianten plus een "(All)"-rij met het totaal; `_match` kiest die laatste."""
    params = urllib.parse.urlencode({
        "content":    ",".join(batch),
        "year_start": year_start,
        "year_end":   year_end,
        "corpus":     corpus,
        "smoothing":  smoothing,
        "case_insensitive": "true",
    })
    url = f"https://books.google.com/ngrams/json?{params}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; NoochVillage/1.0; research)"
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def _match(found: dict, term: str):
    """De rij voor `term` uit de respons: bij case_insensitive de "(All)"-totaalrij, anders de
    exacte (kleine-letter-)vorm. None als de bron de term niet kent."""
    t = term.lower()
    return found.get(f"{t} (all)") or found.get(t)


_RICHTING_EN = {"stijgend": "rising", "dalend": "falling", "vlak": "flat", "onbekend": "unknown"}


def _rij_tekst(signal: dict, ts: list, year_start: int) -> str:
    """De strekking van één rij in één zin, Engels: richting, venster, laatste en piekwaarde.
    De piek krijgt zijn jaar (year_start + index), zodat "piek in 2014" leesbaar is."""
    valid = [v for v in ts if v is not None]
    if not valid:
        return "no data points"
    eind = year_start + len(ts) - 1
    venster = min(_RECENT_YEARS, len(valid))
    richting = _RICHTING_EN.get(str(signal.get("direction")), "unknown")
    piek = max(valid)
    piek_jaar = year_start + next(i for i, v in enumerate(ts) if v == piek)   # de eerste piek telt
    return (f"{richting} over {eind - venster + 1}–{eind}; last {valid[-1]:.1e}, "
            f"peak {piek:.1e} in {piek_jaar}")


def _corpus_uit_payload(payload: dict):
    """Het corpus dat de payload voorschrijft: `corpus` (int) wint, dan `locale` ('nl'|'en');
    None = per term detecteren (het oude gedrag, voor termen buiten de indicatorlijst een gok)."""
    c = (payload or {}).get("corpus")
    try:
        if c not in (None, ""):
            return int(c)
    except (TypeError, ValueError):
        pass
    loc = str((payload or {}).get("locale") or "").strip().lower()
    return _LANG_TO_CORPUS.get(loc)


def _als_tekst(rows: list[dict], year_start: int, year_end: int) -> str:
    """De leeswijzer: per richting de termen, plus wat niet gevonden of gestoord was."""
    groepen: dict[str, list[str]] = {}
    for r in rows:
        if r.get("error"):
            groepen.setdefault("failed", []).append(r["term"])
        elif r.get("no_data"):
            groepen.setdefault("not in corpus", []).append(r["term"])
        else:
            d = _RICHTING_EN.get(str((r.get("signal") or {}).get("direction")), "unknown")
            groepen.setdefault(d, []).append(r["term"])
    corpora = sorted({str(r.get("corpus")) for r in rows if r.get("corpus") is not None})
    gevonden = sum(1 for r in rows if not r.get("error") and not r.get("no_data"))
    kop = (f"{gevonden} of {len(rows)} term(s) found in Google Books Ngram (corpus {', '.join(corpora)}, "
           f"{year_start}–{year_end})")
    delen = [f"{k} — {', '.join(v)}" for k, v in groepen.items()]
    return kop + (": " + "; ".join(delen) if delen else "") + "."


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
    input_schema = ("terms: list[str] (required — the words or phrases to measure, at most 5 words each, "
                    "spelled as they appear in books, case-insensitive; give ONE language per call). "
                    "locale: 'nl'|'en' (recommended — the language of the terms; picks the corpus: nl → "
                    "Dutch 10 (data to 2012), en → English 26 (data to 2019); omitted = guessed per term "
                    "from a short Dutch word list). Optional: corpus: int (overrides locale) · "
                    "year_start: int (default 1980) · year_end: int (default: this year; the corpus ends "
                    "earlier) · smoothing: int (default 3)")
    required_payload = ("terms",)
    output_schema = ("list: rows: list[{term, locale, corpus, signal{direction: stijgend|dalend|vlak, "
                     "slope_recent}, freq_last, freq_peak, timeseries, tekst (one-line reading)} | a row "
                     "with no_data + reason when the corpus lacks the term, or error when the source "
                     "failed for that batch], text (summary for the wall) | no_data + reason (no term in "
                     "the corpus) | error (the source failed for every term)")
    cost = "rate_limited"
    description = (
        "How often a word or phrase appears in books per year over decades (Google Books Ngram): give "
        "terms of at most 5 words in ONE language and set locale 'nl' (Dutch corpus, data to 2012) or "
        "'en' (English corpus, data to 2019). Returns per term the direction (rising, falling, flat) "
        "over the last 10 corpus years, the last and peak frequency and the yearly series; 'no_data' "
        "when the corpus lacks the term. Fail-closed per batch."
    )

    def run(self, payload: dict, context) -> dict:
        payload = payload if isinstance(payload, dict) else {}
        from nooch_village.sleutelmasker import masker
        year_start = int(payload.get("year_start", _YEAR_START))
        year_end   = int(payload.get("year_end",   datetime.date.today().year))
        smoothing  = int(payload.get("smoothing",  _SMOOTHING))

        # Payload-override: losse termen zonder Lexicon-context. Het corpus komt uit de payload
        # (`corpus`/`locale`) als de planner dat zegt; anders per term geraden (indicatorlijst) —
        # en die lijst is kort, dus een Nederlands woord erbuiten belandde in het Engelse corpus.
        vast = _corpus_uit_payload(payload)
        if payload.get("terms"):
            termen = payload["terms"] if isinstance(payload["terms"], (list, tuple)) else [payload["terms"]]
            locale_groups: dict[str, list[tuple[str, str]]] = {}
            for term in termen:
                term = str(term or "").strip()
                if not term:
                    continue
                corpus = vast if vast is not None else _detect_corpus(term)
                lang = "nl" if corpus == _CORPUS_NL else "en"
                locale_groups.setdefault(lang, []).append((term, term))
        else:
            locale_groups = _locale_term_groups(context)

        rows: list[dict] = []
        legacy_terms: dict[str, dict] = {}

        for lang, term_pairs in locale_groups.items():
            corpus = vast if vast is not None else _LANG_TO_CORPUS.get(lang, _CORPUS_EN)
            terms_list = [t for t, _ in term_pairs]
            concept_of = {t: c for t, c in term_pairs}

            for i in range(0, len(terms_list), 5):
                batch = terms_list[i:i + 5]
                try:
                    raw   = _fetch_ngram(batch, corpus, year_start, year_end, smoothing)
                    found = {str(item.get("ngram", "")).lower(): item
                             for item in (raw or []) if isinstance(item, dict)}
                    for term in batch:
                        item = _match(found, term)
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
                                "tekst":      _rij_tekst(signal, ts, year_start),
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
                                "tekst":   f"not found in corpus {corpus}",   # de strekking voor het verslag
                            }
                            legacy_terms[term] = {
                                "corpus": corpus,
                                "error":  "term niet gevonden in corpus",
                            }
                        rows.append(row)
                except Exception as exc:
                    # Een storing is geen 'niet gevonden': de rij zegt `error`, zodat de
                    # NL-dekkingscheck hem niet als corpus-gat telt en het topniveau hem als
                    # storing kan optellen.
                    reden = masker(exc)
                    for term in batch:
                        rows.append({
                            "concept": concept_of.get(term, term),
                            "locale":  lang,
                            "term":    term,
                            "corpus":  corpus,
                            "error":   reden,
                        })
                        legacy_terms[term] = {"corpus": corpus, "error": reden}
                time.sleep(1.5)   # onofficieel endpoint — vriendelijk blijven

        uit = {
            "rows":       rows,          # locale-bewust (nieuw)
            "terms":      legacy_terms,  # backward compat
            "year_start": year_start,
            "year_end":   year_end,
        }
        gestoord = [r for r in rows if r.get("error")]
        gevonden = [r for r in rows if not r.get("error") and not r.get("no_data")]
        if not rows:
            return {**uit, "error": "geen termen om te meten"}
        if not gevonden and gestoord:
            # Niets gevonden én minstens één batch stuk: "niet in het corpus" is dan niet te
            # claimen — het item blijft open. Alle rijen stuk is het gemeten geval (48 runs
            # 'gelukt' zonder één cijfer); een deel stuk zonder één treffer is even onbeslist.
            return {**uit, "error": f"Google Books Ngram gaf voor {len(gestoord)} van {len(rows)} "
                                    f"term(en) een storing en vond de rest niet: {gestoord[0]['error']}"}
        if not gevonden:
            return {**uit, "no_data": True,
                    "reason": f"geen van de {len(rows)} term(en) komt voor in het corpus"}
        uit["text"] = _als_tekst(rows, year_start, year_end)
        return uit
