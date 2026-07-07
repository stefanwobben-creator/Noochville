"""Bi-weekly bevindingen-rapport: deterministisch, gegrond (delta t.o.v. vorige periode), bronnen zonder
data expliciet benoemd, te-weinig-punten → geen verzonnen trend."""
from __future__ import annotations
import datetime
import types

from nooch_village.observations import ObservationStore
from nooch_village.biweekly_report import build_biweekly_report, write_biweekly_report


def _st(tmp_path):
    obs = ObservationStore(str(tmp_path / "o.jsonl"))
    # plausible: één punt in de vorige periode (06-25) + één in de periode (07-10) → delta
    obs.record_daily("plausible", "plausible_visitors_day", 10, bron="plausible", datum="2026-06-25")
    obs.record_daily("plausible", "plausible_visitors_day", 25, bron="plausible", datum="2026-07-10")
    # alphavantage: één punt in de periode → te weinig voor een trend
    obs.record_daily("alphavantage", "alphavantage_spx_day", 751.28, bron="alphavantage", datum="2026-07-10")
    return types.SimpleNamespace(observations=obs)


def test_report_delta_gronden_en_geen_data(tmp_path):
    md = build_biweekly_report(_st(tmp_path), datetime.date(2026, 7, 14), window_days=14)
    assert "Bi-weekly bevindingen" in md and "2026-06-30 → 2026-07-14" in md
    assert "Web-analytics (Plausible)" in md and "▲ 15" in md          # 25 − 10
    assert "te weinig voor een trend" in md                            # alphavantage: 1 punt
    assert "Nieuwstoon (GDELT)" in md and "Geen observaties" in md      # verwacht maar afwezig → benoemd
    assert "geen verzonnen duiding" in md                              # discipline expliciet


def test_write_report_naar_output(tmp_path):
    path = write_biweekly_report(_st(tmp_path), str(tmp_path), datetime.date(2026, 7, 14))
    assert path.endswith("bevindingen_2026-07-14.md")
    assert "Bi-weekly bevindingen" in open(path, encoding="utf-8").read()
