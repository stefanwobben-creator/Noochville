"""ruis_check — een te brede zoekopdracht is geen bevinding maar een ongeldige meting.

Sid's accountability (governance, 19 jul): "zoekresultaten boven een ruis-drempel aanmerken
als 'query te breed' en niet als bevindingen presenteren, en de meting vastleggen in De
Kroniek." Deze skill maakt dat waar: hij oordeelt over het AANTAL treffers, niet over de
inhoud. Een zoekopdracht die miljoenen treffers geeft matcht alles → de meting is ongeldig,
niet leeg en niet bevestigd. Deterministisch, geen LLM.

Drempel: config-key `ruis_drempel` (default 5000). Boven de drempel → 'te_breed'.
"""
from __future__ import annotations

from nooch_village.skills import Skill

_DEFAULT_DREMPEL = 5000


class RuisCheckSkill(Skill):
    name = "ruis_check"
    cost = "free"                  # pure telling, geen externe call, geen LLM
    side_effect_free = True        # oordeelt alleen; het Kroniek-record beschrijft hij (inhabitant schrijft)
    description = ("Merkt een te brede zoekopdracht aan als 'query te breed' op basis van het "
                  "aantal treffers, zodat ruis niet als bevinding doorgaat. Legt de meting vast "
                  "in De Kroniek.")
    input_schema = ("query: str (verplicht — de uitgevoerde zoekopdracht); "
                    "aantal: getal (verplicht — het aantal treffers); "
                    "drempel: getal (optioneel — override van de ruis-drempel)")
    required_payload = ("query", "aantal")
    output_schema = "ok, query, aantal, drempel, status ('te_breed'|'bruikbaar'), oordeel"

    def _drempel(self, context, payload: dict) -> int:
        for bron in (payload or {}).get("drempel"), \
                (getattr(context, "settings", {}) or {}).get("ruis_drempel"):
            try:
                if bron not in (None, ""):
                    return int(bron)
            except (TypeError, ValueError):
                pass
        return _DEFAULT_DREMPEL

    def run(self, payload: dict, context=None) -> dict:
        query = ((payload or {}).get("query") or "").strip()
        raw = (payload or {}).get("aantal")
        if not query or raw in (None, ""):
            return {"error": "ontbrekende parameter: 'query' en 'aantal' zijn beide verplicht"}
        try:
            aantal = int(raw)
        except (TypeError, ValueError):
            return {"error": f"'aantal' is geen getal: {raw!r}"}
        drempel = self._drempel(context, payload)
        te_breed = aantal > drempel
        return {
            "ok": True, "query": query, "aantal": aantal, "drempel": drempel,
            "status": "te_breed" if te_breed else "bruikbaar",
            "oordeel": (f"{aantal} treffers boven drempel {drempel}: query te breed, geen "
                        f"bevinding — verfijn de zoekopdracht"
                        if te_breed else
                        f"{aantal} treffers binnen drempel {drempel}: bruikbaar"),
        }

    def evidence_records(self, result: dict, *, role_id: str) -> list:
        """De ruis-meting is zelf een Kroniek-feit. te_breed → 'fout' (de meting is ongeldig,
        de bron gaf geen bruikbaar antwoord); bruikbaar → 'bevestigd'. Zo staat in het register
        zwart-op-wit wanneer een zoekopdracht is afgekeurd als ruis."""
        if not isinstance(result, dict) or not result.get("ok"):
            return []
        te_breed = result.get("status") == "te_breed"
        return [{"role_id": role_id, "skill": self.name,
                 "query": (result.get("query") or "")[:200], "source": "ruis_check",
                 "status": "fout" if te_breed else "bevestigd", "result_ref": "",
                 "meta": {"aantal": result.get("aantal"), "drempel": result.get("drempel")}}]
