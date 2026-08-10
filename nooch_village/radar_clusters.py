"""radar_clusters.py — onderwerp-clustering van radar-signalen, met een BRONNEN-teller.

Waarom dit bestaat: de radar telde vermeldingen, en dat is het verkeerde getal. Acht keer mycelium
uit één feed is één bron die zichzelf herhaalt; acht keer mycelium uit acht bronnen is een trend.
Wie op vermeldingen stuurt, wordt geregeerd door de meest luidruchtige feed. Daarom telt een cluster
hier **verschillende bronnen**, niet losse signalen — en staat het aantal signalen er alleen naast
als context.

Twee lagen, in die volgorde:

1. **Semantisch** (de bedoeling): de signalen worden geëmbed en op cosinus-gelijkenis geclusterd.
   Dat vangt "mycelium leer" en "paddenstoelvezel-materiaal" als één onderwerp, wat een lexicale
   check nooit doet. Hergebruikt `kennis_embeddings` (`embed_many`, `cosine`, `EmbeddingStore`) —
   dezelfde laag die de kennisbank gebruikt, met een eigen index naast de radar.
2. **Lexicaal** (de terugval): geen sleutel, geen SDK, geen vectoren → Jaccard-woordoverlap, zoals
   `NotesStore.gelijkende`. Slechter, maar het levert nog steeds clusters op. Fail-soft is hier geen
   nettigheid maar een eis: zonder embeddings mag de radar niet stilvallen.

De clustering is **berekend, geen oordeel**. Er hoort dus geen rijpheidsniveau bij en er wordt niets
mee weggegooid: een cluster is een manier van kijken naar dezelfde signalen, en elk signaal blijft
individueel opvraagbaar (`Cluster.leden`).

Determinisme: de greedy toewijzing loopt in vaste volgorde (oudste eerst, dan id), zodat dezelfde
data altijd dezelfde clusters geeft. Een clustering die per page-load verspringt is onbruikbaar om
op te sturen.
"""
from __future__ import annotations

import datetime
import logging
import os
import re
import time

from nooch_village.util import JsonStore

log = logging.getLogger("village.radar.clusters")

# Cosinus-drempel voor "zelfde onderwerp". Bewust LAGER dan de duplicaat-drempel van de kennisbank
# (_SEM_KANDIDAAT = 0.86): daar is de vraag "is dit hetzelfde inzicht", hier "gaat dit over hetzelfde
# onderwerp". Twee verschillende feiten over mycelium horen in één cluster maar zijn geen duplicaat.
STANDAARD_DREMPEL = 0.72
# Jaccard-drempel voor de lexicale terugval. Lager dan `gelijkende` (0.55) om dezelfde reden:
# onderwerp-gelijkenis, niet inhoud-gelijkenis.
LEXICAAL_DREMPEL = 0.22
STANDAARD_VENSTER_DAGEN = 30

INDEX_BESTAND = "radar_embeddings.json"

_TOKEN = re.compile(r"[\W_]+")
# Woorden die overal in de radar staan en dus niets onderscheiden — zonder deze lijst klontert de
# lexicale terugval alles samen op "duurzame", "materiaal" en "schoenen".
_STOP = {"deze", "voor", "over", "naar", "wordt", "worden", "heeft", "hebben", "kunnen",
         "waarbij", "waarmee", "zoals", "onder", "tussen", "andere", "nieuwe", "nieuw",
         "duurzame", "duurzaam", "materiaal", "materialen", "schoenen", "schoen", "productie",
         "with", "from", "that", "this", "have", "will", "their", "which", "more", "than",
         "into", "about", "been", "they", "would", "could", "when", "what", "were", "also",
         "sustainable", "material", "materials", "shoes", "shoe", "footwear", "brand", "brands"}


def tokens(tekst: str) -> frozenset:
    """Betekenisdragende woorden (≥4 tekens, geen stopwoord) — dezelfde vorm als `gelijkende`."""
    return frozenset(w for w in _TOKEN.split((tekst or "").lower())
                     if len(w) >= 4 and w not in _STOP)


def jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def signaaltekst(item: dict) -> str:
    """De tekst waarop een signaal wordt vergeleken: inhoud plus de reden dat hij is opgehaald."""
    return f"{item.get('content', '')} {item.get('rationale', '')}".strip()


# ── De bronnen-teller ────────────────────────────────────────────────────────────────────────

