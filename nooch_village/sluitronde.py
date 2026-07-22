"""Sluitronde — de autonome triage die de kansen-inbox zelf leegmaakt (founder, 22 jul).

Het dorp senst volop kansen maar sluit niets: ze wachten op het akkoord van de founder en stapelen
zich op (de dam). Deze module haalt de founder uit het kritieke pad. Per open kans:

  1. VERVAL — ouder dan `ttl_days` zonder actie = de facto 'nee' (verlopen). Geen LLM.
  2. DUBBEL — de kans valt al onder een bestaand actief project. 'nee, al gedekt'. Geen LLM.
  3. RAADSPANEL — een panel van rol-lenzen (elk vanuit z'n purpose) oordeelt tegen Nooch's purpose:
     wordt dit een project (met trekkerrol + korte scope), of een expliciete 'nee, want…'.
  4. ESCALATIE — heeft de kans een ONOMKEERBAAR gevolg (geld uitgeven, publieke claim, extern
     commitment), dan beslist het dorp NIET zelf: de kans blijft staan als beslis-signaal voor jou.

Puur logica met een injecteerbare `reason_fn` (testbaar los van de LLM). Fail-soft: valt de LLM weg,
dan escaleert de kans naar de mens (conservatief) i.p.v. blind te sluiten of te openen. De mutaties
(project maken, kans sluiten) doet de aanroeper via de bestaande stores; deze module beslist alleen.
"""
from __future__ import annotations

import json
import re

from nooch_village.llm import reason
from nooch_village.mission import ANCHOR_PURPOSE

DAY = 86400
_STOP = {"de", "het", "een", "en", "van", "voor", "met", "op", "in", "te", "of", "the", "a", "and",
         "of", "for", "to", "with", "op", "nooch", "created", "done", "maak", "een"}


