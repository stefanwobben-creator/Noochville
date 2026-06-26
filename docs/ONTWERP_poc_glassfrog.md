# PoC: NoochVille als GlassFrog-vervanger

Status: in aanbouw. Doel: de GlassFrog-interface namaken bovenop de bestaande village-kern,
met Nooch als nul-klant. Wat we al hebben gieten we in deze vorm; wat we nog niet hebben tonen
we grijs ("nog te bouwen"), zodat in één oogopslag zichtbaar is welke brokjes resten.

## De GlassFrog-vorm (de ijk)

Elke **cirkel** en **rol** heeft in GlassFrog een paginanavigatie met tabs:

| Tab | Wat | Hebben wij |
|-----|-----|-----------|
| Overview | purpose, strategie/kernwaarden, domeinen, accountabilities | ja (records) |
| Roles | de rollen (en subcirkels) in deze cirkel | deels (records + parent, nog geen verkenner) |
| Members | de mensen in deze cirkel | nieuw (people-store) |
| Policies | harde afspraken per cirkel | deels (nu alleen anchor-policies) |
| Notes | losse notities op een rol/cirkel | nieuw (attachments) — hier vouwen we concurrenten in |
| Projects | projecten op een rol/cirkel | ja (ProjectLedger/prikbord), koppeling per rol nieuw |
| Checklists | terugkerende check-items | nieuw (attachments) |
| Metrics | meetwaarden per rol/cirkel | nieuw (attachments) — hier vouwen we zoekwoord-volume in |
| History | wijzigingsgeschiedenis | deels (records-versies, groeidagboek) |

Twee meetings vanaf de "Start Meeting"-knop:

- **Governance** (= ons roloverleg, net verbouwd). Klaar genoeg voor de PoC.
- **Tactical**: geleide flow Check-in → Checklist Review → Metrics Review → Project Updates →
  Triage Issues (elke spanning → Action of Project, met Rol + Persoon, Next/Waiting) → Closing.
  Dit is het grootste gat. Nieuw te bouwen.

Rechts op elke cirkelpagina: een **org-verkenner** (de cirkelkaart / boom). Subcirkels nesten.

## Kerninzicht: onze extra's zijn GlassFrog-primitieven

- concurrenten = **Notes** op de scout-rol
- zoekwoord-volume = **Metrics** op een rol
- kennislaag-kaartjes = **Notes**

Door dit als generieke primitieven te modelleren wordt de cockpit generiek (verkoopbaar aan
OVM, Obelink, FindYour) en is Nooch gewoon data binnen die primitieven.

## De echte Nooch-structuur (uit de GlassFrog-export)

Twee geneste cirkels:

- **Mother Earth** (wortel): rollen Circle Lead, Facilitator, Secretary, Shareholder (Lotte, Stefan);
  bevat subcirkel Nooch.
- **Nooch** (subcirkel): 16 rollen, o.a. Brand & Visual Designer (Lotte), Carbon Footprint Improver
  (Lotte), Creator of Shoes (Lotte), Community and Email (Nina), Marketing Lead (Matthijs),
  Supply Chain Coördinator (Wytse), Website Developer (Stefan, Dan; domein nooch.earth),
  Financial Controller (Stefan), Strategic Lead & Founder Steward (Stefan), Mother Earth Steward
  (Lotte, Stefan), Facilitator (Stefan).

Mensen: Lotte Mulder, Stefan Wobben, Nina Wolter, Matthijs Boesten, Wytse Valkema, Dan Morgan.
Meervoudige bezetting in beide richtingen (rol → meerdere mensen, mens → meerdere rollen).

## Datamodel (brok 1, deze nacht)

Het bestaande model kan al nesten: `RecordType.CIRCLE`, `Record.parent`, `Record.members`.
Daarop bouwen we, additief en niet-brekend:

1. **`people.py`** — `Person` (id, name, email) + `PeopleStore` (data/people.json). De mensen.
2. **`assignments.py`** — wie vervult welke rol. Meervoudige, hybride bezetting: een *filler* is
   `{"type": "person"|"persona", "id": ...}`. `fillers_of(role_id)` voegt legacy `held_by`
   (mens) en `persona_id` (AI) samen met de nieuwe lijst, zodat niets breekt.
   Dit is de "bemenst"-laag los van de "geboren"-laag (records): assignment is operationeel,
   geen governance.
3. **`attachments.py`** — één generieke `Attachment` (id, anchor, kind ∈ note/metric/checklist/
   policy, title, body, meta, timestamps) + `AttachmentStore` (data/attachments.json).
   Eén store bedient vier tabs. Anchor = elke record-id (nesting-agnostisch).
4. **`org.py`** — boom-helpers over de records: `children_of`, `subcircles_of`, `roles_of`,
   `descendants`, `breadcrumb`, `is_circle`. Puur lezen; nesting-proof.
5. **`glassfrog_import.py`** — `parse_glassfrog_export(text)` (de GlassFrog-export naar een
   org-dict) + `import_org(org, records, people, assignments)`. Dit is het migratie-pad dat we
   straks ook voor OVM/Obelink gebruiken (geen overtik-script).

Niet vanavond aangeraakt: de live `data/`. De importer draait in de PoC-dataset, niet over de
bestaande SEO-agent-village heen (dat is een keuze voor morgen: vers PoC-dataset of samenvoegen).

## Brok-roadmap (PoC)

1. Datamodel-fundament (deze nacht): people, assignments, attachments, org-helpers, importer.
2. Importer draaien → echte Nooch-structuur in een PoC-dataset.
3. Cirkel-/rolpagina met tabs + org-verkenner (lezen eerst). Grijs wat er nog niet is.
4. Mensen-op-rollen + persoonspagina ("mijn rollen") — de hybride zichtbaar.
5. Notes + Metrics generiek; concurrenten/volume erin vouwen.
6. Tactical meeting (de geleide flow).
7. Later: Checklists/Policies/History-tabs, notificaties, web-ontsluiten (auth + hosting).

## Grijs-principe

Wat nog niet bestaat, renderen we als een grijze, niet-actieve placeholder met het label
"nog te bouwen". Zo is de cockpit vanaf dag één een complete kaart van het werk, en zie je
elke brok die nog open staat.
