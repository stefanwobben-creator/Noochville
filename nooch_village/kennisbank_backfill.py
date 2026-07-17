"""Signalen-backfill — de /signals-bibliotheek door de fase-2-atomiser halen.

    python -m nooch_village.kennisbank_backfill                # dry-run: aantallen + tokenschatting
    python -m nooch_village.kennisbank_backfill --apply        # echt atomiseren

Batcht ~8 signalen per LLM-call (besluit Stefan: 8-10× minder calls/tokens dan één call
per signaal); de bron staat per signaal inline zodat de atomiser hem letterlijk kan
behouden. Idempotent op twee niveaus: eigen state per signaal-id (verwerkte signalen
worden nooit opnieuw aangeboden) én de bestaande atoom-dedup op hash(content+bron).
Een gefaalde batch wordt niet geregistreerd en komt bij een her-run vanzelf terug.
"""
from __future__ import annotations

import argparse
from datetime import datetime

from nooch_village.kennisbank_intake import intake
from nooch_village.radar_store import RadarStore
from nooch_village.util import JsonStore

BATCH = 8
# ruwe schatting: ~4 tekens per token; output ~2 atomen à ~120 tokens per signaal
_CHARS_PER_TOKEN = 4
_OUT_TOKENS_PER_SIGNAAL = 240
_PROMPT_OVERHEAD_TOKENS = 700     # het vaste deel van de atomisatie-prompt


class BackfillState(JsonStore):
    """signaal-id → {atom_ids, at}. Alleen geslaagde batches worden geregistreerd."""

    _WRITE_METHODS = ("record",)

    def gedaan(self, signal_id: str) -> bool:
        return signal_id in self._items

    def record(self, signal_ids: list[str], atom_ids: list[str]) -> None:
        at = datetime.now().isoformat(timespec="seconds")
        for sid in signal_ids:
            self._items[sid] = {"atom_ids": atom_ids, "at": at}
        self._save()


def _signaal_bron(sig: dict) -> str:
    return (sig.get("source") or sig.get("link") or sig.get("feed") or "radar").strip()


def _signaal_tekst(sig: dict) -> str:
    """Content + rationale als één leesbare eenheid; markdown-sterretjes eruit."""
    content = (sig.get("content") or "").replace("**", "").strip()
    rat = (sig.get("rationale") or "").strip()
    return f"{content}\n  Context: {rat}" if rat else content


def _batch_raw(batch: list[dict]) -> str:
    regels = []
    for i, sig in enumerate(batch, 1):
        regels.append(f"SIGNAAL {i} [bron: {_signaal_bron(sig)}]:\n{_signaal_tekst(sig)}")
    return "\n\n".join(regels)


def backfill(data_dir: str = "data", apply: bool = False, batch_size: int = BATCH,
             intake_fn=intake) -> list[str]:
    """Geeft een rapport terug (regel per stap); schrijft alleen bij apply=True."""
    report: list[str] = []
    signalen = RadarStore(f"{data_dir}/radar.json").all_approved()
    state = BackfillState(f"{data_dir}/kennisbank_backfill.json")
    todo = [s for s in signalen if not state.gedaan(s.get("id") or "")]
    klaar = len(signalen) - len(todo)
    batches = [todo[i:i + batch_size] for i in range(0, len(todo), batch_size)]

    in_tokens = sum(len(_batch_raw(b)) // _CHARS_PER_TOKEN + _PROMPT_OVERHEAD_TOKENS
                    for b in batches)
    out_tokens = len(todo) * _OUT_TOKENS_PER_SIGNAAL
    report.append(f"signalen: {len(signalen)} goedgekeurd | {klaar} al verwerkt | {len(todo)} te doen")
    report.append(f"batches: {len(batches)} à ≤{batch_size} | geschat ~{len(todo) * 2} atomen | "
                  f"tokens ± {in_tokens:,} in / {out_tokens:,} uit".replace(",", "."))
    if not apply or not todo:
        return report

    for n, batch in enumerate(batches, 1):
        hint = "goedgekeurde radar-signalen; de bron staat per signaal tussen [bron: ...]"
        uitkomst = intake_fn(_batch_raw(batch), hint, data_dir)
        if uitkomst is None:
            report.append(f"✗ batch {n}/{len(batches)}: atomiser gaf niets — "
                          f"signalen blijven staan voor een her-run")
            continue
        nieuw, dubbel = uitkomst
        state.record([s.get("id") or "" for s in batch if s.get("id")], nieuw)
        report.append(f"✓ batch {n}/{len(batches)}: {len(batch)} signalen → "
                      f"{len(nieuw)} atomen ({dubbel} al bekend)")
    return report


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply", action="store_true", help="echt schrijven (default: dry-run)")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--batch", type=int, default=BATCH)
    args = p.parse_args()
    for line in backfill(args.data_dir, apply=args.apply, batch_size=args.batch):
        print(line)
    if not args.apply:
        print("\n(dry-run — niets geschreven; draai met --apply om te atomiseren)")


if __name__ == "__main__":
    main()
