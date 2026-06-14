# CLAUDE.md — NoochVillage

Projectcontext en spelregels voor Claude Code. Lees dit eerst, samen met `README.md`
en (indien aanwezig) `docs/CONTEXT.md` voor de missie van Nooch.earth.

## Wat dit is

NoochVillage is een event-driven "dorp" van autonome inwoners (rollen) met echte skills,
gebouwd voor Nooch.earth (duurzaam schoenenmerk, organische groei via missie-gedreven SEO).
Inwoners pakken autonoom werk op dat bij hun doel en accountabilities past, kunnen elkaar
om hulp vragen, en samenwerken aan een hoger doel. Het governance-model is gebaseerd op
Holacracy.

Dit is een werkende kern, geen simulatie: de skills doen echt I/O.

## Draaien

```bash
python -m nooch_village.village          # demo: snelle hartslag, toont de Field Note
python -m nooch_village.village once      # één echte groei-puls en stoppen (voor cron)
python -m nooch_village.village run       # blijft draaien, puls 1x per echte dag
```

Altijd starten vanuit de map die `nooch_village/` bevat, en met de `-m`-vorm.
Niet `python nooch_village/village.py` (dan breken de imports). Laat de `__init__.py`'s staan.

## Architectuur (drie lagen)

1. **Het marktplein** — `EventBus` (`event_bus.py`): broadcast van feiten/aankondigingen. Autonomie: inwoners reageren zelf op events die hen aangaan.
2. **De postbus** — `Inbox` per inwoner (`inbox/__init__.py`): toegewezen werk dat áf moet. Betrouwbaarheid.
3. **De matchmaker** — `Matchmaker` (`matchmaker.py`): hoort "wie kan dit?" en legt werk in de inbox van een capabele inwoner.

Kerncomponenten:
- `models.py` — `RoleDefinition` (DNA), `Record` (de waarheid), `Task`, `Response`, `Tension`, `RecordType`.
- `inhabitant.py` — `Inhabitant` (leaf, één rol) en `Circle` (composite). Methodes: `handle`, `ask`, `use_skill`, `sense_tension`, `tick`, `react`, `reload`.
- `roles.py` — gespecialiseerde inwoners: `TimeKeeper` (hartslag → `dag_begint`), `GrowthAnalyst` (ochtend-puls).
- `governance.py` — `Records` (json, de waarheid), `Secretary` (records bijhouden, geen veto), `Reconciler` (bouwt het levende dorp uit de records).
- `skills.py` — `Skill` (ABC) + `SkillRegistry`. `skills_impl/` bevat de echte skills.
- `config.py` — `Context` (de rugzak/DI) + `load_context` (leest `config/settings.ini` en `.env`).
- `llm.py` — optionele LLM-redenering (Anthropic of Gemini), valt terug op None zonder key.

Data (allemaal in `data/`, gitignored):
- `governance_records.json` — de bron van waarheid over wie bestaat en wat ze mogen.
- `output/field_note_<datum>.md` — de dagelijkse Field Note.
- `last_pulse.json` — basislijn voor spanning-detectie. `budget.json`, `system_log.jsonl` (audit-trail).

## HARDE REGELS (niet schenden zonder overleg)

1. **Eén rol per inwoner** (leaf). `Circle` is een composite; van buiten is een cirkel gewoon een rol. Het dorp ZELF is de wortelcirkel, zodat een subcirkel later gratis nest.
2. **De EventBus wordt ALTIJD geinjecteerd** (`self.bus`). NOOIT een global singleton importeren of gebruiken. Dit is de enige discipline die geneste cirkels later mogelijk houdt.
3. **Records = de waarheid, levende inwoners = een projectie.** De `Reconciler` bouwt het dorp uit de records. Meer verantwoordelijkheid krijgen = record amenderen (version bump) + `reload()` van DNA. GEEN respawn, geen state die alleen in de thread leeft.
4. **De Secretary heeft GEEN veto.** Een voorstel wordt aangenomen tenzij het structureel ongeldig is. (Dit is de structurele poort. De volledige IDM met objectronde komt later, zie roadmap.)
5. **Skills zijn echt en worden geinjecteerd via de `SkillRegistry`.** Geen mock-data die echte calls dood-codeert. Een skill faalt liever bewust "closed" dan dat hij iets verzint.
6. **Inbox = toegewezen werk** (via de matchmaker). **Events = aankondigingen** (autonomie). **`tick()` = zelf-geinitieerd werk** (hartslag). Houd die drie gescheiden.
7. **Een cirkel heeft geen handen: hij delegeert.** Laat een `Circle` nooit zelf werk uitvoeren in `handle`; hij routeert naar een member.
8. **Niet de oude `src/`-generaties terughalen.** Die repo had drie onderling botsende base-classes (`Role` vs `BaseAgent`), drie versies van het datamodel, en een Plausible-agent met de echte API-call dood-gecodeerd áchter een `return` met mock-data. Dat is bewust vervangen.
9. **Inwoners reageren op events via `self.react(event_name, handler)`, nooit direct via `self.bus.subscribe`.** De `react()`-wrapper deponeert het event-job in de eigen inbox; de handler draait dan op de eigen thread van de inwoner, niet op die van de afzender. Zo blokkeert een `publish()` nooit en werken inwoners parallel. Uitzonderingen (infra): `Matchmaker`, `Secretary`, `Reconciler` mogen direct subscriben — ze hebben lichte, snelle handlers zonder blocking I/O.
10. **Sensing en zelfverbetering produceren UITSLUITEND spanningen en voorstellen.** Een inwoner mag via `_reflect()` gaten signaleren en `amend_role`/`add_role`-voorstellen doen. Hij mag NOOIT zelf nieuwe code schrijven, nieuwe threads starten, nieuwe skills registreren, of nieuwe externe API's aanroepen buiten zijn eigen `skills`-lijst. Uitbreiding van capaciteit is altijd mens-gated — identiek aan de geboren-versus-bemenst-splitsing voor rollen.

