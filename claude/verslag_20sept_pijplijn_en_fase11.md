# Verslag — pijplijn 3+5 en 7, fase 11 laag 1+2, fase 12-audit (20 september 2026)

Sessie gedraaid terwijl Stefan onderweg was. Vier punten van de lijst afgewerkt, in volgorde, met
een commit per punt. Punt 5 (stap 6, archiveren) is niet aangeraakt — die blijft geblokkeerd.

**Uitgangspunt geverifieerd**: commit `4083ee5` (stap 4) stond er inderdaad. Volle suite vóór
aanvang: **3789 passed, 1 xfailed** — gelijk aan wat de brief noteerde.

**Niets gedeployed en niets gepusht.** Er staan nu **12 commits lokaal vóór `origin/main`**; prod
draait nog op `462bcaf`. De eerste deploy van deze pijplijn verandert gedrag (zie §1) en dat is
jouw moment, niet het mijne.

---

## 1. Pijplijnstap 3+5 — commit `f3fa269`

Eén commit, zoals afgesproken: tussen het sluiten van de oude uitgang en het openen van de nieuwe
mag geen week zitten waarin een compliance-vondst nergens landt.

**Stap 3.** `claims_board.zet_op_bord` is uit `claims_site_scan` gehaald. De scan MELDT nu; hij
wijst niets meer toe.

**Eén ding dat bijna stilletjes meeverdween.** In `zet_op_bord` zat óók de schifting "wat loopt al
als taak of werklijst-item" — en dat is precies de regel die in de kop van `claims_site_scan`
staat ("levert alleen NIEUWE bevindingen"). Die helft is afgesplitst als
`claims_board.nieuwe_bevindingen()`, read-only, met `zet_op_bord` als tweede lezer ervan. Eén
definitie, twee gebruikers.

**Rood blijft dezelfde dag melden.** Een rood stoplicht komt uit de regex plus `claims_db` — een
deterministisch wetsoordeel, geen modelvondst — en een week wachten zou betekenen dat een verboden
claim tot zeven dagen ongezien op de site staat. Oranje en de modelvondsten wachten wél op de memo.
*Dit was vraag 1 uit mijn ontwerpvoorstel; ik heb hem zo ingevuld omdat elke andere invulling een
risico verhoogt dat vandaag niet bestaat. Corrigeer als je het anders wilt — het is één regel.*

**Stap 5.** `weekmemo.verzamel_alles()` roept de vijf adapters achter elkaar aan, elk fail-soft:
een stukke bron levert een regel in het bronrapport in plaats van een stille nul, en dat rapport
staat in de memo zelf. `weekmemo.ronde()` doet: verzamelen → wat nog niet is voorgelegd → memo →
bezorgen → **en pas dán** markeren en onthouden. Andersom verliest een week stil zodra de DM niet
aankomt. Een lege ronde stuurt geen memo maar markeert wel, anders verzamelt de daemon elke dag
opnieuw om weer op nul uit te komen.

Bedrading op `dag_begint`, naast de legal-check. Niet als pulse-skill op een rol: de memo is
dorpswerk, en als skill zou zijn ritme afhangen van welke rol hem toevallig draagt (de les van
28 augustus). `village weekmemo` draait hem met de hand, **droog tenzij `--doen`**.

**De laatste levende modelroutering is weg.** `triage_rol.menselijke_eigenaar` had een tweede
trede: hield niemand het domein, dan bepaalde `classificeer` waar de memo landde. Die trede is
vervangen door de founder; het modeloordeel reist mee als `voorstel_regel` — een zin in het
bericht, die niets verplaatst. *Dit was vraag 2 uit mijn voorstel: de materiaal-memo landt hierdoor
voortaan bij de domein-eigenaar uit `feeds.json` of anders bij jou, niet meer bij een rol die het
model uit de tekst afleidde.*

**De eerste ronde met een leeg geheugen** (je expliciete testvraag): vastgelegd in
`test_de_eerste_ronde_legt_alles_voor_en_vult_daarna_het_boek`. Het boek is leeg, dus alles is
nieuw — ook een signaal van maanden terug dat nog in het venster valt. Dat is met opzet: de
pijplijn heeft geen geschiedenis en mag er geen verzinnen. Na de eerste bezorging staat het boek
vol en komt hetzelfde signaal nooit meer terug. De prompt-cap (40) en de marker-cap (40) zorgen dat
een volle eerste memo leesbaar blijft; wat erbuiten valt wordt geteld, niet verzwegen.

**Droge ronde tegen een kopie van de echte data**: alle vijf de adapters draaien zonder te vallen,
`bewijs` levert 8 signalen, de rest 0 (er is lokaal geen `radar.json` en geen scan-marker). Daarbij
viel op dat geen van de acht Kroniek-records een `meta.brand` draagt — het merk zit in de query als
`"<merk> — <claim>"`, waardoor elk bewijs-signaal las als *"een merk — claim 'Vivobarefoot —
biodegradable…'"*. Gesplitst, met een test dat een query zónder scheidingsteken ongemoeid blijft.

