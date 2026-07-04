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
from nooch_village.util import atomic_write_json, read_json

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
    {"name": "Conversie (orders ÷ unieke bezoekers)", "source": "shopify", "unit": "%", "direction": "up",
     "cadence": "maand", "meettype": "venster", "window": "30d",
     "definition": "Shopify-orders gedeeld door unieke bezoekers (Plausible) in dezelfde periode. "
                   "LET OP: niet gelijk aan Shopify's eigen conversie, die sessie-gebaseerd is "
                   "(orders ÷ sessies); sessies > unieke bezoekers, dus dit getal valt hoger uit."},
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
    # Werkoverleg / facilitator (gezondheid van de tactical meetings) — intern gemeten,
    # geen externe API. Per overleg vastgelegd; de facilitator rapporteert maandelijks.
    {"name": "Tevredenheid werkoverleg", "source": "werkoverleg", "unit": "0-10", "direction": "up",
     "cadence": "week", "meettype": "snapshot",
     "definition": "Gemiddelde check-out-score (0-10) van de aanwezigen per overleg."},
    {"name": "Behandelde spanningen", "source": "werkoverleg", "unit": "n", "direction": "",
     "cadence": "week", "meettype": "snapshot",
     "definition": "Aantal in de agenda behandelde spanningen per overleg."},
    {"name": "Info-uitkomsten", "source": "werkoverleg", "unit": "n", "direction": "",
     "cadence": "week", "meettype": "snapshot",
     "definition": "Aantal spanningen dat als 'informatie delen' is afgehandeld."},
    {"name": "Projecten uit overleg", "source": "werkoverleg", "unit": "n", "direction": "",
     "cadence": "week", "meettype": "snapshot",
     "definition": "Aantal spanningen dat tot een nieuw project leidde."},
    {"name": "Acties uit overleg", "source": "werkoverleg", "unit": "n", "direction": "",
     "cadence": "week", "meettype": "snapshot",
     "definition": "Aantal spanningen dat tot een losse of gekoppelde actie leidde."},
    {"name": "Doorlooptijd werkoverleg", "source": "werkoverleg", "unit": "min", "direction": "down",
     "cadence": "week", "meettype": "snapshot",
     "definition": "Duur van het overleg in minuten (korter bij gelijke output is efficiënter)."},

    # ── Cross-domein (nog geen API; handmatig of toekomstige koppeling) ─────────
    # Supply chain (ERP / voorraadsysteem)
    {"name": "Leverbetrouwbaarheid", "source": "erp", "unit": "%", "direction": "up",
     "cadence": "maand", "meettype": "venster", "window": "30d",
     "definition": "Aandeel orders geleverd op of vóór de beloofde datum (on-time delivery)."},
    {"name": "Voorraadrotatie", "source": "erp", "unit": "ratio", "direction": "up",
     "cadence": "kwartaal", "meettype": "venster", "window": "90d",
     "definition": "Kostprijs verkochte goederen gedeeld door de gemiddelde voorraadwaarde."},
    {"name": "Gem. doorlooptijd order", "source": "erp", "unit": "dagen", "direction": "down",
     "cadence": "maand", "meettype": "venster", "window": "30d",
     "definition": "Gemiddelde tijd van bestelling tot levering."},
    {"name": "Voorraadwaarde", "source": "erp", "unit": "EUR", "direction": "",
     "cadence": "maand", "meettype": "snapshot",
     "definition": "Waarde van de voorraad op het meetmoment."},
    # Inkoop (ERP)
    {"name": "Inkoopuitgaven", "source": "erp", "unit": "EUR", "direction": "down",
     "cadence": "maand", "meettype": "cumulatief",
     "definition": "Totaal besteed aan inkoop in de periode."},
    {"name": "Leveranciers op tijd", "source": "erp", "unit": "%", "direction": "up",
     "cadence": "maand", "meettype": "venster", "window": "30d",
     "definition": "Aandeel inkooporders dat leveranciers op tijd leverden."},
    {"name": "Afkeurpercentage inkoop", "source": "erp", "unit": "%", "direction": "down",
     "cadence": "maand", "meettype": "venster", "window": "30d",
     "definition": "Aandeel afgekeurde inkomende goederen."},
    {"name": "Actieve leveranciers", "source": "erp", "unit": "n", "direction": "",
     "cadence": "kwartaal", "meettype": "snapshot",
     "definition": "Aantal leveranciers met inkoop in de periode."},
    # IT (monitoring)
    # IT — gegrond tegen DORA (Accelerate State of DevOps 2024). Twee velocity- + twee stability-metrics.
    {"name": "Deploy-frequentie", "source": "monitoring", "unit": "deploys", "direction": "up",
     "cadence": "week", "meettype": "venster", "window": "7d", "tijd": "leading", "bruikbaar": "actionable",
     "standaard": "DORA (State of DevOps 2024)", "benchmark": "elite: on-demand (meerdere/dag); laag: <1/maand",
     "definition": "Hoe vaak succesvol naar productie wordt uitgeleverd (DORA velocity)."},
    {"name": "Lead time for changes", "source": "monitoring", "unit": "uur", "direction": "down",
     "cadence": "maand", "meettype": "venster", "window": "30d", "tijd": "lagging", "bruikbaar": "actionable",
     "standaard": "DORA (State of DevOps 2024)", "benchmark": "elite: < 1 dag",
     "definition": "Tijd van commit tot in productie (DORA velocity)."},
    {"name": "Wijzigingsfaalpercentage", "source": "monitoring", "unit": "%", "direction": "down",
     "cadence": "maand", "meettype": "venster", "window": "30d", "tijd": "lagging", "bruikbaar": "actionable",
     "standaard": "DORA (State of DevOps 2024)", "benchmark": "elite ~5%, high ~20%, laag ~40%",
     "definition": "Aandeel deploys dat een incident in productie veroorzaakt (DORA stability)."},
    {"name": "Hersteltijd na falen", "source": "monitoring", "unit": "uur", "direction": "down",
     "cadence": "maand", "meettype": "venster", "window": "30d", "tijd": "lagging", "bruikbaar": "actionable",
     "standaard": "DORA (State of DevOps 2024)", "benchmark": "elite: < 1 uur",
     "definition": "Tijd om de dienst te herstellen na een mislukte deploy (DORA; voorheen MTTR)."},
    {"name": "IT-incidenten", "source": "monitoring", "unit": "n", "direction": "down",
     "cadence": "maand", "meettype": "venster", "window": "30d", "tijd": "lagging", "bruikbaar": "actionable",
     "standaard": "operationeel (ITIL); geen DORA-kernmetric",
     "definition": "Aantal IT-incidenten in de periode."},
    # Klanttevredenheid (enquête + klantenservice)
    {"name": "NPS", "source": "survey", "unit": "NPS", "direction": "up",
     "cadence": "kwartaal", "meettype": "snapshot",
     "definition": "Net Promoter Score: % promoters min % detractors (enquête, -100..100)."},
    {"name": "CSAT", "source": "survey", "unit": "%", "direction": "up",
     "cadence": "maand", "meettype": "snapshot",
     "definition": "Aandeel klanten dat (zeer) tevreden scoort in de enquête."},
    {"name": "Eerste reactietijd", "source": "support", "unit": "uur", "direction": "down",
     "cadence": "week", "meettype": "venster", "window": "7d",
     "definition": "Gemiddelde tijd tot de eerste reactie op een klantvraag."},
    {"name": "Oplostijd klantvraag", "source": "support", "unit": "uur", "direction": "down",
     "cadence": "week", "meettype": "venster", "window": "7d",
     "definition": "Gemiddelde tijd tot een klantvraag is opgelost."},
    {"name": "Retourpercentage", "source": "erp", "unit": "%", "direction": "down",
     "cadence": "maand", "meettype": "venster", "window": "30d",
     "definition": "Aandeel verkochte paren dat retour komt."},
    # Medewerkerstevredenheid (enquête + HR-systeem)
    {"name": "eNPS", "source": "survey", "unit": "NPS", "direction": "up",
     "cadence": "kwartaal", "meettype": "snapshot",
     "definition": "Employee Net Promoter Score (enquête, -100..100)."},
    {"name": "Medewerkerstevredenheid", "source": "survey", "unit": "0-10", "direction": "up",
     "cadence": "kwartaal", "meettype": "snapshot",
     "definition": "Gemiddelde tevredenheidsscore uit de medewerkersenquête."},
    {"name": "Personeelsverloop", "source": "hris", "unit": "%", "direction": "down",
     "cadence": "jaar", "meettype": "venster", "window": "365d",
     "definition": "Aandeel medewerkers dat per jaar vertrekt."},
    {"name": "Ziekteverzuim", "source": "hris", "unit": "%", "direction": "down",
     "cadence": "maand", "meettype": "venster", "window": "30d",
     "definition": "Aandeel verzuimde werkdagen in de periode."},
    # Maatschappelijke impact (LCA / impact-audit)
    {"name": "CO2 per paar", "source": "impact", "unit": "kg CO2e", "direction": "down",
     "cadence": "kwartaal", "meettype": "snapshot",
     "definition": "Levenscyclus-emissies per paar schoenen (LCA-onderbouwing vereist)."},
    {"name": "Aandeel gerecycled materiaal", "source": "impact", "unit": "%", "direction": "up",
     "cadence": "kwartaal", "meettype": "snapshot",
     "definition": "Massa-aandeel gerecycled materiaal in het product."},
    {"name": "Aandeel biobased materiaal", "source": "impact", "unit": "%", "direction": "up",
     "cadence": "kwartaal", "meettype": "snapshot",
     "definition": "Massa-aandeel biobased of circulair materiaal in het product."},
    {"name": "Donaties goede doelen", "source": "impact", "unit": "EUR", "direction": "up",
     "cadence": "jaar", "meettype": "cumulatief",
     "definition": "Bedrag gedoneerd of teruggegeven aan goede doelen (bijv. TRAID)."},
    # Financiën (boekhouding)
    {"name": "Brutomarge", "source": "finance", "unit": "%", "direction": "up",
     "cadence": "maand", "meettype": "venster", "window": "30d",
     "definition": "Brutowinst gedeeld door omzet."},
    {"name": "Cashpositie", "source": "finance", "unit": "EUR", "direction": "up",
     "cadence": "maand", "meettype": "snapshot",
     "definition": "Beschikbare liquide middelen op het meetmoment."},
    {"name": "Runway", "source": "finance", "unit": "maanden", "direction": "up",
     "cadence": "maand", "meettype": "snapshot",
     "definition": "Maanden tot het geld op is bij de huidige burn rate."},
)

