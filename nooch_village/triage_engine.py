"""TriageEngine — pure classificatie van spanningen.

Neemt een spanning (als lowercase string) plus de smalle TriageContext in
en geeft een TriageResult terug. Geen bus, geen threads, geen I/O.
Inhabitant.triage() is een dunne facade die context opbouwt en dan actie neemt
op basis van het resultaat.
"""
from __future__ import annotations
from dataclasses import dataclass, field

# Trefwoorden die duiden op een structurele, terugkerende spanning
STRUCTURAL_KW = frozenset([
    "voortaan", "altijd", "elke keer", "niemand bezit", "niemand heeft",
    "niemand pakt", "ontbreekt", "terugkerend", "structureel", "policy",
    "accountability", "nooit belegd", "verwacht wordt", "structuur",
    "verwacht dat", "zou moeten", "onbeheerd",
])


@dataclass
class TriageContext:
    """Smalle context die TriageEngine nodig heeft — geen bus, registry of context-object."""
    role_id: str
    purpose: str
    accountabilities: list[str]
    domains: list[str] = field(default_factory=list)
    records: object = None  # Records | object met .all() -> Iterable[Record]


@dataclass
class TriageResult:
    classification: str         # "structureel" | "eigen-werk" | "andere-rol:<id>" | "tactisch"
    target_role_id: str | None = None
    target_capability: str | None = None


class TriageEngine:
    """Pure spannings-classifier. Instantieer één keer en hergebruik."""

    def classify(self, desc_l: str, ctx: TriageContext,
                 llm_result: str | None = None) -> TriageResult:
        """Classificeer een spanning.

        desc_l     : lowercased spanning-beschrijving
        ctx        : smalle context over de rol en het dorp
        llm_result : pre-computed LLM-uitkomst ('structural','own',<rol_id>,'tactical',None)
        """
        if llm_result == "structural" or (llm_result is None and self._is_structural(desc_l)):
            return TriageResult(classification="structureel")

        if llm_result == "own" or (llm_result is None and self._fits_own_role(desc_l, ctx)):
            return TriageResult(classification="eigen-werk")

        if llm_result and llm_result not in ("tactical", "own", "structural"):
            role_id = llm_result
            cap = self._capability_for_role(role_id, ctx.records)
            return TriageResult(
                classification=f"andere-rol:{role_id}",
                target_role_id=role_id,
                target_capability=cap,
            )

        role_id, cap = self._find_other_role(desc_l, ctx)
        if role_id:
            return TriageResult(
                classification=f"andere-rol:{role_id}",
                target_role_id=role_id,
                target_capability=cap,
            )

        return TriageResult(classification="tactisch")

    # ── Classificatie-helpers ────────────────────────────────────────────────

    def _is_structural(self, desc_l: str) -> bool:
        return any(kw in desc_l for kw in STRUCTURAL_KW)

    def _fits_own_role(self, desc_l: str, ctx: TriageContext) -> bool:
        own = (ctx.purpose + " " + " ".join(ctx.accountabilities)).lower()
        for word in desc_l.split():
            if len(word) >= 6 and word in own:
                return True
        for word in own.split():
            if len(word) >= 6 and word in desc_l:
                return True
        return False

    def _find_other_role(self, desc_l: str, ctx: TriageContext) -> tuple[str | None, str | None]:
        if ctx.records is None:
            return None, None
        desc_words = {w for w in desc_l.split() if len(w) >= 6}
        for rec in ctx.records.all():
            if rec.id == ctx.role_id or rec.archived:
                continue
            for domain in rec.definition.domains:
                if domain.lower() in desc_l:
                    cap = rec.definition.skills[0] if rec.definition.skills else None
                    return rec.id, cap
            acc_text  = " ".join(rec.definition.accountabilities).lower()
            acc_words = {w for w in acc_text.split() if len(w) >= 6}
            if acc_words & desc_words:
                cap = rec.definition.skills[0] if rec.definition.skills else None
                return rec.id, cap
        return None, None

    def _capability_for_role(self, role_id: str, records) -> str | None:
        if records is None:
            return None
        rec = records.get(role_id)
        if rec and rec.definition.skills:
            return rec.definition.skills[0]
        return None


# Module-level singleton — stateless, veilig om te delen
_ENGINE = TriageEngine()


def classify(desc_l: str, ctx: TriageContext, llm_result: str | None = None) -> TriageResult:
    """Convenience-wrapper voor de module-level engine."""
    return _ENGINE.classify(desc_l, ctx, llm_result)
