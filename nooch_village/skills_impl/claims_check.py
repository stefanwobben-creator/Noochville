"""claims_check — toets tekst tegen de eigen claims-database (EmpCo 2024/825 + ACM).

Puur lokaal: leest `config/claims_database.json` via `nooch_village.claims_db` en doet geen enkele
netwerk-aanroep. Fail-closed bij een ontbrekend of corrupt bestand — een claimtoets die stilzwijgend
'geen bevindingen' meldt is gevaarlijker dan een zichtbare fout.

De juridische inhoud van de database is compliance-domein; deze skill leest alleen.
"""
from __future__ import annotations

from nooch_village import claims_db
from nooch_village.skills import Skill


class ClaimsCheckSkill(Skill):
    name = "claims_check"
    cost = "free"
    side_effect_free = True
    required_env = ()
    description = ("Toetst tekst tegen de Nooch claims-database (EmpCo 2024/825 + ACM): geeft per "
                   "gevonden term het stoplicht, de categorie, waarom het risico bestaat en een "
                   "veilig alternatief, plus een compliance-score. Puur lokaal, geen netwerk.")
    input_schema = "text: str  OF  terms: list[str] (de termen worden dan als één tekst getoetst)"
    output_schema = "ok, score, rood, oranje, groen, bevindingen[], versie"
    # "text OF terms" — een disjunctie, geen platte lijst. Als ("text","terms") zou de poort BEIDE
    # eisen en de skill op de andere manier breken; de skill accepteert er één. Zonder declaratie gaf
    # de poort groen en weigerde de skill alsnog bij het draaien, en dat kostte de onderzoekspas zijn
    # tweede bron. Zie `skills.ontbrekende_velden`.
    required_payload = (("text", "terms"),)

    def run(self, payload: dict, context=None) -> dict:
        payload = payload or {}
        tekst = (payload.get("text") or "").strip()
        if not tekst:
            terms = payload.get("terms") or []
            tekst = "\n".join(str(t) for t in terms if t).strip()
        if not tekst:
            return {"ok": False, "error": "geef 'text' of 'terms' mee"}
        try:
            uitslag = claims_db.check_tekst(tekst, data_dir=getattr(context, "data_dir", None))
        except claims_db.ClaimsDbError as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, **uitslag}
