from __future__ import annotations
import json, os, re
from nooch_village.insight import Insight


def _woorden(tekst: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", tekst.lower()) if w}


def subject_van_tags(tags: list[str]) -> str:
    """Het kennisbank-onderwerp = de eerste tag uit het vaste vocabulaire (of '')."""
    from nooch_village.kennisbank_intake import SUBJECTS
    for t in tags or []:
        if t in SUBJECTS:
            return t
    return ""


class NotesStore:
    def __init__(self, path: str = "data/notes.json"):
        self._path = path
        self._notes: dict[str, dict] = self._load()

    def _load(self) -> dict:
        if not os.path.exists(self._path):
            return {}
        with open(self._path, encoding="utf-8") as f:
            return json.load(f)

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._notes, f, indent=2, ensure_ascii=False)

    def add(self, note: Insight) -> None:
        if note.id in self._notes:
            raise ValueError(f"Note id '{note.id}' bestaat al")
        self._notes[note.id] = note.model_dump(mode="json")
        self._save()

    def get(self, note_id: str) -> Insight | None:
        data = self._notes.get(note_id)
        return Insight(**data) if data else None

    def remove(self, note_id: str) -> bool:
        """Verwijder een kaartje (curatie/correctie). Ruimt ook inkomende touwtjes op zodat
        er geen verwijzingen naar een verdwenen kaartje achterblijven. False als het niet
        bestond."""
        if note_id not in self._notes:
            return False
        del self._notes[note_id]
        for d in self._notes.values():
            lt = d.get("links_to") or []
            if note_id in lt:
                d["links_to"] = [x for x in lt if x != note_id]
        self._save()
        return True

    def all(self) -> list[Insight]:
        return [Insight(**d) for d in self._notes.values()]

    def by_concept(self, concept_id: str) -> list[Insight]:
        return [n for n in self.all() if n.concept_id == concept_id]

    def set_kind(self, note_id: str, kind) -> bool:
        """Ken de SOORT (ClaimKind) toe aan een bestaand kaartje. Gebruikt door de migratie en
        door curatie. False als het kaartje niet bestaat."""
        bestaand = self.get(note_id)
        if bestaand is None:
            return False
        bestaand.kind = kind
        from datetime import datetime
        bestaand.last_updated_at = datetime.now()
        self._notes[note_id] = bestaand.model_dump(mode="json")
        self._save()
        return True

    def add_tags(self, note_id: str, tags: list[str]) -> bool:
        """Voeg tags idempotent toe aan een bestaand kaartje (curatie: bijv. het
        onderwerp uit het kennisbank-vocabulaire). Volgorde blijft; bestaande tags
        worden nooit gedupliceerd. False als het kaartje niet bestaat."""
        bestaand = self.get(note_id)
        if bestaand is None:
            return False
        nieuw = [t for t in tags if t and t not in bestaand.tags]
        if nieuw:
            bestaand.tags.extend(nieuw)
            from datetime import datetime
            bestaand.last_updated_at = datetime.now()
            self._notes[note_id] = bestaand.model_dump(mode="json")
            self._save()
        return True

    def archive(self, note_id: str, archived: bool = True) -> bool:
        """Curatie (append-only): archiveren i.p.v. wissen — de kaart verdwijnt uit de
        lijsten (load_atoms filtert) maar blijft bestaan en is terug te zetten."""
        bestaand = self.get(note_id)
        if bestaand is None:
            return False
        bestaand.archived = archived
        from datetime import datetime
        bestaand.last_updated_at = datetime.now()
        self._notes[note_id] = bestaand.model_dump(mode="json")
        self._save()
        return True

    def edit_note(self, note_id: str, *, claim: str | None = None,
                  body: str | None = None) -> Insight | None:
        """Bewerk een kaart append-only (layout PR-2): de vorige claim/body gaat in
        edit_history vóór de nieuwe waarde erin komt. Voor extractie-fouten — geen stille
        overschrijving. Lege claim wordt geweigerd. None als het kaartje niet bestaat."""
        bestaand = self.get(note_id)
        if bestaand is None:
            return None
        nieuwe_claim = (claim if claim is not None else bestaand.claim).strip()
        if not nieuwe_claim:
            return None
        nieuwe_body = body if body is not None else bestaand.body
        if nieuwe_claim == bestaand.claim and nieuwe_body == bestaand.body:
            return bestaand                    # niets veranderd → geen lege historie-entry
        from datetime import datetime
        bestaand.edit_history.append({"claim": bestaand.claim, "body": bestaand.body,
                                      "at": datetime.now().isoformat(timespec="seconds")})
        bestaand.claim = nieuwe_claim
        bestaand.body = nieuwe_body
        bestaand.last_updated_at = datetime.now()
        self._notes[note_id] = bestaand.model_dump(mode="json")
        self._save()
        return bestaand

    def add_related(self, note_id: str, content: str, source: str,
                    provenance: str = "unknown") -> Insight | None:
        """"Voeg gerelateerd feit toe" (layout PR-2, het 36%-geval): maak een NIEUW atoom met
        een EIGEN bron en link het aan het bestaande (append-only, geen verrijking-in-place —
        zo blijft het een aparte stem voor de woozle-guard). None als het anker niet bestaat,
        de content leeg is, of het nieuwe atoom al bestaat (idempotent op hash content+bron)."""
        anker = self.get(note_id)
        if anker is None or not (content or "").strip():
            return None
        from nooch_village.kennisbank_intake import stable_id
        bron = (source or "").strip() or "onbekend"
        nid = stable_id(content, bron)
        if nid in self._notes:
            return None
        subject = subject_van_tags(anker.tags)
        nieuw = Insight(id=nid, claim=content.strip()[:500], source=bron,
                        provenance=provenance,
                        tags=([subject] if subject else []), links_to=[note_id])
        self._notes[nid] = nieuw.model_dump(mode="json")
        self._save()
        return nieuw

    def supersede(self, note_id: str, nieuwe_ids: list[str]) -> bool:
        """Re-atomiseer-migratie (append-only): archiveer een oud atoom en laat het naar
        de nieuwe, schone atomen verwijzen (superseded_by). Het atoom wordt nooit gewist —
        het spoor van oud → nieuw blijft. False als het niet bestaat."""
        bestaand = self.get(note_id)
        if bestaand is None:
            return False
        bestaand.archived = True
        bestaand.superseded_by = list(dict.fromkeys(nieuwe_ids))
        from datetime import datetime
        bestaand.last_updated_at = datetime.now()
        self._notes[note_id] = bestaand.model_dump(mode="json")
        self._save()
        return True

    def merge(self, note_ids: list[str], kop: str, by: str = "") -> Insight | None:
        """Voeg meerdere kaartjes samen tot ÉÉN samengestelde kaart: claim = de (bewerkbare)
        kop, body = de inhouden van de delen, bronnen samengevoegd, provenance = de hoogste
        van de delen. De originelen worden GEARCHIVEERD (niet vernietigd) en de nieuwe kaart
        verwijst ernaar via merged_from — de terugweg blijft altijd bestaan."""
        kop = (kop or "").strip()
        delen = [self.get(nid) for nid in note_ids]
        delen = [d for d in delen if d is not None]
        if len(delen) < 2 or not kop:
            return None
        regels: list[str] = []
        for d in delen:
            regels.append(f"— {d.claim}")
            if d.body:
                regels.append(d.body)
        bronnen = list(dict.fromkeys(d.source for d in delen if d.source))
        from nooch_village.kennisbank import PROVENANCE_TRUST
        provs = [d.provenance for d in delen if d.provenance in PROVENANCE_TRUST]
        prov = max(provs, key=lambda p: PROVENANCE_TRUST[p]) if provs else None
        refs = [d.reference for d in delen if d.reference]
        tags = list(dict.fromkeys(t for d in delen for t in d.tags))
        import hashlib
        mid = "atom_merge_" + hashlib.sha1(
            ("|".join(sorted(d.id for d in delen)) + kop).encode("utf-8")).hexdigest()[:12]
        if self.get(mid) is not None:
            return None                        # zelfde delen + zelfde kop → al samengevoegd
        kaart = Insight(id=mid, claim=kop[:500], body="\n".join(regels)[:4000],
                        source="; ".join(bronnen)[:160] or "samengevoegd",
                        reference=refs[0] if refs else None,
                        provenance=prov, tags=tags,
                        merged_from=[d.id for d in delen])
        self.add(kaart)
        for d in delen:
            self.archive(d.id)
        return kaart

    def add_relation(self, from_id: str, to_id: str, relation: str) -> Insight | None:
        """Leg een bewijs-relatie: `from_id` STEUNT of SPREEKT TEGEN `to_id`.
        relation ∈ {'supports', 'contradicts'}. Gericht, idempotent, geen zelf-relatie, fail-closed
        (bestaat een van beide niet → None). Geeft het bijgewerkte bron-kaartje."""
        if relation not in ("supports", "contradicts") or from_id == to_id:
            return None
        bron = self.get(from_id)
        if bron is None or self.get(to_id) is None:
            return None
        lijst = getattr(bron, relation)
        if to_id not in lijst:
            lijst.append(to_id)
            from datetime import datetime
            bron.last_updated_at = datetime.now()
            self._notes[from_id] = bron.model_dump(mode="json")
            self._save()
        return bron

    def enrich(self, note_id: str, nieuwe_reference: str | None = None) -> Insight | None:
        """Verrijk een bestaande kaart met een nieuwe grounding: voeg bron toe,
        hoog de grounding-teller op, en zet last_updated_at op nu. Claim en status
        blijven ongemoeid. Geeft de verrijkte kaart terug, of None als hij niet bestaat."""
        bestaand = self.get(note_id)
        if bestaand is None:
            return None
        if nieuwe_reference and nieuwe_reference not in (bestaand.reference or ""):
            if bestaand.reference:
                bestaand.reference = bestaand.reference + "; " + nieuwe_reference
            else:
                bestaand.reference = nieuwe_reference
        bestaand.grounding_count += 1
        from datetime import datetime
        bestaand.last_updated_at = datetime.now()
        self._notes[note_id] = bestaand.model_dump(mode="json")
        self._save()
        return bestaand

    def link(self, from_id: str, to_id: str) -> Insight | None:
        """Verbind twee bestaande kaartjes: voeg `to_id` toe aan de links_to van
        `from_id`. Gericht (van bron naar doel), idempotent (geen dubbele link) en
        fail-closed: bestaat een van beide niet, of wijst het kaartje naar zichzelf,
        dan gebeurt er niets en is het resultaat None. Geeft anders het bijgewerkte
        bron-kaartje terug."""
        if from_id == to_id:
            return None
        bron = self.get(from_id)
        doel = self.get(to_id)
        if bron is None or doel is None:
            return None
        if to_id not in bron.links_to:
            bron.links_to.append(to_id)
            from datetime import datetime
            bron.last_updated_at = datetime.now()
            self._notes[from_id] = bron.model_dump(mode="json")
            self._save()
        return bron

    def neighbors(self, note_id: str) -> list[Insight]:
        """Geef alle kaartjes die met `note_id` verbonden zijn, in beide richtingen:
        de kaartjes waar dit kaartje naar wijst (eigen links_to) én de kaartjes die
        naar dit kaartje wijzen. Ontdubbeld, zonder het kaartje zelf, gesorteerd op
        id voor een stabiele volgorde. Bestaat het kaartje niet, dan een lege lijst
        (fail-closed)."""
        kaart = self.get(note_id)
        if kaart is None:
            return []
        verbonden: set[str] = set(kaart.links_to)
        for andere in self.all():
            if note_id in andere.links_to:
                verbonden.add(andere.id)
        verbonden.discard(note_id)
        resultaat = [self.get(vid) for vid in sorted(verbonden)]
        return [n for n in resultaat if n is not None]

    def cluster(self, note_id: str, max_size: int = 8) -> list[Insight]:
        """Verzamel een samenhangend groepje kaartjes rond een zaad-kaartje, breedte-
        eerst via de touwtjes (neighbors, beide richtingen). Het zaad-kaartje staat
        vooraan; daarna de buren oplopend in afstand, deterministisch op id. Begrensd
        op `max_size` zodat het materiaal voor één artikel behapbaar blijft. Bestaat
        het zaad niet, dan een lege lijst (fail-closed)."""
        from collections import deque
        seed = self.get(note_id)
        if seed is None:
            return []
        bezocht = {note_id}
        volgorde: list[Insight] = [seed]
        queue: deque[str] = deque([note_id])
        while queue and len(volgorde) < max_size:
            huidig = queue.popleft()
            for buur in self.neighbors(huidig):   # al gesorteerd op id
                if buur.id not in bezocht:
                    bezocht.add(buur.id)
                    volgorde.append(buur)
                    queue.append(buur.id)
                    if len(volgorde) >= max_size:
                        break
        return volgorde

    def content_seeds(self, budget: int, threshold: int | None = None) -> list[Insight]:
        """Spot welke kaartjes een publiek stuk verdienen: bevestigd (emergentie:
        grounding_count >= drempel) én verbonden (minstens één buur, dus een echt
        cluster, geen los feit). Sterkste eerst (grounding_count desc, dan id),
        begrensd op `budget`. Dedup op al-voorgestelde clusters gebeurt in de inbox."""
        from nooch_village.emergence import is_emerged, EMERGENCE_THRESHOLD
        thr = EMERGENCE_THRESHOLD if threshold is None else threshold
        if budget <= 0:
            return []
        seeds = [n for n in self.all()
                 if is_emerged(n, thr) and self.neighbors(n.id)]
        seeds.sort(key=lambda n: (-n.grounding_count, n.id))
        return seeds[:budget]

    def relevant_for(self, word: str, limit: int = 5) -> list[Insight]:
        """Vind kaartjes die termen delen met `word`, gewogen op zeldzaamheid.
        Een gedeeld woord telt zwaarder naarmate minder kaartjes het bevatten —
        zo onderscheidt 'barefoot' (zeldzaam) zich van 'shoes' (overal). Geen vaste
        stopwoordenlijst: wat generiek is, leidt het systeem zelf af uit de kaartjes.
        Matcht op het word-veld; kaartjes zonder word doen niet mee.
        Geeft de sterkste matches eerst, max `limit`."""
        if not word:
            return []
        kandidaten = [n for n in self.all() if n.word]
        if not kandidaten:
            return []

        zoek = _woorden(word)
        doc_freq: dict[str, int] = {}
        for n in kandidaten:
            for w in _woorden(n.word):
                doc_freq[w] = doc_freq.get(w, 0) + 1

        gescoord: list[tuple[float, Insight]] = []
        for n in kandidaten:
            if n.word == word:
                continue
            gedeeld = zoek & _woorden(n.word)
            score = sum(1.0 / doc_freq[w] for w in gedeeld)
            if score > 0:
                gescoord.append((score, n))

        gescoord.sort(key=lambda t: t[0], reverse=True)
        return [n for _, n in gescoord[:limit]]
