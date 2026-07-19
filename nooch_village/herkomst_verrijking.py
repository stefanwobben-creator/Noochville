"""Verrijkingsronde: bestaande kenniskaartjes alsnog een herkomst-verantwoording geven.

Nieuwe atomen krijgen hun `provenance_note` van de atomiser (survey → intern/extern + N=;
expert_opinion → waarom geloofwaardig; peer_reviewed → journal/DOI; …). Kaartjes van vóór die
wijziging hebben dat veld niet — deze ronde haalt ze in batches langs de LLM, zodat de
bibliotheek niet in twee generaties uiteenvalt (founder, 19 jul).

Ontwerp:
- Mens-geïnitieerd CLI-commando (`kb_verrijk_herkomst`), dry-run eerst; nooit een daemon-taak.
- Zelfde guardrail als de intake: de verantwoording komt UIT DE KAARTTEKST (claim/body/bron/
  reference) — zegt die niets over de herkomst, dan blijft het veld leeg. Nooit gokken.
- Provenance zelf wordt alleen ingevuld als hij nu 'unknown'/leeg is; een bestaande
  classificatie wordt nooit overschreven (expliciet > afgeleid).
- Grootboek (data/herkomst_verrijking.json): elk kaartje wordt één keer geprobeerd — ook een
  "niets gevonden" wordt onthouden, anders betaalt elke herdraai dezelfde LLM-calls opnieuw.
- Fail-closed: geen LLM-antwoord → kaartje blijft ongemoeid en NIET in het grootboek (kan bij
  een latere run alsnog). Schrijven loopt via NotesStore (locks, atomic write).
"""
from __future__ import annotations

import json
import re

from nooch_village.kennisbank import PROVENANCE_TRUST
from nooch_village.kennisbank_intake import INTAKE_LADDER
from nooch_village.llm import reason
from nooch_village.notes_store import NotesStore
from nooch_village.util import JsonStore

_BATCH = 8          # kaartjes per LLM-call: groot genoeg om te schelen, klein genoeg om te parsen
_NOTE_MAX = 200


class VerrijkLedger(JsonStore):
    """atom_id → {"at": iso, "uitkomst": "gevuld"|"leeg"}. Eén poging per kaartje."""

    _WRITE_METHODS = ("mark",)

    def seen(self, atom_id: str) -> bool:
        return atom_id in self._items

    def mark(self, atom_id: str, uitkomst: str) -> None:
        from datetime import datetime
        self._items[atom_id] = {"at": datetime.now().isoformat(timespec="seconds"),
                                "uitkomst": uitkomst}
        self._save()


def build_verrijk_prompt(kaarten: list[dict]) -> str:
    """Batch-prompt: per kaart alléén uit de gegeven tekst afleiden. Zelfde regels als de
    intake-prompt, maar dan achteraf."""
    regels = "\n".join(
        f'- id "{k["id"]}": claim: "{k["claim"]}"'
        + (f' · body: "{k["body"][:400]}"' if k.get("body") else "")
        + f' · bron: "{k.get("source") or ""}"'
        + (f' · reference: "{k["reference"]}"' if k.get("reference") else "")
        + f' · huidige provenance: {k.get("provenance") or "unknown"}'
        for k in kaarten)
    return (
        "Je beoordeelt de HERKOMST van bestaande kennisbank-kaartjes. Per kaartje:\n"
        "1. \"herkomst\": een korte verantwoording (≤1 zin) van de betrouwbaarheid van de\n"
        "   bron, ALLEEN als de gegeven tekst daar iets over zegt — nooit gokken, anders \"\".\n"
        "   survey → interne of externe bron en de steekproef (bijv. \"extern, N=1.200\");\n"
        "   expert_opinion → waarom deze persoon geloofwaardig is (functie, publicaties,\n"
        "   boeken); peer_reviewed → journal/DOI; certificate → welke standaard;\n"
        "   internal_data → welk systeem of welke meting.\n"
        "2. \"provenance\": alleen als de huidige 'unknown' is: kies uit\n"
        f"   {' | '.join(sorted(PROVENANCE_TRUST))} — anders herhaal je de huidige.\n\n"
        f"KAARTJES:\n{regels}\n\n"
        "OUTPUT: ALLEEN een JSON-array, geen proza, geen code-fences:\n"
        '[ { "id": "...", "provenance": "...", "herkomst": "<of leeg>" } ]')


def parse_verrijk(text: str | None) -> dict[str, dict]:
    """LLM-output → {atom_id: {provenance, herkomst}}. Fail-closed: onparseerbaar → {}."""
    if not text:
        return {}
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    start, end = cleaned.find("["), cleaned.rfind("]")
    if start == -1 or end < start:
        return {}
    try:
        rows = json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError:
        return {}
    out: dict[str, dict] = {}
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict) or not r.get("id"):
            continue
        prov = str(r.get("provenance") or "").strip().lower()
        out[str(r["id"])] = {
            "provenance": prov if prov in PROVENANCE_TRUST else None,
            "herkomst": str(r.get("herkomst") or "").strip()[:_NOTE_MAX] or None,
        }
    return out


def verrijk_herkomst(data_dir: str, *, reason_fn=None, dry_run: bool = False,
                     limit: int | None = None) -> dict:
    """De ronde zelf. Geeft een telling terug: {kandidaten, gevuld, prov_gezet, leeg,
    mislukt, overgeslagen}. Dry-run telt alleen de kandidaten (geen LLM, geen schrijf)."""
    fn = reason_fn or (lambda prompt: reason(prompt, ladder=INTAKE_LADDER,
                                             call_site="kb_verrijk_herkomst"))
    notes = NotesStore(f"{data_dir}/notes.json")
    ledger = VerrijkLedger(f"{data_dir}/herkomst_verrijking.json")
    kandidaten = [a for a in notes.all()
                  if not a.archived and not (a.provenance_note or "").strip()
                  and not ledger.seen(a.id)]
    overgeslagen = len([a for a in notes.all() if not a.archived]) - len(kandidaten)
    if limit:
        kandidaten = kandidaten[:limit]
    telling = {"kandidaten": len(kandidaten), "gevuld": 0, "prov_gezet": 0,
               "leeg": 0, "mislukt": 0, "overgeslagen": overgeslagen}
    if dry_run or not kandidaten:
        return telling
    for i in range(0, len(kandidaten), _BATCH):
        batch = kandidaten[i:i + _BATCH]
        prompt = build_verrijk_prompt([
            {"id": a.id, "claim": a.claim, "body": a.body, "source": a.source,
             "reference": a.reference, "provenance": a.provenance} for a in batch])
        uit = parse_verrijk(fn(prompt))
        for a in batch:
            r = uit.get(a.id)
            if r is None:
                telling["mislukt"] += 1          # geen antwoord: NIET in het grootboek
                continue
            note = r.get("herkomst")
            nieuwe_prov = (r.get("provenance")
                           if (a.provenance or "unknown") in ("", "unknown") else None)
            if nieuwe_prov == "unknown":
                nieuwe_prov = None
            if note or nieuwe_prov:
                notes.verrijk_herkomst(a.id, note=note, provenance=nieuwe_prov)
                telling["gevuld"] += 1 if note else 0
                telling["prov_gezet"] += 1 if nieuwe_prov else 0
                ledger.mark(a.id, "gevuld")
            else:
                ledger.mark(a.id, "leeg")        # geprobeerd, tekst zegt niets: onthouden
                telling["leeg"] += 1
    return telling
