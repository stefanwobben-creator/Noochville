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

## 2026-06-20 — deel 1: wiring-gap-diagnoses (Ronnie, locale)

**[ontdekking]** Ronnie-gap stond fout in STATE. Hij abonneert op 8 event-types
(incl. pulse_completed), niet alleen dag_begint; de 15-juni-notitie klopte, de
19-juni-observatie was fout (STATE nog corrigeren). De "stille dag op een drukke dag"
komt door de demo-orkestratie: dag_eindigt valt niet in de demo, dus het bulletin
wordt buiten Ronnie's verzamel-flow geforceerd met een lege _events_today. In een
echte dagcadans werkt Ronnie. Eén losse echte gap: gsc_pulse_completed mist in _TRACK.

**[ontdekking]** Locale is een half-aangelegd dood pad, geen doorgeef-vergetelheid.
Upstream: GSC leidt locale af uit het domein-TLD ("en" voor heel nooch.earth) en zet
'm niet eens in het demand-dict. Downstream: Library.curate slaat locale niet op als
eigen veld, dus LibraryListSkill's locale_filter filtert structureel leeg. Niemand
leest de locale. De grove "en" is daarom dead-on-arrival (harmloos), maar de feature
werkt nergens — een spook-filter.

**[beslissing]** Ronnie: fix als "maak de demo een eerlijke simulatie" (dag_eindigt
laten vallen of bulletin via Ronnie's flow met verzamelde events; join-barrier) plus
gsc_pulse_completed toevoegen. Deel 2.

**[beslissing]** Locale: geen een-regel-fix. Vervolgactie = beslis of locale-filtering
een echte behoefte is. Zo ja: pad afmaken (GSC-country als bron + curate slaat locale
op als veld + filter werkt). Zo nee: dode locale_filter opruimen. Deel 2 of later.

**[les]** Drie wiring-gaps op rij (Ronnie, locale-upstream, locale-downstream) hadden
een diepere oorzaak dan STATE en de lijst suggereerden. De deel-2-wiring-gaps zijn
ontwerpvragen, geen triviale doorgeef-fixes. Herijk de scope: minder items, elk eerst
diagnose dan keuze.
