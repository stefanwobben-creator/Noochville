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
    domains: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)   # capability-ids die deze rol energizet


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
