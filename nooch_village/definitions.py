"""Gedeelde indicator-definities — de 'metrics-database' die de Librarian cureert.

Een definitie is de grondslag van een indicator (wat telt mee, eenheid, richting, drempel,
meetmoment), losgekoppeld van een specifieke KPI zodat meerdere KPI's dezelfde definitie kunnen
delen. Eén bron, dus vergelijkbaarheid (GAAP/IRIS-idee). De Librarian cureert; anderen lezen vrij,
hetzelfde domein-eigenaarschap als bij het Lexicon en de Library.

Versionering (kern van het migratiebeleid):
- Een definitie wordt NOOIT in-place gewijzigd. `amend()` maakt een nieuwe versie.
- Elke versie legt vast hoe de overgang is gedaan (`migration`):
    'clarify'  = alleen de tekst is verduidelijkt; de reeks blijft één geheel (geen breuk).
    'backcast' = de historie is herrekend op de nieuwe grondslag; de reeks blijft vergelijkbaar.
    'break'    = reeksbreuk: de oude versie is bevroren, de nieuwe versie start vers.
- Samples in de MetricStore dragen de versie waaronder ze gemeten zijn (`defv`), zodat
  back-casten of een breuk tonen later altijd mogelijk is zonder data te verliezen.

Opslag: data/definitions.json. Pure datalaag; migratie-uitvoering en governance leven elders.
"""
from __future__ import annotations

import json
import os
import time
import uuid

from nooch_village.metric_schema import normalize as _norm
from nooch_village.util import atomic_write_json

MIGRATIONS = ("clarify", "backcast", "break")

