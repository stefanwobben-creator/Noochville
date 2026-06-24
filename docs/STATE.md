# NoochVille — State & Handover (2026-06-24)

> STATE = huidige waarheid, vervang bij update. `docs/JOURNAL.md` = historie, append-only.

## Waar we staan (2026-06-24)

**Suite: 874 tests groen** (gegroeid van ~688 in de latere sessie van 24/6). Elke stap met mutatie-check.

### Latere sessie 2026-06-24: cockpit-verwerking, LLM-ladder, markt- & linkbuilding-radar

- **Getrapte LLM-ladder** (`llm.py`): `reason()` loopt een ladder af van goedkoop naar duur —
  `gemini:flash-lite → mistral → gemini:flash → anthropic:haiku`. Rate-limit/quota op een trede →
  cooldown-skip (`LLM_TIER_COOLDOWN_S`, default 30m) + door naar de volgende. Fail-closed.
  Instelbaar via `LLM_LADDER`. Killt het oude Sonnet-kostenlek (defaults nu goedkoop). Plus een
  per-minuut throttle (`RateLimiter`/`LIMITER`). Bewezen in de praktijk: ving Gemini's gratis dagcap
  (20/dag) op zonder dat de puls vastliep.
- **Opstart-sleutelrapport** (niet-blokkerend) + CLI `keys`: skills declareren zelf
  `required_env`/`optional_env`; het dorp toont bij elke run welke LLM-treden en skills "scherp"
  staan. Presence-only (geen sleutelwaarden).
- **Cockpit als verwerk-oppervlak** (`cockpit.py`, localhost + CSRF): inbox-acties, project-status,
  kennis-graaf, en nieuw — de **escalated-woordenschat afroombaar** (`override_library_term`),
  **Concurrenten** (bevestig/negeer) en **Linkbuilding** (pitchen/negeer). Schrijft uitsluitend via
  de gevalideerde `inbox_actions`, nooit direct in een store.
- **Loop-fix (root cause)**: de lus leverde niets nieuws omdat (1) de Librarian-beoordeling alles
  zonder vraag escaleerde en escalated terminaal + dedup-blokkerend was (59 van 98 termen vast).
  Stefan heeft de berg via het dashboard afgeroomd (59 → 0). (2) KeywordsEverywhere-auto-approve in
  de Librarian (centraal `_enrich_volume`) was geneutraliseerd door `ke_country=nl` (KE geeft voor NL
  overal 0). Nu `ke_country` leeg = **global** (werkt voor NL-termen ≈ NL/BE én merken). Pas hierdoor
  vuurt de volume-auto-approve echt.
- **Concurrent-scout** (nieuwe inwoner, *Sven Spruce*; seed + idempotente migratie, CLASS_MAP):
  - `competitor_news` — Google News RSS per merk, getrapt venster (maand→kwartaal→jaar), harde
    datumfilter, cross-merk dedup, footwear-context tegen homoniemen (Moea≠ministerie).
  - `competitor_discover` — SerpAPI (echte URLs i.p.v. Google News-redirects) → pagina lezen → LLM
    extraheert merknamen. Fail-closed (liever niets dan titel-rommel). Mens bevestigt in de cockpit.
  - `linkbuilding_targets` — gidsen/lijstjes als pitch-doelwitten; prio "hoog" als een gids
    concurrenten noemt maar Nooch niet.
  - marktinteresse via KE (`competitor_interest`).
- **Gedeelde `context.competitors`-store**: bevestigde concurrenten zijn leesbaar voor élke rol
  (zoals library/lexicon) en voeden de Trends-zaadlijst.
- **Spaced-repetition-scheduler** (`keyword_scheduler.py`) vervangt het platte roterende venster:
  nieuw/productief zaadwoord vaak, uitgekauwd zakt naar een langer interval (verdubbelt tot een
  plafond, reset bij nieuwe oogst). Subsumeert de concurrent-voorrang. "Productief" telt alleen
  schoen-relevante nieuwe termen (gedeeld domeinfilter), zodat brede ruis-zaadwoorden wegzakken.
- **Governance-herkomst rechtgezet + bewaakt (A+B)**: de scout + skills waren via seed/migratie
  toegevoegd (afwijking van "rolwijziging alleen via governance"). **A** — `formalize`-CLI dient de
  add_role (scout) + amend_role (Librarian←keywords_everywhere) alsnog via G0-G4 + Secretary in,
  met audittrail; scout-record herbouwd met `source=sensed`. **B** — `BOOTSTRAP_ROLES` +
  `role_provenance_violations()`: alleen de zes founding-rollen mogen geseed zijn, elke andere rol
  moet sensed (governance-geboren) zijn; boot-audit waarschuwt luid. concurrent_scout uit
  seed/migratie gehaald (wordt via `formalize` geboren). **Actie op de live-data: draai
  `python -m nooch_village.village formalize`** om de scout-provenance op je echte records recht te
  zetten (tot dan waarschuwt de boot-audit, correct).

#### Geparkeerd uit deze sessie
- **Scheduler-productiviteitssignaal telt off-domein-ruis mee**: een breed zaadwoord ("regenerative")
  lijkt productief terwijl z'n gerelateerde termen later als off-domein sneuvelen. Verfijning: laat
  "productief" pas tellen als een term het domeinfilter overleeft. (Stefan akkoord met richting.)
- **Gemini gratis dagcap (20/dag)** wordt geraakt; ladder vangt het op. Optioneel: Gemini
  pay-as-you-go aanzetten zodat trede 1 niet wegvalt.
- **Echte concurrent-rankings** ("op welke termen rankt Veja, op welke plek") vragen een rank-tracker
  (Serpstat); SerpAPI levert nu alleen de lichtere gerelateerde-termen-variant.

Wat de eerdere sessie (2026-06-23/24) is gebouwd en nu de waarheid is:

- **De grondwet `docs/spelregels.md`**: 10 substraat-onafhankelijke spelregels die gelden voor
  elke rol-vervuller (machine/AI/mens). Uitgangspunt voor alle verdere bouw.
- **Mens-zetel**: `Record.held_by` + CLI `seat_human <rol> <naam>`. Stefan bezet `the_source`
  (legitieme zetel binnen het model; nog geen interactieve HumanProxy — dat is roadmap).
- **Regel 5 (dorpsbreed)**: rol-vraagt-rol om een accountability. `Inhabitant.offer(key, handler)`
  + `ask_accountability(target, key, payload)`; doelrol dispatcht of senst een spanning.
  CLI `ask_accountability <rol> <key>`. De mens (als the_source) is gewoon een van de vragers.
- **Sluiten-met-oordeel**: `Inhabitant.propose_close(gap_key, reason)` → voorstel op het inbox-item;
  mens bevestigt met `inbox confirm <id>`. De rol sluit nooit zelf (geen dichtgeklapte lus) en mag
  "nee, maar" zeggen (open houden / scherper gat opwerpen i.p.v. stempelen).
- **Harry's rol verdiept** (rol-upgrade v3 via governance): naast richting nu ook structurele
  co-beweging/substitutie over de lange ngram-boog (`leather free ~ vegan` r=0.97 live gevonden),
  en een gekalibreerde voortzetting voorbij de 2019-cutoff via OpenAlex (`mode='yearly'`,
  relatief aandeel, overlap-kalibratie r≥0.5, anker = corpus-eindjaar). Modules:
  `ngram_correlate.py` (pearson, correlate_terms, findings_from_rows, calibrate, continue_arc,
  assess_continuation, uncovered_nl_terms, label_uncovered).
