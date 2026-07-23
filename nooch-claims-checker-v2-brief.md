# CC-opdracht: Claims Checker v2 — dorpslid-gereedschap (native view, rol-ontsluiting, taakkoppeling, wekelijkse check)

**Voor:** Claude Code in de Noochville-repo. Bouwt voort op de eerste landing (`/claims` statisch achter auth, `config/claims_database.json` via `claims_db.py`, `_role_gate("compliance")`, compliance-rol v4 met `claims_check`). Die landing was v1; deze brief maakt er een volwaardig onderdeel van het dorp van.

**Doel in één zin:** de claims-checker ziet eruit als de rest van de village, is vindbaar bij de tools van de compliance-rol, zet bevindingen als taken bij de juiste rollen op het bord, en compliance checkt de site wekelijks zelf via haar eigen checklist — de website-rol nadrukkelijk niet.

## Taak 0 — Diagnose eerst (de URL-check-bug)

De URL-check in het prototype fetcht client-side via publieke CORS-proxies (allorigins/corsproxy). Dat faalt in de praktijk (geblokkeerd/onbetrouwbaar) terwijl andere dorp-tools dezelfde URL's prima pakken — die fetchen server-side. Bevestig deze diagnose (probeer de bestaande /claims URL-check één keer en noteer wat er misgaat), rapporteer kort, en fix hem in Taak 3 door de fetch naar de server te verplaatsen. Geen work-arounds met andere publieke proxies.

## Taak 1 — Native view in het design system

- Herbouw de checker als governeerde cockpit2-view (`views/claims.py` of conform bestaande indeling), met `nooch.css`-klassen en de `_field()`-helpers. **Geen inline styles, geen nieuwe CSS-klassen zonder ratchet-bump** — de UI-ratchets gelden nu wél volledig.
- Het statische prototype (`scratch/claims-checker/claims_checker.html` / huidige `/claims`) is de **visuele referentie**: maak de verplichte pariteitstabel (element voor element: score-balk, stoplicht-flags met rol-badge, gemarkeerde tekst-preview, werklijst met status, database-browser met zoekveld, landenfilter NL/DE/BE, taken-export). Waar het design system een ander patroon afdwingt dan het prototype: volg het design system en noteer de afwijking in de tabel.
- De oude statische route vervalt zodra de view live is (redirect /claims → de view; geen twee oppervlakken).
- **Acceptatie:** /claims toont de checker in village-stijl; pariteitstabel in de PR; inline-style-teller en CSS-ratchets ongewijzigd of verantwoord gebumpt; alle v1-functionaliteit (check, score, werklijst, database, landen, admin-curatie via `_role_gate("compliance")`) werkt in de nieuwe view.

## Taak 2 — Ontsluiting bij de compliance-rol

- De tool moet vindbaar zijn waar de rollen hun gereedschap vinden: op de rol-detailpagina van compliance (en alleen daar) een "Gereedschap"-blok met de claims-checker (link naar /claims, één regel uitleg, laatste scan-datum als die bestaat).
- Volg het bestaande patroon voor rol → skills/rugzak-weergave; geen nieuw concept introduceren als er al een plek is waar een rol-tools-lijst leeft.
- **Website-rol expliciet NIET:** de wekelijkse site-check en het cureren horen bij compliance. Als de website-rol ergens een claims-accountability heeft of via lopende voorstellen dreigt te krijgen: niets aan toevoegen; noteer het alleen in de PR-beschrijving als het speelt.
- **Acceptatie:** op de compliance-rolpagina staat de checker als gereedschap; op andere rolpagina's niet.

## Taak 3 — Server-side URL-scan + voortgang

- Nieuw endpoint (bijv. `POST /claims/scan_url`): haalt de pagina server-side op (requests, nette timeout ~15s, User-Agent, alleen http/https, max response-size), stript naar tekst (title + meta description + body), scant met dezelfde logica als de tekst-check en geeft hetzelfde bevindingen-payload terug. `# AUTHZ: iedereen-ingelogd — lezen/scannen is vrij; muteren blijft compliance.`
- **SSRF-guardrail:** weiger niet-http(s)-schema's en resolves naar privé-/loopback-ranges (127.0.0.0/8, 10/8, 172.16/12, 192.168/16, 169.254/16, ::1) — de server staat in een datacenter en mag geen interne adressen scannen.
- **Voortgang in de UI:** na klik op "Haal op & check" direct een voortgangsindicator in design-system-stijl (bezig-status met fasen "ophalen → scannen → rapport", of het bestaande spinner/progress-patroon van de village als dat er is — hergebruik dan dat). Knop disabled tijdens de run, nette foutmelding bij timeout/weigering met het advies "plak de tekst handmatig".
- De client-side proxy-code verdwijnt volledig.
- **Acceptatie:** een check van https://nooch.earth/ vanaf /claims levert bevindingen op; tijdens de run is voortgang zichtbaar; een interne URL (bijv. http://127.0.0.1:8766) wordt geweigerd met duidelijke melding.

## Taak 4 — Output gekoppeld aan de andere rollen (taken op het bord)

