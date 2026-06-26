"""Monte-Carlo stresstest op de governance-kern: honderden gerandomiseerde voorstellen door
Gate G0-G4 + Secretary-adoptie houden de records structureel valide. Plus de specifieke gaten
die de stresstest blootlegde (regressie-guards)."""
from __future__ import annotations
import os
import tempfile

from nooch_village.montecarlo import run, base_records, check_invariants, _NullBus
from nooch_village.governance import Gate, Secretary
from nooch_village.models import (Proposal, GovernanceChange, ChangeKind, Record, RecordType,
                                  RoleDefinition)


def test_montecarlo_houdt_records_valide_meerdere_seeds():
    # Reproduceerbaar over meerdere seeds: na alle door de poort gelaten voorstellen mogen er
    # GEEN invariant-schendingen zijn (geen wezen, geen dubbele acc/domein, geen lege purpose).
    for seed in range(5):
        rep = run(400, seed=seed)
        assert rep["invariant_violations"] == [], (seed, rep["invariant_violations"])
        assert rep["first_mid_failure"] is None, (seed, rep["first_mid_failure"])
        assert rep["applied"] > 0 and rep["blocked_by_gate"]      # de poort doet echt werk


def _setup():
    tmp = os.path.join(tempfile.mkdtemp(), "r.json")
    recs = base_records(tmp)
    return recs, Gate(), Secretary(recs, _NullBus())


_META = dict(proposer_role="founder", tension="t", trigger_example="structureel terugkerend",
             rationale="r")


def test_g3_blokkeert_verwijderen_van_cirkel_met_kinderen():
    # Het gat dat de stresstest onthulde: een rol met onderliggende rollen verwijderen maakt die
    # kinderen tot wees. G3 hoort dat te blokkeren (ook als de ouder geen accountabilities heeft).
    recs, gate, sec = _setup()
    recs.put(Record(id="lege_cirkel", type=RecordType.ROLE, parent="noochville",
                    definition=RoleDefinition(purpose="Y"), members=["kind_b"], source="seed"))
    root = recs.get("noochville"); root.members.append("lege_cirkel")
    recs.put(Record(id="kind_b", type=RecordType.ROLE, parent="lege_cirkel",
                    definition=RoleDefinition(purpose="Z", accountabilities=["Werk doen"]), source="seed"))
    p = Proposal(change=GovernanceChange(kind=ChangeKind.REMOVE_ROLE, role_id="lege_cirkel"), **_META)
    passed, gate_name, reason = gate.check(p, recs, None)
    assert passed is False and gate_name == "G3" and "wees" in reason
    # en als we het (ondanks de blokkade) níét adopteren, blijven de records valide
    assert check_invariants(recs) == []


def test_check_invariants_spot_wees_en_dubbele_acc():
    # De invariant-checker moet echte corruptie kunnen zien (anders is de stresstest blind).
    recs, _, _ = _setup()
    recs.put(Record(id="wees", type=RecordType.ROLE, parent="bestaat_niet",
                    definition=RoleDefinition(purpose="P"), source="seed"))
    recs.put(Record(id="dubbel", type=RecordType.ROLE, parent="noochville",
                    definition=RoleDefinition(purpose="P",
                                              accountabilities=["Volgen van de concurrenten"]),
                    source="seed"))
    recs.get("noochville").members.append("dubbel")
    viol = check_invariants(recs)
    assert any("wees" in v for v in viol)
    assert any("dubbele accountability" in v for v in viol)
