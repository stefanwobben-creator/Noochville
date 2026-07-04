from __future__ import annotations
import json, os, logging, dataclasses, time
from nooch_village.util import atomic_write_json
from nooch_village.models import (
    Record, RoleDefinition, RecordType,
    Proposal, GovernanceChange, ChangeKind,
)
from nooch_village.event_bus import EventBus, Event

log = logging.getLogger("village.governance")

# Trefwoorden die herhalingsbewijs aantonen (vereist voor add_role)
_REPETITION_KW = frozenset([
    "meermaals", "herhaald", "herhaaldelijk", "elke keer", "meerdere keren",
    "meerdere incidenten", "structureel", "terugkerend", "wekelijks", "dagelijks",
    "maandelijks", "voortdurend", "steeds", "meerdere malen", "chronisch",
    "elke week", "elke maand", "elke dag", "regelmatig",
    # doorlopende/staande work — evengoed bewijs van een beoogde permanente accountability
    "doorlopend", "periodiek", "staande", "continu",
])


# ── Serialisatie ───────────────────────────────────────────────────────────────

def proposal_to_dict(p: Proposal) -> dict:
    c = p.change
    return {
        "id": p.id,
        "proposer_role": p.proposer_role,
        "tension": p.tension,
        "trigger_example": p.trigger_example,
        "rationale": p.rationale,
        "status": p.status,
        "created_at": p.created_at,
        "escalation_gate": p.escalation_gate,
        "escalation_reason": p.escalation_reason,
        "source": p.source,
        "hypothesis": p.hypothesis,
        "business_case": p.business_case,
        "change": {
            "kind": c.kind.value,
            "role_id": c.role_id,
            "purpose": c.purpose,
            "add_accountabilities": c.add_accountabilities,
            "remove_accountabilities": c.remove_accountabilities,
            "add_domains": c.add_domains,
            "remove_domains": c.remove_domains,
            "add_skills": c.add_skills,
            "remove_skills": c.remove_skills,
            "new_role_parent": c.new_role_parent,
            "policy_id": c.policy_id,
            "policy_text": c.policy_text,
            "rename": c.rename,
        },
    }


def proposal_from_dict(d: dict) -> Proposal:
    c = d["change"]
    return Proposal(
        proposer_role=d["proposer_role"],
        change=GovernanceChange(
            kind=ChangeKind(c["kind"]),
            role_id=c.get("role_id"),
            purpose=c.get("purpose"),
            add_accountabilities=c.get("add_accountabilities", []),
            remove_accountabilities=c.get("remove_accountabilities", []),
            add_domains=c.get("add_domains", []),
            remove_domains=c.get("remove_domains", []),
            add_skills=c.get("add_skills", []),
            remove_skills=c.get("remove_skills", []),
            new_role_parent=c.get("new_role_parent"),
            policy_id=c.get("policy_id"),
            policy_text=c.get("policy_text"),
            rename=c.get("rename"),
        ),
        tension=d["tension"],
        trigger_example=d["trigger_example"],
        rationale=d["rationale"],
        id=d["id"],
        status=d.get("status", "pending"),
        created_at=d.get("created_at", time.time()),
        escalation_gate=d.get("escalation_gate"),
        escalation_reason=d.get("escalation_reason"),
        source=d.get("source", "sensed"),
        hypothesis=d.get("hypothesis", ""),
        business_case=d.get("business_case"),
    )


# ── Poort G0-G4 ───────────────────────────────────────────────────────────────

