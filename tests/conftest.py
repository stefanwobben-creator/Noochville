"""Gedeelde fixtures voor de NoochVillage test-suite."""
from __future__ import annotations
import os
import pytest
from nooch_village.governance import Records
from nooch_village.models import Record, RoleDefinition, RecordType


@pytest.fixture(autouse=True)
def _isolate_village_data(monkeypatch):
    """Geen test schrijft ooit in de échte data/. Wijs BASE_DIR naar een eigen tmp-map (verse
    data), met de echte config gesymlinkt zodat settings/strategy blijven laden. Eigen tmp-map
    (niet de test-tmp_path) om botsing met tests te vermijden. Voorkomt dat een test die een
    volledige Village() bouwt de productie-inbox/records vervuilt ('nonexistent_test_rol')."""
    import tempfile
    import shutil
    import nooch_village.village as village
    real_cfg = os.path.join(village.BASE_DIR, "config")
    base = tempfile.mkdtemp(prefix="nv_test_base_")
    os.makedirs(os.path.join(base, "data"), exist_ok=True)
    if os.path.isdir(real_cfg):
        try:
            os.symlink(real_cfg, os.path.join(base, "config"))
        except OSError:
            shutil.copytree(real_cfg, os.path.join(base, "config"))
    monkeypatch.setattr(village, "BASE_DIR", base)
    yield
    shutil.rmtree(base, ignore_errors=True)


@pytest.fixture(autouse=True)
def _no_llm_throttle():
    """Tests mogen nooit écht wachten op de LLM-rate-limiter. Zet 'm op 'geen limiet'
    (de throttle-logica zelf wordt los getest in test_llm_throttle met een nep-klok)."""
    import nooch_village.llm as llm
    saved = llm.LIMITER
    llm.LIMITER = llm.RateLimiter(0)
    llm.reset_cooldowns()       # geen cooldown-lek tussen tests (de ladder slaat treden over)
    yield
    llm.LIMITER = saved
    llm.reset_cooldowns()


@pytest.fixture(autouse=True)
def _isolate_llm_keys(monkeypatch):
    """Test-only: verwijder echte LLM-provider-keys uit os.environ vóór elke test.

    config.load_context() doet os.environ.setdefault(...) uit .env (config.py:38) — dat lekt de
    echte keys process-globaal en blijft plakken tussen tests. No-key/heuristiek-tests falen dan
    order-afhankelijk: de ladder valt door naar een provider die de test zelf niet delenv't (bijv.
    Mistral) en geeft een echt antwoord. Deze fixture raakt PRODUCTIE NIET aan (load_context blijft
    ongewijzigd); ze schoont enkel de test-env, zodat de suite deterministisch is ongeacht een
    lokale/CI-.env."""
    for _k in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "MISTRAL_API_KEY"):
        monkeypatch.delenv(_k, raising=False)


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
