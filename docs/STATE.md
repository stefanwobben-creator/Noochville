# NoochVille — State & Handover (2026-06-28)

> STATE = huidige waarheid, vervang bij update. `docs/JOURNAL.md` = historie, append-only.

## Werkafspraken Pablo (AI-assistent)

1. **Rootcause eerst** — bij elk probleem eerst de fundamentele oorzaak benoemen voordat
   er een oplossing wordt voorgesteld. Vraag altijd: lost deze oplossing de rootcause op,
   of is het een pleister?

2. **Fundamentele keuzes voorleggen** — als een beslissing architecturele impact heeft,
   altijd de echte keuze benoemen met voor- en nadelen. Niet meegaan in de eerste richting
   zonder dit te doen.

3. **Symptoombestrijding benoemen** — als een voorgestelde oplossing een workaround is,
   dat expliciet zeggen en de structurele oplossing ernaast zetten.

4. **Pushback geven** — als Stefan een richting kiest die niet structureel is, zeg dat dan
   direct. Niet meegaan om tijd te besparen.

5. **Credits bewaken** — lange sessies met kringetjes zijn duurder dan één keer goed
   nadenken. Bij vastlopen: stop, analyseer, kies de juiste richting.

---

## Waar we staan (2026-06-28)

**Suite: 1333 tests groen**, 8 pre-existing failures (LLM/API-afhankelijk of test-isolatie-flaky,
bevestigd identiek op vorige commit). Elke stap met mutatie-check.

---

### Sessie 2026-06-28 (avond): cockpit2 architectuur-refactor — volledige split

cockpit2.py is van 5144 naar ~1400 regels gegaan. Alle view-functies leven nu in eigen modules.

**Commits in volgorde:**

| Brok | Bestand | Commit | Regels weg |
|------|---------|--------|-----------|
| 1 | cockpit2_util.py | 127b918 | 147 |
| 2 | views/feed.py | 77268d9 | 154 |
| 3 | views/werkoverleg.py | 1234a3b | 349 |
| 4 | views/roloverleg.py | 39b3f76 | 517 |
| 5 | views/checklists.py | db9eb5f | 149 |
| 6 | views/noochie.py | 529554e | 117 |
| 7 | views/catalog.py | 6b79055 | 164 |
| 8 | views/metrics.py | 09cabb6 | 869 |
| 9 | views/projects.py | (laatste) | 638 |
| 10 | views/overview.py | (laatste) | 524 |

**Bijvangsten per brok:**
- `_IC_CHECK`, `_IC_INFO`, `_IC_LINK`, `_IC_DL`, `_IC_DESC`, `_IC_CLOCK`, `_IC_FILE`,
  `_IC_TARGET` verhuisd naar cockpit2_util.py (waren late definities, nu overal direct beschikbaar)
- `_ICON_ADD_EMOJI`, `_person_name` naar cockpit2_util (circulaire import voorkomen)
- `os.path.dirname(__file__)` data-paden in views/metrics.py gecorrigeerd (één extra `..` nodig
  door nieuwe locatie in views/)
- Circulaire import bij standalone start (`-m`) opgelost: `_BUILD`, `_EXTRA_CSS`, `_CIRCLE_TABS`,
  `_ROLE_TABS` verhuisd naar cockpit2_util.py

**Wat er nog in cockpit2.py zit (bewust):**
- CSS/JS-constanten bovenin
- `_Stores`, `_bootstrap`
- `dispatch()` (~433 r) — alle POST-acties, nog niet gesplitst
- `make_handler`, `serve`, `main`

**Village-run na refactor (2026-06-28 ~22:45):**
- 64 seconden, 25 skills geregistreerd, 7 inwoners ontwaakt
- GSC: 152 queries opgehaald
- Harry Hemp: microplastics stijgend, 14 termen dalend, 7 OpenAlex-proxy-bogen voortgezet
- Concurrent-scan: LØCI 1M/mnd vs Nooch.earth 0/mnd
- Field Note geschreven → data/output/field_note_2026-06-28.md
- 9 kansen in human inbox (wachten op Stefan)
- Gemini 429-fouten: expected (gratis quotum uitgeput)
- Cockpit 1 op poort 8765, Cockpit 2 op poort 8766 — visueel gecontroleerd, beide werken

