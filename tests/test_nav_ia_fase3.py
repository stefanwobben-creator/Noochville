"""IA-fase 3: één gedeelde keyword-datalaag (afgeleid bij lezen) + vier rol-lenzen."""
from __future__ import annotations

import json
import os

from nooch_village.keyword_layer import build_keyword_layer, converges
from nooch_village.views.keyword_lens import render_keyword_lens, _LENS_KEYS


def _seed(dd):
    json.dump({
        "ocean plastic shoes": {"status": "approved", "function": "doelwit",
            "evidence": {"volume": 320, "competition": 0.4, "opportunity": 180,
                         "source": "gsc", "position": 8.2}},
        "leren schoenen": {"status": "forbidden",
            "evidence": {"volume": 900, "competition": 0.9, "opportunity": 40, "source": "trends"}},
    }, open(os.path.join(dd, "library.json"), "w"))
    open(os.path.join(dd, "trend_signals.jsonl"), "w").write(
        json.dumps({"term": "ocean plastic shoes", "signal_type": "emergence",
                    "recent_sustained": 1.7, "peak": 4.0,
                    "recent_months": ["2026-04", "2026-06"], "is_signal": True}) + "\n" +
        json.dumps({"term": "upcycled sneakers", "signal_type": "peak",
                    "recent_sustained": 0.4, "peak": 1.0,
                    "recent_months": ["2026-05"], "is_signal": False}) + "\n")


def test_laag_joint_op_term_union(tmp_path):
    _seed(str(tmp_path))
    layer = build_keyword_layer(str(tmp_path))
    by = {r["term"]: r for r in layer}
    assert set(by) == {"ocean plastic shoes", "leren schoenen", "upcycled sneakers"}   # union
    ops = by["ocean plastic shoes"]
    assert ops["in_library"] and ops["in_trends"]              # dezelfde term uit beide bronnen
    assert ops["volume"] == 320 and ops["signal_type"] == "emergence"
    assert ops["direction"] == "stijgend"
    # trend-only term draagt geen verzonnen library-nul
    up = by["upcycled sneakers"]
    assert up["in_trends"] and not up["in_library"] and up["volume"] is None


def test_laag_afgeleid_geen_opgeslagen_store(tmp_path):
    _seed(str(tmp_path))
    build_keyword_layer(str(tmp_path))
    # geen keyword_layer.json e.d. weggeschreven — puur afgeleid
    assert not os.path.exists(os.path.join(str(tmp_path), "keyword_layer.json"))


def test_convergentie_signaal_en_volume(tmp_path):
    _seed(str(tmp_path))
    by = {r["term"]: r for r in build_keyword_layer(str(tmp_path))}
    assert converges(by["ocean plastic shoes"])               # signaal + volume + library
    assert not converges(by["upcycled sneakers"])             # blip, geen volume
    assert not converges(by["leren schoenen"])                # volume maar geen signaal


def test_vier_lenzen_delen_de_laag(tmp_path):
    _seed(str(tmp_path))
    dd = str(tmp_path)
    assert _LENS_KEYS == {"marketing", "scientist", "trends", "library"}
    for lens in _LENS_KEYS:
        h = render_keyword_lens(dd, lens)
        assert "chip-opt" in h and "Eén keyword-datalaag" in h  # switcher + gedeelde-laag-framing
        assert h.count("chip-opt on") == 1                      # precies één actieve lens


def test_lens_specifieke_inhoud(tmp_path):
    _seed(str(tmp_path))
    dd = str(tmp_path)
    # scientist: telt echte signalen, toont blip-duiding
    sci = render_keyword_lens(dd, "scientist")
    assert "<b>1</b> van 2" in sci and "opkomst" in sci and "blip" in sci
    # trends: forbidden zichtbaar, suggesties tonen approved
    tr = render_keyword_lens(dd, "trends")
    assert "leren schoenen" in tr and "Suggesties" in tr
    # library-convergentie: alleen de samenkomst-term
    lib = render_keyword_lens(dd, "library")
    assert "ocean plastic shoes" in lib and "upcycled sneakers" not in lib


def test_onbekende_lens_valt_terug_op_trends(tmp_path):
    _seed(str(tmp_path))
    h = render_keyword_lens(str(tmp_path), "zzz")
    assert "Kansrijkheid" in h                                  # de trends-lens-kolom