class Gate:
    """Goedkoop-eerst, deterministisch. Retourneert (passed, gate_name, reason).
    Default is aannemen; we escaleren alleen bij structurele schade of missie-risico."""

    def check(self, proposal: Proposal, records: "Records",
              context=None) -> tuple[bool, str | None, str | None]:
        for gate, fn in [
            ("G0", self._g0),
            ("G1", lambda p, r, _: self._g1(p.change, r)),
            ("G2", lambda p, r, _: self._g2(p.change, r)),
            ("G3", lambda p, r, _: self._g3(p.change, r)),
            ("G4", self._g4),
        ]:
            passed, reason = fn(proposal, records, context)
            if not passed:
                return False, gate, reason
        return True, None, None

    # G0: structurele geldigheid — verplichte velden + kind binnen scope
    def _g0(self, p: Proposal, _records, _ctx) -> tuple[bool, str]:
        if not all([p.proposer_role, p.tension, p.trigger_example, p.rationale]):
            return False, "verplichte velden ontbreken (proposer_role, tension, trigger_example, rationale)"
        c = p.change
        try:
            ChangeKind(c.kind)
        except ValueError:
            return False, f"ongeldig change.kind: '{c.kind}'"
        if c.kind in (ChangeKind.AMEND_ROLE, ChangeKind.REMOVE_ROLE) and not c.role_id:
            return False, f"{c.kind.value} vereist role_id"
        if c.kind == ChangeKind.ADD_ROLE and not (c.role_id and c.purpose):
            return False, "add_role vereist role_id en purpose"
        if c.kind == ChangeKind.ADD_ROLE:
            # Herhalingsbewijs moet in de TRIGGER staan (de waargenomen feiten uit
            # het logboek), niet in de rationale. De rationale is de zelfgeschreven
            # argumentatie van de proposer; die als bewijs accepteren maakte de poort
            # tandeloos (de C-weg vulde 'm met "structureel terugkerend").
            trigger = p.trigger_example.lower()
            if not any(kw in trigger for kw in _REPETITION_KW):
                return False, (
                    "add_role vereist herhalingsbewijs in trigger_example "
                    "(bijv. 'meermaals', 'terugkerend', 'structureel', 'wekelijks'); "
                    "één incident is onvoldoende grond voor een nieuwe rol"
                )
            # Weiger mechanische term-smurrie als purpose ("Beheert en bewaakt X, Y").
            # Een rol-purpose hoort een betekenisvolle functie te beschrijven.
            if c.purpose.strip().lower().startswith("beheert en bewaakt "):
                return False, (
                    "add_role-purpose is een mechanische term-opsomming "
                    f"('{c.purpose[:50]}…'); beschrijf een echte functie, geen woordcluster"
                )
        if c.kind in (ChangeKind.ADD_POLICY, ChangeKind.AMEND_POLICY,
                      ChangeKind.REMOVE_POLICY) and not c.policy_id:
            return False, f"{c.kind.value} vereist policy_id"
        return True, ""

    # G1: domein-botsing
    def _g1(self, c: GovernanceChange, records: "Records") -> tuple[bool, str]:
        if not c.add_domains:
            return True, ""
        new = {d.lower() for d in c.add_domains}
        for rec in records.all():
            if rec.archived or rec.id == c.role_id or rec.source == "demo":
                continue
            overlap = new & {d.lower() for d in rec.definition.domains}
            if overlap:
                return False, f"domein {overlap} overlapt met domeinen van rol '{rec.id}'"
        return True, ""

    # G2: accountability-duplicaat bij een andere rol
    def _g2(self, c: GovernanceChange, records: "Records") -> tuple[bool, str]:
        if not c.add_accountabilities:
            return True, ""
        new = [a.lower() for a in c.add_accountabilities]
        for rec in records.all():
            if rec.archived or rec.id == c.role_id or rec.source == "demo":
                continue
            for existing in rec.definition.accountabilities:
                el = existing.lower()
                for na in new:
                    if el == na or na in el or el in na:
                        return False, (f"accountability '{na}' overlapt met die van "
                                       f"'{rec.id}': '{existing}'")
        return True, ""

    # G3: verweesd werk — verwijdering zonder elders te beleggen
    def _g3(self, c: GovernanceChange, records: "Records") -> tuple[bool, str]:
        if c.kind == ChangeKind.REMOVE_ROLE:
            rec = records.get(c.role_id)
            # Een rol/cirkel met onderliggende rollen verwijderen zou die kinderen tot wezen maken
            # (ouder weg → dangling members). Eerst de kinderen herbeleggen → menselijk oordeel.
            if rec:
                kids = [m for m in rec.members
                        if (k := records.get(m)) and not k.archived]
                if kids:
                    return False, (f"rol '{c.role_id}' is een cirkel met onderliggende rollen "
                                   f"({kids[:3]} …); verwijderen zou die tot wees maken — "
                                   f"herbeleg de kinderen eerst (menselijke beoordeling vereist)")
            if rec and rec.definition.accountabilities:
                accs = rec.definition.accountabilities[:2]
                return False, (f"rol '{c.role_id}' heeft accountabilities ({accs} …); "
                               f"de gate kan niet vaststellen of dit werk elders belegd is — "
                               f"menselijke beoordeling vereist")
        # Verwijderde accountabilities zonder ze elders te beleggen = mogelijk verweesd werk.
        # MAAR: voegt dezelfde wijziging óók accountabilities toe aan de rol, dan is dit een
        # HERSCHRIJVING/HERSCHIKKING binnen de rol (geen orphaning) — die laten we door. De
        # orphan-check geldt dus alleen bij een PURE verwijdering (niets toegevoegd in dezelfde change).
        if c.remove_accountabilities and not c.add_accountabilities:
            removed = {a.lower() for a in c.remove_accountabilities}
            covered = set()
            for rec in records.all():
                if rec.archived or rec.id == c.role_id:
                    continue
                for acc in rec.definition.accountabilities:
                    for rm in removed:
                        if rm in acc.lower() or acc.lower() in rm:
                            covered.add(rm)
            orphaned = removed - covered
            if orphaned:
                return False, f"accountabilities {orphaned} worden verwijderd maar nergens belegd"
        return True, ""

    # G4: missie-poort — deterministisch + optioneel LLM bij twijfel
    def _g4(self, p: Proposal, records: "Records", context) -> tuple[bool, str]:
        # Missie-handhaving zit bewust NIET in de poort: de richting leeft in de missie/visie en de
        # statuten (art. 2a), en waar het praktisch nodig is in domein-policies die via de juiste
        # governance-route ontstaan. G4 bewaakt daarom alleen dat de anchor-purpose mens-eigendom is:
        # een structuurwijziging van de wortelcirkel escaleert altijd naar de mens. Geen verstopte
        # tweede handhavingslaag (regex/LLM) meer.
        c = p.change
        if c.purpose and c.role_id:
            root = records.root() if records else None
            if root and c.role_id == root.id:
                return False, (
                    "Anchor Circle purpose is mens-eigendom (founder-only); "
                    "structuurwijzigingen van de wortelcirkel escaleren altijd naar de mens"
                )
        return True, ""


