"""co2_village — de CO2-KPI als dag-observatiebron.

Leest het llm_usage-log van een dag en aggregeert het tot geschatte gram CO2e (via de bronvermelde
factoren in config/co2_factoren.json, gelezen door `co2`). De generieke collector schrijft de velden
weg als `co2_village_<veld>_day` → tegels in het dashboard. Context-KPI: geen 'lager = beter', geen
ISO-claim; ongeschatte calls (geen bronfactor) worden apart geteld, nooit stil als nul.

Dubbelt als handmatige skill: `run({datum})` geeft de aggregatie van een dag terug ('wat verstookte het
dorp?'). Zuiver lezen, side-effect-free. Een ontbrekend log of een dag zonder calls is `no_data` met de
reden — tot scope 58 was dat `{ok, gram_co2e: 0.0, calls: 0}` als gelukt, en de note toonde "0.0"
(skill-review 12-09-2026: het valse nul).
"""
from __future__ import annotations

import datetime
import os

from nooch_village.skills import DataSourceSkill

_ALIAS = {"today": 0, "vandaag": 0, "yesterday": 1, "gisteren": 1}


def _today() -> datetime.date:
    return datetime.datetime.now(datetime.timezone.utc).date()


def _datum(raw) -> str | None:
    """'YYYY-MM-DD', of een alias (today/yesterday, vandaag/gisteren) → ISO-datum; None als het geen
    datum is. Leeg = vandaag."""
    t = str(raw or "").strip().lower()
    if not t:
        return _today().isoformat()
    if t in _ALIAS:
        return (_today() - datetime.timedelta(days=_ALIAS[t])).isoformat()
    try:
        return datetime.date.fromisoformat(t).isoformat()
    except ValueError:
        return None


class Co2VillageSource(DataSourceSkill):
    name = "co2_village"
    SOURCE = "co2_village"
    CATALOG_LABEL = "CO2 van het dorp (LLM-emissies)"
    cost = "free"
    side_effect_free = True
    kind = "flux"                  # de dagwaarde is de emissie ván die dag (geen oplopende stand)
    required_env = ()              # geen sleutel nodig
    description = ("Estimated inference emissions (grams CO2e) of all LLM calls the village made on one day, "
                   "from the local usage log and the emission factors in config/co2_factoren.json. A context "
                   "KPI (not 'lower is better'), no ISO claim; calls on a model without a factor are counted "
                   "separately as 'not estimated', never as zero.")
    input_schema = "datum: str (optional, 'YYYY-MM-DD' or today/yesterday; default today)"
    output_schema = ("ok, datum, text, gram_co2e, calls, tokens_geschat, ongeschat_calls, ongeschat_tokens | "
                     "no_data + reason (no usage log, no calls that day) | error (datum is not a date)")

    def available_metrics(self, context=None) -> list[str]:
        return ["gram_co2e", "calls", "ongeschat_calls"]

    def validate_payload(self, payload: dict, context) -> list:
        raw = (payload or {}).get("datum")
        if raw not in (None, "") and _datum(raw) is None:
            return [f"'datum' {str(raw)!r} is not a date (use YYYY-MM-DD, today or yesterday)"]
        return []

    @staticmethod
    def _log_pad(context) -> str:
        return os.path.join(getattr(context, "data_dir", None) or ".", "llm_usage.jsonl")

    def _aggregate(self, context, datum: str) -> dict:
        from nooch_village import llm_usage, co2
        return co2.co2_for_day(llm_usage.read_day(datum, path=self._log_pad(context)))

    def daily_values(self, context, datum: str) -> dict:
        agg = self._aggregate(context, datum)
        return {"gram_co2e": agg["gram_co2e"], "calls": agg["calls"],
                "ongeschat_calls": agg["ongeschat_calls"]}

    def run(self, payload: dict, context=None) -> dict:
        raw = (payload or {}).get("datum")
        datum = _datum(raw)
        if datum is None:
            return {"error": f"'datum' {str(raw)!r} is not a date (use YYYY-MM-DD, today or yesterday)"}
        pad = self._log_pad(context)
        if not os.path.exists(pad):
            return {"no_data": True, "datum": datum,
                    "reason": f"no LLM usage log at {pad}: no LLM call has been logged yet"}
        agg = self._aggregate(context, datum)
        if not agg["calls"]:
            return {"no_data": True, "datum": datum, "reason": f"no LLM calls logged on {datum}"}
        return {"ok": True, "datum": datum, "text": self._tekst(datum, agg), **agg}

    @staticmethod
    def _tekst(datum: str, agg: dict) -> str:
        calls = lambda n: f"{n} LLM call" + ("" if n == 1 else "s")
        t = (f"{agg['gram_co2e']} g CO2e over {calls(agg['calls'])} on {datum} "
             f"({agg['tokens_geschat']:,} tokens estimated")
        if agg["ongeschat_calls"]:
            t += (f"; {calls(agg['ongeschat_calls'])} / {agg['ongeschat_tokens']:,} tokens not estimated: "
                  "no emission factor for their model in config/co2_factoren.json")
        return t + "). Context KPI, no ISO claim."
