# Objectives (Doelen) op het projectenbord — plan van record

Doel van deze feature: een Objective/Doel als lichte entiteit, projecten eraan koppelen, op het
bord als label tonen, en bovenin filteren. MITH "Biobased Noochie Barefoot" is de eerste case.
Dit vervangt de zwaardere ideeën (swimlanes, tijdelijke rol): label + filter is genoeg.

## Model (canoniek)
- **Objective = een Doel in de intentielaag.** Founder/Strategic-Lead-eigendom. Geen rol, geen cirkel.
- **Projecten blijven van de rollen** (Holacracy). Een project *verwijst* naar een objective; het
  wordt er niet in "gestopt". Zo blijft de rol-autonomie (`run_project`, `requires_skill`) intact.
- **Eén bron, meerdere views:** de rol-projecten met een `doel_id` (+ optioneel `activiteit`) zijn
  de waarheid. Het gefilterde bord, de Doel-pagina en de urenstaat zijn afgeleiden. Reference, don't copy.

## Jouw UX-visie, uitgeschreven

### 1. Objective aanmaken (met metagegevens)
Nieuw scherm "Doel aanmaken" met velden:
- titel + korte omschrijving/DoD
- budget uren (totaal)
- deadline (of venster begin/eind)
- rollen die eraan werken (checkboxes) — bepaalt welke rollen dit doel in hun project-dropdown zien
- activiteiten (optioneel, licht): een lijstje deel-activiteiten met elk een begroot-uren en venster.
  Voor MITH = de 5 werkpakketten. Dit is de enige toevoeging op je visie, en alleen nodig omdat de
  subsidie-urenstaat per activiteit moet uitsplitsen. Voor een doel zonder subsidie laat je dit leeg.

Opslag: `data/objectives.json` via een lichte `ObjectiveStore` (zelfde vorm als `ProjectLedger`/
`DefinitionStore`). Cockpit-bewerkbaar.

### 2. Project koppelen aan een objective
In de bestaande "+ project"-form een extra dropdown **Doel (optioneel)** met de actieve objectives.
Kies je een doel dat activiteiten heeft, dan verschijnt een tweede dropdown **Activiteit** (bijv.
werkpakket 1-5). Zelfde patroon als het `requires_skill`-veld dat we al bouwden: het project krijgt
`doel_id` (en optioneel `activiteit`) in de scope-dict.

### 3. Label op het bord
Elke kaart die aan een doel meedoet krijgt een klein chip (bijv. "MITH"). Kaarten zonder doel: geen chip.
Geen swimlanes nodig; het bord blijft je status-kanban.

### 4. Filteren bovenin
Een filterbalk boven het bord: **Doel: alle | MITH-rapport | …**. Kiezen filtert de kaarten tot dat
doel. Werkt op het rol-bord én het cirkel-bord (cross-rol overzicht van al het MITH-werk).

## Uren
- Budget staat op het doel (en optioneel per activiteit). De rol vult de **werkelijke uren** in bij
  het op Done zetten van een project (klein uren-veld dat verschijnt bij Done).
- Roll-up: project-uren → activiteit → doel. Export = eigen urenoverzicht + PDF (voldoende bewijs).
- Zonder `activiteit` rolt het alleen naar doel-niveau; mét activiteit krijg je de 5-activiteiten-
  uitsplitsing die de MIT-urenstaat vraagt, plus per persoon (de trekker die logt).

## Doel-pagina (de roll-up)
Klik op een doel → pagina met de metagegevens (budget, deadline, rollen), de roll-up (begroot vs
gerealiseerd, % af) en het bord gefilterd op dit doel. Dit is de prototype-header + het echte bord.
Een tabje "Urenstaat" toont de afgeleide tabel (per activiteit + per persoon).

## Bouwbrokken (klein, toetsbaar, branch per brok, protocol)
- **Brok 1 — ObjectiveStore.** `data/objectives.json` + store (add/get/all/amend), met velden titel,
  dod, budget_uren, deadline/venster, rollen[], activiteiten[]. Tests.
- **Brok 2 — Doel aanmaken/bewerken (UI + dispatch).** Scherm + `obj_add`/`obj_edit`. Autorisatie:
  `# AUTHZ: anchor-lead of Strategic Lead` (doelen zijn org-breed/intent).
- **Brok 3 — Project ↔ doel.** Dropdown "Doel" (+ "Activiteit") in beide project-forms; `doel_id`/
  `activiteit` in de scope-dict (patroon `requires_skill`). Chip op de kaart. Tests.
- **Brok 4 — Filterbalk.** Doel-filter boven het bord (rol- en cirkel-bord). Puur client/query.
- **Brok 5 — Uren op Done.** Uren-veld dat verschijnt bij status Done; opslag `gerealiseerde_uren`.
- **Brok 6 — Doel-pagina + roll-up + urenstaat-tab.** Roll-up over gekoppelde projecten; export PDF.
- **Brok 7 — MITH inrichten.** Doel + 5 activiteiten + 48 projecten (zie `MITH_projectenlijst_Barefoot.md`).

## Referentie
- Inhoud/uren/taken: `docs/MITH_projectenlijst_Barefoot.md` (48 projecten, uren, rollen).
- OKR-variant: `docs/MITH_OKR_structuur.md`.
- Klikbare mockups: `docs/MITH_prototype.html` (3 projecties), `docs/MITH_kanban_prototype.html`
  (kanban + swimlanes). Swimlanes = optionele latere nicety; v1 = label + filter.

## Beslispunt
- Activiteit-laag meenemen in v1 (nodig voor de MIT-urenstaat-uitsplitsing) of pas in v2? Aanbeveling: v1,
  want zonder splitst de urenstaat niet in de 5 verplichte activiteiten.
