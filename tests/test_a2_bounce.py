"""A2: bounce_rate toegevoegd aan de Plausible-collector, gemapt op de BESTAANDE indicator
Bouncepercentage (Plausible) (geen nieuwe), met reeks-start in de meta. Alleen live vanaf nu."""
from __future__ import annotations
import types
from unittest.mock import patch, MagicMock

from nooch_village.skills_impl.plausible import PlausibleSkill, _METRICS, _BOUNCE_REEKS_START


def _ctx():
    return types.SimpleNamespace(settings={"PLAUSIBLE_API_KEY": "k", "PLAUSIBLE_SITE_ID": "s"})


def _resp():
    r = MagicMock()
    r.raise_for_status.return_value = None
    r.json.return_value = {"results": {"visitors": {"value": 15}, "pageviews": {"value": 20},
                                       "visit_duration": {"value": 13}, "bounce_rate": {"value": 62}}}
    return r


def test_bounce_in_metrics_en_available():
    assert "bounce_rate" in _METRICS and "bounce_rate" in PlausibleSkill().available_metrics()


def test_daily_values_leest_bounce_uit_dezelfde_aggregate_call():
    s = PlausibleSkill()
    with patch("nooch_village.skills_impl.plausible.requests.get", return_value=_resp()) as g:
        out = s.daily_values(_ctx(), "2026-07-07")
    assert out["bounce_rate"] == 62 and out["visitors"] == 15          # bounce meegekomen
    assert g.call_count == 1                                            # in de BESTAANDE call, geen tweede
    assert "bounce_rate" in g.call_args.kwargs["params"]["metrics"]


def test_daily_values_bounce_fail_closed():
    s = PlausibleSkill()
    with patch("nooch_village.skills_impl.plausible.requests.get", side_effect=RuntimeError("429")):
        out = s.daily_values(_ctx(), "2026-07-07")
    assert out["bounce_rate"] is None                                  # fout → None (geen mock)


def test_observation_meta_reeks_start_alleen_bounce():
    s = PlausibleSkill()
    assert s.observation_meta(None, "2026-07-07", "bounce_rate") == {"reeks_start": _BOUNCE_REEKS_START}
    assert s.observation_meta(None, "2026-07-07", "visitors") == {}    # bestaande velden ongewijzigd


def test_bouncepercentage_indicator_mapt_op_bounce_rate(tmp_path):
    """Geen nieuwe indicator: de bestaande Bouncepercentage-def krijgt veld='bounce_rate' (retroactief)."""
    from nooch_village.definitions import DefinitionStore, seed_catalog, migrate_definitions
    s = DefinitionStore(str(tmp_path / "defs.json"))
    seed_catalog(s)
    migrate_definitions(s)
    wrap = s.by_name("Bouncepercentage (Plausible)")
    d = s.current(wrap["id"])
    assert d and d.get("source") == "plausible" and d.get("veld") == "bounce_rate"
    # het observatie-pad dat de tegel query't valt exact op wat de collector schrijft
    from nooch_village.views.metrics import _obs_key_for_indicator
    assert _obs_key_for_indicator("plausible", "bounce_rate") == ("plausible_bounce_rate_day", "plausible")