class Records:
    """De governance-records: de enige bron van waarheid over wie bestaat en wat ze mogen."""

    def __init__(self, path: str):
        self.path = path
        self._data: dict[str, Record] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        raw = json.load(open(self.path))
        for rid, r in raw.items():
            self._data[rid] = Record(
                id=r["id"], type=RecordType(r["type"]), parent=r["parent"],
                definition=RoleDefinition(**r["definition"]),
                members=r.get("members", []), version=r.get("version", 1),
                archived=r.get("archived", False),
                source=r.get("source", "sensed"),
                persona=r.get("persona"),
                persona_id=r.get("persona_id"),
                held_by=r.get("held_by"))

    def save(self) -> None:
        out = {}
        for rid, r in self._data.items():
            d = dataclasses.asdict(r)
            d["type"] = r.type.value
            out[rid] = d
        atomic_write_json(self.path, out)

    def all(self):
        return list(self._data.values())

    def get(self, rid):
        return self._data.get(rid)

    def put(self, record: Record) -> None:
        self._data[record.id] = record
        self.save()

    def set_holder(self, role_id: str, name: str | None) -> bool:
        """Leg vast welke mens een rol bezet (bv. de founder in the_source). Een door-mens-
        bemenste rol: een legitieme zetel, geen code-thread. Geeft False als de rol niet bestaat."""
        rec = self._data.get(role_id)
        if rec is None:
            return False
        rec.held_by = name
        self.save()
        return True

    def set_persona(self, role_id: str, persona_id: str | None) -> bool:
        """Koppel een inwoner (data/personas.json) aan een rol, of ontkoppel (persona_id=None).
        Het karakter dat de rol vervult; de skills/rugzak blijven van de rol. Geeft False als de
        rol niet bestaat. (Validatie dat de inwoner bestaat doet de aanroeper.)"""
        rec = self._data.get(role_id)
        if rec is None:
            return False
        rec.persona_id = persona_id or None
        self.save()
        return True

    def root(self):
        for r in self._data.values():
            if r.parent is None and not r.archived:
                return r
        return None


