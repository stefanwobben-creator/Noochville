# Conventies — één mechaniek per ding

> **Zoek eerst de bestaande mechaniek voordat je een nieuwe vorm, store of formulier bouwt.**
>
> Bijna elke bug van 28 augustus 2026 was een tweede mechaniek voor iets dat al bestond: een tweede
> terug-URL in een fragment, een tweede plek waar een actie landde, een tweede telling van hetzelfde
> overleg. Ze faalden allemaal stil — geen foutmelding, wél verkeerde data. Een tweede vorm van
> hetzelfde is geen extra functie; het is een divergentie die op zijn moment wacht.

## De mechanieken

| ding | de mechaniek | waar |
|---|---|---|
| **vangen** (typ-en-Enter, één regel) | `form[data-qa-frag]` + de wachtrij in `static/nooch.js` | `views/vangst.py::_vang_form` |
| **verwerken** (spanning → uitkomsten) | de gedeelde vang-en-verwerk-component | `views/vangst.py::render_vangst_frag` |
| **fragment-swap** (een stuk pagina vervangt zichzelf) | `NV.swap` + `data-nv-mirror(-html)` | `static/nooch.js` |
| **projectcreatie** (door een mens) | de wizard | `views/wizard.py` + `/project/nieuw` |
| **project-checklist** (stappen ín een project) | de checklist op het project zelf | `projects.py::checklist_add` / `check_add` |
| **meldingen aan een mens** | de inbox | `notifications.py::NotifStore` + `views/inbox.py` |
| **bewijs / herkomst** | de Kroniek, append-only | `evidence_ledger.py` |
| **overleg-archief** | het snapshot met de punten erin | `werkoverleg.py::_snapshot` |

Twee dingen die op elkaar lijken maar het níét zijn — verwar ze niet en voeg ze niet samen:

- **`ChecklistStore`** (`checklists.json`) is de *terugkerende cirkel-checklist* uit stap 2 van het
  werkoverleg. Dat is iets anders dan de checklist ván een project.
- **`AITaskStore`** is werk dat een AI-rol uitvoert; de **inbox** is een melding aan een mens. Een
  AI-vervulde rol leest de NotifStore nooit — daar werk neerleggen als bericht is het stil
  verliezen. Zie de dead-letter-guard in `_act_vangst_uitkomst`.

Er zijn **drie postbussen**, en ze zijn geen variant van elkaar:

| klasse | van wie | waarvoor |
|---|---|---|
| `NotifStore` | een **mens** | meldingen, spanningen, acties uit een overleg |
| `Inbox` | een **inwoner** (thread) | toegewezen werk dat áf moet — de betrouwbaarheidskant van de bus |
| `HumanInbox` | de **founder**, lokaal en geauthenticeerd | approvals: governance-escalaties en rol-activaties |

Een vierde is wél een tweede postbus: dan mist iemand de helft van zijn werk en merkt niemand het.

## Fail-open op AI

Een AI-stap is een **bonus, geen poort**. De mens moet zijn handeling altijd kunnen afmaken zonder
model: met een overslaan-knop die er meteen staat (ook tijdens het wachten), een timeout, en een
lege uitkomst met een nette melding in plaats van een hangend scherm. Zie `views/wizard.py`
(`PLAN_TIMEOUT_MS`, `Skip this step`).

## De poortjes

"Modulair, geen redundantie" is pas een regel als een test omvalt. Deze bewaken het:

| test | valt om bij |
|---|---|
| `tests/test_conventies_ratchet.py` | een tweede store (dus ook een tweede checklist-store of meldingskanaal), of een tweede projectcreatie-**vorm** |
| `tests/test_ui_fragment_mechaniek.py` | een tweede fragment-swap of een eigen kopie van de vang-wachtrij |
| `tests/test_actie_routing_ratchet.py` | werk uit een overleg dat weer op een geraden project belandt |
| `tests/test_overleg_archief_ratchet.py` | een overleg-archief dat de punten niet bewaart |

### Een poort bewaakt alleen wat hij telt

De projectcreatie-ratchet telde eerst één actienaam (`proj_add`). Daarna bleef er een formulier op
het projectenbord staan dat de wizard opende maar er precies uitzag als een tweede creatie-vorm:
twee tekstvelden en een groene knop. De telling zei nul; het scherm zei iets anders, en een lezer
concludeerde terecht dat er nog een tweede deur was.

