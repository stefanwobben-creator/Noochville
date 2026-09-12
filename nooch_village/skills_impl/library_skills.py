from __future__ import annotations
import re, json
from nooch_village.skills import Skill
from nooch_village.llm import reason
from nooch_village.skills_impl.field_note import MISSION

# Heuristiek (werkt zonder LLM-key): transparante regels i.p.v. een black box.
MISSION_CORE = ["plasticvrij", "plastic free", "zonder plastic", "plantbased",
                "plant-based", "duurzaam", "duurzame", "circulair", "ethisch",
                "op bestelling", "made in europe", "europa"]
RISK = {
    "vegan": "vegan wordt vaak met plastic (PU/PVC) geassocieerd; risico op off-mission publiek",
    "goedkoop": "goedkoop trekt prijsvechters; botst met de eerlijke prijs",
    "cheap": "cheap trekt prijsvechters; botst met de eerlijke prijs",
    "leer": "leer is door de missie uitgesloten",
    "leather": "leather is door de missie uitgesloten",
}
FORBIDDEN_CLAIM = ["biologisch afbreekbaar", "100%", "co2-neutraal", "co2 neutraal", "klimaatneutraal"]

# Talen waarin we de missie-woordenschat uit het Lexicon lezen.
_CORE_LANGS = ("en", "nl")
# "<risk> free/vrij/frei": de AFWEZIGHEID van het risico is juist missie-positief.
# 'leather free' / 'leervrij' is geen leer-risico maar precies waar Nooch voor staat.
_NEGATORS = ("vrije", "free", "frei", "vrij")


def _norm(s: str) -> str:
    """Normaliseer koppelteken en spatie tot één vorm, zodat 'plastic-free' en
    'plastic free' hetzelfde matchen."""
    return s.lower().replace("-", " ")


def _statussen() -> tuple:
    """De status-enum van de bibliotheek — één bron (library.VALID_STATUSES), niet overgetypt."""
    from nooch_village.library import VALID_STATUSES
    return tuple(VALID_STATUSES)


def _als_set(statuses) -> set[str]:
    """`statuses` als set van statusnamen. Een kale string ('approved' of 'approved,forbidden') werd
    als set van LETTERS gelezen — {'a','p',…} — en filterde dan alles weg (skill-review 12-09-2026)."""
    if isinstance(statuses, str):
        return {x.strip() for x in statuses.replace(";", ",").split(",") if x.strip()}
    return {str(x).strip() for x in (statuses or ()) if str(x).strip()}


class LibraryListSkill(Skill):
    name = "library_list"
    cost = "free"
    description = ("List the terms in the word library for one or more statuses (default: approved and "
                   "insight_statement), optionally filtered on locale — term, status, locale, concept.")
    input_schema = ("statuses: list of str or comma-separated str (optional — any of "
                    "approved | forbidden | avoid | escalated | insight_statement; default "
                    "['approved', 'insight_statement']); locale: str (optional — 'nl' or 'en')")
    output_schema = "terms: list of {term, status, locale, concept_id, gemet_id}, count"

    _DEFAULT_STATUSES = ("approved", "insight_statement")

    def validate_payload(self, payload: dict, context) -> list:
        """Een status buiten de enum filtert stil alles weg; bij het plannen tegenhouden."""
        st = (payload or {}).get("statuses")
        if st is None:
            return []
        onbekend = sorted(_als_set(st) - set(_statussen()))
        return ([f"'statuses' contains unknown status(es) {onbekend}; use one of {list(_statussen())}"]
                if onbekend else [])

    def run(self, payload: dict, context) -> dict:
        p = payload or {}
        statuses = _als_set(p.get("statuses")) if p.get("statuses") is not None \
            else set(self._DEFAULT_STATUSES)
        locale_filter: str | None = p.get("locale")

        terms = []
        for word, entry in context.library.all().items():
            if entry.get("status") not in statuses:
                continue
            term_locale = entry.get("locale")
            if locale_filter is not None and term_locale != locale_filter:
                continue
            terms.append({
                "term": word,
                "status": entry["status"],
                "locale": term_locale,
                "concept_id": entry.get("concept_id"),
                "gemet_id": entry.get("gemet_id"),
            })

        return {"terms": terms, "count": len(terms)}


