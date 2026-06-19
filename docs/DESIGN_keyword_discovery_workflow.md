# NoochVille: Design-notitie — keyword-discovery workflow (rol: scout) — 2026-06-19

*Design-first, geen implementatie. Dit borgt de methodologie zodat we 'm niet elke keer opnieuw beslissen. Het is het anker dat scout volgt en dat we reviewen vóór we bouwen. Spelregels gerespecteerd: skills mechanisch, oordeel bij de rol; capaciteit en credits mens-gated; scope-first, geen overproductie.*

---

## 1. Waarom deze notitie

De keuze "kwalificator-frases, niet losse kopwoorden; doorpakken naar long-tail; cli voor onze markten" mag geen ad-hoc beslissing per sessie zijn. Hij hoort geborgd: als methodologie bij scout, als herhaalbare pijplijn in het dorp, met de credit-rem op de juiste plek, en met een persistente landing in de library.

## 2. Splitsing: skill vs rol (hard)

De `keywords_everywhere`-skill blijft dom: hij haalt data op voor de keywords die hij krijgt, niets meer. De methodologie (welke termen, welke taal, welke data_source, welke seeds) is óórdeel en woont bij scout, niet in de skill. Strategie in de skill zou de lijn "skills mechanisch, rollen dragen oordeel" breken.

## 3. De pijplijn

1. **Seed** — trends/GSC pikken een kandidaat op (een stijgende term in trends, of een organisch binnenkomende term in GSC). Gratis, bestaande sensing.
2. **Uitbreiden** — scout bouwt uit de seed een kandidaten-matrix (zie §5). Gratis, deterministisch.
3. **Meten** — scout draait `keywords_everywhere` op de gecureerde batch. Dít is de betaalde stap, en de enige die door een gate moet (§7).
4. **Borgen** — scout schrijft de gemeten termen naar de library met status `onderzoeken` (operationeel, geen governance-gate, zie §4).
5. **Beoordelen** — de Librarian reviewt (LLM-oordeel): rijpe termen worden gepromoot naar `klaar voor creatie`, twijfelgevallen afgewezen of geëscaleerd.
6. **Terugkoppelen** — een Field Note vat de ronde samen: verbruikte credits, top-bevindingen, en welke termen nu `klaar voor creatie` staan.

Stappen 1, 2, 4, 6 mogen autonoom. Stap 3 is gegate (credits). Stap 5 is de Librarian's fuzzy judgment.

## 4. Koppeling naar de library (status-levenscyclus)

Gevalideerde keyword-data is geen wegwerp-tabel; ze voedt de library (de woordenschat), persistent. Elke term draagt een status die z'n plek in de levenscyclus toont:

- **onderzoeken** — kandidaat: seed binnen en gemeten, maar nog niet beoordeeld als de moeite waard. Scout zet 'm hier neer na de meting.
- **klaar voor creatie** — gevalideerd: reëel volume, on-brand, in een prioriteitsmarkt. Klaar om content voor te schrijven.

