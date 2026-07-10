# Ontwerp — App-shell zodat de call-bar navigatie overleeft

Status: **Route A besloten** (dd 2026-07-10). Deze scope bouwt het **fundament**: de swap-primitive +
cleanup-contract + delegatie, met `wo_close` als eerste call-site. De globale **link-interceptor (1a)**
is een **aparte vervolgscope** zodra dit fundament gemerged is (zie "Buiten scope"). De inventaris-tabel
hieronder is de actuele waarheid.

**Buiten scope (komt later, 1a):** de globale `<a href>`-interceptor die álle navigatie door `shellSwap`
leidt. Dit fundament levert `shellSwap` + het contract; 1a hangt er alleen de interceptor voor.

## Waarom

De dorp-brede LiveKit call-bar draait sinds #172/#173 in een same-origin iframe (`/callbar`), geïnjecteerd
onder aan elke cockpit-pagina. Een iframe is een *child browsing context*: bij elke full-page
navigatie/reload wordt het parent-document — en dus de iframe — weggegooid en opnieuw opgebouwd. De
LiveKit-verbinding reconnect dan en valt terug naar toeschouwer. Dat treft twee dingen:

1. **`wo_close`** → `shut()` doet `location.reload()` (`projects.py`): het sluiten van een werkoverleg
   herlaadt de pagina.
2. **Elke echte `<a href>`-navigatie** (node, breadcrumb, rail): full-page load.

Doel: het document dat de iframe bezit wordt **nooit meer vervangen**. Aanpak: **client-side navigatie**
(pjax-stijl) die alleen het content-gebied (`.c2-main`) verwisselt; de chrome (noo-rail + callbar-iframe,
beide buiten `.c2-main`) blijft staan → de call loopt door.

## Kernidee (kleinste variant, geen serverwijziging)

