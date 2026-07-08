# OpenAlex conceptset-herontwerp — verkenning (2026-07-08, read-only)

Voorbereiding voor een latere vervangings-scope (Stefan stempelt). **Geen writes, geen config-wijziging;
de huidige 3 concept-reeksen zijn NIET aangeraakt.**

---

## ⚠ KRITIEKE BEVINDING — concept-aggregaten zijn BEVROREN

OpenAlex heeft Concepts gedeprecieerd t.g.v. het Topics-systeem. Empirisch bevestigd:

| check | circular economy (C2777448596) | vegan diet (C2911178952) |
|---|---|---|
| `/concepts/<id>` counts_by_year 2023/24/25 | **0 / 0 / 0** (bevroren) | **0 / 0 / 0** (bevroren) |
| live `works?filter=concepts.id:X,publication_year:2025` | **9.982** | **300** |
| idem 2026 | 8.124 | 178 |

**Twee lagen lopen uiteen:**
1. Het **concept-OBJECT** (`works_count`, `cited_by_count`, `counts_by_year`) wordt niet meer bijgewerkt → **bevroren, statisch getal**.
2. De **concept-TAGS op works** worden nog wél toegekend aan 2025-2026-publicaties → `works?filter=concepts.id:X` is **live**.

**Gevolg voor onze meting:** de skill leest nu `/concepts/<id>.works_count` (de bevroren aggregaat) →
de wekelijkse `openalex_*_day::concept`-reeks is een **vlakke lijn zonder weeksignaal**. Dit geldt óók
voor de huidige 3 concepten. Een nieuwe conceptset lost dit NIET op zolang de query-methode hetzelfde
blijft.

**Prerequisite voor de vervangings-scope (los van de ID-keuze):** verander de skill van
`GET /concepts/<id>` (bevroren) naar **`works?filter=concepts.id:X&group_by=publication_year`** (live count).
Dan groeit de voorraad weer wekelijks (analyse op eerste verschillen blijft geldig).
Concept-ID's blijven bruikbaar (tags live); **Topics zijn te grof** (zie tabel, 130k–190k works).
Deprecatie-restrisico: OpenAlex kan concept-toewijzing ooit volledig stoppen — Topics zijn de officiële
opvolger maar missen de Nooch-granulariteit.

---

## Kandidaten — LIVE works (via works-filter) + jaargroei

Beslisregel-suggestie: **live works ~500–50.000** (genoeg massa voor weeksignaal, niet zo breed dat het
Nooch-signaal verdrinkt) **én zichtbare jaargroei**. `citations` = bevroren concept-aggregaat (alleen
grofweg als magnitude; niet in de beslisregel).

| kandidaat | type | ID | officiële naam | live works | works 23/24/25 | citations (bevroren) | oordeel-suggestie |
|---|---|---|---|---:|---|---:|---|
| biodegradable polymers | concept | C45211672 | Biodegradable polymer | 13.120 | 631/552/1358 | 491.081 | ✅ **houden** — range + groei + match |
| natural fibers | concept | C2776176653 | Natural fiber | 14.181 | 958/782/1644 | 404.651 | ✅ **houden** — range + groei + match |
| sustainable consumer behavior | concept | C2776770324 | Sustainable consumption | 14.731 | 803/855/3200 | — | ✅ **houden** — sterke 2025-groei, goede match |
| circular design | concept | C2779439448 | Ecodesign | 2.989 | 107/119/398 | — | ✅ **houden** — goede match, klein maar groeit hard |
| mycelium | concept | C133479454 | Mycelium | 61.862 | 2219/1515/3131 | 1.016.589 | ⚠ **Stefan** — net boven ~50k, wél goede match |
| biobased materials | concept | C2778414984 | Biomaterial | 37.666 | 1841/1433/3808 | — | ⚠ **Stefan** — range+groei, maar semantisch breder (medisch/implantaten) |
| sustainable fashion | topic | T12514 | Fashion and Cultural Textiles | 186.504 | 6808/6462/6836 | — | ❌ te breed (>50k), grof topic |
| plant-based diet | topic | T11259 | Agriculture Sustainability & Env. Impact | 137.546 | 8715/9081/11877 | — | ❌ te breed + off-target |
| on-demand manufacturing | concept? | C26796778 | Selective laser melting | 15.825 | 1245/965/1553 | — | ❌ semantisch verkeerd (SLM ≠ on-demand) |
| right to repair | concept? | C134935766 | DNA repair | 113.513 | 6457/3318/5431 | — | ❌ semantisch verkeerd (DNA repair) |
| leather alternatives / vegan leather | — | — | — | — | — | — | ❌ AFGEWEZEN — geen concept/topic-match |
| textile recycling | — | — | — | — | — | — | ❌ AFGEWEZEN — geen concept/topic-match |

