"""Smoke-subset (`@pytest.mark.smoke`): een representatieve selectie kern-paden per module —
stores, render van de hoofdviews, en dispatch happy-paths. GEEN volledige dekking.

Bedoeld voor de tussentijdse iteraties: `pytest -m smoke` draait in enkele seconden. De VOLLEDIGE
suite (`./venv/bin/python -m pytest tests/`) blijft de verplichte poort vóór elke commit
(WORKING_AGREEMENTS.md) — de smoke-subset vervangt die niet.
"""
from __future__ import annotations

import pytest

from nooch_village import cockpit2
from nooch_village.views import (overview, catalog, metrics,
                                 werkoverleg, roloverleg)

pytestmark = pytest.mark.smoke   # markeert alle tests in dit bestand als smoke

CIRCLE = "mother_earth__nooch"
ROLE = "mother_earth__circle_lead"


@pytest.fixture
def dd(tmp_path):
    d = str(tmp_path / "poc")
    cockpit2._bootstrap(d)
    return d


def test_smoke_stores(dd):
    """Kern-datalaag: records, catalogus-definities, dag-observaties, backlog, werkoverleg."""
    st = cockpit2._Stores(dd)
    assert st.records.get(CIRCLE) is not None                     # governance
    assert len(st.defs.all()) > 0                                 # catalogus geseed
    st.observations.record_daily("website_watcher", "visitors_day", 42,
                                 bron="plausible", datum="2026-07-05")
    rows = st.observations.daily_series("visitors_day", bron="plausible")
    assert rows and rows[-1]["value"] == 42                       # observatie round-trip
    assert isinstance(st.backlog.all(), list)
    assert st.werk.get(CIRCLE) in (None,) or isinstance(st.werk.get(CIRCLE), dict)


def test_smoke_render_hoofdviews(dd):
    """De hoofdviews renderen zonder crash tot volwaardige HTML (per module één kern-render)."""
    st = cockpit2._Stores(dd)
    rec = st.records.get(CIRCLE)
    volledige_paginas = [
        overview.render_node(st, CIRCLE, "overview"),
        overview.render_node(st, CIRCLE, "metrics"),
        catalog.render_catalog(st),
        catalog.render_catalog(st, koppel="plausible", curator=True),   # samengevoegd koppel-scherm
        metrics.render_kpi_composer(st, CIRCLE),
        werkoverleg.render_werkoverleg(st, CIRCLE),
        roloverleg.render_roloverleg2(st, CIRCLE),
    ]
    for html in volledige_paginas:
        assert isinstance(html, str) and "<!doctype" in html.lower() and len(html) > 200
    # metrics-tab is een fragment (geen volledige pagina) → aparte, lichte assertie
    assert len(metrics._metrics_tab_html(st, rec)) > 50


def test_smoke_dispatch_happy_paths(dd):
    """De ACTIONS-registry routeert en muteert: proj_add + backlog_add + onbekende actie (no-op)."""
    # onbekende actie → fall-through no-op (registry-contract)
    assert cockpit2.dispatch(dd, "__bestaat_niet__", {"next": ["/"]}, "guest") == ("/", "")

    st = cockpit2._Stores(dd)
    voor_proj = len(st.projects.all())
    cockpit2.dispatch(dd, "proj_add",
                      {"owner": [ROLE], "scope": ["Smoke-project"], "col": ["nu"], "next": ["/"]},
                      "guest")
    assert len(cockpit2._Stores(dd).projects.all()) == voor_proj + 1

    voor_bl = len(st.backlog.all())
    cockpit2.dispatch(dd, "backlog_add",
                      {"titel": ["Smoke-item"], "beschrijving": ["x"], "type": ["taak"],
                       "domein": ["algemeen"], "next": ["/"]}, "guest")
    assert len(cockpit2._Stores(dd).backlog.all()) == voor_bl + 1
