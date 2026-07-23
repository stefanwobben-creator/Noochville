"""kennis_embeddings — de semantische laag: dubbel-detectie op BETEKENIS, niet op woorden (founder 23 jul).

De lexicale voorkant-poort (`kennis_dedup`) vindt de dichtstbijzijnde bestaande kaart op woord-overlap.
Daardoor mist hij duplicaten die hetzelfde zeggen met ANDERE woorden: de biobased-drieling op laag 2
("bio-based is ver genoeg", "voor schoenen is de biobased route...", "voor gelijmde producten is
composteerbaarheid...") deelt te weinig woorden om elkaar te vinden, dus de LLM-oordeler kreeg ze nooit
te zien. Deze laag vult dat gat: elk kaartje krijgt een embedding (een vector die de betekenis vastlegt),
en we zoeken buren op afstand in die betekenisruimte. Zo komt een parafrase-duplicaat wél als kandidaat
boven, waarna dezelfde LLM-"zelfde?"-check beslist.

Ontwerp, in lijn met llm.py:
- Hergebruikt de Gemini-sleutel (GEMINI_API_KEY / GOOGLE_API_KEY) en de google-genai SDK.
- FAIL-SOFT overal: geen sleutel, geen SDK, geen index of een API-fout → geen vector (None) → de
  aanroeper valt terug op de lexicale poort (ongewijzigd gedrag). Nooit blokkeert dit het aanmaken
  van een kaartje.
- Embeddings ALLEEN als kandidaat-ophaler; het STAPEL-besluit blijft bij de LLM-oordeler. Twee feiten
  over hetzelfde onderwerp liggen dicht in de betekenisruimte maar zijn geen duplicaat — alleen een
  expliciet "zelfde" mag stapelen (zelfde asymmetrie als de rest van de poort).
- De index is een aparte store (kennis_embeddings.json) naast notes.json; hij wordt gevuld door de
  backfill (kennis_embeddings_backfill) en per (pad, mtime) gecachet zodat een intake-lus hem niet
  telkens herleest.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os

log = logging.getLogger("village.embed")

# Google's stabiele embedding-model (768-dim, ruime gratis tier). Overschrijfbaar via env (geen secret).
_MODEL = os.getenv("LLM_EMBED_MODEL", "text-embedding-004")


def _key() -> str | None:
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


def embed_many(texts: list[str], *, strict: bool = False) -> list[list[float] | None]:
    """Lijst teksten → lijst vectoren, één API-call (batch). Fail-soft: geen sleutel/SDK/fout, of een
    lege tekst → None op die plek. Geeft altijd een lijst even lang als de input.

    strict=True: her-raise de API-fout i.p.v. None terug te geven. Alleen de backfill gebruikt dit, zodat
    hij een 429 (quota) kan herkennen en netjes kan wachten+herproberen. De daemon-check laat strict=False
    (fail-soft, nooit wachten in het hete pad)."""
    schoon = [(t or "").strip() for t in texts]
    key = _key()
    if not key or not any(schoon):
        return [None] * len(schoon)
    try:
        from google import genai
        client = genai.Client(api_key=key)
        # Lege strings mogen niet de batch breken: stuur een spatie, maskeer het resultaat hieronder.
        resp = client.models.embed_content(model=_MODEL, contents=[t or " " for t in schoon])
        embs = list(getattr(resp, "embeddings", []) or [])
        if len(embs) != len(schoon):
            if strict:
                raise RuntimeError(f"embed gaf {len(embs)} vectoren voor {len(schoon)} teksten")
            return [None] * len(schoon)
        uit: list[list[float] | None] = []
        for t, e in zip(schoon, embs):
            vals = getattr(e, "values", None)
            uit.append([float(x) for x in vals] if (t and vals) else None)
        return uit
    except Exception as e:                      # geen SDK, netwerkfout, quota → fail-soft (of her-raise)
        if strict:
            raise
        log.warning("embed faalde (%s): %s", _MODEL, e)
        return [None] * len(schoon)


def embed(text: str) -> list[float] | None:
    """Eén tekst → vector of None (fail-soft)."""
    return embed_many([text])[0]


def cosine(a: list[float] | None, b: list[float] | None) -> float:
    """Cosinus-gelijkenis; 0.0 bij lege of ongelijke vectoren (nooit een exception)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _hash(text: str) -> str:
    return hashlib.sha1((text or "").encode("utf-8")).hexdigest()[:16]


class EmbeddingStore:
    """Simpele JSON-store: note_id → {"h": hash(claim), "v": vector}. De hash laat de backfill zien
    wanneer een claim veranderde (dan opnieuw embedden), zodat re-runs idempotent en goedkoop zijn."""

    def __init__(self, path: str):
        self.path = path
        self._d: dict[str, dict] = self._load()

    def _load(self) -> dict:
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:                       # corrupt/half-geschreven → leeg beginnen, niet crashen
            return {}

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._d, f)               # compact; vectoren zijn groot genoeg zonder indent
        os.replace(tmp, self.path)

    def hash_of(self, note_id: str) -> str | None:
        rec = self._d.get(note_id)
        return rec.get("h") if rec else None

    def upsert(self, note_id: str, claim: str, vec: list[float]) -> None:
        self._d[note_id] = {"h": _hash(claim), "v": vec}

    def drop(self, note_id: str) -> None:
        self._d.pop(note_id, None)

    def items(self):
        return self._d.items()

    def __len__(self) -> int:
        return len(self._d)