Twee lessen, allebei duurder dan ze klinken:

1. **Tel de vorm, niet de naam.** De ratchet telt nu het veld waarmee je een project beschrijft bij
   het aanmaken (`done_when`), niet alleen de oude actie. Een volgende poging met andere veldnamen
   valt daarmee alsnog op.
2. **Een ingang is een deur, geen formulier.** Velden die er als een creatie-vorm uitzien maar
   stiekem doorsturen zijn erger dan geen velden: ze beloven iets anders dan ze doen. Typen doe je
   in de wizard, in het veld dat het project ook echt aanmaakt.

Zelfde familie als de postbus-blinde-vlek hierboven: de aanname was "er zijn er twee", de telling
wees de derde aan.

### Handhaving vereist waarneembaarheid

De meta-les onder de twee hierboven, en onder de afslank-poort. Drie keer dezelfde vorm:

| regel | wat er ontbrak | gevolg |
|---|---|---|
| "een tweede projectcreatie-vorm mag niet" | de poort telde een naam, niet de vorm | het formulier stond er gewoon, telling nul |
| "er zijn drie postbussen" | niets telde de klassen | de aanname was twee |
| "een rol slapen leggen mag niet stilletjes werk breken" | niemand keek wat die rol droeg | ingetrokken skill, teruggezaaid door `seeds.py` |
| "nooit andermans woorden herschrijven" | het record schreef `by="dialoog"` — de plek, niet de auteur | de poort kón niet zien dat een mens typte |

**Een principe dat het record niet kan waarnemen, handhaaft niets.** Een regel is pas een regel als
er een feit in de data staat waaraan je hem kunt toetsen; anders is het een voornemen dat toevallig
in een docstring belandde. Twee gevolgen bij elke nieuwe regel:

1. **Leg het feit vast op het pad dat het weet.** Het schrijfpad weet of een mens zat te typen; die
   kennis verdwijnt zodra er alleen een string overblijft. Vandaar `notifications.MENS_GETYPT` —
   het pad merkt zijn eigen tekst, in plaats van dat de poort de afzender moet raden.
2. **Het pad wint van de afleiding.** Herkenning-achteraf faalt precies bij de randgevallen: `zelf`,
   `dialoog`, een uitgelogde gebruiker. Wie de regel op herkenning bouwt, schendt hem bij de mensen
   die hij het minst kent.

### Consolideer het mechaniek, niet de copy

De keerzijde van "één mechaniek per ding". Twee handelingen mogen dezelfde ROUTE delen zonder
dezelfde ZIN te delen — en ze door elkaar halen levert tekst op die niet klopt.

Weigeren en sluiten lopen allebei door `_sluit_reden_terug`: comment op de bron-feed, `worked=False`,
geen tweede kanaal. Dat is de winst. Maar toen de zin ook gedeeld werd, las een weigering als:

> Deze spanning is **gesloten** door `mother_earth__nooch__website_developer` — reden: ✗ je verzoek is **geweigerd**: …

Twee werkwoorden voor twee verschillende dingen, en een rol-ID waar een naam hoort. De aanroeper
geeft nu zijn eigen zin mee; de route blijft één.

De toets: **is dit hetzelfde MECHANIEK of dezelfde WOORDEN?** Bezorging, autorisatie, opslag en
routering horen op één plek. Wat de lezer te zien krijgt hoort bij de handeling — en een handeling
die anders heet, heet anders omdat ze anders is.

Zelfde familie als "een ingang is een deur, geen formulier": het gaat mis zodra iets eruitziet als
iets wat het niet is.

### Drie verwerkingsuitkomsten, en weigeren zit er niet bij

Een spanning verwerk je tot **actie**, **project** of **governance**. Meer niet.

| uitkomst | wanneer |
|---|---|
| **actie** | het werk is van iemand anders — je DEELT het door, via `route_werk` |
| **project** | het werk is van jouw rol — je BORGT het |
| **governance** | de STRUCTUUR moet mee (bereikbaar via een actie: deel de spanning met wie het voorstel indient) |

