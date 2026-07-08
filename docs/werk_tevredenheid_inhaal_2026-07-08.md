# werk_tevredenheid — eenmalige historische inhaal (2026-07-08)

## Aanleiding
Het `werk_tevredenheid_day`-schrijfpad (`record_werk_daily`, observations.py) bestaat pas sinds commit
**cc58b48 (2026-07-05)**. Eén échte check-out-meting dateert van dáárvoor en is daardoor nooit naar de
ObservationStore geschreven — de keten is gezond, alleen was die ene meting van vóór het pad (zie de
read-only diagnose: gezond-maar-ongevoed, geen bug).

## De ingehaalde meting (exact uit de bron)
Gelezen uit `data/werkoverleg.json`, log-snapshot van het gesloten overleg:

| role_id | close (at) | tevredenheid | bron |
|---|---|---|---|
| `mother_earth__nooch` | 2026-07-03T07:35 UTC | **8.7** | werkoverleg |

De waarde **8.7** is de daadwerkelijke opgeslagen `tevredenheid` in de log-snapshot (gem. check-out-score,
`round(avg(scores),1)`). (De diagnose noemde 8.7; een genoemde 8.6 komt niet uit de bron — 8.7 is leidend.)

## Wat NIET is ingehaald
- **`mother_earth` 2026-07-04, 10.0** — een TEST-overleg, bewust NIET ingehaald.
- **`werk_duur_day`** — buiten scope; alleen de tevredenheid-meting is ingehaald, geen andere entries.

## Hoe geschreven
Eén rij via het equivalent van `record_werk_daily` (`obs.record_daily`), met de **oorspronkelijke datum
2026-07-03**, `role_id=mother_earth__nooch`, `bron=werkoverleg`, en een **meta-markering `backfill: true`**
zodat het punt later herkenbaar is als een vóór-schrijfpad-inhaal en niet als een reguliere puls-meting.

## Scope-grens (belangrijk)
Dit is een **bewuste, gescoopte inhaal binnen het geïsoleerde werkoverleg-domein** — één punt, uit de eigen
bron, met de originele datum. Het is **expliciet GEEN algemene backfill-policy** voor andere bronnen: er
wordt niets teruggerekend of geïnterpoleerd voor plausible/gsc/openalex/trends/KE. Nieuwe metingen daar
lopen gewoon vooruit via de puls; historische gaten blijven gaten tenzij een bron een eigen, expliciete
backfill-route heeft (zoals de Plausible-per-land-backfill).
