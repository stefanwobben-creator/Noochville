# Implementatiebrief voor Claude Code: de opruiming van 19 september, in grote stappen

*19 september, avond. Vervolgt `implementatiebrief_claude_code.md` (16-17 sept, het AI-rollen-traject
zelf — governance-niveau afgerond tussen 15-18 sept, zie `state_19sept.md`) en verwerkt de twee
diepe-audit-documenten van vandaag (`functionaliteit_inventaris_afslanken_19sept.md`,
`audit_diep_cockpit_views_skills_19sept.md`) tot uitvoerbare fases. Scope: ~37.000 van de 98.185
broncoderegels, ~40.000 van de 80.040 testregels, met bestand:regel-bewijs per fase voor fase 1-6.
Uitgebreid diezelfde avond, op Stefans verzoek, met drie interface-fases (7-9) die de live cockpit
naar de navigatie, schermindeling en het visuele ontwerp van het prototype (v15) brengen.*

*Zelfde format als vorige keer: elke fase is een prompt die je direct in Claude Code (terminal)
plakt. Ook hetzelfde format, expliciet anders van tempo: dit keer géén per-item goedkeuringsgate
zoals bij de rolopruiming (die had 4 losse rollen, elk met eigen risico op lopende projecten). Fase
1-6 zijn voor het overgrote deel bewezen dode code — nul actief gebruik, bestand:regel-bewijs, geen
lopende projecten die kunnen breken. Fase 7-9 zijn geen opruiming maar bouw, met een net zo hard
naslagwerk: het prototype zelf (v15, drie rondes Playwright-geverifieerd, zie
`heuristische_ux_analyse_prototype_19sept.md`) is de exacte spec, dus ook daar is er iets concreets
om tegenaan te bouwen en te testen, geen open ontwerpvraag. Daarom: negen grote fases in plaats van
kleine stapjes, elke fase eindigt nog steeds met diff + volledige testsuite voor/na (jouw vaste
werkwijze blijft overeind), maar je hoeft niet na elk bestand te pauzeren.*

*Uitvoering (aangepast 19 sept, avond, op Stefans verzoek): draai fase 1 t/m 9 achter elkaar door in
één sessie, zonder op mijn akkoord te wachten tussen de fases. Commit wel na elke fase apart (voor
rollback-granulariteit) en bekijk zelf de diff voor je commit, zoals altijd — maar wacht niet op mij
om verder te gaan naar de volgende fase. Stop en vraag het aan mij alleen in deze gevallen:*

- *een testregressie die je niet kunt verklaren of niet binnen de fase zelf kunt oplossen;*
- *de specifieke momenten die hieronder al met naam gemarkeerd staan als "check dit eerst" of "vraag
  het aan Stefan": orphan_report.py's server-run-status (fase 2), inoreader_ingest's
  cron-vs-dagcyclus-status (fase 4), /catalogus_koppelen + /claims/db.json's gebruik buiten de
  cockpit (fase 6), en welke schermen je in fase 9 bewust overslaat (zie daar);*
- *iets dat je onderweg tegenkomt dat niet in deze brief beschreven staat (een module die toch nog
  een levende aanroeper blijkt te hebben, een test die op een aanname leunt die niet meer klopt, een
  plek waar de live cockpit structureel afwijkt van wat deze brief aanneemt over de huidige nav/UI).*

*Bij elk van die stops: pauzeer, meld precies wat je tegenkwam, en wacht op antwoord voor je verder
gaat. Voor al het overige: doorlopen, fase na fase, tot en met fase 9.*

## Volgorde en waarom

1. Rolklassen-lijken (roles.py) — moet eerst, want vereenvoudigt fase 2 (één van de twee
   "needs-vervanging"-plekken uit de oude Fase 6 verdwijnt vanzelf mee met de klasse).
2. NotesStore + kennisbank-familie + orphan-modules — de oude Fase 6 die nooit is uitgevoerd.
3. AI-projectuitvoering + Founder Flow + Codie-backlog — het grootste blok, alle drie zijn
   "AI-persona voert project uit"-restanten, geen van drie heeft een vervanger nodig (Keep-in-wiki
   dekt het al).
4. Radar-beoordelingslaag eruit, swipefile blijft — **let op**, dit is de enige fase met een niet-
   afgeronde afhankelijkheid: het maandrapport zelf (de nieuwe bestemming van de swipefile) hoort in
   de geplande-taak-mechaniek, die nog niet bestaat. Deze fase verwijdert dus alleen de beoordeling,
   bouwt het rapport nog niet.
5. Claims loskoppelen van rol/persona.
6. cockpit2.py + cli.py + views/ + skills_impl: dode handlers, routes, modes, en de laatste
   AI-tijdperk-UI-lagen (wizard, checklist-skillmatch, strategy-tab, drie tabs → één, alphavantage/
   gdelt).
7. Navigatie + Wiki/Tools/Policies-consolidatie + Keep-in-wiki-ingang, naar het prototype — moet ná
   fase 1-6, want anders bouw je nieuwe schermen bovenop routes/velden die toch weggaan.
8. Channel-laag (project/cirkel/persoon) + zoeken op inhoud — bouwt voort op de nieuwe
   scherm-/navigatiestructuur uit fase 7. Vervangt de bestaande wall en @-notificaties direct
   (geen naast-elkaar-periode, zie fase 8 zelf).
