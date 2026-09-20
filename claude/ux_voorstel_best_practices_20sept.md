# UX-voorstel: Slack/Notion/Obsidian/Duolingo/GlassFrog/Trello-patronen op de live cockpit

**Bijgesteld na Stefans reactie op de eerste versie van dit voorstel (20 sept):**
1. **Punt 1 (organisatie) vereenvoudigd.** Geen cirkeldiagram — de platte lijst werkt prima. Alleen
   een icoon + kleur per rol (gevuld/vacant), dezelfde `.nu-status`-vormtaal die de rest van de app
   al gebruikt. Kleinste mogelijke ingreep, geen nieuwe visuele component.
2. **Het voorstel was te statisch — te veel "status tonen", te weinig "iets laten voelen".**
   Stefans woorden: "microinteracties: een project lekker slepen, hover, iets zien veranderen." Het
   HTML-prototype is daarom uitgebreid met drie *echt werkende* interacties (geen mockup-plaatje,
   klik/sleep er zelf doorheen): een kaart optillen bij hover, een kaart naar een andere kolom
   slepen met een oplichtende doelkolom, en een checklist-item aanvinken waarbij de voortgangsbalk
   direct meebeweegt. Dit voegt een nieuw, vijfde punt toe aan de bevindingen hieronder — de eerdere
   vier (nu opnieuw genummerd 2 t/m 5, GlassFrog-punt vervangen door de eenvoudige versie) blijven
   verder ongewijzigd staan. Zie het HTML-prototype voor de werkende versie.


20 september 2026. Aanleiding: Stefans eigen analyse van wat deze zes interfaces goed doet
(hierboven in het gesprek), met de vraag om dat concreet op de huidige Village-cockpit te leggen —
niet abstract, maar tegen de echte schermen na fase 9/10 (de nooch.earth-huisstijl is net
doorgevoerd). Gekeken naar vijf live schermen (Projects, Circle/Nooch, Messages, Wiki, projectdetail,
via `fase9_screenshots` op prod-stand) en `nooch-ui.css`.

## Het goede nieuws eerst: drie van de zes metaforen staan al

Stefans eigen kernregel ("één hoofdmetafoor per interface") is voor drie schermen al toegepast, en
goed:
- **Projects = Trello.** Kolommen (Active/Waiting/Done/Future), kaarten, groeperen op rol/persoon.
- **Messages = Slack.** Eén kanaalsoort, drie smaken (project/cirkel/persoon), zoekveld, kanalenlijst
  links, gesprek rechts.
- **Wiki = Notion-achtig.** Kaarten met eigenschappen (type-badge, domain-badge, owner), filterbaar,
  gegroepeerd op domein.

Dat is geen toeval: dit is precies de architectuur die fase 7-8 heeft neergezet. Het nieuwe
huisstijlsysteem (`nooch-ui.css`) is bovendien al opvallend dicht bij Stefans eigen regel "maak
status zichtbaar, nooit kleur alleen" — de `.nu-status`-vormen (cirkel/gestippelde cirkel/half
vierkant/driehoek) zijn letterlijk een toegepast UX-principe, niet alleen een kleurenpalet.

**Wat ontbreekt, is niet een nieuwe metafoor voor deze drie schermen — het is dat de metafoor niet
tot in de details is doorgevoerd, en dat twee van de zes referenties (GlassFrog en Obsidian)
nauwelijks terug te vinden zijn**, terwijl één daarvan (GlassFrog) letterlijk de dichtstbijzijnde
verwantschap heeft: dit ís een Holacracy-rollen-en-cirkels-systeem (de code noemt zichzelf al
"GlassFrog (PoC)" in de footer).

## Vijf concrete bevindingen, elk met een naam uit Stefans eigen analyse

### 1. De organisatieboom in de zijbalk is een lijst, geen kaart — GlassFrog's kernwaarde ontbreekt

