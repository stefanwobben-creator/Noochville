"""CO2-KPI van het dorp: usage-log (input/output apart), eerlijke aggregatie (ongeschat ≠ nul, per
exact model, input = output/5), de DataSourceSkill, en de usage-haak in reason(). Geen echte LLM."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from nooch_village import llm_usage, co2
from nooch_village.skills_impl.co2_village import Co2VillageSource

_TS = 1_700_000_000.0                     # vaste tijdstempel → deterministische dag


# ── usage-log ─────────────────────────────────────────────────────────────────

def test_estimate_split_input_en_output_apart():
    assert llm_usage.estimate_split("a" * 40, "b" * 60) == (10, 15)   # 40/4, 60/4


def test_record_en_read_day_filtert_op_dag(tmp_path):
    p = str(tmp_path / "u.jsonl")
    llm_usage.record("plan", "mistral:m", 60, 40, ts=_TS, path=p)     # tokens 100
    llm_usage.record("note", "gemini:g", 30, 20, ts=_TS, path=p)      # tokens 50
    llm_usage.record("oud", "mistral:m", 500, 499, ts=1_600_000_000.0, path=p)   # andere dag
    rows = llm_usage.read_day(llm_usage._day(_TS), path=p)
    assert len(rows) == 2 and sum(r["tokens"] for r in rows) == 150
    assert rows[0]["in_tokens"] == 60 and rows[0]["out_tokens"] == 40


# ── aggregatie: input/output, per model, ongeschat ≠ nul ──────────────────────

def test_co2_zonder_factor_is_ongeschat_niet_nul():
    rows = [{"tier": "mistral:m", "in_tokens": 500, "out_tokens": 500},
            {"tier": "gemini:g", "in_tokens": 250, "out_tokens": 250}]
    agg = co2.co2_for_day(rows, factors={})                 # geen enkele factor
    assert agg["gram_co2e"] == 0.0
    assert agg["ongeschat_calls"] == 2 and agg["ongeschat_tokens"] == 1500


def test_co2_input_telt_als_output_gedeeld_door_vijf():
    rows = [{"tier": "mistral:mistral-small-latest", "in_tokens": 1000, "out_tokens": 2000},
            {"tier": "gemini:gemini-2.5-flash", "in_tokens": 500, "out_tokens": 1000}]
    agg = co2.co2_for_day(rows, factors={"mistral:mistral-small-latest": 0.30})
    # output 2000/1000*0.30 = 0.60 ; input 1000/1000*0.30*0.2 = 0.06 ; totaal 0.66
    assert agg["gram_co2e"] == 0.66
    assert agg["ongeschat_calls"] == 1                      # het gemini-model nog ongeschat


def test_factor_per_model_niet_per_vendor():
    rows = [{"tier": "gemini:gemini-2.5-flash-lite", "in_tokens": 0, "out_tokens": 1000},
            {"tier": "gemini:gemini-2.5-flash", "in_tokens": 0, "out_tokens": 1000}]
    agg = co2.co2_for_day(rows, factors={"gemini:gemini-2.5-flash-lite": 0.15})
    assert agg["gram_co2e"] == 0.15 and agg["ongeschat_calls"] == 1


def test_factoren_zijn_ingevuld_per_model():
    assert co2.factor_for("gemini:gemini-2.5-flash-lite") == 0.15
    assert co2.factor_for("anthropic:claude-haiku-4-5-20251001") == 0.60
    assert co2.factor_for("openai:onbekend") is None        # niet in de tabel → ongeschat


# ── DataSourceSkill ───────────────────────────────────────────────────────────

def test_datasource_aggregeert_de_dag_met_echte_factoren(tmp_path):
    p = str(tmp_path / "llm_usage.jsonl")
    # één bekend model (flash-lite) en één onbekend → deels geschat, deels ongeschat
    llm_usage.record("a", "gemini:gemini-2.5-flash-lite", 0, 1000, ts=_TS, path=p)   # 1000/1000*0.15 = 0.15
    llm_usage.record("b", "onbekend:model", 100, 100, ts=_TS, path=p)
    ctx = SimpleNamespace(data_dir=str(tmp_path))
    src = Co2VillageSource()
    dv = src.daily_values(ctx, llm_usage._day(_TS))
    assert dv["calls"] == 2 and dv["gram_co2e"] == 0.15 and dv["ongeschat_calls"] == 1
    assert src.run({"datum": llm_usage._day(_TS)}, ctx)["ok"]


def test_co2_village_geregistreerd():
    from nooch_village.registry_factory import build_skill_registry
    assert build_skill_registry().get("co2_village") is not None


# ── de haak in reason() ───────────────────────────────────────────────────────

def test_reason_legt_usage_vast():
    import nooch_village.llm as llm
    calls = []
    with patch.object(llm.LIMITER, "acquire", lambda *a, **k: None), \
         patch("nooch_village.llm._call_tier", return_value="een antwoord"), \
         patch("nooch_village.llm._in_cooldown", return_value=False), \
         patch("nooch_village.llm_usage.record", lambda *a, **k: calls.append((a, k))):
        out = llm.reason("een prompt", call_site="test_co2")
    assert out == "een antwoord" and calls       # de succesvolle call is vastgelegd (input+output)
