# NoochVille — State & Handover (2026-07-09)

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

## Sessie 2026-07-14 — designsysteem fase 1: de HTML-basis (Pablo/Cowork)

**Suite: 2201 groen** (was 2195), 1 skip, 1 xfail. Wijzigingen staan LOKAAL in de working tree,
nog niet gecommit — Stefan reviewt de diff en commit zelf (werkafspraak: diff tonen vóór opslaan).

**Aanleiding:** designer-review van de broncode (bevestigde de eerdere Claude Code-review, plus
nieuwe vondsten: 4 verschillende mobile-breakpoints, z-index zonder schaal, 0× :focus-visible,
±70 dode selectors, en de correctie dat cockpit.py wél door 35+ testbestanden wordt geïmporteerd).
Besluit Stefan: eerst de HTML-basis, vormgeving pas als die staat; cockpit 1-only-tests mogen weg
(linkbuilding + Noochie-rapport blijven als prototype tot migratie naar cockpit 2).

**Fase 1a — CSS is een bestand geworden.** `_EXTRA_CSS` (56 KB) verhuisd naar
`nooch_village/static/nooch.css`; `cockpit2_util` leest het bestand en exporteert `_DS_LINK`
(`/static/nooch.css?v=<inhoud-hash>`). Views linken i.p.v. 56 KB inline per pagina; `/static/`
serveert nu met `Cache-Control: public, max-age=86400` (veilig: inhoud-hash bust). Laadvolgorde
ongewijzigd (basis in head, componenten erna) → geen visuele verschuiving. `_frag` injecteert
fragmenten nog steeds inline (bewust: verse CSS in modals). Bekende `.chip`-dubbeldefinitie
gedocumenteerd in de css-header; harmoniseren = fase-2-besluit.

**Fase 1b — semantische basis.** `_page()` wikkelt de inhoud in `<main>` (landmark; chrome komt
er via `_send` buiten te staan). Eén globale `:focus-visible`-regel (WCAG 2.4.7). Nieuwe helper
`web_base._field()`: genereert `<label for>` + veld-`id` altijd als paar (rootcause-fix voor
55 labels zonder for / 288 inputs zonder id).

**Fase 1c — ratchets uitgebreid** (`tests/test_ui_ratchets.py`, zelfde principe als de
inline-style-ratchet): (1) labels-zonder-for per view bevroren op audit-aantal, (2) ad-hoc
`<style>`-blokken bevroren (4 totaal), (3) klasse-prefix-families projectbreed bevroren op 58.
Plus positieve tests voor `_field`, `<main>` en de css-link. Docs bijgewerkt: UX_PATTERNS.md
(kern-klassen wijzen naar nooch.css, _field-regel), CLAUDE.md (UI-sectie), ARCHITECTUUR.md
(hergegenereerd, alleen regelnummers).

**Open:** fase 2 = vocabulaire-sessie (inventarisatie-doc staat klaar in het Claude-project):
417 klassen → kern-atomen + varianten, .chip harmoniseren, breakpoint-tokens, z-index-schaal,
dode selectors schrappen. Fase 3 = migratie per scherm bij aanraking, ratchets zetten vast.

---

## Sessie 2026-07-09 — projectdetail-UX-ronde + bijlage-upload dichtgetimmerd

**Suite: 2000 groen** (was 1873 op 2026-07-08), 1 xfail. 16 PR's (#148–#163), elk branch → squash/rebase-
merge → deploy (Hetzner), volle suite per commit.

