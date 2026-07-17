# CC-opdracht: kennisbank UX-herontwerp

**Voor:** Claude Code, op de kennisbank/layout-branch. Dit is een UX-ronde op de live kennisbank ("Wat Nooch weet"), gebaseerd op tien schermen feedback van de founder. Verken eerst de huidige views, rapporteer je plan, bouw dan. Hergebruik het design system. Append-only en versiebeheer blijven overal intact.

## Leidende regel (hier draait alles om)
Bijna alle klachten zijn één probleem: de kennisbank zet de INHOUD en de MACHINERIE van de methode op hetzelfde visuele niveau (tags, zekerheidsstippen, comment-per-statement, meerdere toevoeg-paden, spel-mechaniek). Het oogt daardoor "rommelig/slordig". 

**De regel: inhoud op het bovenste niveau; machinerie treedt terug tot ze nodig is (achter disclosure, of pas bij selectie/hover).** Fix per LAAG, niet per los knopje. De meeste punten hieronder vallen onder deze ene regel.

---

## Deel A — Opruiming (vier systemische ingrepen)

### A1. Verberg wat secundair is (progressive disclosure)
- **Bibliotheek-tags** (bron-filter-chips) standaard verbergen achter een "toon tags"-uitklap; de balk blijft laag.
- **Comment-per-statement** (het tekstballonnetje op elke bewijs-kaart) weg. Er is één gesprek onderaan het inzicht (zie C3), niet per statement.
- Onderaan het inzichtdetail: **"Voeg bewijs of een reactie toe" weg.** Bewijs koppel je rechts uit de bibliotheek; een reactie plaats je in het gesprek onderaan. Geen derde pad.
- De **hunch-invoer** ("Ik heb een hunch") minder prominent: het is een neveningang, geen hoofdactie. Maak het een vrij-typen-veld dat duidelijk uitnodigt (placeholder + micro-hint), maar visueel ondergeschikt aan de clusters.

### A2. Maak de systeemstatus leesbaar (Nielsen #1)
- **Checkbox aanvinken toont nu geen status.** Bij selectie moet zichtbaar worden wat je ermee kunt (een contextuele actiebalk: samenvoegen / archiveren / koppelen), en dat er iets geselecteerd is. Geen dode checkbox.
- **Groene stippen:** geef ze een expliciete betekenis of haal ze weg. Op inzicht-niveau zijn de vier stippen de zekerheidsmeter naast het woord ("stevig"); laat het WOORD de status dragen (recognition), de stippen zijn secundair, met een tooltip die de meter uitlegt. Op atoom-niveau in de bewijslijst: bepaal wat de stip codeert (status? bevestigd?); label het of laat het weg. Een signaal dat niemand kan lezen is ruis.
- **Inzicht-titel:** een inzicht moet zijn CLAIM als titel dragen, niet een clusternaam ("segment: schoenen · barefoot · worden"). Nu zegt de titel niks over wat het inzicht is.

### A3. Maak interactie direct
- **Bibliotheek-zoek: live filteren terwijl je typt** (debounce), resultaten filteren direct, over de verse volledige bibliotheek. Geen aparte zoekknop-stap.
- **Atomic kaart inline bewerken door op de tekst te klikken** (er is versiebeheer, dus veilig). Opslaan maakt een nieuwe versie; de vorige blijft bewaard (append-only). 
- **Bewaar-knop ONDER het veld** (niet ernaast), met de normale primaire knop-kleur uit het design system.
- **Tekstveld groter** bij bewerken.
- Bij een atoom een **URL of PDF kunnen meegeven als bronlink** (landt in het reference-veld van het atoom; PDF via de bestaande adapter). 

