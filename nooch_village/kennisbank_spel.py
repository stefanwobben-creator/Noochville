"""Kennisbank fase 3 — het spel: van atomen naar een geversioneerd inzicht, server-side.

Twee opritten naar een set (master-brief §7/§8):
  - bottom-up: `clusters()` groepeert ONGEBONDEN atomen (onderwerp-hub + woord-overlap)
    tot "kaarten die een inzicht willen worden", inclusief wat er binnen die hub tegenspreekt;
  - top-down: `gather()` haalt bij een hunch de relevante atomen op, mét een verplichte
    "spreekt dit tegen?"-sectie (stance-suggestie via één LLM-call; fail-closed → de mens
    draait de richting zelf, zoals overal in de kennisbank).

De dialoog zelf (`spel_beurt`) loopt via de bestaande LLM-ladder met de game-prompt uit
fase 1 (kennisbank.bouw_spel_prompt) + het transcript. Eindigt de AI met het
=== INZICHT ===-blok, dan munt `spel_finish` een inzicht v1.0 (of een versie-bump bij
herformuleren) via de bestaande fase-1 functies — het veld-algoritme blijft onaangeroerd.

Toestand: SpelStore (JsonStore) → data/kennisbank_spel.json. Append-only berichten;
een spel wordt nooit herschreven, alleen aangevuld en afgesloten.
"""
from __future__ import annotations

import json
import re
import uuid
from collections import Counter
from datetime import datetime

from nooch_village.kennisbank import bouw_spel_prompt, parse_blok
from nooch_village.kennisbank_intake import SUBJECTS
from nooch_village.llm import reason
from nooch_village.util import JsonStore


def subject_van(atom: dict) -> str:
    """Het onderwerp van een atoom = de eerste tag uit het vaste vocabulaire.
    Volgorde-onafhankelijk (flags/hints mogen vóór het onderwerp staan); geen
    vocabulaire-tag → '' (het ongesorteerd-bakje)."""
    for t in atom.get("tags") or []:
        if t in SUBJECTS:
            return t
    return ""


def _tokens(text: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9à-ÿ]+", (text or "").lower()) if len(w) > 3}


def ongebonden(atoms: dict[str, dict], inzichten: list[dict]) -> dict[str, dict]:
    """Atomen die nog in géén inzicht-evidence zitten (de kandidaten voor emergentie)."""
    gelinkt = {l.get("atom_id") for i in inzichten for l in (i.get("evidence") or [])}
    return {aid: a for aid, a in atoms.items()
            if aid not in gelinkt and (a.get("claim") or "").strip()}


def clusters(atoms: dict[str, dict], inzichten: list[dict],
             min_size: int = 2, max_clusters: int = 4) -> list[dict]:
    """Bottom-up emergentie, deterministisch (bewust GEEN LLM-call: dit draait op elke
    GET van /kennisbank en hoort de rate-limiter niet te belasten). Groepeer ongebonden
    atomen per onderwerp-hub; het thema = de hub + de meest onderscheidende woorden.
    Binnen een hub zit tegenspraak vanzelf in de set — de mens zet de richtingen."""
    from nooch_village.mission import strategie_relevantie
    vrij = ongebonden(atoms, inzichten)
    per_hub: dict[str, list[str]] = {}
    for aid, a in vrij.items():
        hub = subject_van(a)
        if hub:
            per_hub.setdefault(hub, []).append(aid)
    kandidaten: list[dict] = []
    for hub, ids in per_hub.items():
        if len(ids) < min_size:
            continue
        woorden = Counter(w for aid in ids for w in _tokens(vrij[aid].get("claim", ""))
                          if w != hub)
        kern = [w for w, _ in woorden.most_common(3)]
        # Strategische relevantie van het hele cluster (hub + alle claims), deterministisch. Zo komen
        # missie-kernclusters (plasticvrij, leervrij, composteerbaar, transparantie…) vooraan i.p.v.
        # simpelweg het grootste stapeltje kaartjes (founder 24 jul).
        blob = hub + " " + " ".join(vrij[aid].get("claim", "") for aid in ids)
        s_score, s_themas = strategie_relevantie(blob)
        kandidaten.append({"hub": hub,
                           "theme": f"{hub}: {' · '.join(kern)}" if kern else hub,
                           "atom_ids": sorted(ids),
                           "strategie_score": s_score, "strategie_themas": s_themas})
    # Zacht herrangschikken: eerst strategische relevantie, dan clustergrootte, dan hub (stabiel).
    # Niets verdwijnt behalve door de bestaande max_clusters-cap; de suggestiekaart blijft blader-baar.
    kandidaten.sort(key=lambda c: (-c["strategie_score"], -len(c["atom_ids"]), c["hub"]))
    return kandidaten[:max_clusters]


