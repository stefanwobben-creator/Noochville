# NoochVille JOURNAL

Logboek van progressie, ontdekkingen en lessen. Append-only: nieuwe entries
onderaan, oude blijven staan. Per item een type-tag zodat je later kunt filteren
(fix / ontdekking / faalmodus / beslissing / les / procesobservatie).
STATE.md is de huidige waarheid (vervang bij update); dit is de geschiedenis.

---

## 2026-06-19/20 — nachtsessie, klein onderhoud tijdens Hogueras

**[fix]** pandas gecapt op `<3` (requirements.txt, commit cd4116c). CI haalde 3.0.3
binnen; verse install met de cap blijft groen.

**[fix]** scripts/live_measure.py onder versiebeheer gebracht (commit 21d195d),
inclusief correctie van een overgebleven KWFinder-URL naar keywordseverywhere.com.
Het script was untracked en leefde alleen lokaal.

**[fix/beveiliging]** .env toegevoegd aan .gitignore en gecommit (33f62b1).
Via git ls-files geverifieerd dat het nooit getrackt was, dus geen keys in de history.

**[ontdekking]** STATE.md kan twee kanten op onbetrouwbaar zijn. Achterlopen: de
inbox-approve-timeout stond als "parametrisch maken" terwijl het al instelbaar is
via inbox_approve_timeout (default 5). Overschatten: het dom WIP-plafond staat als
gebouwd, maar bestaat niet in de code of een stash. ProjectLedger heeft open()
maar geen cap-logica.

**[beslissing]** Timeout-item doorgestreept: 5s is royaal voor de deterministische
G0-G4-gate, default 5 blijft, oplossen pas bij een echte false-timeout. WIP-cap niet
gebouwd vannacht; geparkeerd als echt te-bouwen item.

**[les]** In STATE.md correleert een commit-hash met geverifieerd-waar, en geen hash
met mogelijk-lucht. Een gebouwd-claim hoort aan een commit te hangen, niet aan een
herinnering. Onderbouwt de STATE/JOURNAL-splitsing.

**[procesobservatie]** De keten: een URL-typo legde een untracked script bloot, dat
een ongecommitte .env-bescherming blootlegde. Klein onderhoud is zelden klein, maar
het stopte op een natuurlijk punt: drie fixes, schone main.

## 2026-06-20 — deel 1: wiring-gap-diagnoses (Ronnie, locale)

**[ontdekking]** Ronnie-gap stond fout in STATE. Hij abonneert op 8 event-types
(incl. pulse_completed), niet alleen dag_begint; de 15-juni-notitie klopte, de
19-juni-observatie was fout (STATE nog corrigeren). De "stille dag op een drukke dag"
komt door de demo-orkestratie: dag_eindigt valt niet in de demo, dus het bulletin
wordt buiten Ronnie's verzamel-flow geforceerd met een lege _events_today. In een
echte dagcadans werkt Ronnie. Eén losse echte gap: gsc_pulse_completed mist in _TRACK.

**[ontdekking]** Locale is een half-aangelegd dood pad, geen doorgeef-vergetelheid.
Upstream: GSC leidt locale af uit het domein-TLD ("en" voor heel nooch.earth) en zet
'm niet eens in het demand-dict. Downstream: Library.curate slaat locale niet op als
eigen veld, dus LibraryListSkill's locale_filter filtert structureel leeg. Niemand
leest de locale. De grove "en" is daarom dead-on-arrival (harmloos), maar de feature
werkt nergens — een spook-filter.

