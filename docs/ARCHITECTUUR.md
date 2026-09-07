# NoochVille — Architectuur-vindkaart

> **Automatisch gegenereerd** door `nooch_village/arch_map.py`. NIET handmatig bewerken —
> draai `python -m nooch_village.arch_map` en commit. De guard-test
> `tests/test_architectuur.py` faalt zodra dit bestand verouderd is (nieuwe route/actie/store
> zonder regenereren). Zie de regel hierover in `CLAUDE.md`.

## (a) Route → handler → view

De GET-routes uit `do_GET` (cockpit2.py) en de view die ze renderen. `(inline)` = geen aparte `render_*`, de response wordt in cockpit2 zelf opgebouwd.

| Route | Handler | View-bestand |
|---|---|---|
| `/login` | `(inline)` | `cockpit2.py` |
| `/logout` | `(inline)` | `cockpit2.py` |
| `/wachtwoord` | `(inline)` | `cockpit2.py` |
| `/snake` | `render_snake_page` | `nooch_village/snake.py` |
| `/context` | `(inline)` | `cockpit2.py` |
| `/epic/frame` | `(inline)` | `cockpit2.py` |
| `/` | `(inline)` | `cockpit2.py` |
| `/index.html` | `(inline)` | `cockpit2.py` |
| `/node` | `render_node` | `nooch_village/views/overview.py` |
| `/backlog` | `render_backlog` | `nooch_village/views/backlog.py` |
| `/rapport` | `render_projectrapport` | `nooch_village/views/rapport.py` |
| `/pagina` | `render_pagina` | `nooch_village/views/wiki.py` |
| `/project/nieuw` | `render_wizard` | `nooch_village/views/wizard.py` |
| `/project` | `render_project` | `nooch_village/views/projects.py` |
| `/rolefillers` | `render_rolefillers` | `nooch_village/views/overview.py` |
| `/aitask` | `render_aitask` | `nooch_village/views/overview.py` |
| `/person` | `render_person` | `nooch_village/views/overview.py` |
| `/admin` | `render_admin` | `nooch_village/views/overview.py` |
| `/founder` | `render_founder_flow` | `nooch_village/views/founder_flow.py` |
| `/_patterns` | `render_patterns` | `nooch_village/views/overview.py` |
| `/signals` | `render_signals` | `nooch_village/views/signals.py` |
| `/inbox` | `render_inbox_frag` | `nooch_village/views/inbox.py` |
| `/search` | `render_search_fragment` | `nooch_village/views/search.py` |
| `/skills` | `render_skills` | `nooch_village/views/skills.py` |
| `/bronnen` | `render_bronnen` | `nooch_village/views/bronnen.py` |
| `/codie` | `render_codie` | `nooch_village/views/codie.py` |
| `/inzichten` | `render_kennislaag` | `nooch_village/views/kennislaag.py` |
| `/kennisbank` | `render_kennisbank` | `nooch_village/views/kennisbank.py` |
| `/kennisbank/search` | `render_kennisbank_search` | `nooch_village/views/kennisbank.py` |
| `/kennisbank/tags` | `render_tag_onderhoud` | `nooch_village/views/tag_onderhoud.py` |
| `/kennisbank/staging` | `render_kennisbank_staging` | `nooch_village/views/kennisbank_staging.py` |
| `/kennisbank/spel` | `render_kennisbank_spel` | `nooch_village/views/kennisbank_spel.py` |
| `/kennisbank/spel/search` | `render_kennisbank_spel_search` | `nooch_village/views/kennisbank_spel.py` |
| `/linkbuilding` | `render_linkbuilding` | `nooch_village/views/linkbuilding.py` |
| `/accountabilities` | `render_accountabilities` | `nooch_village/views/accountabilities.py` |
| `/woordenschat` | `render_woordenschat` | `nooch_village/views/woordenschat.py` |
| `/keywords` | `render_keyword_lens` | `nooch_village/views/keyword_lens.py` |
| `/long-term-trends` | `(inline)` | `cockpit2.py` |
| `/belofte` | `render_belofte` | `nooch_village/views/belofte.py` |
| `/metrics2` | `render_metrics2` | `nooch_village/views/metrics2.py` |
| `/inbox/verwerk` | `render_verwerk` | `nooch_village/views/inbox.py` |
| `/catalog` | `render_catalog` | `nooch_village/views/catalog.py` |
| `/catalogus_koppelen` | `(inline)` | `cockpit2.py` |
| `/kpi_new` | `render_kpi_composer` | `nooch_village/views/metrics.py` |
| `/noochie` | `render_noochie` | `nooch_village/views/noochie.py` |
| `/vangst` | `render_vangst_frag` | `nooch_village/views/vangst.py` |
| `/werkoverleg` | `render_werkoverleg` | `nooch_village/views/werkoverleg.py` |
| `/callbar` | `render_callbar` | `nooch_village/views/callbar.py` |
| `/livekit-token` | `(inline)` | `cockpit2.py` |
| `/livekit-presence` | `(inline)` | `cockpit2.py` |
| `/claims/db.json` | `(inline)` | `cockpit2.py` |
| `/claims` | `render_claims` | `nooch_village/views/claims.py` |
| `/copy-check` | `render_copy_check` | `nooch_village/views/copy_check.py` |
| `/copy-prompt` | `render_copy_prompt` | `nooch_village/views/copy_prompt.py` |
| `/inwoners` | `render_inwoners` | `nooch_village/views/inwoners.py` |
| `/inwoner` | `render_inwoner` | `nooch_village/views/inwoners.py` |
| `/roloverleg2` | `render_roloverleg2` | `nooch_village/views/roloverleg.py` |
| `/metric_export` | `(inline)` | `cockpit2.py` |
| `/file` | `(inline)` | `cockpit2.py` |


