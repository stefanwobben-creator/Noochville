# Execution Contract — AI-rollen in NoochVille
*Ontwerp vastgelegd 2026-06-29*

## Het model

AI-rollen werken via pull, niet push.
Trigger = project op projectenbord in status `queued` of `running`.
Geen actief project? Check status `future`.
Beide leeg? Wacht.

Statussen in volgorde van prioriteit:
| Status | Betekenis |
|--------|-----------|
| `running` | Actief opgepakt door een rol |
| `queued` | Klaar om op te pakken |
| `future` | Gepland, nog niet actief |
| `draft` | Voorstel van een rol — wacht op goedkeuring mens |
| `done` | Afgerond (terminal, wordt niet meer opgepakt) |

## Wie mag projecten toevoegen

- **Circle Lead** (altijd) — direct via cockpit, status `queued`
- **Medevervuller met mens-type** (gekoppeld aan rol) — direct via cockpit
- **Rol zelf**: alleen als voorstel met status `draft`, wacht op goedkeuring van
  medevervuller of Circle Lead (`ProjectLedger.approve_draft()` in `projects.py`)

## Twee staten per rol

### Staat 1: Kan leveren

- Rol herkent dat zijn skills matchen met de projectomschrijving
- Voert uit via zijn skills (geregistreerd in `SkillRegistry`, toegewezen in `dna.skills`)
- Schrijft output terug als notitie op de rol
- Markeert project als `done` (`ProjectLedger.mark_done()`)
- Stuurt inbox-melding naar medevervullers en Circle Lead

### Staat 2: Kan niet leveren

- Rol herkent dat een skill ontbreekt (`dormant_capabilities()` in `inhabitant.py:922`)
- Formuleert spanning: `"KAN NIET: [wat ontbreekt] — heb nodig: [X]"`
- Noochie verzamelt deze spanning
- Noochie vertaalt naar agendapunt werkoverleg
- Mens besluit: skill bouwen of zelf oppakken

Een rol die vastloopt verzint geen output. Hij stopt en meldt.

## Noochie als verbindingspersoon

- Verzamelt spanningen van alle AI-rollen
- Vertaalt naar begrijpelijke taal voor mens
- Brengt in als agendapunt werkoverleg (`data/werkoverleg.json`)
- Is Circle Rep van Noochville: representeert AI Farm naar Nooch-cirkel

## Skill-rol koppeling (nog te bouwen)

Nu hardcoded in `CLASS_MAP` in `nooch_village/village.py:63`.
Doel: koppeling definiëren in governance zodat een nieuwe rol in de cockpit direct
capabilities kan krijgen zonder code-aanpassing.

Stap 1: `capabilities`-veld toevoegen aan rol in governance-record
         (`Inhabitant.capabilities()` bestaat al in `inhabitant.py:77`)
Stap 2: Village checkt capabilities bij project-pickup
Stap 3: Skill-match algoritme bepaalt of rol kan leveren

Tussenstap nu beschikbaar: `dormant_capabilities()` detecteert al rollen die een skill
aanroepen zonder die in hun DNA te hebben — dit is de waarschuwing bij startup.

## Roltoewijzing bepaalt alles

Voorbeeld: Stefan voegt Codie toe aan Website Developer.
Codie weet dan:

- Mijn accountabilities = die van Website Developer
- Ik luister naar medevervullers en Circle Lead
- Mijn projectenbord = mijn werklist
- Mijn output = notitie op rol + inbox-melding

De toewijzing staat in `data/assignments.json`. De cockpit toont per rol wie hem vervult
(mens of AI-persona) en welke projecten er open staan.

## Transparantie en monitoring

- Elk uitgevoerd project krijgt een output-notitie (zichtbaar in cockpit)
- `data/system_log.jsonl` registreert elke actie (audit trail)
- `data/output/field_note_<datum>.md` geeft dagelijks overzicht
- Inbox-melding bij `done` of spanning (`data/human_inbox.json`)
- Circle Lead ziet altijd status via cockpit (`https://village.nooch.earth`)

## Openstaande vragen

- Hoe definiëren we capabilities in governance? (veld in record vs. CLASS_MAP)
- Hoe doet Codie Code research als hij een skill mist? (via Noochie of LLM-call)
- Wanneer gaat een project naar `done`: automatisch of na goedkeuring mens?
- Hoe werkt de skill-match in de praktijk? (fuzzy op accountability-tekst of expliciete tag)