## Herkomst (source) van Records en Proposals

Elk `Record` en elk `Proposal` draagt een `source`-veld dat aangeeft waar het vandaan komt:

| Waarde | Betekenis | Voorbeelden |
|--------|-----------|-------------|
| `"seed"` | Handmatig gedefinieerd bij oprichting | `noochville`, `timekeeper`, `analyst`, `librarian`, `scout`, `facilitator` |
| `"sensed"` | Echte spanning, gevoeld door een inwoner of via governance ingedient door de mens | `tijdgeest_wachter` (menselijk voorstel), toekomstige sensed rollen |
| `"demo"` | Aangemaakt door een test-/demofunctie, niet productie-relevant | `content_strategist` (uit `lifecycle_demo`) |

### Regels

- **Productie draait idealiter alleen op `seed` en `sensed` records.** `demo`-records zijn synthetisch en mogen niet meetellen in botsings-checks.
- **Gate G1 en G2 negeren `demo`-records** bij domein- en accountability-botsingen. Een sensed voorstel voor een content-rol wordt niet geblokkeerd omdat `content_strategist` (demo) toevallig een overlappende accountability heeft.
- **`migrate_records()` markeert bekende demo-records retroactief** (`content_strategist` → `"demo"`) én zet seed-records zonder source op `"seed"`. Idempotent.
- **`lifecycle_demo()`-proposals krijgen expliciet `source="demo"`.** De geboren rol erft die source via de Secretary.
- **Purge-commando:** `python -m nooch_village.village purge` archiveert alle `source="demo"` records en verwijdert ze uit hun ouder-cirkel. Idempotent.
- **Roster-commando:** `python -m nooch_village.village roster` toont alle records met hun source (legende: `✱` = sensed, `⚙` = demo, blanco = seed).

### Startup-log

Bij `Inhabitant.run()` wordt de source gelogd: `ontwaakt [source=seed] | purpose=…` zodat je in de startup-output direct ziet of een rol seed, sensed of demo is.

## Taal als eersteklas as

Taal is een structurele dimensie van het systeem, geen implementatiedetail.

### Meertalig Lexicon (`nooch_village/lexicon.py`, data in `data/lexicon.json`)

Elk missie-begrip bestaat als een **concept** met een stabiele id en een woord per taalvak:

```python
{
  "concept_id": "consumer_frame",
  "words": {"nl": "consument", "en": "consumer"},
  "status": "avoid",
  "rationale": "Consumentenkader versterkt passiviteit; burgerframe heeft voorkeur."
}
```

**Sleutelregels:**
- **Status geldt symmetrisch over alle talen.** Is `consument` `avoid`, dan is `consumer` dat ook. Framing-regels zijn concept-eigenschap, niet woord-eigenschap.
- **Eén bron, beide talen.** `word_for(concept_id, lang)` geeft het taalspecifieke woord; `words_for_lang(lang)` alle woorden voor een taal.
- **De Librarian cureert** (`add_concept`, `add_words`); anderen lezen vrij. Zelfde domein-eigenaarschapsregel als voor de Library.
- **`seed_lexicon()`** laadt 7 zaad-concepten idempotent bij opstarten: `burger_frame`, `consumer_frame`, `sufficiency`, `regenerative`, `plastic_free`, `sustainable`, `vegan`.
- **context.lexicon** is het injectie-punt; altijd beschikbaar na `Village.__init__`.

**Nieuw concept toevoegen** (via Librarian governance of seed):
1. `lexicon.add_concept(concept_id, {"nl": "...", "en": "..."}, status="approved", ...)` of toevoegen aan `_LEXICON_SEED` in `village.py`.
2. Zowel het NL- als EN-woord worden automatisch als zaad gebruikt door ngram, Trends, etc.

### Skills segmenteren per locale

Elke data-skill heeft een notie van de locales die hij ondersteunt:

| Skill | Locale-dimensie | Hoe |
|-------|----------------|-----|
| `ngram_culture` | Taal per corpus: NL → corpus 10, EN → corpus 26 | Woorden uit `context.lexicon.words_for_lang(lang)` per corpus |
| `google_trends` | Geo per geo-code: NL/BE → nl, GB/US/AU/CA → en | `geos=[...]` payload; per geo de locale-woorden uit Lexicon |
| `gsc_performance` | Locale afgeleid van het site-domein (.nl → nl, anders en) | Elke query-row draagt een `locale`-sleutel |
| `plausible_stats` | Segmentatie op `country` beschikbaar via Plausible API | Nog niet geïmplementeerd |