# ── zaad-catalogus: wat we via onze koppelingen IN POTENTIE kunnen meten ───────
# Afgeleid uit de databron-skills (skills_impl/). Niet "wat we nu tonen", maar het volledige
# meetpotentieel per bron. Dit is meteen de toets op het indicator-schema: elke regel hieronder
# MOET valideren via metric_schema.normalize (zie tests). Velden: name, source, unit, direction,
# cadence, meettype, window?, definition.
_DEFINITION_SEED: tuple[dict, ...] = (
    # Google Search Console (zoekprestaties)
    {"name": "Vertoningen (GSC)", "source": "gsc", "unit": "n", "direction": "up",
     "cadence": "week", "meettype": "venster", "window": "28d",
     "definition": "Som van impressions van alle queries in het venster (Search Console)."},
    {"name": "Klikken (GSC)", "source": "gsc", "unit": "n", "direction": "up",
     "cadence": "week", "meettype": "venster", "window": "28d",
     "definition": "Som van clicks van alle queries in het venster (Search Console)."},
    {"name": "CTR (GSC)", "source": "gsc", "unit": "%", "direction": "up",
     "cadence": "week", "meettype": "venster", "window": "28d",
     "definition": "Klikken gedeeld door vertoningen over het venster."},
    {"name": "Gemiddelde positie (GSC)", "source": "gsc", "unit": "positie", "direction": "down",
     "cadence": "week", "meettype": "venster", "window": "28d",
     "definition": "Gemiddelde zoekpositie over alle queries (1 = best)."},
    {"name": "Aandeel op pagina 1 (GSC)", "source": "gsc", "unit": "%", "direction": "up",
     "cadence": "week", "meettype": "venster", "window": "28d",
     "definition": "Percentage queries met positie 1-10."},
    # Plausible (verkeer en betrokkenheid)
    {"name": "Bezoekers (Plausible)", "source": "plausible", "unit": "bezoekers", "direction": "up",
     "cadence": "dag", "meettype": "venster", "window": "30d",
     "definition": "Unieke bezoekers in het venster (Plausible)."},
    {"name": "Paginaweergaven (Plausible)", "source": "plausible", "unit": "n", "direction": "up",
     "cadence": "dag", "meettype": "venster", "window": "30d",
     "definition": "Totaal aantal paginaweergaven in het venster."},
    {"name": "Bezoekduur (Plausible)", "source": "plausible", "unit": "sec", "direction": "up",
     "cadence": "dag", "meettype": "venster", "window": "30d",
     "definition": "Gemiddelde duur van een bezoek in seconden."},
    {"name": "Bouncepercentage (Plausible)", "source": "plausible", "unit": "%", "direction": "down",
     "cadence": "dag", "meettype": "venster", "window": "30d",
     "definition": "Aandeel bezoeken met één paginaweergave."},
    # Shopify (verkoop en omzet)
    {"name": "Paren verkocht (Shopify)", "source": "shopify", "unit": "paar", "direction": "up",
     "cadence": "maand", "meettype": "cumulatief",
     "definition": "Aantal verkochte paren schoenen (som van line-items)."},
    {"name": "Orders (Shopify)", "source": "shopify", "unit": "n", "direction": "up",
     "cadence": "maand", "meettype": "cumulatief",
     "definition": "Aantal betaalde bestellingen."},
    {"name": "Omzet (Shopify)", "source": "shopify", "unit": "EUR", "direction": "up",
     "cadence": "maand", "meettype": "cumulatief",
     "definition": "Totale omzet uit betaalde bestellingen."},
    {"name": "Gemiddelde orderwaarde (Shopify)", "source": "shopify", "unit": "EUR", "direction": "up",
     "cadence": "maand", "meettype": "venster", "window": "30d",
     "definition": "Omzet gedeeld door aantal orders (AOV)."},
    {"name": "Conversieratio (Shopify×Plausible)", "source": "shopify", "unit": "%", "direction": "up",
     "cadence": "maand", "meettype": "venster", "window": "30d",
     "definition": "Orders gedeeld door bezoekers in dezelfde periode."},
    # Google Trends (interesse)
    {"name": "Zoekinteresse (Trends)", "source": "trends", "unit": "index", "direction": "up",
     "cadence": "week", "meettype": "snapshot",
     "definition": "Laatste interesse-index (0-100) voor de term in de geo."},
    # Keywords Everywhere (zoekvraag)
    {"name": "Zoekvolume (Keywords Everywhere)", "source": "keywords_everywhere", "unit": "n",
     "direction": "up", "cadence": "maand", "meettype": "snapshot",
     "definition": "Maandelijks zoekvolume voor de term in het land."},
    {"name": "CPC (Keywords Everywhere)", "source": "keywords_everywhere", "unit": "EUR",
     "direction": "", "cadence": "maand", "meettype": "snapshot",
     "definition": "Gemiddelde kosten per klik (advertentiewaarde van de term)."},
    {"name": "Concurrentie (Keywords Everywhere)", "source": "keywords_everywhere", "unit": "ratio",
     "direction": "", "cadence": "maand", "meettype": "snapshot",
     "definition": "Google Ads-concurrentie voor de term (0-1)."},
    # Ngram (cultureel taalgebruik over decennia)
    {"name": "Woordfrequentie (Ngram)", "source": "ngram", "unit": "frequentie", "direction": "up",
     "cadence": "jaar", "meettype": "snapshot",
     "definition": "Relatieve frequentie van het woord in het Books-corpus (laatste jaar)."},
    # Academisch bewijs
    {"name": "Academische werken (OpenAlex)", "source": "openalex", "unit": "n", "direction": "up",
     "cadence": "kwartaal", "meettype": "snapshot",
     "definition": "Aantal gevonden werken voor de term in OpenAlex."},
    {"name": "Gem. citaties (OpenAlex)", "source": "openalex", "unit": "n", "direction": "up",
     "cadence": "kwartaal", "meettype": "snapshot",
     "definition": "Gemiddeld aantal citaties van de top-resultaten."},
    {"name": "Papers (Semantic Scholar)", "source": "semantic_scholar", "unit": "n", "direction": "up",
     "cadence": "kwartaal", "meettype": "snapshot",
     "definition": "Aantal gevonden papers voor de term."},
    # Sitegezondheid
    {"name": "Beschikbaarheid (Site health)", "source": "site_health", "unit": "%", "direction": "up",
     "cadence": "uur", "meettype": "venster", "window": "30d",
     "definition": "Aandeel checks met HTTP 200 over het venster (uptime)."},
    # Concurrentie-monitoring
    {"name": "Nieuwsitems concurrenten", "source": "competitor_news", "unit": "n", "direction": "",
     "cadence": "week", "meettype": "venster", "window": "7d",
     "definition": "Aantal nieuwsartikelen over gevolgde merken in het venster."},
    # Linkbuilding
    {"name": "Hoge-prioriteit linkdoelen", "source": "linkbuilding", "unit": "n", "direction": "up",
     "cadence": "maand", "meettype": "snapshot",
     "definition": "Aantal gidsen met prioriteit 'hoog' om in genoemd te worden."},
    # Budget
    {"name": "Besteed budget", "source": "budget", "unit": "EUR", "direction": "down",
     "cadence": "maand", "meettype": "cumulatief",
     "definition": "Totaal besteed bedrag over alle budgetlijnen."},
)

