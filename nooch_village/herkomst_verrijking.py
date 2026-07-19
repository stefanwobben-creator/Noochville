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
from nooch_village.kennisbank_intake import INTAKE_LADDER, SUBJECTS
from nooch_village.llm import reason
from nooch_village.notes_store import NotesStore
from nooch_village.util import JsonStore

_BATCH = 8          # kaartjes per LLM-call: groot genoeg om te schelen, klein genoeg om te parsen
_NOTE_MAX = 200


class VerrijkLedger(JsonStore):
    """atom_id → {"at": iso, "herkomst": "gevuld"|"leeg", "onderwerp": "gevuld"|"leeg"}.
    Eén poging per kaartje PER ASPECT. Oude entries ({"uitkomst": …}, van vóór de
    onderwerp-ronde) tellen als herkomst-geprobeerd maar onderwerp-niet — zo krijgen de
    eerste 29 kaartjes alsnog hun onderwerp zonder dubbele herkomst-calls."""

    _WRITE_METHODS = ("mark",)

    def seen(self, atom_id: str, aspect: str = "herkomst") -> bool:
        e = self._items.get(atom_id)
        if e is None:
            return False
        if aspect == "herkomst":
            return "herkomst" in e or "uitkomst" in e
        return aspect in e

    def mark(self, atom_id: str, **uitkomsten: str) -> None:
        from datetime import datetime
        e = self._items.get(atom_id) or {}
        oud = e.pop("uitkomst", None)                # oud formaat migreren bij herbezoek:
        if oud and "herkomst" not in e:              # de oude poging wás de herkomst-poging
            e["herkomst"] = oud
        e.update({"at": datetime.now().isoformat(timespec="seconds")}, **uitkomsten)
        self._items[atom_id] = e
        self._save()


def build_verrijk_prompt(kaarten: list[dict]) -> str:
    """Batch-prompt: per kaart alléén uit de gegeven tekst afleiden. Zelfde regels als de
    intake-prompt, maar dan achteraf. Doet herkomst én onderwerp in één call."""
    regels = "\n".join(
        f'- id "{k["id"]}": claim: "{k["claim"]}"'
        + (f' · body: "{k["body"][:400]}"' if k.get("body") else "")
        + f' · bron: "{k.get("source") or ""}"'
        + (f' · reference: "{k["reference"]}"' if k.get("reference") else "")
        + f' · huidige provenance: {k.get("provenance") or "unknown"}'
        for k in kaarten)
    return (
        "Je beoordeelt bestaande kennisbank-signals. Per signal drie velden:\n"
        "1. \"herkomst\": een korte verantwoording (≤1 zin) van de betrouwbaarheid van de\n"
        "   bron, ALLEEN als de gegeven tekst daar iets over zegt — nooit gokken, anders \"\".\n"
        "   survey → interne of externe bron en de steekproef (bijv. \"extern, N=1.200\");\n"
        "   expert_opinion → waarom deze persoon geloofwaardig is (functie, publicaties,\n"
        "   boeken); peer_reviewed → journal/DOI; certificate → welke standaard;\n"
        "   internal_data → welk systeem of welke meting.\n"
        "2. \"provenance\": alleen als de huidige 'unknown' is: kies uit\n"
        f"   {' | '.join(sorted(PROVENANCE_TRUST))} — anders herhaal je de huidige.\n"
        "3. \"onderwerp\": kies het best passende uit de vaste lijst; laat alleen leeg (\"\")\n"
        "   als er écht niets past. Verzin geen nieuwe onderwerpen.\n"
        f"ONDERWERP-lijst: {', '.join(SUBJECTS)}\n\n"
        f"SIGNALS:\n{regels}\n\n"
        "OUTPUT: ALLEEN een JSON-array, geen proza, geen code-fences:\n"
        '[ { "id": "...", "provenance": "...", "herkomst": "<of leeg>", "onderwerp": "<uit lijst of leeg>" } ]')


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
        subj = str(r.get("onderwerp") or "").strip().lower()
        out[str(r["id"])] = {
            "provenance": prov if prov in PROVENANCE_TRUST else None,
            "herkomst": str(r.get("herkomst") or "").strip()[:_NOTE_MAX] or None,
            "onderwerp": subj if subj in SUBJECTS else None,
        }
    return out


def _heeft_onderwerp(a) -> bool:
    return any(t in SUBJECTS for t in (a.tags or []))


def verrijk_herkomst(data_dir: str, *, reason_fn=None, dry_run: bool = False,
                     limit: int | None = None) -> dict:
    """De ronde zelf: herkomst-verantwoording ÉN onderwerp (het ongesorteerd-bakje leegt
    zichzelf, founder 19 jul) in één LLM-call per batch. Geeft een telling terug:
    {kandidaten, gevuld, prov_gezet, onderwerp_gezet, leeg, mislukt, overgeslagen}.
    Dry-run telt alleen de kandidaten (geen LLM, geen schrijf)."""
    fn = reason_fn or (lambda prompt: reason(prompt, ladder=INTAKE_LADDER,
                                             call_site="kb_verrijk"))
    notes = NotesStore(f"{data_dir}/notes.json")
    ledger = VerrijkLedger(f"{data_dir}/herkomst_verrijking.json")

    def _wil(a) -> tuple[bool, bool]:
        wil_note = (not (a.provenance_note or "").strip()
                    and not ledger.seen(a.id, "herkomst"))
        wil_subj = not _heeft_onderwerp(a) and not ledger.seen(a.id, "onderwerp")
        return wil_note, wil_subj

    actief = [a for a in notes.all() if not a.archived]
    kandidaten = [a for a in actief if any(_wil(a))]
    overgeslagen = len(actief) - len(kandidaten)
    if limit:
        kandidaten = kandidaten[:limit]
    telling = {"kandidaten": len(kandidaten), "gevuld": 0, "prov_gezet": 0,
               "onderwerp_gezet": 0, "leeg": 0, "mislukt": 0, "overgeslagen": overgeslagen}
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
            wil_note, wil_subj = _wil(a)
            marks: dict[str, str] = {}
            iets = False
            if wil_note:
                note = r.get("herkomst")
                nieuwe_prov = (r.get("provenance")
                               if (a.provenance or "unknown") in ("", "unknown") else None)
                if nieuwe_prov == "unknown":
                    nieuwe_prov = None
                if note or nieuwe_prov:
                    notes.verrijk_herkomst(a.id, note=note, provenance=nieuwe_prov)
                    telling["gevuld"] += 1 if note else 0
                    telling["prov_gezet"] += 1 if nieuwe_prov else 0
                    marks["herkomst"] = "gevuld"
                    iets = True
                else:
                    marks["herkomst"] = "leeg"   # geprobeerd, tekst zegt niets: onthouden
            if wil_subj:
                subj = r.get("onderwerp")
                if subj:
                    notes.add_tags(a.id, [subj])
                    telling["onderwerp_gezet"] += 1
                    marks["onderwerp"] = "gevuld"
                    iets = True
                else:
                    marks["onderwerp"] = "leeg"
            ledger.mark(a.id, **marks)
            if not iets:
                telling["leeg"] += 1
    return telling
