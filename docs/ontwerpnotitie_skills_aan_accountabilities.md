# Ontwerpnotitie: skills aan accountabilities (los van rollen)

**Status:** ontwerp, besproken met founder (beslissingen in §7-9 verwerkt), nog geen
bouwopdracht. Bedoeld als grondstof voor een latere cc-brief.
**Aanleiding:** de dialoog "AI op deze accountability" koppelt in de praktijk al een skill aan
één accountability, terwijl de uitvoering (`use_skill`) nog op rol-DNA draait. En hetzelfde
gereedschap zit dubbel in rol-DNA's (voorbeeld: `keywords_everywhere` bij zowel Lara/Librarian
als Billy/Buzz). De vraag: kunnen we de skill loskoppelen van de rol en aan de accountability
hangen, zodat meerdere rollen één dorpsmiddel delen?

---

## 1. Het model: drie lagen

**Laag 1 — Accountability = de belofte.** Tekst in het rol-record, onderdeel van het mandaat.
Wijzigen kan alleen via governance (G0-G4). Dit verandert NIET.

**Laag 2 — Skill = gedeeld dorpsmiddel.** Een capability in de registry
(`skills_impl/…`, mensentaal via `skill_labels.py`) is van het dorp, niet van een rol.
Eén implementatie, één API-key, één limiter — hoeveel rollen hem ook gebruiken.

**Laag 3 — Koppeling = operationeel.** "Deze accountability wordt (mede) waargemaakt met dit
middel" is een operationele uitspraak: omkeerbaar, zonder mandaat-gevolgen, dus zonder
G-ronde. De Circle Lead legt hem, de kroniek logt hem, en hij is per direct weer weg te halen.

### De twee snelheden (de guardrail)

De belofte beweegt op governance-snelheid (traag, geborgd, G0-G4). Het middel beweegt op
operationele snelheid (snel, omkeerbaar, gelogd). Zodra een koppeling de *tekst* van een
accountability zou moeten veranderen, is het geen koppeling meer maar een governance-voorstel.
Die grens hard bewaken, anders ontstaan er twee waarheden — dezelfde valkuil als
mandaat-taal in persona's.

---

## 2. Wat er vandaag staat (code-werkelijkheid)

- `models.py::RoleDefinition.skills: list[str]` — skills zitten in rol-DNA; grants lopen via
  governance (`GovernanceChange.add_skills/remove_skills`, toegepast in `governance.py` ±r361).
- `inhabitant.py::handle()` en `use_skill()` poorten op `self.dna.skills`; de
  dode-capability-audit (`referenced_capabilities` / `dormant_capabilities`) leest letterlijke
  `use_skill("…")`-aanroepen uit de klasse-broncode en vergelijkt met rol-DNA.
- `governance.py::Reconciler._materialize` gebruikt rol-skills óók als levensteken: een rol
  zonder CLASS_MAP-entry én zonder actieve skill in de registry blijft "onbemand".
- `gap_classifier.py` rekent de middelen-overlap (A vs B) op `_skill_tokens(skills)` uit
  het rol-DNA.
- `ai_tasks.py::AITask(role, acc_index, agent, wat)` — de koppeling op accountability-niveau
  bestaat al als datamodel (de dialoog uit de screenshot), maar hangt aan de *index* van de
  accountability binnen de rol.
- `seeds.py` (±r269) duwt `keywords_everywhere` per migratie in het Librarian-DNA; Billy heeft
  hem ook — de dubbeling die deze notitie wil oplossen.
- Persona's (`inwoner-dossiers`) dragen `persona.skills` als metadata-kopie voor dossier en
  export — een derde plek waar skills genoemd worden.

Kortom: de uitvoeringswaarheid is rol-DNA, maar de *bedoeling* (dit middel dient die belofte)
wordt al op accountability-niveau vastgelegd. Deze notitie maakt van die bedoeling de waarheid.

## 3. Waarom index-koppeling eerst gerepareerd moet worden (fase 0)

`AITask.acc_index` is de positie van de accountability in de lijst. Een governance-ronde die
een accountability toevoegt, verwijdert of herformuleert verschuift indices — en dan wijzen
bestaande koppelingen stilletjes naar de verkeerde belofte. Vóór alles: geef accountabilities
een stabiel id (bv. hash van rol-id + oorspronkelijke tekst, of een uuid bij aanmaak, fail-soft
migratie: bestaande teksten krijgen bij eerste load een id). Koppelingen verwijzen daarna naar
`acc_id`, nooit meer naar index. Dit is een kleine, zelfstandige stap met eigen tests — en hij
repareert een bestaande fragiliteit los van de rest.

