from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
import uuid, time


class RecordType(str, Enum):
    ROLE = "role"
    CIRCLE = "circle"


@dataclass
class RoleDefinition:
    """Het DNA van een rol. Wordt alleen via governance gewijzigd."""
    purpose: str
    accountabilities: list[str] = field(default_factory=list)
    # Stabiele ids, positioneel parallel aan `accountabilities`. Koppelingen (AI-taken,
    # skill-links) verwijzen hiernaar, nooit naar de index — zie acc_ids.py.
    accountability_ids: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)   # capability-ids die deze rol energizet
    policies: list[str] = field(default_factory=list)  # harde policies (alleen voor anchor-cirkel)
    name: str = ""                                     # weergavenaam; leeg = val terug op record-id


@dataclass
class Record:
    """De waarheid. Een levende inwoner is een projectie hiervan."""
    id: str
    type: RecordType
    parent: Optional[str]                              # ouder-cirkel; None = wortel
    definition: RoleDefinition
    members: list[str] = field(default_factory=list)   # alleen bij een cirkel
    version: int = 1
    archived: bool = False
    source: str = "sensed"   # "seed" | "sensed" | "demo" — herkomst van het record
    persona: Optional[str] = None  # (afbouwend) losse weergavenaam; vervangen door persona_id
    persona_id: Optional[str] = None  # toegewezen inwoner (data/personas.json) — het karakter
    held_by: Optional[str] = None  # mens die deze rol bezet (bv. de founder in the_source):
    #                                een door-mens-bemenste rol, geen code-thread


@dataclass
class Task:
    capability: str
    payload: dict
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    request_id: Optional[str] = None
    addressee: Optional[str] = None


@dataclass
class Response:
    success: bool
    data: Any = None
    error: Optional[str] = None


@dataclass
class Tension:
    sensed_by: str
    description: str
    kind: str = "operational"                          # of "governance"
    at: float = field(default_factory=time.time)
    # Verifieerbaar herhalingsbewijs uit het logboek (reflect_<rol>.json):
    # {"observations": int, "first_seen": float, "gap_key": str}. Gevuld door
    # _sense_gap bij emit; de poort (G0) leest dit i.p.v. een zelfgeschreven woord.
    evidence: Optional[dict] = None


# ── Governance-voorstel ────────────────────────────────────────────────────────

class ChangeKind(str, Enum):
    ADD_ROLE = "add_role"
    AMEND_ROLE = "amend_role"
    REMOVE_ROLE = "remove_role"
    ADD_POLICY = "add_policy"
    AMEND_POLICY = "amend_policy"
    REMOVE_POLICY = "remove_policy"


@dataclass
class GovernanceChange:
    """Getagde structuur: uitsluitend wat governance mag wijzigen."""
    kind: ChangeKind
    role_id: Optional[str] = None
    purpose: Optional[str] = None
    add_accountabilities: list[str] = field(default_factory=list)
    remove_accountabilities: list[str] = field(default_factory=list)
    add_domains: list[str] = field(default_factory=list)
    remove_domains: list[str] = field(default_factory=list)
    add_skills: list[str] = field(default_factory=list)
    remove_skills: list[str] = field(default_factory=list)
    new_role_parent: Optional[str] = None   # voor add_role: ouder-cirkel
    policy_id: Optional[str] = None         # voor policy-wijzigingen
    policy_text: Optional[str] = None
    rename: Optional[str] = None            # voor amend_role: nieuwe weergavenaam van de rol


@dataclass
class Proposal:
    """Een voorstel tot governance-wijziging met volledige audittrail."""
    proposer_role: str
    change: GovernanceChange
    tension: str
    trigger_example: str    # id of payload van het event/record dat de spanning veroorzaakte
    rationale: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: str = "pending"  # pending | adopted | escalated | rejected
    created_at: float = field(default_factory=time.time)
    escalation_gate: Optional[str] = None
    escalation_reason: Optional[str] = None
    source: str = "sensed"  # "seed" | "sensed" | "demo" — herkomst van het voorstel
    hypothesis: str = ""              # toetsbare aanname: "als we X, dan Y omdat Z"
    business_case: Optional[dict] = None  # {metric, effect, effort, confidence, horizon, rationale}
