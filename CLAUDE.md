# CLAUDE.md — NoochVillage

Projectcontext en spelregels voor Claude Code. Lees dit eerst, samen met `README.md`
en (indien aanwezig) `docs/CONTEXT.md` voor de missie van Nooch.earth.

## Wat dit is

NoochVillage is een event-driven "dorp" van autonome inwoners (rollen) met echte skills,
gebouwd voor Nooch.earth (duurzaam schoenenmerk, organische groei via missie-gedreven SEO).
Inwoners pakken autonoom werk op dat bij hun doel en accountabilities past, kunnen elkaar
om hulp vragen, en samenwerken aan een hoger doel. Het governance-model is gebaseerd op
Holacracy.

Dit is een werkende kern, geen simulatie: de skills doen echt I/O.

## Draaien

```bash
python -m nooch_village.village          # demo: snelle hartslag, toont de Field Note
python -m nooch_village.village once      # één echte groei-puls en stoppen (voor cron)
python -m nooch_village.village run       # blijft draaien, puls 1x per echte dag
```

Altijd starten vanuit de map die `nooch_village/` bevat, en met de `-m`-vorm.
Niet `python nooch_village/village.py` (dan breken de imports). Laat de `__init__.py`'s staan.

## Architectuur (drie lagen)

1. **Het marktplein** — `EventBus` (`event_bus.py`): broadcast van feiten/aankondigingen. Autonomie: inwoners reageren zelf op events die hen aangaan.
2. **De postbus** — `Inbox` per inwoner (`inbox.py`): toegewezen werk dat áf moet. Betrouwbaarheid.
3. **De matchmaker** — `Matchmaker` (`matchmaker.py`): hoort "wie kan dit?" en legt werk in de inbox van een capabele inwoner.

Kerncomponenten:
- `models.py` — `RoleDefinition` (DNA), `Record` (de waarheid), `Task`, `Response`, `Tension`, `RecordType`.
- `inhabitant.py` — `Inhabitant` (leaf, één rol) en `Circle` (composite). Methodes: `handle`, `ask`, `use_skill`, `sense_tension`, `tick`, `reload`.
- `roles.py` — gespecialiseerde inwoners: `TimeKeeper` (hartslag → `dag_begint`), `GrowthAnalyst` (ochtend-puls).
- `governance.py` — `Records` (json, de waarheid), `Secretary` (records bijhouden, geen veto), `Reconciler` (bouwt het levende dorp uit de records).
- `skills.py` — `Skill` (ABC) + `SkillRegistry`. `skills_impl/` bevat de echte skills.
- `config.py` — `Context` (de rugzak/DI) + `load_context` (leest `config/settings.ini` en `.env`).
- `llm.py` — optionele LLM-redenering (Anthropic of Gemini), valt terug op None zonder key.

Data (allemaal in `data/`, gitignored):
- `governance_records.json` — de bron van waarheid over wie bestaat en wat ze mogen.
- `output/field_note_<datum>.md` — de dagelijkse Field Note.
- `last_pulse.json` — basislijn voor spanning-detectie. `budget.json`, `system_log.jsonl` (audit-trail).

## HARDE REGELS (niet schenden zonder overleg)

1. **Eén rol per inwoner** (leaf). `Circle` is een composite; van buiten is een cirkel gewoon een rol. Het dorp ZELF is de wortelcirkel, zodat een subcirkel later gratis nest.
2. **De EventBus wordt ALTIJD geinjecteerd** (`self.bus`). NOOIT een global singleton importeren of gebruiken. Dit is de enige discipline die geneste cirkels later mogelijk houdt.
3. **Records = de waarheid, levende inwoners = een projectie.** De `Reconciler` bouwt het dorp uit de records. Meer verantwoordelijkheid krijgen = record amenderen (version bump) + `reload()` van DNA. GEEN respawn, geen state die alleen in de thread leeft.
4. **De Secretary heeft GEEN veto.** Een voorstel wordt aangenomen tenzij het structureel ongeldig is. (Dit is de structurele poort. De volledige IDM met objectronde komt later, zie roadmap.)
5. **Skills zijn echt en worden geinjecteerd via de `SkillRegistry`.** Geen mock-data die echte calls dood-codeert. Een skill faalt liever bewust "closed" dan dat hij iets verzint.
6. **Inbox = toegewezen werk** (via de matchmaker). **Events = aankondigingen** (autonomie). **`tick()` = zelf-geinitieerd werk** (hartslag). Houd die drie gescheiden.
7. **Een cirkel heeft geen handen: hij delegeert.** Laat een `Circle` nooit zelf werk uitvoeren in `handle`; hij routeert naar een member.
8. **Niet de oude `src/`-generaties terughalen.** Die repo had drie onderling botsende base-classes (`Role` vs `BaseAgent`), drie versies van het datamodel, en een Plausible-agent met de echte API-call dood-gecodeerd áchter een `return` met mock-data. Dat is bewust vervangen.

## Een nieuwe skill toevoegen

1. Maak `skills_impl/<naam>.py` met een `Skill`-subklasse (`name`, `description`, `run(self, payload, context) -> dict`).
2. Registreer hem in `village.py` (`self.registry.register(...)`).
3. Ken de capability via governance toe aan een inwoner (in de demo: een `propose_amendment`-event met `add_skills=[...]`; bij seed: in de `skills`-lijst van het record).

## Een nieuwe inwoner toevoegen

