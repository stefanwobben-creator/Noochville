"""Kennis-eerst — deterministische raadpleging van Lara's kennislaag bij projectstart.

Elke rol die aan een project begint raadpleegt EERST de kennislaag en neemt wat hij vindt
mee als context, zodat hij niet opnieuw uitvindt maar aanvult. Drie bronnen, alle drie
bestaande stores (alleen store-methodes, geen LLM):
  - kaartjes (atomen)  : NotesStore.relevant_for — het bestaande zeldzaamheids-gewogen
    woord-overlap-mechanisme op het word-veld;
  - inzichten (laag 2) : KennisbankStore — zelfde soort matching, gespiegeld op titel + why,
    met het live berekende verdict-woord (field/verdict) erbij;
  - signalen           : RadarStore.all_approved — goedgekeurd én nog niet gepromoveerd
    naar de kennisbank (promoted_atom_id leeg).

Fail-soft overal: een ontbrekende of kapotte store levert een lege deelverzameling op en
blokkeert het projectwerk nooit. De raadpleging zelf is puur deterministisch; de gevonden
kennis reist mee in de LLM-calls die er tóch al waren (geen extra LLM-calls).

Zichtbaarheid: `meld_raadpleging` publiceert bij elke raadpleging (ook bij 0/0/0) een
`kennis_geraadpleegd`-event op de bus — de Village-logger schrijft dat naar system_log.jsonl —
en logt één regel. De feed-regel op de projectkaart ("📚 raadpleegde de kennisbank: …")
zetten de aanroepers zelf via het bestaande ledger.add_feed_entry(kind="system")."""
from __future__ import annotations

import logging
import os

log = logging.getLogger("village.kennis")

# Harde cap op het prompt-context-blok: prompts mogen niet exploderen.
MAX_BLOK_CHARS = 1500

_SOORTEN = ("kaartjes", "inzichten", "signalen")


def _woorden(tekst: str) -> set[str]:
    from nooch_village.notes_store import _woorden as w   # één woord-splitser, geen kopie
    return w(tekst or "")


def _match(zoek: set[str], docs: list[tuple], limit: int) -> list:
    """Spiegel van NotesStore.relevant_for: gedeelde woorden gewogen op zeldzaamheid
    (1/doc_freq) — 'barefoot' (zeldzaam) telt zwaarder dan 'shoes' (overal). Geen vaste
    stopwoordenlijst; sterkste matches eerst, max `limit`. `docs` = [(object, tekst)]."""
    if not zoek or not docs:
        return []
    doc_freq: dict[str, int] = {}
    for _, tekst in docs:
        for w in _woorden(tekst):
            doc_freq[w] = doc_freq.get(w, 0) + 1
    gescoord = []
    for obj, tekst in docs:
        gedeeld = zoek & _woorden(tekst)
        score = sum(1.0 / doc_freq[w] for w in gedeeld)
        if score > 0:
            gescoord.append((score, obj))
    gescoord.sort(key=lambda t: -t[0])                    # stabiel: gelijke score → store-volgorde
    return [obj for _, obj in gescoord[:limit]]


def _regel(tekst: str, cap: int = 160) -> str:
    """Eén regel tekst: whitespace platgeslagen, hard afgekapt."""
    return " ".join(str(tekst or "").split())[:cap]


def _kaartjes(data_dir: str, tekst: str, limit: int) -> list[dict]:
    from nooch_village.notes_store import NotesStore
    pad = os.path.join(data_dir, "notes.json")
    if not os.path.exists(pad):
        return []
    hits = NotesStore(pad).relevant_for(tekst, limit=limit)
    return [{"id": n.id, "tekst": _regel(n.claim), "bron": _regel(n.source, 80)}
            for n in hits if not n.archived]              # gearchiveerd = buiten beeld (curatie)


def _inzichten(data_dir: str, tekst: str, limit: int) -> list[dict]:
    from nooch_village.kennisbank import KennisbankStore, field, load_atoms, verdict
    pad = os.path.join(data_dir, "kennisbank.json")
    if not os.path.exists(pad):
        return []
    alle = KennisbankStore(pad).all()
    docs = [(ins, f"{ins.get('title', '')} {ins.get('why', '')}") for ins in alle]
    hits = _match(_woorden(tekst), docs, limit)
    if not hits:
        return []
    atoms = load_atoms(data_dir)                          # voor het live verdict-woord
    uit = []
    for ins in hits:
        try:
            woord = verdict(field(ins.get("evidence") or [], atoms)).get("word", "")
        except Exception:
            woord = ""                                    # verdict is garnering, nooit blokkerend
        uit.append({"id": ins.get("id", ""), "tekst": _regel(ins.get("title", "")),
                    "verdict": woord})
    return uit


