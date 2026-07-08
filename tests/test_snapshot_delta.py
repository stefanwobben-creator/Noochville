"""Snapshot-delta-weergave: het declaratieve kind-veld stuurt de tegel-render, de delta-afleiding en de
vers-drempel. Snapshot-bronnen tonen de genormaliseerde delta (+N/periode) met het werkelijke interval;
flux-bronnen blijven de waarde zelf tonen. Testdata in de tmp-map."""
from __future__ import annotations
import datetime
import time

from nooch_village import cockpit2
from nooch_village.views.metrics import (_source_kind, _source_frequency, _snapshot_delta,
                                        _fresh_threshold, indicator_freshness, _render_tile)

C = "mother_earth__nooch"
DAY = 86400


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def test_kind_declaratief_van_de_skill():
    assert _source_kind("semanticscholar") == "snapshot" and _source_frequency("semanticscholar") == "monthly"
    assert _source_kind("openalex") == "flux"                # OpenAlex is nu een 90/30-flow, geen snapshot meer
    assert _source_kind("plausible") == "flux" and _source_kind("shopify") == "flux"
    assert _source_kind("gsc") == "flux" and _source_kind("onbekend") == "flux"


def test_snapshot_delta_normalisatie_en_interval():
    # weekly, exact 7 dagen tussen twee standen → +80/week over 7 dagen
    assert _snapshot_delta([(0, 1000), (7 * DAY, 1080)], "weekly") == (80.0, 7)
    # gemiste periode: 14 dagen tussen metingen → genormaliseerd +40/week, interval toont de 14 dagen
    assert _snapshot_delta([(0, 1000), (14 * DAY, 1080)], "weekly") == (40.0, 14)
    # monthly: 30-dagen-periode
    d, iv = _snapshot_delta([(0, 500), (15 * DAY, 560)], "monthly")
    assert round(d) == 120 and iv == 15                       # +60 over 15d → +120/maand
    # < 2 metingen → geen nep-delta
    assert _snapshot_delta([(0, 1000)], "weekly") == (None, None)
    assert _snapshot_delta([], "weekly") == (None, None)


def test_vers_drempel_kind_aware():
    # snapshot (monthly) tolereert langer dan flux: semanticscholar 45d; plausible + openalex (flux) 7d
    assert _fresh_threshold("semanticscholar") == 45 and _fresh_threshold("plausible") == 7
    assert _fresh_threshold("openalex") == 7                 # flux nu


def test_indicator_freshness_snapshot_ruimer_dan_flux(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    veertig = (datetime.date(2026, 7, 15) - datetime.timedelta(days=40)).isoformat()
    st.observations.record_daily("s", "semanticscholar_papers_day", 1000, bron="semanticscholar", datum=veertig)
    st.observations.record_daily("p", "plausible_visitors_day", 42, bron="plausible", datum=veertig)
    today = datetime.date(2026, 7, 15)
    assert indicator_freshness(st, "semanticscholar", "papers", today=today) == "fresh"  # 40 ≤ 45 (monthly snapshot)
    assert indicator_freshness(st, "plausible", "visitors", today=today) == "stale"      # 40 > 7 (flux)


def test_render_snapshot_tegel_toont_delta_stand_optioneel(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path)); rec = st.records.get(C)
    now = time.time()
    st.observations.record_daily("s", "semanticscholar_papers_day", 1000, bron="semanticscholar", datum="2026-06-06", ts=now - 30 * DAY)
    st.observations.record_daily("s", "semanticscholar_papers_day", 1080, bron="semanticscholar", datum="2026-07-06", ts=now)
    h = _render_tile(st, rec, {"id": "t1", "source": "semanticscholar", "measure": "papers", "form": "getal"},
                     cutoff=None, csrf="")
    assert "/maand" in h and "gemeten over 30 dagen" in h      # genormaliseerde delta + interval (monthly snapshot)
    assert "absolute stand" in h and "1080" in h               # stand blijft beschikbaar (uitklap), niet default


def test_render_flux_tegel_ongewijzigd(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path)); rec = st.records.get(C)
    st.observations.record_daily("p", "plausible_visitors_day", 42, bron="plausible", datum="2026-07-06", ts=time.time())
    h = _render_tile(st, rec, {"id": "t2", "source": "pulse_visitors", "measure": "visitors", "form": "getal"},
                     cutoff=None, csrf="")
    assert "/week" not in h and "gemeten over" not in h        # flux → geen delta-taal
