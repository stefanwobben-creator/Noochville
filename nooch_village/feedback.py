"""Feedback — jouw oordeel over een kans als TRAININGSSIGNAAL voor de rollen.

Het idee (van de mens): wat er met een spanning gebeurt (hij sluit) staat los van wat het dorp
ervan leert. Niet elk 'nee' is een harde regel. Daarom kent een afronding een 'verdict':

  praise       👍 leuk idee — geen actie, maar positief signaal ("dit soort denken: meer van")
  soft_reject  🙂 nee, maar geen huis-regel — informatie/context, mag opnieuw bij andere situatie
  not_now      ⏳ goed idee, verkeerde timing — niet nu opnieuw voorstellen
  elsewhere    🌍 buiten NoochVille opgepakt — hoort niet in het dorp
  vision_drop  ✗ past niet binnen de visie — de ENIGE die een harde huis-regel wordt (constraints)

Alleen vision_drop blokkeert (via constraints.py). De rest zijn zachte, gewogen signalen die de
opportunity-reflex kleuren zonder dicht te timmeren. Opslag: data/feedback.json (gitignored).
"""
from __future__ import annotations
import os, time
from nooch_village.util import atomic_write_json, read_json

# Zachte verdicts (geen harde blokkade) en hoe ze in de reflex-prompt verschijnen.
SOFT_VERDICTS = {
    "praise":      ("👍 gewaardeerd (dit soort denken: meer van)", "resolved"),
    "soft_reject": ("🙂 afgewezen, geen harde regel (mag opnieuw bij andere context)", "rejected"),
    "not_now":     ("⏳ goed idee, nu niet (timing)", "deferred"),
    "elsewhere":   ("🌍 hoort buiten NoochVille", "resolved"),
}


class Feedback:
    """Persistente log van menselijke oordelen over kansen (trainingssignaal)."""

    def __init__(self, path: str):
        self.path = path
        self._items: list[dict] = read_json(path, [], expect=list)

    def add(self, verdict: str, title: str, reason: str = "", by: str = "") -> dict:
        """Leg een oordeel vast. by = de rol die de kans inbracht (voor rol-specifiek leren)."""
        rec = {"verdict": verdict, "title": (title or "").strip(),
               "reason": (reason or "").strip(), "by": by or "", "at": time.time()}
        self._items.append(rec)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        atomic_write_json(self.path, self._items)
        return rec

    def all(self) -> list[dict]:
        return list(self._items)


def training_block(items: list[dict], role: str | None = None, limit: int = 8) -> str:
    """Bouw een prompt-blok met de zachte trainingssignalen (positief én negatief), zodat de
    reflex van beide kanten leert. Filtert op rol als gegeven. Leeg ('') als er niets is."""
    rel = [i for i in items if i.get("verdict") in SOFT_VERDICTS
           and (role is None or not i.get("by") or i.get("by") == role)]
    if not rel:
        return ""
    rel = rel[-limit:]
    pos = [i for i in rel if i["verdict"] == "praise"]
    neg = [i for i in rel if i["verdict"] != "praise"]
    out = ["\nWAT DE MENS EERDER VOND (leer hiervan, het zijn geen harde regels maar richting):"]
    for i in pos:
        out.append(f"- 👍 goed denkwerk: {i.get('title','')}"
                   + (f" — {i['reason']}" if i.get("reason") else ""))
    for i in neg:
        lbl = SOFT_VERDICTS[i["verdict"]][0]
        out.append(f"- {lbl}: {i.get('title','')}"
                   + (f" — {i['reason']}" if i.get("reason") else ""))
    return "\n".join(out) + "\n"
