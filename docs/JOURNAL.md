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

---

## 2026-06-25 (vervolg 4) — Seed-trend als meerjarige toestand

**[feat]** Op advies (trendwatcher-lens): een jaar is te kort om een fad van een structurele trend te
scheiden. Volg-woorden krijgen nu een trend-TOESTAND uit een 5-jaars Google Trends-reeks, niet één
percentage. `trend_analysis.trend_state` leest de vórm van de curve (totale helling, recente helling,
piekpositie) → opkomend / stabiel / piek-voorbij / dalend. `serpapi_trends.series(timeframe='today 5-y')`
haalt de TIMESERIES op; `enrich_volumes` slaat de toestand op voor seeds (doelwit-woorden niet). Cockpit
toont de toestand met pijl; 12-mnd% blijft fallback tot een seed verrijkt is.

**[les]** Eén bron/één getal is fragiel (seizoen, endpoints). De toestand-classificatie uit de curve-vorm
is robuuster dan een kaal percentage — precies wat een trendwatcher zou doen.

Tests: 904 → 912.

---

## 2026-06-25 (vervolg 5) — Noochie-dagrapport: 3 bevindingen + 1 suggestie

**[feat]** Noochie's dag-rapport in het weekrapport toonde alleen de aanbevolen actie (vaak een
website-tweak). Op verzoek kijkt Noochie nu naar het GEHEEL (verkeer, markt, missie, kansen, risico's)
en rapporteert drie scherpste bevindingen + één concrete suggestie (als zodanig gelabeld). Eén LLM-call
levert BEVINDING×3 + SUGGESTIE + VERDICT/REASON; `_parse_noochie_report` haalt de bevindingen/suggestie
eruit (robuust tegen markdown/bullets). De verdict→spanning-detectie blijft ongewijzigd (tests intact).
noochie_daily.json bewaart nu findings[] + suggestion; cockpit toont bevindingen als lijst + suggestie.
Back-compat: oude 'oordeel' valt terug op een losse regel.

Tests: 915 → 918.

---

## 2026-06-25 (vervolg 6) — Seed-opleving als spanning: Harry + scout onderzoeken

**[feat]** Een seed met een AANHOUDENDE recente opleving (3-maands gemiddelde ≥30% boven het jaar
ervoor — losse uitschieter telt niet mee) is nu een spanning. `trend_analysis.recent_surge` detecteert;
`enrich_volumes` zet `evidence.recent_surge` + schrijft de term naar `data/seed_surges.json`. Op de puls
publiceert Harry `seed_surge_sensed` en grondt de term academisch (zijn grounding-tak → keyword_evidence /
insight). De ConcurrentScout luistert mee en zoekt in het nieuws (RSS via competitor_news) de actuele
aanleiding → `set_explanation` + `seed_surge_explanation`. Cockpit toont '▲ recent stijgend' bij de seed
+ de mogelijke nieuws-verklaring. Twee onderzoekshoeken: Harry = lange/academische context, scout = actueel
nieuws. refresh.sh draait nu enrich vóór de puls zodat een verse opleving in dezelfde run wordt geduid.

Tests: 919 → 924.

---

## 2026-06-25 (vervolg 7) — Ademend dorp: Fase 1 (business-case-frame)

**[ontwerp]** docs/ADEMEND_DORP.md: de kansen-motor. Diagnose via experiment (15 kaartjes, allemaal
grounding_count=1, gem. gelijkenis 0.06, 13 onbenutte bridge-paren → kennisbank ademt niet). Zes
bouwstenen + 5 fasen + vitaliteits-KPI's. Noordster: 1M paar/jaar; batch 4 = 1000 (sep-dec).

**[feat] Fase 1 — business-case-frame.** Spanning → afweegbare kans.
- `business_case.py`: make_business_case (normaliseert, tiers xs..xl), business_value (effect×confidence÷effort),
  format_business_case.
- `Proposal` krijgt hypothesis + business_case; proposal_to_dict/from_dict roundtrippen ze.
- `config/strategy.json`: north_star (1.000.000 paar/jaar) toegevoegd.
- Cockpit: "🎯 Kansen-backlog" rangschikt voorstellen/projecten mét business-case op waarde, met de
  noordster in de kop. Lege staat verwijst naar Fase 2.

Tests: 928 → 933. Volgende: Fase 2 (opportunity-reflex die de backlog vult), dan Fase 3 (Synthesist).

---

## 2026-06-25 (vervolg 8) — Ademend dorp Fase 2: opportunity-reflex

**[feat]** Elke rol heeft nu een opportunity-reflex (`Inhabitant._opportunity_reflex`, aangeroepen in
`_maybe_reflect`, dus op het reflect-interval, default wekelijks). De rol vraagt de LLM, gevoed met zijn
purpose/accountabilities/skills + de noordster (1M/jaar) + actief doel, om de ÉNE hoogst-renderende kans:
TYPE (project/amend_role/add_role), TITEL, HYPOTHESE, EFFECT/EFFORT/CONFIDENCE/RATIONALE. Resultaat:
- project → ProjectLedger.create (met hypothesis + business_case), dedup op open scope.
- amend_role/add_role → governance-voorstel mét business_case (mens-gated via de gate), dedup per proces.
Alles landt in de cockpit-kansen-backlog, gerangschikt op waarde. Harde regel intact: sensen+voorstellen,
nooit zelf uitvoeren; fail-closed zonder LLM. `_parse_opportunity` robuust tegen markdown.
ProjectLedger.create + open_scopes uitgebreid; make_business_case leest nu ook numerieke strings.

Tests: 933 → 937. Demo: zet reflect_interval_seconds=0 in settings.ini om 'm op de eerstvolgende puls te laten vuren.

---

## 2026-06-25 (vervolg 9) — Ademend dorp Fase 3: Synthesist (creatieve links)

**[feat]** De kennisgraaf gaat ademen. `card_synthesis.py` (puur, gesmoothede TF-IDF): bridge_pairs
(verwant-maar-niet-gelijk, nog niet verbonden), duplicate_pairs, graph_density. `SynthesizeCardsSkill`
(synthesize_cards): twee kaartjes → ÉÉN emergente hypothese (geen samenvatting), fail-closed.
`synthesist.py`: pakt het sterkste bridge-paar, maakt een nieuw synthese-kaartje (tag 'synthese',
links_to=[ouders]) → de ouders zien het als buur. Dedup (geen dubbele bridge). CLI `village synthesize [n]`
+ stap 3/3 in refresh.sh. Cockpit: 🔗-markering + graaf-dichtheid in Inzichten.
Diagnose blijft: 15 kaartjes, 0 links nu → na synthesize gaan de eilandjes verbinden.

Tests: 937 → 942. Mens-gedraaid (LLM-kosten) via refresh.sh / synthesize.

---

## 2026-06-25 (vervolg 10) — Mens-poort op kansen (opportunity-reflex hersteld)

**[fix]** De opportunity-reflex queue'de project-kansen direct als 'queued' projecten — dat omzeilde
de mens-poort (inbox = expliciet akkoord). Nu: een project-kans publiceert `opportunity_sensed`;
Village._on_opportunity zet 'm als `opportunity`-item (pending) in de human_inbox. De kans wordt
PAS een project als de mens 'm goedkeurt. Cockpit-kansen-backlog toont ✓ goedkeuren / ✗ negeer
(decide_opportunity: approve → ProjectLedger.create, reject → gesloten). Dedup op titel. Rol-kansen
(amend/add_role) blijven via de governance-gate (ook mens-gated). 6 reeds auto-gequeuede projecten
teruggezet naar inbox-kansen + projecten geparkeerd (future). Backlog telt geparkeerde/afgeronde
projecten niet meer mee (geen dubbeling).

Tests: 942 → 946 (test_opportunity_gate + bijgewerkte reflex-test).

---

## 2026-06-25 (vervolg 11) — Seed-opleving linkt naar de duiding

**[feat]** Bij een seed-opleving (▲/▼) toont de cockpit nu de duiding inline: 🔬 een link naar Harry's
academische inzicht-kaartje voor die term (per woord het sterkste, op grounding_count) en, indien de
scout nieuws vond, 📰 de nieuws-aanleiding. Zo kom je van het signaal direct bij de verklaring.
Geconstateerd: Harry's duiding bestond al (3 kaartjes met word=seed) maar was niet gelinkt; de
scout-nieuwsverklaring is nu nog leeg omdat de footwear-context-nieuwszoek niets vindt voor brede
seed-termen (tuning-follow-up: bredere nieuws-query voor seed-surges).

Tests: 946 → 947.

---

## 2026-06-25 (vervolg 12) — Scout: brede nieuws-duiding voor seed-verschuivingen

**[feat]** De scout-nieuwszoek bij een seed-verschuiving was leeg: hij gebruikte de merk-monitor
(competitor_news) met schoen- én bedrijfsfilters, te smal voor brede termen. Nu: `web_read.serpapi_news`
(Google News via SerpAPI, kale term, echte URLs) → `ConcurrentScout._pick_news_driver` laat de LLM uit
de top de waarschijnlijke AANLEIDING kiezen, gewogen op aanleiding-kracht (regelgeving > onderzoek >
incident > aandacht > markt; losse vermeldingen genegeerd). Fail-closed → nieuwste kop. Blijft bij de
scout (extern-nieuws-zintuig; geen nieuwe rol — dat ware proliferatie). Verklaring landt als 📰-link
naast de ▲/▼ in de cockpit, naast Harry's 🔬-duiding. Werkt voor oplevingen én dalingen.

Tests: 947 → 948. Mogelijke vervolg: scout-purpose formeel verbreden naar 'externe markt/trendsignalen'
via amend_role (governance), zodat de herkomst klopt.

---

## 2026-06-25 (vervolg 13) — Helderheid + dialoog: WAT in mensentaal, redenveld, leerlus, Aan-jou

**[feat] Voorstel-kwaliteit aan de bron.** De opportunity-reflex schreef afgekapte jargon-voorstellen.
Nieuwe prompt met schrijfregels (uitleggen alsof het een 12-jarige is, geen jargon, concreet, volledige
zinnen) en een gestructureerd WAT (het idee in gewone taal, max 600) + WAAROM (bijdrage). _parse_opportunity
parst WAT/WAAROM; cockpit toont de volledige WAT (niet truncated).
**[feat] Redenveld + leerlus.** Bij goedkeuren/negeren een optioneel redenveld; decide_opportunity bewaart
'm, en _rejected_opportunities voert afgewezen kansen + reden terug in de reflex-prompt ("niet herhalen,
leer hiervan") → de village kalibreert i.p.v. te herhalen.
**[feat] 'Aan jou'-balk.** Eén gele balk bovenaan telt alles wat nú jouw beslissing vraagt (kansen, inbox,
te-beoordelen woorden, concurrenten, linkbuilding) zodat je niet hoeft te scrollen.

Tests: 948 → 949. Bestaande 6 (pre-fix) kansen tonen nu volledig maar nog in oude bewoording; nieuwe
kansen komen in mensentaal. Op de Mac: refresh.sh draait de reflex + vult de nieuwe WAT-voorstellen.

---

## 2026-06-25 (vervolg 14) — Frame + UI-flow op kansen

**[feat] Burger-frame + jargonverbod in de reflex-prompt.** Voorstellen bleven zakelijk ("validatie",
"transacties"). Prompt verbiedt nu expliciet consument/transactie-jargon (validatie, conversie,
implementeren, funnel, KPI, doelgroep, consument...) en eist het BURGER-frame (mensen die bewust kiezen
en dragen, geen 'consumenten'/'transacties'). Opmerking: lexicon-seed markeert 'burger' óók als avoid —
waarschijnlijk een seed-bug (burger_frame hoort approved), los te fixen.
**[feat] UI-flow.** Kansen staan niet langer dubbel: alleen in de Kansen-backlog (met volledige uitleg),
niet meer in de gewone Inbox-tabel. Backlog toont het type expliciet (📋 project · door <rol> / 🏛️
governance). Bij goedkeuren een duidelijke melding: "→ project voor <rol> (zie Proces); de rol pakt 'm
op, jij blijft de poort." Bij negeren: "de rol leert van je reden". Mens-poort + flow-back zichtbaar.

Tests: 949 → 949 (bestaand groen).

---

## 2026-06-25 (vervolg 15) — Triage-prototype: doelwit-woorden ja/nee-met-reden

**[feat]** Eerste triage-prototype: doelwit-woorden krijgen dezelfde ✓/✗-met-reden-flow als kansen.
`decide_target`: ✓ 'maak content-project' → ProjectLedger.create (owner librarian, op het projectbord,
dedup op scope); ✗ 'laat vallen' → library.curate forbidden mét reden. Cockpit: redenveld + twee
knoppen + de bestaande flip naar volg. Doel: voelen hoe de ja→uitkomst / nee→reden-interactie werkt
vóór we alle beslis-plekken samenvoegen tot één triage-inbox (volgende stap). Engelse sweep daarna.

Tests: 949 → 952.

---

## 2026-06-25 (vervolg 16) — Triage v1: kies-bij-goedkeuren + leerlus via huis-regels

**[feat]** Triage als bron-verbetering (Stefans inzicht: rommel is prima, mijn oordeel maakt het dorp
slimmer). Per kans nu: ✓ **project** (kies de eigenaar-rol uit een dropdown) of 📚 **kennis** (kaartje),
en ✗ **negeer** met reden + checkbox "onthoud als huis-regel". Nieuwe `constraints.py` (Constraints-store);
`decide_opportunity` uitgebreid (destination project/knowledge, owner-keuze, remember_constraint).
**Leerlus gesloten:** een als-constraint onthouden reden komt in `data/constraints.json`, en de
opportunity-reflex leest die als "VASTE HUIS-REGELS (respecteer ALTIJD)" in z'n prompt → het dorp stelt
niets meer voor dat ertegen ingaat. Cockpit: 📏 Huis-regels-blok in Kennis.

Tests: 954 → 956. Volgende triage-stappen: nieuwe-rol/roloverleg + advies-aan-rol + doorgeven-aan-mens +
verduidelijk/herleid-dialoog; daarna alles samenvoegen (concurrenten/linkbuilding in de inbox) + Engels.

---

## 2026-06-25 (vervolg 17) — Triage: governance-uitkomst (rol aanmaken/uitbreiden)

**[feat]** Vierde ✓-bestemming toegevoegd: 🏛️ **governance**. Bij een kans kies je in de eigenaar-dropdown
"➕ nieuwe rol" (→ add_role) of een bestaande rol (→ amend_role: de kans wordt een accountability erbij).
`_route_kans_to_governance` bouwt het Proposal en draait het synchroon door Gate.check + Secretary._adopt
op de on-disk records (geen Village/bus). Poort akkoord → rol aangemaakt/uitgebreid (onbemand, born-vs-
manned blijft gelden); poort escaleert → melding dat jouw oordeel nodig is. Triage-uitkomsten nu compleet:
project (voor rol) / kennis / governance / negeer(+constraint).

Tests: 956 → 958.

---

## 2026-06-25 (vervolg 18) — Meerdere uitkomsten per kans (toevoegen vs afronden)

**[feat]** Eén kans kan nu meerdere uitkomsten krijgen (Stefans vraag: 2 projecten + een rol). decide_opportunity
splitst toevoegen van afsluiten: '+ project' / '+ kennis' / '+ governance' MAKEN een uitkomst maar laten het
item OPEN; '✓ afronden' sluit het (approved); '✗ negeer' sluit met reden (+constraint). Project-dedup nu op
scope+eigenaar, zodat 2 projecten voor verschillende rollen vanuit één kans kunnen. Sluit aan op het bestaande
principe 'één spanning, meerdere uitkomsten; afsluiten is een aparte stap'.

Tests: 958 → 960.

## Triage volgens Holacracy + vraag-aan-rol-dialoog + scroll-fix
De kansen-backlog is herbouwd naar het Holacracy-model. Per kans kies je nu Tactical
(Project voor een rol — AI formuleert de uitkomst; Informatie geven → kennisbank; of
Informatie vragen aan de rol) of Governance (Voorstel; bij '🤖 laat AI kiezen' bepaalt de AI
of een bestaande rol wordt uitgebreid of een nieuwe rol nodig is). '✓ klaar' haalt de spanning
uit je inbox; het enige 'weg' is je source-oordeel "past niet binnen de visie" (wordt huis-regel).

Vraag-aan-rol is een GEBUNDELDE dialoog, geen realtime call: de cockpit parkeert de vraag
(label 'wachten op antwoord'), en `village answer_questions` (ook stap 4/4 in refresh.sh)
laat de LLM álle openstaande vragen in één call beantwoorden, elk als de betreffende rol in
gewone taal. Fail-closed zonder LLM (blijft wachten). De dialoog staat onder de kans.

Scroll-fix: elke backlog-rij heeft id=kans-<iid> en de forms sturen een anchor mee, zodat de
303-redirect terugkeert naar exact het item (geen sprong naar boven na een actie).

Nieuw: human_inbox.add_question/answer_question/pending_questions; inbox_actions.ask_role,
answer_pending_questions, pick_governance_target, formulate_project; cockpit Holacracy-UI +
anchor. Tests: +test_triage_dialoog.py. Volledige suite groen (478 + 489 in twee helften).

## Triage opgeschoond: afgehandeld → weg, vraag beschermt afronden, project = concept
Drie verfijningen op de Holacracy-triage:
1. De Kansen-backlog is nu puur een triage-wachtrij: lopende projecten staan er NIET meer in
   (die leven op het projectbord/Proces). Zodra je een kans afrondt (✓ klaar) verdwijnt hij.
2. ✓ klaar is geblokkeerd zolang er een onbeantwoorde vraag op de kans staat — anders zou je
   het antwoord (dat in de volgende puls komt) mislopen. Na beantwoording mag afronden wel.
3. Een project uit triage wordt een CONCEPT (status 'draft'): het verschijnt in een nieuw blok
   'Concept-projecten — wacht op jouw akkoord' met de AI-geformuleerde uitkomst + business-case.
   Goedkeuren → queued (op het bord van de rol); aanpassen via de editpagina; weggooien verwijdert
   alleen drafts. Drafts staan niet op het actieve bord.

Nieuw: ProjectLedger.create(status=…) + approve/discard/drafts; decide_opportunity blokkeert
done bij open vraag en zet project als draft; cockpit concept-blok + dispatch proj_approve/proj_discard.
Tests: +test_klaar_geblokkeerd, +test_project_wordt_concept, +test_lopende_projecten_niet_in_backlog.
Suite groen (478 + 492 in twee helften).

## Focusmodus: /triage — één spanning per scherm (Duolingo-stijl)
De inbox-flow liep stroef (lange dichte tabel, te veel klikken, items sprongen). Nieuw: een
aparte /triage-pagina die je de stapel kansen één-voor-één laat doorwerken. Eén kaart per scherm
met voortgangsbalk ('Spanning 3 van 12'), en stapsgewijze keuzes met grote knoppen:
Hoe pak je dit op? → Tactical (Project / Informatie geven / Informatie vragen) of Governance
(voorstel, AI kiest nieuw vs. uitbreiden), plus '✓ Klaar' en 'Past niet binnen de visie'.

Stap-navigatie is client-side (lichte JS toont één paneel tegelijk); de eigenlijke acties zijn
gewone POST-forms naar /action (zelfde gevalideerde dispatch). Uitkomst toevoegen → blijf op de
kaart (stapelen); klaar/vraag/visie → volgende kaart schuift vanzelf in beeld. Ingang: knop
'▶ Verwerk in focus' in de 'Aan jou'-banner. De dichte backlog-tabel blijft als overzicht bestaan.

Nieuw: cockpit.render_triage + /triage GET-route + focus-knop. Tests: +test_focusmodus_*.
Suite groen (478 + 489; test_loop discovery is een bekende flaky threaded-timing-test).

## Governance-referentiebank: few-shot-grounding uit echte Holacracy-orgs (vertrouwelijk)
Drie governance-exports van bestaande organisaties (geanonimiseerd naar branche-archetype)
geparsed tot 1.651 rol-skeletten: archetype, rolnaam, purpose, accountabilities, domeinen.
Projecten en persoonsnamen bewust NIET bewaard. Nieuw: nooch_village/governance_examples.py
(GovernanceExamples-store + parse_governance_text/_pdf + lexicale search + few_shot_block +
ACCOUNTABILITY_RULES). CLI 'ingest_governance "<archetype>" <pdf...>' accumuleert in
data/governance_examples.json.

HARDE GRENS — vertrouwelijk: de store leeft alleen lokaal in data/ (gitignored), wordt NIET
door cockpit.gather() ingeladen, en mag nooit in notes/keywords/content/Field Notes belanden.
Alleen de governance-formuleer-calls lezen eruit.

Grounding ingebouwd in de bestaande governance-flow: pick_governance_target krijgt vergelijkbare
echte rollen als inspiratie; nieuw formulate_accountability schrijft een kans Holacracy-correct
(NL: -en-vorm vooraan, doorlopende activiteit, bron holacracy.org) gegrond met voorbeelden;
_route_kans_to_governance gebruikt die geformuleerde accountability i.p.v. de ruwe titel (zowel
amend als add_role); formulate_project versterkt met de 'afgeronde toestand'-regel. Alles
fail-closed zonder store/LLM. Tests: +test_governance_examples.py. Suite groen (485 + 491).

## Facilitator-rolreview: alle rollen langs de meetlat (mens-gated)
Nieuw project: de Facilitator reviewt elke operationele dorp-rol tegen de Holacracy-regels,
gegrond in de vertrouwelijke referentiebank (vergelijkbare echte rollen per rol opgezocht).
Per rol levert hij ÉÉN concreet verbetervoorstel (accountability naar -en-vorm, ontbrekend
aandachtsgebied, te detaillistische regel schrappen, purpose scherper), dat als KANS in de
human inbox landt (by=facilitator, kind=governance). Mens-gated: jij verwerkt ze in de
focus-triage; niks wordt automatisch toegepast. Kernrollen (Facilitator/Secretaris/Lead Link)
en de wortelcirkel worden overgeslagen — die liggen in de Grondwet vast.

Nieuw: nooch_village/governance_review.py (review_role + review_all_roles + _parse_review).
CLI: 'python -m nooch_village.village review_roles'. Fail-closed zonder LLM (0 voorstellen).
Tests: +test_role_review.py. Suite groen (507 + 474).

## Focusmodus: overzicht-eerst i.p.v. auto-kaart (geen restart, geen terugkeer)
/triage opent nu een OVERZICHT van alle openstaande spanningen (klikbare lijst, geen gedwongen
volgorde, 'wacht op antwoord'-badge waar een vraag openstaat). Je kiest er zelf één → focuskaart
verwerken → terug naar het overzicht (de afgehandelde is dan weg). Lost twee klachten op: je zag
geen totaaloverzicht, en na het verwerken sprong je terug naar de eerste / leek een verwerkte
weer terug te komen. Oorzaak: /triage laadde automatisch queue[0]; afgehandelde items verdwijnen
nu uit de queue en het overzicht laadt nooit een dichtgezette kaart.

Nieuw: cockpit.render_triage_overview; /triage GET → overzicht zonder iid, focuskaart met geldig
iid; focuskaart-acties: uitkomst toevoegen blijft op de kaart, klaar/vraag/visie → overzicht.
Tests: test_triage_dialoog bijgewerkt + overzicht-tests. Suite groen (507 + 475).

## Quick fixes: volledige rol-voorstellen + toetsenbord-navigatie
1) Rol-review-voorstellen kapten af op "door:" — oorzaak: parser nam alleen de eerste regel van
   SUGGESTIE + te krappe tekenlimieten + de suggestie werd in de titel geperst. Nu: _parse_review
   neemt de VOLLEDIGE (ook meerregelige) suggestie, ruime limieten (600), schone vaste titel
   "Rol 'X' aanscherpen", en de prompt dwingt een voluit-geformuleerd, afgerond voorstel af.
