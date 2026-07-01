# Ontwerp: Backlog Builder
*Vastgelegd 2026-07-01*

## Doel
Van chaos naar een gestructureerde, geprioriteerde en uitvoerbare backlog.
De backlog builder is de speciale Notes-functionaliteit van de Website Developer-rol.

## Twee domeinen
- **Website** — alles wat nooch.earth raakt
- **Village** — alles wat village.nooch.earth / NoochVille raakt

## Twee views
- **Inbrenger** (iedereen): formulier met vrije tekst + type + domein
- **Beheerder** (Website Developer-rolvervuller): volledig overzicht + beheer

## Flow van een item

### Staten
1. **Ruw** — ingebracht als vrije tekst
2. **Geformuleerd** — Noochie helpt scherp maken + acceptatiecriteria verplicht stellen
3. **Verkleind** — opgebroken in concrete acties (klein, specifiek, uitvoerbaar)
4. **Gegroepeerd** — gerelateerde acties worden één project
5. **Geprioriteerd** — impact/effort labels + relatieve prioriteit tussen projecten
6. **Uitgevoerd** — omgezet naar project op projectenbord Website Developer

### Types
- Bug
- Wens
- Idee

### Impact/effort conventie
`#impact:hoog/medium/laag #effort:1u/1d/2d/1w`

## Noochie — twee momenten

### Moment 1: bij de inbrenger (formulering)
Noochie stelt scherp:
- Wat wil je precies?
- Voor wie?
- Wat is het probleem dat je oplost?
- **Verplicht: hoe weet je dat dit af is?** (acceptatiecriteria / Definition of Done)

Output: goed geformuleerd item met type, domein en DoD.

### Moment 2: bij de Website Developer (verfijning + prioritering)
Noochie helpt:
- Is dit in één stap te doen? (actie) Of meerdere? (project)
- Wat is de impact op de gebruiker/organisatie?
- Wat is de effort-inschatting?
- Past dit bij de huidige strategische focus?

Output: geprioriteerd, planbaar item klaar voor het projectenbord.

## Integratie projectenbord
- Acties → direct uitvoerbaar, checklist-item of notitie op de rol
- Projecten → volwaardige projectkaart op het projectenbord van Website Developer
- Stakeholders → automatisch notificatie via bestaande rol-notificaties

## KPIs (volgende fase)
Data zit al in het projectenbord. Nog te bouwen als measures:
- Items per week afgerond (velocity)
- Gemiddelde doorlooptijd: idee → project → done
- Backlog-grootte per domein

## Latere lagen (na MVP)
- Noochie prioriteert op basis van strategie (nu: impact/effort handmatig)
- Intake via inbox of Telegram-koppeling (nu: directe link op rolpagina)
- Navigatie alleen uitgeklapte cirkels waar je rollen in vervult

## Bouwinstructies voor Claude Code (morgen)
- Locatie: speciale view op Website Developer-rol, vervangt huidige Notes-tab
- Autorisatie: AUTHZ: rolvervuller Website Developer = beheerder, iedereen-ingelogd = inbrenger
- Dataopslag: nieuw `data/backlog.json` (zelfde patroon als andere stores)
- Noochie-integratie: bestaande LLM-call hergebruiken, nieuwe prompts voor moment 1 en 2
- Projectenbord-integratie: bestaande `proj_add` dispatch-tak hergebruiken
