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

*Aanvulling tijdens fase 2 (19 sept, avond): de import-graaf bleek groter dan de brief aannam
(notes_store.py had 12 in plaats van de aangenomen paar importers, kennis_context.py 7). Zie de
uitgebreide Fase 2 hieronder voor het definitieve besluit: alles eruit, inclusief
publication_check.py en de twee copywriter-skills die het aanriepen, omdat die laatste twee toch al
geen levende aanroeper meer hebben (copywriter-rol is gearchiveerd). Dat is bewust vervroegd uit
fase 6.*

*Tweede aanvulling tijdens fase 2 (19 sept, avond): een aparte store, kennisbank.py
(data/kennisbank.json), bleek niet hetzelfde als notes_store.py (data/notes.json) en voedt de skill
weten_we_dit_al, die vandaag nog in het DNA van twee levende, mens-vervulde rollen zit
(financial_controller, strategic_lead_founder_steward — Stefans eigen rol). Besluit: kennisbank.py
en de store blijven ongewijzigd staan, alleen de eromheen liggende UI gaat weg (die viel al onder de
kennisbank-familie hierboven). Zie de eigen subsectie in Fase 2 hieronder.*

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
`data/notes.json` is vandaag opnieuw gecontroleerd. De brief nam aan dat notes_store.py en
kennis_context.py maar een handvol importers hadden; de echte import-graaf, tijdens de uitvoering
zelf opgevraagd, gaf een groter beeld (zie de aanvulling hieronder). Dit is de definitieve, bijgestelde
versie van fase 2.

```
NotesStore (notes_store.py, 625 regels) en de kennisbank-familie eromheen kunnen weg: nul nieuwe
records sinds 17 juli, het rendermechanisme haalt al twee maanden nul kaartjes boven zijn eigen
drempel (EMERGENCE_THRESHOLD, emergence.py:17,20).

Verwijder direct, geen vervanging nodig (eenmalige/handmatige onderhoudsscripts):
notes_store.py, kennisbank_seed.py, kennis_context.py se eigen store-laag (niet de aanroeper, zie
hieronder), kennis_merge.py, kennis_tags.py, kennisbank_reatomise.py, kennisbank_bronherstel.py,
tag_onderhoud.py, herkomst_verrijking.py, plus hun CLI-entries in cli.py (kennis_migrate,
notes_remove, en de overige notes/kennis-gerelateerde modes).

Daarnaast, gebleken tijdens je eigen import-graaf-check en bevestigd als eenduidig: verwijder ook
kennisbank_intake.py (326), kennisbank_staging.py (305), embed_opruimen.py (126), en de vier
kennisbank-views (views/kennisbank.py + _staging + _spel + kennislaag.py, samen 1.526 regels) plus
hun zes routes (/kennisbank, /kennisbank/search, /kennisbank/tags, /kennisbank/staging,
/kennisbank/spel, /inzichten). Dit is puur UI/pijplijn bovenop dezelfde dode store, geen aparte
afweging nodig.

**Publication_check.py en de twee copywriter-skills, vervroegd uit fase 6**: publication_check.py
(126 regels) leest notes_store.py inhoudelijk — unverified_claims() toetst of een kaartje de status
VERIFIED heeft vóór publicatie, een fail-closed poort. Die poort heeft precies twee echte aanroepers:
skills_impl/content_check.py en skills_impl/content_schrijven.py (claims_substantiatie.py noemt hem
alleen in een docstring, geen echte import). Beide skills stonden al op de verwijderlijst van fase 6
(skills_impl groep 2), gehouden door de nu-gearchiveerde copywriter-rol, geen ander pad. Stefans
besluit: trek die twee skills naar voren uit fase 6 en verwijder ze hier, samen met
publication_check.py. Voorwaarde, verifieer dit expliciet voor je iets weghaalt: bevestig dat de
copywriter-rol inderdaad gearchiveerd is en dat geen enkele levende thread of cockpit-actie
content_check.py of content_schrijven.py vandaag nog aanroept. Klopt dat, dan heeft de poort geen
enkele aanroeper meer over (dood, niet halfdood: geen fail-closed-verrassing later, want er is
niemand meer die er tegenaan loopt) en kunnen alle vier (notes_store.py, publication_check.py,
content_check.py, content_schrijven.py) inclusief hun tests (waaronder test_publication_check,
test_verified_check, test_review_publication, test_scope56_compliance) nu weg. Is er toch nog een
levend pad dat je over het hoofd had gezien, stop en meld dat in plaats van door te zetten. Noteer
voor jezelf dat fase 6 deze twee skills dan niet nogmaals hoeft te verwijderen.

**kennisbank.py + data/kennisbank.json blijven vooralsnog staan, dit is geen dode store**: tijdens de
uitvoering bleek een tweede, ander store dan notes_store.py/data/notes.json — kennisbank.py (460
regels, KennisbankStore(data/kennisbank.json)) — die de skill weten_we_dit_al voedt. Die skill zit
vandaag in het DNA van twee levende, mens-vervulde rollen: financial_controller en
strategic_lead_founder_steward (Stefans eigen rol). Dit is dus organisatiegeheugen dat nu actief
gebruikt wordt, geen stilstaande kaartjes-store. Besluit: kennisbank.py en de store blijven precies
zoals ze zijn, alleen de UI eromheen gaat weg (kennisbank_intake.py, kennisbank_staging.py, de vier
kennisbank-views en hun routes — al hierboven meegenomen). Geen vervanging bouwen, geen halve
maatregel: weten_we_dit_al blijft werken zoals hij nu werkt. Bewaar dit als een latere, aparte
ontwerpvraag (niet in deze fase, niet in deze opruimronde): weten_we_dit_al ooit migreren naar
dezelfde Wiki-laag (AttachmentStore) als de rest van de kennis, in lijn met "twee concepten voor
kennis: Wiki en Channels, geen aparte stores" (state_19sept.md, besluit 1) — maar dat is een bewuste
ontwerpkeuze voor later, niet iets om nu terloops mee te nemen.

Eén plek heeft wel een vervanging nodig: kennis_context.py wordt aangeroepen vanuit project_worker.py
(bij het opstarten van een nieuw project, "REEDS BEKEND"-blok) en, bleek uit de import-graaf, ook
vanuit onderzoekspas.py (dezelfde soort contextvraag, in de claims-keten maar side-effect-free) en
vier andere plekken (inhabitant.py op 3 plekken, key_audit.py, embed_opruimen.py — laatste verdwijnt
toch al mee, cockpit2.py, skills_impl/voorstel.py). Vervang ALLE aanroepen van kennis_context.py door
een verse AI-onderzoeksaanroep in dezelfde stijl als de bestaande onderzoeksvraag-skill
(skills_impl/onderzoeksvraag.py, side_effect_free=True, één LLM-call op de meegegeven payload, niets
zelf opgeslagen) — niet alleen bij project_worker, overal waar kennis_context vandaan werd
aangeroepen. Let op: dit is een andere `onderzoeksvraag` dan de skill die in fase 6 als groep-2-lid
wordt weggehaald (zie de waarschuwing daar) — verwar de twee niet.

Verwijder daarna de losse orphan-modules waar Stefan op 19 sept al over besloten heeft (zie
state_19sept.md): montecarlo.py, attribution.py, claims_migrate.py, concept_suggest.py,
link_suggest.py, projects_cli.py. orphan_report.py: laat vooralsnog gewoon staan, code-niveau, niet
verwijderen in deze fase — er is geen importer en geen spoor op de server (geen cron, geen timer,
geen deploy-log-vermelding), maar of hij ooit handmatig is gedraaid staat nog open bij Stefan. Kost
niets om te laten staan tot dat antwoord er is. inoreader_ingest.py blijft (nodig voor de
radar-ingest, fase 4).

Verifieer ook kort (git log volstaat) wat data/notes.json op 10 september heeft aangeraakt — het
bestand zelf is die dag om 20:45 aangeraakt, ook al zijn er sinds 17 juli geen nieuwe records bij
gekomen. Is dat een onschuldige touch (geen actief schrijfproces eronder), dan is dat voldoende om
door te gaan; is er toch een proces dat nog op dit bestand leunt, meld dat apart.

Ook weg, want puur onderdeel van de kennisbank-UI die nu geen doel meer dient: de drie
Policies/Notes/Tools-tabs in cockpit2_util.py (regel 62-72) en hun renderpaden in views/overview.py.
Vervang ze hier alleen door een tijdelijke doorverwijzing naar de bestaande Wiki-tab (geen filter
nog) — de echte, prototype-gelijke Wiki-tab-met-filter wordt in fase 7 gebouwd, samen met de rest van
de navigatie; dit is bewust in twee stappen geknipt zodat fase 2 zich tot data/opruiming kan
beperken.

Volledige testsuite voor/na (dit raakt relatief veel bestanden, extra aandacht hier, en nu ook de
claims-tests expliciet vanwege publication_check.py), diff, laat expliciet zien welke bestanden zijn
verwijderd en welke vervangen (alle kennis_context.py-aanroepers, Policies/Notes/Tools → tijdelijke
Wiki-doorverwijzing), commit en ga door naar fase 3.
```

## Fase 3: AI-projectuitvoering + Founder Flow + Codie-backlog eruit

Dit is het grootste blok qua regels (~9.500 broncode + ~9.750 tests), en het meest eenduidige: drie
losse dingen die alle drie hetzelfde zijn — machinerie gebouwd voor een AI die een project uitvoert
en zichzelf daarop beoordeelt, en die AI bestaat niet meer. Stefan heeft dit vanavond zelf zo
verwoord: "een project een deliverable laten krijgen is misschien overkill, borg het in de wiki met
menselijke input" — dat is precies Keep-in-wiki, wat al in het prototype zit. Geen van de drie
onderdelen hieronder heeft dus een vervanging nodig.

**Correctie tijdens fase 3 (19 sept, avond) — BLOK A was niet idle**: de audit (§1/§7) noemde
BLOK A "Idle" op basis van de verkeerde velden (executions/critic_verdict/resultaat in een
9-sept-snapshot). De echte call-sites (`data/llm_usage.jsonl`, `data/gaps.jsonl`, `data/
draaistaat.jsonl` op prod) laten zien dat de cluster tot en met vandaag draait, en wel op Stefans
eigen rol (strategic_lead_founder_steward) en compliance: `deliverable_conclusie` is de duurste
LLM-call-site van het hele systeem, `plan_checklist`/`ronde_twee_leads` draaiden vanochtend. §1's
eigen genoemde methode-aantallen (16/1.172, 8/410) zijn bovendien niet reconstrueerbaar tot een
eenduidige helper-set — meerdere verschillende subsets geven hetzelfde totaal. Stefans besluit,
expliciet gevraagd en gegeven: BLOK A gaat nu toch weg, ondanks dat het leeft, want dat is precies
wat "borg het in de wiki met menselijke input" betekent — een project naar "Actief" slepen levert
vanaf nu geen automatische checklist meer op, en er komt geen automatische deliverable-notitie meer.
Dat is een bewuste, per-direct-ingaande gedragsverandering op Stefans eigen dagelijkse workflow, geen
opruiming van dode code. Consequentie voor de uitvoering: gebruik niet §1's ambigue 9+4-subset, maar
de volledige aanroep-closure van de BLOK A-entry-points (prepare_project, _plan_checklist,
_execute_checklist, _critic_gate, _deliverable_note, _ronde_twee, _herplan_na_strategie, sensing-
cluster) — elke helper die uitsluitend door deze cluster wordt aangeroepen gaat mee, alles met een
aanroeper buiten de cluster (zoals `_run_pulse_skills`) blijft staan.

```
Verwijder de volgende drie AI-projectuitvoeringsblokken volledig, inclusief hun cockpit-routes,
views en tests. Geen van drie heeft een vervanging nodig (Keep-in-wiki dekt de vervanging al, staat
in het prototype, wordt in fase 7 als ingang gebouwd).

BLOK A — projectuitvoering in inhabitant.py (960-2117). Gebruik niet audit_diep_cockpit_views_
skills_19sept.md §1's methode-aantallen (die bleken niet reconstrueerbaar en de "Idle"-claim daar
was fout, zie de correctie hierboven) — bepaal zelf de volledige aanroep-closure van: prepare_project,
_plan_checklist, _execute_checklist, _critic_gate, _deliverable_note, _ronde_twee,
_herplan_na_strategie, plus de sensing-cluster _sense_gap/_sense_redundancy/_opportunity_reflex/
_raise_governance_proposal. Alles wat uitsluitend door deze cluster wordt aangeroepen gaat mee.
Laat staan wat een aanroeper buiten de cluster heeft, met name _run_pulse_skills (blijft actief nodig
voor de mens-vervulde rollen met periodieke skills).

Dit is bevestigd levende code (niet idle, zie de correctie hierboven): de cluster wordt vandaag nog
aangeroepen vanuit _on_project_activated, _tend_projects, run_project, triage en _maybe_reflect.
Verwijderen van BLOK A betekent dat elk van deze vijf aanroep-plekken aangepast moet worden zodat ze
niet meer naar een verwijderde methode verwijzen — niet alleen de BLOK A-methoden zelf weghalen.
Kies per aanroeper de kleinst mogelijke aanpassing die geen dode aanroep achterlaat (meestal: de
aanroep eruit, zonder vervangende actie — een checklist en een deliverable-notitie worden vanaf nu
handmatig aangemaakt, dat is precies het bedoelde gedrag). Test expliciet dat een project naar
"Actief" slepen niet meer crasht nu de checklist-aanroep weg is.

Bijvangst voor fase 6: lead_beoordeling en curate (audit §2, groep 1 resp. groep 2) draaiden 18 sept
op strategic_lead_founder_steward via _use_skill_with_ladder — dat pad hoort bij BLOK A. Verwijder ze
hier, als onderdeel van dezelfde closure, in plaats van te wachten op fase 6; noteer dat voor fase 6
zodat die ze niet nogmaals hoeft te doen.

**Correctie tijdens BLOK B (19 sept, avond) — /rapport was niet leeg, en toch weg**: de audit §3E
("0 van 386 projecten heeft er een") bleek de derde onbetrouwbare premisse in dit document (na
"Idle" voor BLOK A en de BLOK C-bestandenlijst hieronder). Op prod staan 363 einddocumenten
(`data/project_docs`, 3,0 MB, nieuwste van 18 sept), en /rapport is geen verborgen scherm — elke
projectkaart linkt ernaartoe (`views/projects.py:1106`). Eerste besluit was: reader houden, alleen de
assembler (`stel_samen`) weg. Stefans definitieve besluit, direct daarna: nee, de oude content mag
gewoon weg, "we beginnen opnieuw, no pasa nada" — dus toch de volledige /rapport-verwijdering zoals
oorspronkelijk in deze brief stond, inclusief project_verslag.py en de 363 bestaande documenten. Ze
worden niet gemigreerd naar de Wiki, ze vervallen gewoon (de bestanden blijven fysiek op schijf
staan, alleen niet meer via de cockpit bereikbaar). Geen aparte fase-7-actie hiervoor nodig.

BLOK B — deliverables/rapport/pakket/critic/inwoners-schermen: project_verslag.py (649, incl.
stel_samen), project_pakket.py + inwoner_pakket.py (304 samen), project_worker.py's
AI-executie-paden (niet de kennis_context-vervanging uit fase 2, die blijft), de routes /rapport,
/project_pakket, /inwoners en hun views. missie_critic.py hoort NIET bij dit blok, bleek uit je eigen
check — laat die staan, hij hangt aan de keten onderzoekspas → fase 4, niet aan BLOK B. personas.py
blijft
zolang Noochie bestaat (221 regels), de
rest van de persona-machinerie niet. Check ook business_case.py, board_loop.py, noochie_memo.py: dit
zijn de Mission Impact/Business/Effort-invoervelden die zonder AI-prioritering drie verplichte
dropdowns zijn die niemand terugleest (12-15 van 112 levende projecten ingevuld, business_case op
0) — velden mogen in de data blijven staan als historie, haal ze uit het formulier
(views/wizard.py, 458 regels: overweeg het hele wizard-scherm te vervangen door één vraag,
"wat is klaar-wanneer?", done_when staat al op 184 van 386 projecten dus dat veld werkt al — de
definitieve wizard-vervanging naar het prototype-formulier gebeurt in fase 7, hier alleen de
AI-velden eruit).

**Correctie tijdens BLOK C (19 sept, avond) — drie bestanden zijn geen Founder-Flow-bestanden**:
founder_kaart.py, gap_ledger.py en gap_classifier.py stonden hieronder op naam, maar zijn het niet:
founder_kaart.py is FOUNDER_ROL + de kaart-renderer van de levende inbox (views/inbox.py 2×,
waarde_audit.py, villageraad.py, zelf_verwerking.py, cli.py, cockpit2.py — weghalen breekt /inbox);
gap_ledger.py wordt vandaag nog geschreven door escalation_router.py bij elke escalatie (/codie was
alleen de lezer, niet de enige aanroeper); gap_classifier.py hangt aan village.py, skills_catalog.py,
skills_naar_links.py en de inbox-CLI, en beslist of een gat bouwbaar of mens-extern is. Alle drie
blijven ongewijzigd staan — dit is geen opruiming die ze raakt, ze zijn er alleen naar vernoemd of
werden er toevallig door gelezen. Zou je ze alsnog kwijt willen, dan is dat een herbedrading van
/inbox en de escalatie-router, geen opruiming — niet in deze fase.

BLOK C — Founder Flow, helemaal (Stefans besluit van vanavond, definitief, triage én
trainingsloop): founder_flow.py (575), founder_taken.py (666), views/founder_flow.py (503),
founder_park.py (117), route /founder (founder_kaart.py blijft, zie de correctie hierboven). Ook weg:
accountability_check (skills_impl, +views /accountabilities, "Last run: unknown · 0 duplicates" —
nooit iets opgeleverd, 98+99 regels). Codie-backlog: route /codie en zijn eigen view (gap_ledger.py en
gap_classifier.py blijven, zie de correctie hierboven — dit is alleen het /codie-scherm zelf, niet de
twee modules die het las) — machine-geschreven probleemstellingen voor een AI-programmeur die nooit
heeft opgeleverd (0 deliverables, gearchiveerd 18 sept). /belofte ("unproven 0/23 grounded") gaat mee,
zelfde reden. /catalog blijft (8 KPI-definities met echte data) maar verhuist naar onder Metrics, niet
als los scherm met "Librarian" in de titel.

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

**Correctie tijdens de fase-6-inventarisatie (19 sept, avond) — vijf afwijkingen, niets gesneden
vóór akkoord**: (1) views/strategy.py + strategy_store.py NIET verwijderen — de brief had het mis,
_strategy_tab_html wordt wél aangeroepen (views/overview.py:206 en :840, ingebed in elk
cirkel-overzicht), weghalen breekt het cirkel-overzicht; strategy_store.StrategyStore is bovendien
een top-level import in cockpit2 (_Stores.strategies). Blijft staan. (2) /epic/frame (NASA-aardbol)
is geen verborgen route maar een zichtbaar element op de overview-pagina van de Mother Earth-cirkel
onder "Domains" (views/overview.py:210) — codereview_live_systeem_19sept.md, waar de brief naar
verwijst, bestaat niet. Stefans besluit: toch weg, widget en route allebei, past niet bij fase 9's
nieuwe visuele stijl en heeft geen datawaarde. (3) Snake zit niet alleen in snake.py maar ook in
web_base.py (openSnake() + Konami-code-listener) — het bestand dat elke pagina laadt. Verwijderen
raakt dus web_base.py, niet alleen de losse route. (4) render_patterns is geen apart bestand, zit in
views/overview.py:1039. (5) alphavantage is geen slapende skill maar een dagelijks actieve collector
(alphavantage_aex_day/spx_day, laatste meting 19 sept, active in meetcatalog.CATALOG en
sources.json) — geen enkele KPI-tegel leest hem ("meet voor niemand" klopt, maar het is een
lekkende kraan, geen dode code). Stefans besluit: toch weg, inclusief de catalogus- en
sources.json-regel (anders meldt de recency-guard hem straks als "verwacht maar afwezig").
gdelt_tone is wel het schone geval (al inactive, laatst 8-10 sept) en gaat gewoon mee zoals gepland.

Verwijder de speeltuin: /snake + het bijbehorende highscore-endpoint (217+27, incl. de Snake-haken
in web_base.py, zie correctie hierboven), /callbar + /livekit-token + /livekit-presence (391 + 3
handlers), /epic/frame + de aardbol-widget op de overview-pagina (zie correctie hierboven).

In skills_impl/: verwijder groep 1, nooit door iemand gehouden, nooit uitgevoerd, geen collector,
niet vanuit de cockpit aangeroepen (11 modules, 2.139 regels): accountability_check (deels al weg
via fase 3, check overlap), bulletin_schrijven, cert_evidence, lead_beoordeling (LET OP: bleek in
fase 3 toch te zijn gedraaid via _use_skill_with_ladder/BLOK A — al verwijderd daar samen met de
rest van de BLOK A-closure, sla hier over, alleen ter controle dat er niets van overblijft),
openlibrary_search_inside, pappers_financials, serpapi_trends, site_watch, synthesize (al deels weg
via fase 2, check overlap), trustpilot_reviews, zoekstrategie. Verwijder groep 2, alleen gehouden
door nu-gearchiveerde rollen, geen ander pad (2.815 regels, zie audit_diep_cockpit_views_skills_
19sept.md §2 voor de volledige lijst met exacte regelaantallen — let op, §1 van datzelfde document
bleek voor BLOK A onbetrouwbaar, dus verifieer ook hier zelf import/aanroep in plaats van blind op
§2's regelaantallen te vertrouwen): trend_reindex, ngram, community_listening (al weg via fase 4,
check overlap), semantic_scholar, competitor_discover (al weg via fase 4), library_skills,
content_check EN content_schrijven (LET OP: deze twee zijn al in fase 2 verwijderd, samen met
publication_check.py — sla ze hier over, alleen ter controle dat er niets van overblijft),
field_note, onderzoeksvraag — LET OP: dit is een ANDERE onderzoeksvraag dan de skill die je in fase 2
als patroon hergebruikt voor kennis_context, controleer dat je niet de verkeerde weggooit —
verband_voorstel, kroniek_interpret, ruis_check, curate (LET OP: bleek net als lead_beoordeling via
BLOK A te zijn gedraaid — al verwijderd daar, alleen ter controle), competitor_news (al weg via
fase 4).

Verwijder alphavantage.py (131) en gdelt_tone.py (151): voedden de Tijdgeest-lens van Harry, die er
niet meer is. Voor alphavantage geldt, per de correctie hierboven: verwijder ook de catalogus-regel
in meetcatalog.CATALOG en de sources.json-regel in dezelfde stap, anders klaagt de recency-guard.
De overige databron-collectors (plausible, gsc, gsc_report, shopify_sales, trends,
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

**Resultaat fase 6, en daarmee het hele opruimdeel (19 sept, avond)**: 98.185 → 71.556 broncoderegels
(−26.629, −27,1%), 80.040 → 57.795 testregels (−22.245, −27,8%). De audit schatte ~37.000 regels
broncode "verdedigbaar weg"; het verschil met de 26.629 die daadwerkelijk weg zijn, zit vrijwel
geheel in posten die bij nader inzien een levende lezer bleken te hebben (/rapport, BLOK A, de
kennisbank/weten_we_dit_al-uitzondering, en de negen afwijkingen hieronder) — niet in gemiste
opruiming, maar in een schatting die op een onbetrouwbare audit leunde.

Twee dingen tijdens fase 6 zelf verwijderd en teruggezet na beter onderzoek: `_act_check_handoff`
(geen AI-plumbing maar het @-mens-op-checklist-item-pad naar de inbox, de AI-tak is slechts de
fallback erin) en `skills_impl/semantic_scholar.py` (tweede trede van de bewijs-ladder onder
`openalex_evidence`, draagt bron-metadata voor /catalog). Zeven andere uit de brief zijn nooit
aangeraakt na de inventarisatie: views/strategy.py, views/catalog_koppelen.py (alleen de losse
redirect-route was dood), en drie skills_impl-modules met een overlevende CLI-mode
(cert_evidence, serpapi_trends, library_skills). Definitief: /epic/frame + de aardbol-widget weg,
alphavantage.py weg inclusief de catalogus- en sources.json-regel — beide zoals besloten.

Methodeles, genoteerd voor fase 7-9: de eerste verzender-check zocht alleen op `value='actie'` in
HTML en miste dat `nooch.js` ook `data-qa-action` leest. Alle twaalf kandidaten zijn daarna opnieuw
gecontroleerd (bleken alsnog onbereikbaar), maar de aardigheid is dat een aanroep-check die alleen
naar server-side templates kijkt, de client-side JS kan missen — relevant zodra fase 7-9 zelf nieuwe
front-end-koppelingen bouwt.

## Fase 7: navigatie + Wiki/Tools/Policies-consolidatie + Keep-in-wiki-ingang, naar het prototype (v15)

Eerste interface-fase. Doel: de vaste zijbalk en schermindeling van het prototype (live artifact
versie 15, https://claude.ai/artifact/Y76cYZFUvYiAzp6oweqeD1) overzetten naar de live cockpit, met de
bestaande data erachter (`AttachmentStore`, `ProjectLedger`, `HumanInbox` — geen van drie hoeft
qua schema te veranderen; `zoomout_informatiearchitectuur.md` bleek te ontbreken, maar Claude Code
heeft de onderliggende claim zelf geverifieerd: artefacts.py onderscheidt kind als note/tool/policy,
wiki.py:130 leest meta["feiten"], de conclusie houdt stand). Nog geen nieuwe visuele stijl (dat is
fase 9): deze fase gaat over structuur, niet over hoe het eruitziet.

**Correctie tijdens de fase-7-inventarisatie (19 sept, avond) — twee besluiten, één nog open**:
(1) Messages komt NIET in de fase-7-zijbalk. Het prototype zelf markeert dat scherm als voorstel
("this screen does not exist in the real system yet") — het hoort bij fase 8's channel-laag. Een
nav-item bouwen dat naar iets bestaands doorverwijst zou dezelfde valse-klikbaarheid zijn die de
UX-audit eerder dit traject al als bug aanmerkte. Messages verschijnt pas in fase 8, met de echte
channel-laag erachter. (2) De stijl blijft zoals gepland: fase 7 bouwt in de huidige cockpit-stijl,
fase 9 doet het visuele werk in één keer over alle herbouwde schermen — geen tussentijdse
prototype-styling, dat zou een lappendeken worden die fase 9 weer moet ontwarren. (3) Nog open:
Admin·Skills is in het prototype schrijfbaar (toggles, "no approval needed"), live is /skills
expliciet read-only. Dit is een nieuwe bevoegdheid, geen structuurkeuze — ligt bij Stefan.

```
Begin met een korte audit, zelf uit te voeren, voor je iets bouwt: breng de huidige nav in
cockpit2_util.py/cockpit2.py in kaart (welke tabs/routes bestaan nu, wat is de huidige indeling) en
leg die naast de vaste zijbalk van het prototype: Projects (landing), Inbox (lade, "+ tension"),
Wiki, Circle, Admin, organisatieboom. Messages hoort hier NIET bij (zie de correctie hierboven,
komt in fase 8). Rapporteer de diff (wat moet verhuizen, wat moet samenkomen, wat blijft) voor je
begint te bouwen — dit is niet vanaf hier te verifiëren, dus neem geen aanname over hoe de huidige
nav in elkaar zit.

Bouw daarna:
1. Projects als eigen scherm/landing (in het prototype al zo; in de live cockpit waarschijnlijk nog
   een tab of gedeeld met iets anders — volgt uit je eigen audit hierboven).