9. Het visuele ontwerp (Nooch UI v1) op alle schermen die in fase 7-8 zijn herbouwd.

**Waarom fase 7-9 niet hoeven te wachten op de geplande-taak-mechaniek, ondanks de eerdere afspraak
dat de UI-bouw daarna komt**: die afspraak (zie `state_19sept.md`) is gemaakt met de inhoud van het
maandrapport in gedachten — een wiki-pagina die pas gevuld wordt zodra de mechaniek de swipefile
leegt. Dat is uitsluitend een contentvraag, geen structuurvraag: de wiki-pagina, het kanaal, de
navigatie en de zoekfunctie kunnen allemaal al bestaan en werken zonder dat er al een rapport in
staat (net zoals de swipefile na fase 4 ook gewoon vult zonder dat er al iets mee gebeurt). De
geplande-taak-mechaniek blijft dus wel nodig vóórdat de maandrapport-pagina's zelf gevuld raken, maar
dat blokkeert fase 7-9 niet.

Niet in deze brief: de geplande-taak-mechaniek zelf bouwen (apart traject, `ontwerp_geplande_taak_
mechaniek.md`), het maandrapport dat daar straks uit komt (leunt op die mechaniek, niet op deze
UI-fases), en de `cockpit2.py`-routetabel + splitsing (verdient een eigen scope zodra fase 6 de dode
routes heeft weggehaald — anders bouw je een nette tabel voor deuren die nergens heen gaan). Ook niet
in deze brief: de oudere `designsysteem_fase2_inventaris.md`-vocabulairesessie (14 juli) — dat ging
over het opschonen van de bestaande, oude cockpit-CSS-klassenset, een ander traject dan fase 9
hieronder, dat een compleet nieuw visueel systeem neerzet zoals het prototype het toont.

Draai voor je begint de volledige testsuite één keer en bewaar het resultaat (passed/failed/errors)
als nulmeting voor alle negen fases.

## Fase 1: de zes dode rolklassen uit `roles.py`, code-niveau (niet alleen governance-niveau)

De rollen zelf zijn tussen 15-18 sept al gearchiveerd op governance-niveau (`verwijderplan_ai_
rollen.md`), en de vorige implementatiebrief heeft in Fase 8 al een deel van de hardgecodeerde
referenties opgeruimd (`founder_taken.SCIENTIST_ROL`, `discovery_board.TAG`, `radar_store.py`,
`role_proposals.py`, `dagcyclus.py`'s default, `cli.py`'s harry_hemp-modes, de CLASS_MAP-regels
zelf). Wat daarbij NIET is gebeurd: de klassen zélf staan nog gewoon in `roles.py`, dood gewicht.
Vandaag opnieuw geverifieerd via de import-graaf: 1.903 van de 2.404 regels in dat bestand horen bij
rollen die niet meer bestaan.

```
Verifieer eerst zelf, voor je iets verwijdert: check of de CLASS_MAP-regels voor HarryHemp,
WebsiteWatcherWorker, ConcurrentScout, Librarian, TrendsWorker en ContentStrategist inderdaad al weg
zijn uit village.py (dit zou uit een eerdere ronde moeten komen) — als dat nog niet zo is, doe dat
eerst.

Verwijder daarna uit roles.py de zes klasse-definities zelf:
- HarryHemp (696 regels)
- WebsiteWatcherWorker (364 regels)
- ConcurrentScout (358 regels)
- Librarian (337 regels)
- TrendsWorker (85 regels)
- ContentStrategist (63 regels)

Let op ContentStrategist specifiek: dit is waar _spot_content leeft (roles.py:2342-2368), de
methode die NotesStore-kaartjes selecteert via notes.content_seeds(). Die verdwijnt hiermee
automatisch mee — dat is gewenst, fase 2 hoeft er dan geen vervanging voor te bouwen.

Ruim daarna in village.py de bijbehorende dode bus.subscribe(...)-regels op (rond regel 183-217) voor
events die alleen deze zes klassen publiceerden: tijdgeest_*, competitor_*, gsc_pulse_completed,
keyword_decided, content_opportunity/content_draft_ready, seed_surge_*, nl_corpus_*.

Kritisch: keyword_decided en keyword_proposed worden ook los aangeroepen vanuit cli.py (rond regel
93-151) voor handmatige CLI-flows die niets met deze rollen te maken hebben. Controleer per
event-naam of er nog een niet-persona-aanroeper is voor je de subscription weggooit — niet blind
alles op naam verwijderen.

Volledige testsuite voor/na, diff, commit en ga door naar fase 2.
```

## Fase 2: NotesStore + kennisbank-familie + orphan-modules (de oude Fase 6, nu wel afmaken)

Dit stond al gescoped in `implementatiebrief_claude_code.md` (Fase 6), maar is nooit uitgevoerd:
`data/notes.json` is vandaag opnieuw gecontroleerd en is nog exact hetzelfde bestand van 16 juli. Nu
ContentStrategist er niet meer is (fase 1), vervalt één van de twee destijds genoemde
"needs-vervanging"-plekken vanzelf. De andere blijft staan.