*Alternatieve zoektermen die AFGEWEZEN/verkeerd opleverden: "biomaterials"→Biomaterial (breed, medisch),
"additive manufacturing"→Selective laser melting (specifieke metaal-3D-print), "repair"→DNA repair
(moleculaire biologie), "sustainable consumption"→correct. Voor vegan leather/textile recycling gaf geen
enkele variant ("artificial/synthetic leather", "leather substitute", "fiber recycling") een bruikbaar
concept- of topic-ID.*

---

## Shortlist-suggestie (Stefan stempelt)

- **Sterk houden (4):** `biodegradable polymers`, `natural fibers`, `sustainable consumption`, `ecodesign`.
  Alle vier binnen ~3k–15k live works, zichtbare 2025-groei, goede semantische match.
- **Stefan beslist (2):** `mycelium` (62k — net boven het plafond) en `biobased materials`→Biomaterial
  (37k, maar semantisch breder dan bedoeld).
- **Afgewezen (6):** sustainable fashion + plant-based diet (Topics, >130k te breed); on-demand
  manufacturing + right to repair (enige matches semantisch verkeerd); vegan leather + textile recycling
  (geen bruikbaar ID).

**Belangrijkste boodschap:** de ID-keuze is secundair aan de **query-methode-fix**. Zonder de overstap
van de bevroren `/concepts`-aggregaat naar de live `works?filter=…`-count blijft élke openalex-reeks een
vlakke lijn — ook de huidige drie. Dat is de eerste stap van de vervangings-scope.

---

# Scope gerealiseerd (2026-07-08) — query-fix + 6 concepten + 90/30-venster

## Waarom concept-tags i.p.v. de bevroren aggregaat
De skill meet per week niet meer `/concepts/<id>.works_count` (bevroren), maar **telt de works die in een
publicatievenster VERSCHENEN** via `works?filter=concepts.id:<ID>,from_publication_date,to_publication_date`
→ `meta.count`. De concept-TAGS zijn live, dus dit is een echte, bewegende reeks. Het is een **FLOW**
(niveau per venster), geen cumulatieve voorraad → analyse direct op niveau, géén eerste-verschillen nodig
(daarom is de bron nu `kind="flux"`, niet meer `snapshot`).

## De 6 concepten (config `openalex_concepts = naam:ID`, fail-closed)
biodegradable polymers `C45211672` · natural fibers `C2776176653` · sustainable consumption `C2776770324` ·
ecodesign `C2779439448` · mycelium `C133479454` · biomaterial `C2778414984`.

## Het 90/30-venster — identiek voor alle 6 (vergelijkbaarheid)
R = einde laatste complete week (zaterdag; zelfde weekgrens-logica als Trends). **eind = R−30** (30-daagse
buffer voor de OpenAlex-indexeer-lag), **start = R−120** (90 dagen breed). **Label = R−30** (de meetweek,
niet de pulsdatum). Meta per punt draagt `from_publication_date`/`to_publication_date` → elk punt
reproduceerbaar; de buffer kan later herzien worden zonder de reeks weg te gooien. Immutability: elk label
wordt precies één keer geschreven (idempotent, geen refetch).

## Retro-ijking mycelium (26 weken, read-only, vóór de eerste write) — GATE GESLAAGD
Bevestigt beweging (geen vlakke lijn) en een adequate buffer (laatste punten geen scherpe lag-cliff):

| label (R−30) | works | | label | works | | label | works |
|---|---|---|---|---|---|---|---|
| 2025-12-11 | 1302 | | 2026-02-19 | 1632 | | 2026-04-30 | 1286 |
| 2026-01-01 | 1625 | | 2026-03-05 | 1580 | | 2026-05-14 | 1238 |
| 2026-01-15 | 1631 | | 2026-03-19 | 1543 | | 2026-05-28 | 1223 |
| 2026-01-29 | 1626 | | 2026-04-02 | 1230 | | 2026-06-04 | 1210 |
| 2026-02-05 | 1658 | | 2026-04-16 | 1264 | | | |

min/mediaan/max = 1210/1433/1665 (spreiding 455 ≈ 30% van de mediaan). De laatste 3 (1233/1223/1210) zijn
een geleidelijke voortzetting, geen eind-cliff → 30-daagse buffer volstaat.

## Aandachtspunten
- **ecodesign is een dunne reeks** (klein veld, ~3k works totaal): in dunne weken kan `meta.count` laag of
  0 zijn. `count=0` bij een geldige respons wordt als **0 weggeschreven** (echte observatie, geen gat).
- **Bewust NIET gedekt** (geen bruikbaar concept-ID gevonden): `vegan leather`, `textile recycling`,
  `right to repair`. Het **repair-/versoberings-signaal komt uit de Trends-stemming-paren** (repair÷replace).

## Store-opruiming (verworpen meetopzet)
De oude 3 CUMULATIEVE concept-reeksen (`openalex_works_day::…` / `openalex_citations_day::…`, circular
economy / sustainable agriculture / vegan diet, 2026-07-06) zijn verwijderd via `_bootstrap`
(`remove_bron("openalex", keep_prefix="openalex_works_90d")`, idempotent) — bevroren aggregaat, vóór
meetstart. Aantal: zie de deploy-verificatie.
