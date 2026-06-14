# NoochVille — State & Handover (2026-06-14)

## Waar we staan

- Code op ~8, bewezen: 75/75 tests groen + schone supervised live run.
- 4 review-fixes doorgevoerd: atomic writes + Noochie-rem (één voorstel, geen
  stroom), test-fundament (pytest), single-source missie/policy, village.py
  gesplitst + TriageEngine eruit + DRY.
- Keyword-lus gesloten: Librarian-escalaties landen als eigen type "keyword" in
  de inbox (approve → approved, reject → forbidden naar de bibliotheek, direct,
  deduped).
- Live burgers: GrowthAnalyst, Librarian, PerformanceScout, TimeKeeper,
  Facilitator, CircleLead, TijdgeestWachter, KennisScout, Noochie.

## Principes die niet mogen driften

- **Spine blijft dom**: gate G0-G4, prioriteit Missie > Policy > Strategy > Goal,
  provenance, fail-closed. LLM alleen bij fuzzy oordelen, fail-closed.
- **Born vs activated**: rollen geboren onbemand in de records; code/API-activatie
  altijd mens-gated + per-edit review. De diff zien telt vooral bij activatie en
  gate/missie-code, niet bij kleine operationele plumbing.
- **Inbox = zeldzaam en zwaar** (governance-escalaties, activaties). Laag-volume
  houden. Keyword-beslissingen zijn een apart, licht, omkeerbaar type, gate niet
  nodig.
- **Missie = Anchor-purpose, mens-eigendom.** Noochie is steward/stem, geen
  missie-beslisser. Publieke Noochie = los later product, twee-Noochie firewall.
- **Circle blijft Inhabitant erven** (niet "fixen" met compositie). Geen
  DI-container, geen plugin-autodiscovery, EventBus/models.py niet splitsen.
- **Patroon**: AI stelt plausibel-maar-soms-fout voor (bronnen, API's, capabilities).
  De mens/gate fit-check is de feature, niet een gebrek.

## Volgende stappen

1. Verifiëren: tests opnieuw draaien na de keyword-lus; inbox openen en de 4
   pending keywords beslissen (earth shoes, natuurlijke schoenen, noosh,
   sneaker zero).
2. Op echt ritme draaien en observeren. Laat het dorp de volgende prioriteit
   aanwijzen, niet een vooraf bedacht lijstje.
3. Cockpit aan live data hangen (records/inbox/proces), met de auth-grens erin.
4. CI: pytest bij elke commit (stap richting 9).
5. Laat opkomen uit echte behoefte: synthesizer-rol, sub-cirkels voor schaal,
   batched keyword-review + Librarian die glasheldere gevallen zelf afwijst
   (pas als keyword-volume groeit).
6. openlibrary_v2-activatie NIET reflexief goedkeuren: API is per-boek, niet
   corpus-breed. Laat onbemand tot er een echte per-boek use case is.
