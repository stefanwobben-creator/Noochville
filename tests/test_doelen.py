"""Doelen (scope 46): store, voortgang, kritieke pad, zaad, de schermen en de poorten.

Aanleiding (11 september 2026): "onder goals hangen weer projecten, we willen voortgang zien,
zou mooi zijn als je ook het kritieke pad inzichtelijk kunt maken." Ontwerp: docs/ontwerpnotitie_doelen.md.
"""
from __future__ import annotations

import pytest

from nooch_village import cockpit2, doelen
from nooch_village.views.doelen import render_goals, render_goal
from nooch_village.views.projects import render_project
from nooch_village.views.overview import render_node

ROL = "mother_earth__nooch__website_developer"
CIRKEL = "mother_earth__nooch"


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


def _proj(st, titel, status="queued", owner=ROL):
    pid = st.projects.create(owner, titel, "human", status="queued", done_when="af")
    if status == "running":
        st.projects.start(pid)
    return pid


# ── store ────────────────────────────────────────────────────────────────────

def test_store_add_update_en_validatie(tmp_path):
    dd, st = _st(tmp_path)
    d = st.doelen.add("De nieuwe website live", label="Website", deadline="2026-12-01", dod="Live op nooch.earth",
                      activiteiten=["Thema", "Content", ""])
    assert d["label"] == "Website" and d["deadline"] == "2026-12-01" and d["activiteiten"] == ["Thema", "Content"]
    assert d["status"] == "open"
    assert st.doelen.update(d["id"], deadline="niet-een-datum", status="onzin", titel="  ") is True
    d2 = st.doelen.get(d["id"])
    assert d2["deadline"] == "" and d2["status"] == "open" and d2["titel"] == "De nieuwe website live", "fail-closed: geen gok"
    assert st.doelen.update(d["id"], status="behaald", label="")
    assert st.doelen.get(d["id"])["status"] == "behaald" and st.doelen.get(d["id"])["label"] == "De"
    with pytest.raises(ValueError):
        st.doelen.add("   ")
    assert st.doelen.update("bestaat-niet", titel="x") is False
    assert cockpit2._Stores(dd).doelen.get(d["id"])["status"] == "behaald", "op schijf"


def test_zaad_is_idempotent_en_dry_run_default(tmp_path):
    dd, st = _st(tmp_path)
    assert [r["actie"] for r in doelen.zaai(st.doelen)] == ["zou aanmaken"] * 5
    assert st.doelen.all() == []
    uit = doelen.zaai(st.doelen, apply=True)
    assert [r["actie"] for r in uit] == ["aangemaakt"] * 5
    assert [d["label"] for d in st.doelen.all()] == ["Website", "STCB", "MITH", "Batch 4", "Supply chain"]
    assert [r["actie"] for r in doelen.zaai(st.doelen, apply=True)] == ["bestaat"] * 5
    assert len(st.doelen.all()) == 5


# ── project ↔ doel ───────────────────────────────────────────────────────────

def test_project_verwijst_naar_een_doel_en_blijft_van_zijn_rol(tmp_path):
    dd, st = _st(tmp_path)
    d = st.doelen.add("Rapport MITH", label="MITH", activiteiten=["Patentsearch"])
    pid = _proj(st, "Patentsearch EPO")
    assert st.projects.set_doel(pid, d["id"], "Patentsearch")
    p = st.projects.get(pid)
    assert p["doel_id"] == d["id"] and p["activiteit"] == "Patentsearch" and p["owner"] == ROL
    assert st.projects.set_doel(pid, "")                      # ontkoppelen wist ook het werkpakket
    assert st.projects.get(pid)["doel_id"] is None and st.projects.get(pid)["activiteit"] is None
    # afhankelijkheden: nooit zichzelf, geen dubbelen, alleen bestaande projecten
    q = _proj(st, "Zoekstrategie")
    assert st.projects.set_depends_on(pid, [q, q, pid, "bestaat-niet"])
    assert st.projects.get(pid)["depends_on"] == [q]


