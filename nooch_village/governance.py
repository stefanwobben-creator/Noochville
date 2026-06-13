from __future__ import annotations
import json, os, logging, dataclasses
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus, Event

log = logging.getLogger("village.governance")


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
                archived=r.get("archived", False))

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        out = {}
        for rid, r in self._data.items():
            d = dataclasses.asdict(r)
            d["type"] = r.type.value
            out[rid] = d
        json.dump(out, open(self.path, "w"), indent=2, ensure_ascii=False)

    def all(self):
        return list(self._data.values())

    def get(self, rid):
        return self._data.get(rid)

    def put(self, record: Record) -> None:
        self._data[record.id] = record
        self.save()

    def root(self):
        for r in self._data.values():
            if r.parent is None and not r.archived:
                return r
        return None


class Secretary:
    """Houdt de records bij en interpreteert de structuur. Heeft GEEN veto:
    een voorstel wordt aangenomen tenzij het structureel ongeldig is. (De volledige
    IDM-objectronde is de volgende laag; dit is de structurele poort.)"""

    def __init__(self, records: Records, bus: EventBus):
        self.records = records
        self.bus = bus
        bus.subscribe("propose_amendment", self._on_proposal)

    def _on_proposal(self, e: Event) -> None:
        rid = e.data["record_id"]
        new_skills = e.data.get("add_skills", [])
        new_accs = e.data.get("add_accountabilities", [])
        record = self.records.get(rid)
        if record is None:
            self._reject(rid, "record bestaat niet"); return
        for acc in new_accs:
            if len(acc.split()) < 2:
                self._reject(rid, f"accountability '{acc}' is te kort"); return
        d = record.definition
        d.skills = sorted(set(d.skills) | set(new_skills))
        d.accountabilities = sorted(set(d.accountabilities) | set(new_accs))
        record.version += 1
        self.records.put(record)
        log.info("voorstel aangenomen voor '%s' -> v%s", rid, record.version)
        self.bus.publish(Event("role_adopted", {"record_id": rid}, "Secretary"))

    def _reject(self, rid, reason):
        log.warning("voorstel afgewezen voor '%s': %s", rid, reason)
        self.bus.publish(Event("proposal_rejected", {"record_id": rid, "reason": reason}, "Secretary"))


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
        bus.subscribe("role_adopted", self._on_adopted)

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
                    circle.add_member(member)
                    self.matchmaker.register(member)
            self.matchmaker.register(circle)
            return circle
        inh_cls = self.class_map.get(record.id, Inhabitant)
        inh = inh_cls(record, self.bus, self.registry, self.context)
        self.live[record.id] = inh
        return inh

    def _on_adopted(self, e):
        rid = e.data["record_id"]
        record = self.records.get(rid)
        if record is None:
            return
        if rid in self.live:                       # bestaande inwoner: herlaad DNA, geen respawn
            self.live[rid].reload(record)
            self.matchmaker.register(self.live[rid])
