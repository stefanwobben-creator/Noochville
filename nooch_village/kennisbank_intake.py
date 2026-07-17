"""Kennisbank fase 2 — server-side intake: fleeting → atomic, via de LLM-ladder.

Laag 1 blijft DOM (master-brief §1/§4): de intake splitst en labelt alleen — geen oordeel
over waarheid, geen consensus, geen veld. Trust wordt nooit door de LLM gezet; die wordt
afgeleid uit provenance (kennisbank.atom_trust) op het moment van gebruik in laag 2.

Patroon volgt curate.py: build-prompt + parser + deterministische validator (fail-closed),
met een injecteerbare reason-functie zodat alles testbaar is zonder netwerk.

Idempotentie (besluit Stefan dd 2026-07-17): de stabiele id is een hash van
genormaliseerde content + genormaliseerde BRON. Dezelfde claim uit een ándere bron blijft
dus een aparte stem (dat is precies wat de woozle-guard in laag 2 nodig heeft);
dezelfde claim uit dezelfde bron wordt nooit gedupliceerd.
"""
from __future__ import annotations

import hashlib
import json
import os
import re

from nooch_village.insight import Insight
from nooch_village.kennisbank import PROVENANCE_TRUST, norm_bron
from nooch_village.llm import reason
from nooch_village.notes_store import NotesStore
from nooch_village.util import JsonStore

# ── Het vaste onderwerp-vocabulaire (master-brief §5) ────────────────────────
# Eén bron: de prompt, de validator én de view lezen deze lijst. Uitbreiden is een
# bewust besluit (nieuwe regel hier), nooit een bijproduct van één losse tekst.
SUBJECTS = ("duurzame-schoenen", "outsole", "leer", "wol", "vegan-leer", "materiaal",
            "regelgeving", "concurrentie", "segment", "prijs", "markt", "keyword",
            "ethiek", "vraag")

# Subject-loze atomen zijn zichtbaar, geen stille restcategorie (besluit Stefan):
# de view toont ze in het "ongesorteerd"-bakje zodat een mens ze kan cureren.
ONGESORTEERD = "ongesorteerd"

FLAG_VERIFICATIE = "verificatie_vereist"
_GELDIGE_FLAGS = {FLAG_VERIFICATIE, "quote", "contested"}

# Intake heeft een eigen ladder die bij de volwaardige flash begint: flash-LITE bleek in
# de acceptatie een atomiciteits-zeloot (23 snippers uit één column, aanhef als "bron") en
# gaf soms onparseerbare output. Intake is mens-geïnitieerd en laagfrequent — kwaliteit
# weegt hier zwaarder dan de laatste cent. Overschrijfbaar via env (geen secret).
INTAKE_LADDER = os.getenv(
    "LLM_KB_INTAKE_LADDER",
    "gemini:gemini-2.5-flash,mistral:mistral-small-latest,anthropic:claude-haiku-4-5-20251001")


