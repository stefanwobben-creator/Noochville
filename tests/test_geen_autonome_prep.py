"""Geen autonome projectvoorbereiding meer (drie-stagiairs-besluit, 5 september 2026).

Er zijn geen autonoom werkende AI-rollen meer, alleen stagiairs die mensen helpen. Dus bereidt
niemand ongevraagd een TOEKOMST-project voor; de mens start het werk door een project naar ACTIEF
te slepen. Deze tests vervangen `test_wip_policy.py`, dat het verdwenen gedrag vastlegde.

Thread-vrij: `prepare_project` is gemonkeypatcht, er draait geen enkele LLM-call.
"""
from __future__ import annotations

from types import SimpleNamespace

from nooch_village.attachments import AttachmentStore
from nooch_village.event_bus import Event, EventBus
from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RecordType, RoleDefinition
from nooch_village.projects import ProjectLedger
from nooch_village.skills import SkillRegistry


class _Recs:
    def __init__(self, records):
        self._m = {r.id: r for r in records}

    def all(self):
        return list(self._m.values())

    def get(self, rid):
        return self._m.get(rid)


def _build(tmp_path, monkeypatch, *, persona_id="persona-1"):
    ledger = ProjectLedger(str(tmp_path / "projects.json"))
    att = AttachmentStore(str(tmp_path / "att.json"))
    circle = Record(id="noochville", type=RecordType.CIRCLE, parent=None,
                    definition=RoleDefinition(purpose="c", accountabilities=[], domains=[], skills=[]),
                    source="seed")
    role = Record(id="harry", type=RecordType.ROLE, parent="noochville",
                  definition=RoleDefinition(purpose="r", accountabilities=[], domains=[], skills=[]),
                  source="sensed")
    role.persona_id = persona_id
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0"}, data_dir=str(tmp_path),
                          projects=ledger, records=_Recs([circle, role]), att=att)
    inh = Inhabitant(role, EventBus(name="t"), SkillRegistry(), ctx)
    prep, run = [], []
    # `**kw` want de bord-drag geeft sinds 07-09 `net_gevraagd=True` mee: de mens staat op de kaart,
    # dus dat plan hoeft geen inbox-bericht. Deze test gaat over het VOORBEREIDEN, niet over de melding.
    monkeypatch.setattr(inh, "prepare_project", lambda pid, **kw: prep.append(pid))
    monkeypatch.setattr(inh, "_claim_run_complete", lambda pid: run.append(pid))
    return inh, ledger, prep, run


def _future(ledger, n, owner="harry"):
    return [ledger.create(owner, f"doel-{i}", "human", status="future") for i in range(n)]


# ── TOEKOMST blijft liggen ───────────────────────────────────────────────────────────────────

def test_tend_bereidt_geen_enkel_toekomst_project_voor(tmp_path, monkeypatch):
    """Twaalf future-projecten, dagpuls, nul voorbereidingen. Dit was het pad waarlangs 195
    ongevraagde projecten ontstonden."""
    inh, ledger, prep, _run = _build(tmp_path, monkeypatch)
    _future(ledger, 12)
    inh._tend_projects()
    assert prep == []


def test_tend_voert_actief_werk_nog_steeds_uit(tmp_path, monkeypatch):
    """ACTIEF is wél toegewezen werk: dat blijft doorlopen."""
    inh, ledger, _prep, run = _build(tmp_path, monkeypatch)
    pid = ledger.create("harry", "doel", "human", status="running")
    inh._tend_projects()
    assert run == [pid]


def test_tend_raakt_projecten_van_een_ander_niet(tmp_path, monkeypatch):
    inh, ledger, prep, run = _build(tmp_path, monkeypatch)
    ledger.create("iemand_anders", "doel", "human", status="running")
    _future(ledger, 3, owner="iemand_anders")
    inh._tend_projects()
    assert prep == [] and run == []


# ── slepen naar ACTIEF is de opdracht ────────────────────────────────────────────────────────

def _activated(pid, owner="harry"):
    return Event("project_activated", {"pid": pid, "owner": owner}, "board_watch")


def test_activatie_bereidt_alsnog_voor_en_voert_uit(tmp_path, monkeypatch):
    """Zonder deze stap zou de mens na het slepen tot de volgende dagpuls (04:32) niets zien."""
    inh, ledger, prep, run = _build(tmp_path, monkeypatch)
    pid = ledger.create("harry", "doel", "human", status="running")
    inh._on_project_activated(_activated(pid))
    assert prep == [pid]
    assert run == [pid]


def test_activatie_bereidt_niet_opnieuw_voor_met_bestaande_checklist(tmp_path, monkeypatch):
    inh, ledger, prep, run = _build(tmp_path, monkeypatch)
    pid = ledger.create("harry", "doel", "human", status="running")
    cl = ledger.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE)
    ledger.check_add(pid, cl["id"], "item")
    inh._on_project_activated(_activated(pid))
    assert prep == []
    assert run == [pid]


def test_activatie_van_andermans_project_doet_niets(tmp_path, monkeypatch):
    inh, ledger, prep, run = _build(tmp_path, monkeypatch)
    pid = ledger.create("iemand_anders", "doel", "human", status="running")
    inh._on_project_activated(_activated(pid, owner="iemand_anders"))
    assert prep == [] and run == []


def test_activatie_zonder_ledger_valt_niet_om(tmp_path, monkeypatch):
    inh, _ledger, prep, run = _build(tmp_path, monkeypatch)
    inh.context.projects = None
    inh._on_project_activated(_activated("bestaat-niet"))
    assert prep == []
    assert run == ["bestaat-niet"]          # uitvoeren mag het proberen; dat pad is al fail-closed


# ── een mislukt plan is zichtbaar ────────────────────────────────────────────────────────────

def test_mislukt_plan_meldt_dat_aan_de_rol(tmp_path, monkeypatch):
    """Fail-open op AI: wie het project activeerde ziet anders een stilstaand project zonder uitleg."""
    inh, ledger, _prep, _run = _build(tmp_path, monkeypatch)
    monkeypatch.setattr(inh, "prepare_project", Inhabitant.prepare_project.__get__(inh))
    monkeypatch.setattr(inh, "_raadpleeg_kennis", lambda *a, **k: None)
    monkeypatch.setattr(inh, "_plan_checklist", lambda *a, **k: None)      # het plan mislukt
    meldingen = []
    monkeypatch.setattr(inh, "_notify_rol", lambda rol, pid, snippet: meldingen.append((rol, pid, snippet)))
    pid = ledger.create("harry", "een doel", "human", status="future")
    inh.prepare_project(pid)
    assert len(meldingen) == 1
    rol, gemeld_pid, snippet = meldingen[0]
    assert rol == "harry" and gemeld_pid == pid
    assert "execution plan" in snippet.lower()
    assert ledger.get(pid).get("checklists") in (None, [])                 # niets half aangemaakt
