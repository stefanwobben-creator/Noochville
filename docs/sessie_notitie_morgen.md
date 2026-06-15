# Sessie-notitie voor morgen 16 juni

Vastgelegd op 15 juni 2026, einde van de dag, zodat morgen-Stefan
weet wat de afspraken zijn voordat hij begint.

## Volgorde van morgen

1. Lees eerst docs/visie_noochville.md en
   docs/option_value_noochville.md (samen 5 minuten). Geen
   herhaling, wel scherp jezelf in voor je begint.

2. Triage de openstaande spanningen van de inhabitants. Welke zijn
   binnen één dag oplosbaar, welke schuiven door naar de week na
   het familie-bezoek (16-21 juni).

3. Pytrends-onderzoek. Wat kan pytrends nu werkelijk doen, en wat
   doet tijdgeest_wachter ermee. Voor je gaat bouwen: weet eerst
   de bottleneck.

4. Op basis van triage en onderzoek: kies één concrete bouw-actie
   voor de dag. Niet meer.

## TrendScout-rol (besloten 15 juni avond)

- Aparte rol, niet skill-uitbreiding bij kennis_scout of
  tijdgeest_wachter.
- Karakter: ENTJ. Gericht, ongedurig, naar buiten kijkend.
- Mandaat: monitort publiek zoekgedrag (pytrends) om te sensen
  wat in de wereld leeft.

### Eerste skill (alleen deze, niet de andere ideeën)

"Rising queries vergelijken met kernwoorden":
- Haalt kernwoorden uit de bestaande librarian (skill
  library_lookup, onderzoek morgen hoe die werkt).
- Vergelijkt die kernwoorden tegen pytrends' rising queries.
- Vuurt een sense-event als een rising query 200-300% omhoog
  schiet ten opzichte van een kernwoord.

### Onderzoek-vraag voor morgen

- Hoe werkt library_lookup precies? Is het een query (geef
  kernwoorden in categorie X) of een lookup (bestaat kernwoord
  Y)? Antwoord bepaalt hoe TrendScout 'm gebruikt.

### Geparkeerd voor latere sessie (niet morgen)

- Geografische focus per stad (UK/Londen, Duitsland/Berlijn, etc).
- Suggesties-disambiguation via pytrends.suggestions().
- Proxies-strategie en exponential backoff tegen Google-blokkades.

## Andere openstaande beslissingen voor latere sessies

### Kennis_scout en tijdgeest_wachter mogelijk samenvoegen

Beide rollen werken met sedimentaire/contemplatieve bronnen
(boeken bij kennis_scout, ngram bij tijdgeest_wachter). Karakters
neigen naar ISTJ/INFJ-vergelijkbaar. Mandaten overlappen mogelijk.
Onderzoeken in latere sessie. Niet nu beslissen.

### Librarian-uitbreiding

Vanmiddag schreven we docs/ontwerp_kennislaag.md alsof librarian
een toekomstige rol was. Maar librarian bestaat al als seed met
purpose "Hoeder van de goedgekeurde woordenschat" en skill
library_lookup. Het ontwerp-document is dus eigenlijk een
uitbreiding van de bestaande librarian naar een volwaardige
kennislaag, niet een nieuwe rol. Te corrigeren in
docs/ontwerp_kennislaag.md bij volgende sessie.

## Tijdvenster morgen

Volle dag voor NoochVille, want vanaf morgenavond is er familie
(mama plus nichtje Elise) tot en met vrijdag, met slechts 1 uur
per dag voor NoochVille.

Belangrijk: niet alles morgen willen halen. Triage geeft
controle, bouwen-zonder-triage geeft kans op spijt.

## Wat ik geleerd heb vandaag

(Korte herinnering voor morgen-Stefan)

- Mijn werkritme is vier-takt: filosoferen, opruimen, iets
  bouwen, draaien. Alle vier nodig per sessie voor een
  afgesloten gevoel.

- Karakter aan een rol toevoegen (Ronnie ESFJ) brengt 'm
  werkelijk tot leven. Niet kosmetisch, wel functioneel.

- Externe koppelingen brengen het dorp echt tot leven. Niet
  langer in eigen lus, wel in dialoog met de buitenwereld.

- Spanning mag nooit doodlopen. Elke spanning krijgt een uitweg
  (governance, project, of escalatie).