De overgang `onderzoeken` -> `klaar voor creatie` is een óórdeel (past de term bij Nooch's stem en strategie, niet alleen "heeft volume"). Dat oordeel is de Librarian's werk, niet scout's: scout brengt de data, de Librarian beslist of de term rijp is. Dit is precies de fuzzy-judgment-plek waar LLM is toegestaan.

Library-schrijfacties en statusovergangen zijn operationeel en omkeerbaar, dus ze gaan NIET door de governance-gate (consistent met de bestaande regel: keyword-beslissingen zijn operationeel, niet structureel). Downstream put content-creatie uit `klaar voor creatie`: de status is de brug tussen onderzoek en productie.

## 5. Kandidaat-generatie-regel

**Nooit losse kopwoorden** ("schoenen", "shoes", "schuhe", "sneakers"). Vanity-volume: generiek, niet te winnen, off-intent. De kwalificator is het hele punt, die filtert de zoeker tot Nooch's klant.

**Matrix = kwalificator x categorie-woord x (modifier).**

- Kwalificatoren (v1): vegan / duurzaam / nachhaltig / sustainable / plastic free / plasticvrij / plastikfrei / leather free / leervrij / lederfrei.
- Categorie-woorden: schoenen / shoes / schuhe / skor, sneakers / sneaker.
- Modifiers (de long-tail): geslacht (dames/heren/damen/herren), type (running, work), kleur, gebruik.

**Trapsgewijs:** eerst twee woorden (kwalificator + categorie), dan drie tot vier (+ modifier) als de twee-woord-term volume toont. De long-tail is waar een klein merk wint: lage competitie, hoge intentie, en precies wat cli wél ziet.

**Taal per markt:** NL -> Nederlands + Engels; DACH -> Duits (+ Engels); UK -> Engels; Nordics -> Engels (+ lokale probe).

**Data source:** `cli` (clickstream) als default voor onze markten, want GKP is blind voor lokale talen en long-tail (bewezen: NL/DE vol=0 op gkp, reële volumes op cli). `gkp` alleen als cross-check op Engelse kop-termen.

## 6. Lezen van de resultaten (fit-check-heuristieken)

- `vol=0` op GKP betekent niet "geen vraag", het betekent "GKP rapporteert het niet". Check cli.
- Identieke getallen over meerdere landen = een gepoolde (Engelstalige) waarde, geen vraag-per-land. Niet als afzonderlijke landvraag lezen.
- `competition` is adverteerder-competitie (betaald), GEEN organische SEO-moeilijkheid. Laag = weinig adverteerders, niet "makkelijk te ranken".
- "sustainable / nachhaltig / duurzaam" heeft lagere adverteerder-competitie dan "vegan", én is meer Nooch's hoek. Positioneringssignaal: minder volgevochten, on-brand.
- cli-cijfers zijn panel-extrapolaties: richtinggevend, niet precies.

## 7. Cadans & gating (de twee fasen)

**Fase A (nu): voorstellen-dan-goedkeuren.** Scout senset een seed, cureert een batch, en legt voor: subject + de termen + geschatte credits ("vegan stijgt, ik wil deze 40 termen op cli, ~40 credits"). Human zegt go, scout draait, resultaat als Field Note. On-demand, mens-gated. Dit respecteert §8 van de skill-spec.

**Fase B (later, verdiend): begrensde weekautonomie.** Scout draait zelf wekelijks een batch binnen een hárde creditcap, gecureerd uit echte signalen. Bewuste versoepeling.
- **Voorwaarde 1:** de budget/cost-gate (nu "genoteerd-niet-gebouwd") bestaat en dwingt de cap af.
- **Voorwaarde 2:** scout's curatie is in fase A bewezen goed (stelde batches voor die je tóch had goedgekeurd).

Autonomie wordt verdiend, niet gegeven, identiek aan "rollen geboren op afroep, mens-gated".

## 8. Markt-context (waarom dit telt)

Prioriteit: NL > DACH > UK > Nordics. Content/brand/klantcomm overal hoofdzakelijk Engels. De data legt een spanning bloot: de top-twee markten zoeken juist in hún taal (vegane schuhe DE = 48k, vegan schoenen NL = 3,4k), terwijl Engelse content vooral de Engelstalige pool bedient (= UK, prioriteit 3). De workflow moet die lokale vraag zichtbaar maken zodat de content-keuze op data rust, niet op gevoel.

## 9. Harde regels (borging)

1. Skill mechanisch; methodologie bij scout.
2. `keywords_everywhere` nooit in de dagpuls.
3. De betaalde call loopt altijd door een gate: fase A = mens, fase B = harde creditcap. Nooit ongebreideld.
4. `cli` default voor NL/DACH/Nordics; `gkp` alleen Engelse cross-check.
5. Losse kopwoorden niet meten.
6. Library-schrijven en statusovergangen zijn operationeel en reversibel: buiten de governance-gate.
7. De promotie `onderzoeken` -> `klaar voor creatie` is de Librarian's oordeel, niet scout's. Data versus oordeel blijven gescheiden.

## 10. Bewust niet nu (roadmap)

- De budget/cost-gate-mechaniek (voorwaarde voor fase B).
- Extra statussen (bijv. `afgewezen`, `in productie`) zodra de content-pijplijn erom vraagt.
- Related-keywords-endpoints (`get_related_keywords`, `get_pasf_keywords`) als aparte skills voor auto-expansie vanuit één zaadje.
- Bredere modifier-sets en meer landen (at/ch/no/dk/fi) zodra een markt de moeite blijkt.
- Legal-check als derde gate, downstream van `klaar voor creatie`: claim-dragende termen en de content erop (biologisch afbreekbaar, CO2, vergelijkend, certificering) door de `nooch-legal`-check vóór publicatie. Hoort bij content-creatie, niet bij keyword-discovery.
