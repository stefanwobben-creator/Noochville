"""scope_nudge — Noochie's proactieve match (Level 3, optie 1: alleen nudgen).

Vraag: heeft ÉÉN rol (niet de eigenaar) dit project duidelijk binnen haar accountabilities ÉN een skill
om er iets concreets mee te doen? Zo ja, dan mag Noochie er een nudge bij plaatsen ('dit lijkt jouw
scope, oppakken?'). De ROL beslist zelf; Noochie wijst alleen.

GRENS: dit MATCHT alleen. Het voert niets uit en maakt geen taken (dat was optie 2, niet gekozen). De
skill wordt HARD tegen het DNA gecheckt: een voorgestelde skill buiten de rol-DNA telt niet mee, geen
verzonnen tool en geen zachte 'lijkt-erop'. Fail-closed op elke fout: geen match, geen exception naar
buiten.
"""
from __future__ import annotations

import json
import re

from nooch_village.util import refuse


def _extract_json(text):
    """Eerste JSON-object uit een LLM-antwoord, robuust tegen ```json-fences en omringend proza."""
    if not text:
        return None
    s = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", s, re.DOTALL | re.IGNORECASE)
    if fence:
        s = fence.group(1).strip()
    m = re.search(r"\{.*\}", s, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def match_project_to_role(project_text: str, roster: list, *, reason_fn=None, name: str = "noochie"):
    """Bepaal of één rol uit `roster` dit project binnen haar scope heeft ÉN een skill om te handelen.

    `roster` = [{"role_id", "name", "accountabilities": [...], "skills": [...]}]. Alleen rollen MÉT skills
    tellen mee (zonder skill kan een rol niets concreets, dus geen nudge). `reason_fn(prompt)->str|None` is
    injecteerbaar (test); standaard via llm.reason met json_mode. Returnt {role_id, name, skill} of None.
    Machine-check: de teruggegeven rol moet bestaan en de skill moet echt in háár DNA zitten."""
    project_text = (project_text or "").strip()
    roster = [r for r in (roster or []) if r.get("skills")]
    if not project_text or not roster:
        return None
    try:
        lines = []
        for r in roster:
            accts = list(r.get("accountabilities") or [])[:5]
            lines.append(f"- {r['role_id']} ({r.get('name', '')}): "
                         f"accountabilities={accts}; skills={list(r.get('skills') or [])}")
        prompt = (
            "Hieronder een projectinhoud en een lijst rollen met hun accountabilities en skills. Bepaal of "
            "ÉÉN rol dit project DUIDELIJK binnen haar accountabilities heeft ÉN een van haar skills kan "
            "inzetten om er iets concreets mee te doen. Wees streng: alleen bij een duidelijke, inhoudelijke "
            "match, niet bij een vaag verband.\n\n"
            f"Project:\n{project_text[:1500]}\n\n"
            f"Rollen:\n" + "\n".join(lines) + "\n\n"
            "Antwoord UITSLUITEND met JSON, exact dit schema: "
            "{\"role_id\": \"<id uit de lijst of null>\", \"skill\": \"<een skill van díé rol of null>\"}. "
            "Geen duidelijke match → beide null."
        )
        if reason_fn is not None:
            raw = reason_fn(prompt)
        else:
            from nooch_village import llm
            raw = llm.reason(prompt, json_mode=True, call_site="scope_nudge_match")
        if not raw:
            return None
        data = _extract_json(raw)
        if not isinstance(data, dict):
            return None
        rid = data.get("role_id")
        sk = data.get("skill")
        match = next((r for r in roster if r["role_id"] == rid), None)
        if not match or not sk or sk not in (match.get("skills") or []):
            return None                       # machine-check: rol bestaat + skill hoort echt bij die rol
        return {"role_id": rid, "name": match.get("name", ""), "skill": sk}
    except Exception as e:
        refuse("SCOPE_NUDGE_EXC", "match_project_to_role wierp een exceptie (fail-closed)",
               exc=type(e).__name__, name=name)
        return None
