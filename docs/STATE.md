# NoochVille — State & Handover (2026-06-17)

## Waar we staan

- Code op ~10, 263 tests groen (suite groeide fors sinds 14 juni: 221 → 263).
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

## Afgesloten 15 juni

Vijf commits, alle tests groen (216 op het laatst gemeten punt, mogelijk
221 na inbox-handler).

- Noochie-misfire fix: markdown-bold ontsnapte de startswith-check in
  _weigh_in, waardoor positieve missie-alignment-oordelen via
  sense_tension als spanning de B-route ingingen. Vervangen door
  gestructureerd VERDICT/REASON-patroon, consistent met
  coherentiepoort. parse_verdict_reason geëxtraheerd als gedeelde
  helper in coherence.py.

- Hygiëne-veeg: log-niveau drop-paden in _funnel_c_proposal info ->
  warning, module-level import voor evaluate_coherence in inhabitant.py.

- LLM-timeout plus exception-handling: native 30s timeout op Anthropic
  en Gemini, "except: pass" vervangen door warning-logging. Tweede
  silent-fallthrough patroon van de week opgeruimd, na de Noochie-fix.
  Lost impliciet ook de openstaande observatie "geen timeout op
  llm.reason in _funnel_c_proposal" op: de client time-out gooit een
  exception, reason() vangt die als None, _funnel_c_proposal sluit
  fail-closed — geen oneindige wacht meer op de geboorte-naad.

- Inbox-CLI means_gap-approve handler: mens kan means_gap-items
  goedkeuren met skill_name + rationale + alternatives_considered,
  voorstel gaat via Village.submit_proposal door de gate.
  5-seconden-timeout op gate-uitkomst. Resolutievelden in inbox-item
  (skill_added, rationale, alternatives_considered, resolved_by).

- Documenten: visie_noochville.md (vier pijlers, doelgroep,
  eindplaatje), ontwerp_governance_ritueel.md (concept, plus inzicht
  mens-als-rol en tweedeling eigenaar/rolhouder).

Bovenop de vijf code-commits (Noochie-fix, hygiëne-veeg, LLM-timeout,
inbox-handler, STATE.md afsluiter ochtend) zijn er vier strategische
documenten gemaakt en gecommit:

- docs/visie_noochville.md: vier pijlers (missie is de baas, mens-AI
  harmonie, missie-strategisch fundamenteler, drie maturity-lagen) plus
  doelgroep en eindplaatje.

- docs/option_value_noochville.md: option-value-afspraak NoochVille
  als 100-uur-investering over 10 weken, evaluatie op 24 augustus
  2026 met drie reflectievragen. Reminder ingepland.

- docs/ontwerp_governance_ritueel.md: concept-ontwerp mens-getriggerd
  governance-ritueel plus mens-als-rol-inzicht plus tweedeling
  eigenaar/rolhouder. Wacht op herlezing Holacracy v5 constitution.

- docs/ontwerp_kennislaag.md: concept-ontwerp drie rollen (ingestie,
  librarian per cirkel, domein-rapporteurs) op basis van
  Ahrens/Zettelkasten-vertaling naar mens-LLM-werkverdeling.
  Pull-request principe voor cross-cirkel kennis.

Middag en avond (na de afsluiter ochtend):

- Vier strategische documenten gecommit: docs/visie_noochville.md
  (vier pijlers), docs/option_value_noochville.md (100 uur, 10
  weken, reminder 24 augustus), docs/ontwerp_governance_ritueel.md
  (concept met mens-als-rol-tweedeling), docs/ontwerp_kennislaag.md
  (drie rollen, Ahrens-vertaling, cirkel-libraries).

- Nieuwe rol Ronnie de Reflector (ESFJ-dorpschroniqueur): roles.py
  uitgebreid plus skills_impl/bulletin_schrijven.py, dagelijks
  bulletin op dag_eindigt-event, markdown-output in data/bulletins/.
  TimeKeeper aangepast: _first_ring vlag plus dag_eindigt-publicatie
  voor elke dag_begint behalve de eerste. Twee village-runs
  succesvol uitgevoerd, twee bulletins geschreven.