**Het werkwoord bepaalt of het werk doorloopt.** Dat is de kern, en alles hieronder volgt eruit.
Delen, borgen en amenderen zetten werk in beweging; weigeren stopt het op de plek waar het juist
door moest. Daarom is **weigeren geen uitkomst** — niet uit voorkeur maar omdat het geen richting
heeft.

Holacracy zegt hetzelfde in andere woorden: hoort het bij je rol, dan borg je het — een rol weigert
zijn eigen accountability niet. Hoort het er niet bij, dan deel je het door naar wie het wél draagt.
In beide gevallen is "nee" het verkeerde werkwoord: het sluit een vraag zonder hem ergens te laten
landen.

Het enige "nee" dat ooit op prod is gegeven laat dat zien. Lara vroeg om een oordeel; ze kreeg
*"NEE — verkeerde doelgroep"*. Dat is inhoudelijk precies goed en als handeling precies fout: het
werk bleef van haar rol, dus het antwoord had een ACTIE moeten zijn die haar verder helpt. Zelfde
inhoud, ander werkwoord — en het werkwoord besliste of haar vraag doorliep of doodliep.

**Sluiten is een uitgang, geen uitkomst.** "Niet meer relevant" is geen verwerking maar het einde
ervan; hij draagt een optionele reden die teruggaat naar de vrager (zie hieronder). Zet hem niet
naast de drie alsof het er vier zijn — dan wordt de makkelijkste weg een uitkomst.

**Goed formuleren is de voorwaarde, niet een vierde keuze.** Je kunt een spanning alleen delen of
borgen als er staat wát er aan de hand is; een onbegrijpelijk verzoek is niet weigerbaar maar
onleesbaar. Dat is precies wat de leesbaarheidslaag levert (`systeemtaal` + `bevinding`), en waarom
"aanpassen" geen aparte uitkomst is: het is de stap die overal beschikbaar hoort te zijn.

#### Wat de meting zei

Over de hele prod-historie: **0 weigeringen, 0 herformuleringen.** Van de zes `naar_rol`-items zijn
er drie geaccepteerd (→ project, dus geborgd), twee waren testruis en één staat open. Het enige
"nee" ooit kwam uit Decide-now — en dat was geen weigering maar een *inhoudelijk antwoord*
("verkeerde doelgroep"), dus onder deze regels een ACTIE terug naar de rol die het vroeg.

De knoppenrij accepteren/aanpassen/weigeren had dus één gebruikte tak van de drie.

### Bewijs blijft woordelijk

**Een feit wijs je aan; je herschrijft het niet.** Dat is één principe onder drie regels die er los
van elkaar uitzagen:

| waar | wat het zegt |
|---|---|
| `bevinding.feitbehoud` | de herschrijving mag niet zekerder of specifieker zijn dan de bron |
| regel 5 in de herschrijf-prompt | een geciteerde claim blijft staan, ook in het Engels |
| COPYCHECK-001 | *"Quote the failing sentence, do not summarise"* |

Alle drie beschermen hetzelfde: de woorden waarop iemand zich straks beroept. Een geciteerde
klantclaim staat er omdat iemand precies díe zin op de site zag; een falende zin moet je kunnen
terugvinden; een slag om de arm is een uitspraak over hoe zeker het feit is, en dus zelf een feit.
Vertaal, vat samen of poets die op, en het bewijs is losgeraakt van waar het vandaan komt — zonder
dat iemand het merkt, want de tekst leest juist béter.

Praktisch, in volgorde van hardheid:

1. **Behoud het epistemische niveau.** `mogelijk` blijft `mogelijk`; `A of B` wordt niet stil één
   ervan; er komt geen getal, naam of oorzaak bij die de bron niet had.
2. **Citaten blijven letterlijk**, ook als de rest vertaald wordt. Vertaal eromheen.
3. **Herkomst poets je niet op.** `bevinding["ruw"]` en het blok "ruwe signalering" tonen wat er
   werkelijk stond; alleen de LEESTEKST wordt leesbaar gemaakt.
4. **Andermans woorden herschrijf je nooit** — zie `notifications.MENS_GETYPT` hierboven.

En de keerzijde die dit werkbaar houdt: kan een herschrijving het feit niet behouden, dan is de ruwe
tekst de uitkomst. **Onbegrijpelijk-maar-waar is te repareren; vloeiend-maar-onwaar niet.**

