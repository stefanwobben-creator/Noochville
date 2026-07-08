# Uitvoer-primitief — werk-laag, Fase 1 (2026-07-08)

Bord-gedreven statusmachine voor projecten: **TOEKOMST = voorbereiden**, **ACTIEF = uitvoeren**,
**DONE = alles af**. Vervangt de oude `run_project → "stub:done"`-stub (die succes voorwendde) door een
echte, eerlijke keten: projectdoel → checklist → skill → note (deliverable). Leeft op de basis-`Inhabitant`,
dus **elke** rol verzorgt autonoom zijn eigen projecten binnen zijn governance-grenzen.

Bord-kolommen ↔ ledger-status (`views/projects.py`): TOEKOMST=`future`, ACTIEF=`queued`/`running`, DONE=`done`.

## Trigger
`Inhabitant.__init__` wired `dag_begint → _tend_projects` **universeel** (niet in `_setup_events`, dat
subklassen overschrijven — dit was precies het gat waardoor harry_hemp/concurrent_scout hun projecten niet
oppakten). Elke puls verzorgt de rol zijn eigen projecten:
- `future` (TOEKOMST) eigendom van mij → `prepare_project` (DEEL A)
- `queued`/`running` (ACTIEF) eigendom van mij → `_claim_run_complete` → `run_project` (DEEL B)

## DEEL A — voorbereiding (`prepare_project`, alleen TOEKOMST, string-scope, nog geen checklist)
1. **LLM-stap (Noochie, `_plan_checklist`)**: toetst het doel tegen mijn accountabilities + skills en
   breekt het op in 2–5 deel-items. Per item een skill-naam + query, óf `skill:null` + reden.
2. **Machine-check**: een voorgestelde skill die niet in mijn harde DNA-lijst (`self.dna.skills`) zit wordt
   teruggezet naar `skill:null` + reden — het model mag geen skill "verzinnen".
3. De checklist (named checklist "Uitvoerplan", zichtbaar op het bord) + één samenvattende note (de
   deliverable-belofte + welke items geen skill hebben en waarom) komen op het project. **Niets wordt
   uitgevoerd; het project blijft in TOEKOMST.** Geen LLM/plan → geen checklist, blijft in TOEKOMST
   (fail-closed, geen valse voorbereiding).

## DEEL B — uitvoering (`run_project` → `_execute_checklist`, ACTIEF)
- **Geen checklist** → luid signaal `project_needs_preparation` + log "sleep terug naar TOEKOMST"; **geen
  uitvoering, geen stub:done**.
- Per afvinkbaar item (skill-referentie, nog niet afgevinkt): draai de skill (`use_skill(skill, {term:
  query})`).
  - Skill-resultaat → **note bij het project** (de deliverable, `add_role_message`) → item afgevinkt.
  - Skill faalt of `no_data` → item **blijft open**, reden in een note (`… niet gelukt: <reden>`) + log.
    Geen stille skip.
  - Item zonder skill → blijft open (reden staat al in het item).
- **Alle items afgevinkt → DONE** (`run_project` geeft een outcome terug → `_claim_run_complete` completeert).
  Eén of meer open → **blijft in ACTIEF** (eerlijke voortgang X/Y; geen valse DONE).
- **Idempotent**: een afgevinkt item wordt niet opnieuw gedraaid; `last_tended`-dag-anker voorkomt dat een
  tweede puls dezelfde dag notes dupliceert.

## Test-case (harry_hemp — het deels-geval)
Doel "Patents and scientific studies on barefoot shoes researched": voorbereiding levert studies-items
gekoppeld aan `openalex_evidence`/`semscholar_tldr` (afvinkbaar) + een patent-item als "geen skill" (open).
Na uitvoering: studies-items gedraaid → notes met resultaat, patent-item open → project blijft in ACTIEF,
checklist toont de deel-voortgang. (Geen patent-skill = eerlijk zichtbaar, geen verzonnen dekking.)

## WIP-limiet op voorbereiding (cirkelpolicy WIP-001 — eerste gedrag-sturende policy)

Autonome voorbereiding is begrensd door een **work-in-progress-limiet**, verankerd als **cirkelpolicy** op
NoochVille (`mother_earth__nooch`, `kind=policy`, id **`WIP-001`**, `inherit=True`) — zichtbaar in de
Policies-tab, net als MONEY-001. Dit is de eerste policy die **gedrag stuurt** i.p.v. alleen beschrijft;
de scheiding blijft strikt (governance verankert de afspraak; code dwingt af, **geen tekst-interpretatie
van de body**):

- **Aan-schakelaar = de policy:** de hook `_wip_prepare_limit` checkt via `own_and_inherited` of `WIP-001`
  actief is op de omvattende cirkel. Afwezig/inactief → **geen limiet** (huidig gedrag). De policy is dus
  de expliciete, zichtbare aan-knop.
- **Getal N = config:** `wip_prepare_limit` (default 8) uit `settings.ini` — **niet** uit de policy-body
  geparsed. Body wijzigen verandert het gedrag niet.
- **Alleen AI-bemande rollen** (`record.persona_id` gezet). Mens-bemande rollen bereiden niet autonoom voor
  → limiet raakt hen in de praktijk niet.
- **Gedrag (FIFO):** per AI-rol worden max N future-projecten voorbereid, **oudste (`created_at`) eerst**;
  de rest **wacht** (geen weigering) tot een plek vrijkomt doordat een voorbereid project naar ACTIEF gaat.
  Zo geen voorbereidings-burst over veel TOEKOMST-projecten.

## Generalisatie voorbij {term}→{hits} (optie C — skill-schema's)

Het primitief kende aanvankelijk alleen `{term}→{hits}`; de prep-LLM kreeg alleen skill-namen en gokte de
payload (gokte `term` voor `kw`-lijst/`brands`-lijst-skills → concurrent_scout kon niet uitvoeren). Opgelost
via de al bestaande `Skill.input_schema`/`output_schema`-velden:

- **Schema's ingevuld** voor de werk-skills (openalex_evidence, semscholar_tldr, keywords_everywhere,
  ngram_culture, openlibrary_search_inside; de competitor-/onderzoeksvraag-skills hadden er al).
- **Doorgegeven aan de prep-LLM:** `_plan_checklist` bouwt een catalogus met per skill `description` +
  `input_schema`. De LLM levert nu per item de skill **én** een `payload` in de voorgeschreven vorm
  (`{"term":…}` / `{"kw":[…]}` / `{"brands":[…]}`). Fail-soft: een skill zonder schema → de LLM valt terug
  op naam + omschrijving.
- **Status genormaliseerd (de enige echte normalisatie):** `_classify_result` vertaalt beide fail-conventies
  (`{error}`/`{no_data}` én `{ok:False,error}`) naar één uitkomst **gelukt / leeg / fout** — daarop wordt
  afgevinkt of open gelaten.
- **Note-inhoud rauw-maar-leesbaar per archetype** (bepaald door de output-vorm, geen per-skill hardcoding):
  lijst-van-records → opgesomd, elk record met zijn **eigen** velden (paper: titel/abstract/citaties; merk:
  merk-info); enkele tekst → direct; metriek-serie → waarde-per-datum. Geen velden weggegooid, geen
  gemene-deler-vorm.

Legacy back-compat: een item met alleen `query` (oud) valt terug op `{"term": query}`.

## Bewust NIET in Fase 1
Meerdere named checklists per project als parallelle sporen; her-voorbereiding bij een gewijzigd doel;
automatische kolom-overgang TOEKOMST→ACTIEF (nu mens-gedreven via het bord); niet-`term`-payloads voor
skills met een afwijkend contract.
