"""Inwoners (persona's) — het karakter los van de rol.

Een rol is het *wat* (capaciteit: purpose, accountabilities, skills/rugzak). Een inwoner is het
*wie* (personality: naam, MBTI, vrije instructies). The Source maakt inwoners aan en koppelt ze
aan rollen (Record.persona_id). Skills horen bij de rol, niet bij de inwoner — het karakter is
draagbaar, het gereedschap hoort bij de stoel. Zie docs/ONTWERP_inwoners.md.

NB: de naam `Inhabitant` is in code al de levende rol-agent (inhabitant.py). Daarom heet de
karakter-entiteit hier `Persona`. Naar de gebruiker toe heet het "inwoner".
"""
from __future__ import annotations
import json
import os
import uuid
from dataclasses import dataclass, asdict

from nooch_village.util import atomic_write_json

# Veelgebruikte MBTI-typen (validatie is licht: vrije tekst mag, maar we normaliseren naar hoofdletters).
_MBTI = {
    "INTJ", "INTP", "ENTJ", "ENTP", "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ", "ISTP", "ISFP", "ESTP", "ESFP",
}


@dataclass
class Persona:
    """Een inwoner: een herbruikbaar karakter dat een rol kan vervullen."""
    id: str
    name: str
    mbti: str = ""
    instructions: str = ""        # vrije personality-/specifieke instructies


def persona_prompt(p: Persona | dict | None) -> str:
    """Bouw de persona-preamble voor de LLM. Leeg als er geen inwoner is (neutrale stem).
    Het karakter kleurt TOON en aanpak, niet WAT de rol inhoudelijk kan."""
    if p is None:
        return ""
    name = p.get("name", "") if isinstance(p, dict) else p.name
    mbti = p.get("mbti", "") if isinstance(p, dict) else p.mbti
    instr = p.get("instructions", "") if isinstance(p, dict) else p.instructions
    if not (name or mbti or instr):
        return ""
    wie = name or "deze inwoner"
    kop = f"Je bent {wie}" + (f" ({mbti})" if mbti else "") + "."
    staart = (f" {instr.strip()}" if instr.strip() else "")
    return (kop + staart +
            " Laat je karakter doorklinken in toon en aanpak, niet in wat je inhoudelijk kunt.")


class PersonaStore:
    """JSON-store voor inwoners (data/personas.json). Achter dezelfde bestand-interface als de
    andere stores; The Source cureert (add/update/remove), de rest leest."""

    def __init__(self, path: str):
        self.path = path
        self._items: dict[str, dict] = {}
        if os.path.exists(path):
            try:
                self._items = json.load(open(path))
            except Exception:
                self._items = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        atomic_write_json(self.path, self._items)

    def add(self, name: str, mbti: str = "", instructions: str = "") -> Persona:
        """Maak een nieuwe inwoner. Naam verplicht; MBTI wordt genormaliseerd naar hoofdletters."""
        name = (name or "").strip()
        if not name:
            raise ValueError("een inwoner heeft een naam nodig")
        mbti = (mbti or "").strip().upper()
        pid = uuid.uuid4().hex[:12]
        p = Persona(id=pid, name=name[:60], mbti=mbti[:8], instructions=(instructions or "").strip()[:1000])
        self._items[pid] = asdict(p)
        self._save()
        return p

    def get(self, pid: str | None) -> Persona | None:
        if not pid:
            return None
        d = self._items.get(pid)
        return Persona(**d) if d else None

    def all(self) -> list[Persona]:
        return [Persona(**d) for d in sorted(self._items.values(), key=lambda x: x.get("name", ""))]

    def update(self, pid: str, *, name: str | None = None, mbti: str | None = None,
               instructions: str | None = None) -> Persona | None:
        d = self._items.get(pid)
        if d is None:
            return None
        if name is not None and name.strip():
            d["name"] = name.strip()[:60]
        if mbti is not None:
            d["mbti"] = mbti.strip().upper()[:8]
        if instructions is not None:
            d["instructions"] = instructions.strip()[:1000]
        self._save()
        return Persona(**d)

    def remove(self, pid: str) -> bool:
        if pid in self._items:
            del self._items[pid]
            self._save()
            return True
        return False