```
NotesStore (notes_store.py, 625 regels) en de kennisbank-familie eromheen kunnen weg: nul nieuwe
records sinds 17 juli, het rendermechanisme haalt al twee maanden nul kaartjes boven zijn eigen
drempel (EMERGENCE_THRESHOLD, emergence.py:17,20).

Verwijder direct, geen vervanging nodig (eenmalige/handmatige onderhoudsscripts):
notes_store.py, kennisbank_seed.py, kennis_context.py se eigen store-laag (niet de aanroeper, zie
hieronder), kennis_merge.py, kennis_tags.py, kennisbank_reatomise.py, kennisbank_bronherstel.py,
tag_onderhoud.py, herkomst_verrijking.py, plus hun CLI-entries in cli.py (kennis_migrate,
notes_remove, en de overige notes/kennis-gerelateerde modes).

Eén plek heeft wel een vervanging nodig: kennis_context.py wordt via project_worker.py aangeroepen
bij het opstarten van een nieuw project om een "REEDS BEKEND"-blok te vullen, nu een NotesStore-
lookup. Vervang door een verse AI-onderzoeksaanroep in dezelfde stijl als de bestaande
onderzoeksvraag-skill (skills_impl/onderzoeksvraag.py, side_effect_free=True, één LLM-call op de
meegegeven payload, niets zelf opgeslagen): geen store-lookup meer, gewoon vers onderzoek bij het
opstarten van elk nieuw project.

Verwijder daarna de losse orphan-modules waar Stefan op 19 sept al over besloten heeft (zie
state_19sept.md): montecarlo.py, attribution.py, claims_migrate.py, concept_suggest.py,
link_suggest.py, projects_cli.py. orphan_report.py: laat draaien op de server als dat nog niet is
gebeurd, daarna pas verwijderen uit de repo — check dit eerst zelf (deploy-logs, laatste run), en
vraag het pas aan Stefan (stop, meld het, wacht op antwoord) als je zelf niet kunt verifiëren of dat
al is gedraaid. inoreader_ingest.py blijft (nodig voor de radar-ingest, fase 4).

Ook weg, want puur onderdeel van de kennisbank-UI die nu geen doel meer dient: de drie
Policies/Notes/Tools-tabs in cockpit2_util.py (regel 62-72) en hun renderpaden in views/overview.py.
Vervang ze hier alleen door een tijdelijke doorverwijzing naar de bestaande Wiki-tab (geen filter
nog) — de echte, prototype-gelijke Wiki-tab-met-filter wordt in fase 7 gebouwd, samen met de rest van
de navigatie; dit is bewust in twee stappen geknipt zodat fase 2 zich tot data/opruiming kan
beperken.

Volledige testsuite voor/na (dit raakt relatief veel bestanden, extra aandacht hier), diff, laat
expliciet zien welke bestanden zijn verwijderd en welke twee herbouwd (kennis_context.py-aanroeper,
Policies/Notes/Tools → tijdelijke Wiki-doorverwijzing), commit en ga door naar fase 3 — tenzij
orphan_report.py's server-runstatus onduidelijk blijft, dan eerst stoppen en aan Stefan vragen.
```

## Fase 3: AI-projectuitvoering + Founder Flow + Codie-backlog eruit

Dit is het grootste blok qua regels (~9.500 broncode + ~9.750 tests), en het meest eenduidige: drie
losse dingen die alle drie hetzelfde zijn — machinerie gebouwd voor een AI die een project uitvoert
en zichzelf daarop beoordeelt, en die AI bestaat niet meer. Stefan heeft dit vanavond zelf zo
verwoord: "een project een deliverable laten krijgen is misschien overkill, borg het in de wiki met
menselijke input" — dat is precies Keep-in-wiki, wat al in het prototype zit. Geen van de drie
onderdelen hieronder heeft dus een vervanging nodig.

