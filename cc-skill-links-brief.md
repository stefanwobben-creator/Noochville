# CC-opdracht: skill-links — middelen aan accountabilities, los van rollen

**Voor:** Claude Code in de Noochville-repo, eigen branch (`skill-links`), los van lopende branches.
**Ontwerp:** `docs/ontwerpnotitie_skills_aan_accountabilities.md` is leidend en met de founder
besproken. Wijk alleen af waar de code-werkelijkheid het afdwingt, en meld dat.

**Doel in één zin:** skills worden gedeelde dorpsmiddelen die via een operationele koppeling aan
accountabilities hangen (Circle Lead legt, kroniek logt, per direct omkeerbaar), terwijl de
accountability zelf op governance-snelheid blijft (G0-G4) en de domeinregel absoluut blijft:
beslissen kan alleen de domeinhouder, andere rollen suggereren.

## Het model (de harde scheidslijnen)

- **Accountability = belofte.** Tekst in het rol-record, alleen wijzigbaar via governance. Raakt
  deze brief NIET aan.
- **Skill = gedeeld dorpsmiddel.** Eén implementatie, één key, één limiter, hoeveel rollen hem
  ook gebruiken.
- **Koppeling = operationeel.** "Dit middel dient die belofte": omkeerbaar, gelogd, geen G-ronde.
- **Domeinregel (absoluut, geen policy-omweg):** een skill die BESLIST in een domein
  (bv. `library_curate` in "bibliotheek") is alléén koppelbaar aan een rol die dat domein zelf
  heeft. Andere rollen krijgen hooguit de suggestie-variant, waarvan de output in de wachtrij
  van de domeinhouder landt (patroon: Billy/Sid nomineren, Lara beslist).

## Wat er al staat

- `models.py::RoleDefinition.skills` — rol-DNA; grants via `GovernanceChange.add_skills/remove_skills`.
- `inhabitant.py` — `handle()`/`use_skill()` poorten op `dna.skills`; dode-capability-audit
  (`referenced_capabilities`/`dormant_capabilities`).
- `governance.py::Reconciler._materialize` — gebruikt rol-skills mede als levensteken (onbemand-check).
- `gap_classifier.py` — A/B/C-classificatie op `_skill_tokens(skills)`; pure functie, geen I/O.
- `ai_tasks.py::AITask(role, acc_index, agent, wat)` + de dialoog "AI op deze accountability"
  in cockpit2 (`_act_aitask_add`, autorisatie: Circle Lead) — de kiem van de koppelingslaag,
  maar hangt aan de accountability-INDEX (fragiel, zie taak 0).
- `skill_labels.py` — mensentaal per skill; registry (`registry_factory.py`) weet wat echt
  geïmplementeerd is.
- Bekende dubbeling: `keywords_everywhere` in het DNA van librarian (seeds-migratie ±r269) én
  van billy — de testcase voor het eindbeeld "één middel, twee links".

## Taak 0 — Stabiele accountability-ids (zelfstandige reparatie, eerst)

- Geef elke accountability een stabiel `acc_id` (uuid bij aanmaak; bestaande teksten krijgen er
  fail-soft één bij eerste load, records-migratie idempotent). Governance-wijzigingen aan de
  tekst behouden het id; toevoegen maakt een nieuw id; verwijderen laat andere ids ongemoeid.
- Migreer `AITask.acc_index` → `acc_id` (fail-soft: bestaande taken krijgen het id van de
  accountability die nu op hun index staat; daarna is index dood).
- **Acceptatie:** test die een accountability-herordening/verwijdering doet en bewijst dat
  bestaande AI-taken aan de JUISTE accountability blijven hangen (dat faalt op main nu).

## Taak 1 — Koppelingslaag: store + UI (additief, uitvoering ongewijzigd)

- Breid `AITaskStore` uit tot één koppelingsstore (`data/ai_tasks.json` blijft de opslag,
  additief veld `kind`: `"autonoom"` (bestaand, default bij lezen) of `"middel"`), of leg een
  parallel `skill_links.json` aan als dat schoner blijkt — kies en motiveer. Velden per link:
  `{id, acc_id, skill, wat?, gelegd_door, gelegd_op}`.
- De bestaande dialoog op de rol-pagina wordt de beheer-UI: Circle Lead koppelt daar middel én
  autonomie (zelfde autorisatie als nu). Elke leg/verwijder-actie append-logt (bv.
  `skill_links_kroniek.jsonl` of de bestaande kroniek-conventie).
- **Domeinpoort in de UI:** skills met `schrijft_in_domein` (taak 2) verschijnen alleen in de
  picker bij rollen die dat domein hebben. Geen uitzonderingsroute.
- Rol-pagina toont per accountability de gekoppelde middelen (mensentaal-label, technisch id
  klein); inwoner-dossier en pakket-export lezen de links van de zetel mee als bron naast
  rol-DNA.
- Afgeleide helper: `effectief(rol) = dna.skills ∪ {link.skill voor links op acc's van rol}` —
  in deze taak alléén voor weergave, NIET voor uitvoering.
- **Acceptatie:** koppelen/ontkoppelen werkt en logt; domein-skill niet aanbiedbaar bij
  niet-domeinhouder; daemongedrag byte-voor-byte ongewijzigd (volle suite groen zonder
  gedragswijziging); ratchets groen.

