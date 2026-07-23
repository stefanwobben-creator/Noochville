#!/usr/bin/env python3
"""Eenmalige migratie (founder, 21 jul): breng bestaande projecten in lijn met het nieuwe model
waarin de uitgebreide DoD ('klaar wanneer') als kop van het einddocument staat en de projectpoort
doc-gedreven is.

Per project (ALLE projecten, ook gearchiveerde en afgeronde):
  - Heeft het einddocument al ECHTE inhoud (wijkt af van de seed) → met rust laten.
  - Zijn er deliverables opgeleverd → Noochie schrijft het rapport (synthesize_einddocument).
  - Anders → alleen de DoD als kop klaarzetten (seed_document), zodat de 'klaar wanneer'
    onder de titel verschijnt; het project blijft eerlijk op-slot tot er een antwoord staat.

Draai NA het deployen van de patch (deze imports bestaan pas dan). Op de server, als de app-user:
    cd /opt/noochville
    sudo -u nooch python3 einddoc_migratie.py --dry     # eerst kijken wat er zou gebeuren
    sudo -u nooch python3 einddoc_migratie.py           # echt uitvoeren
Vlaggen:
    --dry         niets schrijven, alleen tonen
    --seed-only   geen LLM-synthese, overal alleen de DoD-kop seeden
"""
from __future__ import annotations

import logging
import sys

logging.basicConfig(level=logging.WARNING, format="%(message)s")
LOG = logging.getLogger("einddoc_migratie")

DRY = "--dry" in sys.argv
SEED_ONLY = "--seed-only" in sys.argv


def _dod_van(p: dict) -> str:
    dod = (p.get("done_when") or "").strip()
    if dod:
        return dod
    sc = p.get("scope")
    return sc.strip() if isinstance(sc, str) else ""


def main() -> int:
    from nooch_village.cockpit2 import _Stores, _default_data_dir, _load_env
    from nooch_village.projects import seed_document, _norm
    from nooch_village.inhabitant import synthesize_einddocument

    _load_env()
    dd = _default_data_dir()
    st = _Stores(dd)
    docs = st.project_docs

    projecten = st.projects.all()
    n_totaal = len(projecten)
    n_skip = n_seed = n_synth = n_synth_faal = n_geen_dod = 0

    print(f"Datamap: {dd}")
    print(f"Projecten: {n_totaal}  |  modus: "
          f"{'DRY-RUN (niets schrijven)' if DRY else 'ECHT'}"
          f"{' · seed-only' if SEED_ONLY else ''}\n")

    for p in projecten:
        pid = p.get("id")
        titel = (p.get("scope") if isinstance(p.get("scope"), str) else str(p.get("scope") or ""))[:60]
        arch = " [gearchiveerd]" if p.get("archived") else ""
        dod = _dod_van(p)
        cur = docs.read(pid)
        seed = seed_document(dod)
        heeft_echt = bool(cur.strip()) and _norm(cur) != _norm(seed)

        if heeft_echt:
            n_skip += 1
            print(f"· overslaan  {pid}{arch} — heeft al een einddocument  «{titel}»")
            continue
        if not dod:
            n_geen_dod += 1
            print(f"· geen DoD   {pid}{arch} — geen 'klaar wanneer' om te seeden  «{titel}»")
            continue

        heeft_deliverables = bool(st.deliverables.for_project(pid))

        if heeft_deliverables and not SEED_ONLY:
            if DRY:
                n_synth += 1
                print(f"→ SYNTH     {pid}{arch} — {len(st.deliverables.for_project(pid))} deliverables → Noochie schrijft rapport  «{titel}»")
                continue
            rec = st.records.get(p.get("owner"))
            ok = False
            try:
                ok = synthesize_einddocument(
                    project_docs=docs, deliverables=st.deliverables, projects=st.projects,
                    personas=st.personas, record=rec, settings={}, project=p,
                    force_final=False, log=LOG)
            except Exception as e:
                LOG.warning("synthese-fout %s: %s", pid, e)
            if ok:
                n_synth += 1
                print(f"✓ SYNTH     {pid}{arch} — rapport geschreven  «{titel}»")
            else:
                # Geen LLM-key / geen bruikbaar antwoord → val terug op de seed-kop.
                docs.write(pid, seed)
                n_synth_faal += 1
                print(f"~ seed(fb)  {pid}{arch} — synthese lukte niet, DoD-kop geplaatst  «{titel}»")
            continue

        # Geen deliverables (of --seed-only): DoD-kop klaarzetten.
        if DRY:
            n_seed += 1
            print(f"→ SEED      {pid}{arch} — DoD-kop  «{titel}»")
            continue
        docs.write(pid, seed)
        n_seed += 1
        print(f"✓ seed      {pid}{arch} — DoD-kop geplaatst  «{titel}»")

    print(f"\nKlaar. rapport-synthese: {n_synth}"
          f"{f' (waarvan {n_synth_faal} teruggevallen op seed)' if n_synth_faal else ''}"
          f"  ·  DoD-kop geseed: {n_seed}"
          f"  ·  al goed: {n_skip}"
          f"  ·  geen DoD: {n_geen_dod}")
    if DRY:
        print("(DRY-RUN — er is niets geschreven. Laat --dry weg om echt uit te voeren.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