```
Verwijder de volgende drie AI-projectuitvoeringsblokken volledig, inclusief hun cockpit-routes,
views en tests. Geen van drie heeft een vervanging nodig (Keep-in-wiki dekt de vervanging al, staat
in het prototype, wordt in fase 7 als ingang gebouwd).

BLOK A — projectuitvoering in inhabitant.py (960-2117, zie audit_diep_cockpit_views_skills_
19sept.md §1 voor de exacte methodegrenzen): prepare_project, _plan_checklist, _execute_checklist,
_critic_gate, _deliverable_note, _ronde_twee, _herplan_na_strategie, plus de sensing-cluster
_sense_gap/_sense_redundancy/_opportunity_reflex/_raise_governance_proposal. Laat de rest van
inhabitant.py staan (thread/bus/skill-registry-helpers, _run_pulse_skills — die laatste blijft
actief nodig voor de mens-vervulde rollen met periodieke skills). Verifieer voor het verwijderen
live dat geen van de huidige 6 wakkere inwoners (compliance, website_developer,
strategic_lead_founder_steward, financial_controller, facilitator, noochie) hier nog op leunt buiten
_run_pulse_skills om.

BLOK B — deliverables/rapport/pakket/critic/inwoners-schermen: missie_critic.py (440), project_
pakket.py + inwoner_pakket.py (304 samen), project_verslag.py (649), project_worker.py's
AI-executie-paden (niet de kennis_context-vervanging uit fase 2, die blijft), de routes /rapport,
/project_pakket, /inwoners en hun views. personas.py blijft zolang Noochie bestaat (221 regels), de
rest van de persona-machinerie niet. Check ook business_case.py, board_loop.py, noochie_memo.py: dit
zijn de Mission Impact/Business/Effort-invoervelden die zonder AI-prioritering drie verplichte
dropdowns zijn die niemand terugleest (12-15 van 112 levende projecten ingevuld, business_case op
0) — velden mogen in de data blijven staan als historie, haal ze uit het formulier
(views/wizard.py, 458 regels: overweeg het hele wizard-scherm te vervangen door één vraag,
"wat is klaar-wanneer?", done_when staat al op 184 van 386 projecten dus dat veld werkt al — de
definitieve wizard-vervanging naar het prototype-formulier gebeurt in fase 7, hier alleen de
AI-velden eruit).

BLOK C — Founder Flow, helemaal (Stefans besluit van vanavond, definitief, triage én
trainingsloop): founder_flow.py (575), founder_taken.py (666), views/founder_flow.py (503),
founder_kaart.py (151), founder_park.py (117), route /founder. Ook weg: accountability_check
(skills_impl, +views /accountabilities, "Last run: unknown · 0 duplicates" — nooit iets opgeleverd,
98+99 regels). Codie-backlog: gap_ledger, gap_classifier, route /codie (1.518 regels + 1.485 tests) —
machine-geschreven probleemstellingen voor een AI-programmeur die nooit heeft opgeleverd (0
deliverables, gearchiveerd 18 sept). /belofte ("unproven 0/23 grounded") gaat mee, zelfde reden.
/catalog blijft (8 KPI-definities met echte data) maar verhuist naar onder Metrics, niet als los
scherm met "Librarian" in de titel.

Ook opruimen in cli.py: alle 27 AI/notes-tijdperk modes (harry_hemp, harry_run,
content_strategist*, librarian, reflect, discovery, synthesize, recurate, notes_remove al gedaan in
fase 2, kennis_migrate al gedaan in fase 2, add_seed, radar_embed, competitor, community_listening,
work_projects, montecarlo al gedaan in fase 2, review_roles, teleology_*, grant_serpapi_trends,
upgrade_harry_role, ask_accountability, grant_accountability). Wat overblijft in cli.py: run, once,
inbox approve, seeds, healthcheck, wiki_zaad, doelen_zaad, status_log, plus de afslank-tooling
(afslanken/afslank_wezen/sluitronde/waarde_audit/villageraad/les/poort — die blijft, is nog in
gebruik voor dit traject zelf).

Volledige testsuite voor/na (grootste fase qua bestandenaantal, neem er de tijd voor), diff, laat
zien welke routes/views/modules precies weg zijn, commit en ga door naar fase 4.
```

## Fase 4: radar-beoordelingslaag eruit, swipefile blijft ongefilterd (nog geen maandrapport)

Stefans definitieve besluit (audit §11): geen goedkeuren per signaal, geen wachtrij, geen
wekelijkse beoordeling. Feeds landen ongefilterd in een swipefile per onderwerp, en pas het
maandrapport (een LLM-job in de geplande-taak-mechaniek) leegt de bak. **Die mechaniek bestaat nog
niet.** Deze fase bouwt hem dus niet — verwijdert alleen de beoordelingslaag, zodat de swipefile vast
al vult zonder dat er een dode wachtrij-UI naast blijft staan. Uitzondering: de legal-feed krijgt wél
een klein los stukje nieuwe code, want dat is geen rapport maar een dagelijkse inbox-check, en die
bestaat al onafhankelijk van de geplande-taak-mechaniek (het patroon van `_meld_weesprojecten` in
village.py, rol-onafhankelijk sinds 16 sept).

```
Verwijder de radar-beoordelingslaag: views/signals.py (322), radar_beoordeling.py (273),
radar_promote.py (277), radar_nieuwheid.py (232), radar_clusters.py BEHALVE het bronnen-tellende
deel (behoud ~100 van de 330 regels, dat telonderdeel heb je straks weer nodig in het maandrapport —
zet het apart in een kleine losse functie, niet weggooien), views/linkbuilding.py (78),
link_targets.py/link_suggest.py (link_suggest.py is al weg via fase 2), news_distill.py (275),
project_signal.py (331 — een afgerond project hoort straks in de wiki via Keep-in-wiki, niet in de
radar), de hele community-listening/buzz-tak (community_listening.py 312 + buzz_fetchers 438),
competitor_discover.py (243), competitor_news.py (246, let op: wordt nu nog door /signals
gerenderd, verdwijnt vanzelf mee), competitor_brands (onderdeel van de 588 samen met discover), en de
bijbehorende _act_radar_*/link_*-handlers in cockpit2.py.

Laat inoreader_ingest.py (191) en een uitgeklede radar_store.py staan: dit wordt de swipefile.
Ontdubbeling op artikel-URL blijft (~10 regels), verder geen status/cluster/promotie meer — een
signaal landt en blijft liggen tot de maandjob (nog te bouwen) hem leegt. Hang inoreader_ingest.py
aan de dagcyclus (dag_begint) in plaats van een externe cron als dat nu zo draait — check dat eerst
zelf op de server/in de deploy-config (dit is niet vanaf hier te verifiëren); als je het niet zeker
kunt vaststellen, stop en vraag het aan Stefan voor je dit onderdeel doorvoert.

Bouw wel, klein en apart, de legal-inbox-check: een dagelijkse functie (patroon: _meld_
weesprojecten in village.py) die de Legal & Green Claims-feed checkt op "nieuw én relevant voor
Nooch" (LLM-classificatie, side-effect-free zoals onderzoeksvraag.py) en bij een treffer één
human_inbox-item aanmaakt voor de founder. Niets anders: geen rapport, geen wachtrij, één
inbox-item per treffer.

Bouw het maandrapport zelf (Concurrentie & Industry samengevoegd, en Materials Innovation, elk als
wiki-pagina, bak leeg na het rapport) NIET in deze fase — dat hoort in de geplande-taak-mechaniek en
is een apart traject. Laat de swipefile dus na deze fase groeien zonder dat er nog iets mee gebeurt;
dat is correct en tijdelijk.

Volledige testsuite voor/na, diff, commit en ga door naar fase 5 — tenzij de cron-vs-dagcyclus-status
van inoreader_ingest onduidelijk blijft, dan eerst stoppen en aan Stefan vragen.
```