**Output-formaat:** alle skills produceren `rows` met expliciete locale-sleutels:
```python
{"term": "vegan", "locale": "en", "corpus": 26, "signal": {"direction": "stijgend"}, ...}
# of bij ontbrekende data:
{"term": "plasticvrij", "locale": "nl", "corpus": 10, "no_data": True, "reason": "term niet gevonden in corpus"}
```

**Drie regels:**
1. **Geen data ≠ nul.** `no_data: True` met `reason` onderscheidt afwezige data van interest=0 of een vlak signaal. Fail-closed per locale-segment.
2. **Forceer geen segment.** Een bron zonder taal-dimensie (bijv. Plausible country, GSC zonder language-filter) krijgt geen gesimuleerde locale.
3. **NL-woorden in NL-bronnen, EN-woorden in EN-bronnen.** De woorden per locale komen altijd uit het Lexicon; nooit een NL-woord aan een EN-corpus aanbieden.

### Taal van een output

De taal van een output volgt de context:
- **Rapportage aan de mens** (Field Note, voorstel, rationale): taal van de mens (nu NL).
- **Content-analyse**: taal van de data-bron (ngram EN corpus → EN termen in het event).
- **`keyword_proposed`-events** dragen een `locale`-sleutel zodat de Librarian weet in welke taal het woord thuishoort.

### Simulatie

```bash
python -m nooch_village.village simulate
```

Voert 7 fasen opeenvolgend uit: Roster+Lexicon → Governance → Triage → Reflectie →
Ngram live NL+EN → Librarian → Herkomst. Externe API-aanroepen (ngram) zijn beperkt
tot 3 termen voor snelheid.

## Een nieuwe skill toevoegen

1. Maak `skills_impl/<naam>.py` met een `Skill`-subklasse (`name`, `description`, `run(self, payload, context) -> dict`).
2. Registreer hem in `village.py` (`self.registry.register(...)`).
3. Ken de capability via governance toe aan een inwoner (in de demo: een `propose_amendment`-event met `add_skills=[...]`; bij seed: in de `skills`-lijst van het record).

## Een nieuwe inwoner toevoegen

1. Voeg een `Record` toe in `seed_records` (of via een governance-voorstel), met `parent="noochville"` en de juiste `skills`.
2. Zet de id in de `members`-lijst van de wortelcirkel.
3. Wil de inwoner eigen gedrag (zoals de puls)? Maak een `Inhabitant`-subklasse in `roles.py` en zet hem in `CLASS_MAP` in `village.py`. Anders wordt het een generieke `Inhabitant`.

## Governance (Holacracy) — model en status

- **Rollen** hebben een purpose, accountabilities, domeinen en skills (`RoleDefinition`). **Cirkels** bevatten rollen.
- **Spanningen** zijn de motor: elke inwoner kan er een sensen (`sense_tension`). Triage: operationeel → de inwoner handelt autonoom; governance → een voorstel dat de structuur wijzigt.
- **Domeinen = "libraries".** Lezen is vrij (via `context`); cureren/wijzigen is het exclusieve recht van de eigenaar. Dit is de enige Holacracy-uitzondering waarin toegang beperkt is.
- **Twee poorten** bij een voorstel: procedureel (Holacracy-geldigheid) én inhoudelijk (de Nooch-waarden uit `CONTEXT.md`). Houd die gescheiden.
- **Status nu:** structurele poort via de Secretary. **Nog niet gebouwd:** de volledige IDM (clarifying → reaction → objection-round met de vier validiteitscriteria → integration), Lead Link / Rep Link, en geneste governance per cirkel.

## De ontdekkingslus voor zoekwoorden (actief)

Twee onafhankelijke bronnen voeden dezelfde lus elke ochtend:

```
Bron 1 — Google Trends (GrowthAnalyst):
  TrendsSkill haalt data op (zaad: keywords.txt + goedgekeurde bibliotheekwoorden)
    → GrowthAnalyst._propose_related() publiceert keyword_proposed per nieuwe related query

Bron 2 — Google Search Console (PerformanceScout):
  GscPerformanceSkill haalt last-28-days queries op (dimensie: query)
    → PerformanceScout._propose_from_gsc() publiceert keyword_proposed per nieuwe high_potential query

Beide bronnen → Librarian:
  → KeywordReviewSkill toetst aan de missie (heuristiek of LLM met bewijs als demand)
    → approved  → in bibliotheek → volgend puls-zaad voor Trends via _read_keywords
    → forbidden → in bibliotheek → nooit meer voorgesteld
    → escalated → in bibliotheek → spanning naar mens, ook niet meer voorgesteld
```

Betrokken bestanden:

- `skills_impl/trends.py` — `_read_keywords` laadt naast `config/keywords.txt` ook alle
  goedgekeurde woorden uit `context.library`. `top_related` is `[{"query": str, "value": int}]`.
- `skills_impl/gsc.py` — `GscPerformanceSkill` (`gsc_performance`): OAuth via token.json
  (`GSC_TOKEN_PATH` in .env, scope `webmasters.readonly`), site via `GSC_SITE`. Geeft per
  query terug: impressions, clicks, positie en bucket (page1 / high_potential / low_ranking /
  content_gap). Faalt closed als token of site ontbreekt.
- `roles.py` — `GrowthAnalyst._propose_related()`: Trends-gerelateerde queries → Librarian.
- `roles.py` — `PerformanceScout._propose_from_gsc()`: GSC high_potential queries → Librarian.
  Publiceert `gsc_pulse_completed` zodat de demo op beide inwoners kan wachten.
