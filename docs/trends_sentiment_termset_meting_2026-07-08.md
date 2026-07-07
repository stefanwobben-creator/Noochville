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