## Fase 5: claims loskoppelen van rol/persona

Geen opruimvraag zoals de rest — de 4.300 regels claims-code blijven vrijwel allemaal, dit is het
best werkende, meest gebruikte stuk van het hele dorp (281 uitvoeringen in 60 dagen). Het is een
governance-vraag die is beantwoord: geen domeineigenaar meer nodig, gewoon een tool die een mens
draait.

```
Haal claims_site_scan en regulation_watch uit pulse_skills (config/settings.ini) — geen dagelijkse
puls meer, ze worden knoppen op /claims (de scan-knop bestaat al: /claims/scan, voeg toe waar nodig
voor regulation_watch). Verwijder de _role_gate op claims-curatie in cockpit2.py ("cureren is
exclusief compliance"): wie ingelogd is mag de term-database bijwerken, geen domein-eigenaar-poort
meer.

Verwijder de persona-plumbing in claims_check.py/claim_evidence.py: de escaleer/projectverzoek-
aanroepen (deze twee skills bestonden om AI-rollen werk naar mensen te schuiven — 198 van de 578
Kroniek-records in 30 dagen waren "werk doorgeven", geen werk doen) en de project_verslag-koppeling
(project_verslag.py is al weg via fase 3). Vervang "werk doorgeven" waar het nog een functie heeft
door een simpele dropdown op het project (assignee wijzigen), geen aparte skill.

De rest van het claims-cluster (claims_board.py, claims_db.py, claims_substantiatie.py,
claim_oordeel.py, claims_modelpas.py, claims_verify.py, claims_context.py, claims_labels.py,
claim_classify.py, views/claims.py) blijft ongewijzigd staan — dit is geen opruiming, alleen de
persona-koppeling eraf. Ook qua UI blijft /claims in deze fase ongemoeid; het krijgt in fase 9 pas
het nieuwe visuele ontwerp, als een bewuste keuze (zie daar).

Volledige testsuite voor/na, diff, laat expliciet zien wat je uit settings.ini en de role_gate hebt
gehaald, commit en ga door naar fase 6.
```

## Fase 6: cockpit2.py, de laatste views-laag, skills_impl groep 1+2

Laatste opruimfase: opruimen wat overblijft nadat fase 1-5 hun eigen routes/handlers al hebben
meegenomen. Dit bereidt ook de latere routetabel-refactor voor (niet in deze brief: eerst dode
deuren weg, dán een tabel bouwen, nooit andersom), én de interface-fases 7-9 hierna: hoe minder dode
routes er nog liggen, hoe minder je in fase 7 hoeft te ontwarren.

