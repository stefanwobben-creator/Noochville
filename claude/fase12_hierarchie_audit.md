# Fase 12 — audit visuele hiërarchie: welke klassen dragen een kader dat ze niet horen te dragen

**Status: ONDERZOEK EN VOORSTEL. Er is geen CSS gewijzigd.** Dit raakt gedeelde klassen over
tientallen schermen, dus het gaat eerst langs Stefan — zelfde afspraak als bij de `--nu-*`-tokenronde
van fase 9/10.

Datum: 20 september 2026. Gemeten op de huidige `main` (fase 11 laag 1+2 inbegrepen).

---

## 1. De diagnose in één zin

De kader-taal uit fase 9/10 (2px zwart, geen radius, geen schaduw) is het juiste vocabulaire voor
**content-containers**, maar hij staat óók op dingen die in de referentiebeelden nooit een kader
krijgen: op de primaire knop (bovenop zijn vulling), op elk etiket van twee woorden, en op de
filterknoppen. Daardoor heeft alles op het scherm dezelfde visuele stem.

De maat is het bewijs: **`.chip` staat 101 keer in 22 bestanden** en draagt sinds fase 9 een
1,5px zwarte rand. Eén etiket met een kader valt niet op; honderd wel.

---

## 2. Wat de referentiebeelden doen (uit de brief, §Fase 12)

| element | in de referentie | dus |
|---|---|---|
| navigatie (`SHOP STORE MISSION CONTACT`) | platte tekst, geen kader per item | gewicht/kleur draagt "actief" |
| primaire knop | gevulde vlakke kleur, **geen rand** | de vulling ís het signaal |
| eyebrow / label | kleine hoofdletter-tekst, geen kader | licht van gewicht |
| content-container | zwarte rand | het enige element mét kader |

---

## 3. De audit per klasse-familie

Aantallen = voorkomens in de views (`class='…'`), plus het aantal bestanden. Een bestand ≈ een
scherm; `cockpit2.py` telt als één maar bedient er meer, dus de spreiding is eerder groter dan
kleiner.

### 3.1 Container — GEEN WIJZIGING NODIG

| klasse | nu | voorkomens | voorstel |
|---|---|---|---|
| `.card` `.box` `.kpi` `table` | `2px solid #000`, radius 0, wit, geen schaduw | `.card` 78× / 15 best. | **ongewijzigd** |
| `.pkaart` `.kcard` `.pcard` | idem | kaart + bord | **ongewijzigd** |
| `.pcol` (bordkolom) | 1,5px subtiel + tint, merkteken per kolom | 1× | **ongewijzigd** |

Dit is de enige rol die een kader hóórt te dragen, en hij doet het goed.

### 3.2 Primaire actie — KADER ERAF

| klasse | nu | voorkomens | voorstel |
|---|---|---|---|
| `.btn.ok` | `background:#00FF00` **plus** `border:2px solid #000` | `ok` 65× / 24 best. | vulling houden, **rand weg**; hover blijft inverteren |

De vulling en de rand zeggen allebei "dit is de hoofdactie". Twee signalen voor één betekenis is
precies wat het onderscheid opeet: naast een kaart met dezelfde 2px lijn leest de knop als nóg een
vlak in plaats van als de handeling.

### 3.3 Secundaire actie — DUNNER DAN EEN CONTAINER

| klasse | nu | voorkomens | voorstel |
|---|---|---|---|
| `.btn` | `border: 2px solid #000` — **exact de container-rand** | `btn` 110× / 23 best. | `1.5px`, zodat de 2px van een container de zwaarste lijn op het scherm blijft |
| `.btn.ghost` | 1,5px subtiel, grijze tekst | 4× / 3 best. | ongewijzigd (doet het al goed) |

Dit is de kern van Stefans klacht, in één regel CSS: een knop en een kaart trekken nu dezelfde lijn.
Hiërarchie ontstaat niet door een kader weg te halen maar door **één lijndikte per rol**.

### 3.4 Label / badge / status — LICHT, GEEN ZWART KADER

| klasse | nu | voorkomens | voorstel |
|---|---|---|---|
| `.chip` `.pill` `.badge` | `1.5px solid #000`, wit vlak, uppercase | `chip` 101× / 22 best.; `pill` 21× / 6 | **rand weg**, lichte tint als vulling (`--nu-bg-alt`) met `--nu-accent-text` als tekst |
| `.chip.outline` / `.amber` / `.coral` | eigen randen bovenop | `outline` 16×, `amber` 13×, `coral` 4× | tint-varianten van hetzelfde atoom, nog steeds zonder zwart kader |
| `.nu-status` | 1,5px rand + vorm + woord | 2× / 2 best. | **vorm en woord blijven** (dat is de toegankelijkheidsregel), de RAND vervalt; de tint draagt het vlak |
| `.msg-nieuw` (ongelezen-teller) | zwart vlak, neon cijfer | 1× | ongewijzigd — dit ís een teller, geen kader |

Opmerkelijk: de basis-`.chip` in `nooch.css` was al een tintvulling **zonder** rand. De zwarte rand
is er in fase 9 bijgekomen. Het voorstel is dus deels een terugkeer naar wat er stond, in de
`--nu-*`-tinten.

### 3.5 Navigatie en tabs — BIJNA GOED

