# Ontwerpdocument: echte afbeeldingen, bestanden en slepen in het blokkensysteem (26 september)

*Vervolg op #602/#603/#604. Bevestigd met Stefan aan de hand van een werkend HTML-prototype
(`wiki-blokkensysteem-prototype.html`) en geverifieerd tegen de bestaande code vóór dit werd
opgeschreven — geen nieuw opslagformaat nodig, de drie stukken hieronder passen in wat er al staat.*

## Aanleiding

Stefan wil dat een wiki-pagina echt kan mixen: tekst, een feit, een afbeelding, meer tekst, meer
feiten, een link, in elke volgorde, versleepbaar. Het prototype liet dat zien met neptekst. Bij het
uitzoeken bleek de aanname "dat vraagt een nieuwe blok-datastructuur" niet te kloppen — de drie
losse gaten hieronder zijn elk klein en passen in de bestaande markdown+`contenteditable`-aanpak.

## 1. Een upload wordt een zichtbare afbeelding, geen kale link

**Nu**: `_link()` in `cockpit2_util.py` zet `![naam](url)` om in `<a data-beeld href=...>naam</a>` —
een klikbare tekstlink, `data-beeld` bestaat alleen om bij het opslaan het uitroepteken terug te
zetten (`_md_naar_bron`, regel ~801). Er wordt nergens een `<img>` getekend.

**Wordt**: als `data-beeld` staat én de url op een bekende afbeeldingsextensie eindigt
(`.png .jpg .jpeg .gif .webp .svg`), rendert `_link()` een `<img src='{url}' alt='{label}'>` in
plaats van de `<a>`. Geen `data-beeld`, of geen afbeeldingsextensie: huidige gedrag (link) blijft
staan — dat dekt PDF's en andere bijlagen die al via dezelfde `![...]`-syntax lopen.

`_md_naar_bron` moet de nieuwe kant op ook lezen: een `<img>`-tag terugvertalen naar `![alt](src)`
(nu leest hij alleen `<a>`/`<span>`). Zelfde plek, `elif tag == "img":` naast de bestaande
`elif tag in ("a", "span"):`.

**Vormgeving**: geen `.card`, zelfde principe als `.wiki-inline`. Voorstel uit het prototype:
`.wb-img img{border:2px solid var(--nu-text)}` onder `.nu`, geen rand in de niet-`.nu`-stand
(zelfde soort onderscheid als de rest van dit systeem), bijschrift eronder in `.muted`, klein.

## 2. Uploaden via het blokmenu, op de plek van de `+`, niet altijd onderaan

**Nu**: `_bijlage_form` (`views/wiki.py:374`) is een los `<details>`-formulier dat altijd aan het
eind van `_wiki_editor` staat (`{bijlage}` in de `main =`-assemblage). De `wiki_bijlage`-actie plakt
de upload-regel achter de bestaande body-tekst. Er is bewust geen aparte bijlagelijst — "de body is
de enige bron van waarheid" (code-comment) — dat principe blijft overeind, alleen de plek waar de
regel landt wordt de `+`-positie in plaats van altijd het einde.

**Wordt**: twee nieuwe entries in `BLOK_MENU` (`cockpit2_util.py:1170`): **Afbeelding** en
**Bestand**. Klikken opent een bestandskiezer (`<input type=file>`, hetzelfde `accept` uit
`channels.BIJLAGE_TYPES`, geen tweede allowlist). Na kiezen: dezelfde upload-aanroep als vandaag
(`wiki_bijlage`), maar de server geeft de markdown-regel (`![naam](url)` of `[naam](url)`) terug in
plaats van 'm zelf aan de body te plakken; de client zet die regel neer op de `+`-positie, exact
zoals de andere blokmenu-items dat al doen voor tekst/kop/lijst.

Áls de server het bestand liever direct blijft opslaan in `a.body` (minder client-state, en de
huidige actie doet dat al): dan krijgt `wiki_bijlage` een optioneel `positie`-veld (bloknummer of
"na blok X") in plaats van altijd-append, en de client stuurt dat mee vanuit de `+`-context. Kies
wat het minste aan de bestaande `wiki_bijlage`-actie verandert; dit is een detail voor de bouw, geen
ontwerpbeslissing.

Het oude `_bijlage_form` onderaan de pagina kan weg zodra het blokmenu dit dekt — twee wegen naar
dezelfde handeling is precies het "twee schermen die uit elkaar lopen"-risico dat de code-comment
bij `_bijlage_form` zelf al benoemt.

