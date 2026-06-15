# Ontwerp: Governance Ritueel voor NoochVille

Status: concept, niet geïmplementeerd. Vastgelegd 15 juni 2026 als
startpunt voor latere bouw. Volledig ontwerp wacht op herlezing
Holacracy v5 constitution door Stefan.

## Uitgangspunt

NoochVille volgt het Holacracy v5 model voor scheiding van governance
en operationeel werk. De constitutie is de bron, dit document is de
vertaling naar een agent-systeem.

## Eerste keuzes (Stefan, 15 juni)

**Type ritme**: mens-getriggerd, niet klok-gebaseerd. Stefan triggert
governance-modus expliciet. Operatie pauzeert tijdens governance.

**Doel**: efficiënt systeem (niet wachten op vaste tijdslots als er
niks is, niet doorgaan als er governance-werk klaar staat).

**Werkverdeling tijdens governance**:

- Secretary tussen twee governance-momenten in: verzamelt spanningen,
  classificeert (tactisch vs governance), bereidt agenda voor.
- Stefan bij start governance: ontvangt agenda met open
  governance-spanningen plus Secretary's voorgestelde acties plus
  classificatie. Doorloopt één voor één: keurt goed, past aan,
  pakt door. Governance sluit als agenda leeg is.

**Verschil tussen governance-ritueel en huidige inbox-CLI**:

- Governance verwerkt een agenda van meerdere items in één sessie,
  Secretary is gids.
- Huidige inbox-CLI verwerkt één item per commando, transactioneel.
- Beide blijven naast elkaar bestaan, governance is structurele bouw,
  inbox is dag-tot-dag operationeel.

## Inzicht 15 juni: mens als rol

Tijdens het gesprek over het governance-ritueel kwam Stefan tot een
herframing: de mens is óók een rol in het systeem, met een
projectenbord, accountabilities, en zichtbaarheid voor andere rollen.

Concreet zou dit betekenen:

- Stefan heeft een record in governance_records.json met purpose,
  accountabilities, domains, skills.
- Stefan's werk-in-uitvoering is zichtbaar voor inhabitants via een
  projectenbord, zodat het dorp weet waar Stefan aan werkt.
- Stefan's persoonlijke inbox (huidige items als project-suggesties
  vanuit zijn richting) hoort mogelijk thuis in zijn rol-projectenbord,
  niet in een aparte mens-inbox.

### Tweedeling: eigenaar versus rolhouder

Stefan's rol in het systeem heeft twee lagen die helder gescheiden
moeten blijven, in lijn met Holacracy v5:

1. **Stefan als eigenaar (anchor van Nooch.earth)**:
   - Staat buiten governance.
   - Kan in laatste instantie de constitutie wijzigen of het systeem
     stoppen.
   - Wordt zelden expliciet gebruikt. Bestaat omdat ergens iemand de
     laatste verantwoordelijkheid moet dragen.

2. **Stefan als rolhouder ("Stefan-rol", naam te bepalen)**:
   - Valt volledig onder governance.
   - Accountabilities (eerste denken): input geven aan het dorp,
     verbinding leggen met externe bronnen, troubleshooting bij
     onverwachte systeemstaat.
   - Heeft een projectenbord dat zichtbaar is voor andere rollen.
   - Bezwaren tegen voorstellen die deze rol raken worden net zo
     getoetst als bij andere rollen. Bij een geldig bezwaar moet
     Stefan ook nadenken over een aangepast voorstel om de spanning
     op te lossen.

Het overgrote deel van de tijd opereert Stefan als rolhouder, niet
als eigenaar. De eigenaar-pet is een uitzondering, niet een
standaard.

### Open vragen (te verfijnen na constitutie-herleting)

1. Bestaat Stefan als gewone rol (zelfde regels als andere rollen)
   of als speciale categorie (human role) met aparte regels? Holacracy
   v5 zegt: gewone rol. Praktische verschillen: mens sensed niet
   automatisch, wordt niet vanzelf wakker, heeft andere skills.

2. Wordt de huidige inbox vervangen door een rol-projectenbord,
   naast elkaar, of geïntegreerd? Want als mens een rol is, dan zijn
   de items in zijn inbox eigenlijk projecten in zijn rol.

3. Rolnaam: "Stefan-rol" als werknaam is prima, maar Holacracy-rollen
   hebben beschrijvende namen, geen persoonsnamen. Echte rolnaam te
   bepalen (bijv. "Anchor Liaison", "External Connector").

4. Kan Stefan's rol via governance worden geamendeerd, en wie modereert
   dat? Stefan is zowel rolhouder als governance-moderator. Holacracy
   v5 normaliseert dit (CEO-rollen worden ook door governance
   vormgegeven), maar het vraagt discipline.

## Open vragen, na herlezing constitutie

- Wat zegt Holacracy v5 over de exacte structuur van tactical en
  governance meetings? Welke onderdelen zijn verplicht?
- Hoe vertaalt "voorzitter" en "secretary" zich naar een
  agent-systeem? Worden dit aparte rollen (we hebben al Secretary en
  Facilitator) of LLM-functies?
- Hoe verhoudt het huidige sense-classify-route mechanisme zich tot
  het constitutionele "tension processing" proces?
- Wat doet het systeem met spanningen die binnenkomen TIJDENS
  governance-modus? Bufferen, weigeren, sensen maar niet routeren?

## Connectie met huidige stand

- Means_gap-approve via CLI (15 juni gebouwd) is een interim-oplossing.
  Blijft bestaan tot rituelen-bouw gereed.
- Lichtgewicht governance-CLI (op de plank van 15 juni) wordt
  overbodig: governance-modus is geen losse CLI maar een Village-staat.
  Mag van openstaand-lijst zodra rituelen-bouw begint.
- Inzicht "mens als rol" raakt mogelijk meer dan dit document: kan
  betekenen dat er een Stefan-rol-record bij komt, en dat huidig
  inbox-model wordt herzien.

## Volgende stap (Stefan)

Herlezing Holacracy v5 constitution met focus op:

- Artikel 3 (Governance Process)
- Artikel 4 (Operational Process / Tactical Meetings)
- Definities van Tension, Project, Accountability, Domain, Role

Bron: https://www.holacracy.org/constitution

Daarna: terugkomen met ontwerp dat constitutie als basis heeft, niet
gevoel.
