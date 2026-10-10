"""De configuratie van de managementadministratie (Finance PR 1, 10 oktober 2026).

ÉÉN PLEK: `config/finance.json` — managementregels in vaste volgorde met hun groep en laag (het
voorbeeld-P&L), Venema-hoofdgroepen met een standaard-managementregel als voorstel, en batches.
Geen regel, groep of rekening in de code.
"""
from __future__ import annotations

import json
import os

_PAD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "finance.json")


def laad(pad: str = "") -> dict:
    with open(pad or _PAD, encoding="utf-8") as f:
        return json.load(f)


def regels(cfg: dict | None = None) -> list[dict]:
    """Alle managementregels in P&L-volgorde: [{key, label, groep, negatief}]."""
    cfg = cfg or laad()
    return [{**r, "groep": g["groep"], "negatief": bool(r.get("negatief"))}
            for g in cfg["management_lines"] for r in g["regels"]]


def regel(key: str, cfg: dict | None = None) -> dict | None:
    return next((r for r in regels(cfg) if r["key"] == key), None)


def standaard_regel(account: str, cfg: dict | None = None) -> str:
    """De voorgestelde managementregel bij een rekening: op code, en zolang er geen codes zijn op
    de naam van de hoofdgroep (NL of EN). "" als er geen voorstel is."""
    cfg = cfg or laad()
    a = " ".join(str(account or "").split()).lower()
    for acc in cfg.get("accounts") or []:
        namen = {str(acc.get(k) or "").strip().lower() for k in ("code", "naam_nl", "naam_en")}
        if a and a in namen - {""}:
            return acc.get("standaard_regel") or ""
    return ""
