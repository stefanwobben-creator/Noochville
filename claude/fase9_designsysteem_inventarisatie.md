# Fase 9 — designsysteem-inventarisatie

**Datum:** 20 september 2026
**Status:** inventarisatie, geen regel CSS aangeraakt
**Bronnen:** prototype v15 (`claude.ai/artifact/Y76cYZFUvYiAzp6oweqeD1`, 1.737 regels HTML) naast
`nooch_village/static/nooch.css` (1.603 regels) en `nooch_village/web_base.py::_CSS`

---

## 1. Het verschil in één blik

| | prototype (Nooch UI v1) | live nu |
|---|---|---|
| Randen | `2px solid #000`, overal dezelfde | **168** randen van 1px, **9** van 2px |
| Radius | `border-radius:0` (scherpe hoeken) | `--radius:9px`, **110×** gebruikt; `border-radius:0` staat er 5× |
| Achtergrond | `--bg:#FFFAFA` (één wit-roze) | `--cream`, `--cream-2`, `--cream-3`, `--sand` — vier crèmetinten |
| Accent | `--neon:#00FF00` + `--accent:#00A551` | `--green:#1F9D55`, `--green-dark:#14713C`, `--green-tint:#D3EFDD` |
| Typografie | Archivo, één familie, gewichten 400–700 | Bricolage Grotesque (display) + DM Sans (body) |
| Tokens | 10 | **25** |
| Extra kleuren | geen | `--yellow`, `--yellow-light`, `--coral`, `--goal` (paars), `--goal-tint` |
| Schaduw | geen | `--shadow` (twee lagen) |
| Status | vorm **plus** woord | kleur-alleen (zie §4) |
| Omvang | ~180 regels CSS | 1.603 regels, 1.093 selectors, **201** prefix-families |

### De 25 huidige tokens

```
--ink          #1B1B1B      --cream        #FCFAF4      --neon         #2bff6f
--gray         #4A4A4A      --cream-2      #FBF6EA      --goal         #6a4fa0
--subtle       #7A7A7A      --cream-3      #FFF7E8      --goal-tint    #ece5f6
--muted        #9A9483      --sand         #F1ECDF      --radius       9px
--green        #1F9D55      --surface      #fff         --radius-pill  999px
--green-dark   #14713C      --yellow       #FFCE2E      --shadow       (2 lagen)
--green-tint   #D3EFDD      --yellow-light #FFF1B8      --font-display 'Bricolage Grotesque'
--border       #DDD4C0      --coral        #FF6B5B      --font-body    'DM Sans'
--error-tint   #FDEAEA
```

### De 10 prototype-tokens

```
--neon          #00FF00     --surface       #FFFFFF     --border-subtle #E6E7E8
--accent        #00A551     --text          #000000     --danger        #EE4036
--accent-text   #14713C     --muted         #58595B     --border        2px solid var(--text)
--bg-alt        #E9FBE9     --bg            #FFFAFA
```

