# Meetvenster — formele start 2026-07-13

Doc-actie: dit legt de **formele start** van het meetvenster vast. **Geen gedragswijziging aan de
collector** — enkel de streep in het zand + de definitieve bronnenlijst voor de duur van het venster.

## Periode
- **Startdatum:** 2026-07-13 (ISO-maandag — sluit aan op de weekly weekgrenzen van Trends/OpenAlex/KE).
- **Einddatum:** 2026-08-23 (6 weken).
- **Evaluatie:** 2026-08-24.

## Bron van waarheid
De **gekeurde meetcatalogus** is leidend: [`docs/meetcatalogus.md`](meetcatalogus.md) is de levende bron
van waarheid; het **execution-contract** ([`docs/ONTWERP_execution_contract.md`](ONTWERP_execution_contract.md),
guard: `village healthcheck`) bewaakt de conformiteit. Wijkt dit document ooit af van de catalogus, dan
**wint de catalogus**.

## Definitieve actieve bronnenlijst (dit venster)
| Bron | Wat | Cadans |
|---|---|---|
| **Plausible** | totalen, per-land, page_path | daily |
| **Trends** stemming-paren | 4 paren: repair÷replace, second hand÷brand new, thrift÷luxury, slow÷fast fashion | weekly (last-complete-week) |
| **KE** (Keywords Everywhere) | 27 keywords | weekly (ISO-maandag) |
| **OpenAlex** flow | 6 concepten (biodegradable_polymers, biomaterial, ecodesign, mycelium, natural_fibers, sustainable_consumption) | weekly (venster-eind R−30) |
| **GSC** | totalen | daily (lag) |
| **AlphaVantage** | index-standen | daily |

## Bewust inactief tijdens dit venster (uit ≠ kapot)
Deze bronnen staan **bewust uit** en horen géén data te leveren gedurende het venster; hun afwezigheid is
geen signaal:
- `gdelt`
- `shopify`
- `semanticscholar`
- `trends_categorie`

## Toegestane verrijkingen tijdens het venster (verstoren de meting niet)
Deze twee openstaande verbeteringen **mogen landen** binnen het venster zonder de meting te breken:
1. **Backfill (stap 4)** — historische aanvulling; raakt de lopende cadans/labels niet.
2. **Page_path-drempel-herijking** — zodra méér pagina's structureel ≥3 bezoekers halen, mag de drempel
   opnieuw geijkt worden.

## Read-only sanity vóór de streep (2026-07-13)
De start is pas gezet nadat deze poort schoon was:
- **Contract-healthcheck:** `village healthcheck` → **0 signalen — contract gezond**.
- **Weekly bronnen op de verwachte (lag-)weekgrens:**
  - Trends → `2026-07-05` = `_last_complete_week(2026-07-13)` ✅
  - OpenAlex → `2026-06-11` = `_window(2026-07-13)` (R−30), advancing vanaf `2026-06-04` ✅
  - KE → `2026-07-13` (ISO-maandag) ✅
- **OpenAlex 6 concept-reeksen:** alle 6 gevuld en wekelijks advancing (`2026-06-04` → `2026-06-11`). ✅

> NB: de Trends- en OpenAlex-datums lopen bewust achter op vandaag (last-complete-week resp. R−30
> indexeer-buffer). Dat is by design, geen freeze — geverifieerd tegen `expected_datum` / `_window`.
