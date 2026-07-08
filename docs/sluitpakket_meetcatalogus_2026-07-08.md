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
