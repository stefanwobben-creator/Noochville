# Metrics NoochVille

Vastgelegd 15 juni 2026. Doel: definiëren wat we meten zodat we
op 24 augustus (evaluatie van de option-value afspraak) en
daarvoor en daarna structureel kunnen kijken hoe het dorp zich
ontwikkelt.

## Beginsel

We meten nu nog niet automatisch. We leggen alleen vast welke
metingen relevant zijn. Implementatie volgt later, wanneer rollen
zelf metrics gaan bijhouden of wanneer Stefan besluit dat
handmatige meting niet meer voldoet.

## Drie meet-categorieën

### 1. Systeemgezondheid (technische staat)

- Exceptions per run
- LLM-calls totaal plus succesvol
- Hangende of niet-afgesloten processen na run-stop

Doel: garanderen dat het systeem niet kapot gaat. Geen inhoudelijke
betekenis, wel fundamenteel.

### 2. Activiteit (operationeel ritme)

- Events per run, totaal en per type (sense_tension, means_gap_sensed,
  governance_changed, etc.)
- Aantal unieke rollen die events publiceerden per run
- Inbox-status: nieuwe items, opgeloste items, achterstand pending

Doel: zien of het dorp leeft en wat voor leven het heeft. Stijgende
of dalende lijn zegt iets, geen van beide is per se goed of slecht.

### 3. Kwaliteit (inhoudelijke betekenis)

- B-observer-verdicts: ratio coherent/vague/unparseable over tijd
- Inbox-items die langer dan een week pending staan
- Governance-voorstellen ingediend versus geadopteerd
- Ronnie's bulletins: subjectieve leesbaarheid en consistentie

Doel: zien of het dorp niet alleen activiteit produceert maar ook
betekenis. Vereist menselijke interpretatie, niet alleen tellen.

## Wanneer en hoe

Voor nu: Stefan kijkt ad-hoc naar deze data, vooral via Ronnie's
bulletins, console-output van runs, en system_log.jsonl.

Op 24 augustus (evaluatie option-value afspraak): Stefan gebruikt
deze categorieën als kompas bij de drie reflectievragen.

Later, wanneer rollen zelf metrics gaan bijhouden, automatiseert
het dorp delen van deze meting. Welke delen het eerst, beslissen
wanneer 't actueel wordt.

## Wat dit document NIET is

Geen meet-dashboard. Geen tracking-script. Geen automatische
rapportage. Het is een referentiekader voor wat we als interessant
beschouwen om te volgen.