class LibraryLookupSkill(Skill):
    name = "library_lookup"
    cost = "free"
    description = ("Read the status of ONE word in the word library (approved | forbidden | avoid | "
                   "escalated | insight_statement) with its rationale; a word not in the library is "
                   "reported as not found. Read-only, for every role.")
    # Machine-leesbaar contract: de planner (inhabitant._missing_required) markeert een item
    # zónder 'word' vóór uitvoering als niet-uitvoerbaar, i.p.v. het te laten draaien en live
    # te crashen op payload["word"] (de KeyError 'word' die Lara zag, founder 19-20 jul).
    required_payload = ("word",)
    input_schema = "word: str (required — one term per call; batch over several calls yourself)"
    output_schema = "word, status, rationale, text | no_data+reason (not in the library) | error"

    def run(self, payload: dict, context) -> dict:
        word = (payload or {}).get("word")
        if not word:
            return {"error": "ontbrekende parameter 'word' — geef één term per aanroep"}
        e = context.library.status(word)
        if not e:
            # Onbekend woord = geen antwoord. `word` is geen META-sleutel, dus de eigen term won de
            # wall en het item werd afgevinkt als beantwoord (live: 15 van 18, skill-review
            # 12-09-2026). Nu een gemelde nul: 📭, het item telt als kennisgat.
            return {"word": word, "status": "unknown", "no_data": True,
                    "reason": f"'{word}' is not in the word library — no status, no rationale"}
        return {"word": word, "status": e["status"], "rationale": e.get("rationale", ""),
                "text": f"'{word}' is {e['status']}" + (f": {e.get('rationale')}" if e.get("rationale") else "")}


