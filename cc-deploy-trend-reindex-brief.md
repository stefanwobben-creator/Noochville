# CC-opdracht: trend_reindex-skill deployen + granten aan Sid

**Voor:** Claude Code in de Noochville-repo. De skill-code is al geschreven en getest; dit is de deploy + de grant + het bepalen van de dagelijkse aanroep.

**Doel in één zin:** zorg dat Sid aan de slag kan — dat hij dagelijks uit zichzelf zijn projecten uitvoert én de trend-re-index draait. Niet netjes opsplitsen in losse PR's is prima; landing die Sid werkend krijgt gaat vóór.

## Wat er al staat (in de working tree, nog niet op prod)
- `nooch_village/skills_impl/trend_reindex.py` — de skill (Sid's dagelijkse trend-re-index). Pure helpers + injecteerbare `_fetch`/`reason_fn`, overal fail-closed. Getest: emergence/trend/blip-classificatie klopt, blip valt buiten de signalen, append-only watchlist + `trend_signals.jsonl`, curate-hand-off zonder levertiming-framing.
- `nooch_village/registry_factory.py` — import + `TrendReindexSkill()` toegevoegd aan `build_skill_registry()` (met backup `.bak.<ts>`). `build_skill_registry()` bevestigt registratie (37 skills).

Verifieer dat beide klopt, en zet het netjes op een aparte branch (`trend-reindex-skill`), los van de `kennisbank`-branches.

## Taak 0 — Diagnose/bevestig eerst
- Draai de bestaande testsuite plus een gerichte unit-test voor `trend_reindex` (pure helpers met een synthetische reeks + `run()` met een geïnjecteerde `_fetch` die een pandas-df teruggeeft; géén netwerk, géén LLM). Bevestig groen.
- Bevestig dat `pytrends` en `pandas` in de prod-venv van user `nooch` zitten (de skill importeert ze lazy; ontbreken → de skill escaleert fail-closed i.p.v. te crashen, maar dan draait hij nooit).
- Bevestig hoe een rugzak-skill dagelijks wordt aangeroepen in de draaiende `village run`: via een project-checklist-item dat `_plan_checklist` oppakt, of moet er een pulse-hook/standing project bij? Zie Taak 2.

## Taak 1 — Grant in Sid's rugzak (op prod, voorzichtig)
De skill bestaat pas voor Sid als `"trend_reindex"` in de `skills`-lijst van de Scientist-rol staat.
- **Prod-data is levende state.** Doe een GERICHTE veld-edit op prod's `data/governance_records.json`, geen git-overwrite: voeg `"trend_reindex"` toe aan `harry_hemp.definition.skills`, bump `harry_hemp.version` (+1). Maak eerst een backup (`.bak.<ts>`, zoals de bestaande backups daar).
- **Acceptatie:** Sid's rol toont `trend_reindex` in de rugzak; de andere skills en de versiehistorie blijven intact.

## Taak 2 — Dagelijkse autonome aanroep (het initiatief bij Sid)
Het raadsvoorstel eist: Sid pulseert dagelijks uit zichzelf, niemand hoeft te vragen. De skill in de rugzak is nog niet hetzelfde als "draait elke dag".
- Bepaal, gegeven de bestaande `inhabitant._tend_projects` / `_plan_checklist`-architectuur, de MINIMALE wiring voor een dagelijkse run op `dag_begint`: ofwel een staand/terugkerend project voor Sid met een checklist-item dat `trend_reindex` aanroept, ofwel een expliciete pulse-hook. Kies de weg die het dichtst bij de bestaande architectuur ligt; rapporteer je keuze vóór je bouwt.
- Idempotent per dag: één run per `dag_begint`, niet vier keer. **Doe dit samen met de tend-verbreding uit de `projecten-tend-escalatie`-brief** (queued + running-niet-af): één landing waarin Sid zowel zijn bestaande projecten als de trend-re-index in dezelfde dagpuls oppakt. Geen aparte PR's als dat de boel ophoudt.
- **Acceptatie:** na een `dag_begint`-puls verschijnt er een verse regel in `trend_signals.jsonl` en is de watchlist bijgewerkt, zonder dat een mens iets startte.

## Taak 3 — Escalatie zichtbaar (sluit aan op de andere brief)
- Als de skill `escalate` teruggeeft (LLM leverde geen kandidaten én lege watchlist, of pytrends niet beschikbaar), moet dat een ZICHTBAAR bericht aan de founder worden (@founding farmer), niet een stille regel. Gebruik hetzelfde zichtbare-escalatie-oppervlak uit de `projecten-tend-escalatie`-brief (heads-up met context, beslissen blijft op het geauthenticeerde human_inbox-oppervlak).
- **Acceptatie:** trek de stekker uit de LLM-ladder in een dry-run met lege watchlist → de founder krijgt een zichtbaar bericht, geen crash, geen 0%-stilte.

## Config (optioneel, alles heeft defaults)
In `config/settings.ini` desgewenst overriden; zonder config draait hij op de ankerset vegan/sustainable/plastic-free shoes, worldwide, `today 5-y`, factor 2.0, 3 complete maanden, cap 5:
`trend_reindex_anchors`, `trend_reindex_geo`, `trend_reindex_timeframe`, `trend_reindex_base_year`, `trend_reindex_max_candidates`, `trend_reindex_factor`, `trend_reindex_min_months`, `trend_reindex_emergence_floor`, `trend_reindex_keep`.

## Guardrails
- Applies op prod als user `nooch` (niet root — anders de 502-val), na backup, met dry-run vóór de echte run.
- Append-only overal; geen overschrijven van levende prod-data; gerichte veld-edits, geen git-clobber van `data/`.
- Eén branch (bijv. `sid-aan-de-slag`), volle testsuite groen vóór deploy. Combineren met de tend-verbreding mag; splits alleen als het écht schoner is.
- De skill is en blijft alleen-lezen naar buiten (haalt Trends-data op; publiceert/verstuurt/koopt niets). De enige schrijf-acties zijn de eigen append-only bestanden en de curate-hand-off.