- `roles.py` / `skills_impl/library_skills.py` — `Librarian` + `KeywordReviewSkill` ongewijzigd.
- `library.py` — `Library` slaat elke beslissing op in `data/library.json`.

Dedup-garantie: `lib.status(term) is not None` blokkeert hervoorstel voor ALLE statussen
(ook `escalated`). Beide bronnen controleren dit zelfstandig vóór ze publiceren.
Zelfversterkend: goedgekeurde woorden worden automatisch extra Trends-zaad.

GSC-token genereren (eenmalig, interactief):
```bash
./venv/bin/python -c "
from google_auth_oauthlib.flow import InstalledAppFlow
SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly']
flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
creds = flow.run_local_server(port=0)
open('gsc_token.json', 'w').write(creds.to_json())
"
```
Zet daarna `GSC_TOKEN_PATH=./gsc_token.json` en `GSC_SITE=sc-domain:jouwsite.nl` in `.env`.

## Intentielaag — missie, strategie, doelen en prioritering

De intentielaag maakt duidelijk waarom het dorp bestaat en hoe agents keuzes maken.
Ze bestaat uit vijf lagen, van zwaar naar licht:

| Laag | Wat | Eigenaar | Hoe afgedwongen |
|------|-----|----------|-----------------|
| **Missie** | Anchor Circle purpose: het duurzaamste schoenenmerk ter wereld zijn, om een industrie vol menselijk, dierlijk en planetair leed te laten zien dat meliorisme echt kan | Founder | G4-guard: elk voorstel dat de Anchor-purpose raakt escaleert ALTIJD naar de mens |
| **Policies** | Harde grenzen op de Anchor Circle: geen advertising, alleen nooch.earth, on-demand productie, geen plastic/leer | Founder via records | G4-poort + `intent.prioritize()` markeert overtredingen als `dropped` |
| **Strategie** | Heuristieken: organisch boven betaald, langetermijn-keywords, eigen website | Founder | `config/strategy.json` — bewerkt direct, niet via governance |
| **Doelen** | Tijdgebonden targets: 1000 paar schoenen Q4 2026 via nooch.earth | Founder | `config/strategy.json` — agents rangschikken acties op doelbijdrage |
| **Structuur** | Rollen, cirkels, accountabilities | Agents via governance | G0-G4-poort + Secretary + Reconciler |
| **Operatie** | Dagelijks autonoom werk binnen de rol | Agents | Vrij binnen bovenstaande kaders |

**Prioriteitsvolgorde (hard ingebakken):**
Missie > Policy > Strategie > Doel. Een doel mag nooit een policy of de missie overrulen.
Botst een doel met een policy (bijv. verkoopdoel dreigt niet gehaald zonder advertising),
dan escaleert de agent naar de mens — de strategie wordt nooit gebroken.

**`config/strategy.json`** is mens-bewerkbaar en wordt bij elke `load_context` ingeladen in `context.strategy`.
Het bevat `strategy` (lijst heuristieken) en `goals` (lijst tijdgebonden targets met `metric`, `target`, `window_start/end`, `active`, `contributes_via`).

**`nooch_village/intent.py`** — `prioritize(actions, context) -> list[dict]`:
- Acties met een policy-schending (`_POLICY_VIOLATIONS`) krijgen `dropped=True`.
- Overige acties scoren op doelbijdrage (`contributes_via`-signalen) + strategie-afstemming.
- Gesorteerd: niet-afgevallen eerst (op score desc), afgevallen achteraan.
- GrowthAnalyst gebruikt dit om gerelateerde Trends-keywords te rangschikken vóór ze worden voorgesteld.

## Rol-lifecycle: hoe een nieuwe rol het dorp binnenkomt

Een `add_role`-voorstel doorloopt een afwijkend pad ten opzichte van andere governance-wijzigingen.

### Geboren versus bemenst
Een aangenomen `add_role` **schrijft alleen de roldefinitie** naar de records (purpose, accountabilities, domeinen). De rol wordt **onbemand geboren**: er draait geen thread, er is geen live inwoner. Pas als een menselijke ontwikkelaar de bijbehorende implementatie heeft geschreven én geregistreerd in `CLASS_MAP` én `SkillRegistry`, kan de Reconciler de rol activeren als live inwoner. Dit is de **enige plek waar adopt-by-default niet geldt**: draaiende autonome code is niet omkeerbaar zoals een record-edit dat is.

### Activatie is altijd mens-gated
Het schrijven en registreren van code voor een nieuwe rol vereist menselijke goedkeuring vóórdat de rol draait. Een agent mag een rol-definitie draften via governance; een mens tekent af op de code. De Reconciler (`_on_governance_changed`) controleert bij elke `add_role` of `CLASS_MAP` een entry heeft:
- Ja → activeer als live inwoner (thread start)
- Nee → sla op in `reconciler.unmanned`, geen thread

### Onbemande rol als signaal
Zolang een rol onbemand is, vallen zijn accountabilities toe aan de founder (Circle Lead, Holacracy 1.4.2). De stapel `reconciler.unmanned`-rollen is het vraagsignaal of een rol bemenst moet worden. Het groeidagboek (`data/groeidagboek.jsonl`) toont welke rollen wanneer geboren zijn en waarom.

