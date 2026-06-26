# Ontwerp — Inwoners (persona's): het karakter los van de rol

## Kern in één zin
Een **rol** is het *wat* (capaciteit), een **inwoner** is het *wie* (karakter); The Source koppelt ze.

## Waarom
In zuiver Holacracy vervullen mensen rollen, en is rol los van rolvervuller. NoochVille koos
één agent per rol (geen meerdere mensen per rol nodig). Maar een rolvervuller een karakter geven
is leuk én nuttig: de output van Trends mag anders klinken dan die van Harry. Dit ontwerp maakt
het karakter een eersteklas, herbruikbare entiteit los van de rol.

Het ruimt ook bestaande rommel op: `name` (rol-weergavenaam), `persona` (losse vervuller-naam) en
`held_by` (mens die zetelt) waren drie halve antwoorden op "wie zit in deze stoel?". De inwoner-
entiteit + koppeling vervangt de losse `persona`-string.

## De twee assen (houd ze gescheiden)
1. **Capaciteit (rol).** purpose, accountabilities, **skills (de rugzak)** — via governance,
   mens-gated. Wie de rol vervult erft het rugzakje. Skills horen bij de STOEL, niet bij de persoon.
   - "Onbemand" = de rol heeft geen code/skills om te kunnen werken (CLASS_MAP/registry).
2. **Personality (inwoner).** naam, MBTI, vrije instructies. Bepaalt HOE het werk klinkt, niet WAT.
   - "Geen inwoner" = de rol kan werken maar is gezichtloos (neutrale stem).

Skills koppelen we bewust NIET aan de inwoner: anders zou je iedereen alles geven en valt de
rol-afbakening (domeinen/accountabilities) weg, en omzeil je de mens-gated capaciteitsgrens.
Het karakter is draagbaar; het gereedschap hoort bij de stoel. Zelfde inwoner in een andere rol →
ander rugzakje, zonder duplicatie.

## Beslissingen (vastgelegd)
1. **Functioneel**, niet cosmetisch: MBTI + instructies worden in de LLM-prompts van de rol
   geïnjecteerd (work_one, project-replies, later Field Notes). De output klinkt echt anders.
2. **Veel-op-veel**: een inwoner is herbruikbaar en mag meerdere rollen vervullen (in de praktijk
   meestal 1:1). Eén rol heeft hooguit één toegewezen inwoner.
3. **Skills blijven op de rol.** De inwoner draagt puur personality.

## Datamodel
- `Persona` (code; gebruikersterm "inwoner") in `nooch_village/personas.py`,
  opslag `data/personas.json`: `{id, name, mbti, instructions}`.
  - NB: de naam `Inhabitant` is in code al de levende rol-agent (`inhabitant.py`); daarom heet de
    karakter-entiteit in code `Persona`.
- Koppeling: `Record.persona_id` (de toegewezen inwoner van een rol). `held_by` blijft apart voor
  een mens-zetel (bijv. The Source). De losse `persona`-string wordt afgebouwd t.g.v. `persona_id`.
- `persona_prompt(persona)` bouwt de preamble: "Je bent <naam> (<MBTI>). <instructies>. Laat dit
  doorklinken in toon en aanpak, niet in wat je inhoudelijk kunt."

## Wie koppelt
The Source (de mens) maakt inwoners aan (creator/lijst) en koppelt ze aan rollen. Dit is een
mens-handeling, geen autonome agent-actie (consistent met de capaciteitsgrens).

## Bouw in brokken (klein & toetsbaar)
1. Persona-store (`personas.py`) + `persona_prompt`. + tests.
2. Koppeling `Record.persona_id` + `Records.set_persona` + serialisatie. + tests.
3. Functionele injectie: `work_one(..., persona="")`; `work_projects` resolvet de inwoner. + tests.
4. CLI: inwoner aanmaken / lijst / koppelen aan rol.
5. Cockpit: inwoner in de roster (naam+MBTI) + de twee markeringen (onbemand = punt 3, geen-inwoner).
