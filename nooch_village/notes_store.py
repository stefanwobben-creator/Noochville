from __future__ import annotations
import json, os
from nooch_village.permanent_note import PermanentNote


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

    def add(self, note: PermanentNote) -> None:
        if note.id in self._notes:
            raise ValueError(f"Note id '{note.id}' bestaat al")
        self._notes[note.id] = note.model_dump(mode="json")
        self._save()

    def get(self, note_id: str) -> PermanentNote | None:
        data = self._notes.get(note_id)
        return PermanentNote(**data) if data else None

    def all(self) -> list[PermanentNote]:
        return [PermanentNote(**d) for d in self._notes.values()]