### Anti-proliferatie (G0-poort)
Een `add_role`-voorstel vereist **bewijs van herhaling** in zowel `trigger_example` als `rationale`. Zonder herhalingswoorden (bijv. `meermaals`, `terugkerend`, `structureel`, `wekelijks`) wijst G0 het voorstel af als **ongeldig** (terug naar de proposer, geen menselijk oordeel). Één incident is onvoldoende grond voor een nieuwe structurele rol.

### Groeidagboek
Bij elke `add_role`-adoptie publiceert de Secretary een `role_born`-event. De Village schrijft dit naar `data/groeidagboek.jsonl` met `role_id`, `purpose`, `trigger_example`, `rationale` en tijdstempel. Zo is de ontwikkelgeschiedenis van het dorp terug te lezen.

## Triage — hoe een inwoner een spanning classificeert en routeert

`Inhabitant.triage(tension)` classificeert in deze volgorde (eerste match wint):

| Prio | Signaal | Actie |
|------|---------|-------|
| 1 | Structureel/terugkerend trefwoord (`_STRUCTURAL_KW`) of LLM="structural" | `_raise_governance_proposal()` → `proposal_raised` → Facilitator + G0-G4 |
| 2 | Overlap ≥6 tekens met eigen purpose/accountabilities, of LLM="own" | `_do_own_work()` — log, geen verdere actie (werk is al in scope) |
| 3 | Domein-match bij andere rol (sterkste signaal), dan accountability-overlap ≥6 tekens, of LLM="other:<id>" | `_route_to_role()` → `ask(cap, ...)` of broadcast `tension_routed` |
| 4 | Geen match | `_try_tactical_or_escalate()` → `ask("assistance", ...)` → Matchmaker → `human_intervention_needed` |

`sense_tension(description, kind)` publiceert eerst `tension_sensed` (audittrail), dan roept hij `triage()` aan.

Scheiding van verantwoordelijkheden:
- **Triage ≠ Poort**: triage classificeert *wie* het werk uitvoert; G0-G4 toetst *of* een voorstel geldig is. De ene roept de andere aan; ze dupliceren elkaars logica niet.
- **Operationeel vs. governance**: structureel terugkerende spanning → governance; eenmalig werk → operationeel. De grens ligt bij de trefwoorden in `_STRUCTURAL_KW`.
- **Default is tactisch**: als geen rol past, escaleer pas naar de mens nadat het tactisch geprobeerd is via de Matchmaker. Zo blijft het dorp zelf-redzaam.

## TijdgeestWachter — culturele taalverschuiving observeren

De TijdgeestWachter is geboren via het eerste echte governance-voorstel van de founder
(`python -m nooch_village.village proposal`). Hij observeert de lange culturele boog van
de wereldtaal via het onofficiële JSON-endpoint van Google Books Ngram Viewer (data t/m ~2019).

### Rol en grenzen
- **Observeert** de frequentie van missie-relevante termen over decennia (corpus EN 26 of NL 10).
- **Voedt** GrowthAnalyst en Librarian via `keyword_proposed` (stijgende termen) en
  `tijdgeest_signaal` (opvallende verschuiving ≥ 2 termen in dezelfde richting).
- **Claimt het lexicon-domein NIET**: de Librarian cureert; de TijdgeestWachter voedt alleen.
- **Ritme**: productie = wekelijks (`tijdgeest_interval_seconds = 604800`);
  demo/test: stel `tijdgeest_interval_seconds=0` in `settings.ini` of via `context.settings`.

### Skill: `ngram_culture` (`skills_impl/ngram.py`)
- Zaad-termen: `burger`, `consument`, `sufficiency`, `regenerative`, `plastic-free` +
  alle goedgekeurde bibliotheekwoorden (automatisch zelfversterkend).
- Corpus-detectie: `_NL_INDICATORS` → corpus 10 (NL 2012); anders corpus 26 (EN 2019).
- Signaal: `slope_recent` (laatste 10 jaar) geeft `stijgend` / `dalend` / `vlak`.
- Fail-closed: bij netwerk- of parse-fouten per term `{"error": str(e)}`; geen mock-data.
- Beleefde aanroep: 1,5s sleep tussen batches (onofficieel endpoint).

### Events
| Event | Wie publiceert | Inhoud |
|-------|---------------|--------|
| `tijdgeest_pulse` | mens/demo | Handmatige trigger; optioneel `{"terms": [...]}` payload |
| `tijdgeest_pulse_completed` | TijdgeestWachter | `ok`, `stijgend`, `dalend`, `terms` (volledige details) |
| `tijdgeest_signaal` | TijdgeestWachter | `stijgend`, `dalend`, `boodschap` — bij ≥ 2 verschuivingen |
| `keyword_proposed` | TijdgeestWachter | Per stijgende term nog niet in de bibliotheek |

### Demo draaien
```bash
# Stap 1: zorg dat het governance-record bestaat (eenmalig)
python -m nooch_village.village proposal

# Stap 2: draai de echte ngram-puls
python -m nooch_village.village ngram
```

De ngram-demo wacht maximaal 90 seconden op de API-response. Na afloop toont hij een
per-term tabel met corpus, richting (stijgend/dalend/vlak), recente helling en frequentie.

### Implementatie-aantekeningen
- `activate_tijdgeest_wachter(records)` in `village.py` voegt `ngram_culture` idempotent
  toe aan het record zodra het bestaat.