def _tokens(s: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", (s or "").lower()) if len(w) > 2 and w not in _STOP}


def _dedup(titel: str, active_scopes: list[str], drempel: float = 0.6) -> str | None:
    """Valt deze kans al onder een actief project? Token-overlap (Jaccard) boven de drempel → match."""
    t = _tokens(titel)
    if not t:
        return None
    best, beststr = 0.0, None
    for sc in active_scopes:
        st = _tokens(sc)
        if not st:
            continue
        j = len(t & st) / len(t | st)
        if j > best:
            best, beststr = j, sc
    return beststr if best >= drempel else None


def _jacc(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if (a or b) else 0.0


def _titel_van(kans: dict) -> str:
    return (kans.get("context") or {}).get("title") or kans.get("subject") or ""


def cluster(kansen: list[dict], drempel: float = 0.5) -> list[list[dict]]:
    """Groepeer near-duplicaat-kansen (template-spam: één idee, tig herformuleringen). Greedy op
    token-overlap (Jaccard) van de titel. Zo beoordeelt de ronde één keer per THEMA i.p.v. per item."""
    clusters: list[dict] = []
    for k in kansen:
        t = _tokens(_titel_van(k))
        for c in clusters:
            if _jacc(t, c["tok"]) >= drempel:
                c["leden"].append(k)
                c["tok"] |= t                       # cluster groeit mee (vangt zo de hele familie)
                break
        else:
            clusters.append({"tok": set(t), "leden": [k]})
    return [c["leden"] for c in clusters]


def _lens_block(lenzen: list[dict]) -> str:
    return "\n".join(f"- {l.get('naam') or l.get('id')}: {(l.get('purpose') or '')[:160]}"
                     for l in (lenzen or [])) or "- (geen rol-lenzen)"


def _panel(titel: str, ctx: dict, lenzen: list[dict], reason_fn, open_werk: int = 0) -> dict | None:
    """Eén raadspanel-oordeel: elke rol-lens stemt vanuit haar purpose, meerderheid beslist.
    Geeft {stemmen, besluit, onomkeerbaar, owner_rol, scope, reden} of None bij LLM-uitval."""
    wat = ctx.get("wat") or ""
    waarom = ctx.get("waarom") or ""
    by = ctx.get("by") or ""
    prompt = (
        "Je bent een raadspanel dat namens Nooch beslist of een gesensde KANS NU werk moet worden.\n\n"
        f"NOOCH PURPOSE:\n{ANCHOR_PURPOSE}\n\n"
        f"BELANGRIJKE CONTEXT: het dorp heeft AL {open_werk} open projecten en senst veel meer dan "
        "het afmaakt. Een nieuw project kost een schaarse plek. De lat ligt daarom HOOG en de "
        "STANDAARD is 'nee'. Stem alleen 'ja' als de kans ALLE vier haalt:\n"
        "  1. draagt DIRECT bij aan de kern-purpose (duurzaamste veganistische schoenmerk, "
        "meliorisme via transparantie, organische missie-gedreven groei op nooch.earth);\n"
        "  2. is concreet en waardevol genoeg om NU een plek te verdienen (geen nice-to-have, geen "
        "generiek community- of spel-idee, geen vaag 'zichtbaar maken');\n"
        "  3. is geen bijna-duplicaat van een bestaand project of een andere kans (varianten van "
        "hetzelfde idee → nee);\n"
        "  4. is geen interne proces- of governance-review die kan wachten gezien de overload.\n"
        "Bij twijfel: 'nee'. Onomkeerbaarheid is NIET de goedkeuringstest (zie hieronder), alleen "
        "purpose-waarde-urgentie telt voor ja/nee.\n\n"
        f"DE KANS:\n  titel: {titel}\n  wat: {wat}\n  waarom: {waarom}\n  gesensd door: {by}\n\n"
        f"HET PANEL (oordeel PER rol vanuit haar eigen purpose-lens):\n{_lens_block(lenzen)}\n\n"
        "APART, na de ja/nee: heeft uitvoeren een ONOMKEERBAAR gevolg (geld uitgeven, een publieke "
        "claim doen, een extern commitment aangaan)? Zo ja, zet onomkeerbaar=true; dan beslist het "
        "panel niet zelf en gaat de kans naar de mens, ongeacht ja/nee.\n\n"
        "Antwoord UITSLUITEND met JSON:\n"
        '{"stemmen":[{"rol":"...","stem":"ja of nee","reden":"kort"}],'
        '"besluit":"ja of nee (meerderheid, standaard nee)","onomkeerbaar":true of false,'
        '"waarde":1-5 (hoe waardevol voor de purpose NU, 5=cruciaal),'
        '"reden":"kernreden","owner_rol":"de rol-id die dit het beste trekt (bij ja)",'
        '"scope":"één korte, toetsbare uitkomst-zin (bij ja)"}')
    raw = reason_fn(prompt, max_tokens=700, json_mode=True, call_site="sluitronde_panel")
    return _extract(raw)


def beslis_kans(kans: dict, lenzen: list[dict], active_scopes: list[str], *,
                reason_fn=reason, now: float, ttl_days: int = 14) -> dict:
    """Beslis over één kans. Puur (muteert niets). Geeft een besluit-dict:
    {actie: 'verlopen'|'nee'|'project'|'escaleer', reden, owner_rol?, scope?, stemmen?}."""
    ctx = kans.get("context") or {}
    titel = ctx.get("title") or kans.get("subject") or ""
    leeftijd = (now - (kans.get("created_at") or now)) / DAY

    if leeftijd > ttl_days:
        return {"actie": "verlopen", "reden": f"verlopen: {int(leeftijd)} dagen zonder actie"}

    dup = _dedup(titel, active_scopes)
    if dup:
        return {"actie": "nee", "reden": f"al gedekt door bestaand project: {dup[:70]}"}

    data = _panel(titel, ctx, lenzen, reason_fn, open_werk=len(active_scopes))
    if not isinstance(data, dict):
        return {"actie": "escaleer", "reden": "kon niet automatisch beoordelen (LLM weg) — naar jou"}
    stemmen = data.get("stemmen") if isinstance(data.get("stemmen"), list) else []
    if data.get("onomkeerbaar"):
        return {"actie": "escaleer", "stemmen": stemmen,
                "reden": (data.get("reden") or "onomkeerbaar gevolg") + " (onomkeerbaar → naar jou)"}
    if str(data.get("besluit", "")).strip().lower().startswith("ja"):
        try:
            waarde = int(data.get("waarde") or 3)
        except (ValueError, TypeError):
            waarde = 3
        return {"actie": "project", "stemmen": stemmen, "reden": data.get("reden", ""),
                "owner_rol": (data.get("owner_rol") or "").strip(),
                "waarde": max(1, min(5, waarde)),
                "scope": (data.get("scope") or titel).strip()}
    return {"actie": "nee", "stemmen": stemmen,
            "reden": data.get("reden") or "past niet binnen de purpose"}


def _extract(raw):
    if not raw:
        return None
    s = re.sub(r"```(?:json)?", "", str(raw)).strip()
    try:
        return json.loads(s[s.find("{"):s.rfind("}") + 1])
    except (ValueError, IndexError):
        return None
