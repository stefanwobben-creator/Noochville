# Ontwerpnotitie — Doelen op het projectenbord

Status: vastgelegd ontwerp, klaar om te bouwen. Eerste case: MITH "Biobased Noochie Barefoot".
Klikbare mockup: `docs/MITH_doelen_incockpit.html` (leidend voor de look).

## Naam
In de UI heet het overal **Doel** (Nederlands, sluit aan op de intentielaag die al "Doelen" heet;
consistenter dan Goal/Objective in een verder Nederlandse cockpit). Conceptueel/in code mag de
entiteit `objective` heten. De bestaande grijze detailknop "Goals" wordt hernoemd naar **Doel**.

## Kernmodel (canoniek)
- Een **Doel** is een lichte entiteit in de intentielaag (Founder/Strategic-Lead-eigendom). Geen rol, geen cirkel.
- Een **project blijft van zijn rol** en *verwijst* naar een doel (`doel_id` + optioneel `activiteit`).
  Zo blijft rol-autonomie (`run_project`, `requires_skill`) intact.
- Eén bron (de rol-projecten met een doel-verwijzing), meerdere views: het gelabelde bord, de
  Doel-pagina en de urenstaat zijn afgeleiden. Reference, don't copy.

## UI-beslissingen (vastgelegd)

### Op het projectenbord
- Naast **+ project** komt **+ Doel** (nieuw doel aanmaken), zelfde horizontale inline-vorm.
- Bovenin een **Doel-filterbalk** (Alle | MITH | …). Filtert de kaarten tot dat doel.
- Groepering blijft **per rol** (bestaande swimlanes). Geen extra swimlanes nodig.

### De kaart (minimaal)
- Toont alleen: het **Doel-label** (bijv. "MITH"), de titel en de persoon (+ voortgangsbalkje).
- **Geen** rol-chip (de rol is al de swimlane). **Geen** budget of werkpakket op de kaart.

### Het projectdetail (achter de Doel-knop)
- De **Doel-knop** opent de koppel-sectie: **Doel** kiezen (geeft de kaart z'n label),
  **Werkpakket/activiteit** kiezen, **Budget uren** zetten, en **Werkelijke uren** invullen
  (pas invulbaar zodra het project op Done staat).
- Budget en werkpakket wonen hier, niet op de kaart.

### Doel aanmaken (metagegevens)
Titel + korte DoD, **budget uren**, **deadline** (of venster), **rollen die eraan werken**
(checkboxes), en een optionele **activiteiten-lijst** (voor MITH = de 5 werkpakketten; nodig om
de urenstaat per activiteit te splitsen; leeg laten voor een doel zonder subsidie).

### Doel aanklikken → voortgang
Klik op een doel (pill of Doelen-overzicht) → **Doel-pagina** met de metagegevens, de roll-up
(budget vs gerealiseerd, % af) en het bord gefilterd op dit doel. Tab "Urenstaat" toont de
afgeleide tabel (per activiteit + per persoon). Export = eigen urenoverzicht + PDF.

## Uren
Budget op doel (+ optioneel per project/activiteit). De rol logt de **werkelijke uren** bij Done in
het detail. Roll-up: project → activiteit → doel. De urenstaat is een afgeleide, geen tweede administratie.

## Datamodel
- `data/objectives.json` via een lichte `ObjectiveStore` (vorm zoals `ProjectLedger`/`DefinitionStore`):
  id, titel, dod, budget_uren, deadline/venster, rollen[], activiteiten[] (elk naam + begroot + venster).
- Project krijgt `doel_id` (+ optioneel `activiteit`) en `gerealiseerde_uren`, via het bestaande
  scope-dict-patroon (zoals `requires_skill`).

## Bouwbrokken (klein, toetsbaar, branch per brok)
1. **ObjectiveStore** + `data/objectives.json` (add/get/all/amend). Tests. (Additief: maakt bestand aan als het ontbreekt.)
2. **+ Doel** aanmaken/bewerken (UI + dispatch). AUTHZ: anchor-lead of Strategic Lead.
3. **Project ↔ doel** via de detail-knop "Doel": doel + werkpakket + budget + werkelijke uren. Label op de kaart. Tests.
4. **Doel-filterbalk** boven het bord (rol- en cirkel-bord).
5. **Doel-pagina** + roll-up + urenstaat-tab + PDF-export.
6. **MITH inrichten**: doel + 5 activiteiten + 48 projecten (zie `MITH_projectenlijst_Barefoot.md`).

## Referentie
Inhoud/uren/rollen: `MITH_projectenlijst_Barefoot.md`. Mockups: `MITH_doelen_incockpit.html` (leidend),
`MITH_doelen_prototype.html`, `MITH_prototype.html`, `MITH_kanban_prototype.html`.
