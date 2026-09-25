# Ontwerpdocument: projectkaart, koppost en composer opruimen (25 september, 3e ronde)

*Zelfde patroon als de vorige twee documenten: los van de lopende sprints, eerst een kort
technisch antwoord terug, pas na akkoord bouwen.*

## Aanleiding

Twee screenshots van de project-detail-modal ("Website Re-Design Done", `/project?pid=...`).

## Observaties, geverifieerd in de code

1. **De "PAKKET"-knop is een Nederlands woord in een verder Engelse interface.**
   `views/projects.py:1527-1529`: `<a class='btn sm' ...>⬇ pakket</a>`, met tooltip "All wall
   content + attachments as a zip, for manual AI analysis". De `.btn`-stijl zet de tekst in
   hoofdletters, dus op het scherm staat "PAKKET" — een los Nederlands woord tussen "Description",
   "Checklist" en "Conversation". Het label moet Engels worden en zeggen wat de tooltip al zegt
   (bijv. "Export" of "Download package").

2. **Diezelfde knop valt op een eigen regel, los onder de titel.** `.pcard-head` is een flex-rij
   met titel + knop naast elkaar; in de screenshot springt de knop naar een eigen regel, met de
   onderrand van `.pcard-head` er los onder — oogt als een weesknop in plaats van een bijbehorende
   actie naast de titel. Uit te zoeken of dit aan de breedte van het titelveld ligt of aan het
   knopgedrag bij een lange projectnaam; hoort zo of naast de titel te blijven staan, of een vaste
   eigen plek te krijgen die niet meewrapt.

3. **"remove" staat net zo prominent naast de checklist-titel als de titel zelf.** Een
   destructieve actie (verwijdert de hele checklist "Acties uit overleg", niet één item) krijgt
   dezelfde visuele nadruk als het label ernaast. Zelfde principe als Move/Edit op de wiki-pagina:
   een secundaire/destructieve actie die er even zwaar bijstaat als de hoofdzaak, is te makkelijk
   mis te klikken en trekt de aandacht verkeerd. Voorstel: minder prominent (ghost-achtig, geen
   los rood label naast de kop) en/of een bevestiging.

4. **De hint "Steer via the checklist." staat los tussen het tekstveld en de Post-knop.** Geen
   bug (bewust verplaatst vanuit een oud label, zie code-comment), maar visueel een eilandje op
   een eigen regel. Voorstel: als klein bijschrift direct onder het tekstveld i.p.v. een losse
   regel ertussen.

## Open vraag, niet-layout maar wel gezien

Het Noochie-bericht in de conversatie toont interne jargon aan een mens: "@Library, dit lijkt
binnen jouw scope (skill: keyword_review). Oppakken?" — vergelijkbaar met het ID dat ooit vóór de
wiki-titel stond: techniek op een plek die voor mensen bedoeld is. Dit is geen layout-kwestie maar
een contentkwestie (wat de AI-rol schrijft, niet hoe het blok eromheen staat). Apart traject of nu
meenemen: aan Stefan.

## Wat "klaar" hier betekent

- "pakket" wordt een Engels label dat zegt wat de knop doet.
- De knop staat aantoonbaar naast de titel, niet erop een eigen regel eronder (of krijgt een
  bewust andere, niet-wrappende plek als naast-de-titel niet haalbaar is).
- "remove" bij een checklist is visueel duidelijk secundair/destructief t.o.v. de checklist-naam.
- De composer-hint staat bij het veld waar hij bij hoort, niet los ertussen.
- Screenshot van het resultaat hoort bij het rapport (staat al in WORKING_AGREEMENTS.md).
