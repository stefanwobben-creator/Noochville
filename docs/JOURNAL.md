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
