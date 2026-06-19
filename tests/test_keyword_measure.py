"""Tests voor keyword_measure — gate-volgorde en runner-injectie. Geen netwerk."""
from __future__ import annotations
import pytest
from nooch_village.keyword_batch import propose_batch
from nooch_village.keyword_measure import measure_batch


class _FakeRunner:
    def __init__(self, return_value=None):
        self.call_count = 0
        self.last_args = None
        self._return = return_value or []

    def __call__(self, candidates, country, data_source):
        self.call_count += 1
        self.last_args = (candidates, country, data_source)
        return self._return


def _batch(market="nl", tier="core"):
    return propose_batch(market, tier=tier)


def _approval(ceiling=100):
    return {"approved": True, "credits_ceiling": ceiling, "by": "human-cli"}


def test_geen_approval_geeft_permission_error_runner_niet_aangeroepen():
    runner = _FakeRunner()
    with pytest.raises(PermissionError, match="niet goedgekeurd"):
        measure_batch(_batch(), approval=None, runner=runner)
    assert runner.call_count == 0


def test_approved_false_geeft_permission_error_runner_niet_aangeroepen():
    runner = _FakeRunner()
    with pytest.raises(PermissionError, match="niet goedgekeurd"):
        measure_batch(_batch(), approval={"approved": False, "credits_ceiling": 100, "by": "x"}, runner=runner)
    assert runner.call_count == 0


def test_credits_boven_plafond_geeft_valueerror_runner_niet_aangeroepen():
    runner = _FakeRunner()
    batch = _batch()
    ceiling = batch["estimated_credits"] - 1  # één te weinig
    with pytest.raises(ValueError, match="creditplafond"):
        measure_batch(batch, approval=_approval(ceiling=ceiling), runner=runner)
    assert runner.call_count == 0


def test_geldige_goedkeuring_roept_runner_exact_eenmaal_aan():
    runner = _FakeRunner()
    batch = _batch()
    measure_batch(batch, approval=_approval(), runner=runner)
    assert runner.call_count == 1
    candidates, country, data_source = runner.last_args
    assert candidates == batch["candidates"]
    assert country == batch["country"]
    assert data_source == batch["data_source"]


def test_resultaatrecord_heeft_alle_zeven_keys_en_credits_spent():
    fake_results = [{"keyword": "vegan schoenen", "vol": 3400}]
    runner = _FakeRunner(return_value=fake_results)
    batch = _batch()
    result = measure_batch(batch, approval=_approval(), runner=runner)
    for key in ("market", "tier", "data_source", "country", "requested", "credits_spent", "results"):
        assert key in result, f"Key '{key}' ontbreekt in resultaatrecord"
    assert result["credits_spent"] == len(result["requested"])
    assert result["results"] == fake_results


def test_credits_spent_binnen_plafond_na_geslaagde_meting():
    runner = _FakeRunner()
    batch = _batch()
    ceiling = batch["estimated_credits"]
    result = measure_batch(batch, approval=_approval(ceiling=ceiling), runner=runner)
    assert result["credits_spent"] <= ceiling


def test_gate_toetst_op_echte_kandidaten_niet_op_estimated_credits():
    """Gate moet blokkeren als len(candidates) het plafond overschrijdt,
    ook als estimated_credits lager is (misvormde batch). Runner mag niet worden aangeroepen."""
    runner = _FakeRunner()
    batch = _batch()
    # Manipuleer estimated_credits zodat het lager is dan het werkelijke aantal kandidaten
    echte_tel = len(batch["candidates"])
    assert echte_tel >= 2, "batch heeft te weinig kandidaten voor deze test"
    batch["estimated_credits"] = echte_tel - 1  # goedkoper dan de werkelijkheid
    ceiling = echte_tel - 1                      # plafond ertussenin: boven estimated, onder echte tel
    with pytest.raises(ValueError, match="creditplafond"):
        measure_batch(batch, approval=_approval(ceiling=ceiling), runner=runner)
    assert runner.call_count == 0
