# Fixup-brief: atomiser-versionering + re-atomiseer van oude atomen

**Voor:** Claude Code in de `Noochville` repo. Kennisbank live op prod.
**Probleem uit echt gebruik:** de pre-A/B atomen staan nog in de bibliotheek (o.a. de CLARISSA-stappen: losse broertjes + citatie-smeer `© IDS 2021 ISBN... DOI...` in de content). De A/B-fix raakt alleen nieuwe ingests. En de idempotentie-ledger serveert voor al-geziene content de oude atomen ("0 te doen"), dus elke atomiser-verbetering bereikt de bestaande corpus nooit. Twee taken.

## Taak 1 — Atomiser-versie in de ledger (het systemische gat)
- Geef de atomiser een expliciete `ATOMISER_VERSION`-constante. Bump 'm bij elke logic-wijziging; de huidige A/B-logica is de nieuwe versie.
- Sla per ledger-entry op met welke `atomiser_version` de content is verwerkt.
- Pas de dedup/lookup aan: content die al gezien is maar door een **oudere** versie telt niet meer als "klaar". Voeg een expliciete `--reatomise` (force) toe, en detecteer version-mismatch.
- **Acceptatie:** content verwerkt onder v1, opnieuw aangeboden onder v2, wordt her-verwerkt in plaats van overgeslagen. Zelfde versie opnieuw = nog steeds idempotent (0 te doen).

## Taak 2 — Migratie: re-atomiseer de bestaande pre-fix atomen
- Vind atomen gemaakt door een oudere atomiser-versie (of heuristiek als de versie ontbreekt: citatie-smeer in content / oud bron-format). Groepeer per brondocument.
- Her-atomiseer het brondocument met de nieuwe atomiser → schone, samengestelde atomen.
- **Append-only:** de oude atomen niet hard wissen maar **archiveren** met een `superseded_by`-link naar de nieuwe, zodat het spoor blijft.
- **Bescherm menselijk werk (belangrijk):** een oud atoom dat al in gebruik is (gelinkt aan een inzicht, geannoteerd, met de hand gemerged) mag je **niet** automatisch vervangen. Markeer die voor handmatige review. Alleen ongebruikte oude atomen auto-superseden.
- **Dry-run eerst:** toon per document X oude atomen → Y nieuwe, Z geflagd voor review, plus een tokenschatting. Dan pas `--apply`. Idempotent (her-run doet niets).
- **Acceptatie:** na de migratie toont het CLARISSA-rapport de vier samengestelde kaarten, geen losse smeer-broertjes; de oude atomen zijn gearchiveerd met een link; en niets dat al in een inzicht of annotatie zat is stil verdwenen (dat staat op de review-lijst).

## Guardrails
- Branch `kennisbank-reatomise`, tests + volle suite groen, aparte PR.
- Append-only overal; nooit menselijke curatie overschrijven.
- Applies op prod als user `nooch`, back-up de datamap, dry-run voor elke `--apply`.
- Hergebruik de bestaande atomiser en ladder; geen nieuwe pijplijn.

## Noot
Voor dit ene CLARISSA-document kan de gebruiker nu al met de hand opruimen (Bibliotheek → de stap-atomen aanvinken → Voeg samen → archiveer de rest). Deze brief lost het structureel op, zodat het bij elke volgende atomiser-verbetering vanzelf goed komt.