De chrome wordt al **buiten** `.c2-main` geïnjecteerd (zie `overview.py:663` — `…{main}{rail}</div>{modal}`,
waarbij `main` de `.c2-main` is en de iframe via `_send` ná `</body>` komt). Als navigatie **alleen de
`.c2-main` verwisselt** i.p.v. het document te herladen, blijft de iframe leven. Dat kan client-side:
een globale interceptor fetcht de doel-URL, knipt `.c2-main` eruit en swapt alleen die in (+ `<title>` +
`pushState`). De verse chrome van de opgehaalde pagina (incl. z'n eigen iframe) wordt weggegooid.

## Welke pagina's shell-genoot worden / buiten blijven

| In de shell (swap `.c2-main`) | Buiten de shell (volledige navigatie, fallback) |
|---|---|
| Standaard cockpit-GET-pagina's mét `.c2-main`: `/`, `/node`, `/person`, `/project`, `/catalog`, `/admin`, `/werkoverleg` (full-page), `/aitask`, … | `/login`, `/logout` (auth-grens; daar loopt geen call) |
| | `/callbar` (iframe-body zelf — nooit een shell-doel) |
| | `/snake` (fullscreen, eigen layout) |
| | `/file`, `/static/*` (binaries), `/livekit-token`, `/action` (POST) |
| | Elke respons **zonder** `.c2-main` → fallback naar full nav |
| | Links met `target`, `download`, `#hash`, extern, of modifier-klik (cmd/ctrl/mid-click) |

De interceptor is **allowlist-op-gedrag**: alleen kale same-origin content-links; al het andere valt door
naar normale navigatie. Fail-safe: bij twijfel (geen `.c2-main` in de respons, fetch-fout) → `location.href`.

## Inventaris (punt 3): wat leeft er ín `.c2-main` en overleeft een swap NIET?

Verzameld read-only. Drie dimensies die de swap-veiligheid bepalen:

| Pagina (`.c2-main`) | Inline content-`<script>` | Timers / listeners die een swap overleven (→ lek/stapeling) | Pageview-tracking |
|---|---|---|---|
| **`/node`** (`overview.py`) | **Ja, zwaar**: `_projects_board` (kanban drag+click, **per-kaart bij init** gebonden) + `_epic_earth` | **`setInterval(5000)`** (aardbol-rotatie, `overview.py:183`) blijft draaien op losgekoppelde nodes; kanban-drag/click-bindings gaan verloren | geen |
| **`/person`** (`overview.py`) | Ja: `_projects_board` (kanban, per-kaart init-gebonden) | kanban-drag/click verloren bij swap | geen |
| **`/project`** (`projects.py`) | Ja: `scroll_js` (wall-scroll, `:941`) | eenmalige scroll bij load; geen persistente timer | geen |
| **`/catalog`, `/metrics`** | Ja (1–2 scripts) | te auditen vóór 1a | geen |
| Modal-machinerie (`_modal_html`) | n.v.t. — staat **buiten** `.c2-main` (`overview.py:663`) | `document`-brede click-binding voor `.js-modal/.pcard` (`projects.py:485-487`) + `keydown` (`:490`): overleeft de swap, **maar** bindt bij init elementen die ná een swap vervangen zijn → **stale links** | geen |

**Conclusie inventaris:** er is **geen** client-side pageview-tracking in de cockpit (Plausible is
server-side) — die dimensie is leeg, geen handmatig vuren nodig. De echte pijn zit in (a) de
**per-kaart init-binding** van kanban-drag/click én de modal-links, en (b) de **aardbol-`setInterval`**.
Beide leven in de zwaarste shell-genoot-pagina's (`/node`, `/person`). Daarmee is 1a **geen middag maar
eerder een week**, tenzij we de binding delegeren en een cleanup-contract invoeren (zie onder).

## Scroll- en focusgedrag na een swap (punt 4)

- **Nieuwe navigatie** (klik op een link, `pushState`): scroll naar `0,0` en zet focus op de nieuwe
  `.c2-main` (of de eerste `h1`) zodat toetsenbord/schermlezer meelopen. `document.title` bijwerken.
- **`popstate`** (back/forward): de scrollpositie **herstellen**. Bewaar per history-entry de scroll-offset
  (in `history.state` of een `Map` op `state.key`) en herstel 'm ná de swap. Geen focus-sprong bij
  back/forward (de gebruiker had z'n plek al).
- **Bij een swap altijd** `history.scrollRestoration = 'manual'` zetten zodat de browser niet óók nog
  eigen scroll-herstel doet (dubbel/verkeerd).

## Cleanup-contract voor content-pagina's (punt 4)

Een `.c2-main` mag alleen "shell-veilig" zijn als hij zijn eigen timers/listeners opruimt bij een swap.
Contract:

- **Registratie:** een content-script dat een timer/interval start of een listener op `document`/`window`/
  `body` hangt, registreert een teardown via een gedeelde hook, bv. `window.__shellCleanup.push(fn)`.
- **Teardown:** de shell roept vóór elke swap alle `__shellCleanup`-fns aan en leegt de lijst
  (`clearInterval`, `removeEventListener`). Zo lekt de aardbol-`setInterval` niet en stapelen listeners niet.
- **Re-init:** ná de swap draait de shell de init opnieuw. Twee opties, per pagina te kiezen:
  1. **Delegatie** (voorkeur voor klik/drag): vervang per-element-binding door één gedelegeerde
     `document`-listener die `e.target.closest('.js-modal,.pcard')` afhandelt. Overleeft elke swap
     zonder re-init. Dit is de duurzame fix voor `projects.py:485-487`.
  2. **Her-eval**: extraheer de `<script>`-tags uit de verse `.c2-main` en voer ze opnieuw uit (nieuwe
     `script`-elementen). Nodig voor scripts die niet te delegeren zijn (bv. de aardbol-animatie). Combineer
     met het cleanup-contract, anders stapelt de `setInterval`.

Regel: **een nieuwe of aangeraakte content-pagina die een timer/`document`-listener opzet, MOET een
`__shellCleanup`-teardown registreren.** Guard-test mogelijk (grep op `setInterval(`/`addEventListener('` in
views zonder bijbehorende cleanup-registratie).

## Wat er met de `wo_close`-reload gebeurt — en waarom 1b niet triviaal is

`shut()` (`projects.py:422`) doet nu `location.reload()` bij een dirty-close. De bedoeling was: 1b vervangt
alleen díe regel door een shell-reload (fetch huidige URL, swap `.c2-main`). **Maar** de wo_close-context is
de **node-pagina**, en dat is precies de zwaarste `.c2-main` (kanban met per-kaart-binding + de
aardbol-`setInterval` + de modal-links die bij init gebonden zijn). Een naïeve swap dáár:

- laat de oude aardbol-`setInterval` doordraaien op losgekoppelde nodes (lek),
- verliest de kanban-drag/click-bindings (dood bord),
- verliest de top-level `.js-modal`-bindings (dode links).

**Daarom is 1b niet los te koppelen van het cleanup-contract + de re-init.** Het is in feite "de
swap-primitive toegepast op één trigger (wo_close)". Twee eerlijke routes:

- **Route A (aanbevolen): bouw eerst de swap-primitive mét cleanup-contract + delegatie** (klein, algemeen),
  dan is `wo_close` een one-liner die 'm aanroept, én is de basis voor 1a gelegd.
- **Route B (chirurgische 1b): swap NIET de hele `.c2-main`**, maar ververs na `wo_close` alleen het
  werkoverleg-CTA/-statusblok op de node (een specifiek element met een stabiele selector). Raakt geen
  scripts/timers, maar is fragiel (je moet exact weten wélke stukken stale worden — CTA + evt. de
  tevredenheids-tegel) en dekt alleen wo_close, niet navigatie.

## Kleinste eerste stap die de acceptatietest haalt

Gegeven de inventaris is de kleinste **robuuste** stap **Route A**:

1. Swap-primitive `shellSwap(url, {push})`: fetch → parse → **teardown (`__shellCleanup`)** → `.c2-main`
   vervangen → `<title>` → scroll/focus → re-init (delegatie waar mogelijk, anders her-eval).
2. Delegeer `projects.py:485-487` (klik op `.js-modal/.pcard`) naar één `document`-listener → swap-veilig,
   geen re-init nodig voor links.
3. Registreer de aardbol-`setInterval` in `__shellCleanup`.
4. Globale link-interceptor (allowlist) → `shellSwap`. `popstate` → `shellSwap` + scroll-herstel.
5. `wo_close`: `location.reload()` → `shellSwap(location.href)`.

Feature-flagbaar (één `if` bovenaan de interceptor) zodat je 'm direct kunt uitzetten.

## Risico's / blast radius per stap

| Stap | Blast radius | Grootste risico | Mitigatie |
|---|---|---|---|
| 1. Swap-primitive + cleanup-contract | Middel (nieuwe infra, geen bestaande call-sites) | Onvolledige teardown → lek/stapeling | Cleanup-contract + guard-test; begin met de bekende gevallen (aardbol-interval) |
| 2. Delegatie van `.js-modal/.pcard`-klik | Middel (raakt de bord-modal-JS, de zwaarste) | Regressie op drag-vs-klik (`__pdrag`-guard) en de werkoverleg-`back`-logica (`:480-483`) | 1-op-1 gedrag overnemen in de delegatie; bestaande drag-drop-tests groen houden |
| 3. Aardbol-`setInterval` → cleanup | Laag | Vergeten interval blijft draaien | Registreren + teardown-test |
| 4. Link-interceptor (globaal) | **Hoog** (vangt álle `<a>`-clicks) | Verkeerde link gekaapt (download/extern/hash/target) of script-afhankelijke pagina niet ge-re-init | Strikte allowlist + fallback `location.href`; feature-flag; per-pagina audit (metrics/catalog) |
| 5. `wo_close` → `shellSwap` | Laag (één functie) | Node toont stale meeting-status na close | Volledige node-URL her-fetchen; verifiëren na close |
| (later) Form-redirects door de shell | Middel | POST→303 die nog full-load't | Redirect-doel fetchen + swappen; of accepteren dat losse full-page-forms nog reloaden |
| (later) `?shell=1` server-content-only | Middel-hoog | Inconsistentie full vs. fragment | Per view; guard-test dat beide dezelfde content geven |

**Samengevat:** de acceptatietest ("call overleeft navigatie én wo_close") is haalbaar, maar de kleinste
robuuste stap is de swap-primitive mét cleanup-contract + delegatie — niet een losse one-line-fix op
`wo_close`. De inventaris wijst de node-/person-pagina's (kanban + aardbol-interval) als het zwaartepunt aan.