# de velden die een versie van een definitie vastlegt (subset van het indicator-schema)
_FIELDS = ("name", "unit", "definition", "source", "direction",
           "threshold", "cadence", "meettype", "window")


class DefinitionStore:
    def __init__(self, path: str):
        self.path = path
        self._d: dict[str, dict] = {}
        if os.path.exists(path):
            try:
                x = json.load(open(path))
                if isinstance(x, dict):
                    self._d = x
            except Exception:
                self._d = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        atomic_write_json(self.path, self._d)

    # ── toevoegen (Librarian cureert) ──────────────────────────────────────────
    def add(self, name: str, owner: str = "", provenance: str = "seed", **grondslag) -> dict | None:
        # `provenance` = herkomst van de definitie (seed/sensed/...), los van het schema-veld
        # `source` (de databron als gsc/plausible/...), dat in **grondslag zit.
        spec = _norm(name=name, **grondslag)
        if spec is None:                       # ongeldig (lege naam)
            return None
        did = uuid.uuid4().hex[:12]
        v1 = {"version": 1, "at": time.time(), "migration": "", **spec}
        self._d[did] = {"id": did, "owner": owner, "current": 1,
                        "src": provenance, "versions": [v1], "created_at": time.time()}
        self._save()
        return self._d[did]

    # ── lezen ──────────────────────────────────────────────────────────────────
    def get(self, did: str) -> dict | None:
        return self._d.get(did)

    def all(self) -> list[dict]:
        return list(self._d.values())

    def current(self, did: str) -> dict | None:
        """De huidige versie-velden van een definitie (of None)."""
        d = self._d.get(did)
        if not d:
            return None
        return next((v for v in d["versions"] if v["version"] == d["current"]), None)

    def version(self, did: str, n: int) -> dict | None:
        d = self._d.get(did)
        if not d:
            return None
        return next((v for v in d["versions"] if v["version"] == n), None)

    def current_version_no(self, did: str) -> int:
        d = self._d.get(did)
        return d["current"] if d else 0

    # ── wijzigen = nieuwe versie (nooit in-place) ──────────────────────────────
    def amend(self, did: str, migration: str, **fields) -> dict | None:
        """Maak een nieuwe versie van een bestaande definitie.

        `migration` ∈ MIGRATIONS bepaalt hoe met de historie is omgegaan. Velden die niet
        worden meegegeven, erven van de huidige versie. Geeft de nieuwe versie terug, of None
        bij een onbekende definitie/migratie of een ongeldige grondslag."""
        d = self._d.get(did)
        if not d or migration not in MIGRATIONS:
            return None
        base = self.current(did) or {}
        merged = {k: base.get(k) for k in _FIELDS}
        merged.update({k: v for k, v in fields.items() if v is not None})
        spec = _norm(**merged)
        if spec is None:
            return None
        n = max(v["version"] for v in d["versions"]) + 1
        ver = {"version": n, "at": time.time(), "migration": migration, **spec}
        d["versions"].append(ver)
        d["current"] = n
        self._save()
        return ver

    # ── bestaande definitie vinden op (naam, bron) — voor dedup en hergebruik ──
    def find(self, name: str, source: str = "") -> dict | None:
        key = (name or "").strip().lower()
        for d in self._d.values():
            cur = self.current(d["id"]) or {}
            if cur.get("name", "").strip().lower() == key and cur.get("source", "") == source:
                return d
        return None


def seed_catalog(store: DefinitionStore, owner: str = "librarian") -> int:
    """Laad de zaad-catalogus idempotent in (dedup op naam+bron). Geeft het aantal toegevoegde
    definities terug. Tegelijk de praktijktoets op het schema: een ongeldige zaad-regel zou hier
    None opleveren en dus niet worden toegevoegd (de test dekt dit af)."""
    added = 0
    for entry in _DEFINITION_SEED:
        e = dict(entry)
        name, source = e.pop("name"), e.get("source", "")
        if store.find(name, source) is not None:
            continue
        if store.add(name, owner=owner, provenance="seed", **e):  # **e bevat source=gsc/plausible/...
            added += 1
    return added
