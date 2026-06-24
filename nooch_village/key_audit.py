"""Opstart-rapport: welke API-sleutels staan scherp?

Niet-blokkerend. Het dorp draait gewoon door; dit rapport maakt alleen zichtbaar welke
treden van de LLM-ladder een sleutel hebben en welke skills 'scherp staan' (alle harde
sleutels aanwezig) versus closed falen tot je een sleutel invult.

Zelfbeschrijvend: het leest `required_env`/`optional_env` van de geregistreerde skills en
de LLM-ladder uit `llm._ladder()`. Geen losse, drift-gevoelige sleutel-map. Sleutel-WAARDEN
worden nooit getoond, alleen 'aanwezig: ja/nee'."""
from __future__ import annotations

import os

from nooch_village.llm import _ladder

# Welke env-sleutel hoort bij welke vendor-trede van de ladder.
_LADDER_KEYS = {
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),   # één van beide volstaat
    "mistral": ("MISTRAL_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
}


def _present(var: str, settings, environ) -> bool:
    """Een sleutel telt als aanwezig als hij in settings.ini óf in de omgeving staat én niet leeg is."""
    val = (settings.get(var) if settings else None) or environ.get(var)
    return bool(val and str(val).strip())


def audit_keys(registry, context, *, environ=None) -> dict:
    """Bouw een gestructureerd rapport (testbaar, geen I/O behalve env-lezen)."""
    environ = os.environ if environ is None else environ
    settings = getattr(context, "settings", {}) or {}

    ladder = []
    for vendor, model in _ladder():
        vars_ = _LADDER_KEYS.get(vendor, ())
        ok = any(_present(v, settings, environ) for v in vars_)
        ladder.append({"vendor": vendor, "model": model, "ok": ok})

    skills = []
    for sk in registry.all():
        req = tuple(getattr(sk, "required_env", ()) or ())
        opt = tuple(getattr(sk, "optional_env", ()) or ())
        if not req and not opt:
            continue
        req_status = [{"var": v, "ok": _present(v, settings, environ)} for v in req]
        opt_status = [{"var": v, "ok": _present(v, settings, environ)} for v in opt]
        skills.append({
            "name": sk.name,
            "required": req_status,
            "optional": opt_status,
            "active": all(r["ok"] for r in req_status),   # alle HARDE sleutels aanwezig
        })
    skills.sort(key=lambda s: s["name"])
    return {"ladder": ladder, "skills": skills}


def format_key_report(audit: dict) -> str:
    """Render het rapport als platte tekst voor de opstart-log."""
    lines = ["🔑 API-sleutels bij opstart (rapport, niet-blokkerend):", "",
             "  LLM-ladder (goedkoop → duur, stopt bij de eerste die antwoordt):"]
    for i, t in enumerate(audit["ladder"], 1):
        mark = "✓ sleutel" if t["ok"] else "✗ geen sleutel — trede overgeslagen"
        lines.append(f"    {i}. {t['vendor']:<9} {(t['model'] or '(default)'):<28} {mark}")

    lines += ["", "  Skills met externe sleutels:"]
    if not audit["skills"]:
        lines.append("    (geen)")
    for s in audit["skills"]:
        parts = [("✓ " if r["ok"] else "✗ ") + r["var"] for r in s["required"]]
        parts += [("✓ " if o["ok"] else "✗ ") + o["var"] + " (optioneel)" for o in s["optional"]]
        suffix = "" if s["active"] else "   → faalt closed tot de sleutel er is"
        lines.append(f"    {s['name']:<22} {'  '.join(parts)}{suffix}")

    actief = sum(1 for s in audit["skills"] if s["active"])
    treden = sum(1 for t in audit["ladder"] if t["ok"])
    lines += ["",
              f"  Samenvatting: {treden}/{len(audit['ladder'])} LLM-treden met sleutel, "
              f"{actief}/{len(audit['skills'])} sleutel-skills scherp."]
    return "\n".join(lines)
