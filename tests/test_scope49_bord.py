"""Scope 49 (12 september 2026) — het bord zonder `queued`, en het verslag sluit het project af.

Stefan: "als ik een project toevoeg onder Active staat de status standaard op queued en moet ik het
handmatig op actief zetten. Kan die hele queue-functie weg? Een project staat standaard op future en
als je hem sleept naar actief maak je hem van slapend naar actief. En als ik een project op done
sleep kan ik het rapport maken; als ik dat gedaan heb moet ie eigenlijk worden gearchiveerd."

Vier regels, allemaal hier getoetst:
1. nieuw = future (slapend), behalve de "+ add project"-deur ónder Active → running;
2. ook wat het dorp zelf aanmaakt (doorgeven, claims, voorstellen, goedgekeurde concepten) slaapt;
3. een legacy `queued`-project wordt bij het laden actief, met een regel in zijn status_log;
4. verslag bevestigd of overgeslagen = gearchiveerd, en een afgerond project blijft voor zijn doel
   meetellen, gearchiveerd of niet."""
from __future__ import annotations

import inspect
import json

from nooch_village import cockpit2, doelen, projects as P
from nooch_village.projects import ProjectLedger

ROLE = "mother_earth__nooch__brand_visual_designer"          # één vervuller: geen owner-keuze nodig


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


# ── 1 en 2: het vocabulaire ───────────────────────────────────────────────────

def test_queued_bestaat_niet_meer():
    assert "queued" not in P.STATUSSEN and "queued" not in P.START_STATUSSEN
    assert P.LOPEND == ("running",) and P.OP_HET_BORD == ("running", "blocked")
    assert P.START_STATUSSEN[0] == "future"                       # de default staat vooraan
    bron = inspect.getsource(P.ProjectLedger.create)
    assert 'status: str = "future"' in bron


def test_nieuw_is_slapend_en_alleen_de_active_deur_maakt_actief(tmp_path):
    dd, st = _st(tmp_path)
    basis = {"owner": [ROLE], "scope": ["X"], "next": ["/"]}
    cockpit2.dispatch(dd, "proj_add", {**basis, "scope": ["Zonder kolom"]}, username="guest")
    cockpit2.dispatch(dd, "proj_add", {**basis, "scope": ["Onder Active"], "col": ["actief"]}, username="guest")
    cockpit2.dispatch(dd, "proj_add", {**basis, "scope": ["Onder Future"], "col": ["toekomst"]}, username="guest")
    cockpit2.dispatch(dd, "proj_add", {**basis, "scope": ["Onder Waiting"], "col": ["wacht"]}, username="guest")
    per = {p["scope"]: p["status"] for p in cockpit2._Stores(dd).projects.all()}
    assert per == {"Zonder kolom": "future", "Onder Active": "running",
                   "Onder Future": "future", "Onder Waiting": "blocked"}


def test_wat_het_dorp_zelf_aanmaakt_slaapt(tmp_path):
    """Doorgegeven werk, een goedgekeurd concept en een aangenomen voorstel: allemaal future. Een mens
    sleept naar Active; dat is de regel van 5 september, en queued was er de uitzondering op."""
    pl = ProjectLedger(str(tmp_path / "p.json"))
    d = pl.create("rol", "Concept", "human", status="draft"); pl.approve(d)
    assert pl.get(d)["status"] == "future"
    v = pl.create("rol", "Voorstel", "role", status="proposed"); pl.accept_proposal(v)
    assert pl.get(v)["status"] == "future"
    from nooch_village.project_items import handoff
    src = inspect.getsource(handoff)
    assert 'status="future"' in src and "queued" not in src
    from nooch_village import claims_board
    assert 'status="future"' in inspect.getsource(claims_board) and "queued" not in inspect.getsource(claims_board)


def test_de_rol_werkt_alleen_aan_actief_werk_en_maar_een_keer(tmp_path):
    """`_eligible`: running en nog niet gewerkt. Future is niet aan de beurt, en na één ronde is het
    `worked`-anker de rem (dat was vroeger de overgang queued → running)."""
    from nooch_village.project_worker import _eligible
    assert not _eligible({"status": "future"}, 3)
    assert _eligible({"status": "running"}, 3)
    assert not _eligible({"status": "running", "worked": True}, 3)
    assert not _eligible({"status": "blocked"}, 3) and not _eligible({"status": "done"}, 3)


# ── 3: de migratie ───────────────────────────────────────────────────────────

