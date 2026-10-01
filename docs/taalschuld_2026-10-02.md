# Taalschuld — scan van 2 oktober 2026

Systeemstrings die nog Nederlands zijn, onder de regel **systeemoutput is Engels, mens-op-mens-tekst
mag Nederlands** (`docs/CONVENTIES.md`). Gemaakt met de scanner van `tests/test_taal_ratchet.py`
(zelfde woordenlijst, zelfde AST-filters), in drie lagen. Dit is een MOMENTOPNAME voor het
prioriteren, geen werklijst om in één ronde af te werken.

| laag | wat | woordtreffers | unieke strings | bestanden |
|---|---|---|---|---|
| A | de huidige ratchet: `views/` + `cockpit2_util` + `web_base`, logregels uit | 13 | 9 | 6 |
| B | zonder uitzondering 'DE DATA is inhoud': alle modules, logregels uit | 1959 | 1128 | 149 |
| C | zonder beide vervallen uitzonderingen: alle modules, logregels mee | 2202 | 1288 | 165 |

**Lees de getallen met deze ruis in gedachten** (nog niet uitgefilterd):

- `i18n.py` is de vertaaltabel zelf; Nederlandse bronstrings horen daar.
- `arch_map.py` genereert `docs/ARCHITECTUUR.md`, ontwikkelaarsdocumentatie (Nederlands mag).
- `demos/` is demo-code, geen productiepad.
- Een woordtreffer is één Nederlands woord; één zin geeft er vaak meerdere. 'Unieke strings' is de betere maat.

## Per bestand (laag C, aflopend)

