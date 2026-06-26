"""Monte-Carlo stresstest voor de governance-kern.

Genereert honderden gerandomiseerde rolvoorstellen (nieuwe rollen, dubbele accountabilities,
amend bestaande, remove, domein-botsingen, hernoemen, geneste cirkels) en draait ze door de
échte poort (Gate G0-G4) + Secretary-adoptie op een geïsoleerde, in-memory records-set.

Daarna toetst `check_invariants` of de records nog structureel kloppen. Een schending = een gat:
iets wat de poort doorliet maar de waarheid corrumpeert. Reproduceerbaar via een seed.

CLI:  python -m nooch_village.village montecarlo [n] [seed]
"""
from __future__ import annotations
import random
import tempfile
import os

from nooch_village.governance import Gate, Secretary, Records
from nooch_village.models import (Proposal, GovernanceChange, ChangeKind, Record, RecordType,
                                  RoleDefinition)


class _NullBus:
    def publish(self, *a, **k): pass
    def subscribe(self, *a, **k): pass


# Bouwstenen voor gerandomiseerde, betekenisvolle proposals.
_VERBS = ["Bewaken", "Schrijven", "Volgen", "Analyseren", "Cureren", "Plannen", "Onderhouden",
          "Verzamelen", "Toetsen", "Publiceren", "Vertalen", "Modereren"]
_OBJ = ["de socials", "de blog", "de nieuwsbrief", "de zoekwoorden", "de concurrenten",
        "de reviews", "de community", "de productpagina", "de roadmap", "de partners"]
_DOMS = ["de blog", "de socials", "het lexicon", "de webshop", "de nieuwsbrief", "de roadmap",
         "de community", "de data", "de partners", "de merkstijl"]
_PURP = ["De markt vóór zijn", "Het merk laten resoneren", "De woordenschat verzorgen",
         "De groei voeden", "De community laten bloeien", "De missie bewaken"]
_REP = ["dit komt structureel terug", "speelt wekelijks", "meermaals voorgekomen",
        "terugkerend patroon", "elke maand weer"]


def _acc(rng): return f"{rng.choice(_VERBS)} van {rng.choice(_OBJ)}"


def base_records(path: str) -> Records:
    """Een kleine, valide startset: wortelcirkel + een paar leaf-rollen met eigen werk/domeinen."""
    recs = Records(path)
    recs.put(Record(id="noochville", type=RecordType.CIRCLE, parent=None,
                    definition=RoleDefinition(purpose="Het duurzaamste schoenenmerk zijn"),
                    members=["scout", "librarian", "analyst"], source="seed"))
    seed = {
        "scout": ("De markt vóór zijn", ["Volgen van de concurrenten"], ["de concurrenten"]),
        "librarian": ("De woordenschat verzorgen", ["Cureren van het lexicon"], ["het lexicon"]),
        "analyst": ("De groei voeden", ["Analyseren van de data"], ["de data"]),
    }
    for rid, (pur, accs, doms) in seed.items():
        recs.put(Record(id=rid, type=RecordType.ROLE, parent="noochville",
                        definition=RoleDefinition(purpose=pur, accountabilities=accs, domains=doms),
                        source="seed"))
    recs.save = lambda: None        # in-memory voor snelheid tijdens de stresstest
    return recs