```
In cockpit2.py: verwijder de resterende dode POST-handlers die nergens een formulier hebben dat ze
verstuurt (controleer eerst of fase 1-5 ze al hebben meegenomen, wat overblijft is voornamelijk):
ai_reply, kb_annotate, kb_atoom_related, kb_evidence, kb_intake_url, kb_new, kb_reformulate,
kb_stage_edit, m_add_from_def, notif_processed, notif_read, proj_comment, proj_dod, proj_edit,
proj_setlabel. En de routes die nergens als link voorkomen, alleen bereikbaar door de URL te typen:
/_patterns (levende stijlgids van de oude cockpit — verdwijnt sowieso in fase 9, het nieuwe
designsysteem vervangt hem), /catalogus_koppelen (catalog_koppelen.py, 232 regels — check eerst of
iemand anders dan Stefan dit ooit heeft gebruikt; kun je dat niet vaststellen, stop en vraag het aan
Stefan), /claims/db.json (check eerst of dit een extern gebruikt endpoint is voor iets buiten de
cockpit; kun je dat niet uitsluiten, stop en vraag het aan Stefan, niet blind verwijderen).

Let op voor fase 8 hierna: notif_processed/notif_read staan hierboven als dode POST-handlers (geen
formulier stuurt ze aan) — dat is precies het @-notificatiepad dat fase 8 vervangt door de
channel-laag. Verwijder ze hier gewoon als dode handlers zoals gepland; fase 8 regelt de vervanging
van wat er functioneel voor in de plaats komt.

In views/: halveer views/checklists.py (661 regels) door de skill-matching per item te verwijderen
("○ no skill · needs a human", regel 254-260) en de hand-off-flow (_act_check_handoff in
cockpit2.py, 46 regels) — zonder AI-uitvoerder is een checklist-item een tekstregel met een vinkje.
Verwijder views/strategy.py (153) + strategy_store.py (38): staat in _TAB_LABEL maar niet in
_CIRCLE_TABS, wordt sowieso nooit getoond.

Verwijder de speeltuin, alle drie zonder discussie: /snake + het bijbehorende highscore-endpoint
(217+27), /callbar + /livekit-token + /livekit-presence (391 + 3 handlers), /epic/frame (NASA-
widget, zie ook codereview_live_systeem_19sept.md voor het eigen verwijderplan daar).

In skills_impl/: verwijder groep 1, nooit door iemand gehouden, nooit uitgevoerd, geen collector,
niet vanuit de cockpit aangeroepen (11 modules, 2.139 regels): accountability_check (deels al weg
via fase 3, check overlap), bulletin_schrijven, cert_evidence, lead_beoordeling,
openlibrary_search_inside, pappers_financials, serpapi_trends, site_watch, synthesize (al deels weg
via fase 2, check overlap), trustpilot_reviews, zoekstrategie. Verwijder groep 2, alleen gehouden
door nu-gearchiveerde rollen, geen ander pad (2.815 regels, zie audit_diep_cockpit_views_skills_
19sept.md §2 voor de volledige lijst met exacte regelaantallen): trend_reindex, ngram,
community_listening (al weg via fase 4, check overlap), semantic_scholar, competitor_discover (al
weg via fase 4), library_skills, content_check, content_schrijven, field_note, onderzoeksvraag —
LET OP: dit is een ANDERE onderzoeksvraag dan de skill die je in fase 2 als patroon hergebruikt voor
kennis_context, controleer dat je niet de verkeerde weggooit — verband_voorstel, kroniek_interpret,
ruis_check, curate, competitor_news (al weg via fase 4).

Verwijder alphavantage.py (131) en gdelt_tone.py (151): voedden de Tijdgeest-lens van Harry, die er
niet meer is. De overige databron-collectors (plausible, gsc, gsc_report, shopify_sales, trends,
trends_categorie, co2_village, mobiel_audit) blijven, die zijn rolonafhankelijk en leveren nog
gebruikte metrics.

Verwijder epo_patents/google_patents/openalex NIET (995 regels, patentskill-roadmap) — deze
moeten losgekoppeld worden van hun oude persona-aanroep en herbelegd als cockpit-tool die een mens
vanuit een project start, maar dat is scope van `roadmap_volwaardige_patentskill.md`, niet van deze
opruimfase. Hier alleen: verifieer dat er geen dode aanroep vanuit een net-verwijderde rol op
achterblijft.

Volledige testsuite voor/na, diff, en rapporteer aan het eind van deze fase het totale regelaantal
vóór fase 1 en ná fase 6 (broncode + tests apart), zodat er een harde afsluitcijfer is voor het
opruimdeel van dit traject. Commit en ga door naar fase 7.
```

## Fase 7: navigatie + Wiki/Tools/Policies-consolidatie + Keep-in-wiki-ingang, naar het prototype (v15)