2) Toetsenbord-navigatie in de focusmodus: op het overzicht ↑/↓ (of j/k) door de lijst + Enter
   opent; op een kaart Esc/← terug naar het overzicht en 1/2 voor Tactical/Governance (genegeerd
   terwijl je in een veld typt). Hints in beeld.

Tests: +test_parse_review_volledige_meerregelige_suggestie, toetsenbord-assert. Suite groen (507 + 476).

## "Oordeel = training"-laag: zachte verdicts voeden de rollen
Een spanning afronden kan nu mét een oordeel dat het dorp traint, los van het feit dát hij sluit:
- 👍 leuk idee (resolved) — positief signaal "meer van dit denken"
- ✓ klaar, niets nodig (neutraal, geen signaal)
- 🙂 nee, geen huis-regel (rejected) — zacht, mag opnieuw bij andere context
- ⏳ nu niet (deferred) — timing, niet de inhoud
- 🌍 buiten NoochVille (resolved) — hoort niet in het dorp
- ✗ past niet binnen de visie (rejected) — de ENIGE die een harde huis-regel wordt (constraints)

Kern: wat er met het item gebeurt (sluit) staat los van wat het dorp leert (signaaltype). Alleen
vision_drop blokkeert; de rest zijn zachte, gewogen signalen die de opportunity-reflex kleuren.