def gather(hunch: str, atoms: dict[str, dict], limit: int = 10,
           reason_fn=reason) -> list[dict]:
    """Top-down: recall (woord-overlap, zeldzaamheid gewogen) + stance-suggestie per
    kandidaat via één JSON-LLM-call — zodat er altijd een expliciete "spreekt dit
    tegen?"-sectie is (anti-cherry-pick). Fail-closed: geen LLM → alles 'support'
    en de mens draait zelf. Geen mutaties; puur een voorstel."""
    # Lichte stemming voor recall: woorden matchen op hun eerste 5 tekens, zodat
    # "wachttijd" ook "wachten" vindt. Alleen hier (ranking); cluster-thema's blijven
    # hele woorden.
    def _stems(text: str) -> set[str]:
        return {w[:5] for w in _tokens(text)}

    toks = _stems(hunch)
    if not toks:
        return []
    doc_freq: Counter = Counter()
    for a in atoms.values():
        doc_freq.update(_stems(a.get("claim", "")))
    scored: list[tuple[float, str]] = []
    for aid, a in atoms.items():
        gedeeld = toks & _stems(a.get("claim", ""))
        score = sum(1.0 / doc_freq[w] for w in gedeeld if doc_freq[w])
        if score > 0:
            scored.append((score, aid))
    scored.sort(key=lambda t: (-t[0], t[1]))
    top = [aid for _, aid in scored[:limit]]
    if not top:
        return []

    stances = {aid: "support" for aid in top}
    regels = "\n".join(f"{i + 1}. {atoms[aid].get('claim', '')}" for i, aid in enumerate(top))
    out = reason_fn(
        "Je sorteert kaarten voor een kennisspel. Oordeel NIET over waarheid; bepaal alleen "
        "per kaart of hij het vermoeden STEUNT of TEGENSPREEKT.\n\n"
        f"VERMOEDEN: {hunch}\n\nKAARTEN:\n{regels}\n\n"
        "OUTPUT: alleen een JSON-array, per kaart één object, zelfde volgorde:\n"
        '[{"nr": 1, "stance": "support"|"counter"}]',
        max_tokens=400, json_mode=True, call_site="kb_gather_stance")
    if out:
        try:
            cleaned = re.sub(r"```(?:json)?", "", out).strip()
            arr = json.loads(cleaned[cleaned.find("["):cleaned.rfind("]") + 1])
            for row in arr:
                nr = int(row.get("nr", 0)) - 1
                if 0 <= nr < len(top) and row.get("stance") in ("support", "counter"):
                    stances[top[nr]] = row["stance"]
        except (json.JSONDecodeError, ValueError, TypeError, AttributeError):
            pass                               # fail-closed: suggesties blijven 'support'
    return [{"atom_id": aid, "stance": stances[aid]} for aid in top]


