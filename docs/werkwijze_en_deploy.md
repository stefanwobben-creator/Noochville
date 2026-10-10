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

## Back-up (sinds 10 oktober 2026)
Tot die dag draaide er GEEN back-up: de stap hieronder werd niet uitgevoerd, en de losse `.bak`- en
`backups/`-kopieën staan op dezelfde schijf als de data. Nu:
- **Dagelijks naar Stefans Mac**: `scripts/backup_mac.sh` haalt `data/` binnen als dagsnapshot in
  `~/NoochVille-backups/<datum>/data` (hardlinks naar de vorige dag; 30 dagen bewaard). launchd draait
  hem om 07:15 (`scripts/launchd/nl.nooch.backup.plist`; een gemiste dag haalt hij in bij het wakker worden).
  launchd draait een vaste kopie van de scripts in `~/NoochVille-backups/bin/` (zie de kop van de plist),
  zodat de back-up niet afhangt van welke branch er in de repo uitgecheckt is.
- **Na elke run een herstel-toets** (`scripts/backup_herstel_toets.py`): alle JSON leesbaar en de
  stores te openen, op een kopie. Mislukt iets: een macOS-melding en een regel in `backup.log`.
- **Terugzetten**: `rsync -a ~/NoochVille-backups/<datum>/data/ root@138.201.154.162:/opt/noochville/data/`
  met de services gestopt, daarna `chown -R nooch:nooch /opt/noochville/data` en de services starten.
- Een nieuwe map onder `data/` (bijv. `data/finance/`) zit er automatisch in.
- **To-do (besluit Stefan, 10 oktober 2026: nu niet):** een aparte SSH-sleutel die alleen `data/` mag
  lezen (`authorized_keys` met `command="rrsync -ro /opt/noochville/data"`). Nu logt het script in als
  root met de gewone sleutel. Pas dit aan op de server zodra het aan de beurt is; het script hoeft dan
  alleen `NOOCH_SERVER` en de sleutel te kennen.

## Deploy-stappen (op de server, data blijft staan)
1. **Snapshot de data** (veiligheidsnet, met de hand vóór een migratie): `tar czf backups/data_$(date +%F_%H%M).tgz data/`.
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
