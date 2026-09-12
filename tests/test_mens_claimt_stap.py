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
from nooch_village.projects import ProjectLedger, checklist_progress
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
    cl = ledger.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE)
    for tekst, skill in items:
        ledger.check_add(pid, cl["id"], tekst, skill=skill,
                         reason="" if skill else "geen skill: dit vraagt een mens")
    return pid, cl["id"]


def _cl(p, clid):
    return next(c for c in p["checklists"] if c["id"] == clid)


def _pauzes(p) -> list:
    return [e["text"] for e in p.get("log", []) if e["text"].startswith("⏸️")]


# ── 1 + 2: de lus stopt, maar de klep blijft werken ─────────────────────────

def test_na_claimen_blijft_het_project_actief(tmp_path):
    ledger = ProjectLedger(str(tmp_path / "projects.json"))
    pid, clid = _project(ledger, [("verifieer de claim", "claims_check"),
                                  ("bel de boekhouder over de bankafschriften", None)])
    inh = _inh(tmp_path, ledger)

    inh._execute_checklist(ledger.get(pid), DAG1)
    assert ledger.get(pid)["status"] == "blocked"          # één keer vragen mag
    assert len(_pauzes(ledger.get(pid))) == 1

    # de mens sleept terug naar ACTIEF: dát is het antwoord
    assert ledger.claim_human_items(pid, door="stefan") != []
    ledger.start(pid)

    inh._execute_checklist(ledger.get(pid), DAG2)

    p = ledger.get(pid)
    assert p["status"] == "running"                          # geen tweede parkering
    assert len(_pauzes(p)) == 1                              # en geen tweede hulpvraag
    assert p.get("park") is None


def test_zonder_claim_parkeert_hij_gewoon_opnieuw(tmp_path):
    """De tegenproef: zonder het vastgelegde antwoord doet de klep precies wat hij hoort te doen."""
    ledger = ProjectLedger(str(tmp_path / "projects.json"))
    pid, _clid = _project(ledger, [("verifieer de claim", "claims_check"),
                                   ("bel de boekhouder over de bankafschriften", None)])
    inh = _inh(tmp_path, ledger)

    inh._execute_checklist(ledger.get(pid), DAG1)
    ledger.start(pid)                                        # terug naar actief, maar niets geclaimd
    inh._execute_checklist(ledger.get(pid), DAG2)

    p = ledger.get(pid)
    assert p["status"] == "blocked" and len(_pauzes(p)) == 2


# ── 3: een geclaimde stap is echt werk en telt mee ──────────────────────────

def test_geclaimde_stap_telt_mee_voor_klaar(tmp_path):
    """`human_task` zou hem uit de noemer halen; dan is 1/1 'compleet' en gaat het project naar
    review terwijl de mens zijn stap nog moet doen. Review is óók blocked: de lus terug."""
    ledger = ProjectLedger(str(tmp_path / "projects.json"))
    pid, clid = _project(ledger, [("verifieer de claim", "claims_check"),
                                  ("bel de boekhouder over de bankafschriften", None)])
    inh = _inh(tmp_path, ledger)
    inh._execute_checklist(ledger.get(pid), DAG1)
    ledger.claim_human_items(pid, door="stefan")
    ledger.start(pid)

    inh._execute_checklist(ledger.get(pid), DAG2)

    p = ledger.get(pid)
    item = next(it for it in _cl(p, clid)["items"] if it["text"].startswith("bel de boekhouder"))
    assert item.get("geclaimd") is True and not item.get("human_task")
    assert checklist_progress(_cl(p, clid)) == (1, 2)        # eerlijk: 1 van 2, nog niet af
    assert p["status"] == "running"                          # dus ook niet 'klaar voor review'


def test_afvinken_maakt_het_project_alsnog_afrondbaar(tmp_path):
    """Claimen is geen ontsnapping: doet de mens de stap, dan is de checklist gewoon af."""
    ledger = ProjectLedger(str(tmp_path / "projects.json"))
    pid, clid = _project(ledger, [("verifieer de claim", "claims_check"),
                                  ("bel de boekhouder over de bankafschriften", None)])
    inh = _inh(tmp_path, ledger)
    inh._execute_checklist(ledger.get(pid), DAG1)
    ledger.claim_human_items(pid, door="stefan")
    ledger.start(pid)
    item = next(it for it in _cl(ledger.get(pid), clid)["items"]
                if it["text"].startswith("bel de boekhouder"))
    ledger.check_toggle(pid, clid, item["id"])

    inh._execute_checklist(ledger.get(pid), DAG2)

    p = ledger.get(pid)
    assert checklist_progress(_cl(p, clid)) == (2, 2)
    assert p.get("blocked_on") == "review"


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