### Chrome is Engels, inhoud is Nederlands

De taalgrens loopt niet om de applicatie maar dwars erdoorheen:

| | taal | voorbeelden |
|---|---|---|
| **chrome** | Engels (i18n fase 1) | knoppen, kolomkoppen, menu's, statusmeldingen |
| **inhoud** | Nederlands | bevindingen, Field Notes, spanningen, checklist-items, projecttitels |

Waarom dit erin staat: één regel in de checklist-prompt — `"Write all free text in English."` — zette
134 Engelse berichten in de inbox van de founder, náást bevindingen en Field Notes die allemaal
Nederlands zijn. De regel leek consistent (de cockpit is immers Engels) maar stond aan de verkeerde
kant van de grens.

Twee uitzonderingen, allebei principieel en geen slordigheid:

- **Klant-copy blijft in zijn eigen taal.** De Copywriter schrijft met opzet Engels.
- **Citaten blijven letterlijk** — zie "Bewijs blijft woordelijk" hierboven.

#### Een record neemt de taal van zijn buren

De inhoudsregel hierboven zegt niets over wat er gebeurt als een bestaand record al in een andere
taal staat. Rol-DNA is zo'n record: het wordt als GEHEEL gelezen, en accountabilities verschijnen
geciteerd naast elkaar op het scherm.

`mother_earth__secretary` draagt vijf Engelse accountabilities uit de GlassFrog-import. Er een
Nederlandse bij zetten leest als een **fout**, niet als een keuze — ook al is roldefinitie-tekst
volgens de regel hierboven "inhoud". Dus: **een nieuwe regel neemt de taal van zijn buren, en een
taalwissel is een bewuste hele-rol-pass.**

Dat kost hier niets: de triage vergelijkt het citaat LETTERLIJK tegen de records, dus de matching is
taal-onafhankelijk.

En taal repareer je bij de BRON, niet bij de leesbaarheidslaag: vertalen is precies waar een model
iets bijverzint, dus de veiligste vertaling is de vertaling die niet nodig is. De laag blijft het
vangnet voor wat tóch in de verkeerde taal binnenkomt — een vangnet, geen route.

### Onafhankelijke deelchecks dekken verschillende assen

**Eén goede check is zwakker dan drie die elkaar niet dekken.** Dat is de reden dat de
leesbaarheidslaag drie poorten heeft in plaats van één strenge.

De aanleiding, op prod, op het eerste echte bericht dat de laag raakte. De bron zei
`(vermoeden, geen wet)`; de herschrijving maakte er *"de EU-richtlijn 2024/825 (EmpCo)"* van. Het
model hield zich **keurig aan de zekerheidsregel** — `mogelijk` bleef gewoon staan — en glipte langs
een as die niemand bewaakte. Een enkele check had hem doorgelaten, en de tekst las beter dan het
origineel.

| deelcheck | as | waar |
|---|---|---|
| slag om de arm | hoe ZEKER is het | gemeten (`bevinding.feitbehoud`) |
| grond | is dit gegeven OPZOEKBAAR in de bron | gemeten (`_ongegronde_specifieken`) |
| alternatieven heel | zijn er MOGELIJKHEDEN weggevallen | oordeel (in de prompt) |

Drie regels bij het toevoegen van een deelcheck:

1. **Een nieuwe as, geen strengere versie van een bestaande.** Twee checks die hetzelfde meten geven
   de illusie van dekking; de smokkel loopt langs de derde as die er niet is.
2. **Meten waar het kan, vragen waar het moet.** Een model dat zijn eigen tekst beoordeelt kijkt
   zijn eigen huiswerk na. Wat je met de bron kunt vergelijken, vergelijk je.
3. **Streng mag, mits falen goedkoop is.** Deze poorten mogen scherp staan omdat afkeuren betekent:
   de ruwe tekst blijft staan. Zonder die fail-open is elke valse afwijzing verlies, en dan durf je
   niet meer streng te zijn — dan bewaakt de poort niets meer.

Zelfde vorm als "een poort bewaakt alleen wat hij telt", één trede hoger: die gaat over wat één
poort ziet, deze over wat je tússen de poorten door laat lopen.

### Een ratchet toetst gedrag, niet broncode