- Vervang/breid de klembord-export uit: knop "Zet op het bord" bij een scan-resultaat maakt per rode/oranje bevinding een taak via het bestáánde projecten/taken-mechanisme (projects.py / checklists), toegewezen aan de juiste rol volgens de rol-routing die al in de bevindingen zit (copywriter = tekstclaims, visual designer = labels/badges/visuals, marketeer = vergelijkingen/statistieken, compliance = sociaal/labels-conflicten). Taakinhoud: claim + locatie + stoplicht + veilige herformulering + nacheck "tov + legal".
- **Dedupe is de kern:** geen nieuwe taak als er al een open taak of werklijst-item voor dezelfde claim bestaat (match op werklijst-nr of genormaliseerde claim-tekst). Anders spamt elke scan het bord vol.
- `# AUTHZ: rolvervuller of Circle Lead — compliance zet bevindingen om in werk; andere rollen zien de knop niet.`
- De klembord-export mag blijven als secundaire optie (voor extern gebruik).
- **Acceptatie:** één scan met bekende bevindingen → 0 nieuwe taken (alles al in de werklijst); een scan met een gefingeerde nieuwe rode term → precies één taak bij de juiste rol, zichtbaar op het bord, met de herformulering erin.

## Taak 5 — Wekelijkse check als terugkerende taak van compliance

- Compliance checkt de site wekelijks zelf. Bouw dit dorp-native volgens het patroon van Sid's `trend_reindex` (staand/terugkerend project met checklist-item dat een skill aanroept in de puls; idempotent per periode — hier per week, niet per dag).
- Nieuwe skill `skills_impl/claims_site_scan.py` (`claims_site_scan`): pure helpers + injecteerbare `_fetch` (zoals trend_reindex), scant de vaste pagina-set (home, FAQ, mission, made_on_demand, één productpagina) tegen `claims_db`, vergelijkt met werklijst + open taken, en levert alleen NIEUWE bevindingen op. Fail-closed: site onbereikbaar of JSON corrupt → escalatie, geen crash, geen stille 0. NB: `claims_check` heeft een test die netwerk-imports verbiedt — die skill blijft puur; de fetch hoort alleen in `claims_site_scan`.
- Uitkomst van een run: nieuwe bevindingen → taken via het Taak 4-mechanisme + een zichtbare heads-up aan de founder bij rode bevindingen; niets nieuws → één stille logregel, geen bord-ruis.
- Grant `claims_site_scan` aan de compliance-rol via een gerichte governance-edit op prod (patroon uit de trend_reindex-brief: backup, veld-edit, versie-bump → v5).
- **Meld in de PR-beschrijving expliciet dat de dorp-native watcher leeft** — dan wordt de externe interim-watcher (Claude scheduled task, maandags) uitgezet door de founder.
- **Acceptatie:** na een weekpuls staat er een scan-regel in de log; een tweede puls in dezelfde week scant niet opnieuw; een dry-run met een geïnjecteerde `_fetch` die een nieuwe verboden term teruggeeft produceert precies één taak + heads-up.

## Taak 6 — Bronvalidatie toepassen (zwart-wit-principe)

- In `scratch/claims-checker/claims_database.json` staat v2 van de database (meta.versie `2026-07-18.2`): elke term heeft nu `bron` (A = EU-wet geverifieerd op EUR-Lex, B = ACM Leidraad, C = interpretatie, D = Nooch-beleid), `bron_detail` en `hardheid` (`hard`/`escaleren`). Zes C-termen hebben `stoplicht: "escaleren"` (advies bewaard in `stoplicht_advies`). Ook nieuw: `meta.toetsingskader` met het principe en de geverifieerde bronnen.
- Pas dit toe op `config/claims_database.json` volgens de claims_db.py-conventies: backup `.bak.<ts>`, gerichte merge (bewaar admin-edits die er sinds de landing bij zijn gekomen), versie-bump.
- UI: "escaleren" is een eigen status naast rood/oranje/groen — duidelijk label ("⚖ mens beslist — compliance"), en toon per bevinding de bron-badge (A/B/C/D) met `bron_detail` als tooltip/uitklap. Bij taak-aanmaak (Taak 4): escaleren-bevindingen worden ALTIJD een taak voor compliance, nooit voor een andere rol.
- Het principe is beleid: de tool oordeelt alleen waar wet (A), toezichthouder (B) of Nooch-beleid (D) hard is; interpretatie (C) gaat naar de mens.
- **Acceptatie:** een scan met "schoon" of het PETA-logo in de tekst geeft status "escaleren → compliance" en telt niet mee als rood/oranje in de score; een scan met "milieuvriendelijk" toont bron A met het recital-9-citaat in de detail.

## Guardrails

- Volle testsuite groen vóór commit; `python -m nooch_village.arch_map` + `docs/ARCHITECTUUR.md` mee-committen (nieuwe view, endpoints, skill, dispatch-acties).
- Eén branch (`claims-checker-v2`), **schone working tree bij de start** — geen herhaling van de woordenschat-vermenging uit v1; check `git status` vóór je begint.
- Prod-data is levende state: gerichte veld-edits met `.bak.<ts>`-backup, apply als user `nooch`, nooit root. En check na deploy de eigenaar van `config/claims_database.json` (nooch:nooch) — bekende val uit v1; neem de `chown` op in het deploy-protocol zodat dit geen geheugenwerk meer is.
- Juridische inhoud van de database niet aanpassen; dat is compliance-domein (mens).
- De scan publiceert niets extern; alleen GET's naar de eigen site (en de SSRF-guardrail uit Taak 3 geldt overal waar server-side gefetcht wordt).
- Bij conflict tussen prototype-look en design system wint het design system; bij conflict tussen deze brief en CLAUDE.md wint CLAUDE.md — noteer het en bouw verder.