## (b) Dispatch-actie → handler

De POST-acties uit de `ACTIONS`-registry (cockpit2.py). Elke actie wijst naar zijn `_act_*`-handlerfunctie; het regelnummer is de def-regel. Gegroepeerde acties delen één handler.

| Actie | Handler (cockpit2.py:regel) |
|---|---|
| `ff_beslis` | `cockpit2.py:5616` |
| `ff_cluster` | `cockpit2.py:5744` |
| `ff_promote` | `cockpit2.py:5674` |
| `ff_demote` | `cockpit2.py:5698` |
| `ff_run` | `cockpit2.py:5717` |
| `kb_new` | `cockpit2.py:4979` |
| `kb_intake` | `cockpit2.py:5061` |
| `kb_intake_url` | `cockpit2.py:5078` |
| `kb_stage_edit` | `cockpit2.py:5097` |
| `kb_stage_accept` | `cockpit2.py:5109` |
| `kb_stage_delete` | `cockpit2.py:5128` |
| `kb_stage_merge` | `cockpit2.py:5134` |
| `kb_stage_commit` | `cockpit2.py:5145` |
| `kb_stage_discard` | `cockpit2.py:5165` |
| `kb_atoom_subject` | `cockpit2.py:5420` |
| `kb_atoom_purge` | `cockpit2.py:5404` |
| `tag_voorstel_besluit` | `cockpit2.py:5241` |
| `tag_onderhoud_run` | `cockpit2.py:5391` |
| `copy_stack_inclusie` | `cockpit2.py:5373` |
| `verzoek_besluit` | `cockpit2.py:5260` |
| `kb_blacklist_leeg` | `cockpit2.py:5413` |
| `kb_atoom_edit` | `cockpit2.py:5171` |
| `kb_atoom_related` | `cockpit2.py:5178` |
| `kb_atoom_reference` | `cockpit2.py:5223` |
| `kb_insight_link` | `cockpit2.py:5190` |
| `kb_insight_unlink` | `cockpit2.py:5197` |
| `kb_meta_start` | `cockpit2.py:5203` |
| `kb_atoom_merge` | `cockpit2.py:5431` |
| `kb_atoom_archive` | `cockpit2.py:5452` |
| `kb_atoom_unarchive` | `cockpit2.py:5461` |
| `kb_atoom_naar_spel` | `cockpit2.py:5467` |
| `kb_spel_start` | `cockpit2.py:5488` |
| `kb_spel_add` | `cockpit2.py:5502` |
| `kb_spel_remove` | `cockpit2.py:5512` |
| `kb_spel_flip` | `cockpit2.py:5519` |
| `kb_spel_finish` | `cockpit2.py:5525` |
| `kb_link` | `cockpit2.py:4988` |
| `kb_unlink` | `cockpit2.py:5002` |
| `kb_annotate` | `cockpit2.py:5013` |
| `kb_evidence` | `cockpit2.py:5019` |
| `kb_discuss` | `cockpit2.py:5040` |
| `kb_reformulate` | `cockpit2.py:5046` |
| `kw_nominate` | `cockpit2.py:5536` |
| `kw_nom_accept` | `cockpit2.py:5547` |
| `kw_nom_reject` | `cockpit2.py:5565` |
| `ws_forbid` | `cockpit2.py:5595` |
| `ws_approve` | `cockpit2.py:5600` |
| `proj_add` | `cockpit2.py:1239` |
| `artefact_add` | `cockpit2.py:1292` |
| `artefact_edit` | `cockpit2.py:1336` |
| `artefact_archive` | `cockpit2.py:1363` |
| `pagina_feit_add` | `cockpit2.py:1383` |
| `pagina_feit_del` | `cockpit2.py:1412` |
| `pagina_voorstel` | `cockpit2.py:1443` |
| `proj_status` | `cockpit2.py:1473` |
| `proj_done` | `cockpit2.py:1491` |
| `proj_dod` | `cockpit2.py:1585` |
| `proj_archive` | `cockpit2.py:1599` |
| `proj_unarchive` | `cockpit2.py:1622` |
| `proj_delete` | `cockpit2.py:1632` |
| `proj_edit` | `cockpit2.py:1659` |
| `proj_comment` | `cockpit2.py:1672` |
| `proj_rename` | `cockpit2.py:1682` |
| `proj_describe` | `cockpit2.py:1693` |
| `proj_doc_edit` | `cockpit2.py:1827` |
| `verslag_bevestig_behaald` | `cockpit2.py:1768` |
| `verslag_bevestig_niet_behaald` | `cockpit2.py:1774` |
| `verslag_overslaan` | `cockpit2.py:1779` |
| `verslag_bijwerken` | `cockpit2.py:1805` |
| `proj_regen_doc` | `cockpit2.py:1704` |
| `proj_settrekker` | `cockpit2.py:1840` |
| `proj_setowner` | `cockpit2.py:1881` |
| `proj_approve` | `cockpit2.py:1900` |
| `proj_discard` | `cockpit2.py:1911` |
| `proj_proposal_accept` | `cockpit2.py:1922` |
| `proj_proposal_reject` | `cockpit2.py:1935` |
| `proj_setlabel` | `cockpit2.py:1948` |
| `proj_setimpact` | `cockpit2.py:1963` |
| `proj_seteffort` | `cockpit2.py:1982` |
| `proj_agendeer_verzwakt` | `cockpit2.py:2005` |
| `proj_setprivate` | `cockpit2.py:2029` |
| `proj_setdue` | `cockpit2.py:2040` |
| `attach_add` | `cockpit2.py:2051` |
| `attach_remove` | `cockpit2.py:2062` |
| `react_add` | `cockpit2.py:2072` |
| `feed_edit` | `cockpit2.py:2082` |
| `feed_remove` | `cockpit2.py:2092` |
| `wall_outcome` | `cockpit2.py:3712` |
| `notif_read` | `cockpit2.py:3808` |
| `notif_processed` | `cockpit2.py:3813` |
| `notif_outcome` | `cockpit2.py:4077` |
| `notif_klaar` | `cockpit2.py:4024` |
| `goedkeur` | `cockpit2.py:3818` |
| `notif_delete` | `cockpit2.py:3863` |
| `notif_add` | `cockpit2.py:3975` |
| `notif_archive` | `cockpit2.py:4194` |
| `metrics2_fav` | `cockpit2.py:3869` |
| `metrics2_unfav` | `cockpit2.py:3879` |
| `metrics2_form` | `cockpit2.py:3884` |
| `metrics2_dim` | `cockpit2.py:3890` |
| `metrics2_compare` | `cockpit2.py:3897` |
| `metrics2_formula` | `cockpit2.py:3960` |
| `source_activate` | `cockpit2.py:3943` |
| `source_deactivate` | `cockpit2.py:3952` |
| `link_pursue` | `cockpit2.py:3924` |
| `link_ignore` | `cockpit2.py:3934` |
| `acc_check` | `cockpit2.py:3905` |
| `ai_reply` | `cockpit2.py:2101` |
| `proj_feed` | `cockpit2.py:2112` |
| `checklist_add` | `cockpit2.py:2159` |
| `checklist_remove` | `cockpit2.py:2199` |
| `plan_akkoord` | `cockpit2.py:2182` |
| `checklist_uitvoer` | `cockpit2.py:2170` |
| `check_add` | `cockpit2.py:2249` |
| `check_accept` | `cockpit2.py:2266` |
| `check_toggle` | `cockpit2.py:2276` |
| `check_skip` | `cockpit2.py:2298` |
| `check_unskip` | `cockpit2.py:2310` |
| `check_handoff` | `cockpit2.py:2331` |
| `check_remove` | `cockpit2.py:2379` |
| `role_assign` | `cockpit2.py:2389` |
| `role_unassign` | `cockpit2.py:2407` |
| `role_focus` | `cockpit2.py:2426` |
| `radar_approve` | `cockpit2.py:2459` |
| `radar_dismiss` | `cockpit2.py:2469` |
| `radar_promote` | `cockpit2.py:2473` |
| `radar_merge` | `cockpit2.py:2493` |
| `radar_koppel` | `cockpit2.py:2509` |
| `kb_stage_koppel` | `cockpit2.py:2536` |
| `aitask_add` | `cockpit2.py:2574` |
| `aitask_remove` | `cockpit2.py:2605` |
| `skilllink_add` | `cockpit2.py:2633` |
| `means_gap_add` | `cockpit2.py:2663` |
| `persona_skill_add` | `cockpit2.py:2817` |
| `rov2_add` | `cockpit2.py:2832` |
| `rov2_add_to_group` | `cockpit2.py:2844` |
| `rov2_remove` | `cockpit2.py:2856` |
| `rov2_remove_group` | `cockpit2.py:2871` |
| `rov2_setkind` | `cockpit2.py:2889` |
| `rov2_consent` | `cockpit2.py:2902` |
| `rov2_end` | `cockpit2.py:2924` |
| `wo_open` | `cockpit2.py:2948` |
| `wo_close` | `cockpit2.py:2958` |
| `wo_presence` | `cockpit2.py:2974` |
| `wo_present_all` | `cockpit2.py:2985` |
| `vangst_add` | `cockpit2.py:2997` |
| `vangst_tekst` | `cockpit2.py:3045` |
| `vangst_klaar` | `cockpit2.py:3055` |
| `vangst_uitkomst` | `cockpit2.py:3104` |
| `vangst_uitkomst_weg` | `cockpit2.py:3092` |
| `vangst_uitkomst_edit` | `cockpit2.py:3067` |
| `vangst_remove` | `cockpit2.py:3036` |
| `vangst_verwerk` | `cockpit2.py:3220` |
| `wo_checkout` | `cockpit2.py:4199` |
| `noochie_send` | `cockpit2.py:4214` |
| `noochie_reset` | `cockpit2.py:4240` |
| `noochie_ctx` | `cockpit2.py:4247` |
| `cl_add` | `cockpit2.py:4254` |
| `cl_report` | `cockpit2.py:4272` |
| `cl_remove` | `cockpit2.py:4287` |
| `m_add_kpi` | `cockpit2.py:4297` |
| `m_add_from_def` | `cockpit2.py:4329` |
| `def_add` | `cockpit2.py:4344` |
| `catalog_publish` | `cockpit2.py:4366` |
| `def_amend` | `cockpit2.py:4392` |
| `m_add_link` | `cockpit2.py:4434` |
| `m_sample` | `cockpit2.py:4445` |
| `m_remove` | `cockpit2.py:4455` |
| `m_pin` | `cockpit2.py:4465` |
| `m_unpin` | `cockpit2.py:4476` |
| `tile_add` | `cockpit2.py:4514` |
| `indicator_activate` | `cockpit2.py:4486` |
| `tile_remove` | `cockpit2.py:4548` |
| `rov2_set` | `cockpit2.py:4558` |
| `rov2_acc_add` | `cockpit2.py:4558` |
| `rov2_acc_remove` | `cockpit2.py:4558` |
| `rov2_dom_add` | `cockpit2.py:4558` |
| `rov2_dom_remove` | `cockpit2.py:4558` |
| `backlog_add` | `cockpit2.py:4590` |
| `backlog_update_staat` | `cockpit2.py:4602` |
| `backlog_update_prioriteit` | `cockpit2.py:4614` |
| `person_edit` | `cockpit2.py:4626` |
| `person_remove` | `cockpit2.py:4643` |
| `lk_mute` | `cockpit2.py:4664` |
| `claims_term_add` | `cockpit2.py:4767` |
| `claims_term_retract` | `cockpit2.py:4804` |
| `claims_work_status` | `cockpit2.py:4788` |
| `claims_bewijs_link` | `cockpit2.py:4833` |
| `claims_vondst_whitelist` | `cockpit2.py:4857` |
| `claims_regel_uit_vondst` | `cockpit2.py:4883` |
| `claims_to_board` | `cockpit2.py:4915` |
| `persona_edit` | `cockpit2.py:2716` |
| `persona_llm` | `cockpit2.py:2735` |
| `persona_finetune` | `cockpit2.py:2752` |
| `persona_finetune_apply` | `cockpit2.py:2770` |


