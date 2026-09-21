# Ontwerpdocument: Wiki inline-editen en Messages-kanaalmodel (21 september)

*Dit is geen opruim-item. Dit is een vervangingsopdracht: het huidige model gaat eruit, niet
"verbeteren". Claude Code: stuur eerst een kort technisch ontwerp terug (welke databron, welke
structuur, welke risico's) voordat je gaat bouwen — pas na akkoord daarop bouwen. Dit voorkomt dat
het weer een patch wordt op het bestaande model, wat bij de vorige twee pogingen (wiki-editknop
#529, kanaal-opruiming #530) wél is gebeurd omdat de opdracht als opruiming was geformuleerd terwijl
het eigenlijk nieuwbouw is.*

## Waarom dit een apart traject is

Sinds 19 september stond alles in opruim-modus: dode code weg, minder regels, meer consistentie —
kleinste ingreep, niets nieuws tenzij het moet. Dat is de juiste reflex voor opruiming en de
verkeerde reflex voor dit werk. Wiki-editen en het kanalenmodel vragen om een ander databronmodel,
niet om een zichtbaardere knop op het bestaande model. Vandaar deze aparte, expliciet als
"vervanging" gemarkeerde opdracht.

---

## 1. Wiki: inline editen, geen apart formulier

**Huidige situatie (geverifieerd op prod, `/pagina?id=NOTE-COMPLI-021`)**: de opgemaakte tekst staat
bovenaan, in een eigen kader. Klik je op "Edit page" (of het kleine "edit"-linkje eronder), dan
verschijnt daaronder een volledig apart blok: een TITLE-veld en een BODY-textarea met de ruwe
markdown-bron (`## Four conditions`, `- **On the list.**`, etc.) plus een mini-toolbar (B/I/S/•/H/
oogje-preview). De opgemaakte weergave blijft intussen gewoon bovenaan staan, losstaand van waar je
typt. Dit is een formulier-onder-de-content-model, geen inline-model.

**Gewenst**: je klikt in de tekst zelf (of op een duidelijke "bewerken"-toggle voor de hele pagina)
en de content zelf wordt editable, op precies de plek waar hij staat. Opmaak (vet, koppen,
lijstjes) blijft zichtbaar terwijl je typt — geen aparte ruwe-markdown-weergave als standaard
aanzicht. Denk aan hoe Notion een pagina behandelt: klikken = daar typen, niet klikken = ergens
anders een los formulier invullen.

**Niet-onderhandelbaar**:
- Geen zichtbare tweede content-kopie (opgemaakt boven, ruw eronder) tijdens het bewerken.
- Opslaan gebeurt op dezelfde plek als waar je las, geen page-scroll naar een ander blok.
- De geschiedenis-functie ("historie (1)") en de Facts/Links-secties eronder blijven bestaan zoals
  ze zijn — dit gaat alleen over het bewerken van de hoofdtekst.

**Open voor Claude Code om te scopen**: of de onderliggende opslag markdown blijft (waarschijnlijk
wel, gezien de rest van het systeem) met een contenteditable/rich-text-laag ervoor, en wat de
kleinste betrouwbare manier is om dat te bouwen zonder een zware editor-library te importeren die
niet bij de rest van de stack past.

---

## 2. Messages: geen automatische volledige kanalenlijst, kanalen zijn bewust

**Huidige situatie (geverifieerd op prod, `/messages`)**: de kanalenlijst toont standaard alle 159
projecten als kanaal ("PROJECTS 25 of 159 · search for the rest"), plus alle DM-kanalen. Er is geen
apart concept van "kanalen die je volgt" versus "alles wat ooit een project was".

**Stefans drie punten, letterlijk verwerkt**:
1. De Inbox-pagina/functie is overbodig — Messages dekt dit nu. **Inbox-navigatie-item en -route
   verwijderen**, niet alleen verbergen.
2. Messages moet niet standaard alle projecten tonen. Een project moet je eerst kunnen **zoeken**,
   en dan pas **selecteren/toevoegen** aan je zichtbare lijst — niet fungeren als kanaal totdat jij
   dat besluit.
3. Vergelijk met Slack: één algemeen kanaal, en daarna kanalen per thema. Stefan noemt dit expliciet
   "per doel" — wat al bestaat als eerste-klas concept in Projects (de Goal-filter: ALL, WEBSITE,
   STCB, MITH, BATCH 4, SUPPLY CHAIN). Kanalen worden bewust aangemaakt door iemand, niet automatisch
   gegenereerd per project.

**Gewenst model**:
- **Eén algemeen kanaal** (village-breed), altijd zichtbaar.
- **Eén kanaal per doel/Goal** (dezelfde vijf/zes Goals die Projects al kent), automatisch aanwezig
  omdat de Goal-taxonomie al bestaat — geen losse aanmaakstap nodig voor deze laag.
- **Losse kanalen** (huidige "+ new channel"-functie) blijven bestaan voor iets dat geen project en
  geen Goal is — bewust aangemaakt door een mens, zoals nu.
- **Projecten worden geen kanaal meer by default.** Een project vinden gebeurt via zoeken (het
  bestaande "FIND A CHANNEL"-zoekveld, of eventueel vanuit de projectkaart zelf een link naar zijn
  gespreksdraad); pas als je 'm opent of expliciet toevoegt verschijnt hij in je lijst.
- **DM-kanalen** (de `dm:<a>|<b>`-vorm uit de kanaal-inventarisatie) blijven bestaan zoals ze zijn —
  dit gaat niet over die laag, alleen over de project-afgeleide kanalen die nu de lijst vullen.

**Relatie met de dode-kanalen-inventarisatie (`inventaris_kanalen_21sept.md`)**: die opruiming
(archiveren van de 13 dode + subcategorieën) kan gewoon los doorgaan zodra Stefan zijn regel per rij
heeft gegeven — dat is data-opruiming, dit hier is het lijst-gedrag zelf. Ze raken elkaar wel: zodra
kanalen niet meer automatisch uit elk project ontstaan, is de kans op nieuwe dode kanalen in de
toekomst een stuk kleiner, dus dit voorkomt een deel van het probleem dat de inventarisatie nu
oplost.

**Open voor Claude Code om te scopen**: hoe "toevoegen aan je lijst" technisch het handigst werkt
gegeven de bestaande databron (blijft een project-kanaal net zo goed bestaan, alleen ongefilterd uit
het zicht totdat je het zoekt/toevoegt, of wordt er een echt aparte "gevolgd"-vlag nodig).

---

## Volgorde van opleveren

Geen harde volgorde vereist, maar Wiki en Messages raken andere delen van de code en kunnen dus
parallel of na elkaar, net wat Claude Code het handigst vindt. Wel eerst het technisch ontwerp terug
naar Stefan/Claude (dit gesprek), pas daarna bouwen.
