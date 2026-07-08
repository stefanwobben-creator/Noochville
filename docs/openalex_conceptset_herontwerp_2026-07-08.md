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