def bron_van(item: dict) -> str:
    """De bron van één signaal, genormaliseerd tot iets telbaars.

    Volgorde: het `source`-veld (de host die de ingest vastlegde: 'fashionunited.com'), anders de
    host uit de link, anders de feed. Leeg → "onbekend", en dat is één bron, geen n bronnen: acht
    signalen zonder herkomst mogen niet als acht onafhankelijke bevestigingen tellen."""
    bron = str(item.get("source") or "").strip().lower()
    if bron:
        return bron
    link = str(item.get("link") or "").strip().lower()
    if link:
        host = link.split("//", 1)[-1].split("/", 1)[0]
        if host:
            return host
    return str(item.get("feed") or "").strip().lower() or "onbekend"


def bronnen_van(leden: list[dict]) -> set[str]:
    """De VERSCHILLENDE bronnen in een cluster. Dit is het getal dat een trend aanwijst; het aantal
    signalen is dat niet. Acht vermeldingen uit één feed geven hier 1 terug."""
    return {bron_van(i) for i in leden}


# ── Tijd ─────────────────────────────────────────────────────────────────────────────────────

def tijdstip(item: dict) -> float:
    """Het moment waarop dit signaal telt: de publicatiedatum van het artikel als die er is, anders
    het moment van ingest. Een oud artikel dat vandaag binnenkomt is historisch bewijs, geen vers
    nieuws — dat onderscheid maakt `RadarStore.add` al, en de trend hoort het te respecteren."""
    rauw = str(item.get("published_at") or "").strip()
    if rauw:
        try:
            dt = datetime.datetime.fromisoformat(rauw.replace("Z", "+00:00"))
            return dt.timestamp()
        except ValueError:
            pass
    try:
        return float(item.get("at") or 0.0)
    except (TypeError, ValueError):
        return 0.0


# ── Vectoren ─────────────────────────────────────────────────────────────────────────────────

# Batchen, de cap per render en het slot bij het schrijven leven sinds de kennislaag-grounding in
# `kennis_embeddings.vectors_for` — één route voor beide corpora (radar-signalen en de kennislaag),
# met dezelfde lessen erin. Hier staat alleen nog wat radar-specifiek is: welke tekst en welke index.
STANDAARD_EMBED_CAP = 60


def _vectoren(items: list[dict], data_dir: str, embed_fn=None,
              cap: int = STANDAARD_EMBED_CAP, batch: int = 20) -> dict[str, list[float]]:
    """Vector per signaal-id, met een eigen index naast de radar. Fail-soft: geen sleutel, geen SDK
    of een API-fout → de vectoren die er al waren, en de caller clustert lexicaal."""
    try:
        from nooch_village.kennis_embeddings import vectors_for
    except Exception as e:                           # noqa: BLE001 — geen SDK is een geldige toestand
        log.info("geen embedding-laag beschikbaar (%s) — radar clustert lexicaal", e)
        return {}
    uit = vectors_for(items, os.path.join(data_dir, INDEX_BESTAND), signaaltekst,
                      cap=cap, batch=batch, embed_fn=embed_fn)
    if len(uit) < len(items):
        log.info("radar-embeddings: %d van de %d nog niet geïndexeerd (cap %d per render) — "
                 "draai `village radar_embed` om de index in één keer te vullen",
                 len(items) - len(uit), len(items), cap)
    return uit


# ── Clusteren ────────────────────────────────────────────────────────────────────────────────

def _onderwerp(leden: list[dict]) -> str:
    """Het label van een cluster: de inhoud van het oudste lid. Bewust geen LLM-samenvatting —
    dat zou een oordeel toevoegen aan iets wat een berekening hoort te zijn, en het label moet
    letterlijk terug te vinden zijn in de signalen eronder."""
    oudste = min(leden, key=lambda i: (tijdstip(i), i.get("id", "")))
    return str(oudste.get("content", ""))[:120] or "(zonder titel)"