def build_intake_prompt(raw: str, source_hint: str = "") -> str:
    """De atomisatie-prompt uit de fase-2-brief. Dom en precies: splitsen en labelen."""
    hint = f"\nBRON-HINT van de gebruiker (gebruik als de tekst zelf geen bron noemt): {source_hint}\n" \
        if source_hint.strip() else ""
    return (
        "Je splitst ruwe input in ATOMAIRE notities voor een kennisbank. Wees dom en precies:\n"
        "je oordeelt NIET over waarheid of zekerheid, je splitst en labelt alleen.\n\n"
        f"INPUT:\n\"\"\"{raw}\"\"\"\n{hint}\n"
        "REGELS:\n"
        "- Splits in losse eenheden: één idee per notitie. Niet te grof (verbergt ideeën),\n"
        "  niet te fijn (versplintert). Bij twijfel iets grover. Word geen atomiciteits-zeloot:\n"
        "  een column van deze omvang levert doorgaans 8 tot 12 notities, geen 20+.\n"
        "- Alleen inhoudelijke claims, feiten, quotes en signalen worden notities. Negeer\n"
        "  aanhef, groeten, retorische vragen, de vraag van de lezer en meta-tekst.\n"
        "- \"source\" = de publicatie of spreker (bijv. de column, of 'column, quote X'),\n"
        "  nooit een aanhef of zinsdeel uit de tekst.\n"
        "- Schrijf elke notitie in het Nederlands (vertaal indien nodig), kort en op zichzelf leesbaar.\n"
        "- Behoud de bron letterlijk. Leid het PROVENANCE-type af uit de aard van de bron\n"
        "  (zie lijst). Verzin geen betrouwbaarheidsscore.\n"
        "- Kies het ONDERWERP uit de vaste lijst (zie lijst). Verzin geen nieuwe tags.\n"
        "  Past er echt geen? Laat subject dan leeg (\"\").\n"
        "- Een quote is een quote (grounded dat het gezegd is), geen feit: noem de spreker in de\n"
        "  notitie en zet de flag \"quote\".\n"
        "- Markeer een claim met de flag \"verificatie_vereist\" als er een cijfer of stellige\n"
        "  bewering is zonder primaire bron (bijv. \"een studie zegt 90%\").\n"
        "- Geef per atom een of meer LINK-hints: met welke bestaande onderwerpen/atomen hoort dit samen.\n\n"
        "PROVENANCE-lijst: peer_reviewed | certificate | internal_data | survey | media |\n"
        "  advocacy | expert_opinion | internal_judgment | unknown\n"
        f"ONDERWERP-lijst: {', '.join(SUBJECTS)}\n\n"
        "OUTPUT: ALLEEN een JSON-array, geen proza, geen code-fences. Elk object:\n"
        '[ { "content": "...", "subject": "<uit lijst of leeg>", "provenance": "<uit lijst>",\n'
        '    "source": "<letterlijk>", "flags": ["verificatie_vereist"?, "quote"?],\n'
        '    "link_hints": ["..."] } ]')


def parse_intake(text: str | None) -> list[dict]:
    """LLM-output → gevalideerde atoom-dicts. Fail-closed en onbreekbaar:
    onparseerbaar → []; provenance buiten de lijst → 'unknown'; subject buiten de
    lijst → '' (belandt in het ongesorteerd-bakje); onbekende flags vallen weg."""
    if not text:
        return []
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    start, end = cleaned.find("["), cleaned.rfind("]")
    if start == -1 or end < start:
        return []
    try:
        rows = json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError:
        return []
    if not isinstance(rows, list):
        return []
    out: list[dict] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        content = str(r.get("content") or "").strip()
        if not content:
            continue
        subject = str(r.get("subject") or "").strip().lower()
        if subject not in SUBJECTS:
            subject = ""                       # → ongesorteerd-bakje, mens cureert
        prov = str(r.get("provenance") or "").strip().lower()
        if prov not in PROVENANCE_TRUST:
            prov = "unknown"
        flags = [f for f in (r.get("flags") or []) if isinstance(f, str) and f in _GELDIGE_FLAGS]
        hints = [str(h).strip() for h in (r.get("link_hints") or []) if str(h).strip()][:5]
        out.append({"content": content[:500],
                    "subject": subject,
                    "provenance": prov,
                    "source": str(r.get("source") or "").strip()[:160],
                    "flags": flags,
                    "link_hints": hints})
    return out