def spel_suggesties(atoms: dict[str, dict], inzichten: list[dict],
                    max_suggesties: int = 6) -> list[dict]:
    """Kandidaten voor de suggestiekaart bovenaan /kennisbank (founder, 19 jul): per
    cluster één vóórgevuld inzicht, expliciet 'not verified'. Deterministisch — bewust
    GEEN LLM-call, dit draait op elke GET: de startformulering is de claim van de meest
    REPRESENTATIEVE kaart in het cluster (grootste woord-overlap met de rest; tie-break
    op atom_id). Het scherp formuleren gebeurt tóch in het spel — dit is een startpunt."""
    uit: list[dict] = []
    for cl in clusters(atoms, inzichten, max_clusters=max_suggesties):
        toks = {aid: _tokens((atoms.get(aid) or {}).get("claim", ""))
                for aid in cl["atom_ids"]}
        # hoogste overlap met de rest wint; bij gelijkspel de laagste atom_id (stabiel)
        beste = min(cl["atom_ids"], key=lambda aid: (
            -sum(len(toks[aid] & toks[bid]) for bid in cl["atom_ids"] if bid != aid), aid))
        hunch = ((atoms.get(beste) or {}).get("claim") or cl["theme"]).strip()
        uit.append({"hunch": hunch, "atom_ids": cl["atom_ids"],
                    "theme": cl["theme"], "hub": cl["hub"],
                    "strategie_themas": cl.get("strategie_themas", [])})
    return uit


# ── Het spel (copy-paste: speel in je eigen AI) ─────────────────────────────

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class SpelStore(JsonStore):
    """Eén spel = {id, hunch, set:[{atom_id,stance,annotation?}], status:'open'|'gemunt',
    reformulate_of, insight_id, by, created_at, updated_at}. De set is de "hand" die de
    mens cureert; het spel zelf speelt hij in zijn eigen AI (besluit Stefan dd 2026-07-17 —
    de server-side dialoog is bewust verwijderd, scheelt ook ladder-tokens). Munten is
    eenmalig; een gemunt spel wordt nooit herschreven."""

    _WRITE_METHODS = ("start", "add_kaart", "remove_kaart", "flip_kaart", "mark")

    def get(self, sid: str) -> dict | None:
        return self._items.get(sid)

    def open_spellen(self) -> list[dict]:
        return sorted((s for s in self._items.values() if s.get("status") != "gemunt"),
                      key=lambda s: s.get("updated_at") or "", reverse=True)

    def start(self, hunch: str, kaarten: list[dict], *, reformulate_of: str = "",
              by: str = "", meta: bool = False) -> str:
        """Start een spel met een gecureerde hand. `meta=True` (B1): de kaarten zijn ANDERE
        inzichten i.p.v. atomen — elk draagt een `label` (de claim-tekst) zodat de prompt geen
        atoom-lookup nodig heeft, en spel_finish mint dan een meta-inzicht (related i.p.v. evidence)."""
        sid = "spel_" + uuid.uuid4().hex[:8]
        self._items[sid] = {
            "id": sid, "hunch": (hunch or "").strip(),
            "set": [{"atom_id": k["atom_id"], "stance": k.get("stance") or "support",
                     "annotation": (k.get("annotation") or "").strip() or None,
                     "label": (k.get("label") or "").strip() or None}
                    for k in kaarten if k.get("atom_id")],
            "status": "open", "meta": bool(meta),
            "reformulate_of": reformulate_of or None, "insight_id": None,
            "by": by, "created_at": _now(), "updated_at": _now(),
        }
        self._save()
        return sid

    def add_kaart(self, sid: str, atom_id: str, stance: str = "support",
                  annotation: str = "") -> bool:
        """Breid de hand uit (taak 2). Idempotent: bestaat de kaart al in de set, dan
        worden richting/annotatie bijgewerkt — nooit een dubbele stem."""
        s = self._items.get(sid)
        if s is None or s.get("status") == "gemunt" or not atom_id \
                or stance not in ("support", "counter"):
            return False
        for k in s["set"]:
            if k["atom_id"] == atom_id:
                k["stance"] = stance
                if annotation:
                    k["annotation"] = annotation.strip()
                break
        else:
            s["set"].append({"atom_id": atom_id, "stance": stance,
                             "annotation": (annotation or "").strip() or None})
        s["updated_at"] = _now()
        self._save()
        return True

    def remove_kaart(self, sid: str, atom_id: str) -> bool:
        s = self._items.get(sid)
        if s is None or s.get("status") == "gemunt":
            return False
        voor = len(s["set"])
        s["set"] = [k for k in s["set"] if k["atom_id"] != atom_id]
        if len(s["set"]) == voor:
            return False
        s["updated_at"] = _now()
        self._save()
        return True

    def flip_kaart(self, sid: str, atom_id: str) -> bool:
        """Richting draaien in één klik (steunt ↔ spreekt tegen)."""
        s = self._items.get(sid)
        if s is None or s.get("status") == "gemunt":
            return False
        for k in s["set"]:
            if k["atom_id"] == atom_id:
                k["stance"] = "counter" if k["stance"] == "support" else "support"
                s["updated_at"] = _now()
                self._save()
                return True
        return False

    def mark(self, sid: str, *, status: str, insight_id: str | None = None) -> bool:
        s = self._items.get(sid)
        if s is None:
            return False
        s["status"] = status
        if insight_id:
            s["insight_id"] = insight_id
        s["updated_at"] = _now()
        self._save()
        return True