---

### Sessie 2026-06-28 (ochtend): cockpit2 brok B — KPI-composer focus-flow, metrics-tab opruiming

De aanmaakflow voor KPI's is volledig uit de metrics-tab getild en naar `/kpi_new` (de KPI-composer)
verhuisd. Metrics-tab is nu zuiver lees/uitvoer-oppervlak.

- **`_catalog_picker()` verwijderd** (~70 r)
- **KPI-composer: catalogus als tweede optgroup**
- **`_kpi_id_from_def()` idempotente get-or-create**
- **`retune_kpis_to_def()` afgeleid van `_SCHEMA_FIELDS`**
- **`_bron_html()` helper** — externe URLs klikbaar
- **Tabs**: `metrics` en `checklists` nu `live`
- **Build-timestamp in balk**
- **Catalogus-filter vereenvoudigd**
- **Opschoon-clusters getest en gecommit** (`ac7ef79`)

---

## Rolstatus (geïnventariseerd 2026-06-28)

| Rol | Status | Echte output | Ontbreekt |
|-----|--------|-------------|-----------|
| website_watcher | actief | Field note, Plausible-puls, SerpAPI-trends | Locale-segmentatie Plausible |
| trends | actief | GSC-queries → library | — |
| librarian | actief | Keyword-review, curate, verband-voorstel | — |
| harry_hemp | actief | Ngram + OpenAlex arc + Semantic Scholar grounding | — |
| concurrent_scout | actief | Competitor news + discover + linkbuilding | — |
| noochie | actief | Oordeel field note via LLM, bulletins | advise_metrics is hardcoded dict |
| facilitator | actief | Governance poort + opportunity-reflex per rol | — |
| the_source | onbemand | Founder-proxy (strategische beslissingen) | Volledig mens-gated by design |
| schoenen_voor_duurzame_evenementen_seo | onbemand | SEO-copy schrijven | Skills + CLASS_MAP-entry |
| tijdgeest_wachter | schaduw | (werk zit in HarryHemp) | Governance-record verouderd |
| kennis_scout | schaduw | (werk zit in HarryHemp) | Governance-record verouderd |
| codie | persona only | Code-implementatie | Geen governance-record, geen accs, geen skills |

**Enige echte functionele stub:** `advise_metrics` in Noochie — hardcoded dict van 4 metrics,
TODO staat er al in. Fix: LLM-stap die `strategy/goals` leest en rankt.

---

## Openstaande ontwerpschuld

### Brok 11 — dispatch splitsen (bewust uitgesteld)
`dispatch()` in cockpit2.py (~433 regels) handelt alle POST-acties af voor alle views.
Volgende stap: splitsen naar `views/dispatch_werkoverleg.py` etc., of één centraal `dispatch.py`
buiten views/. Pas aanpakken als je een rustige sessie hebt zonder draaiende village.

### Werkoverleg heeft geen automatische trigger
`WerkoverlegStore.open()` wordt alleen aangeroepen vanuit de HTTP-handler — als Stefan klikt.
Geen event, geen cron, geen inwoner die het zelf opent.

Wat ontbreekt:
1. `cadence_events()` uitbreiden met `week_begint` (weekday() == 0)
2. Facilitator reageert op `week_begint` en opent werkoverleg voor elke actieve cirkel

Blokkade: WerkoverlegStore leeft nu alleen in cockpit2 `_Stores` (HTTP-laag). Moet naar
Village-context verhuizen zodat het dorp er bij kan zonder HTTP.

Besluit: werkoverleg blijft mens-gestuurd (Stefan opent het 1x per week). Rollen mogen autonoom
werken maar hebben transparantieplicht. Zie ook: hybride Holacracy-ontwerp hieronder.