def cluster_signalen(items: list[dict], *, data_dir: str = "data", drempel: float | None = None,
                     embed_fn=None, semantisch: bool | None = None) -> list[dict]:
    """Groepeer signalen per onderwerp. Geeft clusters, nieuwste onderwerp eerst.

    Elk cluster: {sleutel, onderwerp, leden, modus}. `modus` zegt eerlijk welke laag het deed
    ('semantisch' of 'lexicaal'), zodat het scherm niet suggereert dat er betekenis is vergeleken
    terwijl er woorden zijn geteld.

    `semantisch=False` dwingt de lexicale terugval af (tests, en een bewuste uit-stand)."""
    items = [i for i in items if i.get("id")]
    if not items:
        return []
    vecs = {} if semantisch is False else _vectoren(items, data_dir, embed_fn)
    # Semantisch alleen als ÉLK signaal een vector heeft. Bij een gedeeltelijke index zou een
    # signaal zonder vector cosinus 0 scoren tegen alles en dus altijd een eigen cluster worden —
    # dat leest als "apart onderwerp" terwijl het "nog niet geïndexeerd" betekent. Dan liever
    # eerlijk lexicaal voor de hele render, en semantisch zodra de index compleet is.
    volledig = bool(vecs) and len(vecs) == len(items)
    if vecs and not volledig:
        log.info("radar-index nog niet compleet (%d/%d) — deze render clustert lexicaal",
                 len(vecs), len(items))
    if not volledig:
        vecs = {}
    modus = "semantisch" if vecs else "lexicaal"
    grens = drempel if drempel is not None else (
        STANDAARD_DREMPEL if vecs else LEXICAAL_DREMPEL)

    # Vaste volgorde: oudste eerst, dan id. Zonder dit verspringen clusters per page-load en is de
    # trend niet te lezen.
    geordend = sorted(items, key=lambda i: (tijdstip(i), i.get("id", "")))
    if vecs:
        from nooch_village.kennis_embeddings import cosine

        def gelijk(a: dict, b: dict) -> float:
            return cosine(vecs.get(a["id"]), vecs.get(b["id"]))
    else:
        cache: dict[str, frozenset] = {}

        def gelijk(a: dict, b: dict) -> float:
            for it in (a, b):
                if it["id"] not in cache:
                    cache[it["id"]] = tokens(signaaltekst(it))
            return jaccard(cache[a["id"]], cache[b["id"]])

    clusters: list[dict] = []
    for it in geordend:
        beste, beste_score = None, 0.0
        for c in clusters:
            # Vergelijk met de representant (het oudste lid), niet met een centroïde: een centroïde
            # schuift op naarmate een cluster groeit, waardoor het onderwerp langzaam wegdrijft.
            score = gelijk(c["leden"][0], it)
            if score >= grens and score > beste_score:
                beste, beste_score = c, score
        if beste is None:
            clusters.append({"sleutel": it["id"], "leden": [it], "modus": modus})
        else:
            beste["leden"].append(it)
    for c in clusters:
        c["onderwerp"] = _onderwerp(c["leden"])
    clusters.sort(key=lambda c: max(tijdstip(i) for i in c["leden"]), reverse=True)
    return clusters


# ── Trend ────────────────────────────────────────────────────────────────────────────────────

def trend_van(leden: list[dict], *, nu: float, venster_dagen: int = STANDAARD_VENSTER_DAGEN) -> dict:
    """Vergelijk het huidige venster met het venster ervóór. Beslist op BRONNEN, niet op signalen.

    Geeft {signalen, bronnen, eerder_bronnen, eerder_signalen, richting}. `richting` is stijgend /
    stabiel / dalend. Waarom op bronnen: een feed die twee keer zo vaak publiceert over hetzelfde
    is geen opkomend onderwerp, en een teller op vermeldingen zou dat wél zo laten lijken."""
    breedte = max(1, int(venster_dagen)) * 86400
    huidig = [i for i in leden if nu - tijdstip(i) < breedte]
    eerder = [i for i in leden if breedte <= nu - tijdstip(i) < 2 * breedte]
    nu_bronnen, toen_bronnen = len(bronnen_van(huidig)), len(bronnen_van(eerder))
    if nu_bronnen > toen_bronnen:
        richting = "stijgend"
    elif nu_bronnen < toen_bronnen:
        richting = "dalend"
    else:
        richting = "stabiel"
    return {"signalen": len(huidig), "bronnen": nu_bronnen,
            "eerder_signalen": len(eerder), "eerder_bronnen": toen_bronnen,
            "richting": richting}


def met_trend(clusters: list[dict], *, nu: float,
              venster_dagen: int = STANDAARD_VENSTER_DAGEN) -> list[dict]:
    """Hang de trend aan elk cluster en sorteer: stijgend eerst, dan op aantal bronnen."""
    for c in clusters:
        c["trend"] = trend_van(c["leden"], nu=nu, venster_dagen=venster_dagen)
    volgorde = {"stijgend": 0, "stabiel": 1, "dalend": 2}
    clusters.sort(key=lambda c: (volgorde.get(c["trend"]["richting"], 3),
                                 -c["trend"]["bronnen"], -len(c["leden"])))
    return clusters


