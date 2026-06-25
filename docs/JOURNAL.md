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

## 2026-06-22 (middag) — de leeskant van de kennislaag: van schrijf-only naar lezen, groeien, verbinden

**[diagnose]** De kennislaag was schrijf-only. Eén `notes.add` in de Librarian, geen enkele leesaanroep, geen verrijk-methode. Kaarten werden geschreven en niemand keek ze terug. De lakmoesproef die Stefan wilde — een kaart die door een rol gebruikt wordt — bestond dus nog niet als mechaniek. Besloten: bouw de leeskant, in vier vormen, in volgorde van afhankelijkheid (alle drie de doelvormen delen "een kaart vinden + lezen" als basis).

**[bouw] stap nul — leesbasis** (828a085, fc7c434): `word`-veld op Insight (gevuld bij grounding, backward-compatible — oude kaarten laden op None). `NotesStore.relevant_for(word)` vindt verwante kaarten via gewogen woord-overlap. Zelf-metend op zeldzaamheid: een gedeeld woord telt zwaarder (1/doc-frequentie) naarmate minder kaarten het bevatten. Geen vaste stopwoordenlijst — wat "generiek" is, leidt het systeem zelf af uit de kaarten, en groeit mee als het dorp verbreedt (vandaag is 'shoes' generiek, in een breder dorp wordt het onderscheidend). Matcht op het word-veld, niet de claim (te ruizig).

**[bouw] vorm 2 — lezen-en-gebruiken** (3f1c85b): de Librarian raadpleegt bij het beoordelen van een woord zijn verwante kennis (relevant_for) en logt wat hij vond (📚). Bewust het zichtbare niveau: het oordeel wordt NIET gestuurd. Reden: unresolved kaarten (plausibel-maar-soms-onjuist) mogen nog geen beslissing kleuren; eerst meten of de matching zinnig is. Het beslissende niveau is een bewuste latere stap.

**[bouw] vorm 1 — lezen-en-verrijken** (fff9f0c): een tweede grounding van hetzelfde woord verrijkt de bestaande kaart ipv weggegooid te worden (de oude stille `except ValueError: pass`). `enrich` voegt de bron toe, hoogt `grounding_count` op, zet `last_updated_at`. Claim en status blijven ongemoeid — verrijken, niet overschrijven. Bewust smal: alleen bewijs-telling, geen inhoudelijke groei. De teller is meteen de fundering voor het geparkeerde drie-keer-emergentie-idee.

**[bouw] vorm 3a+3b — lezen-en-verbinden, voorstel-kant** (fff9f0c, 273dac2): de Librarian reflecteert op `dag_eindigt`, vindt deterministisch kandidaat-paren (relevant_for, ontdubbeld via frozenset). De LLM-skill `verband_voorstel` beoordeelt per paar of er een zinvol, niet-triviaal verband is — zo ja met een voorgestelde verbindende claim. Fail-closed op vier paden (geen LLM / onparseerbaar / nee / lege claim → geen voorstel). Begrensd tot 3 paren/dag (kosten). Bevestigd verband → `human_decision_needed`-event (topic 'verband', beide kaart-ids + voorstel-claim), klaar voor de inbox. De skill kreeg een plek in de Librarian's DNA (seeds.py) én de registry (village.py) — een skill moet op beide landen, anders faalt use_skill in een live-run.

**[inzicht] meerstemmigheid komt via meer gronde-rollen + links, niet via dikkere kaarten.** Stefan's vraag: voegen verschillende rollen ook inhoud toe ("deze bron zegt dit over dit onderwerp")? Nu niet — alleen de Librarian grondt (via Harry's evidence), en vorm 1 telt alleen bewijs. De rijke variant zou zijn: elke rol legt een deel van wat ze al waarnemen (Noochie's missie-observatie, Corry's trend-bevinding) vast als atomaire, verbindbare kaart ipv vluchtige tekst in bulletin/Field Note. Cruciaal inzicht: dat raakt het fundament NIET, want elk perspectief is een eigen atomaire kaart, en de rijkdom ontstaat TUSSEN kaarten via vorm 3 (links_to), niet binnen dikkere kaarten. Atomariteit (Ahrens) blijft heel. Belegd als richting in STATE.

