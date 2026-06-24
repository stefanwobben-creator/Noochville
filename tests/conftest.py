"""Gedeelde fixtures voor de NoochVillage test-suite."""
from __future__ import annotations
import pytest
from nooch_village.governance import Records
from nooch_village.models import Record, RoleDefinition, RecordType


@pytest.fixture(autouse=True)
def _no_llm_throttle():
    """Tests mogen nooit écht wachten op de LLM-rate-limiter. Zet 'm op 'geen limiet'
    (de throttle-logica zelf wordt los getest in test_llm_throttle met een nep-klok)."""
    import nooch_village.llm as llm
    saved = llm.LIMITER
    llm.LIMITER = llm.RateLimiter(0)
    yield
    llm.LIMITER = saved


@pytest.fixture
def records(tmp_path):
    """Lege Records backed by een tijdelijk bestand."""
    return Records(str(tmp_path / "governance.json"))


@pytest.fixture
def records_with_root(records):
    """Records met een wortelcirkel (noochville) als baseline voor gate-tests."""
    root = Record(
        id="noochville",
        type=RecordType.CIRCLE,
        parent=None,
        definition=RoleDefinition(
            purpose=(
                "Nooch.earth is het duurzaamste schoenenmerk ter wereld. "
                "Kernwaarden: geen plastic, geen leer, in Europa geproduceerd."
            ),
            policies=["geen plastic", "geen leer", "alleen nooch.earth"],
        ),
        source="seed",
    )
    records.put(root)
    return records