def _random_proposal(rng, recs: Records) -> Proposal:
    """Genereer één gevarieerd, soms-vals voorstel. Mix van geldig en grensgeval, zodat de poort
    écht werk krijgt."""
    active = [r for r in recs.all() if not r.archived and r.id != "noochville"]
    kind = rng.choices(
        ["add_role", "amend_add_acc", "amend_dup_acc", "amend_rm_acc", "amend_add_dom",
         "amend_dom_clash", "amend_purpose", "rename", "remove", "add_nested"],
        weights=[14, 16, 10, 10, 10, 10, 8, 8, 8, 6])[0]
    by = rng.choice(active).id if active else "founder"
    trig = rng.choice(_REP) if rng.random() < 0.8 else "eenmalig incident"   # 20% zakt op G0
    meta = dict(proposer_role=by, tension="stresstest-spanning",
                trigger_example=trig, rationale="stresstest", source="sensed")

    if kind == "add_role":
        rid = f"rol_{rng.randrange(100000)}"
        return Proposal(change=GovernanceChange(
            kind=ChangeKind.ADD_ROLE, role_id=rid, purpose=rng.choice(_PURP),
            add_accountabilities=[_acc(rng)], add_domains=([rng.choice(_DOMS)] if rng.random() < .5 else []),
            new_role_parent="noochville"), **meta)
    if kind == "add_nested":
        # Nieuwe rol onder een BESTAANDE rol (maakt nesting → test removal-of-parent later).
        parent = rng.choice(active).id if active else "noochville"
        rid = f"sub_{rng.randrange(100000)}"
        return Proposal(change=GovernanceChange(
            kind=ChangeKind.ADD_ROLE, role_id=rid, purpose=rng.choice(_PURP),
            add_accountabilities=[_acc(rng)], new_role_parent=parent), **meta)
    if not active:
        return Proposal(change=GovernanceChange(kind=ChangeKind.ADD_ROLE, role_id="rol_0",
                        purpose="X", add_accountabilities=[_acc(rng)], new_role_parent="noochville"), **meta)
    target = rng.choice(active)
    if kind == "amend_add_acc":
        return Proposal(change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id=target.id,
                        add_accountabilities=[_acc(rng)]), **meta)
    if kind == "amend_dup_acc":
        # Probeer een accountability te kopiëren van een ANDERE rol (moet G2 blokkeren).
        others = [r for r in active if r.id != target.id and r.definition.accountabilities]
        if others:
            donor = rng.choice(others)
            return Proposal(change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id=target.id,
                            add_accountabilities=[rng.choice(donor.definition.accountabilities)]), **meta)
        return Proposal(change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id=target.id,
                        add_accountabilities=[_acc(rng)]), **meta)
    if kind == "amend_rm_acc":
        if target.definition.accountabilities:
            return Proposal(change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id=target.id,
                            remove_accountabilities=[rng.choice(target.definition.accountabilities)]), **meta)
        return Proposal(change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id=target.id,
                        add_accountabilities=[_acc(rng)]), **meta)
    if kind == "amend_add_dom":
        return Proposal(change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id=target.id,
                        add_domains=[f"domein_{rng.randrange(100000)}"]), **meta)
    if kind == "amend_dom_clash":
        others = [r for r in active if r.id != target.id and r.definition.domains]
        if others:
            donor = rng.choice(others)
            return Proposal(change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id=target.id,
                            add_domains=[rng.choice(donor.definition.domains)]), **meta)
        return Proposal(change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id=target.id,
                        add_domains=[rng.choice(_DOMS)]), **meta)
    if kind == "amend_purpose":
        return Proposal(change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id=target.id,
                        purpose=rng.choice(_PURP)), **meta)
    if kind == "rename":
        return Proposal(change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id=target.id,
                        rename=f"Herdoopt {rng.randrange(1000)}"), **meta)
    if kind == "remove":
        return Proposal(change=GovernanceChange(kind=ChangeKind.REMOVE_ROLE, role_id=target.id), **meta)
    return Proposal(change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id=target.id,
                    add_accountabilities=[_acc(rng)]), **meta)


