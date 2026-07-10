"""ObservationStore — append-only tijdreeks van operationele metingen.

Opslag: data/observations.jsonl. Elke regel is één JSON-object:
  {role_id, metric, value, ts, datum, bron, meta}
Append-only: het bestand wordt nooit herschreven.

`datum` (YYYY-MM-DD, UTC) en `bron` maken elke observatie zelf-beschrijvend: bij welke dag hoort
de waarde en welke bron heeft 'm geleverd. `record_daily` bewaakt "één datapunt per bron per dag"
(idempotent), zodat een tweede puls op dezelfde dag niet dubbel schrijft.
"""
from __future__ import annotations
import json, logging, os, re, time
from datetime import datetime, timezone

from nooch_village.meetcatalog import cadence_of

log = logging.getLogger(__name__)


def _utc_date(ts: float) -> str:
    """De UTC-dag (YYYY-MM-DD) waarin een timestamp valt."""
    return datetime.fromtimestamp(ts, timezone.utc).date().isoformat()


def dim_slug(value: str) -> str:
    """Veilige, stabiele sleutel voor een dimensie-waarde (bijv. een Library-keyword) in de metric-sleutel
    `<source>_<veld>_day::<slug>`. Het rauwe woord leeft in de observatie-meta; de slug in de sleutel."""
    return re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")


