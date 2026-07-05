"""Actief/inactief-status per databron (`data/sources.json`). Bewust los van 'gekoppeld' (catalogus)
en van het vers-signaal (observaties): dit bepaalt of de dag-puls een bron ophaalt.

Structuur: {"<source>": {"active": bool, "configured": bool|None}}.
- active:     alleen actieve bronnen worden door de puls opgehaald. Default: alle bronnen INACTIEF
              (fail-safe — geen ongevraagde externe API-calls). Activeren is mens-gated (CLI).
- configured: laatste is_configured()-uitkomst van de puls (creds aanwezig?). None = nog niet gecheckt.
              Voedt de aparte 'niet geconfigureerd'-status, los van 'dood' (geconfigureerd maar geen data).
"""
from __future__ import annotations
import json

from nooch_village.util import atomic_write_json


class SourceStatusStore:
    def __init__(self, path: str):
        self.path = path
        try:
            with open(path, encoding="utf-8") as f:
                self._d = json.load(f) or {}
        except Exception:
            self._d = {}

    def active(self, source: str) -> bool:
        return bool((self._d.get(source) or {}).get("active", False))

    def configured(self, source: str):
        """True/False als de puls het al checkte, anders None (onbekend)."""
        return (self._d.get(source) or {}).get("configured")

    def set_active(self, source: str, value: bool) -> None:
        self._d.setdefault(source, {})["active"] = bool(value)
        self._save()

    def set_configured(self, source: str, value: bool) -> None:
        self._d.setdefault(source, {})["configured"] = bool(value)
        self._save()

    def all(self) -> dict:
        return dict(self._d)

    def _save(self) -> None:
        atomic_write_json(self.path, self._d)
