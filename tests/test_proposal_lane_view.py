"""De review-baan in de cockpit: voorstellen zichtbaar buiten het bord, met accepteren/afwijzen
als de twee mens-knoppen. Thread-vrij, via render + dispatch (zelfde patroon als de drafts-baan)."""
from __future__ import annotations

from nooch_village import cockpit2
from nooch_village.project_proposals import overlay_for
from nooch_village.views import projects as P

ROLE = "mother_earth__nooch__website_developer"


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


def _voorstel(st, titel="Gap in EU labelling rules mapped", origin="proposal:radar"):
    return st.projects.create(ROLE, titel, "role", status="proposed", origin=origin)


def test_voorstel_staat_in_de_review_baan_en_niet_op_het_bord(tmp_path):
    dd, st = _st(tmp_path)
    _voorstel(st)
    st.projects.create(ROLE, "Gewoon bordwerk", "human", status="queued")
    rec = st.records.get(ROLE)

    html = P._projects_tab_html(cockpit2._Stores(dd), rec, "TOK")

    assert "Proposals — awaiting your judgement (1)" in html
    assert "proj_proposal_accept" in html and "proj_proposal_reject" in html
    assert "approved signal" in html                       # herkomst zichtbaar in de baan
    assert "Projects (1)" in html                          # telling zonder het voorstel: eerlijk
    # het voorstel zit in geen enkele kanban-kolom
    kolom_statussen = {s for _l, _k, sts in P._PROJ_COLS for s in sts}
    assert "proposed" not in kolom_statussen


def test_lege_baan_is_onzichtbaar(tmp_path):
    dd, st = _st(tmp_path)
    st.projects.create(ROLE, "Gewoon bordwerk", "human", status="queued")
    html = P._projects_tab_html(cockpit2._Stores(dd), st.records.get(ROLE), "TOK")
    assert "Proposals" not in html


def test_read_only_toont_geen_knoppen(tmp_path):
    dd, st = _st(tmp_path)
    _voorstel(st)
    html = P._projects_tab_html(cockpit2._Stores(dd), st.records.get(ROLE), "")
    assert "Proposals" in html and "proj_proposal_accept" not in html


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