def _signalen(data_dir: str, tekst: str, limit: int) -> list[dict]:
    from nooch_village.radar_store import RadarStore
    pad = os.path.join(data_dir, "radar.json")
    if not os.path.exists(pad):
        return []
    kandidaten = [it for it in RadarStore(pad).all_approved()
                  if not it.get("promoted_atom_id")]      # al gepromoveerd → zit al in de atomen
    docs = [(it, f"{it.get('content', '')} {it.get('rationale', '')}") for it in kandidaten]
    hits = _match(_woorden(tekst), docs, limit)
    return [{"id": it.get("id", ""), "tekst": _regel(it.get("content", "")),
             "bron": _regel(it.get("source") or it.get("feed") or "", 80)} for it in hits]


def kennis_voor(bron, tekst: str, limit: int = 5) -> dict:
    """Raadpleeg de kennislaag voor een project-scope/hypothese. `bron` = een data_dir-pad
    (str) óf een Context-achtig object met `.data_dir`. Geeft
    {kaartjes, inzichten, signalen, samenvatting} met per item id + één regel tekst +
    bron/verdict. Fail-soft: ontbrekende/kapotte stores of lege tekst → lege uitkomst."""
    data_dir = bron if isinstance(bron, str) else getattr(bron, "data_dir", None)
    uit = {s: [] for s in _SOORTEN}
    if data_dir and (tekst or "").strip():
        for soort, fn in (("kaartjes", _kaartjes), ("inzichten", _inzichten),
                          ("signalen", _signalen)):
            try:
                uit[soort] = fn(data_dir, tekst, limit)
            except Exception as e:                        # nooit projectwerk blokkeren
                log.warning("kennis-raadpleging (%s) faalde fail-soft: %s", soort, e)
                uit[soort] = []
    uit["samenvatting"] = (f"{len(uit['kaartjes'])} kaartjes, {len(uit['inzichten'])} "
                           f"inzichten, {len(uit['signalen'])} signalen")
    return uit


def totaal(kennis: dict | None) -> int:
    """Aantal gevonden items over de drie soorten (fail-soft: geen dict → 0)."""
    if not isinstance(kennis, dict):
        return 0
    return sum(len(kennis.get(s) or []) for s in _SOORTEN)


def kennis_blok(kennis: dict | None, max_chars: int = MAX_BLOK_CHARS) -> str:
    """Render de gevonden kennis als prompt-sectie met de vaste kop
    'REEDS BEKEND (kennisbank — vul aan, herhaal niet):'. Niets gevonden → "" (dan géén
    prompt-injectie). Harde cap op `max_chars` zodat prompts niet exploderen: regels die
    niet meer passen vallen af; past zelfs de eerste regel niet, dan wordt hard afgekapt."""
    if not isinstance(kennis, dict) or totaal(kennis) == 0:
        return ""
    regels: list[str] = []
    for k in kennis.get("kaartjes") or []:
        staart = f" (bron: {k['bron']})" if k.get("bron") else ""
        regels.append(f"- [kaartje {k.get('id', '')}] {k.get('tekst', '')}{staart}")
    for i in kennis.get("inzichten") or []:
        staart = f" (bewijs: {i['verdict']})" if i.get("verdict") else ""
        regels.append(f"- [inzicht {i.get('id', '')}] {i.get('tekst', '')}{staart}")
    for s in kennis.get("signalen") or []:
        staart = f" (bron: {s['bron']})" if s.get("bron") else ""
        regels.append(f"- [signaal {s.get('id', '')}] {s.get('tekst', '')}{staart}")
    blok = "REEDS BEKEND (kennisbank — vul aan, herhaal niet):"
    opgenomen = 0
    for r in regels:
        kandidaat = blok + "\n" + r
        if len(kandidaat) > max_chars:
            if opgenomen == 0:
                return kandidaat[:max_chars]              # altijd íets tonen, nooit kop-zonder-inhoud
            break
        blok = kandidaat
        opgenomen += 1
    return blok


def meld_raadpleging(bus, *, project_id: str, rol: str, kennis: dict | None,
                     sender: str = "") -> None:
    """Maak de raadpleging zichtbaar: één logregel + (als er een bus is) het event
    `kennis_geraadpleegd` met {project_id, rol, gevonden: {kaartjes, inzichten, signalen},
    ids}. Ook 0/0/0 is een event — 'niets gevonden' is óók activiteit. Fail-soft: een
    kapotte bus mag het projectwerk nooit breken."""
    kennis = kennis if isinstance(kennis, dict) else {}
    gevonden = {s: len(kennis.get(s) or []) for s in _SOORTEN}
    ids = [item.get("id", "") for s in _SOORTEN for item in (kennis.get(s) or [])]
    log.info("📚 %s raadpleegde de kennisbank voor project %s: %s", rol or "?", project_id,
             kennis.get("samenvatting") or "0 kaartjes, 0 inzichten, 0 signalen")
    if bus is None:
        return
    try:
        from nooch_village.event_bus import Event
        bus.publish(Event("kennis_geraadpleegd",
                          {"project_id": project_id, "rol": rol, "gevonden": gevonden,
                           "ids": ids}, sender or rol or "kennis_context"))
    except Exception as e:
        log.warning("kennis_geraadpleegd-event kon niet worden gepubliceerd: %s", e)
