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
    vrij = ongebonden(atoms, inzichten)
    per_hub: dict[str, list[str]] = {}
    for aid, a in vrij.items():
        hub = subject_van(a)
        if hub:
            per_hub.setdefault(hub, []).append(aid)
    uit: list[dict] = []
    for hub, ids in sorted(per_hub.items(), key=lambda kv: -len(kv[1])):
        if len(ids) < min_size:
            continue
        woorden = Counter(w for aid in ids for w in _tokens(vrij[aid].get("claim", ""))
                          if w != hub)
        kern = [w for w, _ in woorden.most_common(3)]
        uit.append({"hub": hub, "theme": f"{hub}: {' · '.join(kern)}" if kern else hub,
                    "atom_ids": sorted(ids)})
        if len(uit) >= max_clusters:
            break
    return uit


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


# ── De dialoog ───────────────────────────────────────────────────────────────

BLOK_MARKER = "=== INZICHT ==="


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class SpelStore(JsonStore):
    """Eén spel = {id, hunch, set:[{atom_id,stance}], messages:[{role:'ik'|'ai',text,at}],
    status:'open'|'klaar'|'gemunt', reformulate_of, insight_id, created_at, updated_at}.
    Berichten zijn append-only; afronden zet alleen status/insight_id."""

    _WRITE_METHODS = ("start", "append_message", "mark")

    def get(self, sid: str) -> dict | None:
        return self._items.get(sid)

    def open_spellen(self) -> list[dict]:
        return sorted((s for s in self._items.values() if s.get("status") != "gemunt"),
                      key=lambda s: s.get("updated_at") or "", reverse=True)

    def start(self, hunch: str, kaarten: list[dict], *, reformulate_of: str = "",
              by: str = "") -> str:
        sid = "spel_" + uuid.uuid4().hex[:8]
        self._items[sid] = {
            "id": sid, "hunch": (hunch or "").strip(),
            "set": [{"atom_id": k["atom_id"], "stance": k.get("stance") or "support"}
                    for k in kaarten if k.get("atom_id")],
            "messages": [], "status": "open",
            "reformulate_of": reformulate_of or None, "insight_id": None,
            "by": by, "created_at": _now(), "updated_at": _now(),
        }
        self._save()
        return sid

    def append_message(self, sid: str, role: str, text: str) -> bool:
        s = self._items.get(sid)
        if s is None or role not in ("ik", "ai") or not (text or "").strip():
            return False
        s["messages"].append({"role": role, "text": text.strip(), "at": _now()})
        if role == "ai" and BLOK_MARKER in text:
            s["status"] = "klaar"              # de AI heeft het blok gegeven → muntbaar
        s["updated_at"] = _now()
        self._save()
        return True

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
    """Game-prompt §7 (fase-1 bouwsteen) + het transcript. De ladder is single-shot,
    dus het hele gesprek gaat mee; de AI geeft alleen zijn volgende beurt terug."""
    rows = [{"claim": (atoms.get(k["atom_id"]) or {}).get("claim", ""),
             "stance": k["stance"]} for k in spel.get("set") or []]
    basis = bouw_spel_prompt(spel.get("hunch", ""), rows)
    transcript = "\n".join(
        f"{'IK' if m['role'] == 'ik' else 'JIJ (denkpartner)'}: {m['text']}"
        for m in spel.get("messages") or [])
    if transcript:
        return (f"{basis}\n\nGESPREK TOT NU TOE:\n{transcript}\n\n"
                "Geef ALLEEN je volgende beurt als denkpartner (of het === INZICHT ===-blok "
                "zodra claim, reframe en een waarneembare falsifier er zijn). Geen meta-tekst.")
    return (f"{basis}\n\nBegin het gesprek: geef ALLEEN je eerste beurt (stap 1). "
            "Geen meta-tekst.")


def spel_beurt(store: SpelStore, sid: str, user_text: str, atoms: dict[str, dict],
               reason_fn=reason) -> str | None:
    """Eén beurt: (optioneel) mijn bericht erbij, dan de ladder laten antwoorden.
    Fail-closed: geen antwoord → None en het spel blijft gewoon open (niets verloren)."""
    spel = store.get(sid)
    if spel is None or spel.get("status") == "gemunt":
        return None
    if (user_text or "").strip():
        store.append_message(sid, "ik", user_text)
        spel = store.get(sid)
    out = reason_fn(spel_prompt(spel, atoms), max_tokens=700, call_site="kb_spel")
    if not out:
        return None
    store.append_message(sid, "ai", out)
    return out


def spel_finish(store: SpelStore, sid: str, kb) -> tuple[str, str] | None:
    """Munt het inzicht uit het === INZICHT ===-blok van de dialoog (trage klok).
    Nieuw spel → inzicht v1.0 verankerd aan de set; herformuleer-spel → versie-bump
    op het bestaande inzicht (fase-1 reformulate, history bewaart de vorige versie).
    Geeft (insight_id, versie) of None (geen blok/geen spel)."""
    spel = store.get(sid)
    if spel is None or spel.get("status") == "gemunt":
        return None
    ai_teksten = [m["text"] for m in spel.get("messages") or []
                  if m["role"] == "ai" and BLOK_MARKER in m["text"]]
    if not ai_teksten:
        return None
    parsed = parse_blok(ai_teksten[-1])
    if not parsed["claim"]:
        return None
    if spel.get("reformulate_of"):
        iid = spel["reformulate_of"]
        versie = kb.reformulate(iid, title=parsed["claim"], reframe=parsed["reframe"],
                                falsifier=parsed["falsifier"], by=spel.get("by") or "spel")
        if versie is None:
            return None
    else:
        iid = kb.add(parsed["claim"], why=f"Gespeeld uit {len(spel.get('set') or [])} kaarten.",
                     reframe=parsed["reframe"], falsifier=parsed["falsifier"],
                     by=spel.get("by") or "spel")
        for k in spel.get("set") or []:
            kb.link(iid, k["atom_id"], k["stance"], by=spel.get("by") or "spel")
        versie = "1.0"
    store.mark(sid, status="gemunt", insight_id=iid)
    return iid, versie
