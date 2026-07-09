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


def gather_deliverable_context(ledger, goal, keyword=None, *, max_notes, max_chars, exclude_pid=None) -> str:
    """Bouw een compact contextblok van relevante, eerder opgeleverde deliverables.

    Score = woord-overlap tussen (goal + keyword) en (project-keyword + project-scope + note-text).
    Score 0 → niet opnemen. Sortering: score desc, dan recentste eerst. max_notes en max_chars zijn hard.
    Output per note: "[<owner>/<scope[:60]>] <note-text[:200]>". Leeg → "".

    `exclude_pid`: sluit het huidige project uit als bron (geen zelf-referentie). Aanvulling op de
    scope-signatuur; nodig omdat een project in principe ook een afgeronde eigen bron kan zijn."""
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
            for entry in (p.get("log") or []):
                if entry.get("who") != "rol":
                    continue                                      # mens/voortgang-entries eruit
                text = entry.get("text") or ""
                if not text.startswith(_NOTE_MARK):
                    continue                                      # alleen 📎-deliverables; ⚠️-faalnotes eruit
                score = len(query & _tokens(f"{pkw} {scope} {text}"))
                if score <= 0:
                    continue                                      # geen overlap → niet opnemen
                scored.append((score, entry.get("at", 0) or 0, owner, scope, text))
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
