# Voorstel — de inbox opheffen en als kanaal in Messages laten landen

**Datum:** 20 september 2026 · **Status:** voorstel, niets gebouwd
**Besluit dat hieraan voorafgaat:** Stefan, nacht van 19 op 20 september — *"inbox moet gewoon weg,
dat wordt een kanaal in messages"*. Dat draait de fase-8-keuze om waarin `NotifStore` en `/inbox`
bewust ongewijzigd naast de kanaallaag bleven staan.

---

## 1. Eerst het cijfer dat de hele vraag verandert

Ik ben deze migratie blijven beschrijven als "de 338 rol-notificaties". Dat getal is de **totale
historie**, niet de wachtrij. Gemeten op prod vanmorgen:

| | |
|---|---:|
| notificaties totaal | **371** |
| — gericht op een rol | 338 |
| — gericht op een persoon | 33 |
| **open (niet gearchiveerd, niet verwijderd, niet done)** | **28** |

De rest is dicht: 225 gearchiveerd, 52 verwijderd, 33 done. **De wachtrij is 28 items.** Dat maakt
de migratie kleiner dan ze klonk — en het bewaren van de historie juist belangrijker dan het
verplaatsen van de wachtrij, want 343 van de 371 zíjn historie.

De verwerkingsstate over alle 338 rol-items:

```
read 259 · processed 258 · archived 225 · done 33 · deleted 52
outcome 185 · poort 54 · verwerkingen 83
```

---

## 2. Je eerste vraag: is elke rol eenduidig naar één mens te herleiden?

**Nee.** Voor 9 van de 28 open items wel, voor 19 niet. Geen enkele is machinaal af te leiden.

| doel-rol | open | staat | mens-vervullers |
|---|---:|---|---|
| `mother_earth__nooch__marketing_lead` | 5 | levend | **1** ✓ |
| `mother_earth__nooch__creator_of_shoes` | 2 | levend | **1** ✓ |
| `mother_earth__nooch__strategic_lead_founder_steward` | 2 | levend | **1** ✓ |
| `librarian` | 8 | **gearchiveerd** | 0 |
| `harry_hemp` | 5 | **gearchiveerd** | 0 |
| `mother_earth__nooch__noochville__copywriter` | 2 | **gearchiveerd** | 0 |
| `compliance` | 2 | **gearchiveerd** | 0 |
| `concurrent_scout` | 2 | **gearchiveerd** | 0 |

Die vijf gearchiveerde rollen zijn in fase 1–3 opgeruimd. Ik heb gekeken of `data/afslanken.jsonl`
een opvolger vastlegt — er ís een `naar`-veld, maar dat is bij **alle vijf leeg**. De opvolger staat
alleen in Nederlands proza in het `reden`-veld, en voor twee van de vijf is er bewust **geen**:

| rol | opvolger volgens `reden` |
|---|---|
| `librarian` | *"de 6 accountabilities en het domein bibliotheek gaan naar Strategic Lead & Founder Steward"* |
| `harry_hemp` | *"de 8 accountabilities en het domein onderzoeksmethode gaan naar Strategic Lead & Founder Steward"* |
| `copywriter` | *"vervallen-case: purpose en de 5 accountabilities gaan NIET naar een andere rol"* — **geen opvolger** |
| `concurrent_scout` | *"vervallen BEWUST, ze gaan niet naar een andere rol"* — **geen opvolger** |
| `compliance` | geen `archiveer_rol`-regel; het levende `mother_earth__nooch__compliance` bestaat wél |

Een regex op dat prozaveld loslaten om er een rol-id uit te vissen is precies de soort aanname waar
je me voor waarschuwde. **Ik kies hier niets.**

---

## 3. Mijn voorstel: de ambiguïteit verdwijnt door niet naar een persoon te vertalen

De vraag "naar welke mens gaat dit?" ontstaat alleen als het bericht in een **persoonskanaal**
landt. Dat hoeft niet.

### Voorgestelde vorm: een vijfde kanaalsoort, `role:<record_id>`

Eén kanaal per rol, met dezelfde vorm als de andere vier. Drie redenen:

1. **De notificatie is aan een ROL gericht, niet aan een mens.** Zet je compliance' 69 items in
   Stefans DM, dan loopt die historie de deur uit zodra iemand anders compliance vervult. Dat is
   dezelfde fout als een kanaal-id dat een naam is: identiteit mag niet aan de huidige invulling
   hangen. Precies het argument waarmee je gisteren optie A koos.
2. **De negentien ambigue items lossen zichzelf op.** Een gearchiveerde rol houdt gewoon zijn
   kanaal, read-only. Er hoeft niemand aangewezen te worden, want er wordt niets verplaatst — het
   staat waar het altijd al stond, alleen in een andere vorm.
3. **Wie het ziet, volgt uit governance en niet uit een lijst.** Je ziet de rolkanalen van de
   rollen die je vervult — dezelfde afleiding die `/inbox` nu al doet met `_person_targets`.

De alternatieven en waarom niet:

| vorm | waarom niet |
|---|---|
| persoonskanaal (DM) van de huidige houder | vereist voor 19 items een keuze die niemand kan maken, en laat historie met een persoon meeverhuizen |
| het topic-mechanisme van gisteren | een topic heeft een zelfverzonnen naam en geen ouder; een rolkanaal heeft juist wél een ouder, en dat is het hele punt |
| `circle:<record_id>` hergebruiken voor rollen | werkt technisch (rollen zijn ook records), maar dan heet een rol een cirkel op het scherm — een leugen in het datamodel |

### De harde eis: de verwerkingsstate blijft zichtbaar

Niet-onderhandelbaar, en zo bedoel ik het te doen: elk bericht krijgt `kind="notificatie"` in
plaats van `"comment"`, en een `verwerking`-blok dat de velden **letterlijk overneemt**:

```
{"read": …, "processed": …, "archived": …, "done": …,
 "outcome": …, "poort": …, "verwerkingen": [...], "type": …, "bevinding": …}
```

Geen herinterpretatie, geen samenvatting, geen afgeleide status. Het scherm rendert dat blok onder
het bericht. Er is één guard-test die telt: **185 outcomes en 54 poort-oordelen vóór, dezelfde
aantallen ná** — faalt hij, dan is de migratie fout en gaat hij niet door.

### `/inbox` wordt een filter

Route en scherm vervallen. De lade blijft, maar leest kanalen in plaats van `NotifStore`: berichten
met `kind="notificatie"`, status open, op de rolkanalen die jij vervult. De teller telt hetzelfde.

---

## 4. Wat dit kost — en waarom ik dat vooraf zeg

`NotifStore` verwijderen is geen kleine snede:

```
13 methodes in gebruik, 46 aanroepen, over 18 bronbestanden
37 testbestanden raken NotifStore aan
2 routes (/inbox, /inbox/verwerk) plus een redirect op /inbox?done=
```

Dat is ruim groter dan alles wat ik gisteren aan punt 1b en 4 deed. Het is te doen, maar niet in
één commit en niet zonder dat er iets tussen zit dat ik nu niet zie.

**Mijn advies voor de volgorde:**

1. Het rolkanaal + de migratie **schrijven naast NotifStore**, met de telling-guard. Niets
   verwijderen. Dan is de uitkomst te bekijken vóór er iets onherroepelijk is.
2. `/inbox` omzetten naar de kanaal-lezing. Dan draait het nieuwe pad echt.
3. Pas als dat een tijdje staat: `NotifStore` en de oude routes eruit.

Stap 3 in dezelfde beurt doen betekent dat een fout in stap 1 de historie van 371 items meeneemt.
De data staat in `backups/data_2026-09-19_2341.tgz`, maar een terugrol kost je dan ook alles wat er
sindsdien is gebeurd.

---

## 5. Wat ik van je nodig heb

1. **Akkoord op `role:<record_id>` als vijfde soort** — of zeg dat je toch het persoonskanaal wilt,
   en wat er dan met de 19 items op gearchiveerde rollen moet gebeuren.
2. **De vijf gearchiveerde rollen**: blijven hun kanalen bestaan als read-only historie (mijn
   voorstel), of wil je ze bij een opvolger onderbrengen? In dat laatste geval heb ik per rol jouw
   woord nodig, want `afslanken.jsonl` zegt het niet en voor twee van de vijf is het antwoord
   volgens datzelfde bestand "niemand".
3. **Akkoord op de drie stappen** hierboven, of de opdracht om het in één keer te doen.