De testkant van "handhaving vereist waarneembaarheid". Een poort die zijn eigen implementatie
beschrijft is zwakker dan een die zijn eigen uitkomst meet.

De aanleiding: twee poorten zochten op LETTERS in plaats van op WOORDEN — `"kern"` matchte
`"kernproces"`, `"duidelijk"` matchte `"ONduidelijk"` — en allebei faalden ze stil. Mijn eerste
ratchet scande de broncode op een `in`-vergelijking en gaf een valse treffer op een variabele die
toevallig `r` heette. De tweede versie plakt voor elk woord in elke lijst een voor- en achtervoegsel
en controleert dat geen poort aanslaat (`tests/test_woordgrens.py`). Die versie kent de
implementatie niet en hoeft dat ook niet.

Vuistregel: **kun je de eigenschap meten aan de uitkomst, doe dat dan.** Een broncode-scan is voor
wat je alléén aan de vorm kunt zien — een tweede store, een tweede formulier, een inline style — en
zelfs daar telt hij de vorm en niet de naam (zie hierboven).

### De poort verifieert dat het bewijs BESTAAT, niet dat het PAST

Bestaan is grondbaar; passendheid is oordeel, en oordeel blijft bij de mens.

De triage-poort laat het model een rol noemen én de accountability citeren waarop het matcht, en
controleert dat citaat daarna deterministisch tegen de records. Dat ving op de eerste echte poging
een verzinsel: bij een spanning over een lekkende koffiemachine noemde het model netjes een rol én
een citaat, en dat citaat stond nergens.

**Maar hij toetst niet of de match GOED is.** Bij "Moment van methodische scherpte in bulletin" koos
hij `librarian` met *"Evaluating candidate words for approval."* — een echte accountability, een
magere match. Daar is bewust geen relevantie-poort bijgebouwd:

- **bestaan** is een vergelijking (staat dit citaat in de records, ja of nee) en dus grondbaar;
- **passendheid** is een oordeel, en een machine die dat oordeel afdwingt vervangt de mens in plaats
  van hem te helpen.

Daarom is het een SUGGESTIE en geen routering: de band zegt wat wij denken en waaróm, de rauwe
spanning staat er onaangetast onder, en de lezer ziet de match zelf. Zelfde grens als bij de
feitbehoud-check — wij vergelijken wat vergelijkbaar is, en laten het oordeel waar het hoort.

### Grond stopt fabricatie, niet irrelevantie — dus meet het

Een geverifieerd citaat bewijst dat het bewijs ECHT is. Op prod bleek dat goedkoop: het model vond
voor "de koffiemachine lekt" netjes *"Facilitating the Circle's regular Tactical Meetings"* — waar,
verifieerbaar, en volstrekt naast de kwestie. De poort liet het door, en dat is juist: passendheid is
oordeel (zie hierboven).

**Bouw dan geen strengere poort, maar meet eerst hoe vaak het stoort.** Twee signalen, allebei
meetbaar en geen van beide een oordeel:

- **de acceptatieratio** — accepteerde de mens de suggestie, overschreef hij hem, of hield hij het
  zelf? Dat is de enige echte uitspraak over bruikbaarheid, en hij kost geen UI: de drie handelingen
  bestaan al, je noteert welke het werd (`triage_rol.noteer_uitkomst`, `village triage_ratio`);
- **de marge** tussen de beste en de op-één-na-beste match. Een suggestie die nét wint van vijf
  andere zegt iets anders dan een die er met kop en schouders bovenuit steekt.

En als er ooit een drempel komt: **op de marge, niet op zelf-gerapporteerd zelfvertrouwen.** Een
model dat zijn eigen zekerheid inschat beoordeelt zijn eigen huiswerk — dezelfde reden dat de
feitbehoud-check meet in plaats van vraagt.

De ratio telt alleen de keren dat er een ROL werd gekozen. "Zelf gehouden" en "andere uitkomst"
zeggen niets over de suggestie, en meetellen maakt het getal onleesbaar — precies het getal waar je
later een grens op zou zetten.

**Lees hem daarom naast het aandeel "zelf gehouden" van álle getoonde banden. Twee getallen, niet
één in de ander gevouwen.**

