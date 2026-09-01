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
| `ff_beslis` | `cockpit2.py:5183` |
| `ff_cluster` | `cockpit2.py:5311` |
| `ff_promote` | `cockpit2.py:5241` |
| `ff_demote` | `cockpit2.py:5265` |
| `ff_run` | `cockpit2.py:5284` |
| `kb_new` | `cockpit2.py:4546` |
| `kb_intake` | `cockpit2.py:4628` |
| `kb_intake_url` | `cockpit2.py:4645` |
| `kb_stage_edit` | `cockpit2.py:4664` |
| `kb_stage_accept` | `cockpit2.py:4676` |
| `kb_stage_delete` | `cockpit2.py:4695` |
| `kb_stage_merge` | `cockpit2.py:4701` |
| `kb_stage_commit` | `cockpit2.py:4712` |
| `kb_stage_discard` | `cockpit2.py:4732` |
| `kb_atoom_subject` | `cockpit2.py:4987` |
| `kb_atoom_purge` | `cockpit2.py:4971` |
| `tag_voorstel_besluit` | `cockpit2.py:4808` |
| `tag_onderhoud_run` | `cockpit2.py:4958` |
| `copy_stack_inclusie` | `cockpit2.py:4940` |
| `verzoek_besluit` | `cockpit2.py:4827` |
| `kb_blacklist_leeg` | `cockpit2.py:4980` |
| `kb_atoom_edit` | `cockpit2.py:4738` |
| `kb_atoom_related` | `cockpit2.py:4745` |
| `kb_atoom_reference` | `cockpit2.py:4790` |
| `kb_insight_link` | `cockpit2.py:4757` |
| `kb_insight_unlink` | `cockpit2.py:4764` |
| `kb_meta_start` | `cockpit2.py:4770` |
| `kb_atoom_merge` | `cockpit2.py:4998` |
| `kb_atoom_archive` | `cockpit2.py:5019` |
| `kb_atoom_unarchive` | `cockpit2.py:5028` |
| `kb_atoom_naar_spel` | `cockpit2.py:5034` |
| `kb_spel_start` | `cockpit2.py:5055` |
| `kb_spel_add` | `cockpit2.py:5069` |
| `kb_spel_remove` | `cockpit2.py:5079` |
| `kb_spel_flip` | `cockpit2.py:5086` |
| `kb_spel_finish` | `cockpit2.py:5092` |
| `kb_link` | `cockpit2.py:4555` |
| `kb_unlink` | `cockpit2.py:4569` |
| `kb_annotate` | `cockpit2.py:4580` |
| `kb_evidence` | `cockpit2.py:4586` |
| `kb_discuss` | `cockpit2.py:4607` |
| `kb_reformulate` | `cockpit2.py:4613` |
| `kw_nominate` | `cockpit2.py:5103` |
| `kw_nom_accept` | `cockpit2.py:5114` |
| `kw_nom_reject` | `cockpit2.py:5132` |
| `ws_forbid` | `cockpit2.py:5162` |
| `ws_approve` | `cockpit2.py:5167` |
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
| `wall_outcome` | `cockpit2.py:3347` |
| `notif_read` | `cockpit2.py:3443` |
| `notif_processed` | `cockpit2.py:3448` |
| `notif_outcome` | `cockpit2.py:3657` |
| `notif_klaar` | `cockpit2.py:3614` |
| `notif_delete` | `cockpit2.py:3453` |
| `notif_add` | `cockpit2.py:3565` |
| `notif_archive` | `cockpit2.py:3761` |
| `metrics2_fav` | `cockpit2.py:3459` |
| `metrics2_unfav` | `cockpit2.py:3469` |
| `metrics2_form` | `cockpit2.py:3474` |
| `metrics2_dim` | `cockpit2.py:3480` |
| `metrics2_compare` | `cockpit2.py:3487` |
| `metrics2_formula` | `cockpit2.py:3550` |
| `source_activate` | `cockpit2.py:3533` |
| `source_deactivate` | `cockpit2.py:3542` |
| `link_pursue` | `cockpit2.py:3514` |
| `link_ignore` | `cockpit2.py:3524` |
| `acc_check` | `cockpit2.py:3495` |
| `ai_reply` | `cockpit2.py:1916` |
| `proj_feed` | `cockpit2.py:1927` |
| `checklist_add` | `cockpit2.py:1974` |
| `checklist_remove` | `cockpit2.py:1985` |
| `check_add` | `cockpit2.py:2033` |
| `check_accept` | `cockpit2.py:2050` |
| `check_toggle` | `cockpit2.py:2060` |
| `check_skip` | `cockpit2.py:2082` |
| `check_unskip` | `cockpit2.py:2094` |
| `check_handoff` | `cockpit2.py:2106` |
| `check_remove` | `cockpit2.py:2120` |
| `role_assign` | `cockpit2.py:2130` |
| `role_unassign` | `cockpit2.py:2148` |
| `role_focus` | `cockpit2.py:2167` |
| `radar_approve` | `cockpit2.py:2200` |
| `radar_dismiss` | `cockpit2.py:2210` |
| `radar_promote` | `cockpit2.py:2214` |
| `radar_merge` | `cockpit2.py:2234` |
| `radar_koppel` | `cockpit2.py:2250` |
| `kb_stage_koppel` | `cockpit2.py:2277` |
| `aitask_add` | `cockpit2.py:2315` |
| `aitask_remove` | `cockpit2.py:2346` |
| `skilllink_add` | `cockpit2.py:2374` |
| `means_gap_add` | `cockpit2.py:2404` |
| `persona_skill_add` | `cockpit2.py:2558` |
| `rov2_add` | `cockpit2.py:2573` |
| `rov2_add_to_group` | `cockpit2.py:2585` |
| `rov2_remove` | `cockpit2.py:2597` |
| `rov2_remove_group` | `cockpit2.py:2612` |
| `rov2_setkind` | `cockpit2.py:2630` |
| `rov2_consent` | `cockpit2.py:2643` |
| `rov2_end` | `cockpit2.py:2665` |
| `wo_open` | `cockpit2.py:2689` |
| `wo_close` | `cockpit2.py:2699` |
| `wo_presence` | `cockpit2.py:2715` |
| `wo_present_all` | `cockpit2.py:2726` |
| `vangst_add` | `cockpit2.py:2738` |
| `vangst_tekst` | `cockpit2.py:2786` |
| `vangst_klaar` | `cockpit2.py:2796` |
| `vangst_uitkomst` | `cockpit2.py:2845` |
| `vangst_uitkomst_weg` | `cockpit2.py:2833` |
| `vangst_uitkomst_edit` | `cockpit2.py:2808` |
| `vangst_remove` | `cockpit2.py:2777` |
| `vangst_verwerk` | `cockpit2.py:2961` |
| `wo_checkout` | `cockpit2.py:3766` |
| `noochie_send` | `cockpit2.py:3781` |
| `noochie_reset` | `cockpit2.py:3807` |
| `noochie_ctx` | `cockpit2.py:3814` |
| `cl_add` | `cockpit2.py:3821` |
| `cl_report` | `cockpit2.py:3839` |
| `cl_remove` | `cockpit2.py:3854` |
| `m_add_kpi` | `cockpit2.py:3864` |
| `m_add_from_def` | `cockpit2.py:3896` |
| `def_add` | `cockpit2.py:3911` |
| `catalog_publish` | `cockpit2.py:3933` |
| `def_amend` | `cockpit2.py:3959` |
| `m_add_link` | `cockpit2.py:4001` |
| `m_sample` | `cockpit2.py:4012` |
| `m_remove` | `cockpit2.py:4022` |
| `m_pin` | `cockpit2.py:4032` |
| `m_unpin` | `cockpit2.py:4043` |
| `tile_add` | `cockpit2.py:4081` |
| `indicator_activate` | `cockpit2.py:4053` |
| `tile_remove` | `cockpit2.py:4115` |
| `rov2_set` | `cockpit2.py:4125` |
| `rov2_acc_add` | `cockpit2.py:4125` |
| `rov2_acc_remove` | `cockpit2.py:4125` |
| `rov2_dom_add` | `cockpit2.py:4125` |
| `rov2_dom_remove` | `cockpit2.py:4125` |
| `backlog_add` | `cockpit2.py:4157` |
| `backlog_update_staat` | `cockpit2.py:4169` |
| `backlog_update_prioriteit` | `cockpit2.py:4181` |
| `person_edit` | `cockpit2.py:4193` |
| `person_remove` | `cockpit2.py:4210` |
| `lk_mute` | `cockpit2.py:4231` |
| `claims_term_add` | `cockpit2.py:4334` |
| `claims_term_retract` | `cockpit2.py:4371` |
| `claims_work_status` | `cockpit2.py:4355` |
| `claims_bewijs_link` | `cockpit2.py:4400` |
| `claims_vondst_whitelist` | `cockpit2.py:4424` |
| `claims_regel_uit_vondst` | `cockpit2.py:4450` |
| `claims_to_board` | `cockpit2.py:4482` |
| `persona_edit` | `cockpit2.py:2457` |
| `persona_llm` | `cockpit2.py:2476` |
| `persona_finetune` | `cockpit2.py:2493` |
| `persona_finetune_apply` | `cockpit2.py:2511` |


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
_57 routes · 188 dispatch-acties · 32 stores._
