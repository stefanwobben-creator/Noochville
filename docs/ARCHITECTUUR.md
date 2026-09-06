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
| `ff_beslis` | `cockpit2.py:5502` |
| `ff_cluster` | `cockpit2.py:5630` |
| `ff_promote` | `cockpit2.py:5560` |
| `ff_demote` | `cockpit2.py:5584` |
| `ff_run` | `cockpit2.py:5603` |
| `kb_new` | `cockpit2.py:4865` |
| `kb_intake` | `cockpit2.py:4947` |
| `kb_intake_url` | `cockpit2.py:4964` |
| `kb_stage_edit` | `cockpit2.py:4983` |
| `kb_stage_accept` | `cockpit2.py:4995` |
| `kb_stage_delete` | `cockpit2.py:5014` |
| `kb_stage_merge` | `cockpit2.py:5020` |
| `kb_stage_commit` | `cockpit2.py:5031` |
| `kb_stage_discard` | `cockpit2.py:5051` |
| `kb_atoom_subject` | `cockpit2.py:5306` |
| `kb_atoom_purge` | `cockpit2.py:5290` |
| `tag_voorstel_besluit` | `cockpit2.py:5127` |
| `tag_onderhoud_run` | `cockpit2.py:5277` |
| `copy_stack_inclusie` | `cockpit2.py:5259` |
| `verzoek_besluit` | `cockpit2.py:5146` |
| `kb_blacklist_leeg` | `cockpit2.py:5299` |
| `kb_atoom_edit` | `cockpit2.py:5057` |
| `kb_atoom_related` | `cockpit2.py:5064` |
| `kb_atoom_reference` | `cockpit2.py:5109` |
| `kb_insight_link` | `cockpit2.py:5076` |
| `kb_insight_unlink` | `cockpit2.py:5083` |
| `kb_meta_start` | `cockpit2.py:5089` |
| `kb_atoom_merge` | `cockpit2.py:5317` |
| `kb_atoom_archive` | `cockpit2.py:5338` |
| `kb_atoom_unarchive` | `cockpit2.py:5347` |
| `kb_atoom_naar_spel` | `cockpit2.py:5353` |
| `kb_spel_start` | `cockpit2.py:5374` |
| `kb_spel_add` | `cockpit2.py:5388` |
| `kb_spel_remove` | `cockpit2.py:5398` |
| `kb_spel_flip` | `cockpit2.py:5405` |
| `kb_spel_finish` | `cockpit2.py:5411` |
| `kb_link` | `cockpit2.py:4874` |
| `kb_unlink` | `cockpit2.py:4888` |
| `kb_annotate` | `cockpit2.py:4899` |
| `kb_evidence` | `cockpit2.py:4905` |
| `kb_discuss` | `cockpit2.py:4926` |
| `kb_reformulate` | `cockpit2.py:4932` |
| `kw_nominate` | `cockpit2.py:5422` |
| `kw_nom_accept` | `cockpit2.py:5433` |
| `kw_nom_reject` | `cockpit2.py:5451` |
| `ws_forbid` | `cockpit2.py:5481` |
| `ws_approve` | `cockpit2.py:5486` |
| `proj_add` | `cockpit2.py:1214` |
| `artefact_add` | `cockpit2.py:1267` |
| `artefact_edit` | `cockpit2.py:1311` |
| `artefact_archive` | `cockpit2.py:1338` |
| `pagina_feit_add` | `cockpit2.py:1358` |
| `pagina_feit_del` | `cockpit2.py:1387` |
| `pagina_voorstel` | `cockpit2.py:1418` |
| `proj_status` | `cockpit2.py:1448` |
| `proj_done` | `cockpit2.py:1466` |
| `proj_dod` | `cockpit2.py:1560` |
| `proj_archive` | `cockpit2.py:1574` |
| `proj_unarchive` | `cockpit2.py:1597` |
| `proj_delete` | `cockpit2.py:1607` |
| `proj_edit` | `cockpit2.py:1634` |
| `proj_comment` | `cockpit2.py:1647` |
| `proj_rename` | `cockpit2.py:1657` |
| `proj_describe` | `cockpit2.py:1668` |
| `proj_doc_edit` | `cockpit2.py:1802` |
| `verslag_bevestig_behaald` | `cockpit2.py:1743` |
| `verslag_bevestig_niet_behaald` | `cockpit2.py:1749` |
| `verslag_overslaan` | `cockpit2.py:1754` |
| `verslag_bijwerken` | `cockpit2.py:1780` |
| `proj_regen_doc` | `cockpit2.py:1679` |
| `proj_settrekker` | `cockpit2.py:1815` |
| `proj_setowner` | `cockpit2.py:1856` |
| `proj_approve` | `cockpit2.py:1875` |
| `proj_discard` | `cockpit2.py:1886` |
| `proj_proposal_accept` | `cockpit2.py:1897` |
| `proj_proposal_reject` | `cockpit2.py:1910` |
| `proj_setlabel` | `cockpit2.py:1923` |
| `proj_setimpact` | `cockpit2.py:1938` |
| `proj_seteffort` | `cockpit2.py:1957` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1980` |
| `proj_setprivate` | `cockpit2.py:2004` |
| `proj_setdue` | `cockpit2.py:2015` |
| `attach_add` | `cockpit2.py:2026` |
| `attach_remove` | `cockpit2.py:2037` |
| `react_add` | `cockpit2.py:2047` |
| `feed_edit` | `cockpit2.py:2057` |
| `feed_remove` | `cockpit2.py:2067` |
| `wall_outcome` | `cockpit2.py:3643` |
| `notif_read` | `cockpit2.py:3739` |
| `notif_processed` | `cockpit2.py:3744` |
| `notif_outcome` | `cockpit2.py:3963` |
| `notif_klaar` | `cockpit2.py:3910` |
| `notif_delete` | `cockpit2.py:3749` |
| `notif_add` | `cockpit2.py:3861` |
| `notif_archive` | `cockpit2.py:4080` |
| `metrics2_fav` | `cockpit2.py:3755` |
| `metrics2_unfav` | `cockpit2.py:3765` |
| `metrics2_form` | `cockpit2.py:3770` |
| `metrics2_dim` | `cockpit2.py:3776` |
| `metrics2_compare` | `cockpit2.py:3783` |
| `metrics2_formula` | `cockpit2.py:3846` |
| `source_activate` | `cockpit2.py:3829` |
| `source_deactivate` | `cockpit2.py:3838` |
| `link_pursue` | `cockpit2.py:3810` |
| `link_ignore` | `cockpit2.py:3820` |
| `acc_check` | `cockpit2.py:3791` |
| `ai_reply` | `cockpit2.py:2076` |
| `proj_feed` | `cockpit2.py:2087` |
| `checklist_add` | `cockpit2.py:2134` |
| `checklist_remove` | `cockpit2.py:2174` |
| `plan_akkoord` | `cockpit2.py:2157` |
| `checklist_uitvoer` | `cockpit2.py:2145` |
| `check_add` | `cockpit2.py:2223` |
| `check_accept` | `cockpit2.py:2240` |
| `check_toggle` | `cockpit2.py:2250` |
| `check_skip` | `cockpit2.py:2272` |
| `check_unskip` | `cockpit2.py:2284` |
| `check_handoff` | `cockpit2.py:2296` |
| `check_remove` | `cockpit2.py:2310` |
| `role_assign` | `cockpit2.py:2320` |
| `role_unassign` | `cockpit2.py:2338` |
| `role_focus` | `cockpit2.py:2357` |
| `radar_approve` | `cockpit2.py:2390` |
| `radar_dismiss` | `cockpit2.py:2400` |
| `radar_promote` | `cockpit2.py:2404` |
| `radar_merge` | `cockpit2.py:2424` |
| `radar_koppel` | `cockpit2.py:2440` |
| `kb_stage_koppel` | `cockpit2.py:2467` |
| `aitask_add` | `cockpit2.py:2505` |
| `aitask_remove` | `cockpit2.py:2536` |
| `skilllink_add` | `cockpit2.py:2564` |
| `means_gap_add` | `cockpit2.py:2594` |
| `persona_skill_add` | `cockpit2.py:2748` |
| `rov2_add` | `cockpit2.py:2763` |
| `rov2_add_to_group` | `cockpit2.py:2775` |
| `rov2_remove` | `cockpit2.py:2787` |
| `rov2_remove_group` | `cockpit2.py:2802` |
| `rov2_setkind` | `cockpit2.py:2820` |
| `rov2_consent` | `cockpit2.py:2833` |
| `rov2_end` | `cockpit2.py:2855` |
| `wo_open` | `cockpit2.py:2879` |
| `wo_close` | `cockpit2.py:2889` |
| `wo_presence` | `cockpit2.py:2905` |
| `wo_present_all` | `cockpit2.py:2916` |
| `vangst_add` | `cockpit2.py:2928` |
| `vangst_tekst` | `cockpit2.py:2976` |
| `vangst_klaar` | `cockpit2.py:2986` |
| `vangst_uitkomst` | `cockpit2.py:3035` |
| `vangst_uitkomst_weg` | `cockpit2.py:3023` |
| `vangst_uitkomst_edit` | `cockpit2.py:2998` |
| `vangst_remove` | `cockpit2.py:2967` |
| `vangst_verwerk` | `cockpit2.py:3151` |
| `wo_checkout` | `cockpit2.py:4085` |
| `noochie_send` | `cockpit2.py:4100` |
| `noochie_reset` | `cockpit2.py:4126` |
| `noochie_ctx` | `cockpit2.py:4133` |
| `cl_add` | `cockpit2.py:4140` |
| `cl_report` | `cockpit2.py:4158` |
| `cl_remove` | `cockpit2.py:4173` |
| `m_add_kpi` | `cockpit2.py:4183` |
| `m_add_from_def` | `cockpit2.py:4215` |
| `def_add` | `cockpit2.py:4230` |
| `catalog_publish` | `cockpit2.py:4252` |
| `def_amend` | `cockpit2.py:4278` |
| `m_add_link` | `cockpit2.py:4320` |
| `m_sample` | `cockpit2.py:4331` |
| `m_remove` | `cockpit2.py:4341` |
| `m_pin` | `cockpit2.py:4351` |
| `m_unpin` | `cockpit2.py:4362` |
| `tile_add` | `cockpit2.py:4400` |
| `indicator_activate` | `cockpit2.py:4372` |
| `tile_remove` | `cockpit2.py:4434` |
| `rov2_set` | `cockpit2.py:4444` |
| `rov2_acc_add` | `cockpit2.py:4444` |
| `rov2_acc_remove` | `cockpit2.py:4444` |
| `rov2_dom_add` | `cockpit2.py:4444` |
| `rov2_dom_remove` | `cockpit2.py:4444` |
| `backlog_add` | `cockpit2.py:4476` |
| `backlog_update_staat` | `cockpit2.py:4488` |
| `backlog_update_prioriteit` | `cockpit2.py:4500` |
| `person_edit` | `cockpit2.py:4512` |
| `person_remove` | `cockpit2.py:4529` |
| `lk_mute` | `cockpit2.py:4550` |
| `claims_term_add` | `cockpit2.py:4653` |
| `claims_term_retract` | `cockpit2.py:4690` |
| `claims_work_status` | `cockpit2.py:4674` |
| `claims_bewijs_link` | `cockpit2.py:4719` |
| `claims_vondst_whitelist` | `cockpit2.py:4743` |
| `claims_regel_uit_vondst` | `cockpit2.py:4769` |
| `claims_to_board` | `cockpit2.py:4801` |
| `persona_edit` | `cockpit2.py:2647` |
| `persona_llm` | `cockpit2.py:2666` |
| `persona_finetune` | `cockpit2.py:2683` |
| `persona_finetune_apply` | `cockpit2.py:2701` |


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
_59 routes · 194 dispatch-acties · 32 stores._
