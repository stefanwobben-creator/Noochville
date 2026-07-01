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

## NoochVille online (2026-06-29)

Server: Hetzner CPX22, Falkenstein
IP: 138.201.154.162
Cockpit: https://village.nooch.earth
Services: noochville-village + noochville-cockpit2 (systemd)
DNS: village A-record op TransIP → nooch.earth

Openstaande acties:
- Shopify OAuth redirect URL instellen op `https://village.nooch.earth/shopify/callback`
- `serpapi_trends` governance-actie voor `website_watcher` (dode capability-melding bij startup)
- Server naam hernoemen van `ubuntu-4gb-fsn1-1` naar `noochville` in Hetzner console

---

## Sessie 2026-06-30 — veiligheid + UI-microfixes

**Suite: 1382 tests groen**, 7 pre-existing failures (5× LLM-zonder-key, 2× test-isolatie-flaky;
bevestigd identiek aan de baseline). Elke stap met diff-tonen + mutatie-check.

### Wat is af
- **seeds.py-overschrijver onschadelijk gemaakt** — `migrate_records` vult een persona nu alleen-als-leeg
  i.p.v. elke afwijking overschrijven (seeds.py:367). Een puls draait bewuste hernoemingen niet meer terug.
- **once-sandbox** — `python -m nooch_village.village once-sandbox [--keep]`: een puls draait tegen een
  wegwerp-kopie van data/, raakt productie-data nooit. `once()` ongewijzigd via gedeelde `_run_single_pulse`.
  Productie-data is hiermee structureel veilig.
- **shopify_sales geregistreerd** in de SkillRegistry + gekoppeld aan `website_watcher`, met expliciete
  fail-closed stub (geen live data zonder OAuth; opt-in fixture, gemarkeerd `live:False`).
- **5 persona-koppelingen** in assignments.json: Sid→Scientist, Billy→Trends & Competition, Lara→Library,
  Walter→Website Watcher, Wendy→Copywriter (zelfde vorm als Noochie).
- **copywriter-skills** — Wendy's rol gekoppeld aan 3 bestaande content-skills (content_schrijven,
  content_check, voorstel_schrijven); alleen DNA-koppeling, geen nieuwe code.
- **WORKING_AGREEMENTS.md aangelegd** — werkafspraken over pulsen, scope, venv + open aandachtspunten.
- **UI-microfixes:** U4 (checklist altijd tonen, kleurcodering: te-doen geel / gemist coral, aandacht-bubble
  vervallen → één lijst), U5 (checklist-rapportage alleen V/X, waarde-badge + invoerveld weg, opslag intact),
  U6 (AI-assistent in governance verwijderd — knop, route, chat-panel, handlers; overlap met Noochie).

### Openstaande punten (zie WORKING_AGREEMENTS.md)
- **Autorisatie-laag (gedeeltelijk live)** — user-threading, `is_circle_lead` en de gate op de rol-takken
  staan gecommit; zie het kopje "Autorisatie-laag" hieronder voor de volledige stand. Nog open: overige
  dispatch-takken zijn user-agnostisch, en de eerste concrete use case (afwezig-status op de members-tab)
  heeft nog geen gate.
- **Transparantie-brug ontbreekt** — puls-output (notes.json, output/) is niet zichtbaar in cockpit2
  (die leest attachments.json). Twee gescheiden werelden.
- **Lokaal ↔ server-governance divergeren** — verzoenen vóór de eerstvolgende deploy.
- **CSS-default-details** — globale `details{}`-regel (cockpit.py:504) geeft elke `<details>` een card-kader;
  negen plekken erven het, vijf overschrijven ad-hoc. Structureel: default kaal + expliciete `.box-details`.
- **Advies-kwaliteit** — LLM-advies-stappen lezen strategie/beleid nog niet (gaven al Google-Ads-advies
  terwijl Nooch geen advertising voert). Advies tegen beleid toetsen vóór live gebruik.

## Autorisatie-laag (grotendeels live)

Patroon bewezen en gecommit. Vier helpers dragen de laag:
`is_circle_lead`, `is_role_filler`, `is_circle_member`, `resolve_circle_id`,
met poort-wrappers `_role_gate` en `_member_gate`. Regel per default: guest
(auth uit) mag alles; ingelogde-maar-onbekende wordt geweigerd (fail-closed).

