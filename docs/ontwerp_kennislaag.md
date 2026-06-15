# Ontwerp: Kennislaag NoochVille

Status: concept, niet geïmplementeerd. Vastgelegd 15 juni 2026 als
fundament voor de toekomstige kennis-architectuur van NoochVille.

## Aanleiding

Vrijdagavond 12 juni bracht Stefan twee rijke externe datasets binnen
(Customer Insights masterdeck, SE Ranking/Semrush keyword-gap data).
Vandaag (15 juni) werd duidelijk dat NoochVille's huidige architectuur
geen mechanisme heeft om dit soort fuzzy menselijke input structureel
op te nemen. De huidige inhabitants (tijdgeest_wachter, kennis_scout,
analyst) zijn rapporteurs die zelf data sensen, geen ingestie-laag voor
door-mens-aangeleverde kennis.

Tijdens het gesprek over Customer Insights kwam Söhnke Ahrens' "How to
Take Smart Notes" ter sprake. De Zettelkasten-methode bleek
fundamenteel passend bij wat NoochVille nodig heeft, maar met een
belangrijk verschil: wat voor mensen een disciplinair probleem is (drie
cognitieve modi tegelijk volhouden: fleeting, literature, permanent),
is voor een mens-LLM-koppel een natuurlijke werkverdeling. De mens
dumpt fuzzy, de LLM doet het herformuleringswerk, samen ontstaan
atomaire permanent notes.

Dit ontwerp legt de kennis-architectuur vast die uit dat inzicht
voortvloeit.

## Kerninzicht: mens-LLM-werkverdeling lost discipline-probleem op

De Ahrens-methode vraagt van mensen drie cognitieve modi tegelijk te
houden: fleeting (snel iets noteren als het opkomt), literature (in
eigen woorden herformuleren met bron), permanent (atomair, autonoom,
gelinkt). Dat zijn heel verschillende cognitieve modi en mensen zijn
slecht in tegelijkertijd-modus-houden. Dat is de kern van waarom
Zettelkasten zo theoretisch sterk is maar in praktijk vaak verzandt.

