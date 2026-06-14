# NoochVille — State & Handover (2026-06-14)

## Waar we staan

- Code op ~10, 170 tests groen + schone supervised live run (tot stap 8).
- 4 review-fixes doorgevoerd: atomic writes + Noochie-rem (één voorstel, geen
  stroom), test-fundament (pytest), single-source missie/policy, village.py
  gesplitst + TriageEngine eruit + DRY.
- Keyword-lus gesloten: Librarian-escalaties landen als eigen type "keyword" in
  de inbox (approve → approved, reject → forbidden naar de bibliotheek, direct,
  deduped).
- Live burgers: GrowthAnalyst, Librarian, PerformanceScout, TimeKeeper,
  Facilitator, CircleLead, TijdgeestWachter, KennisScout, Noochie.
- **Observatie-store**: getimestampte tijdreeks per rol/metric (`data/observations.jsonl`,
  append-only). GrowthAnalyst logt pulsdata voor gemonitorde metrics.
- **Project-primitief + grootboek + projects-CLI**: ProjectLedger (atomic writes,
  mtime-reload voor cross-process zichtbaarheid), human-push trigger via CLI.
  Levenscyclus: `queued → running → blocked → running → done`.
- **Metric-discovery-lus end-to-end bewezen met gemockte trage delen** (Plausible,
  Trends, LLM): project → analyst ontdekt menukaart → Noochie adviseert →
  analyst zet monitoring → pulse logt. Gevalideerd in `tests/test_loop.py`
  (echte threads, 20s timeout). Echte supervised live run nog te doen.
- **MonitoringStore**: per-rol lijst van te monitoren metrics (`data/role_metrics.json`,
  dedup + gesorteerd). Gevuld door `_on_advice_ready` na Noochie-advies.
- **TimeKeeper**: `maand_begint` / `kwartaal_begint` toegevoegd aan
  `cadence_events` (dag 1 van maand resp. kwartaal).
- **Dom WIP-plafond op het grootboek**: ⚠ niet gecommit — open item.
- **Structurele fix — once-per-pulse-discipline + `_busy`-drop**: `react()` heeft
  `drop_if_busy=True`; een `dag_begint` tijdens een lopende puls wordt bij
  enqueue direct weggegooid (niet gequeued). `_setup_events()`-hook laat
  GrowthAnalyst/PerformanceScout/TijdgeestWachter hun eigen pulsgate definiëren.
  Inbox-flooding opgelost.
- **Blauwdruk `docs/ONTWERP_projecten_metrics.md`**: aangemaakt en gecommit.
- **Sensing-herbouw stap 1 — dedup van staande condities**: `_sense_gap` slaat
  bij eerste emit `acc_text` + `emitted=True` op in reflect-state. Volgende
  aanroepen zwijgen zodra de accountability in het rol-DNA staat of als open
  inbox-item gevonden wordt. `force` omzeilt min_count maar respecteert dedup.
  4 thread-vrije tests in `tests/test_sense_gap.py`, 163 tests groen.
- **Sensing-herbouw stap 2 — means-gap routing naar inbox**: structurele capaciteits-
  grenzen gaan NIET meer via de governance-gate (`amend_role`). Nieuw pad:
  `_report_means_gap` → `means_gap_sensed`-event → `Village._on_means_gap` →
  `HumanInbox.add_means_gap` (dedup op `gap_key`, permanent, ongeacht status).
  Resultaat: `openlibrary_v2`, `ngram_2019_cutoff`, `nl_corpus_coverage` landen
  elk exact één keer als means_gap-item in de inbox; `semscholar_no_key` zwijgt.
  Geen `amend_role`-churn meer. Live bewijs: 4 supervised pulsen vlakke tellers
  (38/34/42/38 onveranderd), `python -m nooch_village.inbox list` toont 3 items,
  `amend_role` = 0 in system_log. 170 tests groen (`tests/test_means_gap.py`).

## Principes die niet mogen driften

- **Spine blijft dom**: gate G0-G4, prioriteit Missie > Policy > Strategy > Goal,
  provenance, fail-closed. LLM alleen bij fuzzy oordelen, fail-closed.
- **Born vs activated**: rollen geboren onbemand in de records; code/API-activatie
  altijd mens-gated + per-edit review. De diff zien telt vooral bij activatie en
  gate/missie-code, niet bij kleine operationele plumbing.
- **Inbox = zeldzaam en zwaar** (governance-escalaties, activaties). Laag-volume
  houden. Keyword-beslissingen zijn een apart, licht, omkeerbaar type, gate niet
  nodig.
- **Missie = Anchor-purpose, mens-eigendom.** Noochie is steward/stem, geen
  missie-beslisser. Publieke Noochie = los later product, twee-Noochie firewall.
- **Circle blijft Inhabitant erven** (niet "fixen" met compositie). Geen
  DI-container, geen plugin-autodiscovery, EventBus/models.py niet splitsen.
- **Patroon**: AI stelt plausibel-maar-soms-fout voor (bronnen, API's, capabilities).
  De mens/gate fit-check is de feature, niet een gebrek.

## Volgende stappen

1. **Echte supervised live run met sleutels**: sluitstuk van de lus. Plausible +
   Google Trends + LLM écht aanroepen, one-shot controleren, dan vrijgeven.
2. **Sensing herbouwen stap 2**: event-driven sensing (in plaats van polling in
   `_maybe_reflect`). Staande-conditie dedup (stap 1) is klaar.
3. **Slimme WIP** (prioriteit-eviction, backpressure) + **synthesizer-rol** die
   open spanningen batcht en de hefboom kiest.
4. Cockpit aan live data hangen (records/inbox/proces), met de auth-grens erin.
5. CI: pytest bij elke commit.
6. `openlibrary_v2`-activatie NIET reflexief goedkeuren: API is per-boek, niet
   corpus-breed. Laat onbemand tot er een echte per-boek use case is.
