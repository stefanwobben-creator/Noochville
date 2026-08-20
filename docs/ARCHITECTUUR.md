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
| `ff_beslis` | `cockpit2.py:4628` |
| `ff_cluster` | `cockpit2.py:4756` |
| `ff_promote` | `cockpit2.py:4686` |
| `ff_demote` | `cockpit2.py:4710` |
| `ff_run` | `cockpit2.py:4729` |
| `kb_new` | `cockpit2.py:4008` |
| `kb_intake` | `cockpit2.py:4090` |
| `kb_intake_url` | `cockpit2.py:4107` |
| `kb_stage_edit` | `cockpit2.py:4126` |
| `kb_stage_accept` | `cockpit2.py:4138` |
| `kb_stage_delete` | `cockpit2.py:4157` |
| `kb_stage_merge` | `cockpit2.py:4163` |
| `kb_stage_commit` | `cockpit2.py:4174` |
| `kb_stage_discard` | `cockpit2.py:4194` |
| `kb_atoom_subject` | `cockpit2.py:4432` |
| `kb_atoom_purge` | `cockpit2.py:4416` |
| `tag_voorstel_besluit` | `cockpit2.py:4270` |
| `tag_onderhoud_run` | `cockpit2.py:4403` |
| `copy_stack_inclusie` | `cockpit2.py:4385` |
| `verzoek_besluit` | `cockpit2.py:4289` |
| `kb_blacklist_leeg` | `cockpit2.py:4425` |
| `kb_atoom_edit` | `cockpit2.py:4200` |
| `kb_atoom_related` | `cockpit2.py:4207` |
| `kb_atoom_reference` | `cockpit2.py:4252` |
| `kb_insight_link` | `cockpit2.py:4219` |
| `kb_insight_unlink` | `cockpit2.py:4226` |
| `kb_meta_start` | `cockpit2.py:4232` |
| `kb_atoom_merge` | `cockpit2.py:4443` |
| `kb_atoom_archive` | `cockpit2.py:4464` |
| `kb_atoom_unarchive` | `cockpit2.py:4473` |
| `kb_atoom_naar_spel` | `cockpit2.py:4479` |
| `kb_spel_start` | `cockpit2.py:4500` |
| `kb_spel_add` | `cockpit2.py:4514` |
| `kb_spel_remove` | `cockpit2.py:4524` |
| `kb_spel_flip` | `cockpit2.py:4531` |
| `kb_spel_finish` | `cockpit2.py:4537` |
| `kb_link` | `cockpit2.py:4017` |
| `kb_unlink` | `cockpit2.py:4031` |
| `kb_annotate` | `cockpit2.py:4042` |
| `kb_evidence` | `cockpit2.py:4048` |
| `kb_discuss` | `cockpit2.py:4069` |
| `kb_reformulate` | `cockpit2.py:4075` |
| `kw_nominate` | `cockpit2.py:4548` |
| `kw_nom_accept` | `cockpit2.py:4559` |
| `kw_nom_reject` | `cockpit2.py:4577` |
| `ws_forbid` | `cockpit2.py:4607` |
| `ws_approve` | `cockpit2.py:4612` |
| `proj_add` | `cockpit2.py:1203` |
| `artefact_add` | `cockpit2.py:1247` |
| `artefact_edit` | `cockpit2.py:1291` |
| `artefact_archive` | `cockpit2.py:1318` |
| `pagina_feit_add` | `cockpit2.py:1338` |
| `pagina_feit_del` | `cockpit2.py:1367` |
| `pagina_voorstel` | `cockpit2.py:1398` |
| `proj_status` | `cockpit2.py:1428` |
| `proj_done` | `cockpit2.py:1446` |
| `proj_dod` | `cockpit2.py:1495` |
| `proj_archive` | `cockpit2.py:1509` |
| `proj_unarchive` | `cockpit2.py:1532` |
| `proj_delete` | `cockpit2.py:1542` |
| `proj_edit` | `cockpit2.py:1569` |
| `proj_comment` | `cockpit2.py:1582` |
| `proj_rename` | `cockpit2.py:1592` |
| `proj_describe` | `cockpit2.py:1603` |
| `proj_doc_edit` | `cockpit2.py:1636` |
| `proj_regen_doc` | `cockpit2.py:1614` |
| `proj_settrekker` | `cockpit2.py:1649` |
| `proj_setowner` | `cockpit2.py:1686` |
| `proj_approve` | `cockpit2.py:1705` |
| `proj_discard` | `cockpit2.py:1716` |
| `proj_proposal_accept` | `cockpit2.py:1727` |
| `proj_proposal_reject` | `cockpit2.py:1740` |
| `proj_setlabel` | `cockpit2.py:1753` |
| `proj_setimpact` | `cockpit2.py:1768` |
| `proj_seteffort` | `cockpit2.py:1787` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1810` |
| `proj_setprivate` | `cockpit2.py:1834` |
| `proj_setdue` | `cockpit2.py:1845` |
| `attach_add` | `cockpit2.py:1856` |
| `attach_remove` | `cockpit2.py:1867` |
| `react_add` | `cockpit2.py:1877` |
| `feed_edit` | `cockpit2.py:1887` |
| `feed_remove` | `cockpit2.py:1897` |
| `wall_outcome` | `cockpit2.py:2847` |
| `notif_read` | `cockpit2.py:2945` |
| `notif_processed` | `cockpit2.py:2950` |
| `notif_outcome` | `cockpit2.py:3097` |
| `notif_besluit` | `cockpit2.py:3184` |
| `notif_klaar` | `cockpit2.py:3083` |
| `notif_delete` | `cockpit2.py:2955` |
| `notif_add` | `cockpit2.py:3067` |
| `notif_archive` | `cockpit2.py:3226` |
| `metrics2_fav` | `cockpit2.py:2961` |
| `metrics2_unfav` | `cockpit2.py:2971` |
| `metrics2_form` | `cockpit2.py:2976` |
| `metrics2_dim` | `cockpit2.py:2982` |
| `metrics2_compare` | `cockpit2.py:2989` |
| `metrics2_formula` | `cockpit2.py:3052` |
| `source_activate` | `cockpit2.py:3035` |
| `source_deactivate` | `cockpit2.py:3044` |
| `link_pursue` | `cockpit2.py:3016` |
| `link_ignore` | `cockpit2.py:3026` |
| `acc_check` | `cockpit2.py:2997` |
| `ai_reply` | `cockpit2.py:1906` |
| `proj_feed` | `cockpit2.py:1917` |
| `checklist_add` | `cockpit2.py:1947` |
| `checklist_remove` | `cockpit2.py:1958` |
| `check_add` | `cockpit2.py:2006` |
| `check_accept` | `cockpit2.py:2023` |
| `check_toggle` | `cockpit2.py:2033` |
| `check_skip` | `cockpit2.py:2055` |
| `check_unskip` | `cockpit2.py:2067` |
| `check_handoff` | `cockpit2.py:2079` |
| `check_remove` | `cockpit2.py:2093` |
| `role_assign` | `cockpit2.py:2103` |
| `role_unassign` | `cockpit2.py:2121` |
| `role_focus` | `cockpit2.py:2140` |
| `radar_approve` | `cockpit2.py:2173` |
| `radar_dismiss` | `cockpit2.py:2183` |
| `radar_promote` | `cockpit2.py:2187` |
| `radar_merge` | `cockpit2.py:2207` |
| `radar_koppel` | `cockpit2.py:2223` |
| `kb_stage_koppel` | `cockpit2.py:2250` |
| `aitask_add` | `cockpit2.py:2288` |
| `aitask_remove` | `cockpit2.py:2319` |
| `skilllink_add` | `cockpit2.py:2347` |
| `means_gap_add` | `cockpit2.py:2377` |
| `persona_skill_add` | `cockpit2.py:2531` |
| `rov2_add` | `cockpit2.py:2546` |
| `rov2_add_to_group` | `cockpit2.py:2558` |
| `rov2_remove` | `cockpit2.py:2570` |
| `rov2_remove_group` | `cockpit2.py:2585` |
| `rov2_setkind` | `cockpit2.py:2603` |
| `rov2_consent` | `cockpit2.py:2616` |
| `rov2_end` | `cockpit2.py:2638` |
| `wo_open` | `cockpit2.py:2662` |
| `wo_close` | `cockpit2.py:2672` |
| `wo_presence` | `cockpit2.py:2688` |
| `wo_present_all` | `cockpit2.py:2699` |
| `wo_ag_add` | `cockpit2.py:2711` |
| `wo_ag_remove` | `cockpit2.py:2723` |
| `wo_ag_note` | `cockpit2.py:2733` |
| `wo_ag_reopen` | `cockpit2.py:2745` |
| `wo_ag_resolve` | `cockpit2.py:2821` |
| `wo_checkout` | `cockpit2.py:3231` |
| `noochie_send` | `cockpit2.py:3243` |
| `noochie_reset` | `cockpit2.py:3269` |
| `noochie_ctx` | `cockpit2.py:3276` |
| `cl_add` | `cockpit2.py:3283` |
| `cl_report` | `cockpit2.py:3301` |
| `cl_remove` | `cockpit2.py:3316` |
| `m_add_kpi` | `cockpit2.py:3326` |
| `m_add_from_def` | `cockpit2.py:3358` |
| `def_add` | `cockpit2.py:3373` |
| `catalog_publish` | `cockpit2.py:3395` |
| `def_amend` | `cockpit2.py:3421` |
| `m_add_link` | `cockpit2.py:3463` |
| `m_sample` | `cockpit2.py:3474` |
| `m_remove` | `cockpit2.py:3484` |
| `m_pin` | `cockpit2.py:3494` |
| `m_unpin` | `cockpit2.py:3505` |
| `tile_add` | `cockpit2.py:3543` |
| `indicator_activate` | `cockpit2.py:3515` |
| `tile_remove` | `cockpit2.py:3577` |
| `rov2_set` | `cockpit2.py:3587` |
| `rov2_acc_add` | `cockpit2.py:3587` |
| `rov2_acc_remove` | `cockpit2.py:3587` |
| `rov2_dom_add` | `cockpit2.py:3587` |
| `rov2_dom_remove` | `cockpit2.py:3587` |
| `backlog_add` | `cockpit2.py:3619` |
| `backlog_update_staat` | `cockpit2.py:3631` |
| `backlog_update_prioriteit` | `cockpit2.py:3643` |
| `person_edit` | `cockpit2.py:3655` |
| `person_remove` | `cockpit2.py:3672` |
| `lk_mute` | `cockpit2.py:3693` |
| `claims_term_add` | `cockpit2.py:3796` |
| `claims_term_retract` | `cockpit2.py:3833` |
| `claims_work_status` | `cockpit2.py:3817` |
| `claims_bewijs_link` | `cockpit2.py:3862` |
| `claims_vondst_whitelist` | `cockpit2.py:3886` |
| `claims_regel_uit_vondst` | `cockpit2.py:3912` |
| `claims_to_board` | `cockpit2.py:3944` |
| `persona_edit` | `cockpit2.py:2430` |
| `persona_llm` | `cockpit2.py:2449` |
| `persona_finetune` | `cockpit2.py:2466` |
| `persona_finetune_apply` | `cockpit2.py:2484` |


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
