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
| `ff_beslis` | `cockpit2.py:4868` |
| `ff_cluster` | `cockpit2.py:4996` |
| `ff_promote` | `cockpit2.py:4926` |
| `ff_demote` | `cockpit2.py:4950` |
| `ff_run` | `cockpit2.py:4969` |
| `kb_new` | `cockpit2.py:4248` |
| `kb_intake` | `cockpit2.py:4330` |
| `kb_intake_url` | `cockpit2.py:4347` |
| `kb_stage_edit` | `cockpit2.py:4366` |
| `kb_stage_accept` | `cockpit2.py:4378` |
| `kb_stage_delete` | `cockpit2.py:4397` |
| `kb_stage_merge` | `cockpit2.py:4403` |
| `kb_stage_commit` | `cockpit2.py:4414` |
| `kb_stage_discard` | `cockpit2.py:4434` |
| `kb_atoom_subject` | `cockpit2.py:4672` |
| `kb_atoom_purge` | `cockpit2.py:4656` |
| `tag_voorstel_besluit` | `cockpit2.py:4510` |
| `tag_onderhoud_run` | `cockpit2.py:4643` |
| `copy_stack_inclusie` | `cockpit2.py:4625` |
| `verzoek_besluit` | `cockpit2.py:4529` |
| `kb_blacklist_leeg` | `cockpit2.py:4665` |
| `kb_atoom_edit` | `cockpit2.py:4440` |
| `kb_atoom_related` | `cockpit2.py:4447` |
| `kb_atoom_reference` | `cockpit2.py:4492` |
| `kb_insight_link` | `cockpit2.py:4459` |
| `kb_insight_unlink` | `cockpit2.py:4466` |
| `kb_meta_start` | `cockpit2.py:4472` |
| `kb_atoom_merge` | `cockpit2.py:4683` |
| `kb_atoom_archive` | `cockpit2.py:4704` |
| `kb_atoom_unarchive` | `cockpit2.py:4713` |
| `kb_atoom_naar_spel` | `cockpit2.py:4719` |
| `kb_spel_start` | `cockpit2.py:4740` |
| `kb_spel_add` | `cockpit2.py:4754` |
| `kb_spel_remove` | `cockpit2.py:4764` |
| `kb_spel_flip` | `cockpit2.py:4771` |
| `kb_spel_finish` | `cockpit2.py:4777` |
| `kb_link` | `cockpit2.py:4257` |
| `kb_unlink` | `cockpit2.py:4271` |
| `kb_annotate` | `cockpit2.py:4282` |
| `kb_evidence` | `cockpit2.py:4288` |
| `kb_discuss` | `cockpit2.py:4309` |
| `kb_reformulate` | `cockpit2.py:4315` |
| `kw_nominate` | `cockpit2.py:4788` |
| `kw_nom_accept` | `cockpit2.py:4799` |
| `kw_nom_reject` | `cockpit2.py:4817` |
| `ws_forbid` | `cockpit2.py:4847` |
| `ws_approve` | `cockpit2.py:4852` |
| `proj_add` | `cockpit2.py:1205` |
| `artefact_add` | `cockpit2.py:1249` |
| `artefact_edit` | `cockpit2.py:1293` |
| `artefact_archive` | `cockpit2.py:1320` |
| `pagina_feit_add` | `cockpit2.py:1340` |
| `pagina_feit_del` | `cockpit2.py:1369` |
| `pagina_voorstel` | `cockpit2.py:1400` |
| `proj_status` | `cockpit2.py:1430` |
| `proj_done` | `cockpit2.py:1448` |
| `proj_dod` | `cockpit2.py:1497` |
| `proj_archive` | `cockpit2.py:1511` |
| `proj_unarchive` | `cockpit2.py:1534` |
| `proj_delete` | `cockpit2.py:1544` |
| `proj_edit` | `cockpit2.py:1571` |
| `proj_comment` | `cockpit2.py:1584` |
| `proj_rename` | `cockpit2.py:1594` |
| `proj_describe` | `cockpit2.py:1605` |
| `proj_doc_edit` | `cockpit2.py:1638` |
| `proj_regen_doc` | `cockpit2.py:1616` |
| `proj_settrekker` | `cockpit2.py:1651` |
| `proj_setowner` | `cockpit2.py:1688` |
| `proj_approve` | `cockpit2.py:1707` |
| `proj_discard` | `cockpit2.py:1718` |
| `proj_proposal_accept` | `cockpit2.py:1729` |
| `proj_proposal_reject` | `cockpit2.py:1742` |
| `proj_setlabel` | `cockpit2.py:1755` |
| `proj_setimpact` | `cockpit2.py:1770` |
| `proj_seteffort` | `cockpit2.py:1789` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1812` |
| `proj_setprivate` | `cockpit2.py:1836` |
| `proj_setdue` | `cockpit2.py:1847` |
| `attach_add` | `cockpit2.py:1858` |
| `attach_remove` | `cockpit2.py:1869` |
| `react_add` | `cockpit2.py:1879` |
| `feed_edit` | `cockpit2.py:1889` |
| `feed_remove` | `cockpit2.py:1899` |
| `wall_outcome` | `cockpit2.py:3087` |
| `notif_read` | `cockpit2.py:3185` |
| `notif_processed` | `cockpit2.py:3190` |
| `notif_outcome` | `cockpit2.py:3337` |
| `notif_besluit` | `cockpit2.py:3424` |
| `notif_klaar` | `cockpit2.py:3323` |
| `notif_delete` | `cockpit2.py:3195` |
| `notif_add` | `cockpit2.py:3307` |
| `notif_archive` | `cockpit2.py:3466` |
| `metrics2_fav` | `cockpit2.py:3201` |
| `metrics2_unfav` | `cockpit2.py:3211` |
| `metrics2_form` | `cockpit2.py:3216` |
| `metrics2_dim` | `cockpit2.py:3222` |
| `metrics2_compare` | `cockpit2.py:3229` |
| `metrics2_formula` | `cockpit2.py:3292` |
| `source_activate` | `cockpit2.py:3275` |
| `source_deactivate` | `cockpit2.py:3284` |
| `link_pursue` | `cockpit2.py:3256` |
| `link_ignore` | `cockpit2.py:3266` |
| `acc_check` | `cockpit2.py:3237` |
| `ai_reply` | `cockpit2.py:1908` |
| `proj_feed` | `cockpit2.py:1919` |
| `checklist_add` | `cockpit2.py:1949` |
| `checklist_remove` | `cockpit2.py:1960` |
| `check_add` | `cockpit2.py:2008` |
| `check_accept` | `cockpit2.py:2025` |
| `check_toggle` | `cockpit2.py:2035` |
| `check_skip` | `cockpit2.py:2057` |
| `check_unskip` | `cockpit2.py:2069` |
| `check_handoff` | `cockpit2.py:2081` |
| `check_remove` | `cockpit2.py:2095` |
| `role_assign` | `cockpit2.py:2105` |
| `role_unassign` | `cockpit2.py:2123` |
| `role_focus` | `cockpit2.py:2142` |
| `radar_approve` | `cockpit2.py:2175` |
| `radar_dismiss` | `cockpit2.py:2185` |
| `radar_promote` | `cockpit2.py:2189` |
| `radar_merge` | `cockpit2.py:2209` |
| `radar_koppel` | `cockpit2.py:2225` |
| `kb_stage_koppel` | `cockpit2.py:2252` |
| `aitask_add` | `cockpit2.py:2290` |
| `aitask_remove` | `cockpit2.py:2321` |
| `skilllink_add` | `cockpit2.py:2349` |
| `means_gap_add` | `cockpit2.py:2379` |
| `persona_skill_add` | `cockpit2.py:2533` |
| `rov2_add` | `cockpit2.py:2548` |
| `rov2_add_to_group` | `cockpit2.py:2560` |
| `rov2_remove` | `cockpit2.py:2572` |
| `rov2_remove_group` | `cockpit2.py:2587` |
| `rov2_setkind` | `cockpit2.py:2605` |
| `rov2_consent` | `cockpit2.py:2618` |
| `rov2_end` | `cockpit2.py:2640` |
| `wo_open` | `cockpit2.py:2664` |
| `wo_close` | `cockpit2.py:2674` |
| `wo_presence` | `cockpit2.py:2690` |
| `wo_present_all` | `cockpit2.py:2701` |
| `vangst_add` | `cockpit2.py:2713` |
| `vangst_tekst` | `cockpit2.py:2761` |
| `vangst_klaar` | `cockpit2.py:2771` |
| `vangst_uitkomst` | `cockpit2.py:2820` |
| `vangst_uitkomst_weg` | `cockpit2.py:2808` |
| `vangst_uitkomst_edit` | `cockpit2.py:2783` |
| `vangst_remove` | `cockpit2.py:2752` |
| `vangst_verwerk` | `cockpit2.py:2932` |
| `wo_checkout` | `cockpit2.py:3471` |
| `noochie_send` | `cockpit2.py:3483` |
| `noochie_reset` | `cockpit2.py:3509` |
| `noochie_ctx` | `cockpit2.py:3516` |
| `cl_add` | `cockpit2.py:3523` |
| `cl_report` | `cockpit2.py:3541` |
| `cl_remove` | `cockpit2.py:3556` |
| `m_add_kpi` | `cockpit2.py:3566` |
| `m_add_from_def` | `cockpit2.py:3598` |
| `def_add` | `cockpit2.py:3613` |
| `catalog_publish` | `cockpit2.py:3635` |
| `def_amend` | `cockpit2.py:3661` |
| `m_add_link` | `cockpit2.py:3703` |
| `m_sample` | `cockpit2.py:3714` |
| `m_remove` | `cockpit2.py:3724` |
| `m_pin` | `cockpit2.py:3734` |
| `m_unpin` | `cockpit2.py:3745` |
| `tile_add` | `cockpit2.py:3783` |
| `indicator_activate` | `cockpit2.py:3755` |
| `tile_remove` | `cockpit2.py:3817` |
| `rov2_set` | `cockpit2.py:3827` |
| `rov2_acc_add` | `cockpit2.py:3827` |
| `rov2_acc_remove` | `cockpit2.py:3827` |
| `rov2_dom_add` | `cockpit2.py:3827` |
| `rov2_dom_remove` | `cockpit2.py:3827` |
| `backlog_add` | `cockpit2.py:3859` |
| `backlog_update_staat` | `cockpit2.py:3871` |
| `backlog_update_prioriteit` | `cockpit2.py:3883` |
| `person_edit` | `cockpit2.py:3895` |
| `person_remove` | `cockpit2.py:3912` |
| `lk_mute` | `cockpit2.py:3933` |
| `claims_term_add` | `cockpit2.py:4036` |
| `claims_term_retract` | `cockpit2.py:4073` |
| `claims_work_status` | `cockpit2.py:4057` |
| `claims_bewijs_link` | `cockpit2.py:4102` |
| `claims_vondst_whitelist` | `cockpit2.py:4126` |
| `claims_regel_uit_vondst` | `cockpit2.py:4152` |
| `claims_to_board` | `cockpit2.py:4184` |
| `persona_edit` | `cockpit2.py:2432` |
| `persona_llm` | `cockpit2.py:2451` |
| `persona_finetune` | `cockpit2.py:2468` |
| `persona_finetune_apply` | `cockpit2.py:2486` |


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
_57 routes · 189 dispatch-acties · 32 stores._
