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

# Atomiser-versie: BUMP bij elke logic-wijziging in de atomisatie (prompt/validator).
#   v1 = pre-A/B (losse enumeratie-broertjes, citatie-smeer in content).
#   v2 = A/B/addendum: samengestelde enumeratie-kaarten, schone citaties (source+reference).
# De ledger onthoudt per verwerkte input met welke versie hij liep; content die door een
# OUDERE versie is verwerkt telt niet meer als "klaar" en kan opnieuw (zie IntakeLedger.seen
# + --reatomise). Elk atoom draagt zijn eigen atomiser_version, zodat de migratie de oude
# corpus vindt zonder de nieuwe schone atomen opnieuw aan te raken.
ATOMISER_VERSION = 2

# Intake heeft een eigen ladder die bij de volwaardige flash begint: flash-LITE bleek in
# de acceptatie een atomiciteits-zeloot (23 snippers uit één column, aanhef als "bron") en
# gaf soms onparseerbare output. Intake is mens-geïnitieerd en laagfrequent — kwaliteit
# weegt hier zwaarder dan de laatste cent. Overschrijfbaar via env (geen secret).
INTAKE_LADDER = os.getenv(
    "LLM_KB_INTAKE_LADDER",
    "gemini:gemini-2.5-flash,mistral:mistral-small-latest,anthropic:claude-haiku-4-5-20251001")


