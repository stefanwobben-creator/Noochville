"""Tests voor scripts/extract_terms.py — negen scenario's."""
from __future__ import annotations
import importlib.util, json
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

_script = Path(__file__).parent.parent / "scripts" / "extract_terms.py"
_spec = importlib.util.spec_from_file_location("extract_terms", _script)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

extract     = _mod.extract
main        = _mod.main
run_dry_run = _mod.run_dry_run
run_apply   = _mod.run_apply
_review_path = _mod._review_path


def _library(*known: str) -> dict:
    return {term: {"status": "approved"} for term in known}


def _write_lib(tmp_path: Path, *known: str) -> str:
    p = str(tmp_path / "library.json")
    Path(p).write_text(json.dumps(_library(*known)), encoding="utf-8")
    return p


def _write_text(tmp_path: Path, content: str) -> str:
    p = str(tmp_path / "tekst.txt")
    Path(p).write_text(content, encoding="utf-8")
    return p


def _write_review(tmp_path: Path, data: dict) -> None:
    Path(_review_path(str(tmp_path))).write_text(
        json.dumps(data), encoding="utf-8"
    )


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


# ── Review-file en --apply ────────────────────────────────────────────────────

def test_dry_run_writes_review_file(tmp_path):
    lib_path = _write_lib(tmp_path, "vegan")
    text_path = _write_text(tmp_path, "test tekst")

    with patch.object(_mod, "reason", return_value='["mycelium", "vegan", "polyurethaan"]'):
        run_dry_run(text_path, lib_path, str(tmp_path))

    review_path = Path(_review_path(str(tmp_path)))
    assert review_path.exists()
    review = json.loads(review_path.read_text(encoding="utf-8"))

    assert "mycelium" in review
    assert "polyurethaan" in review
    assert "vegan" not in review
    assert review["mycelium"]["decision"] == "PENDING"
    assert review["mycelium"]["source"] == text_path


def test_apply_blocked_on_pending(tmp_path):
    lib_path = _write_lib(tmp_path)
    _write_review(tmp_path, {
        "mycelium":    {"source": "tekst.txt", "decision": "escalated"},
        "polyurethaan": {"source": "tekst.txt", "decision": "PENDING"},
    })
    with patch("nooch_village.library.Library.curate") as mock_curate:
        with pytest.raises(SystemExit) as exc:
            run_apply(lib_path, str(tmp_path))
    assert exc.value.code != 0
    mock_curate.assert_not_called()


def test_apply_writes_escalated_and_forbidden(tmp_path):
    lib_path = _write_lib(tmp_path)
    _write_review(tmp_path, {
        "mycelium":    {"source": "tekst.txt", "decision": "escalated"},
        "polyurethaan": {"source": "tekst.txt", "decision": "escalated"},
        "fast fashion": {"source": "tekst.txt", "decision": "forbidden"},
        "eva-schuim":  {"source": "tekst.txt", "decision": "ignore"},
    })
    with patch("nooch_village.library.Library.curate") as mock_curate:
        run_apply(lib_path, str(tmp_path))

    assert mock_curate.call_count == 3
    called_terms = {c.args[0] for c in mock_curate.call_args_list}
    assert "mycelium" in called_terms
    assert "polyurethaan" in called_terms
    assert "fast fashion" in called_terms
    assert "eva-schuim" not in called_terms


def test_apply_missing_review_file(tmp_path):
    lib_path = _write_lib(tmp_path)
    with pytest.raises(SystemExit) as exc:
        run_apply(lib_path, str(tmp_path))
    assert exc.value.code != 0


def test_apply_invalid_decision(tmp_path):
    lib_path = _write_lib(tmp_path)
    _write_review(tmp_path, {
        "mycelium": {"source": "tekst.txt", "decision": "verkeerd"},
    })
    with pytest.raises(SystemExit) as exc:
        run_apply(lib_path, str(tmp_path))
    assert exc.value.code != 0
