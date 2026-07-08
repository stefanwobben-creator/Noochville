# Meetcatalogus — alles wat de ObservationStore in gaat

Read-only gegenereerd op 2026-07-08 (prod-store: 10.922 rijen). Twee invalshoeken gekruist: **data**
(alle distinct `(bron, metric, dimensie)` in de store) én **code** (alle `record(`/`record_daily(`-
schrijfpaden). Elk schrijfpad is een catalogusregel, óók zonder data — een pad zonder observaties is
onzichtbaar in de data alleen (de `visitors_via_*`-les).

**Beoordeling:** het veld `OORDEEL` is leeg — Stefan vult per regel `houden` / `fixen` / `weg`.

---

## Twee conventie-notities (lees eerst)

1. **OpenAlex = FLOW in een 90/30-venster, geen cumulatieve voorraad** (herzien 2026-07-08).
   `openalex_works_90d::<concept>` telt de works die per concept in een 90-daags publicatievenster
   VERSCHENEN (`works?filter=concepts.id:X,from_publication_date,to_publication_date` → meta.count). Dit is
   een niveau per venster → **analyse direct op niveau, GEEN eerste-verschillen**. Vervangt de bevroren
   `/concepts/<id>.works_count`-aggregaat (counts_by_year 2023-2025 = 0). Zie
   docs/openalex_conceptset_herontwerp_2026-07-08.md.
2. **Weekgrens-offset OpenAlex vs. Trends.** Beide weekly, beide op de Trends-weekgrens (R = einde laatste
   complete week, zaterdag). Verschil: **Trends** labelt met de weekstart-zondag (bv. 2026-06-28);
   **OpenAlex** labelt met het venster-eind **R−30** (bv. 2026-06-04) — dus ~5-6 weken vóór het Trends-
   label van dezelfde puls. Het OpenAlex-label is de meetweek van het FLOW-venster (de 30d-buffer dekt de
   indexeer-lag), niet de pulsweek. Bij het uitlijnen van weekreeksen: nooit 1-op-1 op datum joinen.

**Datumlabel-conventies (collector):** daily → laatst-complete dag = `today − 1 − lag` (UTC); weekly →
ISO-maandag van de (lag-)week; Trends weekly → laatste complete Trends-zondag-week (skill-override).

---

## plausible  (bron actief, daily)

| metric | dim | schrijfpad | cadans | datumlabel | orde v. grootte | betekenis | OORDEEL |
|---|---|---|---|---|---|---|---|
| `plausible_visitors_day` | — | collector.py:142 | daily | today−1 | 0–2.365 (bulk <100) | Unieke bezoekers per dag | [ ] |
| `plausible_pageviews_day` | — | collector.py:142 | daily | today−1 | 0–7.333 | Paginaweergaven per dag | [ ] |
| `plausible_visit_duration_day` | — | collector.py:142 | daily | today−1 | 0–1.938 (sec) | Gem. bezoekduur (seconden) per dag | [ ] |
| `plausible_bounce_rate_day` | — | collector.py:142 | daily | today−1 | 0–100 (%) | Bouncepercentage/dag (reeks-start 2026-07-07) | [ ] |
| `plausible_*_day::<land>` | country | collector.py:165 | daily | today−1 | 7 landen (NL,BE,DE,FR,ES,GB,US) | Zelfde 4 metrics per land | [ ] |
| `visitors_via_<utm>_day` | — | roles.py:233 | per puls | today−1 (laatst-complete dag) | 1–9 | UTM-bron-bezoekers (7-daags Plausible-aggregaat, gesampled per puls) | [ ] |
| `<monitored metric>` | — | roles.py:237 | per puls | today−1 | — (geen data) | Door MonitoringStore geconfigureerde plausible-metric per rol; nu leeg | [ ] |

*Backfill-schrijfpad voor bovenstaande plausible-reeksen: backfill.py:115 (totaal) + backfill.py:175
(dimensie) — schrijft dezelfde metrics historisch, idempotent.*

## gsc  (bron actief, daily, lag=3)

| metric | dim | schrijfpad | cadans | datumlabel | orde v. grootte | betekenis | OORDEEL |
|---|---|---|---|---|---|---|---|
| `gsc_impressions_day` | — | collector.py:142 | daily | today−4 | 61–77 | Vertoningen in de zoekresultaten/dag | [ ] |
| `gsc_clicks_day` | — | collector.py:142 | daily | today−4 | 2–3 | Klikken vanuit Google/dag | [ ] |
| `gsc_ctr_day` | — | collector.py:142 | daily | today−4 | 0,026–0,049 | Klik-door-ratio/dag | [ ] |
| `gsc_position_day` | — | collector.py:142 | daily | today−4 | 11–15 | Gem. positie/dag | [ ] |
| `gsc_*_day::<keyword>` | query | collector.py:165 | daily | today−4 | **nu 1 keyword** (`nothing shoes`) | Zelfde 4 metrics per Library-doelwit-keyword; vult alleen waar de site impressies heeft | [ ] |

## openalex  (bron actief, weekly, FLOW per concept — 90/30-venster)