Live: de zijbalk toont onder "Organization" een platte, alfabetische bullet-lijst van 13 rollen
onder Nooch (Brand & Visual Designer, Carbon Footprint Improver, ... Website Developer), zonder
enig visueel onderscheid tussen een rol met een levende vervuller en een lege rol, zonder groepering
op sub-cirkel, zonder enige ruimtelijke aanwijzing dat dit een cirkel-in-cirkel-structuur is.

Stefans eigen analyse, letterlijk: *"gebruik de representatie die het mentale model van de gebruiker
het beste weerspiegelt... soms is het een kaart van rollen en cirkels."* Voor déze app is dat geen
verre analogie — het IS een rollen-en-cirkels-app. Een lijst van 13 namen is de spreadsheet-versie
van wat GlassFrog als kaart toont.

**Voorstel**: vervang de platte lijst door een klein, ruimtelijk cirkel-diagram (grote cirkel Nooch,
rollen als knopjes eromheen, gevulde stip = bemand, lege stip = vacature — hergebruikt de bestaande
`.nu-status`-vormtaal, geen nieuwe visuele taal nodig). Dat lost twee dingen tegelijk op: het maakt
in één oogopslag zichtbaar hoeveel vacatures er zijn (nu onzichtbaar, moet je 13 namen mentaal
tegen een oude lijst afzetten), en het geeft de zijbalk een eigen identiteit die past bij wat dit
systeem daadwerkelijk is, in plaats van een generieke linklijst zoals elke andere admin-tool.

### 2. Het Circle-scherm heeft acht tabs en geen primaire actie — schendt Stefans eigen regel #2

Live: `Nooch` (het Circle-scherm) toont 8 gelijkwaardige tabs (Overview/Roles/Members/Goals/Wiki/
Projects/Checklists/Metrics) plus twee losse knoppen (Governance/Tactical meeting) erboven, en de
Overview-tab zelf is drie regels tekst ("Purpose", "Strategy: no strategy defined", "Domains: no
domain"). Niets op dit scherm zegt "dit is de ene actie die je hier meestal komt doen."

Stefans eigen regel, letterlijk: *"op elk moment is meestal duidelijk wat je moet doen... een
interface wordt moeilijk wanneer meerdere acties visueel even belangrijk lijken."* Acht tabs zonder
hiërarchie is exact dat probleem.

**Voorstel**: geen tabs wegnemen (die dekken echte, verschillende dingen), maar de Overview-tab
vervangen door het cirkel-diagram uit punt 1, ditmaal groter en met de purpose/strategy als
onderschrift eronder in plaats van als hoofdinhoud — zodat je bij binnenkomst eerst de vorm van de
cirkel ziet (wie zit erin, wat zijn de sub-cirkels), en pas daarna de tabs voor de details.

### 3. Projectkaarten op het bord tonen bijna niets — Trello's eigen kernregel gemist

Live: een kaart op het Projects-bord toont alleen titel + "no owner · today". Geen checklist-
voortgang, geen deadline, geen label/batch-chip, geen avatar. Om te weten of een project aandacht
nodig heeft, moet je 'm openen — de projectdetailpagina zelf heeft wél alle info (12 velden in de
Details-kolom: Status, Assignee, Deadline, Goal, Effort, etc.), maar die zit verstopt achter een
klik per kaart.

Stefans eigen analyse, letterlijk: *"een kaart bevat detail zonder het overzicht te verliezen... 
labels, leden en deadlines zijn scanbaar."* Dat is precies het stuk dat nu ontbreekt: de kaart is een
titel, geen Trello-kaart.

**Voorstel**: kaartvoorkant uitbreiden met (in volgorde van waarde): checklist-teller ("2/5") als
die niet leeg is, deadline als chip als die gezet is, batch/categorie als klein badge-chipje (al een
bestaand concept, nu alleen zichtbaar in de Details-kolom). Geen nieuwe velden, alleen de al
bestaande projectvelden zichtbaar maken op het niveau waar je ze het eerst nodig hebt.

### 4. Messages heeft geen enkel Slack-signaal — geen ongelezen, geen urgentie

