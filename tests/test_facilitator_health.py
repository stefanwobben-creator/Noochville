"""Facilitator: werkoverleg-gezondheid als metric-bron + accountability + maandelijkse checklist."""
from __future__ import annotations

from nooch_village import cockpit2

C = "mother_earth__nooch"
FAC = "mother_earth__nooch__facilitator"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def test_accountability_en_maandchecklist(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    fac = st.records.get(FAC)
    assert cockpit2._FAC_ACC in fac.definition.accountabilities
    cl = st.checklists.for_node(FAC)
    assert any(i["description"] == cockpit2._FAC_CHECK and i["cadence"] == "maand" for i in cl)
    # idempotent: nog een keer draaien voegt niets dubbel toe
    cockpit2._ensure_facilitator_health(cockpit2._Stores(dd))
    st2 = cockpit2._Stores(dd)
    assert st2.records.get(FAC).definition.accountabilities.count(cockpit2._FAC_ACC) == 1
    assert len([i for i in st2.checklists.for_node(FAC) if i["description"] == cockpit2._FAC_CHECK]) == 1


def test_werkoverleg_bron_in_wizard(tmp_path):
    dd = _dd(tmp_path)
    # de Werkoverleg-bron is beschikbaar op de facilitator (rol onder de cirkel)
    page = cockpit2.render_kpi_composer(cockpit2._Stores(dd), FAC, csrf_token="t")
    # deelopdracht 3: werk staat één keer per metric (geconsolideerde def), niet als 3 dim-combos
    assert "Tevredenheid werkoverleg" in page and "Behandelde spanningen" in page
    assert "· gemiddeld per overleg" not in page and "Spanningen verwerkt · totaal" not in page


def _run_meeting(dd, person_id, satisfaction, resolve=("project", "info")):
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    for i, otype in enumerate(resolve):
        cockpit2.dispatch(dd, "wo_ag_add", {"circle": [C], "naam": [f"Spanning {i}"], "next": ["/"]}, username="guest")
    st = cockpit2._Stores(dd)
    for it in st.werk.agenda(C):
        idx = int(it["title"].split()[-1])
        otype = resolve[idx]
        extra = {"owner": [FAC], "detail": ["x"]} if otype == "project" else {"detail": ["x"]}
        cockpit2.dispatch(dd, "wo_ag_resolve", {"circle": [C], "iid": [it["id"]], "otype": [otype], **extra, "next": ["/"]}, username="guest")
    cockpit2.dispatch(dd, "wo_checkout", {"circle": [C], "pid": [person_id], "score": [str(satisfaction)], "next": ["/"]}, username="guest")
    cockpit2.dispatch(dd, "wo_close", {"circle": [C], "next": ["/"]}, username="guest")


def test_werkoverleg_metrics_aggregeren_over_log(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    p = st.people.all()[0]
    st.assign.assign(FAC, "person", p.id)
    _run_meeting(dd, p.id, 8, resolve=("project", "info"))
    _run_meeting(dd, p.id, 6, resolve=("project", "project"))
    st = cockpit2._Stores(dd)
    assert len(st.werk.log(C)) == 2
    # tevredenheid gemiddeld over 2 overleggen = (8+6)/2 = 7
    r = cockpit2._werk_fetch(st, C, "tevredenheid", "gemiddeld", None)
    assert r["value"] == 7.0
    # projecten totaal: meeting1 = 1, meeting2 = 2 -> 3
    r2 = cockpit2._werk_fetch(st, C, "projecten", "totaal", None)
    assert r2["value"] == 3
    # spanningen (behandeld) totaal = 2 + 2 = 4
    r3 = cockpit2._werk_fetch(st, C, "spanningen", "totaal", None)
    assert r3["value"] == 4
    # over tijd -> reeks van 2 punten
    r4 = cockpit2._werk_fetch(st, C, "projecten", "over_tijd", None)
    assert r4["kind"] == "series" and len(r4["points"]) == 2
