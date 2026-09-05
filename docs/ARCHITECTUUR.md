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
| `ff_beslis` | `cockpit2.py:5399` |
| `ff_cluster` | `cockpit2.py:5527` |
| `ff_promote` | `cockpit2.py:5457` |
| `ff_demote` | `cockpit2.py:5481` |
| `ff_run` | `cockpit2.py:5500` |
| `kb_new` | `cockpit2.py:4762` |
| `kb_intake` | `cockpit2.py:4844` |
| `kb_intake_url` | `cockpit2.py:4861` |
| `kb_stage_edit` | `cockpit2.py:4880` |
| `kb_stage_accept` | `cockpit2.py:4892` |
| `kb_stage_delete` | `cockpit2.py:4911` |
| `kb_stage_merge` | `cockpit2.py:4917` |
| `kb_stage_commit` | `cockpit2.py:4928` |
| `kb_stage_discard` | `cockpit2.py:4948` |
| `kb_atoom_subject` | `cockpit2.py:5203` |
| `kb_atoom_purge` | `cockpit2.py:5187` |
| `tag_voorstel_besluit` | `cockpit2.py:5024` |
| `tag_onderhoud_run` | `cockpit2.py:5174` |
| `copy_stack_inclusie` | `cockpit2.py:5156` |
| `verzoek_besluit` | `cockpit2.py:5043` |
| `kb_blacklist_leeg` | `cockpit2.py:5196` |
| `kb_atoom_edit` | `cockpit2.py:4954` |
| `kb_atoom_related` | `cockpit2.py:4961` |
| `kb_atoom_reference` | `cockpit2.py:5006` |
| `kb_insight_link` | `cockpit2.py:4973` |
| `kb_insight_unlink` | `cockpit2.py:4980` |
| `kb_meta_start` | `cockpit2.py:4986` |
| `kb_atoom_merge` | `cockpit2.py:5214` |
| `kb_atoom_archive` | `cockpit2.py:5235` |
| `kb_atoom_unarchive` | `cockpit2.py:5244` |
| `kb_atoom_naar_spel` | `cockpit2.py:5250` |
| `kb_spel_start` | `cockpit2.py:5271` |
| `kb_spel_add` | `cockpit2.py:5285` |
| `kb_spel_remove` | `cockpit2.py:5295` |
| `kb_spel_flip` | `cockpit2.py:5302` |
| `kb_spel_finish` | `cockpit2.py:5308` |
| `kb_link` | `cockpit2.py:4771` |
| `kb_unlink` | `cockpit2.py:4785` |
| `kb_annotate` | `cockpit2.py:4796` |
| `kb_evidence` | `cockpit2.py:4802` |
| `kb_discuss` | `cockpit2.py:4823` |
| `kb_reformulate` | `cockpit2.py:4829` |
| `kw_nominate` | `cockpit2.py:5319` |
| `kw_nom_accept` | `cockpit2.py:5330` |
| `kw_nom_reject` | `cockpit2.py:5348` |
| `ws_forbid` | `cockpit2.py:5378` |
| `ws_approve` | `cockpit2.py:5383` |
| `proj_add` | `cockpit2.py:1209` |
| `artefact_add` | `cockpit2.py:1262` |
| `artefact_edit` | `cockpit2.py:1306` |
| `artefact_archive` | `cockpit2.py:1333` |
| `pagina_feit_add` | `cockpit2.py:1353` |
| `pagina_feit_del` | `cockpit2.py:1382` |
| `pagina_voorstel` | `cockpit2.py:1413` |
| `proj_status` | `cockpit2.py:1443` |
| `proj_done` | `cockpit2.py:1461` |
| `proj_dod` | `cockpit2.py:1551` |
| `proj_archive` | `cockpit2.py:1565` |
| `proj_unarchive` | `cockpit2.py:1588` |
| `proj_delete` | `cockpit2.py:1598` |
| `proj_edit` | `cockpit2.py:1625` |
| `proj_comment` | `cockpit2.py:1638` |
| `proj_rename` | `cockpit2.py:1648` |
| `proj_describe` | `cockpit2.py:1659` |
| `proj_doc_edit` | `cockpit2.py:1729` |
| `verslag_bevestig` | `cockpit2.py:1692` |
| `verslag_bijwerken` | `cockpit2.py:1707` |
| `proj_regen_doc` | `cockpit2.py:1670` |
| `proj_settrekker` | `cockpit2.py:1742` |
| `proj_setowner` | `cockpit2.py:1783` |
| `proj_approve` | `cockpit2.py:1802` |
| `proj_discard` | `cockpit2.py:1813` |
| `proj_proposal_accept` | `cockpit2.py:1824` |
| `proj_proposal_reject` | `cockpit2.py:1837` |
| `proj_setlabel` | `cockpit2.py:1850` |
| `proj_setimpact` | `cockpit2.py:1865` |
| `proj_seteffort` | `cockpit2.py:1884` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1907` |
| `proj_setprivate` | `cockpit2.py:1931` |
| `proj_setdue` | `cockpit2.py:1942` |
| `attach_add` | `cockpit2.py:1953` |
| `attach_remove` | `cockpit2.py:1964` |
| `react_add` | `cockpit2.py:1974` |
| `feed_edit` | `cockpit2.py:1984` |
| `feed_remove` | `cockpit2.py:1994` |
| `wall_outcome` | `cockpit2.py:3540` |
| `notif_read` | `cockpit2.py:3636` |
| `notif_processed` | `cockpit2.py:3641` |
| `notif_outcome` | `cockpit2.py:3860` |
| `notif_klaar` | `cockpit2.py:3807` |
| `notif_delete` | `cockpit2.py:3646` |
| `notif_add` | `cockpit2.py:3758` |
| `notif_archive` | `cockpit2.py:3977` |
| `metrics2_fav` | `cockpit2.py:3652` |
| `metrics2_unfav` | `cockpit2.py:3662` |
| `metrics2_form` | `cockpit2.py:3667` |
| `metrics2_dim` | `cockpit2.py:3673` |
| `metrics2_compare` | `cockpit2.py:3680` |
| `metrics2_formula` | `cockpit2.py:3743` |
| `source_activate` | `cockpit2.py:3726` |
| `source_deactivate` | `cockpit2.py:3735` |
| `link_pursue` | `cockpit2.py:3707` |
| `link_ignore` | `cockpit2.py:3717` |
| `acc_check` | `cockpit2.py:3688` |
| `ai_reply` | `cockpit2.py:2003` |
| `proj_feed` | `cockpit2.py:2014` |
| `checklist_add` | `cockpit2.py:2061` |
| `checklist_remove` | `cockpit2.py:2072` |
| `check_add` | `cockpit2.py:2120` |
| `check_accept` | `cockpit2.py:2137` |
| `check_toggle` | `cockpit2.py:2147` |
| `check_skip` | `cockpit2.py:2169` |
| `check_unskip` | `cockpit2.py:2181` |
| `check_handoff` | `cockpit2.py:2193` |
| `check_remove` | `cockpit2.py:2207` |
| `role_assign` | `cockpit2.py:2217` |
| `role_unassign` | `cockpit2.py:2235` |
| `role_focus` | `cockpit2.py:2254` |
| `radar_approve` | `cockpit2.py:2287` |
| `radar_dismiss` | `cockpit2.py:2297` |
| `radar_promote` | `cockpit2.py:2301` |
| `radar_merge` | `cockpit2.py:2321` |
| `radar_koppel` | `cockpit2.py:2337` |
| `kb_stage_koppel` | `cockpit2.py:2364` |
| `aitask_add` | `cockpit2.py:2402` |
| `aitask_remove` | `cockpit2.py:2433` |
| `skilllink_add` | `cockpit2.py:2461` |
| `means_gap_add` | `cockpit2.py:2491` |
| `persona_skill_add` | `cockpit2.py:2645` |
| `rov2_add` | `cockpit2.py:2660` |
| `rov2_add_to_group` | `cockpit2.py:2672` |
| `rov2_remove` | `cockpit2.py:2684` |
| `rov2_remove_group` | `cockpit2.py:2699` |
| `rov2_setkind` | `cockpit2.py:2717` |
| `rov2_consent` | `cockpit2.py:2730` |
| `rov2_end` | `cockpit2.py:2752` |
| `wo_open` | `cockpit2.py:2776` |
| `wo_close` | `cockpit2.py:2786` |
| `wo_presence` | `cockpit2.py:2802` |
| `wo_present_all` | `cockpit2.py:2813` |
| `vangst_add` | `cockpit2.py:2825` |
| `vangst_tekst` | `cockpit2.py:2873` |
| `vangst_klaar` | `cockpit2.py:2883` |
| `vangst_uitkomst` | `cockpit2.py:2932` |
| `vangst_uitkomst_weg` | `cockpit2.py:2920` |
| `vangst_uitkomst_edit` | `cockpit2.py:2895` |
| `vangst_remove` | `cockpit2.py:2864` |
| `vangst_verwerk` | `cockpit2.py:3048` |
| `wo_checkout` | `cockpit2.py:3982` |
| `noochie_send` | `cockpit2.py:3997` |
| `noochie_reset` | `cockpit2.py:4023` |
| `noochie_ctx` | `cockpit2.py:4030` |
| `cl_add` | `cockpit2.py:4037` |
| `cl_report` | `cockpit2.py:4055` |
| `cl_remove` | `cockpit2.py:4070` |
| `m_add_kpi` | `cockpit2.py:4080` |
| `m_add_from_def` | `cockpit2.py:4112` |
| `def_add` | `cockpit2.py:4127` |
| `catalog_publish` | `cockpit2.py:4149` |
| `def_amend` | `cockpit2.py:4175` |
| `m_add_link` | `cockpit2.py:4217` |
| `m_sample` | `cockpit2.py:4228` |
| `m_remove` | `cockpit2.py:4238` |
| `m_pin` | `cockpit2.py:4248` |
| `m_unpin` | `cockpit2.py:4259` |
| `tile_add` | `cockpit2.py:4297` |
| `indicator_activate` | `cockpit2.py:4269` |
| `tile_remove` | `cockpit2.py:4331` |
| `rov2_set` | `cockpit2.py:4341` |
| `rov2_acc_add` | `cockpit2.py:4341` |
| `rov2_acc_remove` | `cockpit2.py:4341` |
| `rov2_dom_add` | `cockpit2.py:4341` |
| `rov2_dom_remove` | `cockpit2.py:4341` |
| `backlog_add` | `cockpit2.py:4373` |
| `backlog_update_staat` | `cockpit2.py:4385` |
| `backlog_update_prioriteit` | `cockpit2.py:4397` |
| `person_edit` | `cockpit2.py:4409` |
| `person_remove` | `cockpit2.py:4426` |
| `lk_mute` | `cockpit2.py:4447` |
| `claims_term_add` | `cockpit2.py:4550` |
| `claims_term_retract` | `cockpit2.py:4587` |
| `claims_work_status` | `cockpit2.py:4571` |
| `claims_bewijs_link` | `cockpit2.py:4616` |
| `claims_vondst_whitelist` | `cockpit2.py:4640` |
| `claims_regel_uit_vondst` | `cockpit2.py:4666` |
| `claims_to_board` | `cockpit2.py:4698` |
| `persona_edit` | `cockpit2.py:2544` |
| `persona_llm` | `cockpit2.py:2563` |
| `persona_finetune` | `cockpit2.py:2580` |
| `persona_finetune_apply` | `cockpit2.py:2598` |


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
_59 routes · 190 dispatch-acties · 32 stores._