`--accent-text` (#14713C) is **identiek** aan de huidige `--green-dark`. Dat is het enige token dat
één-op-één overeenkomt.

---

## 2. Klasse-pariteitstabel (CLAUDE.md, harde regel)

| prototype-klasse | live-klasse(n) | oordeel |
|---|---|---|
| `.card`, `.card--soft` | `.card` | 1-op-1. Alleen rand (1px→2px) en radius (9px→0) wijzigen. |
| `.btn`, `--primary`, `--quiet`, `--sm` | `.btn`, `.btn.ok`, `.btn.ghost`, `.btn.sm` | 1-op-1. Live: groene vulling + 1px rand + schaduw. Prototype: zwart-op-wit, hover inverteert, `--primary` = neon. |
| `.pill`, `--muted`, `--accent` | `.pill`, `.chip`, `.badge` | **3 live → 1 prototype.** Samenvoegen, of het verschil expliciet maken. Nu doen ze grotendeels hetzelfde met drie namen. |
| `.status--ok`, `--open`, `--wait` | *bestaat niet* | **Nieuw.** Zie §4 — dit is de grootste inhoudelijke toevoeging. |
| `.tabs .tab`, `.is-active` | `.c2-tabs` | 1-op-1. |
| `.side`, `.subnav`, `.orgtree` | `.c2-side`, `.c2-subnav`, `.c2-org` | 1-op-1 — in fase 7 al naar deze structuur gebouwd. |
| `.kanban`, `.kcol`, `.kcard` | `.pkaart-*`, `.pchip-*`, `.psec-*`, `.rail-*` | **4 live-families → 3 prototype-klassen.** Herindeling, niet enkel herkleuren. |
| `.trail`, `.trail-item`, `--system` | `.fentry` (wall), `.msg-item` (Messages) | **2 live → 1 prototype.** De wall en Messages renderen nu verschillend terwijl ze sinds fase 8 dezelfde data zijn. Samenvoegen. |
| `.wiki-grid`, `.domain-list` | `.c2-wiki`, `.wiki-doms` | 1-op-1 — fase 7. |
| `.msg-layout`, `.msg-channel` | `.msg-layout`, `.msg-kanaal` | 1-op-1 — fase 8. |
| `.detail-row` | `.detail-row` (projectkaart) | 1-op-1. |
| `.chips`, `.chip`, `.is-active` | `.cl-filters`, `.cl-filter` | 1-op-1, andere naam. |
| `.checkrow`, `.tri`, `.tribtn` | `.ck-*` | 1-op-1. |
| `.kpi`, `.spark` | `.kpi-*`, `.kpidata-*` | 1-op-1 — maar staat op `/metrics2`, buiten scope (§5). |
| `.toggle`, `.track` | *bestaat niet* | **Niet bouwen.** Alleen nodig op Admin·Skills, en die blijft read-only tot Stefan beslist. |
| `.embed`, `.embed-head`, `.file-grid`, `.file-card`, `.img-placeholder` | *bestaat niet* | **Niet bouwen.** Dit is de "rich page (demo)" op de wiki: een demonstratie van wat een pagina *zou kunnen* dragen (projectbord, metriek, tool, bijlagen). Geen bestaande functionaliteit; bouwen zou een feature verzinnen onder het mom van vormgeving. |
| `.avatar` | `.avatar` | 1-op-1. |
| `.modal-mask`, `.modal`, `.meeting-grid`, `.steps`, `.step` | `.ovl-*`, `.rov-*`, `.rovm-*`, `.wo-*` | De governance- en tactical-modals bestaan functioneel; alleen stijl. |
| `.crumb` | *verwijderd op 23 juli* | De breadcrumb is bewust weggehaald (de hiërarchie staat in de organisatieboom). **Niet terugzetten** zonder besluit. |
| `.empty` | `.empty`, `.muted` | 1-op-1. |

### Bewuste afwijkingen van het prototype

1. **`.embed` / `.file-grid` niet bouwen** — demo van een niet-bestaande feature.
2. **`.toggle` niet bouwen** — hangt aan Admin·Skills-schrijfbaarheid, staat on hold.
3. **`.crumb` niet terugzetten** — is op 23 juli met reden verwijderd.

---

## 3. Waar de klassen live staan (omvang van het werk)

```
nooch.css            1.603 regels, 1.093 selectors, 201 prefix-families
web_base._CSS        tokens + basis-atomen (h1/h2/a/table/.btn/.chip/.badge)
```

Het prototype heeft **~30** klassen. De live set heeft er 1.093. Het verschil is niet dat het
prototype minder kan — het is dat 8 maanden schermen elk hun eigen familie hebben meegebracht.
Fase 9 hoeft die niet op te ruimen (dat was het juli-traject), maar moet er wel doorheen.

---

## 4. Statusweergave: de enige inhoudelijke toevoeging

Het prototype:

```css
.status        { border:1.5px solid var(--text); font-weight:700; }
.status::before{ content:""; width:.55em; height:.55em; }        /* de VORM */
.status--ok::before   { background:var(--accent); border-radius:50%; }          /* rond, gevuld */
.status--open::before { border:1px solid var(--muted); border-radius:50%; }     /* rond, leeg */
.status--wait::before { background:var(--text); clip-path:polygon(...); }       /* half vierkant */
```

Dus: **vorm + woord + rand**, nooit kleur alleen.

Live is status vrijwel overal een gekleurde achtergrond. Exact geteld per selector die
`--green-tint`, `--yellow-light`, `--error-tint`, `--coral` of `--goal-tint` als achtergrond zet:

```
63 selectors  (mijn eerdere schatting van 54 was te laag — dit is de telling per selector)

kn-  14   (kennisbank)        ck-   3   (checklists)
ibx-  6   (inbox-drawer)      imp-  2   (impact)
cl-   5   (checklist-filters) noo-  2
wz-   5   (wizard)            rdr-  2   (reader)
chip.coral 2                  einddoc- 2
…en 18 losse selectors
```

**Dit is het punt dat over de scopegrens heen loopt.** De regel "status is vorm plus woord" is
dorpsbreed; `kn-` (kennisbank) en `wz-` (wizard) staan op schermen die in fase 9 buiten scope
vallen. Pas ik `.status` alleen toe op de 19 schermen in scope, dan draagt hetzelfde begrip twee
verschijningsvormen. Alles ineens is groter dan fase 9 zoals de brief hem beschrijft.

**Openstaande vraag 1 voor Stefan.**

---

## 5. Scope: 19 schermen in, 27 uit

### In scope (aangeraakt in fase 7/8)

```
/ (→ /projects)   /projects      /messages      /wiki          /pagina
/node             /person        /project       /project/nieuw /admin
/search           /inbox         /inbox/verwerk /goals         /goal
/werkoverleg      /roloverleg2   /vangst        /index.html
```

Views aangeraakt in fase 7–8: `bronnen`, `doelen`, `feed`, `inbox`, `messages`, `overview`,
`projects`, `search`, `site_audit`, `vangst`, `wiki`.

### Buiten scope — 27 routes

```
/claims  /claims/scan          ← best werkende cluster, externe deadline (EmpCo 27 sept)
/metrics2  /kpi_new  /metric_export   ← grootste view-bestand (2.149 regels)
/catalog  /bronnen  /skills
/copy-check  /copy-prompt  /decision-coach  /site-audit
/keywords  /woordenschat  /long-term-trends
/rapport  /noochie  /middelen  /rolefillers  /context  /file
/login  /logout  /wachtwoord
/wizard/create  /wizard/plan  /wizard/sharpen
```

Twee daarvan springen eruit: **`/claims`** (het meest gebruikte cluster van het dorp) en
**`/metrics2`** (het grootste scherm). Die overslaan betekent dat het dorp er half nieuw en half
oud uitziet op precies de schermen die dagelijks open staan. Reële kandidaat voor de tiende fase
die de brief openlaat.

**Openstaande vraag 3 voor Stefan.**

---

## 6. Tokens: één bron of twee?

De brief zegt: *"Bouw het nieuwe visuele systeem als een eigen, klein tokenbestand … naast de
bestaande nooch.css, niet erin vermengd."*

Voor de **klassenset** is dat verstandig: de oude en de nieuwe set door elkaar geeft precies de
wildgroei die de juli-inventarisatie signaleerde.

Voor de **tokens** botst het met een harde regel uit CLAUDE.md: *"Reference, don't copy — een
feit/getal leeft op ÉÉN gezaghebbende plek."* Twee `:root`-blokken met elk een eigen groen is die
overtreding, en de toets uit CLAUDE.md ("als dit getal verandert, op hoeveel plekken pas ik het
aan?") geeft dan het verkeerde antwoord.

**Voorstel:** één nieuw tokenbestand als bron, en de oude tokens verwijzen ernaar:

```css
/* nooch-ui.css — de bron */
:root { --accent:#00A551; --text:#000; --bg:#FFFAFA; --border:2px solid var(--text); … }

/* web_base._CSS — de oude namen blijven werken, maar wijzen naar de bron */
:root { --green: var(--accent); --green-dark: var(--accent-text); --ink: var(--text); … }
```

Zo bewegen de oude klassen mee zonder dat ik er één aanraak, en is er één plek waar een kleur
verandert. De klassensets blijven wél gescheiden, zoals de brief vraagt.

**Openstaande vraag 2 voor Stefan.**

---

## 7. Eindcheck: screenshots

De brief vraagt een screenshot-vergelijking met Playwright, op desktop- en mobielbreedte.

**Playwright zit niet in de venv en de cockpit draait hier niet.** Wat ik wél kan: renderen en de
HTML-structuur vergelijken, zoals bij de fase 7- en fase 8-doorlopen (negen respectievelijk tien
controlepunten, alle gehaald). Maar *"het oogt hetzelfde"* kan ik daarmee niet aantonen — alleen
*"het bevat hetzelfde"*.

Twee wegen:
- Playwright toevoegen aan de venv en de cockpit lokaal starten; of
- Stefan doet de visuele check op prod na deploy, met het prototype ernaast.

**Openstaande vraag 4 voor Stefan.**

---

## 8. Samengevat: vier vragen

1. **Statusweergave** — `.status` alleen op de 19 schermen in scope (twee verschijningsvormen voor
   hetzelfde begrip), of dorpsbreed doortrekken (groter dan fase 9)?
2. **Tokens** — één bron met alias-tokens zoals in §6, of strikt twee gescheiden `:root`-blokken
   zoals de brief letterlijk zegt?
3. **`/claims` en `/metrics2`** — meenemen, of bewust overslaan en als tiende fase parkeren?
4. **Screenshots** — Playwright toevoegen, of visuele check door Stefan op prod?

Zodra deze vier beantwoord zijn kan het bouwen beginnen. Tot die tijd is er geen regel CSS
gewijzigd.

---

# ADDENDUM — wat er gebouwd is (20 september 2026)

De vier vragen uit §8 zijn beantwoord: status alleen op de 19 schermen, tokens strikt gescheiden,
`/claims` en `/metrics2` geparkeerd, Playwright voor de eindcheck.

## Eén afwijking, uit noodzaak

De opdracht was "twee gescheiden `:root`-blokken". Dat kan technisch niet: vier tokennamen botsen,
en `--border` is dodelijk — oud een KLEUR, nieuw een SHORTHAND, en hij staat **147×** in nooch.css
als `border:1px solid var(--border)`. Een tweede globale `:root` maakt daar
`border:1px solid 2px solid #000` van: ongeldige CSS, en dan verdwijnen de randen op élk scherm,
óók de geparkeerde.

Opgelost met de **`--nu-`-naamruimte onder een `.nu`-scope**: eigen bestand, eigen blok, geen
aliasing, geen botsing. Een scherm doet mee doordat `<body>` de klasse `nu` krijgt. De vier
botsende namen zijn nu `--nu-border`, `--nu-muted`, `--nu-neon`, `--nu-surface`.

## Wat er staat

| | |
|---|---|
| `static/nooch-ui.css` | 170 regels, alles onder `.nu` |
| `cockpit2._NU_ROUTES` | de 19 schermen, één lijst, route-gestuurd in `_send` |
| `web_base._status()` | vorm + woord; buiten `.nu` een gewone leesbare span |
| `tests/test_fase9_nooch_ui.py` | 12 tests |

Toegepast: 2px randen, radius 0, Archivo, zwart-op-wit knoppen met neon als primair, pill/chip/badge
één vorm, tabs, filters, invoervelden, de zijbalk, het bord, de wiki-index, de kanalenlijst en de
organisatieboom.

## Twee dingen die alleen de screenshots aan het licht brachten

1. **De vier bordkolommen droegen elk een pasteltint** (blauw/oranje/groen/grijs) — precies de
   kleur-alleen-status die dit systeem vervangt. Nu één rustige achtergrond en een merkteken per
   kolom, dezelfde vormen als `.nu-status`.
2. **Messages opende op een leeg kanaal.** Hij pakte simpelweg het eerste, en dat was de
   anchor-cirkel: je landde op "Nothing said here yet" terwijl er drie kanalen verderop wél
   gesprek stond. Nu opent hij op het eerste kanaal mét berichten.

Geen van beide was met een unit-test te vinden: de tests toetsen de broncode, de browser toetst de
pagina.

## Eindcheck

Playwright + Chromium, acht schermen × twee breedtes (1280×900 en 390×844) = 16 screenshots.
`body.nu` is `True` op alle zeven schermen in scope en `False` op `/claims` — de scopegrens doet
wat hij belooft. Screenshots staan in de scratchpad van de sessie, niet in de repo.

## Onaangeroerd gebleven

De 63 kleur-alleen-statussen buiten de 19 schermen (`kn-` 14, `ibx-` 6, `cl-` 5, `wz-` 5, `ck-` 3,
…) staan er nog, zoals besloten. Gelogd voor een eventuele latere fase.
