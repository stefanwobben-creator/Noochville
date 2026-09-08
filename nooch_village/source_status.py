"""Actief/inactief-status per databron (`data/sources.json`). Bewust los van 'gekoppeld' (catalogus)
en van het vers-signaal (observaties): dit bepaalt of de dag-puls een bron ophaalt.

Structuur: {"<source>": {"active": bool, "configured": bool|None}}.
- active:     alleen actieve bronnen worden door de puls opgehaald. Default: alle bronnen INACTIEF
              (fail-safe — geen ongevraagde externe API-calls). Activeren is mens-gated (CLI).
- configured: laatste is_configured()-uitkomst van de puls (creds aanwezig?). None = nog niet gecheckt.
              Voedt de aparte 'niet geconfigureerd'-status, los van 'dood' (geconfigureerd maar geen data).
"""
from __future__ import annotations

from nooch_village.util import JsonStore


class SourceStatusStore(JsonStore):
    """TWEE SCHRIJVERS, ÉÉN BESTAND. De collector (daemon) zet `configured` bij elke dag-puls; jij zet
    `active` aan en uit in het cockpit. Dat zijn twee processen op dezelfde `sources.json`.

    Vóór 8 september hield elk proces zijn eigen kopie in geheugen en schreef het hele bestand terug
    vanuit die kopie. Wie het laatst schreef won, en de ander merkte niets: je zette een bron uit, en
    bij de volgende puls schreef de daemon zijn oude snapshot terug en stond de bron weer aan.

    `JsonStore` lost dat op: elke schrijfmethode neemt het bestandsslot en leest ONDER dat slot vers
    van schijf. De guard-test `test_geen_ongelockte_write.py` noemde deze store nog "single-writer",
    en dat klopte al niet meer sinds het cockpit `set_active` kreeg."""

    _STATE = "_d"
    _WRITE_METHODS = ("set_active", "set_configured")

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