- `CLASS_MAP["tijdgeest_wachter"] = TijdgeestWachter` — de Reconciler activeert de rol
  automatisch als het record in governance aanwezig is.
- Dedup via `lib.status(term) is not None` — ook stijgende termen worden nooit dubbel voorgesteld.

## Gap-sensing — drie niveaus van spanning

Sensing is niet "een incident melden" maar "een gat observeren". Elk inwoner senst op drie niveaus:

| Niveau | Wat | Trigger | Voorbeeld |
|--------|-----|---------|-----------|
| **Doel-voortgang** | Werkelijke trend vs. vereiste run-rate voor actief doel | Elke puls (GrowthAnalyst) | Bezoekers 3 pulsen dalend terwijl Q4-doel nadert |
| **Missie-gat** | Wat ontbreekt om de missie te dienen (geen rol, geen meting, geen koppeling) | Periodieke reflectie | pairs_sold niet meetbaar in de puls |
| **Zelf-gat** | Eigen capaciteit vs. eigen accountabilities | Periodieke reflectie | ngram_culture stopt in 2019; 7 jaar blind |

**Doel-voortgang (GrowthAnalyst, elke puls):**
- Schrijft bezoekers naar `data/pulse_history.jsonl` (rolling history)
- Theorie-gat: als de doel-metriek niet meetbaar is → eenmalig sensen, daarna elke 14 dagen
- Off-pace: ≥3 opeenvolgende dalende pulsen → spanning; bij één hobbel niet
- State in `data/goal_state.json` (deduplicatie)

**Periodieke reflectie (elke inwoner, eigen ritme):**
- `Inhabitant._maybe_reflect()` → reageert op `dag_begint`, bewaakt `_reflect_interval` (default: 7 dagen)
- `Inhabitant._reflect()` → stub; subklassen overschrijven met specifieke gaten
- `Inhabitant._sense_gap(gap_key, description, min_count, force)`:
  - `min_count=2` (default): ruis-filter; pas spanning bij ≥2 opeenvolgende observaties
  - `force=True`: structureel bekende limieten (altijd waar, geen herhaling nodig)
  - State per rol in `data/reflect_<rol_id>.json`
- Demo: `python -m nooch_village.village reflect` (stel `reflect_interval_seconds=0` in voor directe trigger)

**Hoe een spanning er na gap-sensing uitziet:**
- Doel-gap → `sense_tension(kind="operational")` → triage → meest waarschijnlijk eigen-werk of mens-escalatie
- Missie-gap → `sense_tension(kind="governance")` + "accountability:" in beschrijving → triage → `_raise_governance_proposal` → `AMEND_ROLE` of `ADD_ROLE`
- Zelf-gap → identiek aan missie-gap; het voorstel amendeert de eigen rol

## Roadmap (depth-first, niet breadth-first)

1. **Echte missie-redenering aanzetten** in de Field Note (zet een LLM-key in `.env`).
2. **Skills porten** uit de oude repo: GSC (`get_gsc_data.py`), Trustpilot (`trustpilot_agent.py`), Serpstat, en de SQLite-`repository.py` als opslaglaag.
3. **Volledige IDM-governance** (objectronde + de twee poorten).
4. **Web**: vervang de in-memory `EventBus` door een netwerk-bus (WebSocket/SSE) en de `Inbox` door een server-queue. Beide zitten al achter een interface.
5. **Mens in het dorp**: een `HumanProxy`-inwoner die taken naar een UI stuurt en op het antwoord-event wacht. Voor de rest van het dorp niet te onderscheiden van een agent.

Principe: maak eerst één inwoner één ding echt waardevol doen (de groei-puls is het sjabloon), bewijs de waarde, en schaal pas daarna in de breedte.

## Governance: async en adopt-by-default

### Rolverdeling
- **Facilitator** draait het proces: ontvangt `proposal_raised` via `self.react()`, voert de G0-G4 poort uit, beslist adopt of escaleren. Oordeelt NOOIT over inhoud, alleen over de deterministische poort.
- **Secretary** bezit de records en de adoptie-schrijfactie: schrijft de change, verhoogt de versie, publiceert `governance_changed`. Direct `bus.subscribe` (infra, lichte handler).
- **Reconciler** herbouwt het levende dorp na `role_adopted` (compat) en `governance_changed`.

### De poort G0-G4 (goedkoop-eerst, deterministisch tegen de records)
| Poort | Wat | Uitkomst bij falen |
|-------|-----|--------------------|
| G0 | Veldgeldigheid: change.kind ∈ scope, verplichte velden aanwezig | `proposal_invalid` terug naar proposer, geen mens |
| G1 | Domein-botsing: nieuw domein overlapt met bestaande rol | Escaleer naar mens |
| G2 | Accountability-duplicaat: al bij een andere rol | Escaleer naar mens |
| G3 | Verweesd werk: verwijdering zonder elders te beleggen | Escaleer naar mens |
| G4 | Missie-poort: plastic/leer-goedkeuring of overproductie + optioneel LLM | Escaleer naar mens |

Slaagt alles: direct aannemen. **Bezwaren worden NOOIT automatisch geïntegreerd** — alleen de mens kan een geëscaleerd voorstel goedkeuren (via `governance_verdict: approve`).