- Ronnie verbreed: means_gap_sensed toegevoegd aan _TRACK, Field
  Note lezen bij dag_eindigt (met fallback), guardrail
  'verzin niets' in prompt. Twee bulletins vergeleken: eerste
  was charmant maar verzon een zonsopgang, tweede was feitelijk
  én warm met expliciete 'ik weet nog niet precies waar dit over
  gaat' bij onvolledige informatie. Guardrail werkt.

- Metrics-referentiekader vastgelegd: docs/metrics_noochville.md
  met drie meet-categorieën (systeemgezondheid, activiteit,
  kwaliteit), niet-automatisch, kompas voor evaluatie 24 augustus.

## Afgesloten 16 juni

Twee commits, beide kennis-laag-fundament.

- LibraryListSkill in SkillRegistry: nieuwe skill in
  nooch_village/skills_impl/library_skills.py, geregistreerd in
  village.py. Default-statussen approved + insight_statement,
  optioneel locale-filter. 5 tests groen. Backward-compatible:
  gebruikt .get() voor toekomstige velden (locale, concept_id,
  gemet_id) die nog niet bestaan in library.json entries.

- scripts/library_cleanup.py: CLI-tool voor cleanup van escalated
  entries via vijf clusters (nooch-typo, food-noise, authority-noise,
  vegan-risico, missie-adjacent). Dry-run produceert tabel plus
  review-file, --apply blokkeert op PENDING, schrijft via
  library.curate(). 6 tests groen. Echte dry-run op data/library.json
  toonde: 21 automatisch forbidden, 31 PENDING voor Stefan
  (9 vegan-risico, 6 missie-adjacent, 16 overig).

- migratie-script library_migrate_v2: idempotente migratie die drie
  nullable velden (locale, concept_id, gemet_id) toevoegt aan elke
  library-entry. 3 tests groen. Daadwerkelijk uitgevoerd op
  data/library.json: 69/69 entries gemigreerd, geen commit van
  data-bestand (gitignored).

- Ahrens-fundament gelegd: PermanentNote Pydantic-model en
  NotesStore in nooch_village/. Minimaal model met zes velden
  (id, claim, source, source_date, created_at, links_to, tags),
  geen status/GEMET/versioning. 4 tests groen. seed_first_notes
  script schreef zes echte notes naar data/notes.json: vijf
  atomaire claims uit de pillar "Vegan sneakers: what they are
  and what's inside" plus één claim uit customer insights deck.
  Link-integriteit gecontroleerd, geen dangling refs. Eerste
  end-to-end-test van het kennislaag-fundament in praktijk.

## Afgesloten 17 juni

Plan-uur plus woord-vinder-machine.

- Plan-uur uitgevoerd: dependency-diagram getekend voor alle 11
  te-bouwen functies. Drie onafhankelijke ketens (GEMET, insights,
  woord-vinder). GEMET-track geparkeerd voor na 24 augustus
  (5 SP). Resterende 6 SP verdeeld in twee tracks: insights
  (3.5 SP) en woord-vinder (2.5 SP). Woord-vinder gekozen voor
  eerst, want sneller operationeel.

- Term-extractor gebouwd (scripts/extract_terms.py): LLM-gebaseerde
  extractie van kandidaat-termen uit een tekstbestand, filtering
  tegen library. Aangescherpte prompt sluit geografie, procesbegrip
  en eigen merknaam uit. 4 tests groen.

- Review-tabel + --apply toegevoegd aan extract_terms.py: zelfde
  patroon als library_cleanup. Schrijft data/extract_review_
  YYYY-MM-DD.json met PENDING-decisions, --apply blokkeert tot
  alle PENDING vervangen zijn door escalated/forbidden/ignore.
  5 nieuwe tests, 255 totaal. Machine 3 (woord-vinder) operationeel.

- Bug-fix in extract_terms: strip markdown-fence van LLM-output.
  Wijziging werd ongevraagd door Claude Code gedaan tijdens een
  test-run, achteraf geaccepteerd vanwege technische correctheid
  maar gemarkeerd als afwijking van stop-regel-discipline.

- Eerste echte test op pillar-content "What is a plant-based shoe
  actually made of?": 18 termen geëxtraheerd, 0 bekend, 18 nieuw.
  Stefan triageerde handmatig via JSON-bewerking: 7 escalated,
  3 forbidden, 8 ignored. Library uitgebreid van 69 naar 79
  entries.

