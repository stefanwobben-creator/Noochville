"""claims_labels.py — de gratis labels van de claim-checker.

Elke keer dat compliance een vlag wegwuift ("dit is geen claim") of een gemiste claim tot regel
promoveert ("dit had je moeten vangen"), ontstaat een label: een menselijk oordeel over een concrete
zin. Dat is gratis trainingsmateriaal dat normaal verdampt in een muisklik. Hier wordt het bewaard.

Waar het naartoe gaat:
- **negatieven** (geen claim) voeden de prompt van `claims_modelpas`, zodat dezelfde over-vlag niet
  elke week terugkomt.
- **positieven** (wél claim) worden een echte regel in de claims-database, en zijn daarnaast de
  evaluatieset waarmee je later kunt meten of de modelpas beter wordt.

Append-only JSONL naast de stores, hetzelfde patroon als `gap_ledger`: een label is een waarneming
met een tijdstip, geen state die je muteert. Fail-soft — een label mag nooit een klik laten klappen.
"""
from __future__ import annotations

import json
import logging
import os
import time

log = logging.getLogger("village.claims.labels")

BESTAND = "claims_labels.jsonl"
CLAIM = "claim"                    # wél een claim: dit had de scan moeten vangen
GEEN_CLAIM = "geen-claim"          # over-vlag: de scan vlagde iets dat geen claim is
_LABELS = (CLAIM, GEEN_CLAIM)


def pad(data_dir: str) -> str:
    return os.path.join(data_dir, BESTAND)


def leg_vast(data_dir: str, *, fragment: str, label: str, pagina: str = "", door: str = "",
             reden: str = "", herkomst: str = "") -> dict | None:
    """Leg één menselijk oordeel vast. Geeft het record terug, of None bij een fout of leeg fragment."""
    fragment = (fragment or "").strip()
    if not fragment or label not in _LABELS:
        log.warning("label NIET vastgelegd: leeg fragment of onbekend label %r", label)
        return None
    rij = {"fragment": fragment[:300], "label": label, "pagina": (pagina or "")[:80],
           "door": door or "?", "reden": (reden or "")[:200], "herkomst": herkomst or "",
           "ts": time.time()}
    try:
        os.makedirs(data_dir, exist_ok=True)
        with open(pad(data_dir), "a", encoding="utf-8") as f:
            f.write(json.dumps(rij, ensure_ascii=False) + "\n")
    except Exception as e:                           # noqa: BLE001 — labelen mag een klik nooit breken
        log.warning("label niet weggeschreven: %s", e)
        return None
    log.info("🏷 claim-label [%s] %s", label, fragment[:80])
    return rij


def alle(data_dir: str) -> list[dict]:
    """Alle labels, oudste eerst. Kapotte regels worden overgeslagen, niet fataal."""
    uit = []
    try:
        with open(pad(data_dir), encoding="utf-8") as f:
            for regel in f:
                regel = regel.strip()
                if not regel:
                    continue
                try:
                    rij = json.loads(regel)
                except ValueError:
                    continue
                if isinstance(rij, dict):
                    uit.append(rij)
    except FileNotFoundError:
        return []
    except Exception as e:                           # noqa: BLE001
        log.warning("labelbestand onleesbaar: %s", e)
        return []
    return uit


def negatieven(data_dir: str, limiet: int = 8) -> list[str]:
    """De laatst weggewuifde fragmenten (nieuwste eerst) — het negatieve voorbeeldmateriaal voor
    de modelpas. Begrensd, want een prompt is geen archief."""
    rijen = [r for r in alle(data_dir) if r.get("label") == GEEN_CLAIM]
    rijen.sort(key=lambda r: r.get("ts", 0), reverse=True)
    return [str(r.get("fragment", "")) for r in rijen[:limiet] if r.get("fragment")]


def telling(data_dir: str) -> dict:
    """Hoeveel labels van elke soort — voor de weergave op het claims-scherm."""
    rijen = alle(data_dir)
    return {"claim": sum(1 for r in rijen if r.get("label") == CLAIM),
            "geen-claim": sum(1 for r in rijen if r.get("label") == GEEN_CLAIM),
            "totaal": len(rijen)}