def test_voortgang_is_afgeleid_uit_af_en_checklist_ratio(tmp_path):
    dd, st = _st(tmp_path)
    d = st.doelen.add("Batch 4", label="Batch 4")
    a = _proj(st, "Tongue label")           # af
    b = _proj(st, "Doos", "running")         # checklist 1 van 2
    c = _proj(st, "Pers", "queued")          # niets meetbaars
    st.projects.set_doel(a, d["id"]); st.projects.set_doel(b, d["id"]); st.projects.set_doel(c, d["id"])
    st.projects.start(a); st.projects.complete(a)
    cl = st.projects.checklist_add(b, "tasks")["id"]
    assert st.projects.check_add(b, cl, "een") and st.projects.check_add(b, cl, "twee")
    i1 = st.projects.get(b)["checklists"][0]["items"][0]["id"]
    st.projects.check_toggle(b, cl, i1)
    v = doelen.voortgang(d, st.projects.all())
    assert v["totaal"] == 3 and v["af"] == 1 and v["open"] == 2 and v["punten"] == 1.5 and v["pct"] == 50
    assert doelen.voortgang(st.doelen.add("Leeg"), st.projects.all()) == {
        "totaal": 0, "af": 0, "open": 0, "punten": 0, "pct": 0, "per_status": {}}


# ── kritieke pad ─────────────────────────────────────────────────────────────

def test_kritieke_pad_keten_knelpunt_wachtend_vrij_en_vlaggen(tmp_path):
    dd, st = _st(tmp_path)
    d = st.doelen.add("De nieuwe website live", label="Website", deadline="2026-11-01")
    ontwerp = _proj(st, "Ontwerp")
    thema = _proj(st, "Thema bouwen")
    content = _proj(st, "Content schrijven")
    live = _proj(st, "Live zetten")
    seo = _proj(st, "SEO check")
    klaar = _proj(st, "Domein geregeld")
    for pid in (ontwerp, thema, content, live, seo, klaar):
        st.projects.set_doel(pid, d["id"])
    st.projects.start(klaar); st.projects.complete(klaar)
    st.projects.set_depends_on(thema, [ontwerp, klaar])       # klaar is af: geen schakel meer
    st.projects.set_depends_on(content, [ontwerp])
    st.projects.set_depends_on(live, [thema, content])
    st.projects.set_depends_on(seo, [live])
    st.projects.set_due(live, "2026-12-15")                    # ná de deadline van het doel
    kp = doelen.kritieke_pad(d, st.projects.all())
    assert kp["open"] == 5 and kp["met_afhankelijkheden"] == 4
    assert kp["keten"] == [ontwerp, thema, live, seo] or kp["keten"] == [ontwerp, content, live, seo]
    assert kp["knelpunt"] == {"pid": ontwerp, "wachtenden": 4}
    assert kp["vrij"] == [ontwerp]
    assert dict(kp["wachtend"])[thema] == [ontwerp], "een afgerond project is geen schakel"
    assert kp["vlaggen"] == [{"pid": live, "due": "2026-12-15", "in_keten": True}]
    assert kp["kring"] == ""


def test_kritieke_pad_zonder_afhankelijkheden_en_met_een_kring(tmp_path):
    dd, st = _st(tmp_path)
    d = st.doelen.add("STCB", label="STCB")
    a = _proj(st, "A"); b = _proj(st, "B")
    st.projects.set_doel(a, d["id"]); st.projects.set_doel(b, d["id"])
    kp = doelen.kritieke_pad(d, st.projects.all())
    assert kp["open"] == 2 and kp["met_afhankelijkheden"] == 0 and kp["keten"] and len(kp["keten"]) == 1
    assert kp["knelpunt"] is None and sorted(kp["vrij"]) == sorted([a, b])
    st.projects.set_depends_on(a, [b]); st.projects.set_depends_on(b, [a])
    kp = doelen.kritieke_pad(d, st.projects.all())
    assert kp["kring"] in (a, b) and kp["keten"] == [], "een kring is een invoerfout, geen pad"
    html = render_goal(cockpit2._Stores(dd), d["id"], csrf_token="t")
    assert "dependency loop" in html


# ── schermen ─────────────────────────────────────────────────────────────────

