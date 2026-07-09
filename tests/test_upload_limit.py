"""Upload-limiet + eerlijke foutafhandeling.

- _upload_max_bytes: config-key upload_max_bytes (default 20M), '20M'/'20MB'/bytes, fail-soft default.
- _upload_error: te groot → 413-melding; leeg/ontbrekend bestand → 400-melding (geen stille no-op); geldig → None.
- wire(): de modal-fetch checkt response.ok → een niet-2xx toont NOOIT '✓ opgeslagen' (JS-conditie als string-assert).
"""
from __future__ import annotations

import os

from nooch_village.cockpit2 import _upload_max_bytes, _upload_error
from nooch_village.views.projects import _modal_html


# ── config-key ───────────────────────────────────────────────────────────────
def test_upload_max_bytes_default_en_parsing(monkeypatch):
    monkeypatch.delenv("upload_max_bytes", raising=False)
    assert _upload_max_bytes() == 20 * 1024 * 1024                # default 20M
    monkeypatch.setenv("upload_max_bytes", "25M")
    assert _upload_max_bytes() == 25 * 1024 * 1024
    monkeypatch.setenv("upload_max_bytes", "20MB")
    assert _upload_max_bytes() == 20 * 1024 * 1024
    monkeypatch.setenv("upload_max_bytes", "1048576")            # kale bytes
    assert _upload_max_bytes() == 1048576
    monkeypatch.setenv("upload_max_bytes", "onzin")             # fail-soft → default
    assert _upload_max_bytes() == 20 * 1024 * 1024


def test_app_limiet_onder_nginx_cap():
    # de app-default (20M) ligt bewust onder het nginx-plafond (25M in deploy/nginx.conf)
    assert _upload_max_bytes.__doc__ and 20 * 1024 * 1024 < 25 * 1024 * 1024


# ── _upload_error (de gate vóór wegschrijven) ────────────────────────────────
def test_te_groot_bestand_geeft_413(monkeypatch):
    monkeypatch.delenv("upload_max_bytes", raising=False)
    limit = _upload_max_bytes()
    big = {"file": ("groot.pdf", b"x" * (limit + 1))}
    err = _upload_error(big, limit)
    assert err is not None and err[1] == 413 and "te groot" in err[0].lower() and "20 MB" in err[0]


def test_leeg_of_ontbrekend_bestand_geeft_400():
    limit = _upload_max_bytes()
    assert _upload_error({}, limit) == ("Geen bestand geselecteerd", 400)          # geen file-veld
    assert _upload_error({"file": ("", b"")}, limit)[1] == 400                     # lege filename+blob
    assert _upload_error({"file": ("naam.pdf", b"")}, limit)[1] == 400             # filename maar lege blob


def test_geldig_bestand_geen_fout():
    limit = _upload_max_bytes()
    assert _upload_error({"file": ("ok.pdf", b"kleine inhoud")}, limit) is None


# ── deel 3: wire() checkt response.ok ────────────────────────────────────────
def test_wire_checkt_response_ok():
    modal = _modal_html()
    assert "if(!resp.ok)" in modal                               # de response.ok-poort bestaat
    # de succes-toast staat NIET onvoorwaardelijk vóór de ok-check: de non-ok-tak returnt eerst
    idx_ok = modal.index("if(!resp.ok)")
    idx_succes = modal.index("opgeslagen')")
    assert idx_ok < idx_succes                                   # eerst ok-check, dan pas 'opgeslagen'