Nieuw: nooch_village/feedback.py (Feedback-store data/feedback.json + training_block, pos/neg
gegroepeerd, rol-filter). decide_opportunity verwerkt de verdicts + logt feedback (vision_drop
logt 'vision_drop' + huis-regel). Cockpit focus-kaart: nieuw 'Afronden / oordeel'-paneel (toets 3)
met alle verdict-knoppen, gedeelde reden + huis-regel-vinkje. Inhabitant._training_signals voedt
de reflex (rol-specifiek). Tests: +test_feedback.py, reflex-signaal-test, stub bijgewerkt.
Suite groen (483 + 507).

## Roloverleg (IDM): governance-voorstellen behandelen i.p.v. direct doorvoeren
Het echte governance-overleg, zoals de roadmap aankondigde. Governance-keuzes uit de triage
worden niet meer meteen doorgevoerd maar op een AGENDA gezet (data/roloverleg_agenda.json).
In /roloverleg behandel je ze één voor één:
- huidige rol (purpose + accountabilities) + de voorgestelde wijziging + reden;
- Secretaris-check: de deterministische poort G0-G4 + de -en-formuleercheck (blok / let op);
- reactie geven → AI past het voorstel aan (gegrond in de referentiebank, Holacracy-regels);
- Consent (aangenomen) of Schadelijk (blijft staan, volgende keer oplossen);
- zelf een voorstel toevoegen via hetzelfde proces;
- 'Einde roloverleg' → de aangenomen voorstellen worden doorgevoerd via Gate + Secretary._adopt;
  een voorstel dat de poort alsnog blokkeert blijft staan (objected).

