# Keywords Everywhere — country-config-fix + herfetch (2026-07-08)

## Bevinding (read-only diagnose, 2026-07-08)
De 28 KE-reeksen van 2026-07-06 stonden allemaal op volume **0**. Handmatige KE-call bewees: dat is een
**echte API-respons voor `country=nl`** (KE heeft geen bruikbare NL-data), geen fetch-defect. Global
levert wél volume: `footwear` 110.000, `sustainable shoes` 27.100, `compostable shoes` 260.

**Oorzaak:** sleutel-mismatch. `settings.ini` zet `ke_country =` (leeg = bewust global), maar
`KeywordsEverywhereSkill.daily_values` las een **andere** sleutel `keywordseverywhere_country` met
default `"nl"`. De bedoelde "global" kwam dus nooit aan; de skill draaide op de NL-markt.

## Fix
- `daily_values` leest voortaan **`ke_country`** (dezelfde sleutel als library_enrich en roles). De oude
  sleutel `keywordseverywhere_country` is volledig verwijderd (grep-test bewaakt dit).
- **Geen `"nl"`-default meer** — nergens. `ke_country` leeg/afwezig = bewust global; ontbrekende settings
  (settings-object None) → ERROR + bron levert niets (fail-closed, geen fallback-land). Ook de
  `run`-payload-default is van `"nl"` naar `""` (global) gezet.

## Store-opruiming
De 28 KE-reeksen van **2026-07-06** (country=nl, allemaal 0) zijn verkeerde-markt-observaties, geschreven
vóór meetstart → **verwijderd** via een eenmalige `remove_bron("keywordseverywhere")` op prod. Nodig
vóór de herfetch: `record_daily` dedupliceert op `(metric, bron, datum)`, dus zonder opruiming zouden de
0-rijen de nieuwe global-waarden voor dezelfde week blokkeren. **Aantal verwijderde rijen: 28.**

## Herfetch (verificatie)
Eén KE-puls na de opruiming schrijft 28 global-waarden voor 2026-07-06. Verwacht (steekproef):
`sustainable shoes ≈ 27.100`, `footwear ≈ 110.000`, `compostable shoes ≈ 260`.
