"""Tests voor scripts/library_cleanup.py — vijf scenario's."""
from __future__ import annotations
import importlib.util, json, sys
from pathlib import Path
from unittest.mock import patch
import pytest

# Import uit scripts/ (geen package)
_script = Path(__file__).parent.parent / "scripts" / "library_cleanup.py"
_spec = importlib.util.spec_from_file_location("library_cleanup", _script)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

classify_entry = _mod.classify_entry
run_dry_run    = _mod.run_dry_run
run_apply      = _mod.run_apply
_review_path   = _mod._review_path


# ── Helpers ───────────────────────────────────────────────────────────────────

def _write_lib(tmp_path: Path, data: dict) -> str:
    p = str(tmp_path / "library.json")
    Path(p).write_text(json.dumps(data), encoding="utf-8")
    return p


def _write_review(tmp_path: Path, data: dict) -> None:
    Path(_review_path(str(tmp_path))).write_text(
        json.dumps(data), encoding="utf-8"
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_cluster_nooch_typo_matches():
    assert classify_entry("nooches")[0]       == "nooch-typo"
    assert classify_entry("nootch")[0]        == "nooch-typo"
    assert classify_entry("no shors")[0]      == "nooch-typo"
    assert classify_entry("vegan schoenen")[0] == "vegan-risico"


def test_dry_run_produces_review_file(tmp_path):
    lib_data = {
        "nooches":              {"status": "escalated", "rationale": "", "evidence": {"source": "gsc", "interest": 5}},
        "vegan schoenen dames": {"status": "escalated", "rationale": "", "evidence": {"source": "google_trends_related", "interest": 100}},
        "compostable shoes":    {"status": "escalated", "rationale": "", "evidence": {}},
        "approved term":        {"status": "approved",  "rationale": "", "evidence": {}},
    }
    lib_path = _write_lib(tmp_path, lib_data)

    run_dry_run(lib_path, str(tmp_path))

    review_path = _review_path(str(tmp_path))
    assert Path(review_path).exists()
    review = json.loads(Path(review_path).read_text(encoding="utf-8"))

    # Alleen escalated entries
    assert "nooches" in review
    assert "vegan schoenen dames" in review
    assert "compostable shoes" in review
    assert "approved term" not in review

    # Automatisch cluster → decision = suggested
    assert review["nooches"]["decision"] == "forbidden"
    assert review["nooches"]["cluster"]  == "nooch-typo"

    # Mens-clusters → PENDING
    assert review["vegan schoenen dames"]["decision"] == "PENDING"
    assert review["compostable shoes"]["decision"]    == "PENDING"


def test_apply_blocked_on_pending(tmp_path):
    _write_lib(tmp_path, {})
    _write_review(tmp_path, {
        "nooches":              {"cluster": "nooch-typo",   "suggested": "forbidden", "decision": "forbidden"},
        "vegan schoenen dames": {"cluster": "vegan-risico", "suggested": None,        "decision": "PENDING"},
    })

    with pytest.raises(SystemExit) as exc:
        run_apply(str(tmp_path / "library.json"), str(tmp_path))
    assert exc.value.code != 0


def test_apply_writes_decisions(tmp_path, capsys):
    _write_lib(tmp_path, {})
    _write_review(tmp_path, {
        "nooches":     {"cluster": "nooch-typo", "suggested": "forbidden", "decision": "forbidden"},
        "earth shoes": {"cluster": "overig",     "suggested": None,        "decision": "forbidden"},
    })

    with patch("nooch_village.library.Library.curate") as mock_curate:
        run_apply(str(tmp_path / "library.json"), str(tmp_path))

    assert mock_curate.call_count == 2
    out = capsys.readouterr().out
    assert "2 entries bijgewerkt" in out


def test_navigational_nooch_not_typo():
    assert classify_entry("nooch amsterdam")[0]              == "overig"
    assert classify_entry("nooch traveller of the world")[0] == "overig"
    assert classify_entry("nooch wallisellen")[0]            == "overig"
    # Echte typo's matchen nog steeds
    assert classify_entry("nooches")[0] == "nooch-typo"
    assert classify_entry("nootch")[0]  == "nooch-typo"
    assert classify_entry("noech")[0]   == "nooch-typo"


def test_apply_skips_ignore(tmp_path):
    _write_lib(tmp_path, {})
    _write_review(tmp_path, {
        "globe": {"cluster": "overig", "suggested": None, "decision": "ignore"},
    })

    with patch("nooch_village.library.Library.curate") as mock_curate:
        run_apply(str(tmp_path / "library.json"), str(tmp_path))

    mock_curate.assert_not_called()
