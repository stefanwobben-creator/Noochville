"""Geheugen-laag fase 1: bestaande deliverables als context voor de prep-prompt.

Dom en deterministisch — woord-overlap-score, GEEN LLM, GEEN state. Bewust GEEN Skill-subklasse en
geen registry-registratie: de prep-flow (prepare_project → _plan_checklist) draait geen skills, dus een
Skill zou hier een kostuum zijn. Kandidaat voor extractie naar Skill zodra een TWEEDE consument
(bijv. synthese of _reflect) deze context ook nodig heeft.

Bron: de wall (p["log"]) van AFGERONDE projecten, dorpsbreed (kennis is dorpsbreed; de wall is leesbaar,
zelfde regel als de library). Fail-closed: elke fout → "" (de prep mag NOOIT vallen over de geheugen-laag).
"""
from __future__ import annotations

import logging
import re

log = logging.getLogger("village.deliverable_context")

_MIN_LEN = 4                                    # stopwoorden-arm: alleen woorden ≥4 tekens tellen mee
_NOTE_MARK = "📎"                                # deliverable-notes beginnen hiermee (faalnotes met ⚠️)


def _tokens(text: str) -> set[str]:
    """Case-insensitieve woordverzameling, stopwoorden-arm (≥4 tekens)."""
    return {w for w in re.findall(r"\w+", (text or "").lower(), re.UNICODE) if len(w) >= _MIN_LEN}


def _scope_text(scope) -> str:
    if isinstance(scope, str):
        return scope
    if isinstance(scope, dict):
        return str(scope.get("goal") or scope.get("title") or "")
    return str(scope or "")


def _clip(text: str, n: int) -> str:
    """Eén regel, gecapt op ≤ n tekens, op een nette (woord-)grens; '…' als er is afgekapt."""
    s = " ".join((text or "").split())          # multi-line note → één regel
    if len(s) <= n:
        return s
    cut = s[:n].rsplit(" ", 1)[0]
    return (cut or s[:n]) + "…"


def _wall_notes(p) -> list[tuple]:
    """[(text, at)] van de 📎-rol-deliverables op de project-wall — fallback voor oude projecten
    (van vóór de DeliverableStore). ⚠️-faalnotes en mens/voortgang-entries eruit."""
    out = []
    for entry in (p.get("log") or []):
        if entry.get("who") != "rol":
            continue
        text = entry.get("text") or ""
        if not text.startswith(_NOTE_MARK):
            continue
        out.append((text, entry.get("at", 0) or 0))
    return out


def _store_notes(store, pid) -> list[tuple] | None:
    """[(summary, created_at)] uit de DeliverableStore. None als de store ontbreekt of dit project
    géén records heeft → de caller valt dan terug op de wall (oud project). De `summary` is exact de
    📎-rendering die óók op de wall staat, dus de scoring is gedragsgelijk."""
    if store is None:
        return None
    try:
        recs = store.for_project(pid)
    except Exception:
        return None
    if not recs:
        return None
    return [((r.get("summary") or ""), r.get("created_at", 0) or 0) for r in recs]


def gather_deliverable_context(ledger, goal, keyword=None, *, max_notes, max_chars,
                               exclude_pid=None, store=None) -> str:
    """Bouw een compact contextblok van relevante, eerder opgeleverde deliverables.

    Bron: de DeliverableStore (records per afgerond project); voor oude projecten zonder records
    valt hij terug op de wall-parsing (📎-notes). Score = woord-overlap tussen (goal + keyword) en
    (project-keyword + project-scope + note-text). Score 0 → niet opnemen. Sortering: score desc, dan
    recentste eerst. max_notes en max_chars zijn hard. Output per note: "[<owner>/<scope[:60]>] <note[:200]>".

    `exclude_pid`: sluit het huidige project uit als bron (geen zelf-referentie)."""
    try:
        query = _tokens(f"{goal or ''} {keyword or ''}")
        if not query:
            return ""
        scored = []
        for p in ledger.by_status("done"):
            if exclude_pid and p.get("id") == exclude_pid:
                continue                                          # geen zelf-referentie
            owner = p.get("owner", "") or ""
            scope = _scope_text(p.get("scope"))
            pkw = p.get("keyword", "") or ""
            notes = _store_notes(store, p.get("id"))
            if notes is None:                                     # geen store-records → wall-fallback
                notes = _wall_notes(p)
            for text, at in notes:
                score = len(query & _tokens(f"{pkw} {scope} {text}"))
                if score <= 0:
                    continue                                      # geen overlap → niet opnemen
                scored.append((score, at, owner, scope, text))
        if not scored:
            return ""
        scored.sort(key=lambda t: (-t[0], -t[1]))                 # score desc, dan recentste eerst
        lines, used = [], 0
        for _score, _at, owner, scope, text in scored[:max_notes]:
            line = f"[{owner}/{_clip(scope, 60)}] {_clip(text, 200)}"
            sep = 1 if lines else 0
            if used + sep + len(line) > max_chars:                # hard max_chars → zichtbaar afgekapt
                room = max_chars - used - sep
                if room > 0:
                    lines.append(line[:room])
                break
            lines.append(line)
            used += sep + len(line)
        return "\n".join(lines)
    except Exception as e:                                        # fail-closed: prep mag hier nooit over vallen
        log.debug("deliverable_context overgeslagen: %s", e)
        return ""
