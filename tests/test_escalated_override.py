"""Escalated-berg afroombaar vanuit het dashboard: override_library_term schrijft via
Library.curate, en de cockpit toont een 'wacht op jouw oordeel'-blok met knoppen."""
from __future__ import annotations

from nooch_village.library import Library
from nooch_village.inbox_actions import override_library_term
from nooch_village.cockpit import render_html


def _lib(tmp_path):
    lib = Library(str(tmp_path / "library.json"))
    lib.curate("animal sneakers", "escalated", rationale="geen aangetoonde vraag", by="Librarian")
    return lib


def test_override_approve_zet_op_approved(tmp_path):
    lib = _lib(tmp_path)
    res = override_library_term(lib, "animal sneakers", "approve", reason="past bij de missie")
    assert res["ok"] and res["status"] == "approved"
    entry = lib.status("animal sneakers")
    assert entry["status"] == "approved" and entry["by"] == "human"


def test_override_reject_zet_op_forbidden(tmp_path):
    lib = _lib(tmp_path)
    res = override_library_term(lib, "animal sneakers", "reject")
    assert res["ok"] and res["status"] == "forbidden"
    assert lib.status("animal sneakers")["status"] == "forbidden"


def test_override_onbekend_besluit_faalt(tmp_path):
    lib = _lib(tmp_path)
    assert not override_library_term(lib, "animal sneakers", "maybe")["ok"]


def test_override_onbekend_woord_faalt(tmp_path):
    lib = _lib(tmp_path)
    assert not override_library_term(lib, "bestaat niet", "approve")["ok"]


def _snap_with_escalated():
    return {
        "roster": [], "inbox": [], "projects": [], "insights": [], "generated_at": 0,
        "library": [
            {"word": "animal sneakers", "status": "escalated",
             "rationale": "geen aangetoonde vraag", "by": "Librarian", "date": ""},
            {"word": "vegan", "status": "approved", "rationale": "", "by": "Librarian", "date": "2026-01-01"},
        ],
    }


def test_render_toont_escalated_blok_met_knoppen_in_verwerkmodus():
    html = render_html(_snap_with_escalated(), csrf_token="tok")
    assert "Wacht op jouw oordeel" in html
    assert "animal sneakers" in html
    assert "lib_override" in html and "keur goed" in html and "verbied" in html


def test_render_read_only_toont_blok_zonder_knoppen():
    html = render_html(_snap_with_escalated())          # csrf_token=None → read-only
    assert "Wacht op jouw oordeel" in html              # zichtbaar
    assert "animal sneakers" in html
    assert "lib_override" not in html                   # maar geen knoppen
