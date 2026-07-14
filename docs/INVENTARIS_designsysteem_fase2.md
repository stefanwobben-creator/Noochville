# Inventarisatie designsysteem — input voor de fase 2-vocabulairesessie

*Gegenereerd 2026-07-14 uit de broncode (views/*, cockpit2*, human_inbox, inbox). Doel: de
vocabulairesessie is een keuzemenu, geen archeologie. Cijfers: 417 klassen in de markup,
425 selectors in nooch.css, 58 prefix-families, 35 aantoonbaar dode selectors.*

## Hoe dit te lezen

Fase 1 (klaar) heeft de HTML-basis rechtgezet: CSS in `static/nooch.css`, `<main>`-landmark,
`_field()`-helper, focus-visible, drie nieuwe ratchets. Fase 2 is het vocabulaire: van 58
prefix-families naar een kleine set kern-atomen plus varianten. Dit document clustert wat er
nu is, zodat de sessie over besluiten gaat en niet over inventaris.

De kernvraag per cluster: **is dit een eigen component, of een variant van een bestaand atoom?**

---

## 1. Het kern-vocabulaire dat er al is (behouden en uitbouwen)

Deze klassen zijn al scherm-overstijgend en gedragen zich als echte atomen. Dit is de kandidaat-kern:

| Atoom | Huidige klassen | Gebruikt in |
|---|---|---|
| **Kaart** | `card` (+ `arch`), `acard-*` | vrijwel overal |
| **Knop** | `btn` + `ok` / `no` / `sm` / `ghost`, `dellink` | overal |
| **Chip/pill** | `chip`, `chip-opt`, `chip-wrap`, `pill`, `badge` | overal |
| **Filter/segment** | `cl-filter` + `on`, `cl-bar` | 6 schermen |
| **Tegel (KPI)** | `tile-*` (14 klassen) | metrics |
| **Formulier** | `qadd-form`, `editor`, `att-lbl`, `fieldform`, `pf` | 10+ schermen |
| **Toggle** | `switch` + `on`, `switch-field` | callbar, metrics |
| **Layout/chrome** | `c2-wrap`, `c2-main`, `c2-bar`, `c2-sec`, `c2-tabs`, `bar` | alle cockpit2-schermen |
| **Tekst-tonen** | `muted`, `ptitle`, `flash` (+ `err`) | overal |
| **Modal/overlay** | `js-modal`, `ovl-*`, `js-flip`/`js-flipback` | 5 schermen |

**Besluit dat hier hoort:** de dubbele `.chip` (web_base vs nooch.css) harmoniseren naar één
definitie. Binnen cockpit2 wint nu de nooch.css-variant (inline-flex, 700); legacy cockpit 1
gebruikt de web_base-variant. Voorstel: nooch.css-variant wordt dé chip, web_base-versie krijgt
dezelfde declaraties (cockpit 1 verandert dan mee, is prototype, acceptabel).

## 2. Scherm-families: variant of component?

Per familie de vraag: eigen component (houden, dan documenteren in UX_PATTERNS) of variant van
een kern-atoom (migreren, prefix verdwijnt). Voorzet:

| Familie | # | Schermen | Voorzet |
|---|---|---|---|
| `wo-*` | 30 | werkoverleg (+feed/projects/roloverleg) | Deels echt component (stap-nav, timer); `wo-grid`/`wo-head`/`wo-sec` zijn layout-varianten → kern |
| `kc-*` | 20 | metrics (KPI-composer) | Wizard-component; velden/knoppen erin → kern-atomen |
| `cl-*` | 18 | 6 schermen | `cl-filter`/`cl-bar` zijn al kern; rest checklist-component |
| `rov-*` + `rovm-*` | 24 | roloverleg, werkoverleg | Eén roloverleg-component; modal-deel (`rovm-*`) → generieke modal |
| `tile-*` | 14 | metrics | Houden als kern-atoom "tegel" (al gedocumenteerd) |
| `cat-*` | 13 | catalog | Grid/kaart/zoek-varianten → kern; weinig eigens |
| `kpi-*` | 12 | metrics | Overlapt met `tile-*` — samenvoegen tot één tegel-vocabulaire |
| `cb-*` | 12 | callbar | Eigen chrome (iframe-wereld), apart laten |
| `noo-*` | 12 | noochie-rail | Eigen chrome, apart laten |
| `rdr-*` | 11 | overview, signals | "Reader"-lijst → generieke lijst-kaart-variant |
| `ck-*` | 10 | checklists | Checklist-component, overlapt met `cl-*` → samenvoegen |
| `att-*`, `qadd-*`, `epic-*`, `ai-*`, `bar-*`, `einddoc-*`, `kb-*`, `admin-*`, `rrole-*` | ≤6 elk | divers | Bijna allemaal formulier-/lijst-varianten → kern; `epic-*` (aardbol) is bewust uniek |
| 20 micro-families (≤3 klassen) | ~50 | divers | De eigenlijke wildgroei: `bu-`, `vz-`, `gr-`, `is-`, `tb-`, `m-`, `emo-`, `sec-`, … → vrijwel allemaal opgaan in kern-atomen |
| zonder prefix | 108 | overal | Mengbak: kern-atomen (`card`, `btn`, `muted`) náást scherm-restjes (`fbubble`, `swim`, `pboard`) — per stuk toewijzen |

**Vuistregel voor de sessie:** een familie blijft alleen bestaan als hij (a) op meerdere plekken
als geheel wordt hergebruikt of (b) bewust een eigen wereld is (callbar, noochie, epic). Anders
is het een variant: `--modifier` op een kern-atoom.

## 3. Aantoonbaar dode selectors (35) — direct te schrappen

Komen als string nérgens in de broncode voor (ook niet dynamisch samengesteld of in legacy
cockpit.py; wel eerst even de bewuste check herhalen bij het schrappen):

`actioncards, actrow, ai-ask, att-x, card-del, chiplink, cmt, def-all, def-grp, def-pick,
def-rec, def-recs, def-share, desc-read, descedit, descform, detailsbox, editbox, fkind,
ghost-off, grey, here-highlight, imp-wrap, m-sel, m-selrow, nt-dot, nt-item, nt-list,
opdracht-add, pdetail-h, rov-block, rov-field, rov-fv, rov-kind, smeta`

Let op: een eerdere ruwere telling gaf ~70 kandidaten; de rest bleek dynamisch samengesteld
(bv. `ck-done`, `cl-attn` via f-strings) of door JS gezet. Alleen bovenstaande 35 zijn hard.

## 4. Tokens die nog ontbreken (fase 2-besluiten, klein werk)

1. **Breakpoints:** er zijn nu vier verschillende mobile-grenzen (560, 620, 680, 760 px).
   Voorstel: twee tokens (bv. `--bp-kaart: 640px`, `--bp-rail: 900px`) en alle media queries
   daarheen. Eén besluit, daarna ratchet-baar.
2. **Z-index-schaal:** huidige waarden 2, 5, 6, 7, 8, 9, 40, 45, 50, 70, 1000, 9998, 9999.
   Voorstel: vijf lagen (`--z-basis:1; --z-dropdown:10; --z-sticky:20; --z-modal:30;
   --z-overlay:40`) en klaar.
3. **Spacing:** veel losse rem-waarden (.3/.4/.55/.6/.7/.85/.9); een 4-stappen-schaal
   (`--sp-1` t/m `--sp-4`) vangt vrijwel alles.

## 5. Voorgestelde agenda voor de vocabulairesessie

1. Kern-atomen vaststellen (tabel 1): namen, varianten, wat is de canonieke vorm.
2. `.chip`-harmonisatie + `kpi-*`/`tile-*`-samenvoeging beslissen.
3. Per micro-familie (tabel 2, onderste rijen): variant-van-wat? (snel, hamerstukken)
4. Tokens: breakpoints, z-index, spacing (punt 4).
5. Ratchets aanscherpen: prefix-plafond omlaag bij elke migratie (staat al vast op 58),
   dode selectors schrappen = nooch.css kleiner, hash verandert, cache ververst vanzelf.

Daarna geldt fase 3: nieuw werk alleen in het vocabulaire; oude schermen gaan om wanneer je ze
toch aanraakt. De ratchets bewaken dat het nooit meer terugglijdt.

---

*Meetmethode: regex over class-attributen in de UI-bronbestanden + selector-parse van
nooch.css; dynamische klassen gecheckt via substring-zoek over de volledige broncode.
Hergenereer de ruwe data met de sessie-notitie van 2026-07-14 als referentie.*