## (c) Concern → store → bestand

De stores uit `_Stores.__init__` (cockpit2.py): het attribuut (de handle), de store-klasse en het databestand in `data/` (gitignored).

| Concern (st.…) | Store-klasse | Databestand |
|---|---|---|
| `records` | `Records` | `governance_records.json` |
| `people` | `PeopleStore` | `people.json` |
| `assign` | `Assignments` | `assignments.json` |
| `att` | `AttachmentStore` | `attachments.json` |
| `observations` | `ObservationStore` | `observations.jsonl` |
| `evidence` | `EvidenceLedger` | `evidence_ledger.jsonl` |
| `sources` | `SourceStatusStore` | `sources.json` |
| `personas` | `PersonaStore` | `personas.json` |
| `projects` | `ProjectLedger` | `projects.json` |
| `deliverables` | `DeliverableStore` | `deliverables.json` |
| `ai` | `AITaskStore` | `ai_tasks.json` |
| `match` | `ai_match.MatchCache` | `ai_match_cache.json` |
| `notif` | `NotifStore` | `notifications.json` |
| `agenda` | `Agenda` | `roloverleg_agenda.json` |
| `noochie` | `NoochieStore` | `noochie.json` |
| `checklists` | `ChecklistStore` | `checklists.json` |
| `metrics` | `MetricStore` | `metrics.json` |
| `defs` | `DefinitionStore` | `definitions.json` |
| `werk` | `WerkoverlegStore` | `werkoverleg.json` |
| `strategies` | `StrategyStore` | `strategies.json` |
| `backlog` | `BacklogStore` | `backlog.json` |
| `copy_stack` | `CopyStackConfig` | `copy_stack.json` |
| `radar` | `RadarStore` | `radar.json` |
| `radar_besluiten` | `ClusterBesluitStore` | `radar_clusters.json` |
| `kennisbank` | `KennisbankStore` | `kennisbank.json` |
| `notes` | `NotesStore` | `notes.json` |
| `spel` | `SpelStore` | `kennisbank_spel.json` |
| `staging` | `StagingStore` | `kennisbank_staging.json` |
| `library` | `Library` | `library.json` |
| `nominations` | `NominationQueue` | `keyword_nominaties.json` |
| `nom_kroniek` | `NominationKroniek` | `keyword_nominaties.jsonl` |
| `link_kroniek` | `SkillLinkKroniek` | `skill_links_kroniek.jsonl` |


---
_59 routes · 195 dispatch-acties · 32 stores._