**[live-run]** Eén `once()`-run na de bouw: keten draait stabiel op de nieuwe code, geen crash, 423 groen. Maar geen 📚/🌱/🔗 in de log, om twee verklaarbare redenen, geen losse eindjes: (1) library-saturatie — Harry's ngram vond 'vegan' stijgend, maar dat is al approved, dedup blokkeert → geen nieuwe grounding → geen kaart → geen lees/verrijk-signaal; (2) run-vorm — `dag_eindigt` valt alleen in `run_forever()` en pas vanaf dag twee (eerste `_ring` slaat 'm over), dus `once()` triggert de dag-reflectie structureel nooit. De leeskant is gebouwd-en-getest; live zichtbaar pas in een langer draaiend dorp. Observatie voor later: als het dorp vooral via `once()` draait, vuurt de dag-reflectie zelden — is `dag_eindigt` het juiste trigger-moment?

**[les]** Vorm 1 en vorm 3a raakten verweven in één commit (fff9f0c) omdat er na vorm 1 niet tussendoor gecommit werd voordat 3a begon. Splitsen-achteraf van verweven werk is foutgevoeliger dan de winst; eerlijk als één commit gelabeld. Les: af-is-af, commit elke vorm zodra hij groen is voor de volgende begint.

Tests: 403 (word-veld) → 408 (relevant_for) → 410 (vorm 2) → 413 (vorm 1) → 416 (vorm 3a) → 423 (vorm 3b).
Commits: 828a085 (word-veld) · fc7c434 (relevant_for, zelf-metend) · 3f1c85b (vorm 2, Librarian leest) · fff9f0c (vorm 1 enrich + vorm 3a dag-reflectie, verweven) · 273dac2 (vorm 3b verband_voorstel LLM-skill) · 389f084, 5cfa392 (STATE-updates: K2 af, emergentie-teller, leeskant + drie richtingen)

---

## 2026-06-23/24 — lange sessie: van één inbox-spanning naar de grondwet