- **NL-corpus-dekking dynamisch**: `_check_nl_corpus` (modus c, stil tenzij vondst) + op verzoek
  via regel 5. Geen hardcoded `_reflect`-gaten meer; beide oude zelf-gaten zijn opgelost.
- **Trends: SerpApi i.p.v. pytrends** (door Google geblokkeerd). `serpapi_trends`-skill,
  wekelijks/zuinig (`serpapi_interval_seconds`, `serpapi_keywords_per_run`), per-taal-geo.
  Field Note níét meer gegijzeld door Trends (`run_bounded`, harde tijdslimiet). pytrends dormant.
- **Gemini als default LLM** (Anthropic fallback). Bugfix: `HttpOptions.timeout` is MS, niet sec
  (stond op 30ms → elke Gemini-call timeoutte). Modelnamen via env (`GEMINI_MODEL`/`ANTHROPIC_MODEL`).
- **KE-aanjager + per-taal-geo**: `measure_propose` zet per-taal meet-batches in de inbox
  (en→gb, nl→nl); credits mens-gated via approve.
- **Librarian-heuristiek tweetalig**: missie-kern uit het Lexicon (en+nl), leather-free/leervrij
  niet meer als leer-risico. `rereview`-CLI her-beoordeelt geëscaleerde termen.
- **Ingest-proces** (`nooch_village/ingest.py` + CLI `ingest <json>`): mens-gecureerde insight-kaartjes
  in de NotesStore (survey-insights + KE-demand insights), via `notes.link` (gevalideerd).
- **Governance-toolset (CLI)**: `grant_skill`, `revoke_skill`, `remove_role`, `grant_serpapi_trends`,
  `upgrade_harry_role`, `seat_human`, `ask_accountability`, `measure_propose`, `rereview`, `ingest`.
- **Opgelost via deze sessie**: inbox-items `ngram_2019_cutoff` en `nl_corpus_coverage`
  (beide approved). Nieuw, scherper gat opgeworpen: `nl_corpus_bron_onbruikbaar` (corpus 10 mist
  doodgewone NL-woorden → Delpher-kandidaat of NL buiten scope).

### Geparkeerd (aparte sessies)

- **Inbox-herontwerp** (eigen designsessie; nu niet perfect = bewust oké). Klein dichtgezet:
  approve-vangnet zodat geen type stil blijft hangen.
- **Grondwet fijnslijpen** (sessie 3), o.a. expliciet: een rol mag nee/openhouden/escaleren.
- **Delpher (KB)** als Nederlandse lange-boog-bron (SRU-API, toegang op aanvraag, loopt tot 1995).
  Stefan kent er mensen. Pas bouwen na KB-toegang.
- **Getrapte LLM-modelkeuze** (Flash-Lite voor classificatie, Flash voor duiding) + prompt-caching:
  pas relevant als je buiten de Gemini-gratis-tier valt.
- **HumanProxy** (interactieve mens-in-het-dorp) — volle versie van de mens-zetel.

---

### Detail-status uit eerdere sessies (historisch, kan deels achterhaald zijn door bovenstaande)

- Code op ~10, 401 tests groen (suite groeide: ... → 384 → 401).
- **LLM-timeout fix** (commit `851c7da`): `anthropic.Anthropic(timeout=30.0)` en
  `GenerateContentConfig(http_options=HttpOptions(timeout=30))` op beide backends.
  Bare `except Exception: pass` vervangen door `logging.warning("LLM <backend> faalde: %s", exc)`.
  5 tests in `tests/test_llm.py` (timeout aanwezig, exception gelogd ×2, fall-through, geen-key).
- **inbox: means_gap approve-handler** (commit `bf10ca0`): mens kan nu een means_gap via de
  inbox-CLI omzetten naar een `amend_role`-governance-voorstel met skill-uitbreiding.
  `human_inbox.add_means_gap` slaat `role_id` op in context (B-uitkomst `classify_gap`).
  `human_inbox.resolve` accepteert `extra={}` voor aanvullende resolution-velden.
  Handler: prompt skill_name/rationale/alternatives, `EOFError`/`KeyboardInterrupt` breekt
  netjes af, submit via `Village.submit_proposal`, wacht max 5s op gate-uitkomst,
  schrijft `skill_added`/`resolved_by="human-cli"` in resolution. Gate-veto toont poort +
  reden, item blijft pending. Fallback voor oude items zonder `role_id`: herleidt via
  `classify_gap`; als dat ook niets oplevert → foutmelding + return, geen crash.
  5 tests in `tests/test_inbox_means_gap_approve.py`.
- 4 review-fixes doorgevoerd: atomic writes + Noochie-rem (één voorstel, geen
  stroom), test-fundament (pytest), single-source missie/policy, village.py
  gesplitst + TriageEngine eruit + DRY.
- Keyword-lus gesloten: Librarian-escalaties landen als eigen type "keyword" in
  de inbox (approve → approved, reject → forbidden naar de bibliotheek, direct,
  deduped).
- Live AI-burgers: WebsiteWatcher (Corry Coconut), Librarian, TrendsWorker (Maisy Mushroom),
  Facilitator, HarryHemp, Noochie. Onbemand seed: The Source (Stefan).
- **Observatie-store**: getimestampte tijdreeks per rol/metric (`data/observations.jsonl`,
  append-only). WebsiteWatcher (Corry Coconut) logt pulsdata voor gemonitorde metrics.
- **Project-primitief + grootboek + projects-CLI**: ProjectLedger (atomic writes,
  mtime-reload voor cross-process zichtbaarheid), human-push trigger via CLI.
  Levenscyclus: `queued → running → blocked → running → done`.
- **Metric-discovery-lus end-to-end bewezen met gemockte trage delen** (Plausible,
  Trends, LLM): project → website_watcher ontdekt menukaart → Noochie adviseert →
  website_watcher zet monitoring → pulse logt. Gevalideerd in `tests/test_loop.py`
  (echte threads, 20s timeout). Echte supervised live run nog te doen.
- **MonitoringStore**: per-rol lijst van te monitoren metrics (`data/role_metrics.json`,
  dedup + gesorteerd). Gevuld door `_on_advice_ready` na Noochie-advies.
- **Facilitator (absorbeert TimeKeeper-cadans)**: `maand_begint` / `kwartaal_begint` toegevoegd aan
  `cadence_events` (dag 1 van maand resp. kwartaal).
- **Dom WIP-plafond op het grootboek**: ontworpen, NIET gebouwd; `ProjectLedger` heeft `open()` maar geen cap-logica; te bouwen.
- **Structurele fix — once-per-pulse-discipline + `_busy`-drop**: `react()` heeft
  `drop_if_busy=True`; een `dag_begint` tijdens een lopende puls wordt bij
  enqueue direct weggegooid (niet gequeued). `_setup_events()`-hook laat
  WebsiteWatcher/TrendsWorker/HarryHemp hun eigen pulsgate definiëren.
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
  `amend_role` = 0 in system_log. 170 tests groen (`tests/test_means_gap.py`, groep-A;
  groep-B verwijderd in 1ed484d, volledige route-dekking via `test_harry_hemp.py` en `test_gap_routing.py`).