# de velden die een versie van een definitie vastlegt (subset van het indicator-schema)
_FIELDS = ("name", "unit", "definition", "source", "direction", "threshold", "cadence",
           "meettype", "window", "meetwijze", "tijd", "bruikbaar", "standaard", "benchmark",
           "bron_url", "verificatie", "waarde", "aard", "aggregatie", "formule",
           "categorie", "veld")


class DefinitionStore:
    def __init__(self, path: str):
        self.path = path
        self._d: dict[str, dict] = read_json(path, {})

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

    def by_name(self, name: str) -> dict | None:
        """Eerste definitie met deze huidige naam (bron-onafhankelijk) — voor 'knows exactly'-zoek."""
        key = (name or "").strip().lower()
        for d in self._d.values():
            if (self.current(d["id"]) or {}).get("name", "").strip().lower() == key:
                return d
        return None


_MEASURABLE = ("unit", "direction", "threshold", "cadence", "meettype", "window", "source")


def suggest_migration(old: dict, new: dict) -> tuple[str, str]:
    """Stel de migratie voor bij een definitiewijziging (heuristiek; de LLM/mens kan overrulen).

    - Alleen de definitietekst gewijzigd → 'clarify' (zelfde meting, reeks blijft heel).
    - Een meetbaar veld gewijzigd (eenheid/richting/drempel/cadans/meettype/venster/bron) → 'break'
      als veilige default; de mens kan dit naar 'backcast' zetten als hij stelt dat de historie
      vergelijkbaar blijft (eventueel met LLM-advies)."""
    changed = [f for f in _MEASURABLE if f in new and str(old.get(f) or "") != str(new.get(f) or "")]
    if changed:
        return "break", "meetbare grondslag gewijzigd (" + ", ".join(changed) + ")"
    if "definition" in new and (old.get("definition") or "") != (new.get("definition") or ""):
        return "clarify", "alleen de definitietekst is verduidelijkt"
    return "clarify", "geen meetbare wijziging"


