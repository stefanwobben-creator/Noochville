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
    assert "Geëscaleerd (wacht op jouw oordeel)" in html and "No-follow list" in html
    assert "animal sneakers" in html and "verboden woord" in html
    assert "past niet bij de missie" in html and "2026-07-03" in html   # rationale + datum
    for actie in ("ws_forbid", "ws_approve"):                # knoppen posten /action
        assert f"value='{actie}'" in html
    assert "heractiveer" in html and "tok123" in html   # via de button-title
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


# ── nieuw-ster, ingeklapte verboden-lijst en nominatie-wachtrij ──────────────

def test_nieuw_woord_krijgt_first_seen_en_ster(tmp_path):
    from datetime import date, timedelta
    lib = _lib(tmp_path)
    e = lib.status("vegan sneakers dames")
    assert e["first_seen"] == e["date"]              # curate legt het geboortemoment vast
    # her-curatie verplaatst first_seen niet
    curate_library_term(lib, "vegan sneakers dames", "approved", reason="opnieuw")
    assert lib.status("vegan sneakers dames")["first_seen"] == e["first_seen"]
    html = render_woordenschat(str(tmp_path), csrf_token="tok")
    assert "★ nieuw" in html and "nieuw in de Library sinds" in html
    # ouder dan 28 dagen → geen ster
    import json as _json, os as _os
    path = _os.path.join(str(tmp_path), "library.json")
    d = _json.load(open(path))
    oud = (date.today() - timedelta(days=40)).isoformat()
    d["vegan sneakers dames"]["first_seen"] = oud
    _json.dump(d, open(path, "w"))
    assert "★ nieuw" not in render_woordenschat(str(tmp_path), csrf_token="tok")


def test_no_follow_list_is_ingeklapt(tmp_path):
    html = _render(tmp_path, csrf="tok123")
    assert "<details class='c2-hist'><summary class='muted'>No-follow list · 1</summary>" in html
    assert "verboden woord" in html                  # inhoud blijft aanwezig (ingeklapt)
    assert "🚫" in html and "✅" in html             # icoon-acties: verbied + heractiveer


def test_nominatie_wachtrij_op_woordenschat(tmp_path):
    import json as _json, os as _os
    _json.dump({"hemp sneakers": {"term": "hemp sneakers", "by": "concurrent_scout",
                                  "created_at": "2026-07-17"}},
               open(_os.path.join(str(tmp_path), "keyword_nominaties.json"), "w"))
    with open(_os.path.join(str(tmp_path), "library.json"), "w", encoding="utf-8") as f:
        _json.dump(_LIB, f)
    html = render_woordenschat(str(tmp_path), csrf_token="tok", can_decide=True)
    assert "Genomineerd (wacht op jouw oordeel)" in html and "hemp sneakers" in html
    assert "value='kw_nom_accept'" in html and "value='kw_nom_reject'" in html
    # zonder beslisrecht: wachtrij zichtbaar, geen knoppen
    html_ro = render_woordenschat(str(tmp_path), csrf_token="tok", can_decide=False)
    assert "alleen de Librarian-vervuller beslist" in html_ro
    assert "kw_nom_accept" not in html_ro
