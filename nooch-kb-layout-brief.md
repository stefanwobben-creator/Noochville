# Build-brief: Kennisbank layout-herinrichting (drie zones)

**Voor:** Claude Code in de Noochville repo. Kennisbank live op prod. **Vervangt** de losse search-curatie-brief; die gaat hierin op.
**Leidend:** de master-brief (model + principes) en de layout-mock die de gebruiker heeft goedgekeurd.
**Werkwijze:** branch `kennisbank-layout`. Verken eerst de huidige /kennisbank-view, de intake en het koppel-paneel; rapporteer je plan; bouw dan. Hergebruik de bestaande design-system-componenten, de atomiser en de ladder. Append-only overal.

## De layout: drie zones

### 1. Compacte actiebalk bovenaan (sticky)
Twee knoppen die op klik open klappen (accordion); de balk zelf blijft laag.
- "Bron toevoegen"
- "Speel een inzicht"

### 2. Bron toevoegen (klapt open)
- EEN invoer die zowel plakken als bestand-drop accepteert. **Auto-detectie** van het type, de gebruiker hoeft niks te kiezen: begint met http(s) -> URL/website; een Google Sheets/Slides-URL -> die adapter; een bestand -> PDF/Excel op mime/extensie; anders -> platte tekst. Geen handmatige bron-type-kiezer (hooguit als stille override).
- Bron-adapters produceren (ruwe tekst OF data, bron-label) -> de bestaande atomiser. **Belangrijk:** tabellaire bronnen (Google Sheet, Excel) zijn vaak DATA, geen proza. Forceer die niet blind door de proza-atomiser: rijen/kolommen worden gestructureerde feiten of metrics (append-only reeks) waar dat past. Een survey-sheet wordt bevindingen en cijfers, geen verhaaltjes.
- **Staging-ronde (de kern):** na verwerken toont het een "even nakijken"-lijst van de voorgestelde atomen, BEWERKBAAR, met samenvoegen en verwijderen, VOORDAT ze de bibliotheek in gaan. Pas op "Voeg set toe aan bibliotheek" worden ze opgeslagen. Dit is de plek om rommel op te ruimen (zoals de CLARISSA-stappen) voordat het de bibliotheek vervuilt.
- Noot: deze staging geldt voor handmatige/interactieve intake. Bulk- en auto-ingest (signalen-backfill, de auto-hook) hebben geen mens om na te kijken en gaan direct de bibliotheek in (permissief); daar ruim je in de bibliotheek op.

### 3. Speel een inzicht (klapt open)
- Een hunch-invoer OF kies uit bestaande suggesties (de clusters), EEN tegelijk in beeld met vorige/volgende, zodat de balk laag blijft. "Speel deze" genereert de prompt voor je eigen AI (de copy-paste-flow, zoals nu).

### 4. Werkgebied in twee kolommen
- LINKS - Inzichten (laag 2, het denken): blader door je inzichten, klik er een open -> detail (claim, zekerheid, bewijs plus tegenspraak). Vanuit het detail bouw je bewijs door kaarten uit de bibliotheek rechts te trekken.
- RECHTS - Bibliotheek (laag 1, het materiaal): een live smart search plus filter bovenaan, daaronder de volledige atomenlijst.

## Smart search plus filter (rechts)
- Live terwijl je typt (debounce), VERVANGT de resultaten, over de verse volledige bibliotheek (inclusief net toegevoegde atomen). Geen stale resultaten eronder.
- Zoekt op inhoud EN op BRON. Typ een bronnaam ("Fixed Delivery Moments") en je ziet alle kaarten van die bron. Maak het bron-label van een kaart klikbaar -> filtert op die bron.
- De onderwerp/relevantie-filters staan in dezelfde strook.

## Bewijs koppelen (het brug-mechanisme tussen de kolommen)
- Met een open inzicht links markeert de bibliotheek rechts SUGGESTIES: kandidaten die steunen EN kandidaten die tegenspreken (aparte markering, anti-cherry-pick).
- Koppel met "+ steunt" / "+ tegen" (of sleep in de betreffende bak). Dit is richting (stance), GEEN belangrijkheids-rangschikking; de zwaarte blijft berekend uit onafhankelijke bronnen.
- Annotatie optioneel per koppeling.

## Curatie in de bibliotheek
- Per kaart: bewerken (met historie, append-only, geen stille overschrijving; voor extractie-fouten), en "voeg gerelateerd feit toe" (maakt een NIEUW gelinkt atoom met eigen bron -> het 36%-geval), plus aanvinken voor samenvoegen en archiveren.

## Acceptatie
- Plak een URL -> herkend als website, geen chip nodig; upload een PDF -> herkend; plak een Google Sheet-link -> als data behandeld.
- Na verwerken kun je in de staging een kaart bewerken, twee samenvoegen, een weggooien, en dan de set committen; niets staat in de bibliotheek voor je commit.
- Rechts: typ "fixed delivery" -> alle kaarten van die survey; klik een bron-label -> zelfde filter.
- Open een inzicht links, koppel een steun- en een tegenkaart uit rechts; de zekerheid herberekent.

## Guardrails
- Append-only overal; bewerken bewaart historie, verrijken maakt een nieuw gelinkt atoom.
- Auto-detectie mag, maar toon kort wat het herkende (verklaarbaar).
- Tabellaire bronnen niet blind door de proza-atomiser.
- Suggesties tonen altijd ook tegenbewijs.
- Geen handmatige weging; zwaarte blijft afgeleid.
- Design system hergebruiken; branch, tests, aparte PR; applies als user nooch, back-up, dry-run.