class Secretary:
    """Bezit de records en de adoptie-schrijfactie. Heeft GEEN veto:
    de Facilitator heeft de poort al gedraaid. De Secretary schrijft alleen."""

    def __init__(self, records: Records, bus: EventBus):
        self.records = records
        self.bus = bus
        self._pending: dict[str, Proposal] = {}   # proposal_id → Proposal (wacht op menselijk verdict)
        bus.subscribe("propose_amendment", self._on_legacy_amendment)  # legacy: directe amendementen
        bus.subscribe("proposal_gate_passed", self._on_gate_passed)
        bus.subscribe("governance_verdict", self._on_governance_verdict)
        bus.subscribe("_store_pending_proposal", lambda e: self.store_pending(
            proposal_from_dict(e.data["proposal"])))

    # ── Legacy: directe propose_amendment (voor backward compat) ──────────────
    def _on_legacy_amendment(self, e: Event) -> None:
        rid = e.data["record_id"]
        new_skills = e.data.get("add_skills", [])
        new_accs = e.data.get("add_accountabilities", [])
        record = self.records.get(rid)
        if record is None:
            self._reject_legacy(rid, "record bestaat niet"); return
        for acc in new_accs:
            if len(acc.split()) < 2:
                self._reject_legacy(rid, f"accountability '{acc}' is te kort"); return
        d = record.definition
        d.skills = sorted(set(d.skills) | set(new_skills))
        d.accountabilities = sorted(set(d.accountabilities) | set(new_accs))
        record.version += 1
        self.records.put(record)
        log.info("legacy-amendement aangenomen voor '%s' -> v%s", rid, record.version)
        self.bus.publish(Event("role_adopted", {"record_id": rid}, "Secretary"))

    def _reject_legacy(self, rid, reason):
        log.warning("legacy-amendement afgewezen voor '%s': %s", rid, reason)
        self.bus.publish(Event("proposal_rejected", {"record_id": rid, "reason": reason}, "Secretary"))

    # ── Nieuw governance-pad: Facilitator heeft de poort gedraaid ─────────────
    def _on_gate_passed(self, e: Event) -> None:
        proposal = proposal_from_dict(e.data["proposal"])
        self._adopt(proposal)

    def _on_governance_verdict(self, e: Event) -> None:
        """Menselijk oordeel na escalatie: approve of reject."""
        pid = e.data.get("proposal_id")
        decision = e.data.get("decision", "reject")
        proposal = self._pending.pop(pid, None)
        if proposal is None:
            log.warning("governance_verdict voor onbekend voorstel '%s'", pid)
            return
        if decision == "approve":
            log.info("👤 mens keurde voorstel %s goed", pid)
            self._adopt(proposal)
        else:
            proposal.status = "rejected"
            log.info("👤 mens wees voorstel %s af", pid)
            self.bus.publish(Event("governance_rejected", {
                "proposal_id": pid, "by": "human", "reason": e.data.get("reason", "")
            }, "Secretary"))

    def store_pending(self, proposal: Proposal) -> None:
        """Facilitator slaat een geëscaleerd voorstel op zodat governance_verdict het kan vinden."""
        self._pending[proposal.id] = proposal

    def _adopt(self, proposal: Proposal) -> None:
        """Schrijft de change naar de records (Secretary bezit de records)."""
        c = proposal.change
        log.info("✅ governance aangenomen: %s (voorstel %s)", c.kind.value, proposal.id)

        if c.kind == ChangeKind.AMEND_ROLE:
            rec = self.records.get(c.role_id)
            if rec is None:
                log.error("adopt AMEND_ROLE: record '%s' niet gevonden", c.role_id)
                return
            d = rec.definition
            if c.add_accountabilities:
                d.accountabilities = sorted(set(d.accountabilities) | set(c.add_accountabilities))
            if c.remove_accountabilities:
                d.accountabilities = [a for a in d.accountabilities
                                       if a not in c.remove_accountabilities]
            if c.add_domains:
                d.domains = sorted(set(d.domains) | set(c.add_domains))
            if c.remove_domains:
                d.domains = [a for a in d.domains if a not in c.remove_domains]
            if c.add_skills:
                d.skills = sorted(set(d.skills) | set(c.add_skills))
            if c.remove_skills:
                d.skills = [a for a in d.skills if a not in c.remove_skills]
            if c.purpose:
                d.purpose = c.purpose
            if c.rename and c.rename.strip():
                d.name = c.rename.strip()              # weergavenaam; record-id blijft stabiel
            rec.version += 1
            self.records.put(rec)
            self.bus.publish(Event("role_adopted", {"record_id": c.role_id}, "Secretary"))

        elif c.kind == ChangeKind.ADD_ROLE:
            parent_id = c.new_role_parent or (self.records.root().id if self.records.root() else None)
            new_rec = Record(id=c.role_id, type=RecordType.ROLE, parent=parent_id,
                             definition=RoleDefinition(
                                 purpose=c.purpose or "Nieuwe rol",
                                 accountabilities=c.add_accountabilities,
                                 domains=c.add_domains, skills=c.add_skills),
                             source=proposal.source)
            self.records.put(new_rec)
            parent = self.records.get(parent_id) if parent_id else None
            if parent and c.role_id not in parent.members:
                parent.members.append(c.role_id)
                self.records.put(parent)
            # Groeidagboek: geboorte-event met audittrail
            self.bus.publish(Event("role_born", {
                "role_id": c.role_id,
                "purpose": c.purpose,
                "accountabilities": c.add_accountabilities,
                "trigger_example": proposal.trigger_example,
                "rationale": proposal.rationale,
                "by": proposal.proposer_role,
            }, "Secretary"))

        elif c.kind == ChangeKind.REMOVE_ROLE:
            rec = self.records.get(c.role_id)
            if rec:
                rec.archived = True
                rec.version += 1
                self.records.put(rec)
                # Prune uit de ouder-cirkel: een gearchiveerde rol mag geen dangling
                # member-ref achterlaten (records-drift). De Reconciler bouwt het
                # dorp uit members; een verwijzing naar een archief-record is rommel.
                parent = self.records.get(rec.parent) if rec.parent else None
                if parent and c.role_id in parent.members:
                    parent.members = [m for m in parent.members if m != c.role_id]
                    parent.version += 1
                    self.records.put(parent)

        elif c.kind in (ChangeKind.ADD_POLICY, ChangeKind.AMEND_POLICY, ChangeKind.REMOVE_POLICY):
            root = self.records.root()
            if root is None:
                return
            if c.kind == ChangeKind.ADD_POLICY and c.policy_text:
                if c.policy_text not in root.definition.policies:
                    root.definition.policies.append(c.policy_text)
            elif c.kind == ChangeKind.AMEND_POLICY and c.policy_id and c.policy_text:
                root.definition.policies = [
                    c.policy_text if p.startswith(c.policy_id) else p
                    for p in root.definition.policies]
            elif c.kind == ChangeKind.REMOVE_POLICY and c.policy_id:
                root.definition.policies = [
                    p for p in root.definition.policies if not p.startswith(c.policy_id)]
            root.version += 1
            self.records.put(root)

        self.bus.publish(Event("governance_changed", {
            "proposal_id": proposal.id,
            "kind": c.kind.value,
            "role_id": c.role_id,
            "by": proposal.proposer_role,
            "trigger_example": proposal.trigger_example,
        }, "Secretary"))