## 4. De koppelingslaag

Nieuw (of uitgebreid vanuit `AITaskStore`): `data/skill_links.json` met
`{id, acc_id, skill, agent?, wat?, gelegd_door, gelegd_op}`. Verschil met AITask: AITask zegt
"deze AI doet dit autonoom binnen die accountability"; de skill-link zegt "dit dorpsmiddel is
beschikbaar voor die belofte". Ze kunnen samenvallen (één store met een `kind`-veld) of naast
elkaar leven — samenvallen heeft de voorkeur, want de dialoog uit de screenshot is dan meteen
de beheer-UI: één plek waar de Circle Lead middel én autonomie regelt.

De effectieve skillset van een rol wordt dan afgeleid:

```
effectief(rol) = rol.definition.skills  ∪  {link.skill voor elke link op een acc van rol}
```

Tijdens de migratie is rol-DNA de vloer (niets breekt), de links zijn de plus. Eindbeeld:
rol-DNA-skills leeg, alles via links.

## 5. Wat er geraakt wordt (de vier lezers van rol-skills)

1. **`use_skill`/`handle`** — poort verandert van `capability in self.dna.skills` naar
   `capability in effectief(rol)`. De dode-capability-audit idem: een aanroep is pas "dood"
   als hij noch in DNA noch in een link zit. De waarschuwingstekst ("Grant via governance…")
   krijgt een tweede route: "…of leg een koppeling op de accountability".
2. **Reconciler (onbemand-check)** — het levensteken "heeft actieve skills" moet de afgeleide
   set lezen, anders blijft een rol die alléén via links werkt onterecht onbemand.
3. **Gap-classifier (means-gap A/B)** — `_skill_tokens` voedt zich met de afgeleide set. Let op
   de bijwerking: middelen die via een link gedeeld worden tellen dan bij méér rollen mee, dus
   B-gaps ("mandaat wel, middel niet") worden zeldzamer. Dat is de bedoeling, maar de
   drempelwaarden (`MEANS_THRESHOLD`) verdienen daarna een herijking op echte data.
4. **Gate- en ratchet-tests** — alle tests die `add_skills`-governance of DNA-membership
   aannemen krijgen een tweede pad. De poort blijft bestaan (géén skill zonder DNA óf link),
   dus de fail-closed-filosofie blijft overeind; er komt alleen een tweede sleutel bij.

Buiten schot: LIMITER/cooldowns (blijven centraal per skill, juist makkelijker als het middel
van het dorp is), persona's (`persona.skills` blijft metadata; de export-manifest leest voortaan
de links van de zetel in plaats van het rol-DNA — zelfde informatie, eerlijker bron).

## 6. Migratiepad (elke fase zelfstandig leverbaar, suite groen per fase)

- **Fase 0 — stabiele acc-ids.** Zie §3. Geen gedragswijziging, wel tests op herordening.
- **Fase 1 — additief.** Store + UI (bestaande dialoog uitbreiden), links puur als metadata en
  weergave (rol-pagina toont per accountability de middelen; dossier en export lezen mee).
  Plus de skills-catalogus (§9) en de secretaris-check in de gate (§8), beide leeswerk.
  Uitvoering ongewijzigd; byte-voor-byte hetzelfde daemongedrag.
- **Fase 2 — de poort om.** `effectief(rol)` wordt de uitvoeringswaarheid in use_skill/handle,
  audit, Reconciler en gap-classifier. Feature-vlag (`skill_links_active = 0|1`, default 0)
  zodat prod pas omgaat als de logs schoon zijn.
- **Fase 3 — opdrogen.** Bestaande DNA-skills per rol omzetten naar links op de best passende
  accountability (voorstel per rol, mens keurt), daarna `remove_skills` via de normale
  governance-ronde. De dubbeling (keywords_everywhere ×2) verdwijnt hier vanzelf: één middel,
  twee links.

## 7. Beslissingen uit het gesprek (founder, 2026-07-18)

