"""Scope 48 — de status-historie van een project (12 september 2026).

Stefan: "houden we bij wanneer een project is aangemaakt, wanneer die naar actief gaat en wanneer
completed? Daarmee kunnen we per doel straks een heel admin uitrollen." Gemeten vóór deze scope: nee,
alleen `created_at` en `updated_at`, en die laatste overschrijft elke aanraking. Nu: één setter
(`_zet_status`) voor elke overgang, één regel per overgang in `status_log`, en de datums afgeleid
(`tijdlijn`, `dagen_per_status`), nooit opgeslagen."""
from __future__ import annotations

import inspect
import time

from nooch_village import projects as P
from nooch_village.projects import ProjectLedger


def _pl(tmp_path) -> ProjectLedger:
    return ProjectLedger(str(tmp_path / "projects.json"))


def test_de_geboorte_is_de_eerste_regel(tmp_path):
    pl = _pl(tmp_path)
    pid = pl.create("rol", "Iets", "human", status="future")
    log = pl.get(pid)["status_log"]
    assert len(log) == 1 and log[0]["van"] is None and log[0]["naar"] == "future"
    assert abs(log[0]["at"] - pl.get(pid)["created_at"]) < 1e-6      # zelfde moment, geen tweede klok


def test_elke_overgang_laat_een_regel_achter_met_wie(tmp_path):
    pl = _pl(tmp_path)
    pid = pl.create("rol", "Iets", "human")
    pl.start(pid, "stefan")
    pl.block(pid, "—", "stefan")
    pl.unblock(pid, "lotte")
    pl.to_future(pid, "stefan")
    pl.start(pid, "stefan")
    pl.complete(pid, "af", door="stefan")
    log = pl.get(pid)["status_log"]
    assert [e["naar"] for e in log] == ["future", "running", "blocked", "running", "future", "running", "done"]
    assert [e["van"] for e in log][1:] == ["future", "running", "blocked", "running", "future", "running"]
    assert log[3]["door"] == "lotte" and log[-1]["door"] == "stefan"
    assert all(e["at"] > 0 for e in log)
    # heropenen is ook een overgang
    pl.reopen(pid, "stefan")
    assert pl.get(pid)["status_log"][-1] == {**pl.get(pid)["status_log"][-1], "van": "done", "naar": "running"}


def test_dezelfde_status_is_geen_gebeurtenis(tmp_path):
    """Twee keer 'start' op een lopend project schrijft één regel, niet twee: een no-op is geen
    gebeurtenis, anders telt een rapport dubbele starts."""
    pl = _pl(tmp_path)
    pid = pl.create("rol", "Iets", "human")
    pl.start(pid); pl.start(pid)
    assert [e["naar"] for e in pl.get(pid)["status_log"]] == ["future", "running"]


def test_ook_de_machine_overgangen_lopen_door_de_setter(tmp_path):
    """De review-parkeerplaats, de scheduler (wait_for), approve en accept_proposal: allemaal via
    `_zet_status`. De bron bewaakt dat er geen tweede schrijfpad voor `status` bestaat. De rol die
    werkt (record_progress) verandert de status NIET meer: werk gebeurt aan een project dat een mens
    actief maakte (scope 49)."""
    bron = inspect.getsource(P.ProjectLedger)
    assert bron.count('p["status"] = ') == 0, "een status-schrijf buiten _zet_status om"
    pl = _pl(tmp_path)
    pid = pl.create("rol", "Iets", "human", status="running")
    pl.record_progress(pid, "gedaan")                      # werk laat de status met rust
    assert [e["naar"] for e in pl.get(pid)["status_log"]] == ["running"]
    pl.mark_awaiting_review(pid)
    assert pl.get(pid)["status_log"][-1] == {**pl.get(pid)["status_log"][-1], "naar": "blocked", "door": "review"}
    d = pl.create("rol", "Concept", "human", status="draft")
    pl.approve(d, "stefan")
    assert pl.get(d)["status_log"][-1]["naar"] == "future"        # goedgekeurd = slapend, tot de sleep
    v = pl.create("rol", "Voorstel", "role", status="proposed")
    pl.accept_proposal(v, person="p1")
    assert pl.get(v)["status_log"][-1] == {**pl.get(v)["status_log"][-1], "naar": "future", "door": "p1"}


def test_de_tijdlijn_is_afgeleid(tmp_path):
    pl = _pl(tmp_path)
    pid = pl.create("rol", "Iets", "human", status="future")
    p = pl.get(pid)
    assert P.tijdlijn(p) == {"aangemaakt": p["created_at"], "gestart": None, "afgerond": None, "bron": "log"}
    pl.start(pid); t_start = pl.get(pid)["status_log"][-1]["at"]
    pl.block(pid, "—"); pl.unblock(pid)                   # een tweede 'running' verschuift de start niet
    pl.complete(pid, "af"); t_af = pl.get(pid)["status_log"][-1]["at"]
    tl = P.tijdlijn(pl.get(pid))
    assert tl["gestart"] == t_start and tl["afgerond"] == t_af and tl["bron"] == "log"
    pl.reopen(pid)                                        # heropend = niet meer af
    assert P.tijdlijn(pl.get(pid))["afgerond"] is None
    pl.complete(pid, "echt af")
    assert P.tijdlijn(pl.get(pid))["afgerond"] == pl.get(pid)["status_log"][-1]["at"]
    # geen veld op het project: afgeleid, nooit opgeslagen
    assert "started_at" not in pl.get(pid) and "done_at" not in pl.get(pid)


