"""WIP-cirkelpolicy op autonome projectvoorbereiding (eerste gedrag-sturende policy).
De policy WIP-001 is de expliciete AAN-schakelaar; het getal N komt uit config (niet uit de body);
per AI-bemande rol worden max N future-projecten voorbereid (FIFO), de rest wacht. Thread-vrij."""
from __future__ import annotations
import pytest
from types import SimpleNamespace

from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus
from nooch_village.skills import SkillRegistry
from nooch_village.projects import ProjectLedger
from nooch_village.attachments import AttachmentStore


class _Recs:
    def __init__(self, records):
        self._m = {r.id: r for r in records}

    def all(self):
        return list(self._m.values())

    def get(self, rid):
        return self._m.get(rid)


def _build(tmp_path, monkeypatch, *, persona_id="persona-1", wip_on=True, N="8", body="N is 8"):
    ledger = ProjectLedger(str(tmp_path / "projects.json"))
    att = AttachmentStore(str(tmp_path / "att.json"))
    if wip_on:
        att.add("noochville", "policy", title="WIP-limit", body=body, domain="WIP", inherit=True)  # → WIP-001
    circle = Record(id="noochville", type=RecordType.CIRCLE, parent=None,
                    definition=RoleDefinition(purpose="c", accountabilities=[], domains=[], skills=[]), source="seed")
    role = Record(id="harry", type=RecordType.ROLE, parent="noochville",
                  definition=RoleDefinition(purpose="r", accountabilities=[], domains=[], skills=[]), source="sensed")
    role.persona_id = persona_id
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0", "wip_prepare_limit": N},
                          data_dir=str(tmp_path), projects=ledger, records=_Recs([circle, role]), att=att)
    inh = Inhabitant(role, EventBus(name="t"), SkillRegistry(), ctx)
    calls = []
    monkeypatch.setattr(inh, "prepare_project", lambda pid: calls.append(pid))   # tel/registreer selectie
    return inh, ledger, calls


def _future(ledger, n, *, prepared=0, base=1000.0):
    """n future-projecten met deterministische created_at (FIFO); de eerste `prepared` krijgen een checklist."""
    pids = []
    for i in range(n):
        pid = ledger.create("harry", f"doel-{i}", "human", status="future")
        if i < prepared:
            cl = ledger.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE)
            ledger.check_add(pid, cl["id"], "item")
        pids.append(pid)
    for i, pid in enumerate(pids):
        ledger.get(pid)["created_at"] = base + i          # deterministische volgorde
    ledger._save()
    return pids


# a. WIP-001 aan, AI-rol met >8 future → max 8 voorbereid, rest wacht
def test_a_wip_cap_max_n(tmp_path, monkeypatch):
    inh, ledger, calls = _build(tmp_path, monkeypatch, N="8")
    _future(ledger, 12)
    inh._tend_projects()
    assert len(calls) == 8                                 # 8 voorbereid, 4 wachten


# b. FIFO: de oudste future-projecten eerst
def test_b_fifo_oudste_eerst(tmp_path, monkeypatch):
    inh, ledger, calls = _build(tmp_path, monkeypatch, N="3")
    pids = _future(ledger, 6)                              # created_at 1000..1005 (oplopend = FIFO)
    inh._tend_projects()
    assert calls == pids[:3]                               # exact de 3 oudste, in volgorde


# c. plek komt vrij (voorbereid project → ACTIEF) → volgende in de rij voorbereid
def test_c_slot_vrij_volgende_voorbereid(tmp_path, monkeypatch):
    inh, ledger, calls = _build(tmp_path, monkeypatch, N="3")
    pids = _future(ledger, 5, prepared=3)                 # 3 al voorbereid (slots vol), 2 wachten
    inh._tend_projects()
    assert calls == []                                    # limiet vol → niets nieuws
    ledger.start(pids[0])                                 # een voorbereid project → ACTIEF (verlaat future)
    inh._tend_projects()
    assert calls == [pids[3]]                             # 1 plek vrij → volgende FIFO-wachtende voorbereid


# d. WIP-001 afwezig → geen limiet
def test_d_geen_policy_geen_limiet(tmp_path, monkeypatch):
    inh, ledger, calls = _build(tmp_path, monkeypatch, wip_on=False)
    _future(ledger, 12)
    inh._tend_projects()
    assert len(calls) == 12                               # ongelimiteerd (huidig gedrag)


# e. N komt uit config/hook, NIET uit de body-tekst
def test_e_n_uit_config_niet_body(tmp_path, monkeypatch):
    inh, ledger, calls = _build(tmp_path, monkeypatch, N="3", body="Rollen bereiden maximaal 999 projecten voor")
    _future(ledger, 10)
    inh._tend_projects()
    assert len(calls) == 3                                # config (3) wint; de "999" in de body doet niets


# f. mens-bemande rol → niet beperkt (bereidt niet autonoom); geen persona_id → geen limiet
def test_f_mens_bemand_niet_beperkt(tmp_path, monkeypatch):
    inh, ledger, calls = _build(tmp_path, monkeypatch, persona_id=None, N="3")
    _future(ledger, 12)
    inh._tend_projects()
    assert len(calls) == 12                               # WIP-cap raakt mens-bemande rol niet
    assert inh._wip_prepare_limit() is None


def test_g_wip_limit_resolutie(tmp_path, monkeypatch):
    # directe check op de hook-resolutie (eigen data-dir per build, anders erft att.json door)
    d1 = tmp_path / "ai"; d1.mkdir()
    d2 = tmp_path / "off"; d2.mkdir()
    inh_ai, _, _ = _build(d1, monkeypatch, persona_id="p", wip_on=True, N="8")
    assert inh_ai._wip_prepare_limit() == 8                # AI + policy aan → N
    inh_off, _, _ = _build(d2, monkeypatch, persona_id="p", wip_on=False)
    assert inh_off._wip_prepare_limit() is None            # policy uit → geen limiet
