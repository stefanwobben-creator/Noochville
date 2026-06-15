# Ontwerp: Governance Ritueel voor NoochVille

Status: concept, niet geïmplementeerd. Vastgelegd 15 juni 2026 als
startpunt voor latere bouw. Volledig ontwerp wacht op Stefan's
herlezing van de Holacracy v5 constitution.

## Uitgangspunt

NoochVille volgt het Holacracy v5 model voor de scheiding van
governance en operationeel werk. De constitutie is de bron, dit
document is de vertaling naar een agent-systeem.

## Wat we al weten (Stefan's intuïtie, 15 juni)

- Governance is een aparte ruimte, niet parallel aan operatie.
  Tijdens governance pauzeert de operatie.
- Een rol met accountability + skill kan operationeel aan de slag.
- Loopt een rol vast (spanning, blokkade, ontbrekend middel), dan
  verzamelt Secretary deze spanningen en classificeert:
    - Tactisch (werkoverleg-werk): prioriteiten aanpassen, doorlopende
      werkzaamheden bijsturen.
    - Governance (roloverleg-werk): concreet voorstel formuleren voor
      volgend governance-overleg.
- Ritme:
    - Tactisch ritme: dagelijks werkoverleg aan begin van de dag.
    - Governance ritme: één keer per week, operatie pauzeert.

## Open vragen, te beantwoorden na herlezing constitutie

- Wat zegt Holacracy v5 over de exacte structuur van tactical en
  governance meetings? Welke onderdelen zijn verplicht?
- Hoe vertaalt "voorzitter" en "secretary" zich naar een agent-systeem?
  Worden dit aparte rollen (we hebben al Secretary en Facilitator),
  of LLM-functies?
- Wat is de minimale en maximale duur van governance-modus? Per
  voorstel, of vast window?
- Hoe verhoudt het huidige sense-classify-route mechanisme zich tot
  het constitutionele "tension processing" proces?
- Wat doet het systeem met spanningen die binnenkomen TIJDENS
  governance-modus (bufferen, weigeren, sense maar niet routeren)?

## Connectie met huidige stand

- Means_gap-approve via CLI (15 juni gebouwd) is een interim-oplossing.
  In het ritueel-model wordt dit governance-modus-actie. CLI-handler
  blijft bestaan tot rituelen-bouw gereed is.
- Lichtgewicht governance-CLI (op de plank van 15 juni) wordt
  overbodig: governance-modus is geen losse CLI maar een Village-staat.
  Mag van openstaand-lijst af zodra ritueel-ontwerp wordt gebouwd.

## Volgende stap (Stefan)

Herlezen van Holacracy v5 constitution, met focus op:
- Artikel 3 (Governance Process)
- Artikel 4 (Operational Process / Tactical Meetings)
- Definities van Tension, Project, Accountability, Domain

Bron: https://www.holacracy.org/constitution

Daarna terugkomen met ontwerp dat constitutie als basis heeft, niet
gevoel.
