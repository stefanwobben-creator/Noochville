"""Hefboom 2 — van signaal naar projectVOORSTEL, met de mens als poort.

Twee bronnen worden omgezet in voorgestelde projecten. Een voorstel komt NOOIT vanzelf op het
actieve bord: het krijgt status `proposed`, en die status staat bewust buiten élke autonome lus
(`board_loop.activate_pulse` kijkt alleen naar future/blocked, `Inhabitant._tend_projects` naar
future/queued/running, `project_worker._eligible` naar queued/running). De mens accepteert of wijst
af in de review-baan van de cockpit.

Bron 1 — **radar** (default aan): signalen met status `goedgekeurd` die nog geen voorstel opleverden.
Het approve is de relevantie-poort die al gepasseerd is; dit is de lichtere tweede vraag: *verdient
dit een project?*

Bron 2 — **Kroniek-gaten** (default UIT, `project_proposals_kroniek = 1` zet 'm aan): de `leeg`-lijst
uit `evidence_ledger.interpret()` per lopend onderwerp — onderzocht, niets gevonden — als kandidaat-
onderzoeksproject. Bewust opt-in: ruis is duur, en anders dan een radar-item is een kennisgat nog
door niemand op relevantie beoordeeld.

Drie ruis-remmers, in deze volgorde:
1. **Dedup** — elke bron-referentie die ooit een voorstel opleverde wordt onthouden in de overlay
   `data/project_proposals.json`, ongeacht de afloop (voorgesteld/geaccepteerd/afgewezen). Zelfde
   garantie als de bibliotheek-dedup: één keer beoordeeld = nooit opnieuw voorgesteld.
2. **Cap** — maximaal N openstaande voorstellen in de baan (`project_proposals_cap`, default 10).
   Zit de baan vol, dan slaan we over en LOGGEN we wát we oversloegen — nooit stil afkappen.
3. **Formulering** — `wizard.sharpen_outcome` maakt er één Holacracy-uitkomst in de verleden tijd
   van, in het Engels (nieuwe content is Engels). Fail-soft: valt de LLM weg, dan de ruwe tekst.
"""
from __future__ import annotations

import logging
import os
import time

from nooch_village.util import JsonStore

_LOG = logging.getLogger("village.proposals")

_DEFAULT_CAP = 10
_STATUSES = ("proposed", "accepted", "rejected")


def radar_key(item_id: str) -> str:
    return f"radar:{item_id}"


def kroniek_key(topic: str) -> str:
    return f"kroniek:{(topic or '').strip().lower()}"


class ProposalOverlay(JsonStore):
    """De dedup-herinnering: welke bron-referentie leverde al een voorstel op, en hoe liep het af.

    Los van het projectgrootboek, want de herinnering moet een afgewezen (en dus verwijderd)
    project OVERLEVEN — anders stelt de volgende puls precies hetzelfde opnieuw voor. Zelfde
    patroon als de claims-runtime-overlay: een append-achtig zijbestand naast de hoofd-store."""

    _WRITE_METHODS = ("remember", "set_status")
    _STATE = "_items"
    _default = dict
    _EXPECT = dict

    def seen(self, key: str) -> bool:
        """Is deze bron ooit voorgesteld? Waar (ongeacht status: ook afgewezen telt) → nooit opnieuw."""
        return bool(key) and key in self._items

    def get(self, key: str) -> dict | None:
        return self._items.get(key)

    def remember(self, key: str, *, source: str, ref: str, pid: str,
                 title: str = "", owner: str = "") -> dict:
        row = {"key": key, "source": source, "ref": ref, "pid": pid, "title": title[:200],
               "owner": owner, "status": "proposed", "at": time.time()}
        self._items[key] = row
        self._save()
        return row

    def set_status(self, key: str, status: str) -> bool:
        if status not in _STATUSES or key not in self._items:
            return False
        self._items[key]["status"] = status
        self._items[key]["decided_at"] = time.time()
        self._save()
        return True

    def by_pid(self, pid: str) -> dict | None:
        return next((r for r in self._items.values() if r.get("pid") == pid), None)

    def all(self) -> list[dict]:
        return list(self._items.values())


def overlay_for(data_dir: str) -> ProposalOverlay:
    return ProposalOverlay(os.path.join(data_dir, "project_proposals.json"))


