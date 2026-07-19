"""Bronlink-herstel — zet de ÉCHT gebruikte artikellink terug op bestaande signals.

    python -m nooch_village.kennisbank_bronherstel                # dry-run: wat zou er gebeuren
    python -m nooch_village.kennisbank_bronherstel --apply        # echt terugzetten

Aanleiding (founder, 19 jul): kaartjes die uit een radar-signaal zijn gepromoveerd
droegen soms een door de LLM overgetypte DOI/citatie als reference — die kan
gehallucineerd zijn en doodlopen. De échte artikellink stond al die tijd op het
radar-item (promoted_atom_id ↔ link). Dit script haalt hem terug:

- alleen atomen waarvan de reference GEEN werkende link is (leeg, DOI, ISBN, label);
- een bestaande http(s)/kbref-reference wordt NOOIT overschreven;
- gearchiveerde atomen en radar-items zonder link/promotie slaan we over;
- idempotent: na een run heeft elk hersteld atoom een URL-reference en doet een
  tweede run niets meer. De oude reference staat in het rapport (niets stil weg).

Voor kaartjes uit "Verwerk de bron" (geplakte URL of PDF-upload) is de oorspronkelijke
link/PDF vroeger nergens bewaard — die zijn niet terug te halen; vanaf nu bewaart de
intake ze wél (kennisbank_sources.bron_reference + data/kbref/).
"""
from __future__ import annotations

import argparse

from nooch_village.notes_store import NotesStore
from nooch_village.radar_store import RadarStore


def _is_link(ref: str) -> bool:
    return (ref or "").strip().lower().startswith(("http://", "https://", "/kbref/"))


def herstel(data_dir: str, apply: bool = False) -> list[dict]:
    """Geeft de herstel-regels terug: [{atom_id, oud, nieuw, claim}]. Bij apply=True is de
    reference dan al gezet (NotesStore.set_reference, append-only versiegedrag van de store)."""
    radar = RadarStore(f"{data_dir}/radar.json")
    notes = NotesStore(f"{data_dir}/notes.json")
    regels: list[dict] = []
    gezien: set[str] = set()
    for it in radar.all_items():
        aid = (it.get("promoted_atom_id") or "").strip()
        link = (it.get("link") or "").strip()
        if not aid or aid in gezien or not link.lower().startswith("http"):
            continue
        gezien.add(aid)
        a = notes.get(aid)
        if a is None or a.archived or _is_link(a.reference or ""):
            continue
        regels.append({"atom_id": aid, "oud": (a.reference or "").strip() or None,
                       "nieuw": link[:200], "claim": (a.claim or "")[:80]})
        if apply:
            notes.set_reference(aid, link[:200])
    return regels


def main() -> None:
    p = argparse.ArgumentParser(description="Bronlink-herstel voor kennisbank-signals")
    p.add_argument("--apply", action="store_true", help="echt terugzetten (default: dry-run)")
    p.add_argument("--data", default="data", help="pad naar de data-map (default: data)")
    args = p.parse_args()
    regels = herstel(args.data, apply=args.apply)
    if not regels:
        print("Niets te herstellen — alle gepromoveerde signals hebben al een link-reference.")
        return
    for r in regels:
        oud = r["oud"] or "(leeg)"
        print(f"{r['atom_id']}  {oud}  →  {r['nieuw']}\n    {r['claim']}")
    print(f"\n{len(regels)} kaartje(s) {'hersteld' if args.apply else 'te herstellen'}"
          + ("" if args.apply else " — draai met --apply om echt terug te zetten"))


if __name__ == "__main__":
    main()
