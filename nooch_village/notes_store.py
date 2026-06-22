from __future__ import annotations
import json, os, re
from nooch_village.insight import Insight


def _woorden(tekst: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", tekst.lower()) if w}


class NotesStore:
    def __init__(self, path: str = "data/notes.json"):
        self._path = path
        self._notes: dict[str, dict] = self._load()

    def _load(self) -> dict:
        if not os.path.exists(self._path):
            return {}
        with open(self._path, encoding="utf-8") as f:
            return json.load(f)

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._notes, f, indent=2, ensure_ascii=False)

    def add(self, note: Insight) -> None:
        if note.id in self._notes:
            raise ValueError(f"Note id '{note.id}' bestaat al")
        self._notes[note.id] = note.model_dump(mode="json")
        self._save()

    def get(self, note_id: str) -> Insight | None:
        data = self._notes.get(note_id)
        return Insight(**data) if data else None

    def all(self) -> list[Insight]:
        return [Insight(**d) for d in self._notes.values()]

    def by_concept(self, concept_id: str) -> list[Insight]:
        return [n for n in self.all() if n.concept_id == concept_id]

    def relevant_for(self, word: str, limit: int = 5) -> list[Insight]:
        """Vind kaartjes die termen delen met `word`, gewogen op zeldzaamheid.
        Een gedeeld woord telt zwaarder naarmate minder kaartjes het bevatten —
        zo onderscheidt 'barefoot' (zeldzaam) zich van 'shoes' (overal). Geen vaste
        stopwoordenlijst: wat generiek is, leidt het systeem zelf af uit de kaartjes.
        Matcht op het word-veld; kaartjes zonder word doen niet mee.
        Geeft de sterkste matches eerst, max `limit`."""
        if not word:
            return []
        kandidaten = [n for n in self.all() if n.word]
        if not kandidaten:
            return []

        zoek = _woorden(word)
        doc_freq: dict[str, int] = {}
        for n in kandidaten:
            for w in _woorden(n.word):
                doc_freq[w] = doc_freq.get(w, 0) + 1

        gescoord: list[tuple[float, Insight]] = []
        for n in kandidaten:
            if n.word == word:
                continue
            gedeeld = zoek & _woorden(n.word)
            score = sum(1.0 / doc_freq[w] for w in gedeeld)
            if score > 0:
                gescoord.append((score, n))

        gescoord.sort(key=lambda t: t[0], reverse=True)
        return [n for _, n in gescoord[:limit]]
