# i18n — de logica-laag naar Engels (apart project)

De UI-tekst (fase 1) is een veilige tekst-swap: alleen weergave, niets in de data. Dit document gaat
over de **logica-laag**: routes, action-namen, statuswaarden en dataveld-sleutels die nog Nederlands
(of gemengd) zijn. Die staan **opgeslagen in JSON én worden in code vergeleken**, dus hernoemen is een
datamigratie plus code-wijziging, geen tekst-swap. Dit is bewust een apart, riskanter project dan de
UI-vertaling, en het **blokkeert fase 1 niet**: de UI kan Engels worden terwijl deze waarden nog
Nederlands zijn — je ziet ze toch niet.

Observatie: de datalaag is al **half-Engels**. Projectstatussen kennen `future`, `running`, `blocked`,
`done` naast het Nederlandse `wacht`. Dit project maakt dus deels een half-af karwei af.

## Aanpak (per domein, nooit big-bang)

Voor elk domein:
1. Een migratiescript dat de opgeslagen waarden/sleutels in de JSON herschrijft (idempotent).
2. Een **compat-laag** die tijdens de overgang zowel de oude als de nieuwe waarde leest, zodat een
   half-gemigreerde dataset nooit stukloopt.
3. Pas daarna de code-vergelijkingen omzetten en de compat-laag verwijderen.

Volgorde op risico: **radar** (kleinste, meest geïsoleerde set) → **projecten** → **kennisbank**.
Draai elke migratie als `nooch` op de server, met een backup van het betreffende JSON-bestand vooraf.

## Tier 1 — opgeslagen statuswaarden (hoogste risico: data + logica)

Radar (`radar.json`, `radar_store._STATUSES`):

| nu | engels |
|-----|--------|
| wacht | waiting |
| goedgekeurd | approved |
| afgewezen | rejected |
| samengevoegd | merged |

Project (`projects.json`) — de nog-Nederlandse waarden, naast de al-Engelse (`future`/`running`/
`blocked`/`done`/`open`/`pending`/`queued`/`waiting`/`approved`/`rejected`):

`wacht`, `aangenomen`, `bevestigd`, `agendeerd`, `gelukt`, `gemonitord`, `genegeerd`, `geëscaleerd`,
`leeg`, `ongeldig` → kies consistente Engelse termen (bv. waiting, accepted, confirmed, scheduled,
succeeded, monitored, ignored, escalated, empty, invalid).

## Tier 2 — Nederlandse dataveld-sleutels in JSON (datamigratie van de bestanden)

| nu | engels |
|-----|--------|
| uitkomst | outcome |
| spanning | tension |
| bron | source |
| voorstel | proposal |
| reden | reason |
| inwoner | inhabitant |
| gemunt | minted |

(`scope`, `done_when`, `dod_outcome` zijn al Engels.)

## Tier 3 — action-dispatch-namen (HTML-formwaarde + server-sleutel als paar; ~41 stuks)

Gemengd Nederlands, o.a.: `proj_agendeer_verzwakt`, `proj_settrekker`, `radar_koppel`, `radar_merge`,
`kb_bron_add`, `rov_keep_role`, `rov_to_project`, `tac_project`, plus de rest van de
`proj_*`/`radar_*`/`kb_*`/`rov_*`-families. Contained: verander de HTML-`value` en de server-dispatch
tegelijk. Geen datamigratie, wel overal-tegelijk per naam.

## Tier 4 — routes / URL-paden (laagste risico: alleen links bijwerken)

`/inwoner`, `/inwoners`, `/kennisbank` (+ `/search`, `/spel`, `/spel/search`, `/staging`, `/tags`),
`/prikbord`, `/project/nieuw`, `/roloverleg`, `/roloverleg2`, `/wachtwoord`, `/werkoverleg`,
`/woordenschat`, `/rolefillers`. Werk de route én alle links/`href`/`data-href` bij; overweeg een
301-achtige redirect van oud → nieuw als er bookmarks bestaan.

## Niet vergeten

- De strategie-lexicon (`mission.STRATEGIE_THEMAS`) matcht op Nederlandse trefwoorden. Wordt de content
  Engels, dan moeten die termen mee (anders matcht de kennisbank-weging niets meer).
- De AI-prompts en de missie (`ANCHOR_PURPOSE`) zijn fase 2 (nieuwe output Engels), niet dit project.
