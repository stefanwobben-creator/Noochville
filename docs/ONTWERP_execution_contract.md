# Execution Contract — AI-rollen in NoochVille

## Het model

AI-rollen werken via **pull, niet push**.
Trigger = project op het projectenbord.

Een rol doet geen werk tenzij er een project aan hem is toegewezen. Er is geen automatische
agenda, geen cron-job per rol, geen "ga maar iets nuttigs doen". De intentie van de mens
(via het projectenbord) is de enige energiebron voor operationeel werk.

Uitzondering: **pulsen** (tijdgebonden checks zoals GSC, ngram, Plausible) blijven
event-driven via de village-hartslag. Die zijn de ogen en oren van het dorp, geen
projectwerk.

---

## Twee staten per rol

### Staat 1: Kan leveren

De rol heeft een project toegewezen, zijn skills zijn beschikbaar, en hij kan autonoom
uitvoeren. Output: een update op het project, een Field Note, een keyword-voorstel,
een spanning via Noochie.

### Staat 2: Kan niet leveren — spanning via Noochie

De rol signaleert een blokkade:
- Skill ontbreekt of faalt (API down, token verlopen, geen data)
- Scope buiten eigen accountabilities
- Beslissing vereist van mens (policy-grens, missie-twijfel)

In staat 2 **doet de rol niets zelf**. Hij deponeert een spanning bij Noochie.
Noochie vertaalt de spanning naar een bulletin of governance-voorstel en escaleert naar
de Circle Lead (Stefan).

Rollen verzinnen geen output als ze vastziten. Ze stoppen en melden.

---

## Wie mag projecten toevoegen

| Wie | Hoe |
|-----|-----|
| **Circle Lead (Stefan)** | Direct via cockpit — geen goedkeuring nodig |
| **Medevervuller (mens)** | Direct via cockpit — binnen de rol waarvoor hij is toegewezen |
| **Rol zelf als voorstel** | Via spanning → Noochie → Circle Lead → goedkeuring vereist |

Een AI-rol mag nooit zichzelf een project toewijzen zonder menselijke goedkeuring.
De grens: een rol *mag* een voorstel formuleren ("ik denk dat dit project zinvol is"),
maar de mens beslist of het op het bord komt.

---

## Skill-rol koppeling (nog te bouwen)

Elke rol heeft een `skills`-lijst in zijn governance-record. Pas als een skill geregistreerd
is in de `SkillRegistry` én de rol hem in zijn DNA heeft, mag hij hem aanroepen.

Huidige rollen en hun beoogde skills (deels nog te registreren):

| Rol | Huidige skills | Beoogd |
|-----|---------------|--------|
| Scientist (harry_hemp) | ngram_culture | + recente corpus (post-2019) |
| Library (librarian) | keyword_review | + bibliotheek-export |
| Website Watcher | site_health, plausible_stats, google_trends, field_note | serpapi_trends (pending governance) |
| Trends & Competition | google_trends, gsc_performance | + competitor tracking |
| Coder | — | code_review, deploy, test_runner |
| Copywriter | — | content_draft, tone_check |
| Noochie | field_note | + bulletin_schrijven |

Een rol die een skill claimt maar hem niet heeft geregistreerd → staat 2 (kan niet leveren).

---

## Noochie als verbindingspersoon

Noochie is de Circle Rep van Noochville: spanningen uit het dorp gaan via hem naar de
Nooch-cirkel en uiteindelijk naar Stefan.

Noochie heeft drie taken:
1. **Vertalen** — technische blokkades omzetten naar begrijpelijke bulletins voor Stefan
2. **Prioriteren** — niet elke spanning is even urgent; Noochie filtert ruis
3. **Bewaken** — hij houdt bij welke spanningen open staan en herinnert de Circle Lead eraan

Noochie is ook het gezicht van het dorp naar buiten: de dagelijkse Field Note draagt zijn
stem, ook als de inhoud van andere rollen komt.

---

## Transparantie en monitoring

Alle output van AI-rollen is zichtbaar in de cockpit (`https://village.nooch.earth`):

| Wat | Waar |
|-----|------|
| Projecten per rol | Cockpit → rol → projecttab |
| Spanningen en escalaties | Human inbox (`python -m nooch_village.inbox`) |
| Dagelijkse Field Note | `data/output/field_note_<datum>.md` |
| Audit trail | `data/system_log.jsonl` |
| Pulse history | `data/pulse_history.jsonl` |
| Groeidagboek | `data/groeidagboek.jsonl` |

Rollen loggen hun eigen werk niet naar een apart kanaal. Wat niet in het audit trail staat,
is niet gebeurd.

---

## Wat dit contract niet regelt

- **Hoe een skill technisch werkt** — dat staat in `skills_impl/`
- **Governance-proces** — dat staat in `CLAUDE.md` onder "Governance"
- **Deployment en server** — dat staat in `deploy/README.md`
- **Roadmap** — dat staat in `docs/STATE.md`