Nieuw: nooch_village/roloverleg.py (Agenda + secretary_check + amend_with_reaction + apply_consented).
inbox_actions._route_kans_to_governance/decide_opportunity: met agenda → agenderen (status 'agendeerd'),
zonder agenda → oude direct-adopt (back-compat). Cockpit: /roloverleg overzicht + behandel-scherm,
rov_* dispatch, dashboard-link + 'Aan jou'-telling, flash. Tests: +test_roloverleg.py.
Suite groen (504 + 492).

## Check-out 2026-06-25 (de grote triage/governance-dag)
**Tevreden:** de hele keten staat en is end-to-end testbaar: rol-review → focus-triage → agenda →
roloverleg → records, plus de "oordeel = training"-lus. ~996 tests groen, alles mens-gated, niks
autonoom doorgevoerd. De focusmodus valt goed ("dit werkt heel goed daarboven").

**Ontevreden / schuld:** veel UI in cockpit.py inline-HTML (groeit; ooit splitsen). De lexicale
zoek in de governance-bank mist samengeplakte PDF-woorden ("socialemediakanalen") — semantisch
matchen is beter. De roloverleg-amend past nu alleen de eerste accountability / purpose aan, niet
meerdere. Schadelijk = alleen "blijft staan" (tegenvoorstel/validiteitstoets nog niet).