**7a. Passendheid als criterium; de domeinhouder beslist, anderen suggereren.**
Het criterium is: past het middel bij de verantwoordelijkheid van de rol, dan mag hij het
gebruiken om die verantwoordelijkheid waar te maken. Geen algemene domein-check dus.
Maar de domeinregel is absoluut: BESLISSEN in een domein kan alleen de domeinhouder
(voorbeeld: alleen Lara keurt woorden goed of verbiedt ze in "bibliotheek"). Er komt géén
policy-route die dat omzeilt. Wat andere rollen krijgen is de suggestie-variant, naar het
patroon dat al draait: Billy en Sid nomineren kernwoorden, de nominatie landt in de wachtrij,
Lara beslist. Praktisch: elke domein-schrijvende skill splitst in twee capabilities:

- de **beslis-skill** (bv. `library_curate`), registry-veld `schrijft_in_domein: "bibliotheek"`;
  alléén koppelbaar aan een rol die dat domein zelf heeft. De koppel-UI biedt hem bij andere
  rollen niet eens aan; de poort in `use_skill` weigert hem fail-closed.
- de **suggestie-skill** (bv. `keyword_nominatie`), vrij koppelbaar op passendheid; de output
  landt altijd in de wachtrij van de domeinhouder, nooit direct in de data.

Lees-skills en externe-data-skills zijn vrij koppelbaar op passendheid.

**7b. Circle Lead legt de link; policy als opschaalroute.**
De Circle Lead gaat over middelen en legt de koppeling (consistent met de bestaande
autorisatie op AI-taken). Op termijn kan de Circle Lead per cirkel een policy schrijven die
vastlegt hoe een rol zélf directe toegang tot een middel krijgt (bv. "lees-skills en
suggestie-skills mag een rolhouder zelf koppelen op eigen accountabilities"). De policy is de
gedelegeerde bevoegdheid; zonder policy blijft het Circle Lead-werk. NB: een policy kan alleen
het KOPPELEN delegeren, nooit de domeinregel uit 7a opheffen; beslis-skills blijven exclusief
bij de domeinhouder.

**7c. `add_skills` in governance blijft bestaan** voor middelen met mandaat-gewicht, maar wordt
de uitzondering. De registry markeert die expliciet (zelfde veld als 7a of een `zwaar`-vlag).

## 8. Secretaris-check: uitvoerbaarheid tijdens het roloverleg

Wens: tijdens een governance-ronde moet de Secretaris dynamisch kunnen toetsen of een
voorgestelde accountability uitvoerbaar is. De bouwsteen bestaat al: `gap_classifier.py`
klasseert een tekst tegen mandaat en middelen als A/B/C. Hang die live in het gate-scherm:
bij elke voorgestelde (nieuwe of gewijzigde) accountability toont de gate direct een stoplicht:

- **groen** — er is een gekoppeld of in-DNA aanwezig middel dat de tekst dekt (A);
- **oranje** — het middel bestaat in het dorp (registry) maar is nog niet aan deze rol
  gekoppeld: één klik voor de Circle Lead, meteen vanuit het gate-scherm (B, oplosbaar);
- **rood** — geen enkele bestaande skill dekt dit: dit wordt een means-gap in de inbox of een
  bouwverzoek voor nieuwe tooling (B/C, niet oplosbaar met wat er is).

Puur informatief in de gate (de mens beslist, zoals altijd); geen blokkade. Dit hergebruikt de
bestaande drempelwaarden en wordt beter naarmate de koppelingslaag (fase 1-2) de echte
middelenverdeling weerspiegelt.

## 9. Skills-catalogus: wat kan al, waarvoor moet tooling komen

Eén overzichtspagina (bv. `/skills`) uit bestaande data, drie kolommen kennis:

1. **Uitvoerbaar** — skills met een implementatie in de registry (`registry.get` ≠ None), met
   mensentaal-label uit `skill_labels.py`, en per skill: welke rollen/accountabilities hem
   gebruiken (DNA + links) en of hij een API-key nodig heeft.
2. **Genoemd maar niet gedekt** — skills die in rol-DNA of links staan zonder implementatie,
   plus de dode-capability-audit (`dormant_capabilities`): aangeroepen in code zonder grant.
3. **Gewenst** — rode uitkomsten uit de secretaris-check (§8) en means-gaps uit de inbox:
   de bouwlijst voor nieuwe tooling.

Dit scherm is ook de natuurlijke plek voor de `schrijft_in_domein`- en `zwaar`-markeringen
uit §7, en toont per beslis-skill welke suggestie-tegenhanger erbij hoort. Grotendeels
leeswerk op bestaande stores; kan al in fase 1 mee.