**[procesobservatie]** Werkwijze: één spanning per keer, écht serieus nemen ("tijd maakt niet
uit"), elke stap klein + getest + mutatie-check + commit. Eén inbox-item serieus nemen leidde tot
diepere lagen die vooraf niet zichtbaar waren — dat is de kern van de methode geworden.

**[bouw]** Trends-saga. pytrends wordt door Google hard geblokkeerd (429, bevestigd live).
Drie stappen: (1) Field Note ontkoppeld van Trends via `run_bounded` (harde tijdslimiet) — een
unit-bug ontdekt: de puls hing in pytrends-backoff (~10min) voorbij de 180s once()-timeout, dus
géén Field Note; (2) roterend keyword-venster + UA hielpen niet (Google blokkeert hard); (3)
SerpApi als betrouwbare bron, wekelijks/zuinig, per-taal-geo. pytrends dormant gemaakt (via
governance uit website_watcher's DNA gehaald).

**[fix]** Gemini SSL-timeout was geen netwerk maar een unit-bug: `HttpOptions.timeout` is in
MILLISECONDEN; stond op 30 (=30ms) → elke call timeoutte op de TLS-handshake. Nu 30000.
Gemini is meteen ook de default-LLM gemaakt (Anthropic fallback), want ~10-30x goedkoper en
ruime gratis tier; Anthropic-credits raakten steeds op.

**[ontdekking]** Het "bijzondere" van zelf-gesensde spanningen ligt niet bij het gat zelf maar bij
de autonome afhandeling eromheen. `ngram_2019_cutoff` bleek HARDGECODEERD in Harry's `_reflect`
(een mens-geschreven bekende limiet), niet dynamisch ontdekt. De gap-classifier + coherence-observer
+ routing zijn wél autonoom. Onderscheid hardcoded-gat vs dynamisch-gat als vaste rubriek opgenomen
in `docs/inbox_analyse.md`.

**[bouw]** Harry's spanning helemaal afgemaakt i.p.v. afgevinkt. ngram-correlaties (co-beweging +
substitutie over decennia; `leather free ~ vegan` r=0.97 live), OpenAlex jaar-aandeel (relatief),
overlap-kalibratie (eerlijkheidstoets vóór vertrouwen), gekalibreerde voortzetting voorbij 2019.
Harry's rol verdiept van "mist 7 jaar" naar een scherpzinniger waarnemer. Rol-definitie via
amend_role (governance) bijgewerkt.

**[beslissing/grondwet]** Stefan: "de inbox is mijn expliciete akkoord — weet je waarom?" → het
systeem mag z'n eigen huiswerk niet beoordelen; menselijke goedkeuring breekt de zelfbevestigende
lus open. Claude had ten onrechte zelf een inbox-item gesloten → teruggezet op pending.

**[bouw]** Regel 5 (rol-vraagt-rol om een accountability) als dorpsbrede laag. Inzicht van Stefan:
een event wordt door een rol getriggerd, en de mens is óók een rol → a/b/c collapst tot twee modi
(autonoom + op-verzoek-door-elke-rol). Mens-zetel toegevoegd (`Record.held_by`, `seat_human`) zodat
de founder legitiem in `the_source` zit.

**[bouw/grondwet]** "Ik dek dit nu, voorstel tot sluiten": rol stelt voor, mens bevestigt
(`propose_close` → `inbox confirm`). Stefans vervolgvraag "zou de rol ooit nee zeggen?" legde een
te-eager wiring bloot: `nl_corpus_coverage` werd onvoorwaardelijk voorgesteld te sluiten, terwijl de
check juist bewees dat het corpus kapot is. Fix (optie a): sluit de validatie-vraag, maar werp het
échte, scherpere gat op (`nl_corpus_bron_onbruikbaar`). Spelregel: `propose_close` draagt het
oordeel van de rol, geen stempel; een rol mag nee/openhouden/escaleren.

**[bouw]** De grondwet `docs/spelregels.md`: 10 substraat-onafhankelijke spelregels (machine/AI/mens,
zelfde regels per rol). Distillaat van CLAUDE.md + de inzichten van deze sessie.

**[les]** STATE liep weer achter op de code (het terugkerende thema). Bijgewerkt naar de actuele
waarheid; de oude detail-status als historisch gemarkeerd.

Tests: ~502 → 688, elke stap met mutatie-check.
Commits o.a.: a5d7c06 (Field Note ontkoppeld) · c147151 (Trends-rotatie) · 829776a (SerpApi) ·
abb0640 (Gemini default) · 1ee2358 (Gemini ms-fix) · 6963e05 (grondwet) · 26499d0 (mens-zetel) ·
bc47cf5 (regel 5) · 67ab5da (propose_close) · 76dd301 (rol mag nee-maar zeggen) ·
90ab730 (OpenAlex-voortzetting) · 8281673 (NL-check) · 6f56765 (inbox approve-vangnet)

---

## 2026-06-24 (latere sessie) — cockpit-verwerking, LLM-ladder, markt- & linkbuilding-radar

**[bouw]** Getrapte LLM-ladder in `llm.py`: `reason()` loopt `gemini:flash-lite → mistral →
gemini:flash → anthropic:haiku` af, goedkoop eerst, stopt bij de eerste die antwoordt. Rate-limit/
quota → trede in cooldown + door (`LLM_TIER_COOLDOWN_S`). Fail-closed. Killt het Sonnet-kostenlek
(defaults goedkoop). Instelbaar via `LLM_LADDER`. Aanleiding: twee `run`-processen draaiden sinds
maandag op Sonnet en aten credits.

**[ontdekking]** Gemini's gratis tier is 20 calls/DAG (niet per minuut). De ladder ving die muur
live op: flash-lite 429 → cooldown → door naar Mistral/Haiku, puls liep gewoon door.

**[bouw]** Opstart-sleutelrapport (niet-blokkerend) + CLI `keys`. Skills declareren zelf
`required_env`/`optional_env` (zelfbeschrijvend, geen drift-gevoelige losse map). Presence-only.

**[bouw]** Cockpit uitgebouwd tot verwerk-oppervlak (localhost + CSRF, schrijft alleen via
`inbox_actions`): escalated-woordenschat afroombaar, Concurrenten bevestig/negeer, Linkbuilding
pitchen/negeer. Nooch design-tokens toegepast.

**[root-cause]** "De lus levert niets nieuws" onderzocht: 59 van 98 library-termen stonden op
escalated, en escalated was terminaal + dedup-blokkerend → de lus at z'n eigen input op. Stefan
heeft de berg via het dashboard afgeroomd (59 → 0). Tweede oorzaak: de KE-volume-auto-approve was
geneutraliseerd door `ke_country=nl` (KE geeft voor NL overal 0; global werkt wél). `ke_country` nu
leeg/global → de auto-approve vuurt voor het eerst echt.

**[bouw]** Nieuwe inwoner Concurrent-scout (*Sven Spruce*): `competitor_news` (getrapt venster
maand→kwartaal→jaar, harde datumfilter, dedup, footwear-context tegen homoniemen),
`competitor_discover` (SerpAPI echte URLs → pagina lezen → LLM merk-extractie; mens bevestigt),
`linkbuilding_targets` (gidsen als pitch-doelwitten, prio = noemt concurrent zonder Nooch), plus
marktinteresse via KE. Live bewezen: 4 echte concurrenten bevestigd (LØCI, Lane Eight, Alohas,
Merrell), 15 linkbuilding-gidsen gevonden, marktinteresse met echte getallen (LØCI 1M/mnd).

**[faalmodus→fix]** Eerste `competitor_discover` raadde merknamen uit titels → rommel ("Ultimate",
"Good", "Business", "Insider", publicatienamen). Daarna pagina-lezen via Google News-links → die zijn
redirects, lezer komt er niet bij → niets. Pas SerpAPI (echte URLs) + LLM-extractie gaf de echte
merken. Les: de bron bepaalt of extractie kán; Google News RSS is voor titels, niet voor body.

**[bouw]** Gedeelde `context.competitors`-store: bevestigde concurrenten leesbaar voor elke rol,
voeden de Trends-zaadlijst (consument 2, licht: gerelateerde termen rond concurrenten → Librarian).

**[bouw]** Spaced-repetition-scheduler (`keyword_scheduler.py`) vervangt het platte roterende venster
— idee van Stefan. Nieuw/productief zaadwoord vaak, uitgekauwd zakt weg (interval verdubbelt tot
plafond, reset bij nieuwe oogst). Subsumeert de concurrent-voorrang (nieuw = vanzelf voorrang).

**[les]** Drie keer dezelfde diagnose-stap nodig op concurrent-ontdekking (titels → Google News-body
→ SerpAPI) voordat het klopte. Sneller naar "kan de bron dit überhaupt leveren?" springen had een
ronde gescheeld. Stefans "maar het dorp is toch nog bezig?" was een terechte check die liet zien dat
een deel van het probleem oude persistente data was, niet de live run.

Tests: ~688 → 862, elke stap met mutatie-check.

---

## 2026-06-24 (avond, vervolg) — governance-herkomst rechtgezet (A) + bewaakt (B)

**[ontdekking/proces]** Stefan: "hebben we de nieuwe rol + skills wel via governance laten lopen?"
Nee. De Concurrent-scout + skills + de Librarian-KE-grant waren via seed/migratie toegevoegd, een
afwijking van de eigen regel "rolwijziging alleen via governance" (precedent: Content Strategist
ging wél via de gate). Eerlijk benoemd i.p.v. weggepoetst.

**[bouw] A — formaliseren achteraf.** `build_concurrent_scout_proposal` (add_role: herhalingsbewijs
in de trigger voor G0, uniek domein voor G1, niet-botsende accountabilities voor G2, de 4 skills)
+ de Librarian-KE als amend_role, samen in `formalize_session_governance` / CLI `formalize`. Loopt
alsnog door G0-G4 + Secretary; herbouwt het scout-record getrouw met `source=sensed` + groeidagboek-
audit. Deterministische test (gate + adopt, geen threads).

**[bouw] B — de herkomst-wachter.** `BOOTSTRAP_ROLES` (de zes founding-rollen) +
`role_provenance_violations()`: elke niet-bootstrap, niet-gearchiveerde rol moet `source=sensed`
zijn; seed-gehardcodeerde structuur wordt gevlagd. Boot-audit in `Village.start()` waarschuwt luid.
concurrent_scout uit seed/migratie gehaald: hij wordt voortaan via `formalize` (de gate) geboren,
niet geseed. Test dwingt af: seed+migratie leveren 0 violations; de wachter betrapt een smokkelrol.

**[les]** De afwijking ontstond in bouwflow (snel seeden i.p.v. via de gate). De wachter maakt het
nu zichtbaar én onmogelijk om stil te herhalen, precies de structurele rugdekking onder born-vs-
activated die al als schuld op de lijst stond. Detectie nu; harde preventie (records alleen via de
Secretary) en skill-grant-provenance blijven als vollere B-stap open.

Tests: 862 → 874. Actie op live-data: `python -m nooch_village.village formalize`.

---

## 2026-06-25 — Sessie: test-isolatie, cross-path-memory, weekrapport

**[fix] Test-data-isolatie.** Vondst: de echte `human_inbox.json` bevatte 130+ `nonexistent_test_rol`-
items. Oorzaak: `test_the_source` (en 9 andere tests) bouwden een volledige `Village()` zonder data-dir-
override → schreven in de productie-`data/`. Conftest autouse-fixture wijst `BASE_DIR` nu per test naar
een eigen tmp-map (echte config gesymlinkt zodat settings/strategy blijven laden). Bewijs: inbox bleef
170 tijdens de hele suite (geen groei). 120 junk-items opgeschoond (50 echte over, `.bak` bewaard).

**[fix] Cross-path-memory voor means-gaps.** Harry sensde `nl_corpus_bron_onbruikbaar` 11×: de inbox
dedupliceerde het item al, maar het EVENT bleef komen → de B-observer her-evalueerde het telkens als
ruis (resolve-dan-opnieuw-lus). `_report_means_gap` checkt nu de inbox-historie (type means_gap +
subject, ongeacht status): staat het er al, dan stil. Spiegelt `add_means_gap` aan de sense-kant.

**[feat] Weekrapport in de cockpit.** `compute_digest()` (pure functie, geen I/O) + `_render_digest()`
bovenaan `render_html`: één overzicht over de afgelopen 7 dagen — nieuw goedgekeurde woorden (met
vraag-signaal), nieuwe linkbuilding-doelwitten (★ hoog eerst), marktinteresse (nieuw + gemonitord).

**[les]** Twee van de drie waren onzichtbare ruis: testjunk in productie-data en een gat dat eindeloos
opnieuw gesensed werd. Beide opgelost bij de wortel (isolatie-fixture; sense-kant-geheugen), niet met
een eenmalige opruiming. Het weekrapport maakt de waarde die het dorp produceert in één blik zichtbaar.

Tests: 874 → 889.

---

## 2026-06-25 (vervolg) — Kans-score per zoekwoord

**[feat] Meetbare kans i.p.v. losse interesse.** Het weekrapport toonde alleen `evidence.interest`
(trends 1-100 / GSC-impressies), inconsistent. Nu een kwantitatieve kans: `opportunity_score(volume,
competition) = round(volume*(1-competition))` — "haalbaar maandelijks verkeer". `_enrich_volume`
bewaart bij goedkeuren volume + competition + kans. CPC bewust verwijderd (niet relevant voor ons).

**[feat] GSC-stand per term.** Op verzoek: naast volume/concurrentie ook onze huidige Google-stand
voor exact die zoekterm (positie + klikken/impressies), of "nog niet in Google top-resultaten" =
onontgonnen. Eén GSC-call, per woord gematcht op de query. Maakt zichtbaar: veel kans én ranken we
nog niet = eerste prioriteit.

**[bouw] set_evidence + backfill.** `Library.set_evidence` merget evidence zonder status/datum te
raken (verrijking achteraf, niet de approval-datum resetten). `library_enrich.enrich_library` +
CLI `enrich_volumes [dry] [nogsc]` vult bestaande approved-woorden, mens-gated. Faalt closed per bron.

Tests: 889 → 895. Mac-actie: `./venv/bin/python -m nooch_village.village enrich_volumes`.

---

## 2026-06-25 (vervolg 2) — Functie-as: seed vs rank-doel

**[ontwerp+feat]** Probleem (Stefan): brede termen als 'vegan' (1,22M), 'microplastics', 'biobased'
verschenen als grootste 'kans', maar dat zijn seeds om de radar te voeden — geen woorden waar we op
willen ranken. Eén platte approved-lijst verbergt dat onderscheid. Oplossing: een functie-as per woord,
`volg` (seed) vs `doelwit` (rank), orthogonaal op status. Heuristiek classificeert (mega-volume of
één generiek woord → volg; specifiek meerwoord → doelwit), de mens corrigeert uitzonderingen met een
flip-knop in de cockpit (`Library.set_function` via inbox-actie `lib_function`). Weekrapport splitst in
'🎯 Doelwit-woorden — kans om te ranken' (kans/GSC) en '🌱 Volg-woorden — seeds voor trends/SerpAPI'
(geen misleidende kans). Discovery blijft uit álle approved zaaien (volg-woorden waren al seeds).

**[les]** Het was geen bug in de kans-formule maar een ontbrekend concept: input (seed) vs output
(rank-doel). Zelfde input-versus-output-scheiding als elders. 17 bestaande woorden geclassificeerd
via de heuristiek (vegan/microplastics/biobased → volg, rest → doelwit).

Tests: 895 → 900.

---

## 2026-06-25 (vervolg 3) — Cockpit-herinrichting

**[feat] Weekrapport = dashboard.** Puur kwantitatief: KPI-tegels (nieuwe doelwit-woorden, volg-woorden,
linkbuilding-doelwitten, concurrenten) + Noochie's dagverdict. Noochie schrijft zijn missie-lens-oordeel
nu weg (`noochie_daily.json`); de cockpit toont het als dagelijkse update.

**[feat] Woordenschat gesplitst.** 🎯 Doelwit-woorden: volume + kans + onze GSC-stand. 🌱 Volg-woorden:
de 12-maands trend% (`trend_change_pct` over de KE-trendreeks) i.p.v. een 7-daagse momentopname — zo zie
je de échte beweging van een seed. `enrich_volumes` slaat de trend nu op.

**[feat] Concurrenten: volledige monitor + nieuws.** Per merk (config ∪ bevestigd) het laatste nieuwsfeit.
Nieuwe store `competitor_news.json`, geschreven door de scout in `_run_news`; eenmalig gevuld uit het
laatste veldrapport (8 merken, 6 met nieuws).

Tests: 900 → 904. Mac: na `enrich_volumes` verschijnt de seed-trend%; elke pulse ververst het nieuws.
