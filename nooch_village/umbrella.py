"""umbrella — leidt de bredere 'umbrella'-term boven een niche-keyword af.

De scout doet keyword-research vaak op heel niche termen ('biodegradable barefoot shoes') die op 0
zoekvolume uitkomen. Dat is prima, maar de BREDE context ('barefoot shoes') mist dan. Deze stap leidt
per niche-keyword de naaste bredere basisterm af, zodat die ook meegenomen wordt.

Lichte LLM-stap, bewust toegestaan: dit maakt geen claim en fabriceert geen bewijs, het kiest alleen wat
je ER EXTRA bij onderzoekt (context). Fail-closed: geen LLM / geen antwoord / onparsebaar → een LEGE map,
de research loopt ongewijzigd door. Nooit een umbrella forceren, nooit de niche-term zelf teruggeven.
"""
from __future__ import annotations

import json
import re

from nooch_village.util import refuse


def _extract_json(text):
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


def umbrella_terms(keywords, *, reason_fn=None, name: str = "") -> dict:
    """{keyword: umbrella} voor niche-keywords, in ÉÉN LLM-call. De umbrella is de naaste bredere
    basisterm; is een keyword zelf al een basisterm (of gelijk aan de umbrella), dan komt het NIET in de
    map. `reason_fn(prompt)->str|None` injecteerbaar (test); standaard via llm.reason met json_mode.
    Fail-closed: elke fout → {} (geen umbrella toegevoegd)."""
    kws = [k for k in (keywords or []) if (k or "").strip()]
    if not kws:
        return {}
    try:
        genummerd = "\n".join(f"{i + 1}. {k}" for i, k in enumerate(kws))
        prompt = (
            "Geef voor elk keyword de naaste BREDERE umbrella-term (de basiscategorie erboven), voor "
            "rijkere zoek-context. Voorbeeld: 'biodegradable barefoot shoes' -> 'barefoot shoes'; "
            "'vegan running sneakers' -> 'running sneakers'. Is een keyword zelf al een basisterm (geen "
            "zinvolle bredere term), geef dan null voor dat keyword.\n\n"
            f"Keywords:\n{genummerd}\n\n"
            "Antwoord UITSLUITEND met JSON, exact dit schema en exact evenveel items als keywords, in "
            "dezelfde volgorde: {\"umbrellas\": [\"<umbrella of null>\", ...]}"
        )
        if reason_fn is not None:
            raw = reason_fn(prompt)
        else:
            from nooch_village import llm
            raw = llm.reason(prompt, json_mode=True, call_site="keyword_umbrella")
        if not raw:
            return {}
        data = _extract_json(raw)
        arr = data.get("umbrellas") if isinstance(data, dict) else None
        if not isinstance(arr, list):
            return {}
        out = {}
        for i, k in enumerate(kws):
            u = arr[i] if i < len(arr) else None
            if isinstance(u, str) and u.strip() and u.strip().lower() != k.strip().lower():
                out[k] = u.strip()
        return out
    except Exception as e:
        refuse("UMBRELLA_EXC", "umbrella_terms wierp een exceptie (fail-closed)",
               exc=type(e).__name__, name=name)
        return {}
