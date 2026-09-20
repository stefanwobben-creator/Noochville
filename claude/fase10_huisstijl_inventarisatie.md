# Fase 10 · punt 2 — huisstijl-ijking en restyling-dekking

**Datum:** 20 september 2026
**Status:** inventarisatie. Geen regel CSS gewijzigd.
**Opdracht:** a) `--nu-`-tokens naast de live nooch.earth-huisstijl · b) gecorrigeerde
tokenwaarden voorstellen · c) welke schermen de fase-9-restyling hebben gemist.

---

## 0. Twee dingen ontbreken, en dat bepaalt wat hieronder wel en niet kan

**De referentiebeelden zijn er niet.** `claude/huisstijl_referentie_productpagina.jpg` en
`claude/huisstijl_referentie_email.png` bestaan niet in de repo. De map `claude/` bevat op dit
moment vier bestanden en `fase9_screenshots/`, geen van beide beelden.

Deel **a** en **b** hieronder zijn daarom getoetst aan de **geschreven kenmerken** uit Stefans
bericht, niet aan de beelden. Dat is genoeg om de meeste afwijkingen aan te wijzen — maar níét om
de exacte kleurwaarden vast te stellen. Het limoengroen is de kern van de huisstijl en dat moet uit
een pixel komen, niet uit mijn hoofd. Die ene waarde blijft open tot de beelden er zijn.

**De Fase 10-brief zit niet in de repo.** `claude/implementatiebrief_opruiming_19sept.md` (de
versie die op 19 september in de PR is meegekomen) eindigt bij fase 9 plus een sectie *"Wat hierna
nog open staat"* met drie bullets. Er staat geen fase 10 in, en geen genummerde punten 1 t/m 4. Het
woord "tiende fase" valt twee keer, allebei als open vraag. Wat punt 1, 3 en 4 zijn weet ik dus
niet; ik werk alleen aan wat in het bericht zelf staat.

Deel **c** staat hier los van en is volledig.

---

## 1. (a) De huidige `--nu-`-tokens tegenover de beschreven huisstijl

Alle elf tokens, met hun werkelijke gebruik in `nooch-ui.css`:

| token | waarde | uses | oordeel tegen de beschrijving |
|---|---|---:|---|
| `--nu-bg` | `#FFFAFA` | 1 | **wijkt af.** Dit is 255,250,250 — wit met een roze zweem, geen crème. |
| `--nu-surface` | `#FFFFFF` | 21 | **wijkt af.** Zuiver wit, en dat is expliciet uitgesloten. |
| `--nu-text` | `#000000` | 37 | **wijkt af.** Zuiver zwart, de beschrijving zegt *bijna* zwart. |
| `--nu-neon` | `#00FF00` | 8 | **wijkt af.** Zuiver groen (0,255,0), geen limoen. |
| `--nu-accent` | `#00A551` | 2 | **wijkt af.** Tweede groen. |
| `--nu-accent-text` | `#14713C` | 2 | **wijkt af.** Derde groen. |
| `--nu-bg-alt` | `#E9FBE9` | 2 | **wijkt af.** Vierde groen, als vlak achter de bordkolommen. |
| `--nu-muted` | `#58595B` | 9 | plausibel; te ijken op het beeld. |
| `--nu-border-subtle` | `#E6E7E8` | 7 | **twijfel.** Grijze rand naast de zwarte; de beschrijving kent alleen zwarte randen. |
| `--nu-danger` | `#EE4036` | 3 | buiten de beschrijving; niet te ijken zonder beeld. |
| `--nu-border` | `2px solid var(--nu-text)` | 9 | past binnen "1-2px", maar is overal 2px zonder onderscheid. |

### De vier groenen zijn het zwaarste punt

De beschrijving zegt **precies één** fel limoengroen accent. Er staan er vier in het systeem, en ze
doen alle vier iets anders: `--nu-neon` op de primaire knop en de nav-teller, `--nu-accent` op het
gevulde statusbolletje, `--nu-accent-text` voor groene tekst, en `--nu-bg-alt` als vlak. Dat is geen
accentkleur meer maar een palet.

