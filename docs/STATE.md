# NoochVille — State & Handover (2026-06-19)

## Waar we staan

- Code op ~10, 297 tests groen (suite groeide: 221 → 297).
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
- Live burgers: GrowthAnalyst, Librarian, PerformanceScout, TimeKeeper,
  Facilitator, CircleLead, TijdgeestWachter, KennisScout, Noochie, Ronnie
  (live sinds 15 juni).
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
  noochville (anchor-purpose) en analyst, alle drie B, geen C. Lek is dicht.
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
- **Academische grounding live**: KennisScout grondt elke binnenkomende term
  tegen OpenAlex (citatie-rang, key-auth) en Semantic Scholar (recente literatuur
  + tldr). Per_page-bug gefixed; 429-backoff actief; beide sockets groen op echte keys.
- **Keyword-pijplijn compleet op main**: matrix → batch → measure → integration
  → inbox, lineair, CI-groen. nl/core village-run bevestigd (15 credits, Librarian
  en KennisScout verwerken gepubliceerde termen). FR/ES/IT (Romance word-order)
  gecommit en live getest.

## Openstaand / let op

- **Venv is gebroken** (wijst naar oud `~/Downloads/noochville`-pad). `./venv/bin/python`
  werkt, `./venv/bin/pip` niet — gebruik `python -m pip`. Fix: recreëren uit de
  nu-complete `requirements.txt` en controleren dat het 297 blijft.
- **`KEYWORDS_EVERYWHERE_API_KEY` moet in `.env`** (regenereren; oude sleutel is
  in een chat-sessie verschenen).
- **`pandas>=2.0` trekt in CI al `pandas 3.0.3` binnen**; gemockt dus geen pijn,
  overweeg een cap (`pandas>=2.0,<3`).
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

- **tijdgeest_wachter means-gap blokkade**: `ngram_2019_cutoff` staat op deferred
  (CLI `resolve()` weigert non-pending items). Means_gap-items kennen sowieso geen
  approve-handler in de inbox-CLI — `approve` op een means_gap valt door alle type-
  branches zonder effect. Het juiste pad loopt via
  `Village.submit_proposal(amend_role, add_skills=[...])` → Facilitator G0-G4 →
  Secretary adopt. Operationele acties via een losse Python-one-liner schaalt niet;
  op de lange termijn: óf inbox-CLI uitbreiden met een `means_gap`-approve die het
  governance-voorstel triggert, óf een aparte governance-CLI.

- **MANDATE_THRESHOLD = 0.10 empirisch laag**: junk-mandaat-scores liggen op
  0.125–0.571, klantverhalen op 0.333. C is in de praktijk bijna onbereikbaar
  voor alles wat Nooch-woorden bevat (anchor-purpose vangt breed). Voorlopig
  ongewijzigd laten tot er een gelabelde dataset is om op te kalibreren.
  De LLM-coherentiepoort in de trechter krijgt mede de taak om verdachte B's
  te beoordelen (lage score, brede match op anchor-purpose), niet alleen C's.
- **Cirkelfilter in classify_gap**: `noochville` (type=circle) wordt meegeschand.
  Uitfilteren verandert B/C-verdeling niet (gemeten), maar verschuift matchende
  rol van noochville naar analyst. Cosmetisch, geen veiligheidsprobleem.
  Beslissing uitgesteld.
- **Durable-reject**: feature gebouwd (commit `87b91a5`), bevestigingstest
  nog niet. Smart WIP en requirements-dev.txt: open uit vorige sessies.
- **Project b88d2ddaea33** (analyst discovery via plausible_stats):
  credential-conditie ingelost (.env bevat nu PLAUSIBLE_API_KEY). Echte
  blokkade is de event-handshake: Noochie's advies bereikt de analyst niet
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

- **Inbox approve-gate timeout (5s) is een gok**. Bij eerste false-timeout
  (uitkomst arriveert na de wait): parametrisch maken of langer
  default.

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

