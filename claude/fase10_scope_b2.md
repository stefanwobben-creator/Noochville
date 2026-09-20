# Scope B2 — alles wordt DM, er komt geen besluitwachtrij

**Datum:** 20 september 2026 · **Status:** scope, niets gebouwd
**Vervangt** `claude/fase10_scope_besluitwachtrij.md` (dezelfde dag, ingetrokken).

Stefan, na het lezen van die eerste scope: **geen eigen store, geen besluitwachtrij.** De twee
overgebleven schrijfplekken worden ook gewoon DM, identiek aan de andere 371.

- **Werkoverleg-actie** — `roloverleg.py` houdt toewijzing en afronding al zélf bij, los van
  `NotifStore`. De DM is puur de melding erbovenop; er valt niets nieuws vast te leggen.
- **Pagina-voorstel** — menselijk gemaakt, geen automatische consequentie. De DM is een
  *suggestie*; wie de rol vervult past de pagina zelf aan als hij het ermee eens is, net als bij
  elke andere wiki-bewerking. Een genegeerd voorstel betekent: de pagina blijft zoals hij was. Daar
  is geen status voor nodig.

Dat maakt de eerdere scope in één klap overbodig, en dat is winst: geen derde opslagvorm naast
`ProjectLedger` en `ChannelStore`, geen tweede levenscyclus om te onderhouden, en `verzoek_besluit`
kan weg in plaats van verhuizen.

---

## Wat B2 daarmee wordt

1. De twee resterende `st.notif.add`-plekken naar `_signaleer`.
2. `_act_verzoek_besluit` en de bijbehorende knoppen eruit — er valt niets meer te beslissen.
3. `NotifStore`, `/inbox`, `/inbox/verwerk`, `render_inbox`, `render_verwerk`, `render_inbox_frag`
   en de lade-chrome eruit.
4. De lade in de zijbalk wordt een DM-teller, of verdwijnt — zie de open vraag onderaan.

Omvang zoals eerder gemeten: 13 `NotifStore`-methodes, 46 aanroepen, 18 bronbestanden,
37 testbestanden.

---

## ⚠ `spanning_ontstaat` heeft nu geen LEZER meer, niet alleen geen aanroeper

De opdracht zegt: de poort haakt in op *"de ene gedeelde plek waar elke DM ontstaat"*. Dat kan
technisch — `signaal.stuur` is die plek — maar ik moet eerst melden wat ik bij het nalezen vond,
want het verandert de vraag.

De poort doet **twee dingen**, en die zijn uitdrukkelijk niet hetzelfde (staat zo in zijn eigen
docstring, na een omgevallen test):

| handeling | wat het oplevert | wie las dat |
|---|---|---|
| **typeren** (`zelf_verwerking`) | een classificatie naast de tekst: vraag aan een rol, besluit, melding | de inbox-routering en -filtering |
| **herschrijven** (`bevinding`) | een zin die de lezer krijgt **in plaats van** de rauwe tekst | `views/inbox.py::_regel` |

Beide lezers verdwijnen in B2. Een DM toont de tekst zoals hij getypt is; er is geen
`bevinding`-weergave en geen filter op `type`. Hang ik de poort aan `signaal.stuur`, dan draait er
per bericht een LLM-call waarvan **niemand de uitkomst leest**.

Daar komt bij: de helft die woorden vervangt mág sowieso niet op mens-tekst draaien — dat is de
`MENS_GETYPT`-regel, en in een DM-laag is vrijwel alles mens-tekst.

**BESLIST (Stefan, 20 september): weg A — de poort gaat met pensioen.** `spanning_ontstaat`,
`bevinding` en `zelf_verwerking` gaan er in B2 uit. Geen nieuwe lezer: beide helften hebben hun
enige afnemer verloren en horen niet terug te komen voor de sier. Herschrijven mag sowieso niet op
mens-tekst draaien, en in een DM-laag is dat vrijwel alles.

Dat maakt B2 een stuk groter dan alleen `NotifStore`: er gaan drie modules uit in plaats van één.
De verwijdering hoort daarom pas ná de rest van B2, zodat een fout in de omzetting niet met een
dode-code-opruiming in dezelfde commit zit.

---

## Wat er van de lade overblijft — BESLIST

Geen apart label en geen nieuw begrip. De "waar ligt iets bij mij"-behoefte wordt gedekt door de
**kanaal-ongelezen-indicator die al in fase 11 (punt 3a/3b) is gescoped**, en dat is de eerste
bouwstap daar. B2 hoeft er dus niets voor te verzinnen.

Praktisch gevolg voor de volgorde: B2 haalt `/inbox` weg, en de indicator uit fase 11 neemt de
functie over. Zitten die te ver uit elkaar, dan is er even geen enkel scherm met een getal erop —
het enige dat mensen gebruiken om te weten of ze iets gemist hebben. Dat is geen blokkade, wel iets
om bij de planning van B2 en fase 11 naast elkaar te leggen.