### Vier afwijkingen die geen token zijn

1. **Koppen zijn niet in hoofdletters.** `.nu h2, .nu h3` zet expliciet `text-transform: none` en
   `letter-spacing: 0`. De beschrijving vraagt vetgedrukte hoofdletterkoppen met strakke tracking.
   `.nu h1` heeft `letter-spacing: -.01em` maar ook geen hoofdletters.
2. **Er is geen eyebrow-label.** "Kleine hoofdletter-eyebrow-labels boven koppen" bestaat niet als
   component. `.pill`/`.chip`/`.badge` dragen wél `text-transform: uppercase`, maar dat is een badge
   in een rand, geen eyebrow.
3. **De primaire knop is wit, niet groen.** `.nu .btn` is wit met zwarte rand; groen zit alleen op
   `.btn.ok`. De beschrijving zet rechthoekige **groene** knoppen als de CTA-vorm. Bovendien staat
   er op geen enkele knop `text-transform: uppercase`.
4. **Eén radius is blijven staan.** `.nu .c2-navct` heeft `border-radius: 999px` — de ronde
   nav-teller. Verder is alles 0. (De ronde vormen in `.nu-status::before` zijn bewust: dat is de
   vorm-codering, geen decoratie.)

### Wat wél klopt

Geen enkele `box-shadow` (expliciet `none` op kaarten en knoppen), geen gradients, `border-radius: 0`
op kaarten, knoppen, tabs, filters en invoervelden, en Archivo als grotesk — geladen via Google
Fonts in `cockpit2_util._NU_LINK`, dus niet stilletjes teruggevallen op een systeemfont.

---

## 2. (b) Voorgestelde tokenwaarden

**Eerst de risico-inschatting corrigeren, want die bepaalt hoe groot dit is.**

Stefan schreef: *"bij 147 gebruiken van `--border` alleen al is een ongecontroleerde tokenwijziging
een risico."* Dat getal gaat over een ánder token dan dat wat hier wijzigt:

| | waar | uses |
|---|---|---:|
| `--border` | `nooch.css` (oud systeem) | **174**, waarvan 144 in de vorm `1px solid var(--border)`; plus 4 in `web_base._CSS` |
| `--nu-border` | `nooch-ui.css` (nieuw systeem) | **9**, allemaal binnen `.nu` |

De `--nu-`-tokens komen **nergens buiten `nooch-ui.css`** voor — niet in Python, niet in `nooch.css`.
Het zwaarste token is `--nu-text` met 37 uses, daarna `--nu-surface` met 21. Een wijziging aan de
`--nu-`-set raakt dus 179 regels CSS in één bestand, niet 147 verspreide plekken, en alleen binnen
de negentien schermen die `body.nu` dragen. Dat is een overzienbare wijziging.

Het getal 147 dat ik eerder zelf noemde was ook niet exact: het zijn er 144 in die specifieke vorm.

### Het voorstel