2. De Policies/Notes/Tools-consolidatie afmaken: in fase 2 is de data-laag al opgeruimd en een
   tijdelijke doorverwijzing naar Wiki gezet. Bouw hier de echte, prototype-gelijke Wiki-tab met een
   filter (hetzelfde `AttachmentStore.kind`-onderscheid: note/tool/policy, één surface, een
   filter/badge per soort).
3. Keep-in-wiki: een nieuwe ingang vanuit een project-conversatie (of straks een cirkel/persoon-
   kanaal, zie fase 8) om één feit op een gekozen wiki-pagina te zetten, met herkomst. De opslag
   bestaat al (`AttachmentStore.meta["feiten"]`), dit is puur de nieuwe ingang, zoals het prototype
   'm toont.
4. Voertaal naar Engels waar de UI nu Nederlandse labels heeft (het prototype's eigen v15-fix
   "Admin · Mensen" → "Admin · People" is het voorbeeld van het patroon). Bekende resten al
   gevonden tijdens de inventarisatie: views/inbox.py ("Geen rol gevonden", "Voorstel:"),
   views/site_audit.py ("Gewisseld sinds de vorige run", "Nog geen run"), views/vangst.py
   ("volgende spanning →") — neem deze mee, en zoek naar vergelijkbare resten elders.
5. Zoeken (/, Cmd+K) en de organisatieboom blijven in deze fase op titel-niveau (contentindexering
   is fase 8), maar moeten over de nieuwe schermindeling heen blijven werken — check dat expliciet.
6. Admin·Skills blijft read-only tot Stefan antwoord geeft op de openstaande schrijfbaarheidsvraag
   (zie de correctie hierboven) — niet vooruitlopen door alvast toggles te bouwen.

Testdiscipline: 3-5 tests per scherm dat verandert (jouw regel voor routinefeatures), plus een
handmatige doorloop tegen het prototype als referentie voor elke aangepaste flow — het moet zich
hetzelfde gedragen als daar, niet alleen "niet meer crashen".

Volledige testsuite voor/na, diff, commit en ga door naar fase 8.
```

**Resultaat fase 7 (commit `168f548`, 19 sept, avond)**: suite 3.998 geslaagd / 1 gefaald (dezelfde
bekende, al langer bestaande fail — geen regressie). Gebouwd: één vaste linker zijbalk die topbar,
footer en de organisatieboom-rail samenvoegt (`_nav()` behield haar signatuur, dus de ~40 aanroepende
views hoefden niet aangepast te worden; Messages bewust weggelaten, zie de correctie hierboven);
`/projects` als nieuwe landingpagina (hergebruikt `_projects_tab_html` letterlijk, geen herbouw); de
Wiki-consolidatie (drie tabs → één gefilterde tab plus een dorpsbrede `/wiki`-index; oude
`?tab=notes|tools|policies`-links worden binnen `render_node` zelf vertaald, geen aparte
redirect-laag); Keep-in-wiki (knop onder projectgesprek-berichten, met drie expliciete keuzes:
`soort="bron"` — herkomst/onbevestigd, geen bewijs; herkomst draagt project+auteur+datum; hergebruikt
de bestaande `pagina_feit_add`-rechtencheck); de zoek-hotkey; en de drie taalresten
(views/inbox.py, views/site_audit.py, views/vangst.py).

Eén zelf-gevonden en gecorrigeerde auditfout tijdens het bouwen: de eigen fase-7-inventarisatie
claimde eerst dat de organisatieboom nergens bestond — bleek al te bestaan als
`views/overview._tree_html` in de rechter kolom; het werk was verplaatsen, niet nieuw bouwen. Geen
impact op het resultaat, wel genoteerd als methodeles.

Eén bewuste governance-vs-UI-keuze, niet zelfstandig losser gemaakt: Keep-in-wiki's rechtencheck
(`pagina_feit_add`) is strenger dan het prototype (rolhouder/Circle-Lead-only, het prototype suggereert
vrijer). Claude Code hield de bestaande, strengere regel aan in plaats van 'm stilzwijgend te verruimen
richting het prototype — in lijn met de "dood is dood, niet halfdood"-voorzichtigheid: rechten nooit
impliciet verruimen via een UI-bouwtaak. Bevestigd als de juiste keuze; als dit ooit losser moet, is
dat een aparte, expliciete governance-beslissing, geen bijvangst van fase 7.

Nog open uit fase 7, geen van beide blokkeert fase 8: Admin·Skills-schrijfbaarheid (toggles vs.
read-only) ligt nog bij Stefan — Admin·Skills blijft read-only tot dat antwoord er is. Messages is,
zoals gepland, doorgeschoven naar fase 8 met de echte channel-laag erachter.

## Fase 8: channel-laag (project/cirkel/persoon) vervangt wall + @-notificaties direct, plus zoeken op inhoud

**Aanpak, bevestigd (19 sept, avond)**: zelfde volgorde als fase 6 en 7 — eerst een eigen inventarisatie
van de huidige wall- en notificatiemachinerie (welke routes/tabellen bestaan nu, wat doet de
@-notificatie precies, wat heet er "wall" dat eigenlijk iets anders is), de verschillen met het
prototype voorleggen, pas daarna bouwen. Reden om dit expliciet te herbevestigen in plaats van
stilzwijgend aan te nemen: de brief en de audit hebben in elke fase tot nu toe minstens één feitelijk
onjuiste live/dood-aanname bevat (BLOK A "Idle", /rapport "0 documents", views/strategy.py "nooit
getoond", /epic/frame "verborgen", alphavantage "slapend", de organisatieboom "bestaat niet", en de
`data-qa-action`-blinde-vlek in fase 6) — inventariseren-voor-bouwen is inmiddels een bewezen
noodzaak, geen voorzorg meer.

Geen naast-elkaar-periode: dit vervangt de bestaande wall en @-notificaties meteen, geen losse
migratie later. Stefans instructie hierbij: een @-vermelding hoeft geen eigen notificatiemechaniek
te houden, dat kan gewoon een bericht zijn dat in het persoonlijke kanaal van de vermelde persoon
terechtkomt — het persoon-kanaal (één van de drie kanaaltypes hieronder) is dus meteen ook de
vervanger van de huidige @-notificatie.

**Correctie tijdens de fase-8-inventarisatie (19 sept, avond) — de brief had de verkeerde store als
"de wachtrij" aangewezen**: de wall is geen aparte store maar een lijst ín het project
(`project["log"]`, zeven leesplekken). De @-vermelding loopt via `_mentions_in` → `st.notif.add(...)`
→ `NotifStore`, zichtbaar op `/inbox`. Maar `/inbox` toont daarnaast ook `HumanInbox` (goedkeuringen).
De brief zei "laat `human_inbox` los, dat blijft de wachtrij" — op prod heeft `human_inbox` echter
286 items met **0 pending**: hij is feitelijk leeg, niet de wachtrij. De échte wachtrij zit in
`NotifStore` zelf, en die is groter dan alleen @-vermeldingen: van 371 notificaties op prod hebben er
maar 24 een `entry_id` (dat zijn de @-vermeldingen uit de wall); de overige 338 zijn werk dat een rol
kreeg toegewezen (compliance 69, claims-checker 46, harry_hemp 45, plus villageraad/escaleer/
werkoverleg-routing/projectverzoek) — 263 daarvan staan nog open (`open`-veld op de NotifStore-rij).

**Tweede ronde, na doorvragen door Stefan — van drieledige knip naar volledige unificatie**: het
eerste besluit hield de 338 rol-notificaties apart, met als argument dat een kanaalbericht geen
afhandel-status kan dragen. Dat argument houdt geen stand: NotifStore's `open`-veld is precies zo'n
status, en kan gewoon meeverhuizen als een veld op het kanaalbericht (`afgehandeld: bool`, default
false, door de ontvanger zelf omgezet zodra die de opvolging buiten het systeem heeft gedaan — actie
gemaakt, project geformuleerd, rol aangepast). Er is dus geen technische reden om twee systemen naast
elkaar te houden. Besluit (Stefan, 19 sept, herzien): **alle 371 NotifStore-rijen** worden
kanaalberichten, niet alleen de 24 @-vermeldingen. Voorwaarde die Claude Code eerst moet verifiëren:
elke rol met een openstaande notificatie moet eenduidig naar één actuele houder (mens) herleidbaar
zijn — "338 aan een rol, 33 aan een persoon" impliceert dat die vertaling al ergens bestaat; die wordt
hergebruikt om te bepalen in wiens persoonskanaal het bericht landt. Is een rol niet eenduidig
herleidbaar (geen houder, of meerdere), meld dat terug voor verder gebouwd wordt.

**Geen apart Inbox-scherm meer.** Stefans vervolgpunt: een los Inbox-scherm náást Messages is
dubbelop, hij zou hetzelfde ding op twee plekken zien. Dus: `/inbox` als eigen navigatie-item
vervalt. Messages/kanalen wordt de enige surface; wat vandaag "de inbox" is, wordt een filter/weergave
óp de kanalen ("nog niet afgehandeld", over project-, cirkel- en persoonskanalen heen), geen
aparte databron of scherm met eigen identiteit. Gelezen/ongelezen en afgehandeld/niet-afgehandeld
blijven twee losse velden: openen van een bericht zet het niet automatisch op afgehandeld.

`human_inbox` blijft buiten deze fase (0 pending op prod, dus feitelijk niet "de wachtrij", maar of
hij nog een levend schrijfpad heeft is een aparte vraag — zie de bouwinstructie hieronder).
Het persoonskanaal wordt een echt tweerichtings-DM-kanaal (zoals het prototype's "Direct: Lotte
Mulder" toont), niet alleen een inkomende stroom. Cirkelkanalen volgen de bestaande cirkels (geen
nieuw begrip); vrije onderwerp-kanalen (zoals het prototype's `#batch-4`, dat eigenlijk een
projectcategorie is, geen cirkel) worden nu niet gebouwd — apart, later te nemen besluit, de
channel-store wordt generiek genoeg opgezet om dat ooit aan te kunnen.

```
Bouw één gedeelde channel-store: een kanaal per project, per cirkel en per persoon, met trail en
replies als één stroom (zoals het prototype's project-detail "Conversation"-sectie toont). Het
persoon-kanaal is een echt DM-kanaal (twee kanten kunnen schrijven), niet alleen een inkomende
stroom. Cirkelkanalen: één per bestaande cirkel, geen nieuwe vrije-onderwerp-kanalen (apart besluit
voor later). Elk kanaalbericht draagt een `afgehandeld`-veld (bool, default false), los van
gelezen/ongelezen.

Verifieer eerst of elke rol met een NotifStore-rij eenduidig naar één actuele menselijke houder
herleidbaar is (de bestaande rol-naar-persoon-vertaling, want "338 aan een rol" moet ergens al bij
een mens landen om zichtbaar te zijn op /inbox vandaag). Als dat eenduidig is: migreer ALLE 371
NotifStore-rijen (niet alleen de 24 met `entry_id`) naar kanaalberichten — de 24 @-vermeldingen naar
het persoonskanaal van de vermelde persoon, de overige 338 naar het persoonskanaal van de actuele
rolhouder, elk met `afgehandeld` overgenomen uit het huidige `open`-veld (open → afgehandeld=false).
Verwijder NotifStore daarna, geen dubbele opslag. Is de rol-naar-persoon-vertaling NIET eenduidig
voor een deel van de gevallen, meld dat terug in plaats van te bouwen — dan knippen we het toch in
tweeën.

Bouw geen apart Inbox-scherm/route meer. Wat vandaag `/inbox` toont, wordt een filter/weergave op de
kanalen: "nog niet afgehandeld", over alle kanaaltypes heen, gesorteerd zoals de huidige inbox dat
doet. Vervang de route, verwijder de oude inbox-view-code die puur op NotifStore/HumanInbox leunde.

Check of `human_inbox` nog een levend schrijfpad heeft (0 pending op prod bewijst niet dat hij dood
is). Heeft hij die niet meer: raak 'm in deze fase nog niet aan, maar zet 'm op de open-lijst voor een
latere opruimronde (los van fase 8, niet erbij trekken). Heeft hij die wel (bijv. een apart
goedkeuringsmechanisme dat conceptueel iets anders is dan "rol heeft werk"): laat met rust, dat is
een ander mechanisme dat toevallig nu leeg staat.

Breid zoeken uit van titel-only naar ook wiki-body, gespreksinhoud (de nieuwe channel-trail) en
checklist-items.

Testdiscipline: zelfde als fase 7 (3-5 tests per onderdeel, handmatige doorloop tegen het
prototype), plus: een test dat elke notificatie-soort (@-vermelding én rol-werk) als bericht in het
juiste persoonskanaal landt met het juiste afgehandeld-veld, een test voor de "nog niet
afgehandeld"-filter over alle kanaaltypes heen, en een test voor het DM-pad (twee personen die
rechtstreeks berichten uitwisselen via het persoonskanaal).

Volledige testsuite voor/na, diff, commit en ga door naar fase 9.
```

**Derde ronde, definitieve uitkomst (19 sept, avond) — de "volledige unificatie" hierboven is NIET
zo uitgevoerd, met een betere onderbouwing dan eerst gegeven.** Claude Code voerde uit: de wall
vervangen (project-kanaal = `project["log"]`, één bron) en de 24 @-vermeldingen vervangen door een
DM-bericht. De 338 rol-notificaties zijn NIET gemigreerd; NotifStore en `/inbox` bestaan onveranderd
naast Messages. Dat is een afwijking van de "volledige unificatie" hierboven, maar op stevigere
grond dan de eerst genoemde "ruis":
1. **Geen tweede partij voor een DM.** Van de 338 hebben er maar 5 een mens als afzender; de rest
   komt van rol-/systeem-namen (compliance 69, claims-checker 46, harry_hemp 45, librarian 22,
   website_watcher 19, etc. — geen mens om de andere kant van een DM te zijn). Stefan koos expliciet
   voor een écht tweerichtings-DM-kanaal; een eenzijdige stroom in het persoonskanaal duwen zou dat
   weer ondermijnen.
2. **Ze dragen een verwerkingsmodel, geen boolean.** Op de 338: read 259, processed 258, archived
   225, outcome 185, verwerkingen 83, poort 54, done 33 — een verwerkingsgeschiedenis met
   uitkomsten en poort-oordelen, niet "gelezen ja/nee". Dat overzetten naar een `afgehandeld`-veld op
   een kanaalbericht is niet één veld erbij, het is dat model opnieuw bouwen bovenop een chat-trail,
   of 185 vastgelegde uitkomsten en 54 poort-oordelen stilletjes laten vallen.

Resultaat: het "dubbele" dat de brief wilde opheffen (twee meldingspaden voor hetzelfde ding) is wel
degelijk weg — een @-vermelding heeft nu precies één bestemming. Wat overblijft is geen duplicaat
maar een ander soort object (een afhandel-wachtrij met eigen state machine), en dat blijft terecht
NotifStore + `/inbox`. Deze twee cijferreeksen (5/338 met mens-afzender; 185 uitkomsten + 54
poort-oordelen) worden vastgelegd in `channels.py` als commentaarblok, zodat over zes maanden
duidelijk is waaróm dit geen aparte tekortkoming is maar een bewuste grens. Fase 8 is hiermee
akkoord en afgerond (commit `6cbce5f`, suite 4.015 passed / 1 failed, de bekende).

## Fase 9: het visuele ontwerp (Nooch UI v1) op de herbouwde schermen

Laatste fase van deze ronde. Let op: dit is een ANDER traject dan `designsysteem_fase2_
inventaris.md` (14 juli) — dat ging over het opschonen van de bestaande, oude cockpit-CSS-
klassenset (nooch.css, 425 selectors, 58 prefix-families). Dit hier is een compleet nieuw visueel
systeem, exact zoals het prototype het toont: 2px zwarte randen, één neongroen accent per scherm,
status altijd als vorm plus woord (nooit kleur alleen).

**Inventarisatie fase 9 (19 sept, avond, `claude/fase9_designsysteem_inventarisatie.md`, 229
regels)**: volledige tokendiff (25 live tokens vs. 10 prototype-tokens), een pariteitstabel van 20
klassen met drie expliciet benoemde afwijkingen, de statusweergave-analyse (63 kleur-alleen-statussen
op prod — gecorrigeerd van een eerste ruwe telling van 54, exact per selector geteld), en een
scope-lijst van 19 schermen in / 27 uit. Nog geen regel CSS aangeraakt. Vier vragen beantwoord voor
de bouw begint:

1. **Statusweergave-scope: alleen de 19 fase-9-schermen**, niet dorpsbreed. Dat is ook al wat de
   brieftekst hierboven zegt ("schermen die in fase 1-8 niet zijn aangeraakt... hoeven in deze fase
   niet mee, meld expliciet welke"). De 63 kleur-alleen-statussen buiten die 19 blijven dus staan,
   bewust en gelogd, geen halfslachtige dorpsbrede tussenvorm.
2. **Tokens: strikt twee gescheiden bestanden/`:root`-blokken, geen aliasing.** Dit staat al
   letterlijk in de brief ("naast de bestaande nooch.css, niet erin vermengd") en de reden staat er
   ook bij: aliasing tussen oud en nieuw zou precies de wildgroei die de juli-inventarisatie al
   signaleerde erger maken. Bijkomend voordeel: een volledig gescheiden tokenbestand is later in zijn
   geheel te verwijderen zodra nooch.css ooit vervangen wordt, een aliassysteem zit dan in de weg.
3. **`/claims` en `/metrics2`: alsnog meenemen in fase 9, herzien (19 sept, avond, na Stefans
   navraag over wat deze twee schermen precies zijn).** `/claims` is geen wiki-tool-verwijzing maar
   een werkende applicatie (termendatabase, scanknop, bewijsvoering, oordelen — het best werkende,
   meest gebruikte cluster van het dorp, 281 uitvoeringen/60 dagen); `/metrics2` is het bestaande
   KPI-dashboard, geen tweede of ander metrics-systeem naast wat Stefan al gebruikt. Beide krijgen
   dus gewoon de nieuwe huisstijl, zoals de rest. Extra, nieuw: `/claims` moet ook ontsloten worden
   via een Wiki-pagina met het claims-beleid erop (`claude/claims_policy.md` bestaat al als
   beleidsdocument en kan als basis dienen) — een Wiki-pagina (kind=policy of tool) die naar
   `/claims` linkt, zodat je het niet alleen via de URL/nav vindt maar ook via de Wiki, net als de
   andere tools/policies uit fase 7's consolidatie.
4. **Screenshots: Playwright, zoals de brief al voorschrijft** ("zelfde methode als de
   prototype-audits — Playwright, screenshots op desktop- en mobielbreedte"). Geen aparte
   handmatige visuele check door Stefan nodig als eindcheck; dat was al de afgesproken methode.

`claude/`-bestanden (inclusief dit inventarisatiebestand) horen gewoon in de repo, zoals de eerdere
brief/audit/state-documenten dit hele traject al deden — committen.

```
Bouw het nieuwe visuele systeem als een eigen, klein tokenbestand (kleur, rand, radius, status-vorm)
naast de bestaande nooch.css, niet erin vermengd — de oude klassenset en het nieuwe systeem lopen
door elkaar heen als je ze samenvoegt, en dat maakt precies de wildgroei die de juli-inventarisatie
al signaleerde erger, niet beter.

Pas het nieuwe systeem toe op elk scherm dat in fase 7 en 8 is herbouwd of aangeraakt: Projects,
Wiki (incl. de Policies/Notes/Tools-consolidatie), Keep-in-wiki-ingang, de nieuwe channel-laag
(incl. het persoonlijke kanaal), Circle, Admin, organisatieboom, zoeken. De governance- en
tactical-meeting-modals (bestaan al functioneel) krijgen dezelfde visuele stijl, geen functionele
wijziging. Neem ook `/claims` en `/metrics2` mee in de restyling (herzien besluit, zie hierboven —
niet meer geparkeerd).

Bouw voor `/claims` daarnaast een Wiki-pagina (kind=policy of tool, net als de andere
Policies/Notes/Tools-consolidatie uit fase 7) die het claims-beleid beschrijft en naar `/claims`
linkt — gebruik `claude/claims_policy.md` als inhoudelijke basis als die nog actueel is, anders
kort navragen bij Stefan. Doel: `/claims` is straks ook via de Wiki vindbaar, niet alleen via de
URL of een los nav-item.

Overige schermen die in fase 1-8 niet zijn aangeraakt qua UI en niet expliciet hierboven zijn
toegevoegd, hoeven in deze fase niet mee. Dat is een bewuste keuze, geen vergeten stuk: meld
expliciet aan Stefan welke schermen je om die reden nog overslaat, zodat hij kan beslissen of dat
een aparte, tiende fase wordt of blijft staan zoals het is.

Eindcheck: een screenshot-vergelijking (zelfde methode als de prototype-audits — Playwright,
screenshots op desktop- en mobielbreedte) tegen de bijbehorende prototype-schermen. Het gaat hier
niet alleen om "het werkt", ook om "het oogt hetzelfde".

Commit — laatste fase van deze ronde. Meld aan Stefan: het totale regelaantal-eindcijfer uit fase 6,
welke schermen in fase 9 bewust zijn overgeslagen, en alle stopmomenten die zich in fase 1-9 hebben
voorgedaan (ook de niet-kritieke, en welke keuze je zelf hebt gemaakt waar je niet hoefde te
stoppen).
```

**Resultaat fase 9 en afronding van het hele traject (19 sept, avond, commit `19f28da`, niet
gedeployed).** Eigen stylesheet `static/nooch-ui.css` (170 regels) onder een `--nu--`-namespace i.p.v.
letterlijk twee `:root`-blokken — noodzakelijke afwijking, `--border` botste tussen oud (kleur) en
nieuw (shorthand, 147 gebruiksplekken); twee globale blokken hadden op élk scherm de randen gesloopt,
ook de geparkeerde. Toegepast op de 19 fase-9-schermen plus `/claims` en `/metrics2` (herzien, zie
hierboven). Playwright-screenshotcheck (16 screenshots + herhaalbaar script, `claude/
fase9_screenshots/`) vond vier categorieën bugs die geen enkele unit-test kon zien (browser-
afhankelijke rendering, een fout standaardkanaal in Messages, visuele regressie in een dashboard-
sectie) — het bewijs voor de eindcheck-eis uit deze brief. Playwright + Chromium vastgelegd in een
apart `requirements-dev.txt` (niet op prod, deploy.sh/CI installeren beide `requirements.txt`).

Volledig eindrapport: `claude/eindrapport_opruiming_fase1-9.md` (359 regels, negen secties).
Belangrijkste cijfer: van de 19 stopmomenten over fase 1-9 waren er **drie** die de brief zelf
voorzag; **twaalf** kwamen uit premisses in de brief of de audit die bij live-verificatie onjuist
bleken. Dat is de kernles van dit hele traject, zwaarder dan elk regelaantal: een opruimbrief die op
een audit leunt zonder live-verificatie per stap is stelselmatig optimistisch over wat "dood" is.

Bijvangst: `Pillow` in `requirements.txt` draagt nog het commentaar "EPIC-aardbol" (de al verwijderde
NASA-globe-widget), met 0 resterende PIL-verwijzingen in de code. Bewust laten staan: een dependency
schrappen laat `deploy.sh` de venv opnieuw resolven, een apart deploy-risicomoment dat Stefan zelf
moet kiezen, niet iets om onder deze fase te laten meeliften. Kandidaat voor de open-lijst.

De `/claims`-Wiki-pagina (zie hierboven) is apart afgehandeld: de echte beleidstekst
(`claude/claims_policy.md`, uit Stefans eigen Claude-project, niet de repo) is alsnog aangeleverd na
een plak-fout, en het anker is `mother_earth__nooch__compliance` zonder extra poort — consistent met
fase 5's beslissing dat iedereen die ingelogd is de claims-curatie mag doen.

**Claims-Wiki-pagina gebouwd en geverifieerd (commit `0908341`)**: zelfde vorm als
`wiki_how_we_decide` (geen nieuw zaai-mechanisme, geen route, geen store, `arch_map` gaf geen diff).
Eigenaar is een vast rol-id geworden, niet afgeleid via `org.role_for_domain('claims-database')` —
die aanroep levert sinds 18 sept niets op, dus een afgeleide eigenaar had de pagina nooit laten
verschijnen. Poort-check (mijn vraag) bevestigd: `_claims_gate` (curatie, iedereen-ingelogd) en
`_artefact_gate` (pagina bewerken, rolvervuller of Circle Lead) zijn twee aparte oppervlakken die
elkaar niet raken — fase 5 is niet teruggedraaid, met een guard-test
(`test_fase5_is_niet_teruggedraaid_diezelfde_derde_mag_claims_cureren`) om dat te bewaken. Op prod
kunnen 2 van de 5 mensen de pagina direct bewerken (compliance- + Circle Lead-vervullers, grotendeels
dezelfde persoon), de rest kan een voorstel indienen (ongated, want geen mutatie) dat bij compliance
blijft liggen zolang die een mens-vervuller heeft — bestaand gedrag voor elke rolpagina, niets nieuws
voor deze.

**Live bug gevonden via de Playwright-check, niet gerelateerd aan claims maar wel dit traject
waard**: de wiki-renderer (`_md`) ondersteunt alleen `##`-koppen en `- `-lijsten; een `#` of `---`
komt er letterlijk doorheen. De nieuwe claims-pagina is herschreven om binnen die beperking te
passen. Dezelfde fout zit al sinds 18 september op de bestaande pagina NOTE-STRATE-001 ("How we
decide here") — zichtbaar in productie, niet met een bestandswijziging te repareren omdat
`wiki_zaad` bestaande pagina's nooit overschrijft. Dit blijft openstaan tot iemand de pagina expliciet
herschrijft (via de UI, of een bewust, eenmalig correctiescript — geen automatische
seed-overschrijving).

**Correctiescript NOTE-STRATE-001 geverifieerd (`25f0bfa`)**: bewezen woordneutraal (353 nieuwe tegen
357 oude woorden, verschil is exact de vier woorden van de weggehaalde titelregel die Claude Code er
eerst zelf bij had gezet en weer terugdraaide — nul woorden toegevoegd, `git show 25f0bfa --
content/how_we_decide_en.md`). `scripts/herstel_note_strate_001.py`: droogloop tenzij `--doen`, drie
fail-closed controles (id/kind/titel/eigenaar kloppen; het gebrek zit er nog; de live tekst is
woord-voor-woord identiek aan wat verwacht wordt — wijkt die af, dan heeft iemand de pagina inmiddels
bewerkt en stopt het script, want dan is het een gesprek geen script). Schrijft via
`AttachmentStore.update`, dus met version-entry en change_note, terugdraaibaar. Akkoord.

**Blokkade vóór deployen, ontdekt bij het uitvoeren (19 sept, avond) — de hele negen-fasen-ronde
staat nog alleen lokaal.** `deploy.sh` doet alleen een fast-forward naar `origin/main`. Prod en
`origin/main` staan beide op `9c490c4`; Claude Code's werkbranch staat op `25f0bfa`, 18 commits
verder, nooit gepusht. `main` is branch-protected en vereist groene CI — terecht niet omzeild.
Besluit: branch pushen, PR openen (18 commits, −51.270 regels, één PR voor de hele opruimronde,
beschrijving verwijst naar deze brief en `claude/eindrapport_opruiming_fase1-9.md` voor de volledige
besluitvorming) — **Stefan merget zelf**, consistent met het bestaande werkpatroon (Claude scopet
of implementeert, Stefan keurt goed voor een merge/deploy). Na de merge: `deploy.sh`, dan `wiki_zaad`
droogloop + rapport tonen, na akkoord `--apply`, dan `herstel_note_strate_001.py --doen`.

**PR #516 open** (github.com/stefanwobben-creator/Noochville/pull/516): 20 commits, 398 bestanden,
+4.933/−51.314, mergebaar zonder conflicten, CI draait (GitGuardian al groen). Extra, expliciet
gemeld: deze brief zelf stond alleen lokaal (`~/Downloads`), niet in de repo — een PR-beschrijving
die ernaar verwijst zou nergens naartoe wijzen. Claude Code heeft de brief letterlijk (ongewijzigd,
eerst gecheckt op sleutels/wachtwoorden — schoon) toegevoegd als eigen commit (`021cbaf`), vandaar
20 in plaats van 18 commits. De brief staat dus vanaf nu ook in de repo zelf, niet alleen in Stefans
Claude-project. Stefan merget zelf zodra CI groen is.

**Gemerged en gedeployed (19 sept, avond) — live op `8ab787a`.** Health-check HTTP 303, beide
services actief, geen rollback, geen fouten in de logs. Acht routes op prod steekproefsgewijs
gecheckt (`/`, `/projects`, `/messages`, `/wiki`, `/claims`, `/metrics2`, `/admin`, `/inbox`): allemaal
303 (loginredirect), geen 500'en na −51.314 regels. Correctie op een eerdere aanname: `deploy.sh`
maakt GEEN databackup (dat stond dit hele traject en in de PR-beschrijving verkeerd als "backup,
pull, restart, health-check") — hij doet fast-forward pull, deps bijwerken indien nodig,
service-herstart, health-check, auto-rollback van de code. Een datasnapshot is een losse, handmatige
stap uit `INFRA.md`; de nieuwste was van 18 sept. Voor déze deploy geen probleem (alleen code), maar
vóór de twee data-schrijvende stappen hierna (wiki_zaad --apply, de correctie) wordt eerst een verse
snapshot gemaakt.

Droogloop `wiki_zaad`: 15 bestaande pagina's overgeslagen (niet overschreven), 1 overgeslagen (het
bekende, onveranderde gat: geen levende rol met domein `claims-database`), 1 nieuw aan te maken —
"Claims policy", precies zoals voorbereid.

**Afgerond (19 sept, avond).** Snapshot `data_2026-09-19_2341.tgz` (100 MB, als gebruiker `nooch`
gedraaid i.p.v. root — anders was er een root-eigen bestand in de data gekomen). `wiki_zaad --apply`:
1 pagina aangemaakt (`NOTE-COMPLI-021` — het rol-id-teller-nummer, geen probleem; de compliance-rol
had al 20 artefacten), 15 bestaand overgeslagen, 1 gat onveranderd. Live geverifieerd: titel, eigenaar,
kind, versie 1, body woord-voor-woord het bronbestand, geen kale `#` of `---`. Correctiescript
`herstel_note_strate_001.py`: droogloop tegen de échte pagina (niet de lokale reconstructie) haalde
alle drie fail-closed controles, diff identiek aan wat eerder al goedgekeurd was tegen `git show
25f0bfa`. `--doen` uitgevoerd: NOTE-STRATE-001 naar versie 2 met change_note, terugdraaibaar los van
de snapshot.

Hiermee is de negenfasige opruimronde van 19 september, inclusief de twee losse wiki-correcties,
volledig uitgevoerd, gedeployed en geverifieerd op prod.

**Eindstand.** Live op `8ab787a`. Broncode 98.185 → 71.978 regels (−26,7%), tests 80.040 → 58.150
regels (−27,3%). Nieuwe pagina: `village.nooch.earth/pagina?id=NOTE-COMPLI-021`. Gecorrigeerde
pagina: `.../pagina?id=NOTE-STRATE-001` (versie 2, negen regels renderen nu als echte lijst).
Vangnet: `backups/data_2026-09-19_2341.tgz`. Volledige besluitvorming per fase in deze brief;
volledige cijfers, alle 19 stopmomenten en de elf onjuiste premisses in
`claude/eindrapport_opruiming_fase1-9.md` §1-9.

Traject gesloten.

## Fase 10: eerste live-feedbackronde (19 sept, avond, na livegang)

Geen opruimfase zoals 1-9 — dit is UX/functionaliteit-feedback van Stefan op het echte, gedeployde
resultaat. Vier punten, elk apart besproken en bevestigd:

1. **Messages/projectkanalen, volledig zoals Slack.** De platte lijst met projectkanalen is
   onbruikbaar bij dit aantal (titels zijn volzinnen, geen zoekveld). Stefan wil de volledige
   Slack-ervaring: zoeken én zelf een los kanaal kunnen aanmaken dat niet aan een project, cirkel of
   persoon hangt. Dat laatste heropent bewust de fase-8-beslissing om geen vrije-onderwerp-kanalen te
   bouwen ("een nieuw datamodel-begrip zonder aangetoonde noodzaak") — de noodzaak is er nu wel,
   expliciet aangegeven.
2. **`/project/nieuw` (en mogelijk meer) mist de fase 9-restyling.** Zichtbaar op screenshot: ronde
   hoeken, zachte schaduw, crème achtergrond — geen 2px zwarte rand, geen neongroen accent. Dit
   scherm hoorde impliciet bij "Projects" in fase 9's scope, maar is kennelijk gemist.
3. **Circle-pagina's: het rechter "Organization"-paneel (volledige rollenlijst) is dubbelop.** Staat
   al compact in de linkerbalk, en er is al een eigen "Roles"-tab in de tabbalk. Ruimte teruggeven aan
   de hoofdinhoud.
4. **Wiki-pagina's zijn niet inline bewerkbaar.** "Edit" opent nu een apart formulier onder de
   pagina in plaats van direct in de tekst te kunnen klikken en typen.

**Aanvulling op punt 2 (19 sept, avond, na screenshots van nooch.earth zelf).** Stefan heeft twee
screenshots van de echte, publieke Nooch-website gestuurd (productpagina "The '269' Black" en een
e-mail/blog-concept "The votes are in") met de instructie: "zorg dat Village ook in deze design stijl
eruit ziet." Dit is geen los vijfde punt maar een aanscherping van punt 2: de fase 9-huisstijl (de
`--nu--` tokens) is intern bedacht; het echte ijkpunt is nu de live marketing-site, niet Claude Code's
eigen interpretatie. De twee referentiebeelden staan in de repo als `claude/huisstijl_referentie_productpagina.jpg`
en `claude/huisstijl_referentie_email.png` (door Stefan zelf toegevoegd, zie paste-back). Geëxtraheerde
kenmerken ter vergelijking met de bestaande `--nu--` tokens:

- Achtergrond: gebroken wit/crème (geen zuiver wit), ca. `#F7F4EC`.
- Accentkleur: één fel/limoengroen (`#00D46A`-achtig), gebruikt voor CTA-knoppen, topbanner, voortgangsbalken
  en badges — verder geen andere accentkleuren.
- Zwart bijna puur (`#0A0A0A`-achtig) voor tekst, randen, logo en footer.
- Randen: dun, effen zwart (1-2px), vierkante hoeken (geen of nauwelijks border-radius) op kaarten,
  tabellen en invoervelden. Geen zachte schaduwen, geen gradients — alles vlak.
- Typografie: koppen vetgedrukt in hoofdletters, grotesk/sans-serif met strakke tracking; kleine
  "eyebrow"-labels (klein, hoofdletters) boven koppen; lopende tekst gewoon gewicht.
- Knoppen: rechthoekig, groen gevuld, zwarte of witte vetgedrukte hoofdlettertekst, geen schaduw.
- Layout wisselt crème/witte vlakken af met volledig groene bandsecties.

Dit bevestigt dat de fase 9-richting (zwarte rand + neongroen accent, zoals punt 2 zelf al noemt) grotendeels
klopt, maar Stefan wil dit nu expliciet als bindend ijkpunt voor de hele Village-app, niet alleen de 19
fase 9-schermen. Dus: eerst de bestaande `--nu--` tokenwaarden (kleur, radius, rand, typografie) naast
deze referentie leggen en concrete afwijkingen rapporteren en voorstellen voor correctie, vóórdat een
brede toepassingsronde volgt — gezien de schaal (147 gebruiken van `--border` alleen al, zie fase 9) is
een ongecontroleerde tokenwijziging een risico, geen kleine restyle.

**Aanvulling op punt 1 (20 sept, nacht) — de inbox gaat mee.** Stefan, expliciet en zonder voorbehoud:
"inbox moet gewoon weg dat wordt een kanaal in messages." Dit is dus geen open vraag meer of `/inbox`
en NotifStore's 338 rol-notificaties apart blijven staan (de fase 8-beslissing hierboven wordt hiermee
bewust herzien) — ze worden channel-berichten, net als de 24 @-vermeldingen dat al zijn. Twee dingen
zijn daarbij geen ontwerpvraag maar een harde eis, "dood is dood, niet halfdood": de 185 outcomes en
54 poort-oordelen die nu in NotifStore staan mogen niet stilzwijgend verdwijnen bij de migratie, die
horen aan het bericht zelf te blijven hangen (wie besliste wat, wanneer, met welke uitkomst) — anders
verlies je een audit-trail zonder dat iemand het merkt. En: de meeste van de 338 hebben geen mens als
afzender (rol/systeem-namen als compliance, claims-checker, harry_hemp), dus dit is precies dezelfde
vraag als het vierde kanaal-soort hieronder — welk kanaal ontvangt een bericht van een rol/systeem in
plaats van van een mens. Neem dit mee in hetzelfde voorstel, niet als los stuk werk.

```
Punt 1 (Messages): bouw sowieso een zoek/filterveld boven de projectkanalen-lijst — dat staat los van
de rest en lost het acute onbruikbaarheidsprobleem op. Voor het losse-kanaal-concept: doe eerst een
korte inventarisatie van het huidige channel-datamodel (project/circle/dm, zie fase 8) en stel voor
hoe een vierde soort — een los, zelf te noemen kanaal zonder project/cirkel/persoon eraan — daar het
best in past (nieuwe kind, wie mag het aanmaken, hoe verschijnt het in de kanalenlijst). Leg dat voor
voor je bouwt, dit is een nieuw datamodel-begrip.

In hetzelfde voorstel: `/inbox` en NotifStore's 338 rol-notificaties (compliance, claims-checker,
harry_hemp, librarian, website_watcher e.a.) worden ook channel-berichten, net als de 24
@-vermeldingen dat al zijn (fase 8). Dit is een expliciete, onvoorwaardelijke beslissing van Stefan,
geen open vraag. Beantwoord in het voorstel: welk kanaal ontvangt zo'n bericht (waarschijnlijk een
kanaal per rol, mogelijk hetzelfde mechanisme als het vierde kanaal-soort hierboven, of het
persoonskanaal van de huidige rolvervuller — kies zelf de best passende vorm en leg die voor), en hoe
blijft de bestaande verwerkingsstate (185 outcomes, 54 poort-oordelen, read/processed/archived/done)
zichtbaar op het bericht zelf. Niets van die state mag stilzwijgend verdwijnen bij de migratie.

Punt 2 (uitgebreid): er staan twee referentiebeelden van de echte, live nooch.earth-website in
claude/huisstijl_referentie_productpagina.jpg en claude/huisstijl_referentie_email.png. Dat is nu het
bindende ijkpunt voor "de huisstijl" voor de hele Village-app, niet de fase 9-tokens op zich. Doe eerst
dit, in deze volgorde:

  a. Leg de bestaande --nu-- tokens (kleuren, randen, radius, typografie) naast de twee referentiebeelden
     en rapporteer concrete afwijkingen. Belangrijkste kenmerken van de referentie: gebroken wit/crème
     achtergrond (geen zuiver wit), precies één fel limoengroen accent voor CTA's/badges/voortgangsbalken,
     bijna zwart voor tekst/randen/logo, dunne effen zwarte randen (1-2px) met vierkante hoeken (geen/nauwelijks
     radius), geen schaduwen of gradients, vetgedrukte hoofdletterkoppen in een grotesk/sans-serif met
     strakke tracking, kleine hoofdletter-eyebrow-labels boven koppen, rechthoekige groene knoppen met
     vetgedrukte zwarte/witte hoofdlettertekst.
  b. Stel concrete gecorrigeerde tokenwaarden voor waar de --nu---tokens afwijken. Leg dat voor voor je
     iets breed toepast — bij 147 gebruiken van --border alleen al is een ongecontroleerde tokenwijziging
     een risico.
  c. Inventariseer daarna, zoals al gepland, welke andere schermen (net als /project/nieuw) wél in fase
     7/8 zijn herbouwd maar de fase 9-restyling hebben gemist. Rapporteer die lijst voor je begint te
     fixen, dan in één keer meenemen in plaats van steeds één losse plek te patchen.

Pas na akkoord op a+b de daadwerkelijke tokenaanpassing en de lijst uit c doorvoeren.

**Terugkoppeling en besluiten (19 sept, avond, na Claude Code's inventarisatie).** Twee structurele
missers eerst: de twee referentiebeelden stonden niet in `claude/` (alleen aan Stefan geleverd in de
chat, nooit in de repo gezet) en de fase 10-tekst zelf stond nergens in de repo — de brief die met PR
#516 meekwam eindigt bij fase 9. Claude Code kon dus alleen op de geschreven kenmerken toetsen, niet op
echte pixels, en kende punt 1/3/4 niet. Beide worden hieronder rechtgezet.

Inhoudelijk leverde de audit een sterke correctie op mijn eigen risico-inschatting op: het getal 147
(fase 9) ging over het óúde `--border`-token in `nooch.css` (174 gebruiken, grotendeels los verspreid),
niet over `--nu-border` in `nooch-ui.css` (9 gebruiken, allemaal binnen `.nu`). Een fase 10-tokenwijziging
raakt dus 179 regels in één bestand over negentien schermen, niet 147 verspreide plekken — overzienbaar.
Ook bleek er geen één groen-accent te zijn maar vier (`--nu-neon`, `--nu-accent`, `--nu-accent-text`,
`--nu-bg-alt`), en week `--nu-bg` (roze zweem) en `--nu-text` (zuiver zwart) af van de referentie.
Verder: koppen staan op `text-transform: none` (geen hoofdletters), geen eyebrow-component, primaire
knop is wit i.p.v. groen, en `.c2-navct` heeft als enige nog `border-radius: 999px`. Wat al klopte: geen
schaduwen, geen gradients, radius 0 verder overal, Archivo laadt echt.

Besluiten:
- Drie tokens schrappen: `--nu-accent`, `--nu-accent-text`, `--nu-border-subtle`. Eén groen overhouden.
- Hergebruik de bestaande `--cream`, `--ink`, `--sand` uit het oude `nooch.css` in plaats van nieuwe,
  bijna-identieke `--nu-*`-waarden te verzinnen — voorkomt een derde kleursysteem naast elkaar.
- Groen blijft voorbehouden aan de primaire CTA, niet elke `.btn`. Claude Code's eigen argument
  (vijf knoppen naast elkaar op /projects, vijf groene vlakken is geen accent meer) is correct en sluit
  aan bij de referentiebeelden, waar groen zichtbaar schaars en gericht wordt ingezet. Secundaire/
  tertiaire knoppen: wit/transparant met zwarte rand en zwarte tekst, zelfde vocabulaire als de rest.
- De exacte groentint niet op mijn schatting baseren: zodra de referentiebeelden er zijn, de kleur zelf
  uit de pixels sampelen (script, geen visuele inschatting) en die hex rapporteren voor het definitief
  wordt vastgelegd.
- Scope-uitbreiding bevestigd: "zorg dat Village ook in deze design stijl eruit ziet" was expliciet
  bedoeld voor de hele Village-app, niet alleen fase 9's negentien schermen. Dus groep A (wizard.py,
  projects.py, inbox.py, roloverleg.py, overview.py e.a. — in scope maar markup mist het gedeelde
  vocabulaire), groep B (`/site-audit`, `/middelen`, `/rolefillers` — draaien op dezelfde rendercode als
  wel-meedoende routes, twee regels om te herstellen) én groep C (`/werkoverleg`, `/roloverleg2` — nooit
  herbouwd) horen er nu allemaal bij. Groep A eerst (goedkoopste winst: `att-*`/`qadd-*`-families, ~40
  gebruiken over zes views in één klap), dan B, dan C.

**Tweede correctie (19 sept, avond, na echte pixel-sampling).** Mijn eerste akkoord op de tokentabel
rustte op toetsing aan mijn eigen beschrijving van de screenshots, niet op de pixels zelf. Zodra Claude
Code de kleuren daadwerkelijk sampelde uit `claude/huisstijl_referentie_productpagina.jpg` en
`-email.png`, bleek zes van de acht "afwijkingen" pixel-exact te kloppen: `--nu-bg` (#FFFAFA), `--nu-surface`
(#FFFFFF), `--nu-neon` (#00FF00, de knop), `--nu-accent` (#00A551, de bovenbalk), `--nu-muted` (#58595B)
en `--nu-border-subtle` (#E6E7E8) zaten al goed. "Gebroken wit/crème" uit mijn eigen beschrijving bleek
gewoon #FFFAFA te zijn, geen apart crème-kleur — en die kleur komt in geen van beide referentiebeelden
voor, dus het eerdere besluit om `--cream`/`--ink`/`--sand` uit het oude `nooch.css` te hergebruiken
is hiermee ook van tafel: dat is het oude Village-palet, niet het nooch.earth-palet.

Overgebleven, ditmaal wél pixel-onderbouwd:
- `--nu-bg-alt`: #E9FBE9 → #E2FFE3 (het lichtgroene vlak, gemeten op 18% van de productpagina).
- `--nu-accent-text`: #14713C → #1F9D55 (#14713C komt nergens in de beelden voor).
- Een voorstel om `--nu-text` te splitsen in #000000 (randen/koppen/logo) en #1A1A1A (lopende tekst),
  beide pixel-prominent aanwezig — dit raakt 37 losse gebruiken die één voor één ingedeeld moeten worden.

Besluit: de twee kleurcorrecties akkoord. De splitsing van `--nu-text` niet doen — het verschil tussen
#000000 en #1A1A1A is met het blote oog niet waarneembaar, en 37 losse indelingen met dat risico voor een
onzichtbaar verschil is het niet waard. `--nu-text` blijft één token, vastgezet op #000000 (het
pixel-exacte, en het is toch al de waarde voor randen/koppen/logo).

**Derde correctie (19 sept, avond, na att-*/qadd-*-implementatie).** Twee kleurcorrecties gecommit
(`fbb3456`), suite 4.046 passed / 1 failed (bekend). Bijvangst: `.attcard` (alleen in `projects.py`,
buiten de gescande views) had nog een crème kaart met ronde hoeken om zwart-gestylde inhoud — gevonden
doordat Claude Code de test structureel schreef (elke att-/qadd--selector die rand/radius/schaduw zet,
moet een pixel-onderbouwde tegenhanger hebben) in plaats van op naam. Ook een `.qadd-form textarea`
box-shadow verwijderd — referentie heeft nul schaduwen, dat was een fout, geen stijlkeuze.

Claude Code stopte terecht vóór de vier typografiepunten (hoofdletterkoppen, het `.nu-eyebrow`-component,
hoofdletters op knopteksten, de laatste `border-radius: 999px`): mijn akkoord ging alleen over de twee
kleurcorrecties en de groepsvolgorde, en hoofdletterkoppen zijn de zichtbaarste wijziging van het hele
traject. Besluit: wél doen, alle vier — dit is precies wat de referentiebeelden laten zien (NINE PLANTS
ONE SHOE, GROW A PAIR, de eyebrows THE PROOF/THE PRICE/THE PACT, alles in hoofdletters) en dus geen
losse smaakkeuze maar een directe uitwerking van Stefans eigen instructie ("zorg dat Village ook in
deze design stijl eruit ziet"). Meenemen in de eerstvolgende stap, vóór de rest van groep A.

Punt 3: verwijder of verklein het rechter Organization-paneel op Circle-pagina's. De organisatieboom
blijft in de linkerbalk staan (ongewijzigd), de volledige rollenlijst blijft bereikbaar via de
bestaande "Roles"-tab. Geen functionaliteit verdwijnt, alleen de dubbele weergave.

Punt 4: onderzoek eerst hoe het huidige edit-formulier is opgebouwd (welke velden, hoe wordt
opgeslagen, welke rechtencheck) voor je de UI omzet naar inline bewerken (in de pagina zelf klikken
en typen, opslaan zonder aparte pagina-navigatie). Behoud dezelfde rechtencheck en dezelfde
version/change_note-opslag als nu.

Testdiscipline: zelfde regel als de interface-fases hiervoor (3-5 tests per onderdeel, handmatige
doorloop). Rapporteer per punt apart voor je naar het volgende gaat, zodat elk punt los is te
beoordelen — dit is geen aaneengesloten opruimronde, dus geen noodzaak om alles achter elkaar door te
draaien zonder tussenrapportage.

Volledige testsuite voor/na elk punt, commit per punt (niet alles in één grote commit), en meld het
resultaat.
```

**Fase 10, nieuw punt 5: kennisbank/keyword-laag weg (besloten, 20 sept, nacht).** Stefan, expliciet:
"kennisbank ook weg dus." Dit is de laag die in de architectuurreview van vanavond
(`claude/architectuur_review_20sept.md`) al als grootste laaghangende fruit was geïdentificeerd:
~2.991 regels (1.920 bron + 1.071 tests) — alle `keyword_*.py`-modules, `kennisbank.py`,
`kennisbank_sources.py`, `views/keyword_lens.py`, `skills_impl/keywords_everywhere.py` — nog
volledig aanwezig en nog 34x aangeroepen vanuit `cockpit2.py`'s dispatch, terwijl niemand er nog een
lens op leest (bevestigd in de audit van 19 sept). Eén uitzondering, expliciet behouden:
`library.json` (de goedgekeurde/verboden-woordenlijst) blijft bestaan als los bestand, want de
claims-checker gebruikt die al. Verder alles weg: de modules, de routes/dispatch-acties in
`cockpit2.py`, de tests. Dit is onafhankelijk van de fase 10-huisstijl/kanaal-punten hierboven en kan
er los van worden opgepakt zodra Claude Code daar ruimte voor heeft — geen datamodel-risico zoals bij
punt 1, puur verwijderen van code zonder nog-levende aanroeper.

## Fase 10, nachtdoorloop (20 sept, 03:05-04:50) en ochtendbesluiten

Claude Code voerde het nachtmandaat exact uit zoals afgesproken: punt 2 (groep A, B, C) en punt 3
afgerond, elk in een eigen commit (`7fa8492`, `3843cb2`, `0d305a3`, `5703b70`, `3cda4fe`, `506f9d6`),
gestopt bij punt 1 en 4 zoals gezegd, niets gedeployed of gemerged (branch `fase1-dode-rolklassen`,
prod ongewijzigd op `8ab787a`). Van 491 open oude-look-klassegebruiken naar 9, en die negen zijn vorm
en geen kleur (`mform`, `mdot`, `car`, `pdisc`) — niets meer aan te herstylen. Suite 4.060 passed, 1
bekende fail, 1 xfailed. Volledig log in `claude/fase10_nachtlog.md`. Twee keer ving een structurele
test (op patroon, niet op naam) een zelfgemaakte fout op vóór hij vastzat: `.attcard` (fase 9) en een
tweede eyebrow-definitie voor `gs-group`/`gs-kind` (vannacht) — Claude Code was op het punt het
probleem opnieuw te maken dat een uur eerder was opgelost.

Bij het neutraliseren van kleuren zonder merkdekking is vooraf gemeten in plaats van aangenomen:
koraal en paars komen in de referentiebeelden op 0-5 pixels voor (geen merkkleur, weg), geel op
18-662 pixels (dat zijn de sterren, blijft staan). Die meting staat in het CSS-commentaar, net als de
bewuste — niet gemeten — keuze om `--nu-danger` te laten staan (foutkleur is functioneel nodig).

**Zes besluiten op de vragen en bevindingen van vannacht:**

1. **Punt 3, de zijbalk-afweging: functionaliteit behouden, akkoord.** De rail deed iets extra's (de
   huidige node openklappen en markeren) dat de zijbalk niet deed; Claude Code koos dat te behouden
   via `_send`, met als gevolg dat de zijbalk op node-pagina's niet meer letterlijk pixel-voor-pixel
   hetzelfde is als voorheen. "Ongewijzigd" was bedoeld als scopebegrenzing (niet ook de zijbalk zelf
   herontwerpen), niet als eis dat er geen letter code verandert. Terugdraaien zou een echte,
   zichtbare functie (weten waar je bent in de boom) laten verdwijnen voor een woordelijke lezing van
   een instructie. Blijft zoals gebouwd.
2. **Punt 1a, het zoek/filterveld: bouwen, nu, los van de rest.** Dit stond al los aangemerkt
   ("dat staat los van de rest") en is inmiddels acuut: 442 niet-gearchiveerde projecten = 442
   kanalen in de lijst, geen enkele filtering. Niet laten wachten op het kanaal-datamodel-voorstel
   hieronder.
3. **Hoofdletters in zijbalk-navigatie en tabbladen: ja, meenemen.** Dit viel buiten de oorspronkelijke
   vier typografiepunten, maar is dezelfde regel als daar al besloten (hoofdletterkoppen, hoofdletters
   op knopteksten) — de referentie (`SHOP STORE MISSION CONTACT`) bevestigt het, en zijbalk/tabs naast
   knoppen met een ander lettergeval is precies de inconsistentie die deze hele exercitie moest
   wegnemen. Geen nieuwe smaakkeuze, gewoon dezelfde regel volledig doortrekken.
4. **Punt 1b, kanaal-id-vorm: optie A, `topic:<id>` met een aparte namenlijst.** Zelfde argument als
   de gesorteerde DM-id: identiteit hoort niet aan een weergavestring te hangen. Hernoemen mag de
   trail niet breken en twee mensen mogen niet per ongeluk twee kanalen maken door hoofdletter- of
   spatieverschil ("Batch 4" vs "batch-4").
5. **Wie mag een los kanaal aanmaken: iedereen die ingelogd is**, zelfde niveau als `_claims_gate`
   sinds fase 5 — dit is een toevoegende, niet-destructieve actie (er verdwijnt niets, er wordt niets
   overschreven), en past bij Stefans eigen "volledig zoals Slack"-uitspraak van eerder. Expliciet
   AUTHZ-label verplicht op de nieuwe dispatch-tak, zoals CLAUDE.md eist.
   **Geen lidmaatschap-begrip deze ronde**: iedereen ziet alle losse kanalen. Dat is een tweede nieuw
   datamodel-concept en hoort niet in dezelfde ronde als het eerste.
6. **De correctie, expliciet benoemd**: dit draait fase 8's besluit om ("Cirkelkanalen: één per
   bestaande cirkel. Geen vrije onderwerp-kanalen zoals #batch-4"). Terecht dat Claude Code dit niet
   stilzwijgend bouwde. Vastgelegd: Stefan is hierop teruggekomen (zelfde avond als de inbox-migratie
   hierboven), met reden (Messages is bij dit aantal kanalen onbruikbaar zonder zoeken én zonder de
   mogelijkheid een eigen kanaal te beginnen, "zoals bij Slack").
7. **Punt 4, de change_note-vraag: geen drie versie-entries voor één bewerking.** Inline bewerken
   hoeft niet per veld op te slaan. Zelfde patroon als nu (één Save-actie, één versie-entry), alleen
   anders gepositioneerd: velden worden inline bewerkbaar, maar het opslaan blijft één moment — een
   knop/balk die verschijnt zodra er een veld "dirty" is, en die bij klikken alle gewijzigde velden in
   één `update()`-aanroep met één `change_note` wegschrijft, exact zoals het huidige formulier al doet.
   Geen debounce-timer, geen sessie-concept nodig: gewoon dezelfde ene save-actie, alleen niet meer
   achter een aparte "edit"-`<details>` verstopt.

