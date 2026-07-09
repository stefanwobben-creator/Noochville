"""Projectdetails-zijbalk: impact als dropdown, effort numeriek (uren, met legacy-enum-conversie).

- Missie/Business: dropdown (proj_setimpact ongewijzigd) — waarde opslaan + voorselectie.
- Effort: proj_seteffort → {"hours": N}; uren/dagen-toggle; legacy enum (1u/1d/2d/1w) rendert in de
  nieuwe control via lazy conversie; leeg/ontbrekend → nette default, geen crash.
"""
from __future__ import annotations

from nooch_village import cockpit2
from nooch_village.views import projects as P
from nooch_village.views.projects import _effort_hours

ROLE = "mother_earth__nooch__website_developer"


def _setup(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    pid = cockpit2._Stores(dd).projects.create(ROLE, "T", "human")
    return dd, pid


def _get(dd, pid):
    return cockpit2._Stores(dd).projects.get(pid)


def _rw(dd, pid):
    return P.render_project(cockpit2._Stores(dd), pid, csrf_token="TOK")


# ── impact-dropdowns: opslaan + teruglezen ───────────────────────────────────────
def test_missie_business_dropdown_opslaan_en_teruglezen(tmp_path):
    dd, pid = _setup(tmp_path)
    cockpit2.dispatch(dd, "proj_setimpact", {"pid": [pid], "kind": ["missie"], "value": ["versterkt"], "next": ["/"]}, "guest")
    cockpit2.dispatch(dd, "proj_setimpact", {"pid": [pid], "kind": ["business"], "value": ["laag"], "next": ["/"]}, "guest")
    p = _get(dd, pid)
    assert p["missie_impact"] == "versterkt" and p["business_impact"] == "laag"
    frag = _rw(dd, pid)
    assert "value='versterkt' selected" in frag and "value='laag' selected" in frag


# ── effort: numeriek + uren/dagen-toggle ─────────────────────────────────────────
def test_effort_uren_opslaan_en_teruglezen(tmp_path):
    dd, pid = _setup(tmp_path)
    cockpit2.dispatch(dd, "proj_seteffort", {"pid": [pid], "number": ["3"], "unit": ["uren"], "next": ["/"]}, "guest")
    assert _get(dd, pid)["effort"] == {"hours": 3}
    frag = _rw(dd, pid)
    assert "name='number' value='3'" in frag and "value='uren' selected" in frag


def test_effort_dagen_wordt_uren(tmp_path):
    dd, pid = _setup(tmp_path)
    cockpit2.dispatch(dd, "proj_seteffort", {"pid": [pid], "number": ["2"], "unit": ["dagen"], "next": ["/"]}, "guest")
    assert _get(dd, pid)["effort"] == {"hours": 16}          # 2 dagen × 8u
    frag = _rw(dd, pid)
    assert "name='number' value='2'" in frag and "value='dagen' selected" in frag   # 16u = veelvoud van 8 → dagen


def test_effort_leegmaken(tmp_path):
    dd, pid = _setup(tmp_path)
    cockpit2.dispatch(dd, "proj_seteffort", {"pid": [pid], "number": ["5"], "unit": ["uren"], "next": ["/"]}, "guest")
    cockpit2.dispatch(dd, "proj_seteffort", {"pid": [pid], "number": [""], "unit": ["uren"], "next": ["/"]}, "guest")
    assert _get(dd, pid)["effort"] == ""


def test_effort_ongeldige_waarde_wijzigt_niets(tmp_path):
    dd, pid = _setup(tmp_path)
    _, msg = cockpit2.dispatch(dd, "proj_seteffort", {"pid": [pid], "number": ["abc"], "unit": ["uren"], "next": ["/"]}, "guest")
    assert "ongeldig" in msg.lower() and _get(dd, pid)["effort"] == ""


# ── legacy enum rendert in de nieuwe control (lazy conversie) ─────────────────────
def test_legacy_effort_enum_rendert(tmp_path):
    dd, pid = _setup(tmp_path)
    st = cockpit2._Stores(dd)
    st.projects.edit(pid, effort="1d")                       # oude enum-waarde direct opgeslagen
    frag = _rw(dd, pid)
    assert "name='number' value='1'" in frag and "value='dagen' selected" in frag   # 1d = 8u = 1 dag


def test_effort_hours_conversie_unit():
    assert _effort_hours({"hours": 5}) == 5
    assert _effort_hours("1u") == 1 and _effort_hours("1d") == 8
    assert _effort_hours("2d") == 16 and _effort_hours("1w") == 40
    assert _effort_hours("") is None and _effort_hours(None) is None
    assert _effort_hours({"hours": 0}) is None and _effort_hours("banaan") is None


# ── lege/ontbrekende velden → nette default, geen crash ──────────────────────────
def test_leeg_project_rendert_zonder_crash(tmp_path):
    dd, pid = _setup(tmp_path)                                # geen impact/effort gezet
    frag = _rw(dd, pid)
    assert "Effort" in frag and "name='number' value=''" in frag   # leeg getal, default uren
    ro = P.render_project(cockpit2._Stores(dd), pid, csrf_token="")
    assert "—" in ro                                          # read-only default, geen crash
