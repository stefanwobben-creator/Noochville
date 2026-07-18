"""Woordenschat-beheer: de mens cureert de Library vanuit cockpit 2 (/woordenschat).
Bewust minimaal: per approved woord alléén ✗ verbied; goedkeuren/verbieden bij
geëscaleerde woorden; heractiveren op de forbidden-lijst als undo. De functie
(doelwit/volg) wordt automatisch bepaald (heuristiek) — geen knop. De Trend-kolom
toont de GSC-impressies-reeks als sparkline. Render: beheer-secties en knoppen
verschijnen alleen mét csrf-token; zonder token blijft het scherm read-only."""
from __future__ import annotations

import json
import os
import time

from nooch_village.library import Library
from nooch_village.inbox_actions import curate_library_term
from nooch_village.views.woordenschat import render_woordenschat


def _lib(tmp_path):
    lib = Library(str(tmp_path / "library.json"))
    lib.curate("vegan sneakers dames", "approved",
               evidence={"volume": 210, "competition": 0.4})
    return lib


def test_verbieden_met_default_reden(tmp_path):
    lib = _lib(tmp_path)
    res = curate_library_term(lib, "vegan sneakers dames", "forbidden", by="mens")
    assert res["ok"] and res["status"] == "forbidden"
    e = lib.status("vegan sneakers dames")
    assert e["status"] == "forbidden" and e["by"] == "mens"
    assert e["rationale"] == "menselijke curatie via cockpit"   # zinnige default-rationale
    assert e["evidence"]["volume"] == 210            # verrijking overleeft het verbod


def test_heractiveren_zet_approved_terug(tmp_path):
    lib = _lib(tmp_path)
    curate_library_term(lib, "vegan sneakers dames", "forbidden", reason="tijdelijk")
    res = curate_library_term(lib, "vegan sneakers dames", "approved", reason="toch relevant")
    assert res["ok"] and lib.is_approved("vegan sneakers dames")
    assert lib.function_of("vegan sneakers dames") == "doelwit"  # functie blijft staan


def test_valideert_woord_en_status(tmp_path):
    lib = _lib(tmp_path)
    assert not curate_library_term(lib, "", "forbidden")["ok"]
    assert not curate_library_term(lib, "bestaat niet", "forbidden")["ok"]
    assert not curate_library_term(lib, "vegan sneakers dames", "escalated")["ok"]


# ── render: alle woorden gegroepeerd, beheer-knoppen alleen mét csrf ─────────

_LIB = {
    "earth shoes": {"status": "approved", "function": "doelwit",
                    "evidence": {"volume": 33100, "competition": 1.0, "position": 14}},
    "animal sneakers": {"status": "escalated", "rationale": "geen aangetoonde vraag",
                        "date": "2026-07-01"},
    "verboden woord": {"status": "forbidden", "rationale": "past niet bij de missie",
                       "date": "2026-07-03"},
}


def _render(tmp_path, csrf="", observaties=None):
    dd = str(tmp_path)
    with open(os.path.join(dd, "library.json"), "w", encoding="utf-8") as f:
        json.dump(_LIB, f)
    if observaties:
        with open(os.path.join(dd, "observations.jsonl"), "w", encoding="utf-8") as f:
            for o in observaties:
                f.write(json.dumps(o) + "\n")
    return render_woordenschat(dd, csrf_token=csrf)


def test_render_met_csrf_toont_secties_en_knoppen(tmp_path):
    html = _render(tmp_path, csrf="tok123")
    assert "Geëscaleerd (wacht op jouw oordeel)" in html and "Verboden" in html
    assert "animal sneakers" in html and "verboden woord" in html
    assert "past niet bij de missie" in html and "2026-07-03" in html   # rationale + datum
    for actie in ("ws_forbid", "ws_approve"):                # knoppen posten /action
        assert f"value='{actie}'" in html
    assert "heractiveer" in html and "tok123" in html
    # bewust GEEN toggle- of pauzeerknoppen meer (versimpeling)
    assert "ws_func" not in html and "ws_pause" not in html


def test_render_zonder_csrf_blijft_read_only(tmp_path):
    html = _render(tmp_path)
    assert "earth shoes" in html
    assert "verboden woord" not in html      # geen beheer-secties zonder schrijf-token
    assert "ws_forbid" not in html and "Acties" not in html


def test_trend_sparkline_uit_gsc_reeks(tmp_path):
    obs = [{"role_id": "collector", "metric": "gsc_impressions_day::earth_shoes",
            "value": v, "ts": time.time() + i, "datum": f"2026-07-{10+i:02d}",
            "bron": "gsc", "meta": {"keyword": "earth shoes"}}
           for i, v in enumerate([5, 9, 14, 11, 20])]
    html = _render(tmp_path, csrf="tok123", observaties=obs)
    assert "Trend" in html
    assert "class='spark'" in html                        # sparkline-SVG voor earth shoes
    assert "GSC-impressies 2026-07-10" in html            # tooltip met datumbereik


def test_trend_zonder_reeks_toont_streepje(tmp_path):
    html = _render(tmp_path, csrf="tok123")
    assert "nog geen GSC-reeks" in html
