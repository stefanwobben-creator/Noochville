# CC-opdracht: inwoner-dossiers — persona als drager (personality + skills + tools + LLM)

**Voor:** Claude Code in de Noochville-repo, op een eigen branch (`inwoner-dossiers`), los van `claims-checker`.

**Doel in één zin:** maak de persona het dragende object van elke AI-inwoner — personality, skills, tools en LLM-voorkeuren in één dossier, zichtbaar en beheerbaar in cockpit 2, exporteerbaar als verkoopbaar pakketje — terwijl de rol (het mandaat) onaangetast bij governance blijft.

**Referentie-ontwerp (leidend voor de UI):** `docs/prototype_inwoners_index.html` + `docs/prototype_persona_*.html` (v3, met Tools-kaart). Billy Buzz is het maat-exemplaar. De prototypes zijn besproken en akkoord; wijk alleen af waar de code-werkelijkheid het afdwingt, en meld dat.

## Het model (de harde scheidslijn)

- **Rol** = mandaat: purpose, accountabilities, domeinen. Wijzigen kan alleen via governance (G0-G4). Blijft exact zoals nu.
- **Persona (inwoner)** = drager: personality (MBTI, instructies, prompt-extra), skills (wat hij kán), tools (de UI-schermen die bij hem horen), LLM-voorkeuren (default + per taak). Reist mee bij een zetelwissel.
- **Zetel** = de koppeling (assignments/persona_id), zoals nu.

GUARDRAIL: er komen NOOIT accountabilities, domeinen of mandaat-taal in de persona. Zodra dat gebeurt zijn er twee waarheden en is de poort een wassen neus.

## Wat er al staat

- `personas.py` — PersonaStore (id, name, mbti, instructions) + `persona_prompt` (kleurt de toon).
- `llm.py` — `reason(prompt, ladder=..., call_site=...)`: per-aanroep-ladder bestaat al; `llm_usage.jsonl` logt al per call_site.
- `assignments.py` + `persona_id` op records — zetels bestaan.
- `views/overview.py::_ROLE_TOOLS` — tools per eigenaar (nu rol-gekeyd).
- `skills.py` — Skill-ABC met `description` (basis voor mensentaal).
- `data/personas.json` — Billy (ISTP), Lara (ISTJ), Sid (INFP), Noochie (ENFJ, alleen MBTI), Wendy/Walter/Codie (leeg).

## Taak 1 — Persona-datamodel uitbreiden

Voeg aan Persona toe (alles optioneel, bestaande data blijft geldig):
- `avatar` (emoji), `prompt_extra` (string), `skills` (list[str], zie taak 4), `tools` (list[{label, desc, href}]),
- `llm` (dict: `{"default": "vendor:model", "per_taak": {"<call_site>": "vendor:model"}}`).

Migratie niet nodig (fail-soft lezen met `.get`). `persona_prompt` neemt `prompt_extra` mee (achter de bestaande instructies, gescheiden regel).

**Acceptatie:** bestaande personas.json laadt ongewijzigd; een persona mét nieuwe velden rendert en prompt.

## Taak 2 — LLM-resolutie per persona/taak

Bouw één helper (bv. `llm_voorkeur(context, role_id, call_site) -> str | None`) die de ladder bepaalt:
1. persona van de zittende inwoner → `llm.per_taak[call_site]`
2. anders persona → `llm.default`
3. anders `None` → `reason()` valt terug op de globale `LLM_LADDER` (huidig gedrag).

Bedraad hem MINIMAAL: kies de 3-5 call-sites waar dit nu waarde heeft (einddocument-synthese, grounding, triage) en geef daar `ladder=` mee; de rest blijft onaangeraakt. LIMITER/cooldowns blijven centraal en gedeeld — géén aparte throttles per persona.

**Acceptatie:** unit-test die de resolutie-volgorde bewijst (per_taak > default > globaal); zonder persona-velden identiek gedrag aan nu.

## Taak 3 — De twee schermen

**/inwoners** (ingang: Deelnemers-pagina): tabel van alle persona's — avatar, naam, MBTI, zetel(s), status (actief = had activiteit; concept = lege persona; motor = Facilitator). Zie index-prototype, maar ZONDER prijzen/pakket-kolom (dat is de externe catalogus, niet dit scherm).

