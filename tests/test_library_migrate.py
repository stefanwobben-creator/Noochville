"""Tests voor scripts/library_migrate_v2.py — drie scenario's."""
from __future__ import annotations
import importlib.util
from pathlib import Path

_script = Path(__file__).parent.parent / "scripts" / "library_migrate_v2.py"
_spec = importlib.util.spec_from_file_location("library_migrate_v2", _script)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

migrate = _mod.migrate


def _entry(status="escalated", **extra):
    return {"status": status, "rationale": "", **extra}


def test_dry_run_no_writes():
    data = {
        "plastic-free": _entry(),
        "vegan":        _entry(),
    }
    original = {k: dict(v) for k, v in data.items()}

    updated, already_complete = migrate(data, dry_run=True)

    assert updated == 2
    assert already_complete == 0
    assert data == original


def test_apply_adds_three_fields():
    data = {
        "plastic-free": _entry(),
        "vegan":        _entry(),
    }

    updated, already_complete = migrate(data, dry_run=False)

    assert updated == 2
    assert already_complete == 0
    for entry in data.values():
        assert entry["locale"] is None
        assert entry["concept_id"] is None
        assert entry["gemet_id"] is None


def test_idempotent():
    data = {
        "plastic-free": _entry(locale="en", concept_id="plastic_free", gemet_id=42),
        "vegan":        _entry(),
    }

    updated, already_complete = migrate(data, dry_run=False)

    assert updated == 1
    assert already_complete == 1
    # Bestaande waarden niet overschreven
    assert data["plastic-free"]["locale"] == "en"
    assert data["plastic-free"]["concept_id"] == "plastic_free"
    assert data["plastic-free"]["gemet_id"] == 42
    # Ontbrekende velden ingevuld
    assert data["vegan"]["locale"] is None
    assert data["vegan"]["concept_id"] is None
    assert data["vegan"]["gemet_id"] is None