### Proposal-model
`Proposal` heeft: `proposer_role`, `change` (GovernanceChange met `kind` ∈ {add_role, amend_role, remove_role, add_policy, amend_policy, remove_policy}), `tension`, `trigger_example` (VERPLICHT audittrail), `rationale`, `status`, `created_at`. Escalaties bewaren `escalation_gate` en `escalation_reason`.

### De missie leeft in de Anchor Circle
De wortelcirkel heeft een `purpose` die de Nooch-missie verwoordt en `policies` (harde policies waartegen G4 toetst). Governance wijzigt alleen structuur; operatie blijft autonoom binnen de rol (artikel 4 van Holacracy).

### Events
| Event | Wie publiceert | Betekenis |
|-------|---------------|-----------|
| `proposal_raised` | iedereen | Nieuw voorstel, Facilitator reageert |
| `proposal_gate_passed` | Facilitator | Alle G0-G4 geslaagd → Secretary adopteert |
| `proposal_invalid` | Facilitator | G0 faalde, terug naar proposer |
| `governance_review_requested` | Facilitator | G1-G4 faalde, wacht op menselijk oordeel |
| `governance_verdict` | mens/proxy | `{proposal_id, decision: approve|reject, reason}` |
| `governance_changed` | Secretary | Change aangenomen en geschreven naar records |
| `governance_rejected` | Secretary | Mens wees voorstel af |

## Harde grens: zelfverbetering stopt bij voorstellen

Dit is de meest kritieke architectuurgrens in het systeem en mag NOOIT worden overschreden.

### Wat een inwoner WEL mag
- Een gat signaleren via `sense_tension` of `_sense_gap`
- Een `amend_role`- of `add_role`-voorstel genereren dat beschrijft wat een nieuwe bron of capaciteit zou doen
- In dat voorstel een URL of bron noemen als audittrail voor de mens
- Via triage en governance het voorstel laten beoordelen door de Facilitator

### Wat een inwoner NOOIT mag
- Zelf nieuwe code schrijven, uitvoeren of laden (ook geen `exec`, geen dynamische imports van externe modules)
- Zelf een nieuwe externe API of databron aanroepen die niet al in zijn `skills`-lijst staat
- Een nieuwe `Skill`-subklasse instantiëren of registreren in de `SkillRegistry`
- Een nieuwe thread starten voor een nieuwe capaciteit

### Waarom (dezelfde reden als bij rollen)
De geboren-versus-bemenst-splitsing geldt voor **capaciteit**, niet alleen voor rollen. Net als een `add_role`-voorstel een rol definitie schrijft maar geen thread start, schrijft een `amend_role`-reflectie-voorstel een accountability maar start geen nieuwe API-verbinding. De drempel voor draaiende code is altijd menselijke goedkeuring plus handmatige registratie.

**Voorbeeld:** TijdgeestWachter signaleert via `_reflect()` dat de ngram-databron stopt in 2019. Hij schrijft een voorstel "accountability: aanvullende recente bron evalueren". Het voorstel wordt aangenomen → de accountability staat in het record. De implementatie (bijv. Wikipedia API of een nieuwere corpus) vereist menselijke code + registratie in `SkillRegistry` + `CLASS_MAP`. Tot dan is de accountability een "belofte aan de mens", geen draaiend systeem.

**In code:** `Inhabitant._reflect()` bevat een docstring die dit expliciet verwoordt. Elke subklasse die `_reflect()` overschrijft MOET dit patroon respecteren.

## Human inbox — het geauthenticeerde lokale approval-oppervlak

`HumanInbox` (`human_inbox.py`) is de persistente wachtrij voor beslissingen die menselijke goedkeuring vereisen.
State in `data/human_inbox.json` (gitignored). CLI: `python -m nooch_village.inbox`.

### Twee item-typen

| Type | Wanneer | Voorbeeld |
|------|---------|-----------|
| `escalation` | Governance-voorstel dat G1-G4 niet passeerde | Domein-botsing bij een `add_role` |
| `activation` | Sensed onbemande rol zonder `CLASS_MAP`-entry | `kennis_scout` geboren via governance |

### CLI-commando's

```bash
python -m nooch_village.inbox              # toon pending items
python -m nooch_village.inbox list         # idem
python -m nooch_village.inbox all          # alle items incl. gesloten
python -m nooch_village.inbox show <id>    # volledig item met activatieplan / gate-context

python -m nooch_village.inbox approve <id> [reden]   # zie effecten per type hieronder
python -m nooch_village.inbox reject  <id> [reden]
python -m nooch_village.inbox amend   <id> <tekst>   # sluit het item + instructie voor herindiening
python -m nooch_village.inbox defer   <id> [reden]   # uitstellen, blijft geregistreerd
```

### Effecten per actie × type

| Actie | escalation | activation |
|-------|-----------|-----------|
| `approve` | `governance_verdict approve` op de bus → Secretary adopteert direct | Green-light; toont stappenplan voor handmatige implementatie |
| `reject` | `governance_verdict reject` op de bus → Secretary markeert voorstel afgewezen | Item gesloten; geen code |
| `amend` | Item amended + instructie om voorstel aangepast her in te dienen | Idem voor activatieplan |
| `defer` | Uitgesteld; blijft in `data/human_inbox.json` | Idem |

### Beveiligingsgrens (nooit te doorbreken)

