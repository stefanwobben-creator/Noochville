"""Een inwoner als verkoopbaar pakketje: export en import.

Een `.inwoner` is een zip met drie bestanden:
- `persona.json`  — het volledige dossier (karakter, skills, tools, modelvoorkeur)
- `manifest.json` — wat deze village moet kunnen om hem te draaien: welke skill-modules,
                    welke API-sleutels, welke tool-routes
- `README.md`     — hetzelfde verhaal in mensentaal

TWEE HARDE GRENZEN, allebei getest:
1. **Geen geheimen.** Nooit .env-waarden, keys of tokens. Het manifest noemt alleen de NAMEN
   van de sleutels die nodig zijn ("SERPAPI_KEY"), nooit hun waarde.
2. **Geen organisatie-data.** Geen library, records, observaties, projecten of governance. Een
   pakket beschrijft een inwoner, niet het dorp waar hij woonde.

Import installeert geen code. Hij meldt wat er ontbreekt en laat de mens beslissen — dezelfde
geboren-versus-bemenst-grens als bij rollen.
"""
from __future__ import annotations

import json
import os
import re
import zipfile
from dataclasses import asdict

VERSIE = 1

# Sleutels die nooit in een pakket terechtkomen, ongeacht waar ze vandaan komen. De export
# bouwt het dossier expliciet op uit toegestane velden; deze lijst is de tweede grendel.
_VERBODEN = ("token", "key", "secret", "password", "wachtwoord", "credential")


def slug(naam: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (naam or "inwoner").lower()).strip("_") or "inwoner"


def _schoon(dossier: dict) -> dict:
    """Laatste zeef: gooi elk veld weg dat naar een geheim ruikt."""
    return {k: v for k, v in dossier.items()
            if not any(w in k.lower() for w in _VERBODEN)}


def bouw_manifest(persona, registry=None) -> dict:
    """Wat een andere village nodig heeft om deze inwoner te draaien.

    Alleen namen — van modules, van sleutels, van routes. Nooit waarden."""
    if registry is None:
        from nooch_village.registry_factory import shared_registry
        registry = shared_registry()
    modules, sleutels, onbekend = {}, set(), []
    for naam in (persona.skills or []):
        skill = registry.get(naam)
        if skill is None:
            onbekend.append(naam)
            continue
        modules[naam] = type(skill).__module__
        for env in (getattr(skill, "required_env", ()) or ()):
            sleutels.add(env)
    return {
        "pakket_versie": VERSIE,
        "inwoner": persona.name,
        "skills": sorted(persona.skills or []),
        "skill_modules": modules,
        "skills_onbekend": sorted(onbekend),
        "vereiste_sleutels": sorted(sleutels),      # NAMEN, geen waarden
        "tool_routes": [t.get("href", "") for t in (persona.tools or []) if t.get("href")],
    }


def bouw_readme(persona, manifest: dict) -> str:
    from nooch_village.skill_labels import label as skill_label
    kan = "\n".join(f"- {skill_label(s)}  (`{s}`)" for s in manifest["skills"]) or "- (nog niets)"
    nodig = "\n".join(f"- `{k}`" for k in manifest["vereiste_sleutels"]) or "- geen API-sleutels"
    tools = "\n".join(f"- {t.get('label', '')} — `{t.get('href', '')}`"
                      for t in (persona.tools or [])) or "- geen eigen schermen"
    return (f"# {persona.name}\n\n"
            f"{persona.avatar}  {persona.mbti or 'geen MBTI'}\n\n"
            f"## Wie is dit\n\n{persona.instructions or '(geen karakterbeschrijving)'}\n\n"
            + (f"**Werkafspraak:** {persona.prompt_extra}\n\n" if persona.prompt_extra else "")
            + f"## Wat hij kan\n\n{kan}\n\n"
            f"## Eigen schermen\n\n{tools}\n\n"
            f"## Wat hij nodig heeft\n\n{nodig}\n\n"
            f"De skill-modules moeten in de doel-village aanwezig zijn:\n"
            + "\n".join(f"- `{m}`" for m in sorted(set(manifest['skill_modules'].values())))
            + "\n\n---\n\nDit pakket bevat GEEN sleutels en GEEN organisatie-data — alleen de "
              "inwoner zelf.\n")


def exporteer(persona, pad: str, registry=None) -> str:
    """Schrijf `<slug>.inwoner` en geef het pad terug."""
    dossier = _schoon(asdict(persona))
    manifest = bouw_manifest(persona, registry)
    os.makedirs(os.path.dirname(pad) or ".", exist_ok=True)
    with zipfile.ZipFile(pad, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("persona.json", json.dumps(dossier, ensure_ascii=False, indent=1))
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1))
        z.writestr("README.md", bouw_readme(persona, manifest))
    return pad


def lees(pad: str) -> tuple[dict, dict]:
    """(dossier, manifest) uit een pakket. Faalt luid bij een kapot bestand."""
    with zipfile.ZipFile(pad) as z:
        dossier = json.loads(z.read("persona.json").decode("utf-8"))
        try:
            manifest = json.loads(z.read("manifest.json").decode("utf-8"))
        except KeyError:
            manifest = {}
    return dossier, manifest


def installeer(store, pad: str, registry=None) -> dict:
    """Importeer de persona; rapporteer wat deze village mist.

    Installeert GEEN code. Ontbrekende skill-modules en sleutels worden gemeld zodat een mens
    kan beslissen — dezelfde grens als bij het bemensen van een rol."""
    if registry is None:
        from nooch_village.registry_factory import shared_registry
        registry = shared_registry()
    dossier, manifest = lees(pad)
    naam = dossier.get("name") or "Naamloos"
    if any(p.name == naam for p in store.all()):
        naam = f"{naam} (import)"          # botsing → nieuw id én zichtbaar andere naam
    nieuw = store.add(naam, mbti=dossier.get("mbti", ""),
                      instructions=dossier.get("instructions", ""))
    store.update(nieuw.id, avatar=dossier.get("avatar", ""),
                 prompt_extra=dossier.get("prompt_extra", ""),
                 tools=dossier.get("tools") or [], llm=dossier.get("llm") or {},
                 skills=dossier.get("skills") or [], kind=dossier.get("kind", "ai"))

    ontbrekende_skills = [s for s in (dossier.get("skills") or []) if registry.get(s) is None]
    ontbrekende_sleutels = [k for k in manifest.get("vereiste_sleutels", [])
                            if not os.getenv(k)]
    return {"persona_id": nieuw.id, "naam": naam,
            "ontbrekende_skills": ontbrekende_skills,
            "ontbrekende_sleutels": ontbrekende_sleutels,
            "tool_routes": manifest.get("tool_routes", [])}
