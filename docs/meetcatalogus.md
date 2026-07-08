# Meetcatalogus — alles wat de ObservationStore in gaat

Read-only afgeleid, afgesloten 2026-07-08 (sluitpakket). Twee doelen: **(1) keuring** (OORDEEL per reeks)
en **(2) signaleringslaag** (OPMERKELIJK-DREMPEL: wat een opmerkelijke verandering is). Twee invalshoeken
gekruist: **data** (distinct `(bron, metric, dimensie)`) én **code** (alle `record_daily(`-schrijfpaden).

`OORDEEL` = houden / fixen / weg. `OPMERKELIJK-DREMPEL` = ruis-drempel (procentueel/absoluut) én/of een
**categorische** trigger (een gebeurtenis die op zich al een signaal is).

---

## De meetcatalogus als KAART van één stroom (reinforcing loop — mechanisme, nog niet geautomatiseerd)

De bronnen zijn geen losse metertjes; samen vormen ze een **zelfversterkende lus**:

```
  OpenAlex + Trends   →   Keywords Everywhere   →   content (mens)   →   GSC + Plausible page_path
   RADAR                  VALIDATIE                  INTERVENTIE           EFFECT-TERUGKOPPELING
  (brede vroege seeds)   (is er zoekvraag?)         (mens handelt)        (werkte de seed?)
        ▲                                                                        │
        └──────────────────────────  de lus leert welke seeds werken  ──────────┘
```

- **Radar** (OpenAlex-concepten, Trends-stemming-paren): brede, vroege culturele/academische seeds.
- **Validatie** (Keywords Everywhere): is er daadwerkelijk zoekvraag naar een seed?
- **Interventie** (content): de mens maakt content op een gevalideerde seed.
- **Effect-terugkoppeling** (GSC-keyword-dimensie + Plausible page_path): rankt/bezoekt het?

**Rand-principe (expliciet):** de lus **versterkt wat werkt** (bewezen seeds → meer content) **én houdt de
radar open voor seeds zónder bewezen effect** — *innovatie gebeurt aan de randen*. Een seed zonder
zoekvraag of effect wordt niet weggegooid maar blijft in de radar; de brede OpenAlex/Trends-dekking is
bewust breder dan wat nu converteert. De catalogus is de **kaart van deze stroom**, geen losse KPI-lijst.

---

## Conventie-notities (staan vast)

1. **OpenAlex = 90/30-FLOW** (works die per concept in een 90-daags publicatievenster verschenen), label =
   venster-eind R−30. Analyse direct op niveau. `ecodesign` = dunste reeks (week-ruis verwacht).
2. **Trends stemming-paren = ratio A/B**, complete-week-label (zondag-grens). A = zuinigheid/behoud,
   B = nieuw/luxe; ↑ = versobering ↑. `repair`/`textile recycling`/`vegan leather` bewust NIET in OpenAlex.
3. **OpenAlex-label ligt op een andere weekgrens dan Trends** (R−30 vs zondag) → grid-offset, geen echte
   lead/lag; nooit 1-op-1 op datum joinen.

**Datumlabel-conventies:** daily → `today−1−lag`; weekly → ISO-maandag; Trends → complete Trends-week
(zondag); OpenAlex → venster-eind R−30; Plausible page_path/visitors_via → laatst-complete dag.

## Controlepunten

- **KE 27 reeksen** (was 29): sluitpakket Scope 1 verwijderde `carbonkiller` + `noochwear.com reviews`
  (0 volume/ruis, → forbidden). `noech` (typo-variant) **bewust behouden** (Stefan).
- **`werk_duur_day` twee circles** (`mother_earth` + `mother_earth__nooch`): bewuste twee-circle-situatie,
  GEEN duplicaat.
- **`trends_categorie` VERWIJDERD** (Scope 1): gedeactiveerd + reeksen weg (bevroren, comprimeert, overlapt
  met KE + stemming-paren).
- **Nieuw:** Plausible `page_path`-dimensie (Scope 2) en het 4e Trends-paar `slow÷fast fashion` (Scope 3).

---

## plausible  (actief, daily)