def stable_id(content: str, source: str) -> str:
    """Stabiele atoom-id: hash van genormaliseerde content + genormaliseerde bron.
    Zelfde claim + zelfde bron → zelfde id (re-run dupliceert niets); zelfde claim uit
    een ANDERE bron → andere id (blijft een aparte stem voor de woozle-guard)."""
    key = _norm_content(content) + "|" + norm_bron(source)
    return "atom_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def _norm_content(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def atoom_kaart(a: dict) -> Insight:
    """Atoom-dict → kaart in de bestaande bibliotheek. Mapping: subject = tags[0]
    (leeg subject krijgt géén tag → ongesorteerd), flags en link-hints ook in tags
    (hint als 'hint:...' zodat curatie ze herkent). Geen trust, geen oordeel."""
    tags = ([a["subject"]] if a["subject"] else []) + a["flags"] \
        + [f"hint:{h}" for h in a["link_hints"]]
    return Insight(id=stable_id(a["content"], a["source"]),
                   claim=a["content"],
                   source=a["source"] or "onbekend",
                   provenance=a["provenance"],
                   tags=tags)


class IntakeLedger(JsonStore):
    """Idempotentie op het niveau van de RUWE input: een hash van (genormaliseerde tekst +
    bron-hint) → de atoom-ids die eruit ontstonden. Nodig omdat de LLM niet deterministisch
    is: dezelfde input kan bij een re-run nét anders gesplitst worden, en dan zou de
    content-hash-dedup alsnog bijna-duplicaten doorlaten. Dezelfde input nogmaals posten
    slaat de LLM dus helemaal over (sneller, goedkoper, gegarandeerd niets dubbel)."""

    _WRITE_METHODS = ("record",)

    @staticmethod
    def raw_key(raw: str, source_hint: str) -> str:
        return hashlib.sha1((_norm_content(raw) + "|" + norm_bron(source_hint))
                            .encode("utf-8")).hexdigest()[:16]

    def seen(self, raw: str, source_hint: str) -> list[str] | None:
        rec = self._items.get(self.raw_key(raw, source_hint))
        return list(rec.get("atom_ids") or []) if rec else None

    def record(self, raw: str, source_hint: str, atom_ids: list[str]) -> None:
        from datetime import datetime
        self._items[self.raw_key(raw, source_hint)] = {
            "atom_ids": atom_ids, "source_hint": source_hint,
            "at": datetime.now().isoformat(timespec="seconds")}
        self._save()


def intake(raw: str, source_hint: str, data_dir: str, reason_fn=reason
           ) -> tuple[list[str], int] | None:
    """De hele fase-2-pijplijn: ruwe tekst → LLM-ladder → gevalideerde atomen →
    idempotent append aan notes.json. Twee dedup-lagen: (1) exact dezelfde ruwe input
    is al eens verwerkt → LLM overslaan, niets toevoegen; (2) per atoom de stabiele
    hash(content+bron). Geeft (nieuwe_ids, overgeslagen) terug, of None als de ladder
    geen antwoord gaf (fail-closed, caller meldt het)."""
    if not (raw or "").strip():
        return [], 0
    ledger = IntakeLedger(f"{data_dir}/kennisbank_intake.json")
    eerder = ledger.seen(raw, source_hint)
    if eerder is not None:                     # zelfde input al verwerkt → geen LLM, niets dubbel
        return [], len(eerder)
    # max_tokens ruim: een volle column produceert ~10 atomen mét hints; te krap =
    # afgekapte JSON → fail-closed (bewust: half salvagen zou via de ledger re-runs
    # blokkeren terwijl de staart van de input stilletjes ontbreekt).
    out = reason_fn(build_intake_prompt(raw.strip(), source_hint),
                    ladder=INTAKE_LADDER, max_tokens=4000, json_mode=True,
                    call_site="kb_intake")
    if out is None:
        return None
    atoms = parse_intake(out)
    if not atoms:
        return None                            # wél antwoord maar niets bruikbaars → fail-closed
    notes = NotesStore(f"{data_dir}/notes.json")
    nieuw: list[str] = []
    overgeslagen = 0
    for a in atoms:
        kaart = atoom_kaart(a)
        if notes.get(kaart.id) is not None:    # zelfde content + zelfde bron → skip (idempotent)
            overgeslagen += 1
            continue
        notes.add(kaart)
        nieuw.append(kaart.id)
    ledger.record(raw, source_hint, nieuw)
    return nieuw, overgeslagen