def build_intake_prompt(raw: str, source_hint: str = "", tabular: bool = False) -> str:
    """De atomisatie-prompt uit de fase-2-brief. Dom en precies: splitsen en labelen.
    `tabular=True` voor tabeldata (Excel/CSV/Sheet): elke rij is een feit/meting, geen verhaal."""
    hint = f"\nBRON-HINT van de gebruiker (gebruik als de tekst zelf geen bron noemt): {source_hint}\n" \
        if source_hint.strip() else ""
    if tabular:
        hint += ("\nDIT IS TABELDATA (rijen 'kolom: waarde | ...'). Maak per rij een concreet\n"
                 "FEIT of een METING, geen verhaal: neem de getallen letterlijk over met hun\n"
                 "kolom-context (bijv. 'Betaalbereidheid segment Idealist: €120'). Verzin geen\n"
                 "verbanden tussen rijen; sla lege of louter technische kolommen over.\n")
    return (
        "Je splitst ruwe input in ATOMAIRE notities voor een kennisbank. Wees dom en precies:\n"
        "je oordeelt NIET over waarheid of zekerheid, je splitst en labelt alleen.\n\n"
        f"INPUT:\n\"\"\"{raw}\"\"\"\n{hint}\n"
        "REGELS:\n"
        "- Splits in losse eenheden: één idee per notitie. Niet te grof (verbergt ideeën),\n"
        "  niet te fijn (versplintert). Bij twijfel iets grover. Word geen atomiciteits-zeloot:\n"
        "  MAXIMAAL 12 notities per input — kies de belangrijkste; liever 8 sterke dan 20 snippers.\n"
        "- Alleen ZELFSTANDIGE bevindingen, metingen, conclusies, quotes en signalen worden\n"
        "  notities. Negeer aanhef, groeten, retorische vragen, meta-tekst, methodebeschrijvingen\n"
        "  zonder uitkomst, inhoudsopgaven, referentielijsten, auteurslijsten, colofons en\n"
        "  financierings-/dankwoordvermeldingen.\n"
        "- Een ENUMERATIE, stappenproces, tabel of opsomming is ÉÉN kenniseenheid, geen N losse\n"
        "  feiten: maak er één samengestelde notitie van met \"content\" = een korte kop-claim\n"
        "  (bijv. \"In de leerschoenproductie zijn 19 micro-stappen met kinderarbeid\n"
        "  geïdentificeerd\") en \"body\" = de stappen/regels zelf (nummering behouden).\n"
        "  Nooit één notitie per lijstregel.\n"
        "- Losse triviale definities of glossarium-regels (\"de term X betekent...\") worden GEEN\n"
        "  notitie — sla ze over (definities horen in het lexicon, niet in de kennisbank).\n"
        "- \"source\" = een KORTE aanduiding van publicatie of spreker (bijv. \"IDS 2021\" of\n"
        "  'column, quote X'), nooit een aanhef of zinsdeel uit de tekst. Copyright-regels,\n"
        "  ISBN en DOI horen NOOIT in \"content\": zet een DOI of ISBN één keer in \"reference\".\n"
        "  Zet NIET de artikel-URL in \"reference\" — de publicatie staat al in \"source\".\n"
        "- Schrijf elke notitie in het Nederlands (vertaal indien nodig), kort en op zichzelf leesbaar.\n"
        "- Leid het PROVENANCE-type af uit de aard van de bron (zie lijst); verzin geen\n"
        "  betrouwbaarheidsscore. Een onderzoeksinstituut of journal met DOI/ISBN =\n"
        "  peer_reviewed, ook als de toon geëngageerd is; advocacy is voor belangenorganisaties\n"
        "  zonder eigen onderzoek.\n"
        "- Kies het ONDERWERP uit de vaste lijst (zie lijst). Verzin geen nieuwe tags.\n"
        "  Kies bij twijfel het dichtstbijzijnde onderwerp; laat subject alleen leeg (\"\")\n"
        "  als er écht niets past.\n"
        "- Een quote is een quote (grounded dat het gezegd is), geen feit: noem de spreker in de\n"
        "  notitie en zet de flag \"quote\".\n"
        "- Markeer een claim met de flag \"verificatie_vereist\" als er een cijfer of stellige\n"
        "  bewering is zonder primaire bron (bijv. \"een studie zegt 90%\").\n"
        "- Een GEMETEN getal is een meting, geen vage claim: neem het getal mét methode en\n"
        "  conditie op in de notitie waar de tekst die geeft (bijv. \"15,6% afbraak in 236\n"
        "  dagen onder industriële compostering\"), en rond niet af.\n"
        "- Geef per atom een of meer LINK-hints: met welke bestaande onderwerpen/atomen hoort dit samen.\n"
        "- Geef bij de gekozen provenance een korte VERANTWOORDING in \"herkomst\" (≤1 zin,\n"
        "  alleen als de tekst er iets over zegt — nooit gokken, anders leeg):\n"
        "  survey → interne of externe bron en de steekproef (bijv. \"extern, N=1.200\");\n"
        "  expert_opinion → waarom deze persoon geloofwaardig is (functie, publicaties, boeken);\n"
        "  peer_reviewed → journal/DOI; certificate → welke standaard/certificeerder;\n"
        "  internal_data → welk systeem of welke meting.\n\n"
        "PROVENANCE-lijst: peer_reviewed | certificate | internal_data | survey | media |\n"
        "  advocacy | expert_opinion | internal_judgment | unknown\n"
        f"ONDERWERP-lijst: {', '.join(SUBJECTS)}\n\n"
        "OUTPUT: ALLEEN een JSON-array, geen proza, geen code-fences. Elk object:\n"
        '[ { "content": "...", "body": "<alleen bij een samengestelde notitie: de stappen/regels>",\n'
        '    "subject": "<uit lijst of leeg>", "provenance": "<uit lijst>",\n'
        '    "herkomst": "<korte verantwoording van de provenance-keuze, of leeg>",\n'
        '    "source": "<kort>", "reference": "<DOI/ISBN/URL of leeg>",\n'
        '    "flags": ["verificatie_vereist"?, "quote"?], "link_hints": ["..."] } ]')


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
                    "body": str(r.get("body") or "").strip()[:2500] or None,
                    "subject": subject,
                    "provenance": prov,
                    "provenance_note": str(r.get("herkomst") or "").strip()[:200] or None,
                    "source": str(r.get("source") or "").strip()[:160],
                    "reference": _schoon_reference(str(r.get("reference") or "")),
                    "flags": flags,
                    "link_hints": hints})
    # Backstop op de zeloot-cap uit de prompt: een model dat tóch doorsnippert wordt op
    # de eerste 15 gehouden (de prompt vraagt "kies de belangrijkste", dus de kop is de
    # curatie van het model zelf — geen stille aftopping van willekeurige staarten).
    return out[:15]


