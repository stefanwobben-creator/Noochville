"""Data-vers-signaal (3 staten: recente data / geen recente data / geen data) via de gedeelde helper,
getoond op het koppelscherm én in de KPI-wizard; plus de all-coupled-boodschap op het koppelscherm.
Testdata in de tmp-map. Dezelfde observatie-store als de tegels voedt het signaal."""
from __future__ import annotations
import datetime

from nooch_village import cockpit2
from nooch_village.views.metrics import indicator_freshness, freshness_chip
from nooch_village.views.catalog_koppelen import _koppel_section

C = "mother_earth__nooch"
TODAY = datetime.date(2026, 7, 5)


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def test_drie_staten_plus_geen_bronveld(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    st.observations.record_daily("x", "plausible_visitors_day", 10, bron="plausible", datum="2026-07-03")     # 2d
    st.observations.record_daily("s", "shopify_orders_day", 5, bron="shopify", datum="2026-06-01")  # 34d
    assert indicator_freshness(st, "plausible", "visitors", today=TODAY) == "fresh"
    assert indicator_freshness(st, "shopify", "orders", today=TODAY) == "stale"
    assert indicator_freshness(st, "gsc", "impressions", today=TODAY) == "none"       # bron-veld, niet gevoed
    assert indicator_freshness(st, "plausible", "pageviews", today=TODAY) == "none"
    assert indicator_freshness(st, "handmatig", "x", today=TODAY) is None             # geen bron-veld → geen chip
    assert freshness_chip(None) == "" and "recente data" in freshness_chip("fresh")


def test_drempel_zeven_dagen(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    st.observations.record_daily("x", "plausible_visitors_day", 1, bron="plausible", datum="2026-06-28")
    assert indicator_freshness(st, "plausible", "visitors", today=datetime.date(2026, 7, 5)) == "fresh"   # 7d ≤ 7
    assert indicator_freshness(st, "plausible", "visitors", today=datetime.date(2026, 7, 6)) == "stale"   # 8d > 7


def test_koppel_all_coupled_boodschap_en_vers(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    # plausible is in de seed volledig gekoppeld → banner + geen publiceer-formulier
    st.observations.record_daily("x", "plausible_visitors_day", 9, bron="plausible", datum=datetime.date.today().isoformat())
    h = _koppel_section(st, "t", "plausible")
    assert "Alle velden van deze bron staan in de catalogus" in h
    assert "Publiceer naar catalogus" not in h                 # niets te koppelen → geen formulier
    assert "recente data" in h                                 # visitors vult
    assert "geen data" in h                                    # pageviews/visit_duration niet gevoed


def test_koppel_mixed_toont_formulier_en_vers(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    st.defs._d.clear(); st.defs._save()                        # niets gekoppeld → alle shopify-velden ongekoppeld
    h = _koppel_section(st, "t", "shopify")
    assert "Alle velden van deze bron" not in h                # niet all-coupled
    assert h.count("Publiceer naar catalogus") == 4            # 4 ongekoppelde velden met formulier
    assert "geen data" in h                                    # shopify wordt niet gevoed → geen data


def test_wizard_toont_vers_signaal(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    st.observations.record_daily("x", "plausible_visitors_day", 7, bron="plausible", datum=datetime.date.today().isoformat())
    w = cockpit2.render_kpi_composer(st, C, csrf_token="t")
    assert "recente data" in w                                 # visitors-indicator vult
    assert "geen data" in w                                    # de niet-gevoede bron-indicatoren


def test_catalog_toont_vers_signaal(tmp_path):
    """Op /catalog krijgt elke definitiekaart hetzelfde vers-signaal (via dezelfde helper), zodat je per
    definitie ziet of de bron vult — naast 'in gebruik'."""
    st = cockpit2._Stores(_dd(tmp_path))
    st.observations.record_daily("x", "plausible_visitors_day", 8, bron="plausible", datum=datetime.date.today().isoformat())
    h = cockpit2.render_catalog(st, csrf_token="t")
    assert "recente data" in h        # de plausible-visitors-definitie vult
    assert "geen data" in h           # niet-gevoede bron-definities (shopify/gsc/pageviews)
