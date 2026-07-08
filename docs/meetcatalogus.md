# Meetcatalogus — alles wat de ObservationStore in gaat

Read-only gegenereerd op 2026-07-08 (store: ~10.900 rijen). Twee doelen: **(1) keuring nu** (per reeks
houden/fixen/weg) en **(2) voorbereiding op een signaleringslaag** (per reeks: wat is een opmerkelijke
wekelijkse verandering). Twee invalshoeken gekruist: **data** (distinct `(bron, metric, dimensie)` in de
store) én **code** (alle `record_daily(`-schrijfpaden — óók slapende paden zonder data).

**Stefan vult met de hand:** `OORDEEL` (houden / fixen / weg) en `OPMERKELIJK-DREMPEL` (wat een wekelijkse
rimpel waard is — bijv. "nieuw keyword", "±15% w/w", "meerjarige piek"; mag leeg waar nog onbekend).

---

## Conventie-notities (lees eerst — staan vast)

1. **OpenAlex = 90/30-FLOW, geen voorraad.** `openalex_works_90d::<concept>` = het aantal works dat per
   concept in een 90-daags publicatievenster VERSCHEEN. Label = **venster-eind (R−30)**, waarbij R = einde
   laatste complete week. Analyse direct op niveau (geen eerste-verschillen). **`ecodesign` is de dunste
   reeks** (~130/venster) → week-ruis verwacht, geen defect.
2. **Trends stemming-paren = ratio A/B**, complete-week-label (zondag-grens). A = zuinigheid/behoud,
   B = nieuw/luxe; ↑ = versobering ↑. `repair` / `textile recycling` / `vegan leather` zijn **bewust NIET
   in OpenAlex** gedekt (geen bruikbaar concept) — het repair-signaal komt uit deze Trends-paren.
3. **OpenAlex-label ligt op een andere weekgrens dan Trends** (R−30 ≈ 5-6 weken vóór het Trends-zondag-
   label van dezelfde puls). Bij latere cross-correlatie is dat een **grid-offset, geen echte lead/lag** —
   nooit 1-op-1 op datum joinen.

**Datumlabel-conventies (collector):** daily → laatst-complete dag `today−1−lag`; weekly → ISO-maandag;
Trends → complete Trends-week (zondag); OpenAlex → venster-eind R−30.

## Controlepunten (expliciet)

- **KE 29 reeksen (we spraken over 28):** de **29e is `vegan shoes`** — **bewust approved** (rank-target /
  doelwit, global volume 22.200, goedgekeurd via de Librarian-KE-check tijdens een puls), **geen stray**.
  Alle 29 KE-velden = de approved-set van de Library (available_metrics volgt de Library dynamisch).
- **`werk_duur_day` twee circles** (`mother_earth` + `mother_earth__nooch`): **bewuste twee-circle-
  situatie, GEEN duplicaat** — twee geldige circles, elk hun eigen werkoverleg (record_daily houdt ze
  apart op role_id).
- **`trends_categorie` vs `trends`:** twee APARTE bronnen — categorie-interesse (bevroren termen, daily)
  versus stemming-paren (ratio, weekly). Eigen blok elk; niet verwarren.

---

## plausible  (actief, daily)

