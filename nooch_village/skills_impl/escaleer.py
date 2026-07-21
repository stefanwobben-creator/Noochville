"""escaleer — een rol routeert bewust een twijfel, kans of blokkade naar de juiste plek.

Cross-cutting middel (founder 20 jul): Lara's "escalating doubts to @Founding Farmer" en
"escalating unclear cases to the right role" hadden geen middel, maar élke autonome rol heeft
dit nodig — een gestructureerde manier om te zeggen "dit is niet van mij / ik ben er niet
zeker van, leg het bij X". De plumbing (notificaties + inbox) bestaat al; deze skill is de
knop die een rol zelf kan indrukken tijdens haar werk.

Landing: een notificatie voor de doel-rol ('the_source' voor de Founding Farmer). Nooit een
approve-knop, alleen een gerichte heads-up met reden. Side-effecting (schrijft één notificatie).
"""
from __future__ import annotations

import os

from nooch_village.skills import Skill

# Aliassen voor de mens-aan-het-roer: alles wat "founder/farmer/mens" betekent → the_source.
_FOUNDER = {"founder", "founding farmer", "the_source", "the source", "mens", "human",
            "stefan", "@founding farmer"}


class EscaleerSkill(Skill):
    name = "escaleer"
    cost = "free"                  # lokale notificatie-append, geen externe call, geen LLM
    side_effect_free = False       # schrijft één notificatie
    description = ("Routeert een twijfel, onduidelijk geval of blokkade naar de juiste rol of "
                   "naar de Founding Farmer, als gerichte notificatie. Voor wanneer iets niet van "
                   "de eigen rol is of menselijk oordeel vraagt.")
    input_schema = ("reden: str (verplicht — wat en waarom je escaleert); "
                    "naar: str (verplicht — doel-rol-id, of 'founder' voor de Founding Farmer); "
                    "van: str (optioneel — de escalerende rol, voor de afzender-label)")
    required_payload = ("reden", "naar")
    output_schema = "ok, naar (opgeloste rol-id), reden, notif_id"

    def run(self, payload: dict, context=None) -> dict:
        reden = ((payload or {}).get("reden") or "").strip()
        naar_raw = ((payload or {}).get("naar") or "").strip()
        if not reden or not naar_raw:
            return {"error": "ontbrekende parameter: 'reden' en 'naar' zijn beide verplicht"}
        naar = "the_source" if naar_raw.lower() in _FOUNDER else naar_raw
        van = ((payload or {}).get("van") or "").strip() or "een rol"
        dd = getattr(context, "data_dir", ".") or "."
        try:
            from nooch_village.notifications import NotifStore
            notif = NotifStore(os.path.join(dd, "notifications.json"))
            n = notif.add("role", naar, "", by=van, snippet=f"⤴ escalatie: {reden}"[:160])
        except Exception as e:
            return {"error": f"escalatie kon niet landen: {e}"}
        return {"ok": True, "naar": naar, "reden": reden, "notif_id": n.get("id", "")}

    def evidence_records(self, result: dict, *, role_id: str) -> list:
        """Een escalatie is een feit in De Kroniek: bevestigd = de doorverwijzing is gemaakt.
        Zo zie je later welke rol waarover naar wie escaleerde (leren: waar loopt het vast)."""
        if not isinstance(result, dict) or not result.get("ok"):
            return []
        return [{"role_id": role_id, "skill": self.name,
                 "query": (result.get("reden") or "")[:200], "source": "escaleer",
                 "status": "bevestigd", "result_ref": result.get("notif_id", ""),
                 "meta": {"naar": result.get("naar")}}]