## Fase 10, verduidelijking op de uitvoeringsterugkoppeling (20 sept, ochtend)

Claude Code voerde de zes ochtendbesluiten uit (zoek/filterveld + 25-cap met "25 van 37 · zoek voor
de rest", de front-deur/zoekfilter-bugfix, `hernoem_topic()` + de "batch niet in id"-assert, de
omgedraaide leeg-kanaal-zichtbaarheid, hergebruik van de `qadd-`-familie, de altijd-in-HTML-
zichtbare save-balk die JS verbergt) en vroeg om twee dingen. Antwoord op beide:

**1. "De inbox-migratie van gisteravond" is geen misverstand — het is optie (b): een nieuw, groot,
al genomen besluit.** Niet de visuele pas op `inbox.py` (die is inderdaad af en apart), en niet een
verwarring uit een andere draad. Dit staat al drie keer in deze brief vastgelegd, met oplopende
precisie:
- Fase 8, "tweede ronde": het eerste besluit om de 338 rol-notificaties apart te houden omdat een
  kanaalbericht geen afhandelstatus zou kunnen dragen.
- Fase 8, "derde ronde, definitieve uitkomst": dat argument bleek destijds toch overeind te blijven
  op andere gronden (geen mens als DM-tegenpartij voor 333 van de 338, en een verwerkingsmodel met
  outcome/poort dat niet zomaar een boolean wordt) — NotifStore + `/inbox` bleven bestaan, met die
  reden vastgelegd in `channels.py` als commentaarblok.
- Fase 10, "Aanvulling op punt 1" (20 sept, nacht): Stefan komt hier expliciet en zonder voorbehoud
  op terug — "inbox moet gewoon weg dat wordt een kanaal in messages" — en ik heb toen zelf tegen
  Stefan ingebracht dat het non-DM-argument (geen mens als afzender) niet per se een blokkade is
  (een bericht kan actieknoppen/state dragen, net als een Slack-bot-bericht), waarna Stefan expliciet
  besliste: niet onderzoeken, gewoon bouwen. Dat overrulet fase 8's "derde ronde" bewust, met reden.

Dit was al meegegeven in de paste-back van vannacht (het instructieblok bevatte expliciet de zin
"In hetzelfde voorstel: `/inbox` en NotifStore's 338 rol-notificaties... worden ook channel-
berichten"), maar de nachtronde heeft dit deel van het voorstel niet gemaakt — alleen het vierde-
kanaalsoort-deel (het losse/topic-kanaal) is voorgesteld en, na mijn ochtendbesluiten, gebouwd. De
NotifStore/inbox-migratie zelf is dus nog steeds niet voorgesteld, laat staan gebouwd. Gevraagd:
maak nu dat specifieke deel van het voorstel, met dezelfde harde eisen als eerder vastgelegd
(fase 8, regel 683 e.v.):
- Verifieer eerst of elke rol met een openstaande NotifStore-rij eenduidig naar één actuele
  menselijke houder herleidbaar is (de bestaande rol-naar-persoon-vertaling). Is dat niet eenduidig
  voor een deel van de gevallen: terugmelden voor er iets gebouwd wordt, niet zelf een aanname kiezen.
- Is het wel eenduidig: stel voor welk kanaal zo'n bericht ontvangt — een kanaal per rol (mogelijk
  hetzelfde mechanisme als het nieuwe losse/topic-kanaal van vannacht) of het persoonskanaal van de
  actuele rolhouder. Kies zelf de best passende vorm en leg die voor.
- Harde eis, niet-onderhandelbaar: de bestaande verwerkingsstate (185 outcomes, 54 poort-oordelen,
  read/processed/archived/done) moet zichtbaar blijven op het resulterende bericht zelf. Niets van
  die state mag stilzwijgend verdwijnen bij de migratie ("dood is dood, niet halfdood").
- Na migratie: NotifStore verwijderen, geen dubbele opslag, en `/inbox` als apart scherm/route laten
  vervallen (wordt een filter/weergave op de kanalen, zoals fase 8 al beschreef).

**2. Markdown-broncode i.p.v. opgemaakte tekst bij inline bewerken — bericht kwam afgebroken door.**
Ik heb Stefan gevraagd het vervolg van dit punt te sturen; zodra dat er is volgt het antwoord. Bouw
hier nog niets aan tot dat antwoord er is.

## Fase 10, tweede antwoord op de NotifStore-vraag en het markdown-punt (20 sept, ochtend)

**Correctie op mijn eigen cijfer, door Claude Code aangetoond**: ik heb de hele week "338
rol-notificaties" als dé wachtrij genoemd. Dat is de totale historie van rol-notificaties, niet wat
nog open staat. De echte verdeling van de 371 NotifStore-rijen: 28 open, 225 gearchiveerd, 52
verwijderd, 33 done. De wachtrij is dus 28 items; 343 van de 371 zijn al afgesloten historie. Dat
verandert het karakter van de migratie: het zwaartepunt ligt bij historie bewaren, niet bij een
levende wachtrij verplaatsen.

**Rol-naar-persoon-vertaling: niet eenduidig, zoals gevraagd te verifiëren voor er iets gebouwd
werd.** Van de 28 open items: 9 wel eenduidig (marketing_lead 5, creator_of_shoes 2,
strategic_lead_founder_steward 2 — alle drie levend, precies één mens-vervuller), 19 niet
(librarian 8, harry_hemp 5, copywriter 2, compliance 2, concurrent_scout 2 — allemaal rollen die in
fase 1-3 zijn gearchiveerd, nul mens-vervullers over). Claude Code controleerde `afslanken.jsonl` op
een vastgelegde opvolger: het `naar`-veld is bij alle vijf leeg; twee van de vijf hebben zelfs
expliciet in het prozaveld staan dat er bewust geen opvolger is (copywriter: "vervallen-case: gaan
NIET naar een andere rol"; concurrent_scout: "vervallen BEWUST"). Terecht geen regex op dat
prozaveld losgelaten om alsnog een persoon te forceren — dat was precies de aanname waar ik voor
waarschuwde.

**Voorstel geaccordeerd: een vijfde kanaalsoort `role:<record_id>`, niet vertalen naar een
persoonskanaal.** Dit lost de "naar welke mens"-vraag niet op, het maakt hem overbodig: een
gearchiveerde rol behoudt zijn eigen kanaal als read-only historie, in plaats van dat de historie
gedwongen wordt in de DM van wie de rol *nu* toevallig vervult (of, erger, van niemand). Zelfde
principe als optie A voor het topic-kanaal: identiteit hoort niet aan de huidige invulling te
hangen. Stop je compliance's 69 items in Stefans DM, dan loopt die historie de deur uit zodra iemand
anders compliance gaat vervullen. Akkoord, geen verdere afweging nodig.

**De 19 niet-eenduidige open items op de vijf gearchiveerde rollen: met rust laten, niet
geforceerd sluiten of toewijzen.** Omdat het kanaal per rol is (niet per persoon), is er niets te
kiezen: ze migreren gewoon mee naar hun rol-kanaal, met hun huidige status (`open`) intact. Ze
blijven zichtbaar als nog-niet-afgehandeld, want dat is de waarheid — niemand heeft ze ooit gesloten
en er is nu ook niemand die dat namens de rol kan doen. Geen fabricage van een afgehandeld-status,
geen automatische toewijzing aan een willekeurige mens: "dood is dood, niet halfdood" geldt ook hier
in de andere richting — een rol die dood is, krijgt geen kunstmatig levend gemaakte wachtrij. Wil
Stefan zelf ooit een van die 19 als mens beoordelen en afsluiten, dan kan dat gewoon vanuit het
rol-kanaal, als aparte, latere actie.

**Verwerkingsstate: letterlijk overnemen, geen samenvatting.** Akkoord met het voorstel om de
volledige verwerkingsstate (185 outcomes, 54 poort-oordelen, en de rest) in een apart
verwerking-blok op het bericht te zetten, geen afgeleide/samengevatte status, met een guard-test die
de aantallen vóór en ná telt en gelijk moet zijn.

**Aanpak: drie stappen, akkoord.** Eerst naast elkaar schrijven (NotifStore blijft leidend,
kanaalberichten worden er parallel bij geschreven), dan `/inbox` omzetten naar de kanalen-weergave,
pas daarna NotifStore verwijderen. Bij 13 methodes, 46 aanroepen, 18 bronbestanden en 37 testbestanden
is dit de grootste ingreep van fase 10 tot nu toe — een fout in stap 1 mag niet de historie van 371
items meenemen, dus liever drie kleinere, apart te testen stappen dan één grote.

**Punt 2, het markdown-punt: optie 2, akkoord.** ~~Niet optie 1... Bouw dit.~~ **Teruggedraaid, zie
hieronder — Stefan wil geen preview-knop, maar echte inline-bewerking.**

## Fase 10, herziening op het markdown-punt: geen preview-knop, echte Notion-achtige inline-bewerking (20 sept, ochtend)

Stefans reactie op "optie 2, akkoord" hierboven: dat lost het probleem niet op zoals hij het bedoelt.
Een preview-knop laat je nog steeds `**vet**` als brontekst zien terwijl je typt, en pas ná een klik
op preview zie je hoe het eruitziet — dat is niet wat "inline bewerken" voor hem betekent. Zijn eis,
expliciet: de Wiki moet aanvoelen als Notion — je klikt in tekst en die is al opgemaakt, je selecteert
een woord en klikt vet, en het wordt op dat moment zichtbaar vet, geen sterretjes of hekjes ooit
zichtbaar tijdens het bewerken. Dat is dus geen optie 2 en ook geen (het eerder afgewezen) optie 3 —
het is een derde, grotere technische aanpak: een echte rich-text/WYSIWYG-editor in plaats van een
tekstvak met markdown-brontekst plus toolbar. **De eerdere goedkeuring van optie 2 hierboven is
hiermee teruggedraaid — niet bouwen.**

Dit is geen kleine aanvulling maar een andere technische laag dan `md_editor` nu heeft (textarea +
toolbar die sterretjes/hekjes invoegt). Vraag aan Claude Code: doe eerst een korte technische
verkenning (geen bouw) van wat een contenteditable-achtige of vergelijkbare inline-rich-text-aanpak
kost, en leg een voorstel voor vóór er iets gebouwd wordt — dit raakt potentieel elke Wiki-pagina en
elk `md_editor`-gebruik in de app, dus hetzelfde "leg voor voor je bouwt"-patroon als bij de
kanaal-datamodel-vragen. Randvoorwaarde die al vaststaat en niet opnieuw ter discussie staat: het
opslagmodel blijft één save-actie per bewerking (fase 10, punt 4) — de editor mag intern rich text
tonen, maar de onderliggende opslag blijft dezelfde markdown-string plus één `change_note`, geen
nieuw dataformaat.

**Tweede, nieuwe eis bij dezelfde reactie: Messages moet zich als Slack gedragen, expliciet genoemd:
een bericht moet verwijderd kunnen worden.** Dit stond nog niet in fase 8's channel-ontwerp. Vraag
aan Claude Code: neem dit mee in hetzelfde soort voorstel (niet blind bouwen) — hoe een verwijderd
bericht zich moet gedragen (volledig weg, of een Slack-achtige "dit bericht is verwijderd"-plek-
houder) is een keuze met gevolgen voor de trail/audit-gedachte die de rest van dit traject
("dood is dood, niet halfdood") vasthoudt voor rol-/verwerkingsberichten — voor een gewone
DM-typo is een andere afweging redelijk dan voor een NotifStore-afkomstig bericht met een
poort-oordeel erin. Laat dat onderscheid (mag een bericht met een verwerking-blok wél verwijderd
worden, of alleen "gewone" berichten) onderdeel van het voorstel zijn.

**Het DM-gedeelte van dezelfde reactie ("DM kunnen sturen gewoon die interface") is al zo
ontworpen.** Fase 8 legde het persoonskanaal al vast als een echt tweerichtings-DM-kanaal (twee
kanten kunnen schrijven), geen aparte actie nodig — alleen bevestigen dat dit inderdaad zo aanvoelt
zodra de kanalen straks in gebruik zijn, geen nieuwe bouwvraag.

## Fase 10, NotifStore-migratie stap 1 van 3 afgerond (20 sept, ochtend, commit `a8aed27`)

Alleen schrijven, nog niets verwijderd — NotifStore, `/inbox` en `/inbox/verwerk` blijven ongewijzigd
tot stap 3. Suite 4.098 passed / 1 failed (bekende). Getest op een lokale kopie van de echte
productiedata (`notifications.json`, kopie na afloop verwijderd): 338 rol- + 33 persoon-notificaties
verwerkt, 338 berichten geschreven naar 17 rolkanalen (niet 8 zoals de open-items-telling deed
vermoeden — meerdere gearchiveerde rollen als the_source, noochville__circle_lead, librarian hebben
wél historie maar geen open items, en bevestigen daarmee de vormkeuze: een opgeheven rol houdt zijn
kanaal, er hoeft niemand aangewezen). De harde eis is exact gehaald: outcome 185→185, poort 54→54,
verwerkingen 83→83, en de overige velden (read/processed/archived/done/deleted) kwamen allemaal
ongewijzigd door.

Drie bouwkeuzes, vastgelegd: het notificatie-id wordt het bericht-id (idempotent, en herleidbaar
naar de bron zolang NotifStore nog bestaat); `at` komt uit de notificatie, niet uit de klok (anders
staat drie maanden gesprek op de migratiedag); de verwerking wordt letterlijk overgenomen, geen
afgeleide status — zoals al vastgelegd.

Eigen bug gevonden en gefixt tijdens het testen: de droogloop-uitvoer toonde ook de ná-kolom, die bij
een droogloop per definitie nul is en dus als "acht regels wijken af" oogde — dezelfde soort
misleidende no-op-melding als eerder bij de deploy-status. Droogloop toont nu alleen de huidige
telling; de ná-telling en de guard-test lopen pas bij `--apply`. Geen beslissing nodig, gewoon
genoteerd voor de geschiedenis.

Ga door met stap 2 (`/inbox` laten lezen uit de kanalen).

## Fase 10, NotifStore-migratie stap 2 van 3 afgerond (20 sept, commit `3f261c7`) — eerst een dag op prod voor stap 3

Alleen de lezer is om, NotifStore blijft de schrijver. Suite 4.102 passed / 1 failed (bekende).
Fail-open opgezet, bewust andersom dan de standaardregel: faalt de kanaal-lezing, dan valt `/inbox`
terug op NotifStore, want een lege inbox is hier het gevaarlijke antwoord (iemand denkt dat er geen
werk ligt).

**Stap 2 ving een echte fout in stap 1**: `VERWERKING_VELDEN` was een handgekozen lijst van twaalf
velden. Zodra `/inbox` erop ging lezen bleek de view zeventien velden te gebruiken — `herkomst`,
`pagina`, `voorstel`, `triage_grond`, `triage_rol`, `triage_vorm` en `ok` stonden er niet bij en
waren dus stil leeg gebleven. Nu gaat alles mee, met een overslaan-lijst van drie (id/at/tekst, die
al op het bericht zelf staan) in plaats van een aanvink-lijst — een handgekozen lijst is zelf een
tweede plek waar een veld vergeten kan worden. Precies de reden voor de drie-stappenaanpak: in één
grote commit was dit pas ná het verwijderen van NotifStore gevonden, zonder bron om uit te herstellen.

**Besluit: stap 3 nu nog niet bouwen/deployen.** Claude Code's eigen advies, overgenomen: mijn
eerdere akkoord op de drie-stappenaanpak was "pas als dat een tijdje staat" — en stap 2 heeft tien
minuten gedraaid, alleen tegen een lokale kopie van `notifications.json`, nooit op prod. Volgorde:
(1) deploy stap 1+2 (verwijdert niets, `/inbox` valt fail-open terug op NotifStore bij problemen),
(2) laat een dag op prod draaien als echt bewijs in plaats van alleen de testsuite, (3) pas dan stap
3 bouwen én deployen — met NotifStore-verwijdering zelf (13 methodes, 46 aanroepen, 18 bronbestanden,
37 testbestanden) onomkeerbaar, dus geen deploy vóór Stefan hem gezien heeft.

## Fase 10, fundamentele vereenvoudiging van de NotifStore-migratie (20 sept) — de verwerkingsstate hoeft niet bewaard te worden

**Stefan, voor de deploy van stap 1+2: "alles wat tot dusver in de inbox is gekomen kon ik niet echt
veel mee, dus dat werkte sowieso niet, dus ook niet om te houden — ik denk dat als er iets
gesignaleerd is het gewoon naar een DM kan en dan is de mens verantwoordelijk."** Dit is geen kleine
correctie maar een terugtrekking van de "hard eis, niet-onderhandelbaar"-eis die hierboven staat.
Expliciet nagevraagd en bevestigd:

- **Dit geldt ook voor de al gemigreerde historie, niet alleen voor toekomstig gedrag.** De hele
  verwerkingsstate-bewaar-exercitie (het `verwerking`-blok, de guard-test op 185 outcomes/54
  poort-oordelen, het vijfde kanaalsoort `role:<record_id>`) was zorgvuldigheid voor een mechanisme
  dat in de praktijk nooit bruikbaar bleek. Stap 1+2 zoals gebouwd (commits `a8aed27`, `3f261c7`)
  worden hiermee **niet** de basis voor stap 3 — ze worden vervangen door een simpeler ontwerp,
  hieronder.
- **Voor de 19 niet-eenduidige open items op de vijf gearchiveerde rollen (compliance, librarian,
  harry_hemp, copywriter, concurrent_scout): naar Stefans eigen DM**, als vangnet. Niet laten
  vervallen, niet opnieuw een rol-kanaal ervoor optuigen.

**Het nieuwe, simpele ontwerp: elke NotifStore-rij wordt één gewoon DM-bericht, geen aparte
kanaalsoort, geen verwerking-blok, geen state machine.** Voor alle 371 rijen (niet alleen de 28 open
— hetzelfde principe geldt voor de 343 al gesloten items, gewoon leesbare historie in een DM in
plaats van een apart archief):
- 33 rijen met een `entry_id` (de @-vermeldingen): DM naar de vermelde persoon, zoals fase 8 al
  deed voor de wall-vermeldingen — geen wijziging.
- 338 rol-rijen: DM naar de huidige vervuller van die rol. Is er geen levende vervuller (de vijf
  gearchiveerde rollen): DM naar Stefan zelf, voor alle rijen van die rol, niet alleen de 19 open.
- Geen `afgehandeld`/`verwerking`-veld nodig op het bericht — het is een gewoon berichtItems, de
  mens die 'm ontvangt is verantwoordelijk, precies zoals elk ander DM-bericht. `at` blijft uit de
  notificatie komen (niet de klok), dat principe verandert niet.
- Het `role:<record_id>`-kanaalsoort uit de eerdere voorstellen: **vervalt**, niet meer nodig nu er
  altijd een mens (rolvervuller of Stefan) als DM-ontvanger is.

Gevraagd aan Claude Code: beoordeel zelf hoeveel van commit `a8aed27`/`3f261c7` herbruikbaar is
(het idee "notificatie-id wordt bericht-id", "at uit de notificatie" blijven bijvoorbeeld gewoon
goed) versus wat vervangen moet worden (het rol-kanaal-concept, het verwerking-blok, de
guard-test-op-staat). Nog steeds niet in één keer: eerst de nieuwe opzet als voorstel, dan pas
bouwen — dezelfde reden als eerder (dit raakt in potentie alle 371 items, een fout is duur om achteraf
te herstellen als NotifStore eenmaal weg is). Stap 3 (NotifStore verwijderen) blijft de laatste,
onomkeerbare stap, pas na Stefans akkoord op het herziene voorstel én na een periode op prod.

## Fase 10, NotifStore-vereenvoudiging: signaal.py (commit `c8a7790`) en B1 in de stash (20 sept)

**Gecommit**: `signaal.py`, één plek die bepaalt bij wie een melding landt, gebruikt door zowel de
historische migratie als alles wat nieuw ontstaat — voorkomt dat dezelfde rol-id via twee losse
implementaties op een dag uit elkaar kan gaan lopen. Suite 4.102 passed / 1 failed (bekende).

**Eén bewust verschil tussen historie en nieuw werk, expliciet vastgelegd**: bij een rol met
meerdere huidige vervullers parkeert de migratie (geen automatische keuze), maar een nieuwe melding
gaat naar alle huidige vervullers tegelijk. Redenering, overgenomen: historie hoort precies één
rustplaats te hebben, gekozen door een mens; nieuw werk mag liever dubbel aankomen dan bij niemand.

**B1 (de tien schrijfplekken van `.notif.add` omzetten naar een DM) werkt functioneel — nul
`.notif.add`-aanroepen meer in `cockpit2.py` — maar staat in de stash (`B1-writers-wip`), niet
gecommit, niet gedeployed.** Reden, overgenomen zonder discussie: de suite gaat van 1 naar 44
failures over twaalf testbestanden, allemaal van dezelfde vorm (`assert len(items) == 1` → `0 == 1`)
— geen bugs, maar tests die vastleggen "er ontstaat een inbox-item" terwijl ze nu moeten vastleggen
"er ontstaat een DM". Terecht geweigerd dit aan het eind van een lange beurt in één veeg te
herschrijven; volledige suite groen vóór commit blijft de afspraak.

**Twee gedragsbesluiten, voorgelegd in plaats van stilzwijgend gebouwd — beide akkoord:**
1. `_settle_inbox(processed=True)` stuurt voortaan niets meer. Vier van de vijf aanroepen zetten
   voorheen een item neer en markeerden het in dezelfde beweging als verwerkt — werk dat al gedaan
   was op het moment dat het verscheen. Zonder verwerkingsmodel is er geen "al gedaan"-status meer
   om aan te hangen, en een bericht over reeds afgerond werk is geen bericht maar een log. Terechte
   conclusie: alleen `processed=False` levert nog een zinnig DM-bericht op.
2. De extra velden (`type`, `rol`, `prive`, `opdrachtgever`, `MENS_GETYPT`, `afronding`,
   `suggestie`) vervallen — die dienden het oude inbox-scherm, een DM heeft alleen tekst, afzender en
   tijd. `bron_project` blijft als enige uitzondering, puur als herkomst ("from project X"), anders
   is het bericht niet meer leesbaar op zichzelf. Consistent met de eerder besloten vereenvoudiging
   (geen verwerkingsstate meer bewaren) — dit is dezelfde beslissing nu toegepast op de velden in
   plaats van op de status.

**De 11 geparkeerde rijen (rol met meerdere huidige vervullers, geen automatische keuze): behandel
hetzelfde als "geen vervuller"** — naar Stefans eigen DM, net als bij de vijf gearchiveerde rollen
zonder levende vervuller. Geen 11 losse handmatige toewijzingen nodig: het gaat om historie
(grotendeels al gesloten items, net als de rest van de 371), en Stefan kan van daaruit zelf
doorsturen als dat nodig blijkt. Uitzondering hierop is aan Stefan, maar dit is de pragmatische
default die aansluit bij "dit leverde toch nooit veel op" — geen zwaar proces optuigen voor iets met
lage waarde.

**Akkoord op het voorgestelde vervolg**: B1 als eigen beurt, de 44 tests per bestand nagelopen (niet
gehaast herschreven) zodat elk vastlegt "er ontstaat een DM" in plaats van "er ontstaat een
inbox-item" — bij elke test expliciet checken of de nieuwe assertie ook echt de juiste ontvanger en
inhoud verifieert, niet alleen `len() == 1` vervangen door een andere aanname. Daarna deploy van A+B1
samen (niet A alleen, terecht — een halfslachtige tussenstand deployen heeft geen zin). B2 pas
daarna.

## Fase 10, B1 groen (commit `12c7f7a`) en de besluitwachtrij-vraag (20 sept)

B1 staat: 4.104 passed, 1 failed (de bekende), 1 xfailed. Nog niet gedeployed. Van de tien
schrijfplekken zijn er acht omgezet naar plain-DM; twee niet, en dat bleek geen restwerk maar een
echte grens:

1. **Het pagina-voorstel** is geen signalering maar een verzoek met een beslissing (accepteren/
   weigeren/aanpassen).
2. **De werkoverleg-actie** is toegewezen werk met een afrondknop.

Samen goed voor 25 van de 43 gebroken tests — het bewijs dat dit een andere soort item is dan de
rest: in de oude inbox zat, naast de meldingenlijst die nu een DM wordt, ook een echte
**besluitwachtrij**. Gevolg: `spanning_ontstaat` (de typeer-/bevindingpoort) had alleen `NotifStore.
add` als aanroeper en draait nergens meer op de acht omgezette paden — een module die stilviel
zonder dat iets het zei.

~~**Besluit: de besluitwachtrij krijgt een eigen kleine store** (voorstellen + acties, niets meer),
niet NotifStore laten voortleven voor "nog even die twee flows."~~ — **teruggedraaid, zie hieronder.**

**Herzien (20 sept, na Stefans tegenvraag "wat hebben we hieraan, en wat als we dit niet doen?")**:
geen besluitwachtrij, geen nieuwe store. De twee vragen die dit bepaalden, zijn beantwoord:

- **Werkoverleg-actie: dat doet het werkoverleg al.** Er is al een bestaand mechanisme
  (`roloverleg.py`) dat de toewijzing en het afronden bijhoudt, los van NotifStore. De DM is dus
  puur een melding ("je hebt een actie toegewezen gekregen") bovenop een staat die al ergens anders
  leeft — niets nieuws om vast te leggen, alleen de melding zelf via de gewone DM-route.
- **Pagina-voorstel: menselijk maken, geen eigen mechaniek.** Geen automatische consequentie bij
  "accepteren" — Stefan (of wie de rol vervult) leest de suggestie en past de pagina, als hij het
  ermee eens is, gewoon zelf aan zoals bij elke andere wiki-bewerking. Geen aparte status nodig: een
  genegeerd voorstel betekent simpelweg dat de pagina niet verandert, hetzelfde patroon als elke
  andere DM vandaag.

Beide worden dus gewoon een plain DM, identiek aan de andere 371 rijen — geen uitzondering meer op
de tien schrijfplekken. `spanning_ontstaat` (de typeer-/bevindingpoort) haakt daarmee ook niet in op
een nieuwe store, maar op de ene gedeelde plek waar elke DM/message ontstaat — dezelfde plek voor
alle signalen, geen aparte aanroeper per type. Dit sluit de NotifStore-vereenvoudiging nu volledig:
geen nieuwe infrastructuur, geen `/inbox`-restant in welke vorm dan ook.

Twee bugs gevonden én al gefixt tijdens B1, akkoord, geen verdere actie: (1) een gast zonder
gekoppelde ontvanger verloor zijn genoteerde spanning stilletjes — valt nu terug op Stefans DM in
plaats van in het niets; (2) een zelf-regressie (jezelf vermelden maakte weer een gesprek met
jezelf) gevangen door een bestaande test en gefixt.

Correct gelaten: de twee documenten van vandaag (`implementatiebrief_opruiming_19sept.md`,
`ux_voorstel_best_practices_20sept.md`) zijn niet aangeraakt — die horen niet in een Claude
Code-commit. Fase 11 (UX-microinteracties) is bewust nog niet opgepakt.

**Deploy-akkoord**: ga door met A+B1 — `deploy.sh`, snapshot, `village notif_migratie`-droogloop,
rapport. Zoals altijd: geen `--apply` zonder dat rapport eerst gezien te hebben.

## Fase 10/11, terugkoppeling op de HARDE REGEL, de besluitwachtrij-scope en de deploy-blokkade (20 sept)

**Spoor 1a (CLAUDE.md, commit `38c7770`)** — geplaatst zoals gevraagd, geen verdere actie.

**Spoor 1b (read-only inventarisatie van bestaande atoom-schuld)** — het kerngetal: 533 klassen
totaal, 57 gedeeld (≥3 bestanden), 420 privé (precies 1 bestand). Bijna vier op de vijf klassen is
dus "geen atoom". Grootste privé-aandeel: `wizard.py` (88%), `noochie.py` (67%), `search.py` (59%),
`roloverleg.py` (50%), `checklists.py` (42%), `projects.py` (37%), `inbox.py` (36%), `metrics.py`
(33%). Scherpste concreet bewijs: voor kaart/rij/knop-achtige dingen zijn er 10 gedeelde klassen
tegenover 55 eigen varianten in één bestand (`metrics.py` alleen al 17, `projects.py` 14). Losse
`<style>`/`style=`-schuld zit al onder de bestaande ratchet (`overview.py`, `strategy.py` als
grootste twee) — geen nieuwe actie nodig, die guard dekt dat al. Geen fix gedaan, terecht: de
monotone daling van de nieuwe regel betekent dat `wizard.py`, `roloverleg.py` en `metrics.py` de
eerste kandidaten zijn zodra iemand ze toch aanraakt voor iets anders. Vastgelegd als lijst, niet
als actie — precies de bedoeling.

**Spoor 2 (besluitwachtrij-scope, `claude/fase10_scope_besluitwachtrij.md`, commit `8728638`)** —
twee objecttypen, drie states in plaats van vijf vlaggen, wie schrijft/leest, en een bevriezende
guard in plaats van een plafond. `spanning_ontstaat` verhuist naar de write-kant, terecht: dat is
een vraag bij een verzoek, niet bij een mededeling.

Eén open vraag stond erin, nu beantwoord: **verzoeken gaan naar de plek waar ze over gaan**
(pagina-voorstel bij de wiki-pagina, werkoverleg-actie bij het werkoverleg) — geen aparte
`/inbox`-sectie voor verzoeken. Reden: een tweede, apart soort inbox-scherm is precies het patroon
dat vandaag al is afgeschaft omdat het niet werkte ("dit leverde toch nooit veel op" — dezelfde
constatering die tot de DM-vereenvoudiging leidde). Het zorgpunt uit de scope-vraag ("dan is er geen
enkele plek meer die zegt dat iets bij jou ligt") wordt opgevangen door dezelfde DM-laag die er al
is: een nieuw voorstel of een nieuwe actie stuurt, net als elke andere melding, een DM naar wie moet
handelen, met een link naar de plek waar de beslissing zelf plaatsvindt. Zo blijft er precies één
plek die zegt "hier moet je iets mee" (Messages, zoals nu al voor alles geldt), zonder een tweede
besluit-scherm te bouwen dat los staat van waar de beslissing inhoudelijk hoort.

**Aanscherping op de routing (20 sept, Stefans vraag "hoe gaat de routing dan?")**: geen aparte
routinglogica voor deze twee objecttypen. De routing loopt via exact hetzelfde mechanisme als de
andere 371 rijen vandaag: `signaal.py` bepaalt wie de huidige vervuller (rol) of toegewezene (actie)
is, en daar gaat een gewone message naartoe, precies zoals elke andere melding. "Oppakken" betekent:
de mens ziet 'm in Messages zoals nu al voor alles geldt, en die message wijst naar de plek waar de
beslissing/afronding daadwerkelijk gebeurt (accepteer/weiger/aanpas bij het voorstel, de afrondknop
bij de actie — bestaande of geplande knoppen, geen nieuw scherm). "Bij de wiki-pagina/werkoverleg"
uit de vorige alinea is dus niet een alternatieve manier om het te vínden, het is waar je na het
klikken op de message landt. Enige verschil met een gewone DM: er hangt een besluitwachtrij-record
achter (pending/geaccepteerd/geweigerd, toegewezen/afgerond), zodat de status niet verloren gaat
zoals bij een plain DM wel zou gebeuren.

**Per-bericht acties: vinken (verwerkt) en verwijderen (20 sept, Stefans aanvulling)**: uitbreiding
op de al geplande Slack-stijl berichtverwijdering. Twee acties per bericht: een vink om 'm als
verwerkt te markeren, en verwijderen (dan is-ie weg uit de conversatie). Onderscheid, bewust gemaakt
om niet dezelfde soort bug te herhalen als de gast-zonder-ontvanger van vandaag (een record dat stil
verdwijnt terwijl de onderliggende staat er niets van weet):

- **Plain DM** (de 371 gemigreerde + alle toekomstige gewone meldingen): geen backing-state, dus
  vinken is een pure, persoonlijke marker (decluttering, geen effect op iets anders) en verwijderen
  is onschuldig — weg is weg, er hangt niets aan vast.
- **Besluitwachtrij-bericht** (voorstel/actie, wél backing-state): vinken mag geen los, onafhankelijk
  vinkje zijn naast de echte beslissing — dat zou precies het lek herhalen dat B1 vandaag al een keer
  blootlegde. Vinken op zo'n bericht IS de beslissing afronden (accepteren/afronden raakt de
  besluitwachtrij-record rechtstreeks, geen aparte marker die uit de pas kan lopen). Verwijderen mag
  alleen als de onderliggende beslissing al is afgehandeld; staat 'ie nog open, dan eerst afhandelen
  — anders verdwijnt een openstaand verzoek spoorloos, hetzelfde risico als vandaag al eenmaal
  gevonden en gefixt is.

**Deploy** — geblokkeerd, niet door Claude Code maar door een actie bij Stefan: `deploy.sh` doet
alleen een fast-forward naar `origin/main`, prod staat op `8ab787a`, al het werk zit in PR #517 (een
nieuwe branch, `fase10-huisstijl-en-inbox` — de oude remote branch is bij de merge van #516
opgeruimd). Draaien voegt nu niets toe. **Actie bij Stefan: PR #517 mergen.** Zodra dat gebeurd is,
draait Claude Code zelfstandig door met wat al is afgesproken (`deploy.sh` → snapshot → `village
notif_migratie`-droogloop → rapport), geen nieuwe instructie nodig — alleen het rapport wachten op
een expliciet `--apply`-akkoord, zoals altijd.

