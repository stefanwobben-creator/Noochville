# NoochVille — Changelog

## Afgesloten 2026-07-04: Mother-Earth-aardbol, UI-opschoning, governance-fix + metrics-diagnose

Zeven kleine gemergde PR's (elk branch → PR → squash-merge → deploy op Hetzner, suite groen: 1548)
plus een diagnose-ronde op het metrics-dashboard.

- **Governance-meeting sluit nu écht** (#8, `ed77524`): de groene "Governance meeting"-knop bleef
  groen na sluiten omdat `rov2_end` alleen geconsenteerde voorstellen verwerkte en open agendapunten
  liet staan. `rov2_end` haalt nu ook de resterende agendapunten van díe cirkel van de agenda
  (scoped; andere cirkels ongemoeid). +2 regressietests.
- **Live NASA-EPIC-aardbol** op de Mother-Earth (anchor) overview, in het DOMAINS-blok (#9–#11):
  - `nooch_village/epic.py`: `latest_frames()` (metadata, 1u in-memory cache) + `frame_bytes()`
    (volle EPIC-PNG ophalen → met Pillow naar 512px resizen → 1u cache per frame-id). Key uit
    `os.getenv("NASA_API_KEY")`, blijft server-side; frames via eigen route `/epic/frame`.
    Fail-closed op geen-key/API-/Pillow-fout → nette muted-fallback. `Pillow>=11` toegevoegd.
  - Widget alleen op de anchor; 8 frames gesampled over de héle dag (volle rotatie, ook Europa),
    trage cross-fade (4s), UTC-onderschrift. CSS `.epic-earth/.epic-frame/.epic-cap` (geen inline
    styles): bijna kolombreed, rond, geen rand, `scale(1.25)` zodat de zwarte marge wegvalt.
- **UI-opschoning:**
  - Geen "Geen domein."-placeholder meer onder de aardbol op de anchor (#12).
  - Maturity-status-cirkels (groen/geel/grijs) uit de tab-navigatie + de dode "Nog te bouwen"-
    placeholder (`_todo`) en bijbehorende CSS opgeruimd (#13).
  - Legenda (werkt/basis/nog te bouwen) onder de organisatie-boom in de rechter-rail weg (#14).
  - Seen-marker (gewijzigd-sinds-laatst-gezien) bewust behouden.
- **Metrics-dashboard gediagnosticeerd** (alleen bevindingen, geen fix — besluit volgt):
  1. Er is géén "over tijd"-grafiek: Chart.js bestaat niet; de enige viz is een 84×22px inline-SVG
     sparkline (`_spark_svg`), die wél rendert mét variërende data. Wat ontbreekt is een echt
     grafiek-component.
  2. "bezoekers (7D)" negeert de periodefilter: de metric is vast 7-daags (`visitors_7d` uit de
     Plausible-puls, `period` hard `7d`); de filter kan het venster niet wijzigen, en alle samples
     zijn <7 dagen oud. Aggregaat-werktegels negeren `cutoff` volledig (all-time), reeks-tegels
     wel → inconsistent. Werkoverleg-cijfers (8.6/10 tevredenheid, 5.1 min duur) zijn échte
     werk-log-data (geen seed), maar dun/scheef (tevredenheid op 4/16 records; `duur_min` =
     8×0 min + 1×60 min-uitschieter).

## Afgesloten 2026-06-19: Academische grounding live

KennisScout grondt nu elke binnenkomende term tegen twee echte bronnen:
OpenAlex (gezag, citatie-rang) en Semantic Scholar (relevante recente
literatuur plus tldr). Beide sockets stonden al in het DNA (v50) en waren al
bedraad in `_on_keyword_proposed`; ze misten alleen authenticatie.

- **openalex.py**: van keyless/polite-pool (sinds 13-02-2026 stil gebroken,
  409 na de 100-credit testtoelage, door KennisScout als warning weggeslikt)
  naar key-auth (`api_key` in URL), `needs_secret=True`, `cost "free"` →
  `"rate_limited"`, 429-backoff gekopieerd uit `semantic_scholar.py`.
  Pre-existing bug meegefixed: `per-page` → `per_page` (limit gaf default 25).
- **`semantic_scholar.py`**: ongewijzigd, was al key-ready; key in `.env`,
  `x-api-key`-header actief.
- **Live-bevestigd** op "plant-based leather": beide bronnen geven echte hits.
  Gemerged naar main, CI groen. Geen governance-amend nodig.
- **Inzicht**: de twee bronnen zijn complementair, niet redundant. De
  "bedraad beide"-keuze boven "kies er een" werd door de rooktest gevalideerd.
- **Geparkeerd**: OpenAlex relevance-sort hybride (relevance + citatie-floor)
  als bewuste 3-punter met recency-spanning en drempel-test; cost-taxonomie
  vangt "gratis-laag-met-dagquota" nog niet.

## Afgesloten 18 juni (blok 2): CI, bug-fix, deps, keywords_everywhere

- **CI opgezet** (`.github/workflows/ci.yml`): GitHub Actions op de Noochville-repo,
  advies-modus, Python 3.14 (matcht lokaal), draait `pytest -q` op elke push.
  Branch-plus-CI is nu de werkflow.

- **Bug gevangen die lokaal onzichtbaar was**: `Inhabitant._stop` (een
  `threading.Event`) botste met `threading.Thread._stop` → `TypeError: 'Event'
  object is not callable` bij `join()`, alleen in CI. Hernoemd naar `_stop_event`
  (commit `0f394e0`). Les: nooit een `Thread`-subclass-attribuut `_stop` (of
  andere Thread-internals) noemen.

- **`requirements.txt` structureel compleet gemaakt**: was lazy/gemockt. Gedeclareerd
  met gepinde versies: `pydantic>=2.0,<3`, `anthropic==0.109.1`,
  `google-genai==2.8.0`, `google-api-python-client==2.197.0`,
  `google-auth-oauthlib==1.4.0`.

- **`keywords_everywhere`-skill gebouwd** (spec-first, branch `skill/keywords-everywhere`,
  CI-groen, gemerged op main, commit `82b072b`): haalt echte search volume, CPC,
  competitie en 12-maands trend per keyword uit de Keywords Everywhere API.
  `cost="credits"` — nooit in de dagpuls; on-demand op gecureerde shortlist.
  `side_effect_free=True`. 6 tests in `tests/test_keywords_everywhere.py`.

- **Scout v3** — `keywords_everywhere` toegekend via `amend_role`-voorstel
  (proposer `human-cli`, proposal `5980bc58f3fa`), volledig door G0-G4, Secretary
  geadopteerd, DNA live herladen. Skills: `['gsc_performance', 'gsc_report',
  'keywords_everywhere']`. 279 tests groen.

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
  eigenaar/rolhouder. Wacht op herlezing Holacracy v5 constitutie.

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