Suite na afloop: **3803 passed, 1 xfailed**.

### Open vragen uit dit punt

1. **`legal_signaal.check` staat nog náást de memo.** Een legal-signaal verschijnt dus twee keer:
   dagelijks als inbox-item en wekelijks in de memo. Ik heb hem laten staan (dagelijkse urgentie
   versus wekelijkse synthese), maar het is een bewuste keuze die je kunt terugdraaien.
2. **De scan stuurt nog drie losse berichten aan "de rol die het claims-domein bezit"** (pagina
   onbereikbaar, scan vastgelopen, claim-regressie). Dat loopt via `claims_board.bericht_aan_rol`,
   en die maakt bij een AI-bemande rol nog steeds een project aan — hetzelfde mechanisme als stap
   3, op kleinere schaal. Ik heb het buiten deze commit gehouden omdat het een ander onderwerp is
   (de gezondheid van de scan, niet de vondsten) en de commit anders onreviewbaar werd. Sinds fase
   5 bezit bovendien niemand het claims-domein, dus die drie berichten komen vandaag waarschijnlijk
   nergens aan. Wil je dat ik ze naar jou laat gaan?

---

## 2. Pijplijnstap 7 — commit `ce59c1e`

**Ratchet 1** (`test_geen_model_routering`): slaagt nog steeds, en dekt nu ook `classificeer` —
die stond niet in `BASIS_ORAKELS`, waardoor de ratchet precies de plek miste die ik in stap 5
repareerde.

Onderweg bleek hij de ECHTE vorm nog steeds niet te vangen: `rol = uitslag.get("rol") or ""`
ontsnapt aan de besmetting. Verbreden geprobeerd; dat gaf **5 treffers op echte code, alle vijf
onterecht** (twee dragen tekst, drie dragen een deterministisch adres met een besmette invoer).
Vijf uitzonderingen op zo'n ratchet is precies waar zijn eigen kop voor waarschuwt, dus
teruggedraaid. De grens staat nu als test vastgelegd, mét die meting en met de verwijzing naar de
gedragstest die deze plek wél bewaakt.

**Ratchet 2** (`test_verzamelaar_schrijft_niet.py`, nieuw): elke functie die `verzamel` heet of
daarmee begint, mag in zijn aanroepketting binnen de eigen module niet schrijven. De regel is de
NAAM, dus een nieuwe bron valt er automatisch onder. Vier zelf-tests: hij vuurt op
`materiaal_memo.verzamel` zoals die vóór stap 2 was, ook als het schrijven via een hulpje ernaast
loopt, en hij laat het LEZEN van hetzelfde boek met rust. Alle zeven bestaande `verzamel*`-functies
zijn schoon.

Suite: **3812 passed, 1 xfailed**.

---

## 3. Fase 11, laag 1 + 2 — commit `765a605`

**Atomen**: `.nu-progress` (één voortgangsbalk voor projectkaart, doelkop en checklist — stond op
drie plekken, drie keer anders gebouwd), `.nu-status--icoon` (bezet/vacant in de organisatieboom,
dezelfde twee vormen als het bord) en `.sr` (het woord naast de vorm). Beide atomen staan in beide
CSS-lagen; alleen de `.nu`-laag zou betekenen dat het icoon een leeg span is op elk scherm dat nog
niet meedoet — en de zijbalk staat op álle schermen.

**Moleculen**: kaartvoorkant (titel → etiketten → voortgang → wie/wanneer; de titel stond ónder het
doel-etiket, dus de kaart begon met een categorie), checklist-rij (klik verschuift de stand meteen,
de POST eronder is onveranderd en blijft leidend) en de kanaalrij (naam, tijdstip, ongelezen).

**Messages-navigatie**, zoals je bevestigde: 64px rail op desktop met monogrammen (het volledige
woord blijft in de DOM), organisatieboom achter een flyout, en op mobiel drill-down via één
rendering met twee standen — dus de terug-pijl werkt zonder JS en elke stand is een deelbare URL.
De hamburger komt alleen op als JS draait; het script zet zelf de klasse die hem nodig maakt, zodat
een mislukt script geen onbruikbaar menu achterlaat.

**Drie dingen gingen onderweg mis, alle drie gevangen door een test.** De belangrijkste: `lijst`
was al een lokale variabele in `render_messages`, dus mijn nieuwe parameter werd overschreven —
het scherm stond permanent in lijst-stand en markeerde daardoor nooit meer iets als gelezen. Ook
gevonden: een testhelper die kanaalnamen met een regex las gaf na deze wijziging een lege lijst
terug, en de test die hem tegen een bovengrens telde bleef gewoon groen. Beide gerepareerd.