def seed_catalog(store: DefinitionStore, owner: str = "librarian") -> int:
    """Laad de zaad-catalogus idempotent in (dedup op naam+bron). Geeft het aantal toegevoegde
    definities terug. Tegelijk de praktijktoets op het schema: een ongeldige zaad-regel zou hier
    None opleveren en dus niet worden toegevoegd (de test dekt dit af)."""
# Gronding-overlay: per definitie de erkende bron (standaard), leading/lagging (tijd),
# actionable/vanity (bruikbaar) en een benchmark waar een verdedigbaar cijfer bestaat.
# Bronnen: DORA, Bain/Reichheld (NPS), ACSI (CSAT), SCOR/ASCM (OTIF), GHG Protocol + IRIS+,
# ECDB/Smart Insights (e-commerce 2024), Holacracy (tactical meeting). IT staat al inline.
_GROUNDING: dict[str, dict] = {
    # Marketing / zoekprestaties (Google Search Console)
    "Vertoningen (GSC)": {"standaard": "Google Search Console", "tijd": "lagging", "bruikbaar": "vanity"},
    "Klikken (GSC)": {"standaard": "Google Search Console", "tijd": "lagging", "bruikbaar": "actionable"},
    "CTR (GSC)": {"standaard": "Google Search Console", "tijd": "lagging", "bruikbaar": "actionable"},
    "Gemiddelde positie (GSC)": {"standaard": "Google Search Console", "tijd": "lagging", "bruikbaar": "actionable"},
    "Aandeel op pagina 1 (GSC)": {"standaard": "afgeleide (GSC posities 1-10)", "tijd": "lagging", "bruikbaar": "actionable"},
    # Web-analytics (Plausible)
    "Bezoekers (Plausible)": {"standaard": "Plausible (web-analytics)", "tijd": "lagging", "bruikbaar": "vanity"},
    "Paginaweergaven (Plausible)": {"standaard": "Plausible (web-analytics)", "tijd": "lagging", "bruikbaar": "vanity"},
    "Bezoekduur (Plausible)": {"standaard": "Plausible (web-analytics)", "tijd": "lagging", "bruikbaar": "actionable"},
    "Bouncepercentage (Plausible)": {"standaard": "Plausible (web-analytics)", "tijd": "lagging", "bruikbaar": "actionable", "benchmark": "e-commerce gem. ~60% (2024)"},
    # Verkoop (e-commerce standaard)
    "Paren verkocht (Shopify)": {"standaard": "e-commerce standaard", "tijd": "lagging", "bruikbaar": "actionable"},
    "Orders (Shopify)": {"standaard": "e-commerce standaard", "tijd": "lagging", "bruikbaar": "actionable"},
    "Omzet (Shopify)": {"standaard": "e-commerce standaard", "tijd": "lagging", "bruikbaar": "actionable"},
    "Gemiddelde orderwaarde (Shopify)": {"standaard": "e-commerce standaard (AOV)", "tijd": "lagging", "bruikbaar": "actionable", "benchmark": "wereldwijd ~€110 (2024)"},
    "Conversie (orders ÷ unieke bezoekers)": {"standaard": "e-commerce standaard (definitie-afwijking)", "tijd": "lagging", "bruikbaar": "actionable", "benchmark": "e-commerce ~2,7% (2024); noemer hier = unieke bezoekers, niet sessies"},
    # Zoekvraag / cultuur / onderzoek (vraagsignalen, meestal leading)
    "Zoekinteresse (Trends)": {"standaard": "Google Trends (zoekindex 0-100)", "tijd": "leading", "bruikbaar": "actionable"},
    "Zoekvolume (Keywords Everywhere)": {"standaard": "Keywords Everywhere (Google Ads-data)", "tijd": "leading", "bruikbaar": "actionable"},
    "CPC (Keywords Everywhere)": {"standaard": "Keywords Everywhere (Google Ads-data)", "tijd": "leading", "bruikbaar": "vanity"},
    "Concurrentie (Keywords Everywhere)": {"standaard": "Keywords Everywhere (Google Ads-data)", "tijd": "leading", "bruikbaar": "vanity"},
    "Woordfrequentie (Ngram)": {"standaard": "Google Books Ngram", "tijd": "leading", "bruikbaar": "vanity"},
    "Academische werken (OpenAlex)": {"standaard": "OpenAlex (academische index)", "tijd": "leading", "bruikbaar": "vanity"},
    "Gem. citaties (OpenAlex)": {"standaard": "OpenAlex (academische index)", "tijd": "lagging", "bruikbaar": "vanity"},
    "Papers (Semantic Scholar)": {"standaard": "Semantic Scholar (academische index)", "tijd": "leading", "bruikbaar": "vanity"},
    "Nieuwsitems concurrenten": {"standaard": "intern (nieuws-monitor)", "tijd": "leading", "bruikbaar": "vanity"},
    "Hoge-prioriteit linkdoelen": {"standaard": "intern (SEO-prioritering)", "tijd": "leading", "bruikbaar": "actionable"},
    # IT-infra
    "Beschikbaarheid (Site health)": {"standaard": "SRE / SLO (uptime)", "tijd": "lagging", "bruikbaar": "actionable", "benchmark": "SLO vaak 99,9%"},
    # Supply chain / inkoop (SCOR / ASCM)
    "Leverbetrouwbaarheid": {"standaard": "SCOR / OTIF (ASCM)", "tijd": "lagging", "bruikbaar": "actionable", "benchmark": "goed: 95-99% (OTIF)"},
    "Voorraadrotatie": {"standaard": "SCOR (asset management, ASCM)", "tijd": "lagging", "bruikbaar": "actionable"},
    "Gem. doorlooptijd order": {"standaard": "SCOR (order fulfillment cycle time)", "tijd": "lagging", "bruikbaar": "actionable"},
    "Voorraadwaarde": {"standaard": "boekhouding / ERP", "tijd": "lagging", "bruikbaar": "vanity"},
    "Inkoopuitgaven": {"standaard": "intern (inkoop)", "tijd": "lagging", "bruikbaar": "actionable"},
    "Leveranciers op tijd": {"standaard": "SCOR / OTIF (leverancier)", "tijd": "lagging", "bruikbaar": "actionable", "benchmark": "goed: 95-99%"},
    "Afkeurpercentage inkoop": {"standaard": "kwaliteit (incoming quality)", "tijd": "lagging", "bruikbaar": "actionable"},
    "Actieve leveranciers": {"standaard": "intern (inkoop)", "tijd": "lagging", "bruikbaar": "vanity"},
    "Retourpercentage": {"standaard": "e-commerce standaard", "tijd": "lagging", "bruikbaar": "actionable"},
    # Klantenservice (SLA)
    "Eerste reactietijd": {"standaard": "SLA (klantenservice)", "tijd": "lagging", "bruikbaar": "actionable"},
    "Oplostijd klantvraag": {"standaard": "SLA (klantenservice)", "tijd": "lagging", "bruikbaar": "actionable"},
    # Klant- en medewerkerstevredenheid (Bain / ACSI / afgeleid)
    "NPS": {"standaard": "NPS (Reichheld, Bain)", "tijd": "leading", "bruikbaar": "actionable", "benchmark": "B2C gem. ~49 (varieert per sector)"},
    "CSAT": {"standaard": "CSAT (ACSI / industrie)", "tijd": "lagging", "bruikbaar": "actionable", "benchmark": "goed 75-85%, top 90%+"},
    "eNPS": {"standaard": "eNPS (afgeleid van NPS)", "tijd": "leading", "bruikbaar": "actionable", "benchmark": "mediaan 0-30, top 30-50"},
    "Medewerkerstevredenheid": {"standaard": "medewerkersenquête (intern)", "tijd": "lagging", "bruikbaar": "actionable"},
    "Personeelsverloop": {"standaard": "HR-standaard (turnover)", "tijd": "lagging", "bruikbaar": "actionable"},
    "Ziekteverzuim": {"standaard": "HR-standaard (verzuim)", "tijd": "lagging", "bruikbaar": "actionable"},
    # Maatschappelijke impact (GHG Protocol / IRIS+)
    "CO2 per paar": {"standaard": "ISO 14067 (2030calculator) / GHG Protocol / IRIS+ PD9427",
                     "tijd": "lagging", "bruikbaar": "actionable",
                     "benchmark": "conventioneel ~13,6 kg → −65% (voorlopig, herrekenen)",
                     "bron_url": "/carbon-footprint-of-shoes", "verificatie": "voorlopig", "waarde": 4.75},
    "Aandeel gerecycled materiaal": {"standaard": "IRIS+ (circulair)", "tijd": "lagging", "bruikbaar": "actionable"},
    "Aandeel biobased materiaal": {"standaard": "intern (circulair)", "tijd": "lagging", "bruikbaar": "actionable"},
    "Donaties goede doelen": {"standaard": "intern (impact)", "tijd": "lagging", "bruikbaar": "vanity"},
    # Financiën
    "Brutomarge": {"standaard": "boekhouding (GAAP)", "tijd": "lagging", "bruikbaar": "actionable"},
    "Cashpositie": {"standaard": "boekhouding", "tijd": "lagging", "bruikbaar": "actionable"},
    "Runway": {"standaard": "startup-finance (cash ÷ burn)", "tijd": "leading", "bruikbaar": "actionable"},
    # Werkoverleg (Holacracy tactical meeting)
    "Tevredenheid werkoverleg": {"standaard": "Holacracy (tactical meeting)", "tijd": "lagging", "bruikbaar": "actionable"},
    "Behandelde spanningen": {"standaard": "Holacracy (tactical meeting)", "tijd": "lagging", "bruikbaar": "vanity"},
    "Info-uitkomsten": {"standaard": "Holacracy (tactical meeting)", "tijd": "lagging", "bruikbaar": "vanity"},
    "Projecten uit overleg": {"standaard": "Holacracy (tactical meeting)", "tijd": "lagging", "bruikbaar": "vanity"},
    "Acties uit overleg": {"standaard": "Holacracy (tactical meeting)", "tijd": "lagging", "bruikbaar": "vanity"},
    "Doorlooptijd werkoverleg": {"standaard": "Holacracy (tactical meeting)", "tijd": "lagging", "bruikbaar": "actionable"},
    "Besteed budget": {"standaard": "intern (boekhouding)", "tijd": "lagging", "bruikbaar": "actionable"},
}