✅ user-threading: dispatch() ontvangt username via sessie
✅ gate op role_assign / role_unassign / role_focus (Circle Lead only)
✅ aitask_add (Circle Lead ouder-cirkel) + persona_skill_add (anchor-lead)
✅ groep A — anchor-lead only: def_add, def_amend, person_edit, person_remove
✅ groep B — Circle Lead ouder-cirkel (afgeleid): proj_delete (pid→owner, incl.
   Individueel Initiatief "ii:<circle>"), aitask_remove (tid→rol)
✅ groep C — Circle Lead van de overleg-cirkel (g("circle")): rov2_remove,
   rov2_remove_group, rov2_consent, rov2_end
✅ operationele laag — rolvervuller OF Circle Lead, op 38 takken: proj_* (m.u.v.
   collaboratie), attach_*, checklist_*, check_*, m_add_*, tile_*, cl_*,
   m_sample/remove. role_id direct (owner/node) of afgeleid (pid/mid/cid).
✅ proj_add van een Individueel Initiatief: elk cirkellid mag (_member_gate)
✅ collaboratie-takken BEWUST ongated (ingelogd = mag): proj_comment, react_add,
   proj_feed, feed_edit, feed_remove, ai_reply
✅ people-beheer buiten dispatch: person_add + person_reset_password (anchor-lead,
   handlers geven nu (body, statuscode) terug; do_POST unpackt)
✅ roloverleg-bewerking — circle-member (shaping = lid): rov2_add, rov2_add_to_group,
   rov2_setkind, rov2_set/acc/dom. Besluiten (consent/end) blijven Circle Lead.
✅ werkoverleg wo_* — twee lagen (helper _lead_gate): overleg leiden/agenda-flow =
   Circle Lead (open/close/present_all/ag_remove/ag_reopen/ag_resolve); deelnemen =
   circle-member (ag_add/ag_note/presence/checkout).
✅ m_pin / m_unpin — cirkeldashboard beheren = Circle Lead van g("circle").
✅ noochie_* (send/reset/ctx) — BEWUST ongated (ingelogd = mag).
✅ bootstrap: Stefan (dc5685eb2074) gezaaid als mother_earth__circle_lead
   (in data/assignments.json, gitignored — handmatig op server zetten)

**Schrijf-kant van dispatch is nu volledig doorlopen**: elke tak is óf gegated
(rol/lid/lead/anchor) óf bewust ongated (collaboratie + noochie). Vijf poort-
helpers: is_circle_lead / is_role_filler / is_circle_member / resolve_circle_id
+ wrappers _role_gate / _member_gate / _lead_gate.

⏳ Nog open:
- Read-kant (do_GET/render): privé-projecten worden bij tonen nog niet per gebruiker
  afgeschermd. Aparte beslissing of dat moet.
- Server: mother_earth__circle_lead-filler nog handmatig zetten (commando staat klaar).

## Backlog (na vrijdag)

- **Hernoemen cockpit2 → cockpit**: cockpit2.py, service-namen, imports, tests en
  documentatie in één refactor-sessie. Doel: schone semantiek en overdraagbaarheid.
- **Self-service wachtwoord wijzigen**: ingelogde gebruiker kan eigen wachtwoord
  veranderen zonder anchor-lead tussenkomst. (Nu: alleen anchor-lead reset via /admin;
  geen change-flow — zie person_reset_password. Nieuwe gate-laag "gebruiker zelf".)
- **Publieke read-kant**: bepaalde pagina's (strategie, Impact Forest) zichtbaar zonder
  inloggen. (Raakt de open "read-kant"-vraag in de Autorisatie-laag-sectie hierboven.)
- **PDF-upload bug B1**: oorsprong onduidelijk, mogelijk glued-words-parser in
  governance_examples.py. Onderzoeken na vrijdag.

### Morgen
- **Strategie-laag ontwerpen** — `data/strategy.json` met do's en don'ts die advies-stappen en agents lezen.
- **Context-patroon voor LLM-stappen** — hoe elke LLM-aanroep consistent missie/strategie/databronnen meekrijgt.
- **LLM-leer-model uitleggen** — hoe het dorp leert (welke feedback-lus, welke data, welke grens).

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