def _cap(context) -> int:
    try:
        return max(0, int(context.settings.get("project_proposals_cap", _DEFAULT_CAP)))
    except (TypeError, ValueError):
        return _DEFAULT_CAP


def _kroniek_on(context) -> bool:
    return str(context.settings.get("project_proposals_kroniek", "0")).strip() in ("1", "true", "yes")


def running_topics(ledger) -> list[str]:
    """De lopende onderwerpen: de `keyword` van openstaande projecten. Bewust smal — een onderwerp
    zonder eigen naam levert geen leesbare projecttitel op, en `interpret()` matcht op substring in
    de query, dus een lange vrije zin zou toch niets vinden. Liever weinig en juist dan veel en vaag."""
    seen, out = set(), []
    for p in ledger.all():
        kw = (p.get("keyword") or "").strip()
        if not kw or p.get("archived") or p.get("status") in ("done", "proposed"):
            continue
        if kw.lower() not in seen:
            seen.add(kw.lower())
            out.append(kw)
    return out


def _radar_candidates(radar, records=None) -> list[dict]:
    """Goedgekeurde radar-signalen → kandidaten. Eigenaar = de rol van het signaal."""
    out = []
    for it in radar.all_approved():
        owner = (it.get("role") or "").strip()
        if not owner or (records is not None and records.get(owner) is None):
            continue                      # zonder bestaande eigenaar-rol geen voorstel (fail-closed)
        ruw = (it.get("content") or "").strip()
        if not ruw:
            continue
        out.append({"key": radar_key(it["id"]), "source": "radar", "ref": it["id"],
                    "owner": owner, "raw": ruw,
                    "why": (it.get("rationale") or "").strip(),
                    "link": (it.get("link") or "").strip()})
    return out


def _kroniek_candidates(ledger, evidence, records=None) -> list[dict]:
    """Kennisgaten per lopend onderwerp → kandidaat-onderzoeksprojecten. De eigenaar is de rol die
    het gat ZELF opliep (de rol op het lopende project met dat onderwerp), niet een vaste rol."""
    from nooch_village.evidence_ledger import interpret
    eigenaar_van = {}
    for p in ledger.all():
        kw = (p.get("keyword") or "").strip().lower()
        if kw and kw not in eigenaar_van and p.get("owner"):
            eigenaar_van[kw] = p["owner"]
    out = []
    for topic in running_topics(ledger):
        res = interpret(evidence, topic)
        gaten = res.get("leeg") or []
        if not gaten:
            continue
        owner = eigenaar_van.get(topic.lower(), "")
        if not owner or (records is not None and records.get(owner) is None):
            continue
        bronnen = ", ".join(sorted({g.get("skill", "") for g in gaten if g.get("skill")}))
        out.append({"key": kroniek_key(topic), "source": "kroniek", "ref": topic, "owner": owner,
                    "raw": f"answer the open question about '{topic}' that {len(gaten)} earlier "
                           f"searches left unanswered",
                    "why": f"{len(gaten)} knowledge gap(s) in the Chronicle for '{topic}'"
                           + (f" (searched via: {bronnen})" if bronnen else ""),
                    "link": ""})
    return out


def _provenance(cand: dict) -> str:
    """De herkomstregel op de kaart: waar dit voorstel vandaan komt, zodat de mens het kan wegen."""
    bron = {"radar": "approved radar signal", "kroniek": "gap in the Chronicle"}.get(
        cand["source"], cand["source"])
    regel = f"💡 proposed by the village — source: {bron} · {cand['raw'][:200]}"
    if cand.get("why"):
        regel += f"\n\nWhy: {cand['why'][:400]}"
    if cand.get("link"):
        regel += f"\n\n{cand['link'][:300]}"
    return regel


