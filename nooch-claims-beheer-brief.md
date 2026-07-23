# CC-opdracht: Claims Checker — de wijzigingsloop structureel sluiten

**Voor:** Claude Code in de Noochville-repo. Laatste structurele scope op de claims-checker (v1-v3 + Taak 6 geland). Eigen branch (`claims-beheer`), schone working tree, bekende guardrails.

**Doel in één zin:** elke soort wijziging aan de claims-laag heeft één vaste, self-service route — inhoud via de beheer-tab, wet via de puls, code via briefs — vastgelegd in de repo, zodat er nooit meer een losse eenmalige instructie nodig is.

## Taak 1 — `claims_term_edit`: inhoud volledig self-service

- Nieuwe dispatch-actie achter dezelfde poort als `claims_term_add` (`_role_gate("compliance")`, fail-closed): een bestaande term bewerken — stoplicht, waarom, alternatief, bron, bron_detail, hardheid. Patroon is immutable via de UI (patroon-wijziging = nieuwe term + oude deactiveren, zodat de scan-historie betekenis houdt); als deactiveren nog niet bestaat: een `actief`-vlag met default true, gedeactiveerde termen scannen niet mee maar blijven in het bestand.
- Elke edit: versie-bump + system_log-regel + zichtbaar in de beheer-tab ("laatst gewijzigd [datum] door [rol]").
- **Direct toepassen als eerste echte edit (het staande ⚖️-besluit):** term "PETA Approved Vegan" — bron D erbij ("intern conflict opgelost: Nooch is PETA Approved Vegan, bevestigd door Stefan 18-07-2026"), stoplicht escaleren → orange, alternatief/vereiste: "logo alleen tonen mét korte uitleg wat het label dekt en dat het zelf-declaratie is; heroverwegen vóór 27-09-2026 voor DE (UWG-accreditatie-eis, Vegan Society als geaccrediteerd alternatief)". Werklijst #5 → "in behandeling".
- **Acceptatie:** compliance kan een term bewerken via de tab; een andere ingelogde rol ziet geen bewerkknoppen; de PETA-term staat live op orange met de nieuwe onderbouwing.

## Taak 2 — Kennisbank-koppeling (reference, don't copy)

- Registreer `config/claims_database.json` als bron in de kennisbank (verwijzing naar /claims, geen kopie van termen — twee waarheden is precies wat we niet willen).
- Bij afronding van een ⚖️-taak: automatisch een kennisbank-item (besluit, datum, beslisser, bron_detail, verwijzing naar de term). Kies het bestaande intake-pad dat hier het dichtst bij ligt en rapporteer de keuze. Backfill: het PETA-besluit van 18-07-2026 als eerste item.
- **Acceptatie:** een zoekende rol (library/kennis_scout) vindt het PETA-besluit in de kennisbank met verwijzing naar de claims-database.

## Taak 3 — `docs/CLAIMS_BEHEER.md`: de wijzigingsloop op schrift

Kort document (max 1 A4) in docs/, gelinkt vanaf de beheer-tab, met exact deze vier loops:

1. **Inhoud** (term, stoplicht, status, ⚖️-besluit) → beheer-tab door compliance. Enige schrijfroute; versie-bump + log automatisch. Nooit handmatig in het JSON-bestand, nooit via losse CC-instructies.
2. **Wet** → regulation_watch (maandpuls) detecteert → ⚖️-taak @compliance → mens beoordeelt → curatie via loop 1. Mijlpalen (27-09-2026, NL-omzetting) zitten in de skill.
3. **Code/features** → wensen als taak op het bord met label `checker-onderhoud`; gebundeld in één onderhouds-brief in de repo-root wanneer er genoeg ligt; CC voert uit op eigen branch, rapport aan de founder.
4. **Spiegels** (Claude-skills buiten het dorp) → na elke versie-bump één commando aan Claude: "synchroniseer de claims-skill met prod". Versienummer in beide wijzigingslogs maakt drift zichtbaar.

Plus de vaste principes onderaan: bron van waarheid is config/claims_database.json; zwart-wit (A/B/D hard, C escaleert naar mens); reference-don't-copy richting kennisbank en spiegels; alles terugkerends in de pulslaag (product-principe: geen externe scheduling).

- **Acceptatie:** het document bestaat, klopt met de gebouwde werkelijkheid, en de beheer-tab linkt ernaar.

## Guardrails

Zoals altijd: volle suite groen, arch_map + ARCHITECTUUR.md mee, deploy conform protocol incl. chown-stap, geen mutaties buiten de gedefinieerde routes (de bestaande guard-tests blijven het bewijs).