**Verrast:** hoe naadloos de echte governance-exports op NoochVille's eigen model bleken te passen
(zelfde rol → purpose/accountabilities/domeinen, zelfde kernrollen). En dat de afgekapte voorstellen
mijn eigen parser-bug waren, niet de LLM.

**Geleerd:** de Holacracy-canon — accountability = doorlopende activiteit, -ing/-en-vorm vooraan,
geen autoriteit (dat zijn domeinen/policies); project = afgeronde toestand. En het principe dat
Stefan steeds aanscherpte: wát er met een spanning gebeurt (sluiten) staat los van wat het dorp
ervan leert (signaaltype); alleen de visie-afwijzing blokkeert hard.

**Ontdekt:** de bundel-aanpak (vragen parkeren, in één puls-call beantwoorden) is het bovenliggende
principe van het hele dorp, niet alleen voor de dialoog. En: een overzicht-eerst-flow lost zowel
"geen totaalbeeld" als "springt terug naar de eerste" in één keer op.

## Roloverleg-fixes (na eerste echte gebruik)
- Governance vanuit de triage haalt het item nu UIT je focus-triage (resolved) zodra het op de
  roloverleg-agenda staat — rol-reviews bleven anders in 'verwerk in focus' hangen.
- Secretaris-check ziet nu ook een accountability die de rol AL (vergelijkbaar) heeft (Gate's G2
  slaat de eigen rol over). Dit ving de website_watcher-casus: een purpose-review werd als bijna-
  dubbele accountability geformuleerd.
Tests: +test_secretary_check_dubbel_in_dezelfde_rol. Suite groen (503/504 + 493; de ene rode is de
bekende flaky test_discovery_loop, slaagt los).

### Nog open na deze ronde (volgende sessie)
- Purpose-reviews worden nu altijd als ACCOUNTABILITY geformuleerd; een purpose-intentie hoort een
  purpose-wijziging te worden (intentie detecteren of de mens laten kiezen accountability/purpose).
- Reactie in het roloverleg: de flash staat bovenaan (je stond eronder) en de AI-amend raakt alleen
  de voorgestelde accountability, niet de bestaande accountabilities waar je reactie over ging.
  Inline-bevestiging + breder amend gewenst.
