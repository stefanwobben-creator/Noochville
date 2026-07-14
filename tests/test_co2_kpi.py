"""CO2-KPI van het dorp: usage-log (schatting), eerlijke aggregatie (ongeschat ≠ nul), de
DataSourceSkill, en de usage-haak in reason(). Geen echte LLM/netwerk."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from nooch_village import llm_usage, co2
from nooch_village.skills_impl.co2_village import Co2VillageSource

_TS = 1_700_000_000.0                     # vaste tijdstempel → deterministische dag


# ── usage-log ─────────────────────────────────────────────────────────────────

def test_estimate_tokens():
    assert llm_usage.estimate_tokens("a" * 40, "b" * 40) == 20     # 80 tekens / 4


def test_record_en_read_day_filtert_op_dag(tmp_path):
    p = str(tmp_path / "u.jsonl")
    llm_usage.record("plan", "mistral:m", 100, ts=_TS, path=p)
    llm_usage.record("note", "gemini:g", 50, ts=_TS, path=p)
    llm_usage.record("oud", "mistral:m", 999, ts=1_600_000_000.0, path=p)   # andere dag
    rows = llm_usage.read_day(llm_usage._day(_TS), path=p)
    assert len(rows) == 2 and sum(r["tokens"] for r in rows) == 150


# ── aggregatie: ongeschat ≠ nul ───────────────────────────────────────────────

def test_co2_for_day_zonder_factor_is_ongeschat_niet_nul():
    rows = [{"tier": "mistral:m", "tokens": 1000}, {"tier": "gemini:g", "tokens": 500}]
    agg = co2.co2_for_day(rows, factors={})                 # geen enkele factor
    assert agg["gram_co2e"] == 0.0
    assert agg["ongeschat_calls"] == 2 and agg["ongeschat_tokens"] == 1500


def test_co2_for_day_met_factor_per_model_telt_alleen_gedekte_calls():
    rows = [{"tier": "mistral:mistral-small-latest", "tokens": 2000},
            {"tier": "gemini:gemini-2.5-flash", "tokens": 1000}]
    # factor per EXACT model, niet per vendor
    agg = co2.co2_for_day(rows, factors={"mistral:mistral-small-latest": 0.02})
    assert agg["gram_co2e"] == 0.04                         # 2000/1000 * 0.02
    assert agg["tokens_geschat"] == 2000
    assert agg["ongeschat_calls"] == 1                      # het gemini-model nog ongeschat


def test_factor_per_model_niet_per_vendor():
    rows = [{"tier": "gemini:gemini-2.5-flash-lite", "tokens": 1000},
            {"tier": "gemini:gemini-2.5-flash", "tokens": 1000}]
    # alleen het lite-model heeft een factor → het grote flash-model blijft ongeschat (geen vendor-smearing)
    agg = co2.co2_for_day(rows, factors={"gemini:gemini-2.5-flash-lite": 0.01})
    assert agg["gram_co2e"] == 0.01 and agg["ongeschat_calls"] == 1


def test_factoren_zijn_leeg_by_default():
    # bewust: geen verzonnen factoren; alles ongeschat tot een mens bronvermelde waarden invult
    assert co2.EMISSION_FACTORS == {}
    assert co2.factor_for("mistral:mistral-small-latest") is None


# ── DataSourceSkill ───────────────────────────────────────────────────────────

def test_datasource_aggregeert_de_dag(tmp_path):
    p = str(tmp_path / "llm_usage.jsonl")
    llm_usage.record("a", "mistral:m", 1000, ts=_TS, path=p)
    llm_usage.record("b", "gemini:g", 500, ts=_TS, path=p)
    ctx = SimpleNamespace(data_dir=str(tmp_path))
    src = Co2VillageSource()
    dv = src.daily_values(ctx, llm_usage._day(_TS))
    assert dv["calls"] == 2 and dv["ongeschat_calls"] == 2      # geen factoren → eerlijk ongeschat
    res = src.run({"datum": llm_usage._day(_TS)}, ctx)
    assert res["ok"] and res["calls"] == 2 and res["gram_co2e"] == 0.0


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
    assert out == "een antwoord" and calls       # de succesvolle call is vastgelegd voor de CO2-KPI