- **Durable reject** (commit `87b91a5`): CLI-leespaden (`list`/`show`/`defer`/
  `approve`) muteren niet meer via `sync_unmanned`. Reject-activatie archiveert
  het onderliggende sensed-record zodat het niet terugkomt. `add_activation`
  dedupt op elke status (ook rejected/approved). `inbox show` voor means_gap
  toont de beschrijving. 176 tests groen.
- **classify_gap — pure functie A/B/C** (commit `79e8e9e`): term-overlap classifier
  via drie handtekeningen (gap, mandaat, middelen). MANDATE_THRESHOLD=0.10,
  MEANS_THRESHOLD=0.15. 9 thread-vrije tests, 185 tests groen.
- **classify_gap aan means-gap-naad** (commit `83b26e5`): `Village._on_means_gap`
  dispatcht nu op A/B/C: A → log-only, B → means_gap inbox (zoals voorheen),
  C → suggestion inbox (placeholder, geen geboorte). 7 nieuwe tests, 192 groen.
- **Geboorte-naad-reroute** (commit `5548557`): `classify_gap` zit nu op
  `Inhabitant._raise_governance_proposal`; `roster_match()` en de losse
  `COVERAGE_THRESHOLD=0.34` zijn retired — één dekking-autoriteit. A-spanningen
  worden gelogd en teruggestuurd. B-spanningen gaan via `_report_means_gap` naar
  de means-gap inbox. Alleen C-uitkomsten genereren nog een ADD_ROLE-voorstel.
  Junk-rollen worden niet meer geboren.
  Gevalideerd: (1) thread-vrije integratietests via twee-slag-gate
  (`tests/test_birth_gate_two_strike.py`, 5 tests): 3 junk-beschrijvingen → A,
  geen ADD_ROLE; legal-compliance → C → ADD_ROLE. (2) Live run 7 pulsen: geen
  nieuwe rol geboren, geen nieuwe activatie-items, alle junk-spanningen als B
  geblokkeerd. (3) Meting tegen echt Noochie-record
  (`data/governance_records.json`): junk-scores 0.125–0.571, matchende rol
  noochville (anchor-purpose) en website_watcher, alle drie B, geen C. Lek is dicht.
  De twee-slag-gate (`_sense_gap`, `min_count=2`) bestaat al stroomopwaarts en
  is geen extra werk voor de trechter.
- **C-trechter + coherentiepoort live** (commit `13802c9`): `_funnel_c_proposal`
  bevat drie filters in volgorde: (1) kandidaat-dedup op `gap_key == rec.id`,
  (2) recurrence-passage (no-op, upstream gegarandeerd), (3) coherentiepoort via
  `llm.reason`. Poort is fail-closed: `None`-response, exception, onverstaanbaar
  antwoord, en expliciet `vague` geven allemaal `False`. Alleen `VERDICT: coherent`
  laat door. 6 tests in `test_c_funnel.py`, 203 tests groen.
- **Skill/metadata-schema**: 15 skills declareren `cost`, `side_effect_free`,
  `input_schema`, `output_schema`; 4 tests in `test_skill_metadata.py`.
- **Keyword-discovery stack — drie bricks op main, CI-groen**:
  - `nooch_village/keyword_matrix.py` — MARKET_LANGUAGES × QUALIFIERS × CATEGORIES × MODIFIERS, pure module
  - `nooch_village/keyword_batch.py` — `propose_batch()`, credit-schatting + metadata
  - `nooch_village/keyword_measure.py` — `measure_batch()`, fail-closed credit-gate, geïnjecteerde runner
  - Ontwerpdocument: `docs/DESIGN_keyword_discovery_workflow.md` (§6 methodologie, fase A/B gating, 6-staps pipeline)
- **Live validatie `keywords_everywhere` (19 juni)**: GKP geeft vol=0 voor NL/DE lokale
  termen; CLI (clickstream) geeft echte volumes. NL "vegan schoenen" = 3.4k CLI,
  DE "vegane schuhe" = 48k CLI. Conclusie: `data_source="cli"` default voor
  NL/DACH/Nordics, vastgelegd in DESIGN doc §6.
- **Academische grounding live**: HarryHemp grondt elke binnenkomende term
  tegen OpenAlex (citatie-rang, key-auth) en Semantic Scholar (recente literatuur
  + tldr). Per_page-bug gefixed; 429-backoff actief; beide sockets groen op echte keys.
- **Keyword-pijplijn compleet op main**: matrix → batch → measure → integration
  → inbox, lineair, CI-groen. nl/core village-run bevestigd (15 credits, Librarian
  en HarryHemp verwerken gepubliceerde termen). FR/ES/IT (Romance word-order)
  gecommit en live getest.

## Openstaand / let op

- ~~**Venv was gebroken**~~ ✅ Gedaan — schoon herbouwd met Python 3.14, pip-shebang
  gecorrigeerd, 327 tests groen (lokale actie, geen commit).
- **`KEYWORDS_EVERYWHERE_API_KEY` moet in `.env`** (regenereren; oude sleutel is
  in een chat-sessie verschenen).
- ~~**`pandas>=2.0` trekt in CI al `pandas 3.0.3` binnen**~~: ✅ Gedaan — gecapt op `<3`
  (commit `cd4116c`); verse venv pakt `pandas 2.3.3`.
- **cost-gate** (puls weigert `cost != "free"`): blijft genoteerd, niet gebouwd.
- **credit-gate-hardening**: de plafond-check in `measure_batch` toetst
  `batch["estimated_credits"]`, terwijl `credits_spent` op `len(batch["candidates"])`
  telt. Nu altijd gelijk (brick 1 garandeert het), maar bij een misvormde batch
  kunnen ze divergeren en zou de gate kunnen goedkeuren terwijl de spend het plafond
  overschrijdt. Fold in de wiring-brick: laat de plafond-check óók op
  `len(batch["candidates"])` toetsen, zodat je gate op wat je werkelijk uitgeeft.

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

## Openstaande ontwerpschuld

- **Beveiliging: rolwijzigingen alleen via governance** — ✅ deels gedaan (2026-06-24, B):
  de herkomst-wachter (`role_provenance_violations` + boot-audit) dwingt nu af dat alleen
  bootstrap-rollen geseed zijn; elke andere rol moet sensed/governance-geboren zijn. Detecteert
  (waarschuwt luid), verbiedt nog niet hard op records.put-niveau. Resterend (voller B): records
  alleen schrijfbaar via de Secretary (write-token of guard op put), en óók skill-grants aan
  bootstrap-rollen via governance i.p.v. migratie. Oorspronkelijke notitie hieronder.
- **Beveiliging: rolwijzigingen alleen via governance (taak voor later, 2026-06-23)**:
  structureel afdwingen dat élke rolwijziging (add/amend/remove_role) uitsluitend via het
  officiële governance-proces kan (proposal → G0-G4 → Secretary → records), nooit via
  directe records-mutatie of seed-hardcoding. Aanleiding: de Content Strategist is bewust
  via governance geboren (`role_proposals.py` + `python -m nooch_village.village
  content_strategist`), niet geseed; de oude demote-regel in `migrate_records` is
  verwijderd. Volgende stap: een wachter/invariant die een rol-wijziging buiten de
  Secretary om detecteert of verbiedt (records alleen schrijfbaar via de Secretary;
  seed_records/migrate uitsluitend voor de oprichtings-bootstrap, niet voor latere
  structuurwijzigingen). Dit is de structurele rugdekking van born-vs-activated.
