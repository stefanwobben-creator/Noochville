"""Een project als export-pakket: alle wall-content in één zip, voor handmatige AI-analyse.

Een `.zip` bevat:
- `project.json`  — het ruwe project-record (checklist, log, comments, attachments-lijst)
- `wall.md`       — het complete gesprek (rol + mens), leesbaar, ONGECAPT
- `checklists.md` — de checklist(s) met status (behaald/niet_behaald/overgeslagen)
- `attachments/`  — de bijlage-bestanden zelf (de PDF's etc.), niet alleen de metadata
- `README.md`     — wat hierin zit en waarom

Ontstaan uit een concrete vraag (14 september 2026): het automatische projectverslag
(`project_verslag.stel_samen`) en elke plan-/rondemechaniek lezen `attachments` niet als bron
(bevestigd, zie het project-doc `wall_diepdive_rubberproject_13sept.md`). Dit pakket is de
handmatige tussenoplossing: alles wat op een project staat, in één bestand, klaar om in een
willekeurige AI met een eigen prompt te gooien — geen vervanging voor het gat dichten, wel een
snelle manier om de kwaliteit te vergelijken.

BEWUST ONGECAPT. `project_verslag._gesprek()` kapt het gesprek af op 50 regels van 1500 tekens,
terecht voor een verslag dat kort moet blijven. Hier is compleetheid het hele punt, dus geen van
beide grenzen wordt hier herhaald.

Zelfde vorm als `inwoner_pakket.py` (zip + README), maar het omgekeerde privacy-contract: een
inwoner-pakket mag GEEN organisatiedata bevatten, een project-pakket IS organisatiedata — dat is
precies waar dit om gevraagd is. Alleen voor wie het project al mag zien (zelfde route-grens als
`/file`).
"""
from __future__ import annotations

import datetime
import io
import json
import os
import re
import zipfile


def slug(project: dict) -> str:
    scope = project.get("scope")
    titel = (" · ".join(f"{k}: {v}" for k, v in scope.items())
             if isinstance(scope, dict) else str(scope or project.get("id", "project")))
    kort = re.sub(r"[^a-z0-9]+", "_", titel.lower()).strip("_")[:60]
    return kort or "project"


def _wie(entry: dict) -> str:
    wie = entry.get("who")
    if wie:
        return wie
    a = entry.get("author")
    return (a.get("type") if isinstance(a, dict) else None) or "onbekend"


def _tijd(entry: dict) -> str:
    t = entry.get("at")
    if not t:
        return ""
    try:
        return datetime.datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError, OSError):
        return ""


def bouw_wall_md(project: dict) -> str:
    """Het complete gesprek (log), chronologisch, ONGECAPT."""
    regels = []
    for e in (project.get("log") or []):
        if not isinstance(e, dict):
            continue
        tekst = (e.get("text") or "").strip()
        if not tekst:
            continue
        kop = f"**{_wie(e)}**"
        tijd = _tijd(e)
        if tijd:
            kop += f" ({tijd})"
        regels.append(f"{kop}\n\n{tekst}")
    if not regels:
        return "_Geen berichten op de wall._\n"
    return "\n\n---\n\n".join(regels) + "\n"


def bouw_checklists_md(project: dict) -> str:
    out = []
    for cl in (project.get("checklists") or []):
        titel = cl.get("title") or "(zonder titel)"
        out.append(f"## {titel}\n")
        for item in (cl.get("items") or []):
            tekst = item.get("text") or ""
            if item.get("done"):
                icoon = "✅"
            elif item.get("skipped"):
                icoon = "⏭"
            else:
                icoon = "☐"
            out.append(f"- {icoon} {tekst}")
        out.append("")
    return "\n".join(out) if out else "_Geen checklist._\n"


def _veilige_naam(naam: str, gebruikt: set) -> str:
    """Voorkomt padverwarring en botsende bestandsnamen in de attachments/-map."""
    basis = os.path.basename(naam or "bestand")
    kandidaat = basis
    i = 1
    while kandidaat in gebruikt:
        wortel, ext = os.path.splitext(basis)
        kandidaat = f"{wortel}_{i}{ext}"
        i += 1
    gebruikt.add(kandidaat)
    return kandidaat


def bouw_readme(project: dict, n_ok: int, n_missing: int) -> str:
    scope = project.get("scope")
    titel = (" · ".join(f"{k}: {v}" for k, v in scope.items())
             if isinstance(scope, dict) else str(scope or project.get("id", "")))
    missend = (f"\n**Let op:** {n_missing} bijlage(n) stonden in het record maar het bestand "
               f"ontbrak op schijf; die zitten er niet bij.\n" if n_missing else "")
    return (f"# Project-pakket: {titel}\n\n"
            f"Alle content van dit project in één bestand, voor handmatige AI-analyse buiten "
            f"NoochVille om.\n\n"
            f"## Inhoud\n\n"
            f"- `project.json` — het ruwe project-record\n"
            f"- `wall.md` — het complete gesprek (rol + mens), ongecapt\n"
            f"- `checklists.md` — de checklist(s) met status\n"
            f"- `attachments/` — {n_ok} bijlage-bestand(en)\n"
            f"{missend}\n"
            f"## Waarom dit bestaat\n\n"
            f"Het automatische projectverslag en elke plan-/rondemechaniek lezen bijlagen niet als "
            f"bron (bevestigd 14 september 2026). Dit pakket vult dat gat handmatig: gooi het in "
            f"een AI met een eigen prompt en vergelijk het resultaat met het bestaande verslag.\n")


def _vul_zip(z: zipfile.ZipFile, project: dict, data_dir: str) -> dict:
    gebruikt: set = set()
    n_ok = n_missing = 0
    z.writestr("project.json", json.dumps(project, ensure_ascii=False, indent=1))
    z.writestr("wall.md", bouw_wall_md(project))
    z.writestr("checklists.md", bouw_checklists_md(project))
    for a in (project.get("attachments") or []):
        stored = a.get("stored")
        if not stored:
            continue                                  # kind='link': geen bestand, alleen een URL
        volledig = os.path.join(data_dir, stored)
        if not os.path.exists(volledig):
            n_missing += 1
            continue
        naam = _veilige_naam(a.get("name") or os.path.basename(stored), gebruikt)
        z.write(volledig, arcname=f"attachments/{naam}")
        n_ok += 1
    z.writestr("README.md", bouw_readme(project, n_ok, n_missing))
    return {"n_attachments": n_ok, "n_ontbrekend": n_missing}


def exporteer(project: dict, pad: str, data_dir: str) -> dict:
    """Schrijf de zip naar `pad` en geef {"pad", "n_attachments", "n_ontbrekend"} terug."""
    os.makedirs(os.path.dirname(pad) or ".", exist_ok=True)
    with zipfile.ZipFile(pad, "w", zipfile.ZIP_DEFLATED) as z:
        info = _vul_zip(z, project, data_dir)
    return {"pad": pad, **info}


def bouw_zip_bytes(project: dict, data_dir: str) -> bytes:
    """Als `exporteer`, maar in het geheugen — voor de downloadroute (geen tijdelijk bestand nodig)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        _vul_zip(z, project, data_dir)
    return buf.getvalue()
