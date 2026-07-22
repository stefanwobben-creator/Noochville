"""tegenspraak — kritische tegenspraak vóór 'done' (founder, 22 jul).

Het dorp gathert en schrijft volop, en heeft domein-checks (content_check voor copy, claims_check
voor compliance), maar geen ALGEMENE skill die een willekeurige deliverable of claim ADVERSARIEEL
toetst voordat hij als klaar geldt. Deze skill vult dat gat: gegeven een stuk output (en optioneel
de onderbouwing waarop het zou moeten rusten), zoekt hij de zwakste of meest overdreven claim, wat
ongegrond is, het sterkste tegenargument, en geeft een concrete revisie of de verplichte nuance.
Voor élke rol, op élke output — de 'waarheidslat' van de Kroniek als bruikbaar gereedschap.

Read-only, fail-soft: zonder LLM of zonder tekst geeft-ie geen oordeel i.p.v. een verzonnen 'ok'.
Legt de toetsing vast in De Kroniek, zodat Lara ziet welke rollen hun eigen werk tegenspreken en of
het de lat haalde.
"""
from __future__ import annotations

import json
import re

from nooch_village.skills import Skill


class TegenspraakSkill(Skill):
    name = "tegenspraak"
    cost = "free"                   # begrensde LLM-tokenkost, bewust niet gevlagd (zoals content_check)
    side_effect_free = True         # leest/redeneert, schrijft niets; het Kroniek-record beschrijft hij
    description = ("Spreekt een deliverable of claim kritisch tegen vóór 'done': zoekt de zwakste of "
                   "meest overdreven claim, wat ongegrond is, het sterkste tegenargument, en geeft een "
                   "concrete revisie of verplichte nuance. Voor elke rol, op elke output.")
    input_schema = ("tekst: str (verplicht — de deliverable/claim die getoetst wordt); "
                    "bewijs: str (optioneel — de onderbouwing waarop het zou moeten rusten); "
                    "doel: str (optioneel — de uitkomst die de output dient)")
    required_payload = ("tekst",)
    output_schema = ("ok, oordeel ('houdt stand'|'moet bij'), zwakste_claim, ongegrond (list), "
                     "tegenargument, revisie, samenvatting | error")

    def run(self, payload: dict, context=None) -> dict:
        tekst = ((payload or {}).get("tekst") or "").strip()
        if not tekst:
            return {"error": "ontbrekende parameter: 'tekst' is verplicht"}
        bewijs = ((payload or {}).get("bewijs") or "").strip()
        doel = ((payload or {}).get("doel") or "").strip()
        from nooch_village.llm import reason
        prompt = (
            "Je bent een strenge, eerlijke reviewer voor Nooch (duurzame veganistische schoenen). Spreek "
            "de onderstaande output kritisch tegen VÓÓR hij als klaar geldt. Scherp maar constructief: je "
            "doel is een betere, eerlijkere output, geen afbraak.\n\n"
            + (f"DOEL dat de output moet dienen:\n{doel}\n\n" if doel else "")
            + (f"BESCHIKBARE ONDERBOUWING (alleen wat hier staat mag als bewijs gelden):\n{bewijs}\n\n"
               if bewijs else
               "LET OP: er is geen onderbouwing meegegeven. Behandel elk getal, elke prijs en elke "
               "stellige bewering als potentieel ongegrond.\n\n")
            + f"OUTPUT OM TE TOETSEN:\n{tekst}\n\n"
            "Doe vier dingen:\n"
            "1. Noem de ZWAKSTE of meest overdreven claim (één zin).\n"
            "2. Lijst de beweringen die NIET gegrond zijn in de onderbouwing, of stellig zijn zonder "
            "bewijs. Is alles gegrond, geef een lege lijst.\n"
            "3. Geef het STERKSTE tegenargument of het belangrijkste ontbrekende tegenbewijs.\n"
            "4. Geef een CONCRETE revisie, of de nuance/caveat die er verplicht bij moet.\n"
            "Oordeel: 'houdt stand' als de output klopt en gegrond is, anders 'moet bij'.\n\n"
            "Antwoord UITSLUITEND met JSON:\n"
            '{"oordeel":"houdt stand of moet bij","zwakste_claim":"...","ongegrond":["..."],'
            '"tegenargument":"...","revisie":"..."}')
        raw = reason(prompt, call_site="skill_tegenspraak", json_mode=True, max_tokens=700)
        data = _extract(raw)
        if not isinstance(data, dict):
            return {"ok": False, "error": "geen bruikbaar oordeel (LLM weg) — toets handmatig"}
        oordeel = "houdt stand" if str(data.get("oordeel", "")).lower().startswith("houdt") else "moet bij"
        ongegrond = [str(x)[:200] for x in (data.get("ongegrond") or []) if str(x).strip()][:8]
        zwak = str(data.get("zwakste_claim") or "")[:300]
        return {
            "ok": True, "oordeel": oordeel, "zwakste_claim": zwak, "ongegrond": ongegrond,
            "tegenargument": str(data.get("tegenargument") or "")[:400],
            "revisie": str(data.get("revisie") or "")[:400],
            "samenvatting": (oordeel
                             + (f" — {len(ongegrond)} ongegronde bewering(en)" if ongegrond else "")
                             + (f"; zwakste: {zwak[:80]}" if zwak else "")),
        }

    def evidence_records(self, result: dict, *, role_id: str) -> list:
        """De toetsing is zelf een Kroniek-feit: een uitgevoerde review is 'bevestigd' (er ligt een
        gegrond oordeel); het oordeel zelf (houdt stand / moet bij) staat in de meta. Zo ziet Lara
        welke rollen hun eigen werk tegenspreken en hoe vaak output moest worden bijgesteld."""
        if not isinstance(result, dict) or not result.get("ok"):
            return []
        return [{"role_id": role_id, "skill": self.name,
                 "query": (result.get("zwakste_claim") or result.get("samenvatting") or "")[:200],
                 "source": "tegenspraak", "status": "bevestigd", "result_ref": "",
                 "meta": {"oordeel": result.get("oordeel"),
                          "ongegrond": len(result.get("ongegrond") or [])}}]


def _extract(raw):
    if not raw:
        return None
    s = re.sub(r"```(?:json)?", "", str(raw)).strip()
    try:
        return json.loads(s[s.find("{"):s.rfind("}") + 1])
    except (ValueError, IndexError):
        return None
