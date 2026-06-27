"""Noochie — de bestaande dorpsassistent (de warme, enthousiaste brug tussen de oprichter en de
bewoners; zie roles.Noochie en skills_impl/voorstel.py). Hier als globale launcher in cockpit 2.

Noochie is GEEN ambient agent: hij leest niet automatisch je scherm en handelt nooit zelf. Hij
voert een korte, geleide mini-triage (spanning → behoefte) en doet dan een gerichte suggestie.
Context van het scherm wordt alleen meegenomen als de mens dat zelf aanzet (zichtbaar via een chip).
Elke wijziging die eruit volgt loopt via de normale consent/inbox; Noochie stelt alleen voor.

Lichtgewicht store (data/noochie.json): één lopend gesprek per dorp (v1).
Fasen: ask_spanning -> ask_need -> free. `ctx` = door de mens meegegeven schermcontext (of leeg).
"""
from __future__ import annotations
import json
import os
import time

from nooch_village.util import atomic_write_json


class NoochieStore:
    def __init__(self, path: str):
        self.path = path
        self._st: dict = {"messages": [], "phase": "ask_spanning",
                          "spanning": "", "need": "", "ctx": ""}
        if os.path.exists(path):
            try:
                d = json.load(open(path))
                if isinstance(d, dict):
                    self._st.update(d)
            except Exception:
                pass

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        atomic_write_json(self.path, self._st)

    def state(self) -> dict:
        return dict(self._st)

    @property
    def messages(self) -> list[dict]:
        return list(self._st.get("messages", []))

    @property
    def phase(self) -> str:
        return self._st.get("phase", "ask_spanning")

    @property
    def ctx(self) -> str:
        return self._st.get("ctx", "")

    def add(self, who: str, text: str) -> None:
        """who = 'noochie' of 'jij'. Lege tekst wordt genegeerd."""
        if not (text or "").strip():
            return
        self._st.setdefault("messages", []).append(
            {"who": who, "text": text.strip(), "at": time.time()})
        self._save()

    def set_phase(self, phase: str) -> None:
        self._st["phase"] = phase
        self._save()

    def set_field(self, key: str, value: str) -> None:
        if key in ("spanning", "need", "ctx"):
            self._st[key] = (value or "").strip()
            self._save()

    def reset(self) -> None:
        self._st = {"messages": [], "phase": "ask_spanning",
                    "spanning": "", "need": "", "ctx": self._st.get("ctx", "")}
        self._save()