- 'Einde roloverleg' geeft wél een bevestigingsbanner ("X doorgevoerd"); evt. prominenter maken.

## Shopify-koppeling + Website Watcher-verkoopdashboard
De website_watcher krijgt de verkoopkant naast Plausible (bezoekers) en GSC (vindbaarheid).
Nieuw: `skills_impl/shopify_sales.py` (ShopifySalesSkill, Admin GraphQL 2026-01, read-only):
gepagineerde orders in een venster → geaggregeerde indicatoren (paren verkocht, orders, omzet,
AOV, per land, topproducten). UITSLUITEND geaggregeerd, geen PII. Pure `aggregate_orders` +
injecteerbare `fetch_orders`/`_post` (volledig testbaar zonder netwerk). Fail-closed zonder
SHOPIFY_STORE/SHOPIFY_TOKEN. CLI `village shopify [dagen]` schrijft data/shopify_metrics.json;
toegevoegd als stap 5/5 in refresh.sh.

Cockpit: `_render_watcher_dashboard` toont '📊 Website Watcher — verkoop' (KPI-tegels + top
landen/producten), boven de kansen-backlog; fail-safe als er nog geen data is. Hiermee wordt
`pairs_sold` (de noordster-metriek) eindelijk echt meetbaar. Tests: +test_shopify_sales.py.
Suite groen (497 + 506).

### Volgende stappen (genoteerd)
- Conversie-join: Plausible-bezoekers × Shopify-orders = conversie + sale-per-keyword/pagina
  (order.landing_site/referring_site) — de echte SEO-ROI-lus.
- Skill via governance aan website_watcher's DNA + in de puls (nu CLI/refresh-gedreven).

## Shopify-auth → Dev Dashboard (client-credentials) + conversie-indicator
Shopify staat sinds 2026 geen legacy custom apps meer toe; tokens komen nu uit een Dev Dashboard-app
via de client-credentials-flow (Client ID + secret, kortlevend token). Skill aangepast:
get_access_token() wisselt Client ID/secret om voor een token (injecteerbaar voor tests); run()
accepteert zowel een statische SHOPIFY_TOKEN (oude apps) als SHOPIFY_CLIENT_ID+SHOPIFY_CLIENT_SECRET.
.env: SHOPIFY_STORE + SHOPIFY_CLIENT_ID + SHOPIFY_CLIENT_SECRET.

Conversie-indicator op het Website Watcher-dashboard: aggregate_orders levert nu ook een 7-daags
subvenster (orders_7d/pairs_7d); de cockpit leest het laatste visitors_7d uit pulse_history.jsonl
(Plausible) en toont 'bezoekers (7d)' + 'conversie (7d)' = orders_7d ÷ bezoekers_7d. Dit is de eerste
stap van de verkeer-naar-verkoop-lus. Tests uitgebreid. Suite groen (497 + 509).

## Shopify-dashboard: hele historie + gemiddelden per maand
Op verzoek (winkel nu dicht → hele historie + gemiddelden interessanter dan een 7d-venster):
- venster instelbaar; default = HELE HISTORIE (window 0 → geen datumfilter in fetch_orders).
  CLI `village shopify` = hele historie; `village shopify 7` = venster (campagnetijd).
- aggregate_orders berekent first_order_date, span_days en gemiddelden per maand
  (avg_pairs_month/avg_orders_month/avg_revenue_month) over de werkelijke periode.
- dashboard toont periode-label ('hele historie · sinds <datum>' of 'laatste N dagen'),
  plus tegels 'gem. paren/maand' + 'gem. omzet/maand'. 7d-conversie blijft voor campagnetijd.
Tests uitgebreid. Suite groen (497 + 511).

## Attributie-lus: welke landingspagina/kanaal leidde tot een order
De verkeer-naar-verkoop-lus. De Shopify-skill leest nu per order de customer journey (eerste
bezoek): landingspagina, kanaal (sourceType, bijv. SEARCH/DIRECT/SOCIAL) en UTM-term. aggregate_orders
levert top_landing_pages (→ paren), channels (→ orders) en top_keywords (UTM, → paren). Dashboard
toont deze naast land/producten. Eerlijke grens: organische zoekterm is bij Google meestal
'not provided', dus attributie is op landingspagina + kanaal (UTM-term vooral bij campagnes).
fetch_orders surfacet nu ook GraphQL-fouten (geen stille 0). Geen PII. Tests uitgebreid.
Suite groen (497 + 514).

## Landingspagina → keyword: verkoop terug in de woordenschat
De attributie sluit nu de cirkel naar de bibliotheek. Nieuw: nooch_village/attribution.py
(attribute_keywords, puur): match elke landingspagina (uit Shopify-attributie) aan het best
passende doelwit-woord via woord-overlap (prefix-match enkelvoud/meervoud, drempel ≥helft van het
zoekwoord, één pagina telt bij één woord). cockpit.gather berekent per doelwit-woord 'sales_pairs'
en de doelwit-tabel toont een 'verkoop'-kolom (👟 N), gesorteerd op verkoop eerst (wat geld
oplevert bovenaan). Zo zie je welke targets daadwerkelijk verkopen, niet alleen welke volume hebben.
Tests: +test_attribution.py. Suite groen (522 + 493).

## Governance: purpose-wijziging vs accountability (+ omzetten in het roloverleg)
Een governance-kans wordt niet meer altijd een accountability. Nieuw in inbox_actions:
classify_governance_facet (trefwoorden purpose/ziel/reden-van-bestaan, dan LLM, default
accountability) en formulate_purpose (reden van bestaan, GEEN -en-vorm). _route_kans_to_governance:
bij een bestaande rol → purpose-wijziging (change.purpose) of accountability (add_accountabilities)
afhankelijk van de facet; bij een nieuwe rol → purpose + eerste accountability. Secretary._adopt
voerde een purpose-amend al door. Roloverleg toont een purpose-wijziging correct (huidige vs nieuwe
purpose), amend_with_reaction is purpose-bewust, en een knop 'rov_flip_facet' zet een voorstel met
één klik om tussen purpose en accountability als de AI ernaast zat. Tests uitgebreid.
Suite groen (525 + 493).

