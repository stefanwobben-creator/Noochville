# Meetcatalogus — alles wat de ObservationStore in gaat

Read-only gegenereerd op 2026-07-08 (prod-store: 10.922 rijen). Twee invalshoeken gekruist: **data**
(alle distinct `(bron, metric, dimensie)` in de store) én **code** (alle `record(`/`record_daily(`-
schrijfpaden). Elk schrijfpad is een catalogusregel, óók zonder data — een pad zonder observaties is
onzichtbaar in de data alleen (de `visitors_via_*`-les).

**Beoordeling:** het veld `OORDEEL` is leeg — Stefan vult per regel `houden` / `fixen` / `weg`.

---

## Twee conventie-notities (lees eerst)

1. **OpenAlex = cumulatieve voorraad, geen periodewaarde.** `openalex_works_day` / `openalex_citations_day`
   zijn een lópend totaal (alle werken/citaties ooit voor dat concept), niet de aanwas van die week.
   Analyseer daarom op **eerste verschillen** (delta tussen twee weken = nieuwe werken/citaties), nooit de
   absolute stand als "weekwaarde".
2. **Weekgrens-offset OpenAlex vs. Trends.** Twee weekly-bronnen met een verschillend week-anker:
   - OpenAlex labelt met de **ISO-maandag van de puls-week** (`_expected_period`, bv. 2026-07-06) — een
     momentopname van de cumulatieve stand.
   - Trends labelt met de **laatste COMPLETE Trends-week (zondag-start)** (`_last_complete_week`, bv.
     2026-06-28). Bij het uitlijnen van weekreeksen: deze twee delen géén weekgrens (± enkele dagen +
     OpenAlex = lopende week, Trends = afgesloten week). Nooit 1-op-1 op datum joinen.

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

## openalex  (bron actief, weekly, concept-dimensie)  — ⚠ cumulatieve voorraad, zie notitie 1

| metric | dim | schrijfpad | cadans | datumlabel | orde v. grootte | betekenis | OORDEEL |
|---|---|---|---|---|---|---|---|
| `openalex_works_day::<concept>` | concept | collector.py:165 | weekly | ISO-maandag | 3.135–97.598 | Cumulatief aantal werken per gepind concept | [ ] |
| `openalex_citations_day::<concept>` | concept | collector.py:165 | weekly | ISO-maandag | 53.333–840.784 | Cumulatief aantal citaties per gepind concept | [ ] |

*Concepten (3): circular economy, sustainable agriculture, vegan diet. Undimensioned totaal bestaat
bewust NIET (daily_values geeft None) — alleen de concept-dimensie.*

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