| treffers (C) | waarvan logregels | bestand |
|---|---|---|
| 100 | 4 | `cockpit2.py` |
| 92 | 0 | `cli.py` |
| 84 | 0 | `role_proposals.py` |
| 81 | 0 | `waarde_audit.py` |
| 70 | 0 | `inbox/__main__.py` |
| 60 | 2 | `materiaal_memo.py` |
| 57 | 3 | `noochie_memo.py` |
| 56 | 0 | `skills.py` |
| 50 | 0 | `inbox_actions.py` |
| 50 | 7 | `seeds.py` |
| 45 | 15 | `triage_rol.py` |
| 41 | 5 | `skills_impl/claims_site_scan.py` |
| 40 | 0 | `kennisbank.py` |
| 39 | 0 | `i18n.py` |
| 38 | 6 | `weekmemo.py` |
| 35 | 3 | `afslanken.py` |
| 35 | 0 | `claims_modelpas.py` |
| 35 | 4 | `zelf_verwerking.py` |
| 34 | 0 | `definitions.py` |
| 32 | 11 | `village.py` |
| 30 | 13 | `governance.py` |
| 27 | 0 | `arch_map.py` |
| 25 | 0 | `demos/analysis.py` |
| 25 | 0 | `demos/governance_demos.py` |
| 25 | 0 | `sluitronde.py` |
| 24 | 14 | `llm_keuze.py` |
| 23 | 1 | `skills_impl/web_zoek.py` |
| 22 | 2 | `claims_substantiatie.py` |
| 22 | 0 | `demos/ops.py` |
| 22 | 0 | `skills_impl/mobiel_audit.py` |
| 22 | 0 | `wiki_domein.py` |
| 21 | 1 | `copycheck.py` |
| 21 | 0 | `skills_impl/regulation_watch.py` |
| 20 | 0 | `skills_impl/cert_evidence.py` |
| 20 | 0 | `skills_impl/claims_check.py` |
| 19 | 1 | `site_audit.py` |
| 18 | 2 | `claim_oordeel.py` |
| 18 | 12 | `escalation_router.py` |
| 18 | 1 | `governance_review.py` |
| 18 | 10 | `inhabitant.py` |
| 17 | 0 | `biweekly_report.py` |
| 17 | 0 | `roloverleg.py` |
| 16 | 0 | `backfill.py` |
| 16 | 6 | `roles.py` |
| 15 | 3 | `claims_board.py` |
| 15 | 0 | `project_items.py` |
| 14 | 2 | `safe_fetch.py` |
| 13 | 11 | `llm.py` |
| 13 | 2 | `skills_impl/gsc.py` |
| 12 | 0 | `skill_labels.py` |
| 12 | 1 | `skills_impl/openalex.py` |
| 11 | 0 | `claims_context.py` |
| 11 | 0 | `claims_db.py` |
| 11 | 0 | `governance_examples.py` |
| 11 | 0 | `human_inbox.py` |
| 11 | 0 | `skills_impl/haal_pagina.py` |
| 11 | 0 | `verslag.py` |
| 10 | 0 | `artefacts.py` |
| 10 | 5 | `cert_register.py` |
| 10 | 0 | `claim_classify.py` |
| 10 | 0 | `domeinen.py` |
| 10 | 10 | `draaistaat.py` |
| 10 | 0 | `skill_match.py` |
| 10 | 3 | `skills_impl/trends.py` |
| 10 | 2 | `skills_naar_links.py` |
| 9 | 2 | `assignments.py` |
| 9 | 0 | `puls_wacht.py` |
| 9 | 0 | `role_rhythm.py` |
| 8 | 0 | `discovery_board.py` |
| 8 | 4 | `founder_kaart.py` |
| 8 | 2 | `skills_impl/epo_patents.py` |
| 8 | 0 | `voorstel_mutatie.py` |
| 7 | 1 | `afslank_wezen.py` |
| 7 | 3 | `citeerbaar.py` |
| 7 | 0 | `dm_samenvoegen.py` |
| 7 | 0 | `noochie_kanaal.py` |
| 7 | 1 | `park_klep.py` |
| 7 | 6 | `rugzak.py` |
| 7 | 0 | `skills_impl/library_skills.py` |
| 7 | 0 | `wizard.py` |
| 6 | 0 | `claims_verify.py` |
| 6 | 3 | `dagcyclus.py` |
| 6 | 0 | `feedback.py` |
| 6 | 2 | `kennis_embeddings.py` |
| 6 | 0 | `key_audit.py` |
| 6 | 0 | `skill_meta.py` |
| 6 | 0 | `skills_impl/escaleer.py` |
| 6 | 0 | `skills_impl/semantic_scholar.py` |
| 6 | 0 | `skills_impl/shopify_sales.py` |
| 5 | 0 | `afslank_afhankelijkheden.py` |
| 5 | 5 | `bron_ophalen.py` |
| 5 | 5 | `deliverable_store.py` |
| 5 | 0 | `evidence_ledger.py` |
| 5 | 0 | `gap_classifier.py` |
| 5 | 0 | `orphan_report.py` |
| 5 | 5 | `project_doc_store.py` |
| 5 | 0 | `skills_impl/keywords_everywhere.py` |
| 5 | 0 | `skills_impl/projectverzoek.py` |
| 5 | 1 | `vastgelopen_route.py` |
| 5 | 0 | `wiki_bronnen.py` |
| 5 | 0 | `wiki_seed.py` |
| 4 | 4 | `ai_tasks.py` |
| 4 | 1 | `checklist_vorm.py` |
| 4 | 4 | `collector.py` |
| 4 | 2 | `gap_ledger.py` |
| 4 | 1 | `giphy.py` |
| 4 | 1 | `inoreader_ingest.py` |
| 4 | 0 | `library.py` |
| 4 | 1 | `linkbuilding.py` |
| 4 | 0 | `maturity.py` |
| 4 | 0 | `skills_impl/google_patents.py` |
| 4 | 0 | `systeemtaal.py` |
| 4 | 3 | `views/metrics.py` |
| 4 | 0 | `views/vangst.py` |
| 4 | 0 | `wiki_claims_policy.py` |
| 4 | 0 | `wiki_how_we_decide.py` |
| 3 | 0 | `doelen.py` |
| 3 | 0 | `grounding.py` |
| 3 | 0 | `insight.py` |
| 3 | 0 | `legal_signaal.py` |
| 3 | 0 | `projects.py` |
| 3 | 3 | `skill_links.py` |
| 3 | 3 | `skills_catalog.py` |
| 3 | 1 | `skills_impl/claim_evidence.py` |
| 3 | 0 | `skills_impl/tegenspraak.py` |
| 3 | 0 | `skills_impl/voorstel.py` |
| 3 | 0 | `views/noochie.py` |
| 3 | 3 | `views/search.py` |
| 2 | 1 | `auth.py` |
| 2 | 2 | `claims_labels.py` |
| 2 | 0 | `coherence.py` |
| 2 | 2 | `copy_stack.py` |
| 2 | 1 | `decision_sheets.py` |
| 2 | 0 | `keyword_measure.py` |
| 2 | 0 | `leesextract.py` |
| 2 | 0 | `metrics.py` |
| 2 | 0 | `mission.py` |
| 2 | 2 | `observations.py` |
| 2 | 0 | `project_verslag.py` |
| 2 | 0 | `skills_impl/serpapi_trends.py` |
| 2 | 0 | `skills_impl/site_health.py` |
| 2 | 0 | `skills_impl/trends_categorie.py` |
| 2 | 2 | `skillset.py` |
| 2 | 1 | `util.py` |
| 2 | 0 | `views/messages.py` |
| 2 | 0 | `views/navpaneel.py` |
| 2 | 0 | `werkoverleg.py` |
| 2 | 0 | `wiki.py` |
| 1 | 1 | `attachments.py` |
| 1 | 0 | `board_loop.py` |
| 1 | 1 | `co2.py` |
| 1 | 0 | `intent.py` |
| 1 | 0 | `kennis_migrate.py` |
| 1 | 0 | `keyword_nominations.py` |
| 1 | 0 | `metric_schema.py` |
| 1 | 0 | `ngram_correlate.py` |
| 1 | 0 | `people.py` |
| 1 | 0 | `personas.py` |
| 1 | 0 | `pinboard.py` |
| 1 | 1 | `signaal.py` |
| 1 | 0 | `skills_impl/linkbuilding.py` |
| 1 | 0 | `skills_impl/weten_we_dit_al.py` |
| 1 | 0 | `views/checklists.py` |
| 1 | 0 | `voorstel_opruiming.py` |
| 1 | 0 | `web_read.py` |