## 3. Echt slepen — hergebruik `NV.sleep`, niet opnieuw bouwen

**Bevestigd met Stefan**: sleep is een TOEVOEGING naast het bestaande grip-menu (↑ omhoog / ↓ omlaag
/ ✕ verwijderen in `nooch.js`), niet een vervanging. Dat menu blijft de manier voor toetsenbord en
touch — dezelfde toegankelijkheidsregel die al in de code staat ("op touch sleept dit dorp niet, en
met een toetsenbord al helemaal niet") blijft gelden. Sleep is muis/pen, een versnelling.

**Grote meevaller bij het uitzoeken**: dit hoeft niet opnieuw gebouwd. `NV.sleep` (`nooch.js`,
rond regel 264) is al het gedeelde sleep-mechanisme achter het projectenbord, en de code-comment
erboven zegt het letterlijk: *"De wiki-blokken willen exact hetzelfde gedrag met andere selectors,
en een tweede implementatie zou betekenen dat de ene na een wijziging anders sleept dan de andere."*
`opties.helft` bestaat al specifiek voor "een blok valt vóór of ná een ander blok" — dat is precies
het wiki-geval, nu alleen nog niet aangeroepen.

**Wat er dus wél moet gebeuren**: `NV.sleep` aanroepen voor de wiki-body met:
- `kaart`: `.wb[data-blok-id]` (elk blok heeft dan een stabiel `data-blok-id` nodig — nu bestaat
  alleen `data-blok` voor het TYPE, niet een identiteit per instantie; dat is de enige nieuwe state)
- `greep`: `.wb-greep-knop` (zelfde grip als vandaag, niet de hele blok-breedte — anders vecht
  slepen met tekst selecteren, exact de reden dat `opties.greep` bestaat)
- `doel`: `.wb[data-blok-id]` met `opties.helft: true`
- `onDrop(id, naarId, kant)`: de twee blokken in de live DOM verwisselen (`before`/`after`), en
  daarna hetzelfde opslaan-pad als een gewone tekstbewerking (de hele body gaat als `innerHTML` mee
  bij het opslaan — geen aparte "volgorde opslaan"-aanroep nodig, het is dezelfde weg terug via
  `_md_naar_bron` die al bestaat)

Vormgeving: hergebruik `.pdrag-ghost`/`.pdrag-bron` (of een eigen klasse met identieke eigenschappen
als die twee te bordspecifiek blijken) zodat het optillen er hetzelfde uitvoelt als op het bord.

## 4. Pagina archiveren/verwijderen (los onderwerp, klein)

**Aanleiding**: Stefan wil de wiki flink kunnen opschonen — "bijna alles wat er nu in staat kan
weg". Bestaat al voor projecten (`views/projects.py`, acties `proj_archive`/`proj_delete`, met
`confirm('Delete permanently? Archiving keeps the project.')` op de destructieve knop). De wiki
heeft nog geen van beide.

**Wordt**: dezelfde twee acties voor wiki-pagina's (`wiki_archive`/`wiki_delete`), zelfde
bevestigingstekst-patroon, in het `.wiki-meta`-blok onderaan (staat al in het prototype: twee ghost-
knoppen naast de metadata-rijen). Archiveren zet `status="archived"` (dat veld en die waarde
bestaan al, zie `wiki.py:262`); verwijderen is permanent, zelfde soort backup-voor-de-zekerheid als
bij projecten als die er is.

## Wat "klaar" hier betekent

- Een geüploade afbeelding is een zichtbare afbeelding in de pagina, geen kale bestandsnaam-link.
- Afbeelding en Bestand staan in het blokmenu en landen op de `+`-positie, niet altijd onderaan.
- Een blok is met de muis te verslepen naar elke andere plek in de pagina; het bestaande
  ↑/↓/✕-menu blijft ernaast bestaan voor toetsenbord en touch.
- Slepen hergebruikt `NV.sleep`, er komt geen tweede sleepmechanisme.
- Een wiki-pagina heeft Archive en Delete, met dezelfde bevestiging als projecten.
- Screenshot/kort verslag zoals gebruikelijk (WORKING_AGREEMENTS.md), en een genuine gemengde
  testpagina (tekst → feit → afbeelding → tekst → tekst → 3 feiten → link) om op te verifiëren —
  precies de volgorde uit het prototype.