## Afgesloten 17 juni (blok 2): wachters en governance-consistentie

- Audit-trail-gat noochie_weighed_in gedicht (commit `77885e0`):
  `self.bus.subscribe("noochie_weighed_in", self._observe)` toegevoegd
  aan Village. Regressietest `test_audit_trail.py` bewaakt dit: haalt
  de subscribe-regel weg → test rood om de juiste reden (beide kanten
  gevalideerd).

- library_list via governance-amend toegekend aan librarian-record:
  `amend_role`-voorstel (proposer: human-cli) doorliep G0-G4, werd
  direct aangenomen, Secretary schreef record naar v3. Audit-trail
  toont `proposal_id=41142db48186/65dc8945ace9` (twee runs, idempotent
  op skills). `governance_records.json` is gitignored runtime-state;
  de governance-weg zelf is het bewijs.

- Wachter `test_record_registry_consistentie.py` toegevoegd: controleert
  dat elke skill in elk governance-record ook bestaat in de SkillRegistry.
  Both-ways gevalideerd: in-memory injectie van "zzz_spook" geeft spook-
  lijst `['librarian:zzz_spook']`; schijf bleef ongewijzigd (v3).

## Afgesloten 17 juni (blok 3): Plausible verrijkt

- `plausible_stats` (GrowthAnalyst) verrijkt: aggregate haalt nu
  visitors/pageviews/visit_duration (bounce_rate eruit). Vier resiliente
  breakdowns toegevoegd: top_pages (event:page), sources (visit:source),
  countries (visit:country), utm_sources (visit:utm_source), limit=10.
  Falende breakdown valt terug op [] — de puls wordt nooit afgebroken door
  een netwerk- of rate-limit-fout op een breakdown. Fixture-getest (5 golden
  responses), resilience-test met geïnjecteerde exception. Suite 257 → 263.
  FieldNoteSkill-prompt uitgebreid (commit `c8833ee`): LLM krijgt nu
  expliciete instructie om bezoekduur, top-pagina's, bronnen, landen en
  UTM-bronnen te verwerken. Rijkdom stroomt automatisch door naar Ronnie
  (die de volledige field note als tekst leest). Blok 3 daarmee dicht.

- Geparkeerd ontwerp (niet gebouwd): rol-model gesneden op de website-grens.
  Rol 1 "website-performance" draagt Plausible EN GSC (gedrag op de site plus
  hoe mensen ons vinden; later ook 404/conversie/broken links). Rol 2 kijkt
  naar buiten (bredere zoekvraag, pytrends). Huidige code wijkt af: Plausible
  op GrowthAnalyst, GSC op PerformanceScout. Consolidatie plus hernoeming is
  een toekomstige governance-herstructurering.
  - GSC zit op de grens: "queries die clicks brachten" hoort bij Rol 1, de
    "hoge impressies, lage CTR"-kansensnede bij Rol 2. Eén bron, twee rollen,
    via aparte skills op gedeelde OAuth-plumbing.
  - pytrends = toekomstige Rol-2-skill (eerder TrendScout genoemd).
  - GSC search terms (must-have) komen NIET uit de Plausible Stats API maar
    uit GSC zelf; eigen verrijkingsblok op gsc_performance, zelfde patroon.

## Afgesloten 17 juni (blok 4): analyst-record opgeschoond

- `analyst`-record naar v8 via governance amend (G3-escalatie → founder
  approve → Secretary adopt → governance_changed). Purpose aangescherpt:
  "Data en inzicht omzetten in bruikbaar advies dat Nooch.earth gezond,
  vindbaar en groeiend houdt." Twee accountabilities verwijderd:
  "maandrapportage opstellen voor stakeholders" (gedekt door dagelijkse
  Field Note, geen aparte skill) en "taalgebruik per locale bewaken"
  (geen skill-dekking, wens voor later). Vijf keepers over: pairs_sold-
  goal-derived, bezoekersdata duiden, locale-analyse, dagelijkse Field
  Note, site monitoren. Skills ongemoeid.

