"""projectverzoek — werk dat bij een ANDERE rol hoort doorgeven i.p.v. dood laten lopen (founder, 23 jul).

De knel: een rol raakt in een project een deel-item dat geen van haar skills kan uitvoeren maar dat
duidelijk binnen een andere rol valt (bv. Compliance die een QR-code + webpagina nodig heeft — werk
van de website-rol). Er was geen toegepaste manier om die spanning door te geven, dus het project liep
dood op 'geen skill'. Deze skill maakt de handoff waar: hij zet een queued project op het bord van de
doelrol, met een terugverwijzing. Die rol pakt het via haar eigen ritme op; de vragende rol heeft haar
deel gedaan (doorgegeven) en kan verder. Zo bewegen spanningen eindelijk tússen rollen i.p.v. alleen
naar de founder.

side_effect: maakt een project aan. Fail-soft: onbekende rol of ontbrekende store → nette error.
"""
from __future__ import annotations

from nooch_village.skills import Skill


class ProjectverzoekSkill(Skill):
    name = "projectverzoek"
    cost = "free"
    side_effect_free = False        # zet een project op het bord van een andere rol
    description = ("Draag een deel-item dat bij een ANDERE rol hoort over als projectverzoek: zet een "
                   "queued project op het bord van die rol, met een terugverwijzing. Gebruik dit voor een "
                   "item dat geen van jouw skills kan uitvoeren maar binnen een andere bestaande rol valt "
                   "(geef de rol-id in naar_rol). Zo loopt een project niet dood op werk dat elders hoort.")
    input_schema = ("naar_rol: str (verplicht — de rol-id die dit werk oppakt); "
                    "titel: str (verplicht — de over te dragen uitkomst, één zin); "
                    "done_criterium: str (optioneel — waaraan de andere rol ziet dat het klaar is)")
    required_payload = ("naar_rol", "titel")
    output_schema = "ok, pid, naar_rol, titel | error"

    def run(self, payload: dict, context=None) -> dict:
        naar = ((payload or {}).get("naar_rol") or "").strip()
        titel = ((payload or {}).get("titel") or "").strip()
        if not naar or not titel:
            return {"error": "ontbrekende parameter: 'naar_rol' en 'titel' zijn beide verplicht"}
        projects = getattr(context, "projects", None)
        if projects is None:
            return {"error": "geen projectledger in context — kan geen projectverzoek plaatsen"}
        records = getattr(context, "records", None)
        if records is not None and records.get(naar) is None:
            return {"error": f"onbekende doelrol: '{naar}'"}
        done = (((payload or {}).get("done_criterium") or "").strip() or titel)
        try:
            pid = projects.create(naar, titel[:200], "tension", status="queued",
                                  done_when=done[:200], origin="projectverzoek")
        except Exception as e:
            return {"error": f"kon projectverzoek niet plaatsen: {e}"}
        try:                        # terugverwijzing op het nieuwe project (fail-soft)
            projects.add_feed_entry(
                pid, f"📥 Binnengekomen als projectverzoek (overdracht van werk dat hier hoort). "
                     f"Klaar wanneer: {done[:160]}", kind="system", author_type="role")
        except Exception:
            pass
        return {"ok": True, "pid": pid, "naar_rol": naar, "titel": titel[:200]}

    def evidence_records(self, result: dict, *, role_id: str) -> list:
        """Een geplaatst projectverzoek is een Kroniek-feit: 'bevestigd' (de overdracht is gedaan).
        Zo ziet Lara welke rollen werk doorgeven en naar wie, i.p.v. dood te lopen op 'geen skill'."""
        if not isinstance(result, dict) or not result.get("ok"):
            return []
        return [{"role_id": role_id, "skill": self.name,
                 "query": (result.get("titel") or "")[:200], "source": "projectverzoek",
                 "status": "bevestigd", "result_ref": result.get("pid") or "",
                 "meta": {"naar_rol": result.get("naar_rol")}}]