def _merge_grounding(entry: dict) -> dict:
    """Voeg de gronding-overlay (standaard/tijd/bruikbaar/benchmark) toe aan een zaad-entry."""
    e = dict(entry)
    e.update(_GROUNDING.get(e.get("name", ""), {}))
    return e


# standaard meetwijze per bron (de Librarian kan dit per definitie overschrijven)
_SOURCE_MEETWIJZE = {"survey": "enquete", "impact": "handmatig", "": "handmatig"}


def _meetwijze_for(source: str) -> str:
    # alles wat uit een systeem/API/berekening komt = 'systeem'; enquête en impact afwijkend
    return _SOURCE_MEETWIJZE.get(source, "systeem")


def seed_catalog(store: DefinitionStore, owner: str = "librarian") -> int:
    added = 0
    for entry in _DEFINITION_SEED:
        e = _merge_grounding(entry)
        name, source = e.pop("name"), e.get("source", "")
        if store.find(name, source) is not None:
            continue
        e.setdefault("meetwijze", _meetwijze_for(source))
        e.setdefault("standaard", "interne aanname")   # eerlijk: nog niet gegrond tegen een erkende bron
        if store.add(name, owner=owner, provenance="seed", **e):  # **e bevat source=gsc/plausible/...
            added += 1
    return added


