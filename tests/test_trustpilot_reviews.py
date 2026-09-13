"""Tests voor TrustpilotReviewsSkill. Geen netwerk: requests.post/get zijn gemockt."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nooch_village.skills_impl.trustpilot_reviews import TrustpilotReviewsSkill


def _ctx(login="user", wachtwoord="pw"):
    settings = {}
    if login:
        settings["DATAFORSEO_LOGIN"] = login
    if wachtwoord:
        settings["DATAFORSEO_PASSWORD"] = wachtwoord
    return SimpleNamespace(settings=settings)


class _FakeResp:
    def __init__(self, data, status_code=200, text=""):
        self._data = data
        self.status_code = status_code
        self.text = text or str(data)[:200]

    def json(self):
        return self._data


def _task_post_ok(task_id="abc-123", status_code=20000):
    return _FakeResp({"tasks": [{"id": task_id, "status_code": status_code,
                                  "status_message": "Task Created."}]})


def _task_get_klaar(items):
    return _FakeResp({"tasks": [{"id": "abc-123", "status_code": 20000,
                                  "result": [{"domain": "www.voorbeeld-merk.com",
                                              "rating": {"value": 3.8}, "items": items}]}]})


def _task_get_niet_klaar():
    return _FakeResp({"tasks": [{"id": "abc-123", "status_code": 20100, "result": None}]})


_REVIEWS = [
    {"review_text": "Geweldige service, snel geleverd.", "rating": {"value": 5},
     "timestamp": "2026-09-01 10:00:00 +00:00", "user_profile": {"name": "A"}, "verified": True},
    {"review_text": "Schoen ging na twee weken kapot.", "rating": {"value": 1},
     "timestamp": "2026-09-05 10:00:00 +00:00", "user_profile": {"name": "B"}, "verified": True},
]


# ── configuratie ─────────────────────────────────────────────────────────────

def test_zonder_creds_faalt_closed():
    with pytest.raises(RuntimeError, match="DATAFORSEO_LOGIN"):
        TrustpilotReviewsSkill().run({"domain": "www.x.com"}, _ctx(login="", wachtwoord=""))


def test_zonder_domain_of_task_id_geeft_foutmelding():
    uit = TrustpilotReviewsSkill().run({}, _ctx())
    assert "error" in uit


# ── happy path ────────────────────────────────────────────────────────────────

def test_happy_path_post_dan_direct_klaar():
    def _post(url, json=None, auth=None, timeout=None):
        assert json[0]["domain"] == "www.voorbeeld-merk.com"
        assert json[0]["priority"] == 2                      # default: snel
        return _task_post_ok()

    def _get(url, auth=None, timeout=None):
        assert "abc-123" in url
        return _task_get_klaar(_REVIEWS)

    with patch("nooch_village.skills_impl.trustpilot_reviews.requests.post", _post), \
         patch("nooch_village.skills_impl.trustpilot_reviews.requests.get", _get):
        uit = TrustpilotReviewsSkill().run({"domain": "www.voorbeeld-merk.com"}, _ctx())

    assert uit["ok"] is True
    assert uit["aantal_reviews"] == 2
    assert uit["gemiddelde_score"] == 3.8
    assert uit["negatief_1_2_sterren"] == 1
    assert uit["positief_4_5_sterren"] == 1
    assert uit["reviews"][0]["tekst"].startswith("Geweldige")
    assert "www.voorbeeld-merk.com" in uit["text"]


def test_task_id_in_payload_slaat_task_post_over():
    post_calls = {"n": 0}

    def _post(*a, **k):
        post_calls["n"] += 1
        return _task_post_ok()

    def _get(url, auth=None, timeout=None):
        return _task_get_klaar(_REVIEWS)

    with patch("nooch_village.skills_impl.trustpilot_reviews.requests.post", _post), \
         patch("nooch_village.skills_impl.trustpilot_reviews.requests.get", _get):
        uit = TrustpilotReviewsSkill().run({"task_id": "abc-123"}, _ctx())

    assert post_calls["n"] == 0                     # geen nieuwe (betaalde) taak
    assert uit["ok"] is True
    assert uit["task_id"] == "abc-123"


def test_geen_reviews_is_no_data():
    with patch("nooch_village.skills_impl.trustpilot_reviews.requests.post",
               lambda *a, **k: _task_post_ok()), \
         patch("nooch_village.skills_impl.trustpilot_reviews.requests.get",
               lambda *a, **k: _task_get_klaar([])):
        uit = TrustpilotReviewsSkill().run({"domain": "www.onbekend.com"}, _ctx())
    assert uit["no_data"] is True


def test_niet_op_tijd_klaar_geeft_tijdelijke_fout_met_task_id():
    with patch("nooch_village.skills_impl.trustpilot_reviews.requests.post",
               lambda *a, **k: _task_post_ok()), \
         patch("nooch_village.skills_impl.trustpilot_reviews.requests.get",
               lambda *a, **k: _task_get_niet_klaar()), \
         patch("nooch_village.skills_impl.trustpilot_reviews.time.sleep"), \
         patch("nooch_village.skills_impl.trustpilot_reviews._POLL_BUDGET_S", 1):
        uit = TrustpilotReviewsSkill().run({"domain": "www.traag.com"}, _ctx())
    assert "error" in uit and uit["tijdelijk"] is True
    assert uit["task_id"] == "abc-123"
    assert "abc-123" in uit["error"]


def test_taak_geweigerd_door_dataforseo():
    def _post(*a, **k):
        return _FakeResp({"tasks": [{"id": "", "status_code": 40501,
                                       "status_message": "Invalid Field: 'domain'."}]})
    with patch("nooch_village.skills_impl.trustpilot_reviews.requests.post", _post):
        uit = TrustpilotReviewsSkill().run({"domain": ""}, _ctx())
    assert "error" in uit


def test_http_fout_maskeert_wachtwoord():
    def _post(url, json=None, auth=None, timeout=None):
        return _FakeResp({}, status_code=401, text="Unauthorized for password geheim123wachtwoord")
    with patch("nooch_village.skills_impl.trustpilot_reviews.requests.post", _post):
        uit = TrustpilotReviewsSkill().run({"domain": "www.x.com"}, _ctx(wachtwoord="geheim123wachtwoord"))
    assert "error" in uit
    assert "geheim123wachtwoord" not in uit["error"]


def test_prioriteit_en_diepte_worden_doorgegeven():
    captured = {}

    def _post(url, json=None, auth=None, timeout=None):
        captured.update(json[0])
        return _task_post_ok()

    with patch("nooch_village.skills_impl.trustpilot_reviews.requests.post", _post), \
         patch("nooch_village.skills_impl.trustpilot_reviews.requests.get",
               lambda *a, **k: _task_get_klaar(_REVIEWS)):
        TrustpilotReviewsSkill().run({"domain": "www.x.com", "depth": 200, "priority": 1,
                                       "sort_by": "relevance"}, _ctx())

    assert captured == {"domain": "www.x.com", "depth": 200, "sort_by": "relevance", "priority": 1}


def test_ongeldige_prioriteit_valt_terug_op_2():
    captured = {}

    def _post(url, json=None, auth=None, timeout=None):
        captured.update(json[0])
        return _task_post_ok()

    with patch("nooch_village.skills_impl.trustpilot_reviews.requests.post", _post), \
         patch("nooch_village.skills_impl.trustpilot_reviews.requests.get",
               lambda *a, **k: _task_get_klaar(_REVIEWS)):
        TrustpilotReviewsSkill().run({"domain": "www.x.com", "priority": 9}, _ctx())

    assert captured["priority"] == 2


def test_validate_payload_weigert_verzonnen_task_id():
    reden = TrustpilotReviewsSkill().validate_payload({"task_id": "de taak van stap 1"}, None)
    assert reden and "geen echte" in reden[0]


def test_validate_payload_accepteert_echte_task_id():
    assert TrustpilotReviewsSkill().validate_payload(
        {"task_id": "09261123-1535-0216-0000-01e2a3b4c5d6"}, None) == []


def test_validate_payload_leeg_zonder_task_id():
    assert TrustpilotReviewsSkill().validate_payload({"domain": "www.x.com"}, None) == []


def test_skill_metadata_compleet():
    s = TrustpilotReviewsSkill()
    assert s.name == "trustpilot_reviews"
    assert s.required_env == ("DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD")
    assert s.side_effect_free is True
    assert s.required_payload == (("domain", "task_id"),)
    assert s.input_schema and s.output_schema and s.description
