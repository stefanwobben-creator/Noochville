# Trends anker-ratio — sentiment-termset meetverantwoording (2026-07-08)

Read-only dry-run via pytrends (géén writes naar de ObservationStore) om vast te stellen welke
teller-termen genoeg resolutie geven tegen een vast anker. Dit is de "waarom deze termen"-notitie
voor de `trends` anker-ratio-bron (socionomics-doel: stemming van de massa, geen niche-zoekintentie).

## Opzet
- **Anker (noemer):** `shoes`
- **Timeframe:** `today 5-y` (weekly), **geo:** worldwide (leeg)
- **Request:** kandidaat + anker samen (max 5 termen/request, batches van 4 kandidaten + anker), zodat
  term én anker binnen dezelfde 0-100-normalisatie zitten.
- **Beslisregel per kandidaat (alle drie vereist):**
  a. gemiddelde score ≥ 3 (0-100-schaal, anker draait mee)
  b. ≥ 80% van de weekpunten niet-nul
  c. max nooit > 80 (marge: het anker mag nooit ingehaald worden)

Referentie: anker `shoes` had 262 weekpunten, max 100 (correct 5-jaars weekly).

## Resultaat

| term | mean | % niet-nul | max | oordeel |
|---|---|---|---|---|
| barefoot shoes | 0.0 | 4.6% | 1 | AFGEWEZEN — mean < 3 én %niet-nul < 80 |
| minimalist shoes | 0.0 | 0.8% | 1 | AFGEWEZEN — mean < 3 én %niet-nul < 80 |
| toe shoes | 0.3 | 24.4% | 3 | AFGEWEZEN — mean < 3 én %niet-nul < 80 |
| shoe repair | 0.0 | 1.5% | 1 | AFGEWEZEN — mean < 3 én %niet-nul < 80 |
| second hand shoes | 0 | 0.0% | 0 | AFGEWEZEN — geen enkel niet-nul weekpunt |

**Geslaagde termen: 0.** De poort (minimaal 2) is **DICHT** → Scope 1 (vaste sentiment-termset) is
niet gestart.

## Analyse — waarom alles faalt
- De voormeting verwachtte `barefoot shoes` op ~12% van het anker (zou slagen). Gemeten: **~1%**
  (mean 0.0, max 1) — een factor ~10 lager.
- Oorzaak: het anker **`shoes`** is een generieke term met enorm volume; élke specifieke footwear-term
  (of het nu een conversie-niche of een sub-categorie is) comprimeert daartegen naar 0-1 op de
  0-100-schaal. Dit is dezelfde faalmodus als de Library-conversie-termen (2026-07-08 gemeten: "vegan
  shoes"/"sustainable shoes" → 0-1 tegen "shoes").
- De aanname dat "brede categorie-sentiment-termen" wél zouden scoren houdt niet: deze vijf kandidaten
  zijn nog steeds sub-niches, niet de brede stemmings-termen die het socionomics-doel vraagt.

## Aanbeveling (besluit aan de curator, niet in deze scope gebouwd)
Een van:
1. **Minder dominant anker** kiezen (bijv. een term van vergelijkbare orde als de kandidaten), zodat de
   ratio's binnen een bruikbaar bereik vallen; of
2. **Écht brede sentiment-termen** meten (niet footwear-sub-niches maar massa-stemmingswoorden), tegen
   een passend anker; of
3. **De bron heroverwegen** voor het socionomics-doel (Trends' 0-100-normalisatie is ongeschikt zodra
   het anker het volume domineert).

Meetopzet en ruwe cijfers hierboven zijn reproduceerbaar met dezelfde timeframe/geo/anker.

---

# Iteratie 2 (2026-07-08) — herontwerp: stemming-PAREN i.p.v. anker-ratio

## Waarom
Iteratie 1 faalde structureel: Trends normaliseert op de zwaarste term per request, dus naast een
dominant anker (`shoes`) comprimeert elke niche naar 0-1. Herontwerp: **paren van tegengestelde stemming
met vergelijkbare grootte**, ratio per punt = term_A / term_B, **geen gedeeld anker**.

## Opzet
- Eén request per paar (2 termen), timeframe `today 5-y` (weekly), geo worldwide (leeg).
- **Beslisregel per paar (beide termen):** mean ≥ 5 op de 0-100-schaal van de eigen request, én
  ≥ 90% van de weekpunten niet-nul.

## Resultaat

| paar (A ÷ B) | mean A | mean B | %niet-nul A | %niet-nul B | oordeel |
|---|---|---|---|---|---|
| thrift ÷ luxury | 9.5 | 36.5 | 100% | 100% | **GESLAAGD** |
| second hand ÷ brand new | 44.4 | 18.7 | 100% | 100% | **GESLAAGD** |
| repair ÷ replace | 45.2 | 16.9 | 100% | 100% | **GESLAAGD** |
| barefoot shoes ÷ running shoes | 1.7 | 19.7 | 95% | 100% | AFGEWEZEN — mean A < 5 |
| minimalism ÷ shopping | 0.1 | 68.9 | 6.9% | 100% | AFGEWEZEN — mean A < 5, %niet-nul A < 90 |

**Geslaagde paren: 3.** Poort (≥2) is **OPEN**. De twee afgewezen paren mengen een niche (barefoot shoes,
minimalism) met een veel groter woord (running shoes, shopping) → de niche comprimeert weer; de drie
geslaagde paren zijn stemmings-tegenstellingen van vergelijkbare orde en houden 100% niet-nul over 5 jaar.

## Definitieve paarset (onder voorbehoud van curator-bevestiging)
`thrift÷luxury`, `second hand÷brand new`, `repair÷replace`. Scope 1 volgt pas na bevestiging (ontwerp
wijzigt mee: `trends_pairs` i.p.v. `trends_terms`+`trends_anchor`).

---

# Scope 1 gerealiseerd (2026-07-08) — vaste paarset + opruiming

Curator bevestigde de paarset. De `trends`-bron is omgebouwd van anker-ratio naar stemming-paren:
- **Config:** `trends_pairs = thrift:luxury, second hand:brand new, repair:replace` (settings.ini);
  `trends_anchor` verwijderd (sleutel + code). Fail-closed op `trends_pairs` (ontbreekt/leeg/misvormd
  paar → ERROR + niets, geen partial parse).
- **Gedrag:** één request per paar `[A, B]`; veld/metric `trends_ratio_<A>_<B>_day`; waarde = A/B
  (float, ongeschaald). Noemer-guard: B=0/afwezig → punt geskipt + ERROR. A=0 → ratio 0 (echte obs).
  Request-fout → gat + ERROR. De Library-koppeling, anker-batching en `_ratio` zijn volledig verwijderd.
- **Oriëntatie (meetconstante):** A = zuinigheid/behoud, B = toegeeflijkheid/nieuw; A/B stijgt =
  versobering-stemming stijgt.

## Store-opruiming (verworpen ontwerp)
De 28 reeksen die de `trends`-bron op **2026-07-06** schreef onder het verworpen Library-anker-ontwerp
(metrics `trends_<keyword>_day`, vóór meetstart) zijn **verwijderd** via `remove_bron("trends",
keep_prefix="trends_ratio_")` in `_bootstrap` (idempotent; behoudt de nieuwe `trends_ratio_*`-reeksen).
**Aantal verwijderde rijen: 28.** Reden: geschreven onder een ontwerp dat de meting (iteratie 1/2) heeft
verworpen; niet doortellen.