In een mens-LLM-koppel vervallen die schakelkosten:
- Mens dumpt fuzzy ("er was iets over zero-waste als kernwaarde, denk
  in de Customer Insights-deck").
- LLM doet het werk tussen fleeting en permanent: herformuleert in
  atomaire eenheden, stelt verbindingen voor, voert context aan,
  stelt verhelderingsvragen.
- Mens valideert, scherpt aan, beslist over verbindingen.

Permanent notes ontstaan als bijproduct van het gesprek tussen die
twee. Dat is geen "AI verbetert mijn workflow". Dat is een
fundamenteel andere kennisproductie-structuur dan wat Ahrens voor
mensen schreef.

## Drie rollen in de kennislaag

### 1. Ingestie-rol

**Mandaat**: dialoog met geautoriseerde mensen om fuzzy input om te
zetten naar atomaire, autonoom-leesbare eenheden.

**Werk**: ontvangt input statement-voor-statement (geen
dump-in-één-keer), stelt verhelderingsvragen waar nodig, stelt
herformuleringen voor, helpt bron-metadata vast te leggen, geleidt
naar de librarian zodra een atomaire eenheid gereed is.

**Niet content-specifiek**: kan over alles gaan, van customer
insights tot artikelen tot productie-observaties.

**Toegang**: bepaalde mensen krijgen autoriteit om met de
ingestie-rol te praten. Die mensen kunnen op hun beurt input
verzamelen bij anderen. Geen open toegang, geen democratisering.
Wel delegatie van kennis-verzameling.

### 2. Librarian-rol (per cirkel)

**Mandaat**: data gestructureerd vastleggen, onderhouden,
beschikbaar maken binnen de eigen cirkel.

**Werk**: bewaakt atomariteit (één idee per notitie), beheert
verbindingen tussen notities binnen de cirkel, signaleert
conflicten of overlap met bestaande notities, controleert of een
nieuwe notitie al bestaat in een variant.

**Per cirkel één librarian**: kennis is cirkel-specifiek. Wat in
de ene cirkel atomair is, kan in de andere irrelevant zijn. Een
notitie over een keyword-bevinding leeft in SEO-cirkel, een
notitie over een leveranciersrelatie in Productie-cirkel.

**Continu actief**: niet alleen op aanvraag, ook tussen ingestie
en opslag in.

**Apart van Secretary**: Library en Secretary worden gesplitst.
Secretary doet governance-integriteit (validatie, registratie van
rolwijzigingen). Librarian doet kennis-integriteit. Andere lagen,
andere expertise.

### 3. Domein-rapporteurs

**Mandaat**: haalt uit de library wat in hun domein hoort, brengt
het in beeld voor andere rollen of voor mensen.

**Voorbeelden**:
- Customer Insights-rapporteur: trekt uit library wat over
  klanten bekend is, voor missie- of groei-strategische vragen.
- Market-trends-rapporteur: combineert library met externe data
  (GDELT, Google Trends) voor markt-trend-signalen.
- Policy-rapporteur: trekt uit library wat over wetgeving en
  certificering bekend is, voor missie-strategische steun.

**Domein-specifiek per rol**: één rapporteur per domein, geen
alleskunners.

## Cross-cirkel kennis: pull-request principe

Wanneer een cirkel of mens een vraag heeft die meerdere cirkels
raakt ("we moeten besluiten of x, of we hebben doel y te bereiken"),
worden de rollen aangeroepen die in de relevante libraries kunnen
graven. Zij rapporteren terug, eerst aan de mens (in fase 1), later
mogelijk aan een synthese-rol (fase 2).

Geen automatische globale beschikbaarheid van kennis. Wel
beschikbaarheid op expliciete aanvraag. Dat past bij Holacracy:
cirkels hebben autonomie binnen hun domein, samenwerking ontstaat
door expliciete vraag, niet door allesomvattende transparantie.

**Pull-request werkt ook over instrument-grenzen**: NoochVille als
één systeem is niet de eindstaat. Meerdere kennislagen kunnen elkaar
dienen, mogelijk zonder centrale unificatie. De pull-request-
mechaniek werkt in principe ook naar libraries in andere systemen
of naar libraries die naast NoochVille bestaan.

## Drie soorten notities (Ahrens-vertaling)

- **Fleeting**: tijdelijke notities die in de ingestie-dialoog
  ontstaan. Niet bedoeld om te bewaren, alleen om mee te werken
  in het gesprek tussen mens en ingestie-rol.

- **Literature**: notities die de essentie van een externe bron
  vastleggen in eigen woorden, met bron-metadata. Tussenstap van
  fleeting naar permanent.

- **Permanent**: atomaire, autonoom-leesbare eenheden in de
  library. Eén idee per notitie. Gelinkt aan gerelateerde
  notities. Geen kopieer-werk.

## Werkverdeling mens en LLM

- **Mens (Stefan, in fase 1)**: levert fuzzy input, valideert
  herformuleringen, beslist over verbindingen die de ingestie-rol
  voorstelt, kent context die niet uit de tekst alleen blijkt.

- **Ingestie-rol (LLM-gebaseerd)**: doet het werk tussen fleeting
  en literature/permanent. Stelt verhelderingsvragen, formuleert
  herhalingen voor, stelt verbindingen voor.

- **Librarian (LLM-gebaseerd)**: onderhoudt de structurele
  integriteit van de library. Beslist niet over inhoud, wel over
  vorm en samenhang.

## Cirkelstructuur en governance over de kennislaag

Per cirkel komt er een librarian. Plus een rol (of mens) die via
holacratisch proces bepaalt hoe binnen die cirkel data wordt
vastgelegd: wat is een atomaire eenheid, welke metadata is
verplicht, welke verbindingen worden actief bijgehouden. De
librarian voert uit wat governance heeft besloten over hoe.

In fase 1 bestaan er nog geen formele cirkels in NoochVille. De
huidige inhabitants zijn los georganiseerd. Cirkels kunnen later
ontstaan, en de kennislaag groeit daar parallel mee mee.

## Schaal-overweging

Stefan's visie ziet NoochVille uiteindelijk groeien naar mogelijk
honderd inhabitants. Niet vandaag, mogelijk over jaren, mogelijk
nooit. Maar het kennislaag-ontwerp moet die deur niet dichtdoen:
ontwerp zo dat groei naar veel libraries en veel rollen technisch
mogelijk blijft. Als het technisch niet kan, ontstaan er gewoon
losse cirkels naast elkaar zonder centrale unificatie. Dat is
acceptabel.

## Open vragen, vast te leggen voor latere uitwerking

1. **Datamodel**: hoe ziet een permanent note er technisch uit?
   Pydantic-model met velden voor content, metadata, connecties,
   bron. Te ontwerpen voor implementatie.

2. **Verbindingen-mechaniek**: hoe legt de librarian verbindingen
   vast? Bidirectionele links zoals in moderne Zettelkasten-tools
   (Roam, Obsidian, Logseq)? Tags? Beide? Implementatiekeuze die
   het ophaalpad voor rapporteurs bepaalt.

3. **Cross-cirkel-notities**: een notitie kan voor meerdere
   cirkels relevant zijn. Twee opties: dupliceren met
   cirkel-specifieke context (verlies van atomairiteit) of op één
   plek met cross-cirkel-verwijzingen (behoud van atomairiteit,
   mechanisme voor cross-references nodig). Voorlopige voorkeur:
   het tweede, in lijn met Ahrens.

4. **Relatie tot bestaande inhabitants en data-opslag**: vervangt
   de librarian bestaande data-opslag (Library, ObservationLog,
   Lexicon), of komt 'ie ernaast te staan? Migratie-pad te
   ontwerpen.

5. **Librarian-splitsing**: is "kennis-integriteit" één coherent
   mandaat of splitst het in praktijk in twee rollen
   (orde-bewaker en semantisch-curator)? Te beslissen na eerste
   bouw als de last zichtbaar wordt.

6. **Trigger voor ingestie**: hoe komt een ingestie-sessie tot
   stand? Mens initieert? Andere rol verwijst door bij vondst van
   externe bron? Te ontwerpen.

7. **Autorisatie-mechanisme**: wie mag met de ingestie-rol praten?
   Hoe wordt autoriteit toegekend en ingetrokken? Hoort dit bij
   governance of bij operationeel toegangsbeheer?

## Verbinding met visie

Dit ontwerp realiseert drie pijlers uit visie_noochville.md:

- **Pijler 4 (strategie-vriendelijk gebouwd)**: de library is de
  structurele data-laag waaruit toekomstige strategische rollen
  putten. Niet wegwerp, expliciet bewaard voor latere bevraging.

- **Pijler 2 (mens-AI harmonie)**: de werkverdeling tussen mens
  (fuzzy input, validatie, context) en LLM (herformulering,
  verbinding, integriteit) is geen vervanging maar samenwerking
  in de geest van de visie.

- **Pijler 3 (missie-strategisch fundamenteler)**: de
  domein-rapporteurs kunnen zowel groei-strategische (markt,
  product) als missie-strategische (steward ownership, beleid)
  domeinen bedienen. De architectuur staat beide toe.

## Volgende stappen (in volgorde, ná akkoord op dit ontwerp)

1. Datamodel ontwerpen (Pydantic) voor de drie notitie-types
   en hun verbindingen.
2. Eerste bouw van de librarian-rol voor één cirkel (orde en
   opslag).
3. Eerste bouw van de ingestie-rol (mens-dialoog).
4. Migratie van Customer Insights als eerste real-world test.
5. Eerste domein-rapporteur bouwen (Customer Insights), zodat
   de end-to-end-flow getest kan worden.

Geen van deze stappen vandaag. Eerst akkoord op dit ontwerp, dan
op een later moment beginnen.