| metric | dim | schrijfpad | cadans | label | laatste | betekenis (voor Nooch) | OORDEEL | OPMERKELIJK-DREMPEL |
|---|---|---|---|---|---|---|---|---|
| `plausible_visitors_day` | — | collector.py:142 | daily | today−1 | 6 | Hoeveel mensen de site per dag bezoeken (bereik) | **houden** | **Procentueel** (0–2.365, campagne-batch-model): de spike ~2.365 was een campagne-batch; markeer campagnedagen als bekende uitschieters. Categorisch: **nieuw record** = signaal. |
| `plausible_pageviews_day` | — | collector.py:142 | daily | today−1 | 13 | Hoeveel pagina's per dag bekeken worden | **houden** | Idem procentueel (campagnedagen bekende uitschieters); categorisch nieuw record. |
| `plausible_visit_duration_day` | — | collector.py:142 | daily | today−1 | 57 | Gem. bezoekduur (sec) — betrokkenheid | **houden** | Procentueel w/w. |
| `plausible_bounce_rate_day` | — | collector.py:142 | daily | today−1 | 50 | Aandeel dat direct weggaat | **houden** | **Jonge reeks (start 2026-07-07)** → baseline-drempel voorlopig het minst betrouwbaar; geen scherpe drempel tot er ~4-6 weken staat. |
| `plausible_*_day::<land>` | country | collector.py:165 (+backfill) | daily | today−1 | 7 landen | 4 metrics per land — waar het bereik zit | **houden** | Categorisch: **nieuw of verdwenen land** = signaal. |
| `plausible_page_visitors_day::<page>` | page_path | plausible.py:collect_extra_series (+backfill) | daily | today−1 | 1 pagina (`/`) | Bezoekers per pagina; een pagina komt erbij bij ≥3/dag, daarna volledige dagreeks — de effect-terugkoppeling van de lus | **houden** | Categorisch: **nieuwe pagina kwalificeert** (≥3) = ripple (content sloeg aan). Per pagina procentueel w/w. |
| `visitors_via_<utm>_day` | — | roles.py:233 | per puls | today−1 | 1–3 | Bezoekers per kanaal (7-daags aggregaat) | **houden** | Geen canoniek origineel (Plausible levert UTM alleen zo) → **bewuste uitzondering op reference-don't-copy**. Categorisch: **nieuw kanaal** = signaal. |

*Landen: NL, BE, DE, FR, ES, GB, US. page_path-opslag = per pagina (stabiel); top-10 = afgeleide view.*

## gsc  (actief, daily, lag 3)

| metric | dim | schrijfpad | cadans | label | laatste | betekenis (voor Nooch) | OORDEEL | OPMERKELIJK-DREMPEL |
|---|---|---|---|---|---|---|---|---|
| `gsc_impressions_day` | — | collector.py:142 | daily | today−4 | 61 | Zoek-vertoningen/dag | **houden** | **Lage volumes** → een **absolute sprong** is betekenisvoller dan een %; drempel op absolute stap. |
| `gsc_clicks_day` | — | collector.py:142 | daily | today−4 | 3 | Klikken vanuit Google/dag | **houden** | Idem: absolute sprong (bij 2–3/dag zegt % weinig). |
| `gsc_ctr_day` | — | collector.py:142 | daily | today−4 | 0,049 | Klik-door-ratio | **houden** | Absolute stap (lage volumes). |
| `gsc_position_day` | — | collector.py:142 | daily | today−4 | 15,1 | Gem. positie in Google | **houden** | **LAAG = BETER.** Drempel: een daling (verbetering) onder een positie-grens is het signaal, niet een stijging. |
| `gsc_*_day::<keyword>` | query | collector.py:165 | daily | today−4 | 1 keyword | Zoekprestaties per doelwit-keyword (effect-terugkoppeling) | **houden** | **1 keyword is de VERWACHTE staat, geen alarm.** Categorisch: **nieuw keyword verschijnt** (site rankt op een extra term) = ripple. |

## openalex  (actief, weekly, FLOW 90/30-venster)

| metric | dim | schrijfpad | cadans | label | laatste | betekenis (voor Nooch) | OORDEEL | OPMERKELIJK-DREMPEL |
|---|---|---|---|---|---|---|---|---|
| `openalex_works_90d::<concept>` | concept | openalex.py:193 | weekly | R−30 | 6 concepten | Wetenschappelijke aandacht per missie-concept — de radar | **houden** | **Procentueel PER CONCEPT** (niet absoluut over de 6 samen; ze verschillen sterk in orde). `ecodesign` (~130) krijgt een **hogere** drempel (dunne reeks, week-ruis). |

*Concepten: biomaterial 1593, sustainable consumption 1392, mycelium 1210, natural fibers 742,
biodegradable polymers 541, ecodesign 129.*

## trends  (actief, weekly, stemming-paren — 4)

