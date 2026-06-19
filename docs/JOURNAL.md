# NoochVille JOURNAL

Logboek van progressie, ontdekkingen en lessen. Append-only: nieuwe entries
onderaan, oude blijven staan. Per item een type-tag zodat je later kunt filteren
(fix / ontdekking / faalmodus / beslissing / les / procesobservatie).
STATE.md is de huidige waarheid (vervang bij update); dit is de geschiedenis.

---

## 2026-06-19/20 — nachtsessie, klein onderhoud tijdens Hogueras

**[fix]** pandas gecapt op `<3` (requirements.txt, commit cd4116c). CI haalde 3.0.3
binnen; verse install met de cap blijft groen.

**[fix]** scripts/live_measure.py onder versiebeheer gebracht (commit 21d195d),
inclusief correctie van een overgebleven KWFinder-URL naar keywordseverywhere.com.
Het script was untracked en leefde alleen lokaal.

**[fix/beveiliging]** .env toegevoegd aan .gitignore en gecommit (33f62b1).
Via git ls-files geverifieerd dat het nooit getrackt was, dus geen keys in de history.

**[ontdekking]** STATE.md kan twee kanten op onbetrouwbaar zijn. Achterlopen: de
inbox-approve-timeout stond als "parametrisch maken" terwijl het al instelbaar is
via inbox_approve_timeout (default 5). Overschatten: het dom WIP-plafond staat als
gebouwd, maar bestaat niet in de code of een stash. ProjectLedger heeft open()
maar geen cap-logica.

**[beslissing]** Timeout-item doorgestreept: 5s is royaal voor de deterministische
G0-G4-gate, default 5 blijft, oplossen pas bij een echte false-timeout. WIP-cap niet
gebouwd vannacht; geparkeerd als echt te-bouwen item.

**[les]** In STATE.md correleert een commit-hash met geverifieerd-waar, en geen hash
met mogelijk-lucht. Een gebouwd-claim hoort aan een commit te hangen, niet aan een
herinnering. Onderbouwt de STATE/JOURNAL-splitsing.

**[procesobservatie]** De keten: een URL-typo legde een untracked script bloot, dat
een ongecommitte .env-bescherming blootlegde. Klein onderhoud is zelden klein, maar
het stopte op een natuurlijk punt: drie fixes, schone main.