# ── Wat de founder met een cluster deed ──────────────────────────────────────────────────────

class ClusterBesluitStore(JsonStore):
    """Wat de founder met een stijgend onderwerp deed: er een project van gemaakt, of geparkeerd
    als 'watch'.

    Bewust GEEN label en geen trede. Clustering en de bronnen-teller zijn een berekening; de vraag
    of een opkomend onderwerp een project waard is, is een strategische keuze van de founder die
    niet uit een steekproef te leren valt. Deze store onthoudt alleen wat hij besloot, zodat een
    afgehandeld onderwerp niet elke week opnieuw om aandacht vraagt.

    Sleutel = het cluster-id (het id van het oudste lid), dus stabiel zolang dat signaal bestaat."""

    _WRITE_METHODS = ("zet",)
    _STATE = "_data"
    _EXPECT = dict

    def _load(self) -> None:
        super()._load()
        self._data.setdefault("besluiten", {})

    def besluit(self, sleutel: str) -> dict | None:
        return (self._data.get("besluiten") or {}).get(sleutel)

    def alles(self) -> dict:
        return dict(self._data.get("besluiten") or {})

    def zet(self, sleutel: str, keuze: str, *, onderwerp: str = "", door: str = "",
            ref: str = "") -> bool:
        """`keuze` ∈ {project, watch}. `ref` = het project-id als er een project uit ontstond."""
        if not sleutel or keuze not in ("project", "watch"):
            return False
        self._data["besluiten"][sleutel] = {"keuze": keuze, "onderwerp": onderwerp[:160],
                                            "door": door or "?", "ref": ref, "ts": time.time()}
        self._save()
        return True


def vul_index(items: list[dict], data_dir: str, *, batch: int = 20, per_min: int = 90,
              sleep_fn=None, log_fn=print, embed_fn=None) -> dict:
    """Vul de radar-embedding-index in één keer, getemporiseerd — de tegenhanger van de
    kennisbank-backfill (`kennis_embeddings.index_backfill`), voor radar-signalen.

    Bestaat omdat een page-load geen plek is om honderden embeddings op te halen. Draai dit één
    keer na een deploy of een grote ingest; daarna houdt de render zichzelf bij met het handjevol
    verse signalen dat er per dag bijkomt.

    Herstartbaar en idempotent: al geïndexeerde signalen worden overgeslagen (hash-vergelijk), dus
    een tweede run kost niets."""
    import time as _time
    sleep_fn = sleep_fn or _time.sleep
    try:
        from nooch_village.kennis_embeddings import EmbeddingStore, _hash
    except Exception as e:                           # noqa: BLE001
        log_fn(f"geen embedding-laag beschikbaar: {e}")
        return {"todo": 0, "gedaan": 0, "mislukt": 0}
    store = EmbeddingStore(os.path.join(data_dir, INDEX_BESTAND))
    todo = [i for i in items if store.hash_of(i["id"]) != _hash(signaaltekst(i))]
    log_fn(f"signalen: {len(items)} | al geïndexeerd: {len(items) - len(todo)} | "
           f"te doen: {len(todo)}")
    pauze = (60.0 * batch / per_min) if per_min > 0 else 0.0
    gedaan = mislukt = 0
    for start in range(0, len(todo), batch):
        groep = todo[start:start + batch]
        # cap=batch: `_vectoren` doet precies deze groep, schrijft 'm weg en respecteert dezelfde
        # fail-soft-regels. Geen tweede embed-pad dat kan gaan afwijken.
        voor = len(store)
        _vectoren(groep, data_dir, embed_fn=embed_fn, cap=batch, batch=batch)
        store = EmbeddingStore(os.path.join(data_dir, INDEX_BESTAND))
        erbij = len(store) - voor
        gedaan += max(0, erbij)
        mislukt += len(groep) - max(0, erbij)
        log_fn(f"  {min(start + batch, len(todo))}/{len(todo)} — {gedaan} geïndexeerd")
        if pauze and start + batch < len(todo):
            sleep_fn(pauze)
    return {"todo": len(todo), "gedaan": gedaan, "mislukt": mislukt}
