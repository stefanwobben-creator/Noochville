"""Tests voor atomic_insights: pure helpers, geen netwerk (reason_fn geïnjecteerd)."""
from nooch_village.skills_impl.atomic_insights import (
    AtomicInsightsSkill, build_insights_prompt, parse_insights,
    synthesize_insights, to_fuzzy, validate_insight,
)

FAKE_OUT = (
    '[{"insight": "Company-level certifications are used as substitutes for product-level '
    'evidence.", "status": "hypothesis", "grounds": "Multiple brands cite B Corp in the '
    'context of biodegradability while B Corp says nothing about materials."},'
    '{"insight": "A claim without a test standard is unverifiable.", "status": "fact", '
    '"grounds": "Only claims referencing a norm (ASTM D5338) could be checked."}]'
)


def test_prompt_bevat_data_en_regels():
    p = build_insights_prompt("merk X zegt Y", mission="plasticvrij")
    assert "merk X zegt Y" in p
    assert "ENGLISH ONLY" in p
    assert "hypothesis" in p
    assert "plasticvrij" in p


def test_prompt_zonder_missie_geen_lege_regel():
    p = build_insights_prompt("data")
    assert "Mission context" not in p


def test_parse_strips_codefences():
    assert len(parse_insights(f"```json\n{FAKE_OUT}\n```")) == 2


def test_parse_fail_closed():
    assert parse_insights(None) == []
    assert parse_insights("geen json hier") == []
    assert parse_insights("[{kapot") == []


def test_validate_weigert_incompleet_en_vreemde_status():
    assert validate_insight({"insight": "a", "status": "fact", "grounds": "b"})
    assert not validate_insight({"insight": "", "status": "fact", "grounds": "b"})
    assert not validate_insight({"insight": "a", "status": "fact", "grounds": "  "})
    assert not validate_insight({"insight": "a", "status": "zeker_weten", "grounds": "b"})


def test_synthesize_fail_closed_zonder_llm():
    assert synthesize_insights("data", reason_fn=lambda p: None) == []


def test_synthesize_happy_path_valideert_en_normaliseert():
    res = synthesize_insights("ruwe data", reason_fn=lambda p: FAKE_OUT)
    assert len(res) == 2
    assert res[0]["status"] == "hypothesis"
    assert res[1]["insight"].startswith("A claim without a test standard")


def test_to_fuzzy_draagt_status_mee():
    fuzzy = to_fuzzy(synthesize_insights("x", reason_fn=lambda p: FAKE_OUT))
    assert "INSIGHT (fact):" in fuzzy
    assert "GROUNDS:" in fuzzy
    assert fuzzy.count("\n") == 1


def test_skill_run_fail_fast_zonder_data():
    res = AtomicInsightsSkill().run({}, context=None)
    assert "error" in res


def test_skill_metadata_compleet():
    s = AtomicInsightsSkill()
    assert s.name == "atomic_insights"
    assert s.cost == "free"
    assert s.side_effect_free
    assert s.required_payload == ("data",)
    assert s.description and s.input_schema and s.output_schema