De schone ratio meet PRECISIE-BIJ-ROUTEREN: koos de mens de voorgestelde rol op het moment dat hij
een rol koos. Wat hij niet meet is de band die zó zwak was dat er helemaal geen rol werd gekozen —
die verdwijnt in de zelf-bucket en telt nergens als misser. Eén getal zou dus kunnen stijgen terwijl
de suggesties slechter worden:

| ratio | zelf-aandeel | wat het zegt |
|---|---|---|
| hoog | laag | de band werkt: hij wordt gebruikt én hij klopt |
| hoog | **hoog** | **gewenning** — de enkele keer dat hij wordt gevolgd klopt hij, maar meestal wordt hij genegeerd |
| laag | laag | de band wordt gebruikt en zit ernaast: dán is er iets te repareren |
| laag | hoog | **nutteloos** — hij wordt niet gevolgd én klopt niet: uitzetten of hard repareren |

De vierde rij staat er omdat een onvolledige grid je juist in de steek laat op het moment dat je hem
nodig hebt: bij drie rijen lees je een leeg vakje als "komt niet voor" in plaats van als "hier heb ik
niet over nagedacht". En dit is het enige vakje waar het antwoord WEGHALEN is — de andere drie
vragen om bijstellen, dit om stoppen.

`village triage_ratio` drukt beide af; het pairen is een LEESHANDELING, geen ontbrekende functie.
Zelfde valkuil als bij `scope_nudge`: nul calls zag eruit als winst en was stilte.

### Eén bewaakte schrijfroute per store — schrijf nooit rechtstreeks

Elke store heeft een route die WEIGERT wat niet mag: te lange tekst, een ontbrekende poort, een
dead letter. Nieuwe code gebruikt die route. Schrijf je rechtstreeks naar de store, dan omzeil je
niet één controle maar alle controles die daar ooit nog bij komen.

**Dit is de tweede keer in één week:**

| omzeiling | wat er stil misging |
|---|---|
| een eigen `notif.add` naast `route_werk` | een bericht aan een AI-rol werd een dead letter |
| een script dat rechtstreeks in `AttachmentStore` schreef | een policy-body werd stil afgekapt; er bleef een half codeblok achter |

Beide keren bestond de bewaakte route al (`route_werk`, `cockpit2._body_te_lang`), en beide keren
faalde de omzeiling STIL — dat is geen toeval maar de vorm: de controle die je oversloeg is precies
degene die het gemerkt zou hebben.

Twee gevolgen:

1. **Ook eenmalige scripts gaan door de route.** Een migratie of opruiming is geen uitzondering; het
   is juist de plek waar niemand meekijkt.
2. **De backstop schreeuwt.** Een store die stil afkapt verbergt de omzeiling die hij zou moeten
   vangen — dus logt hij nu wát er wegviel en wélke route had moeten weigeren.

### De afzender is niet de auteur — poort op herkomst, niet op indiener

`_is_mens_schrijver` las `by`: wie het item indiende. Dat werkt tot iemand iets DOORZET. Op 1
september zette de founder een machine-melding door als actie; `by` was hij, de tekst was van een
skill — en de poort liet hem daarom met rust, inclusief het `python -m …` erin.

Het actieformulier is VOORGEVULD met de spanningstekst, dus onbewerkt doorzetten stuurt machinetekst
door met een mensennaam eronder. Het schrijfpad weet dat en `by` niet:

- **onbewerkt doorgezet** → machinetekst; het merk gaat expliciet op `False`;
- **bewerkt** → jouw zin geworden; mensgeschreven, geen model-herschrijving;
- **staat het merk expliciet, dan wint het** van de afleiding uit `by` — ook als het `False` is.

De spiegel van de regel uit #394: daar wist het pad dat een mens typte terwijl de naam ontbrak, hier
weet het pad dat een mens indiende terwijl de tekst van een machine is. Beide keren is de vraag
"waar komt deze tekst vandaan", niet "wie drukte op verzenden".

**En splits de zorgen die aan zo'n vlag hangen.** Het lek bestond omdat commando-strippen en
model-herschrijven allebei aan `mens_getypt` hingen. Ze zijn niet hetzelfde: een terminalopdracht
weghalen is geen herschrijving van iemands stem maar een **display-invariant** — die draait altijd,
ongeacht afzender. Alleen het model-oordeel is gepoort op auteurschap.

