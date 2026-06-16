"""Tests voor scripts/extract_terms.py — vier scenario's."""
from __future__ import annotations
import importlib.util, json
from pathlib import Path
from unittest.mock import patch
import pytest

_script = Path(__file__).parent.parent / "scripts" / "extract_terms.py"
_spec = importlib.util.spec_from_file_location("extract_terms", _script)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

extract = _mod.extract
main    = _mod.main


def _library(*known: str) -> dict:
    return {term: {"status": "approved"} for term in known}


def test_filters_known_terms():
    library = _library("vegan")
    with patch.object(_mod, "reason", return_value='["mycelium", "vegan", "polyurethaan"]'):
        unknown, all_terms = extract("tekst", library)
    assert "mycelium" in unknown
    assert "polyurethaan" in unknown
    assert "vegan" not in unknown
    assert len(all_terms) == 3
    assert len(unknown) == 2


def test_handles_empty_llm_response(capsys):
    library = _library("vegan")
    with patch.object(_mod, "reason", return_value="[]"):
        unknown, all_terms = extract("tekst", library)
    assert unknown == []
    assert all_terms == []


def test_handles_invalid_json():
    library = _library()
    with patch.object(_mod, "reason", return_value="geen json maar tekst"):
        with pytest.raises(ValueError, match="geen geldige JSON"):
            extract("tekst", library)


def test_file_not_found(tmp_path):
    pad = str(tmp_path / "bestaat_niet.txt")
    import sys
    with patch("sys.argv", ["extract_terms.py", pad]):
        with pytest.raises(SystemExit) as exc:
            main()
    assert exc.value.code != 0
