"""Signals-lijst: RadarStore.all_approved aggregeert goedgekeurde signalen over álle rollen; de
/signals-pagina rendert ze read-only (geen nieuwe opslag, raakt de radar-flow niet)."""
from __future__ import annotations

from nooch_village import cockpit2
from nooch_village.radar_store import RadarStore
from nooch_village.views.signals import render_signals


def test_all_approved_aggregates_over_roles(tmp_path):
    r = RadarStore(str(tmp_path / "radar.json"))
    a = r.add(role="role_a", feed="Competitor", kind="concurrent", content="Veja")
    b = r.add(role="role_b", feed="Legal", kind="kaart", content="PFAS rules")
    r.add(role="role_a", feed="Competitor", kind="kaart", content="Nog in de wachtrij")  # blijft 'wacht'
    r.set_status(a, "goedgekeurd")
    r.set_status(b, "goedgekeurd")
    appr = r.all_approved()
    assert {it["id"] for it in appr} == {a, b}                 # alleen goedgekeurd, over beide rollen
    assert all(it["status"] == "goedgekeurd" for it in appr)


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def test_render_signals_lists_approved(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    rid = st.radar.add(role="concurrent_scout", feed="Competitor Watch", kind="concurrent",
                       content="Vivobarefoot Run Club", rationale="concurrent-zet",
                       source="vivobarefoot.com", link="https://vivobarefoot.com/x",
                       published_at="2026-05-11T00:00:00Z")
    st.radar.set_status(rid, "goedgekeurd")
    html = render_signals(st)
    assert "Signalen" in html and "Vivobarefoot Run Club" in html
    assert "Competitor Watch" in html and "/signals" in html   # feed-chip + navlink
    assert "2026-05-11" in html                                # datum-badge


def test_render_signals_empty(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    assert "Nog geen goedgekeurde signalen" in render_signals(st)
