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

**Twee wegen, en dit is een keuze voor jou:**

- **A — de poort met pensioen.** `spanning_ontstaat`, `bevinding` en `zelf_verwerking` eruit in B2.
  Eerlijk: zijn beide afnemers zijn weg, en een module die draait zonder lezer is de duurste soort
  dode code — hij kost tokens en niemand merkt dat het antwoord nergens landt.
- **B — de poort een nieuwe lezer geven.** Bijvoorbeeld: het TYPEREN blijft, en een DM toont een
  klein label ("vraag aan jou" / "melding") zodat je in een lange kanalenlijst ziet wát er op je
  wacht. Herschrijven vervalt hoe dan ook. Dat is dan wél een nieuwe UI-vraag, en onder de nieuwe
  CLAUDE.md-regel begint die bij een atoom (het label), niet bij het scherm.

Ik bouw geen van beide tot je kiest. Weg is niet terug te halen; wiring zonder lezer is stil.

---

## Open vraag: wat blijft er over van de lade?

Zonder inbox is er geen plek meer die zegt "dit ligt bij jou". De DM-kanalen zijn een stroom, geen
wachtrij. Drie mogelijkheden, van klein naar groot:

1. De lade toont **ongelezen DM's** — één teller, geen nieuw begrip.
2. De lade verdwijnt; `/messages` is de enige plek.
3. `/messages` krijgt een **"aan jou gericht"**-filter (de DM-groep staat er al apart).

Mijn voorkeur is 1 of 3: die gebruiken wat er is. Optie 2 is het eerlijkst bij "de mens is
verantwoordelijk", maar dan is er geen enkel scherm meer met een getal erop, en dat is precies wat
mensen gebruiken om te weten of ze iets gemist hebben.