def test_een_project_van_voor_het_log_gokt_niet(tmp_path):
    """Live staan 386 projecten zonder historie. Aangemaakt kennen we (created_at), gestart niet
    (dus leeg, geen gok), en afgerond is bij een done-project de laatste bewerking, als BENADERING
    gemarkeerd. Een rapport hoort dat te tonen."""
    oud = {"id": "x", "status": "done", "created_at": 100.0, "updated_at": 900.0}
    assert P.tijdlijn(oud) == {"aangemaakt": 100.0, "gestart": None, "afgerond": 900.0, "bron": "benadering"}
    open_ = {"id": "y", "status": "running", "created_at": 100.0, "updated_at": 900.0}
    assert P.tijdlijn(open_)["afgerond"] is None and P.tijdlijn(open_)["bron"] == "benadering"


def test_dagen_per_status_telt_de_periodes(tmp_path):
    dag = 86400.0
    p = {"id": "z", "status": "done", "created_at": 0.0,
         "status_log": [{"van": None, "naar": "future", "at": 0.0},
                        {"van": "future", "naar": "running", "at": 2 * dag},
                        {"van": "running", "naar": "blocked", "at": 5 * dag},
                        {"van": "blocked", "naar": "running", "at": 6 * dag},
                        {"van": "running", "naar": "done", "at": 10 * dag}]}
    assert P.dagen_per_status(p, now=20 * dag) == {"future": 2.0, "running": 7.0, "blocked": 1.0}
    # open project: de lopende periode telt tot nu
    q = {"id": "q", "status": "running", "created_at": 0.0,
         "status_log": [{"van": None, "naar": "future", "at": 0.0},
                        {"van": "future", "naar": "running", "at": 1 * dag}]}
    assert P.dagen_per_status(q, now=4 * dag) == {"future": 1.0, "running": 3.0}
    # een oud project waarvan het log pas later begint: de periode ervóór krijgt de status die de
    # eerste regel als `van` noemt, vanaf created_at
    r = {"id": "r", "status": "done", "created_at": 0.0,
         "status_log": [{"van": "running", "naar": "done", "at": 3 * dag}]}
    assert P.dagen_per_status(r, now=9 * dag) == {"running": 3.0}
    # helemaal zonder log: sinds created_at in de huidige status
    assert P.dagen_per_status({"id": "s", "status": "future", "created_at": 0.0}, now=2 * dag) == {"future": 2.0}


def test_de_rail_toont_started_en_done(tmp_path):
    from nooch_village import cockpit2
    from nooch_village.views.projects import _tijdlijn_rijen
    pl = _pl(tmp_path)
    pid = pl.create("rol", "Iets", "human")
    assert _tijdlijn_rijen(pl.get(pid)) == ""                          # niets bekend = geen regel
    pl.start(pid); pl.complete(pid, "af")
    h = _tijdlijn_rijen(pl.get(pid))
    assert "Started" in h and "Done" in h and "≈" not in h
    oud = {"id": "x", "status": "done", "created_at": time.time() - 3 * 86400, "updated_at": time.time()}
    h2 = _tijdlijn_rijen(oud)
    assert "Started" not in h2 and "Done" in h2 and "≈" in h2 and "approximate" in h2


def test_het_bord_zet_de_verplaatser_in_het_log(tmp_path):
    """Wie sleept, staat erbij: de bord-acties geven de persoon door (of de loginnaam)."""
    from nooch_village import cockpit2 as c2
    dd = str(tmp_path / "poc"); c2._bootstrap(dd)
    st = c2._Stores(dd)
    rid = "mother_earth__nooch__website_developer"
    pid = st.projects.create(rid, "Iets", "human")
    bron = inspect.getsource(c2._act_proj_status) + inspect.getsource(c2._act_proj_done)
    assert "pj.start(g(\"pid\"), door)" in bron and "pj.to_future(g(\"pid\"), door)" in bron
    assert "pj.complete(pid, outcome, door=" in bron


def test_de_export_geeft_een_regel_per_overgang(tmp_path, monkeypatch, capsys):
    """`village status_log` → CSV: de grondstof voor een rapportage per doel, zonder bouwwerk.
    Projecten van vóór het log krijgen hun aangemaakt-regel en, als ze af zijn, een benaderde
    done-regel; de kolom `bron` zegt welke het is."""
    import csv
    import io
    import sys
    import types

    from nooch_village import cli, cockpit2
    dd = str(tmp_path / "cli")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    d = st.doelen.add("Rapport MITH", label="MITH", activiteiten=["WP1"])
    pid = st.projects.create("rol", "Sectie 1", "human")
    st.projects.set_doel(pid, d["id"], "WP1")
    st.projects.start(pid, "stefan"); st.projects.complete(pid, "af", door="stefan")
    oud = st.projects.create("rol", "Oud en af", "human")
    st.projects._projects[oud].pop("status_log"); st.projects._projects[oud]["status"] = "done"
    st.projects._save()
    monkeypatch.setattr("nooch_village.config.load_context", lambda _b: types.SimpleNamespace(data_dir=dd))
    monkeypatch.setattr(sys, "argv", ["village", "status_log"])
    cli.main()
    rijen = list(csv.DictReader(io.StringIO(capsys.readouterr().out)))
    mijn = [r for r in rijen if r["pid"] == pid]
    assert [r["naar"] for r in mijn] == ["future", "running", "done"]
    assert mijn[0]["doel"] == "MITH" and mijn[0]["werkpakket"] == "WP1" and mijn[-1]["door"] == "stefan"
    assert all(r["bron"] == "log" and r["wanneer"] for r in mijn)
    oude = [r for r in rijen if r["pid"] == oud]
    assert [r["bron"] for r in oude] == ["aangemaakt", "benadering"] and oude[1]["naar"] == "done"