| token | nu | voorstel | reden |
|---|---|---|---|
| `--nu-bg` | `#FFFAFA` | **`#FCFAF4`** | crème in plaats van rozig wit. Deze waarde bestaat al als `--cream` in `nooch.css`, dus het dorp draagt hem al. |
| `--nu-surface` | `#FFFFFF` | **`#FFFDF8`** | kaarten net iets lichter dan de achtergrond, maar geen zuiver wit. |
| `--nu-text` | `#000000` | **`#1B1B1B`** | bijna zwart. Bestaat al als `--ink`. |
| `--nu-neon` | `#00FF00` | **⟵ uit het beeld** | dit is *de* merkkleur. Ik vul hem niet in op gevoel. |
| `--nu-accent` | `#00A551` | **schrappen** | één groen. De twee uses gaan naar `--nu-neon`. |
| `--nu-accent-text` | `#14713C` | **schrappen** | groene tekst vervalt; tekst is bijna-zwart. |
| `--nu-bg-alt` | `#E9FBE9` | **`#F1ECDF`** | het vlak achter de bordkolommen wordt zand in plaats van groen, zodat groen alleen accent is. Bestaat al als `--sand`. |
| `--nu-border-subtle` | `#E6E7E8` | **schrappen → `--nu-text`** | één randkleur. Raakt `.btn.ghost`, `.pill.muted` en `:disabled`; die onderscheiden zich dan op gewicht en dekking in plaats van op randkleur. |
| `--nu-border` | `2px solid` | **`1.5px solid`** voor kaarten, **`2px`** voor knoppen en het bord | "1-2px", met de zwaardere rand op de klikbare dingen. |
| `--nu-muted` | `#58595B` | ongewijzigd, te ijken | |
| `--nu-danger` | `#EE4036` | ongewijzigd, te ijken | |

### Vier wijzigingen die geen token zijn

1. `.nu h2, .nu h3` → `text-transform: uppercase; letter-spacing: .02em; font-weight: 700`.
   `.nu h1` idem. Dit is de zichtbaarste wijziging van het hele voorstel.
2. Nieuw component `.nu-eyebrow`: klein, hoofdletters, `--nu-muted`, boven de kop.
3. `.nu .btn` krijgt `text-transform: uppercase`; de groene vulling verhuist van `.btn.ok` naar de
   primaire knop, zodat groen de CTA markeert en niet alleen "bevestigen".
4. `.nu .c2-navct` → `border-radius: 0`.

**Eén open vraag bij punt 3.** Nu is `.btn` wit en `.btn.ok` groen. Wordt élke `.btn` groen, dan
verdwijnt het onderscheid tussen "een knop" en "de actie die je moet doen". Op `/projects` staan vijf
`+ add project`-knoppen naast elkaar; vijf groene vlakken is geen accent meer. Mijn voorkeur: `.btn`
blijft zwart-op-crème, `.btn.ok` wordt het limoengroen, en dát is de CTA-vorm uit de referentie.
Te beslissen op het beeld.

---

## 3. (c) Welke schermen de fase-9-restyling hebben gemist

Eerst een correctie op de aanname in de vraag. `/project/nieuw` **staat gewoon in `_NU_ROUTES`** —
het krijgt `body.nu` en `nooch-ui.css`. Het ziet er toch oud uit om een andere reden: de wizard
rendert met een eigen `wz-*`-familie, en `nooch-ui.css` stuurt geen enkele `wz-`-klasse aan.

**De echte regel is dus:** een scherm wordt herstyled als (1) zijn route in `_NU_ROUTES` staat **én**
(2) zijn markup het gedeelde vocabulaire gebruikt (`.card`, `.btn`, `.pill`, `.c2-tabs`, `.pkaart`,
`.msg-item`, …). Valt (2) weg, dan verandert alleen de achtergrond en het lettertype.

### Groep A — in de scope, maar de markup vangt het niet op

Geteld per view: hoeveel klasse-gebruiken staan er die `nooch.css` een kleur, rand, radius of
schaduw geeft en die `nooch-ui.css` níét overschrijft. Dat is precies de oude look die blijft staan.