1. Voeg een `Record` toe in `seed_records` (of via een governance-voorstel), met `parent="noochville"` en de juiste `skills`.
2. Zet de id in de `members`-lijst van de wortelcirkel.
3. Wil de inwoner eigen gedrag (zoals de puls)? Maak een `Inhabitant`-subklasse in `roles.py` en zet hem in `CLASS_MAP` in `village.py`. Anders wordt het een generieke `Inhabitant`.

## Governance (Holacracy) — model en status

- **Rollen** hebben een purpose, accountabilities, domeinen en skills (`RoleDefinition`). **Cirkels** bevatten rollen.
- **Spanningen** zijn de motor: elke inwoner kan er een sensen (`sense_tension`). Triage: operationeel → de inwoner handelt autonoom; governance → een voorstel dat de structuur wijzigt.
- **Domeinen = "libraries".** Lezen is vrij (via `context`); cureren/wijzigen is het exclusieve recht van de eigenaar. Dit is de enige Holacracy-uitzondering waarin toegang beperkt is.
- **Twee poorten** bij een voorstel: procedureel (Holacracy-geldigheid) én inhoudelijk (de Nooch-waarden uit `CONTEXT.md`). Houd die gescheiden.
- **Status nu:** structurele poort via de Secretary. **Nog niet gebouwd:** de volledige IDM (clarifying → reaction → objection-round met de vier validiteitscriteria → integration), Lead Link / Rep Link, en geneste governance per cirkel.

## De ontdekkingslus voor zoekwoorden (actief)

Twee onafhankelijke bronnen voeden dezelfde lus elke ochtend:

```
Bron 1 — Google Trends (GrowthAnalyst):
  TrendsSkill haalt data op (zaad: keywords.txt + goedgekeurde bibliotheekwoorden)
    → GrowthAnalyst._propose_related() publiceert keyword_proposed per nieuwe related query

Bron 2 — Google Search Console (PerformanceScout):
  GscPerformanceSkill haalt last-28-days queries op (dimensie: query)
    → PerformanceScout._propose_from_gsc() publiceert keyword_proposed per nieuwe high_potential query

Beide bronnen → Librarian:
  → KeywordReviewSkill toetst aan de missie (heuristiek of LLM met bewijs als demand)
    → approved  → in bibliotheek → volgend puls-zaad voor Trends via _read_keywords
    → forbidden → in bibliotheek → nooit meer voorgesteld
    → escalated → in bibliotheek → spanning naar mens, ook niet meer voorgesteld
```

Betrokken bestanden:

- `skills_impl/trends.py` — `_read_keywords` laadt naast `config/keywords.txt` ook alle
  goedgekeurde woorden uit `context.library`. `top_related` is `[{"query": str, "value": int}]`.
- `skills_impl/gsc.py` — `GscPerformanceSkill` (`gsc_performance`): OAuth via token.json
  (`GSC_TOKEN_PATH` in .env, scope `webmasters.readonly`), site via `GSC_SITE`. Geeft per
  query terug: impressions, clicks, positie en bucket (page1 / high_potential / low_ranking /
  content_gap). Faalt closed als token of site ontbreekt.
- `roles.py` — `GrowthAnalyst._propose_related()`: Trends-gerelateerde queries → Librarian.
- `roles.py` — `PerformanceScout._propose_from_gsc()`: GSC high_potential queries → Librarian.
  Publiceert `gsc_pulse_completed` zodat de demo op beide inwoners kan wachten.
- `roles.py` / `skills_impl/library_skills.py` — `Librarian` + `KeywordReviewSkill` ongewijzigd.
- `library.py` — `Library` slaat elke beslissing op in `data/library.json`.

Dedup-garantie: `lib.status(term) is not None` blokkeert hervoorstel voor ALLE statussen
(ook `escalated`). Beide bronnen controleren dit zelfstandig vóór ze publiceren.
Zelfversterkend: goedgekeurde woorden worden automatisch extra Trends-zaad.

GSC-token genereren (eenmalig, interactief):
```bash
./venv/bin/python -c "
from google_auth_oauthlib.flow import InstalledAppFlow
SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly']
flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
creds = flow.run_local_server(port=0)
open('gsc_token.json', 'w').write(creds.to_json())
"
```
Zet daarna `GSC_TOKEN_PATH=./gsc_token.json` en `GSC_SITE=sc-domain:jouwsite.nl` in `.env`.

## Roadmap (depth-first, niet breadth-first)

1. **Echte missie-redenering aanzetten** in de Field Note (zet een LLM-key in `.env`).
2. **Skills porten** uit de oude repo: GSC (`get_gsc_data.py`), Trustpilot (`trustpilot_agent.py`), Serpstat, en de SQLite-`repository.py` als opslaglaag.
3. **Volledige IDM-governance** (objectronde + de twee poorten).
4. **Web**: vervang de in-memory `EventBus` door een netwerk-bus (WebSocket/SSE) en de `Inbox` door een server-queue. Beide zitten al achter een interface.
5. **Mens in het dorp**: een `HumanProxy`-inwoner die taken naar een UI stuurt en op het antwoord-event wacht. Voor de rest van het dorp niet te onderscheiden van een agent.

Principe: maak eerst één inwoner één ding echt waardevol doen (de groei-puls is het sjabloon), bewijs de waarde, en schaal pas daarna in de breedte.

## Conventies

- Python 3.10+. `from __future__ import annotations` boven in modules.
- Dataclasses voor interne modellen; Pydantic mag voor ingest-data (zie oude `SeoOpportunity`).
- Nederlandse comments/logs zijn prima.
- Geen global mutable state. Alles wat een inwoner nodig heeft komt via de constructor (`bus`, `registry`, `context`).
