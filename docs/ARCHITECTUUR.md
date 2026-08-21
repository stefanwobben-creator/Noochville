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
| `ff_beslis` | `cockpit2.py:4629` |
| `ff_cluster` | `cockpit2.py:4757` |
| `ff_promote` | `cockpit2.py:4687` |
| `ff_demote` | `cockpit2.py:4711` |
| `ff_run` | `cockpit2.py:4730` |
| `kb_new` | `cockpit2.py:4009` |
| `kb_intake` | `cockpit2.py:4091` |
| `kb_intake_url` | `cockpit2.py:4108` |
| `kb_stage_edit` | `cockpit2.py:4127` |
| `kb_stage_accept` | `cockpit2.py:4139` |
| `kb_stage_delete` | `cockpit2.py:4158` |
| `kb_stage_merge` | `cockpit2.py:4164` |
| `kb_stage_commit` | `cockpit2.py:4175` |
| `kb_stage_discard` | `cockpit2.py:4195` |
| `kb_atoom_subject` | `cockpit2.py:4433` |
| `kb_atoom_purge` | `cockpit2.py:4417` |
| `tag_voorstel_besluit` | `cockpit2.py:4271` |
| `tag_onderhoud_run` | `cockpit2.py:4404` |
| `copy_stack_inclusie` | `cockpit2.py:4386` |
| `verzoek_besluit` | `cockpit2.py:4290` |
| `kb_blacklist_leeg` | `cockpit2.py:4426` |
| `kb_atoom_edit` | `cockpit2.py:4201` |
| `kb_atoom_related` | `cockpit2.py:4208` |
| `kb_atoom_reference` | `cockpit2.py:4253` |
| `kb_insight_link` | `cockpit2.py:4220` |
| `kb_insight_unlink` | `cockpit2.py:4227` |
| `kb_meta_start` | `cockpit2.py:4233` |
| `kb_atoom_merge` | `cockpit2.py:4444` |
| `kb_atoom_archive` | `cockpit2.py:4465` |
| `kb_atoom_unarchive` | `cockpit2.py:4474` |
| `kb_atoom_naar_spel` | `cockpit2.py:4480` |
| `kb_spel_start` | `cockpit2.py:4501` |
| `kb_spel_add` | `cockpit2.py:4515` |
| `kb_spel_remove` | `cockpit2.py:4525` |
| `kb_spel_flip` | `cockpit2.py:4532` |
| `kb_spel_finish` | `cockpit2.py:4538` |
| `kb_link` | `cockpit2.py:4018` |
| `kb_unlink` | `cockpit2.py:4032` |
| `kb_annotate` | `cockpit2.py:4043` |
| `kb_evidence` | `cockpit2.py:4049` |
| `kb_discuss` | `cockpit2.py:4070` |
| `kb_reformulate` | `cockpit2.py:4076` |
| `kw_nominate` | `cockpit2.py:4549` |
| `kw_nom_accept` | `cockpit2.py:4560` |
| `kw_nom_reject` | `cockpit2.py:4578` |
| `ws_forbid` | `cockpit2.py:4608` |
| `ws_approve` | `cockpit2.py:4613` |
| `proj_add` | `cockpit2.py:1204` |
| `artefact_add` | `cockpit2.py:1248` |
| `artefact_edit` | `cockpit2.py:1292` |
| `artefact_archive` | `cockpit2.py:1319` |
| `pagina_feit_add` | `cockpit2.py:1339` |
| `pagina_feit_del` | `cockpit2.py:1368` |
| `pagina_voorstel` | `cockpit2.py:1399` |
| `proj_status` | `cockpit2.py:1429` |
| `proj_done` | `cockpit2.py:1447` |
| `proj_dod` | `cockpit2.py:1496` |
| `proj_archive` | `cockpit2.py:1510` |
| `proj_unarchive` | `cockpit2.py:1533` |
| `proj_delete` | `cockpit2.py:1543` |
| `proj_edit` | `cockpit2.py:1570` |
| `proj_comment` | `cockpit2.py:1583` |
| `proj_rename` | `cockpit2.py:1593` |
| `proj_describe` | `cockpit2.py:1604` |
| `proj_doc_edit` | `cockpit2.py:1637` |
| `proj_regen_doc` | `cockpit2.py:1615` |
| `proj_settrekker` | `cockpit2.py:1650` |
| `proj_setowner` | `cockpit2.py:1687` |
| `proj_approve` | `cockpit2.py:1706` |
| `proj_discard` | `cockpit2.py:1717` |
| `proj_proposal_accept` | `cockpit2.py:1728` |
| `proj_proposal_reject` | `cockpit2.py:1741` |
| `proj_setlabel` | `cockpit2.py:1754` |
| `proj_setimpact` | `cockpit2.py:1769` |
| `proj_seteffort` | `cockpit2.py:1788` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1811` |
| `proj_setprivate` | `cockpit2.py:1835` |
| `proj_setdue` | `cockpit2.py:1846` |
| `attach_add` | `cockpit2.py:1857` |
| `attach_remove` | `cockpit2.py:1868` |
| `react_add` | `cockpit2.py:1878` |
| `feed_edit` | `cockpit2.py:1888` |
| `feed_remove` | `cockpit2.py:1898` |
| `wall_outcome` | `cockpit2.py:2848` |
| `notif_read` | `cockpit2.py:2946` |
| `notif_processed` | `cockpit2.py:2951` |
| `notif_outcome` | `cockpit2.py:3098` |
| `notif_besluit` | `cockpit2.py:3185` |
| `notif_klaar` | `cockpit2.py:3084` |
| `notif_delete` | `cockpit2.py:2956` |
| `notif_add` | `cockpit2.py:3068` |
| `notif_archive` | `cockpit2.py:3227` |
| `metrics2_fav` | `cockpit2.py:2962` |
| `metrics2_unfav` | `cockpit2.py:2972` |
| `metrics2_form` | `cockpit2.py:2977` |
| `metrics2_dim` | `cockpit2.py:2983` |
| `metrics2_compare` | `cockpit2.py:2990` |
| `metrics2_formula` | `cockpit2.py:3053` |
| `source_activate` | `cockpit2.py:3036` |
| `source_deactivate` | `cockpit2.py:3045` |
| `link_pursue` | `cockpit2.py:3017` |
| `link_ignore` | `cockpit2.py:3027` |
| `acc_check` | `cockpit2.py:2998` |
| `ai_reply` | `cockpit2.py:1907` |
| `proj_feed` | `cockpit2.py:1918` |
| `checklist_add` | `cockpit2.py:1948` |
| `checklist_remove` | `cockpit2.py:1959` |
| `check_add` | `cockpit2.py:2007` |
| `check_accept` | `cockpit2.py:2024` |
| `check_toggle` | `cockpit2.py:2034` |
| `check_skip` | `cockpit2.py:2056` |
| `check_unskip` | `cockpit2.py:2068` |
| `check_handoff` | `cockpit2.py:2080` |
| `check_remove` | `cockpit2.py:2094` |
| `role_assign` | `cockpit2.py:2104` |
| `role_unassign` | `cockpit2.py:2122` |
| `role_focus` | `cockpit2.py:2141` |
| `radar_approve` | `cockpit2.py:2174` |
| `radar_dismiss` | `cockpit2.py:2184` |
| `radar_promote` | `cockpit2.py:2188` |
| `radar_merge` | `cockpit2.py:2208` |
| `radar_koppel` | `cockpit2.py:2224` |
| `kb_stage_koppel` | `cockpit2.py:2251` |
| `aitask_add` | `cockpit2.py:2289` |
| `aitask_remove` | `cockpit2.py:2320` |
| `skilllink_add` | `cockpit2.py:2348` |
| `means_gap_add` | `cockpit2.py:2378` |
| `persona_skill_add` | `cockpit2.py:2532` |
| `rov2_add` | `cockpit2.py:2547` |
| `rov2_add_to_group` | `cockpit2.py:2559` |
| `rov2_remove` | `cockpit2.py:2571` |
| `rov2_remove_group` | `cockpit2.py:2586` |
| `rov2_setkind` | `cockpit2.py:2604` |
| `rov2_consent` | `cockpit2.py:2617` |
| `rov2_end` | `cockpit2.py:2639` |
| `wo_open` | `cockpit2.py:2663` |
| `wo_close` | `cockpit2.py:2673` |
| `wo_presence` | `cockpit2.py:2689` |
| `wo_present_all` | `cockpit2.py:2700` |
| `wo_ag_add` | `cockpit2.py:2712` |
| `wo_ag_remove` | `cockpit2.py:2724` |
| `wo_ag_note` | `cockpit2.py:2734` |
| `wo_ag_reopen` | `cockpit2.py:2746` |
| `wo_ag_resolve` | `cockpit2.py:2822` |
| `wo_checkout` | `cockpit2.py:3232` |
| `noochie_send` | `cockpit2.py:3244` |
| `noochie_reset` | `cockpit2.py:3270` |
| `noochie_ctx` | `cockpit2.py:3277` |
| `cl_add` | `cockpit2.py:3284` |
| `cl_report` | `cockpit2.py:3302` |
| `cl_remove` | `cockpit2.py:3317` |
| `m_add_kpi` | `cockpit2.py:3327` |
| `m_add_from_def` | `cockpit2.py:3359` |
| `def_add` | `cockpit2.py:3374` |
| `catalog_publish` | `cockpit2.py:3396` |
| `def_amend` | `cockpit2.py:3422` |
| `m_add_link` | `cockpit2.py:3464` |
| `m_sample` | `cockpit2.py:3475` |
| `m_remove` | `cockpit2.py:3485` |
| `m_pin` | `cockpit2.py:3495` |
| `m_unpin` | `cockpit2.py:3506` |
| `tile_add` | `cockpit2.py:3544` |
| `indicator_activate` | `cockpit2.py:3516` |
| `tile_remove` | `cockpit2.py:3578` |
| `rov2_set` | `cockpit2.py:3588` |
| `rov2_acc_add` | `cockpit2.py:3588` |
| `rov2_acc_remove` | `cockpit2.py:3588` |
| `rov2_dom_add` | `cockpit2.py:3588` |
| `rov2_dom_remove` | `cockpit2.py:3588` |
| `backlog_add` | `cockpit2.py:3620` |
| `backlog_update_staat` | `cockpit2.py:3632` |
| `backlog_update_prioriteit` | `cockpit2.py:3644` |
| `person_edit` | `cockpit2.py:3656` |
| `person_remove` | `cockpit2.py:3673` |
| `lk_mute` | `cockpit2.py:3694` |
| `claims_term_add` | `cockpit2.py:3797` |
| `claims_term_retract` | `cockpit2.py:3834` |
| `claims_work_status` | `cockpit2.py:3818` |
| `claims_bewijs_link` | `cockpit2.py:3863` |
| `claims_vondst_whitelist` | `cockpit2.py:3887` |
| `claims_regel_uit_vondst` | `cockpit2.py:3913` |
| `claims_to_board` | `cockpit2.py:3945` |
| `persona_edit` | `cockpit2.py:2431` |
| `persona_llm` | `cockpit2.py:2450` |
| `persona_finetune` | `cockpit2.py:2467` |
| `persona_finetune_apply` | `cockpit2.py:2485` |


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
_55 routes · 186 dispatch-acties · 32 stores._
