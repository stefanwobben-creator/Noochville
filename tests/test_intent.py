"""Tests voor de intentielaag: prioritize()."""
from __future__ import annotations
import pytest
from unittest.mock import MagicMock
from nooch_village.intent import prioritize, _is_schoen_domein


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
        actions = [{"label": "vegan schoenen blogpost", "description": "organische content over vegan schoenen"}]
        result = prioritize(actions, _ctx())
        assert result[0]["dropped"] is False


# ── doel-scoring ──────────────────────────────────────────────────────────────

class TestGoalScoring:
    def test_doelbijdrage_signaal_verhoogt_score(self):
        goals = [{"active": True, "contributes_via": ["organische bezoekers"]}]
        actions = [
            {"label": "seo artikel vegan shoes", "description": "organische bezoekers trekken via content over shoes"},
            {"label": "andere taak sneakers",    "description": "iets anders doen met sneakers"},
        ]
        result = prioritize(actions, _ctx(goals=goals))
        seo = next(a for a in result if "seo" in a["label"])
        other = next(a for a in result if "andere" in a["label"])
        assert seo["score"] > other["score"]

    def test_inactief_doel_telt_niet(self):
        goals = [{"active": False, "contributes_via": ["organische bezoekers"]}]
        actions = [{"label": "seo vegan shoes", "description": "organische bezoekers via content over shoes"}]
        result = prioritize(actions, _ctx(goals=goals))
        assert result[0]["score"] == pytest.approx(0.0, abs=0.5)

    def test_meerdere_signalen_tellen_op(self):
        goals = [{"active": True, "contributes_via": ["content", "bezoekers"]}]
        actions = [{"label": "artikel over sneakers", "description": "content schrijven voor bezoekers over sneakers"}]
        result = prioritize(actions, _ctx(goals=goals))
        assert result[0]["score"] >= 2.0


# ── policy overrulet doel ────────────────────────────────────────────────────

class TestPolicyOverrulesDoel:
    def test_policy_wint_van_hoge_doelscore(self):
        goals = [{"active": True, "contributes_via": ["advertis", "google ads"]}]
        actions = [
            {"label": "Google Ads",          "description": "advertis via google ads"},
            {"label": "SEO artikel schoenen", "description": "content over duurzame schoenen"},
        ]
        result = prioritize(actions, _ctx(goals=goals))
        seo = next(a for a in result if "SEO" in a["label"])
        ads = next(a for a in result if "Ads" in a["label"])
        assert ads["dropped"] is True
        assert seo["dropped"] is False
        # gedropt staat achteraan ondanks hogere raw score
        assert result.index(seo) < result.index(ads)


# ── schoen-domeinfilter ──────────────────────────────────────────────────────

class TestSchoenDomeinfilter:
    def test_barefoot_dress_shoes_niet_dropped(self):
        actions = [{"label": "barefoot dress shoes", "description": "opkomende zoekterm"}]
        result = prioritize(actions, _ctx())
        assert result[0]["dropped"] is False, (
            "'barefoot' en 'shoes' zitten in _SCHOEN_WOORDEN — mag niet droppen"
        )

    def test_veganistisch_brood_dropped(self):
        actions = [{"label": "veganistisch brood", "description": "veganistisch brood recept"}]
        result = prioritize(actions, _ctx())
        assert result[0]["dropped"] is True
        assert "schoen" in result[0]["drop_reason"]

    def test_kernenergie_dropped(self):
        actions = [{"label": "is kernenergie duurzaam", "description": "zoekterm over energie"}]
        result = prioritize(actions, _ctx())
        assert result[0]["dropped"] is True
        assert "schoen" in result[0]["drop_reason"]

    def test_vegan_sneakers_womens_niet_dropped(self):
        actions = [{"label": "vegan sneakers womens", "description": "opkomende zoekterm"}]
        result = prioritize(actions, _ctx())
        assert result[0]["dropped"] is False, (
            "'sneakers' zit in _SCHOEN_WOORDEN — mag niet droppen"
        )

    def test_off_domein_label_niet_gered_door_schoen_in_description(self):
        # Randzwakte vóór de fix: 'barefoot shoes' in description redde het off-domein label.
        actions = [{"label": "veganistisch brood", "description": "gerelateerd aan barefoot shoes"}]
        result = prioritize(actions, _ctx())
        assert result[0]["dropped"] is True, (
            "schoen-woord in description mag het label niet redden; alleen het label telt"
        )
        assert "schoen" in result[0]["drop_reason"]

    def test_schoen_woord_in_label_passeert_domeinfilter(self):
        actions = [{"label": "barefoot shoes kids", "description": "opkomende zoekterm"}]
        result = prioritize(actions, _ctx())
        assert result[0]["dropped"] is False, (
            "'shoes' en 'barefoot' zitten in het label — moet doorkomen"
        )


# ── sorteervolgorde ──────────────────────────────────────────────────────────

class TestSortering:
    def test_niet_gedropt_staat_voor_gedropt(self):
        actions = [
            {"label": "google ads sneakers", "description": "google ads voor sneakers"},
            {"label": "content over shoes",  "description": "organische content over shoes"},
        ]
        result = prioritize(actions, _ctx())
        assert result[0]["dropped"] is False
        assert result[-1]["dropped"] is True
