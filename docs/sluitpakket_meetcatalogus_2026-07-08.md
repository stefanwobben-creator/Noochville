# Sluitpakket meetcatalogus — meetverantwoording (2026-07-08)

Verantwoording van de opruim-/uitbreidingsronde die de meetcatalogus afsluit vóór de 6-weken-meetperiode.
Per scope: wat, waarom, en de effecten op de store.

## Scope 1 — Opruimen (weg)

### trends_categorie — bron gedeactiveerd + reeksen verwijderd
- **Actie:** `sources.set_active("trends_categorie", False)` + `remove_bron("trends_categorie")`.
- **Verwijderd: 6 rijen** (3 termen — footwear, sustainable shoes, vegan shoes — × 2 dagen).
- **Reden:** de bron is bevroren (categorie-interesse now-7-d), comprimeert, en **overlapt** met Keywords
  Everywhere (zoekvolume per term) én de stemming-paren (relatieve verschuiving). Geen eigen signaal dat
  de andere twee niet beter geven. De skill blijft in code (alleen gedeactiveerd; default is toch inactief).

### Keywords Everywhere — 2 termen uit de approved-set
- **Actie:** `library.curate("carbonkiller", "forbidden", …)` + idem `noochwear.com reviews`; hun
  0-reeksen verwijderd (`remove_metric keywordseverywhere_carbonkiller_day` + `_noochwear_com_reviews_day`).
- **Reden:** 0 global zoekvolume, geen meetwaarde (ruis-/merk-artefacten). `forbidden` voorkomt dat de
  discovery-lus ze opnieuw voorstelt.
- **`noech` BEHOUDEN** (bewust besluit van Stefan, 2026-07-08): de typo-variant blijft approved om
  brand-typo-verkeer te blijven volgen, ook al is het volume nu 0.
- **Effect:** KE approved-set **29 → 27**; KE-reeksen in de store **29 → 27**.

Prod-verificatie (read-only, na restart): trends_categorie actief=False, 0 reeksen; KE 27 approved,
27 reeksen; carbonkiller/noochwear niet meer approved; noech nog approved.

## Scope 2 — Plausible page_path-dimensie (erbij)

Nieuwe **drempel-gebaseerde, persistente** dimensie op de Plausible-bron, additief naast de country-
dimensie + totalen (via een nieuwe collector-hook `collect_extra_series`, die NAAST de generieke paden
draait i.p.v. ze te vervangen).

- **Drempel + persistentie:** een pagina komt in de meetset zodra hij op **één dag ≥ 3 bezoeken** haalt
  (`_PAGE_THRESHOLD=3`); **daarna** wordt zijn **volledige dagreeks** vastgelegd — ook lagere dagen en
  0 (echte waarde, geen gat). De reeds gekwalificeerde set = de pagina's die al een reeks in de store
  hebben (`obs.dimensioned_series`), die worden altijd doorgemeten.
- **Opslag = per pagina** (`plausible_page_visitors_day::<slug>`, meta `{dimension: page_path, value:
  <page_path>}`); de homepage `/` → slug `home`. Een **top-10 is een AFGELEIDE view**, niet de opslag
  (stabiel/terugleesbaar per pagina).
- **Bron:** Plausible `event:page`-breakdown per dag (visitors); fail-closed bij geen creds/API-fout, geen
  interpolatie.
- **Backfill:** `backfill_page_paths` haalt per gekwalificeerde pagina de dagreeks over een venster op
  (Plausible timeseries, filter `event:page==<page>`), elk punt **meta `backfill: true`**. Idempotent.

Tests (test_plausible_page_path.py): drempel-entree (≥3 wel, <3 niet), persistent doormeten onder de
drempel, afwezig=0, backfill-meta, fail-closed, en de additieve collector-hook (totaal + extra samen).

## Scope 3 — Trends-paar slow÷fast fashion (erbij)

- **Config:** `trends_pairs` uitgebreid met **`slow fashion:fast fashion`** (A=slow/behoud, B=fast/nieuw,
  consistent met de oriëntatie A=zuinig/behoud). Gevalideerd op 2026-07-08 (mean slow 5.4 / fast 38.3,
  100% niet-nul, semantiek zuiver op 1 ruis-query na — zie iteratie 3). Ratio slow÷fast stijgt =
  slow-fashion-stemming wint = versobering/duurzaamheid.
- **Mechaniek = zelfde als de bestaande 3 paren:** ratio A/B, complete-week-label (Trends-zondag-week),
  isPartial-filter. Een 4e ratio-reeks `trends_ratio_slow_fashion_fast_fashion_day` vult per puls.
- **Backfill 5 jaar:** nieuwe `TrendsSkill.backfill_pairs` — per paar de volledige interest_over_time
  (today 5-y), partiële week weg, per complete week ratio A/B → punt met meta `backfill:true`, datum = de
  weekgrens. Noemer 0 → week overgeslagen. Idempotent (reeds live geschreven week blijft). Toegepast op
  alle 4 paren zodat de bestaande 3 óók hun 5-jaars historie krijgen (consistent).

Tests: slow÷fast paar-parse + backfill_pairs per-week (ratio, meta, partieel weg, noemer 0 over).