**/inwoner?id=…** (ingang: /inwoners + de inwoner-chip op de rol-pagina): het dossier, per prototype v3:
- **Personality**: MBTI, instructies, prompt-extra — bewerkbaar (POST /action, bestaand patroon).
- **✨ Finetune met AI**: knop genereert via `llm.reason` twee alternatieven voor prompt-extra ("strakker" en "ruimer", elk ≤2 zinnen); mens kiest via radio + "gebruik selectie". Fail-closed: geen LLM-antwoord → nette melding, nooit een lege overschrijving. Elke wijziging logt oud→nieuw (append, bv. `persona_kroniek.jsonl`).
- **LLM-voorkeuren**: default + per-taak-tabel (bewerkbaar), plus 14-dagen-verbruik per call_site uit `llm_usage.jsonl` (echt, geen mock) en een budgetbalkje (config `persona_llm_budget_eur`, alleen visueel signaal, geen harde stop in deze fase).
- **Skills in mensentaal**: hoofdregel = omschrijving, technisch id klein eronder (taak 4).
- **Tools**: kaarten uit persona.tools; voor de bestaande inwoners seed je ze uit de huidige `_ROLE_TOOLS`-inhoud (Lara: Woordenschat, Kennisbank, Signals; Sid: Long-term trends; Billy: Keywords-analyse). `_ROLE_TOOLS` op de rol-Tools-tab blijft óók werken (geen regressie); dubbele bron is hier oké omdat de persona-tools het pakket-manifest zijn.
- **Zetels**: uitklapbaar (details/summary, eerste open) per rol: purpose + vereist-vs-gedekt-match + link naar de rol-pagina.
- **Recente activiteit**: laatste ~10 events van deze persona/rol uit `system_log.jsonl` (tail), met klikbare uitkomst-links waar een doel bestaat (inbox-item, project, note). Puur referentie; geen nieuwe stores.

Design: bestaand designsysteem (nooch.css / web_base), géén nieuwe inline styles (ratchets!), labels met for, geen nieuwe klasse-prefix-familie tenzij nodig (dan ratchet bijwerken met uitleg).

**Acceptatie:** beide routes renderen met echte data; render-tests voor dossier (secties aanwezig, read-only zonder csrf); ratchet-tests groen.

## Taak 4 — Skills: mensentaal + persona-metadata (NIET de uitvoering)

- Geef elke skill een NL-mensentaal-omschrijving (uitbreiden op de Skill-ABC of één centrale map `skill_labels.py`): "Luistert op Reddit, Bluesky en YouTube naar wat mensen echt zeggen" i.p.v. `community_listening`.
- Vul `persona.skills` voor de bestaande inwoners als KOPIE van de rol-DNA-skills van hun zetel (metadata, voor dossier + export).
- **Expliciet BUITEN scope:** `use_skill`/uitvoering blijft op rol-DNA draaien. Skills-bij-persona als uitvoeringsmodel is een aparte, latere brief (grote verschuiving door Reconciler/gates/tests). Zet een TODO-comment met verwijzing.

**Acceptatie:** dossier toont mensentaal; daemon-gedrag byte-voor-byte ongewijzigd (bestaande suite groen).

## Taak 5 — Pakket-export (het verkoopbare bestand)

- `python -m nooch_village.village inwoner_export <persona_id|naam>` → schrijft `<slug>.inwoner` (zip) met:
  `persona.json` (volledig dossier), `manifest.json` (versie, vereiste API-keys per skill, vereiste skills_impl-modules, tool-routes), en een `README.md` (autogen: wie is dit, wat kan hij, wat heeft hij nodig).
- `inwoner_install <pad.inwoner>` → importeert de persona (nieuw id bij botsing), toont wat er ontbreekt in deze village (skills_impl-modules / keys) — installeren van CODE doet hij NIET, alleen rapporteren. Fail-soft.
- GUARDRAIL: export bevat NOOIT secrets (.env-waarden, keys, tokens) en NOOIT organisatie-data (library, records, observations). Test dit expliciet.

**Acceptatie:** export van Billy → install in een lege test-village → dossier rendert daar met "ontbreekt: …"-melding voor de skills-modules; round-trip-test in de suite.

## Taak 6 — Kleine dingen

- Personality invullen voor Walter, Wendy, Codie kan de mens daarna zelf via het dossier — maar seed avatar-emoji's voor alle zeven (🐝📚🔬🌐🌱✍️💻; Rupert ⚖️ met kind="motor", geen LLM-blok).
- Noochie heeft twee zetels (noochie + circle_rep noochville) — het dossier moet meerdere zetels aankunnen.

## Volgorde & werkwijze

1 → 2 → 3 (dossier eerst read-only, dan de write-acties) → 4 → 5 → 6. Per taak: gerichte tests erbij, volle suite vóór elke merge. Prod-data (personas.json op de server) is levende state: alleen additieve velden, nooit een herschrijf-migratie. Rapporteer per taak kort wat je koos waar de brief ruimte laat.

## Config (defaults, alles optioneel)

`settings.ini`: `persona_llm_budget_eur = 5` (visueel), `persona_activity_tail = 10`.

## Guardrails (samengevat)

- Rol = governance, persona = drager. Geen mandaat in persona's.
- Uitvoering van skills verandert in deze brief NIET.
- Finetune is mens-gated: AI stelt voor, mens kiest, alles geborgd.
- Export zonder secrets en zonder organisatie-data.
- Ratchets en bestaande tests blijven groen; geen refactors buiten de taak.