## Fase 10, PR #517 blijkt niet te mergen: 400+ bestanden "conflict" (20 sept)

Stefan probeerde te mergen en GitHub meldt conflicten op 400+ bestanden (screenshots,
`docs/ARCHITECTUUR.md`, meerdere `.py`/CSS-bestanden, `claude/implementatiebrief_opruiming_19sept.md`
zelf). Uitgezocht via `git merge-base`/`git diff` (read-only, geen wijziging):

**De oorzaak, geverifieerd**: `fase10-huisstijl-en-inbox` en `main` delen een merge-base van vóór
zowel de fase 1-9-opruiming (#516) als het fase 10-werk. Beide takken zijn sindsdien onafhankelijk
van elkaar doorontwikkeld: beide verwijderden grotendeels dezelfde oude code (vandaar de duizenden
gedeelde deletions op beide kanten), en beide "creëerden" onder meer `claude/
implementatiebrief_opruiming_19sept.md` zelf, ieder vanuit hun eigen kant. Git ziet dat als twee
onafhankelijke toevoegingen van hetzelfde pad, geen inhoudelijke botsing — vandaar dat bijna alles
als conflict verschijnt, niet omdat er tegenstrijdige beslissingen in zitten.

**Voor de brief specifiek, geverifieerd door de content te vergelijken**: main's kopie (490 regels,
uit #516) is een oude momentopname van dezelfde brief, van vóór fase 3-11. De branch-kopie (1392
regels gecommit, plus 317 regels van mij nog ongecommit erbovenop) bevat exact diezelfde inhoud plus
alle latere correcties en uitbreidingen. Geen echte inhoudelijke tegenstelling — main's versie is
puur achterhaald. Voor dit bestand geldt: branch wint volledig.

**Risico dat nog opgelost moet worden vóór er gemerged wordt**: mijn 317 ongecommitte regels op de
brief bestaan nu alleen als bestand op schijf, niet als commit. Een merge starten terwijl dat er nog
zo bij staat is riskant (git-mergegereedschap werkt op commits, niet op een vuile werkmap). Eerst
committen, dan pas de merge proberen.

**Advies, niet zelf uitgevoerd (dit hoort bij Claude Code, niet bij een web-UI-conflictresolutie
over 400+ bestanden zonder de context waarom dingen verwijderd zijn)**:
1. Commit eerst de huidige staat van de brief (los, doc-only, geen test-impact).
2. Los de merge via de command line op (niet via GitHub's "Resolve conflicts"-editor — te groot,
   te foutgevoelig zonder de context die Claude Code al heeft over waarom elk bestand is verwijderd
   of gewijzigd).
3. Voor de brief specifiek: neem de branch-versie volledig, main's kopie is stale.
4. Voor de overige bestanden: per bestand beoordelen (niet blind "ours" toepassen) — sommige zijn
   waarschijnlijk hetzelfde soort vals conflict, maar niet gegarandeerd allemaal.
5. Volledige testsuite na het oplossen, rapport van de gemaakte keuzes vóór pushen.
6. Dit lost alleen de PR-mergebaarheid op. Nog geen merge náár main, nog geen deploy — dat blijft
   zoals afgesproken bij Stefan's expliciete akkoord.

## Fase 11: UX-microinteracties en informatiedichtheid, atomair opgebouwd (20 sept)

Aanleiding: een losse UX-review (los van fase 1-10, zie `ux_voorstel_best_practices_20sept.md` voor
de volledige analyse en een werkend HTML-prototype) tegen Stefans eigen analyse van wat Slack,
Notion, Obsidian, Duolingo, GlassFrog en Trello goed doen. Twee rondes feedback verwerkt: (1) geen
cirkeldiagram voor de organisatie, de lijst blijft — alleen bezet/vacant zichtbaar; (2) niet alleen
status tonen, ook laten voelen — echte microinteracties (slepen, hover, direct zichtbaar effect),
niet alleen informatie toevoegen.

**Zelfde discipline als de fase 9/10-huisstijl-opruiming: eerst het vocabulaire (atoms), dan de
samengestelde onderdelen (molecules), dan het gedrag (patterns) — niet per scherm losse CSS/JS
verzinnen.** Dit is precies de atomic-design-vraag die eerder deze fase (architectuurreview, 20
sept) al signaleerde: goede atomen bestaan in `nooch-ui.css` (`.btn`, `.card`/`.box`/`.kpi`,
`.pill`/`.chip`/`.badge`, `.nu-status` met `--ok`/`--open`/`--wait`/`--off`-modifiers), maar worden
niet overal hergebruikt. Fase 11 moet die lijn doortrekken, niet een parallelle set verzinnen.

```
Bouw fase 11 in drie lagen, in deze volgorde — elke laag eerst af, met eigen tests en commit, voor je
aan de volgende begint. Referentiebeeld en werkend gedrag staan in het HTML-prototype dat bij
`ux_voorstel_best_practices_20sept.md` hoort (vraag Stefan om de link als je 'm niet kunt vinden);
gebruik dat als gedragsspec (hoe het hoort te reageren), niet als CSS om te kopiëren (dat is een
los prototype-bestand, geen `nooch-ui.css`).

LAAG 1 — ATOMS (nieuw of hergebruikt, geen scherm-specifieke CSS)
1a. Rol-status-icoon: hergebruik de bestaande `.nu-status`-vorm+kleur-taal (gevulde cirkel = bezet,
    gestippelde cirkel = vacant) als klein icoon vóór een rolnaam in de organisatieboom. Geen nieuwe
    kleur, geen nieuwe vorm — dezelfde visuele taal die het bord en de checklist al gebruiken.
2a. Nieuw atoom `.nu-progress` (track + fill), klein en generiek: één balkje dat een percentage
    toont. Dit wordt hergebruikt in zowel de projectkaart (checklist-voortgang) als de losse
    checklist-weergave — bouw 'm dus als apart, herbruikbaar element, niet twee keer losse CSS.
3a. Kanaal-ongelezen-indicator als modifier op de bestaande `.msg-kanaal`-klasse (vetgedrukt +
    klein stipje/telling), geen nieuwe component.

LAAG 2 — MOLECULES (samengesteld uit de atomen hierboven)
1b. Projectkaart-voorkant (`.pkaart`-body uitgebreid, niet vervangen): titel, dan een rij chips
    (bestaand `.chip`/`.pill`-atoom: batch, deadline-indien-gezet), dan `.nu-progress` met de
    checklist-stand, dan owner/datum zoals nu. Alleen al bestaande projectvelden zichtbaar maken,
    geen nieuw datamodel.
2b. Checklist-rij: checkbox-atoom + label, gekoppeld aan de `.nu-progress` van hetzelfde project
    (klik = direct bijwerken, geen aparte opslagactie nodig voor de visuele stand — de bestaande
    checklist-opslag blijft leidend, dit is alleen de weergave die live meebeweegt).
3b. Kanaal-rij in Messages: naam + de ongelezen-modifier uit 3a + tijdstip laatste bericht.

LAAG 3 — PATTERNS (gedrag, niet alleen CSS)
1c. Sleep-patroon op het Projects-bord: een kaart naar een andere kolom slepen wijzigt de status
    van het project (zelfde statussen als de kolommen nu al vertegenwoordigen: actief/wacht/done/
    toekomst). Visuele feedback tijdens het slepen: de kaart iets optillen (geen schaduw — een
    randkleur-verandering of lichte transform, consistent met "geen schaduwen" uit de fase 9-regels),
    de doelkolom een lichte kleurverandering zolang je erboven zweeft. Val terug op de bestaande
    manier om een project van status te wisselen (dropdown/knop) voor toegankelijkheid — slepen is
    een versnelling, geen vervanging van de enige manier.
2c. Checklist-klik-patroon: klikken op een item toont het effect meteen (vinkje, doorhaling,
    voortgangsbalk), zonder page-reload. De onderliggende opslag (huidige checklist-mechaniek) blijft
    ongewijzigd — dit raakt alleen hoe snel je het ziet, niet wat er wordt opgeslagen.
3c. Rol-status-icoon (1a) is puur visueel, geen eigen patroon nodig — geen klikgedrag, alleen
    weergave van bestaande bezet/vacant-data.

Volgorde van bouwen, laagste risico eerst: 3a/3b (kanaal-ongelezen, puur leeswerk op al bestaande
lees-tijdstippen) → 1a (rol-icoon, puur leeswerk op bestaande rol-bemanningsdata) → 1b/2a
(projectkaart-voorkant + progress-atoom, leeswerk op bestaande projectvelden) → 2b/2c
(checklist-interactie) → 1c (sleep-patroon, het meeste JS-werk en het enige met een echte
statuswijziging als gevolg, dus als laatste en met de meeste testaandacht).

Testdiscipline zoals gebruikelijk: 3-5 structurele tests per atoom/molecule/pattern-laag apart,
volledige suite voor/na elke laag, diff, commit per laag, rapporteer voor je doorgaat naar de
volgende laag. Voor laag 3 (patterns) specifiek: een test die bevestigt dat slepen en de bestaande
dropdown-methode tot dezelfde statuswijziging leiden (geen tweede, afwijkend pad naar dezelfde
status).
```

## Fase 11, verduidelijking op de reikwijdte: staande regel in CLAUDE.md, niet alleen deze fase (20 sept)

Stefans vraag, letterlijk: pak je dit (atoms/molecules/patterns) nu echt voor alles aan, of alleen
voor de schermen die in fase 11 besproken zijn — "dit is het principe dat op infrastructuur voor
alles moet gelden."

Terecht onderscheid. Zoals Fase 11 hierboven is opgeschreven, is het een instructie die deze ene
batch werk (bord, checklist, kanalen, org-icoon, sleep-patroon) in drie lagen structureert. Het
is geen regel die vanzelf ook geldt voor het eerstvolgende scherm dat na deze fase gebouwd wordt —
daarvoor moet het niet in de implementatiebrief staan (die is per-fase), maar in `CLAUDE.md`, het
bestand dat Claude Code al als staande, verplichte regels leest (zo staat bijvoorbeeld de
AUTHZ-labelplicht en de "geen inline style"-regel er al in, onder "UI — designsysteem (HARDE REGEL)").

`CLAUDE.md` bevat die sectie al, met exact dezelfde onderliggende gedachte (hergebruik bestaande
klassen, "reference, don't invent", geen ad-hoc CSS) — alleen benoemt die sectie nog niet expliciet
de gelaagdheid atoms → molecules → patterns als bouwvolgorde voor élke nieuwe UI. Voorstel: één
nieuwe HARDE REGEL-bullet aan die sectie toevoegen, in dezelfde toon en structuur als de bestaande
bullets, zodat de regel automatisch voor al het toekomstige UI-werk geldt, ook zonder dat iedere
fase het opnieuw hoeft te specificeren. Akkoord van Stefan verondersteld op basis van zijn vraag;
onderstaande paste-back voegt de regel toe en laat Claude Code 'm zelf plaatsen en committen (net
als elke andere wijziging aan `CLAUDE.md` hoort dat via Claude Code te lopen, niet via een externe
edit buiten zijn eigen werkstroom om).

```
Voeg aan CLAUDE.md, in de sectie "## UI — designsysteem (HARDE REGEL)", een nieuwe bullet toe
(na de bestaande bullets, vóór de "## Autorisatie"-sectie eronder):

**Atomair opbouwen: atoms → molecules → patterns (HARDE REGEL).** Nieuwe UI wordt nooit in één stap
als kant-en-klaar scherm gebouwd. Eerst de atomen (bestaande, of na expliciet besluit nieuwe
basisklassen: knop, badge, status-vorm, voortgangsbalkje), dan de moleculen (samengestelde
onderdelen die atomen combineren: een kaart, een rij, een filterbalk), dan pas het patroon (het
scherm of de interactie die de moleculen inzet: een sleepbaar bord, een checklist met live
voortgang, een kanalenlijst met ongelezen-indicator). Dit geldt voor élke nieuwe UI-scope, niet
alleen voor scopes die dit expliciet benoemen — het is dezelfde discipline als de CSS-opruiming
van fase 6/9 en staat hier generiek, niet per fase. Terugkoppeling op een UI-scope benoemt daarom
expliciet welke laag (atom/molecule/pattern) elk gebouwd stuk is, net zoals de pariteitstabel-regel
hierboven dat al voor prototype-scopes eist. Reden: zonder deze laagscheiding ontstaat opnieuw het
probleem dat de CSS-opruiming al één keer moest oplossen — ad-hoc, niet-herbruikbare UI-stukjes die
elders straks weer opnieuw worden uitgevonden.

Commit deze wijziging apart (alleen CLAUDE.md, geen codewijziging erbij), met een duidelijke
commit message, en bevestig kort dat 'm geplaatst is — geen verdere actie nodig, dit raakt geen
tests.
```

## Fase 11, terugwerkende kracht: geen retrofit, zelfde ratchet als de inline-style-regel (20 sept)

Stefans vraag: geldt dit voor al het toekomstige, of moeten bestaande schermen er ook met
terugwerkende kracht aan voldoen?

Nee, geen losse retrofit-actie. `CLAUDE.md` heeft dit precedent al, voor exact dezelfde soort
regel: de "geen inline style"-guard (`tests/test_ui_no_inline_style.py`) telt per view en verlangt
een **monotone daling**, geen big-bang-opruiming — "ruim je schuld op bij een view die je toch
aanraakt." Zelfde redenering hier: bestaande schermen werken; ze in één aparte beurt omzetten naar
atoms/molecules/patterns voegt risico toe zonder dat er een bug wordt opgelost, en concurreert om
Claude Code's tijd met fases die dat wél doen (Fase 11 zelf, de NotifStore-vereenvoudiging). De
HARDE REGEL-bullet is daarom aangevuld met dezelfde ratchet-clausule als de inline-style-regel.

Eén aanvulling om de schuld niet onzichtbaar te laten worden (dat is precies waarom de inline-style-
regel wél een teller heeft): een kort, read-only inventarisatieverzoek aan Claude Code, geen
bouwwerk — welke bestaande views bevatten ad-hoc CSS/dubbele component-logica die niet uit atomen
is opgebouwd. Dat geeft zicht op waar de schuld zit, zonder dat er nu iets aan gerepareerd hoeft te
worden.

```
Twee dingen op de HARDE REGEL die je zojuist aan CLAUDE.md hebt toegevoegd (atoms → molecules →
patterns), of gaat toevoegen als dat nog niet gebeurd is:

1. Voeg aan het einde van die bullet deze zin toe:
   "**Geen big-bang-retrofit:** bestaande schermen die dit patroon nog niet volgen, blijven zoals
   ze zijn totdat je er toch aan werkt voor iets anders — dan neem je 'm mee. Zelfde ratchet-
   principe als de inline-style-regel hierboven: monotone daling, geen losse opruimronde."
   (Eén commit, alleen CLAUDE.md.)

2. Los daarvan, geen CLAUDE.md-wijziging: maak een korte, read-only inventarisatie (geen bouwwerk,
   geen commit nodig aan productiecode) van bestaande views die dit patroon nog niet volgen — ad-hoc
   CSS-blokken, gedupliceerde kaart/rij-opbouw die niet uit bestaande atomen komt. Rapporteer de
   lijst terug (view-naam + korte reden), zodat zichtbaar is waar de schuld zit. Geen prioritering
   of fix nodig, puur zicht erop.
```

## Fase 10, A+B1 live, droogloop schoon, spanning_ontstaat met pensioen (20 sept)

**A+B1 staat live op prod** (`8ecf29a`), health-check 303, beide services actief, geen fouten.
Backup vooraf: `backups/data_2026-09-20_0945.tgz` (100 MB, 2.070 bestanden).

**Droogloop, cijfers kloppen**: 371 in, 371 verwerkt, 0 geparkeerd, 41 DM-kanalen. Routering:
vervuller 308, persoon 33, terugval 30 (= 19 zonder levende vervuller + 11 geparkeerde-met-
meerdere-vervullers, precies zoals besloten). Grootste ontvangers: Stefan 351, Lotte 14, Matthijs 5,
Wytse 1. Geen `--apply` gedraaid, wacht op Stefans expliciete go.

**spanning_ontstaat met pensioen, geen nieuwe lezer.** De poort deed twee dingen, en Claude Code
vond terecht dat allebei hun lezer kwijt zijn: typeren (las door de oude inbox-routering/-filtering,
die niet meer bestaat nu alles één plat DM-kanaal is, geen buckets meer om te vullen) en herschrijven
(las door `views/inbox.py::_regel`, ook weg). Herschrijven kan bovendien sowieso niet blijven
bestaan: hij mag niet op `MENS_GETYPT` draaien, terwijl in een DM-laag vrijwel alles mens-tekst is —
hem laten voortbestaan zou zijn eigen regel breken. Geen van beide dus nieuw bedraden voor de sier;
retire, zoals Claude Code zelf al voorstelde als optie ("de poort met pensioen").

**"Waar zie ik dat het bij mij ligt" — geen nieuw mechanisme, dit is al Fase 11 punt 3a/3b.** Zonder
inbox geen los getal meer. Maar dat probleem is al herkend en al gescoped: de kanaal-ongelezen-
indicator uit Fase 11 (vetgedrukte kanaalnaam + stipje/telling op `.msg-kanaal`, al de eerste stap in
de bouwvolgorde) is precies dit, generiek voor elk DM-kanaal inclusief de nieuwe signaal-kanalen.
Geen los "vraag aan jou"/"melding"-label bouwen — dat zou een tweede, aparte manier zijn om hetzelfde
te laten zien naast wat al gepland stond. Claude Code's eigen voorkeur (hergebruiken wat er al is)
komt hiermee exact overeen met Fase 11.

## Fase 10, live gebruik legt vier dingen bloot vóór de --apply-bevestiging (20 sept)

Stefan gebruikte de live omgeving (na A+B1, nog vóór de `--apply` van de notif-migratie) en meldde
vier dingen, los van elkaar:

1. **`/inbox` staat er nog.** Precies wat eerder vandaag al voorspeld werd ("zolang de route bestaat,
   blijft hij de default"): de route/het scherm is nooit verwijderd, alleen het schrijfpad erachter
   is omgebouwd. Nu alles een plain DM is, dupliceert `/inbox` Messages zonder eigen functie.
   **Besluit: `/inbox` (route + navigatie-item) helemaal weghalen.**
2. **Project-kanalen zijn automatisch voor élk project, moet alleen voor actieve.** Sluit direct aan
   bij de eerder gevonden schaal (442 niet-gearchiveerde project-kanalen). Aanname, direct benoemd:
   "actief" = dezelfde status als de Active-kolom op het Projects-bord. Niet-actieve projecten
   (Waiting/Done/Future/Archived) verliezen hun kanaal niet (berichten blijven bestaan, niets
   verwijderen), maar het kanaal verdwijnt uit de standaard kanalenlijst — alleen zichtbaar via
   zoeken/een archief-filter. Wordt een project weer actief, dan komt het kanaal gewoon terug in de
   lijst. Puur een presentatiefilter op bestaande status, geen nieuw datamodel.
3. **Bug, waarschijnlijk urgent: DM's staan niet in de kanalenlijst.** Het links-scrollen/rechts-
   lezen-patroon (kanalenlijst links, gesprek rechts) bestaat al, maar toont kennelijk geen
   persoon-kanalen. Dat is een probleem los van punt 1/2: de 371 zojuist gemigreerde berichten landen
   grotendeels in DM's (Stefan 351, Lotte 14, Matthijs 5, Wytse 1) — als DM's niet in de lijst
   verschijnen, is die hele migratie na `--apply` onzichtbaar in de UI. **Dit blokkeert niet de
   `--apply` zelf (dat is puur een schrijfactie), maar wel de mogelijkheid om het resultaat visueel
   te controleren.** Aanbeveling: eerst dit fixen, dan pas `--apply`, zodat er meteen gecontroleerd
   kan worden — maar dat is Stefans afweging, niet de mijne.
4. **Project-scherm "een beetje een rommeltje".** Te vaag om nu te scopen. Sluit vermoedelijk aan bij
   wat al bekend is: `projects.py` stond al in de atoom-schuld-inventarisatie (37% privé-klassen,
   grootste ad-hoc families `einddoc-`, `att-`, `rail-`) en de projectkaart-voorkant staat al gepland
   in Fase 11 (laag 2, punt 1b). Gevraagd: een screenshot of concreter voorbeeld voordat dit een
   eigen instructie wordt, anders is "rommelig" niet uitvoerbaar voor Claude Code.

## Fase 10, bevestiging punt 2/3 en vier nieuwe dingen vanuit de projectdetailpagina (20 sept)

**Punt 2 (kanalen alleen voor actieve projecten) en punt 3 (DM-bug, urgent) bevestigd: akkoord,
fixen.**

Vanuit een screenshot van de live projectdetailpagina (`village.nooch.earth/project`), vier nieuwe
dingen:

1. **De "pakket"-koppeling is één grote platte pulldown van alle gerelateerde projecten — werkt
   niet.** Moet een cascade worden: eerst rol kiezen, dan pas de projecten van die rol. Dit is
   dezelfde onderliggende schaal (442 projecten) die vandaag al drie keer eerder opdook (kanalenlijst,
   org-boom, projectkaart). **Bouw dit als herbruikbare rol-eerst-projectkiezer (molecule, conform de
   nieuwe HARDE REGEL van vandaag), niet als losse fix voor alleen dit ene veld** — dezelfde
   "kies-uit-alles-platte-lijst"-fout zal elders terugkomen zolang er geen gedeeld patroon voor is.
2. **Berichten verwijderen en inline bewerken, ook op de projectpagina.** De "Conversation"-sectie
   hier is hetzelfde onderliggende kanaal-type als in Messages (project-kanaal, één van de drie
   smaken) — wat er voor Messages gebouwd wordt (verwijderen, inline bewerken) geldt dus automatisch
   ook hier, geen aparte implementatie nodig.
3. **"Keep in wiki" communiceert zijn eigen scope niet.** Onduidelijk of het de bijlage, de checklist,
   het hele project of alleen het bericht eronder bewaart. Kleine, concrete UX-fix: de knop moet
   zeggen wát hij bewaart (bijv. "Keep bericht in wiki" in plaats van kaal "Keep in wiki"), of de
   scope moet zichtbaar worden vóór het klikken.
4. **Grotere reflectie, nog niet scopen als losse instructie**: Stefan overweegt of de wiki niet
   andersom zou moeten werken — niet content vanuit projecten/berichten náár de wiki pushen
   ("Keep in wiki"-knoppen overal), maar vanuit de wiki content uit projecten/berichten trekken
   (pull). Dit raakt rechtstreeks bevinding 5 uit `ux_voorstel_best_practices_20sept.md`
   (Obsidian-backlinks, "kennis is een netwerk, geen hiërarchische mapstructuur") en is een
   architectuurvraag die de relatie tussen Wiki/Projects/Messages omdraait, geen kleine tweak.
   Bewust niet in dezelfde beurt gescoped als 1-3: dit verdient een eigen, aparte scoping-ronde
   (net als het cirkel-diagram destijds), niet blind meegenomen worden in de losse fixes hierboven.

**Bevestigd (20 sept): punt 4 (wiki pull-in-plaats-van-push) wordt apart opgepakt**, los van deze
fase-10-opruimronde. Staat hier alleen genoteerd zodat het niet zoekraakt — geen instructie, geen
scope, tot Stefan er zelf aan toe is.

## Fase 10, B2 gestart en weer geparkeerd: geen nette knip, één aaneengesloten beurt nodig (20 sept)

**Akkoord op beide.** B2 is begonnen (laatste twee `.notif.add`-plekken om, `_act_verzoek_besluit`
eruit, acht beslis-tests weg, drie routeringstests omgezet naar DM), maar Claude Code stopte terecht:
geen knip bestaat waarbij een tussenstap op zichzelf groen is. Acht overgebleven falende tests horen
allemaal bij dingen die pas in dezelfde beurt verdwijnen (de herschrijf-poort, MENS_GETYPT, de
triage-band van het inbox-scherm, `notif_outcome`). Werk staat veilig in stash `B2-wip`, niets kwijt.

**Een echte bug gevonden én al gefixt**: het pagina-voorstel verloor zijn inhoud onderweg naar de DM
— de voorgestelde tekst zat in `extra["pagina"]["body"]`, dat alleen het (verdwijnende) inbox-scherm
uitklapte. Zonder tekst en permalink kan de rolvervuller de pagina niet zelf aanpassen, en dat was
nou net de hele afspraak van vandaag (mens beslist, mens past zelf aan). Terecht gevonden door te
kijken naar wat de mens daadwerkelijk ontvangt, niet naar de code — precies de manier waarop de
gast-zonder-ontvanger-bug eerder vandaag ook werd gevonden.

**Akkoord op het voorstel: B2 als eigen, aaneengesloten beurt**, de suite als leidraad, de poort
(`bevinding.py`, `zelf_verwerking.py`, `spanning_ontstaat.py`) als laatste stap zodat een fout in de
omzetting niet in dezelfde commit zit als de dode-code-opruiming. `views/inbox.py` (1.182 regels)
gaat hiermee ook weg — dit is dus de uitvoering van de eerder vandaag afgesproken `/inbox`-
verwijdering, geen aparte instructie nodig. Let op de genoemde afhankelijkheid: `_at_doelen` moet
naar `checklists.py` verhuizen vóór `inbox.py` weg mag, anders breekt de checklist-functionaliteit.
Prod blijft ondertussen ongewijzigd op `8ecf29a` met de 371 gemigreerde berichten.

## Fase 10, B2 eerste helft groen (20 sept, commit `5c9fdec`): inbox weg, twee bugs blootgelegd

**Status**: 3.984 passed, 1 failed (de al bekende), 1 xfailed. **Niet gedeployed** — prod draait nog
op `8ecf29a`.

**Wat eruit is**: `views/inbox.py` (1.182 regels), de routes `/inbox` en `/inbox/verwerk` (nu 404),
de lade uit de zijbalk-chrome, vier dispatch-acties en `_act_verzoek_besluit` (113 regels). `.notif.add`
komt nergens meer voor — de laatste twee schrijfplekken zijn nu ook gewone DM's. `_at_doelen` is
verhuisd naar `cockpit2_util` (waar `_rol_labels` al stond) vóórdat `inbox.py` weg mocht, precies de
afhankelijkheid die hierboven al was genoteerd.

**Twee dingen die dit blootlegde**:
1. Het pagina-voorstel verloor zijn inhoud onderweg naar de DM (de voorgestelde tekst zat in
   `extra["pagina"]["body"]`, dat alleen het verdwijnende inbox-scherm uitklapte) — **al gefixt**,
   zie de vorige sectie hierboven; nu bevestigd in de groene stand.
2. **Nieuw gevonden, via een omvallende test**: `cockpit2.mens_vervullers` en `signaal.mensen_van`
   deden hetzelfde. De eerste delegeert nu naar de tweede, anders kon een scherm een andere
   rolvervuller tonen dan het bericht dat er daadwerkelijk heen gaat — een stille inconsistentie die
   pas opvalt als het misgaat.

**Tests**: zes bestanden volledig verwijderd (gingen alleen over het scherm), plus 21 losse tests uit
acht andere bestanden, elk met de reden in het bestand zelf genoteerd. Routeringstests zijn niet
verwijderd maar omgezet naar DM-asserties — die bewaken wie het werk krijgt, en dat is ongewijzigd.
Onderweg: een eerste verwijder-script knipte op "tot de volgende `def`" en at zo een helper-klasse op
in `test_zichtbaarheid_bord_en_inbox.py` (99 regels weg, 45 tests stuk) — teruggedraaid en opnieuw
gedaan op inspringing. Zes ratchets zijn meegezakt, waaronder `_PREFIX_CEILING` 65 → 64.

**Nog open (tweede helft B2)**: NotifStore zelf en de poort. Nog zo'n vijftien call-sites verspreid
over `cli.py`, `cockpit2` (het "maak er een project van"-pad dat uit de inbox kwam),
`views/metrics.py` (een metriek over verwerkingen), `claims_board`, `human_inbox`, `inhabitant`,
`puls_wacht`, `roles`, `escaleer`, `triage_rol`, `villageraad`, `wiki` en `views/vangst`. Daarna de
drie poort-modules (`bevinding.py`, `zelf_verwerking.py`, `spanning_ontstaat.py`) als laatste stap.

**Zichtbaarheidspunt voor bij de deploy-beslissing (nog niet beantwoord)**: zodra dit live gaat is de
lade in de zijbalk weg en geeft `/inbox` 404 voor iedereen die inlogt. De 371 gemigreerde berichten
staan op `/messages`, maar wie gewend was aan de lade met een getal erop vindt die niet meer terug —
en de vervangende ongelezen-indicator (kanaalnaam vetgedrukt + stip/aantal) zit in fase 11, nog niet
gebouwd. Dit hoeft nu geen besluit te zijn (B2 is niet af, er wordt niets gedeployed), maar moet wel
worden meegewogen zodra de A+B1+B2-deploy in beeld komt: in één keer live met die tijdelijke leemte,
of wachten tot fase 11's ongelezen-indicator er ook is.

## Messages-prototype gebouwd (20 sept) — reageren op berichtacties en navigatie-inpassing

Op Stefans verzoek ("prototype van messages in html met alle functionaliteit: bericht plaatsen,
reageren, dm sturen, kanaal starten, kanaal vinden") is een interactief HTML-prototype gepubliceerd
als eigen Artifact (Design-canvas), los van de repo — dit is verkenning voor de nog te plannen
Messages-scoping-ronde, geen bouwinstructie voor Claude Code.

**Drie artboards**:
1. **Main** — het volledige, interactieve Messages-scherm: kanalenlijst links (Projecten/Cirkels/
   Topics/Directe berichten/Signalen, met live zoeken en een archief-schakelaar voor niet-actieve
   projecten), gesprek rechts. Alle vijf gevraagde acties werken: bericht plaatsen, reageren
   (emoji-toggle met teller), DM sturen (incl. een collega zonder bestaand gesprek, om een DM vanaf
   nul te tonen), kanaal starten (naam + type), kanaal vinden. Rollen als compliance/harry_hemp/
   librarian/claims-checker staan niet als losse "personen" maar gebundeld in één Signalen-kanaal met
   per bericht een herkomst-label ("via compliance") — de concrete uitwerking van "DM moet naar een
   mens, niet naar een rol".
2. **InContext** — hoe dit past náást de bestaande NoochVille-navigatie (zie vraag hieronder).
3. **Mobile** — hoe dit werkt op een telefoonformaat (zie vraag hieronder).

**Bericht-acties, na Stefans "ik mis nog een bericht verwijderen of editten" (20 sept)**: het
prototype maakte in de eerste versie alleen eigen berichten bewerkbaar/verwijderbaar (Slack-stijl,
zoals besproken voor de projectpagina). Berichten van anderen — inclusief Signalen — hadden nog geen
enkele actie, en dat viel op als een gat. **Aangescherpt naar twee aparte acties, conform het eerder
vandaag genomen besluit over vinken/verwijderen**:
- **Eigen berichten** (elk kanaal): potlood = inline bewerken, prullenbak = verwijderen. Dit is
  klassieke chat-bewerking van je eigen tekst.
- **Signalen-berichten** (van "Systeem", niet van jou): een vinkje = markeer als verwerkt (dimt het
  bericht, puur visueel, geen backend-effect — conform het eerdere besluit voor plain DM's) en een
  prullenbak = verwijder 'm uit je overzicht.
- **Berichten van collega's in een gedeeld kanaal** (DM/project/cirkel/topic): bewust géén bewerk-
  of verwijderknop — dat zou andermans deel van een gedeeld gesprek aantasten. Alleen reageren kan
  daar, wat al werkte. Dit onderscheid stond nog nergens expliciet vastgelegd; nu wel, voor als de
  vraag terugkomt waarom niet elk bericht dezelfde knoppen heeft.

**Navigatie-inpassing, naar aanleiding van Stefans vraag "hoe past dit in de hele interface, want er
is ook nog een linkerkant-navigatie, klapt dit uit of past het naast elkaar, en hoe dan mobiel?"**
(20 sept) — dit was in het eerste prototype niet beantwoord, het toonde Messages losstaand, alsof het
het hele scherm is. Twee nieuwe artboards geven een concreet voorstel, nog niet bevestigd door
Stefan:
- **Desktop (InContext)**: de bestaande globale zijbalk (logo, zoeken, Projects/Messages/Wiki/Circle/
  Admin, org-boom) klapt in tot een smalle icoon-rail (64px) zodra je in een module zit die zelf een
  lijst-paneel nodig heeft, zoals Messages. Dat maakt ruimte voor Messages' eigen twee panelen
  (kanalenlijst + gesprek) ernaast — drie kolommen naast elkaar past ruim binnen een normaal
  schermbreedte. De org-boom verdwijnt niet, maar zit achter een klein icoon (flyout on klik), want
  je hebt 'm niet nodig terwijl je aan het chatten bent.
- **Mobiel (Mobile)**: geen drie kolommen naast elkaar, maar **drill-down**, het standaardpatroon
  van Slack/vergelijkbare apps. Drie niveaus, elk vol scherm: (1) de globale navigatie zit achter een
  hamburger-menu dat als overlay opent, (2) de kanalenlijst is het standaardscherm van Messages, (3)
  tikken op een kanaal opent het gesprek vol scherm met een terug-pijl linksboven die je terugbrengt
  naar de kanalenlijst.

**Nog niet bevestigd door Stefan**: of dit voorstel (rail-inklap op desktop, drill-down op mobiel)
het uitgangspunt wordt voor de Messages-scoping-ronde, of dat hij een andere richting wil.

## Fase 10, B2 tweede helft: de echte poort gevonden, villageraad en waarde_audit uitgezocht (20 sept)

**Naamscorrectie eerst**: "village poort" bleek niet `triage_rol.py` maar `tensie_poort.py` (513
regels). `triage_rol.py` (413 regels) heeft nul notif-verwijzingen en vier levende aanroepers
(`materiaal_memo.py`, `cockpit2.py`, twee testbestanden) — terecht ongemoeid gelaten, dit was nooit
in scope. `tensie_poort.py` is wél weggehaald, samen met `relaunch_park.py` (dit was "rp.park" uit de
eerdere lijst) + zijn CLI-tak, `spanning_ontstaat.py`, en beide bijbehorende testbestanden.

Drie stukjes uit `tensie_poort.py` gingen nooit over de inbox en zijn verhuisd in plaats van
verwijderd: `kern()` (deterministische sjabloon-swap, gebruikt door `bevinding` én `zelf_verwerking`)
naar `systeemtaal.py`; `match()` (het oordeel "wie bezit dit werk") naar `escalation_router.py`, waar
`roster`/`_vraag_llm`/`kies_ontvanger` al wonen; `_VRAAGT_BESLUIT`/`_GEEN_BEWIJS`/`_BESLUIT_DOMEIN`
naar `zelf_verwerking.py`, waarvan `founder_behoefte` de enige lezer is. Twee guards uit
`test_tensie_poort.py` zijn meeverhuisd, de bewijsgrens staat nu op `founder_behoefte` (die zelf nog
geen test had).

**Drie ratchets zijn verbreed in plaats van ingekort**, omdat hun onderwerp verdween: de
caller-cap-test leest nu een AST-scan op de verzendfuncties (`stuur`/`stuur_op_pad`/`_signaleer`/
`post`, 24 call-sites) in plaats van een veld dat niet meer bestaat; de statusvocabulaire-test
verbood niet langer één specifiek label maar controleert nu dat geen enkel bestand buiten
`projects.py` een eigen statuslijst uitschrijft (vond meteen `web_base._STATUS_VORM`, die een eigen
compleetheidstest kreeg); de volle-tekst-test toetst nu `ChannelStore.post`/preview in plaats van het
verdwenen `NotifStore.add`, met drie eerder weggevallen store-onafhankelijke tests terug. Ook een
losstaande, niet aan deze opruiming gerelateerde ordeningsbug in `test_scope58` is en passant
gefixt.

**Villageraad (606 regels)**: bevestigd dood. Geen crontab, geen systemd-timer, geen route, geen
daemon-aanroep, alleen het handmatige `village villageraad`-commando. Laatste output
`villageraad_2026-08-26.md`/`.jsonl`, niets sindsdien. De premisse is ook verlopen: op prod heeft van
de 18 rollen er nog maar 1 een AI-vervuller (noochie), de rest is mens-vervuld — "de AI-raad die zelf
spanningen opwerpt" bestaat feitelijk niet meer. Dit bevestigt exact wat Stefan zelf al zei
("villageraad bestaat niet meer want de AI zijn weg"). **Besluit: verwijderen.** Enige complicatie:
`waarde_audit.py:335` importeert `labels`/`rollen` uit villageraad — die twee helpers verhuizen eerst
naar `waarde_audit.py` (of een klein gedeeld hulpbestand), dan pas gaat `villageraad.py` weg.
`villageraad.jsonl` blijft liggen als archief, net als `notifications.json`.

**Waarde_audit (752 regels)**: dit beantwoordde Stefans vraag "wat is dit?" — geen vergeten hoekje,
maar de actieve bron van waarheid voor `village afslanken` (rollen slapend leggen, skills intrekken),
met een expliciete foutmelding als het ontbreekt (`cli.py:972`). Meet per rol/skill vier signalen die
een mens echt raakten: project afgerond met outcome, pagina door een mens bewerkt, besluit genomen,
certificaat gebankt. **Besluit: blijft ongewijzigd staan**, geen actie in B2. Wel een bevinding zonder
voorgestelde fix: het signaal `besluit_genomen` komt uit `notifications.json`, een store die is
opgeheven — het bestand blijft als archief maar krijgt geen nieuwe rijen meer, dus dat signaal telt
vanaf nu alleen nog wat er vóór de opruiming gebeurde. Claude Code heeft dit als waarneming in de
moduledocstring gezet en bewust niets opgelost; wie dit signaal weer wil laten meetellen heeft een
nieuwe bron nodig (bijv. een uitkomst op de DM zelf), geen mechanische telling.

**Nog open bij Stefan, geen codebeslissing**: beide laatste audit-outputs (villageraad 26 aug,
waarde_audit 28 aug) zijn bijna een maand oud. Hoorde iemand `village waarde_audit`/`village
villageraad` periodiek te draaien, en is dat blijven liggen of bewust gepauzeerd? Relevant nu bekend
is dat `afslanken` middenin op waarde_audit leunt.

Met deze twee besluiten kan B2 zich afronden: villageraad-helpers verhuizen, `villageraad.py` weg,
volledige suite draaien, dan rapporteren als af. Nog steeds geen deploy.

## Fase 10, B2 compleet (20 sept): volle suite groen, geen deploy

**Status**: 3.868 passed, 1 xfailed, 0 failed. Twee commits: `444746a` (tweede helft + de poort) en
`8530b3c` (villageraad). Nog steeds niet gedeployed.

**Villageraad-helpers**: `rollen()`/`labels()`/`_naam()` bleken twee lezers te hebben buiten de raad
(`waarde_audit.rollen_regels`, `views/vangst.rol_namen`), dus zijn ze niet naar `waarde_audit.py`
verhuisd zoals eerder voorgesteld, maar naar `org.py`: `villageraad.rollen()` → `org.levende_rollen()`,
`villageraad.labels()` → `org.unieke_namen()`, `villageraad._naam()` → `org.naam_van()`. Terechte
keuze: dit is een vraag over de org-boom, niet over een council-pass. Onderweg een echte bug gevonden
en gefixt: `unieke_namen()` heeft de volle recordlijst nodig als tweede argument, niet alleen de
rollenlijst, want de ouder van een rol is een cirkel en cirkels zitten niet in de rollen-only lijst.
Met alleen de rollen viel de ontdubbeling van meerdere Circle Leads stil weg, zonder fout of log,
precies het soort stille bug dat deze hele opruimronde blijft blootleggen.

**Weg**: `villageraad.py` (606 regels), `tests/test_villageraad.py`, de CLI-tak. `villageraad.jsonl`
blijft als archief liggen (waarde_audit leest het nog), met een aangepaste bronregel
("villageraad (archief)") zodat niemand denkt dat het getal nog groeit. `waarde_audit.py` is verder
ongewijzigd gebleven, zoals besloten; de aantekening over het bevroren `besluit_genomen`-signaal staat
er als waarneming.

**B2 in totaal, alle verdwenen modules**: `notifications.py`, `views/inbox.py`, `notif_migratie.py`,
`notif_opruiming.py`, `spanning_ontstaat.py`, `tensie_poort.py`, `relaunch_park.py`, `villageraad.py`.
Gered en verhuisd in plaats van gesneuveld: preview/volledig → `tekstpreview.py`, `kern()` →
`systeemtaal.py`, `match()` → `escalation_router.py`, de drie founder-domeinpatronen →
`zelf_verwerking.py`, rollen/labels → `org.py`. Netto: `nooch_village/` van 72.621 naar 69.160 regels
(−3.461), `tests/` van 59.489 naar 56.692 (−2.797), gemeten tussen `6cc9470` (vóór B2) en `8530b3c`
(nu).

**Nog open, geen actie genomen**: het zichtbaarheidspunt voor de A+B1+B2-deploy (lade weg, `/inbox`
404, ongelezen-indicator pas in fase 11) — ligt bij Stefan; Admin·Skills-schrijfbaarheid (open sinds
fase 7); fase 11 (UX-microinteracties), aangekondigd maar niet gestart; de 63 kleur-alleen-statussen
buiten de negentien schermen; `Pillow` in `requirements.txt` heeft geen gebruiker meer sinds de
EPIC-globe weg is (dezelfde al eerder genoteerde open dependency-schrap).

**Belangrijk voor het vervolg**: Stefan heeft, terwijl B2 nog liep, een veel grotere richtingvraag
geopperd (zie sectie hieronder) — "helemaal anders opbouwen, veel meer menselijk werk en beslissingen
first, AI veel gerichter inzetten dan nu." `waarde_audit`/`afslanken` (het mechaniek dat op basis van
vier automatisch gemeten signalen rollen slapend legt en skills intrekt, zonder mensbeslissing
ertussen) is precies het soort automatisme dat tegen die visie zou kunnen ingaan. B2 is afgerond
zonder dat mechaniek aan te raken, dus dat gesprek staat nog volledig open en is niet stilzwijgend
opgelost door deze fase.

## Richtingvraag van Stefan, opgehelderd (20 sept): "AI is instrument, geen rol"

Tijdens de B2-afronding zei Stefan, in reactie op de villageraad/waarde_audit-paste-back: "nee die
kunnen weg, ik ga helemaal anders opbouwen veel meer menselijk werk en beslissingen first en veel
gerichter AI inzetten dan wa we nu doen." Dit kwam vóórdat Claude Code's B2-voltooiing binnenkwam, en
is dus niet meegenomen in de B2-uitvoering. Twee verhelderingsvragen zijn gesteld en beantwoord:

**Antwoord**: AI-rollen bestaan niet meer, met **Noochie als enige, bewust genoemde uitzondering**
(wordt langzaam opnieuw opgebouwd, geen precedent voor nieuwe AI-rollen). Omdat AI-rollen niet meer
bestaan, bestaat hun autonomie en beslissingsbevoegdheid ook niet meer. Mensen beoordelen; tools geven
inzicht in trends/cijfers, dat is een instrument, geen AI-rol.

**Concreet betekent dit**: `waarde_audit` past hier al in (het meet, het oordeelt niet, blijft dus
terecht ongewijzigd, geen conflict met dit principe). De aandachtspunten zijn de plekken waar een LLM
wél een organisatorisch effect heeft zonder mensbeslissing ertussen: mogelijk `village afslanken`
(rollen slapend leggen, skills intrekken, nog te checken of dat al mens-bevestigd gebeurt of
automatisch), `escalation_router.match()` ("wie bezit dit werk", nu deels LLM-oordeel) en
`zelf_verwerking`'s besluit-domeinen (`_VRAAGT_BESLUIT`/`_GEEN_BEWIJS`/`_BESLUIT_DOMEIN`).

**Besloten (20 sept)**: het principe wordt vastgelegd als nieuwe HARDE REGEL in `CLAUDE.md`
("AI is instrument, geen rol", met dezelfde geen-big-bang-retrofit-clausule als de andere twee
regels van vandaag), en Claude Code doet daarna een **read-only inventarisatie** (geen wijzigingen,
zelfde opzet als de atom-debt-lijst): welke plekken gebruiken een LLM voor een organisatorisch oordeel
met effect zonder mensbevestiging, met expliciete check op de drie genoemde kandidaten plus een
bredere grep (`_vraag_llm`, `anthropic`, `google-genai`/gemini). Nog geen besluit over wat er met de
gevonden plekken gebeurt, dat komt na de inventarisatie.

## Inventarisatie "AI is instrument": eerste vier kandidaten uitgezocht (20 sept)

De HARDE REGEL staat in `CLAUDE.md`, commit `4e12d43`, als eigen sectie direct vóór "Autorisatie —
elke nieuwe dispatch-tak". Claude Code's bredere sweep over de resterende 34 modules met een
LLM-aanroep loopt nog; onderstaand zijn de vier expliciet genoemde kandidaten uitgezocht en
beoordeeld tegen het nieuwe principe.

**`escalation_router.match()`** (regel 180): roept een LLM aan (via roster → `_vraag_llm` →
`kies_ontvanger`), fail-closed bij twijfel. Enige aanroeper is `zelf_verwerking.verwerk()`, op zijn
beurt alleen bereikbaar via `village zelf_verwerking` (CLI, mens start het, dry-run is de default,
`--live` nodig om `verwerkingen.jsonl` te schrijven). Effect van de uitkomst: **geen** — wordt alleen
als telling uitgelezen door `waarde_audit`. Compliant: mens start het, mens leest het, geen
automatisch organisatorisch gevolg. Bijvangst: `escalation_router.escaleer()`/`route_item()` hebben
nul productie-aanroepers meer, alleen een testbestand roept ze nog aan — dode code, meenemen in de
sweep-conclusies, geen aparte actie nu nodig.

**`escalation_router.naar_mens()`/`_mens_ontvanger()`** (regel 356/322): bepaalt wie een vastgelopen
stap krijgt toegewezen. Effect is **direct** — `route_werk()` levert meteen af, zonder bevestiging van
die specifieke keuze. Enige aanroeper: `vastgelopen_route.py`, via `village vastgelopen_route
[--apply]` (CLI, mens start het, dry-run is default, draait niet mee in de dagelijkse pulse). De
`--apply`-vlag beveiligt de hele batch, maar bevestigt nooit de individuele modelkeuze wie iets
krijgt. Dit is de scherpste van de vier gevallen en de enige die nog een open vraag heeft: toont het
dry-run-rapport per toewijzing de onderbouwing (herbeoordeelbaar), of alleen een kale naam
(afvink-risico)? Nog niet beantwoord door Claude Code.

**`zelf_verwerking`'s besluit-domeinen** (`_VRAAGT_BESLUIT`/`_GEEN_BEWIJS`/`_BESLUIT_DOMEIN`, via
`founder_behoefte()`): bevestigd **geen LLM**, pure regexes, deterministisch. Geen kwestie.

**`village afslanken`**: nul LLM-aanroepen in `afslanken.py` of `waarde_audit.py`, volledig
deterministisch. Twee expliciete mensdrempels: `--apply` voor schrijven, en
`AfhankelijkheidNietBevestigd`/`--afhankelijkheden-gelezen` vóór een rol slapend leggen of skill
intrekken. Volledig compliant, bevestigt de eerdere "blijft ongewijzigd"-conclusie nu met de
daadwerkelijke code erbij.

**Bijvangst, zelf gemeld door Claude Code**: `cockpit2.py:3455`'s `route_werk()` roept nog
`_rolsuggestie()` aan (LLM via `triage_rol.classificeer`), maar het resultaat wordt nergens meer
gebruikt — een weeskind van het weghalen van de `extra=`-parameter op `notif.add` eerder vandaag
tijdens B2. Geen principekwestie, wel een lopende, zinloze modelaanroep per lead-hop/routing-actie.
**Besloten**: dit meteen wegnemen, niet parkeren onder de geen-big-bang-retrofit-clausule — die
clausule is bedoeld voor statische structurele schuld die kan blijven liggen, niet voor een aanroep
die op dit moment nog steeds geld en latency kost bij elke uitvoering.

**Nog open**: het `vastgelopen_route`-vraagstuk hierboven, en de rest van de 34-modules-sweep.

## Inventarisatie "AI is instrument": volledige sweep binnen, plus de dry-run-vraag beantwoord (20 sept)

**De `vastgelopen_route`-vraag van hierboven**: het rapport is een halve kale lijst. Je ziet per
toewijzing wie het krijgt, niet waarom (welke rol/opdrachtgever, welk bewijs). De grond wordt wél per
item berekend (in `pas()`), maar `rapport()` print die sleutel nergens — hij verschijnt alleen
onderaan als telling over de hele batch. En juist de grootste groep binnen die telling ("deze rol
bezit dit werk", 14 van 18) is de minst informatieve: de bewering, niet het bewijs. Praktisch gevolg:
je kunt een foute toewijzing alleen zien als je zelf al weet dat iemand dit niet hoort te krijgen —
"de batch goedkeuren" is dus geen blinde stempel, maar ook geen echte beoordeling, het is een
steekproef op je eigen geheugen. Er is een oude testdocstring die dit letterlijk voorspelde ("een
droge loop die alleen telt laat de vraag onbeantwoord die het besluit draagt") — één stap is toen
opgelost (bestemming tonen), de volgende (de grond tonen) is blijven liggen.

**Herzien na Stefans reactie op het voorbeeld**: het voorbeeld uit het rapport ("Harry Hemp ...
Decide whether to permanently exclude this overlap → Lotte Mulder") noemt Harry Hemp als de rol waar
het werk vastliep. Stefan: "Harry Hemp kan geen bericht naar Lotte sturen, want Harry Hemp is
opgeruimd" — en herhaalt het eerder gestelde uitgangspunt: alles wat ergens blijft zweven, hoort als
DM in zíjn (de founder-)inbox te landen, waar hij het zelf opruimt, niet bij een door het model
gekozen andere rol of persoon.

Dat verandert de fix. Niet "toon de grond erbij" (transparantie over een AI-gekozen ontvanger), maar
de vraag of `_mens_ontvanger` überhaupt een ontvanger zou moeten kiezen — onder "AI is instrument,
geen rol" is de eenvoudigste, meest compliant vorm dat vastgelopen werk altijd naar de founder-inbox
gaat, zonder dat een model bepaalt wie de mens is die het oppakt. Twee dingen aan Claude Code:
1. **Data-vraag, eerst**: is "Harry Hemp" een echte rol uit de huidige data (org/roles), of een
   verzonnen voorbeeldnaam in het rapport? Als het een echte rol is die nog in de brondata van
   `vastgelopen_route`/`org.py` voorkomt terwijl rollen zijn opgeruimd, is dat een apart
   datalek-signaal (stale rollen die nog meedraaien in routering) — los van de ontwerpvraag hieronder.
2. **Ontwerpvraag**: verander `_mens_ontvanger()` zodat vastgelopen werk altijd naar Stefan (de
   founder) gaat, in plaats van een rol-eigenaar of "wie hoort dit werk" te laten kiezen door het
   model. Dat is geen transparantie-toevoeging maar het weghalen van een AI-organisatiekeuze — precies
   het soort wijziging die de HARDE REGEL beoogt. Nog niet doorvoeren zonder Stefans akkoord op de
   precieze vorm (bijvoorbeeld: gaat dit ten koste van gevallen waar een rol-eigenaar wél zinvol is,
   of is founder-inbox-altijd inderdaad de bedoeling voor élk vastgelopen geval?).

`sluitronde.py` heeft exact dezelfde vorm (panel stemt, `--apply` gate op batchniveau, kiest ook een
trekkende rol) — dezelfde twee vragen gelden daar net zo goed.

**Datavraag uitgezocht (20 sept)**: drie lagen. (1) De naam zelf was slordig gekozen door Claude Code:
`harry_hemp` is een echt record-id, maar de weergavenaam (wat `rapport()` print) is "Scientist" —
"Harry Hemp" had dus nooit in een echt rapport kunnen staan, dat was een test-bijnaam die abusievelijk
als voorbeeld diende. (2) Prod-staat geverifieerd: `harry_hemp` (Scientist) staat inderdaad op
`archived: true` (`data/governance_records.json`, 18 sept) — de rol is terecht opgeruimd. Claude Code
ving hier zelf een fout op onderweg: zijn eigen lokale snapshot (9 sept) zei nog `archived: false` en
had niet vertrouwd moeten worden. (3) Speelt een opgeruimde rol nog mee in de routering? Twee kanten:
als **ontvanger** nee, hard afgeschermd — `escalation_router.roster()` filtert archived/slapend eruit
vóórdat het model een kandidatenlijst ziet, met expliciete reden in het comment. Als **afzender**
(eigenaar van het vastgelopen project) wordt dit niet gecontroleerd — `pas()` kijkt alleen naar de
projectstatus, nooit naar de staat van de eigenaar. Verdedigbaar (werk vastgelopen bij een rol die niet
meer bestaat is precies wat je wilt herrouteren) maar impliciet, geen uitgesproken keuze. In de
praktijk vandaag: nul impact — van 41 blocked projects passeren er 3 de eerste guard, beide eigenaren
leven nog; `village vastgelopen_route` zou vandaag 9 stappen routeren, geen daarvan vanaf een
opgeruimde rol.

**Bijvangst**: 256 van de 442 projecten stonden op naam van een opgeruimde rol; de afslanking heeft er
254 correct gearchiveerd. Twee zijn blijven hangen (beide bij Compliance, zelf niet gearchiveerd, niet
blocked dus buiten bereik van `vastgelopen_route`) — precies waar `village afslank_wezen` voor is, het
commando dat Claude Code vanochtend al repareerde (crashte op de verwijderde notifications-import) en
alleen nog groen getest heeft, niet tegen prod gedraaid.

**`afslank_wezen` dry-run tegen prod (20 sept)**: gedraaid, niets geschreven. Uitkomst: **niet
toepassen**. `--apply` zou de twee Compliance-weesprojecten archiveren en herscheppen bij diezelfde
dode `compliance` — netto slechter dan niets doen (ze staan nu tenminste nog zichtbaar open). Oorzaak
gevonden: `cockpit2._circle_lead_van('compliance')` geeft `''` terug omdat de hele
noochville-subcirkel (incl. zijn Circle Lead) gearchiveerd is; de klim-functie stijgt één niveau en
stopt, in plaats van door te klimmen naar `mother_earth__nooch__circle_lead`, die wél leeft. Er
bestaat een levende `mother_earth__nooch__compliance`-rol (vervuller: Stefan) waar deze twee projecten
voor een mens evident naartoe horen — de code ziet alleen het dode, losse `compliance`-id.

## Ontwerpbeslissing: routering wordt geen modelvraag meer, voor beide A2-plekken (20 sept)

Claude Code's voorstel voor `_mens_ontvanger` (vastgelopen_route) en `sluitronde._panel`, beide met
dezelfde vorm (model kiest een adres, systeem levert er direct aan af, mens ziet de keuze niet):

1. **Haal de keuze weg, niet het model.** Vervang de modelkeuze door de bestaande, deterministische
   ladder die elk ander bericht in het dorp al gebruikt: `signaal.ontvangers` → vervuller → Circle
   Lead → terugval (founder). Getest tegen prod-data (`compliance`→terugval Stefan, `harry_hemp`→
   terugval Stefan, `financial_controller`→vervuller Stefan, `strategic_lead_founder_steward`→
   vervuller Stefan). Lost **passant** het Compliance-weesgeval hierboven op, want deze ladder heeft
   wél de founder-terugval die `cockpit2._circle_lead_van` mist — één implementatie in plaats van twee
   van dezelfde routeringsregel.
2. **Degradeer het modelantwoord tot tekst, niet adres.** `escalation_router.match()`'s
   grond-string (rol, kind, waarom) blijft nuttig als toegevoegde suggestie in het bericht zelf, niet
   als bestemming. Maakt de modelaanroep optioneel: geen krediet → bericht landt nog steeds bij de
   juiste mens via de ladder, alleen zonder suggestieregel. Nu is het omgekeerd — geen krediet
   verandert stilletjes de ontvanger.
3. **Toewijzen wordt een menselijke handeling met bestaande infrastructuur.** Fase 8's
   mention-routing (`@rolnaam` in een bericht landt bij de vervuller) is al de accepteer-knop: een
   mens antwoordt, het werk verhuist met een spoor. Geen nieuw scherm, geen nieuwe dispatch-tak.

Voor `sluitronde` dezelfde drie zetten, met één extra knip: die aanroep bevat nu twee besluiten
tegelijk (wie trekt de kans, én gaat de kans door). Het "wie" verdwijnt zoals hierboven. Het "of"
stopt met zelf schrijven: `--apply` betekent straks "schrijf het voorstel" in plaats van "voer de
uitkomst uit" — per kans één bericht met de stem van het panel, de redenering en de scope, de kans
blijft pending tot een mens hem afhandelt. Al het denkwerk van het panel blijft (de scope opstellen is
echt werk), alleen de zelfuitvoering verdwijnt.

**De ene echte keuze — Stefans besluit (20 sept)**: altijd naar Stefan direct, of via de ladder
(vervuller → Circle Lead → Stefan als terugval)? Claude Code adviseerde de ladder; Stefan kiest
expliciet **(a) altijd naar hemzelf**, met een principiële reden die verder gaat dan deze ene
routeringsvraag: "in principe zou AI geen spanningen meer moeten sensen, en ik wil eerst controle over
alles wat binnenkomt voordat ik het open zet voor de rest." Dat is een bewuste, voor nu geldende
overgangskeuze (het woord "eerst" laat ruimte om dit later te verruimen naar de ladder), niet een
correctie op de analyse — de kosten die Claude Code noemde (Stefan wordt het knooppunt) zijn gezien en
bewust geaccepteerd zolang hij zelf alles wil zien voordat het verder gaat.

Dit relativeert niet de eerste twee zetten hierboven (de modelkeuze verdwijnt, het modelantwoord wordt
hooguit een tekstsuggestie) — alleen de bestemming verandert van "de ladder" naar "altijd Stefan".

**Bredere implicatie, nog niet besloten, wel genoteerd**: Stefans "AI zou geen spanningen meer moeten
sensen" raakt direct `inhabitant._classify_llm`/`triage()` uit categorie A hierboven — precies het
mechanisme dat in de dagpuls autonoom bepaalt bij welke rol werk hoort (spanning-sensing/routering
zonder mens ertussen). Dat viel bewust buiten de scope van dit besluit (andere vorm, eigen besluit
nodig), maar Stefans principiële uitspraak wijst daar wel direct naartoe als volgende, waarschijnlijk
hoge-prioriteit kandidaat.

**Extra, in dezelfde ademtocht (20 sept)**: Stefan, eerlijk: "heel veel oude spanningen kunnen gewoon
weg, ik weet dat allemaal al." En op de vraag of hij eerst een inventaris wil zien voordat er iets
weg mag: nee — "er is eigenlijk niets in de history wat ik écht zou willen bewaren, als het belangrijk
is komt het wel terug als mens sensed spanning." Dat is dus geen "inventariseer en dan kies", maar een
generieke, voor het geheel geldende opruiminstructie: de bestaande AI-gesensde spanning-geschiedenis
heeft geen beschermwaarde, omdat een echt relevante spanning vanzelf terugkomt zodra een mens hem
signaleert.

**Besloten**: geen inhoudelijke review vooraf nodig. Wel, uit dezelfde discipline als bij villageraad
(waar `waarde_audit` een verborgen afhankelijkheid bleek te hebben): eerst kort checken of iets anders
in de codebase nog leest uit de spanning-store(s) vóór ze leeggemaakt worden, en de data archiveren
(zoals `villageraad.jsonl`) in plaats van hard te verwijderen — tenzij Stefan expliciet liever
gewoon weg wil. Aan Claude Code: eerst lokaliseren + afhankelijkheidscheck, dan pas opruimen.

**Ook besloten**: de CLAUDE.md-belofte ("een model beslist niet") wordt afgedwongen met een ratchet-
test (AST-scan die faalt zodra `kies_ontvanger`/`_vraag_llm` op een pad staat dat schrijft) — dit is
precies het geval waarvoor `docs/CONVENTIES.md`'s waarneembaarheidsregel is opgeschreven. Meteen
meebouwen, geen aparte stap.

## Alle drie besluiten uitgevoerd (20 sept, commit `fc26653`): 3873 passed, 1 xfailed

**Besluit 1 — bestemming is overal de founder**: `_mens_ontvanger` geeft nu altijd `signaal.terugval
(st)` terug (was: modelkeuze); `sluitronde._panel` levert nu altijd een escalatie op in plaats van
zelf een project aan te maken of af te wijzen; `cockpit2.bestemming` valt bij een doodlopende
lead-hop terug op de founder in plaats van de rol zelf. Het modelantwoord is tekst geworden:
`match()`'s grond reist mee als voorstelregel ("dit lijkt van Creator of Shoes — ..."), accepteren is
`@rol` antwoorden in de DM (bestond al sinds fase 8). De stille fout van de oude versie is er ook mee
verdwenen: wegvallend modelkrediet verandert de bestemming niet meer, alleen de voorstelregel
verdwijnt (met test).

**Eén bewust, opgebiecht verlies**: de opdrachtgever van een vastgelopen project hoort dit niet meer
automatisch — dat was de tweede trede van de oude ladder. Alles komt nu bij Stefan uit, hij geeft het
zelf door. Dat is precies wat Stefan vroeg ("ik wil eerst controle over alles"), dus geen probleem,
wel iets om je bewust van te zijn nu het is opgeleverd.

**Twee losse vervolgvragen van Claude Code, nog niet beantwoord**:
- Sluitronde behield twee deterministische takken (verlopen op leeftijd, afwijzen op scope-overlap)
  — regels, geen oordelen, staan in de code en in het rapport. Vraag: wil je die ook eerst zien?
  Mijn advies: nee, deterministisch en al zichtbaar in het rapport, geen aparte review nodig — tenzij
  je zelf de code even wilt inzien.
- `MENS_SITE` staat nog in `llm_keuze.HOOG_INZET` (het duurdere modeltier), met als reden dat een
  verkeerde ontvanger vroeger via het spoor onomkeerbaar was. Die reden is vervallen nu het een
  weggooibaar voorstel is. Open kostenvraag: mag dit naar een goedkoper model? Tot een besluit blijft
  het op het huidige tier draaien.

**Besluit 2 — de klim valt terug op de founder**: gebouwd en getest
(`test_een_rol_zonder_vervuller_en_zonder_lead_valt_terug_op_de_founder`), met de reden zichtbaar in
het `via`-veld. **Nog niet effectief**: dit staat alleen op de branch, prod draait nog `8ecf29a`. De
twee Compliance-weesprojecten zijn dus nog niet opgelost — dat gebeurt pas bij een deploy, die Stefan
nog niet heeft goedgekeurd. Sluit aan bij de eerder genoteerde, nog onbeantwoorde deploy-vraag
(sidebar/inbox-zichtbaarheid) — de lijst met klaarstaande, ongedeployde fixes groeit.

**De ratchet, met een eigen zelfcorrectie**: de eerste versie van `test_geen_model_routering.py` keek
alleen binnen één functie en miste de echte bug (een `return` tussen keuze en aflevering) — hij
slaagde voor zijn eigen test maar niet voor zijn doel. Herbouwd om de uitkomst over returnwaarden heen
te volgen, per tuple-positie (anders zou hij het hele antwoord — inclusief de goede voorstelregel —
afkeuren). Aangevuld met `test_bestemming_is_altijd_de_founder.py`. Sluitronde had nul tests, heeft er
nu drie.

**Besluit 3 — spanning-geschiedenis opgeruimd**: vier bestanden gevonden en met de villageraad-
discipline gecheckt (`notifications.json` 371 rijen, `verwerkingen.jsonl` 13, `autonomie_signaal.jsonl`
3, `villageraad.jsonl` 13) — alle vier gearchiveerd naar `data/archief/<naam>.20260920` (sha256-
geverifieerd vóór legen), daarna leeggemaakt. `gaps.jsonl` (119 KB, capaciteit-tekorten, geen
spanningen, heeft een levende schrijver) is bewust overgeslagen — vraag aan Stefan: moet die ook weg?
Mijn advies: nee, ander onderwerp, geen reden om mee te nemen.

**Zelfgevonden en hersteld tijdens de uitvoering**: het opruimscript liep als root, waardoor de vier
bestanden root-eigendom werden en `notifications.json` zijn `0600`-rechten verloor — de `nooch`-
service had er niet meer in kunnen schrijven. Eigenaarschap en rechten teruggezet, services
geverifieerd (actief, cockpit antwoordt, NotifStore leest de lege store, geen journal-fouten).

**Sweep-lijst aangevuld**: `escalation_router.mens_kandidaten` heeft sinds vandaag ook geen aanroeper
meer — bundelen met `escaleer()`/`route_item()` op de al bestaande opruimstapel.

## Tempo omgezet naar één geconcentreerde ronde, en volledige beslissing per module (20 sept)

Op de vraag of we het resterende werk stuk voor stuk of in één keer doen: Stefan koos voor één
geconcentreerde sessie. Reden voor de omslag: hij had het gevoel dat de negen fasen van de eerdere
grote opruimronde (dode rolklassen, NotifStore/inbox, AI-projectuitvoering/Founder Flow, UI-herbouw)
dit al hadden moeten wegnemen. **Verheldering**: dat is geen mislukte opruiming — die fasen richtten
zich op zichtbare AI-collega-architectuur en dode code, niet op losse, ingebedde LLM-oordelen in
verder legitieme tools. De lat "AI is instrument, geen rol" is pas deze fase gelegd; onder de oude,
impliciete standaard was zo'n aanroep normaal ontwerp. Vandaar dat dit nu pas, in deze ronde, boven
water komt.

Stefan kreeg de volledige lijst met uitleg per module en gaf per stuk zijn besluit. Twee open vragen
zijn met `AskUserQuestion` voorgelegd en beantwoord (categorie D: blijft staan; de samenvoeg-cluster:
geen voorkeur, dus mijn eigen lezing aangehouden — zie hieronder).

**Definitieve besluiten, per module**:
- `inhabitant.py` `_classify_llm`/`triage()` (spanning-sensing/routering in de dagpuls) — **weg**.
- `legal_signaal.py` `beoordeel`/`check()`, `claims_modelpas.py` `extra_kandidaten`,
  `materiaal_memo.py` `_schift`, `skills_impl/claim_evidence.py` `_verify_brand`,
  `claims_context.py` `beoordeel` — **samenvoegen tot één pijplijn**. Stefans eigen aanwijzingen
  ("3 combineren met 2", "7 combineren met 3 en 4", "12 combineren met 3 en 4") vormen via 3 als
  schakel feitelijk één cluster, niet twee aparte — dat is de lezing die is aangehouden. Vorm: signalen
  verzamelen en false positives eruit filteren (de huidige `claims_context`/`claims_modelpas`/
  `claim_evidence`-logica), dat wordt een memo (materiaal_memo's "vertaal naar memo"), en die memo is
  wat een mens activeert (legal_signaal's rol) — in plaats van vijf losse plekken die elk zelf al dan
  niet een mens inschakelen of iets aanmaken. Nog niet uitgewerkt tot een concreet ontwerp, dat is aan
  Claude Code.
- `skills_impl/escaleer.py` `_classify` — **weg**.
- `scope_nudge.py` `match_project_to_role` — **weg**.
- `skill_match.py` `plan_offers` — **houden**, ongewijzigd.
- `wizard.py` `plan_items` — **houden**, ongewijzigd.
- `library_skills.py` `KeywordReviewSkill._llm` — **houden**, ongewijzigd.
- `governance_review.py` — **houden**, maar wel via een bericht naar Stefan laten lopen (zelfde
  mens-toewijzingspatroon als vandaag bij `vastgelopen_route`/`sluitronde`), niet los laten hangen
  zonder duidelijke aanroeper.
- `cockpit2.py` `_finetune_voorstellen` (stelt twee alternatieve werkinstructies voor een AI-persona
  voor, mens kiest, Kroniek-log) — **weg**.
- Categorie C (dode code, geen aanroeper) — **opruimen**, zoals al voorgesteld.
- Categorie D (puur inzicht, geen organisatorisch effect) — **blijft staan**, expliciet bevestigd:
  dit is precies het soort "AI geeft inzicht in trends/cijfers" dat Stefans eigen principe toestaat.

Volgende stap: dit compacte besluitenoverzicht naar Claude Code, met het verzoek om vooral het
samenvoeg-ontwerp (2+3+4+7+12) als voorstel terug te brengen voordat het gebouwd wordt — dat is de
enige plek hier die nog een ontwerpkeuze vergt, de rest is een rechte verwijder- of behoud-opdracht.

**Volgende besluit, al klaargezet door Claude Code**: `inhabitant._classify_llm`/`triage()` — de
enige van de onderzochte categorie-A-plekken die in de dagpuls draait zonder dat een mens hem start.
Dit is precies het mechanisme dat Stefans eigen uitspraak raakt ("AI zou geen spanningen meer moeten
sensen").

## `inhabitant._classify_llm`/`triage()` uitgezocht: hele keten weg (20 sept)

**Hoe het werkt**: `sense_tension` → `triage()` → `_classify_llm` (het model antwoordt met
`STRUCTURAL`/`OWN`/`OTHER:<rol-id>`/`TACTICAL`) → `triage_engine.classify()` routeert op basis
daarvan. Twee kritieke gebreken in de classifier zelf: (1) het modelantwoord wint altijd — zodra het
model iets zegt, draaien de deterministische checks (trefwoord, purpose-overlap, domein-match)
helemaal niet; de deterministische laag is dus geen vangnet, alleen een terugval voor als er geen
modelantwoord is. (2) geen validatie op de genoemde rol — in tegenstelling tot
`escalation_router.kies_ontvanger` (die een onbekende/uitgesloten rol expliciet weigert) heeft
`triage` die guard niet.

**Drie structurele gaten, los van het model**: de gekozen capability is altijd de eerste skill in het
DNA van de aangewezen rol — heeft die rol geen skills, dan verdampt de spanning spoorloos
(`tension_routed`, niemand luistert mee). De Matchmaker routeert vervolgens op capability, niet op de
door het model gekozen rol — een goede rolkeuze garandeert dus niet dat het werk daar landt. En
`human_intervention_needed`, de bedoelde "escaleer naar mens"-uitgang, bereikt in werkelijkheid geen
mens — het is alleen een regel in `system_log.jsonl`.

**Wat het op prod deed**: 47 spanningen gesensd en getrieerd. 26 van de 38 rol-aanwijzingen (68%)
noemden een rol die inmiddels gearchiveerd is of niet bestaat; nog 2 noemden een levende rol zonder
skills (verdampt evengoed). `human_intervention_needed`: 0 keer, betrouwbaar gemeten. Of
`help_requested` ooit echt werk heeft afgeleverd is niet uit het log af te leiden.

**Waarom het nu toevallig stilligt**: de 4 huidige bewoners kunnen geen spanning sensen; de enige drie
codeplekken die dat kunnen hebben zelf geen aanroepers (of Noochie slaapt). De drie rollen die
historisch de 47 spanningen produceerden (librarian, website_watcher, concurrent_scout) zijn alle
drie gearchiveerd. Het ligt dus stil bij toeval, niet bij besluit — `village afslanken wek noochie`
zet het in één commando weer aan, en dan routeert een model werk terwijl CLAUDE.md dat sinds gisteren
verbiedt. De AST-ratchet vangt dit niet (`ask()` staat niet in de bewaakte lijst).

**Opties van Claude Code**: (A) laten staan, kost niets vandaag maar is een tijdbom; (B) alleen
`_classify_llm` eruit, deterministische classifier laten routeren — kleinste ingreep, lost de drie
structurele gaten niet op; (C) alles naar Stefan zoals bij `_mens_ontvanger`, maar dat beëindigt de
rol-naar-rol-samenwerking uit CLAUDE.md's Triage-hoofdstuk; (D) de hele keten weg
(`sense_tension`/`triage`/`_classify_llm`/`_route_to_role`/`_try_tactical_or_escalate`) — raakt twee
harde regels en de architectuurbeschrijving, dus een architectuurbesluit, geen opruiming.

**Besloten (20 sept)**: **optie D, de hele keten weg**. Reden: het past bij Stefans eigen principe
("AI zou geen spanningen meer moeten sensen"), en het is vandaag goedkoop omdat er toch al geen
levende producent is en de keten nooit heeft bewezen waarde te leveren (68% foute adressen, nul
gemeten mens-escalaties). De week-lang-meten-optie is expliciet afgewezen — met de huidige stilstand
levert dat vermoedelijk niets op. Consequentie, expliciet benoemd: dit raakt ook CLAUDE.md's
Triage-hoofdstuk en de architectuurbeschrijving bovenaan — dat document moet mee worden bijgewerkt,
niet alleen de code verwijderd.

## Hele besluitenpakket uitgevoerd (20 sept): 3778 passed, 2000+ regels weg, zes commits, geen deploy

**1. Triage-keten weg (`dfe4c58`)**: naast de aangewezen functies ook alles dat er alleen voor
bestond — `triage_engine.py`, `matchmaker.py`, `ask`/`offer`/`_on_accountability_requested`,
`propose_close`/`ask_accountability`/`deliver`/`handle`/`Circle.handle`, `models.Task`/
`models.Response`, de Task-tak in `run()`, `Inbox.deliver`, plus `village triage`/`triage_demo` en
fase 3 van `village simulate`. Verantwoording: `.offer(` had nul aanroepers dus
`_on_accountability_requested` viel altíjd in de tak die zelf een `sense_tension` deed — dat
mechanisme bestond uit precies de regel die wegging. En `ask()` had exact twee aanroepers, beide in
triage — de Matchmaker had dus geen producent meer over. Terecht meegenomen, geen scope-verruiming.
Noochie's `_weigh_in`-oordeel gaat niet verloren: `_persist_daily` schreef het toch al naar
`noochie_daily.json` (wat de cockpit toont), de spanning was een tweede kopie — de vier Noochie-tests
zijn verlegd naar dat verdict in plaats van geschrapt. CLAUDE.md bijgewerkt: architectuur telt nu twee
lagen, harde regels 6 en 9 aangepast, Triage-hoofdstuk vervangen door de vier structurele gaten die
er los van het model al in zaten — precies zoals gevraagd, geen kaal "verwijderd".

**3/4/5. Drie modeloordelen weg (`faedcab`)**: `escaleer._classify` weg (de fail-open eronder blijft:
bij twijfel zichtbaar een beslissing). `scope_nudge.match_project_to_role` weg, en met dat oordeel
ook de hele nudge (`_nudge_scope_matches`, puls-wiring, drie helpers, ledger). **Noemenswaardig**:
deze ene aanroep was 3150 van 8478 modelaanroepen — 37% van al het modelverbruik in de hele codebase.
`_finetune_voorstellen` weg, met een scherpe reden: een model dat zijn eigen persona-werkinstructie
herschrijft is precies de zichzelf-in-stand-houdende lus die de nieuwe regel wil voorkomen.

**7. `governance_review` via bericht (`5c3d280`)**: bleek bij nader inzien geen adreswijziging maar
een echte lus-fix. De voorstellen gingen naar `HumanInbox.add_opportunity`, waar `sluitronde` ze weer
oppakte — een raadspanel (zelf ook een model) zei er ja/nee tegen en maakte bij ja een project aan.
Eén model afgetikt door een tweede model is geen mensdrempel. Nu gaat elk voorstel als DM naar Stefan.
Ook `route_teleology_to_roloverleg`/`_parse_teleology_opportunity` weg (zelfde patroon, voor
rolwijzigingsvoorstellen).

**8. Categorie C opgeruimd (`2f1b344`)**: `escalation_router` (escaleer/route_item/mens_kandidaten),
roloverleg (3), inbox_actions (8), `inhabitant._payload_opnieuw`, `umbrella.py`, en de verweesde
triage-acceptatiemeting. **Twee zelfcorrecties, belangrijk voor het vervolg**: `triage_rol.classificeer`
is NIET dood — `menselijke_eigenaar` (triage_rol.py:394) roept 'm aan, en dat is de lookup waarmee
`materiaal_memo` bepaalt bij welke rol een memo hoort. Dus een levend modeloordeel in een daemon-pad,
hoort in het pijplijnvoorstel, niet in opruiming — correct er niet stilzwijgend meegenomen.
`bevinding.py` is wél dood (villageraad was de laatste importer) maar bewust laten staan: een hele
module met vijf testbestanden en een eigen plek in `docs/CONVENTIES.md`, dus een besluit, geen
opruiming. **Besloten**: ook weg, samen met het bijwerken van zijn vermelding in
`docs/CONVENTIES.md` (niet alleen schrappen, zoals bij CLAUDE.md's Triage-hoofdstuk net goed is
gedaan) — dezelfde discipline toepassen.

**Zelfgevonden fout, hersteld**: het knip-script voor `_payload_opnieuw` sneed ook vier
class-attributen van `Inhabitant` en een `@classmethod` mee. 35 tests vielen om, teruggehaald uit HEAD
en de diff nagelopen. De suite ving het — zonder die testdekking was het er stil doorheen geglipt.

**6/9. Ongewijzigd**: `skill_match.plan_offers`, `wizard.plan_items`,
`library_skills.KeywordReviewSkill._llm` en heel categorie D — niet aangeraakt, zoals besloten.

**Nog open, het enige punt met een echte ontwerpkeuze**: het pijplijnvoorstel
(`legal_signaal`+`claims_context`+`claims_modelpas`+`claim_evidence`+`materiaal_memo`), nu inclusief
`triage_rol.classificeer` sinds die aantoonbaar levend en relevant bleek. Claude Code schrijft dit uit
in een volgend bericht, nog niets gebouwd.

**Nog steeds openstaand, niet vergeten**: geen van de zes commits van vandaag (of de eerdere van deze
fase) is gedeployed. De ongedeployde stapel blijft groeien, en CLAUDE.md's architectuurbeschrijving
wijkt nu materieel af van wat op prod draait — dat verschil wordt met elke ronde groter.

## Stefan: niet blijven hangen in kleine stappen, drie dingen nu doorpakken (20 sept)

Stefan, expliciet: niet vasthouden aan veel kleine incrementele veranderingen uit het verleden, maar
doorpakken. Drie concrete dingen genoemd: de resterende CSS/visueel-systeem-afronding, de oude inbox
helemaal weg (inclusief deployen, niet alleen op de branch), en de nog niet bevestigde Messages-
navigatie.

**Messages-navigatie — bevestigd, geen verdere vraag nodig**: het voorstel uit de prototype-sectie
hierboven (desktop: globale zijbalk klapt in tot een 64px-icoonrail zodra je in Messages zit, mobiel:
drill-down met hamburger-slide-over) wordt aangehouden. Geen tegensignaal ontvangen op dit specifieke
punt en het past bij "doorpakken" — Claude Code kan dit bouwen als onderdeel van fase 11.

**CSS/visueel systeem**: de resterende 63 kleur-alleen-statussen buiten de negentien al aangepakte
schermen (fase 9), en fase 11's al volledig gespecificeerde atoms/molecules/patterns-lijst (rol-
status-icoon, `.nu-progress`, kanaal-ongelezen-indicator, sleep-patroon op het Projects-bord, etc.) —
"aangekondigd maar niet gestart." Nu bouwen, in de vastgelegde volgorde (atoms → molecules →
patterns), niet per scherm losse CSS verzinnen.

**Deploy-volgorde voor de oude-inbox-verwijdering — besloten**: eerst het kleine, al gespecificeerde
fase-11-onderdeel bouwen dat een ongelezen-indicator op kanalen zet (kanaal-ongelezen-modifier op
`.msg-kanaal`), dán pas deployen. Reden: zonder die indicator verdwijnt bij deploy de zijbalk-lade en
`/inbox` (404) zonder enige vervanging, en collega's die net inloggen zien geen signaal meer welk
kanaal ongelezen is — dat voelt als "berichten kwijt", niet als een verbetering. Dit is de enige
fase-11-prioriteit die de deploy blokkeert; de rest van fase 11 kan parallel of erna.

**Samengevat, aan Claude Code**: bouw eerst de kanaal-ongelezen-indicator (fase 11, onderdeel 3a),
dan de rest van fase 11 (inclusief de Messages-navigatie hierboven, nu bevestigd) en de resterende
63 kleur-alleen-statussen, en zodra de indicator klaar en getest is: deploy alles wat nu al klaarstaat
(B2, de vier LLM-besluiten van vandaag, de oude-inbox-verwijdering) in één keer — niet nog een ronde
laten liggen.

**Bewust buiten deze beslissing gelaten**: de andere categorie-A-plekken (`inhabitant._classify_llm`,
`legal_signaal`, `claims_site_scan`) hebben een andere vorm (draaien in de daemon zonder enige
batch-start door een mens) en verdienen elk hun eigen besluit — dat komt later, apart.

## Pijplijnvoorstel klaar en besloten (20 sept)

Claude Code's meting die het voorstel stuurde: de twee claim-filters staan op de verkeerde paden.
`claims_context` (haalt valse positieven weg) draait alleen op het scherm waarnaar Stefan al kijkt.
`claims_modelpas` (voegt modelvondsten toe, bewust ruim afgesteld — "bij twijfel meldt het model de
zin") draait alleen in de dagpuls, en dáár worden er automatisch projecten van gemaakt op naam van
een rol. Het gefilterde pad heeft dus al een mens erbij; het ongefilterde pad niet — en dat is precies
het pad dat op recall staat. Vandaar dat samenvoegen meer oplevert dan alleen minder regels.

**Voorgestelde pijplijn, vier stappen**: (1) verzamelen — elke bron levert ruwe signalen in één
gedeelde vorm (`bron, tekst, vindplaats, gevonden_op, herkomst`), eigen ritme per bron blijft (legal
dagelijks, materiaal maandelijks); (2) filteren — een gedeelde, deterministische grondings-poort
(het fragment moet letterlijk in de brontekst staan, elimineert hallucinatie) plus een expliciete,
per-bron-drempel (legal fail-closed, claims_modelpas op recall, claims_context op precisie — bewust
niet gemiddeld, drie verschillende, elk verdedigbare houdingen voor hun eigen onderwerp); (3) memo —
materiaal_memo's vorm (leesstuk, geen store; onthoudt wat al voorgelegd is; "liever nul dan een
zwakke", geen memo bij een lege ronde); (4) activeren — de memo als DM bij Stefan, met
`triage_rol.menselijke_eigenaar` als voorstelregel in plaats van adres (zoals `_mens_ontvanger`
gisteren) — daarmee de laatste levende modelroutering in de codebase weg.

**Bewust niet meegenomen**: `claim_evidence` als skill blijft apart (I/O met externe pagina's en
SerpAPI, geen filterlogica; de pijplijn hergebruikt alleen zijn grondings-poort en statusvocabulaire).
De regex-database (`claims_db`) blijft de enige bron van een "rood" wetsoordeel — dat blijft een
harde grens, verplaatst niet naar modelinzicht.

**Stefans drie besluiten**:
1. **`claims_board` uit de dagpuls — ja.** De duurste van de drie keuzes: compliance-werk begint
   voortaan bij Stefan, geen automatische projectaanmaak meer op naam van een rol. Volume is niet
   nul (`claims_site_scan` is de default pulse-skill, `claim_evidence` draaide 105 keer) — dit gaat
   Stefan echt tijd kosten, met open ogen aanvaard.
2. **Eén gecombineerde memo over alle bronnen heen, niet één per bron — tegen Claude Code's eigen
   advies in.** Reden van Stefan: de synthese over bronnen heen is juist waar waarde ontstaat, en
   daar mag een duurder model voor gebruikt worden. **Cadans, door Stefan zelf gecorrigeerd**: mijn
   voorstel om dagelijks te draaien (zodat legal niet zou wachten op materiaal's langzamere ritme)
   was niet nodig — **wekelijks is voldoende**. De per-bron-drempel uit stap 2 blijft ongewijzigd,
   alleen de synthesestap (stap 3) wordt gecombineerd, wekelijks, met het duurdere model.
3. **De 84 wachtende radar-items en de bestaande openstaande claim-projecten kunnen weg.** Zelfde
   discipline als bij de spanning-geschiedenis eerder vandaag: archiveren (niet hard verwijderen),
   niet alsnog door de nieuwe pijplijn halen.

Aan Claude Code: bouwplan uitwerken op basis van deze drie besluiten plus de cadans-invulling, nog
niet bouwen zonder dat plan gezien te hebben — zelfde patroon als steeds deze fase.

## Bouwplan pijplijn ontvangen en goedgekeurd (20 sept)

**Nulmeting op prod wijkt fors af van de aanname in de brief**: 339 wachtende radar-items (van 938
totaal: 339 wacht, 304 goedgekeurd, 295 afgewezen), niet 84. Open claim-projecten: 3 (niet
"bestaande" in het vage), alle future, van 46 claims_fix-projecten totaal waarvan 43 al af of
gearchiveerd. **Verschuiving**: de claims-kant is triviaal, de radar-kant (339, niet 84) is de
eigenlijke opruiming. Stefans "kunnen weg"-besluit stond op het verkeerde getal toen hij het nam —
gemeld, maar niet aanleiding om de aanpak te wijzigen: het gebeurt via archiveren (status
`gearchiveerd`, bestand niet leeggemaakt, want de 304/295 zijn geschiedenis waar de adapters op
terugkijken), niet hard verwijderen, en pas als laatste stap na bewezen werking van de nieuwe stroom
— dat maakt de aanpak veilig ongeacht de schaal.

**Bouwplan, zeven stappen, goedgekeurd**: (1) gedeelde grondings-poort (`weekmemo.gegrond`),
één implementatie i.p.v. drie, laag risico, met een stopmoment als de drie bestaande implementaties
blijken te verschillen; (2) één signaalvorm + vijf bron-adapters (legal_signaal, claims_modelpas,
claims_context, claim_evidence, materiaal_memo), elk met zijn eigen drempel als veld, niet in de
pijplijn; (3) `claims_board` uit de dagpuls (sluit het filter-gat dat de hele aanleiding was); (4) de
weekmemo zelf — één synthese per ISO-week over alle vijf bronnen, nieuwe call-site
`weekmemo_synthese` in `llm_keuze.HOOG_INZET` (eerste toevoeging sinds 13 september, met Stefans
eigen reden erbij in de ratchet-test), fail-open met een kale, bronvermelde opsomming als het model
uitvalt — belangrijker nu dan bij vijf losse memo's, want nu valt bij uitval alles tegelijk weg;
(5) bezorging als DM bij Stefan, `triage_rol.classificeer` wordt een voorstelregel i.p.v. een adres
(laatste levende modelroutering in de codebase, de AST-ratchet vangt 'm voortaan); (6) archiveren,
apart en als laatste, na goedkeuring van de uitkomst van 1–5; (7) twee nieuwe ratchets (bestaande
routeringsratchet blijft slagen; nieuwe guard dat een verzamelaar niet mag schrijven). Commit-
volgorde bewust: weekmemo (4) vóór het afsluiten van de oude aflevering (3), dan 3+5 in één commit
zodat er geen week is waarin compliance-vondsten nergens landen.

**Go gegeven op stappen 1 t/m 5 en 7**; stap 6 (archiveren) volgt apart na zien van de uitkomst.

**Openstaande vraag aan Claude Code**: gaat `afslank_wezen`'s eigen `_circle_lead_van`-aanroep ook
over op dezelfde ladder als onderdeel van deze wijziging (zodat de twee Compliance-weesprojecten
vanzelf goed routeren zodra dit gebouwd is), of blijft dat een aparte, nog openstaande reparatie?

**`_rolsuggestie` is weg** (functie + aanroep, reden in het comment). `triage_rol.py` zelf blijft
staan: `menselijke_eigenaar` heeft nog een eigen lezer in `materiaal_memo`. De rest van `triage_rol`
(`classificeer`, `noteer_uitkomst`, de acceptatiemeting, en `cockpit2._noteer_triage` die hem voedde)
ligt nu dood — meegenomen in de sweep-conclusies hieronder, geen aparte actie.

**De volledige sweep** (34 modules), ingedeeld naar risico:

**Categorie A — direct effect, geen mens ertussen, draait in de dagpuls** (de scherpste groep):
- `inhabitant.py` `_classify_llm`/`triage()` ✓ geverifieerd — bepaalt bij welke rol werk hoort, routeert
  meteen naar iemands inbox. Geen mens, alleen een event als spoor achteraf.
- `legal_signaal.py` `beoordeel`/`check()` ✓ geverifieerd — bepaalt of een nieuwsbericht Nooch raakt.
  Bij "nee" ziet niemand het signaal ooit. Gewired in de dagpuls. **Dit is de scherpste losse plek**:
  het enige geval waar een fout van het model onzichtbaar blijft, niet alleen fout.
- `claims_modelpas.py` `extra_kandidaten` ✓ geverifieerd — beslist welke tekstfragmenten als
  milieuclaim gelden zonder regex-match. Effect: een project op naam van een rol, plus een bericht.
  Default pulse-skill.
- `materiaal_memo.py` `_schift` — kiest welke 1-2 van tot 60 signalen de shortlist halen; wat
  afvalt ziet niemand.
- `skills_impl/escaleer.py` `_classify` — bepaalt of iets een bevinding is (niemand ziet het) of een
  beslissing (founder/rol krijgt een DM), én wie die ontvangt. Kanttekening: de checklist-uitvoerder
  die dit pad voedde is 19 sept al verwijderd, dus onduidelijk hoe vaak dit nog vuurt — vraag aan
  Claude Code: is dit pad nu nog bereikbaar in productie?
- `scope_nudge.py` `match_project_to_role` — stuurt een scope-nudge naar een rol. Laag risico, en
  Noochie staat op prod op slapend, dus dit tikt nu niet.
- `skills_impl/claim_evidence.py` `_verify_brand` — bepaalt per merk/claim of iets bevestigd is; dat
  voedt of een milieuclaim in de Kroniek als "onderbouwd" (groen, geen taak) geldt. De sweep weet zelf
  niet zeker of dit in de praktijk een claim groen kán maken zonder mensbeoordeling — vraag aan Claude
  Code: kan dat, en zo ja, is dat gewenst?

Twee van deze zeven (`claims_modelpas` en `claim_evidence`) raken rechtstreeks milieuclaims — precies
het domein waar Nooch op "proof, not words" staat en waar een verkeerde automatische classificatie
reputatie- en zelfs juridisch risico is (greenwashing-toetsing kijkt naar precies dit soort claims).
Samen met `legal_signaal` (onzichtbare no's) zijn dit de drie waar ik zou beginnen als er geprioriteerd
moet worden, boven de andere vier in categorie A.

**Categorie A2 — direct effect per item, maar een mens startte de batch**: `sluitronde.py` `_panel`
(panel stemt over een kans, zet onomkeerbaar, kiest trekkende rol — `--apply` gate op batchniveau,
geen per-kans-bevestiging) en `vastgelopen_route.py` (zie hierboven). Zelfde vorm, zelfde soort fix
denkbaar.

**Categorie B — mét mens ertussen, compliant**: `skill_match.plan_offers`, `wizard.plan_items`,
`claims_context.beoordeel`, `library_skills.KeywordReviewSkill._llm` (advies, geen enkel pad schrijft
dit door naar `Library.curate` zonder mensactie), `governance_review` (geen productie-aanroeper
gevonden, alleen tests), `cockpit2._finetune_voorstellen`. Geen actie nodig.

**Categorie C — LLM-oordeel met organisatorische strekking, maar niet gewired** (dode code of geen
aanroeper): `escalation_router.escaleer()`/`route_item()` ✓ (al bekend), `roloverleg.tension_validity`,
`roloverleg.amend_with_reaction`/`flip_facet`, `inbox_actions.pick_governance_target` + 4 andere,
`inhabitant._payload_opnieuw`, `bevinding.herschrijf` (alleen tests), `umbrella.umbrella_terms` (geen
aanroeper), `governance_review.*`, en sinds vandaag ook `triage_rol.classificeer`/`noteer_uitkomst`.
Geen urgentie, meenemen zodra er toch in gewerkt wordt.

Losstaand, buiten de strikte definitie maar wel relevant: `views/metrics._llm_says_comparable` zet
een break-migratie om naar backcast, waarna de meetreeks anders wordt behandeld — een mens start de
opslagactie maar ziet dit methodologische oordeel niet vooraf. Geen toewijzing, wel een besluit dat
cijfers beïnvloedt die elders (o.a. `waarde_audit`) weer als basis dienen. Voeg toe aan de
prioriteitslijst hierboven: als er íets stilletjes cijfers vervormt, is dat dit.

**Categorie D — puur inzicht, geen effect**: lange lijst (coherence, roles._reflect, verslag,
views/noochie, skills_impl/voorstel en tegenspraak, deliverable_kop, leesextract, reeds_bekend,
materiaal_memo._schrijf_memo, inbox_actions.answer_pending_questions, wizard.sharpen_outcome/
guess_impact, kennis_embeddings, llm_keuze) — geen actie. Twee zijaantekeningen: `keyword_nominations`
gebruikt helemaal geen LLM (was een misvatting); en `inoreader_ingest` heeft nog `llm_reason`/
`mission`/`focus` in zijn signatuur terwijl de LLM-poort op 19 sept is weggehaald — de ingest is nu
ongefilterd. **Vraag aan Claude Code**: is dat bewust (filtering gebeurt elders) of een onbedoeld
bijeffect van de poort-verwijdering? Los randgeval: `roles._weigh_in` is zelf inzicht, maar roept bij
`niet_ok` `sense_tension` aan, wat weer de triage-routering uit categorie A voedt — het oordeel is
inzicht, het gevolg niet.

**Mijn advies aan Stefan**: geen van de categorie-A-plekken hoeft vandaag te worden omgebouwd — dat
zou zelf een big-bang zijn en gaat in tegen de net vastgelegde regel. Wel vier dingen nu, klein en
losstaand van de rest: (1) de data-vraag over "Harry Hemp" (echte, nog niet opgeruimde rol, of
verzonnen voorbeeld?) — eerst uitzoeken, dat bepaalt of er ook een stale-data-probleem is naast het
ontwerpprobleem; (2) de ontwerpvraag of `_mens_ontvanger()` (en `sluitronde`'s `_panel`) vastgelopen
werk altijd naar Stefans eigen inbox moet sturen in plaats van een door het model gekozen
rol-eigenaar — dat is Stefans eigen, eerder gestelde uitgangspunt en principieel een schonere
oplossing dan alleen de grond tonen; (3) de drie overige openstaande verificatievragen aan Claude Code
(escaleer-bereikbaarheid, claim_evidence-groen-zonder-mens, inoreader-ingest-filtering); en (4) een
expliciete keuze van Stefan over de volgorde waarin categorie A wordt aangepakt zodra er toch in
gewerkt wordt — suggestie: `legal_signaal` eerst (onzichtbare fout), dan de twee claims-plekken, dan
de rest. Geen conclusie nodig over wát er per plek verandert — dat is een ontwerpkeuze per geval.

## 3a klaar, drie dingen geblokkeerd voordat fase 11 en de deploy verdergaan (20 sept, commit `9c12821`)

**3a (kanaal-ongelezen-indicator)**: klaar en getest (3738 passed). Modifier op `.msg-kanaal`, geen
nieuwe component, drie dragers (vet, telling, tint — nooit kleur alleen). Eén aanname in de eigen
spec bleek fout en stuurde het ontwerp: er bestonden geen "bestaande lees-tijdstippen" om op te lezen
(`ChannelStore` heeft geen leesstatus, en `NotifStore`, die dat wél had, is in B2 opgeheven). Geen
nieuwe store gebouwd — "wanneer heeft deze persoon dit gelezen" hangt aan `PeopleStore`, ongelezen
zelf is nooit opgeslagen maar een vergelijking tussen twee tijdstippen (zelfde vorm als
`wiki.grond_status`). Drie valkuilen zijn getest: je eigen bericht telt niet mee, het kanaal dat je nú
open hebt staat in de lijst nog als ongelezen, en de stand loopt nooit terug.

**Terechte correctie op mij**: ik zei "Messages-navigatie bevestigd zoals voorgesteld" zonder te
zeggen wáár dat voorstel staat. Claude Code zocht in de fase-11-spec en in
`ux_voorstel_best_practices_20sept.md`, vond het daar niet, en twijfelde terecht of het bestond —
**het staat wél**, in ditzelfde bestand, sectie "Messages-prototype gebouwd (20 sept)" (rail-inklap
naar 64px op desktop, org-boom achter een flyout-icoon; op mobiel een hamburger-overlay met
drill-down in drie niveaus). Die sectie zegt zelf nog "geen bouwinstructie, nog niet bevestigd door
Stefan" — dat klopte toen hij geschreven werd, maar is inmiddels achterhaald: het is nu bevestigd.
**Verduidelijkt**: de proza-beschrijving in die sectie (met de concrete maten: 64px rail, drie
mobiele niveaus) ís de bouwspec. Er is geen aparte prototype-HTML nodig voor dit deel — de losse
Design-canvas-Artifact van gisteren was verkennend materiaal, geen bronbestand.

**Nog wel een echt gat**: het HTML-prototype waar `ux_voorstel_best_practices_20sept.md` naar
verwijst voor laag 1 en 2 (klopt, niet nodig, spec is concreet genoeg) én laag 3 (sleep-patroon op
het Projects-bord, checklist-klik — hier is het prototype wél de enige gedragsspec) ontbreekt. Ik heb
'm ook niet. **Aan Stefan gevraagd**: waar staat die link?

**Deploy — groen licht**: de blokkerende voorwaarde (3a klaar en getest) is gehaald. Er staan twaalf
ongedeployde commits (B2, villageraad, de vijf LLM-besluiten van vandaag, de categorie-C-opruiming,
bevinding.py, 3a), prod draait nog `8ecf29a`. Claude Code's eigen advies — nu deployen wat klaarstaat
(incl. 3a), fase 11 laag 1+2 in een tweede ronde, laag 3 wachten op het prototype — **overgenomen**.
Twaalf commits in één keer is al genoeg risico om niet ook nog fase 11 erbovenop te stapelen.

## Deploy uitgevoerd en live op prod (20 sept, commit `462bcaf`/`462bcaf9e`)

De twaalf klaarstaande commits zijn gedeployed. Vooraf een databack-up gezet
(`backups/data_20sept_predeploy.tgz`, 100MB). PR #518 groen (2× tests + GitGuardian), squash-merged
naar main, `deploy.sh` gedraaid: health-check HTTP 303, beide services actief, geen journal-fouten.

**Smoke-test op echte productiedata**: 41 DM-kanalen, `/messages` rendert (18.950 tekens); de
ongelezen-indicator (3a) werkt op Stefans eigen kanalen; `bestemming(compliance)` valt nu correct
terug op Stefan Wobbens inbox, wat de twee wees-projecten bij Compliance daadwerkelijk oplost;
`notifications.py`, `views/inbox.py` en `matchmaker.py` bestaan niet meer op de server.

**De merge zelf had 13 conflicten** (hetzelfde squash-artefact-patroon als bij PR #517). Claude Code
heeft eerst gecontroleerd dat main geen commits miste die niet ook in de branch zaten, toen overal de
branch-versie genomen, en **daarna de merge-uitkomst byte-voor-byte tegen de branch vergeleken** in
plaats van te vertrouwen op "geen conflicten meer". Die laatste stap was geen overbodige
voorzichtigheid: `git checkout --ours` had een modify/delete-conflict niet schoon opgelost en had
stilletjes 4 bestanden/467 regels teruggezet, waaronder een `cli.py`-pad dat nog de inmiddels
verwijderde `st.notif`-store aanriep — een dode code-route zonder testdekking, alleen gevonden door
te vergelijken, niet doordat git "klaar" zei.

**Eén open vraag van Claude Code**: tijdens de merge zijn 747 regels briefwijzigingen gestashed en
staan nu weer in de werkmap, maar zijn niet gecommit naar git en dus niet meegegaan naar main/prod.
Claude Code heeft ze bewust niet zelf gecommit ("het zijn jouw woorden") en vraagt of Stefan ze alsnog
gecommit wil hebben.

**Mijn antwoord daarop**: commit ze. Het zijn legitieme, eerder al besproken briefinhoud (geen
scratch-tekst), en ze laten staan in een ongecommitte werkmap is het enige scenario waarin ze
alsnog stil verloren kunnen gaan (een volgende git-operatie, een schijfprobleem, een nieuwe stash).
Er is geen reden om ze apart te houden van de rest van de brief-historie.

**Nu live op prod**: B2 (het opruimwerk van fase 8), de vijf "AI is instrument"-besluiten (routering
weg bij `vastgelopen_route`/`sluitronde`, hele triage-keten weg, governance-loop dicht,
`scope_nudge` weg, `_finetune_voorstellen` weg), de categorie-C-opruiming, `bevinding.py` weg, en de
ongelezen-indicator (3a).

**Drie dingen staan nog open, in Stefans eigen volgorde**: (1) pijplijnstappen 1 t/m 5 en 7 (al
akkoord, Claude Code begint bij stap 1, de gedeelde grondings-poort); (2) fase 11 laag 1+2 in een
tweede ronde, inclusief de nu bevestigde Messages-navigatie; (3) stap 6 (archiveren) pas na Stefans
review van de uitkomst van 1-5.

## Wat hierna nog open staat

- De geplande-taak-mechaniek zelf (nodig voor: het maandrapport dat straks in de Wiki-schermen uit
  fase 7 landt, materiaal-memo, site-audit-cadans; de legal-check uit fase 4 kan al zonder) — eigen
  traject, `ontwerp_geplande_taak_mechaniek.md`. De schermen/navigatie/wiki-structuur hoeven daar
  niet op te wachten (zie de toelichting hierboven), de inhoud van de maandrapport-pagina's wel.
- `cockpit2.py`'s routetabel + splitsing per domein — pas beginnen als fase 6 is gedraaid, anders
  bouw je een tabel voor dode deuren.
- De schermen die in fase 9 bewust zijn overgeslagen (te bepalen tijdens die fase zelf) — apart te
  beslissen: los laten, of een tiende fase.
- orphan_report.py: of hij ooit handmatig op de server heeft gedraaid, staat nog open bij Stefan.
- `village waarde_audit`/`village villageraad`: hoort iemand dit periodiek te draaien? Beide laatste
  outputs zijn bijna een maand oud (26/28 aug), relevant nu bekend is dat `afslanken` op de eerste
  leunt.
- `vastgelopen_route`/`naar_mens()`: is het dry-run-rapport per toewijzing herbeoordeelbaar (toont
  onderbouwing) of alleen een kale naam? Enige nog openstaande vraag uit de "AI is instrument"-
  inventarisatie, gesteld aan Claude Code, nog niet beantwoord.
- Rest van de sweep over de resterende 34 LLM-modules ("AI is instrument"-inventarisatie) — Claude
  Code meldt zich zodra die binnen is.
- weten_we_dit_al (skills_impl) migreren van zijn eigen kennisbank.json-store naar de Wiki-laag
  (AttachmentStore), zodat kennis nog maar op één plek zit — bewust uitgesteld tijdens fase 2, geen
  onderdeel van deze opruimronde.
- `Pillow` uit `requirements.txt` schrappen (0 resterende PIL-verwijzingen sinds de EPIC-aardbol-
  verwijdering) — bewust niet meegenomen in fase 9, een dependency-schrap is een eigen deploy-
  risicomoment dat Stefan apart moet kiezen.
- ~~Wiki-pagina NOTE-STRATE-001 rendert een zichtbare `#`/`---`~~ — **opgelost** (19 sept, avond,
  `herstel_note_strate_001.py --doen`, pagina op versie 2, live geverifieerd).
- **Nieuw (19 sept, bij de deploy zelf ontdekt)**: `INFRA.md` en `docs/werkwijze_en_deploy.md`
  beschrijven een databackup als stap 1 van deployen, maar `deploy.sh` maakt die niet — hij doet
  alleen fast-forward pull, deps, herstart, health-check, code-rollback. Het `INFRA.md`-commando
  zoals het er letterlijk staat zet bovendien een root-eigen bestand tussen de (als `nooch`
  gedraaide) data, wat vandaag met de hand is omzeild. Een echte naad tussen documentatie en script,
  het waard om apart (niet als bijvangst) recht te zetten.