Live: de kanalenlijst (Projects/Circles, straks ook Topics en Persons) toont kanaalnamen zonder
enige aanduiding van nieuw/ongelezen. Slacks eigen kernpatroon — *"mentions, badges en
notificaties maken urgentie zichtbaar"* — ontbreekt volledig. Met de acute schaal die al eerder
deze fase is vastgesteld (442 niet-gearchiveerde projecten/kanalen), is dit geen esthetisch punt:
zonder ongelezen-indicator moet je 442 kanalen langslopen om te weten waar iets nieuws is.

**Voorstel**: vetgedrukte kanaalnaam + klein stipje/telling voor kanalen met ongelezen berichten
sinds je laatste bezoek, dezelfde plek en vorm als de bestaande `msg-kanaal`/`.nu-status`-taal. Dit
sluit direct aan bij het zoek/filterveld dat nu al gebouwd wordt (fase 10, punt 1a) — het is
dezelfde onderliggende noodzaak (442 kanalen, geen manier om te zien waar iets toe doet) opgelost
vanuit een ander patroon: niet alleen zoeken, ook prioriteren op ongelezen.

### 5. Wiki-kaarten tonen geen relaties — Obsidian's kernwaarde ontbreekt volledig

Live: de "Selco (supplier)"-notitie in de Wiki toont owner + één zin tekst, maar niets over wélke
projecten of gesprekken naar deze pagina verwijzen. Op de projectdetailpagina van "Marktstand
materiaal-expo" staat een bericht dat letterlijk over Selco gaat ("Selco levert in drie weken"), en
er is een "Keep in wiki"-knop om content NAAR een wiki-pagina te sturen — maar geen enkele plek laat
zien dat die twee dingen al met elkaar te maken hebben.

Stefans eigen analyse, letterlijk: *"backlinks tonen waarom een notitie relevant is... kennis is geen
hiërarchische mapstructuur, maar een netwerk."* Dat netwerk bestaat inhoudelijk al (Keep-in-wiki
legt de link vast, `AttachmentStore.meta["feiten"]` bewaart herkomst) — het wordt alleen nergens
getoond.

**Voorstel**: één regel onder elke wiki-kaart, "Genoemd in: 2 projecten" met een klein uitklapbare
lijst — geen graph view (dat is voor een latere ronde, als de hoeveelheid content dat rechtvaardigt),
puur de tekstuele "backlinks tonen"-versie die Obsidian ook als basis heeft voordat de graph erbij
kwam.

## Wat dit niet is

Geen van de vijf punten hierboven is een nieuw datamodel-concept — dit is bestaande data
(checklist-voortgang, deadline, herkomst-koppeling, rol-bemanning, ongelezen-status straks uit fase
10 punt 1) anders tonen, niet nieuw verzamelen. Dat is expres: net als bij de fase 8/9/10-lessen tot
nu toe is de goedkoopste, laagste-risico winst een presentatievraag, geen backend-vraag.

## Aanbevolen volgorde

1. **Kanaal-ongelezen-indicator (punt 4)** — smelt samen met het zoekveld dat al in fase 10 punt 1
   wordt gebouwd, dus nu meenemen is bijna gratis.
2. **Projectkaart-voorkant (punt 3)** — puur presentatie op al bestaande velden, geen nieuwe
   afhankelijkheid, kleinste stap met directe dagelijkse waarde.
3. **Wiki-backlinks (punt 5)** — iets meer werk (moet de al bestaande herkomst-relatie opzoeken en
   tonen), maar nog steeds zuiver leeswerk op bestaande data.
4. **Cirkel-diagram (punt 1+2)** — het grootste en meest waardevolle stuk, maar ook het enige met
   een echt nieuw stuk visuele component (SVG/canvas in plaats van een lijst). Verdient een eigen
   scoping-ronde zoals de eerdere kanaal-datamodel-vragen, niet blind bouwen.

Zie het bijgevoegde HTML-prototype voor hoe dit er concreet uitziet, met de bestaande `nooch-ui.css`-
tokens (crème achtergrond, één limoengroen accent, zwarte 2px randen, hoofdletterkoppen) — geen
nieuwe designtaal, dezelfde taal verder toegepast.