Eerste interface-fase. Doel: de vaste zijbalk en schermindeling van het prototype (live artifact
versie 15, https://claude.ai/artifact/Y76cYZFUvYiAzp6oweqeD1) overzetten naar de live cockpit, met de
bestaande data erachter (`AttachmentStore`, `ProjectLedger`, `HumanInbox` — geen van drie hoeft
qua schema te veranderen, zie `zoomout_informatiearchitectuur.md`). Nog geen nieuwe visuele stijl
(dat is fase 9): deze fase gaat over structuur, niet over hoe het eruitziet.

```
Begin met een korte audit, zelf uit te voeren, voor je iets bouwt: breng de huidige nav in
cockpit2_util.py/cockpit2.py in kaart (welke tabs/routes bestaan nu, wat is de huidige indeling) en
leg die naast de vaste zijbalk van het prototype: Projects (landing), Inbox (lade, "+ tension"),
Messages, Wiki, Circle, Admin, organisatieboom. Rapporteer de diff (wat moet verhuizen, wat moet
samenkomen, wat blijft) voor je begint te bouwen — dit is niet vanaf hier te verifiëren, dus neem
geen aanname over hoe de huidige nav in elkaar zit.

Bouw daarna:
1. Projects als eigen scherm/landing (in het prototype al zo; in de live cockpit waarschijnlijk nog
   een tab of gedeeld met iets anders — volgt uit je eigen audit hierboven).
2. De Policies/Notes/Tools-consolidatie afmaken: in fase 2 is de data-laag al opgeruimd en een
   tijdelijke doorverwijzing naar Wiki gezet. Bouw hier de echte, prototype-gelijke Wiki-tab met een
   filter (hetzelfde `AttachmentStore.kind`-onderscheid: note/tool/policy, één surface, een
   filter/badge per soort — exact het patroon dat `zoomout_informatiearchitectuur.md` beschrijft als
   al mogelijk zonder migratie).
3. Keep-in-wiki: een nieuwe ingang vanuit een project-conversatie (of straks een cirkel/persoon-
   kanaal, zie fase 8) om één feit op een gekozen wiki-pagina te zetten, met herkomst. De opslag
   bestaat al (`AttachmentStore.meta["feiten"]`), dit is puur de nieuwe ingang, zoals het prototype
   'm toont.
4. Voertaal naar Engels waar de UI nu Nederlandse labels heeft (het prototype's eigen v15-fix
   "Admin · Mensen" → "Admin · People" is het voorbeeld van het patroon, zoek naar vergelijkbare
   resten).
5. Zoeken (/, Cmd+K) en de organisatieboom blijven in deze fase op titel-niveau (contentindexering
   is fase 8), maar moeten over de nieuwe schermindeling heen blijven werken — check dat expliciet.

Testdiscipline: 3-5 tests per scherm dat verandert (jouw regel voor routinefeatures), plus een
handmatige doorloop tegen het prototype als referentie voor elke aangepaste flow — het moet zich
hetzelfde gedragen als daar, niet alleen "niet meer crashen".

Volledige testsuite voor/na, diff, commit en ga door naar fase 8.
```

## Fase 8: channel-laag (project/cirkel/persoon) vervangt wall + @-notificaties direct, plus zoeken op inhoud

Geen naast-elkaar-periode: dit vervangt de bestaande wall en @-notificaties meteen, geen losse
migratie later. Stefans instructie hierbij: een @-vermelding hoeft geen eigen notificatiemechaniek
te houden, dat kan gewoon een bericht zijn dat in het persoonlijke kanaal van de vermelde persoon
terechtkomt — het persoon-kanaal (één van de drie kanaaltypes hieronder) is dus meteen ook de
vervanger van de huidige @-notificatie.

```
Bouw één gedeelde channel-store: een kanaal per project, per cirkel en per persoon, met trail en
replies als één stroom (zoals het prototype's project-detail "Conversation"-sectie toont). Het
persoon-kanaal is de "personal channel": elke gebruiker heeft er één, en dat is meteen de vervanger
van de huidige @-notificatie (zie hieronder).

Vervang de bestaande wall en @-notificaties DIRECT door deze channel-laag, geen tijdelijke
naast-elkaar-situatie en geen losse migratiefase later. Concreet: een `@vermelding` (in een project-
of cirkel-kanaal, of waar die vandaag ook vandaan komt) wordt voortaan simpelweg een bericht dat in
het persoonlijke kanaal van de vermelde persoon terechtkomt. Er is geen aparte notificatietabel meer
nodig naast de channel-store zelf.

Audit eerst zelf welke routes/handlers/opslag het huidige @-notificatiepad verzorgen. Let op: in
fase 6 zijn notif_processed en notif_read al verwijderd als dode POST-handlers (geen formulier
stuurt ze aan) — check of dat de volledige @-notificatie-machinerie dekt, of dat er toch nog een
levend stuk is dat je over het hoofd ziet (bijvoorbeeld hoe een vermelding vandaag daadwerkelijk
zichtbaar wordt voor de vermelde persoon, ook als de decision-handlers zelf al dood waren). Verwijder
wat overblijft van het oude pad na de vervanging — niets blijft er dubbel naast bestaan.

Laat `human_inbox` los van deze channel-laag: dat blijft de wachtrij voor nog-te-behandelen items,
geen kanaal, geen trail.

Breid zoeken uit van titel-only naar ook wiki-body, gespreksinhoud (de nieuwe channel-trail) en
checklist-items.

Testdiscipline: zelfde als fase 7 (3-5 tests per onderdeel, handmatige doorloop tegen het
prototype), plus een expliciete test dat een @-vermelding nu als bericht in het juiste persoonlijke
kanaal landt, en dat er nergens meer een dubbele of verweesde melding via het oude pad binnenkomt.

Volledige testsuite voor/na, diff, commit en ga door naar fase 9.
```

## Fase 9: het visuele ontwerp (Nooch UI v1) op de herbouwde schermen

Laatste fase van deze ronde. Let op: dit is een ANDER traject dan `designsysteem_fase2_
inventaris.md` (14 juli) — dat ging over het opschonen van de bestaande, oude cockpit-CSS-
klassenset (nooch.css, 425 selectors, 58 prefix-families). Dit hier is een compleet nieuw visueel
systeem, exact zoals het prototype het toont: 2px zwarte randen, één neongroen accent per scherm,
status altijd als vorm plus woord (nooit kleur alleen).

```
Bouw het nieuwe visuele systeem als een eigen, klein tokenbestand (kleur, rand, radius, status-vorm)
naast de bestaande nooch.css, niet erin vermengd — de oude klassenset en het nieuwe systeem lopen
door elkaar heen als je ze samenvoegt, en dat maakt precies de wildgroei die de juli-inventarisatie
al signaleerde erger, niet beter.

Pas het nieuwe systeem toe op elk scherm dat in fase 7 en 8 is herbouwd of aangeraakt: Projects,
Wiki (incl. de Policies/Notes/Tools-consolidatie), Keep-in-wiki-ingang, de nieuwe channel-laag
(incl. het persoonlijke kanaal), Circle, Admin, organisatieboom, zoeken. De governance- en
tactical-meeting-modals (bestaan al functioneel) krijgen dezelfde visuele stijl, geen functionele
wijziging.

Schermen die in fase 1-8 niet zijn aangeraakt qua UI (bijvoorbeeld /claims, dat in fase 5 alleen
persona-ontkoppeld is) hoeven in deze fase niet mee. Dat is een bewuste keuze, geen vergeten stuk:
meld expliciet aan Stefan welke schermen je om die reden overslaat, zodat hij kan beslissen of dat
een aparte, tiende fase wordt of blijft staan zoals het is.

Eindcheck: een screenshot-vergelijking (zelfde methode als de prototype-audits — Playwright,
screenshots op desktop- en mobielbreedte) tegen de bijbehorende prototype-schermen. Het gaat hier
niet alleen om "het werkt", ook om "het oogt hetzelfde".

Commit — laatste fase van deze ronde. Meld aan Stefan: het totale regelaantal-eindcijfer uit fase 6,
welke schermen in fase 9 bewust zijn overgeslagen, en alle stopmomenten die zich in fase 1-9 hebben
voorgedaan (ook de niet-kritieke, en welke keuze je zelf hebt gemaakt waar je niet hoefde te
stoppen).
```

## Wat hierna nog open staat

- De geplande-taak-mechaniek zelf (nodig voor: het maandrapport dat straks in de Wiki-schermen uit
  fase 7 landt, materiaal-memo, site-audit-cadans; de legal-check uit fase 4 kan al zonder) — eigen
  traject, `ontwerp_geplande_taak_mechaniek.md`. De schermen/navigatie/wiki-structuur hoeven daar
  niet op te wachten (zie de toelichting hierboven), de inhoud van de maandrapport-pagina's wel.
- `cockpit2.py`'s routetabel + splitsing per domein — pas beginnen als fase 6 is gedraaid, anders
  bouw je een tabel voor dode deuren.
- De schermen die in fase 9 bewust zijn overgeslagen (te bepalen tijdens die fase zelf) — apart te
  beslissen: los laten, of een tiende fase.

---

# Fase 10 — de hele Village in de nooch.earth-huisstijl, plus drie losse punten

*Toegevoegd op 20 september 2026. De fase 10-tekst stond tot dan toe alleen in Stefans eigen
Claude-project en niet in de repo; de versie die met PR #516 meekwam eindigde bij fase 9. Punt 1, 3
en 4 staan hieronder letterlijk zoals Stefan ze gaf. Punt 2 is samengevat uit de opdracht van
diezelfde avond, met de uitkomst van de inventarisatie erbij — zie
`claude/fase10_huisstijl_inventarisatie.md` voor de volledige meting.*

**Werkwijze voor alle vier de punten:** 3 à 5 tests per onderdeel, handmatige doorloop, per punt
apart rapporteren en per punt apart committen — niet alles in één grote commit.

## Punt 1 — Messages: zoek/filter, en het losse-kanaal-concept

Bouw sowieso een zoek/filterveld boven de projectkanalen-lijst — dat staat los van de rest en lost
het acute onbruikbaarheidsprobleem op.

Voor het losse-kanaal-concept: doe eerst een korte inventarisatie van het huidige channel-datamodel
(project/circle/dm, zie fase 8) en stel voor hoe een vierde soort — een los, zelf te noemen kanaal
zonder project/cirkel/persoon eraan — daar het best in past (nieuwe kind, wie mag het aanmaken, hoe
verschijnt het in de kanalenlijst). Leg dat voor voor je bouwt, dit is een nieuw
datamodel-begrip.

## Punt 2 — de huisstijl over de hele Village, niet alleen de negentien fase-9-schermen

"Zorg dat Village ook in deze design stijl eruit ziet" was bedoeld voor de héle Village-app. Het
bindende ijkpunt is de live nooch.earth-huisstijl, vastgelegd in
`claude/huisstijl_referentie_productpagina.jpg` en `claude/huisstijl_referentie_email.png` — niet de
fase-9-tokens op zich, en niet een beschrijving in woorden.

**Kleurwaarden komen uit de pixels**, gesampled met een script, niet uit een beschrijving. De
uitkomst van die sampling staat in `claude/fase10_huisstijl_inventarisatie.md` §5.

**Knoppen:** groen blijft voorbehouden aan de primaire CTA, niet elke `.btn`. Secundaire en
tertiaire knoppen worden wit/transparant met zwarte rand en zwarte tekst, in hetzelfde vocabulaire
als de rest.

**Scope: groep A, B én C**, in deze volgorde:

- **Groep A** (route staat in `_NU_ROUTES`, maar de markup gebruikt het gedeelde vocabulaire niet —
  `wizard.py`, `projects.py`, `inbox.py`, `roloverleg.py`, `overview.py` e.a.): begin met de
  goedkoopste winst, de `att-*`- en `qadd-*`-families (~40 gebruiken over zes views in één klap),
  daarna de rest van groep A.
- **Groep B** (`/site-audit`, `/middelen`, `/rolefillers` — dezelfde rendercode als routes die wél
  meedoen): de twee regels fixen, kost weinig.
- **Groep C** (`/werkoverleg`, `/roloverleg2` — nooit herbouwd): als laatste, dat is de grootste
  klus.

## Punt 3 — het dubbele Organization-paneel op Circle-pagina's

Verwijder of verklein het rechter Organization-paneel op Circle-pagina's. De organisatieboom blijft
in de linkerbalk staan (ongewijzigd), de volledige rollenlijst blijft bereikbaar via de bestaande
"Roles"-tab. Geen functionaliteit verdwijnt, alleen de dubbele weergave.

## Punt 4 — inline bewerken in plaats van een apart bewerkformulier

Onderzoek eerst hoe het huidige edit-formulier is opgebouwd (welke velden, hoe wordt opgeslagen,
welke rechtencheck) voor je de UI omzet naar inline bewerken (in de pagina zelf klikken en typen,
opslaan zonder aparte pagina-navigatie). Behoud dezelfde rechtencheck en dezelfde
version/change_note-opslag als nu.
