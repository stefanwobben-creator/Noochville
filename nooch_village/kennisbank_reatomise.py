"""Re-atomiseer bestaande atomen met de nieuwe atomiser (fixup-brief, taak 2).

De A/B-fix raakte alleen nieuwe ingests; de pre-fix atomen (o.a. de CLARISSA-stappen:
losse broertjes + citatie-smeer) staan nog in de bibliotheek. Deze migratie haalt het
brondocument opnieuw door de nieuwe atomiser en ruimt het oude op — append-only en
mens-veilig.

    # per brondocument dat nog in de ledger staat (self-contained, raw is bewaard):
    python -m nooch_village.kennisbank_reatomise --stale            # dry-run: wat zou er gebeuren
    python -m nooch_village.kennisbank_reatomise --stale --apply

    # of expliciet één document opnieuw aanbieden (bv. een PDF die van vóór de ledger is):
    python -m nooch_village.kennisbank_reatomise --source "CLARISSA EER5 (IDS)" --pdf pad.pdf
    python -m nooch_village.kennisbank_reatomise --source "..." --pdf pad.pdf --apply

Regels (fixup-brief):
- Alleen atomen van een OUDERE atomiser-versie (of zonder versie) zijn kandidaat.
- Een oud atoom dat AL IN GEBRUIK is (gelinkt aan een inzicht, in een open spel, of in een
  merged_from) wordt NOOIT automatisch vervangen — het komt op de review-lijst.
- Ongebruikte oude atomen worden gearchiveerd met een superseded_by-link naar de nieuwe
  (nooit hard gewist). Idempotent: een her-run doet niets.
- Dry-run eerst; --apply schrijft.
"""
from __future__ import annotations

import argparse

from nooch_village.kennisbank import KennisbankStore, load_atoms, norm_bron
from nooch_village.kennisbank_intake import ATOMISER_VERSION, IntakeLedger, intake
from nooch_village.kennisbank_spel import SpelStore
from nooch_village.llm import reason
from nooch_village.notes_store import NotesStore

_CHARS_PER_TOKEN = 4
_OUT_TOKENS_PER_ATOOM = 200


def in_use_ids(data_dir: str) -> set[str]:
    """Atomen die menselijk werk dragen en dus niet auto-vervangen mogen worden: gelinkt aan
    een inzicht (evidence), in een open spel-hand, of als origineel onder een merge-kaart."""
    used: set[str] = set()
    for ins in KennisbankStore(f"{data_dir}/kennisbank.json").all():
        for l in ins.get("evidence") or []:
            if l.get("atom_id"):
                used.add(l["atom_id"])
    for s in SpelStore(f"{data_dir}/kennisbank_spel.json").open_spellen():
        for k in s.get("set") or []:
            if k.get("atom_id"):
                used.add(k["atom_id"])
    for a in load_atoms(data_dir, include_archived=True).values():
        for mid in a.get("merged_from") or []:
            used.add(mid)
    return used


def _kandidaten(data_dir: str, source_label: str) -> dict[str, dict]:
    """Actieve atomen van dit brondocument, gemaakt door een oudere atomiser-versie."""
    n = norm_bron(source_label)
    return {aid: a for aid, a in load_atoms(data_dir, include_archived=False).items()
            if norm_bron(a.get("source") or "") == n
            and (a.get("atomiser_version") or 0) < ATOMISER_VERSION
            and not a.get("superseded_by")}


