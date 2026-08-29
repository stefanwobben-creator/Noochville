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
| `ff_beslis` | `cockpit2.py:4957` |
| `ff_cluster` | `cockpit2.py:5085` |
| `ff_promote` | `cockpit2.py:5015` |
| `ff_demote` | `cockpit2.py:5039` |
| `ff_run` | `cockpit2.py:5058` |
| `kb_new` | `cockpit2.py:4337` |
| `kb_intake` | `cockpit2.py:4419` |
| `kb_intake_url` | `cockpit2.py:4436` |
| `kb_stage_edit` | `cockpit2.py:4455` |
| `kb_stage_accept` | `cockpit2.py:4467` |
| `kb_stage_delete` | `cockpit2.py:4486` |
| `kb_stage_merge` | `cockpit2.py:4492` |
| `kb_stage_commit` | `cockpit2.py:4503` |
| `kb_stage_discard` | `cockpit2.py:4523` |
| `kb_atoom_subject` | `cockpit2.py:4761` |
| `kb_atoom_purge` | `cockpit2.py:4745` |
| `tag_voorstel_besluit` | `cockpit2.py:4599` |
| `tag_onderhoud_run` | `cockpit2.py:4732` |
| `copy_stack_inclusie` | `cockpit2.py:4714` |
| `verzoek_besluit` | `cockpit2.py:4618` |
| `kb_blacklist_leeg` | `cockpit2.py:4754` |
| `kb_atoom_edit` | `cockpit2.py:4529` |
| `kb_atoom_related` | `cockpit2.py:4536` |
| `kb_atoom_reference` | `cockpit2.py:4581` |
| `kb_insight_link` | `cockpit2.py:4548` |
| `kb_insight_unlink` | `cockpit2.py:4555` |
| `kb_meta_start` | `cockpit2.py:4561` |
| `kb_atoom_merge` | `cockpit2.py:4772` |
| `kb_atoom_archive` | `cockpit2.py:4793` |
| `kb_atoom_unarchive` | `cockpit2.py:4802` |
| `kb_atoom_naar_spel` | `cockpit2.py:4808` |
| `kb_spel_start` | `cockpit2.py:4829` |
| `kb_spel_add` | `cockpit2.py:4843` |
| `kb_spel_remove` | `cockpit2.py:4853` |
| `kb_spel_flip` | `cockpit2.py:4860` |
| `kb_spel_finish` | `cockpit2.py:4866` |
| `kb_link` | `cockpit2.py:4346` |
| `kb_unlink` | `cockpit2.py:4360` |
| `kb_annotate` | `cockpit2.py:4371` |
| `kb_evidence` | `cockpit2.py:4377` |
| `kb_discuss` | `cockpit2.py:4398` |
| `kb_reformulate` | `cockpit2.py:4404` |
| `kw_nominate` | `cockpit2.py:4877` |
| `kw_nom_accept` | `cockpit2.py:4888` |
| `kw_nom_reject` | `cockpit2.py:4906` |
| `ws_forbid` | `cockpit2.py:4936` |
| `ws_approve` | `cockpit2.py:4941` |
| `proj_add` | `cockpit2.py:1207` |
| `artefact_add` | `cockpit2.py:1251` |
| `artefact_edit` | `cockpit2.py:1295` |
| `artefact_archive` | `cockpit2.py:1322` |
| `pagina_feit_add` | `cockpit2.py:1342` |
| `pagina_feit_del` | `cockpit2.py:1371` |
| `pagina_voorstel` | `cockpit2.py:1402` |
| `proj_status` | `cockpit2.py:1432` |
| `proj_done` | `cockpit2.py:1450` |
| `proj_dod` | `cockpit2.py:1505` |
| `proj_archive` | `cockpit2.py:1519` |
| `proj_unarchive` | `cockpit2.py:1542` |
| `proj_delete` | `cockpit2.py:1552` |
| `proj_edit` | `cockpit2.py:1579` |
| `proj_comment` | `cockpit2.py:1592` |
| `proj_rename` | `cockpit2.py:1602` |
| `proj_describe` | `cockpit2.py:1613` |
| `proj_doc_edit` | `cockpit2.py:1646` |
| `proj_regen_doc` | `cockpit2.py:1624` |
| `proj_settrekker` | `cockpit2.py:1659` |
| `proj_setowner` | `cockpit2.py:1696` |
| `proj_approve` | `cockpit2.py:1715` |
| `proj_discard` | `cockpit2.py:1726` |
| `proj_proposal_accept` | `cockpit2.py:1737` |
| `proj_proposal_reject` | `cockpit2.py:1750` |
| `proj_setlabel` | `cockpit2.py:1763` |
| `proj_setimpact` | `cockpit2.py:1778` |
| `proj_seteffort` | `cockpit2.py:1797` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1820` |
| `proj_setprivate` | `cockpit2.py:1844` |
| `proj_setdue` | `cockpit2.py:1855` |
| `attach_add` | `cockpit2.py:1866` |
| `attach_remove` | `cockpit2.py:1877` |
| `react_add` | `cockpit2.py:1887` |
| `feed_edit` | `cockpit2.py:1897` |
| `feed_remove` | `cockpit2.py:1907` |
| `wall_outcome` | `cockpit2.py:3165` |
| `notif_read` | `cockpit2.py:3261` |
| `notif_processed` | `cockpit2.py:3266` |
| `notif_outcome` | `cockpit2.py:3419` |
| `notif_besluit` | `cockpit2.py:3510` |
| `notif_klaar` | `cockpit2.py:3399` |
| `notif_delete` | `cockpit2.py:3271` |
| `notif_add` | `cockpit2.py:3383` |
| `notif_archive` | `cockpit2.py:3552` |
| `metrics2_fav` | `cockpit2.py:3277` |
| `metrics2_unfav` | `cockpit2.py:3287` |
| `metrics2_form` | `cockpit2.py:3292` |
| `metrics2_dim` | `cockpit2.py:3298` |
| `metrics2_compare` | `cockpit2.py:3305` |
| `metrics2_formula` | `cockpit2.py:3368` |
| `source_activate` | `cockpit2.py:3351` |
| `source_deactivate` | `cockpit2.py:3360` |
| `link_pursue` | `cockpit2.py:3332` |
| `link_ignore` | `cockpit2.py:3342` |
| `acc_check` | `cockpit2.py:3313` |
| `ai_reply` | `cockpit2.py:1916` |
| `proj_feed` | `cockpit2.py:1927` |
| `checklist_add` | `cockpit2.py:1957` |
| `checklist_remove` | `cockpit2.py:1968` |
| `check_add` | `cockpit2.py:2016` |
| `check_accept` | `cockpit2.py:2033` |
| `check_toggle` | `cockpit2.py:2043` |
| `check_skip` | `cockpit2.py:2065` |
| `check_unskip` | `cockpit2.py:2077` |
| `check_handoff` | `cockpit2.py:2089` |
| `check_remove` | `cockpit2.py:2103` |
| `role_assign` | `cockpit2.py:2113` |
| `role_unassign` | `cockpit2.py:2131` |
| `role_focus` | `cockpit2.py:2150` |
| `radar_approve` | `cockpit2.py:2183` |
| `radar_dismiss` | `cockpit2.py:2193` |
| `radar_promote` | `cockpit2.py:2197` |
| `radar_merge` | `cockpit2.py:2217` |
| `radar_koppel` | `cockpit2.py:2233` |
| `kb_stage_koppel` | `cockpit2.py:2260` |
| `aitask_add` | `cockpit2.py:2298` |
| `aitask_remove` | `cockpit2.py:2329` |
| `skilllink_add` | `cockpit2.py:2357` |
| `means_gap_add` | `cockpit2.py:2387` |
| `persona_skill_add` | `cockpit2.py:2541` |
| `rov2_add` | `cockpit2.py:2556` |
| `rov2_add_to_group` | `cockpit2.py:2568` |
| `rov2_remove` | `cockpit2.py:2580` |
| `rov2_remove_group` | `cockpit2.py:2595` |
| `rov2_setkind` | `cockpit2.py:2613` |
| `rov2_consent` | `cockpit2.py:2626` |
| `rov2_end` | `cockpit2.py:2648` |
| `wo_open` | `cockpit2.py:2672` |
| `wo_close` | `cockpit2.py:2682` |
| `wo_presence` | `cockpit2.py:2698` |
| `wo_present_all` | `cockpit2.py:2709` |
| `vangst_add` | `cockpit2.py:2721` |
| `vangst_tekst` | `cockpit2.py:2769` |
| `vangst_klaar` | `cockpit2.py:2779` |
| `vangst_uitkomst` | `cockpit2.py:2828` |
| `vangst_uitkomst_weg` | `cockpit2.py:2816` |
| `vangst_uitkomst_edit` | `cockpit2.py:2791` |
| `vangst_remove` | `cockpit2.py:2760` |
| `vangst_verwerk` | `cockpit2.py:2944` |
| `wo_checkout` | `cockpit2.py:3557` |
| `noochie_send` | `cockpit2.py:3572` |
| `noochie_reset` | `cockpit2.py:3598` |
| `noochie_ctx` | `cockpit2.py:3605` |
| `cl_add` | `cockpit2.py:3612` |
| `cl_report` | `cockpit2.py:3630` |
| `cl_remove` | `cockpit2.py:3645` |
| `m_add_kpi` | `cockpit2.py:3655` |
| `m_add_from_def` | `cockpit2.py:3687` |
| `def_add` | `cockpit2.py:3702` |
| `catalog_publish` | `cockpit2.py:3724` |
| `def_amend` | `cockpit2.py:3750` |
| `m_add_link` | `cockpit2.py:3792` |
| `m_sample` | `cockpit2.py:3803` |
| `m_remove` | `cockpit2.py:3813` |
| `m_pin` | `cockpit2.py:3823` |
| `m_unpin` | `cockpit2.py:3834` |
| `tile_add` | `cockpit2.py:3872` |
| `indicator_activate` | `cockpit2.py:3844` |
| `tile_remove` | `cockpit2.py:3906` |
| `rov2_set` | `cockpit2.py:3916` |
| `rov2_acc_add` | `cockpit2.py:3916` |
| `rov2_acc_remove` | `cockpit2.py:3916` |
| `rov2_dom_add` | `cockpit2.py:3916` |
| `rov2_dom_remove` | `cockpit2.py:3916` |
| `backlog_add` | `cockpit2.py:3948` |
| `backlog_update_staat` | `cockpit2.py:3960` |
| `backlog_update_prioriteit` | `cockpit2.py:3972` |
| `person_edit` | `cockpit2.py:3984` |
| `person_remove` | `cockpit2.py:4001` |
| `lk_mute` | `cockpit2.py:4022` |
| `claims_term_add` | `cockpit2.py:4125` |
| `claims_term_retract` | `cockpit2.py:4162` |
| `claims_work_status` | `cockpit2.py:4146` |
| `claims_bewijs_link` | `cockpit2.py:4191` |
| `claims_vondst_whitelist` | `cockpit2.py:4215` |
| `claims_regel_uit_vondst` | `cockpit2.py:4241` |
| `claims_to_board` | `cockpit2.py:4273` |
| `persona_edit` | `cockpit2.py:2440` |
| `persona_llm` | `cockpit2.py:2459` |
| `persona_finetune` | `cockpit2.py:2476` |
| `persona_finetune_apply` | `cockpit2.py:2494` |


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