## Twee poorten uit de governance-filosofie: rijpheid + omkeerbaarheid
nooch_village/maturity.py (puur): friction_evidence (terugkerende-frictie-signalen) en
irreversible_harm (onomkeerbare-schade-signalen).
- RIJPHEIDSPOORT: de Secretaris-check geeft 'let op: nog niet gestold — overweeg eerst een project'
  bij een accountability-voorstel zonder bewijs van terugkerende frictie. Advies, geen veto
  (Secretary heeft geen veto). Spiegelt G0's herhalingseis voor add_role, nu ook voor accountabilities.
- OMKEERBAARHEIDSPOORT: een project uit triage gaat DIRECT op het bord (queued) als het omkeerbaar
  is; alleen bij mogelijk onomkeerbare schade wordt het een concept (draft) dat jouw akkoord vraagt.
  'De enige check bij een project is: kan het onherstelbare schade doen?'
- De opportunity-reflex-prompt kreeg de vuistregel: begin bij een experiment (project); een
  accountability/rol is een stolling, alleen bij terugkerende frictie.
Filosofie vastgelegd in docs/GOVERNANCE_FILOSOFIE.md. Tests: +test_maturity.py. Suite groen (500 + 522).

## Autonome project-uitvoering: de rol pakt z'n omkeerbare projecten op
De filosofie doorgetrokken naar echt ademen. nooch_village/project_worker.py: een rol werkt in de
puls aan z'n `queued` (= door de omkeerbaarheidspoort als omkeerbaar gemarkeerde) projecten en
levert met BESTAANDE capaciteit (LLM-redenering) een concrete tekst-deliverable/next-action
(record_progress → status running, idempotent via 'worked'). Vraagt het project nieuwe capaciteit of
een onomkeerbare handeling? Dan zegt de rol 'KAN NIET: <wat nodig is>' en wordt het project
geblokkeerd met die capaciteitsvraag voor de mens (geboren-vs-bemenst blijft mens-gated). De mens
sluit projecten af (rol markeert alleen voortgang). CLI work_projects + stap 6/6 in refresh.sh; cap
per run, fail-closed zonder LLM. Accountability ≠ toestemming: een rol mag vrij handelen vanuit z'n
purpose zolang omkeerbaar en binnen z'n skills. Tests: +test_project_worker.py. Suite groen (513 + 514).

## Cockpit-feedback ronde 1 (quick fixes)
- Kansen-backlog uit het dashboard gehaald (verwerken gaat via de focusmodus /triage).
- Inbox ingeklapt tot een details ('overige items'); blijft bestaan voor niet-kans-types.
- Website Watcher: attributie-lijstjes (land/producten/kanaal/landingspagina/UTM) nu in nette
  kaders (.wbox), en een conversie-noot die de getallen toont (orders ÷ bezoekers, 7d-scoped).
- Projecten: leesbare statuslabels (Actief/Toekomst/Wachten op/Done); scope klikbaar naar de
  projectpagina, die nu de deliverable/voortgang (progress) + uitkomst + hypothese toont.
- Externe nieuws-links (volg-woorden 📰 + concurrent-monitor) openen in een nieuw tabblad.
- Field Notes leesbaar in de browser: nieuwe /fieldnotes-pagina (archieflijst + lezen + ←/→
  bladeren), met een link vanuit het Noochie-blok.
Tests: +test_cockpit_cleanup.py; test_business_case/test_triage_dialoog/test_cockpit bijgewerkt.
Suite groen (546 + 484).

### Doorgeschoven naar morgen (feedback ronde 1)
- Website Watcher periode-toggle (7d / maand / hele periode) met eerlijke conversie per periode
  (vraagt bezoekers-historie i.p.v. alleen laatste 7d).
- Datacheck Shopify-koppeling: waarom maar 2 paar over 'hele historie' (waarschijnlijk: de 530 van
  batch 1 zaten niet in deze Shopify-store; verifiëren).
- Scout leest artikelen en destilleert ze tot voorstellen (kenniskaart / seed / doelwit /
  concurrent), inclusief Nooch.earth als zelf-monitor.

## Roloverleg ronde 2: nieuwe-rol-form, hele-rol-reactie, GlassFrog-diff, project-uit-overleg
- 'Zelf een voorstel toevoegen' voor een NIEUWE rol heeft nu naam + purpose + accountabilities
  (één per regel) + domein, met een LIVE AI-suggestieknop (fetch → /suggest_accountabilities,
  geen herladen). inbox_actions.suggest_accountabilities (gegrond, -en-vorm, fail-closed).
- amend_with_reaction herziet nu de HELE rol op je reactie (purpose + accountabilities + domein) en
  levert een echte diff op (add/remove accountabilities t.o.v. de huidige rol). role_snapshot mee.
- Behandel-scherm: GlassFrog-achtige 'Huidige rol' vs 'Na dit voorstel' met groene toevoegingen,
  doorgehaalde verwijderingen en purpose oud→nieuw.
- Nieuwe knop '▶ Doe dit eerst als project': een accountability-voorstel kan direct als omkeerbaar
  experiment naar de indienende rol (rov_to_project) — accountability niet nodig om te handelen;
  bij herhaling stolt het later (rijpheidspoort). Haalt het item van de agenda.
- _proposal_from_item ondersteunt remove_accountabilities (Secretary._adopt deed dat al).
Tests uitgebreid. Suite groen (546 + 488).

### Doorgeschoven (Holacracy-verdieping, volgende ronde)
- Bij INDIENEN: de indienende rol benoemt welke spanning het voorstel oplost + een concreet
  voorbeeld (Holacracy: voorstel is tension-driven). Tonen in het roloverleg.
