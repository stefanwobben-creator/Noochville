"""Tests voor de intentielaag: prioritize()."""
from __future__ import annotations
import pytest
from unittest.mock import MagicMock
from nooch_village.intent import prioritize


def _ctx(goals=None, strategy=None):
    ctx = MagicMock()
    ctx.strategy = {
        "strategy": strategy or ["organische content", "langetermijn keywords"],
        "goals": goals or [],
    }
    return ctx


# ── policy-schendingen ────────────────────────────────────────────────────────

class TestPolicyViolations:
    def test_google_ads_actie_wordt_dropped(self):
        actions = [{"label": "Google Ads campagne", "description": "betaal voor google ads verkeer"}]
        result = prioritize(actions, _ctx())
        assert result[0]["dropped"] is True
        assert "advertising" in result[0]["drop_reason"]

    def test_facebook_ads_wordt_dropped(self):
        actions = [{"label": "FB ads", "description": "facebook ads draaien"}]
        result = prioritize(actions, _ctx())
        assert result[0]["dropped"] is True

    def test_bol_com_wordt_dropped(self):
        actions = [{"label": "bol.com listing", "description": "schoenen verkopen via bol.com"}]
        result = prioritize(actions, _ctx())
        assert result[0]["dropped"] is True
        assert "externe kanalen" in result[0]["drop_reason"]

    def test_voorraadopbouw_wordt_dropped(self):
        actions = [{"label": "bulk inkoop", "description": "voorraadopbouw voor Q4"}]
        result = prioritize(actions, _ctx())
        assert result[0]["dropped"] is True

    def test_schone_actie_niet_dropped(self):
        actions = [{"label": "blogpost schrijven", "description": "organische content over vegan schoenen"}]
        result = prioritize(actions, _ctx())
        assert result[0]["dropped"] is False


# ── doel-scoring ──────────────────────────────────────────────────────────────

class TestGoalScoring:
    def test_doelbijdrage_signaal_verhoogt_score(self):
        goals = [{"active": True, "contributes_via": ["organische bezoekers"]}]
        actions = [
            {"label": "seo artikel", "description": "organische bezoekers trekken via content"},
            {"label": "andere taak", "description": "iets anders doen"},
        ]
        result = prioritize(actions, _ctx(goals=goals))
        seo = next(a for a in result if "seo" in a["label"])
        other = next(a for a in result if "andere" in a["label"])
        assert seo["score"] > other["score"]

    def test_inactief_doel_telt_niet(self):
        goals = [{"active": False, "contributes_via": ["organische bezoekers"]}]
        actions = [{"label": "seo", "description": "organische bezoekers via content"}]
        result = prioritize(actions, _ctx(goals=goals))
        assert result[0]["score"] == pytest.approx(0.0, abs=0.5)

    def test_meerdere_signalen_tellen_op(self):
        goals = [{"active": True, "contributes_via": ["content", "bezoekers"]}]
        actions = [{"label": "artikel", "description": "content schrijven voor bezoekers"}]
        result = prioritize(actions, _ctx(goals=goals))
        assert result[0]["score"] >= 2.0


# ── policy overrulet doel ────────────────────────────────────────────────────

class TestPolicyOverrulesDoel:
    def test_policy_wint_van_hoge_doelscore(self):
        goals = [{"active": True, "contributes_via": ["advertis", "google ads"]}]
        actions = [
            {"label": "Google Ads",  "description": "advertis via google ads"},
            {"label": "SEO artikel", "description": "content over duurzame schoenen"},
        ]
        result = prioritize(actions, _ctx(goals=goals))
        seo = next(a for a in result if "SEO" in a["label"])
        ads = next(a for a in result if "Ads" in a["label"])
        assert ads["dropped"] is True
        assert seo["dropped"] is False
        # gedropt staat achteraan ondanks hogere raw score
        assert result.index(seo) < result.index(ads)


# ── sorteervolgorde ──────────────────────────────────────────────────────────

class TestSortering:
    def test_niet_gedropt_staat_voor_gedropt(self):
        actions = [
            {"label": "google ads", "description": "google ads"},
            {"label": "content",    "description": "organische content"},
        ]
        result = prioritize(actions, _ctx())
        assert result[0]["dropped"] is False
        assert result[-1]["dropped"] is True