**[beslissing]** Ronnie: fix als "maak de demo een eerlijke simulatie" (dag_eindigt
laten vallen of bulletin via Ronnie's flow met verzamelde events; join-barrier) plus
gsc_pulse_completed toevoegen. Deel 2.

**[beslissing]** Locale: geen een-regel-fix. Vervolgactie = beslis of locale-filtering
een echte behoefte is. Zo ja: pad afmaken (GSC-country als bron + curate slaat locale
op als veld + filter werkt). Zo nee: dode locale_filter opruimen. Deel 2 of later.

**[les]** Drie wiring-gaps op rij (Ronnie, locale-upstream, locale-downstream) hadden
een diepere oorzaak dan STATE en de lijst suggereerden. De deel-2-wiring-gaps zijn
ontwerpvragen, geen triviale doorgeef-fixes. Herijk de scope: minder items, elk eerst
diagnose dan keuze.

## 2026-06-20 — deel 2 (deepwork): wiring-faalklasse, Ronnie + TimeKeeper

**[ontdekking/faalmodus]** Ronnie's "stille dag" was geen rol-bug. Drie aannames op rij omgegooid door read-first: (1) "bulletin geforceerd buiten Ronnie's flow op een lege lijst" was onjuist, er is geen forcing, het bulletin gaat altijd via _on_dag_eindigt; (2) "dag_eindigt valt niet in de demo" was omgekeerd, het valt te váák (TimeKeeper._ring publiceert het vóór elke ring na de eerste, met heartbeat=2 dus elke 2s); (3) het echte mechanisme: de demo hangt puls- en dag-cadans aan dezelfde 2s-heartbeat, dus elke 2s schrijft Ronnie een bulletin van die 2s-slice en leegt _events_today, en het datumbestand wordt overschreven ("w"-modus), zodat alleen de laatste slice (toevallig één dag_begint) overleeft.

**[les]** Tijdcompressie in een demo produceert artefacten die zich voordoen als rol-bugs. Ronnie was nooit kapot; productie (heartbeat=0, kalender-cadans) werkte al correct: één dag_eindigt per kalenderdag, events accumuleren, één bulletin. De simulatie loog. STATE las het eerder als "Ronnie alleen op dag_begint", dezelfde misinterpretatie.

**[fix]** Branch fix/demo-eerlijke-dag (gemerged): demo simuleert één eerlijke dag. heartbeat=0 (TimeKeeper levert één start-ring via _last_day=None, geen tweede tick binnen de run), join op alle drie pulse-completions (pulse/gsc/tijdgeest, 180s vangnet), dan één handmatige dag_eindigt via v.bus, join op bulletin_geschreven (30s vangnet) in plaats van de arbitraire 0.3s sleep. 100% demo-orkestratie, Ronnie en TimeKeeper ongemoeid, dus verhuizings-bestendig. Geverifieerd: 1 dag_begint, 1 dag_eindigt, bulletin met de echte dag.

**[ontdekking + fix]** De demo zet de tick-orkestratie stil, dus precies dat deel bleef ongetest. cadence_events (pure functie) was al gedekt (6 tests); het gat was de tick: één ring per kalenderdag (_last_day), eerste ring zonder dag_eindigt (_first_ring), dag_eindigt vóór dag_begint, maand/kwartaal-events op de 1e. Branch test/timekeeper-tick (gemerged): 4 thread-vrije tests via gemockte date.today(), tick() direct aangeroepen. 331 groen. Demo en test samen sluiten de keten: Ronnie schrijft goed bij nette events, TimeKeeper levert die events op de juiste kalendermomenten.

**[parkeren]** Twee latente dingen, niet gefixt. (a) _ring leest date.today() opnieuw na tick()'s read; precies op de middernachtgrens kunnen die één dag verschillen (theoretisch maar echt; nette fix: _ring de al bepaalde datum als argument geven). (b) Sinds de demo op heartbeat=0 draait lijkt de _interval>0-tak van tick() mogelijk dead code; apart checken op gebruikers voor opruimen.

**[richting]** Stefans denkrichting (visie-blok, geen besluit): zowel Ronnie (bulletin) als de TimeKeeper-functie (dagstart/dag-cadans) uiteindelijk onderbrengen bij Noochie, beide als losse seed-rol laten vervallen. Demo-fix en cadans-test zijn bewust rol-agnostisch gehouden zodat dit werk die verhuizing overleeft.

## 2026-06-20 — deel 3 (rollen-review): negen rollen naar zes AI plus The Source, drie machinerie-leugens eerlijk gemaakt

**[ombouw]** De rollen-review consolideerde negen losse seed/sensed-rollen tot zes live AI-burgers plus één menselijke bron-rol. Vier ingrepen: Facilitator absorbeert TimeKeeper's dagcadans (58329ff), Noochie absorbeert Ronnie's bulletin-mandaat plus een kantel-voorwaarde in _reflect (db14c55, 71bb2ca), HarryHemp consolideert tijdgeest_wachter en kennis_scout tot ngram-tijdgeest plus academische grounding (db6da10, ee32d72, d2b7130), en The Source verankert Stefan als onbemande menselijke rol in de records (e2751a6). Renames eraan vooraf: analyst naar website_watcher/Corry Coconut, scout naar trends/Maisy Mushroom (d5ab709, 127079b). Principe vastgehouden: cadans en bulletin verhuizen als functie naar een bestaande rol, niet als nieuwe rol met een eigen thread.

**[dogfood]** Harry's consolidatie liep deels door het eigen governance-proces: ADD_ROLE harry_hemp aangenomen, twee REMOVE_ROLE's geëscaleerd naar de inbox (ee32d72). De gate at zijn eigen voer, en dat onthulde meteen een leugen.

**[ontdekking/faalmodus] G3 deed alsof het de dekking checkte.** Bij REMOVE_ROLE van een rol met accountabilities escaleerde G3 met "nergens elders belegd", zonder dat ooit te checken; de echte dekking-tak werd voor REMOVE_ROLE nooit bereikt. Het gedrag (escaleren naar de mens) was correct fail-closed, want een deterministische gate kan semantische dekking principieel niet vaststellen: Harry dekt tijdgeest in betekenis maar niet in dezelfde woorden. De bug was de boodschap die een nepcheck voorwendde. **[fix]** e57bfa9: eerlijke boodschap, de gate kan niet vaststellen of het werk elders belegd is, mens beoordeelt, accountabilities erbij. De mens-als-dekking-checker is de feature, niet de tekortkoming. **[les]** Een gate die dom-en-cheap moet blijven mag geen oordeel claimen dat hij niet kan vellen.

**[ontdekking/faalmodus] persona overleefde geen reload.** Het natrekken van een onverwachte version-bump bij the_source ontrafelde een systemische bug: _load las het persona-veld niet, dus elke reload zette persona op None en de volgende save schreef null terug. Drie persona's (Corry Coconut, Maisy Mushroom, Harry Hemp) waren genivelleerd; alleen wie een idempotente herstel-tak had overleefde. **[fix]** 3d176be: _load leest persona, een centraal _PERSONAS-dict herstelt alle vijf, en een roundtrip-regressietest dekt de save/_load die niemand testte. **[les]** De stille bug leeft in de ongeteste roundtrip; hij bleef drie ombouwen onzichtbaar omdat niemand opslaan-en-herladen testte.

**[opruiming/faalmodus] residu in drie niveaus.** "Cosmetisch" verborg twee niet-cosmetische lagen. Productie-output: field_note zei nog "Je bent de Growth Analyst" (7851b8b naar Corry Coconut). Een script dat loog: supervised_pulses rapporteerde tijdgeest_ok=True zonder ooit op Harry te wachten, want het checkte op de opgeheven tijdgeest_wachter (7851b8b). Functionele demo's: reflect_demo en simulate toonden lege tabellen, en hier beet de aanname twee keer, eerst hielp de naam wisselen niet, daarna bleek de demo ook op de verkeerde events te abonneren (proposal_raised in plaats van means_gap_sensed) én de reflectie nooit te triggeren omdat de puls onderdrukt was (6474706, 4b43129). **[les]** Een naam wisselen is geen gedrag fixen; de demo draaien was de enige verificatie die de stille bugs ving.

**[beslissing] field_note: feitelijk, niet kaal.** De identiteit-fix liep eerst uit op het uitkleden van de Field Note (duiding en actie-voor-morgen geschrapt onder "geen duiding"). Herkaderd (52b5d61): Corry's nuchtere feitelijke stem stuurt de toon, maar de drie inhoudspunten blijven, met duiding tweemaal expliciet gegrond in de data. Feitelijke toon is iets anders dan geen duiding.

**[opruiming] dode klasse is niet dode route.** Bij het slopen van de klassen TijdgeestWachter en KennisScout plus hun activate-helpers bleek één test (Secretary._pending re-populate na herstart plus remove_role met archived) een levende mechaniek te dekken via een dode klasse. Verplaatst naar test_secretary.py met een generieke id, niet verwijderd; de andere zes groep-B- en scientist_fase2-tests waren echt redundant of dood (7102245, 1ed484d). 349 tests groen. **[les]** Verwijder op de route eronder, niet op de klasse erboven.

**[parkeren]** Niet gefixt: (a) gsc_pulse_completed staat niet in Noochie's _TRACK, bewust weggelaten omdat het te frequent is voor de bulletin-toon (zo al uit Ronnie mee); een klein gat dat later gedicht kan worden als de toon erbij gebaat is. (b) ngram_2019_cutoff blijft een means_gap die Harry zelf naar de inbox signaleert, by design, te dichten door Harry's ngram-meting aan te vullen met academische frequentie. (c) De echt-cosmetische residu-veeg (comments, docstrings, test-string-fixtures, lokale varnamen) staat nog open. (d) OpenLibrary-voltekst-v2 staat ongebruikt klaar, lage prioriteit.

**[richting]** The Source maakt de mens expliciet als rol in het dorp, onbemand en seed, en belegt de twee niemand-bezit-policies. Daarmee schuift NoochVille verder op naar een domein-agnostische governance-substraat waarin de mens het oordeel houdt en de gate dom-en-cheap blijft.

## 2026-06-21 — Insight-datamodel: kenniskaartje met grounding en bewijslaag

**[ombouw]** PermanentNote hernoemd naar Insight, eerst de klasse (a6d4aec), daarna het bestand permanent_note.py naar insight.py via git mv met behoud van history (2807078).

**[bouw]** Grounding-status toegevoegd (GroundingStatus unresolved/supported/verified) met een oplopende validator: supported eist grounds, verified eist grounds plus warrant plus rebuttal (82771b5). Daarna de evidence-laag: EvidenceType (claimed/reported/measured/certified/peer_reviewed) plus een reference-veld, en twee poortregels op verified, evidence_type verplicht en CLAIMED kan nooit verified worden (a6f7bd3). 349 → 353 → 357 groen.

**[ontwerp-besluit]** Tweede laag getoetst aan drie echte voorbeelden (een inzicht, de pillar-blog, de productpagina) plus het DPP-passport. Knip: kaartjes dragen grounding, teksten dragen bestemming en woordkeuze. Een eerste content-model-met-bestemming gebouwd en bewust verworpen. Gekozen voor optie 1 (keuring plus verboden-woordenlijst, geen opgeslagen koppelingen); naspeurbaarheid als optie 2 geparkeerd.

## 2026-06-21 — deel 2: keuring-laag, brug compleet, deterministische vulling, LLM-suggestielaag

Voortbouwend op het Insight-datamodel. De keuring-laag (optie 1) gebouwd:
find_forbidden_words (woordgrens-scan, plasticvrij blijft schoon), unverified_claims
(claim-ids tegen verified status), review_publication (beide checks per PublicationKind,
streng voor sales_page en passport, blog laat door). 357 naar 370.

De brug van kaartje via concept naar keyword compleet: concept_id plus by_concept op
Insight, link_concept plus keywords_for_concept op Library, plus een curate-bugfix die
voorkwam dat her-curatie de koppeling wist. 370 naar 378.

Deterministisch gevuld: backfill (exact lexicon-match, vegan plus regeneratief) en
parent-erving tot fixpoint (12 schone koppelingen via duurzaam, veganistisch, plasticvrij,
regeneratief). De burger- en consument-kinderen bleken homoniem-ruis (hamburgers,
ACM-toezichthouder) en zijn als suggestie geisoleerd, niet gekoppeld. 14 van 86 gekoppeld.
burger_frame stond al op avoid in het lexicon, wat dat besluit bevestigt.

De LLM-suggestielaag (concept_suggest) gebouwd voor de 72 resterende: biedt alleen
approved concepten met hun rationale als doel, een whitelist-guard weert hallucinaties,
fail-closed bij geen key of twijfel. 378 naar 384. Eerste echte run wacht op productie;
zonder key lokaal viel de keten correct terug op nul voorstellen.

Open: de LLM-run op productie, en het koppel-mechanisme voor een goedgekeurd voorstel
(raakt optie 2 / draad 4).

Commits: 6d8b7f0 (find_forbidden_words) · 5370dfe (unverified_claims) · dce2de2 (review_publication) · 60b5df5 (concept_id + by_concept) · fd80508 (link_concept + keywords_for_concept + curate-fix) · a9105d2 (backfill exact-match) · cac60f5 (concept_suggest) · c75399b (parent-erving) · 4125efc (batch-script suggest_concepts)

## 2026-06-22 — kraan-ombouw: van droog-en-rommelig naar Engels-worldwide op schone seeds

**[diagnose]** Brok 0 (vorige sessie) zei: alle bronnen leveren, het is wiring. Deze sessie groef dieper en draaide die conclusie deels om. De kraan was niet stuk door wiring maar mager door bron-eigenschappen: pytrends levert grillig (1 op 3 runs een vers woord), ngram publiceert niets zolang stijgende termen al in de bieb staan, GSC toont alleen waar je al rankt (zelden iets nieuws). Geen draad-fix loste dat op; het vroeg om de juiste knoppen en seeds.

**[bouw] rising erbij** (eb2a6f3): trends-skill leest nu ook `related[kw]["rising"]` naast `top`. De Breakout-string wordt een hoge sentinel (10000) met een vlaggetje, zodat het sterkste discovery-signaal niet wegvalt of crasht. Geen extra pytrends-call, dezelfde respons bevatte top én rising; de helft werd weggegooid.

**[bouw] knoppen instelbaar** (ad87728): `timeframe` en `hl` via payload, oude waarden als default. Dagcyclus geeft nu expliciet de discovery-stand mee. Was nog niet aangezet in de loop — feature gebouwd maar niet gebruikt.

**[bouw] schoen-domeinfilter** (aa13ab3): grof deterministisch filter in `prioritize`, zelfde patroon als de policy-drop. Keyword-acties zonder schoen-categoriewoord vallen vóór scoring. Bewust grof (vangt brood/kernenergie/funderingsherstel, laat aan de randen een kale merknaam vallen). Filtert afgeleiden, niet de seeds zelf.

**[bouw] vier scherpe seeds + locale-fix** (3465429, 5f49630): `config/keywords.txt` naar vier bewezen categorie-seeds (barefoot shoes, sustainable shoes, eco friendly shoes, barefoot sneakers). En de lege-geo-bug: `geos:[""]` (worldwide) leidde via `_geo_to_locale("")` af naar "nl", waardoor de Nederlandse Library-woorden als seeds meedraaiden. Mapping `"":"en"` gezet, past bij de Engelse koers.

**[data] vliegwiel opgeschoond** (data-only, library.json is gitignored): van 16 approved Library-woorden naar 6 schone schoen-termen. 10 off-schoen NL-woorden ('duurzaamheid', 'regeneratief', 'nos shoes', 'duurzaam gewas in opmars', etc.) op `avoid`, zodat ze geen pytrends-quotum meer vreten. Het vliegwiel (approved woorden dienen als extra seeds) is gewenst gedrag — auto-expansie van de database — maar draaide op oude NL-rommel.

**[meting/diagnose] missie-termen hebben geen zoekvraag.** Betaalde KeywordsEverywhere-clickstream-meting (~24 credits over de sessie): 'plastic free shoes' 170/mo, 'plastic free sneakers' 20, alle NL- en DE-plasticvrij-termen 0. Controle: 'barefoot shoes' 165000, 'vegan shoes' 8100, 'sustainable shoes' 3600. Hard antwoord: missie-termen zijn positionering, geen zoektermen. Sturend voor de strategie: categorie-termen via discovery, missie-termen via content (leen het categorie-volume om de missie te introduceren).

**[les]** Elke keer dat we de Library bekeken, vonden we nog een off-schoen woord. Het vliegwiel is zo schoon als de curatie; het domeinfilter vangt afgeleiden maar niet de seeds zelf. Kandidaat voor later: domeinfilter ook aan de seed-kant.

**[les]** Leersnelheid komt van weinig sterke seeds, niet veel matige. Een sterke seed (barefoot, rijke waaier) baart de volgende generatie scherpere seeds en spaart quotum; een magere seed levert één term en vreet evenveel quotum. Tegen-intuïtief: je komt het snelst aan veel scherpe seeds door met weinig sterke te beginnen.

Tests: 394 → 399 (domeinfilter) → 401 (locale-fix). Alles gemerged en gepusht.

Commits: eb2a6f3 (rising_related + Breakout-normalisatie) · ad87728 (timeframe + hl instelbaar) · aa13ab3 (schoen-domeinfilter) · 3465429 (vier EN seeds + dagcyclus worldwide/en-US/3-m) · 5f49630 (locale-fix: worldwide → en)
