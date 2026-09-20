# De 33 kleur-alleen-statussen, per stuk (20 september 2026)

Basis: de telling uit `claude/fase12_hierarchie_audit.md` §7 — selectors in `nooch.css` die
`--green-tint`, `--yellow-light`, `--error-tint`, `--coral` of `--goal-tint` als *background*
zetten en géén tegenhanger hebben in `nooch-ui.css`. Opnieuw uitgedraaid op `origin/main`:
**33 selectors, waarvan 14 in de kennisbank** — precies de getallen uit de audit.

Per selector is daarna één vraag gesteld die de audit niet stelde: **wordt dit eigenlijk nog
gerenderd?** Dat antwoord bepaalt de groep.

## Groep 1 — live én alleen kleur (3) → tweede en derde drager toegevoegd

| selector | wat het is | was | nu |
|---|---|---|---|
| `.mdot.g/.n/.r` | missie-impact op de bordkaart | drie stippen, verschil alleen in kleur, betekenis in een `title` | gevulde cirkel / open ring / driehoek + `.sr`-woord, stip is `aria-hidden` |
| `.cl-attn` | checklist-rij: gemist | alleen een rode tint | + `border-left: 3px solid` + `.sr`-woord "Missed" |
| `.cl-todo` | checklist-rij: te doen | alleen een gele tint | + `border-left: 3px dashed` + `.sr`-woord "Due" |

Een `title` is geen vangnet: hij verschijnt niet op een telefoon en niet bij
toetsenbordnavigatie. Daarom twee dragers erbij en niet één — een vorm voor wie kijkt, een woord
voor wie luistert.

## Groep 2 — live, maar de tweede drager zat al in de markup (7) → niet aangeraakt

`.kc-n` (het stapnummer staat ín het bolletje) · `.noo-cta` (knop met het woord "Noochie") ·
`.noo-head` (kop met 🐸) · `.einddoc-banner` ("📄 Draft report — …") · `.ck-skill` (de chip
bevat de skill-naam) · `.ck-warn` ("⚠ payload incomplete") · `.ck-human` ("🙋 human task …").

Deze staan mét vindplaats in `TWEEDE_DRAGER_IN_DE_MARKUP` in de ratchet, zodat de uitzondering
navolgbaar is en niet op iemands geheugen rust.

## Groep 2b — live en al voorzien van een niet-kleur-drager in de CSS (8) → niet aangeraakt

`.pchip-leeg` (gestippelde rand) · `.kn-stmt.dragover` en `.kn-stage.dragover` (dashed outline) ·
`.kn-vgbaan`, `.kn-mece`, `.kn-sugg`, `.wz-now` (rand) · `.avatar` (vorm + initialen).
De ratchet laat ze automatisch door; ze hoeven niet in een uitzonderingenlijst.

## Groep 3 — dode CSS (15 van de 22 niet-gerenderde) → verwijderd

Geen enkel `class=`-attribuut in de codebase rendert deze klassen.

| selector(s) | waarom dood |
|---|---|
| 14× `kn-*` (`kn-word.stevig/groeit/omstreden`, `kn-caveat`, `kn-note.counter .kn-dot`, `kn-tagchip:hover`, `kn-strat`, `kn-inhand-sup/-cou`, …) | de kennisbank-**view** is verwijderd in fase 1-9 (#516, "de kennisbank-tak eruit"); de stylesheet bleef staan |
| `.imp-pill.g` / `.imp-pill.r` | de detailweergave werd een `<select>`; de klasse staat nog alleen in een comment |
| `.kb-msg.note .kb-text` | de renderer levert alleen `jij` en `noochie`, nooit `note` |
| `.fkind.upd`, `.wz-was`, `.rail-btn:hover` | geen renderer meer |

### De meetmethode, want dit moet navolgbaar zijn
Alle `class=`-attributen uit elke `.py` en `.js` verzameld, plus `classList.add/toggle/remove` en
de variabele-toekenningen waarmee dit project klassen opbouwt (`rowcls = " cl-attn"`). Twee
valkuilen zaten erin en beide zijn gecorrigeerd: een klassenaam die alleen in een **comment** staat
telt niet als gerenderd (daardoor leek `.imp-pill` eerst levend), en een klasse die **dynamisch**
wordt samengesteld telt wél (`.mdot {col}`, `.pchip-leeg`).

## Wat hiernaast nog dood ligt — een eigen opruiming, geen bijvangst

| familie | regels | nog gerenderd |
|---|---:|---|
| `kn-` | 188 | alleen `kn-searchbox` (hergebruikt in de claims-view) |
| `imp-pill` | 7 | geen |
| `wz-was` / `wz-now` | 4 | geen |
| `rail-btn` | 4 | geen |
| `fkind` | 3 | geen |
| `avatar` | 1 | geen |

Ruim 200 regels stylesheet voor schermen die niet meer bestaan. Bewust buiten deze ronde gelaten:
het valt buiten "fix de 33" en verdient zijn eigen commit en review.