_GROUND_FIELDS = ("definition", "unit", "direction", "cadence", "meettype", "window",
                  "tijd", "bruikbaar", "standaard", "benchmark", "bron_url", "verificatie", "waarde")


# Ruwe skill-veldsleutel per zaad-definitie (op naam) — koppelt bestaande catalogus-items aan het
# ruwe bron-veld (available_metrics), zodat het koppelscherm ze niet als 'ongekoppeld' toont.
_SEED_VELD = {
    "Bezoekers (Plausible)": "visitors", "Paginaweergaven (Plausible)": "pageviews",
    "Bezoekduur (Plausible)": "visit_duration",
    "Paren verkocht (Shopify)": "pairs_sold", "Orders (Shopify)": "orders",
    "Omzet (Shopify)": "revenue", "Gemiddelde orderwaarde (Shopify)": "aov",
    "Vertoningen (GSC)": "impressions", "Klikken (GSC)": "clicks",
    "CTR (GSC)": "ctr", "Gemiddelde positie (GSC)": "position",
}

# Groepering per bron — vult de categorie op bestaande definities zodat de KPI-wizard categorie-eerst
# kan groeperen. Idempotent via migrate_definitions (alleen waar categorie leeg is).
_SOURCE_CATEGORIE = {
    "plausible": "Website", "shopify": "Verkoop", "gsc": "Zoekprestaties",
    "werkoverleg": "Werkoverleg", "finance": "Financieel", "budget": "Financieel",
    "erp": "Supply chain", "impact": "Impact",
    "survey": "Team & klant", "hris": "Team & klant", "support": "Team & klant",
    "monitoring": "IT", "site_health": "IT",
    "trends": "Onderzoek", "keywords_everywhere": "Onderzoek", "ngram": "Onderzoek",
    "openalex": "Onderzoek", "semantic_scholar": "Onderzoek",
    "competitor_news": "Marketing", "linkbuilding": "Marketing",
}