def check_invariants(recs: Records) -> list[str]:
    """Structurele waarheids-checks op de records. Elke regel = een gat (poort liet iets door dat
    de records corrumpeert)."""
    viol: list[str] = []
    by_id = {r.id: r for r in recs.all()}
    active = [r for r in recs.all() if not r.archived]
    # 1. Membership-integriteit: members verwijzen naar bestaande, niet-gearchiveerde records.
    for r in active:
        for m in r.members:
            t = by_id.get(m)
            if t is None:
                viol.append(f"members van '{r.id}' verwijst naar onbestaand record '{m}'")
            elif t.archived:
                viol.append(f"members van '{r.id}' verwijst naar GEARCHIVEERDE rol '{m}'")
    # 2. Geen wezen: elke actieve niet-wortelrol heeft een actieve ouder en staat in diens members.
    for r in active:
        if r.parent is None:
            continue
        p = by_id.get(r.parent)
        if p is None or p.archived:
            viol.append(f"rol '{r.id}' is een wees: ouder '{r.parent}' ontbreekt of is gearchiveerd")
        elif r.id not in p.members:
            viol.append(f"rol '{r.id}' staat niet in members van ouder '{r.parent}'")
    # 3. Geen dubbele accountability over actieve rollen heen.
    seen: dict[str, str] = {}
    for r in active:
        for a in r.definition.accountabilities:
            k = a.strip().lower()
            if k in seen and seen[k] != r.id:
                viol.append(f"dubbele accountability '{a}' bij '{r.id}' én '{seen[k]}'")
            seen.setdefault(k, r.id)
    # 4. Geen overlappend domein over actieve rollen heen.
    dseen: dict[str, str] = {}
    for r in active:
        for d in r.definition.domains:
            k = d.strip().lower()
            if k in dseen and dseen[k] != r.id:
                viol.append(f"overlappend domein '{d}' bij '{r.id}' én '{dseen[k]}'")
            dseen.setdefault(k, r.id)
    # 5. Geen lege purpose bij een actieve rol.
    for r in active:
        if not (r.definition.purpose or "").strip():
            viol.append(f"rol '{r.id}' heeft een lege purpose")
    return viol


def run(n: int = 500, seed: int = 0) -> dict:
    """Draai de stresstest. Geeft een rapport met uitkomsten per poort en de invariant-schendingen."""
    rng = random.Random(seed)
    tmp = os.path.join(tempfile.mkdtemp(), "mc_records.json")
    recs = base_records(tmp)
    gate = Gate()
    sec = Secretary(recs, _NullBus())
    applied = 0
    blocked: dict[str, int] = {}
    kinds: dict[str, int] = {}
    mid_failures: list[str] = []
    for _ in range(n):
        p = _random_proposal(rng, recs)
        kinds[p.change.kind.value] = kinds.get(p.change.kind.value, 0) + 1
        passed, g, _reason = gate.check(p, recs, None)
        if not passed:
            blocked[g] = blocked.get(g, 0) + 1
            continue
        sec._adopt(p)
        applied += 1
        # Incrementele check: na élke adoptie horen de records valide te blijven.
        v = check_invariants(recs)
        if v:
            mid_failures.append(f"na {p.change.kind.value} op '{p.change.role_id}': {v[0]}")
            break
    return {"n": n, "seed": seed, "applied": applied, "blocked_by_gate": blocked,
            "kinds": kinds, "invariant_violations": check_invariants(recs),
            "first_mid_failure": mid_failures[0] if mid_failures else None,
            "active_roles": len([r for r in recs.all() if not r.archived])}


def format_report(rep: dict) -> str:
    lines = [f"🎲 Monte-Carlo governance-stresstest (n={rep['n']}, seed={rep['seed']})",
             f"   toegepast: {rep['applied']} · actieve rollen na afloop: {rep['active_roles']}",
             f"   geblokkeerd per poort: {rep['blocked_by_gate']}",
             f"   voorstel-soorten: {rep['kinds']}"]
    if rep["first_mid_failure"]:
        lines.append(f"   ⛔ EERSTE GAT (tijdens run): {rep['first_mid_failure']}")
    viol = rep["invariant_violations"]
    if viol:
        lines.append(f"   ⛔ {len(viol)} invariant-schending(en) — GATEN gevonden:")
        for v in viol[:15]:
            lines.append(f"      - {v}")
    else:
        lines.append("   ✅ geen invariant-schendingen — de records bleven structureel valide")
    return "\n".join(lines)