# Cache van geladen vectoren per (pad, mtime): een intake-lus beoordeelt tot 15 atomen achter elkaar;
# zonder cache zou hij de (paar MB) index telkens herlezen. Ongeldig zodra de backfill het bestand raakt.
_CACHE: dict[str, tuple[float, list[tuple[str, list[float]]]]] = {}


def _geladen_vectoren(path: str) -> list[tuple[str, list[float]]]:
    try:
        mt = os.path.getmtime(path)
    except OSError:
        return []
    c = _CACHE.get(path)
    if c and c[0] == mt:
        return c[1]
    st = EmbeddingStore(path)
    vecs = [(nid, rec.get("v")) for nid, rec in st.items() if rec.get("v")]
    _CACHE[path] = (mt, vecs)
    return vecs


class SemantiekIndex:
    """Betekenis-buren voor de voorkant-poort. Leeft naast notes.json (kennis_embeddings.json).
    Fail-soft: geen index of geen embedding → candidate() geeft None en de poort blijft lexicaal."""

    def __init__(self, notes_path: str, *, embed_fn=None):
        self.path = os.path.join(os.path.dirname(notes_path) or ".", "kennis_embeddings.json")
        self.embed_fn = embed_fn or embed

    def candidate(self, claim: str, notes, *, drempel: float = 0.82) -> tuple[str, str, float] | None:
        """Beste niet-gearchiveerde betekenis-buur boven `drempel`, als (note_id, claim, score).
        None als er geen index is, geen embedding lukt, of niets boven de drempel komt."""
        vecs = _geladen_vectoren(self.path)
        if not vecs:                            # geen backfill gedraaid → puur lexicaal
            return None
        q = self.embed_fn(claim)
        if not q:                               # geen sleutel/fout → fail-soft
            return None
        beste: tuple[str, float] | None = None
        for nid, v in vecs:
            sc = cosine(q, v)
            if sc >= drempel and (beste is None or sc > beste[1]):
                beste = (nid, sc)
        if beste is None:
            return None
        nid, sc = beste
        a = notes.get(nid)
        if a is None or getattr(a, "archived", False):
            return None
        return (nid, a.claim, sc)


def _retry_seconden(msg: str) -> float:
    """Haal de door de API voorgestelde wachttijd uit een 429-boodschap ('retryDelay': '55s' /
    'Please retry in 55.7s'). Geen match → 60s."""
    import re
    m = re.search(r"(\d+(?:\.\d+)?)\s*s(?:econds)?", msg)
    return float(m.group(1)) if m else 60.0


def _is_quota(msg: str) -> bool:
    m = (msg or "").lower()
    return "429" in m or "resource_exhausted" in m or "quota" in m or "rate limit" in m


def index_backfill(notes, store, *, batch: int = 20, per_min: int = 90,
                   sleep_fn=None, log=print, max_wachten: int = 6) -> dict:
    """Getemporiseerde, herstartbare backfill van de embedding-index. Embedt alleen nieuwe/gewijzigde
    claims (hash-vergelijk), in kleine batches, onder `per_min` verzoeken per minuut (elk kaartje telt
    als één verzoek op de gratis tier). Bij een 429 wacht hij de voorgestelde tijd en probeert de batch
    opnieuw (tot `max_wachten` keer). Archiveerde/verdwenen kaartjes gaan uit de index.

    Fail-soft per batch: een niet-quota-fout laat die batch als niet-geïndexeerd en gaat door. Geeft een
    stats-dict terug. `sleep_fn`/`log` injecteerbaar voor tests (geen echte wachttijd)."""
    import time as _time
    sleep_fn = sleep_fn or _time.sleep

    actief = [a for a in notes.all() if not a.archived]
    actieve_ids = {a.id for a in actief}
    weg = [nid for nid, _ in list(store.items()) if nid not in actieve_ids]
    for nid in weg:
        store.drop(nid)
    todo = [a for a in actief if store.hash_of(a.id) != _hash(a.claim)]
    log(f"kaartjes actief: {len(actief)} | al geïndexeerd: {len(actief) - len(todo)} | "
        f"te (her)indexeren: {len(todo)} | uit index verwijderd: {len(weg)}")

    pauze = (60.0 * batch / per_min) if per_min > 0 else 0.0    # proactief onder de limiet blijven
    gedaan = mislukt = 0
    for i in range(0, len(todo), batch):
        groep = todo[i:i + batch]
        vecs = None
        for _poging in range(max_wachten):
            try:
                vecs = embed_many([a.claim for a in groep], strict=True)
                break
            except Exception as e:                             # noqa: BLE001 — quota vs echte fout
                s = str(e)
                if _is_quota(s):
                    w = _retry_seconden(s) + 1.0
                    log(f"  quota bereikt — wacht {w:.0f}s en probeer de batch opnieuw")
                    sleep_fn(w)
                    continue
                log(f"  batch overgeslagen (geen quota-fout): {s[:120]}")
                break
        if vecs is None:
            vecs = [None] * len(groep)
        for a, v in zip(groep, vecs):
            if v:
                store.upsert(a.id, a.claim, v)
                gedaan += 1
            else:
                mislukt += 1
        store.save()                                           # per batch → veilig af te breken/hervatten
        log(f"  batch {i // batch + 1}: +{sum(1 for v in vecs if v)} (totaal {gedaan}/{len(todo)})")
        if pauze and i + batch < len(todo):
            sleep_fn(pauze)
    return {"actief": len(actief), "geindexeerd": gedaan, "mislukt": mislukt,
            "verwijderd": len(weg), "index_omvang": len(store)}
