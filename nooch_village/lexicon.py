"""Meertalig concept-register voor het Nooch-dorp.

Elk concept heeft een stabiele id en een woord per taal.
Status (approved/avoid/forbidden/escalated) geldt voor het concept — symmetrisch
over alle talen: is 'consument' avoid, dan is 'consumer' dat ook.

De Librarian cureert (schrijft); anderen lezen vrij.
"""
from __future__ import annotations
import os
from nooch_village.util import atomic_write_json, read_json
from datetime import datetime


class Lexicon:
    """Meertalig concept-register.

    Struct per concept:
        {
          "words":    {"nl": "consument", "en": "consumer"},
          "status":   "approved" | "avoid" | "forbidden" | "escalated",
          "rationale": str,
          "evidence": dict,
          "by":       str,
          "date":     "YYYY-MM-DD",
        }

    Framing-regels gelden symmetrisch: status is concept-eigenschap, niet
    woord-eigenschap. Voeg een taalvak toe via add_words(); status hoeft
    dan niet opnieuw opgegeven te worden.
    """

    def __init__(self, path: str):
        self.path = path
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        self._data = read_json(self.path, {})

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        atomic_write_json(self.path, self._data)

    # ── lezen (vrij voor iedereen) ─────────────────────────────────────────────

    def concept(self, concept_id: str) -> dict | None:
        return self._data.get(concept_id)

    def word_for(self, concept_id: str, lang: str) -> str | None:
        """Het woord voor een concept in een taal, of None als het taalvak ontbreekt."""
        c = self._data.get(concept_id)
        return c["words"].get(lang) if c else None

    def words_for_lang(self, lang: str,
                       status_filter: str | None = None) -> list[str]:
        """Alle woorden voor een taal, optioneel gefilterd op status."""
        result = []
        for entry in self._data.values():
            if status_filter and entry.get("status") != status_filter:
                continue
            w = entry.get("words", {}).get(lang)
            if w:
                result.append(w)
        return result

    def terms_for_lang(self, lang: str,
                       status_filter: str | None = None) -> list[tuple[str, str]]:
        """Geeft (term, concept_id) voor een taal, optioneel gefilterd op status."""
        result = []
        for cid, entry in self._data.items():
            if status_filter and entry.get("status") != status_filter:
                continue
            w = entry.get("words", {}).get(lang)
            if w:
                result.append((w, cid))
        return result

    def concept_for_word(self, word: str, lang: str | None = None) -> str | None:
        """Zoek het concept-id voor een woord (optioneel beperkt tot één taal)."""
        word_l = word.lower()
        for cid, entry in self._data.items():
            words = entry.get("words", {})
            if lang:
                if words.get(lang, "").lower() == word_l:
                    return cid
            else:
                if any(w.lower() == word_l for w in words.values()):
                    return cid
        return None

    def status_for_word(self, word: str, lang: str | None = None) -> str | None:
        """Status van een woord — geldt symmetrisch voor alle taalvarianten."""
        cid = self.concept_for_word(word, lang)
        return self._data[cid]["status"] if cid else None

    def is_forbidden(self, word: str, lang: str | None = None) -> bool:
        return self.status_for_word(word, lang) in ("forbidden", "avoid")

    def is_approved(self, word: str, lang: str | None = None) -> bool:
        return self.status_for_word(word, lang) == "approved"

    def all(self) -> dict:
        return self._data

    # ── cureren (alleen de Librarian) ──────────────────────────────────────────

    def add_concept(self, concept_id: str, words: dict[str, str],
                    status: str, rationale: str = "",
                    evidence: dict | None = None,
                    by: str = "Librarian", schendt: str = "") -> dict:
        """Voeg een concept toe of overschrijf het volledig.
        Status geldt symmetrisch voor alle taalvarianten.

        `schendt` = het GRONDWET-PRINCIPE dat dit concept schendt (bijv. "geen leer" voor bijenwas).
        Alleen zinvol bij status `avoid`/`forbidden`. Zonder dit veld kan een rol die een signaal
        wegwuift alleen zeggen "stond op een lijst"; mét dit veld citeert hij het principe, en is
        de dismiss herleidbaar tot de grondwet in plaats van tot een tabel."""
        entry = {
            "words": words,
            "status": status,
            "rationale": rationale,
            "schendt": schendt,
            "evidence": evidence or {},
            "by": by,
            "date": datetime.now().strftime("%Y-%m-%d"),
        }
        self._data[concept_id] = entry
        self._save()
        return entry

    def add_words(self, concept_id: str, words: dict[str, str]) -> bool:
        """Voeg taalvakken toe aan een bestaand concept (status ongewijzigd).
        Retourneert False als het concept niet bestaat."""
        if concept_id not in self._data:
            return False
        self._data[concept_id]["words"].update(words)
        self._save()
        return True

    def annoteer(self, concept_id: str, regel: str) -> bool:
        """Vul de rationale van een bestaand concept aan met één regel. Idempotent.

        Bestaat naast `add_concept` omdat die het concept VOLLEDIG overschrijft: wie alleen de
        rationale wil laten groeien moet daar woorden, status, evidence en `by` ongewijzigd
        meegeven, en één vergeten veld wist stilletjes wat een ander heeft vastgelegd. Een
        annotatie is een andere handeling dan een herdefinitie, dus krijgt ze haar eigen ingang.

        Retourneert False als het concept niet bestaat of de regel er al staat — in beide gevallen
        is er niets geschreven, en dat verschil moet de aanroeper kunnen zien."""
        regel = (regel or "").strip()
        entry = self._data.get(concept_id)
        if entry is None or not regel:
            return False
        huidig = str(entry.get("rationale") or "").strip()
        if regel in huidig:
            return False
        entry["rationale"] = f"{huidig} {regel}".strip() if huidig else regel
        self._save()
        return True

    def seed(self, concepts: list[dict]) -> int:
        """Seed het lexicon idempotent — bestaande entries worden niet overschreven.
        Retourneert het aantal nieuw toegevoegde concepten."""
        added = 0
        for c in concepts:
            cid = c["concept_id"]
            if cid not in self._data:
                self._data[cid] = {
                    "words":    c["words"],
                    "status":   c["status"],
                    "rationale": c.get("rationale", ""),
                    "schendt":  c.get("schendt", ""),
                    "evidence": c.get("evidence", {}),
                    "by":       c.get("by", "seed"),
                    "date":     c.get("date", datetime.now().strftime("%Y-%m-%d")),
                }
                added += 1
        if added:
            self._save()
        return added


    def schendt_principe(self, word: str, lang: str | None = None) -> tuple[str, str, str] | None:
        """Schendt dit woord een grondwet-principe? → (concept_id, principe, rationale) of None.

        Alleen voor `avoid`/`forbidden` mét een `schendt`-veld. Een avoid-concept zonder principe
        geeft None: dan is er niets te citeren, en een dismiss zonder citeerbaar principe is precies
        de black-box die we niet willen."""
        cid = self.concept_for_word(word, lang)
        if not cid:
            return None
        entry = self._data.get(cid) or {}
        if entry.get("status") not in ("avoid", "forbidden"):
            return None
        principe = str(entry.get("schendt") or "").strip()
        return (cid, principe, str(entry.get("rationale") or "")) if principe else None