| view | routes | oude-look-uses | klassen | zwaarste families |
|---|---|---:|---:|---|
| `projects.py` | `/projects`, `/project` | 119 | 62 | `ctrl-`(14), `av`(7), `pf-`(6), `fieldform`(5) |
| `inbox.py` | `/inbox`, `/inbox/verwerk` | 76 | 43 | `box-details`(8), `fbubble`(7), `wo-ocd`(3) |
| `roloverleg.py` | `/roloverleg2` | 56 | 31 | `sec-issue`(5), `att-lbl`(4), `sec-kop`(3) |
| `overview.py` | `/node`, `/person`, `/admin` | 47 | 19 | `att-lbl`(9), `av`(5), `dellink`(4) |
| **`wizard.py`** | **`/project/nieuw`** | **35** | **18** | **`wz-hint`(10), `wz-clab`(5), `wz-btn`(3)** |
| `vangst.py` | `/vangst` | 28 | 12 | `att-lbl`(5), `wo-ocd`(4), `box-details`(4) |
| `doelen.py` | `/goals`, `/goal` | 22 | 11 | `box-details`(5), `pbar`(2), `qadd-form`(2) |
| `werkoverleg.py` | `/werkoverleg` | 20 | 13 | `cl-check`(3), `wo-leave`(2), `wo-mem-n`(2) |
| `wiki.py` | `/wiki`, `/pagina` | 14 | 8 | `att-body`(2), `qadd-*`(6) |
| `search.py` | `/search` | 10 | 8 | `gs-empty`(2), `gs-group`(2), `gs-hit`(1) |
| `messages.py` | `/messages` | 4 | 4 | `msg-meta`(1), `att-lbl`(1) |

`wizard.py` is niet de zwaarste in absolute zin, maar wel in verhouding: **2 gedekte klasse-gebruiken
tegen 40 ongedekte**. Alle andere views halen minstens een derde. Daarom valt hij op.

Twee families keren overal terug en zijn de goedkoopste winst: **`att-*`** (`att-lbl` 9+5+4+1) en
**`qadd-*`** (formulierregels), samen goed voor ~40 uses over zes views. Eén regel per familie in
`nooch-ui.css` raakt ze allemaal.

*Ruis in deze telling:* `ok` telt mee als ongedekt omdat `.ok` los in `nooch.css` staat, terwijl
`nooch-ui.css` wél `.btn.ok` aanstuurt. In de praktijk staat hij bijna altijd als `class="btn ok"`
en klopt het dus. Per view is dat 1 tot 7 uses te hoog.

### Groep B — in fase 7/8 herbouwd, maar buiten de nu-scope gebleven

| route | view | wat er aan de hand is |
|---|---|---|
| `/site-audit` | `site_audit.py` | In fase 7 aangeraakt (taalresten), maar staat in de 27 overgeslagen routes. Volledig oude stijl. |
| `/middelen` | `overview.py` | **Zelfde bestand** als `/node`, `/person` en `/admin`, die wél meedoen. Dezelfde rendercode ziet er dus anders uit afhankelijk van de URL. |
| `/rolefillers` | `overview.py` | Idem. |

`/middelen` en `/rolefillers` zijn de scherpste inconsistentie van de drie: er is geen inhoudelijke
reden voor, het is een gat in de routelijst. Ze toevoegen aan `_NU_ROUTES` is twee regels.

### Groep C — in de scope, maar nooit herbouwd

