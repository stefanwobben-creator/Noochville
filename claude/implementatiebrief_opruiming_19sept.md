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