def reatomise_document(data_dir: str, raw_chunks: list[str], source_label: str,
                       apply: bool = False, reason_fn=reason) -> dict:
    """Her-atomiseer één brondocument. raw_chunks = de ruwe tekst (PDF → meerdere chunks,
    tekst/URL → één). Geeft een rapport-dict terug; schrijft alleen bij apply=True."""
    kandidaten = _kandidaten(data_dir, source_label)
    used = in_use_ids(data_dir)
    ongebruikt = {aid: a for aid, a in kandidaten.items() if aid not in used}
    geflagd = {aid: a for aid, a in kandidaten.items() if aid in used}

    tekens = sum(len(c) for c in raw_chunks)
    tok_in = tekens // _CHARS_PER_TOKEN + 700 * len(raw_chunks)
    tok_uit = len(kandidaten) * _OUT_TOKENS_PER_ATOOM
    rapport = {"source": source_label, "oud": len(kandidaten),
               "ongebruikt": len(ongebruikt), "geflagd": len(geflagd),
               "geflagd_ids": sorted(geflagd), "tok_in": tok_in, "tok_uit": tok_uit,
               "nieuw": [], "regels": []}
    rapport["regels"].append(
        f"{source_label}: {len(kandidaten)} oude atomen → {len(ongebruikt)} te vervangen, "
        f"{len(geflagd)} in gebruik (review), ± {tok_in} in / {tok_uit} uit tokens")
    if geflagd:
        rapport["regels"].append(
            f"  ⚠ review (in gebruik, niet aangeraakt): {', '.join(sorted(geflagd))}")
    if not apply:
        return rapport
    if not ongebruikt and not geflagd:
        rapport["regels"].append("  = niets te doen (al gemigreerd of geen oude atomen)")
        return rapport

    nieuw: list[str] = []
    for chunk in raw_chunks:
        res = intake(chunk, source_label, data_dir, reason_fn=reason_fn, force=True)
        if res is None:
            rapport["regels"].append("  ✗ atomiser gaf niets voor een chunk — "
                                     "oude atomen blijven staan voor een her-run")
            continue
        n, _ = res
        nieuw += n
    rapport["nieuw"] = nieuw
    if not nieuw:
        rapport["regels"].append("  ✗ geen nieuwe atomen — niets gearchiveerd (fail-closed)")
        return rapport
    notes = NotesStore(f"{data_dir}/notes.json")
    gearchiveerd = sum(1 for aid in ongebruikt if notes.supersede(aid, nieuw))
    rapport["regels"].append(
        f"  ✓ {len(nieuw)} nieuwe atomen; {gearchiveerd} oude gearchiveerd met "
        f"superseded_by-link ({len(geflagd)} in gebruik overgeslagen)")
    return rapport


def _stale_documenten(data_dir: str) -> list[tuple[list[str], str]]:
    """Brondocumenten uit de ledger die door een oudere versie zijn verwerkt: elk draagt
    zijn eigen bewaarde raw + source_hint, dus self-contained her-atomiseerbaar."""
    docs = []
    for rec in IntakeLedger(f"{data_dir}/kennisbank_intake.json").stale():
        raw = rec.get("raw")
        if raw:
            docs.append(([raw], rec.get("source_hint") or ""))
    return docs


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply", action="store_true", help="echt schrijven (default: dry-run)")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--stale", action="store_true",
                   help="alle door een oudere versie verwerkte ledger-documenten")
    p.add_argument("--source", help="bron-label van het document (matcht de oude atomen)")
    p.add_argument("--pdf", help="pad naar een PDF om opnieuw aan te bieden")
    p.add_argument("--text-file", help="pad naar een tekstbestand om opnieuw aan te bieden")
    args = p.parse_args()

    documenten: list[tuple[list[str], str]] = []
    if args.stale:
        documenten = _stale_documenten(args.data_dir)
        if not documenten:
            print("Geen ledger-documenten van een oudere atomiser-versie gevonden.")
    elif args.source and args.pdf:
        from nooch_village.kennisbank_sources import van_pdf
        chunks = van_pdf(open(args.pdf, "rb").read(), args.source)
        if chunks is None:
            raise SystemExit("Geen tekstlaag in de PDF (scan?).")
        documenten = [([c for c, _ in chunks], args.source)]
    elif args.source and args.text_file:
        documenten = [([open(args.text_file, encoding="utf-8").read()], args.source)]
    else:
        raise SystemExit("Gebruik --stale, of --source met --pdf/--text-file.")

    tot_oud = tot_nieuw = tot_flag = 0
    for raw_chunks, label in documenten:
        rap = reatomise_document(args.data_dir, raw_chunks, label, apply=args.apply)
        for regel in rap["regels"]:
            print(regel)
        tot_oud += rap["oud"]
        tot_nieuw += len(rap["nieuw"])
        tot_flag += rap["geflagd"]
    print(f"\nTotaal: {tot_oud} oude atomen | {tot_flag} in gebruik (review)"
          + (f" | {tot_nieuw} nieuwe atomen geschreven" if args.apply else ""))
    if not args.apply:
        print("(dry-run — niets geschreven; draai met --apply)")


if __name__ == "__main__":
    main()
