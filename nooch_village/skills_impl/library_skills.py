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


class LibraryListSkill(Skill):
    name = "library_list"
    cost = "free"
    description = "Geeft alle termen terug voor een of meer statussen, optioneel gefilterd op locale."

    _DEFAULT_STATUSES = ("approved", "insight_statement")

    def run(self, payload: dict, context) -> dict:
        statuses = set(payload.get("statuses", self._DEFAULT_STATUSES))
        locale_filter: str | None = payload.get("locale")

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
    description = "Leest de status van een woord uit de bibliotheek (read-only, voor iedereen)."

    def run(self, payload: dict, context) -> dict:
        word = payload["word"]
        e = context.library.status(word)
        return {"word": word,
                "status": e["status"] if e else "unknown",
                "rationale": e.get("rationale", "") if e else ""}


class KeywordReviewSkill(Skill):
    name = "keyword_review"
    cost = "free"
    description = "Beoordeelt een kandidaat-woord tegen de missie (LLM of heuristiek) + vraag-bewijs."

    def run(self, payload: dict, context) -> dict:
        word = payload["word"]
        demand = payload.get("demand", {})
        existing = context.library.status(word)
        if existing and existing["status"] in ("approved", "forbidden", "avoid"):
            return {"word": word, "decision": "known", "status": existing["status"],
                    "reason": "al vastgelegd in de bibliotheek"}

        h_decision, h_reason = self._heuristic(word, demand, context)
        llm = self._llm(word, demand)
        decision, reason_txt, basis = (llm[0], llm[1], "llm") if llm else (h_decision, h_reason, "heuristic")
        return {"word": word, "decision": decision, "reason": reason_txt, "basis": basis,
                "demand": demand, "alignment_heuristic": h_decision}

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
        w = word.lower()
        for term in FORBIDDEN_CLAIM:
            if term in w:
                return "reject", f"bevat een onbewezen claim ('{term}')"
        for term, why in RISK.items():
            if re.search(rf"\b{re.escape(term)}", w):
                if self._negated(w, term):
                    continue  # 'leather free'/'leervrij': de afwezigheid is on-mission
                return "escalate", why
        core_terms = self._mission_core(context)
        nw = _norm(w)
        core = any(c in nw for c in core_terms)
        if core and self._has_demand(demand):
            return "approve", "missie-kern en er is aantoonbare vraag"
        if core:
            return "escalate", "past bij de missie maar geen aangetoonde vraag"
        return "escalate", "geen duidelijk missie-signaal; menselijk oordeel gevraagd"

    def _llm(self, word: str, demand: dict):
        prompt = (
            f"Je bent de Librarian van Nooch.earth, hoeder van de goedgekeurde woordenschat.\n"
            f"Missie:\n{MISSION}\n\n"
            f"Kandidaat-woord: '{word}'. Vraag-signaal: {json.dumps(demand, ensure_ascii=False)}.\n"
            "Mag dit woord veilig in content gebruikt worden, gezien de missie (geen plastic, "
            "geen leer, eerlijke prijs, transparantie)? Let op verborgen conflicten, bijvoorbeeld "
            "dat 'vegan' vaak met plastic geassocieerd wordt.\n"
            "Antwoord op EXACT één regel in dit formaat:\n"
            "DECISION: approve|reject|escalate | REASON: <korte reden>"
        )
        out = reason(prompt)
        if not out:
            return None
        m = re.search(r"DECISION:\s*(approve|reject|escalate)\s*\|\s*REASON:\s*(.+)", out, re.I | re.S)
        if not m:
            return None
        return (m.group(1).lower(), m.group(2).strip())