### A4. Ruim dubbele paden op
- Een atoom dat AL aan het geopende inzicht gekoppeld is, verschijnt **niet** nog eens als koppelbare kandidaat in de bewijslijst/rechterkolom (dedup tegen de reeds-gekoppelde set).
- **"+ feit" weg** van de atoom-kaart. Een nieuw gerelateerd feit is gewoon een nieuw atoom via de normale intake (optioneel gelinkt); niet een apart inline-pad.
- **Een punt (bewijs) verwijderen moet kunnen** vanuit het inzicht (ontkoppelen), niet alleen toevoegen.

### A5. Twee schermen die "slordig" ogen, netjes maken
- **Bron toevoegen ("Wat Nooch weet"):** de plak-invoer, de bestandskiezer en "Verwerk de bron" staan rommelig door elkaar. Eén rustige verticale indeling: plak-veld, dan bestand, dan één primaire knop, met de "we herkennen het type zelf"-hint eronder. Uitlijnen, ademruimte, design-system-spacing.
- **Speel een inzicht:** zelfde rust. De cluster-suggestie krijgt een leesbare titel (wat wordt hier het inzicht?), de hunch is ondergeschikt, en de open-spel-regel netjes eronder.

---

## Deel B — Twee diepe items (raken het datamodel: eerst diagnose + voorstel, dan bouwen)

### B1. Gerelateerde inzichten + recursie
"Onze inzichten" wordt **"Gerelateerde inzichten"**: inzichten die je ONDERLING kunt koppelen (dezelfde steunt/tegen-koppeling als atomen, maar wijzend naar andere inzichten), waarna je een abstracter spel speelt op de gekoppelde set → een meta-inzicht. Dit is de Zettelkasten-ladder: atoom → inzicht → meta-inzicht.
- **Diagnose eerst:** kan een link in de notes/insight-store van inzicht naar inzicht wijzen? Wat betekent de zekerheid van een meta-inzicht (afgeleid uit de onderliggende inzichten)? Rapporteer hoe je dit modelleert vóór je bouwt.
- **Bouw:** een inzicht krijgt de koppel-affordance naar andere inzichten, plus een "speel een meta-inzicht" die gekoppelde inzichten als input aan het spel geeft (zelfde copy-paste-prompt-flow als nu).

### B2. De flip ("de andere kant")
"De andere kant" en "Wat zou dit onderuit halen?" worden geen losse tekstblokken maar de **ACHTERKANT van het kaartje**. Bovenin een knop die het hele kaartje omdraait: claim én bewijs-statements flippen mee, zodat je hetzelfde materiaal van de tegenkant leest. Een denkoefening, geen extra sectie eronder.
- **Diagnose eerst:** waar komt de "andere kant"-tekst en de "wat haalt dit onderuit" vandaan (bestaande velden?), zodat de flip die hergebruikt i.p.v. iets nieuws te genereren. Rapporteer, bouw dan.

---

## Deel C — Het gesprek
- **C3. Gesprek onderaan het inzicht:** het kale invoerveld nodigt niet uit. Toon bestaande kanttekeningen als een echt gesprek (afzender, tijd, draad), met het invoerveld als natuurlijke afsluiting. Dit is het gesprek OVER het inzicht als geheel (de plek waar de comment-per-statement uit A1 naartoe verdwijnt). Sluit qua model aan op het curatie-/Kroniek-gesprek dat we eerder bespraken (append-only).

---

## Guardrails
- Append-only overal; bewerken bewaart de vorige versie (geen stille overschrijving); verrijken maakt een nieuw gelinkt atoom.
- Design system hergebruiken; geen nieuwe losse componenten waar een bestaande past.
- Geen handmatige weging; de zwaarte/zekerheid blijft afgeleid uit onafhankelijke bronnen.
- Suggesties tonen altijd ook tegenbewijs (anti-cherry-pick), ongewijzigd.
- Branch, aparte PR, volle testsuite groen. Applies op prod als user `nooch` (niet root), na backup, met dry-run.
- Deel A mag in één landing; Deel B (B1, B2) pas bouwen na je diagnose-rapport, want die raken het datamodel.
