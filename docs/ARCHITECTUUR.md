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
| `/rapport` | `render_projectrapport` | `nooch_village/views/rapport.py` |
| `/pagina` | `render_pagina` | `nooch_village/views/wiki.py` |
| `/project/nieuw` | `render_wizard` | `nooch_village/views/wizard.py` |
| `/project` | `render_project` | `nooch_village/views/projects.py` |
| `/rolefillers` | `render_rolefillers` | `nooch_village/views/overview.py` |
| `/middelen` | `render_middelen` | `nooch_village/views/overview.py` |
| `/person` | `render_person` | `nooch_village/views/overview.py` |
| `/admin` | `render_admin` | `nooch_village/views/overview.py` |
| `/founder` | `render_founder_flow` | `nooch_village/views/founder_flow.py` |
| `/_patterns` | `render_patterns` | `nooch_village/views/overview.py` |
| `/signals` | `render_signals` | `nooch_village/views/signals.py` |
| `/inbox` | `render_inbox_frag` | `nooch_village/views/inbox.py` |
| `/search` | `render_search_fragment` | `nooch_village/views/search.py` |
| `/skills` | `render_skills` | `nooch_village/views/skills.py` |
| `/goals` | `render_goals` | `nooch_village/views/doelen.py` |
| `/goal` | `render_goal` | `nooch_village/views/doelen.py` |
| `/site-audit` | `render_site_audit` | `nooch_village/views/site_audit.py` |
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
| `ff_beslis` | `cockpit2.py:5843` |
| `ff_cluster` | `cockpit2.py:5971` |
| `ff_promote` | `cockpit2.py:5901` |
| `ff_demote` | `cockpit2.py:5925` |
| `ff_run` | `cockpit2.py:5944` |
| `kb_new` | `cockpit2.py:5193` |
| `kb_intake` | `cockpit2.py:5275` |
| `kb_intake_url` | `cockpit2.py:5292` |
| `kb_stage_edit` | `cockpit2.py:5311` |
| `kb_stage_accept` | `cockpit2.py:5323` |
| `kb_stage_delete` | `cockpit2.py:5342` |
| `kb_stage_merge` | `cockpit2.py:5348` |
| `kb_stage_commit` | `cockpit2.py:5359` |
| `kb_stage_discard` | `cockpit2.py:5379` |
| `kb_atoom_subject` | `cockpit2.py:5634` |
| `kb_atoom_purge` | `cockpit2.py:5618` |
| `tag_voorstel_besluit` | `cockpit2.py:5455` |
| `tag_onderhoud_run` | `cockpit2.py:5605` |
| `copy_stack_inclusie` | `cockpit2.py:5587` |
| `verzoek_besluit` | `cockpit2.py:5474` |
| `kb_blacklist_leeg` | `cockpit2.py:5627` |
| `kb_atoom_edit` | `cockpit2.py:5385` |
| `kb_atoom_related` | `cockpit2.py:5392` |
| `kb_atoom_reference` | `cockpit2.py:5437` |
| `kb_insight_link` | `cockpit2.py:5404` |
| `kb_insight_unlink` | `cockpit2.py:5411` |
| `kb_meta_start` | `cockpit2.py:5417` |
| `kb_atoom_merge` | `cockpit2.py:5645` |
| `kb_atoom_archive` | `cockpit2.py:5666` |
| `kb_atoom_unarchive` | `cockpit2.py:5675` |
| `kb_atoom_naar_spel` | `cockpit2.py:5681` |
| `kb_spel_start` | `cockpit2.py:5702` |
| `kb_spel_add` | `cockpit2.py:5716` |
| `kb_spel_remove` | `cockpit2.py:5726` |
| `kb_spel_flip` | `cockpit2.py:5733` |
| `kb_spel_finish` | `cockpit2.py:5739` |
| `kb_link` | `cockpit2.py:5202` |
| `kb_unlink` | `cockpit2.py:5216` |
| `kb_annotate` | `cockpit2.py:5227` |
| `kb_evidence` | `cockpit2.py:5233` |
| `kb_discuss` | `cockpit2.py:5254` |
| `kb_reformulate` | `cockpit2.py:5260` |
| `kw_nominate` | `cockpit2.py:5750` |
| `kw_nom_accept` | `cockpit2.py:5761` |
| `kw_nom_reject` | `cockpit2.py:5779` |
| `ws_forbid` | `cockpit2.py:5822` |
| `ws_approve` | `cockpit2.py:5827` |
| `proj_add` | `cockpit2.py:1247` |
| `artefact_add` | `cockpit2.py:1300` |
| `artefact_edit` | `cockpit2.py:1344` |
| `artefact_archive` | `cockpit2.py:1371` |
| `pagina_feit_add` | `cockpit2.py:1391` |
| `pagina_feit_del` | `cockpit2.py:1420` |
| `pagina_voorstel` | `cockpit2.py:1451` |
| `proj_status` | `cockpit2.py:1481` |
| `proj_done` | `cockpit2.py:1512` |
| `proj_dod` | `cockpit2.py:1607` |
| `proj_archive` | `cockpit2.py:1644` |
| `proj_unarchive` | `cockpit2.py:1652` |
| `proj_delete` | `cockpit2.py:1688` |
| `proj_edit` | `cockpit2.py:1715` |
| `proj_comment` | `cockpit2.py:1728` |
| `proj_rename` | `cockpit2.py:1739` |
| `proj_describe` | `cockpit2.py:1750` |
| `proj_doc_edit` | `cockpit2.py:1888` |
| `verslag_bevestig_behaald` | `cockpit2.py:1828` |
| `verslag_bevestig_niet_behaald` | `cockpit2.py:1834` |
| `verslag_overslaan` | `cockpit2.py:1839` |
| `verslag_bijwerken` | `cockpit2.py:1866` |
| `proj_regen_doc` | `cockpit2.py:1761` |
| `proj_settrekker` | `cockpit2.py:1901` |
| `proj_setowner` | `cockpit2.py:1942` |
| `proj_approve` | `cockpit2.py:1961` |
| `proj_discard` | `cockpit2.py:1972` |
| `proj_proposal_accept` | `cockpit2.py:1983` |
| `proj_proposal_reject` | `cockpit2.py:1996` |
| `proj_setlabel` | `cockpit2.py:2009` |
| `proj_setimpact` | `cockpit2.py:2024` |
| `proj_seteffort` | `cockpit2.py:2054` |
| `proj_agendeer_verzwakt` | `cockpit2.py:2072` |
| `proj_setprivate` | `cockpit2.py:2096` |
| `proj_setdue` | `cockpit2.py:2107` |
| `proj_goal` | `cockpit2.py:2118` |
| `proj_depends` | `cockpit2.py:2133` |
| `goal_add` | `cockpit2.py:2150` |
| `goal_edit` | `cockpit2.py:2164` |
| `goal_link` | `cockpit2.py:2178` |
| `attach_add` | `cockpit2.py:2195` |
| `attach_remove` | `cockpit2.py:2206` |
| `react_add` | `cockpit2.py:2216` |
| `feed_edit` | `cockpit2.py:2227` |
| `feed_remove` | `cockpit2.py:2238` |
| `wall_outcome` | `cockpit2.py:3866` |
| `notif_read` | `cockpit2.py:3962` |
| `notif_processed` | `cockpit2.py:3972` |
| `notif_outcome` | `cockpit2.py:4288` |
| `notif_klaar` | `cockpit2.py:4229` |
| `goedkeur` | `cockpit2.py:3981` |
| `notif_delete` | `cockpit2.py:4026` |
| `notif_add` | `cockpit2.py:4177` |
| `notif_archive` | `cockpit2.py:4410` |
| `metrics2_fav` | `cockpit2.py:4037` |
| `metrics2_unfav` | `cockpit2.py:4052` |
| `metrics2_form` | `cockpit2.py:4057` |
| `metrics2_dim` | `cockpit2.py:4064` |
| `metrics2_compare` | `cockpit2.py:4072` |
| `metrics2_formula` | `cockpit2.py:4162` |
| `source_activate` | `cockpit2.py:4138` |
| `source_deactivate` | `cockpit2.py:4150` |
| `link_pursue` | `cockpit2.py:4112` |
| `link_ignore` | `cockpit2.py:4123` |
| `acc_check` | `cockpit2.py:4081` |
| `ai_reply` | `cockpit2.py:2248` |
| `proj_feed` | `cockpit2.py:2260` |
| `checklist_add` | `cockpit2.py:2308` |
| `checklist_remove` | `cockpit2.py:2348` |
| `plan_akkoord` | `cockpit2.py:2331` |
| `checklist_uitvoer` | `cockpit2.py:2319` |
| `check_add` | `cockpit2.py:2398` |
| `check_accept` | `cockpit2.py:2415` |
| `check_toggle` | `cockpit2.py:2425` |
| `check_skip` | `cockpit2.py:2447` |
| `check_unskip` | `cockpit2.py:2459` |
| `check_handoff` | `cockpit2.py:2480` |
| `check_remove` | `cockpit2.py:2528` |
| `check_rename` | `cockpit2.py:2538` |
| `check_move` | `cockpit2.py:2557` |
| `role_assign` | `cockpit2.py:2571` |
| `role_unassign` | `cockpit2.py:2596` |
| `role_focus` | `cockpit2.py:2618` |
| `radar_approve` | `cockpit2.py:2651` |
| `radar_dismiss` | `cockpit2.py:2661` |
| `radar_promote` | `cockpit2.py:2665` |
| `radar_merge` | `cockpit2.py:2685` |
| `radar_koppel` | `cockpit2.py:2701` |
| `kb_stage_koppel` | `cockpit2.py:2728` |
| `middel_remove` | `cockpit2.py:2776` |
| `skilllink_add` | `cockpit2.py:2807` |
| `means_gap_add` | `cockpit2.py:2837` |
| `rov2_add` | `cockpit2.py:2991` |
| `rov2_add_to_group` | `cockpit2.py:3003` |
| `rov2_remove` | `cockpit2.py:3015` |
| `rov2_remove_group` | `cockpit2.py:3030` |
| `rov2_setkind` | `cockpit2.py:3048` |
| `rov2_consent` | `cockpit2.py:3061` |
| `rov2_end` | `cockpit2.py:3083` |
| `wo_open` | `cockpit2.py:3107` |
| `wo_close` | `cockpit2.py:3117` |
| `wo_presence` | `cockpit2.py:3133` |
| `wo_present_all` | `cockpit2.py:3144` |
| `vangst_add` | `cockpit2.py:3156` |
| `vangst_tekst` | `cockpit2.py:3204` |
| `vangst_klaar` | `cockpit2.py:3214` |
| `vangst_uitkomst` | `cockpit2.py:3263` |
| `vangst_uitkomst_weg` | `cockpit2.py:3251` |
| `vangst_uitkomst_edit` | `cockpit2.py:3226` |
| `vangst_remove` | `cockpit2.py:3195` |
| `vangst_verwerk` | `cockpit2.py:3379` |
| `wo_checkout` | `cockpit2.py:4419` |
| `noochie_send` | `cockpit2.py:4434` |
| `noochie_reset` | `cockpit2.py:4461` |
| `noochie_ctx` | `cockpit2.py:4469` |
| `cl_add` | `cockpit2.py:4477` |
| `cl_report` | `cockpit2.py:4495` |
| `cl_remove` | `cockpit2.py:4510` |
| `m_add_kpi` | `cockpit2.py:4520` |
| `m_add_from_def` | `cockpit2.py:4552` |
| `def_add` | `cockpit2.py:4567` |
| `catalog_publish` | `cockpit2.py:4589` |
| `def_amend` | `cockpit2.py:4615` |
| `m_add_link` | `cockpit2.py:4657` |
| `m_sample` | `cockpit2.py:4668` |
| `m_remove` | `cockpit2.py:4678` |
| `m_pin` | `cockpit2.py:4688` |
| `m_unpin` | `cockpit2.py:4699` |
| `tile_add` | `cockpit2.py:4737` |
| `indicator_activate` | `cockpit2.py:4709` |
| `tile_remove` | `cockpit2.py:4771` |
| `rov2_set` | `cockpit2.py:4781` |
| `rov2_acc_add` | `cockpit2.py:4781` |
| `rov2_acc_remove` | `cockpit2.py:4781` |
| `rov2_dom_add` | `cockpit2.py:4781` |
| `rov2_dom_remove` | `cockpit2.py:4781` |
| `person_edit` | `cockpit2.py:4813` |
| `person_remove` | `cockpit2.py:4830` |
| `lk_mute` | `cockpit2.py:4851` |
| `claims_term_add` | `cockpit2.py:4981` |
| `claims_term_retract` | `cockpit2.py:5018` |
| `claims_work_status` | `cockpit2.py:5002` |
| `claims_bewijs_link` | `cockpit2.py:5047` |
| `claims_vondst_whitelist` | `cockpit2.py:5071` |
| `claims_regel_uit_vondst` | `cockpit2.py:5097` |
| `claims_to_board` | `cockpit2.py:5129` |
| `persona_edit` | `cockpit2.py:2890` |
| `persona_llm` | `cockpit2.py:2909` |
| `persona_finetune` | `cockpit2.py:2926` |
| `persona_finetune_apply` | `cockpit2.py:2944` |


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
| `notif` | `NotifStore` | `notifications.json` |
| `agenda` | `Agenda` | `roloverleg_agenda.json` |
| `noochie` | `NoochieStore` | `noochie.json` |
| `checklists` | `ChecklistStore` | `checklists.json` |
| `metrics` | `MetricStore` | `metrics.json` |
| `defs` | `DefinitionStore` | `definitions.json` |
| `werk` | `WerkoverlegStore` | `werkoverleg.json` |
| `strategies` | `StrategyStore` | `strategies.json` |
| `doelen` | `DoelStore` | `doelen.json` |
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
_61 routes · 197 dispatch-acties · 31 stores._
