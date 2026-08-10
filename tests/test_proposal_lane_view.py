"""De review-baan voor voorstellen — sinds 11 aug 2026 in de Founder Flow, niet meer op het bord.

Adjudicatie hoort op één plek. Verspreid over het projectenbord (rol-tab én cirkel-tab) moest je
per rol en per cirkel langs om te zien wat op je oordeel wachtte, en zag je nooit het totaal.

Wat hetzelfde bleef: de dispatch-takken (`proj_proposal_accept`/`reject`), hun poort, en het
onthouden van een afwijzing. Alleen de rendering verhuisde."""
from __future__ import annotations

from nooch_village import cockpit2
from nooch_village.project_proposals import overlay_for
from nooch_village.views import projects as P
from nooch_village.views.founder_flow import render_founder_flow

ROLE = "mother_earth__nooch__website_developer"


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


def _voorstel(st, titel="Gap in EU labelling rules mapped", origin="proposal:radar"):
    return st.projects.create(ROLE, titel, "role", status="proposed", origin=origin)


def test_guard_geen_voorstellen_blok_meer_op_de_projecten_tab(tmp_path):
    """DE guard. Beide takken: de rol-tab én de cirkel-tab tonen alleen nog echte projecten."""
    dd, st = _st(tmp_path)
    _voorstel(st)
    st.projects.create(ROLE, "Gewoon bordwerk", "human", status="queued")
    for node in (ROLE, "mother_earth__nooch"):
        html = P._projects_tab_html(cockpit2._Stores(dd), st.records.get(node), "TOK")
        assert "awaiting your judgement" not in html, node
        assert "proj_proposal_accept" not in html and "proj_proposal_reject" not in html, node
        assert "Gap in EU labelling rules" not in html, node     # het voorstel zelf ook niet
    # ...en het echte bordwerk staat er nog wél
    rol_html = P._projects_tab_html(cockpit2._Stores(dd), st.records.get(ROLE), "TOK")
    assert "Gewoon bordwerk" in rol_html and "Projects (1)" in rol_html
    kolom_statussen = {s for _l, _k, sts in P._PROJ_COLS for s in sts}
    assert "proposed" not in kolom_statussen                     # nooit in een kanban-kolom


def test_guard_voorstellen_staan_in_de_founder_flow(tmp_path):
    """DE tweede guard: de functie is verhuisd, niet verdwenen."""
    dd, st = _st(tmp_path)
    _voorstel(st)
    html = render_founder_flow(cockpit2._Stores(dd), dd, csrf_token="TOK", username="guest")
    assert "Proposals — awaiting your judgement (1)" in html
    assert "proj_proposal_accept" in html and "proj_proposal_reject" in html
    assert "approved signal" in html                             # herkomst reist mee
    assert "Gap in EU labelling rules mapped" in html


def test_lege_lijst_zegt_dat_er_niets_wacht(tmp_path):
    """Anders dan op het bord (waar een leeg blok onzichtbaar was) hoort de flow te zeggen dat er
    niets ligt — een sectie die verdwijnt laat je twijfelen of je iets mist."""
    dd, st = _st(tmp_path)
    html = render_founder_flow(cockpit2._Stores(dd), dd, csrf_token="TOK", username="guest")
    assert "Nothing awaiting your judgement" in html
    assert "proj_proposal_accept" not in html


def test_read_only_toont_geen_knoppen(tmp_path):
    dd, st = _st(tmp_path)
    _voorstel(st)
    html = render_founder_flow(cockpit2._Stores(dd), dd, csrf_token="", username="guest")
    assert "awaiting your judgement" in html and "proj_proposal_accept" not in html


def test_knop_belooft_niets_wat_de_dispatch_weigert(tmp_path):
    """Een ingelogde die deze rol niet vervult en geen Circle Lead is, mag niet beslissen — dan
    hoort hij ook geen knop te zien. Zelfde principe als de claims-poort."""
    dd, st = _st(tmp_path)
    _voorstel(st)
    html = render_founder_flow(cockpit2._Stores(dd), dd, csrf_token="TOK",
                               username="niemand@nooch.earth")
    assert "awaiting your judgement" in html                      # wel zichtbaar
    assert "proj_proposal_accept" not in html                     # maar geen knop
    assert "Only the role filler or Circle Lead" in html


def test_guard_geaccepteerd_voorstel_landt_op_het_bord(tmp_path):
    """DE derde guard: accepteren vanuit de flow zet het project echt op het bord van de rol —
    in TOEKOMST, waar de gewone flow het oppakt."""
    dd, st = _st(tmp_path)
    pid = _voorstel(st)
    cockpit2.dispatch(dd, "proj_proposal_accept", {"pid": [pid], "next": ["/founder"]},
                      username="guest")
    st2 = cockpit2._Stores(dd)
    assert st2.projects.get(pid)["status"] == "future"
    assert st2.projects.get(pid)["owner"] == ROLE
    # ...en het staat nu wél op de projecten-tab van die rol, want het is echt werk geworden
    html = P._projects_tab_html(st2, st2.records.get(ROLE), "TOK")
    assert "Gap in EU labelling rules mapped" in html


def test_accepteren_via_dispatch(tmp_path):
    dd, st = _st(tmp_path)
    pid = _voorstel(st)

    _nxt, msg = cockpit2.dispatch(dd, "proj_proposal_accept",
                                  {"pid": [pid], "next": ["/"]}, username="guest")

    assert "accepted" in msg
    assert cockpit2._Stores(dd).projects.get(pid)["status"] == "future"


def test_afwijzen_via_dispatch_en_het_komt_niet_terug(tmp_path):
    dd, st = _st(tmp_path)
    ov = overlay_for(dd)
    pid = _voorstel(st)
    ov.remember("radar:x", source="radar", ref="x", pid=pid, title="t", owner=ROLE)

    _nxt, msg = cockpit2.dispatch(dd, "proj_proposal_reject",
                                  {"pid": [pid], "next": ["/"]}, username="guest")

    assert "rejected" in msg
    assert cockpit2._Stores(dd).projects.get(pid) is None
    assert overlay_for(dd).get("radar:x")["status"] == "rejected"   # onthouden, dus geen herhaling


def test_dispatch_raakt_een_gewoon_project_niet(tmp_path):
    """De twee acties werken uitsluitend op een voorstel — nooit op werk dat al op het bord staat."""
    dd, st = _st(tmp_path)
    pid = st.projects.create(ROLE, "Gewoon bordwerk", "human", status="queued")

    cockpit2.dispatch(dd, "proj_proposal_reject", {"pid": [pid], "next": ["/"]}, username="guest")

    assert cockpit2._Stores(dd).projects.get(pid)["status"] == "queued"
