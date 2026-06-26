"""Keyword-intake: bied een lijst kandidaat-woorden aan de Librarian-review aan, ook buiten de
village-puls om (bijv. vanuit een project-gesprek in de cockpit).

Waarom dit bestaat: de ontdekkings→review-lus (Trends/GSC/ngram → keyword_proposed → Librarian →
keyword_review → library) draait alleen tijdens een village-puls. Een rol die in een project tekst
met zoekwoorden oplevert, voedt die lus NIET — de woorden bleven hangen als tekst. Deze module
sluit dat gat: dezelfde KeywordReviewSkill + dezelfde curatie (approved/forbidden/escalated), zodat
woorden echt in de bibliotheek landen en zichtbaar worden (o.a. 'escalated' = ter review).
"""
from __future__ import annotations
import os
import re
import types

_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+(.+)$")


def extract_candidates(text: str, *, limit: int = 40) -> list[str]:
    """Haal kandidaat-zoekwoorden uit vrije tekst (bv. een rol-oplevering): opsommingsregels,
    geen kopjes/markdown-vet, hooguit ~8 woorden per term. Dedup, volgorde behouden."""
    out, seen = [], set()
    for line in (text or "").splitlines():
        m = _BULLET.match(line)
        if not m:
            continue
        term = m.group(1).strip().strip("*_`\"' ").strip()
        term = re.sub(r"\s*\([^)]*\)\s*$", "", term)        # trailing parentheticals weg
        if not term or term.endswith(":") or len(term.split()) > 8 or len(term) < 3:
            continue
        if term.startswith("**") or "**" in term:
            continue
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(term)
        if len(out) >= limit:
            break
    return out


def review_words(words, dd: str, *, settings: dict | None = None) -> dict:
    """Draai de Librarian-review (KeywordReviewSkill) op elk woord en cureer de bibliotheek. Geeft
    een samenvatting {reviewed, approved, forbidden, escalated, known, per_word}. Geen LLM/keys →
    fail-closed naar de heuristiek (missie-poort). De woorden landen in data/library.json."""
    from nooch_village.library import Library
    from nooch_village.skills_impl.library_skills import KeywordReviewSkill
    lib = Library(os.path.join(dd, "library.json"))
    ctx = types.SimpleNamespace(library=lib, settings=settings or {}, notes=None)
    skill = KeywordReviewSkill()
    out = {"reviewed": 0, "approved": 0, "forbidden": 0, "escalated": 0, "known": 0, "per_word": []}
    for w in words:
        w = (w or "").strip()
        if not w:
            continue
        v = skill.run({"word": w, "demand": {}}, ctx)
        dec = v.get("decision")
        reason = v.get("reason", "")
        if dec == "known":
            status = v.get("status", "known")
            out["known"] += 1
        elif dec == "approve":
            lib.curate(w, "approved", rationale=reason, by="Librarian (intake)")
            status = "approved"; out["approved"] += 1
        elif dec == "reject":
            lib.curate(w, "forbidden", rationale=reason, by="Librarian (intake)")
            status = "forbidden"; out["forbidden"] += 1
        else:
            lib.curate(w, "escalated", rationale=reason, by="Librarian (intake)")
            status = "escalated"; out["escalated"] += 1
        out["reviewed"] += 1
        out["per_word"].append({"word": w, "status": status, "reason": reason})
    return out