def migrate_definitions(store: DefinitionStore) -> int:
    """Retroactief de nieuwe verplichte/koppel-velden vullen op bestaande definities. Zelfde patroon
    als `migrate_records` voor `source`: idempotent en in-place, vult alleen ONTBREKENDE velden.

    - `aard` wordt afgeleid uit `meettype` waar het ontbreekt (snapshot → moment, anders → reeks);
    - `aggregatie`/`formule` krijgen hun lege default;
    - `categorie` wordt gezet uit `_SOURCE_CATEGORIE` (op bron) waar het leeg is, zodat de KPI-wizard
      categorie-eerst kan groeperen;
    - `veld` wordt gezet uit `_SEED_VELD` (op naam) waar het ontbreekt, zodat het koppelscherm de
      al-gekoppelde bron-velden herkent.

    Draait over álle versies zodat elke versie zelf-beschrijvend blijft. Geeft het aantal
    aangeraakte definities terug."""
    from nooch_village.metric_schema import AARD, aard_from_meettype
    changed = 0
    for d in store.all():
        dirty = False
        for v in d.get("versions", []):
            if v.get("aard") not in AARD:
                v["aard"] = aard_from_meettype(v.get("meettype", "snapshot"))
                dirty = True
            if "aggregatie" not in v:
                v["aggregatie"] = ""
                dirty = True
            if "formule" not in v:
                v["formule"] = False
                dirty = True
            mapped_cat = _SOURCE_CATEGORIE.get(v.get("source", ""), "")
            if "categorie" not in v:
                v["categorie"] = mapped_cat
                dirty = True
            elif mapped_cat and not v.get("categorie"):
                v["categorie"] = mapped_cat
                dirty = True
            mapped = _SEED_VELD.get(v.get("name", ""), "")
            if "veld" not in v:
                v["veld"] = mapped
                dirty = True
            elif mapped and not v.get("veld"):
                v["veld"] = mapped
                dirty = True
        if dirty:
            changed += 1
    if changed:
        store._save()
    return changed


def reground_seed(store: DefinitionStore) -> int:
    """Werk bestaande definities bij die in de seed inmiddels een echte grondslag hebben gekregen
    (standaard != 'interne aanname'), maar in de opslag nog ongegrond staan. Idempotent: doet niets
    zodra de opgeslagen grondslag al gelijk is. Bewaart historie als nieuwe versie (clarify)."""
    n = 0
    for entry in _DEFINITION_SEED:
        m = _merge_grounding(entry)
        std = m.get("standaard", "")
        if std in ("", "interne aanname"):
            continue
        d = store.find(m["name"], m.get("source", ""))
        if d is None:
            continue
        cur = store.current(d["id"]) or {}
        if cur.get("standaard", "") == std:        # al gegrond → niets doen
            continue
        fields = {k: m[k] for k in _GROUND_FIELDS if k in m}
        if store.amend(d["id"], "clarify", **fields):
            n += 1
    return n