### Rommel en governance-schuld (geïnventariseerd 2026-06-28)

**Gearchiveerde governance-records (12 stuks, doen niets):**

Samengevoegd in HarryHemp:
- `tijdgeest_wachter`, `kennis_scout`

Opportunity-reflex-overflow (aangenomen maar leeg, 0 accs, 0 skills):
- `missie-alignment_missie-gedreven_transparantie`
- `veganistisch_missie-lens_niche-label`
- `missie-alignment_marketingtruc_veganistisch`
- `regeneratief_aanbeveling_homepage`
- `transparantiemodel_externaliteiten_gecertificeerd`

Kansen die als rol zijn geland in plaats van als project:
- `schoenenjagers_op_tiktok`
- `schoenen_met_verhalen`
- `schoenenruilfeest_in_het_dorp`
- `nooch_x_noordster_sneaker_swap`
- `schrijven_van_copy_voor_blogs`

Oude experimenten (archived):
- `ronnie` — vroegere bulletin-rol, opgeslokt door Noochie
- `content_strategist` — lifecycle-demo leftover

Actie: purge-commando schrijven voor archived records.

**Onbemande rol in wortelcirkel:**
- `schoenen_voor_duurzame_evenementen_seo` — 4 accs, geen skills, geen CLASS_MAP-entry,
  duikt elke puls op als onbemand. Actie: archiveren of bemensen.

**Orphan data-bestanden (gewoon deleten):**
- `data/cleanup_review_2026-06-16.json`
- `data/extract_review_2026-06-17.json`
- `data/projects_backup_20260626_102457.json` (72KB)

**Niet rommel (bewust):**
- `data/poc/` — actieve PoC-database voor cockpit2 glassfrog-tab, niet aanraken.

---

## Governance-sessie (volgende keer)

Te behandelen voorstellen:

1. **Verwijder tijdgeest_wachter en kennis_scout** als actieve rollen — werk zit in HarryHemp,
   records zijn verouderde schaduwen.

2. **Koppel the_source accountabilities aan Stefan** — founder-proxy is per definitie mens-gated,
   geen AI-rol.

3. **Beoordeel schoenen_voor_duurzame_evenementen_seo** — verwijderen of bemensen?

4. **Codie toevoegen als rol** — nu alleen persona, nog geen governance-record, geen accountabilities,
   geen skills gedefinieerd. Vragen: wat is Codie's purpose? Wat levert hij concreet op? Doet hij
   mee aan het werkoverleg?

5. **Rollen van mensen uitbreiden** — welke accountabilities hangen nu nergens aan een mens?
   Codie, the_source en anderen koppelen aan menselijke verantwoordelijkheden.

6. **advise_metrics in Noochie** — hardcoded dict vervangen door LLM-stap die strategy/goals leest.
   Enige echte functionele stub in productie.

---

## Ontwerpvraag die beantwoord moet worden vóór de volgende sprint

**Hybride Holacracy-model: hoe werkt het dorp precies?**

Stefan's formulering (2026-06-28):
- Werkoverleg = vangnet, mensen doen het 1x per week
- Rollen mogen autonoom werken maar hebben transparantieplicht
- AI-rollen hangen aan een menselijke accountability, niet los
- Codie en andere AI-rollen zijn rolvervullers, niet zelfstandige entiteiten

Nog te beantwoorden:
- Welke rollen zijn puur AI (autonoom, transparant)?
- Welke rollen zijn puur mens?
- Welke rollen zijn hybride (mens accountable, AI voert uit)?
- Wat is de transparantieplicht concreet — een bulletin? Een entry in het werkoverleg?
- Wie zit er in het werkoverleg — alleen mensen, of ook AI-rollen als rapporteur?
- Wat is het verschil tussen een AI-rol en een persona in governance-termen?

Dit beantwoorden vóórdat je nieuwe rollen bouwt of bestaande uitbreidt.

---

## Human inbox (stand 2026-06-28 ~22:46)

9 kansen wachten op Stefan:

| Tijd | Rol | Kans |
|------|-----|------|
| 20:27 | librarian | Lexicon voor Nooch-schoenen |
| 20:27 | trends | TikTok Vegan Sneaker Testers |
| 20:28 | harry_hemp | Thuiswerk-schoenen met buitenschoen-voordeel |
| 20:28 | noochie | Schoenentestdag in NoochVille |
| 22:45 | librarian | Lexicon voor schoenen op Nooch |
| 22:45 | facilitator | Testen op buurtfeesten met vrienden |
| 22:45 | trends | TikTok "Vegan Sneaker Swap" |
| 22:46 | harry_hemp | Thuiswerkers die ook buiten lopen |
| 22:46 | noochie | Schoenentestdag op de markt |

Beheer via: `python -m nooch_village.inbox`

**Structureel geblokkeerd:**
- `pairs_sold` niet meetbaar — doel verkoopdoel_2026_q4 (1000 paar Q4 2026) vereist
  Shopify-koppeling. Verschijnt elke puls totdat de meting beschikbaar is. Actie voor Dan.

---

## Volgende stappen (prioriteit)

1. **Morgen eerst:** hybride Holacracy-ontwerp beantwoorden (zie ontwerpvraag hierboven)
   vóórdat je nieuwe code schrijft
2. **Governance-sessie** — rollen opruimen, Codie toevoegen, menselijke accountabilities koppelen
3. **Inbox reviewen** — 9 kansen wachten, `python -m nooch_village.inbox`
4. **Shopify-koppeling** — geblokkeerd tot NoochVille online staat (zie hieronder)
5. **Dispatch splitsen (brok 11)** — bewust uitgesteld, rustige sessie zonder draaiende village
6. **advise_metrics Noochie** — hardcoded dict → LLM-stap

## NoochVille online zetten (prioriteit na governance-sessie)

Einddoel: village draait autonoom op een server, niet op Stefan's Mac.

Wat dit oplost:
- Shopify OAuth werkt met echte publieke URL
- Village draait 24/7 zonder Mac
- Cockpit bereikbaar vanaf elke plek

Te onderzoeken:
- Hosting opties (VPS, Railway, Render, Fly.io)
- Kosten vs. requirements (altijd aan, weinig RAM)
- Hoe .env en secrets veilig beheren
- Deployment pipeline

Shopify-koppeling geblokkeerd tot dit geregeld is.
`SHOPIFY_CLIENT_ID` en `SHOPIFY_CLIENT_SECRET` verwijderd uit `.env` (waren van oude app, nutteloos).

---

## Eerder vastgelegde context (nog actueel)

### Sessie 2026-06-25 (vervolg 4): triage-UX, governance-grounding, roloverleg

- Triage volgens Holacracy in de cockpit: per spanning Tactical of Governance
- Focusmodus `/triage` (Duolingo-stijl)
- Vraag-aan-rol = gebundelde dialoog
- Governance-referentiebank (VERTROUWELIJK, lokaal): 1.651 rol-skeletten
- Facilitator-rolreview: `village review_roles`
- "Oordeel = training"-laag: `feedback.py`
- Roloverleg (IDM): `roloverleg.py` + `/roloverleg`

### Wiring-gaps (nog open)

- **locale ontbreekt in de GSC-flow**: TrendsWorker publiceert `keyword_proposed` zonder locale,
  HarryHemp grondt met `locale=""`. Fix: locale meegeven afgeleid uit GSC-property of querytaal.

### Roadmap (daarna, te verifiëren of nog actueel)

- Governance-ritueel bouwen — na herlezing Holacracy v5 constitutie (art. 3 + 4)
- LLM-trechter voor C-en verdachte-B-spanningen
- Slimme WIP (prioriteit-eviction, backpressure) + synthesizer-rol
- Cockpit stap 2: rol/skill-authoring per `docs/ONTWERP_cockpit_rol_skill_werkbank.md`
- `openlibrary_v2`-activatie NIET reflexief goedkeuren: API is per-boek, niet corpus-breed