| klasse | nu | voorkomens | voorstel |
|---|---|---|---|
| `.c2-subnav a` `.c2-navbtn` | geen kader, uppercase, hover inverteert | 1 best. (gedeelde zijbalk, elk scherm) | **ongewijzigd** — dit volgt de referentie al |
| `.msg-kanaal` | geen kader; `.on` inverteert | 1 best. | **ongewijzigd** |
| `.c2-tabs a.on` | `2px` rand met open onderkant | 1 best. | mag blijven (klassieke tab-vorm), maar wel **1,5px** mee met §3.3 |
| `.cl-filter` | `1.5px solid #000` per filterknop | 11× / 6 best. | geen kader in rust; actief = gevuld (zoals nu). Een rij van zes filters leest nu als zes doosjes |

### 3.6 Informatie / data — TYPOGRAFIE, GEEN KADER

| klasse | nu | voorkomens | voorstel |
|---|---|---|---|
| `.ptitle` | vet, geen kader | 7 best. | ongewijzigd |
| `.kpi-val` / `.pbadge` | groot getal, geen kader | 2 best. | ongewijzigd |
| `.nu-progress` (**nieuw, fase 11**) | 8px hoog met `1.5px` rand om de baan | 2 best. | **kandidaat**: een balkje is data. Zonder rand, met `--nu-border-subtle` als baan, past hij bij deze rol. Bewust mét rand gebouwd omdat dat vandaag het systeem is — hij hoort bij dit besluit, niet ervóór |

---

## 4. Wat dit raakt als je het doorvoert

Vier regels CSS in `nooch-ui.css` (`.btn`, `.btn.ok`, `.pill/.chip/.badge`, `.cl-filter`) plus twee
kleine (`.nu-status`, `.c2-tabs a.on`). **Geen enkele view hoeft aangeraakt te worden** — dat is het
gevolg van de fase 9/10-opruiming: de klassen staan al overal, dus de correctie zit in één bestand.

Wel raakt het elk scherm tegelijk. Daarom hoort er een blik van Stefan op het resultaat tussen, net
als bij de tokenronde.

## 5. Aanbevolen volgorde (klein naar groot effect)

1. `.btn.ok` — de rand eraf. Eén regel, meteen zichtbaar op elke primaire knop.
2. `.btn` — 2px → 1,5px. Hiermee wint de container zijn voorrang terug.
3. `.chip/.pill/.badge` — kader eraf, tint erop. Grootste effect (101 voorkomens), dus als derde
   en pas na akkoord op 1 en 2.
4. `.cl-filter` en `.nu-status` — meelopen met 3, zelfde redenering.
5. `.nu-progress` en `.c2-tabs a.on` — restjes, mee in dezelfde beurt.

## 6. Wat NIET voorgesteld wordt

- Geen nieuwe kleuren, geen nieuw lettertype, geen nieuwe klassen. De `--nu-*`-tokens blijven.
- Geen radius en geen schaduwen terug: "scherp en plat" blijft, het gaat alleen over wélk element
  een lijn krijgt.
- De regel "status = vorm plus woord, nooit kleur alleen" blijft onaangetast. Bij `.nu-status`
  vervalt alleen het kader; de vorm en het woord zijn juist de dragers.

---

# 7. Herziening van het getal "63 kleur-alleen-statussen"

Stefans vraag: dat getal komt uit fase 9 en is waarschijnlijk verouderd na de fase 9/10/11-rondes.
Opnieuw gemeten, met **exact dezelfde methode** als toen (tellen per selector in `nooch.css` die
`--green-tint`, `--yellow-light`, `--error-tint`, `--coral` of `--goal-tint` als *background* zet).

| meting | toen (commit `8ab787a`, fase 1-9) | nu |
|---|---|---|
| selectors in `nooch.css` | **64** | **64** — geen enkele erbij, geen enkele weg |

**Twee dingen die de herziening oplevert, en het tweede is het bruikbare getal:**

1. **Het getal was 64, niet 63.** Ik heb het bij dezelfde commit nagemeten waarin de
   fase-9-inventarisatie werd geschreven: daar stonden er al 64. De "63" in die inventarisatie
   (en in de brief) was één te laag. Niet erg, wel goed om te weten: er is sindsdien niets
   veranderd aan dit cijfer, dus elke schommeling die je later ziet is écht nieuw.

2. **Slechts 33 van de 64 zijn vandaag nog kleur-alleen op een `nu`-scherm.** De andere 31 hebben
   inmiddels een tegenhanger in `nooch-ui.css` (fase 9/10 heeft ze binnen `.nu` geneutraliseerd);
   hun regel in `nooch.css` blijft staan voor de schermen die niet meedoen. Dát onderscheid
   bestond in de oorspronkelijke telling nog niet, want toen was er geen `.nu`-laag.

**De 33 die nog echt openstaan, per familie:**

| familie | n | waar |
|---|---:|---|
| `kn-` | 14 | kennisbank |
| `ck-` | 3 | checklists |
| `imp-` | 2 | impact |
| `noo-` | 2 | noochie |
| `cl-` | 2 | checklist-filters |
| `wz-` | 2 | project-wizard |
| losse (`kc-`, `mdot`, `kb-`, `fkind`, `einddoc-`, `avatar`, …) | 8 | verspreid |

De verhouding is scherper dan het oude getal suggereert: **bijna de helft zit in de kennisbank**
(`kn-`, 14 stuks). Wie die ooit aanpakt, haalt in één scherm 42% van de resterende schuld weg.

**Geen actie ondernomen**, zoals gevraagd. Het getal om voortaan te noemen is **33** (nog
kleur-alleen op een nu-scherm) en niet 63/64 (regels in het basis-stylesheet).