class Reconciler:
    """Bouwt het levende dorp uit de records en houdt het in lijn na governance-wijzigingen."""

    def __init__(self, records, bus, registry, context, matchmaker, class_map=None):
        self.records = records
        self.bus = bus
        self.registry = registry
        self.context = context
        self.matchmaker = matchmaker
        self.class_map = class_map or {}     # record-id -> Inhabitant-subklasse
        self.live: dict = {}
        self.unmanned: dict = {}             # rollen born maar zonder implementatie
        bus.subscribe("role_adopted", self._on_adopted)
        bus.subscribe("governance_changed", self._on_governance_changed)

    def build(self):
        root = self.records.root()
        if root is None:
            log.warning("geen wortelcirkel in records"); return None
        return self._materialize(root)

    def _materialize(self, record):
        from nooch_village.inhabitant import Inhabitant, Circle
        if record.type == RecordType.CIRCLE:
            circle = Circle(record, self.bus, self.registry, self.context)
            self.live[record.id] = circle
            for mid in record.members:
                mr = self.records.get(mid)
                if mr and not mr.archived:
                    member = self._materialize(mr)
                    if member is not None:           # None = onbemand
                        circle.add_member(member)
                        self.matchmaker.register(member)
            self.matchmaker.register(circle)
            return circle
        # Rol: bestaat er een implementatie (CLASS_MAP) of een actieve skill?
        inh_cls = self.class_map.get(record.id)
        if inh_cls is None:
            has_active = any(self.registry.get(s) is not None for s in record.definition.skills)
            if not has_active:
                self.unmanned[record.id] = record
                log.info("rol '%s' onbemand [source=%s] (geen CLASS_MAP entry en geen actieve skills)",
                         record.id, record.source)
                return None
            inh_cls = Inhabitant
        inh = inh_cls(record, self.bus, self.registry, self.context)
        self.live[record.id] = inh
        log.info("rol '%s' [source=%s] gematerialiseerd", record.id, record.source)
        return inh

    def _on_adopted(self, e):
        rid = e.data["record_id"]
        record = self.records.get(rid)
        if record is None:
            return
        if rid in self.live:                       # bestaande inwoner: herlaad DNA, geen respawn
            self.live[rid].reload(record)
            self.matchmaker.register(self.live[rid])

    def _on_governance_changed(self, e):
        """Verwerkt governance_changed voor wijzigingen buiten de amend_role-stroom."""
        kind = e.data.get("kind")
        rid = e.data.get("role_id")
        if kind == "add_role" and rid and rid not in self.live:
            record = self.records.get(rid)
            if record:
                if rid in self.class_map:
                    # Implementatie beschikbaar: activeer als live inwoner
                    from nooch_village.inhabitant import Inhabitant
                    inh_cls = self.class_map[rid]
                    inh = inh_cls(record, self.bus, self.registry, self.context)
                    self.live[rid] = inh
                    self.matchmaker.register(inh)
                    if not inh.is_alive():
                        inh.start()
                    log.info("nieuwe inwoner '%s' gestart na governance_changed", rid)
                else:
                    # Onbemand geboren: record bestaat, geen thread tot menselijke activatie
                    self.unmanned[rid] = record
                    log.info("rol '%s' geboren maar onbemand (wacht op implementatie in CLASS_MAP)", rid)
        elif kind == "remove_role" and rid:
            inh = self.live.pop(rid, None)
            if inh is not None:
                try:
                    inh.stop()
                except Exception:
                    pass
                log.info("inwoner '%s' gestopt na remove_role governance_changed", rid)
            self.unmanned.pop(rid, None)