def test_goals_en_goal_schermen(tmp_path):
    dd, st = _st(tmp_path)
    doelen.zaai(st.doelen, apply=True)
    d = st.doelen.by_label("Website")
    a = _proj(st, "Thema bouwen"); b = _proj(st, "Live zetten"); los = _proj(st, "Iets anders")
    st.projects.set_doel(a, d["id"]); st.projects.set_doel(b, d["id"]); st.projects.set_depends_on(b, [a])
    st = cockpit2._Stores(dd)
    html = render_goals(st, csrf_token="t")
    assert html.count("🎯") == 5 and "progress class='pbar wide'" in html and "goal_add" in html
    assert "style=" not in html
    html = render_goal(st, d["id"], csrf_token="t")
    assert "De nieuwe website live" in html and "card doel" in html
    assert "Longest chain" in html and "Bottleneck" in html and "Thema bouwen" in html
    assert "Link projects (1 open projects without a goal)" in html and "Iets anders" in html
    assert "goal_edit" in html and "board filtered on this goal" in html and f"goal={d['id']}" in html
    assert "style=" not in html
    assert "does not exist" in render_goal(st, "nope")
    # zonder csrf (alleen-lezen): geen formulieren
    ro = render_goal(st, d["id"])
    assert "goal_edit" not in ro and "goal_link" not in ro


def test_bord_pills_kop_en_kaartlabel(tmp_path):
    dd, st = _st(tmp_path)
    doelen.zaai(st.doelen, apply=True)
    d = st.doelen.by_label("MITH")
    a = _proj(st, "Patentsearch EPO"); b = _proj(st, "Los project")
    st.projects.set_doel(a, d["id"])
    st = cockpit2._Stores(dd)
    alles = render_node(st, CIRKEL, "projects", csrf_token="t")
    assert "Goal:" in alles and "cl-filter pill on" in alles and alles.count("cl-filter pill") == 6
    assert "chip doel" in alles and "Patentsearch EPO" in alles and "Los project" in alles
    assert "card doel" not in alles, "zonder filter geen doelkop"
    mith = render_node(st, CIRKEL, "projects", csrf_token="t", goal=d["id"])
    assert "card doel" in mith and "🎯 Rapport MITH" in mith and "Patentsearch EPO" in mith
    assert "Los project" not in mith, "gefilterd"
    assert f"goal={d['id']}" in mith, "de group-by-links dragen het filter mee"
    onzin = render_node(st, CIRKEL, "projects", csrf_token="t", goal="nope")
    assert "Los project" in onzin, "onbekend doel = geen filter"
    rol = render_node(st, ROL, "projects", csrf_token="t", goal=d["id"])
    assert "card doel" in rol and "Los project" not in rol


def test_projectdetail_rail_goal_en_depends_on(tmp_path):
    dd, st = _st(tmp_path)
    d = st.doelen.add("Rapport MITH", label="MITH", activiteiten=["Patentsearch", "Marktverkenning"])
    a = _proj(st, "Zoekstrategie"); b = _proj(st, "Search EPO"); c = _proj(st, "Samenvatten")
    for pid in (a, b, c):
        st.projects.set_doel(pid, d["id"])
    st.projects.set_doel(b, d["id"], "Patentsearch")
    st.projects.set_depends_on(b, [a])
    st = cockpit2._Stores(dd)
    h = render_project(st, b, csrf_token="t")
    assert "proj_goal" in h and "title='Rapport MITH' selected>MITH</option>" in h
    assert "Work package" in h and "Patentsearch" in h and "Marktverkenning" in h
    assert "Depends on" in h and "Zoekstrategie" in h and "proj_depends" in h
    assert "+ waits on…" in h and "Samenvatten" in h, "kandidaten: open projecten van hetzelfde doel"
    assert "Search EPO</option>" not in h, "nooit zichzelf"
    los = _proj(st, "Zonder doel")
    h2 = render_project(cockpit2._Stores(dd), los, csrf_token="t")
    assert "link to a goal first" in h2 and "Work package" not in h2
    ro = render_project(st, b)
    assert "proj_goal" not in ro and "MITH" in ro


# ── dispatch en poorten ──────────────────────────────────────────────────────

