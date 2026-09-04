"""Eén huis per eigenschap op de projectkaart.

De herindeling zette de eigenschappen in de chips-rij en liet de rechterkolom over voor
structuur + acties. Status stond daarvóór in beide zones: als etiket in de chips (niet
bewerkbaar) en als trigger van het ⋯-menu in de rail (wél bewerkbaar) — lezen en veranderen
op verschillende plekken. Deze test bevriest de scheiding, want een dubbeling sluipt terug
zodra iemand "even" een veld bijzet waar hij toevallig aan het werk is.
"""
from __future__ import annotations

from nooch_village import cockpit2
from nooch_village.views import projects as P

ROLE = "mother_earth__nooch__website_developer"

# actie-naam -> in welke zone hij thuishoort ("chips" of "rail")
_HUIS = {
    "proj_setimpact": "chips", "proj_seteffort": "chips", "proj_status": "chips",
    "proj_done": "chips", "proj_settrekker": "chips",
    "proj_setdue": "rail",
}
# label -> zone
_LABELS = {"Status": "chips", "Effort": "chips", "Impact": "chips", "Assignee": "chips",
           "Deadline": "rail", "Created": "rail", "Role": "rail", "Visible": "rail"}


def _kaart(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    pid = st.projects.create(ROLE, "Hemp canvas, tweede leverancier", "human",
                             status="queued", missie_impact="versterkt", business_impact="hoog")
    st.projects.start(pid)
    st.projects.set_due(pid, "2026-10-01")
    cockpit2.dispatch(dd, "proj_seteffort", {"pid": [pid], "hours": ["16"], "next": ["/"]},
                      username="guest")
    html = P.render_project(cockpit2._Stores(dd), pid, csrf_token="TOK")
    return (html[html.index("pchips"):html.index("pkaart-body")],
            html[html.index("pkaart-rail"):])


def test_geen_eigenschap_in_beide_zones(tmp_path):
    chips, rail = _kaart(tmp_path)
    dubbel = [a for a in _HUIS if f"value='{a}'" in chips and f"value='{a}'" in rail]
    assert not dubbel, f"eigenschap in twee zones: {dubbel}"


def test_elke_eigenschap_staat_in_zijn_eigen_huis(tmp_path):
    chips, rail = _kaart(tmp_path)
    zones = {"chips": chips, "rail": rail}
    for actie, huis in _HUIS.items():
        assert f"value='{actie}'" in zones[huis], f"{actie} ontbreekt in {huis}"
    for label, huis in _LABELS.items():
        ander = "rail" if huis == "chips" else "chips"
        assert f">{label}<" in zones[huis], f"label {label} ontbreekt in {huis}"
        assert f">{label}<" not in zones[ander], f"label {label} staat ook in {ander}"


def test_status_is_bewerkbaar_waar_hij_gelezen_wordt(tmp_path):
    """De kern van de bug: de zichtbare Status-chip loog dat er niets te kiezen viel."""
    chips, rail = _kaart(tmp_path)
    assert "pchip-status" in chips and "proj_status" in chips
    assert "statustrigger" not in rail and "proj_status" not in rail


def test_rail_menu_houdt_alleen_acties(tmp_path):
    chips, rail = _kaart(tmp_path)
    assert "proj_archive" in rail and "proj_delete" in rail
    assert "proj_status" not in rail and "proj_done" not in rail