- Betere objection-test (per https://holacracy.org/blog/a-better-way-to-test-objections-in-holacracy):
  gestructureerde validiteitsvragen i.p.v. één 'schadelijk'-knop.
- Auto-formalisering: een experiment dat 3x is uitgevoerd stolt automatisch tot accountability-voorstel.

## Roloverleg: voorstel is tension-driven (indiener benoemt spanning + concreet voorbeeld)
- Agenda.add draagt nu `example`; het 'zelf toevoegen'-formulier vraagt expliciet "Welke spanning
  lost dit op?" + een concreet voorbeeld-veld. Behandel-scherm toont 'Lost deze spanning op' +
  'Concreet voorbeeld'. (Holacracy, Chris Cowan: een voorstel is altijd tension-driven.)
- Volgende ronde gepland: betere objection-test volgens
  holacracy.org/blog/a-better-way-to-test-objections-in-holacracy — de Facilitator toetst de VORM
  van het bezwaar (niet de waarheid), in volgorde 1→4→2→3: (1) benoemt het schade, (4) vanuit jouw
  rol, (2) veroorzaakt door dít voorstel (een 'kaart'-wijziging), (3) niet louter speculatief
  ('zou/zou kunnen') of wél omkeerbaar. Default: bezwaar geldig → integreren; mens beslist.

## Roloverleg: 'from your role'-intakepoort (ongeldige cross-rol-spanning direct schrappen)
- roloverleg.tension_validity(item, llm_reason=None): een voorstel om een ÁNDERE rol te wijzigen is
  alleen een geldige spanning als de indiener benoemt hoe aannemen de EIGEN rol helpt (benefit).
  Geen benefit → ongeldig. Met benefit + LLM: die mag een puur 'algemeen belang' alsnog afkeuren.
  Eigen rol, founder en procesrollen (facilitator/secretary) zijn vrijgesteld.
- Agenda.add draagt nu `benefit`; het add-formulier vraagt erom bij een wijziging aan een andere rol.
- Behandel-scherm: bij een ongeldige spanning een Facilitator-banner + knop '⚖️ Spanning ongeldig —
  verwijderen' (rov_invalid) die het punt direct van de agenda haalt, ZONDER governance-proces.
  Een geldige spanning kan zo niet verwijderd worden.
Suite groen (546 + 491).

## Objection-test + auto-stollen na 3x (laatste roloverleg-ronde)
Objection-test (Holacracy, Chris Cowan): roloverleg.test_objection() toetst de VORM van een bezwaar
tegen de vier criteria in volgorde 1→4→2→3 (schade · vanuit je rol · door dit voorstel · niet louter
speculatief). Default-valid, fail-open zonder LLM ('niet getoetst — standaard geldig'). De cockpit
'⚠ Bezwaar toetsen'-knop vraagt eerst de bezwaartekst; geldig → blijft staan (objected) voor
integratie, ongeldig → terug naar open (je kunt alsnog consent geven). Het getoetste bezwaar +
de vier criteria worden op het behandel-scherm getoond. Agenda.set_objection bewaart het.

Auto-stollen na 3x: een project met origin='experiment' (gemaakt via '▶ Doe dit als project') telt
uitvoeringen (ProjectLedger.record_progress → executions++). work_projects herwerkt experimenten elke
puls tot de drempel (3). formalize_ripe_experiments(ledger, agenda) draagt rijpe experimenten
automatisch voor als add_accountability voor de eigenaar (reason bevat 'structureel terugkerend' →
rijpheidspoort vervuld), met dedup via de 'formalized'-vlag. cockpit.gather roept dit aan, zodat
rijpe experimenten vanzelf op de roloverleg-agenda verschijnen.
Suite groen (546 + 495).

## Scout destilleert concurrent-nieuws → mens-gated voorstellen (open punt #3)
nooch_village/news_distill.py: NewsProposals-store + distill_article (LLM, fail-closed) + distill_news.
De Scout leest de gemonitorde koppen (competitor_news) en destilleert elk artikel tot ÉÉN voorstel:
kaart (kenniskaartje) / seed / doelwit / concurrent. Dedup op (kind, content) + 'seen'-links zodat
dezelfde kop niet opnieuw wordt verwerkt. Cockpit: blok 'Scout uit het nieuws' met knop
'🔎 Scout: lees het nieuws & destilleer' (news_scan) en per voorstel ✓ overnemen / ✗ negeer
(news_prop). Bevestigen routeert: kaart→NotesStore, seed/doelwit→Library.curate+set_function,
concurrent→CompetitorBrands. Tests in test_news_distill.py. Suite groen (549 + 497).
Resterend open: #1 Website Watcher datacheck, #2 periode-toggle.

## Website Watcher: eerlijke databaken (#1) + periode-toggle 7d/maand/alles (#2)
#1 Datacheck: de Shopify-winkel bevat 1 order, €0 omzet, 2 items (1782421273) = een testorder; de
530-batch is elders verkocht en zit niet in Shopify. Het dashboard toont nu een 'lees met korrel
zout'-baken (€0-bij-verkochte-paren → testorder; ≤2 orders → andere kanalen niet meegeteld) plus een
scope-regel (bron: alleen footwear-nooch).
#2 Toggle: shopify-skill kan met windows=[0,7,30] in ÉÉN fetch meerdere vensters aggregeren; CLI
'village shopify' slaat standaard 7d/maand/hele-historie op. Dashboard heeft een 7d/maand/alles-
toggle (client-side JS, geen round-trip). Conversie alleen in het 7d-paneel (passend bezoekersgetal).
Eén getal meegeven aan 'village shopify N' = alleen dat venster (oud gedrag). Suite groen (551 + 498).

## Bezwaar-toets = het handout-proces (mens beslist, facilitator vrij)
Vervangt de AI-die-oordeelt door het 4-stappen-proces uit de roldenken.nl/Holacracy-handout:
roloverleg.evaluate_objection(answers, harm) telt op uit de eigen antwoorden van de bezwaarmaker.
Vier vragen (Schade / Door dit voorstel / Zeker-niet-speculatief / Beperkt jouw rol); q3 is een
splitsing: 'anticiperen' (right) leidt naar q3b (aanzienlijke schade vóór bijsturen = geldig, veilig
om te proberen = ongeldig). Geldig = op alle vragen het linker antwoord. De cockpit toont een
uitklapbaar 4-vragen-formulier (radio's, q3b verschijnt alleen bij anticiperen) en het resultaat met
✅/❌ per stap. De facilitator/AI oordeelt NIET meer over de inhoud — dat loste de 'mijn geldige
bezwaar werd afgekeurd'-klacht op. Suite groen (551 + 498).