def _schoon_reference(ref: str) -> str | None:
    """Houd het reference-veld een échte citatie: een DOI of ISBN blijft (tracking-query eraf),
    maar een kale artikel-URL verdwijnt — de publicatie staat al in `source`, en de volle URL
    (met slug/utm) hoort daar niet als 'citatie' te staan (fix-brief bug 2)."""
    ref = (ref or "").strip()[:200]
    if not ref:
        return None
    if re.search(r"10\.\d{4,9}/\S+", ref) or "isbn" in ref.lower():
        return ref.split("?")[0].strip()          # DOI/ISBN: houden, tracking-query weg
    if re.match(r"^https?://", ref):
        return None                                # kale artikel-URL is redundant met de bron
    return ref


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
                   body=a.get("body"),
                   source=a["source"] or "onbekend",
                   reference=a.get("reference"),
                   source_date=a.get("source_date"),      # rapport-lus: afronddatum; anders None
                   provenance=a["provenance"],
                   provenance_note=a.get("provenance_note"),
                   tags=tags,
                   atomiser_version=ATOMISER_VERSION)


class IntakeLedger(JsonStore):
    """Idempotentie op het niveau van de RUWE input: een hash van (genormaliseerde tekst +
    bron-hint) → de atoom-ids die eruit ontstonden. Nodig omdat de LLM niet deterministisch
    is: dezelfde input kan bij een re-run nét anders gesplitst worden, en dan zou de
    content-hash-dedup alsnog bijna-duplicaten doorlaten. Dezelfde input nogmaals posten
    slaat de LLM dus helemaal over (sneller, goedkoper, gegarandeerd niets dubbel).

    Elke entry onthoudt ook de `atomiser_version` waarmee hij liep én de ruwe `raw`-tekst
    (reatomise-fix): zo telt input die door een OUDERE versie is verwerkt niet meer als
    'klaar', en is her-atomiseren self-contained — het brondocument staat in de ledger."""

    _WRITE_METHODS = ("record",)

    @staticmethod
    def raw_key(raw: str, source_hint: str) -> str:
        return hashlib.sha1((_norm_content(raw) + "|" + norm_bron(source_hint))
                            .encode("utf-8")).hexdigest()[:16]

    def seen(self, raw: str, source_hint: str) -> list[str] | None:
        """Al verwerkt ÉN met de huidige atomiser-versie → de atoom-ids (skip). Verwerkt door
        een oudere versie (of vóór de versionering) → None, zodat de nieuwe atomiser er alsnog
        overheen kan (idempotent per versie, niet over versies heen)."""
        rec = self._items.get(self.raw_key(raw, source_hint))
        if rec is None:
            return None
        if (rec.get("atomiser_version") or 0) < ATOMISER_VERSION:
            return None
        return list(rec.get("atom_ids") or [])

    def record(self, raw: str, source_hint: str, atom_ids: list[str]) -> None:
        from datetime import datetime
        self._items[self.raw_key(raw, source_hint)] = {
            "atom_ids": atom_ids, "source_hint": source_hint,
            "atomiser_version": ATOMISER_VERSION, "raw": (raw or "")[:12000],
            "at": datetime.now().isoformat(timespec="seconds")}
        self._save()

    def stale(self) -> list[dict]:
        """Ledger-entries die door een oudere atomiser-versie zijn verwerkt (of vóór de
        versionering). Voor de migratie: elk zo'n entry draagt zijn eigen `raw` + `source_hint`
        zodat her-atomiseren geen extern brondocument nodig heeft."""
        return [dict(rec) for rec in self._items.values()
                if (rec.get("atomiser_version") or 0) < ATOMISER_VERSION]


