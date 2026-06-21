from __future__ import annotations
import re
from dataclasses import dataclass, field
from enum import StrEnum
from nooch_village.notes_store import NotesStore
from nooch_village.insight import GroundingStatus

FORBIDDEN_IN_SALES: list[str] = ["plastic", "leer"]


@dataclass
class ClaimIssue:
    insight_id: str
    reason: str


def unverified_claims(insight_ids: list[str], store: NotesStore) -> list[ClaimIssue]:
    issues = []
    for id_ in insight_ids:
        note = store.get(id_)
        if note is None:
            issues.append(ClaimIssue(insight_id=id_, reason="geen kaartje met dit id"))
        elif note.status != GroundingStatus.VERIFIED:
            issues.append(ClaimIssue(insight_id=id_, reason=f"niet verified, status is {note.status}"))
    return issues


class PublicationKind(StrEnum):
    BLOG = "blog"
    SALES_PAGE = "sales_page"
    PASSPORT = "passport"


STRICT_KINDS: set[PublicationKind] = {PublicationKind.SALES_PAGE, PublicationKind.PASSPORT}


@dataclass
class PublicationReport:
    forbidden_words: list[str] = field(default_factory=list)
    claim_issues: list[ClaimIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.forbidden_words and not self.claim_issues


def review_publication(
    text: str,
    claim_insight_ids: list[str],
    kind: PublicationKind,
    store: NotesStore,
) -> PublicationReport:
    if kind in STRICT_KINDS:
        return PublicationReport(
            forbidden_words=find_forbidden_words(text, FORBIDDEN_IN_SALES),
            claim_issues=unverified_claims(claim_insight_ids, store),
        )
    return PublicationReport()


def find_forbidden_words(text: str, words: list[str]) -> list[str]:
    found = []
    for word in words:
        if re.search(rf"\b{re.escape(word)}\b", text, re.IGNORECASE):
            found.append(word)
    return found