### Een transportfout is onbekend, geen leegte

`no_data ≠ nul`, één laag lager: niet in de data maar in het TRANSPORT.

    ok           opgehaald, hier is de waarde
    leeg         opgehaald, er was niets — dat is een FEIT
    ophaalfout   niet kunnen ophalen — dat is GEEN feit, dat is onwetendheid

`gdelt_tone/vegan_footwear` stond elf dagen als dode bron in de inbox terwijl de ruwe fetch gewoon
HTTP 200 gaf met 103 datapunten. De skill haalde twee termen op met 6 seconden ertussen, GDELT
verbrak de tweede verbinding (`ConnectionResetError`, **geen 429**), en de `except` eromheen las dat
als "geen data". De tweede term werd systematisch uitgehongerd; niets kon het verschil zien.

`nooch_village/bron_ophalen.py` is het gedeelde sjabloon: `haal_met_retry` classificeert de fout
(transport → opnieuw met backoff; inhoudelijk → niet herhalen, dat gaat de tweede keer net zo goed
mis) en geeft een `Uitkomst` met een status terug. **Bluesky (403) en Trends (429) hebben dezelfde
vorm** — de bron zegt geen nee maar hangt op — en horen daar straks langs.

En: **leun op de retry, niet op de spacing.** Een vast interval is een gok over gedrag dat je niet
beheerst; de backoff vangt de drift. De spacing is beleefdheid.

#### Maar aanhoudende ophaalfout is nog steeds een capaciteitsprobleem

De keerzijde, en zonder haar ruil je een zichtbare storing in voor een stille. "Ophaalfout is geen
leegte" mag nooit worden gelezen als "ophaalfout is geen probleem": een bron die dágen alleen
ophaalfouten geeft, levert geen data, en dat hoort gewoon als capaciteitsgat op te duiken.

Dat werkt hier structureel, en het is het controleren waard bij elke refactor van deze laag:
`indicator_freshness` leest de OBSERVATIES en vraagt "wanneer kreeg dit veld voor het laatst een
waarde". Een ophaalfout schrijft er geen — net zomin als "leeg" — dus de versheid verloopt en de
fresh→stale-overgang vuurt gewoon. De splitsing veranderde HOE we loggen en of we opnieuw proberen,
niet WÁT er wordt vastgelegd.

De spanning die dit onderzoek startte was terecht. Ze was alleen verkeerd toegeschreven: de bron was
niet dood, wij haalden hem niet op. **Beide horen zichtbaar te zijn, en het verschil hoort in het
log** — daar leest een mens of een reeks stilviel door de wereld of door ons.

### Een test die van de datum afhangt, injecteert de datum

Tenzij de datum het onderwerp is. Anders is het geen test maar een tijdbom, en die gaat af op een
dag dat je met iets anders bezig bent.

Zes tests van `regulation_watch` vielen om op 1 september 2026 — niet door een wijziging maar doordat
`HANDHAVING_MAAND = "2026-09"` aanbrak. De skill deed precies wat hij hoort te doen (een
mijlpaal-regel schrijven), en de tests rekenden op de wereld van daarvóór. De suite was rood voordat
iemand iets had aangeraakt.

`_maand` is daarom injecteerbaar, net als `_fetch` dat al was. Vijf tests pinnen hem; de zesde wil
juist de ECHTE maand, want die gaat er nou net over dat de meting NU gebeurde — en dat verschil staat
bij de test, niet in het hoofd van wie hem schreef.

Zelfde familie als `no_data ≠ nul`: **een waarde die je niet controleert is geen constante maar een
aanname**, en een aanname over "nu" wordt vanzelf onwaar.

### Een droge run rekent door hetzelfde pad, of hij liegt

Een dry-run die zijn eigen antwoord berekent is geen voorbeschouwing maar een tweede implementatie —
en die loopt na één wijziging uit de pas. Dan toont het scherm A, gebeurt er B, en heeft iemand op A
zijn handtekening gezet.

De sweep van de wees-projecten moest de bestemming per project TONEN vóór er iets verschoof. Eerst
stond er `(dry-run)`: dát er iets gebeurt, niet wát — een handtekening zonder inhoud. De oplossing
was niet een voorspeller ernaast maar de beslissing eruit halen:

    bestemming()   pure functie, schrijft niets — WAAR zou dit landen
    route_werk()   voert diezelfde uitkomst uit

