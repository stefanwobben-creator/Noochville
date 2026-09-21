# Technisch ontwerp — de ZOEK-knop in de navigatiebalk

Antwoord op punt 3 van de navigatie-opdracht. **Nog niets gebouwd.** Alle metingen zijn op
21 september 2026 op productie gedaan, op de echte 442 projecten.

---

## De kern: deze zoekfunctie bestaat al, en hij is beter dan het prototype suggereert

`nooch_village/views/search.py` doorzoekt vandaag al **negen** bronnen in één keer, met de
resultaten per groep gescheiden:

| groep | bron | dekt het prototype-punt? |
|---|---|---|
| People | `st.people` | ✅ personen |
| Roles | `st.records` | ✅ rollen |
| Accountabilities | `st.records` | — (bonus) |
| Projects | `st.projects` | ✅ projecten |
| Steps | checklist-items | — (bonus) |
| Pages | `st.att` — policy + note + tool, **inclusief de feiten erop** | ✅ wiki |
| Messages | berichttekst in project- en cirkelkanalen | ⚠️ deels — zie gat 1 |
| Insights | radar | — (bonus) |
| Words | lexicon | — (bonus) |

Hij is bereikbaar via het zoekveld in de zijbalk, live terwijl je typt (dropdown-fragment) en als
volle pagina op Enter, en de `/`-sneltoets is al bedraad. Per groep is hij **fail-soft mét
melding**: valt één store om, dan staat er "niet geladen" in plaats van "0 treffers" — dat
onderscheid is er ooit bewust in gezet.

**Het voorstel is dus niet een tweede zoekmachine bouwen, maar deze in het paneel zetten en de
drie gaten dichten.** Een tweede index naast deze zou precies het `reference, don't copy`-probleem
zijn: twee plekken die bepalen wat "vindbaar" betekent.

---

## Prestatie: gemeten, geen inschatting

`_zoek()` op de echte productiedataset (442 projecten, 119 wiki-pagina's):

| zoekterm | tijd | treffers |
|---|---|---|
| `batch` | **16,6 ms** | 12 |
| `stefan` | **17,7 ms** | 77 |
| `mycelium` | **16,7 ms** | 11 |
| `claims` | **17,7 ms** | 121 |
| `a` (worst case, matcht bijna alles) | **22,6 ms** | 1400 |

Zelfs de pathologische eenletter-zoekopdracht blijft onder de 25 ms. **Er is geen prestatieprobleem
bij 123+ projecten en er hoeft dus geen index, cache of debounce-op-de-server bij.** Dat scheelt
een hele laag die alleen maar uit de pas kan lopen.

De live-dropdown vraagt wel per toetsaanslag; daar staat al een drempel van 2 tekens op. Die houd
ik, plus een debounce in de browser (die er al is voor `gs-drop`).

---

## De drie gaten die ik wél dicht

### 1. Kanaal-NAMEN zijn niet doorzoekbaar
`_gesprekken` zoekt in de TEKST van berichten in project- en cirkelkanalen. Zoek je op "MITH", dan
vind je berichten waarin dat woord valt — maar **niet het MITH-kanaal zelf**. En sinds PR 4/5
bestaan er twee soorten die hij helemaal niet ziet: `goal:` en `topic:`.

**Fix:** een tiende groep `Channels` die op NAAM matcht (General, de vijf doel-kanalen, losse
kanalen), plus `_gesprekken` uitbreiden naar goal- en topic-trails. Kosten: één extra lus over
~10 kanaalnamen. Verwaarloosbaar.

### 2. In de rail-stand is er geen zoekveld
`.nu .c2-side--rail .c2-search { display: none }` — op `/messages` is de globale zoek dus
onbereikbaar. Dat is precies het gat dat de ZOEK-knop vult: een knop past in 80px waar een veld dat
niet doet.

### 3. De knop en het veld mogen niet uiteen gaan lopen
Het paneel krijgt GEEN eigen zoekveld met eigen gedrag. Het rendert het bestaande
`render_search_fragment` in het paneel — zelfde functie, zelfde groepen, zelfde foutmelding. Het
zoekveld in de zijbalk blijft bestaan zolang de zijbalk breed is; in rail-stand is de knop de enige
ingang. Eén renderer, twee plaatsen.

---

## Wat ik NIET doe

- **DM's doorzoekbaar maken.** Die staan er bewust buiten: "een privégesprek doorzoekbaar maken
  voor iedereen die is ingelogd is geen zoekfunctie maar een lek". Dat is een apart besluit, geen
  bijvangst hiervan. Het prototype noemt "kanalen" en ik lees dat als de gedeelde kanalen.
- **Een eigen index of cache bouwen.** Zie de meting.
- **De negen bestaande groepen terugbrengen tot de vijf van het prototype.** Accountabilities,
  Steps, Insights en Words zijn nuttige treffers die er al in zitten; ze eruit slopen zou
  functionaliteit weghalen om een schets te volgen.

---

## Samengevat

| onderdeel | keuze |
|---|---|
| zoekmachine | de bestaande `_zoek()` — negen groepen, fail-soft per groep |
| render in paneel | het bestaande `render_search_fragment`, geen tweede renderer |
| nieuw | groep `Channels` (op naam) + goal/topic-trails in `Messages` |
| prestatie | gemeten 17–23 ms op 442 projecten; geen index nodig |
| DM's | blijven buiten de zoek (bestaand besluit) |
| sneltoets | `/` bestaat al; de knop krijgt dezelfde |

**Akkoord op dit ontwerp?** Dan bouw ik het samen met de accordeon af. Punten 1 en 2 pak ik
ondertussen op, zoals afgesproken.