- **Kind-woord van verdiep-kaartjes is de volledige vraag (geparkeerd, 2026-06-23)**:
  `_write_child_card` gebruikt de waaróm-vraag als `word`, dus het id (=slug van het
  woord) en de matching hangen aan een verbose vraag vol veelvoorkomende tokens. In de
  simulatie maakte dat de green-gap-kaart een sterke brug (6 buren over beide clusters),
  maar ook een over-matcher: meer verband-kandidaten naar de inbox. Geen foute data,
  wel ruis. Bewust uitgesteld tot er echte data is: bij laag volume (emergentie + budget
  remmen de aanwas) blijft de latere fix klein. **Caveat bij achteraf fixen**: het id is
  afgeleid van het woord, dus een schoner kind-woord vraagt een her-slug + her-link-
  migratie (triviaal bij laag volume, geen pure no-op). De échte fix is dat de LLM naast
  de vraag een beknopt onderwerp-label levert dat beide concepten spant (bijv. "green gap
  price premium"); dat is een kleine feature, geen eenregelig fixje.
- **Engels = werktaal-default (besloten 2026-06-23, gebouwd)**: `language.py` is de bron
  van waarheid; kaart-voedende prompts vragen Engels tenzij expliciete locale. Reden in
  de docstring. Nog te doen: bulletin/Field Note zijn mens-rapporten en volgen nu nog NL;
  besluit of die ook naar Engels gaan (raakt het oude "rapportage volgt de mens"-principe).
- **MANDATE_THRESHOLD = 0.10 empirisch laag**: junk-mandaat-scores liggen op
  0.125–0.571, klantverhalen op 0.333. C is in de praktijk bijna onbereikbaar
  voor alles wat Nooch-woorden bevat (anchor-purpose vangt breed). Voorlopig
  ongewijzigd laten tot er een gelabelde dataset is om op te kalibreren.
  De LLM-coherentiepoort in de trechter krijgt mede de taak om verdachte B's
  te beoordelen (lage score, brede match op anchor-purpose), niet alleen C's.
- **Cirkelfilter in classify_gap**: `noochville` (type=circle) wordt meegeschand.
  Uitfilteren verandert B/C-verdeling niet (gemeten), maar verschuift matchende
  rol van noochville naar website_watcher. Cosmetisch, geen veiligheidsprobleem.
  Beslissing uitgesteld.
- **Durable-reject**: feature gebouwd (commit `87b91a5`), bevestigingstest
  nog niet. Smart WIP en requirements-dev.txt: open uit vorige sessies.
- **Project b88d2ddaea33** (website_watcher discovery via plausible_stats):
  credential-conditie ingelost (.env bevat nu PLAUSIBLE_API_KEY). Echte
  blokkade is de event-handshake: Noochie's advies bereikt website_watcher niet
  terug om de discovery-run te hervatten. Nog open.
- **C-trechter dedup dood-tot-eerste-geboorte**: `_funnel_c_proposal` vergelijkt
  `gap_key` (afgeleid via `_role_id_from_gap`, top-3 tokens) tegen `rec.id`.
  Seed- en handmatige sensed-records hebben korte, leesbare namen die nooit
  matchen op een token-afgeleid ID. De dedup triggert dus pas nadat een eerder
  C-voorstel is aangenomen en het resulterende record in governance staat. Correct
  binnen scope, maar in productie feitelijk inactief totdat de eerste C-rol is
  geboren.
- **B/C-sleutelverschil — cross-pad history ontbreekt**: `_report_means_gap`
  gebruikt `re.sub(r"\W+", "_", desc[:30])` (slug van eerste 30 tekens);
  `_funnel_c_proposal` gebruikt `_role_id_from_gap` (top-3 semantische tokens).
  Een gat dat van B naar C kantelt (bijv. na een records-wijziging) wordt door
  de C-trechter niet als duplicaat van een eerder afgewezen B-item herkend. De
  twee histories (inbox-history voor B, records-history voor C) spreken een
  andere sleuteltaal. Sleutel-uniformering lost dit niet op; een cross-pad
  history-lookup (inbox checken vóór C-publish) is de correcte fix, maar een
  aparte kwestie.

- **Lichtgewicht governance-CLI vs governance-ritueel**: huidige
  means_gap-, escalation- en keyword-approve-handlers starten allemaal
  een volledige Village (8-12 threads) voor één submit_proposal.
  Bestaande schuld, drie handlers met hetzelfde patroon. Wordt
  overbodig zodra governance-ritueel (zie
  docs/ontwerp_governance_ritueel.md) wordt gebouwd, want governance
  wordt dan een Village-staat, geen losse CLI.

- ~~**Inbox approve-gate timeout (5s) is een gok**~~: ✅ Opgelost — al instelbaar via
  `inbox_approve_timeout` in `settings.ini` (default `5`). Geen actie nodig; fix-on-trigger
  als ooit een echte false-timeout optreedt.

- **Ontwerpprincipe vastgelegd (Stefan, 15 juni)**: "een spanning mag
  nooit doodlopen". Elke spanning kan worden omgezet in governance
  (nieuwe, aangepaste of verwijderde rol), in een project (huidig of
  toekomstig), of via human-escalatie voor prioriteitswijziging.
  Routing langs dit principe toetsen bij toekomstige ontwerpkeuzes.
  Huidige means_gap-handler voldoet (drie uitwegen: approve naar
  governance, reject met reden, zichtbare foutmelding bij ontbrekende
  role_id).

- **Diepere ontwerpvraag uit Noochie-misfix**: een missie-alignment-
  rode-vlag ("niet_ok") gaat nu via sense_tension de operational-route
  in en belandt zo in classify_gap en mogelijk de B-route. Een
  missie-rode-vlag is geen capaciteitsgrens, hoort waarschijnlijk
  een eigen kanaal te krijgen (escalation naar governance? eigen
  event-type?). Te onderzoeken later.

- **Inzicht "mens als rol"** (zie ontwerp_governance_ritueel.md) raakt
  meerdere systeemonderdelen. Te bouwen na Holacracy v5
  constitutie-herleting door Stefan.

- **Insight ↔ library brug**: gebouwd deze sessie. concept_id plus
  by_concept op Insight, link_concept plus keywords_for_concept op
  Library, concept_for_word dekt de zaadtermen. Het concept is de
  gedeelde spil. 14 van 86 keywords deterministisch gekoppeld (backfill
  exact-match plus parent-erving); de burger- en consument-kinderen
  bewust ongekoppeld als homoniem-ruis. De 72 resterende wachten op de
  fail-closed LLM-suggestielaag (klaar, eerste run op productie). Open:
  koppel-mechanisme voor een goedgekeurd LLM-voorstel nog te ontwerpen
  (raakt optie 2 / draad 4).

- **Kraan omgebouwd (2026-06-22), discovery draait nu Engels-worldwide op schone seeds.** De brok-0-diagnose klopte: het was wiring, niet data. De ombouw in deze sessie:
  - Trends-skill leest nu ook `rising` related queries naast `top` (breakout-signaal behouden als sentinel), meer oogst per pytrends-call zonder extra quotum.
  - `geos`, `hl`, `timeframe` instelbaar via payload; dagcyclus geeft expliciet de discovery-stand mee (worldwide, en-US, today 3-m). Lege geo leidt nu af naar EN, niet NL.
  - Grof schoen-domeinfilter in `prioritize`: keyword-acties zonder schoen-categoriewoord vallen vóór scoring (zelfde patroon als policy-drop). Filtert afgeleiden, niet de seeds zelf.
  - Vier scherpe seeds in `config/keywords.txt`: barefoot shoes, sustainable shoes, eco friendly shoes, barefoot sneakers. Bewezen volume + schone waaier (meting), gekozen boven brede termen als 'duurzaam' (waaiert naar funderingsherstel) en dode missie-termen.
  - Vliegwiel opgeschoond: van 16 approved Library-woorden (die als extra seeds dienen) naar 6 schone schoen-termen; 10 off-schoen NL-woorden op `avoid` gezet zodat ze geen quotum meer vreten.
- **Strategische diagnose (gemeten, hard): missie-termen hebben geen zoekvraag.** KeywordsEverywhere-clickstream gaf nul volume op 'plastic free shoes', 'plasticvrije schoenen', 'plastikfreie schuhe' (drie talen), terwijl 'barefoot shoes' 165k/mo gaf. Gevolg, sturend voor alle discovery: categorie-termen (barefoot, vegan, sustainable) zoek je via discovery; missie-termen (plasticvrij) creëer je via content, je leent het volume van de categorie-term om de missie te introduceren. Discovery-taal is Engels (vaak ook creatie).
- **Seed-strategie: weinig scherpe seeds, vliegwiel breidt zelf uit.** Een sterke seed baart de volgende generatie scherpere seeds via z'n waaier (top/rising) → approved → seed. Leersnelheid komt van weinig sterke seeds (rijke waaier, spaart quotum), niet veel matige. Stefan promoveert nieuwe seeds met de hand uit de waaier.
- **Openstaand na deze sessie:**
  - **Live-bevestiging (K1d, ~10 min, geen bouw):** één `once()`-run zodra pytrends-quotum hersteld is, kijken of Engelse schoenen-termen met `google_trends_rising`-bron door de keten komen en het domeinfilter de ruis dropt. (Quotum was op aan eind van de sessie.)
  - **K2 — woord-tot-kaartje: in de kern af (2026-06-22).** Bleek een diagnose-brok, geen bouw-brok. De naad vuurt: een gegrond woord wordt door de Librarian als kaartje vastgelegd met een geldige grounding-status (unresolved). Twee vermeende gaten bleken geen bouwwerk te vragen: (1) de grounding-status werkt al (de "status: None" in notes.json laadt via Pydantic-default correct als unresolved; de oude zes gezaaide kaartjes draaien dus goed); (2) het concept blijft bewust None bij grounding. Dat laatste is geen bug maar een ontwerpbesluit: een vers gegrond woord (noochwear.com reviews, duurzaam wonen) staat nog niet in het lexicon, dus concept_for_word geeft terecht None. Een concept is een beloning voor emergentie, niet een administratieve handeling bij elke grounding. Zie de kennis-evolutie-ontwerpvraag voor het koppel-mechanisme.
  - **Leeskant van de kennislaag gebouwd (2026-06-22).** Tot deze sessie was de kennislaag schrijf-only: kaarten werden geschreven, niemand las ze terug. Nu leest, groeit en verbindt ze. Vier vormen, alle getest, alle op main:
    - **Stap nul (leesbasis):** `word`-veld op Insight (gevuld bij grounding, backward-compatible). `NotesStore.relevant_for(word)` vindt verwante kaarten via gewogen woord-overlap, zelf-metend op zeldzaamheid (een gedeeld woord telt zwaarder naarmate minder kaarten het bevatten — geen vaste stopwoordenlijst, "generiek" groeit mee met het dorp). Matcht op het word-veld.
    - **Vorm 2 (lezen-en-gebruiken):** de Librarian raadpleegt bij het beoordelen van een woord zijn verwante kennis (relevant_for) en logt wat hij vond (📚). Zichtbaar, stuurt het oordeel NIET — bewust het veilige niveau, want unresolved kaarten mogen nog geen beslissing kleuren. Het beslissende niveau (kennis stuurt oordeel) is een bewuste latere stap.
    - **Vorm 1 (lezen-en-verrijken):** een tweede grounding van hetzelfde woord verrijkt de bestaande kaart in plaats van weggegooid te worden (de oude stille ValueError). `enrich` voegt de bron toe, hoogt `grounding_count` op, zet `last_updated_at`. Claim en status blijven ongemoeid (verrijken, niet overschrijven). Smal en bewust: alleen bewijs-telling, geen inhoudelijke groei van de claim.
    - **Vorm 3a+3b (lezen-en-verbinden, voorstel-kant):** de Librarian reflecteert op `dag_eindigt`, vindt deterministisch kandidaat-paren (relevant_for, ontdubbeld), en laat de LLM-skill `verband_voorstel` per paar beoordelen of er een zinvol, niet-triviaal verband is — zo ja met een voorgestelde verbindende claim. Fail-closed (geen LLM / onparseerbaar / nee / lege claim → geen voorstel). Begrensd tot 3 paren per dag (kosten). Een bevestigd verband wordt als `human_decision_needed`-event (topic 'verband', met beide kaart-ids en de voorstel-claim) gepubliceerd, klaar voor de inbox. De Librarian kreeg `verband_voorstel` in zijn DNA (seeds.py) + registry (village.py). Prompt aangescherpt + op beide kanten gevalideerd (2026-06-22, e3bd4c0): wijst kaarten af die alleen een gedeelde/lege uitkomst delen (3/3 op echt vegan-paar: twee mislukte groundings → nee), herkent een echt probleem↔antwoord-verband (3/3 op verzonnen paar → ja met zinnige claim). Streng én ruim, stabiel oordeel.
- **Openstaand na de leeskant — vier richtingen:**
  - **3c — verband mens-gated vastleggen (inbox-sessie).** Het verband-voorstel-event ligt klaar. 3c toont het in de inbox met de voorgestelde claim, de mens past 'm aan en keurt goed (of verwerpt), en dan wordt de verbindende kaart geschreven met `links_to` naar beide bron-kaarten. Vraagt een inbox die een bewerkbaar voorstel toont — hoort bij de geplande inbox-verrijking. `links_to` bestaat al op Insight maar wordt nog nergens gevuld.
  - **Meerstemmigheid — andere rollen gronden ook kaarten.** Nu grondt alleen de Librarian (via Harry's evidence). De kennislaag wordt meerstemmig als andere rollen een deel van wat ze al waarnemen vastleggen als atomaire, verbindbare kaart in plaats van als vluchtige tekst in bulletin of Field Note: Noochie een missie-observatie, Corry een trend-bevinding. Niet iets nieuws laten doen, maar vluchtige waarneming laten stollen tot duurzame, bevraagbare kennis. Fundament blijft heel — elke kaart blijft atomair; de rijkdom ontstaat TUSSEN kaarten via vorm 3, niet binnen dikkere kaarten. Afhankelijkheid: heeft 3c nodig (verbanden moeten gelegd kunnen worden voordat meer perspectief-kaarten waarde geven). Per rol een eigen ontwerpvraag: welke waarnemingen verdienen kaart-status, en wanneer.
  - **Continu draaiend dorp met dag- en weekcadans (horizon).** Stip op de horizon: NoochVille niet meer met `once()` aanduwen, maar continu laten leven. Dagritme: Noochie/TimeKeeper start 's ochtends (bv. 7:30), rollen werken tot de middag (bv. 15:30), daarna field notes + bulletin (16:00). Weekritme bovenop het dagritme: één keer per week een human-inbox-moment, een roloverleg, en een diepere week-analyse. Stefan verschuift daarmee van continu-aanwezig naar wekelijkse mens-aan-de-poort — precies de human-AI-harmonie (dorp doet betrouwbaar werk, mens doet oordeel + strategie), maar wekelijks ipv dagelijks. Bouwstenen bestaan deels: TimeKeeper + run_forever() dragen al een dagcadans (zie de once()-nuance in JOURNAL 2026-06-22: dag_eindigt valt alleen in run_forever vanaf dag twee). Drie ontwerpvragen die dit écht maken, niet alleen "draai het op een server":
    - **Veiligheid = de proef op de gate-spine.** Een week zonder toezicht draaien betekent: alles wat het dorp autonoom doet moet reversibel/laag-risico zijn, alles onomkeerbaars wacht op het wekelijkse mens-moment. De inbox stapelt en blokkeert niet (het dorp loopt niet vast omdat het op Stefan wacht). Als het dorp een week veilig zonder Stefan draait, is bewezen dat reversibel-automatisch vs. onomkeerbaar-mens-gated echt goed gescheiden zijn.
    - **Wat is een week-analyse?** Niet zeven bulletins stapelen, maar een patroon dat een dag niet ziet: welke woorden kwamen herhaaldelijk terug, welke trends hielden aan. Raakt het emergentie-idee direct — een week is precies de tijdschaal waarop "≥3 keer teruggekomen" zichtbaar wordt. De grounding_count-teller (vorm 1) voedt dit.
    - **Waar draait het?** 24/7-leven vraagt een host die aan blijft (niet Stefans laptop). Hosting-vraag voor later, niet blokkerend voor het ontwerp.
    Eigen ontwerpsessie. Hangt losjes samen met 3c (de wekelijkse inbox is waar verband-voorstellen landen) en met de emergentie-koppeling (het weekritme is de natuurlijke tijdschaal voor "structuur verdienen door herhaling").
  - **Bekende eigenschappen (geen taak):** domeinfilter kijkt nu ALLEEN naar het label (2026-06-22): een schoen-woord in de description (via parent-term) kan een off-domein term niet meer redden. Randzwakte gedicht, met test. Filter is daarmee iets strenger — een term die het schoen-woord alleen in de description draagt valt nu ook (acceptabel, past bij grof+streng). Library-saturatie op termijn (poort blokkeert elk bekend woord, raakt de geparkeerde poort-versoepeling). KeywordsEverywhere-volume-validatie als geparkeerde vervolgstap, gegate want credits.

- **Spelregel: library-check aan de poort, niet bij de grounding**: voordat een rol
  een woord op de bus zet, checkt ze of het mag in de library (is_forbidden). De zeef
  hoort bij het publiceren, niet bij het gronden. Plek: de gedeelde functie
  _publish_keyword_proposed, waar alle drie de ontdekkingsrollen doorheen gaan
  (WebsiteWatcher via Trends, PerformanceScout via GSC, Harry via ngram). Eén check
  daar filtert voor allemaal, en een verboden woord komt niet eens op de bus. De bus
  wordt zo een gedeelde, schone werkvoorraad waar meerdere rollen uit kunnen putten.
- **Poort filtert al, Harry-check teruggedraaid**: de spelregel bleek bij nader
  inzien al geïmplementeerd. _publish_keyword_proposed laat geen woord door dat al
  in de library staat (productieverkeer loopt volledig via deze poort, alleen demo's
  omzeilen hem). De gisteren toegevoegde is_forbidden-check bij Harry was dus dubbel
  en is teruggedraaid. Let op: de poort blokkeert nu élke bekende status, niet alleen
  forbidden, dus ook approved woorden vallen voorgoed uit de stroom.
- **Vervolg (grote brok, eigen sessie): poort van ken-ik-dit naar mag-dit**: de
  poort moet versoepelen van "woord is bekend" (status is not None) naar "woord mag"
  (is_forbidden), zodat een approved woord opnieuw door de poort kan. Consequenties
  nog te overzien: dan kan élk niet-verboden bekend woord terugkomen, en zonder
  aandrijving zwerft dat rond.
- **Vervolg (hangt aan het vorige): spaced-repetition-ritme**: approved woorden niet
  passief toelaten maar actief op gezette tijden laten herzien en hermeten, zodat
  stijgende termen opnieuw onderzocht worden. Dit is het mechanisme dat de
  versoepelde poort aandrijft; de twee horen bij elkaar.
- **Ontwerpvraag (review over ~10 weken): kennis-evolutie vastleggen**: het idee om
  de poort te versoepelen (approved woorden terug de stroom in) bleek geen regeltje
  maar drie gekoppelde wijzigingen, en eronder lag een diepere vraag. Een approved
  woord dat opnieuw gegrond wordt levert verse kennis op, en die wil je het oude niet
  zomaar laten overschrijven: het verloop van bewijs is zelf waardevol voor het
  leerproces. Dat botst met het huidige model (één Insight-id per woord, één actuele
  stand). Twee richtingen, fris te kiezen: (a) verversen plus een apart logboek dat
  per datum de grounding bewaart, kaartje = heden, logboek = verleden, laat de
  Insight-structuur intact; (b) het kaartje meervoudig maken, een reeks waarnemingen
  in de tijd, rijker maar raakt grounding-status, evidence-laag, poortregels en de
  keuring. Bewust uitgesteld: dit heropent het net-gelegde fundament en verdient een
  eigen sessie met de consequenties overzien, niet een avond-ingreep. Tot dan blijft
  de poort dedup-op-alles (ken-ik-dit), wat voor het lage volume van de eerste weken
  prima volstaat.
    Concrete invulling (Stefan, 2026-06-22): concept-koppeling verdient emergentie.
    Koppel een woord pas aan een concept als het zich bewezen heeft, bijv. na ~3
    groundings van hetzelfde woord. Eerst emergentie bewijzen, dan structuur toekennen
    (zelfde logica als spaced repetition voor seeds: herhaling verdient gewicht).
    Voordeel: geen LLM-call per grounding (verspilling aan eendagsvliegen), wel een
    gerichte koppeling voor woorden die blijven terugkomen. Voorwaarde die nu ontbreekt:
    een telmechanisme. Het systeem onthoudt niet hoe vaak een woord langskwam; sterker,
    een tweede grounding botst nu op de deterministische kaartje-id (ValueError, stil
    gevangen) en wordt weggegooid. Een woord dat terugkomt moet dus geteld of gestapeld
    worden in plaats van verworpen, en dat is precies richting (b) hierboven (kaartje
    meervoudig / reeks waarnemingen). Het emergentie-idee en de meervoudig-kaartje-vraag
    zijn dus hetzelfde mechanisme van twee kanten. Bouwen in deze sessie, niet eerder,
    want het raakt het kaartje-fundament. Tot dan: kaartjes blijven concept-loos bij
    grounding, wat de juiste tussenstaat is.
    Update 2026-06-22: de grounding_count-teller bestaat nu (vorm 1) — een tweede grounding hoogt 'm op in plaats van stil te sneuvelen op de ValueError. De voorwaarde "telmechanisme ontbreekt" is daarmee deels vervuld: er wordt geteld. Wat nog mist voor de emergentie-koppeling is de drempel-logica (na ~3 groundings concept koppelen) en de concept-suggestie zelf. De teller is de fundering; de drempel + koppeling is het resterende werk van deze sessie.
- **Regeneratief-pagina**: kwam 17 juni meermaals boven (field-note-aanbeveling
  + drie Noochie-oordelen). Content-backlog, geen code. Drie stappen:
  1. Research eerst: regeneratief in combinatie met footwear/sneakers, is dit
     een echte kans?
  2. Pas daarna een draft, mét productieketen, materialen en eerlijke prijs
     (niet kaal SEO, conform Noochie's transparantie-waarschuwing).
  3. Draft ter controle naar Noochie.

- **Ingestie-rol nog te bouwen**: zes notes zijn nu handmatig
  toegevoegd via seed-script. Voor schaalbare ingestie van fuzzy
  input is een dialoog-rol nodig die we vrijdag 12 juni hebben
  ontworpen in docs/ontwerp_kennislaag.md. Eerstvolgende
  natuurlijke vervolgstap na het familie-bezoek.

- **Bevindingen uit Noochie's eerste echte bulletin-runs (15 juni middag, toen nog Ronnie)**:

  - Race-condition in dev-pulse: website_watcher's puls (Plausible plus
    schrijven Field Note) duurt langer dan de twaalf seconden tot
    dag_eindigt. Noochie leest de Field Note voor 'm bestaat, valt
    terug op fallback-tekst. In productie (echte dag-cadans) geen
    probleem. In dev-pulse wel. Niet acuut, wel observatie.

  - Noochie's event-subscription omvat nu 9 types in `_TRACK`, inclusief
    gsc_pulse_completed (verzameld met boodschap, getest in
    `test_gsc_pulse_completed_verzameld_met_boodschap`). De oude notitie
    "gsc_pulse_completed bewust weggelaten" is achterhaald: het signaal
    wordt gevolgd. noochie_weighed_in is toegevoegd aan de audit-trail
    (17 juni).

  - Patroon vandaag bevestigd: een ontdekking leidt vaak tot een fix
    die tot een nieuwe ontdekking leidt. Eerste Noochie-bulletin
    toonde guardrail-zwakte. Verbreding plus guardrail leidde tot
    ontdekking van race-condition en audit-trail-gat. Belangrijk om
    in budget-discipline (10 uur per week) deze keten te kunnen
    stoppen op een natuurlijk moment, niet door uitputting.

- **Claude Code commit-discipline en ongevraagde wijzigingen**: vandaag
  drie keer netjes gewacht op akkoord (Noochie-fix, LLM-timeout,
  inbox-handler), één keer ongevraagd gecommit (38a2243 hygiëne-veeg).
  Daarnaast drie keer ongevraagde inhoud-wijzigingen aangebracht in
  bouw-stappen (sense_tension-signature in Noochie-fix,
  parse_verdict_reason-extractie, sectie-aanpassing in
  governance-ritueel-doc). Allemaal technisch verdedigbaar, geen van
  drieën gevraagd. Bewust besluiten hoe verder: accepteren, scherper
  benoemen, of branch-based review afdwingen.

- **Cleanup-review**: 31 items wachten op triage, werkplek = inbox.

- **Approved-status verfijning**: onderscheid tussen "approved voor
  onderzoek" (research-rollen mogen data verzamelen, geen content)
  en "approved voor SEO" (content-rollen mogen content maken).
  Een term kan onderzoekswaardig zijn zonder content-waardig te
  zijn. Implementatie: ofwel twee aparte statussen (research_ready,
  seo_ready), ofwel één approved met sub-veld. Te besluiten in
  latere sessie. Niet in machine 3 of machine 2 ingebouwd.

- **Triage via JSON-bewerking is werkbaar voor MVP maar niet
  schaalbaar**: volgende stap (na machine 2): triage via inbox-
  mechanisme. Stefan krijgt per geëxtraheerde term een inbox-item
  met escalated/forbidden/ignore-knoppen. Consistenter met andere
  goedkeuringsroutes in het systeem.

- **Gate-check add_skills**: een spook-skill in een voorstel
  sneuvelt nu pas in `test_record_registry_consistentie` (na adoptie).
  Grotere broer: G0 of een aparte pre-adoptie-check valideert
  `add_skills` al bij indiening tegen de registry, zodat een typefout
  direct een `proposal_invalid` geeft. Niet gebouwd — uitgesteld.

- **Durabel vastleggen welke skills een Inhabitant nódig heeft**:
  nu kan een `use_skill`-aanroep in code en het governance-record
  stil uit elkaar lopen (code vraagt skill X, record kent skill X
  niet toe). Geen runtime-bewaking van die mismatch. Architectuurvraag:
  moet dit in het record (required_skills naast skills), in de test-
  suite, of als invariant in `use_skill`? Te besluiten later.
- **cost-gate** (puls weigert `cost != "free"`): genoteerd, niet gebouwd.
  Trigger = credits-skill voorgesteld voor de puls óf creditsaldo zakt.
- **Field-note meervoudige rol-reflectie**: ontwerp-item voor een toekomstig
  Noochie-bulletinblok. Niet de growth-field-note hergebruiken als input voor
  meerdere rollen, maar per rol een eigen destillatie-stap. Geen bug: Noochie
  heeft altijd brede event-input (8 typen in `_TRACK`); de field note is verrijking
  bovenop die input.
- ~~**Facilitator.`_ring` leest `date.today()` opnieuw na `tick()`**~~: ✅ Gedaan —
  bleek al gefixt: `tick()` geeft de gelezen datum als argument door aan `_ring`,
  dat de klok niet meer zelf herleest. Vangnet-test toegevoegd
  (`test_ring_gebruikt_de_door_tick_gelezen_datum` in `tests/test_facilitator_cadence.py`):
  klok springt over middernacht (1→2 april), test bewijst dat alleen de door `tick()`
  gelezen datum telt. Mutatie-getest (bug teruggebouwd → test rood → hersteld → groen).
- ~~**`_interval>0`-tak van `tick()` mogelijk dead code**~~: ✅ Onderzocht — GEEN dode code,
  niet weghalen. De tak is het lokale `run`-pad: `cli.py` doet `Village().run_forever()`
  zonder heartbeat-argument, dus `_interval` komt uit `config/settings.ini`
  (`heartbeat_seconds = 5`). In productie is heartbeat 0 (kalender-tak), lokaal 5
  (interval-tak, demo-puls elke 5s). De tak was alleen ongetest: alle overige
  Facilitator-tests draaien op heartbeat 0. Vangnet-test toegevoegd
  (`test_interval_tak_vuurt_en_knijpt_af`): puls vuurt voorbij het interval en wordt
  afgeknepen erbinnen. Mutatie-getest (afknijp-logica uit → test rood → hersteld → groen).
  Let op (geen taak): met heartbeat=5 ringt Facilitator elke 5s een volle dag-cyclus —
  dezelfde dag_eindigt-storm die de growth-demo met heartbeat=0 juist vermijdt.

## Evaluatie-checkpoints

### B-observer pad — beslissing na 7 live pulsen

- Trigger: na 7 live pulsen (~1 echte week) de B-observer logs handmatig
  doornemen, per verdict checken of de mens dezelfde beslissing zou hebben
  genomen.
- Kalibratie-criterium: vals-positieven (vague-verdict op legitieme means-gaps)
  versus vals-negatieven (coherent-verdict op rommel). Drempel X nog te bepalen
  op basis van werkelijk aantal items in de logs.
- Beslissing: coherentiepoort blokkerend maken, observerend houden, of weghalen.

### Eerste live vague-verdict B-observer (45-min run 14 juni avond)

- Vier B-observer calls, drie keer coherent (`openlibrary_v2`, `ngram_2019_cutoff`,
  `nl_corpus_coverage`, consistent met eerdere data), één keer vague:
  `Missie_alignment_ok_De_a`.
- De vague-verdict is correct: het item is een missie-alignment-beoordeling, geen
  capaciteitsgrens. Bewijs dat de coherentiepoort discrimineert op echte vague-cases,
  niet alleen op testfixtures.
- Maar: dit is een **terugkerend patroon**. Gisteren afgewezen als
  `Missie_alignment_ok_Reg`, vandaag opnieuw als `Missie_alignment_ok_De_a`. De suffix
  verandert per genereerronde, dedup pakt 'm niet door verschillende gap_keys.
  Cross-pad memory ontbreekt: afgewezen items worden archived in records, maar Noochie
  stroomopwaarts heeft geen toegang tot die geschiedenis en blijft het patroon
  genereren.
- Te onderzoeken later: wat in Noochie's missie-alignment-werk produceert outputs die
  als means-gap worden gerouteerd? Is dit een type-vraagstuk (output van
  missie-alignment != means-gap), een routing-bug, of een mandate-overlap?
- Voor nu: niet ingrijpen, gewoon observeren. Volgende runs zullen tonen of dit blijft
  terugkomen en hoe vaak.

### Procesnotities

- **Claude Code commit-discipline**: ondanks expliciete stop-regel bovenaan
  de instructie en herhaalde "wacht op akkoord" heeft Claude Code op 15 juni
  opnieuw zonder akkoord gecommit (`38a2243`). Vierde voorkomen sinds vrijdag.
  Inhoud was elke keer correct, maar het reviewproces wordt structureel
  omzeild. Bewust besluiten hoe hiermee om te gaan: accepteren als gegeven,
  branch-based review afdwingen, of expliciet blijven benoemen per voorkomen.
- **15 juni avond — stop-regel gerespecteerd**: beide commits van vandaag
  (`851c7da`, `bf10ca0`) na expliciete "akkoord" — geen voortijdige commits.
  Patroon vastgehouden.

### Herframing 15 juni

Diepere herframing 15 juni: NoochVille is op dit moment primair
denkgereedschap voor Stefan, geen operationele kern. De waarde zit nu
in spill-over naar ander werk. Of NoochVille ook operationele waarde
gaat leveren is onbekend, daarom option-value-aanpak (100 uur, 10
weken, evaluatie 24 augustus). Drie kennislagen die straks horen te
bestaan (ingestie, librarian, rapporteurs) zijn ontworpen maar niet
gebouwd. Het datamodel voor het kenniskaartje is gebouwd als Insight (Pydantic):
een grounding-status (unresolved/supported/verified), een evidence-laag (EvidenceType
plus reference-veld) en twee poortregels, namelijk dat VERIFIED volledige onderbouwing
eist en dat een eigen claim (CLAIMED) nooit VERIFIED kan worden. De tweede laag, de teksten die kaartjes inzetten, is gebouwd als optie 1: een
keuring bij publiceren (publication_check) die per PublicationKind toetst of alleen
verified kaartjes als harde claim gebruikt worden (unverified_claims), plus een
merk-brede verboden-woordenlijst (find_forbidden_words, waarbij plasticvrij schoon
blijft), samengebracht in review_publication. Een content-model-met-bestemming is
gebouwd en verworpen, omdat een tekst geen vaste enkele bestemming heeft en heterogeen
is. Naspeurbaarheid van claim naar tekst (optie 2) blijft geparkeerd tot het tekst-volume
groeit. De brug van kaartje via concept naar keyword is deze sessie gelegd en
deterministisch gevuld (14 van 86), met een fail-closed LLM-suggestielaag (concept_suggest)
klaar voor de 72 resterende. Eerstvolgend bouw-werk: de LLM-run op productie, het
koppel-mechanisme voor goedgekeurde voorstellen, daarna de ingestie- en librarian-rollen.
Niet in deze sessie.

## Volgende stappen

**Phase A — keyword-discovery pipeline (nu)**

(a) **Wiring-brick**: verbind `keywords_everywhere`-skill als echte runner achter
    `measure_batch`. Approval via inbox/verdict-flow. Fold credit-gate-hardening
    erin mee: laat de plafond-check toetsen op `len(batch["candidates"])`.
(b) **Scout research store**: `TrendsWorker` schrijft keyword + volume naar
    store met status `onderzoeken`. `klaar voor creatie`-vlag als volume boven drempel.
(c) **Demand-feed**: koppel `keyword_proposed`-flow aan demand-data (SEO volume
    uit keywords_everywhere-resultaten). Librarian ontvangt voortaan ook demand.
(d) **Promotion join**: `klaar voor creatie` = scout-research klaar én
    Librarian-approved. Beide gates moeten groen zijn voor verdere verwerking.
(e) ~~**Venv repair**~~: ✅ Gedaan — schoon herbouwd, 327 tests groen.

**HarryHemp — follow-up**

(a) **OpenAlex relevance-sort hybride**: nu gesorteerd op citaties; overweeg
    hybride (relevance-score + citatie-floor). Niet blind flippen: 3-punter
    (drempel bepalen, recency-spanning, test-set voor vergelijking).
(b) **cost-taxonomie voor gratis-laag-met-dagquota**: huidig schema (`free` /
    `rate_limited` / `credits`) vangt dagquota-grenzen niet. Extra label of
    `daily_limit`-veld overwegen.
(c) **Observatie-run**: downstream-effect van de nu-gevulde grounding zien —
    Librarian-beslissingen met HarryHemp-bewijs, `keyword_evidence`-events,
    herbeoordeelde escalaties.

**Wiring-gaps (observatie-run 2026-06-19)**

~~**(a) Ronnie blind voor de dag (prioriteit)**~~: ✅ Opgelost — geen rol-bug maar een
    demo-tijdcompressie-artefact (puls- en dag-cadans hingen aan dezelfde 2s-heartbeat,
    dus `dag_eindigt` viel elke 2s en het bulletin werd met een 2s-slice overschreven).
    Demo simuleert nu één eerlijke dag (fix/demo-eerlijke-dag, gemerged). Productie
    werkte al correct. TimeKeeper-tick-orkestratie nu gedekt (test/timekeeper-tick,
    gemerged).
(b) **locale ontbreekt in de GSC-flow**: TrendsWorker publiceert
    `keyword_proposed` zonder locale in de demand, dus HarryHemp grondt met
    `locale=""` (geen taalsleutel). Fix: TrendsWorker een locale laten
    meegeven, afgeleid uit de GSC-property of de querytaal.

**Roadmap (daarna)**

- Governance-ritueel bouwen — na herlezing Holacracy v5 constitutie (art. 3 + 4);
  ontwerp in `docs/ontwerp_governance_ritueel.md` *(te verifiëren of nog actueel)*
- LLM-trechter voor C-en verdachte-B-spanningen; ook B-spanningen met lage score
  (< 0.20) erdoor sturen *(te verifiëren of nog actueel)*
- Slimme WIP (prioriteit-eviction, backpressure) + synthesizer-rol *(te verifiëren of nog actueel)*
- Cockpit stap 2: rol/skill-authoring per `docs/ONTWERP_cockpit_rol_skill_werkbank.md` *(te verifiëren of nog actueel)*
- `openlibrary_v2`-activatie NIET reflexief goedkeuren: API is per-boek, niet
  corpus-breed *(te verifiëren of nog actueel)*