- Approvals en activaties mogen **uitsluitend** op dit geauthenticeerde lokale oppervlak bevestigd worden.
- Geen extern of ongeauthenticeerd kanaal (mail, Slack, webhook) mag een approval triggeren.
- Komt er later notificatie bij, dan is die altijd alleen een **heads-up** met context en een link terug naar de CLI — nooit een approve-knop.

### Activatie-approval ≠ code-review

Een `approve` op een activatie-item green-light de implementatie: de mens heeft besloten dat de rol gebouwd mag worden. Dit **vervangt de per-edit code-review niet**. Iedere stap in het activatieplan (skill-bestanden, klasse in `roles.py`, `CLASS_MAP`-entry) passeert daarna nog de normale code-review voordat hij commit en draait.

### Dedup-garanties

- `add_escalation` dedupliceerde op `proposal_id` — hetzelfde voorstel wordt nooit tweemaal toegevoegd.
- `add_activation` dedupliceerde op `role_id` + status `pending` of `approved` — de KennisScout blijft één item, ook na herstarts.
- `sync_unmanned()` wordt bij elke Village-start aangeroepen zodat nieuwe onbemande rollen automatisch in de inbox verschijnen.

## KennisScout — academische grounding van lexicon-termen

De KennisScout grondt kandidaat-termen in wetenschappelijke literatuur en publiceert
`keyword_evidence`-events voor de Librarian en GrowthAnalyst. Hij beslist en cureert nooit.

### Status: v1 actief

| Skill | Capability | Bron | Key vereist |
|-------|-----------|------|-------------|
| `skills_impl/openalex.py` | `openalex_evidence` | OpenAlex (keyless, polite pool) | Nee — `openalex_mailto` uit config |
| `skills_impl/semantic_scholar.py` | `semscholar_tldr` | Semantic Scholar Graph API | Nee — optioneel `SEMANTIC_SCHOLAR_API_KEY` in `.env` |
| `skills_impl/openlibrary_search_inside.py` | `openlibrary_search_inside` | OpenLibrary boeken-voltekst | Nee — **gepland voor v2**, nog niet in KennisScout DNA |

### OpenAlex (`openalex_evidence`)

- `GET https://api.openalex.org/works?search=TERM&sort=cited_by_count:desc&mailto=<email>`
- `openalex_mailto` uit `context.settings` (settings.ini of .env); fallback `info@nooch.earth`
- Resultaten gesorteerd op citaties (meest geciteerd eerst)
- Abstract gereconstrueerd vanuit inverted index
- `no_data: True` als API 0 resultaten teruggeeft (onderscheiden van netwerk-fout)

### Semantic Scholar (`semscholar_tldr`)

- `GET https://api.semanticscholar.org/graph/v1/paper/search?query=TERM&fields=title,abstract,year,citationCount,tldr`
- `tldr`-veld: machinaal gegenereerde één-zinsamenvatting per paper
- Geen key vereist (~100 req / 5 min gratis); zet `SEMANTIC_SCHOLAR_API_KEY` in `.env` voor hogere limieten
- Exponentiële backoff bij HTTP 429 (max 4 pogingen); daarna fail-closed

### Termen komen uit het Lexicon

De KennisScout reageert op `keyword_proposed`-events. Die events worden gestuurd door
TijdgeestWachter, GrowthAnalyst en PerformanceScout — die halen hun termen op hun beurt
uit het Lexicon. De `locale`-sleutel in `demand.locale` geeft aan in welke taal de term thuis hoort.

### Librarian-integratie

De Librarian luistert ook op `keyword_evidence`. Als een term eerder `escalated` was maar
nu KennisScout-bewijs beschikbaar is, herbeoordeelt de Librarian de term automatisch.

### Demo

```bash
python -m nooch_village.village kennis_scout
```

Haalt approved lexicon-termen op (max 3 NL + 3 EN) en toont per term:
- OpenAlex: aantal werken, topics en citaties
- Semantic Scholar: paper-titels en tldr-samenvattingen

### v2-roadmap

- OpenLibrary voltekst (`openlibrary_search_inside`) toevoegen aan KennisScout DNA
- Approval via human inbox; daarna handmatige registratie in `activate_kennis_scout()`

## Schaal-naden (grenzen die je later kunt opentrekken, nu niet schenden)

Dit zijn de vier plekken waar de architectuur later kan groeien zonder bestaande code te herschrijven:

| Naad | Nu | Later |
|------|----|-------|
| `EventBus` | in-memory, gesynchroniseerd | WebSocket/SSE netwerk-bus; geen wijziging aan inwoners |
| `Inbox` | `Queue` per thread | Redis/SQS server-queue; interface ongewijzigd (`deliver`, `enqueue`, `take`, `done`) |
| `Library` | JSON-bestand | database of API; achter dezelfde `Library`-interface |
| Cirkel-scope | één wortelcirkel | geneste cirkels; de `inner_bus`-injectie maakt dit gratis |

Discipline: schrijf nooit code die aanneemt dat de bus in-memory is, dat de inbox een lokale queue is, of dat er maar één cirkel-niveau bestaat.

## Conventies

- Python 3.10+. `from __future__ import annotations` boven in modules.
- Dataclasses voor interne modellen; Pydantic mag voor ingest-data (zie oude `SeoOpportunity`).
- Nederlandse comments/logs zijn prima.
- Geen global mutable state. Alles wat een inwoner nodig heeft komt via de constructor (`bus`, `registry`, `context`).
