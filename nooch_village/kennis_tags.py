"""kennis_tags — hint-opschoning: de tag-schuld die tag_onderhoud juist laat liggen (founder 23 jul).

Gemeten: van de 51 unieke tags zijn er 34 een `hint:`-tag — de link-hints die de atomiser verzint
("met welk onderwerp hoort dit samen"). Ze waren curatie-aanwijzingen, maar niemand lost ze op, dus ze
stapelen; en `tag_onderhoud` laat ze bewust ongemoeid. Een deel wijst naar een bestaand onderwerp
(hint:duurzame-schoenen naast het echte duurzame-schoenen), een deel naar concepten buiten het vaste
vocabulaire (hint:circulariteit, hint:bio-based, hint:textiel).

Deze module lost de hint-laag op, deterministisch waar het kan en met één LLM-pass voor de rest:
  1. hint:X waarvan X een BESTAAND onderwerp is → promoveer: vervang hint:X door het echte onderwerp
     (NotesStore.retag), zodat het kaartje netjes gesorteerd raakt i.p.v. te blijven hangen als hint.
  2. hint:X die de LLM op een bestaand onderwerp mapt → idem.
  3. hint:X buiten het vocabulaire die vaak terugkomt (>= drempel) → kandidaat-NIEUW-onderwerp: naar de
     human inbox als suggestie (jij beslist over vocabulaire-uitbreiding), en de hint valt weg.
  4. hint:X die zeldzame ruis is → weggooien (retag naar None).

Pure beslis-functies + injecteerbare reason_fn (testbaar zonder netwerk). Toepassen gaat uitsluitend via
bestaande store-primitieven (retag). Fail-soft: geen LLM → alleen de deterministische map (stap 1) draait,
de rest blijft staan (nooit iets stil weggooien wat een onderwerp had kunnen worden)."""
from __future__ import annotations

import json
import re

from nooch_village.kennisbank_intake import SUBJECTS


def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (t or "").lower())


_SUBJ_NORM = {_norm(s): s for s in SUBJECTS}


def hint_telling(notes) -> dict[str, int]:
    """Alle hint-concepten (zonder 'hint:'-prefix) met hun aantal over niet-gearchiveerde kaartjes."""
    telling: dict[str, int] = {}
    for a in notes.all():
        if a.archived:
            continue
        for t in a.tags or []:
            if t.startswith("hint:"):
                concept = t[5:].strip()
                if concept:
                    telling[concept] = telling.get(concept, 0) + 1
    return telling


def build_hint_prompt(concepten: list[str]) -> str:
    """Vraag de LLM elk hint-concept op het vaste vocabulaire te mappen, of NONE."""
    lijst = "\n".join(f"- {c}" for c in concepten)
    return (
        "Je sorteert kennis-tags op een VAST onderwerp-vocabulaire. Voor elk hint-concept hieronder: "
        "welk onderwerp uit de lijst past het best, of NONE als geen enkel onderwerp echt past.\n\n"
        f"VASTE ONDERWERPEN: {', '.join(SUBJECTS)}\n\n"
        f"HINT-CONCEPTEN:\n{lijst}\n\n"
        "Wees streng: map alleen als het concept duidelijk ONDER dat onderwerp valt (bv. 'kurk' → "
        "'materiaal', 'chroomvrij leer' → 'leer'). Twijfel of te breed → NONE.\n"
        'Antwoord UITSLUITEND met JSON: {"concept": "onderwerp-of-NONE", ...} voor elk concept.')


def parse_hint_mapping(text: str | None, concepten: list[str]) -> dict[str, str | None]:
    """LLM-JSON → {concept: subject|None}. Fail-closed: onparseerbaar/onbekend onderwerp → None."""
    uit: dict[str, str | None] = {c: None for c in concepten}
    if not text:
        return uit
    s = re.sub(r"```(?:json)?", "", text).strip()
    try:
        data = json.loads(s[s.find("{"):s.rfind("}") + 1])
    except (ValueError, IndexError):
        return uit
    if not isinstance(data, dict):
        return uit
    for c in concepten:
        doel = str(data.get(c) or "").strip().lower()
        if doel in SUBJECTS:
            uit[c] = doel
    return uit


def plan_hints(notes, *, reason_fn=None, drempel_nieuw: int = 4) -> dict:
    """Beslis per hint-concept: 'map' (→ bestaand onderwerp), 'voorstel' (kandidaat-nieuw-onderwerp) of
    'drop' (ruis). Deterministisch waar X exact een onderwerp is; anders één LLM-pass. Geen LLM → alleen
    de exacte maps, de rest blijft ongemoeid (conservatief). Geeft een plan-dict (past niets toe)."""
    telling = hint_telling(notes)
    concepten = sorted(telling)
    plan = {"map": {}, "voorstel": [], "drop": [], "onaangeroerd": []}
    if not concepten:
        return plan

    # 1) Deterministisch: hint:X waar X exact een onderwerp is.
    rest = []
    for c in concepten:
        s = _SUBJ_NORM.get(_norm(c))
        if s:
            plan["map"][c] = s
        else:
            rest.append(c)
    if not rest:
        return plan

    # 2) LLM-pass voor de rest. reason_fn: None → default llm.reason; False → geen LLM; callable → die.
    if reason_fn is None:
        try:
            from nooch_village.llm import reason as reason_fn
        except Exception:
            reason_fn = None
    llm = reason_fn if callable(reason_fn) else None
    mapping: dict[str, str | None] = {c: None for c in rest}
    if llm is not None:
        try:
            out = llm(build_hint_prompt(rest), call_site="kennis_tags", json_mode=True, max_tokens=800)
            mapping = parse_hint_mapping(out, rest)
        except Exception:
            mapping = {c: None for c in rest}

    for c in rest:
        doel = mapping.get(c)
        if doel:
            plan["map"][c] = doel
        elif telling[c] >= drempel_nieuw:
            plan["voorstel"].append({"concept": c, "aantal": telling[c]})
        elif llm is not None:
            plan["drop"].append(c)          # LLM zei NONE + zeldzaam → ruis
        else:
            plan["onaangeroerd"].append(c)  # geen LLM → niets stil weggooien
    return plan


def pas_hints_toe(notes, plan: dict, *, human_inbox=None) -> dict:
    """Voer het plan uit via bestaande store-primitieven. 'map' → retag hint:X naar het onderwerp;
    'drop' → retag hint:X naar None; 'voorstel' → suggestie in de human inbox (vocabulaire-uitbreiding)
    en de hint valt weg. Geeft stats terug."""
    gemapt = gedropt = voorgesteld = 0
    for concept, doel in (plan.get("map") or {}).items():
        notes.retag(f"hint:{concept}", doel)
        gemapt += 1
    for concept in (plan.get("drop") or []):
        notes.retag(f"hint:{concept}", None)
        gedropt += 1
    for v in (plan.get("voorstel") or []):
        concept = v["concept"]
        if human_inbox is not None:
            try:
                human_inbox.add_suggestion(
                    f"nieuw_onderwerp:{_norm(concept)}",
                    f"Terugkerend hint-concept '{concept}' ({v['aantal']}x) past in geen vast onderwerp. "
                    f"Als onderwerp toevoegen aan het vocabulaire, of laten vallen?")
                voorgesteld += 1
            except Exception:
                pass
        notes.retag(f"hint:{concept}", None)   # de hint zelf valt weg; het voorstel bewaart het concept
    return {"gemapt": gemapt, "gedropt": gedropt, "voorgesteld": voorgesteld}