def test_dispatch_goal_add_edit_link_en_proj_goal(tmp_path):
    dd, st = _st(tmp_path)
    nxt, msg = cockpit2.dispatch(dd, "goal_add", {"titel": ["Supply chain zelf in beheer"], "label": ["Supply chain"],
                                                  "deadline": ["2027-03-01"], "dod": ["Alles in eigen hand"],
                                                  "activiteiten": ["Fabriek\nTransport\n"], "next": ["/goals"]}, "guest")
    assert msg == "🎯 goal created" and nxt.startswith("/goal?id=")
    d = cockpit2._Stores(dd).doelen.all()[0]
    assert d["activiteiten"] == ["Fabriek", "Transport"] and d["deadline"] == "2027-03-01"
    a = _proj(st, "Transport regelen"); b = _proj(st, "Fabriek kiezen")
    _, msg = cockpit2.dispatch(dd, "proj_goal", {"pid": [a], "doel_id": [d["id"]], "activiteit": ["Transport"], "next": ["/"]}, "guest")
    assert msg == "🎯 linked to goal"
    _, msg = cockpit2.dispatch(dd, "proj_goal", {"pid": [a], "doel_id": ["nope"], "next": ["/"]}, "guest")
    assert msg == "✗ goal not found"
    _, msg = cockpit2.dispatch(dd, "goal_link", {"id": [d["id"]], "pids": [b], "next": ["/"]}, "guest")
    assert msg == "🎯 1 project(s) linked"
    _, msg = cockpit2.dispatch(dd, "proj_depends", {"pid": [a], "add": [b], "next": ["/"]}, "guest")
    assert msg == "✓ dependency added"
    st = cockpit2._Stores(dd)
    assert st.projects.get(a)["doel_id"] == d["id"] and st.projects.get(a)["activiteit"] == "Transport"
    assert st.projects.get(b)["doel_id"] == d["id"] and st.projects.get(a)["depends_on"] == [b]
    _, msg = cockpit2.dispatch(dd, "proj_depends", {"pid": [a], "remove": [b], "next": ["/"]}, "guest")
    assert msg == "✓ dependency removed" and cockpit2._Stores(dd).projects.get(a)["depends_on"] == []
    _, msg = cockpit2.dispatch(dd, "goal_edit", {"id": [d["id"]], "status": ["behaald"], "titel": ["Supply chain in eigen beheer"], "next": ["/"]}, "guest")
    assert msg == "✓ goal saved"
    d2 = cockpit2._Stores(dd).doelen.get(d["id"])
    assert d2["status"] == "behaald" and d2["titel"] == "Supply chain in eigen beheer" and d2["activiteiten"] == ["Fabriek", "Transport"]
    _, msg = cockpit2.dispatch(dd, "goal_add", {"titel": [""], "next": ["/goals"]}, "guest")
    assert msg.startswith("✗")


def test_poorten_anchor_lead_voor_doelen_en_rol_voor_de_koppeling(tmp_path):
    """Doelen zijn intentielaag: alleen de anchor-lead. De koppeling is rol-werk: rolvervuller of
    Circle Lead. Een ingelogde onbekende wordt overal geweigerd (fail-closed)."""
    dd, st = _st(tmp_path)
    d = st.doelen.add("MITH", label="MITH")
    a = _proj(st, "Patentsearch")
    for actie, form in (("goal_add", {"titel": ["x"]}), ("goal_edit", {"id": [d["id"]], "titel": ["y"]}),
                        ("goal_link", {"id": [d["id"]], "pids": [a]}),
                        ("proj_goal", {"pid": [a], "doel_id": [d["id"]]}), ("proj_depends", {"pid": [a], "add": [a]})):
        _, msg = cockpit2.dispatch(dd, actie, {**form, "next": ["/"]}, "onbekend@x.nl")
        assert msg.startswith("No access"), (actie, msg)
    assert cockpit2._Stores(dd).doelen.get(d["id"])["titel"] == "MITH"
    assert cockpit2._Stores(dd).projects.get(a)["doel_id"] is None


def test_route_en_navigatie():
    import inspect
    src = inspect.getsource(cockpit2)
    assert 'path == "/goals"' in src and 'path == "/goal"' in src
    from nooch_village.cockpit2_util import _NAV_ITEMS
    assert ("/goals", "Goals") in _NAV_ITEMS
