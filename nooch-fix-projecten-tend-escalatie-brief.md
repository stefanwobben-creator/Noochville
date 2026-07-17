# Fix-brief: Sid's projecten lopen niet — tend verbreden + zichtbaar escaleren

**Context (geverifieerd in de code):** op `dag_begint` (1x per dag, 04:32 Madrid, via TimeKeeper in de draaiende `village run`-service) tendt een rol z'n projecten: `inhabitant._tend_projects` → `prepare_project` → `_plan_checklist` (items met een skill-referentie uit het rugzakje) → `_execute_checklist` / `use_skill` → deliverable, en bij een ontbrekende/falende skill een `add_means_gap` naar de `human_inbox`. Sid's ~18 projecten staan op 0%.

**Gewenst gedrag (van de founder):**
1. 1x per dag is goed (cadans niet aanpassen).
2. De tend moet niet alleen `queued` projecten oppakken, maar ook actieve (`running`) projecten die nog niet af zijn.
3. Als een rol vastloopt, moet er echt een zichtbaar bericht naar de founder komen. Dat gebeurt nu niet.

## Taak 0 — Diagnose eerst (bevestig de oorzaak op de box, bouw daarna)
Rapporteer:
- de echte status van Sid's projecten (`data/projects.json`): queued / future / running / blocked / done.
- of de dagpuls vuurt: `data/timekeeper_last_day.json` + de service-log rond 04:32.
- of er `means_gap`-items voor Sid in `data/human_inbox.json` staan (stille escalaties).
- of Sid's persona-rugzakje de skills bevat (openalex, epo_patents/google_patents, ngram, semscholar) én of die in de `SkillRegistry` geregistreerd zijn.
- of `prepare_project` uitvoerbare checklist-items oplevert of alleen "geen skill"-items.

Dit onderscheidt de drie mogelijke oorzaken: (a) niet-queued dus nooit getend, (b) leeg/ongeregistreerd rugzakje dus geen uitvoerbare items, (c) getend maar stil geëscaleerd. Kies de fixes op basis hiervan.

## Taak 1 — Tend verbreden (queued + actief-niet-af)
- `_tend_projects` op `dag_begint` pakt naast `queued` ook `running`-projecten met een **onvoltooide checklist** op, en werkt het eerstvolgende openstaande item af. Idempotent via de done-vlaggen; herwerk geen afgeronde items.
- **Niet** oppakken: `blocked` (means-gap of wacht-op-review) en `done`. Die wachten bewust op de mens; ze elke dag opnieuw proberen is tokenverspilling tegen dezelfde muur.
- **Acceptatie:** een project dat gisteren half af raakte gaat vandaag verder waar het stopte; een geblokkeerd project blijft staan tot de mens antwoordt.

## Taak 2 — Zichtbaar escaleren naar de founder
- Een means-gap escaleert nu naar de `human_inbox` (CLI-wachtrij), maar de founder ziet dat niet. Maak er een **zichtbare notificatie** van naar de founder (@founding farmer): welk project, welke rol, wat er ontbreekt (skill/means), plus de link terug naar de human_inbox.
- Blijf binnen de beveiligingsgrens uit CLAUDE.md (human_inbox-sectie): de notificatie is een **heads-up met context, geen approve-knop**; beslissen gebeurt op het geauthenticeerde human_inbox-oppervlak.
- **Acceptatie:** als Sid een skill mist of een skill faalt, krijgt de founder een zichtbaar bericht, niet alleen een stille CLI-regel.

## Taak 3 — Sid's bestaande projecten werkbaar maken
- Op basis van taak 0: zet de projecten die klaar zijn om te draaien op `queued` (of de juiste status) zodat de eerstvolgende puls ze oppakt.
- Projecten die een skill vereisen die niet in het rugzakje/registry zit → laat ze zichtbaar escaleren (taak 2) in plaats van stil op 0% blijven.

## Guardrails
- Append-only / idempotent; geen auto-retry van blocked. Human_inbox blijft het beslis-oppervlak (notificatie = alleen heads-up).
- Branch `kennisbank`-los, aparte PR, tests + volle suite groen. Applies op prod als user `nooch`, back-up, dry-run.