def atomiseer(raw: str, source_hint: str, reason_fn=reason,
              tabular: bool = False) -> list[dict] | None:
    """Alleen de LLM-atomisatie: ruwe tekst → gevalideerde atoom-dicts (geen opslag).
    Gedeeld door intake() en de staging-flow (die de dicts eerst laat nakijken). Bounded
    retry + fail-closed, identiek aan intake. None = ladder gaf niets bruikbaars."""
    if not (raw or "").strip():
        return []
    for _poging in range(2):
        out = reason_fn(build_intake_prompt(raw.strip(), source_hint, tabular=tabular),
                        ladder=INTAKE_LADDER, max_tokens=4000, json_mode=True,
                        call_site="kb_intake")
        if out is None:
            return None
        atoms = parse_intake(out)
        if atoms:
            return atoms
    return None


def intake(raw: str, source_hint: str, data_dir: str, reason_fn=reason,
           force: bool = False, tabular: bool = False) -> tuple[list[str], int] | None:
    """De hele fase-2-pijplijn: ruwe tekst → LLM-ladder → gevalideerde atomen →
    idempotent append aan notes.json. Twee dedup-lagen: (1) exact dezelfde ruwe input
    is al eens verwerkt MET de huidige atomiser-versie → LLM overslaan, niets toevoegen;
    (2) per atoom de stabiele hash(content+bron). `force=True` (reatomise) slaat de
    versie-skip over en draait de nieuwe atomiser er sowieso overheen; de content-hash
    zorgt dat schone v2-atomen nieuw zijn en identieke content nooit dubbelt. Geeft
    (nieuwe_ids, overgeslagen) terug, of None als de ladder geen antwoord gaf (fail-closed)."""
    if not (raw or "").strip():
        return [], 0
    ledger = IntakeLedger(f"{data_dir}/kennisbank_intake.json")
    if not force:
        eerder = ledger.seen(raw, source_hint)
        if eerder is not None:                 # zelfde input, zelfde versie → geen LLM, niets dubbel
            return [], len(eerder)
    atoms = atomiseer(raw, source_hint, reason_fn=reason_fn, tabular=tabular)
    if not atoms:
        return None                            # geen antwoord / niets bruikbaars → fail-closed
    notes = NotesStore(f"{data_dir}/notes.json")
    nieuw: list[str] = []
    overgeslagen = 0
    for a in atoms:
        kaart = atoom_kaart(a)
        if notes.get(kaart.id) is not None:    # zelfde content + zelfde bron → skip (idempotent)
            overgeslagen += 1
            continue
        # Voorkant-poort (founder 23 jul): de id-check hierboven vangt alleen EXACT content+bron.
        # Een near-duplicaat (andere bron of iets andere formulering) werd een tweede kaartje. De poort
        # stapelt bij (semantische) gelijkenis i.p.v. dubbelen; fail-open — bij twijfel een nieuw
        # kaartje mét markering, nooit stil stapelen. Fail-soft: elke fout → gewoon toevoegen.
        try:
            from nooch_village.kennis_dedup import beoordeel_kaart
            oordeel = beoordeel_kaart(kaart.claim, notes)
        except Exception:
            oordeel = {"verdict": "nieuw"}
        if oordeel.get("verdict") == "stapel" and oordeel.get("kaart_id"):
            notes.stack_provenance(oordeel["kaart_id"], source=kaart.source or "",
                                   reference=kaart.reference or "")
            overgeslagen += 1
            continue
        if oordeel.get("verdict") == "twijfel" and oordeel.get("kaart_id"):
            kaart.tags = list(kaart.tags) + [f"hint:dup?:{oordeel['kaart_id']}"]
        notes.add(kaart)
        nieuw.append(kaart.id)
    ledger.record(raw, source_hint, nieuw)
    return nieuw, overgeslagen
