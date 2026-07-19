"""Staging-ronde voor handmatige intake (layout-brief zone 2).

Permissieve intake, strenge uitgang: een toegevoegde bron wordt eerst geatomiseerd naar een
STAGING-batch (hier), NIET meteen de bibliotheek in. De mens kijkt na — bewerken, samenvoegen,
weggooien — en pas op "Voeg set toe aan bibliotheek" landen de atomen append-only in notes.json.
Zo ruim je rommel (zoals enumeratie-broertjes) op vóór het de bibliotheek vervuilt.

Bulk/auto-ingest (backfill, re-atomiseer) heeft geen mens om na te kijken en gaat rechtstreeks
de bibliotheek in — die raakt deze staging dus niet. Uitzondering: de rapport-lus
(project_signal.report_to_staging) is wél auto-geïnitieerd maar landt bewust HIER — een
projectrapport verdient dezelfde mens-review als een handmatig toegevoegde bron.

Signaal-promotie loopt óók via deze staging (radar_promote.stage_signal): "→ kenniskaartje"
maakt niet direct een atoom maar zet het signaal hier klaar — bewerken, samenvoegen met andere
signalen, of weggooien — en pas bij commit ontstaat het kaartje (met de bestaande
duplicaat-detectie en de promoted-marker op het radar-item). Zulke atomen dragen `radar_rids`.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from nooch_village.kennisbank_intake import atoom_kaart, SUBJECTS
from nooch_village.notes_store import NotesStore
from nooch_village.util import JsonStore


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class StagingStore(JsonStore):
    """Eén batch = {id, kind, source_label, tabular, by, created_at,
    atoms:[{sid, content, body, subject, provenance, source, reference, flags}]}.
    De atoom-`sid` is batch-lokaal (staging), niet de definitieve bibliotheek-id."""

    _WRITE_METHODS = ("create", "append_atom", "edit_atom", "remove_atom", "merge_atoms",
                      "discard")

    @staticmethod
    def _norm_atom(a: dict, sid: str, source_label: str) -> dict:
        """Eén normalisatie voor create én append: dezelfde velden, dezelfde vangnetten."""
        return {"sid": sid,
                "content": (a.get("content") or "").strip(),
                "body": a.get("body"),
                "subject": a.get("subject") if a.get("subject") in SUBJECTS else "",
                "provenance": a.get("provenance") or "unknown",
                "provenance_note": (a.get("provenance_note") or "").strip() or None,
                "source": (a.get("source") or source_label or "onbekend").strip(),
                "reference": a.get("reference"),
                "source_date": a.get("source_date"),
                "radar_rids": [r for r in (a.get("radar_rids") or [])],
                "extra_bronnen": [dict(e) for e in (a.get("extra_bronnen") or [])],
                "van_bron": bool(a.get("van_bron")),
                "flags": [f for f in (a.get("flags") or [])]}

    def get(self, bid: str) -> dict | None:
        return self._items.get(bid)

    def open_batches(self) -> list[dict]:
        return sorted(self._items.values(), key=lambda b: b.get("created_at") or "",
                      reverse=True)

    def create(self, kind: str, source_label: str, atoms: list[dict], *,
               tabular: bool = False, by: str = "") -> str:
        bid = "stg_" + uuid.uuid4().hex[:8]
        self._items[bid] = {
            "id": bid, "kind": kind, "source_label": source_label, "tabular": tabular,
            "by": by, "created_at": _now(),
            "atoms": [self._norm_atom(a, f"s{i}", source_label)
                      for i, a in enumerate(atoms) if (a.get("content") or "").strip()],
        }
        self._save()
        return bid

    def append_atom(self, bid: str, atom: dict) -> bool:
        """Voeg één voorstel toe aan een BESTAANDE open batch (signaal-promotie: meerdere
        signalen in dezelfde Even-nakijken-set, zodat ze daar samen te mergen zijn).
        De sid is uniek t.o.v. de batch (uuid-staart, geen indexbotsing met s0..sn)."""
        b = self._items.get(bid)
        if b is None or not (atom.get("content") or "").strip():
            return False
        b["atoms"].append(self._norm_atom(atom, "s" + uuid.uuid4().hex[:6],
                                          b.get("source_label") or ""))
        self._save()
        return True

    def edit_atom(self, bid: str, sid: str, *, content: str | None = None,
                  subject: str | None = None, provenance: str | None = None) -> bool:
        b = self._items.get(bid)
        if b is None:
            return False
        for a in b["atoms"]:
            if a["sid"] == sid:
                if content is not None and content.strip():
                    a["content"] = content.strip()
                if subject is not None:
                    a["subject"] = subject if subject in SUBJECTS else ""
                if provenance is not None and provenance.strip():
                    a["provenance"] = provenance.strip()
                self._save()
                return True
        return False

    def remove_atom(self, bid: str, sid: str) -> bool:
        b = self._items.get(bid)
        if b is None:
            return False
        voor = len(b["atoms"])
        b["atoms"] = [a for a in b["atoms"] if a["sid"] != sid]
        if len(b["atoms"]) == voor:
            return False
        self._save()
        return True

    def merge_atoms(self, bid: str, sids: list[str], kop: str) -> bool:
        """Voeg staging-atomen samen tot één samengestelde kaart (kop + body = de rest),
        vóór ze de bibliotheek in gaan. Bron/provenance/reference van het eerste deel."""
        b = self._items.get(bid)
        if b is None or len(sids) < 2 or not (kop or "").strip():
            return False
        delen = [a for a in b["atoms"] if a["sid"] in sids]
        if len(delen) < 2:
            return False
        regels: list[str] = []
        for d in delen:
            regels.append(f"— {d['content']}")
            if d.get("body"):
                regels.append(d["body"])
        from nooch_village.kennisbank import PROVENANCE_TRUST
        provs = [d["provenance"] for d in delen if d["provenance"] in PROVENANCE_TRUST]
        prov = max(provs, key=lambda p: PROVENANCE_TRUST[p]) if provs else "unknown"
        # De verantwoording reist mee met de gekozen provenance (anders de eerste die er is).
        note = (next((d.get("provenance_note") for d in delen
                      if d["provenance"] == prov and d.get("provenance_note")), None)
                or next((d.get("provenance_note") for d in delen
                         if d.get("provenance_note")), None))
        rids: list[str] = []
        for d in delen:
            for r in d.get("radar_rids") or []:
                if r not in rids:
                    rids.append(r)
        samengesteld = {"sid": "m" + uuid.uuid4().hex[:4], "content": kop.strip(),
                        "body": "\n".join(regels)[:4000], "subject": delen[0]["subject"],
                        "provenance": prov, "provenance_note": note,
                        "source": delen[0]["source"],
                        "reference": next((d["reference"] for d in delen if d.get("reference")), None),
                        "radar_rids": rids,
                        "flags": []}
        rest = [a for a in b["atoms"] if a["sid"] not in sids]
        b["atoms"] = [samengesteld] + rest
        self._save()
        return True

    def discard(self, bid: str) -> bool:
        if bid not in self._items:
            return False
        del self._items[bid]
        self._save()
        return True


def _commit_signaal_atoom(a: dict, notes, radar) -> tuple[bool, bool]:
    """Eén staging-atoom mét radar_rids → kenniskaartje, via hetzelfde pad als de directe
    promotie (radar_promote): duplicaat-detectie op content+bron én reference-URL, herkomst
    stapelen i.p.v. dupliceren, en de promoted-marker op elk betrokken radar-item.
    Geeft (nieuw, gekoppeld) voor de telling."""
    from nooch_village.insight import Insight
    from nooch_village.kennisbank_intake import stable_id
    from nooch_village.radar_promote import find_duplicate

    content = a["content"]
    source = a["source"]
    link = (a.get("reference") or "").strip()

    def _stapel_extra(atom_id: str) -> None:
        """Herkomst van op /signals samengevoegde signalen stapelt mee op het kaartje."""
        for e in a.get("extra_bronnen") or []:
            try:
                notes.stack_provenance(atom_id, source=e.get("source") or "",
                                       reference=e.get("link") or "")
            except Exception:
                pass

    def _markeer(atom_id: str) -> None:
        if radar is None:
            return
        for rid in a.get("radar_rids") or []:
            try:
                # Eén signaal kan meerdere voorstellen opleveren (bron gelezen): het eerste
                # gecommitte kaartje wordt het anker; latere overschrijven de marker niet.
                al = radar.get(rid)
                if al is not None and al.get("promoted_atom_id"):
                    continue
                radar.mark_promoted(rid, atom_id)
            except Exception:
                pass  # fail-soft: een kapotte marker mag de commit nooit breken

    if a.get("van_bron"):
        # Atoom uit een GELEZEN bron: meerdere losse insights delen dezelfde artikel-link,
        # dus de reference-match zou ze onterecht samenvouwen. Dedupe hier op claim:
        # zelfde content+bron (stable_id) of exact dezelfde claim uit een andere bron.
        aid0 = stable_id(content, source)
        bestaand = notes.get(aid0)
        dup = aid0 if (bestaand is not None and not bestaand.archived) else None
    else:
        # Vangnet-atoom (de signaaltekst zelf): zelfde artikel-URL = zelfde signaal.
        dup = find_duplicate(notes, content, source, link)
    if dup is None:
        # MECE: exact dezelfde claim uit een ándere bron is hetzelfde inzicht — stapelen.
        dup = notes.find_claim_equal(content)
    if dup is not None:
        notes.stack_provenance(dup, source=source, reference=link)
        notes.add_tags(dup, ["signal"])
        _stapel_extra(dup)
        _markeer(dup)
        return False, True
    aid = stable_id(content, source)
    tags = ["signal"] + ([a["subject"]] if a.get("subject") else [])
    kaart = Insight(id=aid, claim=content[:500], body=a.get("body"),
                    source=source[:160], reference=(link[:200] or None),
                    source_date=a.get("source_date"),
                    tags=tags, evidence_type="reported",
                    provenance=a.get("provenance") or "media",
                    provenance_note=a.get("provenance_note"), version=1)
    try:
        notes.add(kaart)
    except ValueError:
        # Race/archief-rand: id bestaat al — herkomst koppelen i.p.v. crashen (append-only).
        notes.stack_provenance(aid, source=source, reference=link)
        notes.add_tags(aid, ["signal"])
        _stapel_extra(aid)
        _markeer(aid)
        return False, True
    _stapel_extra(aid)
    _markeer(aid)
    return True, False


def _verwerk_atoom(a: dict, notes, radar) -> tuple[int, int, int]:
    """Eén staging-atoom → bibliotheek, met alle dedupe/MECE/marker-regels.
    Geeft (nieuw, overgeslagen, gekoppeld) — precies één van de drie is 1."""
    if a.get("radar_rids"):
        was_nieuw, was_gekoppeld = _commit_signaal_atoom(a, notes, radar)
        return (1 if was_nieuw else 0, 0, 1 if was_gekoppeld else 0)
    kaart = atoom_kaart({"content": a["content"], "body": a.get("body"),
                         "subject": a["subject"], "provenance": a["provenance"],
                         "provenance_note": a.get("provenance_note"),
                         "source": a["source"], "reference": a.get("reference"),
                         "source_date": a.get("source_date"),
                         "flags": a.get("flags") or [], "link_hints": []})
    if notes.get(kaart.id) is not None:
        return 0, 1, 0
    # MECE: zelfde claim, andere bron → geen tweede kaartje maar herkomst erbij
    # (stack_provenance: bron/link stapelen, grounding +1).
    zelfde = notes.find_claim_equal(a["content"])
    if zelfde is not None:
        notes.stack_provenance(zelfde, source=a["source"],
                               reference=(a.get("reference") or ""))
        return 0, 0, 1
    notes.add(kaart)
    return 1, 0, 0


def commit_atom(store: StagingStore, bid: str, sid: str, data_dir: str,
                radar=None) -> dict | None:
    """Verwerk ÉÉN voorstel uit de set (knop "✓ Bewaar → bibliotheek", founder 19 jul:
    verwerkt = weg, anders lijkt het alsof er niets gebeurde). Zelfde pad als commit_batch,
    maar per kaart; het voorstel verdwijnt uit de set en een leeggeraakte set ruimt
    zichzelf op. Geeft {"uitkomst": "nieuw"|"bekend"|"gekoppeld", "leeg": bool} of None."""
    b = store.get(bid)
    a = next((x for x in (b or {}).get("atoms", []) if x["sid"] == sid), None)
    if a is None:
        return None
    notes = NotesStore(f"{data_dir}/notes.json")
    nieuw, overgeslagen, gekoppeld = _verwerk_atoom(a, notes, radar)
    store.remove_atom(bid, sid)
    rest = store.get(bid)
    leeg = rest is None or not rest.get("atoms")
    if leeg and rest is not None:
        store.discard(bid)
    uitkomst = "nieuw" if nieuw else ("gekoppeld" if gekoppeld else "bekend")
    return {"uitkomst": uitkomst, "leeg": leeg}


def commit_batch(store: StagingStore, bid: str, data_dir: str,
                 radar=None) -> tuple[int, int, int] | None:
    """Zet de (nagekeken) staging-atomen append-only in de bibliotheek. Idempotent op
    hash(content+bron): al bestaande kaarten worden overgeslagen. Atomen met `radar_rids`
    (signaal-promotie) lopen via het promote-pad: dedupe óók op reference-URL, herkomst
    stapelen op een bestaand kaartje, en de radar-items krijgen hun promoted-marker (mits
    `radar` is meegegeven). Geeft (nieuw, overgeslagen, gekoppeld) of None als de batch niet
    bestaat. De batch wordt na commit opgeruimd."""
    b = store.get(bid)
    if b is None:
        return None
    notes = NotesStore(f"{data_dir}/notes.json")
    nieuw = overgeslagen = gekoppeld = 0
    for a in b["atoms"]:
        n, o, g = _verwerk_atoom(a, notes, radar)
        nieuw += n
        overgeslagen += o
        gekoppeld += g
    store.discard(bid)
    return nieuw, overgeslagen, gekoppeld