| metric | dim | schrijfpad | cadans | label | laatste | betekenis (voor Nooch) | OORDEEL | OPMERKELIJK-DREMPEL |
|---|---|---|---|---|---|---|---|---|
| `trends_ratio_<A>_<B>_day` | — | collector.py:142 (+backfill_pairs) | weekly | complete-week | 4 paren | Massa-stemming zuinig↔nieuw per paar (ratio A/B); de radar | **houden** | Categorisch: **meerjarige piek/dal** in een ratio = signaal (5-jaars historie beschikbaar als baseline). |

*Paren (voetnoot per paar): `repair÷replace` = **reparatiecultuur**; `second hand÷brand new` =
**circulariteit**; `thrift÷luxury` = **consumptie(-versobering)**; `slow fashion÷fast fashion` =
**marktpositionering** (duurzaamheids-framing). Alle 4 met 5-jaars historie (2021→).*

## keywordseverywhere  (actief, weekly, dynamisch uit Library)

| metric | dim | schrijfpad | cadans | label | laatste | betekenis (voor Nooch) | OORDEEL | OPMERKELIJK-DREMPEL |
|---|---|---|---|---|---|---|---|---|
| `keywordseverywhere_<keyword>_day` | — | collector.py:142 | weekly | ISO-maandag | 27 keywords | Maandelijks **global** zoekvolume per approved keyword (validatie-stap van de lus) | **houden** | **country: global** (`ke_country` leeg). Categorisch: een **merkterm die van 0 loskomt** = mijlpaal (merk-bekendheid groeit); een **nieuw auto-approved keyword** verschijnt = signaal. |

*27 reeksen (approved-set van de Library, dynamisch). Steekproef: footwear 110.000, nooches/nootch 49.500,
earth shoes 33.100, sustainable shoes 27.100, vegan shoes 22.200, … noech 0 (behouden brand-typo-variant).*

## alphavantage  (actief, daily, ETF-proxy)

| metric | dim | schrijfpad | cadans | label | laatste | betekenis (voor Nooch) | OORDEEL | OPMERKELIJK-DREMPEL |
|---|---|---|---|---|---|---|---|---|
| `alphavantage_<symbool>_day` | — | collector.py:142 | daily | today−1 | spx 747,71 · aex 107,8 | **HYPOTHESE**: beursstemming loopt mogelijk vóór op consumptie (macro-proxy) — **nog te valideren** | **houden** | Drempel **dagbeweging > 2–3%**. **Weekend/feestdag-gaten = normaal, GEEN alarm** (beurs dicht). |

## werkoverleg  (intern, per circle)

| metric | dim | schrijfpad | cadans | label | laatste | betekenis (voor Nooch) | OORDEEL | OPMERKELIJK-DREMPEL |
|---|---|---|---|---|---|---|---|---|
| `werk_duur_day` | — | observations.py:267 | per overleg | overleg-datum | 0 | Duur werkoverleg per circle (2 legit circles) | **houden** | — |
| `werk_tevredenheid_day` | — | observations.py:264 | per overleg | overleg-datum | 8.7 (1 hist. inhaal) | Gem. check-out-tevredenheid (0-10) per circle | **houden** | **Zorg-drempel: score < 6 verdient aandacht** (inhoudelijke grens, geen ruis-drempel). |

## Inactieve bronnen  (schrijfpad in code, bewust geen data — uit ≠ kapot, GEEN 0-rijen-alarm)

| metric | bron | status-label | OORDEEL |
|---|---|---|---|
| `gdelt_<term>_day` | gdelt_tone | **rate-limiting op datacenter-IP; heractiveren na oplossing** | houden (uit) |
| `shopify_*_day` | shopify | **bewust uit, geen credentials; activeren bij webshop-koppeling** | houden (uit) |
| `semanticscholar_*_day` | semanticscholar | **monthly te grof voor het venster; heroverwegen als kwartaal-indicator na 2026-08-23** | houden (uit) |

---

## Code-vs-data-kruising

**Schrijfpaden (10):** collector.py:142 (totaal), collector.py:165 (dimensie), roles.py:233 (visitors_via),
observations.py:264 (werk_tevredenheid), observations.py:267 (werk_duur), openalex.py:193 (openalex-flow),
plausible.py:collect_extra_series (page_path, additief) + backfill_page_paths, backfill.py:115/175 +
trends backfill_pairs (historische backfill). `observations.py:189` = interne delegatie (geen eigen reeks).

**In code, NIET in data:** gdelt / shopify / semanticscholar — **inactieve bronnen** (gelabeld, geen alarm).

**In data, GEEN vindbaar schrijfpad:** **geen** — elke reeks is herleidbaar. Geen weesdata.