- MBTI ISTJ vastgelegd als rol-karakter (documentatie; RoleDefinition
  heeft nog geen veld voor MBTI of leesbare naam).

- Geparkeerd (drie):
  * Rol-metadata/persona-laag: leesbare naam los van role_id, plus
    MBTI-veld. Binnenkort oppakken nu de rollen nog weinig zijn, vóór
    het duurder wordt.
  * google_trends migreert naar de toekomstige naar-buiten-rol (rol 2
    in het website-performance-vs-naar-buiten-ontwerp uit blok 3).
  * verkoopdoel_2026_q4 hoort op context/missie-niveau, gediend door
    alle rollen vanuit hun eigen verantwoordelijkheid, niet als
    accountability van één rol. Apart uitdenken. De pairs_sold-
    accountability op analyst blijft tot dan ongemoeid.

## Afgesloten 18 juni

Stap 1 cockpit (read-only) gebouwd en gecommit. Drie schone commits.

- **Cockpit read-only** (`nooch_village/cockpit.py`, commit `2b14988`): stdlib
  `http.server`, geen nieuwe dependency, bindt uitsluitend op `127.0.0.1` en
  weigert een niet-lokale host. Geen schrijfpad (`POST` = 405). Leest de drie
  stores read-only via `Records`/`HumanInbox`/`ProjectLedger` (zelfde patroon als
  `inbox/__main__.py`) en rendert één platte HTML-pagina: roster, inbox, proces.
  Pure `gather` + `render_html`, server apart. 6 tests in `tests/test_cockpit.py`.
  Draaien: `python -m nooch_village.cockpit`, dan `http://127.0.0.1:8765`.
- **Ontwerpnotitie** `docs/ONTWERP_cockpit_rol_skill_werkbank.md`: cockpit als
  mens-kant van de auth-grens, twee activiteiten (authoring versus
  review-dan-submit), twee harde grenzen (alles via de gate, skills mint je niet
  vanuit de UI), bouwvolgorde read-only, authoring, gesensede review, lichte triage.
- **Test-fix** (commit `fd9ce10`): `_FakeVillage` kreeg een `context` zodat de
  means_gap-approve test slaagt zonder de productie-handler te versoepelen. Een
  Claude Code-poging om `inbox/__main__.py` te wijzigen met een
  `try/except AttributeError` (productie verzwakken voor een incomplete fake) is
  teruggedraaid; de fout is in de test gerepareerd waar hij hoort. 269 groen.
- **Discipline**: twee slips gevangen door de stop-regel, een verkeerd gelabelde
  verzamel-commit en de bovenstaande productie-versoepeling, beide rechtgezet
  vóór commit.

Cockpit-bevindingen uit de eerste live run:

- **means_gaps staan op deferred, niet pending.** `ngram_2019_cutoff`,
  `openlibrary_v2`, `nl_corpus_coverage` plus de `Missie_alignment_ok_*`-reeks
  zijn deferred. De oude stap 2 ("approve `ngram_2019_cutoff` via de inbox-CLI")
  is daarmee geblokkeerd: `resolve()` weigert non-pending. Pending-inbox leeg, gezond.
- **`tijdgeest_wachter` v64, `kennis_scout` v50.** Vermoedelijk fossiel van de oude
  `amend_role`-churn van vóór de means-gap-routing. Te verifiëren: bumpt een puls
  die versies nog? Zo niet, dood en begraven.
- **analyst discovery-project `blocked`, `blocked_on=analyst`, sinds 14 juni.** De
  open event-handshake (`b88d2ddaea33`): Noochie's advies bereikt de analyst niet
  terug. Nu zichtbaar zonder commando.
- Verfijning genoteerd: cockpit-header telt alleen pending als "open"; deferred
  apart tellen (deferred is geparkeerd, niet done).

**Volgende:** cockpit stap 2 (rol/skill-authoring) per de ontwerpnotitie. De oude
genummerde stap 2 (`ngram_2019_cutoff` approve) eerst un-deferren of via de
governance-route, niet via inbox approve.

## Afgesloten 18 juni (blok 2): CI, bug-fix, deps, keywords_everywhere

