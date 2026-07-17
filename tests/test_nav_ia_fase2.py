"""IA-fase 2: tools wonen onder hun eigenaar-rol (kaart op de Tools-tab) + twee minimale
nieuwe lens-schermen (Keywords voor de scout, Long-term trends voor de Scientist)."""
from __future__ import annotations

import json
import os
import types

from nooch_village.views.overview import _role_tools_html, _ROLE_TOOLS
from nooch_village.views.keywords import render_keywords
from nooch_village.views.long_term_trends import render_long_term_trends


def _rec(rid):
    return types.SimpleNamespace(id=rid)


def test_role_tools_kaarten_per_eigenaar_rol():
    marketing = _role_tools_html(_rec("mother_earth__nooch__marketing_lead"))
    assert "Linkbuilding" in marketing and "/linkbuilding" in marketing and "tile-grid" in marketing
    lara = _role_tools_html(_rec("librarian"))
    assert "Woordenschat" in lara and "Signals &amp; Insights" in lara
    assert "/woordenschat" in lara and "/signals" in lara
    scout = _role_tools_html(_rec("concurrent_scout"))
    assert "Keywords" in scout and "/keywords" in scout
    sid = _role_tools_html(_rec("harry_hemp"))
    assert "Long-term trends" in sid and "/long-term-trends" in sid


def test_role_tools_leeg_voor_niet_eigenaar():
    assert _role_tools_html(_rec("iemand_anders")) == ""
    assert _role_tools_html(_rec("")) == ""


def test_registry_dekt_de_vier_eigenaars():
    assert set(_ROLE_TOOLS) == {
        "mother_earth__nooch__marketing_lead", "librarian", "concurrent_scout", "harry_hemp"}


def test_keywords_leest_bibliotheek_rangschikt_op_kansrijkheid(tmp_path):
    d = str(tmp_path)
    json.dump({
        "ocean plastic shoes": {"status": "approved",
            "evidence": {"volume": 320, "competition": 0.4, "opportunity": 180, "source": "gsc"}},
        "leren schoenen": {"status": "forbidden",
            "evidence": {"volume": 900, "competition": 0.9, "opportunity": 40, "source": "trends"}},
    }, open(os.path.join(d, "library.json"), "w"))
    h = render_keywords(d)
    assert "ocean plastic shoes" in h and "leren schoenen" in h
    # kansrijkste eerst: de approved (opportunity 180) staat vóór de forbidden (40)
    assert h.index("ocean plastic shoes") < h.index("leren schoenen")
    assert "chip green" in h and "chip coral" in h          # status-kleuren
    assert "Suggesties" in h                                 # approved-kandidaten als suggestie


def test_keywords_leeg_zonder_data(tmp_path):
    h = render_keywords(str(tmp_path))
    assert "Nog geen geëvalueerde keywords" in h


def test_long_term_trends_scheidt_signaal_van_blip(tmp_path):
    d = str(tmp_path)
    open(os.path.join(d, "trend_signals.jsonl"), "w").write(
        json.dumps({"term": "upcycled sneakers", "signal_type": "emergence",
                    "recent_sustained": 1.7, "peak": 4.0,
                    "recent_months": ["2026-04", "2026-05", "2026-06"], "is_signal": True}) + "\n" +
        json.dumps({"term": "carbon neutral boots", "signal_type": "peak",
                    "recent_sustained": 0.4, "peak": 1.0,
                    "recent_months": ["2026-04", "2026-06"], "is_signal": False}) + "\n")
    h = render_long_term_trends(d)
    assert "upcycled sneakers" in h and "carbon neutral boots" in h
    assert "opkomst" in h and "blip" in h                    # duiding per signaal-type
    assert "<b>1</b> van 2" in h                             # 1 echt signaal van 2 termen
    # echt signaal (emergence) staat vóór de blip (peak)
    assert h.index("upcycled sneakers") < h.index("carbon neutral boots")


def test_long_term_trends_laatste_observatie_per_term(tmp_path):
    d = str(tmp_path)
    open(os.path.join(d, "trend_signals.jsonl"), "w").write(
        json.dumps({"term": "vegan boots", "signal_type": "flat",
                    "recent_sustained": 0.1, "is_signal": False}) + "\n" +
        json.dumps({"term": "vegan boots", "signal_type": "trend",
                    "recent_sustained": 2.2, "is_signal": True}) + "\n")
    h = render_long_term_trends(d)
    # de latere observatie (trend, is_signal) telt — 1 van 1
    assert "<b>1</b> van 1" in h and "stijgend" in h
