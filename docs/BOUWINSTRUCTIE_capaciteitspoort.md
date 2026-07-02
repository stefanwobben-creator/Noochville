# Bouwinstructie — capaciteitspoort "requires_skill → spanning"

Voor een Claude-sessie die dit morgen productie-klaar maakt en deployt. Lees eerst
`CLAUDE.md` (harde regels, met name 5, 10 en 11: geboren-versus-bemenst). Werk in
`/Users/stefanwobben/noochville`.

## Doel (één zin)
Als een rol een project oppakt waarvoor hij een skill mist, rondt hij het niet stil af
maar blokkeert hij het en senst "ik heb skill X nodig" naar de mens; declareerbaar via een
UI-veld op de projectkaart.

## Protocol (strikt volgen)
- Python: gebruik `./venv/bin/python` (3.14). De sandbox/CI-Linux is 3.10 en mist `StrEnum`
  en `typing.Self`, dus tests draaien alleen lokaal op de Mac.
- Klein en toetsbaar: één brok tegelijk, branch per brok, pas mergen als de suite groen is.
- Tests: `./venv/bin/python -m pytest -q` (volledig) en gericht
  `./venv/bin/python -m pytest tests/test_project_handling.py -q`.
- Git-workflow: commit klein per brok, daarna pushen. Geen secrets committen
  (`.env`, `config/settings.ini`, `client_secret*`, `*token*.json` blijven gitignored).
- Reference, don't copy: geen waarde hardcoden die elders thuishoort.
- De rol mag NOOIT zelf een skill bouwen, registreren of een thread starten. De poort
  meldt alleen een gat; activatie blijft mens-gated.

## Huidige staat (prototype, NOG NIET gecommit)
Deze wijzigingen staan in de working tree naast een eerdere, losse niet-gecommitte
cockpit2-cosmetische sweep. Eerst die twee uit elkaar halen (brok 0).

- `nooch_village/inhabitant.py`
  - nieuw: `_missing_required_skill(project)` — naam van een gedeclareerde `scope.requires_skill`
    die ontbreekt in registry OF DNA, anders None. Fail-closed: alleen een expliciet veld telt.
  - guard in `_claim_run_complete`: bij een ontbrekende vereiste skill → `ledger.block(pid, self.id)`
    + `_report_means_gap("skill:<naam>", "<uitleg>")` en `return` (geen `stub:done` meer).
- `nooch_village/cockpit2.py`
  - `proj_add`-dispatch leest `g("requires_skill")`; bij invulling wordt de scope een dict
    `{"text": <titel>, "requires_skill": <skill>}`, anders blijft het een string (backward-compat).
- `nooch_village/views/projects.py`
  - veld "Vereiste skill (optioneel)" in `_quickadd` én `_inline_add_project`.
  - nieuw `_scope_str(scope)` (dedup van 4 inline joins): toont "titel · vereist: <skill>";
    generieke dicts vallen terug op `key: value`. `_scope_text` roept `_scope_str` aan.
- `tests/test_project_handling.py`
  - 3 tests: block+sense bij ontbrekende skill, normaal draaien bij aanwezige skill,
    normaal draaien zonder `requires_skill`. Import van `Skill` toegevoegd.

Geverifieerd (onder een StrEnum/Self-shim, want sandbox = 3.10): dispatch-vorm, guard en
weergave kloppen. Volledige suite moet nog lokaal op 3.14 groen bevestigd worden.

## Brokken (elk een branch, elk toetsbaar)

### Brok 0 — repo-hygiëne
`git status` en `git diff` bekijken. De capaciteitspoort-wijziging (inhabitant.py,
tests, plus de requires_skill-delen van cockpit2.py/views) scheiden van de eerdere
cosmetische cockpit2-sweep. Per hunk beslissen; twee losse, nette commits. Geen secrets.

### Brok 1 — capaciteitspoort hardenen
Guard reviewen op edge-cases: string-scope blijft werken; rommelige `requires_skill`
(spaties, hoofdletters, lege string na strip); project al `done`; owner-mismatch.
`tests/test_project_handling.py` groen + volledige suite groen.

