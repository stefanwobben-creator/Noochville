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
| `ff_beslis` | `cockpit2.py:5465` |
| `ff_cluster` | `cockpit2.py:5593` |
| `ff_promote` | `cockpit2.py:5523` |
| `ff_demote` | `cockpit2.py:5547` |
| `ff_run` | `cockpit2.py:5566` |
| `kb_new` | `cockpit2.py:4828` |
| `kb_intake` | `cockpit2.py:4910` |
| `kb_intake_url` | `cockpit2.py:4927` |
| `kb_stage_edit` | `cockpit2.py:4946` |
| `kb_stage_accept` | `cockpit2.py:4958` |
| `kb_stage_delete` | `cockpit2.py:4977` |
| `kb_stage_merge` | `cockpit2.py:4983` |
| `kb_stage_commit` | `cockpit2.py:4994` |
| `kb_stage_discard` | `cockpit2.py:5014` |
| `kb_atoom_subject` | `cockpit2.py:5269` |
| `kb_atoom_purge` | `cockpit2.py:5253` |
| `tag_voorstel_besluit` | `cockpit2.py:5090` |
| `tag_onderhoud_run` | `cockpit2.py:5240` |
| `copy_stack_inclusie` | `cockpit2.py:5222` |
| `verzoek_besluit` | `cockpit2.py:5109` |
| `kb_blacklist_leeg` | `cockpit2.py:5262` |
| `kb_atoom_edit` | `cockpit2.py:5020` |
| `kb_atoom_related` | `cockpit2.py:5027` |
| `kb_atoom_reference` | `cockpit2.py:5072` |
| `kb_insight_link` | `cockpit2.py:5039` |
| `kb_insight_unlink` | `cockpit2.py:5046` |
| `kb_meta_start` | `cockpit2.py:5052` |
| `kb_atoom_merge` | `cockpit2.py:5280` |
| `kb_atoom_archive` | `cockpit2.py:5301` |
| `kb_atoom_unarchive` | `cockpit2.py:5310` |
| `kb_atoom_naar_spel` | `cockpit2.py:5316` |
| `kb_spel_start` | `cockpit2.py:5337` |
| `kb_spel_add` | `cockpit2.py:5351` |
| `kb_spel_remove` | `cockpit2.py:5361` |
| `kb_spel_flip` | `cockpit2.py:5368` |
| `kb_spel_finish` | `cockpit2.py:5374` |
| `kb_link` | `cockpit2.py:4837` |
| `kb_unlink` | `cockpit2.py:4851` |
| `kb_annotate` | `cockpit2.py:4862` |
| `kb_evidence` | `cockpit2.py:4868` |
| `kb_discuss` | `cockpit2.py:4889` |
| `kb_reformulate` | `cockpit2.py:4895` |
| `kw_nominate` | `cockpit2.py:5385` |
| `kw_nom_accept` | `cockpit2.py:5396` |
| `kw_nom_reject` | `cockpit2.py:5414` |
| `ws_forbid` | `cockpit2.py:5444` |
| `ws_approve` | `cockpit2.py:5449` |
| `proj_add` | `cockpit2.py:1209` |
| `artefact_add` | `cockpit2.py:1262` |
| `artefact_edit` | `cockpit2.py:1306` |
| `artefact_archive` | `cockpit2.py:1333` |
| `pagina_feit_add` | `cockpit2.py:1353` |
| `pagina_feit_del` | `cockpit2.py:1382` |
| `pagina_voorstel` | `cockpit2.py:1413` |
| `proj_status` | `cockpit2.py:1443` |
| `proj_done` | `cockpit2.py:1461` |
| `proj_dod` | `cockpit2.py:1555` |
| `proj_archive` | `cockpit2.py:1569` |
| `proj_unarchive` | `cockpit2.py:1592` |
| `proj_delete` | `cockpit2.py:1602` |
| `proj_edit` | `cockpit2.py:1629` |
| `proj_comment` | `cockpit2.py:1642` |
| `proj_rename` | `cockpit2.py:1652` |
| `proj_describe` | `cockpit2.py:1663` |
| `proj_doc_edit` | `cockpit2.py:1795` |
| `verslag_bevestig` | `cockpit2.py:1709` |
| `verslag_overslaan` | `cockpit2.py:1749` |
| `verslag_bijwerken` | `cockpit2.py:1773` |
| `proj_regen_doc` | `cockpit2.py:1674` |
| `proj_settrekker` | `cockpit2.py:1808` |
| `proj_setowner` | `cockpit2.py:1849` |
| `proj_approve` | `cockpit2.py:1868` |
| `proj_discard` | `cockpit2.py:1879` |
| `proj_proposal_accept` | `cockpit2.py:1890` |
| `proj_proposal_reject` | `cockpit2.py:1903` |
| `proj_setlabel` | `cockpit2.py:1916` |
| `proj_setimpact` | `cockpit2.py:1931` |
| `proj_seteffort` | `cockpit2.py:1950` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1973` |
| `proj_setprivate` | `cockpit2.py:1997` |
| `proj_setdue` | `cockpit2.py:2008` |
| `attach_add` | `cockpit2.py:2019` |
| `attach_remove` | `cockpit2.py:2030` |
| `react_add` | `cockpit2.py:2040` |
| `feed_edit` | `cockpit2.py:2050` |
| `feed_remove` | `cockpit2.py:2060` |
| `wall_outcome` | `cockpit2.py:3606` |
| `notif_read` | `cockpit2.py:3702` |
| `notif_processed` | `cockpit2.py:3707` |
| `notif_outcome` | `cockpit2.py:3926` |
| `notif_klaar` | `cockpit2.py:3873` |
| `notif_delete` | `cockpit2.py:3712` |
| `notif_add` | `cockpit2.py:3824` |
| `notif_archive` | `cockpit2.py:4043` |
| `metrics2_fav` | `cockpit2.py:3718` |
| `metrics2_unfav` | `cockpit2.py:3728` |
| `metrics2_form` | `cockpit2.py:3733` |
| `metrics2_dim` | `cockpit2.py:3739` |
| `metrics2_compare` | `cockpit2.py:3746` |
| `metrics2_formula` | `cockpit2.py:3809` |
| `source_activate` | `cockpit2.py:3792` |
| `source_deactivate` | `cockpit2.py:3801` |
| `link_pursue` | `cockpit2.py:3773` |
| `link_ignore` | `cockpit2.py:3783` |
| `acc_check` | `cockpit2.py:3754` |
| `ai_reply` | `cockpit2.py:2069` |
| `proj_feed` | `cockpit2.py:2080` |
| `checklist_add` | `cockpit2.py:2127` |
| `checklist_remove` | `cockpit2.py:2138` |
| `check_add` | `cockpit2.py:2186` |
| `check_accept` | `cockpit2.py:2203` |
| `check_toggle` | `cockpit2.py:2213` |
| `check_skip` | `cockpit2.py:2235` |
| `check_unskip` | `cockpit2.py:2247` |
| `check_handoff` | `cockpit2.py:2259` |
| `check_remove` | `cockpit2.py:2273` |
| `role_assign` | `cockpit2.py:2283` |
| `role_unassign` | `cockpit2.py:2301` |
| `role_focus` | `cockpit2.py:2320` |
| `radar_approve` | `cockpit2.py:2353` |
| `radar_dismiss` | `cockpit2.py:2363` |
| `radar_promote` | `cockpit2.py:2367` |
| `radar_merge` | `cockpit2.py:2387` |
| `radar_koppel` | `cockpit2.py:2403` |
| `kb_stage_koppel` | `cockpit2.py:2430` |
| `aitask_add` | `cockpit2.py:2468` |
| `aitask_remove` | `cockpit2.py:2499` |
| `skilllink_add` | `cockpit2.py:2527` |
| `means_gap_add` | `cockpit2.py:2557` |
| `persona_skill_add` | `cockpit2.py:2711` |
| `rov2_add` | `cockpit2.py:2726` |
| `rov2_add_to_group` | `cockpit2.py:2738` |
| `rov2_remove` | `cockpit2.py:2750` |
| `rov2_remove_group` | `cockpit2.py:2765` |
| `rov2_setkind` | `cockpit2.py:2783` |
| `rov2_consent` | `cockpit2.py:2796` |
| `rov2_end` | `cockpit2.py:2818` |
| `wo_open` | `cockpit2.py:2842` |
| `wo_close` | `cockpit2.py:2852` |
| `wo_presence` | `cockpit2.py:2868` |
| `wo_present_all` | `cockpit2.py:2879` |
| `vangst_add` | `cockpit2.py:2891` |
| `vangst_tekst` | `cockpit2.py:2939` |
| `vangst_klaar` | `cockpit2.py:2949` |
| `vangst_uitkomst` | `cockpit2.py:2998` |
| `vangst_uitkomst_weg` | `cockpit2.py:2986` |
| `vangst_uitkomst_edit` | `cockpit2.py:2961` |
| `vangst_remove` | `cockpit2.py:2930` |
| `vangst_verwerk` | `cockpit2.py:3114` |
| `wo_checkout` | `cockpit2.py:4048` |
| `noochie_send` | `cockpit2.py:4063` |
| `noochie_reset` | `cockpit2.py:4089` |
| `noochie_ctx` | `cockpit2.py:4096` |
| `cl_add` | `cockpit2.py:4103` |
| `cl_report` | `cockpit2.py:4121` |
| `cl_remove` | `cockpit2.py:4136` |
| `m_add_kpi` | `cockpit2.py:4146` |
| `m_add_from_def` | `cockpit2.py:4178` |
| `def_add` | `cockpit2.py:4193` |
| `catalog_publish` | `cockpit2.py:4215` |
| `def_amend` | `cockpit2.py:4241` |
| `m_add_link` | `cockpit2.py:4283` |
| `m_sample` | `cockpit2.py:4294` |
| `m_remove` | `cockpit2.py:4304` |
| `m_pin` | `cockpit2.py:4314` |
| `m_unpin` | `cockpit2.py:4325` |
| `tile_add` | `cockpit2.py:4363` |
| `indicator_activate` | `cockpit2.py:4335` |
| `tile_remove` | `cockpit2.py:4397` |
| `rov2_set` | `cockpit2.py:4407` |
| `rov2_acc_add` | `cockpit2.py:4407` |
| `rov2_acc_remove` | `cockpit2.py:4407` |
| `rov2_dom_add` | `cockpit2.py:4407` |
| `rov2_dom_remove` | `cockpit2.py:4407` |
| `backlog_add` | `cockpit2.py:4439` |
| `backlog_update_staat` | `cockpit2.py:4451` |
| `backlog_update_prioriteit` | `cockpit2.py:4463` |
| `person_edit` | `cockpit2.py:4475` |
| `person_remove` | `cockpit2.py:4492` |
| `lk_mute` | `cockpit2.py:4513` |
| `claims_term_add` | `cockpit2.py:4616` |
| `claims_term_retract` | `cockpit2.py:4653` |
| `claims_work_status` | `cockpit2.py:4637` |
| `claims_bewijs_link` | `cockpit2.py:4682` |
| `claims_vondst_whitelist` | `cockpit2.py:4706` |
| `claims_regel_uit_vondst` | `cockpit2.py:4732` |
| `claims_to_board` | `cockpit2.py:4764` |
| `persona_edit` | `cockpit2.py:2610` |
| `persona_llm` | `cockpit2.py:2629` |
| `persona_finetune` | `cockpit2.py:2646` |
| `persona_finetune_apply` | `cockpit2.py:2664` |


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
_59 routes · 191 dispatch-acties · 32 stores._