Voorspellen en uitvoeren zijn nu één functie; ze kúnnen niet verschillen. Een test bevriest dat
`route_werk` zijn besluit uit `bestemming` haalt en niet zelf opnieuw neemt.

Twee eisen aan elke droge run:

1. **Zelfde pad, geen parallelle berekening.** Verschilt de weg, dan is de uitkomst een gok.
2. **Zeg wát er gebeurt, niet dát er iets gebeurt.** "3 items worden verwerkt" is geen droge run.

En de keerzijde, ook uit deze sweep: een verplaatsing die het origineel laat staan is een KOPIE.
Zonder het oude project te sluiten stond hetzelfde werk op twee plekken, en vond de volgende run het
opnieuw. **Een opruiming die niet idempotent is maakt bij elke beurt meer rommel dan hij weghaalt.**

### Routeer op leven, niet op vermogen

**Een rol met een class KAN werken; een rol met een draaiende thread WERKT.** Die twee door elkaar
halen maakt een wees-fabriek.

`_kan_uitvoeren` vroeg of een rol code, skills of een AI-vervuller HEEFT. `noochie` en `facilitator`
staan allebei in `CLASS_MAP`, dus het antwoord was ja — terwijl ze slapen en er geen thread is.
Gevolg: de opruiming vond de vijf wees-projecten niet, én dezelfde functie stuurde `route_werk`, dus
een slapende AI-rol kreeg nog steeds nieuwe projecten op een dood bord. De opruimer miste wat de
bron bleef produceren.

Dezelfde familie als de hartslag: *de code stond er, er tikte alleen niets meer.*

**En de faalrichting is de andere kant op.** Mijn eerste versie las `role_status.json` — een bestand
dat de daemon schrijft. Ontbreekt het (test, verse installatie, webserver vóór de eerste dorpsstart),
dan werd "leeg" gelezen als "niemand leeft", en dan gaat ál het AI-werk naar de Circle Lead.
**Onbekend leven is geen dood, net zoals `no_data` geen nul is.** De check grondt daarom op de
records zelf — slapend/gearchiveerd, AI-vervuller, skills, `CLASS_MAP` — live berekend, nooit uit een
cache; en wat hij niet kan vaststellen laat hij leven.

### Tonen is zwakker dan wegnemen

De poort uit `afslank_afhankelijkheden.py` is een **vangnet, geen eerste keus.** Hij bestond omdat
`facilitator` slapend werd gelegd terwijl die rol de dagbel luidde; hij zou zo'n snit voortaan tonen
vóór hij gebeurt. Maar een waarschuwing die je mag wegklikken houdt geen systeem overeind — en de
echte fout was niet dat het onzichtbaar was, maar dat de hartslag überhaupt aan een rol hing.

De volgorde is dus:

1. **Kun je ontkoppelen, ontkoppel dan.** De cadans verhuisde naar `dagcyclus.py`: geen rol, geen
   record, geen `CLASS_MAP`. De afhankelijkheid bestaat niet meer, dus valt er ook niets te
   waarschuwen. De test die de koppeling aantoonde, bewijst nu haar afwezigheid.
2. **Bewaak wat je niet kunt weghalen.** `pulse_completed` komt van `website_watcher` en dat is
   terecht rolwerk. Daar heeft de poort tanden, want daar hangt echt werk aan een echte rol.
3. **Wat je niet kunt loskoppelen, moet je kunnen horen.** `once()` printte bij uitval
   `Field Note: None` — dat leest als een lege dag, niet als een uitgevallen puls. `None` hoor je
   niet; een melding mét de naam van de stilgevallen rol wel.

Zelfde beweging als hierboven, één trede hoger: waarneembaarheid maakt een regel handhaafbaar,
maar de regel niet nodig hebben is beter dan hem kunnen handhaven.

Elke ratchet is **monotoon dalend**: het plafond mag omlaag als je schuld opruimt, nooit omhoog.
Een nieuwe mechaniek toevoegen mag — maar dan met een expliciete regel in de lijst en een reden,
niet stilzwijgend.