class KeywordReviewSkill(Skill):
    name = "keyword_review"
    cost = "free"
    description = ("Judge a candidate word against the mission (model or heuristic) plus demand "
                   "evidence: approve, reject, escalate or known. Librarian only (library domain).")
    # Eén woord per aanroep (zie library_lookup): het contract laat de planner een bundel-in-één
    # of leeg 'word' vóór uitvoering afvangen i.p.v. de KeyError 'word' live.
    required_payload = ("word",)
    input_schema = ("word: str (required — one candidate term per call); "
                    "demand: dict (optional — search-volume evidence from KeywordsEverywhere)")

    def run(self, payload: dict, context) -> dict:
        word = (payload or {}).get("word")
        if not word:
            return {"error": "ontbrekende parameter 'word' — beoordeel één term per aanroep"}
        demand = (payload or {}).get("demand", {})
        existing = context.library.status(word)
        if existing and existing["status"] in ("approved", "forbidden", "avoid"):
            return {"word": word, "decision": "known", "status": existing["status"],
                    "reason": "already recorded in the library"}

        # Auto-approve op echt zoekvolume (KeywordsEverywhere). Missie-risico's
        # (RISK / FORBIDDEN_CLAIM) gaan NOOIT automatisch door op volume — die blijven
        # mens-gated en komen in het dashboard.
        block, _ = self._mission_block(word)
        if block is None:
            vol = self._search_volume(demand)
            threshold = self._auto_approve_volume(context)
            if threshold > 0 and vol >= threshold:
                return {"word": word, "decision": "approve", "basis": "volume",
                        "reason": f"real search volume {vol}/month ≥ threshold {threshold} (KeywordsEverywhere)",
                        "demand": demand, "alignment_heuristic": "approve"}

        h_decision, h_reason = self._heuristic(word, demand, context)
        llm = self._llm(word, demand)
        decision, reason_txt, basis = (llm[0], llm[1], "llm") if llm else (h_decision, h_reason, "heuristic")
        return {"word": word, "decision": decision, "reason": reason_txt, "basis": basis,
                "demand": demand, "alignment_heuristic": h_decision}

    @staticmethod
    def _search_volume(demand: dict) -> int:
        """Echt maandelijks zoekvolume uit de demand (KeywordsEverywhere-veld 'volume'/'vol').
        Bewust NIET 'interest' (GSC-impressies) — alleen echt KE-volume telt voor auto-approve."""
        try:
            return int(demand.get("volume") or demand.get("vol") or 0)
        except (TypeError, ValueError):
            return 0

    def _auto_approve_volume(self, context) -> int:
        """Drempel waarboven echt zoekvolume automatisch goedkeurt. 0 = uit."""
        try:
            return int(getattr(context, "settings", {}).get("ke_auto_approve_volume", "100"))
        except (TypeError, ValueError):
            return 100

    def _mission_block(self, word: str):
        """Missie-poort: onbewezen claim → reject, risico-woord (niet ontkend) → escalate.
        Geen blokkade → (None, ""). Gedeeld door run() (volume-gate) en _heuristic()."""
        w = word.lower()
        for term in FORBIDDEN_CLAIM:
            if term in w:
                return "reject", f"contains an unproven claim ('{term}')"
        for term, why in RISK.items():
            if re.search(rf"\b{re.escape(term)}", w) and not self._negated(w, term):
                return "escalate", why
        return None, ""

    def _has_demand(self, demand: dict) -> bool:
        if not demand:
            return False
        return demand.get("signal") in ("rising", "positive") or (demand.get("interest", 0) or 0) > 10

    def _mission_core(self, context) -> list[str]:
        """Missie-kernwoorden, genormaliseerd. Vereniging van de hardcoded baseline en de
        approved Lexicon-woorden (en+nl), zodat ook Engelse missiewoorden als 'sustainable'
        matchen. Geen Lexicon → alleen de baseline (vangnet)."""
        terms = {_norm(c) for c in MISSION_CORE}
        lex = getattr(context, "lexicon", None)
        if lex is not None:
            for lang in _CORE_LANGS:
                for w in lex.words_for_lang(lang, status_filter="approved"):
                    terms.add(_norm(w))
        return sorted(terms)

    def _negated(self, w: str, term: str) -> bool:
        """Staat er direct na het risico-woord een ontkenner (free/vrij/frei)?
        Dan is het juist missie-positief, geen risico."""
        neg = "|".join(_NEGATORS)
        return re.search(rf"\b{re.escape(term)}[\s-]*(?:{neg})\b", w) is not None

    def _heuristic(self, word: str, demand: dict, context=None):
        block, why = self._mission_block(word)
        if block is not None:
            return block, why
        core_terms = self._mission_core(context)
        nw = _norm(word.lower())
        core = any(c in nw for c in core_terms)
        if core and self._has_demand(demand):
            return "approve", "mission core and there is demonstrable demand"
        if core:
            return "escalate", "fits the mission but no demonstrated demand"
        return "escalate", "no clear mission signal; human judgement requested"

    def _llm(self, word: str, demand: dict):
        prompt = (
            f"You are the Librarian of Nooch.earth, keeper of the approved vocabulary.\n"
            f"Mission:\n{MISSION}\n\n"
            f"Candidate word: '{word}'. Demand signal: {json.dumps(demand, ensure_ascii=False)}.\n"
            "Can this word safely be used in content, given the mission (no plastic, no leather, "
            "a fair price, transparency)? Watch for hidden conflicts, for instance that 'vegan' is "
            "often associated with plastic. Judge only from the word, the mission and the demand "
            "signal above; if you cannot tell, escalate.\n"
            "Answer on EXACTLY one line in this format:\n"
            "DECISION: approve|reject|escalate | REASON: <short reason in English>"
        )
        out = reason(prompt, call_site="skill_library_review")
        if not out:
            return None
        m = re.search(r"DECISION:\s*(approve|reject|escalate)\s*\|\s*REASON:\s*(.+)", out, re.I | re.S)
        if not m:
            return None
        return (m.group(1).lower(), m.group(2).strip())