| metric | dim | schrijfpad | cadans | datumlabel | orde v. grootte | betekenis | OORDEEL |
|---|---|---|---|---|---|---|---|
| `openalex_works_90d::<concept>` | concept | openalex.py:collect_series (via collector.py:collect_series-hook) | weekly | venster-eind (R−30) | ~200–4.000 | Aantal works dat per concept in een 90-daags publicatievenster verscheen (FLOW, geen voorraad) | [ ] |

*6 concepten: biodegradable polymers, natural fibers, sustainable consumption, ecodesign, mycelium,
biomaterial. Venster = 90d breed, eindigend 30d vóór R (einde laatste complete week); alle 6 delen
hetzelfde venster. Meta draagt from/to_publication_date. Zie docs/openalex_conceptset_herontwerp_2026-07-08.md.*

## trends  (bron actief, weekly, stemming-paren)  — zie notitie 2 (Trends-zondag-week)

| metric | dim | schrijfpad | cadans | datumlabel | orde v. grootte | betekenis | OORDEEL |
|---|---|---|---|---|---|---|---|
| `trends_ratio_<A>_<B>_day` | — | collector.py:142 | weekly | laatste complete Trends-week | 0,2–3,2 (float) | Stemming-ratio A/B (A=zuinigheid/behoud, B=nieuw/luxe); ↑ = versobering ↑ | [ ] |

*Paren (3): thrift÷luxury, second hand÷brand new, repair÷replace. Ongeschaald, laatste complete week
(isPartial-filter).*

## keywordseverywhere  (bron actief, weekly, dynamisch uit Library)

| metric | dim | schrijfpad | cadans | datumlabel | orde v. grootte | betekenis | OORDEEL |
|---|---|---|---|---|---|---|---|
| `keywordseverywhere_<keyword>_day` | — | collector.py:142 | weekly | ISO-maandag | 0–110.000 (global) | Maandelijks zoekvolume per approved Library-keyword (global markt) | [ ] |

*29 dynamische reeksen (velden volgen de approved-set van de Library). 26/29 niet-nul. Steekproef:
footwear 110.000, sustainable shoes 27.100, vegan shoes 22.200, compostable shoes 260, 3× 0 (merktermen).*

## trends_categorie  (bron actief, daily, bevroren termen)

| metric | dim | schrijfpad | cadans | datumlabel | orde v. grootte | betekenis | OORDEEL |
|---|---|---|---|---|---|---|---|
| `trends_categorie_<term>_day` | — | collector.py:142 | daily | today−1 | 0,7–63 | Relatieve Trends-interesse per bevroren categorieterm (now 7-d) | [ ] |

*Termen (3, bevroren): footwear, sustainable shoes, vegan shoes. source_version=1.*

## alphavantage  (bron actief, daily, ETF-proxy)

| metric | dim | schrijfpad | cadans | datumlabel | orde v. grootte | betekenis | OORDEEL |
|---|---|---|---|---|---|---|---|
| `alphavantage_<symbool>_day` | — | collector.py:142 | daily | today−1 | 107–751 | Slotkoers tracking-ETF (spx→SPY, aex→IAEX.AMS); ETF-koers, niet index-niveau | [ ] |

## werkoverleg  (intern, per circle)

| metric | dim | schrijfpad | cadans | datumlabel | orde v. grootte | betekenis | OORDEEL |
|---|---|---|---|---|---|---|---|
| `werk_duur_day` | — | observations.py:267 | per overleg | overleg-datum | 0 | Duur werkoverleg (min) per circle; 2 circles = 2 legit reeksen | [ ] |
| `werk_tevredenheid_day` | — | observations.py:264 | per overleg | overleg-datum | **GEEN DATA** | Tevredenheid werkoverleg per circle — schrijfpad bestaat, nog nooit geschreven | [ ] |

## Inactieve bronnen (schrijfpad in code, bewust geen data)

| metric | bron | schrijfpad | status | OORDEEL |
|---|---|---|---|---|
| `gdelt_<term>_day` | gdelt_tone | collector.py:142 | inactief (bevroren termen aanwezig) | [ ] |
| `shopify_*_day` | shopify | collector.py:142 | inactief (geen SHOPIFY_CLIENT_ID/SECRET) | [ ] |
| `semanticscholar_*_day` | semanticscholar | collector.py:142 | inactief (monthly; niet geactiveerd) | [ ] |

---

## Code-vs-data-afstemming (invalshoek-kruising)

- **In code, NIET in data:** `werk_tevredenheid_day` (observations.py:264 — nooit geschreven); de
  monitored-metric-tak (roles.py:237 — leeg zonder MonitoringStore-config); gdelt/shopify/semanticscholar
  (inactieve bronnen). Deze zijn alleen zichtbaar via de code-invalshoek.
- **In data, NIET in code:** géén. Elke reeks in de store is herleidbaar tot een `record_daily`-pad
  (collector totaal/dimensie, roles visitors_via, werkoverleg). Geen verdachte weesdata.
- **Schrijfpaden totaal:** 8 (collector 142/165, roles 233/237, observations 264/267, backfill 115/175).
  Alle via `record_daily` — sinds de Scope-B-fix bestaat er geen kale `record()`-pad naar de store meer.