- **PermanentNote vs library.json**: twee aparte stores nu. library is
  keyword-georiënteerd, notes is claim-georiënteerd. Geen brug
  ontworpen, want concept_id-veld in PermanentNote ontbreekt. Te
  besluiten in latere sessie: of permanent notes via concept_id
  aan library-entries gekoppeld worden, of dat ze parallelle data
  blijven.

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

- **Bevindingen uit Ronnie's eerste echte runs (15 juni middag)**:

  - Race-condition in dev-pulse: analyst's puls (Plausible plus
    schrijven Field Note) duurt langer dan de twaalf seconden tot
    dag_eindigt. Ronnie leest de Field Note voor 'm bestaat, valt
    terug op fallback-tekst. In productie (echte dag-cadans) geen
    probleem. In dev-pulse wel. Niet acuut, wel observatie.

  - Ronnie's event-subscription is goed voor nu (8 types), maar mist
    bewust gsc_pulse_completed (te frequent voor bulletin) en
    noochie_weighed_in (toegevoegd aan audit-trail, 17 juni). Beide
    kunnen later toegevoegd worden als de bulletin-toon erbij gediend
    is.

  - Patroon vandaag bevestigd: een ontdekking leidt vaak tot een fix
    die tot een nieuwe ontdekking leidt. Eerste Ronnie-bulletin
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
gebouwd. Eerstvolgende echte bouw-werk: datamodel voor
permanent notes (Pydantic), eerste librarian-rol voor één cirkel.
Niet in deze sessie.

## Volgende stappen

**Phase A — keyword-discovery pipeline (nu)**

(a) **Wiring-brick**: verbind `keywords_everywhere`-skill als echte runner achter
    `measure_batch`. Approval via inbox/verdict-flow. Fold credit-gate-hardening
    erin mee: laat de plafond-check toetsen op `len(batch["candidates"])`.
(b) **Scout research store**: `PerformanceScout` schrijft keyword + volume naar
    store met status `onderzoeken`. `klaar voor creatie`-vlag als volume boven drempel.
(c) **Demand-feed**: koppel `keyword_proposed`-flow aan demand-data (SEO volume
    uit keywords_everywhere-resultaten). Librarian ontvangt voortaan ook demand.
(d) **Promotion join**: `klaar voor creatie` = scout-research klaar én
    Librarian-approved. Beide gates moeten groen zijn voor verdere verwerking.
(e) **Venv repair**: nieuw venv bouwen vanuit volledige `requirements.txt`,
    verifiëren dat 297 tests groen blijven.

**KennisScout — follow-up**

(a) **OpenAlex relevance-sort hybride**: nu gesorteerd op citaties; overweeg
    hybride (relevance-score + citatie-floor). Niet blind flippen: 3-punter
    (drempel bepalen, recency-spanning, test-set voor vergelijking).
(b) **cost-taxonomie voor gratis-laag-met-dagquota**: huidig schema (`free` /
    `rate_limited` / `credits`) vangt dagquota-grenzen niet. Extra label of
    `daily_limit`-veld overwegen.
(c) **Observatie-run**: downstream-effect van de nu-gevulde grounding zien —
    Librarian-beslissingen met KennisScout-bewijs, `keyword_evidence`-events,
    herbeoordeelde escalaties.

**Wiring-gaps (observatie-run 2026-06-19)**

(a) **Ronnie blind voor de dag (prioriteit)**: het bulletin abonneert alleen op
    het `dag_begint`-event van de TimeKeeper, niet op `pulse_completed` /
    `gsc_pulse_completed` / Field Note. Gevolg: het schreef "stille dag" terwijl
    negen inwoners draaiden. Mens-gerichte output zonder gate, dus een vals
    venster op het dorp. Fix: Ronnie op de pulse-events abonneren.
(b) **locale ontbreekt in de GSC-flow**: PerformanceScout publiceert
    `keyword_proposed` zonder locale in de demand, dus KennisScout grondt met
    `locale=""` (geen taalsleutel). Fix: PerformanceScout een locale laten
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