class ObservationStore:
    """Append-only tijdreeks met een lazy in-memory index (scope 2, punt 5). De index (alle rijen +
    een dedup-set + een (metric,bron)-index) wordt éénmaal per instance uit het bestand opgebouwd, en
    incrementeel bijgewerkt bij `record`. Zo is `record_daily` O(1) i.p.v. een lineaire scan per write
    (was O(N·rijen) = kwadratisch bij N dimensie-reeksen/dag) en herlezen we het bestand niet per call.
    De twee herschrijf-migraties (rename_metric, normalize_source_role_ids) invalideren de index.
    Aanname: één schrijvende instance per proces (collector = één `obs`; cockpit = verse store per
    request). Geen gedeelde langlevende instance met een externe schrijver."""

    def __init__(self, path: str):
        self.path = path
        self._rows = None        # lazy cache: alle rijen (list[dict])
        self._dedup = None       # set van (role_id, metric, bron, datum) → O(1) idempotentie
        self._by_mb = None       # {(metric, bron): [rows]} → O(1) daily_series op metric+bron

    def _ensure_cache(self) -> None:
        if self._rows is not None:
            return
        self._rows, self._dedup, self._by_mb = [], set(), {}
        if os.path.exists(self.path):
            with open(self.path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self._index(json.loads(line))

    @staticmethod
    def _dedup_key(role_id, metric, bron, datum, event_id=""):
        """Idempotentie-sleutel, cadans-bewust. Regulier (daily/weekly/monthly/ongecatalogiseerd) →
        per dag: (role_id, metric, bron, datum) — ongewijzigd. Irregulier (bv. werkoverleg) → óók op
        `event_id`, zodat meerdere meetpunten per dag naast elkaar bestaan maar een herhaalde schrijf
        met hetzelfde event_id niet dubbel landt."""
        base = (role_id, metric, bron, datum)
        if cadence_of(metric, bron) == "irregular":
            return base + (str(event_id or ""),)
        return base

    def _index(self, r: dict) -> None:
        self._rows.append(r)
        self._dedup.add(self._dedup_key(r.get("role_id"), r.get("metric"), r.get("bron"),
                                        r.get("datum"), (r.get("meta") or {}).get("event_id", "")))
        self._by_mb.setdefault((r.get("metric"), r.get("bron")), []).append(r)

    def _invalidate(self) -> None:
        """Na een herschrijf van het bestand (in-place mutatie): index opnieuw opbouwen bij volgend gebruik."""
        self._rows = self._dedup = self._by_mb = None

    def record(self, role_id: str, metric: str, value,
               ts: float | None = None, meta: dict | None = None,
               bron: str = "", datum: str | None = None) -> None:
        """Voeg één observatie toe aan het einde van het bestand (en aan de index als die geladen is)."""
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        ts = ts if ts is not None else time.time()
        row = {
            "role_id": role_id,
            "metric":  metric,
            "value":   value,
            "ts":      ts,
            "datum":   datum or _utc_date(ts),
            "bron":    bron,
            "meta":    meta or {},
        }
        with open(self.path, "a") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        if self._rows is not None:
            self._index(row)

    def rename_metric(self, old_metric: str, new_metric: str, bron: str | None = None) -> int:
        """Hernoem een metric-sleutel in alle bestaande rijen (optioneel per bron); herschrijft het
        bestand. Idempotent: geen rijen met old_metric → 0 wijzigingen. Voor migratie van legacy-
        sleutels naar het canonieke <source>_<field>_day-schema."""
        rows = self._read_all()
        n = 0
        for r in rows:
            if r.get("metric") == old_metric and (bron is None or r.get("bron") == bron):
                r["metric"] = new_metric
                n += 1
        if n:
            with open(self.path, "w") as f:
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
            self._invalidate()          # in-place mutatie + herschrijf → index opnieuw opbouwen
        return n

    def remove_metric(self, metric: str, bron: str | None = None) -> int:
        """Verwijder ALLE rijen met deze metric (optioneel per bron) uit het bestand. Voor het opruimen van
        een vervuilde reeks (geen doortelling). Herschrijft alleen bij een echte verwijdering; idempotent.
        Geeft het aantal verwijderde rijen terug."""
        rows = self._read_all()
        kept = [r for r in rows
                if not (r.get("metric") == metric and (bron is None or r.get("bron") == bron))]
        n = len(rows) - len(kept)
        if n:
            with open(self.path, "w") as f:
                for r in kept:
                    f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
            self._invalidate()          # herschrijf → index opnieuw opbouwen
        return n

    def remove_bron(self, bron: str, keep_prefix: str = "") -> int:
        """Verwijder ALLE rijen van een bron, behalve die waarvan de metric met `keep_prefix` begint. Voor
        het opruimen van reeksen die onder een verworpen ontwerp zijn geschreven (geen doortelling) terwijl
        een nieuw ontwerp onder dezelfde bron een andere metric-prefix schrijft. Idempotent; herschrijft
        alleen bij een echte verwijdering. Geeft het aantal verwijderde rijen terug."""
        rows = self._read_all()
        kept = [r for r in rows
                if not (r.get("bron") == bron
                        and not (keep_prefix and (r.get("metric") or "").startswith(keep_prefix)))]
        n = len(rows) - len(kept)
        if n:
            with open(self.path, "w") as f:
                for r in kept:
                    f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
            self._invalidate()
        return n

    def normalize_source_role_ids(self) -> dict:
        """Canoniek: voor een collector-dagmetric `<bron>_<veld>_day` is `role_id == bron`. Legacy-rijen
        met een andere role_id (bv. `website_watcher` van vóór de generieke collector) worden
        genormaliseerd:
          - botst met een canonieke (role_id==bron) rij met DEZELFDE waarde → oude rij droppen (dedup)
          - geen canonieke rij → role_id hernoemen naar bron (wordt daarmee zelf canoniek)
          - botst met een ANDERE waarde → laten staan (mens beslist; nooit data verliezen)
        Precisie-guard: alleen rijen waar `role_id != bron` ÉN `metric == f"{bron}_*_day"` ÉN bron
        niet-leeg — dat sluit werkoverleg (`werk_*` ≠ `werkoverleg_*`, role_id=cirkel) en de
        `visitors_via_*`-familie structureel uit. Herschrijft het bestand alleen als er iets verandert;
        idempotent (niets te doen → geen herschrijf). Geeft {dropped, renamed, conflicts} terug."""
        rows = self._read_all()
        canon = {}          # (metric, bron, datum) -> value voor role_id==bron (groeit mee bij rename)
        for r in rows:
            if r.get("role_id") == r.get("bron"):
                canon[(r.get("metric"), r.get("bron"), r.get("datum"))] = r.get("value")
        kept, dropped, renamed, conflicts = [], 0, 0, 0
        for r in rows:
            m, b, rid = r.get("metric"), r.get("bron"), r.get("role_id")
            in_scope = (bool(b) and rid != b and isinstance(m, str)
                        and m.startswith(f"{b}_") and m.endswith("_day"))
            if not in_scope:
                kept.append(r)
                continue
            key = (m, b, r.get("datum"))
            if key in canon:
                if canon[key] == r.get("value"):
                    dropped += 1                       # canonieke rij heeft dezelfde waarde → oude weg
                else:
                    conflicts += 1                     # andere waarde → niet aanraken
                    kept.append(r)
            else:
                r["role_id"] = b                       # geen canonieke rij → hernoemen (wordt canoniek)
                canon[key] = r.get("value")
                renamed += 1
                kept.append(r)
        if dropped or renamed:
            with open(self.path, "w") as f:
                for r in kept:
                    f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
            self._invalidate()          # in-place mutatie + herschrijf → index opnieuw opbouwen
        return {"dropped": dropped, "renamed": renamed, "conflicts": conflicts}

    def record_daily(self, role_id: str, metric: str, value, bron: str,
                     datum: str | None = None, ts: float | None = None,
                     meta: dict | None = None, event_id: str = "") -> bool:
        """Schrijf een dag-datapunt, cadans-bewust idempotent (catalogus-cadans van de metric):

        - REGULIER (daily/weekly/monthly of ongecatalogiseerd): hoogstens één datapunt per
          (role_id, metric, bron, datum) — ongewijzigd. `event_id` wordt genegeerd.
        - IRREGULIER (bv. werkoverleg — meerdere meetpunten per dag): ontdubbelt óók op `event_id`
          (de natuurlijke identiteit van het meetpunt). Meerdere meetpunten per dag bestaan zo naast
          elkaar, maar een herhaalde schrijf met hetzelfde event_id landt niet dubbel. FAIL-CLOSED:
          een irregulaire metric ZONDER event_id wordt geweigerd (geen stille terugval op dag-dedup).

        Geeft True als er geschreven is. `meta` legt bron-specifieke herkomst vast; voor irregulier
        wordt `meta["event_id"]` gezet zodat de dedup-index na een herstart identiek herbouwt.

        Schaal: de idempotentie-check loopt via de in-memory dedup-index (O(1))."""
        ts = ts if ts is not None else time.time()
        datum = datum or _utc_date(ts)
        self._ensure_cache()
        if cadence_of(metric, bron) == "irregular":
            if not event_id:
                log.warning("record_daily: irregulaire metric %r (bron=%r) zonder event_id — geweigerd "
                            "(geen stille dag-dedup-terugval)", metric, bron)
                return False
            meta = dict(meta or {})
            meta["event_id"] = str(event_id)     # zodat _index de sleutel na herstart identiek herbouwt
        if self._dedup_key(role_id, metric, bron, datum, event_id) in self._dedup:
            return False            # al een datapunt voor die dag(+event) → idempotent, O(1) via de index
        self.record(role_id, metric, value, ts=ts, bron=bron, datum=datum, meta=meta)
        return True

    def _read_all(self) -> list[dict]:
        """Alle rijen (ongefilterd) uit de in-memory index; het bestand wordt hoogstens één keer per
        instance gelezen. Geeft een KOPIE van de lijst terug, zodat een caller die sorteert of de lijst
        muteert de index niet corrumpeert (de rij-dicts zelf zijn gedeeld — in-place mutatie gebeurt alleen
        in de herschrijf-migraties, die daarna invalideren)."""
        self._ensure_cache()
        return list(self._rows)

    def series(self, role_id: str, metric: str) -> list[dict]:
        """Alle observaties voor role_id + metric, oplopend op ts."""
        rows = [r for r in self._read_all()
                if r.get("role_id") == role_id and r.get("metric") == metric]
        rows.sort(key=lambda r: r["ts"])
        return rows

    def latest(self, role_id: str, metric: str) -> dict | None:
        """Laatste observatie voor role_id + metric, of None."""
        rows = self.series(role_id, metric)
        return rows[-1] if rows else None

    def _actueel(self, metric: str, bron: str | None = None):
        """De laatste bekende dagwaarde voor een metric (bron), of None. Voor 'Actueel' op het
        dashboard: dezelfde betekenis als bij Plausible — de meest recente dag-observatie."""
        rows = self.daily_series(metric, bron=bron)
        return rows[-1]["value"] if rows else None

    def daily_series(self, metric: str, bron: str | None = None,
                     role_id: str | None = None) -> list[dict]:
        """De dagreeks van een metric (optioneel op bron en/of rol gefilterd), oplopend op ts.
        De één-per-dag-garantie komt van `record_daily`; hier wordt alleen gelezen. Site-brede
        metrics (bv. bezoekers) laat je role_id weg — dan telt de reeks over alle rollen."""
        self._ensure_cache()
        base = self._by_mb.get((metric, bron), []) if bron is not None \
            else [r for r in self._rows if r.get("metric") == metric]     # O(1) op metric+bron via de index
        rows = [r for r in base if role_id is None or r.get("role_id") == role_id]
        # Sorteer op MEETDAG (datum), niet op schrijf-ts: na een backfill (historische dagen allemaal op
        # één dag geschreven) wijkt ts-volgorde af van datum-volgorde. ts blijft tiebreak + audit.
        rows.sort(key=lambda r: (r.get("datum") or "", r.get("ts", 0)))
        return rows

    def dimensioned_series(self, base_metric: str, bron: str | None = None) -> dict:
        """Alle dimensie-reeksen `<base_metric>::<slug>` (scope 2), gegroepeerd op keyword. Sleutel = het
        rauwe keyword uit de meta (fallback: de slug); waarde = de dagreeks (oplopend op meetdag). LET OP:
        dit scant `_read_all()` met een prefix-filter — lineair; vóór een TWEEDE dimensie-bron is een
        index/dag-bucket vereist (zie record_daily)."""
        prefix = base_metric + "::"
        groups: dict[str, list] = {}
        for r in self._read_all():
            m = r.get("metric") or ""
            if not m.startswith(prefix) or (bron is not None and r.get("bron") != bron):
                continue
            meta = r.get("meta") or {}
            label = meta.get("value") or meta.get("keyword") or m[len(prefix):]  # generiek; keyword = scope-2-GSC
            groups.setdefault(label, []).append(r)
        for rows in groups.values():
            rows.sort(key=lambda r: (r.get("datum") or "", r.get("ts", 0)))
        return groups


# ── dag-observaties per bron (uitrol van de Plausible-aanpak, scope 2) ──────────
# Metric-namen: <bron>_<measure>_day. record_daily blijft idempotent op rol/metric/bron/dag.
WERK_DAILY = {"tevredenheid": "werk_tevredenheid_day", "duur": "werk_duur_day"}
SHOPIFY_DAILY = {m: f"shopify_{m}_day" for m in ("pairs_sold", "orders", "revenue", "aov")}


def record_werk_daily(store: "ObservationStore", circle: str, snap: dict) -> None:
    """Dagwaarden (tevredenheid + duur) van een gesloten werkoverleg → observatie-store. De metrics
    zijn IRREGULIER (meerdere overleggen per dag mogelijk), dus we geven een `event_id` mee = de
    natuurlijke identiteit van HET OVERLEG.

    Keuze event_id: `started_at` (wanneer het overleg begon) — één overleg heeft precies één start,
    het staat in de snapshot dus is stabiel bij een herstart, en het schuift niet mee zoals een
    positioneel log-index dat bij toekomstig trimmen/archiveren zou doen. Fallback op `at` (ended_at)
    voor snapshots van vóór deze wijziging (die geen started_at dragen; ook uniek per overleg)."""
    if not snap:
        return
    datum = _utc_date(snap.get("at") or time.time())
    ev = snap.get("started_at") or snap.get("at")
    event_id = str(int(ev)) if ev else ""
    if snap.get("tevredenheid") is not None:
        store.record_daily(circle, WERK_DAILY["tevredenheid"], snap["tevredenheid"],
                           bron="werkoverleg", datum=datum, event_id=event_id)
    if snap.get("duur_min") is not None:
        store.record_daily(circle, WERK_DAILY["duur"], snap["duur_min"],
                           bron="werkoverleg", datum=datum, event_id=event_id)

# NB: de Shopify-dagwaarden lopen nu via de generieke collector (DataSourceSkill.daily_values →
# record_daily onder shopify_<field>_day). SHOPIFY_DAILY blijft de sleutel-map voor de tegel-lezer.
