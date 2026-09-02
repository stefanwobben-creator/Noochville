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
| `ff_beslis` | `cockpit2.py:5202` |
| `ff_cluster` | `cockpit2.py:5330` |
| `ff_promote` | `cockpit2.py:5260` |
| `ff_demote` | `cockpit2.py:5284` |
| `ff_run` | `cockpit2.py:5303` |
| `kb_new` | `cockpit2.py:4565` |
| `kb_intake` | `cockpit2.py:4647` |
| `kb_intake_url` | `cockpit2.py:4664` |
| `kb_stage_edit` | `cockpit2.py:4683` |
| `kb_stage_accept` | `cockpit2.py:4695` |
| `kb_stage_delete` | `cockpit2.py:4714` |
| `kb_stage_merge` | `cockpit2.py:4720` |
| `kb_stage_commit` | `cockpit2.py:4731` |
| `kb_stage_discard` | `cockpit2.py:4751` |
| `kb_atoom_subject` | `cockpit2.py:5006` |
| `kb_atoom_purge` | `cockpit2.py:4990` |
| `tag_voorstel_besluit` | `cockpit2.py:4827` |
| `tag_onderhoud_run` | `cockpit2.py:4977` |
| `copy_stack_inclusie` | `cockpit2.py:4959` |
| `verzoek_besluit` | `cockpit2.py:4846` |
| `kb_blacklist_leeg` | `cockpit2.py:4999` |
| `kb_atoom_edit` | `cockpit2.py:4757` |
| `kb_atoom_related` | `cockpit2.py:4764` |
| `kb_atoom_reference` | `cockpit2.py:4809` |
| `kb_insight_link` | `cockpit2.py:4776` |
| `kb_insight_unlink` | `cockpit2.py:4783` |
| `kb_meta_start` | `cockpit2.py:4789` |
| `kb_atoom_merge` | `cockpit2.py:5017` |
| `kb_atoom_archive` | `cockpit2.py:5038` |
| `kb_atoom_unarchive` | `cockpit2.py:5047` |
| `kb_atoom_naar_spel` | `cockpit2.py:5053` |
| `kb_spel_start` | `cockpit2.py:5074` |
| `kb_spel_add` | `cockpit2.py:5088` |
| `kb_spel_remove` | `cockpit2.py:5098` |
| `kb_spel_flip` | `cockpit2.py:5105` |
| `kb_spel_finish` | `cockpit2.py:5111` |
| `kb_link` | `cockpit2.py:4574` |
| `kb_unlink` | `cockpit2.py:4588` |
| `kb_annotate` | `cockpit2.py:4599` |
| `kb_evidence` | `cockpit2.py:4605` |
| `kb_discuss` | `cockpit2.py:4626` |
| `kb_reformulate` | `cockpit2.py:4632` |
| `kw_nominate` | `cockpit2.py:5122` |
| `kw_nom_accept` | `cockpit2.py:5133` |
| `kw_nom_reject` | `cockpit2.py:5151` |
| `ws_forbid` | `cockpit2.py:5181` |
| `ws_approve` | `cockpit2.py:5186` |
| `proj_add` | `cockpit2.py:1208` |
| `artefact_add` | `cockpit2.py:1252` |
| `artefact_edit` | `cockpit2.py:1296` |
| `artefact_archive` | `cockpit2.py:1323` |
| `pagina_feit_add` | `cockpit2.py:1343` |
| `pagina_feit_del` | `cockpit2.py:1372` |
| `pagina_voorstel` | `cockpit2.py:1403` |
| `proj_status` | `cockpit2.py:1433` |
| `proj_done` | `cockpit2.py:1451` |
| `proj_dod` | `cockpit2.py:1506` |
| `proj_archive` | `cockpit2.py:1520` |
| `proj_unarchive` | `cockpit2.py:1543` |
| `proj_delete` | `cockpit2.py:1553` |
| `proj_edit` | `cockpit2.py:1580` |
| `proj_comment` | `cockpit2.py:1593` |
| `proj_rename` | `cockpit2.py:1603` |
| `proj_describe` | `cockpit2.py:1614` |
| `proj_doc_edit` | `cockpit2.py:1647` |
| `proj_regen_doc` | `cockpit2.py:1625` |
| `proj_settrekker` | `cockpit2.py:1660` |
| `proj_setowner` | `cockpit2.py:1697` |
| `proj_approve` | `cockpit2.py:1716` |
| `proj_discard` | `cockpit2.py:1727` |
| `proj_proposal_accept` | `cockpit2.py:1738` |
| `proj_proposal_reject` | `cockpit2.py:1751` |
| `proj_setlabel` | `cockpit2.py:1764` |
| `proj_setimpact` | `cockpit2.py:1779` |
| `proj_seteffort` | `cockpit2.py:1798` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1821` |
| `proj_setprivate` | `cockpit2.py:1845` |
| `proj_setdue` | `cockpit2.py:1856` |
| `attach_add` | `cockpit2.py:1867` |
| `attach_remove` | `cockpit2.py:1878` |
| `react_add` | `cockpit2.py:1888` |
| `feed_edit` | `cockpit2.py:1898` |
| `feed_remove` | `cockpit2.py:1908` |
| `wall_outcome` | `cockpit2.py:3348` |
| `notif_read` | `cockpit2.py:3444` |
| `notif_processed` | `cockpit2.py:3449` |
| `notif_outcome` | `cockpit2.py:3668` |
| `notif_klaar` | `cockpit2.py:3615` |
| `notif_delete` | `cockpit2.py:3454` |
| `notif_add` | `cockpit2.py:3566` |
| `notif_archive` | `cockpit2.py:3780` |
| `metrics2_fav` | `cockpit2.py:3460` |
| `metrics2_unfav` | `cockpit2.py:3470` |
| `metrics2_form` | `cockpit2.py:3475` |
| `metrics2_dim` | `cockpit2.py:3481` |
| `metrics2_compare` | `cockpit2.py:3488` |
| `metrics2_formula` | `cockpit2.py:3551` |
| `source_activate` | `cockpit2.py:3534` |
| `source_deactivate` | `cockpit2.py:3543` |
| `link_pursue` | `cockpit2.py:3515` |
| `link_ignore` | `cockpit2.py:3525` |
| `acc_check` | `cockpit2.py:3496` |
| `ai_reply` | `cockpit2.py:1917` |
| `proj_feed` | `cockpit2.py:1928` |
| `checklist_add` | `cockpit2.py:1975` |
| `checklist_remove` | `cockpit2.py:1986` |
| `check_add` | `cockpit2.py:2034` |
| `check_accept` | `cockpit2.py:2051` |
| `check_toggle` | `cockpit2.py:2061` |
| `check_skip` | `cockpit2.py:2083` |
| `check_unskip` | `cockpit2.py:2095` |
| `check_handoff` | `cockpit2.py:2107` |
| `check_remove` | `cockpit2.py:2121` |
| `role_assign` | `cockpit2.py:2131` |
| `role_unassign` | `cockpit2.py:2149` |
| `role_focus` | `cockpit2.py:2168` |
| `radar_approve` | `cockpit2.py:2201` |
| `radar_dismiss` | `cockpit2.py:2211` |
| `radar_promote` | `cockpit2.py:2215` |
| `radar_merge` | `cockpit2.py:2235` |
| `radar_koppel` | `cockpit2.py:2251` |
| `kb_stage_koppel` | `cockpit2.py:2278` |
| `aitask_add` | `cockpit2.py:2316` |
| `aitask_remove` | `cockpit2.py:2347` |
| `skilllink_add` | `cockpit2.py:2375` |
| `means_gap_add` | `cockpit2.py:2405` |
| `persona_skill_add` | `cockpit2.py:2559` |
| `rov2_add` | `cockpit2.py:2574` |
| `rov2_add_to_group` | `cockpit2.py:2586` |
| `rov2_remove` | `cockpit2.py:2598` |
| `rov2_remove_group` | `cockpit2.py:2613` |
| `rov2_setkind` | `cockpit2.py:2631` |
| `rov2_consent` | `cockpit2.py:2644` |
| `rov2_end` | `cockpit2.py:2666` |
| `wo_open` | `cockpit2.py:2690` |
| `wo_close` | `cockpit2.py:2700` |
| `wo_presence` | `cockpit2.py:2716` |
| `wo_present_all` | `cockpit2.py:2727` |
| `vangst_add` | `cockpit2.py:2739` |
| `vangst_tekst` | `cockpit2.py:2787` |
| `vangst_klaar` | `cockpit2.py:2797` |
| `vangst_uitkomst` | `cockpit2.py:2846` |
| `vangst_uitkomst_weg` | `cockpit2.py:2834` |
| `vangst_uitkomst_edit` | `cockpit2.py:2809` |
| `vangst_remove` | `cockpit2.py:2778` |
| `vangst_verwerk` | `cockpit2.py:2962` |
| `wo_checkout` | `cockpit2.py:3785` |
| `noochie_send` | `cockpit2.py:3800` |
| `noochie_reset` | `cockpit2.py:3826` |
| `noochie_ctx` | `cockpit2.py:3833` |
| `cl_add` | `cockpit2.py:3840` |
| `cl_report` | `cockpit2.py:3858` |
| `cl_remove` | `cockpit2.py:3873` |
| `m_add_kpi` | `cockpit2.py:3883` |
| `m_add_from_def` | `cockpit2.py:3915` |
| `def_add` | `cockpit2.py:3930` |
| `catalog_publish` | `cockpit2.py:3952` |
| `def_amend` | `cockpit2.py:3978` |
| `m_add_link` | `cockpit2.py:4020` |
| `m_sample` | `cockpit2.py:4031` |
| `m_remove` | `cockpit2.py:4041` |
| `m_pin` | `cockpit2.py:4051` |
| `m_unpin` | `cockpit2.py:4062` |
| `tile_add` | `cockpit2.py:4100` |
| `indicator_activate` | `cockpit2.py:4072` |
| `tile_remove` | `cockpit2.py:4134` |
| `rov2_set` | `cockpit2.py:4144` |
| `rov2_acc_add` | `cockpit2.py:4144` |
| `rov2_acc_remove` | `cockpit2.py:4144` |
| `rov2_dom_add` | `cockpit2.py:4144` |
| `rov2_dom_remove` | `cockpit2.py:4144` |
| `backlog_add` | `cockpit2.py:4176` |
| `backlog_update_staat` | `cockpit2.py:4188` |
| `backlog_update_prioriteit` | `cockpit2.py:4200` |
| `person_edit` | `cockpit2.py:4212` |
| `person_remove` | `cockpit2.py:4229` |
| `lk_mute` | `cockpit2.py:4250` |
| `claims_term_add` | `cockpit2.py:4353` |
| `claims_term_retract` | `cockpit2.py:4390` |
| `claims_work_status` | `cockpit2.py:4374` |
| `claims_bewijs_link` | `cockpit2.py:4419` |
| `claims_vondst_whitelist` | `cockpit2.py:4443` |
| `claims_regel_uit_vondst` | `cockpit2.py:4469` |
| `claims_to_board` | `cockpit2.py:4501` |
| `persona_edit` | `cockpit2.py:2458` |
| `persona_llm` | `cockpit2.py:2477` |
| `persona_finetune` | `cockpit2.py:2494` |
| `persona_finetune_apply` | `cockpit2.py:2512` |


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
_58 routes · 188 dispatch-acties · 32 stores._
