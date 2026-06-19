"""Tests voor keyword_runner — nep-skill, geen netwerk."""
from __future__ import annotations
from nooch_village.keyword_runner import make_keywords_runner


class _FakeSkill:
    def __init__(self, keywords=None):
        self.last_payload = None
        self.last_context = None
        self._keywords = keywords if keywords is not None else [
            {"keyword": "vegan schoenen", "vol": 3400, "cpc": 0.42, "competition": 0.18, "trend": []},
        ]

    def run(self, payload, context):
        self.last_payload = payload
        self.last_context = context
        return {
            "source": "keywords_everywhere",
            "country": payload.get("country", "nl"),
            "currency": "eur",
            "data_source": payload.get("data_source", "cli"),
            "credits_consumed": len(payload.get("kw", [])),
            "credits_remaining": 99000,
            "keywords": self._keywords,
        }


_FAKE_CONTEXT = object()


def test_runner_roept_skill_aan_met_juiste_kw_param():
    skill = _FakeSkill()
    runner = make_keywords_runner(skill, _FAKE_CONTEXT)
    candidates = ["vegan schoenen", "duurzame schoenen"]
    runner(candidates, "nl", "cli")
    assert skill.last_payload["kw"] == candidates


def test_runner_geeft_juiste_country_door():
    skill = _FakeSkill()
    runner = make_keywords_runner(skill, _FAKE_CONTEXT)
    runner(["vegan schoenen"], "de", "cli")
    assert skill.last_payload["country"] == "de"


def test_runner_geeft_juiste_data_source_door_cli():
    skill = _FakeSkill()
    runner = make_keywords_runner(skill, _FAKE_CONTEXT)
    runner(["vegan schoenen"], "nl", "cli")
    assert skill.last_payload["data_source"] == "cli"


def test_runner_geeft_juiste_data_source_door_gkp():
    skill = _FakeSkill()
    runner = make_keywords_runner(skill, _FAKE_CONTEXT)
    runner(["vegan shoes"], "gb", "gkp")
    assert skill.last_payload["data_source"] == "gkp"


def test_runner_geeft_context_door_aan_skill():
    skill = _FakeSkill()
    ctx = object()
    runner = make_keywords_runner(skill, ctx)
    runner(["vegan schoenen"], "nl", "cli")
    assert skill.last_context is ctx


def test_runner_geeft_keywords_lijst_terug():
    kws = [
        {"keyword": "vegan schoenen", "vol": 3400, "cpc": 0.42, "competition": 0.18, "trend": []},
        {"keyword": "duurzame schoenen", "vol": 1200, "cpc": 0.31, "competition": 0.11, "trend": []},
    ]
    skill = _FakeSkill(keywords=kws)
    runner = make_keywords_runner(skill, _FAKE_CONTEXT)
    result = runner(["vegan schoenen", "duurzame schoenen"], "nl", "cli")
    assert result == kws


def test_runner_geeft_lege_lijst_terug_bij_geen_resultaten():
    skill = _FakeSkill(keywords=[])
    runner = make_keywords_runner(skill, _FAKE_CONTEXT)
    result = runner(["onbekend keyword"], "nl", "cli")
    assert result == []


def test_runner_gb_market_geeft_gb_country_door():
    skill = _FakeSkill()
    runner = make_keywords_runner(skill, _FAKE_CONTEXT)
    runner(["vegan shoes"], "gb", "cli")
    assert skill.last_payload["country"] == "gb"


def test_runner_se_market_geeft_se_country_door():
    skill = _FakeSkill()
    runner = make_keywords_runner(skill, _FAKE_CONTEXT)
    runner(["veganska skor"], "se", "cli")
    assert skill.last_payload["country"] == "se"
