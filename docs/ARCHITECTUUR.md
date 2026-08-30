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
| `ff_beslis` | `cockpit2.py:4966` |
| `ff_cluster` | `cockpit2.py:5094` |
| `ff_promote` | `cockpit2.py:5024` |
| `ff_demote` | `cockpit2.py:5048` |
| `ff_run` | `cockpit2.py:5067` |
| `kb_new` | `cockpit2.py:4346` |
| `kb_intake` | `cockpit2.py:4428` |
| `kb_intake_url` | `cockpit2.py:4445` |
| `kb_stage_edit` | `cockpit2.py:4464` |
| `kb_stage_accept` | `cockpit2.py:4476` |
| `kb_stage_delete` | `cockpit2.py:4495` |
| `kb_stage_merge` | `cockpit2.py:4501` |
| `kb_stage_commit` | `cockpit2.py:4512` |
| `kb_stage_discard` | `cockpit2.py:4532` |
| `kb_atoom_subject` | `cockpit2.py:4770` |
| `kb_atoom_purge` | `cockpit2.py:4754` |
| `tag_voorstel_besluit` | `cockpit2.py:4608` |
| `tag_onderhoud_run` | `cockpit2.py:4741` |
| `copy_stack_inclusie` | `cockpit2.py:4723` |
| `verzoek_besluit` | `cockpit2.py:4627` |
| `kb_blacklist_leeg` | `cockpit2.py:4763` |
| `kb_atoom_edit` | `cockpit2.py:4538` |
| `kb_atoom_related` | `cockpit2.py:4545` |
| `kb_atoom_reference` | `cockpit2.py:4590` |
| `kb_insight_link` | `cockpit2.py:4557` |
| `kb_insight_unlink` | `cockpit2.py:4564` |
| `kb_meta_start` | `cockpit2.py:4570` |
| `kb_atoom_merge` | `cockpit2.py:4781` |
| `kb_atoom_archive` | `cockpit2.py:4802` |
| `kb_atoom_unarchive` | `cockpit2.py:4811` |
| `kb_atoom_naar_spel` | `cockpit2.py:4817` |
| `kb_spel_start` | `cockpit2.py:4838` |
| `kb_spel_add` | `cockpit2.py:4852` |
| `kb_spel_remove` | `cockpit2.py:4862` |
| `kb_spel_flip` | `cockpit2.py:4869` |
| `kb_spel_finish` | `cockpit2.py:4875` |
| `kb_link` | `cockpit2.py:4355` |
| `kb_unlink` | `cockpit2.py:4369` |
| `kb_annotate` | `cockpit2.py:4380` |
| `kb_evidence` | `cockpit2.py:4386` |
| `kb_discuss` | `cockpit2.py:4407` |
| `kb_reformulate` | `cockpit2.py:4413` |
| `kw_nominate` | `cockpit2.py:4886` |
| `kw_nom_accept` | `cockpit2.py:4897` |
| `kw_nom_reject` | `cockpit2.py:4915` |
| `ws_forbid` | `cockpit2.py:4945` |
| `ws_approve` | `cockpit2.py:4950` |
| `proj_add` | `cockpit2.py:1206` |
| `artefact_add` | `cockpit2.py:1250` |
| `artefact_edit` | `cockpit2.py:1294` |
| `artefact_archive` | `cockpit2.py:1321` |
| `pagina_feit_add` | `cockpit2.py:1341` |
| `pagina_feit_del` | `cockpit2.py:1370` |
| `pagina_voorstel` | `cockpit2.py:1401` |
| `proj_status` | `cockpit2.py:1431` |
| `proj_done` | `cockpit2.py:1449` |
| `proj_dod` | `cockpit2.py:1504` |
| `proj_archive` | `cockpit2.py:1518` |
| `proj_unarchive` | `cockpit2.py:1541` |
| `proj_delete` | `cockpit2.py:1551` |
| `proj_edit` | `cockpit2.py:1578` |
| `proj_comment` | `cockpit2.py:1591` |
| `proj_rename` | `cockpit2.py:1601` |
| `proj_describe` | `cockpit2.py:1612` |
| `proj_doc_edit` | `cockpit2.py:1645` |
| `proj_regen_doc` | `cockpit2.py:1623` |
| `proj_settrekker` | `cockpit2.py:1658` |
| `proj_setowner` | `cockpit2.py:1695` |
| `proj_approve` | `cockpit2.py:1714` |
| `proj_discard` | `cockpit2.py:1725` |
| `proj_proposal_accept` | `cockpit2.py:1736` |
| `proj_proposal_reject` | `cockpit2.py:1749` |
| `proj_setlabel` | `cockpit2.py:1762` |
| `proj_setimpact` | `cockpit2.py:1777` |
| `proj_seteffort` | `cockpit2.py:1796` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1819` |
| `proj_setprivate` | `cockpit2.py:1843` |
| `proj_setdue` | `cockpit2.py:1854` |
| `attach_add` | `cockpit2.py:1865` |
| `attach_remove` | `cockpit2.py:1876` |
| `react_add` | `cockpit2.py:1886` |
| `feed_edit` | `cockpit2.py:1896` |
| `feed_remove` | `cockpit2.py:1906` |
| `wall_outcome` | `cockpit2.py:3174` |
| `notif_read` | `cockpit2.py:3270` |
| `notif_processed` | `cockpit2.py:3275` |
| `notif_outcome` | `cockpit2.py:3428` |
| `notif_besluit` | `cockpit2.py:3519` |
| `notif_klaar` | `cockpit2.py:3408` |
| `notif_delete` | `cockpit2.py:3280` |
| `notif_add` | `cockpit2.py:3392` |
| `notif_archive` | `cockpit2.py:3561` |
| `metrics2_fav` | `cockpit2.py:3286` |
| `metrics2_unfav` | `cockpit2.py:3296` |
| `metrics2_form` | `cockpit2.py:3301` |
| `metrics2_dim` | `cockpit2.py:3307` |
| `metrics2_compare` | `cockpit2.py:3314` |
| `metrics2_formula` | `cockpit2.py:3377` |
| `source_activate` | `cockpit2.py:3360` |
| `source_deactivate` | `cockpit2.py:3369` |
| `link_pursue` | `cockpit2.py:3341` |
| `link_ignore` | `cockpit2.py:3351` |
| `acc_check` | `cockpit2.py:3322` |
| `ai_reply` | `cockpit2.py:1915` |
| `proj_feed` | `cockpit2.py:1926` |
| `checklist_add` | `cockpit2.py:1967` |
| `checklist_remove` | `cockpit2.py:1978` |
| `check_add` | `cockpit2.py:2026` |
| `check_accept` | `cockpit2.py:2043` |
| `check_toggle` | `cockpit2.py:2053` |
| `check_skip` | `cockpit2.py:2075` |
| `check_unskip` | `cockpit2.py:2087` |
| `check_handoff` | `cockpit2.py:2099` |
| `check_remove` | `cockpit2.py:2113` |
| `role_assign` | `cockpit2.py:2123` |
| `role_unassign` | `cockpit2.py:2141` |
| `role_focus` | `cockpit2.py:2160` |
| `radar_approve` | `cockpit2.py:2193` |
| `radar_dismiss` | `cockpit2.py:2203` |
| `radar_promote` | `cockpit2.py:2207` |
| `radar_merge` | `cockpit2.py:2227` |
| `radar_koppel` | `cockpit2.py:2243` |
| `kb_stage_koppel` | `cockpit2.py:2270` |
| `aitask_add` | `cockpit2.py:2308` |
| `aitask_remove` | `cockpit2.py:2339` |
| `skilllink_add` | `cockpit2.py:2367` |
| `means_gap_add` | `cockpit2.py:2397` |
| `persona_skill_add` | `cockpit2.py:2551` |
| `rov2_add` | `cockpit2.py:2566` |
| `rov2_add_to_group` | `cockpit2.py:2578` |
| `rov2_remove` | `cockpit2.py:2590` |
| `rov2_remove_group` | `cockpit2.py:2605` |
| `rov2_setkind` | `cockpit2.py:2623` |
| `rov2_consent` | `cockpit2.py:2636` |
| `rov2_end` | `cockpit2.py:2658` |
| `wo_open` | `cockpit2.py:2682` |
| `wo_close` | `cockpit2.py:2692` |
| `wo_presence` | `cockpit2.py:2708` |
| `wo_present_all` | `cockpit2.py:2719` |
| `vangst_add` | `cockpit2.py:2731` |
| `vangst_tekst` | `cockpit2.py:2779` |
| `vangst_klaar` | `cockpit2.py:2789` |
| `vangst_uitkomst` | `cockpit2.py:2838` |
| `vangst_uitkomst_weg` | `cockpit2.py:2826` |
| `vangst_uitkomst_edit` | `cockpit2.py:2801` |
| `vangst_remove` | `cockpit2.py:2770` |
| `vangst_verwerk` | `cockpit2.py:2954` |
| `wo_checkout` | `cockpit2.py:3566` |
| `noochie_send` | `cockpit2.py:3581` |
| `noochie_reset` | `cockpit2.py:3607` |
| `noochie_ctx` | `cockpit2.py:3614` |
| `cl_add` | `cockpit2.py:3621` |
| `cl_report` | `cockpit2.py:3639` |
| `cl_remove` | `cockpit2.py:3654` |
| `m_add_kpi` | `cockpit2.py:3664` |
| `m_add_from_def` | `cockpit2.py:3696` |
| `def_add` | `cockpit2.py:3711` |
| `catalog_publish` | `cockpit2.py:3733` |
| `def_amend` | `cockpit2.py:3759` |
| `m_add_link` | `cockpit2.py:3801` |
| `m_sample` | `cockpit2.py:3812` |
| `m_remove` | `cockpit2.py:3822` |
| `m_pin` | `cockpit2.py:3832` |
| `m_unpin` | `cockpit2.py:3843` |
| `tile_add` | `cockpit2.py:3881` |
| `indicator_activate` | `cockpit2.py:3853` |
| `tile_remove` | `cockpit2.py:3915` |
| `rov2_set` | `cockpit2.py:3925` |
| `rov2_acc_add` | `cockpit2.py:3925` |
| `rov2_acc_remove` | `cockpit2.py:3925` |
| `rov2_dom_add` | `cockpit2.py:3925` |
| `rov2_dom_remove` | `cockpit2.py:3925` |
| `backlog_add` | `cockpit2.py:3957` |
| `backlog_update_staat` | `cockpit2.py:3969` |
| `backlog_update_prioriteit` | `cockpit2.py:3981` |
| `person_edit` | `cockpit2.py:3993` |
| `person_remove` | `cockpit2.py:4010` |
| `lk_mute` | `cockpit2.py:4031` |
| `claims_term_add` | `cockpit2.py:4134` |
| `claims_term_retract` | `cockpit2.py:4171` |
| `claims_work_status` | `cockpit2.py:4155` |
| `claims_bewijs_link` | `cockpit2.py:4200` |
| `claims_vondst_whitelist` | `cockpit2.py:4224` |
| `claims_regel_uit_vondst` | `cockpit2.py:4250` |
| `claims_to_board` | `cockpit2.py:4282` |
| `persona_edit` | `cockpit2.py:2450` |
| `persona_llm` | `cockpit2.py:2469` |
| `persona_finetune` | `cockpit2.py:2486` |
| `persona_finetune_apply` | `cockpit2.py:2504` |


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
