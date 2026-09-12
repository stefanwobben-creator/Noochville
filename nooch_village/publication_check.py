"""De harde publicatie-poort: verboden woorden en ongegronde claim-kaartjes.

Twee bronnen van 'verboden', en ze hebben een verschillende reikwijdte:

1. **De claims-database** (`config/claims_database.json`, compliance-domein): een RODE term is een
   verbod uit EmpCo/ACM/Nooch-beleid en blokkeert in élke publicatiesoort — een blog op nooch.earth
   is óók commerciële communicatie, en de wekelijkse site-scan vlagt hem daar net zo goed. Tot scope
   56 kende deze poort de database niet: twee literals hier, 56 termen daar, en een rode EmpCo-term in
   copy kwam door de eindcheck (skill-review 12-09-2026). Eén termenlijst voor claims_check,
   claims_site_scan én content_check — reference, don't copy.
2. **De beleidswoorden** (`FORBIDDEN_IN_SALES`): 'plastic' en 'leer' zijn geen milieuclaims maar
   missie-woorden (geen plastic, geen leer). Ze blokkeren alleen in de STRIKTE soorten (verkooppagina,
   paspoort): een blog mag uitleggen waarom we geen plastic gebruiken.

Zonder database (ontbrekend of corrupt bestand) vallen alleen de literals terug — en dat is dan
zichtbaar in `PublicationReport.database_ok`, zodat de aanroeper 'niet volledig getoetst' kan melden
in plaats van stil de lichtste poort te draaien.
"""
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


def unverified_claims(insight_ids: list[str], store: NotesStore | None) -> list[ClaimIssue]:
    issues = []
    for id_ in insight_ids:
        if store is None:
            # Fail-closed: zonder store is een kaartje niet te toetsen, en 'niet te toetsen' is
            # geen 'goedgekeurd'. De skill-laag meldt dit apart als 'niet getoetst'.
            issues.append(ClaimIssue(insight_id=id_, reason="niet te toetsen: geen notes-store"))
            continue
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
    # De rode bevindingen uit de claims-database (term, stoplicht, bron, waarom, gevonden…), zodat de
    # skill-laag ze als records mét oordeel en citaat kan tonen — de naam alleen zegt de lezer niets.
    claim_findings: list[dict] = field(default_factory=list)
    # False = de claims-database was niet leesbaar en alleen de literals hebben gedraaid.
    database_ok: bool = True

    @property
    def ok(self) -> bool:
        return not self.forbidden_words and not self.claim_issues


def red_findings(text: str, *, data_dir: str | None = None, db: dict | None = None) -> tuple[list[dict], bool]:
    """De RODE bevindingen van de claims-database over deze tekst, plus of de database leesbaar was.
    Fail-closed op de bron: onleesbaar → ([], False), en de aanroeper zegt dan dat dit deel niet
    getoetst is — nooit stil 'geen bevindingen'."""
    from nooch_village import claims_db
    try:
        uitslag = claims_db.check_tekst(text or "", db=db, data_dir=data_dir)
    except claims_db.ClaimsDbError:
        return [], False
    return [b for b in uitslag.get("bevindingen") or [] if b.get("stoplicht") == "red"], True


def review_publication(
    text: str,
    claim_insight_ids: list[str],
    kind: PublicationKind,
    store: NotesStore | None,
    *,
    data_dir: str | None = None,
    db: dict | None = None,
) -> PublicationReport:
    rood, db_ok = red_findings(text, data_dir=data_dir, db=db)
    if kind in STRICT_KINDS:
        return PublicationReport(forbidden_words=find_forbidden_words(text, FORBIDDEN_IN_SALES, rood=rood),
                                 claim_issues=unverified_claims(claim_insight_ids, store),
                                 claim_findings=rood, database_ok=db_ok)
    # Niet-strikt (blog): de beleidswoorden mogen, de rode claim-termen niet — de wet kent geen
    # publicatiesoort. Kaartjes worden hier niet getoetst (blog is niet streng, bestaand beleid).
    return PublicationReport(forbidden_words=find_forbidden_words(text, [], rood=rood),
                             claim_findings=rood, database_ok=db_ok)


def find_forbidden_words(text: str, words: list[str], *, data_dir: str | None = None,
                         db: dict | None = None, rood: list[dict] | None = None) -> list[str]:
    """De verboden woorden in `text`: de letterlijke `words` (hele woorden, hoofdletter-ongevoelig)
    plus de RODE termen van de claims-database. Zonder leesbare database blijven alleen de literals
    over — het vangnet, en `review_publication` meldt dat dan via `database_ok`.

    `rood` = de al-berekende rode bevindingen (zodat de database niet twee keer gelezen wordt);
    None = hier opzoeken. De beleidswoorden staan vooraan: 'plastic' op een verkooppagina is de
    oudste regel van deze poort."""
    found = []
    for word in words:
        if re.search(rf"\b{re.escape(word)}\b", text, re.IGNORECASE):
            found.append(word)
    if rood is None:
        rood, _ok = red_findings(text, data_dir=data_dir, db=db)
    for b in rood:
        term = str(b.get("term") or "")
        if term and term not in found:
            found.append(term)
    return found
