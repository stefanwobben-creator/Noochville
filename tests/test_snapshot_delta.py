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
    assert _source_kind("openalex") == "snapshot" and _source_frequency("openalex") == "weekly"
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
    # snapshot (weekly) tolereert langer dan flux: 9 dagen oud = nog fresh voor openalex, dood voor plausible
    assert _fresh_threshold("openalex") == 10 and _fresh_threshold("plausible") == 7


def test_indicator_freshness_snapshot_ruimer_dan_flux(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    negen = (datetime.date(2026, 7, 15) - datetime.timedelta(days=9)).isoformat()
    st.observations.record_daily("o", "openalex_works_day", 1000, bron="openalex", datum=negen)
    st.observations.record_daily("p", "plausible_visitors_day", 42, bron="plausible", datum=negen)
    today = datetime.date(2026, 7, 15)
    assert indicator_freshness(st, "openalex", "works", today=today) == "fresh"   # 9 ≤ 10 (snapshot)
    assert indicator_freshness(st, "plausible", "visitors", today=today) == "stale"  # 9 > 7 (flux)


def test_render_snapshot_tegel_toont_delta_stand_optioneel(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path)); rec = st.records.get(C)
    now = time.time()
    st.observations.record_daily("o", "openalex_works_day", 1000, bron="openalex", datum="2026-06-29", ts=now - 14 * DAY)
    st.observations.record_daily("o", "openalex_works_day", 1080, bron="openalex", datum="2026-07-06", ts=now - 7 * DAY)
    h = _render_tile(st, rec, {"id": "t1", "source": "openalex", "measure": "works", "form": "getal"},
                     cutoff=None, csrf="")
    assert "/week" in h and "gemeten over 7 dagen" in h        # genormaliseerde delta + interval
    assert "absolute stand" in h and "1080" in h               # stand blijft beschikbaar (uitklap), niet default


def test_render_flux_tegel_ongewijzigd(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path)); rec = st.records.get(C)
    st.observations.record_daily("p", "plausible_visitors_day", 42, bron="plausible", datum="2026-07-06", ts=time.time())
    h = _render_tile(st, rec, {"id": "t2", "source": "pulse_visitors", "measure": "visitors", "form": "getal"},
                     cutoff=None, csrf="")
    assert "/week" not in h and "gemeten over" not in h        # flux → geen delta-taal
