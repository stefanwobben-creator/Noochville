# NoochVille — State & Handover (2026-06-15)

## Waar we staan

- Code op ~10, 221 tests groen.
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
  Drie observaties:
  1. **Stub-afhankelijkheid verspreid**: twee bestaande C-pad tegenproef-tests
     (`test_truly_new_gap_reaches_add_role_path`, `test_uncovered_gap_reaches_add_role_via_two_strike_gate`)
     en één unit-test (`test_c_funnel_passes_new_gap_key`) waren stil afhankelijk
     van de stub (altijd True). Na invulling braken ze; alle drie zijn bijgewerkt
     met `patch("nooch_village.llm.reason", return_value="VERDICT: coherent\n...")`.
  2. **Poort vereist altijd een mock in tests**: elke toekomstige test die het
     C-pad t/m publish wil valideren moet `llm.reason` mocken. Geen key →
     fail-closed → geen publish. Dit is het gewenste gedrag in productie, maar
     het is een impliciet contract dat bij nieuwe tests niet vanzelf zichtbaar is.
  3. **`llm.reason` swallowt intern al uitzonderingen en geeft `None` terug**:
     de `except Exception`-tak in `_funnel_c_proposal` vangt alleen uitzonderingen
     die `reason` zelf gooit (bijv. importfout). De `None`-tak vangt API-down en
     interne fouten. Beide paden zijn getest via mock (`side_effect=RuntimeError`
     resp. impliciet via `return_value=None`). Geen overlap, geen gat.

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

- **Misfire gezien: `Missie_alignment_ok_Reg`** landde als means_gap terwijl het een
  content-analyse-output is (keyword-review-rationale vanuit een LLM-response).
  Afgewezen als ruis (182742a069c0). Te onderzoeken later: waar in de routing kwam
  dit als means_gap binnen — vermoedelijk: een C-gap-beschrijving met een gestileerde
  rationale die als capaciteitsbeschrijving werd doorgegeven, of een B-gap-route die
  niet de juiste bronbeschrijving filterde. De fix is een filter op de
  `means_gap_sensed`-payload vóór `add_means_gap` (bijv. max-lengte, geen markdown-
  opmaak, of expliciete `accountability:`-prefix vereisen als correctheidsindicator).

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
- **Durable-reject bevestiging, blocked-project recovery, smart WIP,
  requirements-dev.txt**: open uit vorige sessies, ongewijzigd.
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

- ~~**LLM-timeout op `llm.reason`**~~ — opgelost in commit `851c7da` (15 juni).
  Native 30s timeout op Anthropic en Gemini; exceptions worden gelogd als warning.

- ~~**Inbox-CLI gat voor means_gap-approve**~~ — opgelost in commit `bf10ca0` (15 juni).
  Handler aanwezig; `Village.submit_proposal` + 5s timeout + resolution-velden.
  Resterende kanttekening: handler start een volledige Village (alle inwoners + threads)
  voor één submit. Lichte variant (alleen Secretary + Facilitator) bestaat niet als
  losse constructie. Zelfde patroon als bestaande `escalation`- en `keyword`-handlers —
  consistente schuld, geen nieuw gat.

- **Diepere ontwerpvraag uit Noochie-misfix**: een missie-alignment-rode-vlag
  (`"niet_ok"`) gaat nu via `sense_tension` de operational-route in en belandt
  zo in `classify_gap` en mogelijk de B-route. Maar een missie-rode-vlag is
  geen capaciteitsgrens; het hoort waarschijnlijk een eigen kanaal te krijgen
  (escalation naar governance? eigen event-type?). Te onderzoeken later. Voor
  nu blijft het bestaande pad: de fix van 15 juni stopt alleen de false
  positives (positieve oordelen die per ongeluk als spanning werden gerouteerd).

## Evaluatie-checkpoints

### B-observer pad — beslissing na ~1-2 weken data

- Wanneer beslissen we of de coherentiepoort blokkerend wordt op B, observerend
  blijft, of weggaat?
- Kalibratie-criterium nog te kiezen: vals-positieven (vague-verdict op
  legitieme means-gaps) versus vals-negatieven (coherent-verdict op rommel).
- Concreet: na de eerste week B-observer logs handmatig doornemen, per
  observer-verdict checken of de mens dezelfde beslissing zou hebben genomen.
  Bij ≥X% overeenstemming overwegen naar blokkerend. Drempel X nog te bepalen
  op basis van werkelijk aantal items in de logs.

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

### Openstaande observaties C-trechter / coherentiepoort

- Geen timeout op `llm.reason` in `_funnel_c_proposal`: bij hangende LLM blijft
  de geboorte-naad wachten. Relevant zodra meer rollen tegelijk sensen.
  *(log-niveau en functie-scope import opgelost in commit `38a2243`)*

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

## Volgende stappen

1. **Governance ritueel bouwen** — na herlezing Holacracy v5 constitutie
   (art. 3 + 4). Ontwerp staat in `docs/ontwerp_governance_ritueel.md`.
   Eerst open vragen beantwoorden, dan implementatie.
2. **means_gap approve testen op echt item**: `ngram_2019_cutoff` in de inbox
   heeft nu een handler. Eerst `role_id` controleren (item aangemaakt vóór
   `bf10ca0` — heeft nog geen `role_id` in context, fallback via `classify_gap`
   treedt in werking). Via `python -m nooch_village.inbox approve <id>`.
3. **Echte supervised live run met sleutels**: sluitstuk van de lus. Plausible +
   Google Trends + LLM écht aanroepen, one-shot controleren, dan vrijgeven.
4. **LLM-trechter voor C-en verdachte-B-spanningen**: governance-voorstel pas na
   LLM-coherentiecheck, ook B-spanningen met lage score (< 0.20) erdoor sturen.
5. **Slimme WIP** (prioriteit-eviction, backpressure) + **synthesizer-rol** die
   open spanningen batcht en de hefboom kiest.
6. Cockpit aan live data hangen (records/inbox/proces), met de auth-grens erin.
7. CI: pytest bij elke commit.
8. `openlibrary_v2`-activatie NIET reflexief goedkeuren: API is per-boek, niet
   corpus-breed. Laat onbemand tot er een echte per-boek use case is.
