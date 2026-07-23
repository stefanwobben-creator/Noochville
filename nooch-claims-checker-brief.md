# CC-opdracht: Nooch Claims Checker op village.nooch.earth (tool van de compliance-rol)

**Voor:** Claude Code in de Noochville-repo. Het prototype en de databron staan al klaar in `scratch/claims-checker/`; dit is de landing op prod + de wiring in het dorp.

**Doel in één zin:** de EU claims-checker (EmpCo 2024/825 + ACM) draait op village.nooch.earth als tool van de compliance-rol, elke rol kan er tekst/URL's mee toetsen, bevindingen worden taken op het projectenbord, en de database heeft één bron van waarheid.

## Context (waarom dit bestaat)

Nooch.earth scoorde 28/100 in een externe EmpCo-scan (EcoClaim, juli 2026): 10 verboden claims ("100% Planet-Safe", "Zero Waste", "biodegradable"…), boete-exposure tot 4% jaaromzet vanaf 27-09-2026, en de ACM handhaaft nú al in de schoenensector. In plaats van €29-99/mnd voor EcoClaim te betalen bouwen we een eigen, afgeslankte variant, geïntegreerd in het dorp. Benchmark-nulmeting concurrenten (homepages, zelfde methode): MoEa 63, LØCI 75, Veja 78.

## Wat er al staat (in `scratch/claims-checker/`, nog niet gewired)

- `claims_database.json` — dé databron: 56 termen (patroon/stoplicht/categorie/waarom/alternatief, NL+EN+DE), werklijst van 20 site-fixes met status, landenregels NL/DE/BE, meta met scoringsformule en regelgevingskader.
- `claims_checker.html` — werkend prototype (één zelfstandig bestand): tekst- en URL-check, stoplicht + score, rol-routing per bevinding (copywriter/visual designer/marketeer/compliance), "Exporteer als taken"-knop, tabs voor werklijst/database/landen, en een admin-tab (client-side code, zie Taak 3). **De database zit hier nu als kopie ingebakken — dat is de eerste schuld die deze brief aflost.**

## Taak 0 — Diagnose/bevestig eerst

- Bevestig dat `claims_database.json` valide JSON is en dat alle 56 `patroon`-velden compileren als regex (case-insensitive).
- Bepaal en rapporteer vóór je bouwt: wordt de checker (a) een statische pagina geserveerd door cockpit2 achter de bestaande login, of (b) een native cockpit2-view. **Kies (a) voor deze landing** — het prototype staat vol inline styles en mag als zelfstandig statisch bestand NIET door de view-ratchets gaan, en niet als governeerde view gebouwd worden. Een native view is een latere scope; dan geldt het prototype als visuele referentie en is een pariteitstabel verplicht (CLAUDE.md).

## Taak 1 — Eén bron van waarheid (reference, don't copy)

- Verplaats `claims_database.json` naar `data/claims_database.json` (gitignored data? NEE — dit is curated content, geen runtime-state; overleg-loos alternatief: `config/claims_database.json`, naast `strategy.json`. Kies config en rapporteer).
- Cockpit2 serveert hem read-only op een route (bijv. `GET /claims/db.json`). `# AUTHZ: iedereen-ingelogd — naslagwerk, lezen is vrij (domein-regel: cureren is exclusief compliance)`.
- Pas het prototype aan: verwijder de ingebakken `DB`/`WORK`/`COUNTRIES`-data en laad ze bij het openen via `fetch("/claims/db.json")` (zelfde origin, geen CORS). De toets uit CLAUDE.md geldt: "als dit getal verandert, op hoeveel plekken pas ik het aan?" → één (de JSON).
- **Acceptatie:** een term wijzigen in de JSON en de pagina verversen toont de wijziging; er staat geen termenlijst meer hardcoded in de HTML.

## Taak 2 — Serveren op village.nooch.earth

