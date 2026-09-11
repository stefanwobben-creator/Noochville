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

## Gebouwd — scope 46, 11 september 2026

Stefan: "tijd om die functionaliteit te bouwen; onder goals hangen weer projecten, we willen voortgang
zien, en het kritieke pad." Zijn keuzes: afhankelijkheden per project (ja), deadline op het doel, uren
later. Het model hierboven is gebouwd zoals beschreven; wat afwijkt staat hieronder expliciet.

| prototype (`MITH_doelen_incockpit.html`) | live | opmerking |
|---|---|---|
| `.pill` / `.pill.on` (doel-filterbalk) | `.cl-filter.pill` / `.on` in `.vswitch` | bestaande filter-pillen, plus "all goals →" |
| `.objhead` (paarse doelkop) | `.card.doel` | nieuwe tint-tokens `--goal`/`--goal-tint`; variant heet `doel` omdat `.goal` al bestaat (metrics-balk) |
| `.bar` (voortgang in de kop) | `<progress class='pbar wide'>` | zelfde balk als de kaart, als `<progress>` zodat de breedte geen inline style is |
| `.glabel` (doel-label op de kaart) | `.chip.doel` (link naar `/goal`) | |
| `.kcard .pbar` (voortgang op de kaart) | bestaande `.pbadge`/`.pbar` | ongewijzigd |
| "◎ Goals"-knop + `.goalbox` in de modal | rail-regels **Goal · Work package · Depends on** (`_meta_rij`, `mform`, autosave) | bewust anders: sinds de rail-herindeling woont alle meta in de rail; een box achter een knop was een tweede huis |
| Budget / Werkelijke uren | niet gebouwd | uren = scope 47, zodra de subsidie-administratie het vraagt; `doel_id`/`activiteit` staan er al |
| Doel-pagina (roll-up + bord gefilterd) | `/goal?id=` met roll-up, **kritieke pad**, projecten per status, bulk koppelen, bewerken; `/goals` als overzicht (footer-navigatie) | kritieke pad is nieuw t.o.v. de notitie |
| Nederlandse labels ("Doel") | Engelse chrome ("Goal", "Goals") | sinds #466 is de cockpit-chrome Engels; de notitie dateert van daarvoor |

Voortgang = (afgerond × 1 + open × checklist-ratio) / aantal, in `doelen.voortgang`. Kritieke pad in
`doelen.kritieke_pad`: langste keten van open projecten via `depends_on`, knelpunt, wachtend, vrij,
deadline-vlaggen; een kring is een invoerfout. Zaad: `village doelen_zaad --apply` (vijf doelen).