def test_een_legacy_queued_project_wordt_actief_bij_het_laden(tmp_path):
    """Live staan er vijf op queued, allemaal in de kolom Active. Ze worden running, één keer, met
    een regel in het log die zegt dat dit een migratie was en geen sleep."""
    path = str(tmp_path / "p.json")
    json.dump({"a": {"id": "a", "owner": "r", "scope": "Oud", "trigger": "human", "status": "queued",
                     "created_at": 1.0, "updated_at": 1.0},
               "b": {"id": "b", "owner": "r", "scope": "Al af", "trigger": "human", "status": "done",
                     "created_at": 1.0, "updated_at": 2.0}}, open(path, "w"))
    pl = ProjectLedger(path)
    a = pl.get("a")
    assert a["status"] == "running"
    assert a["status_log"][-1] == {**a["status_log"][-1], "van": "queued", "naar": "running"}
    assert "migratie" in a["status_log"][-1]["door"]
    assert pl.get("b")["status"] == "done" and "status_log" not in pl.get("b")   # ongemoeid
    # geschreven, dus een tweede lezer ziet het ook; en de tweede keer laden migreert niets
    assert json.load(open(path))["a"]["status"] == "running"
    assert ProjectLedger(path).migreer_queued() == 0
    assert "migreer_queued" in P._WRITE_METHODS                    # onder het slot, als elke schrijf


# ── 4: het verslag sluit het project af ──────────────────────────────────────

def _afgesloten(dd, st, titel="Sluitstuk"):
    pid = st.projects.create(ROLE, titel, "human", status="running", done_when="af")
    cl = st.projects.checklist_add(pid, "tasks")["id"]
    st.projects.check_add(pid, cl, "A")
    it = next(c for c in st.projects.get(pid)["checklists"] if c["id"] == cl)["items"][0]
    st.projects.check_toggle(pid, cl, it["id"])
    cockpit2.dispatch(dd, "proj_done", {"pid": [pid], "next": ["/"]}, username="guest")
    return pid


def test_bevestigd_verslag_archiveert(tmp_path):
    dd, st = _st(tmp_path)
    pid = _afgesloten(dd, st)
    assert not cockpit2._Stores(dd).projects.get(pid).get("archived")     # done, nog op het bord
    _, msg = cockpit2.dispatch(dd, "verslag_bevestig_behaald", {"pid": [pid], "next": ["/"]}, username="guest")
    p = cockpit2._Stores(dd).projects.get(pid)
    assert p["archived"] is True and p["status"] == "done" and p["resultaat"] == "behaald"
    assert msg.startswith("✓ report confirmed") and "gearchiveerd" in msg


def test_niet_behaald_en_overslaan_archiveren_ook(tmp_path):
    dd, st = _st(tmp_path)
    a = _afgesloten(dd, st, "Niet gelukt")
    cockpit2.dispatch(dd, "verslag_bevestig_niet_behaald", {"pid": [a], "next": ["/"]}, username="guest")
    assert cockpit2._Stores(dd).projects.get(a)["archived"] is True
    b = _afgesloten(dd, st, "Zonder verslag")
    _, msg = cockpit2.dispatch(dd, "verslag_overslaan", {"pid": [b], "next": ["/"]}, username="guest")
    assert cockpit2._Stores(dd).projects.get(b)["archived"] is True and "gearchiveerd" in msg


def test_een_afgerond_project_blijft_voor_zijn_doel_meetellen(tmp_path):
    """Archiveren is het bord opruimen, geen uitschrijving uit het doel. Een gearchiveerd project dat
    NIET af is (opgegeven) telt wél niet mee."""
    dd, st = _st(tmp_path)
    d = st.doelen.add("Rapport MITH", label="MITH")
    af = st.projects.create(ROLE, "Sectie 1", "human", status="running"); st.projects.set_doel(af, d["id"])
    st.projects.complete(af, "af"); st.projects.archive(af)
    open_ = st.projects.create(ROLE, "Sectie 2", "human", status="running"); st.projects.set_doel(open_, d["id"])
    weg = st.projects.create(ROLE, "Opgegeven", "human"); st.projects.set_doel(weg, d["id"]); st.projects.archive(weg)
    alle = st.projects.all()
    assert {p["id"] for p in doelen.projecten_van(d["id"], alle)} == {af, open_}
    assert doelen.voortgang(d, alle)["af"] == 1 and doelen.voortgang(d, alle)["pct"] == 50


def test_archiveren_is_een_gedeelde_route(tmp_path):
    """Eén plek voor 'het bord af, met signaal': de knop en het verslag delen `archiveer`. Twee
    kopieën drijven uiteen (de signaal-plaatsing zou dan op één van de twee ontbreken)."""
    bron = inspect.getsource(cockpit2)
    assert bron.count("signal_from_project(st.radar, p)") == 1
    for f in (cockpit2._act_proj_archive, cockpit2._bevestig_met, cockpit2._act_verslag_overslaan):
        assert "archiveer(" in inspect.getsource(f), f.__name__
