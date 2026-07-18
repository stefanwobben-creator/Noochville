"""Woordenschat-beheer: de mens cureert de Library vanuit cockpit 2 (/woordenschat).
Acties: functie-toggle (volg/doelwit), pauzeren (avoid), verbieden (forbidden, met
reden of default), heractiveren (approved). Render: de beheer-secties en knoppen
verschijnen alleen mét csrf-token; zonder token blijft het scherm read-only."""
from __future__ import annotations

import json
import os

from nooch_village.library import Library
from nooch_village.inbox_actions import curate_library_term, set_word_function
from nooch_village.views.woordenschat import render_woordenschat


def _lib(tmp_path):
    lib = Library(str(tmp_path / "library.json"))
    lib.curate("vegan sneakers dames", "approved",
               evidence={"volume": 210, "competition": 0.4})
    return lib


def test_pauzeren_zet_avoid_en_bewaart_evidence(tmp_path):
    lib = _lib(tmp_path)
    res = curate_library_term(lib, "vegan sneakers dames", "avoid", reason="even parkeren")
    assert res["ok"] and res["status"] == "avoid"
    e = lib.status("vegan sneakers dames")
    assert e["status"] == "avoid" and e["rationale"] == "even parkeren"
    assert e["evidence"]["volume"] == 210            # verrijking overleeft de pauze
    assert lib.is_forbidden("vegan sneakers dames")  # telt niet meer als actieve zoekterm


def test_verbieden_met_default_reden(tmp_path):
    lib = _lib(tmp_path)
    res = curate_library_term(lib, "vegan sneakers dames", "forbidden", by="mens")
    assert res["ok"] and res["status"] == "forbidden"
    e = lib.status("vegan sneakers dames")
    assert e["status"] == "forbidden" and e["by"] == "mens"
    assert e["rationale"] == "menselijke curatie via cockpit"   # zinnige default-rationale


def test_heractiveren_zet_approved_terug(tmp_path):
    lib = _lib(tmp_path)
    curate_library_term(lib, "vegan sneakers dames", "forbidden", reason="tijdelijk")
    res = curate_library_term(lib, "vegan sneakers dames", "approved", reason="toch relevant")
    assert res["ok"] and lib.is_approved("vegan sneakers dames")
    assert lib.function_of("vegan sneakers dames") == "doelwit"  # functie blijft staan


def test_valideert_woord_en_status(tmp_path):
    lib = _lib(tmp_path)
    assert not curate_library_term(lib, "", "avoid")["ok"]
    assert not curate_library_term(lib, "bestaat niet", "avoid")["ok"]
    assert not curate_library_term(lib, "vegan sneakers dames", "escalated")["ok"]


def test_functie_toggle_via_inbox_action(tmp_path):
    lib = _lib(tmp_path)
    assert lib.function_of("vegan sneakers dames") == "doelwit"
    res = set_word_function(lib, "vegan sneakers dames", "volg")
    assert res["ok"] and lib.function_of("vegan sneakers dames") == "volg"


# ── render: alle woorden gegroepeerd, beheer-knoppen alleen mét csrf ─────────

_LIB = {
    "earth shoes": {"status": "approved", "function": "doelwit",
                    "evidence": {"volume": 33100, "competition": 1.0, "position": 14}},
    "animal sneakers": {"status": "escalated", "rationale": "geen aangetoonde vraag",
                        "date": "2026-07-01"},
    "gepauzeerd woord": {"status": "avoid", "rationale": "even rust", "date": "2026-07-02"},
    "verboden woord": {"status": "forbidden", "rationale": "past niet bij de missie",
                       "date": "2026-07-03"},
}


def _render(tmp_path, csrf=""):
    dd = str(tmp_path)
    with open(os.path.join(dd, "library.json"), "w", encoding="utf-8") as f:
        json.dump(_LIB, f)
    return render_woordenschat(dd, csrf_token=csrf)


def test_render_met_csrf_toont_secties_en_knoppen(tmp_path):
    html = _render(tmp_path, csrf="tok123")
    assert "Geëscaleerd (wacht op jouw oordeel)" in html
    assert "Gepauzeerd (avoid)" in html and "Verboden" in html
    assert "animal sneakers" in html and "gepauzeerd woord" in html and "verboden woord" in html
    assert "past niet bij de missie" in html and "2026-07-03" in html   # rationale + datum
    for actie in ("ws_func", "ws_pause", "ws_forbid", "ws_approve"):    # knoppen posten /action
        assert f"value='{actie}'" in html
    assert "heractiveer" in html and "tok123" in html
    assert "⇄ volg" in html          # toggle op de approved-rij wijst naar de andere functie


def test_render_zonder_csrf_blijft_read_only(tmp_path):
    html = _render(tmp_path)
    assert "earth shoes" in html
    assert "verboden woord" not in html      # geen beheer-secties zonder schrijf-token
    assert "ws_forbid" not in html and "Acties" not in html