def generate_proposals(context, *, records=None, radar=None, evidence=None, bus=None,
                       sharpen=None, cap: int | None = None, kroniek: bool | None = None) -> dict:
    """Draai één voorstel-ronde. Geeft {created, skipped_cap, skipped_dedup, cap, open_before}.

    Idempotent door de dedup-overlay: dezelfde bron levert nooit een tweede voorstel op, ook niet
    nadat de mens het eerste afwees. Deterministisch behalve de formulering (LLM, fail-soft)."""
    ledger = getattr(context, "projects", None)
    if ledger is None:
        return {"created": [], "skipped_cap": [], "skipped_dedup": 0, "cap": 0, "open_before": 0}
    data_dir = context.data_dir
    if records is None:
        records = getattr(context, "records", None)
    if radar is None:
        from nooch_village.radar_store import RadarStore
        radar = RadarStore(os.path.join(data_dir, "radar.json"))
    if cap is None:
        cap = _cap(context)
    if kroniek is None:
        kroniek = _kroniek_on(context)
    if sharpen is None:
        from nooch_village.wizard import sharpen_outcome
        sharpen = sharpen_outcome
    overlay = overlay_for(data_dir)

    cands = _radar_candidates(radar, records)
    if kroniek:
        if evidence is None:
            from nooch_village.evidence_ledger import EvidenceLedger
            evidence = EvidenceLedger(os.path.join(data_dir, "evidence_ledger.jsonl"))
        cands += _kroniek_candidates(ledger, evidence, records)

    open_before = len(ledger.proposals())
    room = max(0, cap - open_before)
    created, skipped_cap, skipped_dedup = [], [], 0
    from nooch_village.wizard import board_anchors
    anchors = board_anchors(ledger.all())

    for cand in cands:
        if overlay.seen(cand["key"]):
            skipped_dedup += 1
            continue
        if len(created) >= room:
            skipped_cap.append({"key": cand["key"], "owner": cand["owner"],
                                "raw": cand["raw"][:120]})
            continue
        try:
            uitkomst = sharpen(cand["raw"], anchors=anchors) or cand["raw"]
        except Exception:                     # fail-soft: liever de ruwe tekst dan geen voorstel
            uitkomst = cand["raw"]
        pid = ledger.create(cand["owner"], uitkomst[:200], "role", status="proposed",
                            origin=f"proposal:{cand['source']}", parent=None,
                            links=[cand["link"]] if cand.get("link") else None)
        ledger.add_feed_entry(pid, _provenance(cand), kind="system",
                              author_type="role", author_id=cand["owner"])
        overlay.remember(cand["key"], source=cand["source"], ref=cand["ref"], pid=pid,
                         title=uitkomst, owner=cand["owner"])
        created.append({"pid": pid, "key": cand["key"], "owner": cand["owner"], "title": uitkomst})

    for s in skipped_cap:                      # geen stille truncatie: wát is overgeslagen, en waarom
        _LOG.info("⏭ voorstel overgeslagen (baan vol, cap=%d): [%s] %s", cap, s["owner"], s["raw"])
    _LOG.info("💡 voorstel-ronde: %d nieuw, %d overgeslagen (cap), %d al eerder beoordeeld "
              "(%d openstaand vóór deze ronde, cap %d)",
              len(created), len(skipped_cap), skipped_dedup, open_before, cap)
    res = {"created": created, "skipped_cap": skipped_cap, "skipped_dedup": skipped_dedup,
           "cap": cap, "open_before": open_before}
    if bus is not None:
        from nooch_village.event_bus import Event
        bus.publish(Event("project_proposals_generated",
                          {"created": len(created), "skipped_cap": len(skipped_cap),
                           "skipped_dedup": skipped_dedup, "cap": cap}, "proposals"))
    return res


def accept(ledger, data_dir: str, pid: str, *, person: str = "") -> bool:
    """Mens-poort: neem een voorstel aan. Het wordt een gewoon root-project in TOEKOMST."""
    if not ledger.accept_proposal(pid, person=person):
        return False
    ov = overlay_for(data_dir)
    row = ov.by_pid(pid)
    if row:
        ov.set_status(row["key"], "accepted")
    return True


def reject(ledger, data_dir: str, pid: str) -> bool:
    """Mens-poort: wijs een voorstel af. Het project verdwijnt; de herinnering blijft, zodat
    dezelfde bron het niet volgende puls opnieuw voorstelt."""
    ov = overlay_for(data_dir)
    row = ov.by_pid(pid)                       # eerst opzoeken: na reject_proposal is het pid weg
    if not ledger.reject_proposal(pid):
        return False
    if row:
        ov.set_status(row["key"], "rejected")
    return True