- **CI opgezet** (``.github/workflows/ci.yml``): GitHub Actions op de Noochville-repo,
  advies-modus, Python 3.14 (matcht lokaal), draait ``pytest -q`` op elke push.
  Branch-plus-CI is nu de werkflow.

- **Bug gevangen die lokaal onzichtbaar was**: ``Inhabitant._stop`` (een
  ``threading.Event``) botste met ``threading.Thread._stop`` → ``TypeError: 'Event'
  object is not callable`` bij ``join()``, alleen in CI. Hernoemd naar ``_stop_event``
  (commit ``0f394e0``). Les: nooit een ``Thread``-subclass-attribuut ``_stop`` (of
  andere Thread-internals) noemen.

- **``requirements.txt`` structureel compleet gemaakt**: was lazy/gemockt. Gedeclareerd
  met gepinde versies: ``pydantic>=2.0,<3``, ``anthropic==0.109.1``,
  ``google-genai==2.8.0``, ``google-api-python-client==2.197.0``,
  ``google-auth-oauthlib==1.4.0``.

- **``keywords_everywhere``-skill gebouwd** (spec-first, branch ``skill/keywords-everywhere``,
  CI-groen, gemerged op main, commit ``82b072b``): haalt echte search volume, CPC,
  competitie en 12-maands trend per keyword uit de Keywords Everywhere API.
  ``cost="credits"`` — nooit in de dagpuls; on-demand op gecureerde shortlist.
  ``side_effect_free=True``. 6 tests in ``tests/test_keywords_everywhere.py``.

- **Scout v3** — ``keywords_everywhere`` toegekend via ``amend_role``-voorstel
  (proposer ``human-cli``, proposal ``5980bc58f3fa``), volledig door G0-G4, Secretary
  geadopteerd, DNA live herladen. Skills: ``['gsc_performance', 'gsc_report',
  'keywords_everywhere']``. 279 tests groen.

## Openstaand / let op (18 juni blok 2)

- **Venv is gebroken** (wijst naar oud ``~/Downloads/noochville``-pad). ``./venv/bin/python``
  werkt, ``./venv/bin/pip`` niet — gebruik ``python -m pip``. Fix: recreëren uit de
  nu-complete ``requirements.txt`` en controleren dat het 279 blijft.
- **``KEYWORDS_EVERYWHERE_API_KEY`` moet in ``.env``** (regenereren; oude sleutel is
  in een chat-sessie verschenen).
- **``pandas>=2.0`` trekt in CI al ``pandas 3.0.3`` binnen**; gemockt dus geen pijn,
  overweeg een cap (``pandas>=2.0,<3``).
- **cost-gate** (puls weigert ``cost != "free"``): blijft genoteerd, niet gebouwd.

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

1. **Governance ritueel bouwen** — na herlezing Holacracy v5 constitutie
   (art. 3 + 4). Ontwerp staat in `docs/ontwerp_governance_ritueel.md`
   (commits `adf0044`, `f4e33ab`). Bevat: mens-getriggerd ritme, Secretary
   als agenda-gids, tweedeling eigenaar vs rolhouder (eigenaar buiten
   governance, Stefan-rol volledig erin), inzicht mens-als-rol met open
   vragen over inbox vs projectenbord. Eerst constitutie herlezen, dan
   implementatie.
2. **means_gap approve testen op echt item**: `ngram_2019_cutoff` in de inbox
   heeft nu een handler. Eerst `role_id` controleren (item aangemaakt vóór
   `bf10ca0` — heeft nog geen `role_id` in context, fallback via `classify_gap`
   treedt in werking). Via `python -m nooch_village.inbox approve <id>`.
3. **LLM-trechter voor C-en verdachte-B-spanningen**: governance-voorstel pas na
   LLM-coherentiecheck, ook B-spanningen met lage score (< 0.20) erdoor sturen.
4. **Slimme WIP** (prioriteit-eviction, backpressure) + **synthesizer-rol** die
   open spanningen batcht en de hefboom kiest.
5. Cockpit aan live data hangen (records/inbox/proces), met de auth-grens erin.
6. CI: pytest bij elke commit.
7. `openlibrary_v2`-activatie NIET reflexief goedkeuren: API is per-boek, niet
   corpus-breed. Laat onbemand tot er een echte per-boek use case is.