`/werkoverleg` en `/roloverleg2` staan in `_NU_ROUTES` terwijl hun views in fase 7/8 niet zijn
aangeraakt. Ze kregen de body-klasse op grond van de fase-9-brief ("de governance- en
tactical-meeting-modals krijgen dezelfde visuele stijl"), niet op grond van een herbouw. Samen 76
oude-look-uses. Geen fout, wel goed om te weten dat hier meer werk ligt dan bij de rest.

---

## 4. Wat ik nodig heb voor ik iets aanpas

1. **De twee referentiebeelden**, vooral voor het limoengroen. Dat is de enige waarde in §2 die ik
   niet zelf kan invullen.
2. **Akkoord op de tokentabel** in §2, inclusief het schrappen van `--nu-accent`,
   `--nu-accent-text` en `--nu-border-subtle`.
3. **Een antwoord op de knop-vraag** aan het eind van §2: wordt élke `.btn` groen, of blijft groen
   voorbehouden aan de CTA?
4. **Een keuze in §3**: alleen groep B (drie routes, twee regels), of ook groep A — en dan in welke
   volgorde. `att-*` en `qadd-*` eerst is de grootste winst per regel.

---

# 5. ADDENDUM — de beelden zijn er, en ze weerleggen het halve voorstel

**20 september 2026.** `claude/huisstijl_referentie_productpagina.jpg` (1042×8000) en
`claude/huisstijl_referentie_email.png` (2528×6430) staan er. Elke pixel geteld met Pillow, geen
steekproef, geen schatting.

## 5.1 Wat er werkelijk in de beelden staat

| rol | productpagina | email | huidig `--nu-`-token | oordeel |
|---|---|---|---|---|
| achtergrond | `#FEFAF9` (49,5%) | **`#FFFAFA` (84,4%)** | `--nu-bg: #FFFAFA` | **exact goed** |
| wit vlak | `#FFFFFF` (4,2%) | `#FFFFFF` (6,4%) | `--nu-surface: #FFFFFF` | **exact goed** |
| CTA-vulling | `#00FF00` | `#00FF00` | `--nu-neon: #00FF00` | **exact goed** |
| bovenbalk | `#00A551` | `#00A551` (1,0%) | `--nu-accent: #00A551` | **exact goed**, maar andere rol |
| licht groen vlak | `#E2FFE3` (18,0%) | `#E3FFE3` | `--nu-bg-alt: #E9FBE9` | **fout** |
| tekst/randen | `#000000` + `#1A1A1A` | `#000000` (2,5%) + `#1A1A1A` (1,8%) | `--nu-text: #000000` | **goed**, maar onvolledig |
| grijze tekst | — | `#58595B` (0,8%) | `--nu-muted: #58595B` | **exact goed** |
| subtiele rand | — | `#E6E7E8` | `--nu-border-subtle: #E6E7E8` | **exact goed** |
| — | — | `#1F9D55` (0,35%) | `--nu-accent-text: #14713C` | **komt niet voor** |
| crème | **niet aanwezig** | **niet aanwezig** | (voorstel `#FCFAF4`) | **verworpen** |

## 5.2 Waar de twee groenen staan (bounding boxes, niet geraden)

```
EMAIL        #00FF00   y  99-178   x 1755-2051  (297×80)   tekst op dat vlak: #000000
             #00FF00   y 5332-5419 x  837- 987  (151×88)   tekst op dat vlak: #000000
             #00A551   y   0- 70   x    0-2527  (2528×71)  tekst op dat vlak: #FFFFFF

PRODUCTPAGINA #00FF00  y  43- 71   x  725- 844  (120×29)   "ORDER NOW" in de nav
              #00FF00  y 407- 442  x  575- 972  (398×36)   "BECOME FOUNDING MEMBER"
              #00FF00  y 523- 552  x  853- 972  (120×30)   "ORDER NOW"
              #00A551  y   0- 27   x    0-1041  (1042×28)  de aankondigingsbalk bovenaan
```

Dat is eenduidig:

- **`#00FF00` = de knop.** Losse rechthoeken, altijd met **zwarte** tekst erin.
- **`#00A551` = de aankondigingsbalk.** Eén doorlopende band over de volle breedte, met **witte**
  tekst. Geen knop.

Er is dus **niet** één groen, en ook geen limoengroen. Er zijn er twee, met elk een eigen taak, en
`#00FF00` is zuiver groen.

## 5.3 Gevolg: zes van de acht voorgestelde tokenwijzigingen vervallen

De tokentabel in §2 is getoetst aan de geschreven kenmerken uit Stefans bericht ("gebroken
wit/crème", "precies één fel limoengroen"). De pixels zeggen iets anders, en de pixels zijn het
bindende ijkpunt.

| voorstel uit §2 | status na sampling |
|---|---|
| `--nu-bg` → `#FCFAF4` (crème) | **vervalt.** `#FFFAFA` is exact de merkachtergrond. Crème komt in geen van beide beelden voor. |
| `--nu-surface` → `#FFFDF8` | **vervalt.** Zuiver wit is er wél, als tweede vlakkleur. |
| `--nu-text` → `#1B1B1B` | **vervalt** als vervanging. `#000000` en `#1A1A1A` staan er allebei. Zie 5.4. |
| `--nu-neon` → uit het beeld | **opgelost: `#00FF00`**, ongewijzigd. |
| `--nu-accent` schrappen | **vervalt.** `#00A551` is een echte merkkleur met een eigen rol. |
| `--nu-border-subtle` schrappen | **vervalt.** `#E6E7E8` staat letterlijk in de e-mail. |
| `--nu-bg-alt` → `--sand` | **vervangen door `#E2FFE3`.** Het vlak ís groen, alleen niet de tint die er nu staat. |
| `--nu-accent-text` schrappen | **blijft staan.** `#14713C` komt in geen van beide beelden voor. |

**En het advies om `--cream`, `--ink` en `--sand` te hergebruiken vervalt daarmee ook.** Die drie
zijn het oude Village-palet, niet het nooch.earth-palet. Ze overnemen zou de app juist verder van de
huisstijl af brengen. De `reference, don't copy`-gedachte erachter klopt wel — maar de bron is het
beeld, niet `nooch.css`.

## 5.4 Wat er dan wél te doen valt

Drie kleurwijzigingen, alle drie uit de pixels:

1. `--nu-bg-alt`: `#E9FBE9` → **`#E2FFE3`**
2. `--nu-accent-text`: `#14713C` → **`#1F9D55`** (de enige andere groentint die echt in de e-mail
   staat), of schrappen als groene tekst nergens nodig is
3. **`--nu-text` splitsen**: `#000000` voor randen, koppen en het logo; `#1A1A1A` voor lopende
   tekst. Beide staan prominent in beide beelden; nu draagt één token allebei de rollen.

En de vier niet-kleur-punten uit §1 blijven **onverkort staan** — die zijn door de beelden juist
bevestigd:

- **Koppen in hoofdletters.** De productpagina: `TWO YEARS OF TESTING BEFORE WE SOLD ONE PAIR`,
  `LOOK AT THE PEOPLE, NOT THE PRODUCT PHOTO`, `CHEAP SHOES DON'T EXIST`, `NINE PLANTS, ONE SHOE`,
  `QUESTIONS PEOPLE ACTUALLY ASKED`, `GROW A PAIR`. Allemaal. `.nu h2, .nu h3` zet nu expliciet
  `text-transform: none`.
- **Eyebrow-labels bestaan echt.** Boven die koppen staan `THE PROOF`, `THE PRICE`, `THE PACT`,
  `THE PEOPLE`, `WHAT'S IN IT` — klein, hoofdletters, grijs. Er is geen `.nu-eyebrow`.
- **Knoptekst in hoofdletters.** `ORDER NOW`, `BECOME FOUNDING MEMBER`, `ALL REVIEWS`,
  `READ THE LETTERS`, `WHY NOOCHES DON'T COST €269`. Geen enkele `.nu .btn` heeft
  `text-transform: uppercase`.
- **`.nu .c2-navct` heeft nog `border-radius: 999px`** als enige ronde hoek.

## 5.5 Wat dit over de werkwijze zegt

Het prototype v15 was blijkbaar al uit de echte huisstijl gesampled: zes van de elf tokens zijn
pixel-exact. Mijn §1 en §2 lazen als een reeks afwijkingen omdat ik ze aan een beschrijving in
woorden toetste in plaats van aan het beeld. "Gebroken wit/crème" en `#FFFAFA` klinken hetzelfde en
zijn het niet; "één fel limoengroen" en `#00FF00` + `#00A551` ook niet.

Dat is dezelfde fout als de twaalf premissen uit fase 1-9, nu van de andere kant: toen bleek de
bron onjuist en de code goed, hier bleek de beschrijving onjuist en het token goed. De les is
dezelfde — meet, en laat de meting winnen.
