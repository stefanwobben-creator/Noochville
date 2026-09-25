# Ontwerpdocument: metadata naar onderaan + Feiten/Backlinks in het blokmenu (25 september, 4e ronde)

*Geen stijlronde — een informatiearchitectuur-fix. Zelfde patroon: kort technisch antwoord terug,
pas na akkoord bouwen.*

## Aanleiding

Stefans kernpunt was niet de vormgeving maar de prioriteit en plaatsbaarheid van informatie:
metadata (Owner/Domain/ID/Last edited/History) krijgt nu vaste, prominente ruimte direct onder de
titel, terwijl Feiten en Links-here als losse, vaste secties onderaan staan in plaats van blokken
die je tussen de content kunt plaatsen. "De inhoud is leidend, nu is type informatie leidend."

## Wat er al bestaat (geverifieerd in de code, niet aangenomen)

- `{{facts}}` en `{{backlinks}}` bestaan al als markering (#595, `nooch_village/wiki.py:127-138`).
  Zet een schrijver zo'n markering op een eigen regel in de body, dan landt de sectie daar. Zonder
  markering staat alles onderaan, zoals nu op alle 122 pagina's.
- Het "+"-blokmenu (#600, `BLOK_MENU` in `cockpit2_util.py:1170-1188`) — gebouwd specifiek om een
  blok toe te voegen zonder markdown te kennen — heeft tien opties (Tekst, Kop 1/2/3, Lijst,
  Genummerde lijst, Citaat, Scheiding, Tabel, Codeblok). Feiten en Backlinks staan er niet bij.
  Daardoor bestaat de plaatsbaarheid alleen voor wie toevallig de `{{...}}`-syntax kent — voor
  iedereen die het blokmenu gebruikt (waar het menu juist voor gebouwd is) bestaat de functie niet.
- Afbeelding-als-blok kan nu alleen door zelf `![alt](url)` te typen. Dat is exact PR 3/4, al
  afgesproken, Claude Code is daar net aan begonnen. Geen wijziging hier nodig.

## Wat "klaar" hier betekent

1. **`BLOK_MENU` krijgt twee entries: "Feiten" en "Backlinks".** Zelfde interactiepatroon als de
   bestaande tien: kiesbaar via de plus-knop en het /-menu, en net zo sleepbaar/verplaatsbaar als
   elk ander blok. Ze voegen respectievelijk `{{facts}}` en `{{backlinks}}` in — geen nieuwe opslag,
   alleen de bestaande markering bereikbaar maken.
2. **Metadata verhuist naar onderaan de pagina.** Na de content, na Feiten en Links-here — niet
   meer direct onder de titel. Boven blijft alleen: titel + de hoofdactie (Edit page). De lezer
   ziet eerst de inhoud, niet de administratie erover.
3. **Check de bestaande soorten-telling op hardcoding.** De #595-commit repareerde al een
   hardgecodeerde `=== 7`-telling in `claude/blok_browsercheck.js` die de sprint al drie keer had
   ingehaald. Met twee nieuwe entries moet die telling meegroeien in plaats van opnieuw vast te
   lopen op een vast getal.

## Open voor Claude Code

- Of de bestaande sleep-logica de twee nieuwe bloktypes zonder aanpassing accepteert, of dat er
  iets bloktype-specifieks bestaat dat Feiten/Backlinks apart behandelt.
- Volgorde: eerst het blokmenu (klein, precies, laag risico), dan de metadata-verplaatsing (raakt
  `render_pagina`/`_meta_blok`, net vorige ronde gebouwd — dus voorzichtig met dubbel renderen).
- Screenshot van het resultaat hoort bij het rapport, zoals altijd.