def spel_prompt(spel: dict, atoms: dict[str, dict]) -> str:
    """De prompt die de mens meeneemt naar zijn eigen AI: de game-prompt uit de
    master-brief (§7, fase-1 bouwsteen), geseed met de gecureerde hand."""
    rows = [{"claim": k.get("label") or (atoms.get(k["atom_id"]) or {}).get("claim", ""),
             "stance": k["stance"]} for k in spel.get("set") or []]
    return bouw_spel_prompt(spel.get("hunch", ""), rows)


def steun_onafhankelijk(spel: dict, atoms: dict[str, dict]) -> int:
    """Aantal ONAFHANKELIJKE steunbronnen in de hand (dezelfde woozle-groepering als
    het veld). Voedt de zachte rem: onder de 3 een nudge, nooit een blokkade."""
    from nooch_village.kennisbank import field
    return field(spel.get("set") or [], atoms)["indep"]


def spel_finish(store: SpelStore, sid: str, kb, blok: str) -> tuple[str, str] | None:
    """Munt het inzicht uit het teruggeplakte === INZICHT ===-blok (trage klok).
    Nieuw spel → inzicht v1.0 verankerd aan de set; herformuleer-spel → versie-bump
    op het bestaande inzicht (fase-1 reformulate, history bewaart de vorige versie).
    Geeft (insight_id, versie) of None (geen bruikbaar blok / al gemunt)."""
    spel = store.get(sid)
    if spel is None or spel.get("status") == "gemunt":
        return None
    parsed = parse_blok(blok or "")
    if not parsed["claim"]:
        return None
    if spel.get("reformulate_of"):
        iid = spel["reformulate_of"]
        versie = kb.reformulate(iid, title=parsed["claim"], reframe=parsed["reframe"],
                                falsifier=parsed["falsifier"], by=spel.get("by") or "spel")
        if versie is None:
            return None
    elif spel.get("meta"):
        # META-inzicht (B1): de kaarten zijn ANDERE inzichten → verankeren via related, niet evidence.
        iid = kb.add(parsed["claim"], why=f"Meta-inzicht uit {len(spel.get('set') or [])} inzichten.",
                     reframe=parsed["reframe"], falsifier=parsed["falsifier"],
                     by=spel.get("by") or "spel")
        for k in spel.get("set") or []:
            kb.link_insight(iid, k["atom_id"], k["stance"], by=spel.get("by") or "spel")
        versie = "1.0"
    else:
        iid = kb.add(parsed["claim"], why=f"Gespeeld uit {len(spel.get('set') or [])} kaarten.",
                     reframe=parsed["reframe"], falsifier=parsed["falsifier"],
                     by=spel.get("by") or "spel")
        for k in spel.get("set") or []:
            kb.link(iid, k["atom_id"], k["stance"],
                    annotation=k.get("annotation") or "", by=spel.get("by") or "spel")
        versie = "1.0"
    store.mark(sid, status="gemunt", insight_id=iid)
    return iid, versie