- Zet de aangepaste checker als statisch bestand (bijv. `nooch_village/static/claims_checker.html`) en serveer hem via cockpit2 op `/claims` **achter de bestaande auth** (`auth.py`). Geen apart nginx-blok nodig; de reverse proxy staat er al.
- `# AUTHZ: iedereen-ingelogd — checken is voor alle rollen; muteren kan hier niet.`
- Deploy volgens het vaste protocol (INFRA.md): backup, git pull als user `nooch`, restart `noochville-cockpit2`.
- **Acceptatie:** ingelogd op village.nooch.earth/claims werkt de tekst-check; uitgelogd → login-redirect. De URL-check mag in v1 beperkt werken (CORS/proxy-afhankelijk); tekst-check is de kern.

## Taak 3 — Admin = compliance, via het echte auth-oppervlak

- Vervang de client-side admin-code (`ADMIN_CODE` in het prototype — rolscheiding, geen beveiliging) door de cockpit-sessie: de admin-functies (term toevoegen, werklijststatus wijzigen) worden `dispatch`-acties met `# AUTHZ: rolvervuller of Circle Lead — compliance-domein: alleen de domein-eigenaar cureert de claims-database`. Gebruik `_role_gate`; fail-closed.
- Schrijfacties muteren `config/claims_database.json` append-vriendelijk: term-toevoegingen en statuswijzigingen bumpen een `meta.versie` en loggen naar het bestaande audit-mechanisme (`system_log.jsonl`).
- **Acceptatie:** als compliance-rolvervuller (of founder) kan ik een term toevoegen en een werklijst-status op "live" zetten; als andere ingelogde rol krijg ik de leesweergave zonder schrijfknoppen; de wijziging overleeft een service-restart (staat in de JSON, niet in de browser).

## Taak 4 — De rol en de spanning (het dorp-native deel)

- **Rol:** er bestaat nog geen compliance-inwoner. Volg het normale pad: `add_role`-voorstel ("compliance", purpose: claims en regelgeving bewaken, domein: claims_database) via governance — geboren onbemand, accountabilities vallen aan de founder tot bemensing (CLAUDE.md rol-lifecycle). GEEN CLASS_MAP-entry in deze brief; activatie is mens-gated en een latere beslissing.
- **Skill:** maak `skills_impl/claims_check.py` — `ClaimsCheckSkill` (`claims_check`): payload `{"text": str}` of `{"terms": [str]}`, leest `config/claims_database.json` via context, geeft per match `{term, stoplicht, categorie, alternatief}` + score terug. Puur lokaal, geen netwerk, fail-closed bij ontbrekend/corrupt JSON-bestand. Registreer in `registry_factory.py`. Grant via governance aan de compliance-rol zodra die bestaat (tot die tijd: geen grant — de webtool gebruikt de skill-logica niet, die leest de JSON zelf).
- **Watcher (optioneel in deze landing, wel voorbereiden):** een wekelijkse zelf-scan van nooch.earth die bij een níeuwe rode/oranje term een `sense_tension(kind="operational")` afgeeft, past exact op het bestaande gap-sensing-patroon. Alleen bouwen als het in de bestaande puls-architectuur past zonder nieuwe threads; anders noteren als vervolg. NB: er draait extern al een interim-watcher via Claude (scheduled task "Nooch claims-watcher", maandags); zodra de dorp-native watcher leeft, melden zodat de externe wordt uitgezet.
- **Acceptatie:** het governance-voorstel staat in de records (source="sensed", ingediend door de mens), `claims_check` staat in de SkillRegistry, en `python -m pytest tests/` is groen.

## Guardrails

- Volle testsuite groen vóór commit (WORKING_AGREEMENTS); smoke tijdens het bouwen.
- `python -m nooch_village.arch_map` draaien en `docs/ARCHITECTUUR.md` mee-committen (nieuwe route + dispatch-acties!).
- Geen inline styles of nieuwe CSS-klassen in cockpit-views; het statische prototype valt buiten de views maar krijgt géén governeerde-view-status.
- Prod-data is levende state: gerichte edits, backups met `.bak.<ts>`, apply als user `nooch`, nooit root.
- Eén branch (bijv. `claims-checker`), geen vermenging met kennisbank-branches.
- De checker publiceert niets extern en roept geen externe API's aan (de URL-fetch in de browser is client-side en optioneel); de skill is puur lokaal.
- Bij twijfel over de juridische inhoud van de database: NIET zelf aanpassen — dat is compliance-domein (de mens), niet CC-domein.
