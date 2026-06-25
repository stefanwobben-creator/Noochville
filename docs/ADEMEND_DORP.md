# Een ademend dorp — de kansen-motor

Doel: het dorp bol laten staan van spanningen waarbij spanningen niet alleen problemen zijn maar
kansen. Elke rol denkt vanuit zijn purpose mee: welke uitbreiding van mijn rol, welke nieuwe rol,
welk project maakt ons effectiever richting de noordster? Altijd met een hypothese en, waar kan,
een business-case. De kennisbank wordt continu verrijkt: kaartjes zelf én de creatieve links ertussen.

## Noordster en doel
- **Noordster:** 1.000.000 paar schoenen per jaar via nooch.earth (`config/strategy.json` → `north_star`).
- **Batch 4 (sep-dec 2026):** 1.000 paar (`goals[verkoopdoel_2026_q4]`).
Elke business-case weegt zich af tegen `pairs_sold`.

## Diagnose (meting 2026-06-25)
Experiment op de 15 kennis-kaartjes: alle 15 op `grounding_count = 1` (nooit verrijkt), allemaal
`word = None` (niet gekoppeld), gemiddelde onderlinge gelijkenis 0.06. Twee losse eilandjes
(ngram-frames + materiaal-kaartjes) met 13 onbenutte "bridge"-paren (gelijkenis 0.10-0.30). De
kennisbank ademt nog niet: één bron (Harry), nul verrijking, nul links.

## Zes bouwstenen
1. **Opportunity-reflex per rol** — `_reflect()` van stub naar generatieve, purpose-gedreven reflectie:
   elke rol stelt periodiek een onderbouwd voorstel (amend_role / add_role / project) voor. Sensen +
   voorstellen, nóóit zelf uitvoeren (harde regel blijft).
2. **Business-case als eersteklas veld** — `Proposal.hypothesis` + `Proposal.business_case`
   ({metric, effect, effort, confidence, horizon}). `business_case.business_value` = effect×confidence÷effort.
   De kansen-backlog rangschikt hierop. *(Fase 1 — gebouwd.)*
3. **Kennis-synthese-lus** — kaart-verrijking (grounding_count loopt op), creatieve links (Synthesist
   verbindt bridge-paren tot een synthese-kaartje), consolidatie (bijna-duplicaten samenvoegen).
4. **Meer zintuigen** — reviews/Trustpilot, Reddit/fora, regelgeving/duurzaamheidsnieuws. Mens-gated.
5. **Samenwerkingscadans** — expliciete ketens (scout → strateeg → librarian → Harry → synthesist) +
   een wekelijkse "raad": één synthese-puls met de grootste collectieve kans.
6. **Anti-ruis** — elke spanning draagt een business-case (kwaliteit), cross-path-memory (geen herhaling),
   prioritering toont top-N. De inbox wordt een geprioriteerde kansen-backlog, geen overlopende bus.

## Fasering (hoogste hefboom eerst)
- **Fase 1 — frame (GEBOUWD):** business-case-model + `business_value` + noordster in strategy.json +
  cockpit "🎯 Kansen-backlog" die voorstellen/projecten mét business-case op waarde rangschikt.
- **Fase 2 — opportunity-reflex (GEBOUWD):** elke rol bedenkt periodiek (reflect-interval, default wekelijks) vanuit zijn purpose één hoogst-renderende kans → project (ledger) of governance-voorstel, met hypothese + business-case → backlog. Sensen+voorstellen, nooit zelf uitvoeren. Fail-closed zonder LLM.
- **Fase 3 — Synthesist:** verrijking + bridge-links (13 kandidaten liggen klaar).
- **Fase 4 — nieuw zintuig:** één bron tegelijk (reviews of regelgeving eerst).
- **Fase 5 — wekelijkse raad.**

## Vitaliteit meten (is het écht aan het ademen?)
KPI's, doorlopend: spanningen/week, adoptie-ratio (aangenomen ÷ voorgesteld), graaf-dichtheid
(gemiddelde kaart-gelijkenis + aantal links), kruis-rol-ketens/week. Stuur op de drempels.