**Blok 1 — projectdetail-UX.** `description` stuurt nu de prep-prompt (#148); `@mention` van een AI-persona
op de wall geeft een eenmalig antwoord (#149). Vier micro-fixes (#150): `_md` rendert cursief/doorhalen/
kop/http(s)-link; wall scrollt naar het laatste bericht; bijlage op de composer-toolbar-rij. Opdracht-veld
uit de UI (#151, prep+API blijven). Ronde 2 (#152): ratio 2:1, **WYSIWYG werkt nu in de modal** (wrapSel
guarded in `_modal_html` — fragment-`<script>`s draaien niet bij `innerHTML`), 🔗 weg, hoogte-koppeling.
Stil **skill-aanbod** bij een Uitvoerplan-item (#153, gedeelde `build_skill_registry()`-factory, cockpit
alleen metadata). Impact-dropdowns + effort numeriek in uren `{"hours": N}` met lazy enum-conversie (#154).
Auto-opslaan in de zijbalk (onchange/onblur, knoppen weg) + foutpad-melding (#155).

**Blok 2 — de bijlage-upload-saga: VIER onafhankelijke bugs**, diagnose-gedreven:
1. **nginx-default 1 MB** → 25M-cap (conf.d drop-in, certbot-veilig) + app-limiet `upload_max_bytes` (20M,
   onder de cap) + eerlijke fout (413/400 i.p.v. stille no-op) + modal-fetch checkt `response.ok` (#157).
2. **`_parse_multipart` corruptie** — strípte de laatste byte van elk bestand → byte-exact gemaakt (#159).
3. **Lost-update race op `projects.json`** (bestand op schijf, entry verdween): `file_lock` + verse read op
   alle 35 schrijfpaden (#158, `_synchronized`-decorator, intra-proces) → daarna **`fcntl.flock`** in
   `util.file_lock` (#161) voor cross-proces (cockpit ↔ daemon), crash-veilig + timeout, dekt óók de
   AttachmentStore. Getest met echte subprocessen.
4. **Geneste `<form>`** (de eigenlijke oorzaak dat de upload NU faalde): het upload-form (`filepost`) zat
   genest ín de composer-`<form>` → browser dropt de inner form → `wire()` stuurt form-encoded → de File
   valt weg → het bestand kwam nooit binnen. Un-nested via `form=`-attribuut (#162). Geverifieerd door
   Stefan: **upload werkt**.

Plus: read-only wees-bestand-rapport (#160, `python -m nooch_village.orphan_report`, vond 4 wezen uit de
race-periode — herstelt niets, mens beslist); bord-drag-drop checkt nu ook `response.ok` (#163);
WORKING_AGREEMENTS-notitie over de stille 4000-cap op policy-bodies (#156).

**Data-operatie (server, protocol gevolgd):** de "Tone of Voice"-policy zat op de 4000-cap afgekapt →
gesplitst in **Tone of Voice** + **Position Statements** (bron: `strategies.json`), en het strategie-
duplicaat (`tone_of_voice`+`position_statements`) verwijderd; "Desing System"-titeltypo gefixt.

**Open (geen haast):** de 4 wees-bestanden op schijf zonder wall-entry — nu de bugs weg zijn kan Stefan ze
opnieuw uploaden (blijven nu staan), of per geval opruimen na akkoord. Verder niks blokkerends.

---

## Sessie 2026-07-08 — de werk-laag wordt echt (uitvoer-primitief, eerste gedrag-policy, patent-skill)

**Suite: 1873 groen** (was 1382 op 2026-06-30), 1 xfail (deferred /person-notificatie). ~15 PR's,
elk branch → squash-merge → deploy (Hetzner), volle suite per commit.

**Grote lijn:** de projecten-laag doet nu écht werk. Een rol bereidt een project autonoom voor (checklist)
en voert het uit via zijn skills → deliverables als notes. Bewezen: harry_hemp's project *"Patents and
scientific studies on barefoot shoes researched"* liep bij de puls **100% (4/4) autonoom af** met echte,
on-topic resultaten (12 patenten + 204 studies + samenvattingen + cultuurtrend). Eerste volledig autonoom
afgeronde onderzoeksproject in de werk-laag.

**Wat er nu staat:**
- **Uitvoer-primitief (Fase 1)** — bord-gedreven statusmachine: TOEKOMST=voorbereiden (LLM-checklist met
  skill + payload per item, machine-check tegen DNA), ACTIEF=uitvoeren (skill→note→afvinken, status-
  normalisatie gelukt/leeg/fout, note-opmaak per archetype), DONE=alles af. **Geen valse `stub:done` meer.**
  `dag_begint → _tend_projects` universeel gewired. Idempotent via `last_tended`. Docs:
  `docs/uitvoer_primitief_fase1.md`.
- **WIP-cirkelpolicy (WIP-001)** — de **eerste gedrag-sturende** policy (de 3 bestaande zijn beschrijvend):
  begrenst autonome voorbereiding tot N (config `wip_prepare_limit`, default 8) per AI-rol, FIFO. Policy =
  de expliciete aan-knop (via `own_and_inherited` op de cirkel); N uit config, **niet** uit de body-tekst.
  Scheiding governance-verankert / code-dwingt-af strikt bewaakt.
- **Schema-gedreven skills** — `Skill.input_schema`/`output_schema` gevuld voor de werk-skills en
  doorgegeven aan de prep-LLM, zodat elk item de juiste payload-vorm krijgt (`{term}` / `{kw:[…]}` /
  `{brands:[…]}` / `{terms:[…]}`) i.p.v. een gegokte `term`.
- **Nieuwe skill `epo_patents`** (EPO OPS, XML-interface, OAuth) — wereldwijde patenten, titel-frase-query
  (on-topic), in harry_hemp's DNA. Dekt de accountability "searching global patent registries".
- **Meetcatalogus afgesloten** (sluitpakket, 6 scopes): trends_categorie weg, Plausible page_path-dimensie,
  4e stemming-paar slow÷fast, catalogus + **healthcheck-contract** (`meetcatalog.py`) geactiveerd — 0 vals
  alarm op de schone store. Methode-note bij concurrent_scout.
- **openalex_evidence frase-fix** — exacte frase i.p.v. losse woorden (14.906 → 204 hits, on-topic).
- **Opruiming:** `ask_accountability` generieke offer→complete-lus gedicht; dood hout weg (stooq-skill,
  propose_amendment-legacy-handler). Read-only inventarisatie: `docs/codebase_staat_2026-07-08.md`.

**Bewust NIET (mens/beslissing):** gefaseerde activering van alle 47 TOEKOMST-projecten (WIP-cap dekt de
burst); Copywriter (Wendy Words) heeft nog **geen skills** (content_schrijven/content_check bestaan maar
zijn aan niemand gegrant); de Gemini free-tier (20/dag) knelt bij voorbereidings-volume.

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

## Sessie 2026-07-04 — Mother-Earth-aardbol, UI-opschoning, metrics-diagnose

Zeven kleine PR's, elk branch → squash-merge → deploy (Hetzner), suite groen (1548).

### Wat is af
- **Governance-meeting sluit écht** (#8): `rov2_end` ruimt nu de resterende open agendapunten van
  de cirkel op; de "Governance meeting"-knop blijft niet meer groen hangen.
- **Live NASA-EPIC-aardbol** op de anchor-overview (Mother Earth), DOMAINS-blok (#9–#11):
  `nooch_village/epic.py` (metadata 1u-cache + volle-PNG→Pillow-512px-proxy, key server-side via
  `/epic/frame`), widget alleen op de anchor, 8 frames over de hele dag (Europa in beeld),
  fail-closed fallback. `Pillow>=11` in requirements (server draait 12.3.0).
- **UI-opschoning**: "Geen domein."-placeholder weg op de anchor (#12); maturity-status-dots +
  dode "Nog te bouwen"-placeholder uit de tab-navigatie (#13); legenda onder de organisatie-boom
  weg (#14). Seen-marker behouden.

### Metrics-dashboard — diagnose (nog GEEN fix; besluit welke we aanpakken volgt)
- **Geen "over tijd"-grafiek**: Chart.js bestaat niet in de codebase; de enige tijdreeks-viz is een
  84×22px inline-SVG sparkline (`_spark_svg`, `views/metrics.py:62`) die wél rendert mét variërende
  data. Ontbrekend: een echt grafiek-component.
- **Periodefilter inconsistent / bezoekers vast 7-daags**: `visitors_7d` komt uit de Plausible-puls
  met `period` hard `7d` (`skills_impl/plausible.py:34`); de dashboardfilter kan dat venster niet
  wijzigen (en alle samples zijn <7 dagen oud → filter verandert niets). Reeks-tegels passen `cutoff`
  toe, aggregaat-werktegels negeren 'm (all-time) → inconsistent (`_werk_fetch`, `views/metrics.py:221`).
- **Werkoverleg-cijfers zijn echt**: tevredenheid 8.6/10 en duur 5.1 min komen uit `st.werk.log()`
  (16 echte records), geen seed. Wel dun/scheef: tevredenheid op 4/16 records; `duur_min` =
  [0,0,0,2,2,60,3,0,0,3,1,2,0,4,5,0] (8×0 min + 1×60 min-uitschieter).
- Zie ook de eerder gecommitte tech-schuld-notitie (`cd533e1`: werkoverleg-metrics zonder SSOT).

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

### Sindsdien bijgekomen (artefacten, read-scope, backlog, labelregel)

✅ **AUTHZ-labelregel** (vastgelegd in CLAUDE.md): elke NIEUWE dispatch-tak krijgt bij aanmaak
   verplicht één van vier labels als `# AUTHZ:`-comment — anchor-lead / Circle Lead /
   rolvervuller-of-Circle-Lead / circle-member-of-iedereen-ingelogd. Bewust ongated mag, maar
   dan óók met label + één zin waarom. Voorkomt de situatie van vóór 1 juli 2026 (dispatch zonder
   enige autorisatie).
✅ **Artefact-schrijfgates** (`_artefact_gate` / `can_write_artefact`, `artefacts.py` + `cockpit2.py:450`):
   artefact_add / artefact_edit / artefact_archive mogen alleen door de vervuller van de eigenaar-rol
   OF de Circle Lead van de omvattende cirkel — identiek voor mens en agent. Policies vereisen
   bovendien een governance-referentie (`requires_governance_ref`): een policy hoort bij een
   governance-toegewezen domein, niet zomaar los. Nieuwe helper `_web_actor_id` (username → actor-id).
✅ **Read-scope context/notes** (`role_context` / `/context`): iedereen-ingelogd — dezelfde read-scope
   als `/node?tab=notes`. De context-tab (`/person?tab=context`) is zichtbaar voor elk INGELOGD
   village-lid.
✅ **Auth-uit guest-asymmetrie** (besluit 2026-07-03): in auth-uit-modus ziet een guest losse
   rol-notes via `/node?tab=notes`; de persoon-context-aggregatie (`/person?tab=context`) blijft
   óók dan afgeschermd. Bewuste keuze, geen gat — bij een publieke view wordt per-tab opnieuw bepaald.
✅ **Backlog-takken**: een backlog-item indienen = iedereen-ingelogd; de backlog beheren
   (staat verplaatsen, impact/effort) = rolvervuller `website_developer`.

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
  governance_examples.py. Onderzoeken na vrijdag. (Mogelijke blokkade voor de
  PDF-upload-stories in `docs/BACKLOG.md` → Uploads.)

> Bredere product-wensenlijst (user stories per thema): zie `docs/BACKLOG.md`.

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

### Werkoverleg-metrics: geen single source of truth (4 plekken, gedrift)
De werkoverleg-metrics staan op **vier** handmatig gesyncte plekken zonder SSOT:
`definitions.py`-seed (`source="werkoverleg"` → catalog-pagina), `_sources_for`
(`metrics.py` → pulldown/wizard), `_WERK_MEASURE` en `_WERK_GRONDSLAG`. Ze zijn al
uit de pas: **catalog heeft 6 metrics, pulldown 9**, en de namen wijken af
("Doorlooptijd werkoverleg" vs "Duur (min)", "Behandelde spanningen" vs
"Spanningen verwerkt"). Schendt "Reference, don't copy".
**Fix:** de wizard leest de `werk:`-measures (+ grondslag) uit de DefinitionStore-
catalogus i.p.v. een hardcoded lijst; catalog wordt de bron, seed compleet maken
met de 3 ontbrekende (roloverleg, nevermind, afwezigheid).

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