## Taak 2 — Registry-metadata + skills-catalogus (/skills)

- Registry/Skill-metadata (additief, fail-soft): `schrijft_in_domein: str|None`,
  `zwaar: bool` (governance blijft de grant-route), `suggestie_van: str|None` (deze skill is
  de suggestie-tegenhanger van die beslis-skill). Vul minimaal in voor de bestaande skills:
  `library_curate`/`keyword_review` → `schrijft_in_domein="bibliotheek"`; de bestaande
  nominatie-route als suggestie-tegenhanger.
- Pagina `/skills` (cockpit2, bestaand designsysteem, geen inline styles), drie blokken:
  1. **Uitvoerbaar** — registry-skills met implementatie: mensentaal, key-vereiste, welke
     rollen/accountabilities (DNA + links) hem gebruiken, domein/zwaar-markering.
  2. **Genoemd maar niet gedekt** — in DNA of links zonder implementatie, plus de
     dode-capability-audit (aangeroepen zonder grant).
  3. **Gewenst** — means-gaps uit de inbox + rode uitkomsten van de secretaris-check (taak 3):
     de bouwlijst voor nieuwe tooling.
- **Acceptatie:** pagina rendert met echte data; render-test; de founder kan in één oogopslag
  zien wat al kan en waarvoor tooling moet komen.

## Taak 3 — Secretaris-check: uitvoerbaarheids-stoplicht in de gate

- In het gate-scherm, bij elke voorgestelde nieuwe/gewijzigde accountability, live een
  classificatie via `gap_classifier` tegen `effectief(rol)` + registry:
  **groen** = middel aanwezig/gekoppeld (A); **oranje** = middel bestaat in het dorp maar is
  niet aan deze rol gekoppeld, toon een koppel-knop voor de Circle Lead (respecteert de
  domeinpoort); **rood** = geen bestaande skill dekt dit → knop "meld als means-gap"
  (bestaande inbox-route).
- Puur informatief: de gate blokkeert er NIET op, de mens beslist zoals altijd.
- **Acceptatie:** drie testgevallen (A/B/C) renderen de juiste kleur; koppel-knop legt een
  echte link; gate-gedrag verder ongewijzigd.

## Taak 4 — De poort om (achter een vlag)

- Config-vlag `skill_links_active = 0|1` (settings.ini, default 0). Bij 1:
  - `use_skill`/`handle` poorten op `effectief(rol)`; de dode-capability-waarschuwing noemt
    beide routes ("grant via governance óf koppel op de accountability") en telt links mee.
  - Extra fail-closed check onafhankelijk van de vlag-stand: een `schrijft_in_domein`-skill
    weigert uitvoering voor een rol zonder dat domein, óók als hij per ongeluk in DNA of links
    staat (verdediging in de diepte).
  - Reconciler's onbemand-check en `gap_classifier`-aanroepen lezen `effectief(rol)`.
- Bij 0: gedrag identiek aan vandaag (bewijs met de bestaande suite).
- **Acceptatie:** unit-tests voor de poort in beide vlag-standen; domein-weigering getest;
  bestaande suite groen met vlag uit én aan.

## Taak 5 — Opdrogen (mens-gated, pas na vertrouwen op prod)

- CLI `python -m nooch_village.village skills_naar_links --dry-run`: stel per rol voor welke
  DNA-skill naar welke accountability-link verhuist (beste tekst-match, mensentaal-rapport).
  De echte run maakt de links; het VERWIJDEREN uit rol-DNA gaat daarna via de normale
  governance-ronde (`remove_skills`), niet via dit commando.
- De dubbeling `keywords_everywhere` (librarian + billy) is de acceptatie-case: één middel,
  twee links, DNA leeg op dit punt.
- **Acceptatie:** dry-run-rapport klopt; run is idempotent; geen governance-bypass.

## Volgorde & werkwijze

0 → 1 → 2 → 3 → 4 → 5, per taak gerichte tests + volle suite groen vóór elke merge. Taak 5
alleen voorbereiden (CLI + tests); de echte prod-run doet de founder zelf na een dry-run.
Prod-data (`records.json`, `ai_tasks.json` op de server) is levende state: alleen additieve,
idempotente migraties met backup, nooit een herschrijf. Rapporteer per taak kort wat je koos
waar de brief ruimte laat.

## Config (defaults)

`settings.ini`: `skill_links_active = 0`.

## Guardrails (samengevat)

- De domeinregel is absoluut: beslis-skills alleen bij de domeinhouder, geen policy-omweg;
  suggestie-output altijd via de wachtrij van de domeinhouder.
- Twee snelheden: de accountability-TEKST verandert nooit door een koppeling; zodra dat nodig
  lijkt is het een governance-voorstel.
- Fail-closed overal: onbekende skill, ontbrekend domein, lege registry → weigeren met een
  luide logregel, nooit stil doorlaten.
- LIMITER/cooldowns blijven centraal per skill; geen per-rol- of per-link-throttles.
- Persona's blijven metadata-dragers; geen mandaat- of grant-logica in persona's.
- Ratchets en bestaande tests groen; geen refactors buiten de taak; secretaris-check en
  catalogus zijn leeswerk plus één koppel-actie, geen nieuwe schrijfpaden buiten de store.