### Brok 2 — UI afronden
Veld in beide forms; a11y (label + aria-label) checken. Beslissen wat er met
`requires_skill` gebeurt bij `proj_edit`/`proj_rename`: nu gaat het veld verloren als je de
titel wijzigt (scope wordt weer een string). Kiezen: behouden of bewust laten vervallen,
en dat gedrag testen.

OPGELOST vandaag (geen bug): "project toevoegen lukt niet" kwam doordat de "+ project"-form
alleen rendert met een csrf-token, en dat token is er alleen als je bent INGELOGD. `/node` is
publiek, dus je ziet de pagina wel maar zonder schrijfknoppen. Sessies zitten in het geheugen
van het serverproces en zijn dus weg na elke herstart, waardoor je opnieuw moet inloggen via
`/login` (people.json moet een `email` + `password_hash` hebben; zie `auth.py`).
Voor snel demo'en zonder telkens inloggen: overweeg een expliciete dev-flag (bijv.
`--no-auth`) die `sessions=None` doorgeeft aan `make_handler`, want dan geeft
`_session_username()` "guest" terug en mag alles (guest = auth uit). Bouw die flag netjes en
alleen voor lokaal gebruik.

### Brok 3 — means-gap → inbox end-to-end
`./venv/bin/python -m nooch_village.village once` tegen `data/` draaien nadat een kaart met
`requires_skill=site_content` op `website_watcher` staat (status queued = kolom Actief).
Verwacht: project → `blocked`; `_on_means_gap` classificeert (verwacht uitkomst B) en zet een
means-gap in de human inbox. Controleren via `./venv/bin/python -m nooch_village.inbox`.
Cockpit en village moeten dezelfde `data/` gebruiken (beide default, geen `--data-dir`).

### Brok 4 (volgende fase, optioneel) — de echte skill `site_content`
Bouwen volgens `tech_spec_site_content.md` (v1 = structureel + strategisch; ToV = v3).
Aparte brokken: sitemap-crawler + index, structurele signalen, strategische signalen
(leunt op Lara's lexicon), registratie + capability via governance aan `website_watcher`.
Pas dan verdwijnt de means-gap vanzelf, want de skill bestaat dan.

### Brok 4b — AI-inwoner als rolvervuller toevoegen (UI-gat, prototype al gedaan)
Model en dispatch steunden dit al: `assignments.py` kent `person` én `persona`; `role_assign`
(`cockpit2.py` ~686) doet `assign(role, "persona", agent)` bij een `persona:<id>`-filler; AI-
vervullers worden ook al in de modal getoond. Het gat zat alleen in de keuzelijst van
`render_rolefillers` (`views/overview.py` ~566), die enkel `person:<id>` aanbood. Prototype-fix
staat er: personas worden nu ook als `persona:<id>`-optie aangeboden ("… (AI)").
Morgen: verifiëren met een test (bijv. `tests/` voor overview/assign — assert dat de optie
`persona:` in de modal-HTML zit en dat `role_assign` een persona koppelt), en de outdated
aanname "AI koppel je per accountability" checken tegen `governance.set_persona`
(record-koppeling) versus `assign`. Beslissen of beide paden naast elkaar mogen of dat er één
bron van waarheid moet zijn voor "welke AI vervult deze rol".

### Brok 5 — afronden
`STATE.md`/journal bijwerken, docs kloppend maken, commits pushen, deployen.

## Definition of done
- Volledige `pytest` groen op de 3.14-venv.
- Guard + UI + inbox-lus end-to-end handmatig geverifieerd via `village once`.
- Kleine commits per brok, gepusht; geen onbedoelde bestanden of secrets.

## Valkuilen
- Twee cockpit-instanties: een oude server op poort 8766 toont oude code. Kill met
  `lsof -ti :8766 | xargs kill -9`, check dat de poort vrij is, herstart, hard verversen.
- De cockpit toont alleen; het oppakken doet de draaiende village. Zonder puls verandert
  er niets aan de kaart.
- Harde grens: de rol vraagt om de skill, hij bouwt hem nooit zelf.
