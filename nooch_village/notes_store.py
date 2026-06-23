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

    def enrich(self, note_id: str, nieuwe_reference: str | None = None) -> Insight | None:
        """Verrijk een bestaande kaart met een nieuwe grounding: voeg bron toe,
        hoog de grounding-teller op, en zet last_updated_at op nu. Claim en status
        blijven ongemoeid. Geeft de verrijkte kaart terug, of None als hij niet bestaat."""
        bestaand = self.get(note_id)
        if bestaand is None:
            return None
        if nieuwe_reference and nieuwe_reference not in (bestaand.reference or ""):
            if bestaand.reference:
                bestaand.reference = bestaand.reference + "; " + nieuwe_reference
            else:
                bestaand.reference = nieuwe_reference
        bestaand.grounding_count += 1
        from datetime import datetime
        bestaand.last_updated_at = datetime.now()
        self._notes[note_id] = bestaand.model_dump(mode="json")
        self._save()
        return bestaand

    def link(self, from_id: str, to_id: str) -> Insight | None:
        """Verbind twee bestaande kaartjes: voeg `to_id` toe aan de links_to van
        `from_id`. Gericht (van bron naar doel), idempotent (geen dubbele link) en
        fail-closed: bestaat een van beide niet, of wijst het kaartje naar zichzelf,
        dan gebeurt er niets en is het resultaat None. Geeft anders het bijgewerkte
        bron-kaartje terug."""
        if from_id == to_id:
            return None
        bron = self.get(from_id)
        doel = self.get(to_id)
        if bron is None or doel is None:
            return None
        if to_id not in bron.links_to:
            bron.links_to.append(to_id)
            from datetime import datetime
            bron.last_updated_at = datetime.now()
            self._notes[from_id] = bron.model_dump(mode="json")
            self._save()
        return bron

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
