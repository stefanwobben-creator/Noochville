# Scope — de besluitwachtrij als eigen store

**Datum:** 20 september 2026 · **Status:** scope, niets gebouwd
**Aanleiding:** stap B1 legde bloot dat `NotifStore` twee dingen tegelijk was. Acht van de tien
schrijfpaden waren **signaleringen** (die zijn nu DM). Twee waren **verzoeken met een beslissing**,
en die kunnen niet naar een DM: een bericht kan "hier moet nog over beslist worden" niet dragen.

Stefan, 20 september: de besluitwachtrij krijgt een eigen kleine store, los van `NotifStore` en los
van de DM-laag. Alleen die twee objecttypen, met een guard-test die het bevriest.

---

## 1. De twee objecttypen, en niets anders

### `pagina_voorstel` — iemand stelt een nieuwe tekst voor een wiki-pagina voor

| veld | herkomst | waarom het nodig is |
|---|---|---|
| `id` | gegenereerd | het handvat waarop `verzoek_besluit` terugleest |
| `soort` | `"pagina_voorstel"` | het objecttype; de guard bevriest de verzameling |
| `aan_rol` | `wiki.ontvanger()` | wie beslist — de eigenaar-rol, of de Circle Lead als die rol geen mens heeft |
| `van_id` / `van_naam` | de indiener | het antwoord moet terug naar een persoon, niet naar een rol |
| `aid` | de pagina | welk artefact het betreft |
| `titel` | de pagina | leesbaar zonder de pagina erbij te halen |
| `was` | de pagina | de oude tekst, voor de diff bij het beslissen |
| `body` | het formulier | de voorgestelde tekst |
| `waarom` | het formulier | de reden; zonder dat kan de beslisser niets afwegen |
| `at` | klok | |
| `status` | zie §2 | |
| `besluit` | bij afronding | `{keuze, tekst, door, at}` |

### `actie` — een werkoverleg wijst werk toe

| veld | herkomst | waarom het nodig is |
|---|---|---|
| `id`, `soort` (`"actie"`), `at`, `status`, `besluit` | idem | |
| `aan_type` / `aan_id` | de toewijzing | een actie kan bij een ROL of bij een PERSOON liggen |
| `van_id` | de toewijzer | |
| `tekst` | het overleg | wát er gedaan moet worden |
| `opdrachtgever` | het overleg | krijgt bericht zodra het af is — dat is de afrondlus |
| `bron_project` | het overleg | de herkomst, en het enige veld dat ook op de DM meegaat |
| `rol` | het overleg | vanuit welke rol de actie is belegd |

**Wat er bewust NIET in gaat**, en dat is het halve punt van een eigen store: `read`, `processed`,
`archived`, `done`, `deleted`, `outcome`, `verwerkingen`, `poort`, `prive`, `herkomst`, `afronding`,
`suggestie`, `MENS_GETYPT`, `type`, `bevinding`, `entry_id`, `project_id`. Dat waren de velden van
de wachtrij-als-alles-bak. Wie er later één bij wil, botst op de guard.

## 2. States: drie, niet zeven

```
open  →  afgerond   (besluit genomen: geaccepteerd / geweigerd / aangepast / actie klaar)
      →  ingetrokken (de indiener trekt zijn eigen verzoek terug)
```

`NotifStore` had `read` · `processed` · `archived` · `done` · `deleted` plus een afgeleide
`status_of`. Vijf vlaggen voor één levensloop is precies waarom niemand kon zien wat er nog open
stond. Hier is `status` één veld met drie waarden, en `besluit` draagt de uitkomst.

**Gelezen/ongelezen bestaat niet.** Dat hoort bij een berichtenstroom, en die is nu de DM-laag.

## 3. Wie schrijft, wie leest

| | |
|---|---|
| **schrijft** | `cockpit2._act_pagina_voorstel` en de werkoverleg-actietak — de enige twee plekken |
| **leest** | `views/inbox` (of wat ervoor in de plaats komt), en `_act_verzoek_besluit` |
| **beslist** | `_act_verzoek_besluit`, achter `_artefact_gate` (pagina) resp. de rol-poort (actie) |

De poort verandert niet. Wie vandaag mag beslissen, mag dat morgen ook — dit is een verhuizing van
opslag, geen herverdeling van bevoegdheid. Daar hoort een test op.

## 4. `spanning_ontstaat` haakt hier in

De typeer- en bevindingpoort hing aan `NotifStore.add` en heeft sinds B1 geen aanroeper meer. Hij
gaat aan de **write-kant van deze store** hangen — en dat is inhoudelijk beter dan waar hij stond:
hij bestond om te bepalen *waar iets heen moet en of het hout snijdt*, en dat is een vraag bij een
verzoek, niet bij een mededeling. Een DM hoeft niet getypeerd te worden.

De `MENS_GETYPT`-regel verhuist mee: wat een mens letterlijk typte wordt nooit herschreven.

## 5. De guard-test

Zelfde ratchet-gedachte als de CSS-regels, maar strenger — hier is het een **bevriezing** en geen
plafond, omdat de hele reden van deze store is dat hij klein blijft:

1. **De verzameling objecttypen is precies `{"pagina_voorstel", "actie"}`.** Een derde erbij faalt.
2. **De veldenlijst per objecttype staat vast** (§1). Een veld erbij of eraf faalt.
3. **De statusverzameling is precies `{"open", "afgerond", "ingetrokken"}`.**
4. **Geen enkel veld uit de verboden lijst in §1 komt voor** — structureel getoetst, niet op naam,
   zodat `read_at` of `is_archived` ook stuiten.
5. **De poort staat vóór de mutatie**, zoals bij `_act_artefact_edit` — op volgorde in de bron
   getoetst; een poort ná de schrijfactie is geen poort.

## 6. Wat dit NIET oplost

`NotifStore` kan hierna weg voor de twee flows, maar de **33 persoon-gerichte rijen** en de
historie staan al als DM. Wat overblijft is de klasse zelf plus `/inbox` en `/inbox/verwerk` als
scherm. Dat blijft stap B2, en die is pas te zetten als deze store draait.

**Eén open vraag:** `/inbox` toont straks twee dingen naast elkaar — je DM's (berichten) en je
besluitwachtrij (verzoeken). Wordt dat één scherm met twee secties, of gaat de besluitwachtrij bij
de plek waar hij over gaat (voorstellen bij de wiki-pagina, acties bij het werkoverleg)? Dat laatste
is consistenter met "één hoofdmetafoor per scherm", maar het betekent dat je geen enkele plek meer
hebt die zegt "dit ligt bij jou". Jouw keuze.
