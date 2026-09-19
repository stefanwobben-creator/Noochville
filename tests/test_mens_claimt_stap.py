"""De lus tussen een mens en een daemon die het met elkaar eens waren (prod, 9 september 2026).

Een checklist-item dat alleen een mens kan doen parkeert het project: `_blocking_reason` zegt
"human", de vastloop-klep zet het op WACHT en de founder krijgt de vraag "kun jij dit doen?".
Terecht, één keer.

Maar het project terugslepen naar ACTIEF IS het antwoord op die vraag, en dat antwoord werd nergens
vastgelegd. Dus draaide de rol bij de volgende puls opnieuw, liep op hetzelfde item vast, parkeerde
opnieuw en pingde opnieuw. Stefan sleepte terug. Enzovoort.

Wat hier wordt bevroren:
  1. na het claimen blijft het project ACTIEF, zonder tweede park en zonder tweede hulpvraag;
  2. zónder claim parkeert hij wél opnieuw — de klep zelf blijft dus gewoon werken;
  3. een geclaimde stap TELT MEE voor klaar. Zou hij `human_task` worden, dan valt hij uit de
     klaar-telling en is de checklist "compleet" → klaar voor review → óók `blocked`: dezelfde lus
     in een ander jasje;
  4. het slepen zelf (de mens-route in de cockpit) is wat claimt, niet elke statuswijziging;
  5. accepteer je alsnog een skill-aanbod, dan is de stap weer van de rol.
"""
from __future__ import annotations

from types import SimpleNamespace

from nooch_village import cockpit2
from nooch_village.event_bus import EventBus
from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RecordType, RoleDefinition
from nooch_village.projects import ProjectLedger, checklist_progress, PREP_CHECKLIST_TITLE
from nooch_village.skills import Skill, SkillRegistry

DAG1 = "2026-09-09"
DAG2 = "2026-09-10"


class _OkSkill(Skill):
    name = "claims_check"
    description = "fake skill die het altijd doet"

    def run(self, payload, context):
        return {"ok": True, "result": "gecontroleerd"}


def _inh(tmp_path, ledger, **settings):
    reg = SkillRegistry()
    reg.register(_OkSkill())
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0", **settings},
                          data_dir=str(tmp_path), projects=ledger, records=None)
    rec = Record(id="compliance", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="geen greenwashing", accountabilities=["claims"],
                                           domains=[], skills=["claims_check"]),
                 source="sensed")
    return Inhabitant(rec, EventBus(name="test"), reg, ctx)


def _project(ledger, items):
    pid = ledger.create("compliance", "Subsidieadministratie kloppend maken", "human",
                        status="running")
    ledger.start(pid)
    cl = ledger.checklist_add(pid, title=PREP_CHECKLIST_TITLE)
    for tekst, skill in items:
        ledger.check_add(pid, cl["id"], tekst, skill=skill,
                         reason="" if skill else "geen skill: dit vraagt een mens")
    return pid, cl["id"]


def _cl(p, clid):
    return next(c for c in p["checklists"] if c["id"] == clid)


def _pauzes(p) -> list:
    return [e["text"] for e in p.get("log", []) if e["text"].startswith("⏸️")]










# ── 4: het slepen in de cockpit is wat claimt ───────────────────────────────

def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def _geparkeerd(dd):
    """Een project met een vastgelegde mens-blokkade, zoals de klep het achterlaat."""
    st = cockpit2._Stores(dd)
    pid, clid = _project(st.projects, [("bel de boekhouder", None)])
    item = st.projects.get(pid)["checklists"][0]["items"][0]
    st.projects.park(pid, "human", [{"id": item["id"], "text": item["text"], "reden": "human"}],
                     door="compliance")
    st.projects.block(pid, "vastgelopen op 1 item(s) — wacht op een mens of externe partij")
    return pid, clid, item["id"]


def test_slepen_naar_actief_claimt_de_mens_stap(tmp_path):
    dd = _dd(tmp_path)
    pid, clid, iid = _geparkeerd(dd)

    _nxt, msg = cockpit2.dispatch(dd, "proj_status",
                                  {"pid": [pid], "to": ["actief"], "next": ["/"]}, username="guest")

    p = cockpit2._Stores(dd).projects.get(pid)
    assert p["status"] == "running" and p.get("park") is None
    assert p["checklists"][0]["items"][0].get("geclaimd") is True
    assert "staat nu op jou" in msg


def test_naar_wacht_slepen_claimt_niets(tmp_path):
    """Alleen ACTIEF is het antwoord 'ik ben ermee bezig'. Andere kolommen zeggen dat niet."""
    dd = _dd(tmp_path)
    pid, _clid, _iid = _geparkeerd(dd)

    cockpit2.dispatch(dd, "proj_status", {"pid": [pid], "to": ["toekomst"], "next": ["/"]},
                      username="guest")

    p = cockpit2._Stores(dd).projects.get(pid)
    assert not p["checklists"][0]["items"][0].get("geclaimd")
    assert isinstance(p.get("park"), dict)                   # de vraag staat nog open


def test_zonder_park_reden_valt_er_niets_te_claimen(tmp_path):
    """Een gewoon project uit TOEKOMST naar ACTIEF slepen claimt niets: er stond geen vraag open."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    pid, _clid = _project(st.projects, [("bel de boekhouder", None)])
    st.projects.to_future(pid)

    _nxt, msg = cockpit2.dispatch(dd, "proj_status",
                                  {"pid": [pid], "to": ["actief"], "next": ["/"]}, username="guest")

    p = cockpit2._Stores(dd).projects.get(pid)
    assert not p["checklists"][0]["items"][0].get("geclaimd")
    assert "staat nu op jou" not in msg


# ── 5: teruggeven aan de rol ────────────────────────────────────────────────

def test_skill_aanbod_accepteren_geeft_de_stap_terug_aan_de_rol(tmp_path):
    ledger = ProjectLedger(str(tmp_path / "projects.json"))
    pid, clid = _project(ledger, [("bel de boekhouder", None)])
    item = ledger.get(pid)["checklists"][0]["items"][0]
    ledger.park(pid, "human", [{"id": item["id"], "text": item["text"], "reden": "human"}])
    assert ledger.claim_human_items(pid, door="stefan") == [item["id"]]

    ledger.set_item_offer(pid, clid, item["id"], {"skill": "claims_check", "payload": {"claim": "x"}})
    assert ledger.accept_item_offer(pid, clid, item["id"])

    it = ledger.get(pid)["checklists"][0]["items"][0]
    assert it.get("skill") == "claims_check" and not it.get("geclaimd")


# ── de kaart laat zien dat de rol niet meer vraagt ──────────────────────────

def test_de_kaart_toont_dat_jij_de_stap_hebt_opgepakt(tmp_path):
    dd = _dd(tmp_path)
    pid, _clid, _iid = _geparkeerd(dd)
    cockpit2.dispatch(dd, "proj_status", {"pid": [pid], "to": ["actief"], "next": ["/"]},
                      username="guest")

    html = cockpit2.render_project(cockpit2._Stores(dd), pid, csrf_token="t")

    assert "you picked this up" in html
    assert "○ no skill" not in html