| metric | dim | schrijfpad | cadans | label | laatste | orde v. grootte | betekenis (voor Nooch) | OORDEEL | OPMERKELIJK-DREMPEL |
|---|---|---|---|---|---|---|---|---|---|
| `plausible_visitors_day` | — | collector.py:142 | daily | today−1 | 6 | 0–2.365 | Hoeveel mensen de site per dag bezoeken (bereik) | [ ] | [ ] |
| `plausible_pageviews_day` | — | collector.py:142 | daily | today−1 | 13 | 0–7.333 | Hoeveel pagina's per dag bekeken worden | [ ] | [ ] |
| `plausible_visit_duration_day` | — | collector.py:142 | daily | today−1 | 57 | 0–1.938 (sec) | Hoe lang bezoekers gemiddeld blijven (betrokkenheid) | [ ] | [ ] |
| `plausible_bounce_rate_day` | — | collector.py:142 | daily | today−1 | 50 | 0–100 (%) | Aandeel dat direct weer weggaat (reeks-start 2026-07-07) | [ ] | [ ] |
| `plausible_*_day::<land>` | country | collector.py:165 (+ backfill 115/175, historisch) | daily | today−1 | 7 landen | zie totalen, per land | Zelfde 4 metrics uitgesplitst per land — waar het bereik zit | [ ] | [ ] |
| `visitors_via_<utm>_day` | — | roles.py:233 | per puls | today−1 (laatst-complete dag) | 1–3 | 1–9 | Bezoekers per kanaal (ig, shopify_email, bluemarble) — 7-daags aggregaat | [ ] | [ ] |
| *(gemonitorde metrics)* | — | geen write (curatie-lijst) | — | — | n.v.t. | — | Curatie-lijst van metrics die een rol volgt (MonitoringStore, `data/role_metrics.json`, gevuld via Noochie's keep-verdicts). GEEN kopie-reeks: de waarden leest een rol-view/signaleringslaag via referentie uit de canonieke reeksen (plausible_*_day). Slapend tot het eerste project door de advies→keep-flow gaat. | [ ] | [ ] |

*Landen (7): NL, BE, DE, FR, ES, GB, US. De historische per-land- én totaal-reeksen (terug tot 2024) komen
uit een backfill (backfill.py:115/175), dezelfde metrics idempotent aangevuld.*

## gsc  (actief, daily, lag 3)

| metric | dim | schrijfpad | cadans | label | laatste | orde v. grootte | betekenis (voor Nooch) | OORDEEL | OPMERKELIJK-DREMPEL |
|---|---|---|---|---|---|---|---|---|---|
| `gsc_impressions_day` | — | collector.py:142 | daily | today−4 | 61 | 61–77 | Hoe vaak de site in Google-resultaten verscheen/dag | [ ] | [ ] |
| `gsc_clicks_day` | — | collector.py:142 | daily | today−4 | 3 | 2–3 | Hoeveel mensen vanuit Google doorklikten/dag | [ ] | [ ] |
| `gsc_ctr_day` | — | collector.py:142 | daily | today−4 | 0,049 | 0,026–0,049 | Klik-door-ratio: hoe aantrekkelijk het zoekresultaat is | [ ] | [ ] |
| `gsc_position_day` | — | collector.py:142 | daily | today−4 | 15,1 | 11–15 | Gem. positie in Google (lager = beter) | [ ] | [ ] |
| `gsc_*_day::<keyword>` | query | collector.py:165 | daily | today−4 | **1 keyword** (`nothing shoes`) | schaars | Zoekprestaties per Library-doelwit-keyword; vult alleen waar de site echt impressies heeft | [ ] | [ ] |

## openalex  (actief, weekly, FLOW 90/30-venster)

| metric | dim | schrijfpad | cadans | label | laatste | orde v. grootte | betekenis (voor Nooch) | OORDEEL | OPMERKELIJK-DREMPEL |
|---|---|---|---|---|---|---|---|---|---|
| `openalex_works_90d::<concept>` | concept | openalex.py:193 | weekly | venster-eind (R−30) | 6 concepten | 129–1.593 | Wetenschappelijke aandacht per missie-concept (works in een 90d-venster) — het culturele/academische tij | [ ] | [ ] |

*Concepten (6, laatste waarde 2026-06-04): biomaterial 1593, sustainable consumption 1392, mycelium 1210,
natural fibers 742, biodegradable polymers 541, **ecodesign 129 (dunste reeks — week-ruis verwacht)**.*

## trends  (actief, weekly, stemming-paren)

| metric | dim | schrijfpad | cadans | label | laatste | orde v. grootte | betekenis (voor Nooch) | OORDEEL | OPMERKELIJK-DREMPEL |
|---|---|---|---|---|---|---|---|---|---|
| `trends_ratio_<A>_<B>_day` | — | collector.py:142 | weekly | complete-week (zondag) | 3 paren | 0,20–3,15 | Massa-stemming zuinig↔nieuw (ratio A/B); ↑ = versoberingsstemming stijgt | [ ] | [ ] |

*Paren (2026-06-28): repair÷replace 3,15 · second hand÷brand new 0,86 · thrift÷luxury 0,20.*

## trends_categorie  (actief, daily, bevroren termen)

| metric | dim | schrijfpad | cadans | label | laatste | orde v. grootte | betekenis (voor Nooch) | OORDEEL | OPMERKELIJK-DREMPEL |
|---|---|---|---|---|---|---|---|---|---|
| `trends_categorie_<term>_day` | — | collector.py:142 | daily | today−1 | 3 termen | 0,7–63 | Zoekinteresse per categorieterm (footwear/sustainable shoes/vegan shoes) — vraag naar de categorie | [ ] | [ ] |

## keywordseverywhere  (actief, weekly, dynamisch uit Library)

| metric | dim | schrijfpad | cadans | label | laatste | orde v. grootte | betekenis (voor Nooch) | OORDEEL | OPMERKELIJK-DREMPEL |
|---|---|---|---|---|---|---|---|---|---|
| `keywordseverywhere_<keyword>_day` | — | collector.py:142 | weekly | ISO-maandag | 29 keywords | 0–110.000 | Maandelijks global zoekvolume per approved Library-keyword — hoeveel vraag er naar een term is | [ ] | [ ] |

*29 reeksen (velden = approved-set van de Library, dynamisch). Volumes 2026-07-06 (steekproef): footwear
110.000, nooches/nootch 49.500, earth shoes 33.100, sustainable shoes 27.100, **vegan shoes 22.200 (de 29e,
bewust approved)**, plastic shoes 8.100, no shoes/no i shoes/nos shoes 5.400, … 3× 0 (carbonkiller, noech,
noochwear.com reviews — echte volume-loze merktermen, geen defect).*

## alphavantage  (actief, daily, ETF-proxy)

| metric | dim | schrijfpad | cadans | label | laatste | orde v. grootte | betekenis (voor Nooch) | OORDEEL | OPMERKELIJK-DREMPEL |
|---|---|---|---|---|---|---|---|---|---|
| `alphavantage_<symbool>_day` | — | collector.py:142 | daily | today−1 | spx 747,71 · aex 107,8 | 100–751 | Beurs-slotkoers (tracking-ETF spx→SPY, aex→IAEX.AMS) — macro-stemmingsproxy | [ ] | [ ] |

## werkoverleg  (intern, per circle)

| metric | dim | schrijfpad | cadans | label | laatste | orde v. grootte | betekenis (voor Nooch) | OORDEEL | OPMERKELIJK-DREMPEL |
|---|---|---|---|---|---|---|---|---|---|
| `werk_duur_day` | — | observations.py:267 | per overleg | overleg-datum | 0 | klein | Duur van het werkoverleg per circle — **2 circles = 2 legit reeksen** (mother_earth + mother_earth__nooch) | [ ] | [ ] |
| `werk_tevredenheid_day` | — | observations.py:264 | per overleg | overleg-datum | 8.7 (1 historisch punt) | 0-10 | Gem. check-out-tevredenheid (0-10) per circle. 1 punt: eenmalige inhaal 2026-07-03=8.7 (mother_earth__nooch, meta backfill), meting van vóór het schrijfpad; zie docs/werk_tevredenheid_inhaal_2026-07-08.md | [ ] | [ ] |

## Inactieve bronnen  (schrijfpad in code, bewust geen data)

| metric | bron | schrijfpad | status | OORDEEL | OPMERKELIJK-DREMPEL |
|---|---|---|---|---|---|
| `gdelt_<term>_day` | gdelt_tone | collector.py:142 | inactief (bevroren termen aanwezig) | [ ] | [ ] |
| `shopify_*_day` | shopify | collector.py:142 | inactief (geen SHOPIFY_CLIENT_ID/SECRET) | [ ] | [ ] |
| `semanticscholar_*_day` | semanticscholar | collector.py:142 | inactief (monthly, niet geactiveerd) | [ ] | [ ] |

---

## Code-vs-data-kruising

**Schrijfpaden (9 in code; `observations.py:189` is de interne record_daily→record-delegatie, geen eigen reeks):**
collector.py:142 (totaal), collector.py:165 (dimensie), roles.py:233 (visitors_via),
observations.py:264 (werk_tevredenheid), observations.py:267 (werk_duur),
openalex.py:193 (openalex-flow via collect_series), backfill.py:115/175 (historische backfill, zelfde metrics).
*(De oude monitored-kopie-tak in roles.py is verwijderd — reference, don't copy; de MonitoringStore blijft
als curatie-lijst, zonder eigen write.)*

**In code, NIET in data** (slapend of inactief — alleen zichtbaar via de code-invalshoek):
- gdelt / shopify / semanticscholar (collector.py:142) — **inactieve bronnen**.

*(`werk_tevredenheid_day` had lang geen data; sinds 2026-07-08 staat er 1 punt — de eenmalige historische
inhaal van 2026-07-03=8.7. Het reguliere pad vult verder zodra een overleg met een check-out-score sluit.)*

De **MonitoringStore** (curatie-lijst van gevolgde metrics) is bewust géén schrijfpad meer: waarden komen
via referentie uit de canonieke reeksen. Slapend tot het eerste project door de advies→keep-flow gaat.

**In data, GEEN vindbaar schrijfpad:** **geen.** Elke reeks is herleidbaar tot een `record_daily`-pad
(collector totaal/dimensie, openalex-flow, roles visitors_via, werkoverleg). Geen verdachte weesdata.