**Laag 3 (sleeppatroon) overgeslagen**, zoals gevraagd.

Suite: **3828 passed, 1 xfailed**.

---

## 4. Fase 12-audit + het getal "63" — commit `540d2e3`

Rapport: `claude/fase12_hierarchie_audit.md`. **Geen CSS gewijzigd.**

Kern: het voorstel is vier regels CSS plus twee kleine, en **geen enkele view hoeft aangeraakt te
worden**. De maat van het probleem: `.chip` staat 101 keer in 22 bestanden en kreeg in fase 9 een
zwarte rand; `.btn` trekt met 2px exact dezelfde lijn als een container. Volgorde van klein naar
groot effect staat in het rapport, zodat je tussentijds kunt kijken.

Het getal **63 klopte niet en is nooit veranderd**: het waren er 64, ook al in de commit waarin de
fase-9-inventarisatie werd geschreven. Het bruikbare getal is **33** — zoveel zijn er nog
kleur-alleen op een nu-scherm; de andere 31 zijn binnen `.nu` al geneutraliseerd. Bijna de helft
van die 33 zit in de kennisbank.

---

## 5. Drie besluiten van Stefan, uitgevoerd (20 september, avond)

**Besluit 2 — legal dedupliceren.** `legal_signaal.check()` is weg, met `_vers()`, `VENSTER_UREN`,
de `dag_begint`-haak en `HumanInbox.add_legal_signaal`. Eén bron, één uitgang. Wat je inlevert is
snelheid (maandag → de weekmemo in plaats van dezelfde dag); wat je terugkrijgt is dat er geen twee
beelden van dezelfde feed meer naast elkaar kunnen lopen. De LEZER bleef staan: `goedkeuring.py`
kent het type nog, zodat bestaande items afhandelbaar blijven. Op prod bleken er overigens **nul**
te liggen — de oude uitgang had niets openstaan.

**Besluit 3 — het scan-gaatje.** De drie meldingen gaan naar de founder via één plek
(`_meld_aan_mens`), die logt als hij nergens aankomt. De regressie gaat daarnaast nog steeds naar de
rol die hem ooit fixte; dat is een aantoonbaar feit, en `signaal` zoekt daar zelf de mens bij zonder
een project aan te maken.

**Besluit 1 — gedeployed.** PR #519, squash-merge, prod op `7f58018a0`.

| stap | uitkomst |
|---|---|
| suite lokaal vóór/ná | 3789 → 3825 passed, 1 xfailed |
| CI op de PR | beide runs groen (3m12s en 4m02s) |
| squash byte-voor-byte | tree-hash `a50e6de8…` op main **en** op de branch — identiek, niet alleen "geen conflicten" |
| predeploy-snapshot | `backups/data_predeploy_2026-09-20_1824.tgz`, 100M, eigenaar `nooch` |
| health `/` | 303 |
| diepte `/login` (raakt people.json) | **200** |
| eigendom-sweep `data/` | schoon, vóór én ná elke prod-actie |
| services | `noochville-cockpit2` en `noochville-village` beide active, daemon boot zonder traceback |

**Eén ding om te weten over deze deploy:** het draaiende `deploy.sh` was nog de OUDE versie — de
geharde variant (diepte-check + eigendom-sweep) zat ín deze pull en ging dus pas mee ná de run.
Bash leest het script bij het starten. Die twee checks heb ik daarom met de hand uitgevoerd, met de
uitslagen hierboven. Vanaf de volgende deploy doet het script het zelf.

**Smoke-test op echte data** (`village weekmemo`, droge run als `nooch`): alle vijf de adapters
draaiden, **8 signalen** (7 bewijs, 1 legal), en het dure model maakte er een echte synthese van —
inclusief de constatering dat twee Kroniek-records elkaar tegenspreken over dezelfde claim van
Vivobarefoot, en een eerlijke "wat ik niet kon zien"-slotsectie. Er is niets bezorgd en niets
onthouden: `data/weekmemo.json` bestaat nog niet. De **eerste echte memo komt bij de dagpuls van
04:32**, en die markeert de week dan wel.

Op dezelfde echte data ook de UI gerenderd (read-only): de organisatieboom draagt het rol-icoon en
het bord rendert het voortgangs-atoom en de chips-rij, zonder inline breedte. Eén observatie: op
prod is op dit moment **elke** rol in de boom bezet (een persona telt als vervuller), dus de
gestippelde vacant-cirkel is vandaag nergens te zien. Geen fout — er is niets vacant.

## 6. Wat NOG steeds niet is gedaan

- **Stap 6 (archiveren van de radar-items)** — geblokkeerd tot jouw akkoord op de uitkomst van 1-5.
- **Fase 12 toepassen** — de audit ligt er, het besluit is aan jou.
- **Fase 11 laag 3** (sleeppatroon) — wacht op het prototype-linkje.
