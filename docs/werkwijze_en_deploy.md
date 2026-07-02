# Werkwijze en deploy-protocol

Hoe we van idee naar draaiende functionaliteit gaan zonder serverdata te overschrijven.

## Onze werkwijze (vaste volgorde)
1. **HTML-prototype eerst** (bijna altijd). Klikbaar, standalone, om het ontwerp te zien en te
   ijken vóór er code is. Goedkoop om weg te gooien, snel om op te schuiven.
2. **Ontwerpnotitie.** Leg de vastgestelde keuzes vast (wat, waarom, datamodel, UI-beslissingen),
   zodat de bouw eenduidig is. Zie bijv. `ontwerpnotitie_doelen.md`.
3. **Bouwen, lokaal en klein.** Branch per brok, klein en toetsbaar, tests groen vóór merge
   (protocol uit `CLAUDE.md`). Python via `./venv/bin/python` (3.14).
4. **Lokaal draaien.** Jij test lokaal en loopt vóór op de server; pas als het lokaal af en
   getoetst is, gaat het naar productie.
5. **Deploy** volgens het protocol hieronder.

## Grondprincipe: code en data strikt gescheiden
- **Code** leeft in Git (versioned, tags). Deployen = code bijwerken.
- **Data** leeft in `data/` op de server (`governance_records.json`, `projects.json`, straks
  `objectives.json`, enz.). `data/` staat in `.gitignore` en gaat **nooit** in Git. Een `git pull`
  raakt de serverdata dus niet. Dit is de kern van "niet overschrijven".
- Secrets (`.env`, `config/settings.ini`, `client_secret*`, `*token*.json`) blijven gitignored.

## Nieuwe functionaliteit = additief
- **Nieuwe store maakt zijn eigen bestand aan als het ontbreekt** en laat een bestaand bestand
  ongemoeid (zoals `ProjectLedger`/`DefinitionStore` nu al doen). Een lege `objectives.json` wordt
  bij de eerste start aangemaakt; bestaande data blijft.
- **Migraties zijn idempotent en additief**, nooit destructief (zoals `migrate_records()`).
  Een bestaand project krijgt hooguit een nieuw **optioneel** veld (default leeg: `doel_id=None`,
  `gerealiseerde_uren=0`). Geen kolom verwijderen, geen record herschrijven.
- **Gericht lanceren:** nieuwe functionaliteit is een nieuwe knop/route die bestaand gedrag niet
  verandert tot ze gebruikt wordt. Twijfel je of iets al aan mag? Zet het achter een simpele
  vlag in `settings.ini` (bijv. `feature_doelen = aan`) en zet 'm pas aan als je klaar bent.

## Deploy-stappen (op de server, data blijft staan)
1. **Snapshot de data** (veiligheidsnet): `tar czf backups/data_$(date +%F_%H%M).tgz data/`.
2. **Code bijwerken:** `git fetch && git checkout <tag-of-main>` (alleen code; `data/` wordt niet geraakt).
3. **Additieve migratie** draaien indien nodig (idempotent; veilig om twee keer te draaien).
4. **Herstart** cockpit/village.
5. **Smoke-test:** open het bord, controleer dat bestaande projecten en records er nog zijn en
   dat de nieuwe knop werkt. Pas dan klaar.

## Rollback
Ging er iets mis: `git checkout <vorige-tag>` (code terug) en zo nodig de data-snapshot
terugzetten (`tar xzf backups/<snapshot>.tgz`). Omdat migraties additief zijn, is terugrollen van
code meestal genoeg; de data blijft geldig.

## Lokaal vóórlopen zonder de prod-data te raken
- Ontwikkel tegen je **lokale** `data/`, of tegen een **kopie** van de prod-data. Het dorp heeft
  hiervoor al `once_sandbox()` (draait tegen een wegwerp-kopie van `data/`); voor de cockpit start
  je lokaal met een eigen of gekopieerde data-map.
- Nooit de live `data/` als speeltuin gebruiken; alleen lezen voor analyse is prima.

## Nooit doen
- `data/` committen of overschrijven bij een deploy.
- Een destructieve of niet-idempotente migratie draaien.
- Force-pushen naar de remote.
- Secrets committen.
