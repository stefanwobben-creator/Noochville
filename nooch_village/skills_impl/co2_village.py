"""co2_village — de CO2-KPI als dag-observatiebron.

Leest het llm_usage-log van een dag en aggregeert het tot geschatte gram CO2e (via de bronvermelde
factoren in co2.EMISSION_FACTORS). De generieke collector schrijft de velden weg als
`co2_village_<veld>_day` → tegels in het dashboard. Context-KPI: geen 'lager = beter', geen ISO-claim;
ongeschatte calls (geen bronfactor) worden apart geteld, nooit stil als nul.

Dubbelt als handmatige skill: `run({datum})` geeft de aggregatie van een dag terug ('wat verstookte het
dorp?'). Zuiver lezen, side-effect-free.
"""
from __future__ import annotations

import datetime
import os

from nooch_village.skills import DataSourceSkill


def _today() -> str:
    return datetime.datetime.now(datetime.timezone.utc).date().isoformat()


class Co2VillageSource(DataSourceSkill):
    name = "co2_village"
    SOURCE = "co2_village"
    CATALOG_LABEL = "CO2 van het dorp (LLM-emissies)"
    cost = "free"
    side_effect_free = True
    kind = "flux"                  # de dagwaarde is de emissie ván die dag (geen oplopende stand)
    required_env = ()              # geen sleutel nodig
    description = ("Geschatte inference-emissies (gram CO2e) van alle LLM-calls van het dorp per dag. "
                  "Context-KPI (geen 'lager = beter'), geen ISO-claim; ongeschatte calls apart geteld.")
    input_schema = "optioneel: datum: str (YYYY-MM-DD, default vandaag)"
    output_schema = "ok, datum, gram_co2e, calls, tokens_geschat, ongeschat_calls, ongeschat_tokens"

    def available_metrics(self, context=None) -> list[str]:
        return ["gram_co2e", "calls", "ongeschat_calls"]

    def _aggregate(self, context, datum: str) -> dict:
        from nooch_village import llm_usage, co2
        path = os.path.join(getattr(context, "data_dir", "."), "llm_usage.jsonl")
        return co2.co2_for_day(llm_usage.read_day(datum, path=path))

    def daily_values(self, context, datum: str) -> dict:
        agg = self._aggregate(context, datum)
        return {"gram_co2e": agg["gram_co2e"], "calls": agg["calls"],
                "ongeschat_calls": agg["ongeschat_calls"]}

    def run(self, payload: dict, context=None) -> dict:
        datum = ((payload or {}).get("datum") or "").strip() or _today()
        return {"ok": True, "datum": datum, **self._aggregate(context, datum)}
