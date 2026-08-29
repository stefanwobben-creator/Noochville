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
| `ff_beslis` | `cockpit2.py:4962` |
| `ff_cluster` | `cockpit2.py:5090` |
| `ff_promote` | `cockpit2.py:5020` |
| `ff_demote` | `cockpit2.py:5044` |
| `ff_run` | `cockpit2.py:5063` |
| `kb_new` | `cockpit2.py:4342` |
| `kb_intake` | `cockpit2.py:4424` |
| `kb_intake_url` | `cockpit2.py:4441` |
| `kb_stage_edit` | `cockpit2.py:4460` |
| `kb_stage_accept` | `cockpit2.py:4472` |
| `kb_stage_delete` | `cockpit2.py:4491` |
| `kb_stage_merge` | `cockpit2.py:4497` |
| `kb_stage_commit` | `cockpit2.py:4508` |
| `kb_stage_discard` | `cockpit2.py:4528` |
| `kb_atoom_subject` | `cockpit2.py:4766` |
| `kb_atoom_purge` | `cockpit2.py:4750` |
| `tag_voorstel_besluit` | `cockpit2.py:4604` |
| `tag_onderhoud_run` | `cockpit2.py:4737` |
| `copy_stack_inclusie` | `cockpit2.py:4719` |
| `verzoek_besluit` | `cockpit2.py:4623` |
| `kb_blacklist_leeg` | `cockpit2.py:4759` |
| `kb_atoom_edit` | `cockpit2.py:4534` |
| `kb_atoom_related` | `cockpit2.py:4541` |
| `kb_atoom_reference` | `cockpit2.py:4586` |
| `kb_insight_link` | `cockpit2.py:4553` |
| `kb_insight_unlink` | `cockpit2.py:4560` |
| `kb_meta_start` | `cockpit2.py:4566` |
| `kb_atoom_merge` | `cockpit2.py:4777` |
| `kb_atoom_archive` | `cockpit2.py:4798` |
| `kb_atoom_unarchive` | `cockpit2.py:4807` |
| `kb_atoom_naar_spel` | `cockpit2.py:4813` |
| `kb_spel_start` | `cockpit2.py:4834` |
| `kb_spel_add` | `cockpit2.py:4848` |
| `kb_spel_remove` | `cockpit2.py:4858` |
| `kb_spel_flip` | `cockpit2.py:4865` |
| `kb_spel_finish` | `cockpit2.py:4871` |
| `kb_link` | `cockpit2.py:4351` |
| `kb_unlink` | `cockpit2.py:4365` |
| `kb_annotate` | `cockpit2.py:4376` |
| `kb_evidence` | `cockpit2.py:4382` |
| `kb_discuss` | `cockpit2.py:4403` |
| `kb_reformulate` | `cockpit2.py:4409` |
| `kw_nominate` | `cockpit2.py:4882` |
| `kw_nom_accept` | `cockpit2.py:4893` |
| `kw_nom_reject` | `cockpit2.py:4911` |
| `ws_forbid` | `cockpit2.py:4941` |
| `ws_approve` | `cockpit2.py:4946` |
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
| `wall_outcome` | `cockpit2.py:3168` |
| `notif_read` | `cockpit2.py:3266` |
| `notif_processed` | `cockpit2.py:3271` |
| `notif_outcome` | `cockpit2.py:3424` |
| `notif_besluit` | `cockpit2.py:3515` |
| `notif_klaar` | `cockpit2.py:3404` |
| `notif_delete` | `cockpit2.py:3276` |
| `notif_add` | `cockpit2.py:3388` |
| `notif_archive` | `cockpit2.py:3557` |
| `metrics2_fav` | `cockpit2.py:3282` |
| `metrics2_unfav` | `cockpit2.py:3292` |
| `metrics2_form` | `cockpit2.py:3297` |
| `metrics2_dim` | `cockpit2.py:3303` |
| `metrics2_compare` | `cockpit2.py:3310` |
| `metrics2_formula` | `cockpit2.py:3373` |
| `source_activate` | `cockpit2.py:3356` |
| `source_deactivate` | `cockpit2.py:3365` |
| `link_pursue` | `cockpit2.py:3337` |
| `link_ignore` | `cockpit2.py:3347` |
| `acc_check` | `cockpit2.py:3318` |
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
| `vangst_verwerk` | `cockpit2.py:2946` |
| `wo_checkout` | `cockpit2.py:3562` |
| `noochie_send` | `cockpit2.py:3577` |
| `noochie_reset` | `cockpit2.py:3603` |
| `noochie_ctx` | `cockpit2.py:3610` |
| `cl_add` | `cockpit2.py:3617` |
| `cl_report` | `cockpit2.py:3635` |
| `cl_remove` | `cockpit2.py:3650` |
| `m_add_kpi` | `cockpit2.py:3660` |
| `m_add_from_def` | `cockpit2.py:3692` |
| `def_add` | `cockpit2.py:3707` |
| `catalog_publish` | `cockpit2.py:3729` |
| `def_amend` | `cockpit2.py:3755` |
| `m_add_link` | `cockpit2.py:3797` |
| `m_sample` | `cockpit2.py:3808` |
| `m_remove` | `cockpit2.py:3818` |
| `m_pin` | `cockpit2.py:3828` |
| `m_unpin` | `cockpit2.py:3839` |
| `tile_add` | `cockpit2.py:3877` |
| `indicator_activate` | `cockpit2.py:3849` |
| `tile_remove` | `cockpit2.py:3911` |
| `rov2_set` | `cockpit2.py:3921` |
| `rov2_acc_add` | `cockpit2.py:3921` |
| `rov2_acc_remove` | `cockpit2.py:3921` |
| `rov2_dom_add` | `cockpit2.py:3921` |
| `rov2_dom_remove` | `cockpit2.py:3921` |
| `backlog_add` | `cockpit2.py:3953` |
| `backlog_update_staat` | `cockpit2.py:3965` |
| `backlog_update_prioriteit` | `cockpit2.py:3977` |
| `person_edit` | `cockpit2.py:3989` |
| `person_remove` | `cockpit2.py:4006` |
| `lk_mute` | `cockpit2.py:4027` |
| `claims_term_add` | `cockpit2.py:4130` |
| `claims_term_retract` | `cockpit2.py:4167` |
| `claims_work_status` | `cockpit2.py:4151` |
| `claims_bewijs_link` | `cockpit2.py:4196` |
| `claims_vondst_whitelist` | `cockpit2.py:4220` |
| `claims_regel_uit_vondst` | `cockpit2.py:4246` |
| `claims_to_board` | `cockpit2.py:4278` |
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
